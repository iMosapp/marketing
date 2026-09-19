import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { tid } from '../scripts/shared';
import { GOLD, UpcomingData, UpcomingItem, dayLabel, kindVisual } from '../upcoming/types';

export const ComingUpStrip = ({ userId }: { userId: string }) => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [data, setData] = useState<UpcomingData | null>(null);

  useEffect(() => {
    if (!userId) return;
    let alive = true;
    api.get(`/upcoming/${userId}?days=7`).then(r => { if (alive) setData(r.data); }).catch(() => {});
    return () => { alive = false; };
  }, [userId]);

  if (!data || data.counts.total === 0) return null;
  const next: UpcomingItem[] = data.groups.flatMap(g => g.items).slice(0, 3);
  const openAll = () => router.push('/(tabs)/touchpoints?view=upcoming' as any);

  return (
    <View style={{ marginHorizontal: 16, marginBottom: 16, backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border }} {...tid('coming-up-card')}>
      <TouchableOpacity onPress={openAll} style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10 }} {...tid('coming-up-open')}>
        <Text style={{ flex: 1, fontSize: 17, fontWeight: '700', color: colors.text }}>Coming Up</Text>
        <Text style={{ fontSize: 13, color: colors.textSecondary, marginRight: 4 }}>{data.counts.total} this week</Text>
        <Ionicons name="chevron-forward" size={16} color={GOLD} />
      </TouchableOpacity>
      {next.map((item, i) => {
        const v = kindVisual(item);
        const jessi = item.owner === 'jessi';
        return (
          <TouchableOpacity key={item.id} onPress={() => item.contact_id ? router.push(`/contact/${item.contact_id}` as any) : openAll()}
            style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 8, gap: 10, borderBottomWidth: i < next.length - 1 ? 0.5 : 0, borderBottomColor: colors.border }}
            {...tid(`coming-up-row-${item.id}`)}>
            <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: v.color + '20', alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={v.icon as any} size={14} color={v.color} />
            </View>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }} numberOfLines={1}>{item.contact_name || item.title}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{item.contact_name ? item.title : ''}</Text>
            </View>
            <View style={{ alignItems: 'flex-end' }}>
              <Text style={{ fontSize: 12, fontWeight: '600', color: colors.text }}>{dayLabel(item.date, data.today)}</Text>
              <Text style={{ fontSize: 10, fontWeight: '700', color: jessi ? GOLD : '#5AC8FA', marginTop: 1 }}>{jessi ? 'JESSI' : item.time || 'YOU'}</Text>
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};
