import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { Ionicons } from '@expo/vector-icons';
import { scoreTone, tid } from './shared';

// Circular score gauge: gold ring track, tone-colored arc, % in the middle.
export const ScoreRing = ({ pct, size = 64, stroke = 6, label, colors, testID }: { pct: number | null | undefined; size?: number; stroke?: number; label?: string; colors: any; testID?: string }) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const tone = scoreTone(pct);
  const dash = pct == null ? 0 : (c * Math.max(0, Math.min(100, pct))) / 100;
  return (
    <View style={{ width: size, alignItems: 'center' }} {...(testID ? tid(testID) : {})}>
      <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
        <Svg width={size} height={size} style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}>
          <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.border} strokeWidth={stroke} fill="none" />
          {pct != null && <Circle cx={size / 2} cy={size / 2} r={r} stroke={tone} strokeWidth={stroke} fill="none" strokeDasharray={`${dash} ${c}`} strokeLinecap="round" />}
        </Svg>
        <Text style={{ fontSize: size * 0.28, fontWeight: '800', color: pct == null ? colors.textSecondary : colors.text }}>{pct == null ? '--' : `${pct}%`}</Text>
      </View>
      {label ? <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5, marginTop: 4 }}>{label}</Text> : null}
    </View>
  );
};

// Compact "Scored 78% · 1 critical miss" pill for call cards. Tap opens the evaluation.
export const ScorePill = ({ pct, misses = 0, pending, onPress, testID }: { pct: number | null | undefined; misses?: number; pending?: boolean; onPress?: () => void; testID?: string }) => {
  const tone = pending ? '#8E8E93' : scoreTone(pct);
  return (
    <TouchableOpacity onPress={onPress} disabled={!onPress} activeOpacity={0.7}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, backgroundColor: tone + '1A', borderWidth: 1, borderColor: tone + '66' }}
      {...(testID ? tid(testID) : {})}>
      <Ionicons name={pending ? 'hourglass-outline' : misses ? 'alert-circle' : 'clipboard'} size={13} color={tone} />
      <Text style={{ fontSize: 12, fontWeight: '800', color: tone }}>
        {pending ? 'Scoring call…' : pct == null ? 'Not scored' : `Scored ${pct}%`}{!pending && misses ? ` · ${misses} critical miss${misses === 1 ? '' : 'es'}` : ''}
      </Text>
      {onPress && <Ionicons name="chevron-forward" size={12} color={tone} />}
    </TouchableOpacity>
  );
};
