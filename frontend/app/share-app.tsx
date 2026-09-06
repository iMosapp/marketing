import React, { useCallback, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, Share, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { Image } from 'expo-image';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import { copyToClipboard } from '../utils/clipboard';
import { useToast } from '../components/common/Toast';
import api from '../services/api';

const ACCENT = '#34C759';

const timeAgo = (iso: string) => {
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? 'yesterday' : `${d}d ago`;
};

const EVENT_META: Record<string, { icon: any; color: string; label: (r: any) => string }> = {
  tap: { icon: 'finger-print', color: '#8E8E93', label: r => `Link tapped on ${r.platform === 'ios' ? 'iPhone' : r.platform === 'android' ? 'Android' : 'desktop'}${r.code === 'site' ? ' (website QR)' : ''}` },
  install: { icon: 'phone-portrait', color: ACCENT, label: r => `Installed the app${r.code === 'site' ? ' from the website QR' : ''}` },
  signup: { icon: 'person-add', color: '#C9A962', label: r => `${r.name || 'Someone'} installed and signed up` },
};

export default function ShareAppScreen() {
  const { colors } = useThemeStore();
  const { user, isLoading: authLoading } = useAuthStore();
  const router = useRouter();
  const { showToast } = useToast();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try {
      const r = await api.get(`/app-links/${user._id}`);
      setData(r.data);
    } catch (e) {
      console.error('share-app load failed', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id]);

  useFocusEffect(useCallback(() => {
    if (authLoading) return;
    if (!user?._id) { router.replace('/auth/login' as any); return; }
    load();
  }, [load, user?._id, authLoading, router]));

  const copy = async () => {
    if (!data?.link) return;
    await copyToClipboard(data.link);
    showToast('Link copied');
  };

  const share = async () => {
    if (!data?.link) return;
    const message = `Get the i'M On Social app: ${data.link}`;
    if (Platform.OS === 'web') { await copy(); return; }
    try { await Share.share({ message, url: data.link }); } catch {}
  };

  const stats = data?.stats || {};
  const statCards = [
    { key: 'taps', label: 'Taps', value: stats.taps ?? 0, sub: `${stats.taps_week ?? 0} this week`, color: '#8E8E93' },
    { key: 'installs', label: 'Installs', value: stats.installs ?? 0, sub: 'from your link', color: ACCENT },
    { key: 'signups', label: 'Signed up', value: stats.signups ?? 0, sub: 'by name', color: '#C9A962' },
  ];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} data-testid="share-app-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text, flex: 1 }}>Share the App</Text>
      </View>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator size="large" color={ACCENT} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 14 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.textSecondary} />}>

          <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 18, alignItems: 'center', gap: 14 }} data-testid="share-app-link-card">
            <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>
              Your install link. iPhones go straight to the App Store; you get a ping when someone installs and their name when they sign up.
            </Text>
            {data?.qr_path ? (
              <View style={{ backgroundColor: '#FFF', borderRadius: 16, padding: 10 }}>
                <Image source={{ uri: `${api.defaults.baseURL}${data.qr_path}` }} style={{ width: 200, height: 200 }} contentFit="contain" data-testid="share-app-qr" />
              </View>
            ) : null}
            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }} selectable data-testid="share-app-link-text">{data?.link}</Text>
            <View style={{ flexDirection: 'row', gap: 10, width: '100%' }}>
              <TouchableOpacity onPress={copy} style={{ flex: 1, height: 46, borderRadius: 12, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} data-testid="share-app-copy-btn">
                <Ionicons name="copy-outline" size={17} color={colors.text} />
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Copy</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={share} style={{ flex: 1, height: 46, borderRadius: 12, backgroundColor: ACCENT, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} data-testid="share-app-share-btn">
                <Ionicons name="share-outline" size={17} color="#000" />
                <Text style={{ fontSize: 15, fontWeight: '700', color: '#000' }}>Share</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={{ flexDirection: 'row', gap: 10 }}>
            {statCards.map(c => (
              <View key={c.key} style={{ flex: 1, backgroundColor: colors.card, borderRadius: 14, padding: 14 }} data-testid={`share-app-stat-${c.key}`}>
                <Text style={{ fontSize: 26, fontWeight: '800', color: c.color }}>{c.value}</Text>
                <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text, marginTop: 2 }}>{c.label}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{c.sub}</Text>
              </View>
            ))}
          </View>

          <Text style={{ fontSize: 12, fontWeight: '700', letterSpacing: 1, color: colors.textSecondary, marginTop: 6 }}>RECENT ACTIVITY</Text>
          {(data?.recent || []).length === 0 ? (
            <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 18, alignItems: 'center', gap: 6 }} data-testid="share-app-empty">
              <Ionicons name="paper-plane-outline" size={26} color={colors.textSecondary} />
              <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center' }}>No taps yet. Text the link to someone or let them scan the QR.</Text>
            </View>
          ) : (
            <View style={{ backgroundColor: colors.card, borderRadius: 14 }} data-testid="share-app-recent-list">
              {data.recent.map((r: any, i: number) => {
                const meta = EVENT_META[r.kind] || EVENT_META.tap;
                return (
                  <View key={`${r.kind}-${r.at}-${i}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}>
                    <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: `${meta.color}22`, alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name={meta.icon} size={17} color={meta.color} />
                    </View>
                    <Text style={{ flex: 1, fontSize: 14, color: colors.text }}>{meta.label(r)}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>{timeAgo(r.at)}</Text>
                  </View>
                );
              })}
            </View>
          )}

          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17, marginTop: 4 }}>
            Installs are matched to taps from the same network within 3 days, so a count can occasionally be off by one. Sign-ups are exact.
          </Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
