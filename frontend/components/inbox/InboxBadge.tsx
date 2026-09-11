import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid, firstName } from './ownership';

type BadgeProps = { inboxName?: string | null; color?: string; ownerName?: string | null; isMine?: boolean; unassigned?: boolean; isCollaborator?: boolean; colors: any; compact?: boolean };

// "● Sales · Forest" / "● Sales · Up for grabs" chip shown on conversation rows that live in a shared inbox.
export function InboxBadge({ inboxName, color, ownerName, isMine, unassigned, isCollaborator, colors, compact }: BadgeProps) {
  if (!inboxName) return null;
  const c = color || GOLD;
  const who = unassigned ? 'Up for grabs' : isMine ? 'You' : firstName(ownerName);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', backgroundColor: unassigned ? GOLD + '1F' : c + '18', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 3, borderWidth: 1, borderColor: unassigned ? GOLD + '66' : c + '33' }} {...tid('inbox-badge')}>
      <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: c }} />
      <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textPrimary || colors.text }} numberOfLines={1}>
        {inboxName}{compact ? '' : ` · ${who}`}
      </Text>
      {isCollaborator && !unassigned && !isMine ? <Ionicons name="people" size={10} color={colors.textSecondary} /> : null}
    </View>
  );
}

export function ClaimButton({ onPress, busy, testId, small }: { onPress: (e?: any) => void; busy?: boolean; testId: string; small?: boolean }) {
  return (
    <TouchableOpacity onPress={(e) => { e?.stopPropagation?.(); onPress(e); }} disabled={busy} activeOpacity={0.75}
      style={{ backgroundColor: GOLD, borderRadius: small ? 6 : 10, paddingHorizontal: small ? 8 : 14, height: small ? 24 : 34, flexDirection: 'row', alignItems: 'center', gap: 4, justifyContent: 'center', opacity: busy ? 0.6 : 1 }} {...tid(testId)}>
      {busy ? <ActivityIndicator size="small" color="#111" /> : <Ionicons name="hand-right" size={small ? 10 : 13} color="#111" />}
      <Text style={{ fontSize: small ? 11 : 13, fontWeight: '800', color: '#111' }}>Claim</Text>
    </TouchableOpacity>
  );
}
