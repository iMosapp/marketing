/**
 * my-account.tsx — My Presence screen.
 *
 * This file is the coordinator: state management + layout.
 * All heavy UI is in focused sub-components under components/account/.
 *
 * Sub-components:
 *   ProfilePhotoUpload   — profile photo upload/remove
 *   PresenceLinks        — digital card, showcase, review link, link page, etc.
 *   StoreManagement      — store presence & settings (managers only)
 *   ShareReviewModal     — share review link via SMS/email/copy
 *   AccountInfoCard      — read-only phone/org/store info
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  Platform, Linking, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { showSimpleAlert } from '../services/alert';
import api from '../services/api';

// Sub-components
import { ProfilePhotoUpload } from '../components/account/ProfilePhotoUpload';
import { PresenceLinks } from '../components/account/PresenceLinks';
import { StoreManagement } from '../components/account/StoreManagement';
import { ShareReviewModal } from '../components/account/ShareReviewModal';
import { AccountInfoCard } from '../components/account/AccountInfoCard';
import { ProfileGallery } from '../components/account/ProfileGallery';

const PROD_BASE = 'https://app.imonsocial.com';

export default function MyAccountScreen() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const router = useRouter();
  const { user, setUser, updateUser } = useAuthStore();

  // ── State ───────────────────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<'personal' | 'store'>('personal');
  const [storeSlug, setStoreSlug] = useState<string | null>(user?.store_slug || null);
  const [storeName, setStoreName] = useState<string | null>(user?.store_name || null);
  const [showShareModal, setShowShareModal] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [toolsExpanded, setToolsExpanded] = useState(false);

  const isManager = !!user?.role && ['super_admin', 'org_admin', 'store_manager'].includes(user.role);

  const reviewUrl = storeSlug
    ? `${PROD_BASE}/review/${storeSlug}${user?._id ? `?sp=${user._id}` : ''}`
    : '';

  const ALL_TOOLS = [
    { icon: 'paper-plane', label: 'Send Card', color: '#32ADE6', route: '/settings/create-card' },
    { icon: 'sparkles', label: 'Ask Jessi', color: '#C9A962', route: '/jessie' },
    { icon: 'bar-chart', label: 'My Activity', color: '#5AC8FA', route: '/reports/activity' },
    { icon: 'checkmark-done', label: 'Tasks', color: '#34C759', route: '/tasks' },
    { icon: 'stats-chart', label: 'Analytics', color: '#34C759', route: '/analytics' },
    { icon: 'document-text', label: 'Templates', color: '#FFD60A', route: '/settings/templates' },
    { icon: 'trophy', label: 'Leaderboard', color: '#FFD700', route: '/admin/leaderboard' },
    { icon: 'school', label: 'Training Hub', color: '#FF9500', route: '/training-hub' },
    { icon: 'mail', label: 'Email Analytics', color: '#5856D6', route: '/settings/email-analytics' },
    { icon: 'calendar', label: 'Date Triggers', color: '#FF3B30', route: '/settings/date-triggers' },
    { icon: 'link', label: 'Edit Link Page', color: '#C9A962', route: '/settings/link-page' },
  ];

  // ── Data loading ─────────────────────────────────────────────────────────
  useFocusEffect(
    useCallback(() => {
      if (user?._id) refreshUserData();
      if (user?.store_slug) setStoreSlug(user.store_slug);
      else if (user?.store_id) fetchStoreSlug();
    }, [user?._id, user?.store_slug, user?.store_id]),
  );

  async function fetchStoreSlug() {
    try {
      const res = await api.get(`/admin/stores/${user?.store_id}`, { headers: { 'X-User-ID': user?._id } });
      const slug = res.data?.slug;
      const name = res.data?.name;
      if (name) setStoreName(name);
      if (slug) setStoreSlug(slug);
      else if (name) setStoreSlug(name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
    } catch {}
  }

  async function refreshUserData() {
    try {
      const res = await api.get(`/users/${user?._id}`);
      if (res.data) {
        const merged = { ...user, ...res.data };
        setUser(merged);
        try { await AsyncStorage.setItem('user', JSON.stringify(merged)).catch(() => {}); } catch {}
      }
    } catch {}
  }

  // ── Handlers ─────────────────────────────────────────────────────────────
  async function handlePhotoUpdated(newPhotoUrl: string | null) {
    if (!user) return;
    setUser({ ...user, photo_url: newPhotoUrl });
    await refreshUserData();
  }

  function handleCopyReviewLink() {
    if (!reviewUrl) return;
    if (Platform.OS === 'web' && navigator.clipboard) {
      navigator.clipboard.writeText(reviewUrl);
    }
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  }

  function handleShareSMS() {
    const msg = `Hey! We'd love your feedback. Leave us a review here: ${reviewUrl}`;
    const href = `sms:?body=${encodeURIComponent(msg)}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = href; a.target = '_self';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } else { Linking.openURL(href); }
    setShowShareModal(false);
  }

  function handleShareEmail() {
    const subject = "We'd love your feedback!";
    const body = `Hi!\n\nThank you for your business. We'd really appreciate it if you could take a moment to leave us a review:\n\n${reviewUrl}\n\nThank you!`;
    const href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = href; a.target = '_self';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } else { Linking.openURL(href); }
    setShowShareModal(false);
  }

  function handlePreviewReview() {
    router.push(`/review/${storeSlug || 'my-store'}` as any);
    setShowShareModal(false);
  }

  const roleLabel = user?.role === 'super_admin' ? 'Super Admin'
    : user?.role === 'org_admin' ? 'Org Admin'
    : user?.role === 'store_manager' ? 'Manager' : null;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={[s.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="back-button">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.text }]}>My Presence</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView contentContainerStyle={s.scroll}>
        {/* ── Profile Header ── */}
        <View style={[s.photoSection, { borderBottomColor: colors.border }]}>
          {user && (
            <ProfilePhotoUpload user={user as any} colors={colors} onPhotoUpdated={handlePhotoUpdated} />
          )}
          <Text style={[s.userName, { color: colors.text }]}>{user?.name || 'Guest'}</Text>
          <Text style={[s.userEmail, { color: colors.textSecondary }]}>{user?.email || ''}</Text>
          {roleLabel && (
            <View style={s.roleBadge}>
              <Ionicons name="shield-checkmark" size={14} color="#34C759" />
              <Text style={s.roleText}>{roleLabel}</Text>
            </View>
          )}
        </View>

        {/* ── Personal / Store Toggle (managers only) ── */}
        {isManager && user?.store_id && (
          <View style={[s.toggle, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
            {(['personal', 'store'] as const).map((mode) => (
              <TouchableOpacity
                key={mode}
                style={[s.toggleBtn, viewMode === mode && { backgroundColor: mode === 'personal' ? '#007AFF' : '#34C759' }]}
                onPress={() => setViewMode(mode)}
                data-testid={`toggle-${mode}`}
              >
                <Ionicons name={mode === 'personal' ? 'person' : 'storefront'} size={16}
                  color={viewMode === mode ? '#FFF' : colors.textSecondary} />
                <Text style={[s.toggleText, viewMode === mode && { color: '#FFF', fontWeight: '700' }]}>
                  {mode === 'personal' ? 'Personal' : (storeName || user?.store_name || 'Store')}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* ── Personal View ── */}
        {viewMode === 'personal' && (
          <>
            {/* My Profile links */}
            <View style={s.section}>
              <Text style={[s.sectionTitle, { color: colors.textTertiary }]}>My Profile</Text>
              <View style={[s.menuList, { backgroundColor: colors.card }]}>
                {[
                  { icon: 'person', label: 'Edit Profile & Bio', sub: 'Name, bio, photo, social links', color: '#007AFF', route: '/settings/persona' },
                  { icon: 'color-palette', label: 'My Brand Kit', sub: 'Colors, logo, page theme', color: '#C9A962', route: '/settings/brand-kit' },
                  { icon: 'mic', label: 'Voice Training', sub: 'Train AI with your voice', color: '#FF3B30', route: '/voice-training' },
                ].map((item, i, arr) => (
                  <TouchableOpacity
                    key={item.label}
                    style={[s.menuRow, { borderBottomColor: colors.border }, i === arr.length - 1 && s.lastRow]}
                    onPress={() => router.push(item.route as any)}
                    data-testid={`profile-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                  >
                    <View style={[s.menuIcon, { backgroundColor: `${item.color}20` }]}>
                      <Ionicons name={item.icon as any} size={22} color={item.color} />
                    </View>
                    <View style={s.menuContent}>
                      <Text style={[s.menuTitle, { color: colors.text }]}>{item.label}</Text>
                      <Text style={[s.menuSub, { color: colors.textSecondary }]}>{item.sub}</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Address form */}
            <View style={s.section}>
              <Text style={[s.sectionTitle, { color: colors.textTertiary }]}>My Address (Optional)</Text>
              <View style={[s.menuList, { backgroundColor: colors.card, padding: 16 }]}>
                {[
                  { field: 'address', placeholder: 'Street Address', flex: 1 },
                ].map(({ field, placeholder, flex }) => (
                  <TextInput
                    key={field}
                    style={[s.input, { backgroundColor: colors.bg, color: colors.text, flex: flex as any }]}
                    value={(user as any)?.[field] || ''}
                    onChangeText={(t) => updateUser({ [field]: t } as any)}
                    onBlur={() => { if (user?._id) api.patch(`/auth/users/${user._id}`, { [field]: (user as any)?.[field] || '' }); }}
                    placeholder={placeholder}
                    placeholderTextColor={colors.textSecondary}
                  />
                ))}
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  {[
                    { field: 'city', placeholder: 'City', flex: 1 },
                    { field: 'state', placeholder: 'ST', flex: 0, width: 60, caps: 'characters' as const, max: 2 },
                    { field: 'zip_code', placeholder: 'Zip', flex: 0, width: 90, kb: 'number-pad' as const },
                  ].map(({ field, placeholder, flex, width, caps, max, kb }: any) => (
                    <TextInput
                      key={field}
                      style={[s.input, { backgroundColor: colors.bg, color: colors.text, flex: flex || undefined, width: width || undefined }]}
                      value={(user as any)?.[field] || ''}
                      onChangeText={(t) => updateUser({ [field]: t } as any)}
                      onBlur={() => { if (user?._id) api.patch(`/auth/users/${user._id}`, { [field]: (user as any)?.[field] || '' }); }}
                      placeholder={placeholder}
                      placeholderTextColor={colors.textSecondary}
                      autoCapitalize={caps}
                      maxLength={max}
                      keyboardType={kb}
                    />
                  ))}
                </View>
                <TextInput
                  style={[s.input, { backgroundColor: colors.bg, color: colors.text }]}
                  value={(user as any)?.country || 'United States'}
                  onChangeText={(t) => updateUser({ country: t } as any)}
                  onBlur={() => { if (user?._id) api.patch(`/auth/users/${user._id}`, { country: (user as any)?.country || '' }); }}
                  placeholder="Country"
                  placeholderTextColor={colors.textSecondary}
                />
              </View>
            </View>

            {/* My Photo Gallery */}
            {user?._id && (
              <ProfileGallery userId={user._id} colors={colors} />
            )}

            {/* Presence links — Digital Card, Showcase, Review Link, etc. */}
            <PresenceLinks
              user={user}
              colors={colors}
              storeSlug={storeSlug}
              onOpenShareModal={() => setShowShareModal(true)}
              onPreviewReview={handlePreviewReview}
            />
          </>
        )}

        {/* ── Store View ── */}
        {viewMode === 'store' && isManager && user?.store_id && (
          <StoreManagement user={user} colors={colors} storeSlug={storeSlug} storeName={storeName} />
        )}

        {/* ── All Tools (collapsible) ── */}
        <View style={s.section}>
          <TouchableOpacity
            style={[s.menuList, { backgroundColor: colors.card, flexDirection: 'row', alignItems: 'center', padding: 16 }]}
            onPress={() => setToolsExpanded(!toolsExpanded)}
            activeOpacity={0.7}
            data-testid="tools-toggle"
          >
            <View style={[s.menuIcon, { backgroundColor: '#5856D620' }]}>
              <Ionicons name="grid" size={22} color="#5856D6" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[s.menuTitle, { color: colors.text }]}>All Tools & Settings</Text>
              <Text style={[s.menuSub, { color: colors.textSecondary }]}>{ALL_TOOLS.length} tools available</Text>
            </View>
            <Ionicons name={toolsExpanded ? 'chevron-up' : 'chevron-down'} size={20} color={colors.textTertiary} />
          </TouchableOpacity>

          {toolsExpanded && (
            <View style={[s.menuList, { backgroundColor: colors.card, marginTop: 8 }]}>
              {ALL_TOOLS.map((item, i, arr) => (
                <TouchableOpacity
                  key={item.label}
                  style={[s.menuRow, { borderBottomColor: colors.border }, i === arr.length - 1 && s.lastRow]}
                  onPress={() => router.push(item.route as any)}
                  data-testid={`tool-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  <View style={[s.menuIcon, { backgroundColor: `${item.color}20` }]}>
                    <Ionicons name={item.icon as any} size={22} color={item.color} />
                  </View>
                  <View style={s.menuContent}>
                    <Text style={[s.menuTitle, { color: colors.text }]}>{item.label}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>

        {/* ── Personal Settings ── */}
        <View style={s.section}>
          <Text style={[s.sectionTitle, { color: colors.textTertiary }]}>Personal Settings</Text>
          <View style={[s.menuList, { backgroundColor: colors.card }]}>
            {[
              { icon: 'shield-checkmark', label: 'Security', sub: 'Password & Face ID', color: '#FF3B30', route: '/settings/security' },
              { icon: 'calendar', label: 'Calendar', sub: 'Connect Google Calendar', color: '#007AFF', route: '/settings/calendar' },
              { icon: 'download-outline', label: 'Install App', sub: 'Add to home screen', color: '#007AFF', action: 'install' },
            ].map((item, i, arr) => (
              <TouchableOpacity
                key={item.label}
                style={[s.menuRow, { borderBottomColor: colors.border }, i === arr.length - 1 && s.lastRow]}
                onPress={() => {
                  if ((item as any).action === 'install') {
                    if (Platform.OS === 'web') window.open('/install.html', '_self');
                    else Linking.openURL('https://app.imonsocial.com/install.html');
                  } else { router.push((item as any).route as any); }
                }}
                data-testid={`settings-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <View style={[s.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={22} color={item.color} />
                </View>
                <View style={s.menuContent}>
                  <Text style={[s.menuTitle, { color: colors.text }]}>{item.label}</Text>
                  <Text style={[s.menuSub, { color: colors.textSecondary }]}>{item.sub}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* ── Account Info ── */}
        <AccountInfoCard user={user} colors={colors} />

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* ── Share Review Modal ── */}
      <ShareReviewModal
        visible={showShareModal}
        onClose={() => setShowShareModal(false)}
        colors={colors}
        reviewUrl={reviewUrl}
        copiedLink={copiedLink}
        onCopyLink={handleCopyReviewLink}
        onShareSMS={handleShareSMS}
        onShareEmail={handleShareEmail}
        onPreview={handlePreviewReview}
      />
    </SafeAreaView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1 },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 19, fontWeight: '600' },
  scroll: { paddingBottom: 32 },

  // Profile header
  photoSection: { alignItems: 'center', paddingVertical: 24, borderBottomWidth: 1 },
  userName: { fontSize: 24, fontWeight: '700', marginBottom: 4 },
  userEmail: { fontSize: 17, marginBottom: 8 },
  roleBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#34C75920', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 12, marginTop: 4 },
  roleText: { fontSize: 15, fontWeight: '600', color: '#34C759' },

  // Toggle
  toggle: { flexDirection: 'row', padding: 6, marginHorizontal: 16, marginTop: 16, marginBottom: 4, borderRadius: 12, gap: 4 },
  toggleBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 10, borderRadius: 10, gap: 6 },
  toggleText: { fontSize: 16, fontWeight: '500', color: colors.textSecondary },

  // Sections
  section: { marginTop: 24, paddingHorizontal: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },

  // Menu lists
  menuList: { borderRadius: 12, overflow: 'hidden' },
  menuRow: { flexDirection: 'row', alignItems: 'center', padding: 14, borderBottomWidth: 1 },
  lastRow: { borderBottomWidth: 0 },
  menuIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  menuContent: { flex: 1 },
  menuTitle: { fontSize: 17, fontWeight: '600', marginBottom: 2 },
  menuSub: { fontSize: 14 },

  // Address
  input: { borderRadius: 10, padding: 12, fontSize: 16, marginBottom: 10 },
});
