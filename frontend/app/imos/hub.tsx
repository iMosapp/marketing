import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter, getShareUrl } from './_components';

type PublicPage = {
  title: string;
  description: string;
  icon: string;
  color: string;
  path: string;
  badge?: string;
};

const PAGE_SECTIONS: { category: string; icon: string; color: string; pages: PublicPage[] }[] = [
  {
    category: 'Learn About iMOs',
    icon: 'diamond',
    color: '#C9A962',
    pages: [
      { title: 'Sales Presentation', description: 'Interactive deck showcasing iMOs capabilities', icon: 'easel', color: '#C9A962', path: '/imos/salespresentation', badge: 'Featured' },
      { title: 'Features Overview', description: 'Explore what iMOs can do for your team', icon: 'apps', color: '#007AFF', path: '/imos/features' },
      { title: 'Pricing Plans', description: 'Subscription tiers and pricing', icon: 'pricetag', color: '#34C759', path: '/imos/pricing' },
    ],
  },
  {
    category: 'Experience iMOs',
    icon: 'rocket',
    color: '#FF9500',
    pages: [
      { title: 'Onboarding Preview', description: 'See the onboarding flow for all 5 roles', icon: 'eye', color: '#C9A962', path: '/imos/onboarding-preview', badge: 'Interactive' },
    ],
  },
  {
    category: 'Get Started',
    icon: 'person-add',
    color: '#34C759',
    pages: [
      { title: 'Sign Up', description: 'Create your iMOs account', icon: 'person-add', color: '#34C759', path: '/auth/signup' },
      { title: 'Log In', description: 'Access your dashboard', icon: 'log-in', color: '#007AFF', path: '/auth/login' },
      { title: 'Forgot Password', description: 'Reset your credentials', icon: 'key', color: '#FF9500', path: '/auth/forgot-password' },
    ],
  },
  {
    category: 'Legal & Compliance',
    icon: 'shield-checkmark',
    color: '#8E8E93',
    pages: [
      { title: 'Privacy Policy', description: 'How we protect your data', icon: 'shield', color: '#5856D6', path: '/imos/privacy' },
      { title: 'Terms of Service', description: 'Usage terms and conditions', icon: 'document-text', color: '#8E8E93', path: '/imos/terms' },
    ],
  },
];

export default function HubScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 960 : undefined;

  const navigate = (path: string) => router.push(path as any);

  const copyLink = (path: string) => {
    const url = getShareUrl(path);
    if (Platform.OS === 'web' && navigator.clipboard) {
      navigator.clipboard.writeText(url);
    }
  };

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

          {/* Title */}
          <View style={s.titleSection}>
            <Text style={s.label}>PAGE DIRECTORY</Text>
            <Text style={[s.title, isDesktop && { fontSize: 36 }]}>All Public Pages</Text>
            <Text style={s.subtitle}>Browse, preview, and share every public page in the iMOs platform.</Text>
          </View>

          {/* Sections */}
          {PAGE_SECTIONS.map((section) => (
            <View key={section.category} style={s.section}>
              <View style={s.sectionHeader}>
                <View style={[s.sectionIcon, { backgroundColor: `${section.color}20` }]}>
                  <Ionicons name={section.icon as any} size={18} color={section.color} />
                </View>
                <Text style={s.sectionTitle}>{section.category}</Text>
              </View>
              <View style={isDesktop ? s.gridDesktop : undefined}>
                {section.pages.map((page) => (
                  <TouchableOpacity
                    key={page.path}
                    style={[s.pageCard, isDesktop && s.pageCardDesktop]}
                    onPress={() => navigate(page.path)}
                    activeOpacity={0.7}
                    data-testid={`hub-${page.title.toLowerCase().replace(/\s+/g, '-')}`}
                  >
                    <View style={[s.pageIcon, { backgroundColor: `${page.color}15` }]}>
                      <Ionicons name={page.icon as any} size={20} color={page.color} />
                    </View>
                    <View style={s.pageInfo}>
                      <View style={s.pageTitleRow}>
                        <Text style={s.pageTitle}>{page.title}</Text>
                        {page.badge && (
                          <View style={s.badge}><Text style={s.badgeText}>{page.badge}</Text></View>
                        )}
                      </View>
                      <Text style={s.pageDesc}>{page.description}</Text>
                      <Text style={s.pageUrl}>{getShareUrl(page.path)}</Text>
                    </View>
                    <TouchableOpacity onPress={() => copyLink(page.path)} style={s.copyBtn} data-testid={`copy-${page.title.toLowerCase().replace(/\s+/g, '-')}`}>
                      <Ionicons name="copy-outline" size={16} color="#8E8E93" />
                    </TouchableOpacity>
                    <Ionicons name="chevron-forward" size={18} color="#6E6E73" />
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ))}

        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  scroll: { paddingBottom: 0 },
  titleSection: { alignItems: 'center', paddingTop: 40, paddingBottom: 24, paddingHorizontal: 20 },
  label: { fontSize: 11, fontWeight: '700', color: '#C9A962', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#FFF', marginBottom: 8, textAlign: 'center' },
  subtitle: { fontSize: 15, color: '#8E8E93', textAlign: 'center', lineHeight: 22, maxWidth: 400 },
  section: { marginBottom: 24, paddingHorizontal: 16 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10, paddingLeft: 4 },
  sectionIcon: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  gridDesktop: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  pageCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#1C1C1E', borderRadius: 12, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  pageCardDesktop: { width: '48%', marginBottom: 0 },
  pageIcon: { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  pageInfo: { flex: 1 },
  pageTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pageTitle: { fontSize: 15, fontWeight: '600', color: '#FFF' },
  badge: { backgroundColor: '#C9A96225', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  badgeText: { fontSize: 10, fontWeight: '600', color: '#C9A962' },
  pageDesc: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  pageUrl: { fontSize: 10, color: '#4A4A4C', marginTop: 3, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined },
  copyBtn: { padding: 8, marginRight: 4 },
});
