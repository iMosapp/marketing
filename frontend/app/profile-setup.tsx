/**
 * app/profile-setup.tsx — First-time profile setup wizard.
 *
 * Guides new users through 5 steps to complete their profile:
 *   1. Your Photo       → profile + cover photo
 *   2. About You        → name, title, bio (with AI suggestion)
 *   3. Find Me Online   → social handles + website
 *   4. Make It Yours    → card color, dark/light mode
 *   5. All Done!        → assets summary, mark complete
 *
 * After finishing: onboarding_complete = true, navigate to home.
 * All steps save incrementally — closing and reopening is safe.
 */

import React, { useState, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, Platform, Animated,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';
import { resolveUserPhotoUrlHiRes, resolvePhotoUrl } from '../utils/photoUrl';

const TOTAL_STEPS = 5;

const SOCIAL_PLATFORMS = [
  { key: 'instagram', icon: 'logo-instagram', color: '#E1306C', label: 'Instagram',  placeholder: '@yourhandle' },
  { key: 'facebook',  icon: 'logo-facebook',  color: '#1877F2', label: 'Facebook',   placeholder: 'facebook.com/you' },
  { key: 'tiktok',    icon: 'logo-tiktok',    color: '#FFFFFF', label: 'TikTok',     placeholder: '@yourhandle' },
  { key: 'youtube',   icon: 'logo-youtube',   color: '#FF0000', label: 'YouTube',    placeholder: 'youtube.com/@you' },
  { key: 'linkedin',  icon: 'logo-linkedin',  color: '#0A66C2', label: 'LinkedIn',   placeholder: 'linkedin.com/in/you' },
  { key: 'twitter',   icon: 'logo-twitter',   color: '#1DA1F2', label: 'Twitter/X',  placeholder: '@yourhandle' },
];

const COLOR_PALETTE = [
  '#007AFF','#34C759','#FF9500','#FF3B30','#5856D6',
  '#AF52DE','#FF2D55','#00C7BE','#C9A962','#1877F2',
  '#E1306C','#0A66C2','#FF6B35','#00B4D8',
];

const PROD_BASE = 'https://app.imonsocial.com';

export default function ProfileSetupScreen() {
  const router = useRouter();
  const { user, setUser } = useAuthStore();
  const { colors, themeMode, toggle: toggleTheme } = useThemeStore();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [generatingBio, setGeneratingBio] = useState(false);

  // Step 1 — Photos
  const [photoUploading, setPhotoUploading] = useState(false);
  const [coverUploading, setCoverUploading] = useState(false);

  // Step 2 — About You
  const [name, setName]   = useState(user?.name || '');
  const [title, setTitle] = useState((user as any)?.persona?.title || (user as any)?.title || '');
  const [bio, setBio]     = useState((user as any)?.persona?.bio || (user as any)?.bio || '');

  // Step 3 — Social Links
  const socialLinks = (user as any)?.social_links || (user as any)?.persona?.social_links || {};
  const [links, setLinks]     = useState<Record<string, string>>(socialLinks);
  const [website, setWebsite] = useState((user as any)?.persona?.website || '');

  // Step 4 — Style
  const [primaryColor, setPrimaryColor] = useState(
    (user as any)?.brand_kit?.primary_color || '#C9A962'
  );
  const [customHex, setCustomHex] = useState(primaryColor);

  const photoUrl  = resolveUserPhotoUrlHiRes(user as any);
  const coverUrl  = resolvePhotoUrl((user as any)?.cover_photo_url);

  // ── Progress bar ───────────────────────────────────────────────────────────
  const progress = (step / TOTAL_STEPS) * 100;

  // ── Photo helpers ──────────────────────────────────────────────────────────
  async function pickAndUpload(endpoint: string, aspect: [number, number], setLoading: (v: boolean) => void) {
    if (Platform.OS === 'web') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.onchange = async (e: any) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setLoading(true);
        try {
          const fd = new FormData();
          fd.append('file', file);
          const res = await api.post(endpoint, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
          if (res.data?.photo_url) setUser({ ...user, photo_url: res.data.photo_url } as any);
          if (res.data?.cover_url)  setUser({ ...user, cover_photo_url: res.data.cover_url } as any);
        } catch { showSimpleAlert('Error', 'Upload failed. Please try again.'); }
        setLoading(false);
      };
      input.click();
    } else {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') return;
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: true, aspect, quality: 0.85 });
      if (!result.canceled && result.assets?.[0]) {
        setLoading(true);
        try {
          const asset = result.assets[0];
          const ext = asset.uri.split('.').pop() || 'jpg';
          const fd = new FormData();
          fd.append('file', { uri: asset.uri, name: `photo.${ext}`, type: `image/${ext}` } as any);
          const res = await api.post(endpoint, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
          if (res.data?.photo_url) setUser({ ...user, photo_url: res.data.photo_url } as any);
          if (res.data?.cover_url)  setUser({ ...user, cover_photo_url: res.data.cover_url } as any);
        } catch { showSimpleAlert('Error', 'Upload failed. Please try again.'); }
        setLoading(false);
      }
    }
  }

  // ── AI bio suggestion ──────────────────────────────────────────────────────
  async function suggestBio() {
    if (!user?._id) return;
    setGeneratingBio(true);
    try {
      const res = await api.post(`/profile/${user._id}/generate-bio`, {
        name, title,
        specialties: (user as any)?.persona?.specialties || [],
        years_experience: (user as any)?.persona?.years_experience || '',
        hobbies: (user as any)?.persona?.hobbies || [],
      });
      if (res.data?.bio) setBio(res.data.bio);
    } catch { showSimpleAlert('Error', 'Could not generate bio. Try again or write your own!'); }
    setGeneratingBio(false);
  }

  // ── Save each step & advance ───────────────────────────────────────────────
  async function saveAndNext() {
    if (!user?._id) return;
    setSaving(true);
    try {
      if (step === 2) {
        await api.patch(`/users/${user._id}`, { name: name.trim(), persona: { ...(user as any)?.persona, bio, title } });
        setUser({ ...user, name: name.trim(), persona: { ...(user as any)?.persona, bio, title } } as any);
      }
      if (step === 3) {
        const cleanLinks = Object.fromEntries(Object.entries(links).map(([k, v]) => [k, v.trim().replace(/^@/, '')]));
        await api.patch(`/users/${user._id}`, { social_links: cleanLinks, persona: { ...(user as any)?.persona, website } });
        setUser({ ...user, social_links: cleanLinks } as any);
      }
      if (step === 4) {
        await api.patch(`/users/${user._id}`, { brand_kit: { ...(user as any)?.brand_kit, primary_color: primaryColor } });
        setUser({ ...user, brand_kit: { ...(user as any)?.brand_kit, primary_color: primaryColor } } as any);
      }
      if (step === TOTAL_STEPS) {
        // Mark onboarding complete
        await api.patch(`/users/${user._id}`, { onboarding_complete: true });
        setUser({ ...user, onboarding_complete: true } as any);
        router.replace('/(tabs)/home' as any);
        return;
      }
      setStep(s => s + 1);
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to save. Please try again.');
    }
    setSaving(false);
  }

  // ── Step renders ───────────────────────────────────────────────────────────
  const renderStep = () => {
    switch (step) {
      // ── Step 1: Photos ────────────────────────────────────────────────────
      case 1: return (
        <View style={s.stepContent}>
          <Text style={s.stepTitle}>Start with your photos</Text>
          <Text style={s.stepSub}>
            Your profile photo appears everywhere customers see you — your Digital Card, Showcase, and Link Page. A cover photo makes your Hub stand out.
          </Text>

          {/* Profile photo */}
          <View style={s.photoRow}>
            <TouchableOpacity
              style={s.profilePhotoBtn}
              onPress={() => pickAndUpload(`/profile/${user?._id}/photo`, [1, 1], setPhotoUploading)}
              disabled={photoUploading}
              testID="setup-profile-photo"
            >
              {photoUploading ? (
                <ActivityIndicator color="#C9A962" />
              ) : photoUrl ? (
                <Image source={{ uri: photoUrl }} style={s.profilePhotoImg} contentFit="cover" placeholder={null} />
              ) : (
                <View style={s.profilePhotoEmpty}>
                  <Ionicons name="camera-outline" size={32} color="#C9A962" />
                  <Text style={s.profilePhotoEmptyText}>Profile Photo</Text>
                </View>
              )}
              {photoUrl && (
                <View style={s.photoCheckBadge}>
                  <Ionicons name="checkmark-circle" size={24} color="#34C759" />
                </View>
              )}
            </TouchableOpacity>

            <View style={{ flex: 1, gap: 8 }}>
              <Text style={[s.photoLabel, { color: colors.text }]}>Profile Photo</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>
                Square photo. Use a clear headshot — customers need to recognize you instantly.
              </Text>
              <TouchableOpacity
                style={s.changePhotoBtn}
                onPress={() => pickAndUpload(`/profile/${user?._id}/photo`, [1, 1], setPhotoUploading)}
                disabled={photoUploading}
              >
                <Ionicons name="camera-outline" size={16} color="#C9A962" />
                <Text style={s.changePhotoBtnText}>{photoUrl ? 'Change Photo' : 'Upload Photo'}</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Cover photo */}
          <TouchableOpacity
            style={s.coverPhotoBtn}
            onPress={() => pickAndUpload(`/profile/${user?._id}/cover`, [16, 9], setCoverUploading)}
            disabled={coverUploading}
            testID="setup-cover-photo"
          >
            {coverUrl ? (
              <Image source={{ uri: coverUrl }} style={StyleSheet.absoluteFill} contentFit="cover" placeholder={null} />
            ) : (
              <LinearGradient colors={['#1a1200', '#2c1f00', '#3d2c00']} style={StyleSheet.absoluteFill} />
            )}
            <LinearGradient colors={['transparent', 'rgba(0,0,0,0.6)']} style={StyleSheet.absoluteFill} />
            <View style={s.coverOverlay}>
              {coverUploading ? (
                <ActivityIndicator color="#C9A962" />
              ) : (
                <>
                  <Ionicons name={coverUrl ? 'swap-horizontal-outline' : 'image-outline'} size={20} color="#C9A962" />
                  <Text style={s.coverOverlayText}>{coverUrl ? 'Change Cover Photo' : 'Add Cover Photo'}</Text>
                </>
              )}
            </View>
            {coverUrl && <View style={s.coverCheck}><Ionicons name="checkmark-circle" size={22} color="#34C759" /></View>}
          </TouchableOpacity>
          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', marginTop: 6 }}>
            Cover photo appears behind your name on the Hub. 16:9 ratio, landscape.
          </Text>
        </View>
      );

      // ── Step 2: About You ─────────────────────────────────────────────────
      case 2: return (
        <View style={s.stepContent}>
          <Text style={s.stepTitle}>Tell people about yourself</Text>
          <Text style={s.stepSub}>
            This is what customers read on your Digital Card and Landing Page. Be real — write it like you're talking to someone you just met.
          </Text>

          <Text style={s.fieldLabel}>Your Name</Text>
          <TextInput style={[s.input, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]}
            value={name} onChangeText={setName} placeholder="Full name" placeholderTextColor={colors.textSecondary} testID="setup-name" />

          <Text style={s.fieldLabel}>Your Title or Tagline</Text>
          <TextInput style={[s.input, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]}
            value={title} onChangeText={setTitle} placeholder='e.g. "High Tech Redneck" or "Sales Consultant"'
            placeholderTextColor={colors.textSecondary} testID="setup-title" />

          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text style={s.fieldLabel}>Your Bio</Text>
            <TouchableOpacity
              style={s.aiBtn}
              onPress={suggestBio}
              disabled={generatingBio || !name}
              testID="setup-suggest-bio"
            >
              {generatingBio ? (
                <ActivityIndicator size="small" color="#C9A962" />
              ) : (
                <>
                  <Ionicons name="sparkles" size={14} color="#C9A962" />
                  <Text style={s.aiBtnText}>Suggest with AI</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
          <TextInput
            style={[s.input, s.bioInput, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]}
            value={bio}
            onChangeText={setBio}
            placeholder="Write 2-4 sentences about yourself, your experience, and what makes you different. Customers connect with real people."
            placeholderTextColor={colors.textSecondary}
            multiline
            numberOfLines={5}
            testID="setup-bio"
          />
          <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'right', marginTop: 4 }}>{bio.length} / 500</Text>
        </View>
      );

      // ── Step 3: Social Links ──────────────────────────────────────────────
      case 3: return (
        <View style={s.stepContent}>
          <Text style={s.stepTitle}>Where can people find you?</Text>
          <Text style={s.stepSub}>
            Your social links appear on your Digital Card and Link Page. Customers and leads will tap these to follow you. Skip any you don't use.
          </Text>

          {/* Website */}
          <View style={[s.socialRow, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={[s.socialIcon, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="globe-outline" size={20} color="#34C759" />
            </View>
            <TextInput
              style={[s.socialInput, { color: colors.text }]}
              value={website}
              onChangeText={setWebsite}
              placeholder="https://yourwebsite.com"
              placeholderTextColor={colors.textSecondary}
              keyboardType="url"
              autoCapitalize="none"
              autoCorrect={false}
              testID="setup-website"
            />
            {website.trim().length > 0 && <Ionicons name="checkmark-circle" size={18} color="#34C759" />}
          </View>

          {SOCIAL_PLATFORMS.map((p) => (
            <View key={p.key} style={[s.socialRow, { backgroundColor: colors.card, borderColor: links[p.key] ? p.color + '50' : colors.border }]}>
              <View style={[s.socialIcon, { backgroundColor: p.color + '20' }]}>
                <Ionicons name={p.icon as any} size={20} color={p.color} />
              </View>
              <TextInput
                style={[s.socialInput, { color: colors.text }]}
                value={links[p.key] || ''}
                onChangeText={(v) => setLinks(prev => ({ ...prev, [p.key]: v }))}
                placeholder={p.placeholder}
                placeholderTextColor={colors.textSecondary}
                autoCapitalize="none"
                autoCorrect={false}
                testID={`setup-social-${p.key}`}
              />
              {links[p.key]?.trim().length > 0 && <Ionicons name="checkmark-circle" size={18} color={p.color} />}
            </View>
          ))}
        </View>
      );

      // ── Step 4: Make It Yours ─────────────────────────────────────────────
      case 4: return (
        <View style={s.stepContent}>
          <Text style={s.stepTitle}>Make it yours</Text>
          <Text style={s.stepSub}>
            Pick your primary color — it shows up on your Digital Card, Link Page, and all your customer-facing assets. You can always change it later.
          </Text>

          {/* Color preview card */}
          <View style={[s.colorPreviewCard, { backgroundColor: primaryColor + '15', borderColor: primaryColor + '40' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              {photoUrl
                ? <Image source={{ uri: photoUrl }} style={[s.colorPreviewPhoto, { borderColor: primaryColor }]} contentFit="cover" placeholder={null} />
                : <View style={[s.colorPreviewPhoto, { backgroundColor: primaryColor, borderColor: primaryColor }]}><Text style={{ fontSize: 20, fontWeight: '700', color: '#FFF' }}>{name?.[0] || '?'}</Text></View>
              }
              <View>
                <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{name || 'Your Name'}</Text>
                <Text style={{ fontSize: 13, color: primaryColor, fontWeight: '600', marginTop: 2 }}>{title || 'Your Title'}</Text>
                <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                  {[primaryColor, primaryColor + 'AA', primaryColor + '55'].map((c, i) => (
                    <View key={i} style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: c }} />
                  ))}
                </View>
              </View>
            </View>
          </View>

          {/* Color palette */}
          <Text style={[s.fieldLabel, { marginTop: 16 }]}>Card Color</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 }}>
            {COLOR_PALETTE.map((c) => (
              <TouchableOpacity
                key={c}
                onPress={() => { setPrimaryColor(c); setCustomHex(c); }}
                style={[s.colorSwatch, { backgroundColor: c }, primaryColor === c && s.colorSwatchSelected]}
                testID={`color-swatch-${c}`}
              >
                {primaryColor === c && <Ionicons name="checkmark" size={14} color={c === '#FFFFFF' || c === '#FFD60A' ? '#000' : '#FFF'} />}
              </TouchableOpacity>
            ))}
          </View>

          {/* Custom hex */}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 20 }}>
            <TouchableOpacity
              style={[s.colorSwatchLarge, { backgroundColor: /^#[0-9A-Fa-f]{6}$/.test(customHex) ? customHex : '#C9A962' }]}
              onPress={() => {
                if (Platform.OS === 'web') {
                  const inp = document.createElement('input');
                  inp.type = 'color';
                  inp.value = primaryColor;
                  document.body.appendChild(inp);
                  inp.addEventListener('input', (e: any) => { setCustomHex(e.target.value); setPrimaryColor(e.target.value); });
                  inp.addEventListener('change', () => document.body.removeChild(inp));
                  inp.click();
                }
              }}
            >
              <Ionicons name="eyedrop-outline" size={18} color="#fff" />
            </TouchableOpacity>
            <TextInput
              style={[s.input, { flex: 1, color: colors.text, backgroundColor: colors.card, borderColor: colors.border, fontFamily: 'monospace', marginBottom: 0 }]}
              value={customHex}
              onChangeText={(v) => { setCustomHex(v); if (/^#[0-9A-Fa-f]{6}$/.test(v)) setPrimaryColor(v); }}
              placeholder="#C9A962"
              placeholderTextColor={colors.textSecondary}
              autoCapitalize="characters"
              maxLength={7}
              testID="setup-custom-color"
            />
          </View>

          {/* Dark / Light mode */}
          <Text style={s.fieldLabel}>App Appearance</Text>
          <View style={{ flexDirection: 'row', gap: 12 }}>
            {(['dark', 'light'] as const).map((mode) => (
              <TouchableOpacity
                key={mode}
                style={[s.themeOption, { backgroundColor: colors.card, borderColor: themeMode === mode ? primaryColor : colors.border }]}
                onPress={() => { if (themeMode !== mode) toggleTheme(); }}
                testID={`setup-theme-${mode}`}
              >
                <Ionicons
                  name={mode === 'dark' ? 'moon' : 'sunny'}
                  size={22}
                  color={themeMode === mode ? primaryColor : colors.textSecondary}
                />
                <Text style={[s.themeLabel, { color: themeMode === mode ? primaryColor : colors.textSecondary, fontWeight: themeMode === mode ? '700' : '400' }]}>
                  {mode === 'dark' ? 'Dark Mode' : 'Light Mode'}
                </Text>
                {themeMode === mode && <Ionicons name="checkmark-circle" size={18} color={primaryColor} />}
              </TouchableOpacity>
            ))}
          </View>
        </View>
      );

      // ── Step 5: All Done ──────────────────────────────────────────────────
      case 5: return (
        <View style={s.stepContent}>
          <View style={{ alignItems: 'center', marginBottom: 24 }}>
            <View style={[s.doneIcon, { backgroundColor: primaryColor + '20', borderColor: primaryColor + '40' }]}>
              <Ionicons name="checkmark-circle" size={48} color={primaryColor} />
            </View>
            <Text style={[s.stepTitle, { textAlign: 'center', marginTop: 12 }]}>You're all set!</Text>
            <Text style={[s.stepSub, { textAlign: 'center' }]}>
              Your profile is ready. Here's everything that's been built for you — all live and shareable right now.
            </Text>
          </View>

          {[
            { icon: 'card',         color: '#007AFF', label: 'Digital Card',  sub: 'Your personal business card', url: user?._id ? `${PROD_BASE}/card/${user._id}` : null },
            { icon: 'images',       color: '#34C759', label: 'Showcase',      sub: 'Your public portfolio page',  url: user?._id ? `${PROD_BASE}/showcase/${user._id}` : null },
            { icon: 'link',         color: '#C9A962', label: 'Link Page',     sub: 'All your links in one place', url: user?._id ? `${PROD_BASE}/l/${user._id}` : null },
            { icon: 'globe-outline',color: '#AF52DE', label: 'Landing Page',  sub: 'Your personal welcome page',  url: user?._id ? `${PROD_BASE}/p/${user._id}` : null },
          ].map((asset) => (
            <TouchableOpacity
              key={asset.label}
              style={[s.assetRow, { backgroundColor: colors.card, borderColor: asset.color + '30' }]}
              onPress={() => asset.url && Platform.OS === 'web' && window.open(asset.url, '_blank')}
              testID={`asset-preview-${asset.label}`}
            >
              <View style={[s.assetIcon, { backgroundColor: asset.color + '20' }]}>
                <Ionicons name={asset.icon as any} size={22} color={asset.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{asset.label}</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary }}>{asset.sub}</Text>
              </View>
              {asset.url && <Ionicons name="open-outline" size={18} color={colors.textTertiary} />}
            </TouchableOpacity>
          ))}

          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', marginTop: 16, lineHeight: 18 }}>
            You can edit anything — photos, bio, colors, links — anytime from the Hub.
          </Text>
        </View>
      );
    }
  };

  const canAdvance = () => {
    if (step === 1) return !!(photoUrl); // must have a photo
    if (step === 2) return name.trim().length > 0 && bio.trim().length > 20;
    return true;
  };

  const stepLabel = ['', 'Your Photo', 'About You', 'Find Me Online', 'Make It Yours', 'You\'re Done!'][step];

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top', 'bottom']}>
      {/* Header */}
      <View style={s.header}>
        {step > 1 ? (
          <TouchableOpacity onPress={() => setStep(s => s - 1)} style={s.backBtn} testID="setup-back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
        ) : <View style={{ width: 40 }} />}
        <View style={{ alignItems: 'center' }}>
          <Text style={[s.stepCounter, { color: colors.textSecondary }]}>Step {step} of {TOTAL_STEPS}</Text>
          <Text style={[s.stepName, { color: colors.text }]}>{stepLabel}</Text>
        </View>
        <TouchableOpacity
          onPress={() => { setUser({ ...user, onboarding_complete: true } as any); router.replace('/(tabs)/home' as any); }}
          style={s.skipBtn}
          testID="setup-skip"
        >
          <Text style={{ fontSize: 14, color: colors.textSecondary }}>Skip all</Text>
        </TouchableOpacity>
      </View>

      {/* Progress bar */}
      <View style={s.progressTrack}>
        <View style={[s.progressFill, { width: `${progress}%` as any, backgroundColor: '#C9A962' }]} />
      </View>

      {/* Content */}
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
        {renderStep()}
      </ScrollView>

      {/* CTA button */}
      <View style={[s.footer, { borderTopColor: colors.border }]}>
        {step === 1 && !canAdvance() && (
          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', marginBottom: 8 }}>
            Add a profile photo to continue
          </Text>
        )}
        <TouchableOpacity
          style={[s.nextBtn, { backgroundColor: canAdvance() ? '#C9A962' : colors.card, opacity: canAdvance() ? 1 : 0.6 }]}
          onPress={saveAndNext}
          disabled={saving || (step === 1 && !canAdvance()) || (step === 2 && !canAdvance())}
          testID="setup-next"
        >
          {saving ? (
            <ActivityIndicator color="#000" />
          ) : (
            <>
              <Text style={[s.nextBtnText, { color: canAdvance() ? '#000' : colors.textSecondary }]}>
                {step === TOTAL_STEPS ? 'Launch My Profile' : 'Continue'}
              </Text>
              {step !== TOTAL_STEPS && <Ionicons name="arrow-forward" size={18} color={canAdvance() ? '#000' : colors.textSecondary} />}
            </>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  skipBtn: { paddingHorizontal: 8, paddingVertical: 6 },
  stepCounter: { fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  stepName: { fontSize: 16, fontWeight: '700', marginTop: 2 },
  progressTrack: { height: 4, marginHorizontal: 16, borderRadius: 2, backgroundColor: '#38383A', marginBottom: 4 },
  progressFill: { height: 4, borderRadius: 2 },
  scroll: { paddingHorizontal: 16, paddingBottom: 24 },
  stepContent: { paddingTop: 16 },
  stepTitle: { fontSize: 26, fontWeight: '800', color: '#FFF', marginBottom: 8, letterSpacing: -0.5 },
  stepSub: { fontSize: 15, color: '#8E8E93', lineHeight: 22, marginBottom: 24 },
  fieldLabel: { fontSize: 14, fontWeight: '600', color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 },
  input: { borderRadius: 12, borderWidth: 1, paddingHorizontal: 14, paddingVertical: 12, fontSize: 17, marginBottom: 16 },
  bioInput: { minHeight: 120, textAlignVertical: 'top', paddingTop: 12 },

  // Photos
  photoRow: { flexDirection: 'row', alignItems: 'center', gap: 16, marginBottom: 20 },
  profilePhotoBtn: { width: 96, height: 96, borderRadius: 22, overflow: 'hidden', backgroundColor: '#1C1C1E', borderWidth: 2, borderColor: '#C9A962', borderStyle: 'dashed', position: 'relative' },
  profilePhotoImg: { width: '100%', height: '100%' },
  profilePhotoEmpty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 },
  profilePhotoEmptyText: { fontSize: 11, color: '#C9A962', fontWeight: '600' },
  photoCheckBadge: { position: 'absolute', top: -4, right: -4 },
  photoLabel: { fontSize: 17, fontWeight: '700', marginBottom: 4 },
  changePhotoBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#C9A96220', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, alignSelf: 'flex-start' },
  changePhotoBtnText: { fontSize: 14, color: '#C9A962', fontWeight: '600' },
  coverPhotoBtn: { width: '100%', height: 140, borderRadius: 16, overflow: 'hidden', backgroundColor: '#1C1C1E', position: 'relative', marginBottom: 8 },
  coverOverlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', gap: 8 },
  coverOverlayText: { fontSize: 16, fontWeight: '700', color: '#C9A962' },
  coverCheck: { position: 'absolute', top: 10, right: 10 },

  // AI button
  aiBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#C9A96220', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  aiBtnText: { fontSize: 13, color: '#C9A962', fontWeight: '600' },

  // Social
  socialRow: { flexDirection: 'row', alignItems: 'center', borderRadius: 12, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 2, marginBottom: 10, gap: 10 },
  socialIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  socialInput: { flex: 1, fontSize: 16, paddingVertical: 12 },

  // Colors
  colorPreviewCard: { borderRadius: 16, borderWidth: 1, padding: 16, marginBottom: 8 },
  colorPreviewPhoto: { width: 56, height: 56, borderRadius: 14, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  colorSwatch: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)' },
  colorSwatchSelected: { borderWidth: 2.5, borderColor: '#FFF' },
  colorSwatchLarge: { width: 46, height: 46, borderRadius: 12, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: 'rgba(255,255,255,0.2)' },
  themeOption: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, borderWidth: 1.5, padding: 14 },
  themeLabel: { fontSize: 15, flex: 1 },

  // Done
  doneIcon: { width: 88, height: 88, borderRadius: 24, alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 14, borderWidth: 1, padding: 14, marginBottom: 10 },
  assetIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },

  // Footer
  footer: { paddingHorizontal: 16, paddingVertical: 12, borderTopWidth: 1 },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 16 },
  nextBtnText: { fontSize: 18, fontWeight: '800' },
});
