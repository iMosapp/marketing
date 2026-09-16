import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { showConfirm } from '../../../services/alert';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { CampaignSheet } from '../../../components/dialer/CampaignSheet';
import { ImportLeadsSheet } from '../../../components/dialer/ImportLeadsSheet';
import { Chip, Stat, GoldButton, GOLD, GREEN, RED, AMBER, GREY, tid, pct, fmtWhen, fmtDur, useDialerConfig, LEAD_STATUS, DNC_LABEL, SOURCE_LABEL, type Campaign, type Lead, type Attempt } from '../../../components/dialer/shared';

type Tab = 'leads' | 'log' | 'settings';
const FILTERS = [{ key: '', label: 'All' }, { key: 'new,queued,callback', label: 'To call' }, { key: 'done', label: 'Done' }, { key: 'dnc', label: 'DNC' }, { key: 'wrapup,calling', label: 'In progress' }];

const LeadRow = ({ l, colors, canManage, onDnc, onRemove }: { l: Lead; colors: any; canManage: boolean; onDnc: () => void; onRemove: () => void }) => {
  const st = LEAD_STATUS[l.status] || { label: l.status, color: GREY };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`lead-row-${l.id}`)}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{l.name}{l.company && l.name !== l.company ? <Text style={{ color: colors.textSecondary, fontWeight: '500' }}> · {l.company}</Text> : null}</Text>
        <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
          {l.phone}{l.state ? ` · ${l.state}` : ''}{l.local_time ? ` · ${l.local_time} there` : ''} · {l.attempts} tr{l.attempts === 1 ? 'y' : 'ies'}{l.disposition ? ` · ${l.disposition.replace('_', ' ')}` : ''}{l.next_attempt_at && ['queued', 'callback'].includes(l.status) ? ` · next ${fmtWhen(l.next_attempt_at)}` : ''}
        </Text>
        {l.dnc && l.dnc !== 'clear' && <Text style={{ fontSize: 11, color: l.dnc === 'unscrubbed' ? AMBER : RED, marginTop: 2 }}>{DNC_LABEL[l.dnc] || l.dnc}</Text>}
        {!!l.ghl_sync_error && <Text style={{ fontSize: 11, color: AMBER, marginTop: 2 }}>GHL sync: {l.ghl_sync_error}</Text>}
      </View>
      <View style={{ backgroundColor: `${st.color}22`, borderRadius: 8, paddingHorizontal: 7, paddingVertical: 3 }}><Text style={{ fontSize: 10.5, fontWeight: '800', color: st.color }}>{st.label.toUpperCase()}</Text></View>
      {canManage && l.status !== 'dnc' && <TouchableOpacity onPress={onDnc} hitSlop={8} {...tid(`lead-dnc-${l.id}`)}><Ionicons name="ban-outline" size={18} color={RED} /></TouchableOpacity>}
      {canManage && l.status !== 'calling' && <TouchableOpacity onPress={onRemove} hitSlop={8} {...tid(`lead-remove-${l.id}`)}><Ionicons name="trash-outline" size={18} color={colors.textSecondary} /></TouchableOpacity>}
    </View>
  );
};

const AttemptRow = ({ a, colors }: { a: Attempt; colors: any }) => {
  const tone = a.abandoned ? RED : a.status === 'connected' ? GREEN : GREY;
  return (
    <View style={{ paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 2 }} {...tid(`attempt-row-${a.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }} numberOfLines={1}>{a.lead_name} <Text style={{ fontWeight: '500', color: colors.textSecondary }}>{a.phone}</Text></Text>
        <Text style={{ fontSize: 11, fontWeight: '800', color: tone }}>{a.abandoned ? 'ABANDONED' : a.status.replace('_', ' ').toUpperCase()}</Text>
      </View>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{fmtWhen(a.started_at)}{a.local_time ? ` · ${a.local_time} in ${a.lead_state || 'their zone'}` : ''}{a.rep_name ? ` · ${a.rep_name}` : ''}{a.answered_by ? ` · ${a.answered_by.replace(/_/g, ' ')}` : ''}{a.talk_s ? ` · talked ${fmtDur(a.talk_s)}` : ''}{a.disposition ? ` · ${a.disposition.replace('_', ' ')}` : ''}</Text>
      {!!a.notes && <Text style={{ fontSize: 12, color: colors.text, marginTop: 2 }}>{a.notes}</Text>}
    </View>
  );
};

export default function CampaignDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const { config } = useDialerConfig();
  const [c, setC] = useState<Campaign | null>(null);
  const [tab, setTab] = useState<Tab>('leads');
  const [filter, setFilter] = useState('');
  const [q, setQ] = useState('');
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [sheet, setSheet] = useState(false);
  const [imp, setImp] = useState(false);
  const [ghlConnected, setGhlConnected] = useState(false);
  const [starting, setStarting] = useState(false);

  const load = useCallback(async () => { try { const r = await api.get(`/dialer/campaigns/${id}`); setC(r.data); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); } }, [id]);
  const loadLeads = useCallback(async () => { try { const r = await api.get(`/dialer/campaigns/${id}/leads`, { params: { status: filter || undefined, q: q || undefined, limit: 200 } }); setLeads(r.data.leads); setTotal(r.data.total); } catch { setLeads([]); } }, [id, filter, q]);
  const loadLog = useCallback(async () => { try { const r = await api.get(`/dialer/campaigns/${id}/attempts`, { params: { limit: 200 } }); setAttempts(r.data.attempts); } catch { setAttempts([]); } }, [id]);
  useEffect(() => { load(); api.get('/ghl/connection').then(r => setGhlConnected(!!r.data.connected)).catch(() => setGhlConnected(false)); }, [load]);
  useEffect(() => { if (tab === 'leads') { const t = setTimeout(loadLeads, 250); return () => clearTimeout(t); } if (tab === 'log') loadLog(); }, [tab, loadLeads, loadLog]);

  const canManage = !!config?.is_manager;
  const start = async () => {
    setStarting(true);
    try { const r = await api.post('/dialer/sessions', { campaign_id: id }); router.push(`/dialer/session/${r.data.id}` as any); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not start', 'error'); }
    finally { setStarting(false); }
  };
  const setStatus = async (status: string) => { try { const r = await api.patch(`/dialer/campaigns/${id}`, { status }); setC(r.data); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not update', 'error'); } };
  const remove = () => showConfirm('Delete this campaign?', 'The lead list goes away. The call log is kept for compliance.', async () => {
    try { await api.delete(`/dialer/campaigns/${id}`); router.back(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not delete', 'error'); }
  }, undefined, 'Delete');
  const dncLead = (l: Lead) => showConfirm(`Never call ${l.name}?`, 'Adds the number to the Do Not Call list for every campaign.', async () => {
    try { await api.post(`/dialer/campaigns/${id}/leads/${l.id}/dnc`); loadLeads(); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not update', 'error'); }
  }, undefined, 'Do not call');
  const removeLead = async (l: Lead) => { try { await api.delete(`/dialer/campaigns/${id}/leads/${l.id}`); loadLeads(); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); } };
  const rescrub = async () => { try { const r = await api.post(`/dialer/campaigns/${id}/rescrub`); showToast(`${r.data.flagged} newly flagged`, 'success'); loadLeads(); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not re-check', 'error'); } };

  if (!c) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Campaign" testID="campaign-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const st = c.stats!, qd = c.queue!;
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border } as const;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={c.name} subtitle={`${c.audience === 'b2c' ? 'Consumers' : 'Businesses'} · ${c.lines} line${c.lines === 1 ? '' : 's'} · ${c.hours.start}-${c.hours.end} their time`} testID="campaign-header"
        right={canManage ? <HeaderIconButton icon="settings-outline" onPress={() => setSheet(true)} testID="campaign-edit" color={GOLD} /> : undefined} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }}>
        <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
          <Stat label="Ready now" value={`${qd.ready}`} colors={colors} testID="campaign-stat-ready" />
          <Stat label="Waiting on hours" value={`${qd.waiting_window}`} colors={colors} testID="campaign-stat-waiting" />
          <Stat label="Connected (30d)" value={`${st.connected}`} colors={colors} testID="campaign-stat-connected" />
          <Stat label="Abandon rate" value={`${pct(st.abandon_rate)} / 3%`} colors={colors} tone={st.abandon_rate >= 0.025 ? RED : undefined} testID="campaign-stat-abandon" />
        </View>
        {st.throttled && <View style={{ ...card, borderColor: `${RED}66`, backgroundColor: `${RED}12` }} {...tid('campaign-throttled')}><Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>Throttled to 1 line: abandoned calls are near the legal 3%. Lines come back as the 30-day rate falls.</Text></View>}
        {qd.ready === 0 && qd.waiting_window > 0 && <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('campaign-next-open')}>Nothing callable right now; the next window opens {fmtWhen(qd.next_open)}.</Text>}
        {c.status === 'active' && (c.counts.remaining || 0) > 0 && <GoldButton label={starting ? 'Ringing your phone…' : 'Start dialing'} onPress={start} busy={starting} testID="campaign-start" icon="call" />}
        {canManage && (
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View style={{ flex: 1 }}><GoldButton label="Add leads" onPress={() => setImp(true)} outline testID="campaign-import" icon="cloud-download-outline" /></View>
            <View style={{ flex: 1 }}>{c.status === 'active' ? <GoldButton label="Pause" onPress={() => setStatus('paused')} outline color={AMBER} testID="campaign-pause" icon="pause" /> : <GoldButton label="Activate" onPress={() => setStatus('active')} outline color={GREEN} testID="campaign-activate" icon="play" />}</View>
          </View>
        )}
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {(['leads', 'log', 'settings'] as Tab[]).map(t => <Chip key={t} label={t === 'leads' ? `Leads · ${c.counts.total}` : t === 'log' ? 'Call log' : 'Settings'} active={tab === t} onPress={() => setTab(t)} colors={colors} testID={`campaign-tab-${t}`} />)}
        </View>
        {tab === 'leads' && (
          <View style={card}>
            <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>{FILTERS.map(f => <Chip key={f.key} label={f.label} small active={filter === f.key} onPress={() => setFilter(f.key)} colors={colors} testID={`leads-filter-${f.label.toLowerCase().replace(/\s+/g, '-')}`} />)}</View>
            <TextInput value={q} onChangeText={setQ} placeholder="Search name, company or number" placeholderTextColor={colors.textSecondary} style={{ backgroundColor: colors.bg, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, color: colors.text, fontSize: 14, borderWidth: 1, borderColor: colors.border }} {...tid('leads-search')} />
            <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 8 }}>{total} lead{total === 1 ? '' : 's'}{canManage && <Text onPress={rescrub} style={{ color: GOLD, fontWeight: '700' }} {...tid('campaign-rescrub')}>  · Re-check Do Not Call</Text>}</Text>
            {leads.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 24 }} {...tid('leads-empty')}>{c.counts.total ? 'Nothing matches.' : 'No leads yet. Add a CSV, a GoHighLevel tag or your own tagged contacts.'}</Text>
              : leads.map(l => <LeadRow key={l.id} l={l} colors={colors} canManage={canManage} onDnc={() => dncLead(l)} onRemove={() => removeLead(l)} />)}
          </View>
        )}
        {tab === 'log' && (
          <View style={card}>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginBottom: 4 }}>Every dial, with the lead's local time and outcome. Kept for 5 years (TSR record keeping).</Text>
            {attempts.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 24 }} {...tid('log-empty')}>No calls yet.</Text> : attempts.map(a => <AttemptRow key={a.id} a={a} colors={colors} />)}
          </View>
        )}
        {tab === 'settings' && (
          <View style={{ ...card, gap: 8 }} {...tid('campaign-settings')}>
            {[
              ['Audience', c.audience === 'b2c' ? 'Consumers (full TCPA / TSR / state rules)' : 'Businesses (B2B)'], ['Lines at once', `${c.lines}${st.throttled ? ' (throttled to 1)' : ''}`],
              ['On answer', c.connect_mode === 'press1' ? 'Rep presses 1 to accept' : 'Instant connect'], ['Voicemail', c.voicemail === 'rep' ? 'Rep decides' : 'Skip, retry later'],
              ['Hours (lead local)', `${c.hours.start} - ${c.hours.end}, clamped to state law`], ['Tries per lead', `${c.max_attempts}, ${c.retry_hours} h apart, max ${c.max_per_day}/24 h`],
              ['Recording', c.recording === 'on' ? 'On, except all-party-consent states' : 'Off'], ['Registry hits (B2B)', c.allow_registry_b2b ? 'Called' : 'Skipped'],
              ['Abandon message names', c.seller_name], ['Caller ID', c.caller_id || "Rep's work number"], ['GoHighLevel', c.ghl?.push ? `Outcomes pushed${c.ghl?.tag ? ` · tag ${c.ghl.tag}` : ''}` : 'Not pushed'],
              ['Reps', (c.reps || []).map(r => r.name).join(', ') || 'Managers only'],
            ].map(([k, v]) => <View key={k as string} style={{ flexDirection: 'row', gap: 10 }}><Text style={{ width: 140, fontSize: 12.5, color: colors.textSecondary }}>{k}</Text><Text style={{ flex: 1, fontSize: 12.5, color: colors.text }}>{v}</Text></View>)}
            {!!c.script && <><Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginTop: 6 }}>SCRIPT</Text><Text style={{ fontSize: 13, color: colors.text, lineHeight: 19 }}>{c.script}</Text></>}
            {canManage && <TouchableOpacity onPress={remove} style={{ marginTop: 10, alignSelf: 'flex-start' }} {...tid('campaign-delete')}><Text style={{ fontSize: 13, fontWeight: '700', color: RED }}>Delete campaign</Text></TouchableOpacity>}
          </View>
        )}
      </ScrollView>
      <CampaignSheet visible={sheet} onClose={() => setSheet(false)} colors={colors} campaign={c} storeId={c.store_id} onSaved={setC} />
      <ImportLeadsSheet visible={imp} onClose={() => setImp(false)} colors={colors} campaignId={c.id} ghlConnected={ghlConnected} onDone={() => { load(); loadLeads(); }} />
    </SafeAreaView>
  );
}
