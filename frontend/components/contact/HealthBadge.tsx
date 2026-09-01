import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

export const HealthBadge = ({ userId, contactId }: { userId: string; contactId: string }) => {
  const router = useRouter();
  const [h, setH] = useState<any>(null);

  useEffect(() => {
    if (!userId || !contactId) return;
    let alive = true;
    api.get(`/relationship-health/${userId}/contact/${contactId}`)
      .then(r => { if (alive) setH(r.data); })
      .catch(() => {});
    return () => { alive = false; };
  }, [userId, contactId]);

  if (!h) return null;

  return (
    <TouchableOpacity
      activeOpacity={0.8}
      onPress={() => router.push('/book-of-business' as any)}
      style={{ flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', gap: 7, marginHorizontal: 16, marginBottom: 10, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20, backgroundColor: `${h.color}1A`, borderWidth: 1, borderColor: `${h.color}40` }}
      testID="contact-health-badge"
    >
      <Ionicons name={h.icon} size={14} color={h.color} />
      <Text style={{ fontSize: 13, fontWeight: '800', color: h.color }}>{h.label}</Text>
      {h.reason ? (
        <Text style={{ fontSize: 12, color: h.color, opacity: 0.85 }} numberOfLines={1}>· {h.reason}</Text>
      ) : null}
    </TouchableOpacity>
  );
};
