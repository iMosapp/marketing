import React, { useCallback, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, Share, Platform, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { Image } from 'expo-image';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import { copyToClipboard } from '../utils/clipboard';
import { useToast } from '../components/common/Toast';
import { ScreenHeader } from '../components/common/ScreenHeader';
import api from '../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const openUrl = (url: string) => {
  if (Platform.OS === 'web' && typeof window !== 'undefined') window.open(url, '_blank');
  else Linking.openURL(url).catch(() => {});
};

export default function MyPrintQrScreen() {
  const { colors } = useThemeStore();
  const { user, isLoading: authLoading } = useAuthStore();
  const router = useRouter();
  const { showToast } = useToast();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const base = api.defaults.baseURL;

  const load = useCallback(async () => {
    try {
      const r = await api.get('/go-links/mine');
      setData(r.data);
    } catch (e) {
      console.error('my-print-qr load failed', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => {
    if (authLoading) return;
    if (!user?._id) { router.replace('/auth/login' as any); return; }
    load();
  }, [load, user?._id, authLoading, router]));

  const copy = async () => { if (data?.short_url) { await copyToClipboard(data.short_url); showToast('Link copied'); } };
  const share = async () => {
    if (!data?.short_url) return;
    if (Platform.OS === 'web') { await copy(); return; }
    try { await Share.share({ message: `See i'M On Social in action: ${data.short_url}`, url: data.short_url }); } catch {}
  };

  const scans = data?.scans || {};
  const stats = [
    { k: 'total', v: scans.total ?? 0, l: 'All time' },
    { k: 'week', v: scans.week ?? 0, l: 'This week' },
    { k: 'today', v: scans.today ?? 0, l: 'Today' },
  ];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="My Print QR" testID="my-print-qr" />
      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator size="large" color={GOLD} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 48, gap: 14 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.textSecondary} />}>
          <View style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 18, alignItems: 'center', gap: 12 }} {...tid('my-print-qr-card')}>
            <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 }}>
              Put this on your cards, flyers or window sign. Whoever scans it sees the 46-second story with your name and photo, can text you in one tap, and every demo they book is credited to you.
            </Text>
            {data?.qr_png_path ? (
              <View style={{ backgroundColor: '#FFF', borderRadius: 16, padding: 10 }}>
                <Image source={{ uri: `${base}${data.qr_png_path}?size=600` }} style={{ width: 220, height: 220 }} contentFit="contain" {...tid('my-print-qr-image')} />
              </View>
            ) : null}
            <TouchableOpacity onPress={copy} {...tid('my-print-qr-link')}>
              <Text style={{ fontSize: 17, fontWeight: '800', color: GOLD }} selectable>{(data?.short_url || '').replace(/^https?:\/\//, '')} <Ionicons name="copy-outline" size={14} color={GOLD} /></Text>
            </TouchableOpacity>
            <View style={{ flexDirection: 'row', gap: 10, width: '100%' }}>
              <TouchableOpacity onPress={() => openUrl(`${base}${data?.qr_png_path}?size=3000`)} style={{ flex: 1, height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('my-print-qr-download-png')}>
                <Ionicons name="download-outline" size={17} color="#111" />
                <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>PNG (print)</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => openUrl(`${base}${data?.qr_svg_path}`)} style={{ flex: 1, height: 46, borderRadius: 12, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('my-print-qr-download-svg')}>
                <Ionicons name="shapes-outline" size={17} color={colors.text} />
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>SVG</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={share} style={{ width: 46, height: 46, borderRadius: 12, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid('my-print-qr-share')}>
                <Ionicons name="share-outline" size={18} color={colors.text} />
              </TouchableOpacity>
            </View>
          </View>

          <View style={{ flexDirection: 'row', gap: 10 }}>
            {stats.map(s => (
              <View key={s.k} style={{ flex: 1, backgroundColor: colors.card, borderRadius: 14, padding: 14 }} {...tid(`my-print-qr-stat-${s.k}`)}>
                <Text style={{ fontSize: 26, fontWeight: '800', color: s.k === 'total' ? GOLD : colors.text }}>{s.v}</Text>
                <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text, marginTop: 2 }}>{s.l}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>scans</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity onPress={() => openUrl(data?.landing_url)} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('my-print-qr-preview')}>
            <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="play-circle-outline" size={20} color={GOLD} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Preview your page</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{(data?.landing_url || '').replace(/^https?:\/\//, '')}</Text>
            </View>
            <Ionicons name="open-outline" size={18} color={colors.textSecondary} />
          </TouchableOpacity>

          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>
            "Text {(user as any)?.first_name || 'me'}" on your page goes to your IMOS number{data?.sms_number ? ` (${data.sms_number})` : ' once one is assigned'}, so replies land in your Inbox. Print the code at least 0.8 in (2 cm) wide with the white margin.
          </Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
