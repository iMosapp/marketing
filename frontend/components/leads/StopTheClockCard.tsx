import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';

type Clock = { measured: number; avg_seconds: number | null; median_seconds: number | null; fastest_seconds: number | null };
type Props = {
  clocks: { call: Clock; human_text: Clock; ai_text: Clock } | null | undefined;
  customer: { texted: number; replied: number; reply_rate: number | null; avg_seconds: number | null; median_seconds: number | null } | null | undefined;
  leads: number;
  colors: any;
  fmt: (s: number | null | undefined) => string;
  speedColor: (s: number) => string;
};

export const StopTheClockCard = ({ clocks, customer, leads, colors, fmt, speedColor }: Props) => {
  const cols = [
    { key: 'call', label: 'FIRST CALL', icon: 'call', c: clocks?.call },
    { key: 'human_text', label: 'FIRST HUMAN TEXT', icon: 'chatbubble', c: clocks?.human_text },
    { key: 'ai_text', label: 'FIRST AI REPLY', icon: 'sparkles', c: clocks?.ai_text },
  ];
  const rate = customer?.reply_rate;
  const rateColor = rate == null ? colors.textSecondary : rate >= 50 ? '#34C759' : rate >= 25 ? '#FF9500' : '#FF3B30';
  return (
    <View style={{ gap: 10 }}>
      <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, gap: 12 }} testID="stop-the-clock-card" dataSet={{ testid: 'stop-the-clock-card' } as any}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="stopwatch" size={15} color={GOLD} />
          <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text, letterSpacing: 0.8, flex: 1 }}>STOP THE CLOCK</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>{leads} lead{leads === 1 ? '' : 's'}</Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {cols.map(col => {
            const measured = col.c?.measured || 0;
            const avg = col.c?.avg_seconds ?? null;
            return (
              <View key={col.key} style={{ flex: 1, backgroundColor: colors.bg, borderRadius: 10, paddingVertical: 10, paddingHorizontal: 6, alignItems: 'center', gap: 3 }} testID={`clock-${col.key}`} dataSet={{ testid: `clock-${col.key}` } as any}>
                <Ionicons name={col.icon as any} size={14} color={measured && avg != null ? speedColor(avg) : colors.textSecondary} />
                <Text style={{ fontSize: 20, fontWeight: '800', color: measured && avg != null ? speedColor(avg) : colors.textSecondary }} numberOfLines={1}>{measured ? fmt(avg) : 'none'}</Text>
                <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4, textAlign: 'center' }} numberOfLines={2}>{col.label}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={1}>{measured ? `${measured} of ${leads}${col.c?.median_seconds != null ? ` · med ${fmt(col.c.median_seconds)}` : ''}` : 'not yet'}</Text>
              </View>
            );
          })}
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Average time from lead arrival to each first touch. Counts only leads that got that touch.</Text>
      </View>

      <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 14 }} testID="customer-reply-card" dataSet={{ testid: 'customer-reply-card' } as any}>
        <View style={{ alignItems: 'center', minWidth: 78 }}>
          <Text style={{ fontSize: 28, fontWeight: '800', color: rateColor }} testID="customer-reply-rate" dataSet={{ testid: 'customer-reply-rate' } as any}>{rate == null ? '--' : `${rate}%`}</Text>
          <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }}>REPLIED</Text>
        </View>
        <View style={{ flex: 1, gap: 3 }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>
            {customer?.avg_seconds != null ? `Customers reply in ${fmt(customer.avg_seconds)} on average` : 'No customer replies yet'}
          </Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>
            {`${customer?.replied || 0} of ${customer?.texted || 0} texted leads texted back${customer?.median_seconds != null ? ` · median ${fmt(customer.median_seconds)}` : ''}. Timed from the first text or call, only for leads that replied.`}
          </Text>
        </View>
      </View>
    </View>
  );
};
