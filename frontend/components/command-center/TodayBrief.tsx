import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { Card, Eyebrow, Progress } from './CcShell';
import { GOLD, AMBER, RED, detail, tid, type Brief } from './shared';

const ago = (iso: string) => { const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000)); return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`; };

// TODAY'S BRIEF: generated from the live data on demand, cached for six hours, never invents a deadline.
export const TodayBrief = ({ colors, showToast }: { colors: any; showToast: (m: string, t?: any, d?: number) => void }) => {
  const [b, setB] = useState<Brief | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(true);
  useEffect(() => { api.get('/command-center/advisor/brief').then(r => setB(r.data.brief)).catch(() => setB(null)); }, []);
  const generate = useCallback(async (force: boolean) => {
    setBusy(true);
    try { setB((await api.post('/command-center/advisor/brief', { force }, { timeout: 90000 })).data.brief); setOpen(true); }
    catch (e: any) { showToast(detail(e, 'The brief could not be generated'), 'error', 6000); }
    finally { setBusy(false); }
  }, []);
  return (
    <Card colors={colors} accent={GOLD} testID="cc-brief">
      <Eyebrow t="TODAY'S BRIEF" colors={colors} right={(
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          {b?.generated_at && <Text style={{ fontSize: 11.5, color: b.stale ? AMBER : colors.textSecondary }} {...tid('cc-brief-when')}>{ago(b.generated_at)}{b.stale ? ' · stale' : ''}</Text>}
          <TouchableOpacity onPress={() => generate(!!b)} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 11, height: 28, borderRadius: 14, backgroundColor: GOLD, opacity: busy ? 0.6 : 1 }} {...tid('cc-brief-generate')}>
            {busy ? <ActivityIndicator color="#1C1C1E" size="small" /> : <Ionicons name={b ? 'refresh' : 'sparkles'} size={13} color="#1C1C1E" />}
            <Text style={{ fontSize: 12, fontWeight: '800', color: '#1C1C1E' }}>{busy ? 'Working' : b ? 'Refresh' : 'Generate'}</Text>
          </TouchableOpacity>
          {!!b && <TouchableOpacity onPress={() => setOpen(v => !v)} style={{ padding: 2 }} {...tid('cc-brief-toggle')}><Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} /></TouchableOpacity>}
        </View>
      )} />
      {b === undefined ? <ActivityIndicator color={GOLD} /> : !b ? (
        <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }} {...tid('cc-brief-empty')}>No brief yet. Generate one and the advisor reads the One Big Thing, your three priorities, the roadmap, Waiting On and the Next Best Action, then names one thing to do today.</Text>
      ) : !open ? <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }} numberOfLines={2} {...tid('cc-brief-headline')}>{b.headline}</Text> : (
        <View style={{ gap: 12 }}>
          <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text, lineHeight: 22 }} {...tid('cc-brief-headline')}>{b.headline}</Text>
          {b.priorities?.length ? (
            <View style={{ gap: 8 }} {...tid('cc-brief-priorities')}>
              {b.priorities.map((p, i) => (
                <View key={i} style={{ gap: 3 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }}>{i + 1}. {p.title}</Text><Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{p.progress_pct}%</Text></View>
                  <Progress pct={p.progress_pct} colors={colors} />
                  {!!p.note && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{p.note}</Text>}
                </View>
              ))}
            </View>
          ) : <Text style={{ fontSize: 13, color: AMBER }} {...tid('cc-brief-no-priorities')}>No active priorities. Activate up to three so the brief has something to track.</Text>}
          <Text style={{ fontSize: 13.5, color: colors.text }} {...tid('cc-brief-next')}><Text style={{ fontWeight: '800' }}>Next Best Action: </Text>{b.next_best_action || 'none set'}</Text>
          {b.attention?.length ? <View style={{ gap: 3 }} {...tid('cc-brief-attention')}><Text style={{ fontSize: 11, fontWeight: '800', color: RED, letterSpacing: 0.8 }}>NEEDS ATTENTION</Text>{b.attention.map((a, i) => <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>• {a}</Text>)}</View> : null}
          <View style={{ borderRadius: 12, padding: 10, backgroundColor: GOLD + '1A', borderWidth: 1, borderColor: GOLD + '66', gap: 3 }} {...tid('cc-brief-recommendation')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.8 }}>DO THIS TODAY</Text>
            <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }}>{b.recommendation}</Text>
          </View>
          {b.missing?.length ? <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} {...tid('cc-brief-missing')}>Missing from the Command Center: {b.missing.join(' · ')}</Text> : null}
        </View>
      )}
    </Card>
  );
};
