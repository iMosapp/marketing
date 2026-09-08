import React, { useCallback, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, TextInput, Modal, Linking, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { Image } from 'expo-image';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { copyToClipboard } from '../../utils/clipboard';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { showAlert } from '../../services/alert';
import api from '../../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const openUrl = (url: string) => {
  if (Platform.OS === 'web' && typeof window !== 'undefined') window.open(url, '_blank');
  else Linking.openURL(url).catch(() => {});
};

const timeAgo = (iso: string | null) => {
  if (!iso) return 'never';
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? 'yesterday' : `${d}d ago`;
};

type GoLink = { slug: string; label: string; destination: string; short_url: string; qr_png_path: string; qr_svg_path: string; scans: { total: number; week: number; today: number; last_scan_at: string | null } };

export default function PrintQrScreen() {
  const { colors } = useThemeStore();
  const { user, isLoading: authLoading } = useAuthStore();
  const router = useRouter();
  const { showToast } = useToast();
  const [links, setLinks] = useState<GoLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [editing, setEditing] = useState<{ slug: string; label: string; destination: string; isNew: boolean } | null>(null);
  const [saving, setSaving] = useState(false);
  const base = api.defaults.baseURL;

  const load = useCallback(async () => {
    try {
      const r = await api.get('/go-links');
      setLinks(r.data.links || []);
    } catch (e: any) {
      showAlert('Could not load', e?.response?.data?.detail || 'Try again.');
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

  const save = async () => {
    if (!editing || saving) return;
    setSaving(true);
    try {
      await api.post('/go-links', { slug: editing.slug.trim().toLowerCase(), label: editing.label, destination: editing.destination.trim() });
      showToast(editing.isNew ? 'QR link created' : 'Destination updated');
      setEditing(null);
      load();
    } catch (e: any) {
      showAlert('Not saved', e?.response?.data?.detail || 'Check the slug and URL.');
    } finally {
      setSaving(false);
    }
  };

  const copy = async (text: string) => { await copyToClipboard(text); showToast('Copied'); };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Print QR Codes" testID="print-qr" />
      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator size="large" color={GOLD} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 48, gap: 14 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.textSecondary} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('print-qr-intro')}>
            Every QR here points at a short imonsocial.com/go link. Scans are counted, and you can change where a code lands later without reprinting anything.
          </Text>

          {links.map(link => (
            <View key={link.slug} style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 12 }} {...tid(`print-qr-card-${link.slug}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ backgroundColor: '#FFF', borderRadius: 12, padding: 6 }}>
                  <Image source={{ uri: `${base}${link.qr_png_path}?size=512` }} style={{ width: 96, height: 96 }} contentFit="contain" {...tid(`print-qr-image-${link.slug}`)} />
                </View>
                <View style={{ flex: 1, gap: 3 }}>
                  <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>{link.label || link.slug}</Text>
                  <TouchableOpacity onPress={() => copy(link.short_url)} {...tid(`print-qr-short-${link.slug}`)}>
                    <Text style={{ fontSize: 14, fontWeight: '700', color: GOLD }}>{link.short_url.replace(/^https?:\/\//, '')} <Ionicons name="copy-outline" size={13} color={GOLD} /></Text>
                  </TouchableOpacity>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2}>Lands on: {link.destination}</Text>
                </View>
              </View>

              <View style={{ flexDirection: 'row', gap: 8 }}>
                {[{ k: 'total', v: link.scans.total, l: 'All time' }, { k: 'week', v: link.scans.week, l: 'This week' }, { k: 'today', v: link.scans.today, l: 'Today' }].map(s => (
                  <View key={s.k} style={{ flex: 1, backgroundColor: colors.surface, borderRadius: 12, padding: 10 }} {...tid(`print-qr-stat-${link.slug}-${s.k}`)}>
                    <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>{s.v}</Text>
                    <Text style={{ fontSize: 11, color: colors.textSecondary }}>{s.l}</Text>
                  </View>
                ))}
              </View>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>Last scan: {timeAgo(link.scans.last_scan_at)}</Text>

              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity onPress={() => openUrl(`${base}${link.qr_png_path}?size=3000`)} style={{ flex: 1, height: 44, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`print-qr-download-png-${link.slug}`)}>
                  <Ionicons name="download-outline" size={17} color="#111" />
                  <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>PNG 3000px</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => openUrl(`${base}${link.qr_svg_path}`)} style={{ flex: 1, height: 44, borderRadius: 12, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`print-qr-download-svg-${link.slug}`)}>
                  <Ionicons name="shapes-outline" size={17} color={colors.text} />
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>SVG (vector)</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => setEditing({ slug: link.slug, label: link.label, destination: link.destination, isNew: false })} style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid(`print-qr-edit-${link.slug}`)}>
                  <Ionicons name="create-outline" size={18} color={colors.text} />
                </TouchableOpacity>
              </View>
            </View>
          ))}

          <TouchableOpacity onPress={() => setEditing({ slug: '', label: '', destination: 'https://www.imonsocial.com/', isNew: true })} style={{ height: 50, borderRadius: 14, borderWidth: 1.5, borderColor: GOLD, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('print-qr-add-btn')}>
            <Ionicons name="add" size={20} color={GOLD} />
            <Text style={{ fontSize: 15, fontWeight: '700', color: GOLD }}>New QR link (flyer, banner, sign...)</Text>
          </TouchableOpacity>

          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>
            Print tips: use the SVG for the designer, keep the white margin around the code, and print it at least 0.8 in (2 cm) wide. High error correction is built in, so a small logo over the center still scans.
          </Text>
        </ScrollView>
      )}

      <Modal visible={!!editing} transparent animationType="fade" onRequestClose={() => setEditing(null)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: 24 }}>
          <View style={{ backgroundColor: colors.card, borderRadius: 20, padding: 20, gap: 12 }} {...tid('print-qr-edit-modal')}>
            <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>{editing?.isNew ? 'New QR link' : 'Edit destination'}</Text>
            {editing?.isNew ? (
              <View style={{ gap: 4 }}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>SHORT CODE  (imonsocial.com/go/…)</Text>
                <TextInput value={editing.slug} onChangeText={t => setEditing(e => e && { ...e, slug: t.toLowerCase().replace(/[^a-z0-9-]/g, '') })} placeholder="flyer" placeholderTextColor={colors.textTertiary} autoCapitalize="none" autoCorrect={false}
                  style={{ backgroundColor: colors.surface, borderRadius: 12, padding: 12, fontSize: 16, color: colors.text }} {...tid('print-qr-slug-input')} />
              </View>
            ) : null}
            <View style={{ gap: 4 }}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>LABEL</Text>
              <TextInput value={editing?.label || ''} onChangeText={t => setEditing(e => e && { ...e, label: t })} placeholder="4x6 leave-behind card" placeholderTextColor={colors.textTertiary}
                style={{ backgroundColor: colors.surface, borderRadius: 12, padding: 12, fontSize: 16, color: colors.text }} {...tid('print-qr-label-input')} />
            </View>
            <View style={{ gap: 4 }}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>WHERE IT LANDS</Text>
              <TextInput value={editing?.destination || ''} onChangeText={t => setEditing(e => e && { ...e, destination: t })} placeholder="https://www.imonsocial.com/" placeholderTextColor={colors.textTertiary} autoCapitalize="none" autoCorrect={false} keyboardType="url"
                style={{ backgroundColor: colors.surface, borderRadius: 12, padding: 12, fontSize: 16, color: colors.text }} {...tid('print-qr-destination-input')} />
            </View>
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 4 }}>
              <TouchableOpacity onPress={() => setEditing(null)} style={{ flex: 1, height: 46, borderRadius: 12, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid('print-qr-cancel-btn')}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={save} disabled={saving} style={{ flex: 1, height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: saving ? 0.6 : 1 }} {...tid('print-qr-save-btn')}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>{saving ? 'Saving…' : 'Save'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
