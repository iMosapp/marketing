import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { ClientSheet } from '../../../components/mystery-shops/ClientSheet';
import { Bar, money, scoreColor, GOLD, GREEN, RED, tid, type Client } from '../../../components/mystery-shops/shared';

export default function MysteryShopClients() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [clients, setClients] = useState<Client[] | null>(null);
  const [defaultFrom, setDefaultFrom] = useState('');
  const [sheet, setSheet] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try { const r = await api.get('/shop-clients'); setClients(r.data.clients); setDefaultFrom(r.data.from_number_default || ''); } catch { setClients([]); }
    finally { setRefreshing(false); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const mrr = (clients || []).filter(c => c.active).reduce((s, c) => s + (c.plan.price_monthly || 0), 0);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Mystery Shop Clients" subtitle={clients ? `${clients.length} store${clients.length === 1 ? '' : 's'} · ${money(mrr)}/mo` : undefined} testID="shop-clients-header" right={<HeaderIconButton icon="add-circle" onPress={() => setSheet(true)} testID="shop-clients-add" />} />
      {clients === null ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Stores that pay you to phone-shop their people. The AI shopper calls their cells at random times inside store hours, grades every call, and the store gets a live report link plus a monthly PDF.</Text>
          {clients.length === 0 && (
            <TouchableOpacity onPress={() => setSheet(true)} style={{ alignItems: 'center', padding: 30, gap: 10, backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border }} {...tid('shop-clients-empty')}>
              <Ionicons name="storefront" size={36} color={GOLD} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Add your first client store</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>Name, plan, hours, then the people to shop.</Text>
            </TouchableOpacity>
          )}
          {clients.map(c => {
            const done = c.completed || 0; const planned = c.planned || 0;
            return (
              <TouchableOpacity key={c.id} onPress={() => router.push(`/admin/mystery-shops/${c.id}` as any)} activeOpacity={0.85} style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10, opacity: c.active ? 1 : 0.6 }} {...tid(`shop-client-${c.id}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                  <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="storefront" size={20} color={GOLD} /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{c.name}{!c.active ? '  · paused' : ''}</Text>
                    <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{[c.brand, [c.city, c.state].filter(Boolean).join(', ')].filter(Boolean).join(' · ')}{c.people ? ` · ${c.people} people` : ''}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={{ fontSize: 18, fontWeight: '800', color: scoreColor(c.avg_score) }}>{c.avg_score != null ? `${c.avg_score}%` : '–'}</Text>
                    <Text style={{ fontSize: 10.5, fontWeight: '700', color: colors.textSecondary }}>AVG THIS MONTH</Text>
                  </View>
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <Bar pct={planned ? (100 * done) / planned : 0} color={GOLD} colors={colors} />
                  <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>{done} of {planned} shops</Text>
                </View>
                <View style={{ flexDirection: 'row', gap: 12, flexWrap: 'wrap' }}>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>Sales {c.progress?.sales.completed ?? 0}/{c.plan.sales_per_month}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>Service {c.progress?.service.completed ?? 0}/{c.plan.service_per_month}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{money(c.plan.price_monthly)}/mo</Text>
                  {!!c.needs_training && <Text style={{ fontSize: 12, fontWeight: '700', color: RED }}>{c.needs_training} need training</Text>}
                  {c.billing?.status && <Text style={{ fontSize: 12, fontWeight: '700', color: c.billing.status === 'paid' ? GREEN : GOLD }}>{c.billing.status}</Text>}
                </View>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}
      <ClientSheet visible={sheet} onClose={() => setSheet(false)} colors={colors} onSaved={(c) => router.push(`/admin/mystery-shops/${c.id}` as any)} defaultFrom={defaultFrom} />
    </SafeAreaView>
  );
}
