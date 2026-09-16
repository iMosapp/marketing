import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../../services/api';

// One quiet status line under the hero: how warm this relationship is right now, and why.
export const HealthBadge = ({ userId, contactId }: { userId: string; contactId: string }) => {
  const router = useRouter();
  const [h, setH] = useState<any>(null);

  useEffect(() => {
    if (!userId || !contactId) return;
    let alive = true;
    api.get(`/relationship-health/${userId}/contact/${contactId}`).then(r => { if (alive) setH(r.data); }).catch(() => {});
    return () => { alive = false; };
  }, [userId, contactId]);

  if (!h) return null;
  const reason = h.reason ? String(h.reason).replace(/^Advocate · /, '') : '';
  return (
    <TouchableOpacity activeOpacity={0.8} onPress={() => router.push('/book-of-business' as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginTop: -4, marginBottom: 14 }} testID="contact-health-badge">
      <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: h.color }} />
      <Text style={{ fontSize: 13, fontWeight: '800', color: h.color }}>{h.label}{h.is_advocate ? ' · Advocate' : ''}</Text>
      {reason ? <Text style={{ flexShrink: 1, fontSize: 13, color: '#8E8E93' }} numberOfLines={1}>{reason}</Text> : null}
    </TouchableOpacity>
  );
};
