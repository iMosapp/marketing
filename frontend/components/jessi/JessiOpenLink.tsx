// The "tap to open" link under a typed Jessi answer: the contact, thread, reminder or search she just worked on.
import React from 'react';
import { Text, TouchableOpacity, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { pathFor } from './LiveJessiProvider';
import type { OpenTarget } from '../../hooks/useLiveJessi';
import { GOLD, tid, tint } from '../ui/tokens';

const label = (t: OpenTarget) => {
  if (t.kind === 'contact') return { icon: 'person-circle-outline', text: `Open ${t.name || 'contact'}` };
  if (t.kind === 'thread') return { icon: 'chatbubbles-outline', text: `Open texts with ${t.first || t.name || 'them'}` };
  if (t.kind === 'task') return { icon: 'alarm-outline', text: 'Open reminder' };
  if (t.kind === 'tasks') return { icon: 'list-outline', text: 'Open touchpoints' };
  if (t.kind === 'mentions') return { icon: 'search-outline', text: 'See every match' };
  if (t.kind === 'duplicates') return { icon: 'git-merge-outline', text: 'Review duplicates' };
  if (t.kind === 'team_today') return { icon: 'people-outline', text: 'Open team today' };
  if (t.kind === 'campaign') return { icon: 'megaphone-outline', text: `Open ${t.name || 'campaign'}` };
  return { icon: 'open-outline', text: t.kind === 'inbox' ? 'Open inbox' : 'Open Home' };
};

export const JessiOpenLink = ({ target, onNavigate, testID = 'jessi-open-link', style }: { target?: OpenTarget | null; onNavigate?: () => void; testID?: string; style?: ViewStyle }) => {
  const router = useRouter();
  const path = target?.kind ? pathFor(target) : null;
  if (!target || !path) return null;
  const l = label(target);
  return (
    <TouchableOpacity onPress={() => { onNavigate?.(); router.push(path as any); }} activeOpacity={0.75}
      style={{ flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', gap: 6, marginTop: 8, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, backgroundColor: tint(GOLD, 0.16), borderWidth: 1, borderColor: tint(GOLD, 0.45), ...style }}
      {...tid(testID)}>
      <Ionicons name={l.icon as any} size={15} color={GOLD} />
      <Text style={{ color: GOLD, fontWeight: '800', fontSize: 13 }} numberOfLines={1}>{l.text}</Text>
      <Ionicons name="chevron-forward" size={14} color={GOLD} />
    </TouchableOpacity>
  );
};
