import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';

type RetryRow = {
  user_id: string; name: string; misses: number; voicemails: number; retries: number;
  connected: number; replied: number; open: number; gave_up: number; just_tried: number; reach_rate: number | null; tip?: string;
};
type Attempt = { attempt: number; retries: number; connected: number; replied: number; just_tried: number };
type Insight = { best_attempt: number | null; replied_total: number; share_pct: number | null; median_reply_minutes: number | null };
type RetryData = {
  days: number; is_manager: boolean; totals: Omit<RetryRow, 'user_id' | 'name' | 'tip'>; reps: RetryRow[];
  by_attempt?: Attempt[]; insight?: Insight; my_tip?: string;
};

const rateColor = (r: number | null) => (r == null ? GOLD : r >= 50 ? '#34C759' : r >= 25 ? '#FF9500' : '#FF3B30');
const fmtMins = (m: number) => (m < 60 ? `${Math.max(1, m)} min` : m < 1440 ? `${Math.round(m / 60)} hr` : `${Math.round(m / 1440)} d`);

const AttemptBars = ({ rows, best, colors }: { rows: Attempt[]; best: number | null; colors: any }) => {
  const max = Math.max(1, ...rows.map(r => r.replied));
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 10, paddingHorizontal: 4 }} testID="call-retries-attempt-bars" dataSet={{ testid: 'call-retries-attempt-bars' } as any}>
      {rows.map(r => {
        const hot = r.attempt === best;
        return (
          <View key={r.attempt} style={{ alignItems: 'center', width: 44 }} testID={`call-retries-attempt-${r.attempt}`} dataSet={{ testid: `call-retries-attempt-${r.attempt}` } as any}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: hot ? GOLD : colors.textSecondary, marginBottom: 3 }}>{r.replied}</Text>
            <View style={{ width: 26, height: 6 + Math.round(30 * r.replied / max), borderRadius: 4, backgroundColor: hot ? GOLD : `${GOLD}44` }} />
            <Text style={{ fontSize: 10, fontWeight: '700', color: hot ? colors.text : colors.textSecondary, marginTop: 4 }}>#{r.attempt}</Text>
          </View>
        );
      })}
    </View>
  );
};

const TipLine = ({ text, colors, testid, compact }: { text: string; colors: any; testid: string; compact?: boolean }) => (
  <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: compact ? 6 : 0 }} testID={testid} dataSet={{ testid } as any}>
    <Ionicons name="bulb-outline" size={compact ? 12 : 14} color={GOLD} style={{ marginTop: 1 }} />
    <Text style={{ flex: 1, fontSize: compact ? 12 : 13, lineHeight: compact ? 16 : 18, color: compact ? colors.textSecondary : colors.text, fontStyle: compact ? 'italic' : 'normal' }}>{text}</Text>
  </View>
);

export const CallRetriesCard = ({ data, colors }: { data: RetryData | null; colors: any }) => {
  const t = data?.totals;
  const empty = !t || (t.misses === 0 && t.retries === 0);
  const showReps = !!data && (data.is_manager || data.reps.length > 1) && data.reps.length > 0;
  const ins = data?.insight;
  const bars = (data?.by_attempt || []).filter(b => b.retries > 0);
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

          {!!ins?.best_attempt && bars.length > 0 && (
            <View style={{ backgroundColor: colors.bg, borderRadius: 10, padding: 12, gap: 10 }} testID="call-retries-insight" dataSet={{ testid: 'call-retries-insight' } as any}>
              <Text style={{ fontSize: 10, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>TEXTS BACK BY MISS #</Text>
              <AttemptBars rows={bars} best={ins.best_attempt} colors={colors} />
              <Text style={{ fontSize: 12, color: colors.text, lineHeight: 17 }} testID="call-retries-insight-text" dataSet={{ testid: 'call-retries-insight-text' } as any}>
                {`Most texts back come after miss #${ins.best_attempt}${ins.share_pct != null ? ` (${ins.share_pct}% of replies)` : ''}${ins.median_reply_minutes != null ? `, usually within ${fmtMins(ins.median_reply_minutes)} of the just-tried text` : ''}. Send it by then.`}
              </Text>
            </View>
          )}

          {!!data?.my_tip && (
            <View style={{ backgroundColor: `${GOLD}14`, borderRadius: 10, padding: 10, borderWidth: 1, borderColor: `${GOLD}33` }}>
              <Text style={{ fontSize: 10, fontWeight: '800', color: GOLD, letterSpacing: 0.8, marginBottom: 4 }}>YOUR TIP</Text>
              <TipLine text={data.my_tip} colors={colors} testid="call-retries-my-tip" />
            </View>
          )}

          {showReps && data!.reps.map(r => (
            <View key={r.user_id} style={{ paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border || `${GOLD}22` }} testID={`call-retries-rep-${r.user_id}`} dataSet={{ testid: `call-retries-rep-${r.user_id}` } as any}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
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
              {!!r.tip && <TipLine text={r.tip} colors={colors} testid={`call-retries-rep-tip-${r.user_id}`} compact />}
            </View>
          ))}
        </>
      )}
    </View>
  );
};
