/**
 * PresenceCard.tsx — Reusable card wrapper for every item in "My Presence".
 *
 * Each presence card has the same 3-part structure:
 *  1. Preview panel (tappable, shows a visual preview of the asset)
 *  2. Header (icon + title + URL)
 *  3. Action buttons row (preview, edit, copy, share)
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export interface PresenceAction {
  label: string;
  icon: string;
  color: string;
  onPress: () => void;
  testId?: string;
}

interface Props {
  /** Icon name for the header badge */
  icon: string;
  iconColor: string;
  iconBg: string;
  title: string;
  /** URL shown beneath the title */
  url: string;
  /** Row of action buttons */
  actions: PresenceAction[];
  /** Visual preview panel rendered at the top of the card */
  previewContent: React.ReactNode;
  previewBg: string;
  onPreviewPress: () => void;
  colors: Record<string, string>;
  testId?: string;
}

export function PresenceCard({
  icon, iconColor, iconBg, title, url, actions,
  previewContent, previewBg, onPreviewPress, colors, testId,
}: Props) {
  return (
    <View style={[s.card, { backgroundColor: colors.card }]} data-testid={testId}>
      {/* Preview panel */}
      <TouchableOpacity
        style={[s.preview, { backgroundColor: previewBg }]}
        onPress={onPreviewPress}
        activeOpacity={0.8}
      >
        {previewContent}
      </TouchableOpacity>

      {/* Header */}
      <View style={s.header}>
        <View style={[s.iconBox, { backgroundColor: iconBg }]}>
          <Ionicons name={icon as any} size={20} color={iconColor} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[s.title, { color: colors.text }]}>{title}</Text>
          <Text style={[s.url, { color: colors.textTertiary }]} numberOfLines={1}>{url}</Text>
        </View>
      </View>

      {/* Actions */}
      <View style={s.actions}>
        {actions.map((action) => (
          <TouchableOpacity
            key={action.label}
            style={[s.actionBtn, { backgroundColor: `${action.color}15` }]}
            onPress={action.onPress}
            data-testid={action.testId}
          >
            <Ionicons name={action.icon as any} size={15} color={action.color} />
            <Text style={[s.actionLabel, { color: action.color }]}>{action.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  card: {
    borderRadius: 14,
    overflow: 'hidden',
    marginBottom: 14,
  },
  preview: {
    padding: 16,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 110,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 12,
  },
  iconBox: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 2,
  },
  url: {
    fontSize: 12,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    paddingHorizontal: 14,
    paddingBottom: 14,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  actionLabel: {
    fontSize: 13,
    fontWeight: '600',
  },
});
