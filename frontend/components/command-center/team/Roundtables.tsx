import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import VoiceTextInput from '../../VoiceTextInput';
import { GoldButton } from '../../mystery-shops/shared';
import { Card, Eyebrow, Empty, Pill } from '../CcShell';
import { Monogram } from './Roster';
import { GOLD, RT_STATUS, detail, tid, execColor, execShort, type Executive, type RoundtableSummary } from '../shared';

type Props = { colors: any; execs: Executive[]; prefill: string; onOpen: (id: string) => void };

// LEADERSHIP ROUNDTABLE: the founder states the question; the Chief of Staff picks the room; nothing runs until the founder presses Start.
export const Roundtables = ({ colors, execs, prefill, onOpen }: Props) => {
  const { showToast } = useToast();
  const [rows, setRows] = useState<RoundtableSummary[] | null>(null);
  const [q, setQ] = useState(prefill);
  const [busy, setBusy] = useState(false);
  const load = async () => { try { setRows((await api.get('/command-center/team/roundtables')).data.roundtables); } catch (e: any) { showToast(detail(e, 'Could not load'), 'error'); } };
  useEffect(() => { load(); }, []);
  useEffect(() => { if (prefill) setQ(prefill); }, [prefill]);
  const convene = async () => {
    const t = q.trim();
    if (!t || busy) return;
    setBusy(true);
    try { const r = (await api.post('/command-center/team/roundtables', { question: t }, { timeout: 90000 })).data; setQ(''); onOpen(r.id); }
    catch (e: any) { showToast(detail(e, 'The Chief of Staff could not convene the room'), 'error', 6000); }
    finally { setBusy(false); }
  };
  return (
    <View style={{ gap: 16 }} {...tid('cc-roundtables')}>
      <Card colors={colors} accent={GOLD} testID="cc-convene-card">
        <Eyebrow t="CONVENE A ROUNDTABLE" colors={colors} />
        <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>State the question or opportunity. The Chief of Staff picks the executives whose departments are affected, each assesses independently, then they challenge each other once, and you get a decision brief with every disagreement kept intact.</Text>
        <VoiceTextInput value={q} onChangeText={setQ} placeholder="Should we spin Mystery Shops out as its own brand?" showVoice voiceAppend multiline testID="cc-convene-input" />
        {busy ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('cc-convene-busy')}><ActivityIndicator color={GOLD} size="small" /><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>The Chief of Staff is choosing the room. 10 to 30 seconds.</Text></View>
        ) : <GoldButton label="Ask the Chief of Staff to convene" icon="people" onPress={convene} disabled={!q.trim()} testID="cc-convene-submit" />}
      </Card>
      <View style={{ gap: 8 }}>
        <Eyebrow t="ROUNDTABLES" colors={colors} />
        {rows === null && <ActivityIndicator color={GOLD} />}
        {rows && !rows.length && <Empty t="No roundtables yet. The first one is the one that teaches you how your team disagrees." colors={colors} testID="cc-roundtables-empty" />}
        {(rows || []).map(r => {
          const st = RT_STATUS[r.status] || RT_STATUS.failed;
          return (
            <TouchableOpacity key={r.id} onPress={() => onOpen(r.id)} style={{ padding: 14, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: r.status === 'awaiting_decision' ? GOLD : colors.border, gap: 8 }} {...tid(`cc-rt-${r.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }} numberOfLines={2}>{r.title}</Text>
                <Pill text={st.label} color={st.color} icon={st.icon} testID={`cc-rt-${r.id}-status`} />
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                {r.participants.map(k => <Monogram key={k} e={{ short: execShort(execs, k), color: execColor(execs, k) }} size={26} />)}
                <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginLeft: 4 }}>{r.dissent_count ? `${r.dissent_count} unresolved disagreement${r.dissent_count > 1 ? 's' : ''} · ` : ''}${r.cost_usd.toFixed(2)} · {new Date(r.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</Text>
                <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} style={{ marginLeft: 'auto' }} />
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
};
