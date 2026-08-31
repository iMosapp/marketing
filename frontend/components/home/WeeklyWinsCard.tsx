/**
 * WeeklyWinsCard — Monday morning recap of last week's wins (sold, texts, scans, new contacts).
 */
import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

const GOLD = '#C9A962';

export function WeeklyWinsCard({ userId, forceShow }: { userId: string; forceShow?: boolean }) {
  const [wins, setWins] = useState<any>(null);
  const isMonday = new Date().getDay() === 1;
  const visible = isMonday || !!forceShow;

  useEffect(() => {
    if (!visible || !userId) return;
    api.get(`/home/weekly-wins/${userId}`).then(r => setWins(r.data)).catch(() => {});
  }, [userId, visible]);

  if (!visible || !wins) return null;
  const total = (wins.sold || 0) + (wins.texts || 0) + (wins.scans || 0) + (wins.new_contacts || 0);
  if (total === 0) return null;

  const stats = [
    { key: 'sold', label: 'Sold', value: wins.sold, icon: 'trophy', color: GOLD },
    { key: 'texts', label: 'Texts', value: wins.texts, icon: 'chatbubble', color: '#34C759' },
    { key: 'scans', label: 'QR Scans', value: wins.scans, icon: 'qr-code', color: '#AF52DE' },
    { key: 'contacts', label: 'New', value: wins.new_contacts, icon: 'person-add', color: '#FF9500' },
  ];

  return (
    <View
      style={{
        marginHorizontal: 16, marginBottom: 16, padding: 14,
        borderRadius: 16, backgroundColor: '#1C1C1E',
        borderWidth: 1, borderColor: `${GOLD}40`,
      }}
      testID="weekly-wins-card"
      dataSet={{ testid: 'weekly-wins-card' }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <View style={{ width: 26, height: 26, borderRadius: 8, backgroundColor: `${GOLD}20`, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="sparkles" size={14} color={GOLD} />
        </View>
        <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 1.2 }}>LAST WEEK'S WINS</Text>
      </View>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {stats.map(s => (
          <View key={s.key} style={{ flex: 1, alignItems: 'center', backgroundColor: '#2C2C2E55', borderRadius: 12, paddingVertical: 10, gap: 3 }} testID={`wins-stat-${s.key}`} dataSet={{ testid: `wins-stat-${s.key}` }}>
            <Ionicons name={s.icon as any} size={16} color={s.color} />
            <Text style={{ fontSize: 18, fontWeight: '800', color: '#FFF' }}>{s.value}</Text>
            <Text style={{ fontSize: 10, fontWeight: '600', color: '#8E8E93', letterSpacing: 0.3 }}>{s.label}</Text>
          </View>
        ))}
      </View>
      {(wins.waiting_cleared || 0) > 0 && (
        <View
          style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#2C2C2E' }}
          testID="wins-waiting-cleared"
          dataSet={{ testid: 'wins-waiting-cleared' }}
        >
          <Ionicons name="checkmark-circle" size={14} color="#34C759" />
          <Text style={{ fontSize: 12, color: '#8E8E93', flex: 1 }}>
            <Text style={{ color: '#34C759', fontWeight: '700' }}>{wins.waiting_cleared}</Text>
            {wins.waiting_cleared === 1 ? ' waiting alert cleared itself' : ' waiting alerts cleared themselves'} — no action needed
          </Text>
        </View>
      )}
    </View>
  );
}
