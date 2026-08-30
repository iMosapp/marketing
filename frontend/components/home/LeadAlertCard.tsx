/**
 * LeadAlertCard — red urgency card on Home when internet leads await a first reply.
 * Taps straight into the oldest waiting thread. Refreshes on focus + every 30s.
 */
import React, { useCallback, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { waitInfo } from '../LeadWaitTimer';

const RED = '#FF3B30';

export function LeadAlertCard({ userId }: { userId: string }) {
  const router = useRouter();
  const [data, setData] = useState<any>(null);

  useFocusEffect(
    useCallback(() => {
      if (!userId) return;
      let alive = true;
      const load = () =>
        api.get(`/leads/awaiting/${userId}`).then(r => { if (alive) setData(r.data); }).catch(() => {});
      load();
      const t = setInterval(load, 30000);
      return () => { alive = false; clearInterval(t); };
    }, [userId])
  );

  if (!data?.count || !data.oldest) return null;
  const { label } = waitInfo(data.oldest.received_at);
  const title = data.count === 1
    ? `1 lead waiting ${label}`
    : `${data.count} leads waiting — oldest ${label}`;

  return (
    <TouchableOpacity
      onPress={() => router.push(`/thread/${data.oldest.conversation_id}` as any)}
      activeOpacity={0.8}
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 10,
        marginHorizontal: 16, marginBottom: 12,
        paddingHorizontal: 14, paddingVertical: 12,
        borderRadius: 16, backgroundColor: `${RED}16`,
        borderWidth: 1.5, borderColor: `${RED}55`,
      }}
      testID="lead-alert-card"
      dataSet={{ testid: 'lead-alert-card' }}
    >
      <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: `${RED}25`, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name="flame" size={19} color={RED} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color: RED }} testID="lead-alert-title" dataSet={{ testid: 'lead-alert-title' }}>
          {title}
        </Text>
        <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 1 }} numberOfLines={1}>
          {data.oldest.contact_name || 'New lead'} · Tap to respond
        </Text>
      </View>
      <View style={{ backgroundColor: RED, borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7 }}>
        <Text style={{ fontSize: 12, fontWeight: '800', color: '#FFF' }}>Respond</Text>
      </View>
    </TouchableOpacity>
  );
}
