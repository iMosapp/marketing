/**
 * HotVehiclesCard - what shoppers are opening (tracked lot links) and asking Jessi about this week, store-wide.
 * variant 'home' = compact top 3 strip, 'full' = top 8 with shopper chips (Inventory screen).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { resolvePhotoUrl } from '../../utils/photoUrl';

const GOLD = '#C9A962';
const FLAME = '#FF6B35';
const tid = (id: string): any => ({ testID: id, dataSet: { testid: id } });

type Shopper = { contact_id: string; name: string; clicks: number; asks: number; rep: string; mine: boolean; last?: string | null };
export type HotVehicle = {
  inventory_id: string; name: string; price?: number | null; status: string; stock_number?: string; photo?: string | null; primary_image?: string | null;
  clicks: number; asks: number; shoppers: Shopper[]; shopper_count: number; score: number; trend: 'new' | 'up' | 'down' | 'flat'; last_activity?: string | null;
};

const ago = (iso?: string | null) => {
  if (!iso) return '';
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
};

export function HotVehiclesCard({ userId, variant = 'home' }: { userId: string; variant?: 'home' | 'full' }) {
  const { colors } = useThemeStore();
  const router = useRouter();
  const [data, setData] = useState<{ vehicles: HotVehicle[]; total_shoppers: number } | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!userId) return;
    api.get(`/inventory/${userId}/hot?days=7&limit=${variant === 'home' ? 3 : 8}`).then(r => setData(r.data)).catch(() => {});
  }, [userId, variant]);
  useEffect(load, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (!data || data.vehicles.length === 0) return null;

  const photoOf = (v: HotVehicle) => v.photo ? (resolvePhotoUrl(v.photo) || v.photo) : v.primary_image || null;
  const trendIcon = (t: HotVehicle['trend']) => t === 'up' ? 'trending-up' : t === 'down' ? 'trending-down' : t === 'new' ? 'sparkles' : 'remove';

  const header = (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
      <View style={{ width: 26, height: 26, borderRadius: 8, backgroundColor: `${FLAME}22`, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name="flame" size={14} color={FLAME} />
      </View>
      <Text maxFontSizeMultiplier={1} style={{ fontSize: 12, fontWeight: '700', color: FLAME, letterSpacing: 0.8, flex: 1 }}>HOT THIS WEEK</Text>
      <Text maxFontSizeMultiplier={1} style={{ fontSize: 12, color: colors.textSecondary }} {...tid('hot-vehicles-shoppers')}>
        {data.total_shoppers} shopper{data.total_shoppers === 1 ? '' : 's'}
      </Text>
    </View>
  );

  if (variant === 'home') {
    return (
      <View style={{ marginHorizontal: 16, marginBottom: 16, padding: 14, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: `${FLAME}40` }} {...tid('hot-vehicles-card')}>
        {header}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
          {data.vehicles.map((v, i) => {
            const p = photoOf(v);
            return (
              <TouchableOpacity key={v.inventory_id} onPress={() => router.push('/inventory?hot=1' as any)} style={{ width: 168, backgroundColor: colors.bg, borderRadius: 12, overflow: 'hidden' }} {...tid(`hot-vehicle-${v.inventory_id}`)}>
                <View style={{ height: 84, backgroundColor: colors.surface }}>
                  {p ? <Image source={{ uri: p }} style={{ width: '100%', height: '100%' }} contentFit="cover" /> : (
                    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="car-sport" size={26} color={colors.textTertiary} /></View>
                  )}
                  <View style={{ position: 'absolute', top: 6, left: 6, backgroundColor: FLAME, borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2, flexDirection: 'row', alignItems: 'center', gap: 3 }}>
                    <Ionicons name="flame" size={10} color="#fff" /><Text style={{ fontSize: 10, fontWeight: '800', color: '#fff' }}>#{i + 1}</Text>
                  </View>
                </View>
                <View style={{ padding: 8, gap: 2 }}>
                  <Text maxFontSizeMultiplier={1} style={{ fontSize: 13, fontWeight: '700', color: colors.text }} numberOfLines={1}>{v.name}</Text>
                  <Text maxFontSizeMultiplier={1} style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
                    {v.clicks} open{v.clicks === 1 ? '' : 's'} · {v.asks} ask{v.asks === 1 ? '' : 's'} · {v.shopper_count} shopper{v.shopper_count === 1 ? '' : 's'}
                  </Text>
                </View>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={{ marginHorizontal: 16, marginBottom: 12, padding: 14, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: `${FLAME}40` }} {...tid('hot-vehicles-card')}>
      {header}
      <Text maxFontSizeMultiplier={1} style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 10 }}>Opens = shoppers tapping the lot link Jessi sent. Asks = shoppers asking about the exact vehicle. Push these first.</Text>
      {data.vehicles.map((v, i) => {
        const p = photoOf(v);
        const isOpen = open === v.inventory_id;
        return (
          <View key={v.inventory_id} style={{ borderTopWidth: i ? 1 : 0, borderTopColor: colors.border, paddingVertical: 10 }}>
            <TouchableOpacity onPress={() => setOpen(isOpen ? null : v.inventory_id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`hot-vehicle-${v.inventory_id}`)}>
              <Text maxFontSizeMultiplier={1} style={{ width: 18, fontSize: 14, fontWeight: '800', color: i === 0 ? FLAME : colors.textSecondary }}>{i + 1}</Text>
              <View style={{ width: 48, height: 48, borderRadius: 10, backgroundColor: colors.surface, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' }}>
                {p ? <Image source={{ uri: p }} style={{ width: 48, height: 48 }} contentFit="cover" /> : <Ionicons name="car-sport" size={20} color={colors.textTertiary} />}
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text maxFontSizeMultiplier={1} style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{v.name}</Text>
                <Text maxFontSizeMultiplier={1} style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
                  {v.clicks} open{v.clicks === 1 ? '' : 's'} · {v.asks} ask{v.asks === 1 ? '' : 's'} · {v.shopper_count} shopper{v.shopper_count === 1 ? '' : 's'}{v.status === 'sold' ? ' · SOLD' : ''}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 2 }}>
                <Ionicons name={trendIcon(v.trend) as any} size={16} color={v.trend === 'down' ? colors.textTertiary : FLAME} />
                <Text maxFontSizeMultiplier={1} style={{ fontSize: 10, color: colors.textTertiary }}>{ago(v.last_activity)}</Text>
              </View>
              <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textTertiary} />
            </TouchableOpacity>
            {isOpen && (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10, marginLeft: 28 }} {...tid(`hot-shoppers-${v.inventory_id}`)}>
                {v.shoppers.map(s => (
                  <TouchableOpacity key={s.contact_id} onPress={() => router.push(`/contact/${s.contact_id}` as any)}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: s.mine ? `${GOLD}22` : colors.bg, borderWidth: 1, borderColor: s.mine ? GOLD : colors.border, borderRadius: 14, paddingHorizontal: 10, paddingVertical: 6 }}
                    {...tid(`hot-shopper-${s.contact_id}`)}>
                    <Ionicons name="person" size={11} color={s.mine ? GOLD : colors.textSecondary} />
                    <Text maxFontSizeMultiplier={1} style={{ fontSize: 12, fontWeight: '600', color: colors.text }}>{s.name}</Text>
                    <Text maxFontSizeMultiplier={1} style={{ fontSize: 11, color: colors.textSecondary }}>
                      {s.clicks ? `${s.clicks}x` : ''}{!s.mine && s.rep ? ` · ${s.rep}` : ''}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
}

export default HotVehiclesCard;
