import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid, firstName } from './ownership';

type Info = { inbox_id?: string | null; inbox_name?: string | null; assigned_to?: string | null; assigned_to_name?: string | null; is_unassigned?: boolean; collaborators?: string[]; graduated?: boolean; handoff_note?: any };

type Props = { info: Info | null; meId?: string; color?: string; colors: any; onOpen: () => void; onClaim: () => void; claiming?: boolean };

// Under the thread header: where this thread lives and who has it. Tap = ownership sheet.
export function InboxThreadBanner({ info, meId, color, colors, onOpen, onClaim, claiming }: Props) {
  if (!info?.inbox_id) return null;
  const c = color || GOLD;
  const unassigned = !!info.is_unassigned || !info.assigned_to;
  const mine = !!info.assigned_to && info.assigned_to === meId;
  const who = unassigned ? 'Up for grabs' : mine ? 'You have this' : `${firstName(info.assigned_to_name)} has this`;
  const collabs = (info.collaborators || []).length;
  return (
    <TouchableOpacity onPress={onOpen} activeOpacity={0.8} style={{ marginHorizontal: 12, marginBottom: 6, borderRadius: 14, backgroundColor: unassigned ? GOLD + '1A' : colors.surface, borderWidth: 1, borderColor: unassigned ? GOLD + '66' : colors.border, paddingHorizontal: 12, paddingVertical: 9, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('inbox-thread-banner')}>
      <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: c }} />
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 13, fontWeight: '800', color: colors.textPrimary || colors.text }} numberOfLines={1}>
          {info.inbox_name} inbox <Text style={{ color: colors.textSecondary, fontWeight: '600' }}>· {who}</Text>
        </Text>
        {info.handoff_note?.text && unassigned ? (
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>"{info.handoff_note.text}"</Text>
        ) : collabs > 0 ? (
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>+{collabs} teammate{collabs === 1 ? '' : 's'} on it</Text>
        ) : null}
      </View>
      {unassigned ? (
        <TouchableOpacity onPress={onClaim} disabled={claiming} style={{ height: 32, paddingHorizontal: 14, borderRadius: 10, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 5, opacity: claiming ? 0.6 : 1 }} {...tid('inbox-thread-claim-btn')}>
          {claiming ? <ActivityIndicator size="small" color="#111" /> : <Ionicons name="hand-right" size={14} color="#111" />}
          <Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Claim</Text>
        </TouchableOpacity>
      ) : (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 2 }}>
          <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Manage</Text>
          <Ionicons name="chevron-forward" size={14} color={GOLD} />
        </View>
      )}
    </TouchableOpacity>
  );
}
