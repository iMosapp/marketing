import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Platform, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { Image as ExpoImage } from 'expo-image';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { showSimpleAlert } from '../services/alert';
import api from '../services/api';
import * as ImagePicker from 'expo-image-picker';
import { resolveUserPhotoUrlHiRes, resolvePhotoUrl } from '../utils/photoUrl';

const PROD_BASE = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';

export default function MyProfileScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const setUser = useAuthStore((s: any) => s.setUser);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);

  const uploadPhotoFile = async (fd: FormData) => {
    setPhotoUploading(true);
    try {
      const res = await api.post(`/profile/${user?._id}/photo`, fd);
      if (res.data?.photo_url) {
        setUser({
          ...user,
          photo_url: res.data.photo_url,
          photo_thumb_path: undefined,
          photo_avatar_path: undefined,
        } as any);
        showSimpleAlert('Photo Updated!', 'Your new profile photo is live on all your pages.');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      showSimpleAlert('Upload Failed', typeof detail === 'string' ? detail : 'Please try a JPEG or PNG under 10MB.');
    } finally {
      setPhotoUploading(false);
    }
  };

  const pickAndUploadPhoto = () => {
    if (Platform.OS === 'web') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.style.position = 'fixed';
      input.style.top = '-9999px';
      input.style.opacity = '0';
      document.body.appendChild(input);
      input.onchange = async (e: any) => {
        const file = e.target.files?.[0];
        document.body.removeChild(input);
        if (!file) return;
        const fd = new FormData();
        fd.append('file', file);
        await uploadPhotoFile(fd);
      };
      input.click();
    } else {
      (async () => {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
          showSimpleAlert('Permission Needed', 'Allow photo access to update your profile picture.');
          return;
        }
        const result = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          allowsEditing: true,
          aspect: [1, 1],
          quality: 0.9,
        });
        if (result.canceled || !result.assets?.[0]) return;
        const asset = result.assets[0];
        const fd = new FormData();
        fd.append('file', { uri: asset.uri, type: 'image/jpeg', name: 'profile.jpg' } as any);
        await uploadPhotoFile(fd);
      })();
    }
  };

  useEffect(() => {
    if ((user as any)?.store_slug) {
      setStoreSlug((user as any).store_slug);
      return;
    }
    if (!user?.store_id) return;
    api.get(`/admin/stores/${user.store_id}`, { headers: { 'X-User-ID': user?._id } })
      .then(res => {
        const slug = res.data?.slug;
        if (slug) setStoreSlug(slug);
        else if (res.data?.name) setStoreSlug(res.data.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
      })
      .catch(() => {});
  }, [user?.store_id, (user as any)?.store_slug]);

  const reviewUrl = storeSlug
    ? `${PROD_BASE}/review/${storeSlug}${user?._id ? `?sp=${user._id}` : ''}${(user as any)?.ref_code ? `&ref=${(user as any).ref_code}` : ''}`
    : null;

  const openExternal = (url: string) => {
    const sep = url.includes('?') ? '&' : '?';
    const u = `${url}${sep}self_preview=1`;
    if (Platform.OS === 'web') window.open(u, '_blank');
    else Linking.openURL(u);
  };

  const shareLink = (url: string, label: string) => {
    if (Platform.OS === 'web' && navigator.clipboard) {
      navigator.clipboard.writeText(url);
      showSimpleAlert('Copied!', `${label} link copied to clipboard`);
    } else if (Platform.OS !== 'web') {
      Linking.openURL(`sms:?body=${encodeURIComponent(`Check this out: ${url}`)}`);
    }
  };

  const perms = (user as any)?.feature_permissions || {};
  const perm = (section: string, item?: string): boolean => {
    const sec = perms[section];
    if (!sec || !sec._enabled) return false;
    if (!item) return true;
    return !!sec[item];
  };

  const hasPhoto = !!((user as any)?.photo_url || (user as any)?.photo_path);
  const hasBio = !!((user as any)?.persona?.bio || (user as any)?.bio);
  const profileComplete = (user as any)?.onboarding_complete === true || (hasPhoto && hasBio);

  const publicPages = [
    { icon: 'id-card', title: 'My Digital Card', subtitle: 'How customers see you', color: '#C9A962', url: user?._id ? `${PROD_BASE}/card/${user._id}` : null, editRoute: '/settings/store-profile', quickSend: 'digitalcard' },
    { icon: 'link', title: 'My Link Page', subtitle: 'All your links in one spot', color: '#007AFF', url: user?._id ? `${PROD_BASE}/l/${user._id}` : null, editRoute: '/settings/link-page', quickSend: 'linkpage' },
    { icon: 'planet-outline', title: 'My Landing Page', subtitle: 'Your full personal page', color: '#AF52DE', url: user?._id ? `${PROD_BASE}/p/${user._id}` : null, editRoute: '/settings/store-profile', quickSend: 'landingpage' },
    { icon: 'images', title: 'My Showcase', subtitle: 'Your customer gallery', color: '#34C759', url: user?._id ? `${PROD_BASE}/showcase/${user._id}` : null, editRoute: '/showroom-manage', quickSend: 'showcase' },
    { icon: 'star', title: 'Review Link', subtitle: 'Share to get reviews', color: '#FFD60A', url: reviewUrl, editRoute: '/settings/review-links', quickSend: 'review' },
  ];

  const contentItems = [
    ...(perm('content', 'sms_templates') ? [{ icon: 'document-text', title: 'My Templates', subtitle: 'SMS & email templates', color: '#AF52DE', route: '/settings/templates' }] : []),
    { icon: 'color-palette-outline', title: 'Card Templates', subtitle: 'Thank-you & congrats card designs', color: '#FF9500', route: '/settings/card-templates' },
    { icon: 'mail-outline', title: 'Email Signature', subtitle: 'Copy & paste into your email', color: '#5856D6', route: '/email-signature' },
    { icon: 'megaphone-outline', title: 'Quick Broadcast', subtitle: 'Write a message, copy & share anywhere', color: '#C9A962', route: '/broadcast-message' },
    { icon: 'gift', title: 'Create a Card to Share', subtitle: 'Pick a template, get a trackable link', color: '#FF9500', route: '/settings/create-card?generic=true' },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={{ paddingBottom: 60 }}>
        {/* Cover header */}
        <View style={styles.coverWrap}>
          {(user as any)?.cover_photo_url ? (
            <ExpoImage source={{ uri: resolvePhotoUrl((user as any).cover_photo_url) || '' }} style={StyleSheet.absoluteFill} contentFit="cover" placeholder={null} />
          ) : (
            <LinearGradient colors={['#1a1200', '#2c1f00', '#3d2c00', '#C9A96225']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={StyleSheet.absoluteFill} />
          )}
          <LinearGradient colors={['rgba(0,0,0,0.35)', 'rgba(0,0,0,0.8)']} style={StyleSheet.absoluteFill} />
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="my-profile-back-btn">
            <Ionicons name="chevron-back" size={24} color="#fff" />
          </TouchableOpacity>
          <View style={styles.coverBottom}>
            <TouchableOpacity onPress={pickAndUploadPhoto} activeOpacity={0.8} data-testid="change-photo-btn">
              {(user as any)?.photo_url ? (
                <ExpoImage source={{ uri: resolveUserPhotoUrlHiRes(user as any) || '' }} style={styles.avatar} contentFit="cover" placeholder={null} />
              ) : (
                <View style={[styles.avatar, styles.avatarFallback]}>
                  <Text style={styles.avatarText}>{user?.name?.split(' ').map((n: string) => n[0]).join('').toUpperCase() || '?'}</Text>
                </View>
              )}
              <View style={styles.cameraBadge}>
                {photoUploading
                  ? <Text style={{ fontSize: 8, color: '#000', fontWeight: '800' }}>...</Text>
                  : <Ionicons name="camera" size={12} color="#000" />}
              </View>
            </TouchableOpacity>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{user?.name || 'Guest'}</Text>
              {((user as any)?.persona?.title || (user as any)?.title) ? (
                <Text style={styles.title}>{(user as any)?.persona?.title || (user as any)?.title}</Text>
              ) : null}
              <Text style={styles.email}>{user?.email || ''}</Text>
            </View>
          </View>
        </View>

        {/* Action buttons */}
        <View style={{ flexDirection: 'row', gap: 10, paddingHorizontal: 16, marginTop: 12 }}>
          <TouchableOpacity style={styles.actionBtn} onPress={() => router.push('/my-account' as any)} data-testid="edit-my-info-btn">
            <Ionicons name="create-outline" size={17} color="#C9A962" />
            <Text style={styles.actionBtnText}>Edit My Info</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionBtn} onPress={() => router.push('/settings/virtual-assistant' as any)} data-testid="my-profile-va-btn">
            <Ionicons name="person-circle-outline" size={17} color="#C9A962" />
            <Text style={styles.actionBtnText}>Virtual Assistant</Text>
          </TouchableOpacity>
        </View>

        {/* Finish profile nudge */}
        {!profileComplete && (
          <TouchableOpacity style={styles.nudge} onPress={() => router.push('/profile-setup' as any)} data-testid="finish-profile-nudge">
            <Ionicons name="sparkles" size={16} color="#C9A962" />
            <Text style={styles.nudgeText}>Finish your profile — add {!hasPhoto ? 'a photo' : ''}{!hasPhoto && !hasBio ? ' & ' : ''}{!hasBio ? 'a bio' : ''} so your pages look their best</Text>
            <Ionicons name="chevron-forward" size={16} color="#C9A962" />
          </TouchableOpacity>
        )}

        {/* Public pages */}
        <Text style={styles.sectionLabel}>HOW CUSTOMERS SEE ME</Text>
        <Text style={styles.sectionHint}>These are your public pages — share them anywhere.</Text>
        {publicPages.map((p) => (
          <View key={p.title} style={styles.pageCard} data-testid={`profile-page-${p.quickSend}`}>
            <View style={[styles.pageIcon, { backgroundColor: `${p.color}20` }]}>
              <Ionicons name={p.icon as any} size={20} color={p.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.pageTitle}>{p.title}</Text>
              <Text style={styles.pageSubtitle}>{p.subtitle}</Text>
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                {p.url && (
                  <TouchableOpacity style={[styles.chipBtn, { backgroundColor: p.color }]} onPress={() => shareLink(p.url!, p.title)} data-testid={`share-${p.quickSend}`}>
                    <Ionicons name="share-outline" size={13} color="#000" />
                    <Text style={[styles.chipBtnText, { color: '#000' }]}>Share</Text>
                  </TouchableOpacity>
                )}
                {p.url && (
                  <TouchableOpacity style={[styles.chipBtn, { backgroundColor: colors.surface }]} onPress={() => router.push(`/quick-send/${p.quickSend}` as any)} data-testid={`send-${p.quickSend}`}>
                    <Ionicons name="paper-plane-outline" size={13} color={colors.textSecondary} />
                    <Text style={[styles.chipBtnText, { color: colors.textSecondary }]}>Send to Contact</Text>
                  </TouchableOpacity>
                )}
                {p.url && (
                  <TouchableOpacity style={[styles.chipBtn, { backgroundColor: colors.surface }]} onPress={() => openExternal(p.url!)} data-testid={`view-${p.quickSend}`}>
                    <Ionicons name="eye-outline" size={13} color={colors.textSecondary} />
                    <Text style={[styles.chipBtnText, { color: colors.textSecondary }]}>View</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity style={[styles.chipBtn, { backgroundColor: colors.surface }]} onPress={() => router.push(p.editRoute as any)} data-testid={`edit-${p.quickSend}`}>
                  <Ionicons name="create-outline" size={13} color={colors.textSecondary} />
                  <Text style={[styles.chipBtnText, { color: colors.textSecondary }]}>Edit</Text>
                </TouchableOpacity>
              </View>
              {p.title === 'Review Link' && !p.url && (
                <Text style={{ fontSize: 11, color: '#FF9500', marginTop: 6 }}>Store slug not set — tap Edit to configure</Text>
              )}
            </View>
          </View>
        ))}

        {/* Content tools */}
        <Text style={[styles.sectionLabel, { marginTop: 20 }]}>MY CONTENT</Text>
        {contentItems.map((c) => (
          <TouchableOpacity key={c.title} style={styles.contentRow} onPress={() => router.push(c.route as any)} activeOpacity={0.7} data-testid={`content-${c.title.toLowerCase().replace(/\s+/g, '-')}`}>
            <View style={[styles.pageIcon, { backgroundColor: `${c.color}20`, width: 34, height: 34, borderRadius: 17 }]}>
              <Ionicons name={c.icon as any} size={17} color={c.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.pageTitle}>{c.title}</Text>
              <Text style={styles.pageSubtitle}>{c.subtitle}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  coverWrap: { height: 190, marginHorizontal: 16, marginTop: 8, borderRadius: 20, overflow: 'hidden', justifyContent: 'flex-end' },
  backBtn: { position: 'absolute', top: 10, left: 10, width: 34, height: 34, borderRadius: 17, backgroundColor: 'rgba(0,0,0,0.4)', alignItems: 'center', justifyContent: 'center', zIndex: 5 },
  coverBottom: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14 },
  avatar: { width: 62, height: 62, borderRadius: 16, borderWidth: 2, borderColor: '#C9A962' },
  cameraBadge: { position: 'absolute', bottom: -4, right: -4, width: 22, height: 22, borderRadius: 11, backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#000' },
  avatarFallback: { backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 22, fontWeight: '800', color: '#000' },
  name: { fontSize: 20, fontWeight: '800', color: '#fff' },
  title: { fontSize: 12, fontWeight: '700', color: '#C9A962', letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 1 },
  email: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  actionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#C9A96218', borderWidth: 1, borderColor: '#C9A96250', borderRadius: 12, paddingVertical: 11 },
  actionBtnText: { fontSize: 13, fontWeight: '700', color: '#C9A962' },
  nudge: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#C9A96212', borderRadius: 12, padding: 12, marginHorizontal: 16, marginTop: 12, borderWidth: 1, borderColor: '#C9A96230' },
  nudgeText: { flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
  sectionLabel: { fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginHorizontal: 16, marginTop: 22, marginBottom: 2 },
  sectionHint: { fontSize: 12, color: colors.textTertiary, marginHorizontal: 16, marginBottom: 10 },
  pageCard: { flexDirection: 'row', gap: 12, backgroundColor: colors.card, borderRadius: 16, padding: 14, marginHorizontal: 16, marginBottom: 10, borderWidth: 1, borderColor: colors.border },
  pageIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  pageTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  pageSubtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  chipBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 14, paddingHorizontal: 10, paddingVertical: 5 },
  chipBtnText: { fontSize: 12, fontWeight: '700' },
  contentRow: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 12, marginHorizontal: 16, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
});
