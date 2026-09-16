import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { GREEN, tid } from '../scripts/shared';

/** "Verified it was you" chip: Voice ID matched the rep's own voice print on this recording. Renders nothing otherwise. */
export function VoiceIdBadge({ item, id, style }: { item: any; id: string; style?: any }) {
  const me = useAuthStore(s => s.user);
  const verified = item?.voice_verified ?? (item?.voice_id?.channel != null ? true : item?.voice_id?.verified);
  if (!verified) return null;
  const mine = !item?.user_id || String(item.user_id) === String(me?._id || (me as any)?.id || '');
  return (
    <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', backgroundColor: GREEN + '1A', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 }, style]} {...tid(`voice-id-badge-${id}`)}>
      <Ionicons name="shield-checkmark" size={12} color={GREEN} />
      <Text style={{ fontSize: 11, color: GREEN, fontWeight: '700' }}>{mine ? 'Verified it was you' : 'Voice ID verified'}</Text>
    </View>
  );
}
