import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, TextInput, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import api from '../../../services/api';

export default function W9SubmitPage() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [quoteInfo, setQuoteInfo]   = useState<any>(null);
  const [loading, setLoading]       = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted]   = useState(false);
  const [error, setError]           = useState('');
  const [name, setName]             = useState('');
  const [email, setEmail]           = useState('');
  const [selectedFile, setSelectedFile] = useState<{ uri: string; type: string; name: string } | null>(null);

  useEffect(() => {
    if (token) loadQuoteInfo();
  }, [token]);

  const loadQuoteInfo = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/subscriptions/w9/${token}`);
      setQuoteInfo(res.data);
      if (res.data.w9_status === 'submitted') setSubmitted(true);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Invalid or expired link.');
    } finally {
      setLoading(false);
    }
  };

  const pickDocument = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: 'application/pdf', copyToCacheDirectory: true });
      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        setSelectedFile({ uri: asset.uri, type: 'application/pdf', name: asset.name || 'w9.pdf' });
      }
    } catch (e) { /* user cancelled */ }
  };

  const pickPhoto = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.9 });
      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        const ext   = asset.uri.split('.').pop() || 'jpg';
        setSelectedFile({ uri: asset.uri, type: `image/${ext}`, name: `w9_photo.${ext}` });
      }
    } catch (e) { /* user cancelled */ }
  };

  const submit = async () => {
    if (!selectedFile) { setError('Please select your W-9 file or photo first.'); return; }
    if (!name.trim())  { setError('Please enter your name.'); return; }
    setError('');
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('name', name.trim());
      formData.append('email', email.trim());
      if (Platform.OS === 'web' && (selectedFile.uri.startsWith('blob:') || selectedFile.uri.startsWith('data:'))) {
        const resp = await fetch(selectedFile.uri);
        const blob = await resp.blob();
        const file = new File([blob], selectedFile.name, { type: selectedFile.type || blob.type });
        formData.append('file', file);
      } else {
        formData.append('file', { uri: selectedFile.uri, type: selectedFile.type, name: selectedFile.name } as any);
      }
      await api.post(`/subscriptions/w9/${token}/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSubmitted(true);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Upload failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <View style={s.center}><ActivityIndicator size="large" color="#007AFF" /></View>
  );

  if (error && !quoteInfo) return (
    <View style={s.center}>
      <Ionicons name="alert-circle" size={48} color="#FF3B30" />
      <Text style={s.errorTitle}>Link Error</Text>
      <Text style={s.errorBody}>{error}</Text>
    </View>
  );

  if (submitted) return (
    <View style={s.center}>
      <View style={s.successIcon}><Ionicons name="checkmark-circle" size={64} color="#34C759" /></View>
      <Text style={s.successTitle}>W-9 Submitted!</Text>
      <Text style={s.successBody}>
        Thank you{name ? `, ${name.split(' ')[0]}` : ''}. We've received your W-9 and will review it shortly.
        You'll hear from us within 1–2 business days.
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={s.container}>
      <ScrollView contentContainerStyle={s.scroll}>
        {/* Header */}
        <View style={s.header}>
          <Text style={s.brand}>I'm On Social</Text>
          <Text style={s.headerTitle}>W-9 Upload</Text>
        </View>

        {/* Quote info */}
        {quoteInfo && (
          <View style={s.infoCard}>
            <Text style={s.infoCompany}>{quoteInfo.company_name}</Text>
            <Text style={s.infoPlan}>{quoteInfo.plan_name} · {quoteInfo.quote_number}</Text>
          </View>
        )}

        <Text style={s.intro}>
          To complete your account setup, please upload your W-9 form. You can upload a PDF or take/upload a photo of the signed form.
        </Text>

        {/* Name */}
        <Text style={s.label}>Your Full Name</Text>
        <TextInput
          style={s.input}
          value={name}
          onChangeText={setName}
          placeholder="Jane Smith"
          placeholderTextColor="#8E8E93"
          autoCapitalize="words"
        />

        {/* Email */}
        <Text style={s.label}>Your Email (optional)</Text>
        <TextInput
          style={s.input}
          value={email}
          onChangeText={setEmail}
          placeholder="jane@company.com"
          placeholderTextColor="#8E8E93"
          keyboardType="email-address"
          autoCapitalize="none"
        />

        {/* File selection */}
        <Text style={s.label}>W-9 Document</Text>
        <View style={s.fileRow}>
          <TouchableOpacity style={s.fileBtn} onPress={pickDocument} activeOpacity={0.8} data-testid="pick-pdf-btn">
            <Ionicons name="document-text" size={22} color="#007AFF" />
            <Text style={s.fileBtnText}>Upload PDF</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.fileBtn} onPress={pickPhoto} activeOpacity={0.8} data-testid="pick-photo-btn">
            <Ionicons name="camera" size={22} color="#34C759" />
            <Text style={[s.fileBtnText, { color: '#34C759' }]}>Take/Upload Photo</Text>
          </TouchableOpacity>
        </View>

        {selectedFile && (
          <View style={s.selectedFile}>
            <Ionicons name={selectedFile.type.startsWith('image') ? 'image' : 'document'} size={18} color="#C9A962" />
            <Text style={s.selectedFileName} numberOfLines={1}>{selectedFile.name}</Text>
            <TouchableOpacity onPress={() => setSelectedFile(null)}>
              <Ionicons name="close-circle" size={18} color="#8E8E93" />
            </TouchableOpacity>
          </View>
        )}

        {error ? <Text style={s.errorText}>{error}</Text> : null}

        <TouchableOpacity
          style={[s.submitBtn, (!selectedFile || !name.trim()) && s.submitBtnDisabled]}
          onPress={submit}
          disabled={!selectedFile || !name.trim() || submitting}
          activeOpacity={0.85}
          data-testid="submit-w9-btn"
        >
          {submitting
            ? <ActivityIndicator size="small" color="#fff" />
            : <><Ionicons name="cloud-upload" size={20} color="#fff" /><Text style={s.submitBtnText}>Submit W-9</Text></>
          }
        </TouchableOpacity>

        <Text style={s.legal}>
          Your W-9 is processed securely and used only for tax reporting purposes per IRS guidelines.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container:   { flex: 1, backgroundColor: '#000' },
  scroll:      { padding: 24, paddingBottom: 60 },
  center:      { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, backgroundColor: '#000' },
  header:      { alignItems: 'center', marginBottom: 28 },
  brand:       { fontSize: 22, fontWeight: '800', color: '#C9A962', marginBottom: 4 },
  headerTitle: { fontSize: 28, fontWeight: '700', color: '#fff' },
  infoCard:    { backgroundColor: '#1C1C1E', borderRadius: 14, padding: 18, marginBottom: 24, borderLeftWidth: 4, borderLeftColor: '#C9A962' },
  infoCompany: { fontSize: 18, fontWeight: '700', color: '#fff', marginBottom: 4 },
  infoPlan:    { fontSize: 14, color: '#8E8E93' },
  intro:       { fontSize: 15, color: '#CCC', lineHeight: 22, marginBottom: 28 },
  label:       { fontSize: 13, fontWeight: '700', color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 },
  input:       { backgroundColor: '#1C1C1E', borderRadius: 12, padding: 14, fontSize: 16, color: '#fff', marginBottom: 20, borderWidth: 1, borderColor: '#2C2C2E' },
  fileRow:     { flexDirection: 'row', gap: 12, marginBottom: 16 },
  fileBtn:     { flex: 1, backgroundColor: '#1C1C1E', borderRadius: 14, padding: 16, alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#2C2C2E' },
  fileBtnText: { fontSize: 13, fontWeight: '700', color: '#007AFF' },
  selectedFile:{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#C9A96215', borderRadius: 10, padding: 12, marginBottom: 20, borderWidth: 1, borderColor: '#C9A96240' },
  selectedFileName: { flex: 1, fontSize: 13, color: '#C9A962' },
  errorText:   { fontSize: 14, color: '#FF3B30', marginBottom: 16, textAlign: 'center' },
  submitBtn:   { flexDirection: 'row', backgroundColor: '#007AFF', borderRadius: 14, padding: 18, alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 20 },
  submitBtnDisabled: { opacity: 0.4 },
  submitBtnText: { fontSize: 17, fontWeight: '700', color: '#fff' },
  legal:       { fontSize: 12, color: '#48484A', textAlign: 'center', lineHeight: 18 },
  errorTitle:  { fontSize: 22, fontWeight: '700', color: '#fff', marginTop: 16 },
  errorBody:   { fontSize: 15, color: '#8E8E93', marginTop: 8, textAlign: 'center' },
  successIcon: { marginBottom: 16 },
  successTitle:{ fontSize: 26, fontWeight: '700', color: '#fff', marginBottom: 12 },
  successBody: { fontSize: 15, color: '#8E8E93', textAlign: 'center', lineHeight: 22 },
});
