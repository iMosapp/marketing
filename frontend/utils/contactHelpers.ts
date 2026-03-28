/**
 * contactHelpers.ts — Utility functions, constants, and the IntelRenderer
 * for the contact detail page.
 * Extracted from contact/[id].tsx to reduce that file's size.
 */

import React from 'react';
import { View, Text } from 'react-native';
import { differenceInYears, differenceInMonths, differenceInDays, format } from 'date-fns';
import { useThemeStore } from '../../store/themeStore';

// ─── Time helpers ─────────────────────────────────────────────────────────────

export function getTimeInSystem(createdAt: string | null): string {
  if (!createdAt) return '0';
  const created = new Date(createdAt);
  const now = new Date();
  const years = differenceInYears(now, created);
  if (years >= 1) return `${years}`;
  const months = differenceInMonths(now, created);
  if (months >= 1) return `${months}`;
  const days = differenceInDays(now, created);
  return `${Math.max(days, 0)}`;
}

export function getTimeInSystemLabel(createdAt: string | null): string {
  if (!createdAt) return 'day';
  const created = new Date(createdAt);
  const now = new Date();
  const years = differenceInYears(now, created);
  if (years >= 1) return 'year';
  const months = differenceInMonths(now, created);
  if (months >= 1) return 'month';
  return 'day';
}

export function formatEventTime(timestamp: string): string {
  if (!timestamp) return '';
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dayDiff = Math.round((nowDay.getTime() - dateDay.getTime()) / 86400000);
    if (dayDiff < 0) {
      return dayDiff === -1
        ? 'Tomorrow at ' + format(date, 'h:mm a')
        : format(date, "MMM d 'at' h:mm a");
    }
    if (dayDiff === 0) return format(date, 'h:mm a');
    if (dayDiff === 1) return 'Yesterday at ' + format(date, 'h:mm a');
    if (date.getFullYear() === now.getFullYear()) return format(date, "MMM d 'at' h:mm a");
    return format(date, "MMM d, yyyy 'at' h:mm a");
  } catch { return ''; }
}

/** Format date-only fields using UTC to prevent timezone from shifting the day */
export function formatDateUTC(dateStr: string, fmt: string = 'MMM d'): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const local = new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
    return format(local, fmt);
  } catch { return ''; }
}

// ─── Constants ────────────────────────────────────────────────────────────────

export const QUICK_ACTIONS = [
  { key: 'sms',    icon: 'chatbubble', label: 'SMS',      color: '#34C759' },
  { key: 'call',   icon: 'call',       label: 'Call',     color: '#32ADE6' },
  { key: 'email',  icon: 'mail',       label: 'Email',    color: '#AF52DE' },
  { key: 'review', icon: 'star',       label: 'Review',   color: '#FFD60A' },
  { key: 'card',   icon: 'card',       label: 'Card',     color: '#007AFF' },
  { key: 'gift',   icon: 'gift',       label: 'Congrats', color: '#C9A962' },
] as const;

export const EVENT_CATEGORY_ICON: Record<string, { icon: string; color: string }> = {
  message:           { icon: 'chatbubble', color: '#007AFF' },
  campaign:          { icon: 'rocket',     color: '#AF52DE' },
  card:              { icon: 'card',       color: '#C9A962' },
  broadcast:         { icon: 'megaphone',  color: '#FF2D55' },
  review:            { icon: 'star',       color: '#FFD60A' },
  voice_note:        { icon: 'mic',        color: '#34C759' },
  note:              { icon: 'document-text', color: '#FF9F0A' },
  customer_activity: { icon: 'arrow-down', color: '#30D158' },
  custom:            { icon: 'flag',       color: '#8E8E93' },
};

// ─── IntelRenderer ────────────────────────────────────────────────────────────

const SECTION_HEADERS = [
  'Quick Take', 'Key Facts', 'Communication Patterns',
  'Personal Notes', 'Before Your Next Interaction',
];

/** Renders relationship intel text with bold section headers and bullet formatting */
export const IntelRenderer = ({ text }: { text: string }) => {
  const { colors } = useThemeStore();
  const lines = text.split('\n').filter(l => l.trim());
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    const trimmed = line.trim().replace(/\*\*/g, '');
    const isHeader = SECTION_HEADERS.some(h => trimmed.toLowerCase().startsWith(h.toLowerCase()));
    const isBullet = trimmed.startsWith('-') || trimmed.startsWith('•');

    if (isHeader) {
      elements.push(
        <Text key={i} style={{ color: colors.text, fontSize: 16, fontWeight: '700', marginTop: i > 0 ? 14 : 0, marginBottom: 4 }}>
          {trimmed.replace(/:$/, '')}
        </Text>,
      );
    } else if (isBullet) {
      elements.push(
        <View key={i} style={{ flexDirection: 'row', paddingLeft: 4, marginBottom: 3 }}>
          <Text style={{ color: colors.textTertiary, fontSize: 15, marginRight: 6 }}>{'\u2022'}</Text>
          <Text style={{ color: colors.textSecondary, fontSize: 15, lineHeight: 19, flex: 1 }}>
            {trimmed.replace(/^[-•]\s*/, '')}
          </Text>
        </View>,
      );
    } else {
      elements.push(
        <Text key={i} style={{ color: colors.textSecondary, fontSize: 15, lineHeight: 19, marginBottom: 4 }}>
          {trimmed}
        </Text>,
      );
    }
  });

  return React.createElement(View, null, ...elements);
};
