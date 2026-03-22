import React, { useState, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import api from '../../../services/api';
import { useAuthStore } from '../../../store/authStore';
import { showSimpleAlert } from '../../../services/alert';

import { useThemeStore } from '../../../store/themeStore';
export default function PrepareNDA() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [step, setStep] = useState<'sign' | 'recipient' | 'done'>('sign');
  const [sending, setSending] = useState(false);
  const [senderName, setSenderName] = useState(user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : '');
  const [senderTitle, setSenderTitle] = useState('Founder & CEO');
  const [signatureData, setSignatureData] = useState('');
  const [recipientName, setRecipientName] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [ndaLink, setNdaLink] = useState('');
  const [ndaId, setNdaId] = useState('');

  // Canvas drawing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(false);

  const initCanvas = () => {
    if (Platform.OS !== 'web') return;
    setTimeout(() => {
      const canvas = document.getElementById('sig-canvas-nda') as HTMLCanvasElement;
      if (!canvas) return;
      canvasRef.current = canvas;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2.5;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
      }
    }, 100);
  };

  React.useEffect(() => { initCanvas(); }, []);

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
    if (canvas) {
      setSignatureData(canvas.toDataURL('image/png'));
    }
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx?.clearRect(0, 0, canvas.width, canvas.height);
    setSignatureData('');
    setHasDrawn(false);
  };

  const handleNextToRecipient = () => {
    if (!senderName.trim()) { showSimpleAlert('Required', 'Enter your name'); return; }
    if (!senderTitle.trim()) { showSimpleAlert('Required', 'Enter your title'); return; }
    if (!hasDrawn || !signatureData) { showSimpleAlert('Required', 'Draw your signature'); return; }
    setStep('recipient');
  };

  const handleCreate = async () => {
    if (!recipientName.trim()) { showSimpleAlert('Required', 'Enter recipient name'); return; }
    if (!recipientEmail.trim() || !recipientEmail.includes('@')) { showSimpleAlert('Required', 'Enter a valid email'); return; }
    if (!recipientPhone.trim()) { showSimpleAlert('Required', 'Enter recipient phone number'); return; }

    setSending(true);
    try {
      const res = await api.post('/nda/agreements', {
        sender_name: senderName.trim(),
        sender_title: senderTitle.trim(),
        sender_signature: signatureData,
        signature_type: 'drawn',
        recipient_name: recipientName.trim(),
        recipient_email: recipientEmail.trim(),
        recipient_phone: recipientPhone.trim(),
      });
      setNdaLink(res.data.link);
      setNdaId(res.data.id);
      setStep('done');
    } catch (err: any) {
      showSimpleAlert('Error', err.response?.data?.detail || 'Failed to create NDA');
    } finally {
      setSending(false);
    }
  };

  const handleSendEmail = async () => {
    if (!ndaId) return;
    setSending(true);
    try {
      await api.post(`/nda/agreements/${ndaId}/send`);
      showSimpleAlert('Sent', `NDA emailed to ${recipientEmail}`);
    } catch (err) {
      showSimpleAlert('Error', 'Failed to send email');
    } finally {
      setSending(false);
    }
  };

  const handleCopyLink = async () => {
    if (!ndaLink) return;
    await Clipboard.setStringAsync(ndaLink);
    showSimpleAlert('Copied', 'Link copied to clipboard');
  };

  const handleTextLink = () => {
    if (!ndaLink) return;
    const body = encodeURIComponent(`Hi ${recipientName}, please review and sign this NDA: ${ndaLink}`);
    const phone = recipientPhone.replace(/\D/g, '');
    const sep = /iPhone|iPad|iPod/i.test(navigator?.userAgent || '') ? '&' : '?';
    window.location.href = `sms:${phone}${sep}body=${body}`;
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>
          {step === 'sign' ? 'Your Signature' : step === 'recipient' ? 'Recipient Info' : 'NDA Ready'}
        </Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView style={styles.content} contentContainerStyle={{ paddingBottom: 40 }}>
        {step === 'sign' && (
          <>
            <Text style={styles.label}>Your Full Name</Text>
            <TextInput
              style={styles.input}
              value={senderName}
              onChangeText={setSenderName}
              placeholder="Forest Ward"
              placeholderTextColor={colors.textSecondary}
              data-testid="nda-sender-name"
            />

            <Text style={styles.label}>Your Title</Text>
            <TextInput
              style={styles.input}
              value={senderTitle}
              onChangeText={setSenderTitle}
              placeholder="Founder & CEO"
              placeholderTextColor={colors.textSecondary}
              data-testid="nda-sender-title"
            />

            <Text style={styles.label}>Your Signature</Text>
            <Text style={styles.hint}>Draw your signature below</Text>

            {Platform.OS === 'web' && (
              <View style={styles.canvasWrap}>
                <canvas
                  id="sig-canvas-nda"
                  width={340}
                  height={150}
                  style={{
                    width: '100%',
                    height: 150,
                    backgroundColor: colors.card,
                    borderRadius: 12,
                    border: '1px solid #333',
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
                <TouchableOpacity onPress={clearSignature} style={styles.clearBtn}>
                  <Ionicons name="refresh" size={16} color="#FF3B30" />
                  <Text style={styles.clearText}>Clear</Text>
                </TouchableOpacity>
              </View>
            )}

            <TouchableOpacity
              style={[styles.primaryBtn, (!hasDrawn || !senderName.trim()) && styles.disabledBtn]}
              onPress={handleNextToRecipient}
              disabled={!hasDrawn || !senderName.trim()}
              data-testid="nda-next-btn"
            >
              <Text style={styles.primaryBtnText}>Next: Recipient Info</Text>
              <Ionicons name="arrow-forward" size={20} color={colors.text} />
            </TouchableOpacity>
          </>
        )}

        {step === 'recipient' && (
          <>
            <Text style={styles.sectionTitle}>Who is this NDA for?</Text>
            <Text style={styles.hint}>They'll use their email and phone to verify identity before signing.</Text>

            <Text style={styles.label}>Recipient Name</Text>
            <TextInput
              style={styles.input}
              value={recipientName}
              onChangeText={setRecipientName}
              placeholder="John Smith"
              placeholderTextColor={colors.textSecondary}
              data-testid="nda-recipient-name"
            />

            <Text style={styles.label}>Recipient Email</Text>
            <TextInput
              style={styles.input}
              value={recipientEmail}
              onChangeText={setRecipientEmail}
              placeholder="john@example.com"
              placeholderTextColor={colors.textSecondary}
              keyboardType="email-address"
              autoCapitalize="none"
              data-testid="nda-recipient-email"
            />

            <Text style={styles.label}>Recipient Phone</Text>
            <TextInput
              style={styles.input}
              value={recipientPhone}
              onChangeText={setRecipientPhone}
              placeholder="(801) 555-1234"
              placeholderTextColor={colors.textSecondary}
              keyboardType="phone-pad"
              data-testid="nda-recipient-phone"
            />

            <View style={{ flexDirection: 'row', gap: 12, marginTop: 24 }}>
              <TouchableOpacity style={styles.secondaryBtn} onPress={() => setStep('sign')}>
                <Ionicons name="arrow-back" size={18} color="#007AFF" />
                <Text style={styles.secondaryBtnText}>Back</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.primaryBtn, { flex: 1 }, sending && styles.disabledBtn]}
                onPress={handleCreate}
                disabled={sending}
                data-testid="nda-create-btn"
              >
                {sending ? <ActivityIndicator color={colors.text} /> : (
                  <>
                    <Ionicons name="document-text" size={20} color={colors.text} />
                    <Text style={styles.primaryBtnText}>Create NDA</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </>
        )}

        {step === 'done' && (
          <>
            <View style={styles.successIcon}>
              <Ionicons name="checkmark-circle" size={72} color="#34C759" />
            </View>
            <Text style={styles.successTitle}>NDA Created</Text>
            <Text style={styles.successSub}>Ready to send to {recipientName}</Text>

            <View style={styles.linkBox}>
              <Text style={styles.linkText} numberOfLines={2}>{ndaLink}</Text>
            </View>

            <TouchableOpacity style={styles.actionBtn} onPress={handleSendEmail} data-testid="nda-send-email">
              {sending ? <ActivityIndicator color={colors.text} /> : (
                <>
                  <Ionicons name="mail" size={20} color={colors.text} />
                  <Text style={styles.actionBtnText}>Send via Email</Text>
                </>
              )}
            </TouchableOpacity>

            <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#34C759' }]} onPress={handleTextLink} data-testid="nda-send-sms">
              <Ionicons name="chatbubble" size={20} color={colors.text} />
              <Text style={styles.actionBtnText}>Send via Text</Text>
            </TouchableOpacity>

            <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#5856D6' }]} onPress={handleCopyLink} data-testid="nda-copy-link">
              <Ionicons name="copy" size={20} color={colors.text} />
              <Text style={styles.actionBtnText}>Copy Link</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionBtn, { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.surface }]}
              onPress={() => router.push('/admin/nda')}
              data-testid="nda-view-all"
            >
              <Ionicons name="list" size={20} color={colors.text} />
              <Text style={styles.actionBtnText}>View All NDAs</Text>
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  backBtn: { width: 40 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  content: { flex: 1, paddingHorizontal: 20, paddingTop: 24 },
  label: { fontSize: 16, fontWeight: '600', color: '#AAA', marginTop: 20, marginBottom: 6 },
  hint: { fontSize: 15, color: '#666', marginBottom: 12 },
  input: { backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 18, color: colors.text, borderWidth: 1, borderColor: colors.surface },
  sectionTitle: { fontSize: 21, fontWeight: '700', color: colors.text, marginBottom: 4 },
  canvasWrap: { marginTop: 4 },
  clearBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-end', marginTop: 8, padding: 8 },
  clearText: { fontSize: 15, color: '#FF3B30' },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 12, marginTop: 28 },
  primaryBtnText: { fontSize: 18, fontWeight: '600', color: colors.text },
  disabledBtn: { opacity: 0.4 },
  secondaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: colors.card, paddingVertical: 14, paddingHorizontal: 20, borderRadius: 12, borderWidth: 1, borderColor: colors.surface },
  secondaryBtnText: { fontSize: 17, fontWeight: '600', color: '#007AFF' },
  successIcon: { alignItems: 'center', marginTop: 20, marginBottom: 12 },
  successTitle: { fontSize: 24, fontWeight: '700', color: colors.text, textAlign: 'center' },
  successSub: { fontSize: 17, color: colors.textSecondary, textAlign: 'center', marginTop: 4, marginBottom: 24 },
  linkBox: { backgroundColor: colors.card, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: colors.surface, marginBottom: 20 },
  linkText: { fontSize: 16, color: '#007AFF', fontFamily: 'monospace' },
  actionBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 12, marginBottom: 12 },
  actionBtnText: { fontSize: 18, fontWeight: '600', color: colors.text },
});
