import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';

type RetryRow = {
  user_id: string; name: string; misses: number; voicemails: number; retries: number;
  connected: number; replied: number; open: number; gave_up: number; just_tried: number; reach_rate: number | null;
};
type RetryData = { days: number; is_manager: boolean; totals: Omit<RetryRow, 'user_id' | 'name'>; reps: RetryRow[] };

const rateColor = (r: number | null) => (r == null ? GOLD : r >= 50 ? '#34C759' : r >= 25 ? '#FF9500' : '#FF3B30');

export const CallRetriesCard = ({ data, colors }: { data: RetryData | null; colors: any }) => {
  const t = data?.totals;
  const empty = !t || (t.misses === 0 && t.retries === 0);
  const showReps = !!data && (data.is_manager || data.reps.length > 1) && data.reps.length > 0;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, gap: 12, borderWidth: 1, borderColor: `${GOLD}44` }} testID="call-retries-card" dataSet={{ testid: 'call-retries-card' } as any}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="call-outline" size={15} color={GOLD} />
        </View>
        <Text style={{ fontSize: 12, fontWeight: '800', color: colors.text, letterSpacing: 0.8, flex: 1 }}>CALL RETRIES</Text>
        {!empty && t?.reach_rate != null && (
          <Text style={{ fontSize: 12, fontWeight: '700', color: rateColor(t.reach_rate) }} testID="call-retries-rate" dataSet={{ testid: 'call-retries-rate' } as any}>
            {t.reach_rate}% reached
          </Text>
        )}
      </View>

      {empty ? (
        <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} testID="call-retries-empty" dataSet={{ testid: 'call-retries-empty' } as any}>
          No missed calls in this period. When a call hits voicemail, the retry tasks and how many turned into real conversations show up here.
        </Text>
      ) : (
        <>
          <View style={{ flexDirection: 'row', gap: 8 }} testID="call-retries-stats" dataSet={{ testid: 'call-retries-stats' } as any}>
            {[
              { label: 'MISSED', val: t!.misses, color: '#FF9500' },
              { label: 'CONNECTED', val: t!.connected, color: '#34C759' },
              { label: 'TEXTED BACK', val: t!.replied, color: GOLD },
            ].map(s => (
              <View key={s.label} style={{ flex: 1, alignItems: 'center', backgroundColor: colors.bg, borderRadius: 10, paddingVertical: 10 }}>
                <Text style={{ fontSize: 20, fontWeight: '800', color: s.color }}>{s.val}</Text>
                <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.5 }} numberOfLines={1}>{s.label}</Text>
              </View>
            ))}
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2} testID="call-retries-footer" dataSet={{ testid: 'call-retries-footer' } as any}>
            {`${t!.retries} retr${t!.retries === 1 ? 'y' : 'ies'} · ${t!.open} still open · ${t!.just_tried} "just tried you" text${t!.just_tried === 1 ? '' : 's'}${t!.gave_up ? ` · ${t!.gave_up} hit max tries` : ''}`}
          </Text>

          {showReps && data!.reps.map(r => (
            <View key={r.user_id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border || `${GOLD}22` }} testID={`call-retries-rep-${r.user_id}`} dataSet={{ testid: `call-retries-rep-${r.user_id}` } as any}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{r.name}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
                  {r.misses} missed · {r.retries} retr{r.retries === 1 ? 'y' : 'ies'}{r.open ? ` · ${r.open} open` : ''}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: rateColor(r.reach_rate) }}>
                  {r.connected + r.replied} reached{r.reach_rate != null ? ` · ${r.reach_rate}%` : ''}
                </Text>
                <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.4 }}>
                  {r.connected} CALL · {r.replied} TEXT
                </Text>
              </View>
            </View>
          ))}
        </>
      )}
    </View>
  );
};
