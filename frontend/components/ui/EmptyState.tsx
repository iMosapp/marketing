import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { PrimaryButton } from './PrimaryButton';
import { GREEN, RADIUS, SPACE, TYPE, tid } from './tokens';

type Props = {
  icon?: string;
  iconColor?: string;
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
  compact?: boolean;
  testID?: string;
};

/** "Nothing here" card. Green check by default because an empty queue is good news. */
export const EmptyState = ({ icon = 'checkmark-circle', iconColor = GREEN, title, subtitle, actionLabel, onAction, compact, testID = 'empty-state' }: Props) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: RADIUS.lg, borderWidth: 1, borderColor: colors.border, alignItems: 'center', padding: compact ? SPACE.lg : SPACE.xl }} {...tid(testID)}>
      <Ionicons name={icon as any} size={compact ? 28 : 40} color={iconColor} />
      <Text style={{ fontSize: compact ? TYPE.body : 16, fontWeight: '700', color: colors.text, marginTop: compact ? 6 : 10, textAlign: 'center' }}>{title}</Text>
      {subtitle ? <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary, marginTop: 4, textAlign: 'center', lineHeight: 18 }}>{subtitle}</Text> : null}
      {actionLabel && onAction ? <PrimaryButton label={actionLabel} onPress={onAction} variant="soft" size="sm" style={{ marginTop: SPACE.md }} testID={`${testID}-action`} /> : null}
    </View>
  );
};
