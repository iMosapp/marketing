import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, TextInput, Platform, useWindowDimensions, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter } from './_components';
import api from '../../services/api';

export default function DemoScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 560 : undefined;

  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [teamSize, setTeamSize] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim() || !email.trim()) return;
    setSending(true);
    try {
      await api.post('/demo-requests', {
        name: name.trim(),
        company: company.trim(),
        email: email.trim(),
        phone: phone.trim(),
        team_size: teamSize.trim(),
        message: message.trim(),
        source: 'imos_demo_page',
      });
      setSent(true);
    } catch {
      setSent(true);
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <View style={s.container}>
        <ImosHeader />
        <ScrollView contentContainerStyle={s.scroll}>
          <View style={[s.successWrap, maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined]}>
            <View style={s.successIcon}>
              <Ionicons name="checkmark-circle" size={64} color="#34C759" />
            </View>
            <Text style={s.successTitle}>We'll Be in Touch!</Text>
            <Text style={s.successDesc}>
              Thank you for your interest in iMOs. A member of our team will reach out within 24 hours to schedule your personalized demo.
            </Text>
            <TouchableOpacity style={s.backBtn} onPress={() => router.push('/imos' as any)} data-testid="demo-back-home">
              <Text style={s.backBtnText}>Back to Home</Text>
            </TouchableOpacity>
          </View>
          <ImosFooter />
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

          <View style={s.titleSection}>
            <Text style={s.label}>SCHEDULE A DEMO</Text>
            <Text style={[s.title, isDesktop && { fontSize: 36 }]}>See iMOs in Action</Text>
            <Text style={s.subtitle}>
              Get a personalized walkthrough of iMOs and see how it can transform your team's customer relationships.
            </Text>
          </View>

          {/* Form */}
          <View style={s.form}>
            <View style={s.row}>
              <View style={s.fieldHalf}>
                <Text style={s.fieldLabel}>Full Name *</Text>
                <TextInput style={s.input} placeholder="John Smith" placeholderTextColor="#555" value={name} onChangeText={setName} data-testid="demo-name" />
              </View>
              <View style={s.fieldHalf}>
                <Text style={s.fieldLabel}>Company</Text>
                <TextInput style={s.input} placeholder="Acme Motors" placeholderTextColor="#555" value={company} onChangeText={setCompany} data-testid="demo-company" />
              </View>
            </View>

            <View style={s.row}>
              <View style={s.fieldHalf}>
                <Text style={s.fieldLabel}>Email Address *</Text>
                <TextInput style={s.input} placeholder="john@company.com" placeholderTextColor="#555" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" data-testid="demo-email" />
              </View>
              <View style={s.fieldHalf}>
                <Text style={s.fieldLabel}>Phone Number</Text>
                <TextInput style={s.input} placeholder="+1 (555) 123-4567" placeholderTextColor="#555" value={phone} onChangeText={setPhone} keyboardType="phone-pad" data-testid="demo-phone" />
              </View>
            </View>

            <View style={s.field}>
              <Text style={s.fieldLabel}>Team Size</Text>
              <TextInput style={s.input} placeholder="e.g. 5-10 people" placeholderTextColor="#555" value={teamSize} onChangeText={setTeamSize} data-testid="demo-team-size" />
            </View>

            <View style={s.field}>
              <Text style={s.fieldLabel}>Anything specific you'd like to see?</Text>
              <TextInput
                style={[s.input, { height: 100, textAlignVertical: 'top', paddingTop: 14 }]}
                placeholder="Tell us about your goals, challenges, or features you're most interested in..."
                placeholderTextColor="#555"
                value={message}
                onChangeText={setMessage}
                multiline
                data-testid="demo-message"
              />
            </View>

            <TouchableOpacity
              style={[s.submitBtn, (!name.trim() || !email.trim()) && { opacity: 0.5 }]}
              onPress={handleSubmit}
              disabled={!name.trim() || !email.trim() || sending}
              data-testid="demo-submit-btn"
            >
              {sending ? (
                <ActivityIndicator color="#FFF" />
              ) : (
                <>
                  <Ionicons name="calendar" size={20} color="#FFF" />
                  <Text style={s.submitBtnText}>Schedule My Demo</Text>
                </>
              )}
            </TouchableOpacity>

            <Text style={s.hint}>
              Or start a 14-day free trial right now  -{' '}
              <Text style={s.hintLink} onPress={() => router.push('/auth/signup' as any)}>Sign up here</Text>
            </Text>
          </View>

          {/* Trust signals */}
          <View style={s.trustRow}>
            <View style={s.trustItem}>
              <Ionicons name="shield-checkmark" size={20} color="#34C759" />
              <Text style={s.trustText}>No credit card required for demo</Text>
            </View>
            <View style={s.trustItem}>
              <Ionicons name="time" size={20} color="#007AFF" />
              <Text style={s.trustText}>30-minute personalized walkthrough</Text>
            </View>
            <View style={s.trustItem}>
              <Ionicons name="people" size={20} color="#C9A962" />
              <Text style={s.trustText}>See real results from real teams</Text>
            </View>
          </View>

        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingBottom: 0 },
  titleSection: { alignItems: 'center', paddingTop: 40, paddingBottom: 24, paddingHorizontal: 20 },
  label: { fontSize: 11, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', marginBottom: 8, textAlign: 'center' },
  subtitle: { fontSize: 15, color: '#6E6E73', textAlign: 'center', lineHeight: 22, maxWidth: 420 },
  form: { paddingHorizontal: 20, gap: 16 },
  row: { flexDirection: 'row', gap: 12 },
  field: {},
  fieldHalf: { flex: 1 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: '#6E6E73', marginBottom: 6, marginLeft: 2 },
  input: {
    backgroundColor: '#F5F5F7',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 15,
    color: '#1D1D1F',
  },
  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#007AFF',
    paddingVertical: 16,
    borderRadius: 28,
    marginTop: 8,
  },
  submitBtnText: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  hint: { fontSize: 13, color: '#86868B', textAlign: 'center', marginTop: 12 },
  hintLink: { color: '#007AFF', fontWeight: '600' },
  trustRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 20, paddingVertical: 40, paddingHorizontal: 20 },
  trustItem: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  trustText: { fontSize: 13, color: '#6E6E73' },
  successWrap: { alignItems: 'center', paddingTop: 80, paddingBottom: 60, paddingHorizontal: 20 },
  successIcon: { marginBottom: 20 },
  successTitle: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', marginBottom: 12 },
  successDesc: { fontSize: 16, color: '#6E6E73', textAlign: 'center', lineHeight: 24, maxWidth: 400, marginBottom: 32 },
  backBtn: { paddingVertical: 14, paddingHorizontal: 28, borderRadius: 24, borderWidth: 1, borderColor: '#007AFF' },
  backBtnText: { fontSize: 16, fontWeight: '600', color: '#007AFF' },
});
