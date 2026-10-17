// "Add people I met at…": pick where you met (from How we met), see who joins and who is skipped and why, then add them in one tap.
import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { SheetShell, Eyebrow, GoldButton, Chip } from './Sheet';
import { GOLD, GREEN, AMBER, tid } from './utils';

type Person = { id: string; name: string; met: string; status: string; reason: string };
type Preview = { campaign: { id: string; name: string; active: boolean }; event: string; query: string; matched: number; counts: Record<string, number>; ok_ids: string[]; people: Person[]; limit: number };
type Props = { userId: string; campaignId: string; campaignName: string; colors: any; onClose: () => void; onAdded: (n: number) => void; showToast: (m: string, t?: any, d?: number) => void };

const errText = (e: any, f: string) => e?.response?.data?.detail || f;

export function MetAtSheet({ userId, campaignId, campaignName, colors, onClose, onAdded, showToast }: Props) {
  const [events, setEvents] = useState<{ key: string; label: string; count: number }[] | null>(null);
  const [q, setQ] = useState('');
  const [pv, setPv] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.get(`/met-at/${userId}/events`).then(r => setEvents(r.data?.events || [])).catch(() => setEvents([]));
  }, [userId]);

  const look = async (event: string) => {
    if (!event.trim()) return;
    setLoading(true); setErr('');
    try { setPv((await api.get(`/met-at/${userId}/preview`, { params: { campaign_id: campaignId, event: event.trim() } })).data); }
    catch (e) { setErr(errText(e, 'Could not look that up')); }
    finally { setLoading(false); }
  };

  const add = async () => {
    if (!pv?.ok_ids.length) return;
    setAdding(true);
    try {
      const r = (await api.post(`/met-at/${userId}/enroll`, { campaign_id: campaignId, event: pv.query, contact_ids: pv.ok_ids }, { timeout: 120000 })).data;
      const n = r?.enrolled || 0;
      showToast(n ? `${n} ${n === 1 ? 'person' : 'people'} from ${pv.event} added to ${campaignName}` : 'Nobody was added', n ? 'success' : 'error', 4000);
      onAdded(n);
      onClose();
    } catch (e) { setErr(errText(e, 'Could not add them')); }
    finally { setAdding(false); }
  };

  const n = pv?.ok_ids.length || 0;
  const skipped = pv ? pv.matched - n : 0;
  const footer = pv ? (
    <>
      {!pv.campaign.active ? <Text style={{ fontSize: 12.5, color: AMBER, textAlign: 'center' }} {...tid('met-at-inactive')}>This plan is turned off. Turn it on first.</Text> : null}
      <GoldButton label={adding ? 'Adding…' : n ? `Add ${n} ${n === 1 ? 'person' : 'people'} to ${campaignName}` : 'Nobody new to add'} icon="person-add"
        onPress={add} disabled={adding || !n || !pv.campaign.active} testId="met-at-confirm" />
    </>
  ) : null;

  return (
    <SheetShell title="Add people I met at…" subtitle={`Everyone you met at one place joins ${campaignName}. Up to 100 at a time.`} onClose={onClose} testId="met-at-sheet" colors={colors} footer={footer}>
      {!pv ? (
        <>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TextInput value={q} onChangeText={t => { setQ(t); setErr(''); }} onSubmitEditing={() => look(q)} placeholder="NADA, the golf tournament, Vegas" placeholderTextColor={colors.textTertiary} returnKeyType="search"
              style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: colors.text, borderWidth: 1, borderColor: colors.border }} {...tid('met-at-input')} />
            <TouchableOpacity onPress={() => look(q)} disabled={!q.trim() || loading} style={{ width: 48, borderRadius: 12, backgroundColor: q.trim() ? GOLD : colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid('met-at-search')}>
              {loading ? <ActivityIndicator color="#111" /> : <Ionicons name="search" size={20} color={q.trim() ? '#111' : colors.textTertiary} />}
            </TouchableOpacity>
          </View>
          <Eyebrow colors={colors}>WHERE YOU MET PEOPLE</Eyebrow>
          {events === null ? <ActivityIndicator color={GOLD} /> : events.length === 0 ? (
            <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('met-at-no-events')}>No one has How we met filled in yet. Jessi fills it from your voice notes, or add it on a contact's profile.</Text>
          ) : (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {events.map(e => <Chip key={e.key} label={`${e.label} · ${e.count}`} icon="location-outline" colors={colors} testId={`met-at-event-${e.key.replace(/\s+/g, '-')}`} onPress={() => { setQ(e.label); look(e.label); }} />)}
            </View>
          )}
        </>
      ) : (
        <>
          <TouchableOpacity onPress={() => { setPv(null); setErr(''); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} {...tid('met-at-back')}>
            <Ionicons name="chevron-back" size={16} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Pick another place</Text>
          </TouchableOpacity>
          <View style={{ gap: 4 }}>
            <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }} {...tid('met-at-title')}>Met at {pv.event} · {pv.matched} {pv.matched === 1 ? 'person' : 'people'}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('met-at-summary')}>{n} will join{skipped ? ` · ${skipped} skipped` : ''}</Text>
          </View>
          {pv.matched === 0 ? (
            <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('met-at-none')}>Nobody is marked as met at "{pv.query}". Try another name for it.</Text>
          ) : (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
              {pv.people.map((p, i) => <PersonRow key={p.id} p={p} first={i === 0} colors={colors} />)}
            </View>
          )}
        </>
      )}
      {err ? <Text style={{ fontSize: 13, color: '#FF3B30' }} {...tid('met-at-error')}>{err}</Text> : null}
    </SheetShell>
  );
}

const PersonRow = ({ p, first, colors }: { p: Person; first: boolean; colors: any }) => {
  const ok = p.status === 'ok';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 10, borderTopWidth: first ? 0 : 1, borderTopColor: colors.border, opacity: ok ? 1 : 0.7 }} {...tid(`met-at-person-${p.id}`)}>
      <Ionicons name={ok ? 'checkmark-circle' : 'remove-circle-outline'} size={18} color={ok ? GREEN : colors.textTertiary} />
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14.5, fontWeight: '700', color: colors.text }} numberOfLines={1}>{p.name}</Text>
        {p.met ? <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{p.met}</Text> : null}
      </View>
      <Text style={{ fontSize: 11.5, fontWeight: '800', color: ok ? GREEN : AMBER, maxWidth: 150, textAlign: 'right' }} numberOfLines={2} {...tid(`met-at-status-${p.id}`)}>{ok ? 'Joins' : p.reason}</Text>
    </View>
  );
};
