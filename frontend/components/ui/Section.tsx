import React, { ReactNode } from 'react';
import { View, Text, TouchableOpacity, ViewStyle } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, SPACE, TYPE, tid } from './tokens';

type Props = {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
  right?: ReactNode;
  children: ReactNode;
  testID?: string;
  style?: ViewStyle;
};

/** A titled block on a screen: 17/700 title, optional one-line subtitle, optional gold "See all" action. */
export const Section = ({ title, subtitle, actionLabel, onAction, right, children, testID = 'section', style }: Props) => {
  const { colors } = useThemeStore();
  return (
    <View style={[{ marginHorizontal: SPACE.lg, marginBottom: SPACE.xl }, style]} {...tid(testID)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: SPACE.md, gap: SPACE.sm }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: TYPE.section, fontWeight: '700', color: colors.text }}>{title}</Text>
          {subtitle ? <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{subtitle}</Text> : null}
        </View>
        {right}
        {actionLabel && onAction ? (
          <TouchableOpacity onPress={onAction} hitSlop={8} {...tid(`${testID}-action`)}>
            <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: GOLD }}>{actionLabel} →</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      {children}
    </View>
  );
};
