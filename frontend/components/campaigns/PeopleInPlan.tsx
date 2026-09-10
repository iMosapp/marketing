import React from 'react';
import { View, Text, TouchableOpacity, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, RED, initials, shortDate, tid } from './utils';
import { Eyebrow } from './Sheet';

export type Enrollment = {
  _id: string; contact_id: string; contact_name: string; contact_photo?: string | null; current_step: number; total_steps?: number;
  status: string; next_send_at: string | null; contact_missing?: boolean;
};

type Props = { enrollments: Enrollment[]; triggerLabel: string; colors: any; onRemove: (e: Enrollment) => void; onRemoveAll: () => void };

export function PeopleInPlan({ enrollments, triggerLabel, colors, onRemove, onRemoveAll }: Props) {
  const router = useRouter();
  const live = enrollments.filter(e => e.status === 'active' || e.status === 'paused');
  const cancelled = enrollments.filter(e => e.status === 'cancelled').length;
  const completed = enrollments.filter(e => e.status === 'completed').length;
  return (
    <View style={{ gap: 10 }} {...tid('people-in-plan')}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <Eyebrow colors={colors} style={{ flex: 1 }}>PEOPLE IN THIS PLAN · {live.length}</Eyebrow>
        {live.length > 0 ? (
          <TouchableOpacity onPress={onRemoveAll} hitSlop={8} {...tid('people-remove-all')}>
            <Text style={{ fontSize: 12, fontWeight: '700', color: RED }}>Remove everyone</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      <View style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
        {live.length === 0 ? (
          <View style={{ padding: 18, alignItems: 'center', gap: 6 }}>
            <Ionicons name="people-outline" size={26} color={colors.textTertiary} />
            <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 }}>
              Nobody yet. {triggerLabel ? `Tag a contact ${triggerLabel} and they join automatically.` : 'Set a trigger and people join automatically.'}
            </Text>
          </View>
        ) : live.map((e, i) => (
          <View key={e._id} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 10, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }} {...tid(`person-row-${e._id}`)}>
            <TouchableOpacity style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 }} onPress={() => !e.contact_missing && router.push(`/contact/${e.contact_id}`)} {...tid(`person-open-${e._id}`)}>
              {e.contact_photo ? (
                <Image source={{ uri: e.contact_photo }} style={{ width: 36, height: 36, borderRadius: 18 }} />
              ) : (
                <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>{initials(e.contact_name)}</Text>
                </View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }} numberOfLines={1}>{e.contact_name}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>
                  Touch {Math.min(e.current_step || 1, e.total_steps || e.current_step || 1)}{e.total_steps ? ` of ${e.total_steps}` : ''}
                  {e.status === 'paused' ? ' · paused' : ''}
                  {e.next_send_at ? ` · next ${shortDate(e.next_send_at)}` : ''}
                </Text>
              </View>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => onRemove(e)} hitSlop={8} style={{ padding: 4 }} {...tid(`person-remove-${e._id}`)}>
              <Ionicons name="close-circle-outline" size={22} color={colors.textTertiary} />
            </TouchableOpacity>
          </View>
        ))}
      </View>
      {completed || cancelled ? (
        <Text style={{ fontSize: 11, color: colors.textTertiary, textAlign: 'center' }}>
          {[completed ? `${completed} finished the plan` : '', cancelled ? `${cancelled} removed` : ''].filter(Boolean).join(' · ')}
        </Text>
      ) : null}
    </View>
  );
}
