/**
 * ReplyHealthCard — amber warning on Home when an AI reply failed to send in the last 24h.
 */
import React, { useCallback, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';

const AMBER = '#FF9500';

export function ReplyHealthCard({ userId }: { userId: string }) {
  const router = useRouter();
  const [data, setData] = useState<any>(null);

  useFocusEffect(
    useCallback(() => {
      if (!userId) return;
      let alive = true;
      api.get(`/home/reply-health/${userId}`).then(r => { if (alive) setData(r.data); }).catch(() => {});
      return () => { alive = false; };
    }, [userId])
  );

  if (!data?.failed) return null;
  const title = data.failed === 1 ? '1 AI reply didn\u2019t send' : `${data.failed} AI replies didn\u2019t send`;

  return (
    <TouchableOpacity
      onPress={() => {
        if (data.conversation_id) router.push(`/thread/${data.conversation_id}` as any);
        else router.push('/(tabs)/inbox' as any);
      }}
      activeOpacity={0.8}
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 10,
        marginHorizontal: 16, marginBottom: 12,
        paddingHorizontal: 14, paddingVertical: 11,
        borderRadius: 16, backgroundColor: `${AMBER}14`,
        borderWidth: 1.5, borderColor: `${AMBER}50`,
      }}
      testID="reply-health-card"
      dataSet={{ testid: 'reply-health-card' } as any}
    >
      <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: `${AMBER}25`, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name="warning" size={17} color={AMBER} />
      </View>
      <View style={{ flex: 1 }}>
        <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, fontWeight: '800', color: AMBER }}>
          {title}
        </Text>
        <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, color: '#8E8E93', marginTop: 1 }} numberOfLines={1}>
          In the last day · Tap to review the conversation
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={AMBER} />
    </TouchableOpacity>
  );
}
