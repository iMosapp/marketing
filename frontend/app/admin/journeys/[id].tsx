import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { ScreenHeader } from '../../../components/common/ScreenHeader';
import { Label, Stat, GoldButton, fmtWhen, scoreColor, GOLD, RED, GREEN, tid } from '../../../components/mystery-shops/shared';
import { LeadShopDetailSheet } from '../../../components/mystery-shops/lead-shops/LeadShopDetailSheet';
import { CAMPAIGN_STATUS, isRunning, type Campaign, type Identity, type JourneyOptions, type Modes } from '../../../components/mystery-shops/journeys/shared';
import { ModesEditor } from '../../../components/mystery-shops/journeys/ModesEditor';
import { IdentityCard } from '../../../components/mystery-shops/journeys/IdentityCard';
import { IdentityEditSheet } from '../../../components/mystery-shops/journeys/IdentityEditSheet';
import { ArmSheet } from '../../../components/mystery-shops/journeys/ArmSheet';

// One campaign: its identities, how the shopper answers on each channel, the authorization record and the stop button.
export default function JourneyCampaign() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [c, setC] = useState<Campaign | null>(null);
  const [opts, setOpts] = useState<JourneyOptions | null>(null);
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState<Identity | null>(null);
  const [openShop, setOpenShop] = useState<string | null>(null);
  const [arming, setArming] = useState(false);
  const [more, setMore] = useState(1);

  const load = useCallback(async () => {
    try { const [a, b] = await Promise.all([api.get(`/journeys/${id}`), api.get('/journeys/options')]); setC(a.data); setOpts(b.data); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); router.back(); }
  }, [id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!c || !isRunning(c)) return; const t = setInterval(load, 30000); return () => clearInterval(t); }, [c?.status, load]);

  const act = async (fn: () => Promise<any>, ok: string) => { setBusy(true); try { const r = await fn(); if (r?.data?.id) setC(r.data); else await load(); showToast(ok, 'success'); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not do that', 'error'); } finally { setBusy(false); } };
  const setModes = (m: Modes) => c && act(() => api.patch(`/journeys/${c.id}`, { modes: m }), 'Reply modes saved');
  const generate = () => c && act(() => api.post(`/journeys/${c.id}/identities/generate`, { count: more }), `${more} more identit${more === 1 ? 'y' : 'ies'} drafted`);
  const removeIdentity = (s: Identity) => c && showConfirm(`Remove ${s.persona.name}?`, 'The draft identity is deleted. Nothing has reached the store.', () => act(() => api.delete(`/journeys/${c.id}/identities/${s.id}`), 'Removed'), undefined, 'Remove');
  const stop = () => c && showConfirm('Emergency stop?', `Every identity in play closes right now, their numbers go back to the pool and whatever happened so far is graded. ${c.counts.draft ? 'Drafts stay as they are.' : ''}`, () => act(() => api.post(`/journeys/${c.id}/stop`, { reason: 'Stopped from the campaign screen' }), 'Campaign stopped'), undefined, 'Stop everything');
  const close = () => c && showConfirm('Close the campaign?', 'Identities still in play close and grade on what happened so far; drafts that were never armed are removed.', () => act(() => api.post(`/journeys/${c.id}/close`), 'Closing and grading'), undefined, 'Close & grade');
  const remove = () => c && showConfirm('Delete this campaign?', 'Finished identities keep their timelines and scores under Lead Shops; drafts are removed.', () => act(async () => { await api.delete(`/journeys/${c.id}`); router.back(); }, 'Deleted'), undefined, 'Delete');
  const openIdentity = (s: Identity) => (s.status === 'draft' ? setEdit(s) : setOpenShop(s.id));

  if (!c) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Journey campaign" testID="journey-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const st = CAMPAIGN_STATUS[c.status];
  const identities = c.identities as Identity[];
  const n = c.counts;
  const canEditModes = c.status !== 'closed' && c.status !== 'stopped';
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={c.name} subtitle={`${c.store_name} · ${c.department} · ${c.window_label}`} testID="journey-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 16 }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, height: 26, borderRadius: 13, backgroundColor: st.color + '22' }} {...tid(`journey-detail-status-${c.status}`)}><Ionicons name={st.icon} size={13} color={st.color} /><Text style={{ fontSize: 12, fontWeight: '800', color: st.color }}>{st.label}</Text></View>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{c.method === 'adf' ? 'ADF to CRM' : 'web form by hand'} · source "{c.source_name}"{c.scenario?.offering ? ` · ${c.scenario.offering}` : ''}</Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
          <Stat label="Identities" value={String(n.total)} colors={colors} testID="journey-stat-total" />
          <Stat label="In play" value={String(n.open)} colors={colors} tone={n.open ? GREEN : undefined} testID="journey-stat-open" />
          <Stat label="Graded" value={String(n.completed)} colors={colors} testID="journey-stat-done" />
          <Stat label="Avg score" value={c.avg_score == null ? '–' : `${c.avg_score}%`} colors={colors} tone={scoreColor(c.avg_score)} testID="journey-stat-score" />
        </View>
        {c.status === 'draft' && <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('journey-draft-hint')}>Nothing has reached {c.store_name}. Review and edit each identity (tap a card), add more if you like, then arm the campaign.</Text>}
        {!!c.authorization && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('journey-authorization')}>Authorized by {c.authorization.by_name || 'an admin'} {fmtWhen(c.authorization.at)}{c.authorization.website_url ? ` · ${c.authorization.website_url}` : ''}{c.authorization.note ? ` · "${c.authorization.note}"` : ''}</Text>}
        {!!c.emergency_stop && <Text style={{ fontSize: 12.5, color: RED, lineHeight: 17 }} {...tid('journey-stopped-line')}>Emergency stop by {c.emergency_stop.by_name || 'an admin'} {fmtWhen(c.emergency_stop.at)}{c.emergency_stop.reason ? `: ${c.emergency_stop.reason}` : ''}</Text>}
        {c.arm_errors.length > 0 && <View style={{ backgroundColor: RED + '14', borderRadius: 12, borderWidth: 1, borderColor: RED + '55', padding: 10, gap: 4 }} {...tid('journey-arm-errors')}>{c.arm_errors.map((e, i) => <Text key={i} style={{ fontSize: 12.5, color: colors.text }}>{e}</Text>)}</View>}

        <View style={{ gap: 8 }}>
          <Label t={`IDENTITIES · ${n.total}`} colors={colors} />
          {identities.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('journey-no-identities')}>No identities yet.</Text>}
          {identities.map(s => <IdentityCard key={s.id} s={s} colors={colors} onPress={() => openIdentity(s)} onRemove={c.status === 'draft' ? () => removeIdentity(s) : undefined} />)}
          {c.status === 'draft' && n.total < (c.submission_limit || 10) && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('journey-generate-row')}>
              <TouchableOpacity onPress={() => setMore(v => Math.max(1, v - 1))} hitSlop={8} style={{ width: 34, height: 34, borderRadius: 17, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('journey-generate-minus')}><Ionicons name="remove" size={16} color={colors.text} /></TouchableOpacity>
              <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text, minWidth: 22, textAlign: 'center' }} {...tid('journey-generate-count')}>{Math.min(more, (c.submission_limit || 10) - n.total)}</Text>
              <TouchableOpacity onPress={() => setMore(v => Math.min((c.submission_limit || 10) - n.total, v + 1))} hitSlop={8} style={{ width: 34, height: 34, borderRadius: 17, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('journey-generate-plus')}><Ionicons name="add" size={16} color={colors.text} /></TouchableOpacity>
              <View style={{ flex: 1 }}><GoldButton label="Add identities" onPress={generate} busy={busy} outline icon="sparkles" testID="journey-generate" /></View>
            </View>
          )}
        </View>

        <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 10 }} {...tid('journey-modes-card')}>
          <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>How the shopper answers</Text>
          <ModesEditor modes={c.modes} onChange={setModes} colors={colors} disabled={!canEditModes || busy} prefix="journey-mode" />
          {!canEditModes && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Modes are frozen once a campaign ends.</Text>}
        </View>

        <View style={{ gap: 8 }}>
          {c.status === 'draft' && <GoldButton label={n.draft ? 'Arm the campaign' : 'Add an identity first'} onPress={() => setArming(true)} disabled={!n.draft} busy={busy} icon="shield-checkmark" testID="journey-arm" />}
          {isRunning(c) && <GoldButton label="Emergency stop" onPress={stop} busy={busy} color={RED} icon="hand-left" testID="journey-stop" />}
          {(isRunning(c) || c.status === 'draft') && n.total > 0 && <GoldButton label={c.status === 'draft' ? 'Discard drafts & close' : 'Close now & grade all'} onPress={close} busy={busy} outline icon="stop-circle-outline" testID="journey-close" />}
          {!isRunning(c) && <GoldButton label="Delete campaign" onPress={remove} busy={busy} outline color={RED} icon="trash-outline" testID="journey-delete" />}
        </View>
      </ScrollView>
      <IdentityEditSheet campaignId={c.id} identity={edit} onClose={() => setEdit(null)} colors={colors} opts={opts} onSaved={load} />
      <ArmSheet campaign={arming ? c : null} visible={arming} onClose={() => setArming(false)} colors={colors} onArmed={(x) => setC(x)} />
      <LeadShopDetailSheet id={openShop} onClose={() => setOpenShop(null)} colors={colors} onChanged={load} />
    </SafeAreaView>
  );
}
