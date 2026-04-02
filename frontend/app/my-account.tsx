/**
 * my-account.tsx — "My Presence" redesign.
 *
 * A+B hybrid: Instagram-style profile header (cover photo, avatar,
 * inline editable bio) + visual tap-cards for all presence assets below.
 *
 * Layout:
 *  1. Cover photo banner + profile circle (overlap)
 *  2. Name / title / bio — inline editable, tap to edit
 *  3. Profile completeness bar
 *  4. Social link chips
 *  5. Presence asset cards (2-column grid)
 *  6. My Photos gallery
 *  7. Address (collapsible)
 *  8. Personal Settings
 *  9. Account Info
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, Platform, Linking, Animated, ActivityIndicator,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter, useFocusEffect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';
import { ProfilePhotoUpload } from '../components/account/ProfilePhotoUpload';
import { ProfileGallery } from '../components/account/ProfileGallery';
import { ShareReviewModal } from '../components/account/ShareReviewModal';
import { AccountInfoCard } from '../components/account/AccountInfoCard';
import { StoreManagement } from '../components/account/StoreManagement';
import { resolveUserPhotoUrlHiRes, resolvePhotoUrl } from '../utils/photoUrl';

const PROD_BASE = 'https://app.imonsocial.com';

const SOCIAL_PLATFORMS = [
  { key: 'instagram', icon: 'logo-instagram', color: '#E1306C', label: 'Instagram' },
  { key: 'facebook',  icon: 'logo-facebook',  color: '#1877F2', label: 'Facebook'  },
  { key: 'tiktok',    icon: 'logo-tiktok',     color: '#FFFFFF', label: 'TikTok'    },
  { key: 'youtube',   icon: 'logo-youtube',    color: '#FF0000', label: 'YouTube'   },
  { key: 'linkedin',  icon: 'logo-linkedin',   color: '#0A66C2', label: 'LinkedIn'  },
  { key: 'twitter',   icon: 'logo-twitter',    color: '#1DA1F2', label: 'Twitter'   },
];

// ─── Profile completeness ─────────────────────────────────────────────────────
function calcCompleteness(user: any): number {
  const fields = [
    user?.photo_url || user?.photo_path,
    user?.name,
    user?.phone,
    user?.persona?.bio || user?.bio,
    user?.persona?.title || user?.title,
    Object.values(user?.persona?.social_links || user?.social_links || {}).some(Boolean),
  ];
  const done = fields.filter(Boolean).length;
  return Math.round((done / fields.length) * 100);
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function MyAccountScreen() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const router = useRouter();
  const { user, setUser, updateUser } = useAuthStore();

  // ── State ──────────────────────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<'personal' | 'store'>('personal');
  const [storeSlug, setStoreSlug] = useState<string | null>(user?.store_slug || null);
  const [storeName, setStoreName] = useState<string | null>(user?.store_name || null);
  const [showShareModal, setShowShareModal] = useState(false);
  const [copiedReview, setCopiedReview] = useState(false);
  const [addressOpen, setAddressOpen] = useState(false);
  const [editingBio, setEditingBio] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [editingPhone, setEditingPhone] = useState(false);
  const [editingEmail, setEditingEmail] = useState(false);
  const [savingBio, setSavingBio] = useState(false);
  const [coverUploading, setCoverUploading] = useState(false);
  // Social link inline editing
  const [editingSocial, setEditingSocial] = useState<string | null>(null);
  const [socialEditValue, setSocialEditValue] = useState('');

  // Local edit buffers
  const [bioText, setBioText] = useState(user?.persona?.bio || user?.bio || '');
  const [nameText, setNameText] = useState(user?.name || '');
  const [titleText, setTitleText] = useState(user?.persona?.title || user?.title || '');
  const [phoneText, setPhoneText] = useState((user as any)?.phone || '');
  const [emailText, setEmailText] = useState(user?.email || '');

  const bioInputRef = useRef<TextInput>(null);
  const completeness = calcCompleteness(user);
  const isManager = !!user?.role && ['super_admin', 'org_admin', 'store_manager'].includes(user.role);
  const coverPhotoUrl = (user as any)?.cover_photo_url || null;

  const reviewUrl = storeSlug
    ? `${PROD_BASE}/review/${storeSlug}${user?._id ? `?sp=${user._id}` : ''}`
    : '';

  // ── Data loading ───────────────────────────────────────────────────────────
  useFocusEffect(useCallback(() => {
    if (user?._id) refreshUserData();
    if (user?.store_id && !storeSlug) fetchStoreSlug();
  }, [user?._id]));

  async function fetchStoreSlug() {
    try {
      const res = await api.get(`/admin/stores/${user?.store_id}`);
      if (res.data?.slug) setStoreSlug(res.data.slug);
      if (res.data?.name) setStoreName(res.data.name);
    } catch {}
  }

  async function refreshUserData() {
    try {
      const res = await api.get(`/users/${user?._id}`);
      if (res.data) {
        const merged = { ...user, ...res.data };
        setUser(merged);
        setBioText(merged?.persona?.bio || merged?.bio || '');
        setNameText(merged?.name || '');
        setTitleText(merged?.persona?.title || merged?.title || '');
        try { await AsyncStorage.setItem('user', JSON.stringify(merged)).catch(() => {}); } catch {}
      }
    } catch {}
  }

  // ── Save fields ────────────────────────────────────────────────────────────
  async function saveBio() {
    setSavingBio(true);
    try {
      await api.patch(`/users/${user?._id}`, { bio: bioText });
      setUser({ ...user, bio: bioText, persona: { ...(user as any)?.persona, bio: bioText } });
      setEditingBio(false);
    } catch { showSimpleAlert('Error', 'Failed to save bio.'); }
    setSavingBio(false);
  }

  async function saveName() {
    if (!nameText.trim()) return;
    try {
      await api.patch(`/users/${user?._id}`, { name: nameText.trim() });
      setUser({ ...user, name: nameText.trim() });
      setEditingName(false);
    } catch { showSimpleAlert('Error', 'Failed to save name.'); }
  }

  async function saveTitle() {
    try {
      await api.patch(`/users/${user?._id}`, { persona: { ...(user as any)?.persona, title: titleText } });
      setUser({ ...user, persona: { ...(user as any)?.persona, title: titleText } });
      setEditingTitle(false);
    } catch { showSimpleAlert('Error', 'Failed to save title.'); }
  }

  async function savePhone() {
    const cleaned = phoneText.trim();
    try {
      await api.patch(`/users/${user?._id}`, { phone: cleaned });
      setUser({ ...user, phone: cleaned } as any);
      setEditingPhone(false);
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to save phone number.');
    }
  }

  async function saveEmail() {
    const cleaned = emailText.trim().toLowerCase();
    if (!cleaned.includes('@')) { showSimpleAlert('Error', 'Please enter a valid email address.'); return; }
    try {
      await api.patch(`/users/${user?._id}`, { email: cleaned });
      setUser({ ...user, email: cleaned } as any);
      setEditingEmail(false);
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to save email.');
    }
  }

  // ── Cover photo — works on web AND mobile ────────────────────────────────
  // IMPORTANT: On iOS Safari, file pickers MUST be triggered synchronously from
  // the user gesture. Any `await` before input.click() breaks it silently.
  // Keep the trigger sync — do all async work inside the onChange callback.
  function handleCoverPick() {
    if (Platform.OS === 'web') {
      // Create, append, and click synchronously within the gesture handler
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.style.position = 'fixed';
      input.style.top = '-9999px';
      input.style.left = '-9999px';
      input.style.opacity = '0';
      document.body.appendChild(input);

      input.onchange = async (e: any) => {
        const file = e.target.files?.[0];
        document.body.removeChild(input);
        if (!file) return;
        setCoverUploading(true);
        try {
          const fd = new FormData();
          fd.append('file', file);
          const res = await api.post(`/profile/${user?._id}/cover`, fd);
          if (res.data?.cover_url) setUser({ ...user, cover_photo_url: res.data.cover_url } as any);
          else showSimpleAlert('Error', 'Upload succeeded but no URL returned.');
        } catch (err: any) {
          const detail = err?.response?.data?.detail;
          const msg = typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
            ? detail.map((d: any) => d.msg || String(d)).join(', ')
            : (err?.message || 'Failed to upload cover photo.');
          showSimpleAlert('Error', msg);
        } finally {
          setCoverUploading(false);
        }
      };

      // Remove on cancel too (no file selected)
      input.addEventListener('cancel', () => {
        try { document.body.removeChild(input); } catch {}
      });

      // Click synchronously — no await before this line
      input.click();
      } else {
      // Native: async is fine since ImagePicker handles its own gesture
      (async () => {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
          showSimpleAlert('Permission Required', 'Allow photo library access to set a cover photo.');
          return;
        }
        const result = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          allowsEditing: true,
          aspect: [16, 9],
          quality: 0.8,
        });
        if (!result.canceled && result.assets?.[0]) {
          setCoverUploading(true);
          try {
            const asset = result.assets[0];
            // Use mimeType if available (handles HEIC correctly); fallback to extension
            const mimeType = (asset as any).mimeType || '';
            const ext = mimeType === 'image/heic' || mimeType === 'image/heif'
              ? 'jpg'
              : (asset.uri.split('.').pop()?.toLowerCase() || 'jpg');
            const fileType = mimeType && !mimeType.includes('heic') && !mimeType.includes('heif')
              ? mimeType
              : `image/${ext === 'jpg' ? 'jpeg' : ext}`;
            const fd = new FormData();
            fd.append('file', { uri: asset.uri, name: `cover.${ext}`, type: fileType } as any);
            const res = await api.post(`/profile/${user?._id}/cover`, fd);
            if (res.data?.cover_url) setUser({ ...user, cover_photo_url: res.data.cover_url } as any);
          } catch (err: any) {
            const detail = err?.response?.data?.detail;
            const msg = typeof detail === 'string'
              ? detail
              : Array.isArray(detail)
              ? detail.map((d: any) => d.msg || String(d)).join(', ')
              : (err?.message || 'Failed to upload cover photo. Please try a JPEG or PNG file.');
            showSimpleAlert('Error', msg);
          } finally {
            setCoverUploading(false);
          }
        }
      })();
    }
  }

  // ── Social link editing ───────────────────────────────────────────────────
  function openSocialEdit(platformKey: string) {
    const current = socialLinks[platformKey] || '';
    setSocialEditValue(current);
    setEditingSocial(platformKey);
  }

  async function saveSocialLink() {
    if (!editingSocial || !user?._id) return;
    const val = socialEditValue.trim().replace(/^@/, ''); // strip leading @
    const updatedLinks = { ...socialLinks, [editingSocial]: val || null };
    try {
      await api.patch(`/users/${user?._id}`, { social_links: updatedLinks });
      setUser({ ...user, social_links: updatedLinks } as any);
      setEditingSocial(null);
    } catch { showSimpleAlert('Error', 'Failed to save social link.'); }
  }

  // ── Review share handlers ──────────────────────────────────────────────────
  function handleCopyReview() {
    if (!reviewUrl) return;
    if (Platform.OS === 'web' && navigator.clipboard) navigator.clipboard.writeText(reviewUrl);
    setCopiedReview(true);
    setTimeout(() => setCopiedReview(false), 2500);
  }
  function handleShareSMS() {
    const href = `sms:?body=${encodeURIComponent(`Hey! Leave us a review: ${reviewUrl}`)}`;
    Platform.OS === 'web' ? window.open(href, '_self') : Linking.openURL(href);
    setShowShareModal(false);
  }
  function handleShareEmail() {
    const href = `mailto:?subject=We'd love your feedback!&body=${encodeURIComponent(`Hi!\n\nWould you mind leaving us a quick review?\n\n${reviewUrl}\n\nThank you!`)}`;
    Platform.OS === 'web' ? window.open(href, '_self') : Linking.openURL(href);
    setShowShareModal(false);
  }

  const photoUrl = resolveUserPhotoUrlHiRes(user as any);
  const roleLabel = user?.role === 'super_admin' ? 'Super Admin'
    : user?.role === 'org_admin' ? 'Org Admin'
    : user?.role === 'store_manager' ? 'Manager' : null;

  const socialLinks = (user as any)?.persona?.social_links || (user as any)?.social_links || {};

  // ── Presence asset cards ───────────────────────────────────────────────────
  const ASSETS = [
    { id: 'card',     icon: 'card',         color: '#007AFF', label: 'Digital Card',  sub: 'Your business card',  url: user?._id ? `${PROD_BASE}/card/${user._id}` : null,         route: '/settings/store-profile' },
    { id: 'showcase', icon: 'images',        color: '#34C759', label: 'Showcase',       sub: 'Happy customers',     url: user?._id ? `${PROD_BASE}/showcase/${user._id}` : null,     route: '/showroom-manage' },
    { id: 'review',   icon: 'star',          color: '#FFD60A', label: 'Review Link',    sub: 'Collect reviews',     url: reviewUrl || null,                                           route: '/settings/review-links' },
    { id: 'linkpage', icon: 'link',          color: '#C9A962', label: 'Link Page',      sub: 'All your links',      url: user?._id ? `${PROD_BASE}/l/${user._id}` : null,            route: '/settings/link-page' },
    { id: 'landing',  icon: 'globe-outline', color: '#AF52DE', label: 'Landing Page',   sub: 'Full profile page',   url: user?._id ? `${PROD_BASE}/p/${user._id}` : null,            route: '/settings/store-profile' },
    { id: 'brand',    icon: 'color-palette', color: '#C9A962', label: 'Brand Kit',      sub: 'Colors & theme',      url: null,                                                        route: '/settings/brand-kit' },
  ] as const;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header nav */}
      <View style={s.nav}>
        <TouchableOpacity onPress={() => router.back()} style={s.navBtn} testID="back-button">
          <Ionicons name="chevron-back" size={26} color="#007AFF" />
        </TouchableOpacity>
        <Text style={s.navTitle}>My Presence</Text>
        <TouchableOpacity onPress={() => router.push('/settings/persona' as any)} style={s.navBtn} testID="edit-profile-btn">
          <Text style={s.navAction}>Edit</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 48 }} showsVerticalScrollIndicator={false}>

        {/* ── Cover Photo + Avatar ─────────────────────────────────────────── */}
        <View style={s.coverBlock}>
          {/* Cover photo — entire area is tappable to change */}
          <TouchableOpacity
            onPress={handleCoverPick}
            disabled={coverUploading}
            activeOpacity={0.85}
            style={s.coverTouch}
            testID="cover-photo-btn"
          >
            {coverPhotoUrl ? (
              <Image source={{ uri: resolvePhotoUrl(coverPhotoUrl) || '' }} style={s.cover} contentFit="cover" placeholder={null} />
            ) : (
              <LinearGradient
                colors={['#1a1200', '#2c1f00', '#3d2c00', '#C9A96230']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={s.cover}
              />
            )}
            {/* Dark bottom gradient for readability */}
            <LinearGradient
              colors={['transparent', 'rgba(0,0,0,0.7)']}
              style={s.coverGrad}
            />
            {/* Camera overlay — visible indicator the whole area is tappable */}
            <View style={s.coverEditBtn} pointerEvents="none">
              {coverUploading ? (
                <ActivityIndicator size="small" color="#C9A962" />
              ) : (
                <>
                  <Ionicons name="camera-outline" size={16} color="#C9A962" />
                  <Text style={s.coverEditBtnText}>
                    {coverPhotoUrl ? 'Change Cover' : 'Add Cover Photo'}
                  </Text>
                </>
              )}
            </View>
          </TouchableOpacity>

          {/* Avatar + completeness ring */}
          <View style={s.avatarArea}>
            <View style={s.avatarOuter}>
              {user && (
                <ProfilePhotoUpload
                  user={user as any}
                  colors={{ ...colors }}
                  onPhotoUpdated={(url) => {
                    // Clear old cached thumbnail paths so new photo shows immediately
                    setUser({ ...user, photo_url: url, photo_path: null, photo_thumb_path: null, photo_avatar_path: null } as any);
                    refreshUserData();
                  }}
                />
              )}
            </View>
            {/* Personal / Store toggle */}
            {isManager && user?.store_id && (
              <View style={s.toggle}>
                {(['personal', 'store'] as const).map((mode) => (
                  <TouchableOpacity
                    key={mode}
                    style={[s.toggleBtn, viewMode === mode && { backgroundColor: mode === 'store' ? '#34C759' : '#007AFF' }]}
                    onPress={() => setViewMode(mode)}
                    testID={`toggle-${mode}`}
                  >
                    <Ionicons name={mode === 'personal' ? 'person' : 'storefront'} size={14}
                      color={viewMode === mode ? colors.text : colors.textSecondary} />
                    <Text style={[s.toggleTxt, viewMode === mode && { color: colors.text, fontWeight: '700' }]}>
                      {mode === 'personal' ? 'Personal' : (storeName || 'Store')}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
        </View>

        {/* ── Identity Block ─────────────────────────────────────────────────── */}
        <View style={s.identity}>
          {/* Name */}
          {editingName ? (
            <View style={s.inlineEditRow}>
              <TextInput
                style={[s.nameInput, { color: colors.text }]}
                value={nameText}
                onChangeText={setNameText}
                autoFocus
                returnKeyType="done"
                onSubmitEditing={saveName}
                onBlur={saveName}
                testID="name-input"
              />
              <TouchableOpacity onPress={saveName} style={s.inlineEditDone}>
                <Ionicons name="checkmark" size={20} color="#34C759" />
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity style={s.nameRow} onPress={() => setEditingName(true)} testID="name-tap">
              <Text style={s.nameText}>{user?.name || 'Your Name'}</Text>
              <Ionicons name="pencil" size={14} color="#8E8E93" style={{ marginLeft: 6, marginTop: 3 }} />
            </TouchableOpacity>
          )}

          {/* Title / tagline */}
          {editingTitle ? (
            <TextInput
              style={[s.titleInput, { color: colors.textSecondary }]}
              value={titleText}
              onChangeText={setTitleText}
              placeholder="Your title or tagline..."
              placeholderTextColor="#38383A"
              autoFocus
              returnKeyType="done"
              onSubmitEditing={saveTitle}
              onBlur={saveTitle}
              testID="title-input"
            />
          ) : (
            <TouchableOpacity onPress={() => setEditingTitle(true)} testID="title-tap">
              <Text style={s.titleText}>
                {(user as any)?.persona?.title || (user as any)?.title || 'Add your title or tagline...'}
              </Text>
            </TouchableOpacity>
          )}

          {/* Role badge — userSelect:none prevents iOS text selection when cover is tapped */}
          {roleLabel && (
            <View style={[s.roleBadge, { backgroundColor: user?.role === 'super_admin' ? '#FF3B3020' : '#C9A96220' }]}>
              <Ionicons name="shield-checkmark" size={13}
                color={user?.role === 'super_admin' ? '#FF3B30' : '#C9A962'} />
              <Text style={[s.roleTxt, { color: user?.role === 'super_admin' ? '#FF3B30' : '#C9A962' }, { userSelect: 'none' } as any]}>
                {roleLabel}
              </Text>
            </View>
          )}

          {/* Email — tap to edit */}
          {editingEmail ? (
            <View style={s.inlineEditRow}>
              <TextInput
                style={[s.titleInput, { color: colors.text, flex: 1, borderBottomWidth: 1, borderBottomColor: '#C9A962' }]}
                value={emailText}
                onChangeText={setEmailText}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                autoFocus
                returnKeyType="done"
                onSubmitEditing={saveEmail}
                onBlur={saveEmail}
                placeholder="your@email.com"
                placeholderTextColor={colors.textTertiary}
              />
              <TouchableOpacity onPress={saveEmail} style={s.inlineEditDone}>
                <Ionicons name="checkmark-circle" size={22} color="#34C759" />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => { setEditingEmail(false); setEmailText(user?.email || ''); }} style={s.inlineEditDone}>
                <Ionicons name="close-circle" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity onPress={() => setEditingEmail(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <Text style={[s.emailText, { marginBottom: 0, userSelect: 'none' } as any]}>{user?.email || 'Tap to add email'}</Text>
              <Ionicons name="pencil-outline" size={13} color={colors.textTertiary} />
            </TouchableOpacity>
          )}

          {/* Phone — tap to edit */}
          {editingPhone ? (
            <View style={s.inlineEditRow}>
              <TextInput
                style={[s.titleInput, { color: colors.text, flex: 1, borderBottomWidth: 1, borderBottomColor: '#C9A962' }]}
                value={phoneText}
                onChangeText={setPhoneText}
                keyboardType="phone-pad"
                autoFocus
                returnKeyType="done"
                onSubmitEditing={savePhone}
                onBlur={savePhone}
                placeholder="(801) 555-1234"
                placeholderTextColor={colors.textTertiary}
              />
              <TouchableOpacity onPress={savePhone} style={s.inlineEditDone}>
                <Ionicons name="checkmark-circle" size={22} color="#34C759" />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => { setEditingPhone(false); setPhoneText((user as any)?.phone || ''); }} style={s.inlineEditDone}>
                <Ionicons name="close-circle" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity onPress={() => setEditingPhone(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 14 }}>
              <Ionicons name="call-outline" size={14} color={colors.textTertiary} />
              <Text style={[s.emailText, { marginBottom: 0, userSelect: 'none' } as any]}>
                {(user as any)?.phone || 'Tap to add phone number'}
              </Text>
              <Ionicons name="pencil-outline" size={13} color={colors.textTertiary} />
            </TouchableOpacity>
          )}

          {/* ── Profile completeness ── */}
          <View style={s.completenessBar}>
            <View style={s.completenessTrack}>
              <View style={[s.completenessFill, {
                width: `${completeness}%` as any,
                backgroundColor: completeness >= 80 ? '#34C759' : completeness >= 50 ? '#C9A962' : '#FF453A',
              }]} />
            </View>
            <Text style={s.completenessText}>{completeness}% complete</Text>
          </View>

          {/* ── Bio ── */}
          <View style={s.bioBlock}>
            {editingBio ? (
              <View>
                <TextInput
                  ref={bioInputRef}
                  style={[s.bioInput, { color: colors.text }]}
                  value={bioText}
                  onChangeText={setBioText}
                  multiline
                  maxLength={300}
                  placeholder="Write something about yourself..."
                  placeholderTextColor="#38383A"
                  autoFocus
                  testID="bio-input"
                />
                <View style={s.bioActions}>
                  <Text style={s.bioCount}>{bioText.length}/300</Text>
                  <TouchableOpacity onPress={() => { setEditingBio(false); setBioText((user as any)?.persona?.bio || (user as any)?.bio || ''); }}>
                    <Text style={s.bioCancel}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={saveBio} style={s.bioSaveBtn} disabled={savingBio} testID="bio-save-btn">
                    {savingBio
                      ? <ActivityIndicator size="small" color="#000" />
                      : <Text style={s.bioSaveText}>Save</Text>
                    }
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <TouchableOpacity onPress={() => setEditingBio(true)} testID="bio-tap">
                {bioText ? (
                  <Text style={s.bioText}>{bioText}</Text>
                ) : (
                  <View style={s.bioEmpty}>
                    <Ionicons name="add-circle-outline" size={18} color="#C9A962" />
                    <Text style={s.bioEmptyText}>Add your bio</Text>
                  </View>
                )}
              </TouchableOpacity>
            )}
          </View>

          {/* ── Social link chips ── */}
          <View style={s.socialChips}>
            {SOCIAL_PLATFORMS.map((p) => {
              const val = socialLinks[p.key];
              return (
                <TouchableOpacity
                  key={p.key}
                  style={[s.socialChip, val && { borderColor: p.color + '60', backgroundColor: p.color + '15' }]}
                  onPress={() => openSocialEdit(p.key)}
                  testID={`social-chip-${p.key}`}
                >
                  <Ionicons name={p.icon as any} size={16} color={val ? p.color : '#8E8E93'} />
                  {val
                    ? <Text style={[s.socialChipText, { color: p.color }]} numberOfLines={1}>@{val.replace(/^@/, '')}</Text>
                    : <Text style={[s.socialChipText, { color: '#555' }]}>{p.label}</Text>
                  }
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* ── Personal View ─────────────────────────────────────────────────── */}
        {viewMode === 'personal' && (
          <>
            {/* ── Presence Assets 2-col grid ── */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>My Presence</Text>
              <Text style={s.sectionSub}>Tap any card to manage or share</Text>
              <View style={s.assetGrid}>
                {ASSETS.map((asset) => (
                  <TouchableOpacity
                    key={asset.id}
                    style={s.assetCard}
                    activeOpacity={0.8}
                    onPress={() => router.push(asset.route as any)}
                    testID={`asset-card-${asset.id}`}
                  >
                    {/* Mini preview area */}
                    <View style={[s.assetPreview, { backgroundColor: asset.color + '12', borderColor: asset.color + '30' }]}>
                      <Ionicons name={asset.icon as any} size={28} color={asset.color} />
                      {asset.url && (
                        <TouchableOpacity
                          style={s.assetPreviewLink}
                          onPress={() => Platform.OS === 'web' && asset.url && window.open(asset.url, '_blank')}
                          testID={`asset-preview-${asset.id}`}
                        >
                          <Ionicons name="eye-outline" size={13} color={asset.color} />
                        </TouchableOpacity>
                      )}
                    </View>
                    {/* Info row */}
                    <View style={s.assetInfo}>
                      <Text style={s.assetLabel}>{asset.label}</Text>
                      <Text style={s.assetSub}>{asset.sub}</Text>
                    </View>
                    {/* Actions row */}
                    <View style={s.assetActions}>
                      <TouchableOpacity
                        style={[s.assetActionBtn, { backgroundColor: asset.color + '20' }]}
                        onPress={() => router.push(asset.route as any)}
                      >
                        <Ionicons name="create-outline" size={13} color={asset.color} />
                        <Text style={[s.assetActionTxt, { color: asset.color }]}>Edit</Text>
                      </TouchableOpacity>
                      {asset.url && (
                        <TouchableOpacity
                          style={[s.assetActionBtn, { backgroundColor: colors.borderLight }]}
                          onPress={() => {
                            if (Platform.OS === 'web' && navigator.clipboard && asset.url) {
                              navigator.clipboard.writeText(asset.url);
                            }
                          }}
                        >
                          <Ionicons name="copy-outline" size={13} color="#8E8E93" />
                          <Text style={[s.assetActionTxt, { color: colors.textSecondary }]}>Copy</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* ── Photo Gallery ── */}
            {user?._id && (
              <ProfileGallery
                userId={user._id}
                colors={colors}
                onSetProfilePhoto={(url) => {
                    setUser({ ...user, photo_url: url, photo_path: null, photo_thumb_path: null, photo_avatar_path: null } as any);
                    refreshUserData();
                }}
              />
            )}

            {/* ── Address (collapsible) ── */}
            <View style={s.section}>
              <TouchableOpacity style={s.collapseHeader} onPress={() => setAddressOpen(!addressOpen)} testID="address-toggle">
                <Ionicons name="location-outline" size={18} color="#C9A962" />
                <Text style={s.collapseTitle}>My Address</Text>
                <Ionicons name={addressOpen ? 'chevron-up' : 'chevron-down'} size={18} color="#8E8E93" style={{ marginLeft: 'auto' }} />
              </TouchableOpacity>
              {addressOpen && (
                <View style={[s.collapseBody, { borderLeftColor: '#C9A96240' }]}>
                  {[
                    { field: 'address', placeholder: 'Street Address' },
                    { field: 'city', placeholder: 'City' },
                  ].map(({ field, placeholder }) => (
                    <TextInput
                      key={field}
                      style={s.addrInput}
                      value={(user as any)?.[field] || ''}
                      onChangeText={(t) => updateUser({ [field]: t } as any)}
                      onBlur={() => { if (user?._id) api.patch(`/auth/users/${user._id}`, { [field]: (user as any)?.[field] || '' }); }}
                      placeholder={placeholder}
                      placeholderTextColor="#38383A"
                      testID={`addr-${field}`}
                    />
                  ))}
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {[
                      { field: 'state', placeholder: 'ST', flex: 0, width: 60 },
                      { field: 'zip_code', placeholder: 'ZIP', flex: 1, kb: 'number-pad' as const },
                    ].map(({ field, placeholder, flex, width, kb }: any) => (
                      <TextInput
                        key={field}
                        style={[s.addrInput, { flex: flex || undefined, width: width || undefined }]}
                        value={(user as any)?.[field] || ''}
                        onChangeText={(t) => updateUser({ [field]: t } as any)}
                        onBlur={() => { if (user?._id) api.patch(`/auth/users/${user._id}`, { [field]: (user as any)?.[field] || '' }); }}
                        placeholder={placeholder}
                        placeholderTextColor="#38383A"
                        keyboardType={kb}
                        testID={`addr-${field}`}
                      />
                    ))}
                  </View>
                </View>
              )}
            </View>
          </>
        )}

        {/* ── Store View ── */}
        {viewMode === 'store' && isManager && user?.store_id && (
          <StoreManagement user={user} colors={colors} storeSlug={storeSlug} storeName={storeName} />
        )}

        {/* ── Personal Settings ── */}
        <View style={s.section}>
          <Text style={s.sectionTitle}>Settings</Text>
          <View style={s.settingsList}>
            {[
              { icon: 'shield-checkmark', label: 'Security', sub: 'Password & Face ID', color: '#FF453A', route: '/settings/security' },
              { icon: 'calendar', label: 'Calendar', sub: 'Google Calendar sync', color: '#007AFF', route: '/settings/calendar' },
              { icon: 'mic', label: 'Voice Training', sub: 'Train AI with your voice', color: '#FF3B30', route: '/voice-training' },
              { icon: 'download-outline', label: 'Install App', sub: 'Add to home screen', color: '#34C759', action: 'install' },
            ].map((item, i, arr) => (
              <TouchableOpacity
                key={item.label}
                style={[s.settingsRow, i === arr.length - 1 && { borderBottomWidth: 0 }]}
                onPress={() => {
                  if ((item as any).action === 'install') {
                    Platform.OS === 'web' ? window.open('/install.html', '_self') : Linking.openURL('https://app.imonsocial.com/install.html');
                  } else { router.push((item as any).route as any); }
                }}
                testID={`settings-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <View style={[s.settingsIcon, { backgroundColor: item.color + '20' }]}>
                  <Ionicons name={item.icon as any} size={20} color={item.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.settingsLabel}>{item.label}</Text>
                  <Text style={s.settingsSub}>{item.sub}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#38383A" />
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* ── Account Info ── */}
        <AccountInfoCard user={user} colors={colors} />

        {/* ── Sign Out ── */}
        <View style={{ paddingHorizontal: 16, marginTop: 24, marginBottom: 8 }}>
          <TouchableOpacity
            style={[s.settingsList, { backgroundColor: '#FF3B3010', borderWidth: 1, borderColor: '#FF3B3025' }]}
            onPress={async () => {
              const authStore = await import('../store/authStore');
              await authStore.useAuthStore.getState().logout();
              router.replace('/auth/login' as any);
            }}
            testID="logout-btn"
          >
            <View style={[s.settingsRow, { borderBottomWidth: 0 }]}>
              <View style={[s.settingsIcon, { backgroundColor: '#FF3B3020' }]}>
                <Ionicons name="log-out-outline" size={20} color="#FF3B30" />
              </View>
              <Text style={[s.settingsLabel, { color: '#FF3B30' }]}>Sign Out</Text>
            </View>
          </TouchableOpacity>
        </View>

        <View style={{ height: 32 }} />
      </ScrollView>

      {/* Social Link Edit Modal */}
      {editingSocial && (() => {
        const platform = SOCIAL_PLATFORMS.find(p => p.key === editingSocial);
        return (
          <View style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' }}>
            <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 36 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                {platform && <Ionicons name={platform.icon as any} size={24} color={platform?.color} />}
                <Text style={{ fontSize: 20, fontWeight: '700', color: colors.text, flex: 1 }}>{platform?.label}</Text>
                <TouchableOpacity onPress={() => setEditingSocial(null)}>
                  <Ionicons name="close" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
              <Text style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 8 }}>Your handle or username</Text>
              <TextInput
                style={{ backgroundColor: colors.surface, color: colors.text, borderRadius: 12, padding: 14, fontSize: 17, borderWidth: 1, borderColor: platform?.color + '40' }}
                value={socialEditValue}
                onChangeText={setSocialEditValue}
                placeholder={`@yourhandle`}
                placeholderTextColor={colors.textTertiary}
                autoFocus
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="done"
                onSubmitEditing={saveSocialLink}
                testID={`social-edit-${editingSocial}`}
              />
              {socialEditValue.trim() !== '' && (
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 6 }}>
                  Will show as: @{socialEditValue.trim().replace(/^@/, '')}
                </Text>
              )}
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 18 }}>
                {socialLinks[editingSocial] && (
                  <TouchableOpacity
                    style={{ flex: 1, paddingVertical: 13, borderRadius: 12, backgroundColor: '#FF3B3020', alignItems: 'center', borderWidth: 1, borderColor: '#FF3B3030' }}
                    onPress={() => { setSocialEditValue(''); saveSocialLink(); }}
                  >
                    <Text style={{ color: '#FF3B30', fontWeight: '600', fontSize: 16 }}>Remove</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity
                  style={{ flex: 2, paddingVertical: 13, borderRadius: 12, backgroundColor: platform?.color || '#C9A962', alignItems: 'center' }}
                  onPress={saveSocialLink}
                  testID="social-save-btn"
                >
                  <Text style={{ color: '#FFF', fontWeight: '700', fontSize: 16 }}>Save</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        );
      })()}

      {/* Share Review Modal */}
      <ShareReviewModal
        visible={showShareModal}
        onClose={() => setShowShareModal(false)}
        colors={colors}
        reviewUrl={reviewUrl}
        copiedLink={copiedReview}
        onCopyLink={handleCopyReview}
        onShareSMS={handleShareSMS}
        onShareEmail={handleShareEmail}
        onPreview={() => { router.push(`/review/${storeSlug || 'my-store'}` as any); setShowShareModal(false); }}
      />
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },

  // Nav
  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 10 },
  navBtn: { padding: 4, minWidth: 48 },
  navTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
  navAction: { fontSize: 17, color: '#C9A962', fontWeight: '600' },

  // Cover
  coverBlock: { position: 'relative', marginBottom: 0 },
  coverTouch: { width: '100%', height: 160, position: 'relative' },
  cover: { width: '100%', height: 160 },
  coverGrad: { position: 'absolute', bottom: 0, left: 0, right: 0, height: 80 },
  coverEditBtn: {
    position: 'absolute', bottom: 12, right: 14,
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(0,0,0,0.65)',
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1, borderColor: '#C9A96260',
  },
  coverEditBtnText: { fontSize: 14, color: '#C9A962', fontWeight: '700' },
  avatarArea: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', paddingHorizontal: 16, marginTop: -48 },
  avatarOuter: { position: 'relative' },
  completenessRing: { position: 'absolute', top: -6, left: -6, right: -6, bottom: -6, borderRadius: 999, borderWidth: 2, pointerEvents: 'none' },

  // Toggle
  toggle: { flexDirection: 'row', backgroundColor: colors.card, borderRadius: 20, padding: 3, gap: 2, marginBottom: 8 },
  toggleBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16 },
  toggleTxt: { fontSize: 13, color: colors.textSecondary, fontWeight: '500' },

  // Identity
  identity: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 },
  nameRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  nameText: { fontSize: 26, fontWeight: '700', color: colors.text, letterSpacing: 0.3 },
  nameInput: { fontSize: 26, fontWeight: '700', flex: 1, paddingVertical: 0, paddingHorizontal: 0 },
  inlineEditRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  inlineEditDone: { padding: 4 },
  titleText: { fontSize: 15, color: colors.textSecondary, marginBottom: 8 },
  titleInput: { fontSize: 15, paddingVertical: 4, paddingHorizontal: 0, marginBottom: 8 },
  roleBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, marginBottom: 6 },
  roleTxt: { fontSize: 13, fontWeight: '600' },
  emailText: { fontSize: 14, color: colors.textSecondary, marginBottom: 14 },

  // Completeness
  completenessBar: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 16 },
  completenessTrack: { flex: 1, height: 4, backgroundColor: colors.borderLight, borderRadius: 2, overflow: 'hidden' },
  completenessFill: { height: 4, borderRadius: 2 },
  completenessText: { fontSize: 12, color: colors.textSecondary, fontWeight: '600' },

  // Bio
  bioBlock: { marginBottom: 16 },
  bioText: { fontSize: 15, color: colors.text, lineHeight: 21, opacity: 0.85 },
  bioEmpty: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  bioEmptyText: { fontSize: 15, color: '#C9A962', fontWeight: '500' },
  bioInput: { fontSize: 15, lineHeight: 21, paddingVertical: 8, paddingHorizontal: 12, backgroundColor: colors.card, borderRadius: 10, borderWidth: 1, borderColor: colors.borderLight, minHeight: 80, textAlignVertical: 'top', color: colors.text },
  bioActions: { flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 10, marginTop: 8 },
  bioCount: { fontSize: 12, color: colors.textSecondary, flex: 1 },
  bioCancel: { fontSize: 15, color: colors.textSecondary },
  bioSaveBtn: { backgroundColor: '#C9A962', paddingHorizontal: 18, paddingVertical: 7, borderRadius: 16 },
  bioSaveText: { fontSize: 15, fontWeight: '700', color: '#000' },

  // Social chips
  socialChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  socialChip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.borderLight },
  socialChipText: { fontSize: 13, fontWeight: '600', maxWidth: 80 },

  // Sections
  section: { marginTop: 28, paddingHorizontal: 16 },
  sectionTitle: { fontSize: 20, fontWeight: '700', color: colors.text, marginBottom: 2 },
  sectionSub: { fontSize: 13, color: colors.textSecondary, marginBottom: 14 },

  // Asset cards 2-col grid
  assetGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  assetCard: { width: '47.5%', backgroundColor: colors.card, borderRadius: 16, overflow: 'hidden', borderWidth: 1, borderColor: colors.borderLight },
  assetPreview: { height: 88, alignItems: 'center', justifyContent: 'center', position: 'relative', borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  assetPreviewLink: { position: 'absolute', top: 8, right: 8, backgroundColor: 'rgba(0,0,0,0.4)', borderRadius: 12, padding: 4 },
  assetInfo: { paddingHorizontal: 12, paddingTop: 10, paddingBottom: 6 },
  assetLabel: { fontSize: 14, fontWeight: '700', color: colors.text, marginBottom: 2 },
  assetSub: { fontSize: 12, color: colors.textSecondary },
  assetActions: { flexDirection: 'row', gap: 6, paddingHorizontal: 10, paddingBottom: 10 },
  assetActionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 3, paddingVertical: 6, borderRadius: 8 },
  assetActionTxt: { fontSize: 12, fontWeight: '600' },

  // Address
  collapseHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 14, paddingHorizontal: 16, backgroundColor: colors.card, borderRadius: 12 },
  collapseTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  collapseBody: { borderLeftWidth: 2, marginLeft: 16, paddingLeft: 16, paddingTop: 12, gap: 10 },
  addrInput: { backgroundColor: colors.card, color: colors.text, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, borderWidth: 1, borderColor: colors.borderLight, marginBottom: 8 },

  // Settings list
  settingsList: { backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden' },
  settingsRow: { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12, borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  settingsIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  settingsLabel: { fontSize: 16, fontWeight: '600', color: colors.text, marginBottom: 2 },
  settingsSub: { fontSize: 13, color: colors.textSecondary },
});
