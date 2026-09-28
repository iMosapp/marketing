import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Label, Chip, GoldButton, fmtPhone, deptLabel, deptsOfClient, directionHint, DIFFICULTIES, GOLD, tid, type Client, type Person, type Direction, type Difficulty, type Challenge } from './shared';

type Props = { person: Person | null; client: Client; colors: any; onClose: () => void; onStarted: () => void };

// "Shop now" on a person: pick the challenge (or let Jessi surprise them), who calls whom and how tough the shopper is; the call goes out in seconds.
export const ShopNowSheet = ({ person, client, colors, onClose, onStarted }: Props) => {
  const { showToast } = useToast();
  const [direction, setDirection] = useState<Direction | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [scriptId, setScriptId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [textGuide, setTextGuide] = useState(true);
  const [lead, setLead] = useState<string>(String(client.guide_lead_min ?? 0));
  const first = (person?.name || '').split(' ')[0];

  useEffect(() => {
    if (!person) return;
    setDirection(null); setDifficulty('medium'); setScriptId(null); setQuery(''); setError(''); setLead(String(client.guide_lead_min ?? 0));
    api.get(`/shop-clients/${client.id}/challenges`).then(r => setChallenges(r.data.challenges || [])).catch(() => setChallenges([]));
  }, [person?.id]);

  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    return challenges
      .filter(c => !person?.department || c.department === person.department)
      .filter(c => !q || c.title.toLowerCase().includes(q) || (c.purpose || '').toLowerCase().includes(q))
      .sort((a, b) => a.title.localeCompare(b.title));
  }, [challenges, person?.department, query]);
  const picked = challenges.find(c => c.id === scriptId) || null;
  const had = new Set((person as any)?.challenge_history || []);

  const go = async () => {
    if (!person) return;
    setBusy(true); setError('');
    try {
      const r = await api.post(`/shop-clients/${client.id}/calls/shop-now`, {
        target_id: person.id, difficulty, text_guide: textGuide,
        ...(textGuide ? (lead === 'ready' ? { ready_only: true } : { guide_lead_min: Number(lead) }) : {}),
        ...(scriptId ? { script_id: scriptId } : {}),
        ...(direction && !picked?.direction ? { direction } : {}),
      });
      const gt = r.data?.guide_text;
      const later = textGuide && lead !== '0';
      const ringLine = later ? (lead === 'ready' ? `rings when ${first} taps I\u2019m ready` : `rings in ${lead} min`) : `Calling ${first} now`;
      if (gt && !gt.ok) showToast(`${later ? 'Shop set up, ' + ringLine : ringLine}, but the guide text failed: ${gt.error || 'could not send'}`, 'error');
      else showToast(later ? `Guide texted to ${first} \u00b7 ${ringLine}` : (gt?.ok ? `${ringLine} \u00b7 call guide texted` : ringLine), 'success');
      onClose(); onStarted();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || (!e?.response ? 'No connection to the server, try again in a moment' : 'Could not place the call');
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally { setBusy(false); }
  };

  return (
    <Sheet visible={!!person} onClose={onClose} title={person ? `Shop ${first} now` : 'Shop now'} colors={colors} testID="shop-now-sheet" error={error}
      footer={<GoldButton label={textGuide && lead !== '0' ? (lead === 'ready' ? `Text guide, ring when ${first || 'they'} taps Ready` : `Text guide, ring in ${lead} min`) : `Call ${first || 'them'} now`} onPress={go} busy={busy} icon={textGuide && lead !== '0' ? 'chatbubble-ellipses' : 'call'} testID="shop-now-call" />}>
      {!!person && <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }} {...tid('shop-now-text')}>The AI {client.customer_noun || 'shopper'} calls {fmtPhone(person.phone)} in a few seconds. Business hours don't apply; if they don't pick up or press 2, the shop waits for you to tap Try again.</Text>}

      <View style={{ gap: 6 }}>
        <Label t="WHICH CHALLENGE" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          <Chip label="Surprise me" active={!scriptId} onPress={() => setScriptId(null)} colors={colors} testID="shop-now-challenge-any" />
          {picked && <Chip label={picked.title} active onPress={() => setScriptId(null)} colors={colors} testID="shop-now-challenge-picked" />}
        </View>
        {!scriptId && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Jessi picks a {deptLabel(person?.department || '', deptsOfClient(client)).toLowerCase()} challenge {first} has not had yet.</Text>}
        {options.length > 6 && (
          <TextInput value={query} onChangeText={setQuery} placeholder="Search challenges" placeholderTextColor={colors.textSecondary}
            style={{ height: 36, borderRadius: 10, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, color: colors.text, paddingHorizontal: 12, fontSize: 13 }} {...tid('shop-now-challenge-search')} />
        )}
        <ScrollView style={{ maxHeight: 210 }} nestedScrollEnabled showsVerticalScrollIndicator={false}>
          <View style={{ borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
            {options.length === 0 && <Text style={{ fontSize: 12.5, color: colors.textSecondary, padding: 12 }} {...tid('shop-now-challenge-empty')}>No {deptLabel(person?.department || '', deptsOfClient(client)).toLowerCase()} challenges in the library yet.</Text>}
            {options.map((c, i) => {
              const on = c.id === scriptId;
              return (
                <TouchableOpacity key={c.id} onPress={() => setScriptId(on ? null : c.id)}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 9, backgroundColor: on ? 'rgba(201,169,98,0.14)' : colors.card, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}
                  {...tid(`shop-now-challenge-${c.id}`)}>
                  <Ionicons name={c.direction === 'outbound' ? 'call-outline' : 'call'} size={14} color={on ? GOLD : colors.textSecondary} />
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={{ fontSize: 13.5, fontWeight: '700', color: on ? GOLD : colors.text }} numberOfLines={1}>{c.title}</Text>
                    <Text style={{ fontSize: 11.5, color: colors.textSecondary }} numberOfLines={1}>
                      {c.direction === 'outbound' ? 'Outbound' : 'Inbound'}{c.purpose ? ` · ${c.purpose}` : ''}{had.has(c.id) ? ' · had it before' : ''}
                    </Text>
                  </View>
                  {on && <Ionicons name="checkmark-circle" size={18} color={GOLD} />}
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>
      </View>

      {!picked?.direction && (
        <View style={{ gap: 6 }}>
          <Label t="WHO CALLS WHOM" colors={colors} />
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            <Chip label="Surprise me" active={!direction} onPress={() => setDirection(null)} colors={colors} testID="shop-now-direction-any" />
            <Chip label="Inbound" active={direction === 'inbound'} onPress={() => setDirection('inbound')} colors={colors} testID="shop-now-direction-inbound" />
            <Chip label="Outbound" active={direction === 'outbound'} onPress={() => setDirection('outbound')} colors={colors} testID="shop-now-direction-outbound" />
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>{direction ? directionHint(direction) : 'Inbound or outbound, whichever challenge comes up. Outbound: Jessi tells them the shopper left a lead and they are calling back.'}</Text>
        </View>
      )}
      {!!picked?.direction && <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('shop-now-direction-locked')}>{picked.direction === 'outbound' ? 'Outbound challenge: Jessi tells them the shopper left a lead and they are calling back.' : 'Inbound challenge: the shopper calls the store.'}</Text>}

      <View style={{ gap: 6 }}>
        <Label t="HOW TOUGH" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          {DIFFICULTIES.map(d => <Chip key={d.key} label={d.label} active={difficulty === d.key} onPress={() => setDifficulty(d.key)} colors={colors} testID={`shop-now-difficulty-${d.key}`} />)}
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>{DIFFICULTIES.find(d => d.key === difficulty)?.hint}</Text>
      </View>

      <TouchableOpacity onPress={() => setTextGuide(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: textGuide ? GOLD : colors.border, padding: 12 }} {...tid('shop-now-text-guide')}>
        <Ionicons name={textGuide ? 'checkbox' : 'square-outline'} size={22} color={textGuide ? GOLD : colors.textSecondary} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>Text {first || 'them'} the call guide first</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>The read-along script and 100-point scorecard for {deptLabel(person?.department || '', deptsOfClient(client)).toLowerCase()}, so they can follow it while the shopper is on the line.</Text>
        </View>
      </TouchableOpacity>
      {textGuide && (
        <View style={{ gap: 6 }}>
          <Label t="THEN RING" colors={colors} />
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            {LEADS.map(l => <Chip key={l.key} label={l.label} active={lead === l.key} onPress={() => setLead(l.key)} colors={colors} testID={`shop-now-lead-${l.key}`} />)}
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('shop-now-lead-hint')}>{LEADS.find(l => l.key === lead)?.hint.replace('{first}', first || 'they')}</Text>
        </View>
      )}
    </Sheet>
  );
};

const LEADS: { key: string; label: string; hint: string }[] = [
  { key: '0', label: 'Right away', hint: 'The text and the ring land together.' },
  { key: '1', label: 'In 1 min', hint: 'One minute to skim the guide, or sooner when {first} taps I\u2019m ready at the bottom of it.' },
  { key: '2', label: 'In 2 min', hint: 'Two minutes to read the guide, or sooner when {first} taps I\u2019m ready at the bottom of it.' },
  { key: '3', label: 'In 3 min', hint: 'Three minutes to read the guide, or sooner when {first} taps I\u2019m ready at the bottom of it.' },
  { key: '5', label: 'In 5 min', hint: 'Five minutes to read the guide, or sooner when {first} taps I\u2019m ready at the bottom of it.' },
  { key: 'ready', label: 'When they tap Ready', hint: 'No timer: the phone rings only when {first} taps I\u2019m ready on the guide. Cancels itself after 45 minutes.' },
];
