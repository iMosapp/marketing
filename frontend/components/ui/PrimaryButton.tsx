import React from 'react';
import { Text, TouchableOpacity, ActivityIndicator, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, INK, RADIUS, tid, tint } from './tokens';

type Props = {
  label: string;
  onPress?: () => void;
  color?: string;
  variant?: 'solid' | 'soft' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  icon?: string;
  loading?: boolean;
  disabled?: boolean;
  full?: boolean;
  testID?: string;
  style?: ViewStyle;
};

const SIZES = { sm: { h: 34, px: 14, fs: 13, icon: 15 }, md: { h: 44, px: 18, fs: 15, icon: 18 }, lg: { h: 56, px: 22, fs: 17, icon: 22 } } as const;

/** The one button. Gold solid = primary action; pass color RED/GREEN for urgent/success; soft/outline for secondary. */
export const PrimaryButton = ({ label, onPress, color = GOLD, variant = 'solid', size = 'md', icon, loading, disabled, full, testID, style }: Props) => {
  const s = SIZES[size];
  const solid = variant === 'solid';
  const fg = solid ? (color === GOLD ? INK : '#FFFFFF') : color;
  const bg = solid ? color : variant === 'soft' ? tint(color, 0.14) : 'transparent';
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
      style={[{
        height: s.h, paddingHorizontal: s.px, borderRadius: RADIUS.xl, backgroundColor: bg,
        borderWidth: variant === 'outline' ? 1.5 : 0, borderColor: tint(color, 0.6),
        flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
        alignSelf: full ? 'stretch' : 'flex-start', opacity: disabled ? 0.45 : 1,
      }, style]}
      {...(testID ? tid(testID) : {})}
    >
      {loading ? <ActivityIndicator size="small" color={fg} /> : icon ? <Ionicons name={icon as any} size={s.icon} color={fg} /> : null}
      <Text style={{ fontSize: s.fs, fontWeight: '800', color: fg, letterSpacing: 0.2 }} numberOfLines={1}>{label}</Text>
    </TouchableOpacity>
  );
};
