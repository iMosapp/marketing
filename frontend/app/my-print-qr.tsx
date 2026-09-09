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
  const [side, setSide] = useState<'front' | 'back'>('front');
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

          {data?.print_pdf_path ? (
            <View style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 12 }} {...tid('my-print-card')}>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Your 4x6 leave-behind card</Text>
                <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 10, padding: 2 }}>
                  {(['front', 'back'] as const).map(s => (
                    <TouchableOpacity key={s} onPress={() => setSide(s)} style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: side === s ? GOLD : 'transparent' }} {...tid(`my-print-card-side-${s}`)}>
                      <Text style={{ fontSize: 12, fontWeight: '800', color: side === s ? '#111' : colors.textSecondary }}>{s === 'front' ? 'Front' : 'Back'}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
              <View style={{ width: '100%', aspectRatio: 1875 / 1275, borderRadius: 12, overflow: 'hidden', backgroundColor: '#0A0A0F' }}>
                <Image source={{ uri: `${base}${data.print_png_path}?side=${side}&width=1200` }} style={{ width: '100%', height: '100%' }} contentFit="cover" transition={200} {...tid('my-print-card-preview')} />
              </View>
              <TouchableOpacity onPress={() => openUrl(`${base}${data.print_pdf_path}?layout=exact`)} style={{ height: 50, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('my-print-card-download')}>
                <Ionicons name="print-outline" size={19} color="#111" />
                <Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Download 4x6 Card (PDF)</Text>
              </TouchableOpacity>
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <TouchableOpacity onPress={() => openUrl(`${base}${data.print_pdf_path}?layout=letter`)} style={{ flex: 1, height: 42, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('my-print-card-download-letter')}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>Letter sheet + cut marks</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => openUrl(`${base}${data.print_pdf_path}?layout=bleed`)} style={{ flex: 1, height: 42, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('my-print-card-download-bleed')}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>Print shop (with bleed)</Text>
                </TouchableOpacity>
              </View>
              <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>
                4x6 Card = exact 6 x 4 in, front and back, for 4x6 photo paper or any printer set to Actual Size (100%), never "Fit to page". Letter sheet centers the card on 8.5 x 11 with cut marks. Print shop adds the 1/8 in bleed they trim off. Your QR and "Text {(user as any)?.first_name || 'me'}" number are on every version.
              </Text>
            </View>
          ) : null}

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
