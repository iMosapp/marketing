import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, useWindowDimensions } from 'react-native';
import { ImosHeader, ImosFooter } from './_components';
import api from '../../services/api';

export default function TermsScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 800 : undefined;
  const [loading, setLoading] = useState(true);
  const [terms, setTerms] = useState<{ title: string; last_updated: string; content: string } | null>(null);

  useEffect(() => {
    api.get('/legal/terms').then(r => setTerms(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={[s.content, maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined]}>
          <Text style={s.label}>LEGAL</Text>
          <Text style={[s.title, isDesktop && { fontSize: 36 }]}>Terms of Service</Text>
          {loading ? (
            <ActivityIndicator color="#007AFF" style={{ marginTop: 40 }} />
          ) : terms ? (
            <>
              <Text style={s.updated}>Last updated: {terms.last_updated}</Text>
              <Text style={s.body}>{terms.content}</Text>
            </>
          ) : (
            <Text style={s.body}>
              By using i'M On Social, you agree to these terms of service. i'M On Social provides a Relationship Management System for businesses. Users are responsible for maintaining the confidentiality of their account credentials and for all activities under their account.{'\n\n'}
              i'M On Social reserves the right to modify these terms at any time. Continued use constitutes acceptance of modified terms.{'\n\n'}
              For questions, contact us at forest@imonsocial.com.
            </Text>
          )}
        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingBottom: 0 },
  content: { paddingHorizontal: 20, paddingTop: 40, paddingBottom: 40 },
  label: { fontSize: 11, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', marginBottom: 12 },
  updated: { fontSize: 13, color: '#8E8E93', marginBottom: 24 },
  body: { fontSize: 15, color: '#6E6E73', lineHeight: 24 },
});
