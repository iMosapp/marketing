import React, { ReactNode } from 'react';
import { View, Text, TouchableOpacity, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { RADIUS, SPACE, TYPE, tid, tint } from './tokens';

/** Rounded card surface; put Rows inside for a list. */
export const Card = ({ children, style, testID }: { children: ReactNode; style?: ViewStyle; testID?: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={[{ backgroundColor: colors.card, borderRadius: RADIUS.lg, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }, style]} {...(testID ? tid(testID) : {})}>
      {children}
    </View>
  );
};

type RowProps = {
  icon?: string;
  iconColor?: string;
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onPress?: () => void;
  first?: boolean;
  chevron?: boolean;
  titleLines?: number;
  testID?: string;
};

/** One list row: tinted icon circle, title, optional subtitle, optional right slot / chevron. */
export const Row = ({ icon, iconColor, title, subtitle, right, onPress, first, chevron, titleLines = 1, testID }: RowProps) => {
  const { colors } = useThemeStore();
  const color = iconColor || colors.textSecondary;
  const body = (
    <>
      {icon ? (
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: tint(color, 0.14), alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Ionicons name={icon as any} size={16} color={color} />
        </View>
      ) : null}
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={{ fontSize: TYPE.body, fontWeight: '600', color: colors.text, lineHeight: 20 }} numberOfLines={titleLines}>{title}</Text>
        {subtitle ? <Text style={{ fontSize: TYPE.caption, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>{subtitle}</Text> : null}
      </View>
      {right}
      {chevron ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
    </>
  );
  const style = { flexDirection: 'row' as const, alignItems: 'center' as const, gap: SPACE.md, paddingHorizontal: SPACE.lg, paddingVertical: SPACE.md, borderTopWidth: first ? 0 : 0.5, borderTopColor: colors.border };
  if (!onPress) return <View style={style} {...(testID ? tid(testID) : {})}>{body}</View>;
  return <TouchableOpacity onPress={onPress} activeOpacity={0.75} style={style} {...(testID ? tid(testID) : {})}>{body}</TouchableOpacity>;
};
