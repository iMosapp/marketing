import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, useWindowDimensions, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { deptColor } from '../../components/courses/shared';
import { Label, deptLabel, LIGHT, GOLD, GREEN, tid } from '../../components/mystery-shops/shared';

type Cert = { name: string; course_title: string; badge_label: string; department: string; description: string; pass_pct: number; certified_at: string | null; challenges: { title: string; best_pct: number | null; attempts: number }[]; issuer: string };
const fmt = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' }) : '');

// Public, shareable certificate. No login.
export default function PublicCertificate() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const [d, setD] = useState<Cert | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { if (token) api.get(`/public/certificate/${token}`).then(r => setD(r.data)).catch(() => setError('This certificate link is not valid.')); }, [token]);
  const wide = width > 800;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: LIGHT.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 40 : 16, paddingBottom: 60, alignItems: 'center' }}>
        <View style={{ width: '100%', maxWidth: 720, gap: 18 }}>
          {error ? <Text style={{ fontSize: 15, color: LIGHT.textSecondary }} {...tid('certificate-error')}>{error}</Text> : !d ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <View style={{ backgroundColor: LIGHT.card, borderRadius: 24, borderWidth: 2, borderColor: GOLD, padding: wide ? 40 : 24, gap: 14, alignItems: 'center' }} {...tid('certificate-card')}>
                <Image source={require('../../assets/images/icon.png')} style={{ width: 64, height: 64, borderRadius: 16 }} />
                <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 3 }}>CERTIFICATE OF COMPLETION</Text>
                <Text style={{ fontSize: 14, color: LIGHT.textSecondary }}>This certifies that</Text>
                <Text style={{ fontSize: wide ? 40 : 30, fontWeight: '800', color: LIGHT.text, textAlign: 'center' }} {...tid('certificate-name')}>{d.name}</Text>
                <Text style={{ fontSize: 14, color: LIGHT.textSecondary, textAlign: 'center' }}>passed every challenge in</Text>
                <Text style={{ fontSize: wide ? 24 : 20, fontWeight: '800', color: deptColor(d.department), textAlign: 'center' }} {...tid('certificate-course')}>{d.course_title}</Text>
                {!!d.description && <Text style={{ fontSize: 14, color: LIGHT.textSecondary, textAlign: 'center', lineHeight: 20, maxWidth: 520 }}>{d.description}</Text>}
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: GREEN + '18', borderRadius: 20, paddingHorizontal: 14, height: 36, borderWidth: 1, borderColor: GREEN + '66' }} {...tid('certificate-badge')}>
                  <Ionicons name="ribbon" size={18} color={GREEN} /><Text style={{ fontSize: 14, fontWeight: '800', color: LIGHT.text }}>{d.badge_label}</Text>
                </View>
                <Text style={{ fontSize: 13, color: LIGHT.textSecondary }} {...tid('certificate-date')}>{fmt(d.certified_at)} · {d.department === 'mixed' ? 'Multi-department' : deptLabel(d.department)} · pass mark {d.pass_pct}%</Text>
                <Text style={{ fontSize: 12, color: LIGHT.textSecondary }}>Issued by {d.issuer}. Every challenge was a live phone roleplay graded by an AI scorecard.</Text>
              </View>
              <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18, gap: 10 }} {...tid('certificate-challenges')}>
                <Label t={`${d.challenges.length} CHALLENGES PASSED`} colors={LIGHT} />
                {d.challenges.map((c, i) => (
                  <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Ionicons name="checkmark-circle" size={18} color={GREEN} />
                    <Text style={{ flex: 1, fontSize: 14.5, color: LIGHT.text }}>{c.title}</Text>
                    <Text style={{ fontSize: 13.5, fontWeight: '800', color: LIGHT.text }}>{c.best_pct != null ? `${c.best_pct}%` : ''}</Text>
                  </View>
                ))}
              </View>
              <Text style={{ fontSize: 12, color: LIGHT.textSecondary, textAlign: 'center' }}>I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
