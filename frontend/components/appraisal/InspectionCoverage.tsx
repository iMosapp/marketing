import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { tid } from '../inbox/ownership';

type Props = { colors: any; coverage: any; compact?: boolean };
const ICON: Record<string, [any, string]> = { complete: ['checkmark-circle', '#34C759'], partial: ['alert-circle', '#FF9500'], missing: ['close-circle', '#FF3B30'] };
const WORD: Record<string, string> = { complete: 'Complete', partial: 'More photos recommended', missing: 'Not seen' };

// Exterior ✓ · Wheels ✓ · Glass ✓ · Interior ⚠ — and which angles are still missing. Never blocks; always names what is missing.
export const InspectionCoverage = ({ colors, coverage, compact }: Props) => {
  if (!coverage) return null;
  const groups = coverage.groups || {};
  return (
    <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid('inspect-coverage')}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>INSPECTION COVERAGE · {coverage.frames_usable} usable frames</Text>
      {Object.entries(groups).map(([k, g]: any) => {
        const [icon, color] = ICON[g.status] || ICON.missing;
        return (
          <View key={k} style={{ gap: 2 }} {...tid(`coverage-${k}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons name={icon} size={16} color={color} />
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{g.label}</Text>
              <Text style={{ fontSize: 12.5, color, fontWeight: '700' }}>{compact ? g.status[0].toUpperCase() + g.status.slice(1) : WORD[g.status]}</Text>
            </View>
            {!compact && (g.missing?.length || g.partial?.length) && g.status !== 'complete' ? (
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginLeft: 24 }}>
                {g.missing?.length ? `Missing: ${g.missing.join(', ')}` : ''}{g.missing?.length && g.partial?.length ? ' · ' : ''}{g.partial?.length ? `One look only: ${g.partial.join(', ')}` : ''}
              </Text>
            ) : null}
          </View>
        );
      })}
    </View>
  );
};
