// Where did this come from? Provenance for one rep's day: who owns each customer, the task / conversation / message behind each stop,
// and any automations the rep has running on other reps' customers (with a one-tap stop).
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { useToast } from '../components/common/Toast';
import { showAlert } from '../services/alert';
import api from '../services/api';

const GOLD = '#C9A962';
const WARN = '#FF9F0A';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const when = (v?: string | null) => (v ? new Date(v).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');
const day = (v?: string | null) => (v ? new Date(v).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' }) : '');

type Row = {
  n: number; kind: string; label: string; name: string; why: string; contact_id: string | null;
  contact: { owner_user_id: string; owner_name: string; foreign: boolean; birthday?: string | null; anniversary?: string | null; date_sold?: string | null; tags: string[]; created_at?: string | null; source?: string | null };
  task?: Record<string, any>; conversation?: Record<string, any>; recent_messages?: Record<string, any>[];
};
type Explain = { rep_user_id: string; rep_name: string; stops: Row[]; foreign_stops: number; foreign_enrollments: Record<string, any>[] };
type Leaks = { scope: 'team' | 'everyone'; reps: { rep_user_id: string; rep_name: string; enrollments: number; cross_store: number }[]; total: number; cross_store: number; queued_sends: number };

const KV = ({ k, v, colors }: { k: string; v: any; colors: any }) => (v === undefined || v === null || v === '' ? null : (
  <View style={{ flexDirection: 'row', gap: 8 }}><Text style={{ width: 96, fontSize: 11.5, color: colors.textTertiary, fontWeight: '700' }}>{k}</Text><Text style={{ flex: 1, fontSize: 12.5, color: colors.text }}>{String(v)}</Text></View>
));

export default function TeamTodayExplainScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { rep } = useLocalSearchParams<{ rep?: string }>();
  const { showToast } = useToast();
  const [data, setData] = useState<Explain | null>(null);
  const [leaks, setLeaks] = useState<Leaks | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setData((await api.get('/team-today/explain', { params: { rep_user_id: rep }, timeout: 45000 })).data); }
    catch (e: any) { setErr(e?.response?.data?.detail || 'Could not load the breakdown.'); }
    api.get('/team-today/leaks', { timeout: 45000 }).then(r => setLeaks(r.data)).catch(() => setLeaks({ scope: 'team', reps: [], total: 0, cross_store: 0, queued_sends: 0 }));
  }, [rep]);
  useEffect(() => { if (rep) load(); }, [rep, load]);

  const cancelLeaks = (crossOnly: boolean) => {
    const n = crossOnly ? leaks!.cross_store : leaks!.total;
    showAlert(crossOnly ? 'Stop every cross-store automation?' : 'Stop every automation on other reps\' customers?',
      crossOnly ? `${n} enrollment${n === 1 ? '' : 's'} where the customer belongs to a different store will be cancelled, along with their queued texts. Those are the leaked ones.`
        : `${n} enrollment${n === 1 ? '' : 's'} on customers owned by someone else will be cancelled, including ones in the same store that a manager may have set up on purpose.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Stop them', style: 'destructive', onPress: async () => {
        setBusy(true);
        try { const r = (await api.post('/team-today/cancel-leaks', { cross_store_only: crossOnly })).data; showToast(`Stopped ${r.enrollments_cancelled} enrollment${r.enrollments_cancelled === 1 ? '' : 's'} and ${r.sends_cancelled} queued send${r.sends_cancelled === 1 ? '' : 's'} across ${r.reps} rep${r.reps === 1 ? '' : 's'}.`, 'success', 4500); load(); }
        catch (e: any) { showToast(e?.response?.data?.detail || 'Could not stop them.', 'error'); }
        finally { setBusy(false); }
      } },
    ]);
  };

  const cancelForeign = () => showAlert('Stop these automations?', `Every active campaign enrollment and queued send ${data?.rep_name || 'this rep'} has on other reps' customers will be cancelled.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Stop them', style: 'destructive', onPress: async () => {
      setBusy(true);
      try { const r = (await api.post('/team-today/cancel-foreign', { rep_user_id: rep })).data; showToast(`Stopped ${r.enrollments_cancelled} enrollment${r.enrollments_cancelled === 1 ? '' : 's'} and ${r.sends_cancelled} queued send${r.sends_cancelled === 1 ? '' : 's'}.`, 'success'); load(); }
      catch (e: any) { showToast(e?.response?.data?.detail || 'Could not stop them.', 'error'); }
      finally { setBusy(false); }
    } },
  ]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('team-today-explain-screen')}>
      <ScreenHeader title="Where did these come from?" subtitle={data?.rep_name ? `${data.rep_name}'s day, record by record` : 'Record by record'} testID="team-today-explain-header" />
      {!data && !err ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : err ? <Text style={{ margin: 20, color: '#FF453A' }} {...tid('team-today-explain-error')}>{err}</Text> : (
        <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 60, gap: 12 }}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>
            {data!.foreign_stops ? `${data!.foreign_stops} of ${data!.stops.length} stops are on customers owned by someone else.` : 'Every stop is on this rep\'s own customers.'} Each card shows the record that put it on the list.
          </Text>
          {data!.stops.map(r => (
            <View key={r.n} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: r.contact.foreign ? `${WARN}88` : colors.border, padding: 14, gap: 8 }} {...tid(`explain-stop-${r.contact_id}`)}>
              <TouchableOpacity onPress={() => r.contact_id && router.push(`/contact/${r.contact_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>{r.n}. {r.name} <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>· {r.label}</Text></Text>
                {r.contact.foreign && <View style={{ backgroundColor: `${WARN}22`, borderRadius: 8, paddingHorizontal: 7, paddingVertical: 3 }}><Text style={{ fontSize: 11, fontWeight: '800', color: WARN }}>{r.contact.owner_name || 'another rep'}'s customer</Text></View>}
              </TouchableOpacity>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{r.why}</Text>
              <View style={{ gap: 3, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.5 }}>CUSTOMER RECORD</Text>
                <KV k="Owner" v={r.contact.owner_name || r.contact.owner_user_id || 'nobody'} colors={colors} />
                <KV k="Birthday" v={day(r.contact.birthday)} colors={colors} />
                <KV k="Anniversary" v={day(r.contact.anniversary)} colors={colors} />
                <KV k="Sold" v={day(r.contact.date_sold)} colors={colors} />
                <KV k="Tags" v={r.contact.tags?.join(', ')} colors={colors} />
                <KV k="Added" v={`${when(r.contact.created_at)}${r.contact.source ? ` via ${r.contact.source}` : ''}`} colors={colors} />
              </View>
              {r.task && (
                <View style={{ gap: 3, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }} {...tid(`explain-task-${r.contact_id}`)}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.5 }}>THE TASK</Text>
                  <KV k="Title" v={r.task.title} colors={colors} />
                  <KV k="Source" v={[r.task.source, r.task.campaign_name, r.task.nudged_by_name && `nudged by ${r.task.nudged_by_name}`, r.task.auto_generated && 'auto-generated'].filter(Boolean).join(' · ')} colors={colors} />
                  <KV k="Type" v={[r.task.task_type || r.task.type, r.task.action_type].filter(Boolean).join(' / ')} colors={colors} />
                  <KV k="Created" v={when(r.task.created_at)} colors={colors} />
                  <KV k="Due" v={when(r.task.due_date)} colors={colors} />
                </View>
              )}
              {r.conversation && (
                <View style={{ gap: 3, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }} {...tid(`explain-conv-${r.contact_id}`)}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.5 }}>THE CONVERSATION</Text>
                  <KV k="Thread owner" v={r.conversation.owner_name || r.conversation.user_id} colors={colors} />
                  <KV k="Inbox" v={r.conversation.inbox_id} colors={colors} />
                  <KV k="Channel" v={[r.conversation.channel, r.conversation.source].filter(Boolean).join(' · ')} colors={colors} />
                  <KV k="Started" v={when(r.conversation.created_at)} colors={colors} />
                  {(r.recent_messages || []).map((m, i) => (
                    <View key={i} style={{ marginTop: 6, borderLeftWidth: 2, borderLeftColor: m.auto_sent ? WARN : colors.border, paddingLeft: 8 }}>
                      <Text style={{ fontSize: 11.5, fontWeight: '700', color: colors.textSecondary }}>
                        {m.sender === 'contact' ? 'Customer' : m.sender === 'user' ? 'Rep' : m.sender} · {when(m.timestamp)}{m.auto_sent ? ` · AUTOMATED${m.trigger_type ? ` (${m.trigger_type})` : ''}` : ''}{m.campaign_name ? ` · campaign: ${m.campaign_name}` : ''}
                      </Text>
                      <Text style={{ fontSize: 12.5, color: colors.text }} numberOfLines={3}>{m.content}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          ))}
          <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: data!.foreign_enrollments.length ? `${WARN}88` : colors.border, padding: 14, gap: 8 }} {...tid('explain-foreign-automations')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.5 }}>AUTOMATIONS ON OTHER REPS' CUSTOMERS</Text>
            {!data!.foreign_enrollments.length ? <Text style={{ fontSize: 13, color: colors.textSecondary }}>None running. Good.</Text> : (
              <>
                {data!.foreign_enrollments.slice(0, 30).map(e => (
                  <Text key={e.id} style={{ fontSize: 12.5, color: colors.text, lineHeight: 17 }}>• {e.contact_name} <Text style={{ color: colors.textSecondary }}>({e.owner_name || 'another rep'}'s) in {e.campaign_name}{e.trigger_type ? ` · ${e.trigger_type}` : ''} · step {e.current_step} · enrolled {when(e.enrolled_at)}</Text></Text>
                ))}
                {data!.foreign_enrollments.length > 30 && <Text style={{ fontSize: 12, color: colors.textSecondary }}>+{data!.foreign_enrollments.length - 30} more</Text>}
                <TouchableOpacity onPress={cancelForeign} disabled={busy} style={{ marginTop: 6, alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FF453A', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 9, opacity: busy ? 0.5 : 1 }} {...tid('explain-cancel-foreign-btn')}>
                  <Ionicons name="stop-circle" size={15} color="#fff" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>Stop all {data!.foreign_enrollments.length}</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
          <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: leaks?.cross_store ? '#FF453A88' : leaks?.total ? `${WARN}88` : colors.border, padding: 14, gap: 8 }} {...tid('explain-leaks')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.5 }}>{leaks?.scope === 'everyone' ? 'LEAKED AUTOMATIONS, EVERY STORE' : 'LEAKED AUTOMATIONS, WHOLE TEAM'}</Text>
            {!leaks ? <ActivityIndicator color={GOLD} /> : !leaks.total ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('explain-leaks-none')}>Nothing is running on anyone else's customers. Clean.</Text> : (
              <>
                <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }} {...tid('explain-leaks-summary')}>
                  {leaks.total} enrollment{leaks.total === 1 ? '' : 's'} by {leaks.reps.length} rep{leaks.reps.length === 1 ? '' : 's'} on customers owned by someone else
                  {leaks.cross_store ? <Text style={{ fontWeight: '800', color: '#FF453A' }}>, {leaks.cross_store} of them on customers from another store</Text> : null}
                  {leaks.queued_sends ? `, ${leaks.queued_sends} text${leaks.queued_sends === 1 ? '' : 's'} still queued` : ''}.
                </Text>
                {leaks.reps.slice(0, 12).map(r => (
                  <TouchableOpacity key={r.rep_user_id} onPress={() => router.setParams({ rep: r.rep_user_id })} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`explain-leak-rep-${r.rep_user_id}`)}>
                    <Text style={{ flex: 1, fontSize: 12.5, color: colors.text }}>• {r.rep_name} <Text style={{ color: colors.textSecondary }}>· {r.enrollments} enrollment{r.enrollments === 1 ? '' : 's'}{r.cross_store ? `, ${r.cross_store} cross-store` : ''}</Text></Text>
                    <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
                  </TouchableOpacity>
                ))}
                {leaks.reps.length > 12 && <Text style={{ fontSize: 12, color: colors.textSecondary }}>+{leaks.reps.length - 12} more reps</Text>}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
                  {leaks.cross_store ? (
                    <TouchableOpacity onPress={() => cancelLeaks(true)} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FF453A', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 9, opacity: busy ? 0.5 : 1 }} {...tid('explain-cancel-cross-store-btn')}>
                      <Ionicons name="stop-circle" size={15} color="#fff" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>Stop the {leaks.cross_store} cross-store</Text>
                    </TouchableOpacity>
                  ) : null}
                  <TouchableOpacity onPress={() => cancelLeaks(false)} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#FF453A', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 9, opacity: busy ? 0.5 : 1 }} {...tid('explain-cancel-all-leaks-btn')}>
                    <Ionicons name="stop-circle-outline" size={15} color="#FF453A" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#FF453A' }}>Stop all {leaks.total}</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
