import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
const IS_WEB = Platform.OS === 'web';
const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const COLORS = {
  bg: '#000000',
  card: '#1C1C1E',
  border: '#2C2C2E',
  text: '#FFFFFF',
  sub: '#8E8E93',
  accent: '#007AFF',
  success: '#34C759',
  gold: '#C9A962',
};

interface BrandAsset {
  id: string;
  label: string;
  description: string;
  url: string;
  size: string;
  category: 'logo' | 'icon' | 'avatar' | 'custom';
}

export default function BrandAssetsPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [customAssets, setCustomAssets] = useState<BrandAsset[]>([]);
  const [storeData, setStoreData] = useState<any>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Built-in logo assets from the app
  const builtInAssets: BrandAsset[] = [
    { id: 'logo-512', label: 'App Logo (512px)', description: 'White tile logo — PWA home screen & app icon', url: '/logo512.png', size: '512x512', category: 'logo' },
    { id: 'logo-192', label: 'App Logo (192px)', description: 'White tile logo — Android Chrome', url: '/logo192.png', size: '192x192', category: 'logo' },
    { id: 'logo-dark', label: 'Logo (Dark Background)', description: 'Logo on dark background for dark themes', url: '/new-logo-512-dark.png', size: '512x512', category: 'logo' },
    { id: 'logo-light', label: 'Logo (White Background)', description: 'Logo on white background for light themes', url: '/new-logo-512-light.png', size: '512x512', category: 'logo' },
    { id: 'logo-transparent', label: 'Transparent Logo (512px)', description: 'Logo with no background — headers, overlays', url: '/imos-logo-transparent.png', size: '512x512', category: 'logo' },
    { id: 'logo-transparent-hd', label: 'Transparent Logo (1024px)', description: 'High-res transparent logo for print & large displays', url: '/imos-logo-transparent-1024.png', size: '1024x1024', category: 'logo' },
    { id: 'logo-original', label: 'Original Full Logo (1024px)', description: 'Highest resolution transparent logo', url: '/new-logo-original.png', size: '1024x1024', category: 'logo' },
    { id: 'favicon-256', label: 'Favicon (256px)', description: 'High-res browser icon', url: '/favicon-256.png', size: '256x256', category: 'icon' },
    { id: 'favicon-32', label: 'Favicon (32px)', description: 'Standard browser tab icon', url: '/favicon-32x32.png', size: '32x32', category: 'icon' },
    { id: 'favicon-16', label: 'Favicon (16px)', description: 'Small favicon', url: '/favicon-16x16.png', size: '16x16', category: 'icon' },
    { id: 'apple-touch', label: 'Apple Touch Icon', description: 'iOS home screen icon — 180px white tile', url: '/apple-touch-icon.png', size: '180x180', category: 'icon' },
  ];

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load store data for store logo
      if (user?.store_id) {
        const storeRes = await api.get(`/admin/stores/${user.store_id}`);
        setStoreData(storeRes.data);
      }
      // Load custom uploaded assets
      try {
        const assetsRes = await api.get(`/brand-assets/${user?._id}`);
        setCustomAssets(assetsRes.data?.assets || []);
      } catch {
        // endpoint may not exist yet, that's ok
      }
    } catch (err) {
      console.error('Failed to load brand data:', err);
    } finally {
      setLoading(false);
    }
  };

  const dynamicAssets: BrandAsset[] = [];
  if (user?.photo_url) {
    dynamicAssets.push({ id: 'user-avatar', label: 'My Profile Photo', description: 'Your current profile avatar', url: user.photo_url, size: 'Original', category: 'avatar' });
  }
  if (storeData?.logo_url) {
    dynamicAssets.push({ id: 'store-logo', label: 'Store Logo', description: storeData.name || 'Store branding logo', url: storeData.logo_url, size: 'Original', category: 'logo' });
  }

  const allAssets = [...builtInAssets, ...dynamicAssets, ...customAssets];

  const handleDownload = (asset: BrandAsset) => {
    const fullUrl = asset.url.startsWith('http') ? asset.url : `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}${asset.url}`;
    if (IS_WEB) {
      const a = document.createElement('a');
      a.href = fullUrl;
      a.download = `${asset.label.replace(/\s+/g, '-').toLowerCase()}.png`;
      a.target = '_blank';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
    showSimpleAlert('Downloading', `${asset.label} download started`);
  };

  const handleCopyUrl = async (asset: BrandAsset) => {
    const fullUrl = asset.url.startsWith('http') ? asset.url : `${process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'}${asset.url}`;
    try {
      if (IS_WEB) {
        await navigator.clipboard.writeText(fullUrl);
      }
      setCopiedId(asset.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      showSimpleAlert('Error', 'Failed to copy URL');
    }
  };

  const handleUploadAsset = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: false,
      quality: 1,
    });
    if (result.canceled || !result.assets[0]) return;

    setUploading(true);
    try {
      const asset = result.assets[0];
      const formData = new FormData();
      formData.append('user_id', user?._id || '');

      if (IS_WEB) {
        const response = await fetch(asset.uri);
        const blob = await response.blob();
        formData.append('file', blob, asset.fileName || 'brand-asset.png');
      } else {
        formData.append('file', { uri: asset.uri, type: asset.mimeType || 'image/png', name: asset.fileName || 'brand-asset.png' } as any);
      }

      const res = await api.post('/brand-assets/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (res.data?.asset) {
        setCustomAssets(prev => [...prev, res.data.asset]);
        showSimpleAlert('Uploaded', 'Brand asset added to your kit');
      }
    } catch (err: any) {
      showSimpleAlert('Error', err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteAsset = async (assetId: string) => {
    try {
      await api.delete(`/brand-assets/${user?._id}/${assetId}`);
      setCustomAssets(prev => prev.filter(a => a.id !== assetId));
      showSimpleAlert('Deleted', 'Asset removed from your brand kit');
    } catch {
      showSimpleAlert('Error', 'Failed to delete asset');
    }
  };

  const renderAssetCard = (asset: BrandAsset, isCustom: boolean = false) => (
    <View key={asset.id} style={styles.assetCard} data-testid={`asset-${asset.id}`}>
      <View style={styles.assetPreview}>
        <Image
          source={{ uri: asset.url.startsWith('http') ? asset.url : `${API_BASE}${asset.url}` }}
          style={styles.assetImage}
          resizeMode="contain"
        />
      </View>
      <View style={styles.assetInfo}>
        <Text style={styles.assetLabel}>{asset.label}</Text>
        <Text style={styles.assetDesc}>{asset.description}</Text>
        <Text style={styles.assetSize}>{asset.size}</Text>
      </View>
      <View style={styles.assetActions}>
        <TouchableOpacity style={styles.assetBtn} onPress={() => handleDownload(asset)} data-testid={`download-${asset.id}`}>
          <Ionicons name="download-outline" size={18} color={COLORS.accent} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.assetBtn} onPress={() => handleCopyUrl(asset)} data-testid={`copy-${asset.id}`}>
          <Ionicons name={copiedId === asset.id ? 'checkmark' : 'copy-outline'} size={18} color={copiedId === asset.id ? COLORS.success : COLORS.sub} />
        </TouchableOpacity>
        {isCustom && (
          <TouchableOpacity style={styles.assetBtn} onPress={() => handleDeleteAsset(asset.id)} data-testid={`delete-${asset.id}`}>
            <Ionicons name="trash-outline" size={18} color="#FF3B30" />
          </TouchableOpacity>
        )}
      </View>
    </View>
  );

  const logoAssets = allAssets.filter(a => a.category === 'logo');
  const iconAssets = allAssets.filter(a => a.category === 'icon');
  const avatarAssets = allAssets.filter(a => a.category === 'avatar');
  const uploadedAssets = allAssets.filter(a => a.category === 'custom');

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.centered}><ActivityIndicator size="large" color={COLORS.accent} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="brand-assets-back">
          <Ionicons name="chevron-back" size={28} color={COLORS.accent} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Brand Assets</Text>
        <TouchableOpacity onPress={() => router.push('/settings/brand-kit' as any)} data-testid="brand-kit-link">
          <Ionicons name="color-palette-outline" size={24} color={COLORS.gold} />
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={{ paddingBottom: 40 }}>
        {/* Upload Section */}
        <TouchableOpacity
          style={styles.uploadCard}
          onPress={handleUploadAsset}
          disabled={uploading}
          data-testid="upload-brand-asset"
        >
          {uploading ? (
            <ActivityIndicator size="small" color={COLORS.accent} />
          ) : (
            <>
              <View style={styles.uploadIcon}>
                <Ionicons name="cloud-upload" size={28} color={COLORS.accent} />
              </View>
              <Text style={styles.uploadTitle}>Upload Brand Asset</Text>
              <Text style={styles.uploadDesc}>Add logos, icons, or images to your brand kit</Text>
            </>
          )}
        </TouchableOpacity>

        {/* Logos Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="image-outline" size={18} color={COLORS.gold} />
            <Text style={styles.sectionTitle}>Logos ({logoAssets.length})</Text>
          </View>
          {logoAssets.map(a => renderAssetCard(a, a.category === 'custom'))}
        </View>

        {/* App Icons Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="apps-outline" size={18} color="#5856D6" />
            <Text style={styles.sectionTitle}>App Icons ({iconAssets.length})</Text>
          </View>
          {iconAssets.map(a => renderAssetCard(a))}
        </View>

        {/* Avatars Section */}
        {avatarAssets.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="person-circle-outline" size={18} color="#34C759" />
              <Text style={styles.sectionTitle}>Avatars ({avatarAssets.length})</Text>
            </View>
            {avatarAssets.map(a => renderAssetCard(a))}
          </View>
        )}

        {/* Uploaded Assets */}
        {uploadedAssets.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="folder-outline" size={18} color="#FF9500" />
              <Text style={styles.sectionTitle}>Uploaded Assets ({uploadedAssets.length})</Text>
            </View>
            {uploadedAssets.map(a => renderAssetCard(a, true))}
          </View>
        )}

        {/* Quick Links */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="link-outline" size={18} color={COLORS.sub} />
            <Text style={styles.sectionTitle}>Quick Links</Text>
          </View>
          <TouchableOpacity
            style={styles.quickLink}
            onPress={() => router.push('/settings/brand-kit' as any)}
          >
            <View style={[styles.quickLinkIcon, { backgroundColor: '#AF52DE20' }]}>
              <Ionicons name="color-palette" size={18} color="#AF52DE" />
            </View>
            <View style={styles.quickLinkContent}>
              <Text style={styles.quickLinkLabel}>Brand Kit Settings</Text>
              <Text style={styles.quickLinkDesc}>Colors, tagline, footer text</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={COLORS.sub} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.quickLink}
            onPress={() => router.push('/settings/store-profile' as any)}
          >
            <View style={[styles.quickLinkIcon, { backgroundColor: '#007AFF20' }]}>
              <Ionicons name="storefront" size={18} color="#007AFF" />
            </View>
            <View style={styles.quickLinkContent}>
              <Text style={styles.quickLinkLabel}>Store Profile</Text>
              <Text style={styles.quickLinkDesc}>Upload store logo, set company name</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={COLORS.sub} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.quickLink}
            onPress={() => router.push('/help' as any)}
          >
            <View style={[styles.quickLinkIcon, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="help-circle" size={18} color="#34C759" />
            </View>
            <View style={styles.quickLinkContent}>
              <Text style={styles.quickLinkLabel}>How to Change Your Logo</Text>
              <Text style={styles.quickLinkDesc}>Step-by-step guide in Help Center</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={COLORS.sub} />
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  scroll: { flex: 1, paddingHorizontal: 16 },

  // Upload card
  uploadCard: {
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: COLORS.card, borderRadius: 16,
    borderWidth: 2, borderColor: COLORS.border, borderStyle: 'dashed',
    padding: 24, marginTop: 16, marginBottom: 8,
  },
  uploadIcon: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: 'rgba(0,122,255,0.15)',
    justifyContent: 'center', alignItems: 'center', marginBottom: 10,
  },
  uploadTitle: { color: COLORS.text, fontSize: 16, fontWeight: '600', marginBottom: 4 },
  uploadDesc: { color: COLORS.sub, fontSize: 13, textAlign: 'center' },

  // Sections
  section: { marginTop: 24 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  sectionTitle: { color: COLORS.text, fontSize: 15, fontWeight: '700' },

  // Asset card
  assetCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: COLORS.card, borderRadius: 14,
    padding: 12, marginBottom: 8, gap: 12,
  },
  assetPreview: {
    width: 56, height: 56, borderRadius: 12,
    backgroundColor: colors.surface, justifyContent: 'center', alignItems: 'center',
    overflow: 'hidden',
  },
  assetImage: { width: 48, height: 48 },
  assetInfo: { flex: 1 },
  assetLabel: { color: COLORS.text, fontSize: 14, fontWeight: '600', marginBottom: 2 },
  assetDesc: { color: COLORS.sub, fontSize: 12, marginBottom: 1 },
  assetSize: { color: '#6E6E73', fontSize: 11, fontWeight: '500' },
  assetActions: { flexDirection: 'row', gap: 4 },
  assetBtn: {
    width: 36, height: 36, borderRadius: 10,
    backgroundColor: colors.surface, justifyContent: 'center', alignItems: 'center',
  },

  // Quick links
  quickLink: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: COLORS.card, borderRadius: 14,
    padding: 14, marginBottom: 8, gap: 12,
  },
  quickLinkIcon: {
    width: 36, height: 36, borderRadius: 10,
    justifyContent: 'center', alignItems: 'center',
  },
  quickLinkContent: { flex: 1 },
  quickLinkLabel: { color: COLORS.text, fontSize: 14, fontWeight: '600', marginBottom: 2 },
  quickLinkDesc: { color: COLORS.sub, fontSize: 12 },
});
