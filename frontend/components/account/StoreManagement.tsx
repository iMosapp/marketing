/**
 * StoreManagement.tsx — Store presence & management links for managers/admins.
 * Shown when viewMode === 'store' and user has a store_id.
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showSimpleAlert } from '../../services/alert';

const PROD_BASE = 'https://app.imonsocial.com';

interface Props {
  user: any;
  colors: Record<string, string>;
  storeSlug: string | null;
  storeName: string | null;
}

export function StoreManagement({ user, colors, storeSlug, storeName }: Props) {
  const router = useRouter();

  const storeItems = [
    { icon: 'storefront', title: 'Edit Store Profile', subtitle: 'Name, logo, address, hours', color: '#34C759', route: '/settings/store-profile' },
    { icon: 'globe-outline', title: 'Store Landing Page', subtitle: storeSlug ? `${PROD_BASE}/p/store/${storeSlug}` : 'Store public page', color: '#AF52DE', route: '/settings/store-profile',
      previewUrl: storeSlug ? `${PROD_BASE}/p/store/${storeSlug}` : null },
    { icon: 'card-outline', title: 'Store Business Card', subtitle: storeSlug ? `${PROD_BASE}/card/store/${storeSlug}` : 'Store digital card', color: '#007AFF', route: '/settings/store-profile',
      previewUrl: storeSlug ? `${PROD_BASE}/card/store/${storeSlug}` : null },
    { icon: 'sparkles-outline', title: 'Store Showcase', subtitle: storeSlug ? `${PROD_BASE}/showcase/store/${storeSlug}` : 'Store showcase page', color: '#FF2D55', route: '/settings/store-profile',
      previewUrl: storeSlug ? `${PROD_BASE}/showcase/store/${storeSlug}` : null },
    { icon: 'checkmark-circle-outline', title: 'Showcase Approvals', subtitle: 'Approve customer photos & reviews', color: '#FF9500', route: '/settings/showcase-approvals' },
    { icon: 'star-outline', title: 'Store Review Links', subtitle: 'Google, Facebook, Yelp review links', color: '#FFD60A', route: '/settings/review-links' },
    { icon: 'images-outline', title: 'Brand Assets', subtitle: 'Logos, images, marketing materials', color: '#5856D6', route: '/admin/brand-assets' },
    { icon: 'color-palette-outline', title: 'Store Brand Kit', subtitle: 'Colors, logo, theme for store pages', color: '#C9A962', route: '/settings/brand-kit' },
  ] as const;

  return (
    <View style={s.section}>
      <Text style={[s.title, { color: '#34C759' }]}>
        {storeName || user?.store_name || 'Store'} Profile & Presence
      </Text>
      <View style={[s.list, { backgroundColor: colors.card, borderColor: '#34C75930' }]}>
        {storeItems.map((item: any, index, arr) => (
          <View key={item.title}>
            <TouchableOpacity
              style={[s.row, { borderBottomColor: colors.border }, index === arr.length - 1 && !item.previewUrl && s.lastRow]}
              onPress={() => router.push(item.route as any)}
              data-testid={`store-${item.title.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <View style={[s.icon, { backgroundColor: `${item.color}20` }]}>
                <Ionicons name={item.icon as any} size={22} color={item.color} />
              </View>
              <View style={s.content}>
                <Text style={[s.itemTitle, { color: colors.text }]}>{item.title}</Text>
                <Text style={[s.itemSub, { color: colors.textSecondary }]} numberOfLines={1}>{item.subtitle}</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
            </TouchableOpacity>

            {item.previewUrl && storeSlug && (
              <View style={[s.actions, { borderBottomColor: colors.border }, index === arr.length - 1 && s.lastRow]}>
                <TouchableOpacity style={[s.actionBtn, { backgroundColor: `${item.color}15` }]}
                  onPress={() => Platform.OS === 'web' ? window.open(item.previewUrl, '_blank') : null}>
                  <Ionicons name="eye-outline" size={13} color={item.color} />
                  <Text style={[s.actionLabel, { color: item.color }]}>Preview</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.actionBtn, { backgroundColor: '#FF950015' }]}
                  onPress={() => { if (Platform.OS === 'web' && navigator.clipboard) { navigator.clipboard.writeText(item.previewUrl); showSimpleAlert('Copied!', 'Link copied to clipboard'); } }}>
                  <Ionicons name="copy-outline" size={13} color="#FF9500" />
                  <Text style={[s.actionLabel, { color: '#FF9500' }]}>Copy Link</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  section: { marginTop: 24, paddingHorizontal: 16 },
  title: { fontSize: 15, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },
  list: { borderRadius: 12, overflow: 'hidden', borderWidth: 1 },
  row: { flexDirection: 'row', alignItems: 'center', padding: 14, borderBottomWidth: 1 },
  lastRow: { borderBottomWidth: 0 },
  icon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  content: { flex: 1 },
  itemTitle: { fontSize: 17, fontWeight: '600', marginBottom: 2 },
  itemSub: { fontSize: 14 },
  actions: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingBottom: 12, borderBottomWidth: 1 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, flex: 1, justifyContent: 'center' },
  actionLabel: { fontSize: 13, fontWeight: '600' },
});
