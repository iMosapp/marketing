import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, GREEN, RED, tid } from '../scripts/shared';

type Rep = { id: string; name: string; role?: string; voice: { status: string; enrolled: boolean; percent?: number | null; at?: string | null }; calls: { total: number; verified: number; mismatched: number; unchecked: number } };
type Coverage = { days: number; store_name?: string | null; eagle: boolean; totals: { reps: number; enrolled: number; calls: Rep['calls'] }; reps: Rep[] };

const SHOW = 8;

function Stat({ value, label, color, colors, id }: { value: number | string; label: string; color: string; colors: any; id: string }) {
  return (
    <View style={{ flex: 1, minWidth: 90 }} {...tid(id)}>
      <Text style={{ fontSize: 22, fontWeight: '800', color }}>{value}</Text>
      <Text style={{ fontSize: 11, color: colors.textSecondary, lineHeight: 15 }}>{label}</Text>
    </View>
  );
}

function RepRow({ r, colors }: { r: Rep; colors: any }) {
  const v = r.voice;
  const on = v.enrolled;
  const partial = !on && v.status === 'partial';
  const voiceLabel = on ? 'Voice print' : partial ? `Heard ${Math.round(v.percent || 0)}%` : v.status === 'failed' ? 'Enroll failed' : 'No voice print';
  const c = r.calls;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`voice-coverage-rep-${r.id}`)}>
      <Ionicons name={on ? 'shield-checkmark' : partial ? 'shield-half' : 'shield-outline'} size={18} color={on ? GREEN : partial ? GOLD : colors.textSecondary} />
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{r.name}</Text>
        <Text style={{ fontSize: 11, color: on ? GREEN : colors.textSecondary }} {...tid(`voice-coverage-rep-voice-${r.id}`)}>{voiceLabel}</Text>
      </View>
      <View style={{ alignItems: 'flex-end' }} {...tid(`voice-coverage-rep-calls-${r.id}`)}>
        {c.total === 0 ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>No recorded calls</Text> : (
          <>
            <Text style={{ fontSize: 13, fontWeight: '700', color: on ? GREEN : colors.textSecondary }}>{c.verified} of {c.total} verified</Text>
            {c.mismatched > 0 && <Text style={{ fontSize: 11, color: RED }}>{c.mismatched} didn't match</Text>}
          </>
        )}
      </View>
    </View>
  );
}

export function VoiceCoverageCard() {
  const { colors } = useThemeStore();
  const [data, setData] = useState<Coverage | null | undefined>(undefined);
  const [all, setAll] = useState(false);
  const load = useCallback(async () => {
    try { const r = await api.get('/interview/coverage', { params: { days: 7 } }); setData(r.data); }
    catch { setData(null); }
  }, []);
  useEffect(() => { load(); }, [load]);
  if (data === null) return null;
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border, marginBottom: 16 } as const;
  if (data === undefined) return <View style={card}><ActivityIndicator color={GOLD} /></View>;
  const t = data.totals;
  const reps = all ? data.reps : data.reps.slice(0, SHOW);
  return (
    <View style={card} {...tid('voice-coverage-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GREEN + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="shield-checkmark" size={19} color={GREEN} /></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Voice ID coverage</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>{data.store_name ? `${data.store_name} · ` : ''}last {data.days} days</Text>
        </View>
      </View>
      {!data.eagle && <Text style={{ fontSize: 12, color: GOLD, marginTop: 10 }} {...tid('voice-coverage-offline')}>Voice ID is not running on this server yet, so new calls are not being checked.</Text>}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 14 }}>
        <Stat id="voice-coverage-enrolled" value={`${t.enrolled}/${t.reps}`} label="reps with a voice print" color={t.enrolled === t.reps && t.reps > 0 ? GREEN : GOLD} colors={colors} />
        <Stat id="voice-coverage-calls" value={t.calls.total} label="recorded calls" color={colors.text} colors={colors} />
        <Stat id="voice-coverage-verified" value={t.calls.verified} label="verified it was the rep" color={GREEN} colors={colors} />
        <Stat id="voice-coverage-mismatched" value={t.calls.mismatched} label="voice didn't match" color={t.calls.mismatched > 0 ? RED : colors.textSecondary} colors={colors} />
      </View>
      <View style={{ marginTop: 12 }}>
        {reps.map(r => <RepRow key={r.id} r={r} colors={colors} />)}
      </View>
      {data.reps.length > SHOW && (
        <TouchableOpacity onPress={() => setAll(a => !a)} style={{ marginTop: 8, alignSelf: 'flex-start' }} {...tid('voice-coverage-toggle')}>
          <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{all ? 'Show fewer' : `Show all ${data.reps.length}`}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}
