/**
 * Team Tasks — managers see every open customer task per rep so nothing promised slips.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import { Avatar } from '../components/Avatar';
import { HomeSmartBar } from '../components/home/HomeSmartBar';
import { whenLabel, taskKind } from '../components/contact/ContactTasksCard';
import api from '../services/api';

const GOLD = '#C9A962';
const RED = '#FF453A';
const TYPE_ICON: Record<string, string> = { call: 'call', text: 'chatbubble', appointment: 'calendar', task: 'checkbox', birthday: 'gift', anniversary: 'ribbon', follow_up: 'refresh' };
const SOURCE_BADGE: Record<string, string> = { text_extraction: 'from text', call_extraction: 'from call' };
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Filter = 'all' | 'overdue' | 'today';

export default function TeamTasksScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    if (!user?._id) return;
    try {
      const r = await api.get(`/tasks/${user._id}/team`);
      setData(r.data);
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, [user?._id]);

  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const reps = useMemo(() => {
    const list = data?.reps || [];
    if (filter === 'all') return list;
    return list
      .map((r: any) => ({ ...r, tasks: r.tasks.filter((t: any) => filter === 'overdue' ? t.is_overdue : t.is_today) }))
      .filter((r: any) => r.tasks.length > 0);
  }, [data, filter]);

  const totals = data?.totals || { open: 0, overdue: 0, today: 0 };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={10} {...tid('team-tasks-back')}>
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ flex: 1, fontSize: 22, fontWeight: '800', color: colors.text }}>Team Tasks</Text>
      </View>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator size="large" color={GOLD} /></View>
      ) : !data?.is_manager ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }} {...tid('team-tasks-managers-only')}>
          <Ionicons name="lock-closed" size={30} color={colors.textTertiary} />
          <Text style={{ fontSize: 16, color: colors.textSecondary, textAlign: 'center', marginTop: 10 }}>Team Tasks is for managers. Your own tasks live in Touchpoints.</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ paddingBottom: 40 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}
        >
          <HomeSmartBar items={[
            { key: 'open', label: 'Open', icon: 'list', color: GOLD, value: totals.open, onPress: () => setFilter('all') },
            { key: 'overdue', label: 'Overdue', icon: 'alert-circle', color: RED, value: totals.overdue, onPress: () => setFilter('overdue') },
            { key: 'today', label: 'Due today', icon: 'today', color: '#34C759', value: totals.today, onPress: () => setFilter('today') },
          ]} />

          <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 16, marginBottom: 12 }}>
            {(['all', 'overdue', 'today'] as Filter[]).map(f => (
              <TouchableOpacity
                key={f}
                onPress={() => setFilter(f)}
                style={{ paddingHorizontal: 14, paddingVertical: 7, borderRadius: 18, backgroundColor: filter === f ? GOLD : colors.card, borderWidth: 1, borderColor: filter === f ? GOLD : colors.border }}
                {...tid(`team-tasks-filter-${f}`)}
              >
                <Text style={{ fontSize: 13, fontWeight: '700', color: filter === f ? '#000' : colors.textSecondary }}>
                  {f === 'all' ? 'All' : f === 'overdue' ? 'Overdue' : 'Due today'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {reps.length === 0 ? (
            <View style={{ alignItems: 'center', padding: 40 }} {...tid('team-tasks-empty')}>
              <Ionicons name="checkmark-done-circle" size={38} color="#34C759" />
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, marginTop: 10 }}>
                {filter === 'all' ? 'No open tasks across the team' : filter === 'overdue' ? 'Nothing overdue' : 'Nothing due today'}
              </Text>
            </View>
          ) : reps.map((rep: any) => {
            const isCollapsed = collapsed[rep.user_id] ?? false;
            const overdueN = rep.tasks.filter((t: any) => t.is_overdue).length;
            return (
              <View key={rep.user_id} style={{ marginHorizontal: 16, marginBottom: 12, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: overdueN ? `${RED}55` : colors.border, overflow: 'hidden' }} {...tid(`team-tasks-rep-${rep.user_id}`)}>
                <TouchableOpacity
                  onPress={() => setCollapsed(c => ({ ...c, [rep.user_id]: !isCollapsed }))}
                  activeOpacity={0.75}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12 }}
                  {...tid(`team-tasks-rep-toggle-${rep.user_id}`)}
                >
                  <Avatar photo={rep.photo_url} name={rep.name} size="md" />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} numberOfLines={1}>{rep.name}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                      {rep.tasks.length} open{overdueN ? ` · ` : ''}{overdueN ? <Text style={{ color: RED, fontWeight: '700' }}>{overdueN} overdue</Text> : null}
                    </Text>
                  </View>
                  <Ionicons name={isCollapsed ? 'chevron-down' : 'chevron-up'} size={18} color={colors.textTertiary} />
                </TouchableOpacity>

                {!isCollapsed && rep.tasks.map((t: any) => {
                  const w = whenLabel(t);
                  const badge = SOURCE_BADGE[t.source];
                  return (
                    <TouchableOpacity
                      key={t._id}
                      onPress={() => t.contact_id && router.push(`/contact/${t.contact_id}?taskId=${t._id}` as any)}
                      activeOpacity={t.contact_id ? 0.7 : 1}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.border }}
                      {...tid(`team-task-row-${t._id}`)}
                    >
                      <View style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: w.overdue ? `${RED}20` : `${GOLD}20`, alignItems: 'center', justifyContent: 'center' }}>
                        <Ionicons name={(TYPE_ICON[taskKind(t)] || 'checkbox') as any} size={14} color={w.overdue ? RED : GOLD} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text numberOfLines={1} style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{t.title}</Text>
                        <Text numberOfLines={1} style={{ fontSize: 12, color: w.overdue ? RED : colors.textSecondary, marginTop: 1, fontWeight: w.overdue ? '700' : '500' }}>
                          {w.text}{t.contact_name ? ` · ${t.contact_name}` : ''}
                        </Text>
                      </View>
                      {badge ? (
                        <View style={{ paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8, backgroundColor: colors.surface }}>
                          <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary }}>{badge}</Text>
                        </View>
                      ) : null}
                      {t.contact_id ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
                    </TouchableOpacity>
                  );
                })}
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
