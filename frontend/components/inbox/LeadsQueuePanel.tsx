/**
 * LeadsQueuePanel — the shared internet-lead queue inside Inbox.
 * Reps on a source's workflow see its unclaimed leads + their own; managers see everything and can reassign/release.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, FlatList, RefreshControl, ActivityIndicator, Modal, Pressable, ScrollView, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { Avatar } from '../Avatar';

const GOLD = '#C9A962';
const GREEN = '#34C759';
const AMBER = '#FF9F0A';
const RED = '#FF453A';
const HEAT: Record<string, string> = { green: GREEN, amber: AMBER, red: RED };
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export const fmtWait = (s: number) => {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return h < 48 ? `${h}h ${m % 60}m` : `${Math.floor(h / 24)}d`;
};

export const heatFor = (secs: number | null, greenM: number, amberM: number) =>
  secs == null ? null : secs < greenM * 60 ? 'green' : secs < amberM * 60 ? 'amber' : 'red';

const liveWait = (it: any, now: number) => (it.waiting_since ? Math.max(0, Math.floor((now - new Date(it.waiting_since).getTime()) / 1000)) : null);

function LeadCard({ it, now, me, isManager, canClaim, colors, onClaim, onClaimCall, onOpen, onMenu }: any) {
  const wait = liveWait(it, now);
  const heat = heatFor(wait, it.green_m, it.amber_m);
  const border = it.claimed ? (heat ? HEAT[heat] : GREEN) : HEAT[heat || 'green'];
  const mine = it.claimed && it.claimed_by === me;
  let status: { text: string; color: string };
  if (!it.claimed) status = { text: `Waiting ${fmtWait(wait ?? 0)}`, color: HEAT[heat || 'green'] };
  else if (wait != null) status = { text: `Claimed · ${fmtWait(wait)} no reply`, color: HEAT[heat || 'amber'] };
  else if (it.first_reply_seconds != null) status = { text: `Replied in ${fmtWait(it.first_reply_seconds)}`, color: GREEN };
  else status = { text: 'Claimed', color: colors.textSecondary };
  return (
    <TouchableOpacity
      activeOpacity={0.8}
      onPress={() => onOpen(it)}
      style={{ marginHorizontal: 16, marginBottom: 10, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: `${border}80`, padding: 12 }}
      {...tid(`lead-card-${it.id}`)}
    >
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text, flex: 1 }} numberOfLines={1}>{it.contact_name}{it.is_test ? ' (test)' : ''}</Text>
        <View style={{ paddingHorizontal: 9, paddingVertical: 3, borderRadius: 10, backgroundColor: `${status.color}22` }} {...tid(`lead-status-${it.id}`)}>
          <Text style={{ fontSize: 12, fontWeight: '800', color: status.color }}>{status.text}</Text>
        </View>
        {(isManager || mine) && it.claimed && (
          <TouchableOpacity onPress={() => onMenu(it)} hitSlop={8} {...tid(`lead-menu-${it.id}`)}>
            <Ionicons name="ellipsis-horizontal" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 5 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: it.source_color }} />
        <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
          {it.source_name}{it.source_label ? ` · ${it.source_label}` : ''}{it.routing_kind === 'returning_owner' ? ' · Returning customer' : ''}
          {it.sms_opt_in ? <Text style={{ color: GREEN }}> · SMS opted in</Text> : null}
          {it.ai_on ? <Text style={{ color: GOLD }}> · Jessi replying</Text> : null}
        </Text>
      </View>
      {(it.vehicle || it.in_stock) && (
        <Text style={{ fontSize: 13, color: colors.text, marginTop: 4 }} numberOfLines={1}>
          {it.vehicle || it.in_stock?.name}{it.in_stock ? <Text style={{ color: GREEN, fontSize: 11, fontWeight: '800' }}>  IN STOCK{it.in_stock.stock_number ? ` #${it.in_stock.stock_number}` : ''}</Text> : null}
        </Text>
      )}
      {!!it.comments && <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 4, fontStyle: 'italic' }} numberOfLines={2}>"{it.comments}"</Text>}
      {!!it.handoff_note?.text && (
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: 6, backgroundColor: `${AMBER}14`, borderLeftWidth: 2, borderLeftColor: AMBER, paddingHorizontal: 8, paddingVertical: 5, borderRadius: 6 }} {...tid(`lead-handoff-${it.id}`)}>
          <Ionicons name="return-down-forward" size={13} color={AMBER} style={{ marginTop: 1 }} />
          <Text style={{ fontSize: 12, color: colors.text, flex: 1 }} numberOfLines={3}>
            <Text style={{ fontWeight: '800', color: AMBER }}>{it.handoff_note.by_name || 'Previous rep'}: </Text>{it.handoff_note.text}
          </Text>
        </View>
      )}
      {it.claimed && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 }}>
          <Avatar photo={it.claimed_by_photo} name={it.claimed_by_name || '?'} size="sm" />
          <Text style={{ fontSize: 12, color: colors.textSecondary, flex: 1 }} numberOfLines={1}>
            {mine ? 'You' : it.claimed_by_name || 'A rep'}{it.routing_kind === 'returning_owner' ? ' (their rep, auto-routed)' : ` claimed`}
            {it.routing_kind === 'returning_owner' && it.release_at && wait != null ? ` · back to queue ${fmtWait(Math.max(0, Math.floor((new Date(it.release_at).getTime() - now) / 1000)))}` : ''}
          </Text>
        </View>
      )}
      {!it.claimed && canClaim && (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
          <TouchableOpacity onPress={() => onClaim(it)} style={{ flex: 1, backgroundColor: GOLD, borderRadius: 10, paddingVertical: 9, alignItems: 'center' }} {...tid(`lead-claim-${it.id}`)}>
            <Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>Claim</Text>
          </TouchableOpacity>
          {!!it.phone && (
            <TouchableOpacity onPress={() => onClaimCall(it)} style={{ flex: 1, borderRadius: 10, paddingVertical: 9, alignItems: 'center', borderWidth: 1, borderColor: colors.border, flexDirection: 'row', justifyContent: 'center', gap: 6 }} {...tid(`lead-claim-call-${it.id}`)}>
              <Ionicons name="call" size={13} color={colors.text} />
              <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Claim & Call</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
    </TouchableOpacity>
  );
}

export default function LeadsQueuePanel({ userId, colors, showToast, onCounts }: any) {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'unclaimed' | 'mine' | 'claimed' | 'all'>('unclaimed');
  const [now, setNow] = useState(Date.now());
  const [menuFor, setMenuFor] = useState<any>(null);
  const [reassignFor, setReassignFor] = useState<any>(null);
  const [reps, setReps] = useState<any[]>([]);
  const [repSearch, setRepSearch] = useState('');
  const [showAllReps, setShowAllReps] = useState(false);
  const [releaseFor, setReleaseFor] = useState<any>(null);
  const [handoffNote, setHandoffNote] = useState('');
  const busy = useRef(false);

  const load = useCallback(async () => {
    if (!userId) return;
    try {
      const r = await api.get(`/leads/queue/${userId}`);
      setData(r.data);
      onCounts?.(r.data.counts);
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, [userId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15000);
    const p = setInterval(load, 60000);
    return () => { clearInterval(t); clearInterval(p); };
  }, [load]);

  const items = useMemo(() => {
    if (!data) return [];
    if (filter === 'unclaimed') return data.unclaimed;
    if (filter === 'mine') return data.mine;
    if (filter === 'claimed') return data.claimed;
    return [...data.unclaimed, ...data.mine, ...data.claimed];
  }, [data, filter]);

  const claim = async (it: any, thenCall = false) => {
    if (busy.current) return;
    busy.current = true;
    try {
      await api.post(`/lead-sources/claim/${it.id}?user_id=${userId}`);
      showToast?.(`${it.contact_name.split(' ')[0]} is yours`, 'success');
      if (thenCall) {
        router.push({ pathname: '/call-screen', params: { phone: it.phone, contact_name: it.contact_name, contact_id: it.contact_id, conversation_id: it.id } } as any);
      } else {
        router.push(`/thread/${it.id}` as any);
      }
      load();
    } catch (e: any) {
      showToast?.(e?.response?.data?.detail || 'Someone else got it first', 'error');
      load();
    } finally {
      busy.current = false;
    }
  };

  const openRelease = (it: any) => {
    setMenuFor(null);
    setHandoffNote('');
    setReleaseFor(it);
  };

  const release = async () => {
    const it = releaseFor;
    if (!it) return;
    setReleaseFor(null);
    try {
      await api.post(`/leads/queue/${userId}/release/${it.id}`, { note: handoffNote.trim() });
      showToast?.(handoffNote.trim() ? 'Back in the queue with your note' : 'Back in the queue', 'success');
      load();
    } catch (e: any) { showToast?.(e?.response?.data?.detail || 'Could not release', 'error'); }
  };

  const openReassign = async (it: any) => {
    setMenuFor(null);
    setReassignFor(it);
    setRepSearch('');
    setHandoffNote('');
    setShowAllReps(false);
    try { const r = await api.get(`/leads/queue/${userId}/reps`); setReps(r.data.reps || []); } catch { setReps([]); }
  };

  const visibleReps = useMemo(() => {
    const q = repSearch.trim().toLowerCase();
    if (q) return reps.filter(r => r.name.toLowerCase().includes(q));
    const members = reps.filter(r => r.on_workflow);
    return showAllReps || members.length === 0 ? reps : members;
  }, [reps, repSearch, showAllReps]);

  const reassign = async (rep: any) => {
    const it = reassignFor;
    setReassignFor(null);
    try {
      await api.post(`/leads/queue/${userId}/reassign/${it.id}`, { to_user_id: rep.user_id, note: handoffNote.trim() });
      showToast?.(`${it.contact_name.split(' ')[0]} moved to ${rep.name.split(' ')[0]}`, 'success');
      load();
    } catch (e: any) { showToast?.(e?.response?.data?.detail || 'Could not reassign', 'error'); }
  };

  if (loading) return <View style={{ padding: 40, alignItems: 'center' }}><ActivityIndicator color={GOLD} /></View>;
  if (!data?.visible) {
    return (
      <View style={{ padding: 40, alignItems: 'center' }} {...tid('leads-queue-not-visible')}>
        <Ionicons name="lock-closed" size={30} color={colors.textTertiary} />
        <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginTop: 10 }}>You're not on a lead source workflow yet. Ask your manager to add you in Lead Sources.</Text>
      </View>
    );
  }
  const c = data.counts;
  const chips: [typeof filter, string, number][] = [['unclaimed', 'Unclaimed', c.unclaimed], ['mine', 'Mine', c.mine]];
  if (data.is_manager) chips.push(['claimed', 'Claimed', c.claimed], ['all', 'All', c.unclaimed + c.mine + c.claimed]);

  return (
    <View style={{ flex: 1 }} {...tid('leads-queue-panel')}>
      <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingVertical: 8 }}>
        {chips.map(([k, label, n]) => (
          <TouchableOpacity key={k} onPress={() => setFilter(k)} style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: filter === k ? GOLD : colors.card, borderWidth: 1, borderColor: filter === k ? GOLD : colors.border }} {...tid(`leads-filter-${k}`)}>
            <Text style={{ fontSize: 12, fontWeight: '700', color: filter === k ? '#000' : colors.textSecondary }}>{label} {n}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <FlatList
        data={items}
        keyExtractor={(it: any) => it.id}
        extraData={now}
        renderItem={({ item }) => (
          <LeadCard it={item} now={now} me={userId} isManager={data.is_manager} canClaim={data.can_claim_source_ids.includes(item.source_id)} colors={colors}
            onClaim={(it: any) => claim(it)} onClaimCall={(it: any) => claim(it, true)} onOpen={(it: any) => router.push(`/thread/${it.id}` as any)} onMenu={setMenuFor} />
        )}
        contentContainerStyle={{ paddingTop: 4, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}
        ListEmptyComponent={
          <View style={{ padding: 40, alignItems: 'center' }} {...tid('leads-queue-empty')}>
            <Ionicons name="checkmark-done-circle" size={38} color={GREEN} />
            <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, marginTop: 10 }}>{filter === 'unclaimed' ? 'Queue is clear' : 'Nothing here'}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4, textAlign: 'center' }}>{filter === 'unclaimed' ? 'New internet leads land here the second they arrive.' : ''}</Text>
          </View>
        }
      />

      <Modal visible={!!menuFor} transparent animationType="fade" onRequestClose={() => setMenuFor(null)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} onPress={() => setMenuFor(null)}>
          <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, paddingBottom: 36 }} {...tid('lead-menu-sheet')}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text, marginBottom: 12 }}>{menuFor?.contact_name}</Text>
            {[
              { k: 'open', label: 'Open thread', icon: 'chatbubble', onPress: () => { const it = menuFor; setMenuFor(null); router.push(`/thread/${it.id}` as any); } },
              ...(data.is_manager ? [{ k: 'reassign', label: 'Reassign to…', icon: 'swap-horizontal', onPress: () => openReassign(menuFor) }] : []),
              { k: 'release', label: 'Release to queue', icon: 'arrow-undo', color: AMBER, onPress: () => openRelease(menuFor) },
            ].map((a: any) => (
              <TouchableOpacity key={a.k} onPress={a.onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 13 }} {...tid(`lead-menu-${a.k}`)}>
                <Ionicons name={a.icon} size={18} color={a.color || colors.text} />
                <Text style={{ fontSize: 15, fontWeight: '600', color: a.color || colors.text }}>{a.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </Pressable>
      </Modal>

      <Modal visible={!!releaseFor} transparent animationType="slide" onRequestClose={() => setReleaseFor(null)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} onPress={() => setReleaseFor(null)}>
          <Pressable onPress={() => {}} style={{ backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, paddingBottom: 36 }} {...tid('lead-release-sheet')}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Release {releaseFor?.contact_name?.split(' ')[0]} to the queue</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4 }}>Leave one line so the next rep knows where things stand.</Text>
            <TextInput
              value={handoffNote}
              onChangeText={t => setHandoffNote(t.slice(0, 200))}
              placeholder='e.g. "Left VM twice, wants a Tahoe under 60k, best after 5"'
              placeholderTextColor={colors.textSecondary}
              autoFocus
              multiline
              style={{ marginTop: 12, minHeight: 64, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text, borderRadius: 12, borderWidth: 1, borderColor: `${AMBER}66`, backgroundColor: `${AMBER}0F`, textAlignVertical: 'top' }}
              {...tid('lead-release-note')}
            />
            <Text style={{ fontSize: 11, color: colors.textTertiary, textAlign: 'right', marginTop: 4 }}>{handoffNote.length}/200</Text>
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
              <TouchableOpacity onPress={() => setReleaseFor(null)} style={{ flex: 1, paddingVertical: 12, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }} {...tid('lead-release-cancel')}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={release} style={{ flex: 2, paddingVertical: 12, borderRadius: 12, backgroundColor: AMBER, alignItems: 'center' }} {...tid('lead-release-confirm')}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: '#000' }}>{handoffNote.trim() ? 'Release with note' : 'Release without note'}</Text>
              </TouchableOpacity>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={!!reassignFor} transparent animationType="slide" onRequestClose={() => setReassignFor(null)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} onPress={() => setReassignFor(null)}>
          <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, paddingBottom: 36, maxHeight: '70%' }} {...tid('lead-reassign-sheet')}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Move {reassignFor?.contact_name} to…</Text>
            <TextInput value={handoffNote} onChangeText={t => setHandoffNote(t.slice(0, 200))} placeholder="One line for the next rep (optional)" placeholderTextColor={colors.textSecondary}
              style={{ marginTop: 10, paddingHorizontal: 12, paddingVertical: 9, fontSize: 15, color: colors.text, borderRadius: 12, borderWidth: 1, borderColor: `${AMBER}66`, backgroundColor: `${AMBER}0F` }} {...tid('lead-reassign-note')} />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8, paddingHorizontal: 12, borderRadius: 12, borderWidth: 1, borderColor: colors.border }}>
              <Ionicons name="search" size={15} color={colors.textSecondary} />
              <TextInput value={repSearch} onChangeText={setRepSearch} placeholder="Search reps" placeholderTextColor={colors.textSecondary}
                style={{ flex: 1, paddingVertical: 9, fontSize: 15, color: colors.text }} {...tid('lead-reassign-search')} />
            </View>
            {!repSearch && reps.some(r => r.on_workflow) && (
              <TouchableOpacity onPress={() => setShowAllReps(v => !v)} style={{ paddingVertical: 8 }} {...tid('lead-reassign-toggle-all')}>
                <Text style={{ fontSize: 12, color: GOLD, fontWeight: '700' }}>{showAllReps ? 'Show workflow reps only' : `Show everyone (${reps.length})`}</Text>
              </TouchableOpacity>
            )}
            <ScrollView style={{ marginTop: 4 }} keyboardShouldPersistTaps="handled">
              {visibleReps.map(r => {
                const current = r.user_id === reassignFor?.claimed_by;
                return (
                  <TouchableOpacity key={r.user_id} disabled={current} onPress={() => reassign(r)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, opacity: current ? 0.45 : 1 }} {...tid(`lead-reassign-rep-${r.user_id}`)}>
                    <Avatar photo={r.photo_url} name={r.name} size="sm" />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{r.name}{current ? ' · current' : ''}</Text>
                      <Text style={{ fontSize: 12, color: r.on_shift ? GREEN : colors.textTertiary }}>
                        {r.on_shift ? 'On shift' : 'Off shift'} · {r.open_leads} lead{r.open_leads === 1 ? '' : 's'} open{r.on_workflow ? <Text style={{ color: GOLD }}> · workflow</Text> : null}
                      </Text>
                    </View>
                    {!current && <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />}
                  </TouchableOpacity>
                );
              })}
              {reps.length === 0 && <ActivityIndicator color={GOLD} style={{ marginVertical: 20 }} />}
              {reps.length > 0 && visibleReps.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', marginVertical: 16 }}>No reps match</Text>}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}
