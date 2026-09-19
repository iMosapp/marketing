import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { tid } from '../scripts/shared';
import { DayStrip } from './DayStrip';
import { UpcomingRow } from './UpcomingRow';
import { AutoTextSheet } from './AutoTextSheet';
import { GOLD, UPCOMING_FILTERS, UpcomingData, UpcomingFilter, UpcomingItem, dayLabel, matchesFilter } from './types';

export const UpcomingView = ({ userId }: { userId: string }) => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [days, setDays] = useState(14);
  const [data, setData] = useState<UpcomingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<UpcomingFilter>('All');
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [preview, setPreview] = useState<UpcomingItem | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!userId) return;
    if (!quiet) setLoading(true);
    try {
      const res = await api.get(`/upcoming/${userId}?days=${days}`);
      setData(res.data);
    } catch {
      if (!quiet) setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [userId, days]);

  useEffect(() => { load(); }, [load]);

  const groups = useMemo(() => {
    if (!data) return [];
    return data.groups
      .filter(g => !selectedDay || g.date === selectedDay)
      .map(g => ({ ...g, items: g.items.filter(i => matchesFilter(i, filter)) }))
      .filter(g => g.items.length > 0);
  }, [data, filter, selectedDay]);

  const countsByDay = useMemo(() => {
    const out: Record<string, { you: number; jessi: number }> = {};
    data?.groups.forEach(g => {
      out[g.date] = { you: 0, jessi: 0 };
      g.items.forEach(i => { if (matchesFilter(i, filter)) out[g.date][i.owner] += 1; });
    });
    return out;
  }, [data, filter]);

  const openContact = (item: UpcomingItem) => {
    setPreview(null);
    if (!item.contact_id) return;
    const qs = item.kind === 'task' || item.kind === 'appointment' ? `?taskId=${item.id}` : '';
    router.push(`/contact/${item.contact_id}${qs}` as any);
  };

  const sendNow = async (item: UpcomingItem) => {
    try {
      await api.post(`/upcoming/${userId}/sends/${item.id}/send-now`);
      setPreview(null);
      showSimpleAlert('On its way', `Jessi will send this to ${item.contact_name || 'the contact'} within a minute.`);
      load(true);
    } catch (e: any) {
      showSimpleAlert('Could not send', e?.response?.data?.detail || 'Try again in a moment.');
    }
  };

  const cancelSend = async (item: UpcomingItem) => {
    try {
      await api.post(`/upcoming/${userId}/sends/${item.id}/cancel`);
      setPreview(null);
      load(true);
    } catch (e: any) {
      showSimpleAlert('Could not skip', e?.response?.data?.detail || 'Try again in a moment.');
    }
  };

  if (loading && !data) {
    return <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}><ActivityIndicator size="large" color={GOLD} /></View>;
  }
  if (!data) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 }}>
        <Text style={{ color: colors.textSecondary, textAlign: 'center' }}>Could not load what's coming up.</Text>
        <TouchableOpacity onPress={() => load()} style={{ marginTop: 12 }} {...tid('upcoming-retry')}><Text style={{ color: GOLD, fontWeight: '700' }}>Try again</Text></TouchableOpacity>
      </View>
    );
  }

  const c = data.counts;
  return (
    <View style={{ flex: 1 }}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 90 }} showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={GOLD} />}>
        <View style={{ paddingHorizontal: 16, paddingTop: 14, paddingBottom: 10, flexDirection: 'row', alignItems: 'baseline', gap: 8 }}>
          <Text style={{ fontSize: 22, fontWeight: '700', color: colors.text }} {...tid('upcoming-total')}>{c.total} coming up</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('upcoming-split')}>{c.you} need you · {c.jessi} Jessi handles</Text>
        </View>

        <DayStrip today={data.today} days={data.days} countsByDay={countsByDay} selected={selectedDay} onSelect={setSelectedDay} />

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 8, paddingBottom: 12 }}>
          {UPCOMING_FILTERS.map(f => {
            const active = f === filter;
            return (
              <TouchableOpacity key={f} onPress={() => setFilter(f)}
                style={{ paddingVertical: 6, paddingHorizontal: 14, borderRadius: 20, borderWidth: 1, backgroundColor: active ? 'rgba(201,169,98,0.1)' : colors.card, borderColor: active ? 'rgba(201,169,98,0.4)' : colors.border }}
                {...tid(`upcoming-filter-${f.toLowerCase().replace(/\s+/g, '-')}`)}>
                <Text style={{ fontSize: 14, fontWeight: '600', color: active ? GOLD : colors.textSecondary }}>{f}</Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {groups.length === 0 && (
          <View style={{ alignItems: 'center', padding: 36 }} {...tid('upcoming-empty')}>
            <Ionicons name="sunny-outline" size={34} color={colors.textSecondary} />
            <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 10 }}>Nothing {selectedDay ? 'that day' : `in the next ${data.days} days`}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4, textAlign: 'center' }}>Tasks, appointments, birthdays and Jessi's queued texts will show here.</Text>
          </View>
        )}

        {groups.map(g => (
          <View key={g.date} style={{ marginBottom: 14 }} {...tid(`upcoming-group-${g.date}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingBottom: 6 }}>
              <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, textTransform: 'uppercase' }}>{dayLabel(g.date, data.today)}</Text>
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{g.items.length}</Text>
            </View>
            <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
              {g.items.map((item, i) => (
                <UpcomingRow key={item.id} item={item} last={i === g.items.length - 1} onOpenContact={openContact} onPreview={setPreview} />
              ))}
            </View>
          </View>
        ))}

        <TouchableOpacity onPress={() => setDays(days === 14 ? 30 : 14)} style={{ alignSelf: 'center', marginTop: 6, paddingVertical: 10, paddingHorizontal: 18, borderRadius: 20, borderWidth: 1, borderColor: colors.border }} {...tid('upcoming-toggle-days')}>
          <Text style={{ fontSize: 13, fontWeight: '600', color: GOLD }}>{days === 14 ? 'Show next 30 days' : 'Back to 14 days'}</Text>
        </TouchableOpacity>
      </ScrollView>

      <AutoTextSheet item={preview} today={data.today} onClose={() => setPreview(null)} onSendNow={sendNow} onCancel={cancelSend} onOpenContact={openContact} />
    </View>
  );
};
