/**
 * Speed-to-Lead timers — live "Waiting Xm" chip (inbox rows) and banner (thread).
 * Green < 5 min, amber 5-15, red 15+. Self-ticking; stops when a human replies.
 */
import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export function waitInfo(receivedAt: string) {
  const mins = Math.max(0, Math.floor((Date.now() - new Date(receivedAt).getTime()) / 60000));
  const color = mins < 5 ? '#34C759' : mins < 15 ? '#FF9500' : '#FF3B30';
  let label;
  if (mins < 60) label = `${mins}m`;
  else if (mins < 1440) label = `${Math.floor(mins / 60)}h ${mins % 60}m`;
  else label = `${Math.floor(mins / 1440)}d`;
  return { mins, color, label };
}

function useTick(intervalMs: number) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(x => x + 1), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
}

export function LeadWaitChip({ receivedAt }: { receivedAt: string }) {
  useTick(30000);
  if (!receivedAt) return null;
  const { color, label } = waitInfo(receivedAt);
  return (
    <View
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 3,
        backgroundColor: `${color}18`, borderRadius: 6,
        paddingHorizontal: 6, paddingVertical: 2,
        borderWidth: 1, borderColor: `${color}35`,
      }}
      testID="lead-wait-chip"
      dataSet={{ testid: 'lead-wait-chip' }}
    >
      <Ionicons name="stopwatch" size={10} color={color} />
      <Text style={{ fontSize: 10, fontWeight: '800', color, letterSpacing: 0.2 }}>Waiting {label}</Text>
    </View>
  );
}

export function LeadWaitBanner({ receivedAt, sourceName }: { receivedAt: string; sourceName?: string }) {
  useTick(15000);
  if (!receivedAt) return null;
  const { color, label } = waitInfo(receivedAt);
  return (
    <View
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 10,
        marginHorizontal: 12, marginTop: 8, marginBottom: 2,
        paddingHorizontal: 12, paddingVertical: 10,
        borderRadius: 14, backgroundColor: `${color}14`,
        borderWidth: 1, borderColor: `${color}40`,
      }}
      testID="lead-wait-banner"
      dataSet={{ testid: 'lead-wait-banner' }}
    >
      <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: `${color}22`, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name="flame" size={17} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, fontWeight: '800', color }} testID="lead-wait-banner-title" dataSet={{ testid: 'lead-wait-banner-title' }}>
          New internet lead — waiting {label}
        </Text>
        <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 1 }} numberOfLines={1}>
          Reply now to win the deal{sourceName ? ` · ${sourceName}` : ''}
        </Text>
      </View>
      <Ionicons name="stopwatch" size={18} color={color} />
    </View>
  );
}
