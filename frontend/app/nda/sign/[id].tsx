import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, Image, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';

export default function NDASignPage() {
  const { id } = useLocalSearchParams();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [phase, setPhase] = useState<'verify' | 'read' | 'sign' | 'done'>('verify');
  const [loading, setLoading] = useState(true);
  const [ndaInfo, setNdaInfo] = useState<any>(null);
  const [ndaFull, setNdaFull] = useState<any>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Verify form
  const [verifyEmail, setVerifyEmail] = useState('');
  const [verifyPhone, setVerifyPhone] = useState('');
  const [verifyError, setVerifyError] = useState('');

  // Sign form
  const [sigName, setSigName] = useState('');
  const [sigTitle, setSigTitle] = useState('');
  const [sigCompany, setSigCompany] = useState('');
  const [signatureData, setSignatureData] = useState('');
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(false);

  useEffect(() => {
    loadNDAInfo();
  }, [id]);

  const loadNDAInfo = async () => {
    try {
      const res = await api.get(`/nda/sign/${id}`);
      setNdaInfo(res.data);
      if (res.data.status === 'signed') {
        setPhase('done');
      }
    } catch (err) {
      setError('This NDA link is invalid or has expired.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!verifyEmail.trim() || !verifyPhone.trim()) {
      setVerifyError('Please enter both your email and phone number.');
      return;
    }
    setVerifyError('');
    setSubmitting(true);
    try {
      const res = await api.post(`/nda/sign/${id}/verify`, {
        email: verifyEmail.trim(),
        phone: verifyPhone.trim(),
      });
      setNdaFull(res.data);
      setSigName(res.data.recipient?.name || '');
      setPhase('read');
    } catch (err: any) {
      setVerifyError(err.response?.data?.detail || 'Verification failed. Check your email and phone number.');
    } finally {
      setSubmitting(false);
    }
  };

  const initCanvas = () => {
    if (Platform.OS !== 'web') return;
    setTimeout(() => {
      const canvas = document.getElementById('sig-canvas-recipient') as HTMLCanvasElement;
      if (!canvas) return;
      canvasRef.current = canvas;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 2.5;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
      }
    }, 100);
  };

  const handleMouseDown = (e: any) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setIsDrawing(true);
    setHasDrawn(true);
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX || e.touches?.[0]?.clientX) - rect.left;
    const y = (e.clientY || e.touches?.[0]?.clientY) - rect.top;
    ctx?.beginPath();
    ctx?.moveTo(x, y);
  };

  const handleMouseMove = (e: any) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX || e.touches?.[0]?.clientX) - rect.left;
    const y = (e.clientY || e.touches?.[0]?.clientY) - rect.top;
    ctx?.lineTo(x, y);
    ctx?.stroke();
  };

  const handleMouseUp = () => {
    setIsDrawing(false);
    const canvas = canvasRef.current;
    if (canvas) setSignatureData(canvas.toDataURL('image/png'));
  };

  const clearSig = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
    setSignatureData('');
    setHasDrawn(false);
  };

  const handleSubmitSignature = async () => {
    if (!sigName.trim() || !sigTitle.trim() || !sigCompany.trim()) {
      setVerifyError('Please fill in all fields.');
      return;
    }
    if (!hasDrawn || !signatureData) {
      setVerifyError('Please draw your signature.');
      return;
    }
    setVerifyError('');
    setSubmitting(true);
    try {
      await api.post(`/nda/sign/${id}/submit`, {
        name: sigName.trim(),
        title: sigTitle.trim(),
        company: sigCompany.trim(),
        email: verifyEmail.trim(),
        signature: signatureData,
        signature_type: 'drawn',
      });
      setPhase('done');
    } catch (err: any) {
      setVerifyError(err.response?.data?.detail || 'Failed to submit signature.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading agreement...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="alert-circle" size={64} color="#FF3B30" />
        <Text style={styles.errorTitle}>Invalid Link</Text>
        <Text style={styles.errorSub}>{error}</Text>
      </View>
    );
  }

  // ===================== VERIFY PHASE =====================
  if (phase === 'verify') {
    return (
      <SafeAreaView style={styles.pageContainer}>
        <ScrollView contentContainerStyle={styles.formContainer}>
          <View style={styles.logoArea}>
            <Ionicons name="shield-checkmark" size={48} color="#007AFF" />
            <Text style={styles.pageTitle}>Non-Disclosure Agreement</Text>
            <Text style={styles.pageSub}>from {ndaInfo?.sender_name} at i'M On Social</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Verify Your Identity</Text>
            <Text style={styles.cardSub}>
              Enter the email and phone number that were provided when this NDA was created.
            </Text>

            <Text style={styles.fieldLabel}>Email Address</Text>
            <TextInput
              style={styles.fieldInput}
              value={verifyEmail}
              onChangeText={setVerifyEmail}
              placeholder="you@company.com"
              placeholderTextColor="#999"
              keyboardType="email-address"
              autoCapitalize="none"
              data-testid="nda-verify-email"
            />

            <Text style={styles.fieldLabel}>Phone Number</Text>
            <TextInput
              style={styles.fieldInput}
              value={verifyPhone}
              onChangeText={setVerifyPhone}
              placeholder="(555) 123-4567"
              placeholderTextColor="#999"
              keyboardType="phone-pad"
              data-testid="nda-verify-phone"
            />

            {verifyError ? <Text style={styles.errorText}>{verifyError}</Text> : null}

            <TouchableOpacity
              style={[styles.submitBtn, submitting && { opacity: 0.5 }]}
              onPress={handleVerify}
              disabled={submitting}
              data-testid="nda-verify-btn"
            >
              {submitting ? <ActivityIndicator color="#FFF" /> : (
                <Text style={styles.submitBtnText}>Verify & Continue</Text>
              )}
            </TouchableOpacity>
          </View>

          <Text style={styles.footer}>
            i'M On Social LLC | 1741 Lunford Ln, Riverton, UT
          </Text>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ===================== READ PHASE =====================
  if (phase === 'read' && ndaFull) {
    const sections = ndaFull.content?.sections || [];
    return (
      <SafeAreaView style={styles.pageContainer}>
        <View style={styles.readHeader}>
          <Text style={styles.readHeaderTitle}>Review Agreement</Text>
        </View>
        <ScrollView contentContainerStyle={styles.readContent}>
          <View style={styles.readCard}>
            <Text style={styles.readDocTitle}>{ndaFull.content?.title || 'Non-Disclosure Agreement'}</Text>
            <View style={styles.readParties}>
              <Text style={styles.readParty}>
                <Text style={styles.readPartyLabel}>Disclosing Party: </Text>
                {ndaFull.content?.company}
              </Text>
              <Text style={styles.readParty}>
                <Text style={styles.readPartyLabel}>Receiving Party: </Text>
                {ndaFull.recipient?.name}
              </Text>
            </View>

            {sections.map((s: any, i: number) => (
              <View key={i} style={styles.readSection}>
                <Text style={styles.readSectionTitle}>{s.heading}</Text>
                <Text style={styles.readSectionBody}>{s.body}</Text>
              </View>
            ))}

            {/* Sender's signature */}
            <View style={styles.readSigBlock}>
              <Text style={styles.readSigTitle}>Disclosing Party Signature</Text>
              <Text style={styles.readSigName}>{ndaFull.sender?.name}, {ndaFull.sender?.title}</Text>
              {ndaFull.sender?.signature && (
                <Image source={{ uri: ndaFull.sender.signature }} style={styles.readSigImage} resizeMode="contain" />
              )}
              <Text style={styles.readSigDate}>
                Signed {ndaFull.sender?.signed_at ? new Date(ndaFull.sender.signed_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : ''}
              </Text>
            </View>
          </View>

          <TouchableOpacity
            style={styles.submitBtn}
            onPress={() => { setPhase('sign'); setTimeout(initCanvas, 200); }}
            data-testid="nda-proceed-sign"
          >
            <Text style={styles.submitBtnText}>I've Read the Agreement — Proceed to Sign</Text>
          </TouchableOpacity>

          <Text style={styles.footer}>
            This is a legally binding document. Please read carefully before signing.
          </Text>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ===================== SIGN PHASE =====================
  if (phase === 'sign') {
    return (
      <SafeAreaView style={styles.pageContainer}>
        <View style={styles.readHeader}>
          <TouchableOpacity onPress={() => setPhase('read')}>
            <Ionicons name="chevron-back" size={24} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.readHeaderTitle}>Sign Agreement</Text>
          <View style={{ width: 24 }} />
        </View>
        <ScrollView contentContainerStyle={styles.formContainer}>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Your Information</Text>

            <Text style={styles.fieldLabel}>Full Name</Text>
            <TextInput
              style={styles.fieldInput}
              value={sigName}
              onChangeText={setSigName}
              placeholder="Your full legal name"
              placeholderTextColor="#999"
              data-testid="nda-sign-name"
            />

            <Text style={styles.fieldLabel}>Title / Position</Text>
            <TextInput
              style={styles.fieldInput}
              value={sigTitle}
              onChangeText={setSigTitle}
              placeholder="e.g. CEO, Developer, Consultant"
              placeholderTextColor="#999"
              data-testid="nda-sign-title"
            />

            <Text style={styles.fieldLabel}>Company</Text>
            <TextInput
              style={styles.fieldInput}
              value={sigCompany}
              onChangeText={setSigCompany}
              placeholder="Your company name"
              placeholderTextColor="#999"
              data-testid="nda-sign-company"
            />

            <Text style={styles.fieldLabel}>Your Signature</Text>
            <Text style={styles.sigHint}>Draw your signature below</Text>

            {Platform.OS === 'web' && (
              <View>
                <canvas
                  id="sig-canvas-recipient"
                  width={340}
                  height={150}
                  style={{
                    width: '100%',
                    height: 150,
                    backgroundColor: '#f5f5f5',
                    borderRadius: 12,
                    border: '2px solid #ddd',
                    touchAction: 'none',
                    cursor: 'crosshair',
                  }}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                  onTouchStart={handleMouseDown}
                  onTouchMove={handleMouseMove}
                  onTouchEnd={handleMouseUp}
                />
                <TouchableOpacity onPress={clearSig} style={styles.clearSigBtn}>
                  <Ionicons name="refresh" size={14} color="#FF3B30" />
                  <Text style={{ fontSize: 13, color: '#FF3B30' }}>Clear</Text>
                </TouchableOpacity>
              </View>
            )}

            {verifyError ? <Text style={styles.errorText}>{verifyError}</Text> : null}

            <TouchableOpacity
              style={[styles.signSubmitBtn, (!hasDrawn || submitting) && { opacity: 0.5 }]}
              onPress={handleSubmitSignature}
              disabled={!hasDrawn || submitting}
              data-testid="nda-submit-signature"
            >
              {submitting ? <ActivityIndicator color="#FFF" /> : (
                <>
                  <Ionicons name="checkmark-circle" size={20} color="#FFF" />
                  <Text style={styles.submitBtnText}>Sign Agreement</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ===================== DONE PHASE =====================
  return (
    <SafeAreaView style={styles.pageContainer}>
      <ScrollView contentContainerStyle={styles.doneContainer}>
        <Ionicons name="checkmark-circle" size={80} color="#34C759" />
        <Text style={styles.doneTitle}>Agreement Signed</Text>
        <Text style={styles.doneSub}>
          The Non-Disclosure Agreement has been executed. A confirmation email has been sent to both parties.
        </Text>
        <View style={styles.doneDetails}>
          <Text style={styles.doneDetail}>
            <Text style={{ fontWeight: '600' }}>Disclosing Party: </Text>
            {ndaFull?.sender?.name || ndaInfo?.sender_name}
          </Text>
          <Text style={styles.doneDetail}>
            <Text style={{ fontWeight: '600' }}>Receiving Party: </Text>
            {sigName || ndaFull?.recipient?.name || ndaInfo?.recipient_name}
          </Text>
          <Text style={styles.doneDetail}>
            <Text style={{ fontWeight: '600' }}>Date: </Text>
            {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
          </Text>
        </View>
        <Text style={styles.footer}>
          i'M On Social LLC | 1741 Lunford Ln, Riverton, UT
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  centerContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F8F9FA', padding: 40 },
  loadingText: { fontSize: 16, color: '#666', marginTop: 16 },
  errorTitle: { fontSize: 22, fontWeight: '700', color: '#1a1a1a', marginTop: 16 },
  errorSub: { fontSize: 15, color: '#666', marginTop: 8, textAlign: 'center' },
  pageContainer: { flex: 1, backgroundColor: '#F8F9FA' },
  formContainer: { padding: 20, paddingBottom: 60 },
  logoArea: { alignItems: 'center', paddingVertical: 32 },
  pageTitle: { fontSize: 22, fontWeight: '700', color: '#1a1a1a', marginTop: 12 },
  pageSub: { fontSize: 14, color: '#666', marginTop: 4 },
  card: { backgroundColor: '#FFF', borderRadius: 16, padding: 24, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 3 },
  cardTitle: { fontSize: 18, fontWeight: '700', color: '#1a1a1a', marginBottom: 4 },
  cardSub: { fontSize: 14, color: '#666', lineHeight: 20, marginBottom: 20 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: '#555', marginTop: 16, marginBottom: 6 },
  fieldInput: { backgroundColor: '#F5F5F5', borderRadius: 12, padding: 14, fontSize: 16, color: '#1a1a1a', borderWidth: 1, borderColor: '#E5E5E5' },
  errorText: { fontSize: 14, color: '#FF3B30', marginTop: 12, textAlign: 'center' },
  submitBtn: { backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 12, alignItems: 'center', marginTop: 24, flexDirection: 'row', justifyContent: 'center', gap: 8 },
  submitBtnText: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  footer: { textAlign: 'center', fontSize: 12, color: '#999', marginTop: 32 },

  // Read phase
  readHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#E5E5E5', backgroundColor: '#FFF' },
  readHeaderTitle: { fontSize: 17, fontWeight: '600', color: '#1a1a1a' },
  readContent: { padding: 20, paddingBottom: 60 },
  readCard: { backgroundColor: '#FFF', borderRadius: 16, padding: 24, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 3, marginBottom: 20 },
  readDocTitle: { fontSize: 20, fontWeight: '800', color: '#1a1a1a', textAlign: 'center', marginBottom: 16 },
  readParties: { backgroundColor: '#F5F5F5', borderRadius: 12, padding: 16, marginBottom: 20 },
  readParty: { fontSize: 14, color: '#333', marginBottom: 6, lineHeight: 20 },
  readPartyLabel: { fontWeight: '700' },
  readSection: { marginBottom: 20, paddingBottom: 16, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  readSectionTitle: { fontSize: 16, fontWeight: '700', color: '#1a1a1a', marginBottom: 8 },
  readSectionBody: { fontSize: 14, color: '#444', lineHeight: 22 },
  readSigBlock: { marginTop: 20, padding: 16, backgroundColor: '#F8F9FA', borderRadius: 12, borderWidth: 1, borderColor: '#E5E5E5' },
  readSigTitle: { fontSize: 12, fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: 8 },
  readSigName: { fontSize: 15, fontWeight: '600', color: '#1a1a1a', marginBottom: 8 },
  readSigImage: { width: '100%', height: 60 },
  readSigDate: { fontSize: 12, color: '#888', marginTop: 8, textAlign: 'right' },

  // Sign phase
  sigHint: { fontSize: 13, color: '#888', marginBottom: 8 },
  clearSigBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-end', marginTop: 8, padding: 6 },
  signSubmitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#34C759', paddingVertical: 16, borderRadius: 12, marginTop: 24 },

  // Done phase
  doneContainer: { alignItems: 'center', padding: 40, paddingTop: 80 },
  doneTitle: { fontSize: 26, fontWeight: '700', color: '#1a1a1a', marginTop: 16 },
  doneSub: { fontSize: 15, color: '#666', textAlign: 'center', lineHeight: 22, marginTop: 8 },
  doneDetails: { backgroundColor: '#FFF', borderRadius: 16, padding: 20, width: '100%', marginTop: 24, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
  doneDetail: { fontSize: 14, color: '#333', marginBottom: 8, lineHeight: 20 },
});
