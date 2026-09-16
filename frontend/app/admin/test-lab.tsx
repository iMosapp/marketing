import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, GREEN, RED, tid, fmtDate } from '../../components/scripts/shared';
import { InterviewCard } from '../../components/profile/InterviewCard';
import { FactsCard } from '../../components/va/FactsCard';
import { DialerLabCard } from '../../components/dialer/DialerLabCard';

type Feature = { key: string; name: string; icon: string; tagline: string; description: string; how_to_test: string[]; added: string; needs?: string; status: 'lab' | 'live'; changed_at?: string | null; changed_by?: string | null };

const TRY: Record<string, React.ComponentType> = {
  voice_interview: () => <InterviewCard compact dryRun />,
  industry_va: () => <FactsCard />,
  power_dialer: () => <DialerLabCard />,
};

export default function TestLab() {
  const { colors } = useThemeStore();
  const [features, setFeatures] = useState<Feature[] | null>(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const load = async () => {
    try { const r = await api.get('/lab/features'); setFeatures(r.data.features || []); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not load the lab'); setFeatures([]); }
  };
  useEffect(() => { load(); }, []);

  const flip = (f: Feature) => {
    const toLive = f.status !== 'live';
    showConfirm(toLive ? `Release "${f.name}" to everyone?` : `Pull "${f.name}" back into the lab?`,
      toLive ? 'Every rep sees it from their next app open. You can pull it back any time.' : 'It disappears for reps again and stays here for you to test.',
      async () => {
        try { const r = await api.put(`/lab/features/${f.key}`, { status: toLive ? 'live' : 'lab' }); setFeatures(fs => (fs || []).map(x => x.key === f.key ? r.data : x)); }
        catch (e: any) { setError(e?.response?.data?.detail || 'Could not change that'); }
      }, undefined, toLive ? 'Release' : 'Pull back');
  };

  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border, marginBottom: 14 } as const;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Test Lab" subtitle="Try new things on your own account before anyone else sees them" testID="test-lab-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: `${GOLD}14`, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: `${GOLD}40`, marginBottom: 16 }} {...tid('test-lab-intro')}>
          <Ionicons name="flask" size={18} color={GOLD} />
          <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>New features land here first. Everything you do in the lab runs for real (calls, texts, AI) but only touches your account, and only when you say so. Flip the switch when it is ready for reps.</Text>
        </View>
        {!!error && <Text style={{ color: RED, marginBottom: 10 }} {...tid('test-lab-error')}>{error}</Text>}
        {features === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} /> : features.length === 0 ? (
          <Text style={{ color: colors.textSecondary, textAlign: 'center', marginTop: 30 }} {...tid('test-lab-empty')}>Nothing in the lab right now.</Text>
        ) : features.map(f => {
          const Try = TRY[f.key];
          const live = f.status === 'live';
          return (
            <View key={f.key} style={card} {...tid(`lab-feature-${f.key}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={(f.icon || 'sparkles') as any} size={19} color={GOLD} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{f.name}</Text>
                  <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 2 }}>Added {fmtDate(f.added)}{f.changed_at ? ` · ${live ? 'released' : 'pulled back'} ${fmtDate(f.changed_at)}${f.changed_by ? ` by ${f.changed_by}` : ''}` : ''}</Text>
                </View>
                <View style={{ backgroundColor: live ? `${GREEN}22` : `${GOLD}22`, borderRadius: 10, paddingHorizontal: 9, paddingVertical: 4 }} {...tid(`lab-status-${f.key}`)}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: live ? GREEN : GOLD, letterSpacing: 0.6 }}>{live ? 'LIVE' : 'IN THE LAB'}</Text>
                </View>
              </View>
              <Text style={{ fontSize: 13, color: colors.text, lineHeight: 19, marginTop: 12 }}>{f.tagline}</Text>
              <TouchableOpacity onPress={() => setOpen(o => ({ ...o, [f.key]: !o[f.key] }))} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 }} {...tid(`lab-more-${f.key}`)}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{open[f.key] ? 'Less' : 'How it works and how to test it'}</Text>
                <Ionicons name={open[f.key] ? 'chevron-up' : 'chevron-down'} size={13} color={GOLD} />
              </TouchableOpacity>
              {open[f.key] && (
                <View style={{ marginTop: 8 }} {...tid(`lab-details-${f.key}`)}>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 18 }}>{f.description}</Text>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginTop: 12, marginBottom: 6 }}>HOW TO TEST</Text>
                  {f.how_to_test.map((step, i) => (
                    <View key={i} style={{ flexDirection: 'row', gap: 8, marginBottom: 5 }}>
                      <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, width: 16 }}>{i + 1}.</Text>
                      <Text style={{ flex: 1, fontSize: 12, color: colors.text, lineHeight: 18 }}>{step}</Text>
                    </View>
                  ))}
                  {!!f.needs && <Text style={{ fontSize: 11, color: '#FF9500', marginTop: 8, lineHeight: 16 }}>{f.needs}</Text>}
                </View>
              )}
              {Try && <View style={{ marginTop: 14 }}><Try /></View>}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 6, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border }}>
                <View style={{ flex: 1, marginRight: 12 }}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>{live ? 'Live for everyone' : 'Release to everyone'}</Text>
                  <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 1 }}>{live ? 'Reps see it in My Profile and My VA.' : 'Only you can see this right now.'}</Text>
                </View>
                <Switch value={live} onValueChange={() => flip(f)} trackColor={{ true: GREEN, false: colors.border }} thumbColor="#fff" {...tid(`lab-release-${f.key}`)} />
              </View>
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}
