import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { CampaignSheet } from '../../components/dialer/CampaignSheet';
import { GOLD, GREEN, RED, AMBER, BLUE, GREY, tid, pct, useDialerConfig, type Campaign } from '../../components/dialer/shared';

const CampaignCard = ({ c, colors, isManager, onOpen, onStart, starting }: { c: Campaign; colors: any; isManager: boolean; onOpen: () => void; onStart: () => void; starting: boolean }) => {
  const st = c.stats;
  const remaining = c.counts.remaining || 0;
  const tone = c.status === 'active' ? GREEN : c.status === 'paused' ? AMBER : GREY;
  return (
    <TouchableOpacity onPress={onOpen} activeOpacity={0.85} style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 10 }} {...tid(`campaign-card-${c.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} numberOfLines={1}>{c.name}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{c.audience === 'b2c' ? 'Consumers' : 'Businesses'} · {c.lines} line{c.lines === 1 ? '' : 's'} · {c.connect_mode === 'press1' ? 'press 1 to accept' : 'instant connect'}</Text>
        </View>
        <View style={{ backgroundColor: `${tone}22`, borderRadius: 10, paddingHorizontal: 9, paddingVertical: 4 }}><Text style={{ fontSize: 11, fontWeight: '800', color: tone, letterSpacing: 0.6 }}>{c.status.toUpperCase()}</Text></View>
      </View>
      <View style={{ flexDirection: 'row', gap: 14 }}>
        <View><Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{remaining}</Text><Text style={{ fontSize: 10.5, color: colors.textSecondary }}>TO CALL</Text></View>
        <View><Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{c.counts.done || 0}</Text><Text style={{ fontSize: 10.5, color: colors.textSecondary }}>DONE</Text></View>
        <View><Text style={{ fontSize: 18, fontWeight: '800', color: (c.counts.dnc || 0) ? RED : colors.text }}>{c.counts.dnc || 0}</Text><Text style={{ fontSize: 10.5, color: colors.textSecondary }}>DNC</Text></View>
        {!!st && <View><Text style={{ fontSize: 18, fontWeight: '800', color: st.abandon_rate >= 0.025 ? RED : colors.text }}>{pct(st.abandon_rate)}</Text><Text style={{ fontSize: 10.5, color: colors.textSecondary }}>ABANDON</Text></View>}
      </View>
      {c.status === 'active' && remaining > 0 && (
        <TouchableOpacity onPress={onStart} disabled={starting} style={{ height: 42, borderRadius: 13, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: starting ? 0.7 : 1 }} {...tid(`campaign-start-${c.id}`)}>
          <Ionicons name="call" size={16} color="#111" /><Text style={{ fontSize: 14.5, fontWeight: '800', color: '#111' }}>{starting ? 'Ringing your phone…' : 'Start dialing'}</Text>
        </TouchableOpacity>
      )}
    </TouchableOpacity>
  );
};

export default function DialerHome() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const { config, error, reload } = useDialerConfig();
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [sheet, setSheet] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [rules, setRules] = useState(false);

  const load = useCallback(async () => {
    try { const r = await api.get('/dialer/campaigns'); setCampaigns(r.data.campaigns); } catch { setCampaigns([]); }
    finally { setRefreshing(false); }
    reload();
  }, [reload]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const start = async (c: Campaign) => {
    setStarting(c.id);
    try { const r = await api.post('/dialer/sessions', { campaign_id: c.id }); router.push(`/dialer/session/${r.data.id}` as any); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not start', 'error'); }
    finally { setStarting(null); }
  };
  const isManager = !!config?.is_manager;
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border } as const;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Power Dialer" subtitle="You press 1, we ring the list. First live answer is on your phone." testID="dialer-header"
        right={isManager ? <HeaderIconButton icon="add-circle" onPress={() => setSheet(true)} testID="dialer-new-campaign" color={GOLD} /> : undefined} />
      {campaigns === null && !error ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}>
          {!!error && <Text style={{ color: RED }} {...tid('dialer-error')}>{error}</Text>}
          {!!config?.active_session_id && (
            <TouchableOpacity onPress={() => router.push(`/dialer/session/${config.active_session_id}` as any)} style={{ ...card, backgroundColor: GREEN, borderColor: GREEN, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('dialer-resume-session')}>
              <Ionicons name="radio" size={22} color="#111" />
              <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>You have a live session</Text><Text style={{ fontSize: 12, color: '#111111AA' }}>Tap to get back to it.</Text></View>
              <Ionicons name="chevron-forward" size={18} color="#111" />
            </TouchableOpacity>
          )}
          {config && (!config.has_phone || !config.has_number) && (
            <View style={{ ...card, borderColor: `${AMBER}66`, backgroundColor: `${AMBER}12` }} {...tid('dialer-setup-warning')}>
              <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{!config.has_phone ? 'Add your cell number to your profile: the dialer rings you there. ' : ''}{!config.has_number ? 'You have no work number yet, so calls would show the campaign caller ID or the platform number.' : ''}</Text>
            </View>
          )}
          <TouchableOpacity onPress={() => setRules(r => !r)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: `${GOLD}14`, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: `${GOLD}40` }} {...tid('dialer-rules-toggle')}>
            <Ionicons name="shield-checkmark" size={18} color={GOLD} />
            <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Built inside TCPA and TSR limits: legal hours per state, daily caps, Do Not Call lists, no recorded pitches, abandonment under 3%. Every dial is logged and kept.</Text>
            <Ionicons name={rules ? 'chevron-up' : 'chevron-down'} size={14} color={GOLD} />
          </TouchableOpacity>
          {rules && config && (
            <View style={{ ...card, gap: 6 }} {...tid('dialer-rules')}>
              {config.rules.map(r => (
                <View key={r.state} style={{ flexDirection: 'row', gap: 10 }}>
                  <Text style={{ width: 34, fontSize: 12, fontWeight: '800', color: GOLD }}>{r.state}</Text>
                  <Text style={{ flex: 1, fontSize: 12, color: colors.text, lineHeight: 17 }}>{r.hours}{r.note ? ` · ${r.note}` : ''}</Text>
                </View>
              ))}
              <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6, lineHeight: 15 }}>Recording is skipped into all-party-consent states ({config.all_party_states.join(', ')}). Rules verified June 2026; your counsel signs off on use.</Text>
            </View>
          )}
          {isManager && (
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <TouchableOpacity onPress={() => router.push('/dialer/dnc' as any)} style={{ ...card, flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('dialer-dnc-link')}>
                <Ionicons name="ban" size={18} color={RED} /><View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>Do Not Call</Text><Text style={{ fontSize: 11, color: colors.textSecondary }}>{config?.registry?.numbers ? `Registry: ${config.registry.numbers.toLocaleString()} numbers` : 'Registry not loaded'}</Text></View>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.push('/admin/ghl' as any)} style={{ ...card, flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('dialer-ghl-link')}>
                <Ionicons name="git-network" size={18} color={BLUE} /><View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>GoHighLevel</Text><Text style={{ fontSize: 11, color: colors.textSecondary }}>Connect, import, sync</Text></View>
              </TouchableOpacity>
            </View>
          )}
          {(campaigns || []).length === 0 ? (
            <View style={{ alignItems: 'center', paddingVertical: 40, gap: 8 }} {...tid('dialer-empty')}>
              <Ionicons name="call-outline" size={34} color={colors.textSecondary} />
              <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{isManager ? 'No campaigns yet' : 'You are not on a campaign yet'}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 }}>{isManager ? 'Create one, import a list (CSV, GoHighLevel tag or your own tagged contacts) and pick who dials it.' : 'Ask your manager to add you to a dialer campaign.'}</Text>
              {isManager && <TouchableOpacity onPress={() => setSheet(true)} style={{ marginTop: 8, height: 44, paddingHorizontal: 20, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('dialer-empty-new')}><Text style={{ fontSize: 14.5, fontWeight: '800', color: '#111' }}>New campaign</Text></TouchableOpacity>}
            </View>
          ) : (campaigns || []).map(c => <CampaignCard key={c.id} c={c} colors={colors} isManager={isManager} onOpen={() => router.push(`/dialer/campaign/${c.id}` as any)} onStart={() => start(c)} starting={starting === c.id} />)}
        </ScrollView>
      )}
      <CampaignSheet visible={sheet} onClose={() => setSheet(false)} colors={colors} onSaved={c => { setCampaigns(cs => [c, ...(cs || [])]); router.push(`/dialer/campaign/${c.id}` as any); }} />
    </SafeAreaView>
  );
}
