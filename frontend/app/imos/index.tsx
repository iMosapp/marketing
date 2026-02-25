import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

const { width } = Dimensions.get('window');
const APP_URL = process.env.REACT_APP_BACKEND_URL || '';

type PublicPage = {
  title: string;
  description: string;
  icon: string;
  color: string;
  path: string;
  badge?: string;
};

const PUBLIC_PAGES: { category: string; icon: string; color: string; pages: PublicPage[] }[] = [
  {
    category: 'Learn About iMOs',
    icon: 'diamond',
    color: '#C9A962',
    pages: [
      { title: 'Sales Presentation', description: 'Interactive deck showcasing iMOs capabilities', icon: 'easel', color: '#C9A962', path: '/imos/presentation', badge: 'Featured' },
      { title: 'Features Overview', description: 'Explore what iMOs can do for your team', icon: 'apps', color: '#007AFF', path: '/imos/features' },
      { title: 'Pricing Plans', description: 'Subscription tiers and pricing', icon: 'pricetag', color: '#34C759', path: '/subscription/pricing' },
    ],
  },
  {
    category: 'Get Started',
    icon: 'rocket',
    color: '#FF9500',
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
      { title: 'Privacy Policy', description: 'How we protect your data', icon: 'shield', color: '#5856D6', path: '/privacy' },
      { title: 'Terms of Service', description: 'Usage terms and conditions', icon: 'document-text', color: '#8E8E93', path: '/terms' },
    ],
  },
];

export default function ImosHubScreen() {
  const router = useRouter();

  const navigateTo = (path: string) => {
    router.push(path as any);
  };

  return (
    <View style={styles.container}>
      <LinearGradient colors={['#0A0A1A', '#1A1A2E', '#0A0A1A']} style={StyleSheet.absoluteFill} />

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <View style={styles.logoBadge}>
            <Text style={styles.logoI}>i</Text>
            <Text style={styles.logoM}>M</Text>
            <Text style={styles.logoO}>O</Text>
            <Text style={styles.logoS}>s</Text>
          </View>
          <Text style={styles.tagline}>Relationship Management System</Text>
          <Text style={styles.heroText}>
            Empower your sales teams with tools that help them be the best in the business.
          </Text>
          <TouchableOpacity
            style={styles.heroBtn}
            onPress={() => navigateTo('/imos/presentation')}
            data-testid="view-presentation-btn"
          >
            <Ionicons name="play-circle" size={22} color="#000" />
            <Text style={styles.heroBtnText}>View Presentation</Text>
          </TouchableOpacity>
        </View>

        {/* Value Props */}
        <View style={styles.valueProps}>
          {[
            { icon: 'camera', color: '#34C759', title: 'Snap & Start', desc: 'One photo starts a lifetime relationship' },
            { icon: 'repeat', color: '#007AFF', title: 'Never Forget', desc: 'Automated campaigns for every milestone' },
            { icon: 'people', color: '#FF9500', title: 'Team Empowerment', desc: 'Tools that make your team unstoppable' },
            { icon: 'trending-up', color: '#AF52DE', title: 'Measurable Results', desc: 'More deals, better retention, real data' },
          ].map((p, i) => (
            <View key={i} style={styles.valueProp}>
              <View style={[styles.valueIcon, { backgroundColor: `${p.color}15` }]}>
                <Ionicons name={p.icon as any} size={24} color={p.color} />
              </View>
              <Text style={styles.valueTitle}>{p.title}</Text>
              <Text style={styles.valueDesc}>{p.desc}</Text>
            </View>
          ))}
        </View>

        {/* Page Directory */}
        {PUBLIC_PAGES.map((section) => (
          <View key={section.category} style={styles.section}>
            <View style={styles.sectionHeader}>
              <View style={[styles.sectionIcon, { backgroundColor: `${section.color}20` }]}>
                <Ionicons name={section.icon as any} size={18} color={section.color} />
              </View>
              <Text style={styles.sectionTitle}>{section.category}</Text>
            </View>
            {section.pages.map((page) => (
              <TouchableOpacity
                key={page.path}
                style={styles.pageCard}
                onPress={() => navigateTo(page.path)}
                activeOpacity={0.7}
                data-testid={`hub-${page.title.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <View style={[styles.pageIcon, { backgroundColor: `${page.color}15` }]}>
                  <Ionicons name={page.icon as any} size={20} color={page.color} />
                </View>
                <View style={styles.pageInfo}>
                  <Text style={styles.pageTitle}>{page.title}</Text>
                  <Text style={styles.pageDesc}>{page.description}</Text>
                </View>
                {page.badge && (
                  <View style={styles.pageBadge}>
                    <Text style={styles.pageBadgeText}>{page.badge}</Text>
                  </View>
                )}
                <Ionicons name="chevron-forward" size={18} color="#6E6E73" />
              </TouchableOpacity>
            ))}
          </View>
        ))}

        {/* Contact CTA */}
        <View style={styles.contactSection}>
          <Text style={styles.contactTitle}>Ready to get started?</Text>
          <Text style={styles.contactDesc}>See how iMOs can transform your team's performance and customer relationships.</Text>
          <View style={styles.contactBtns}>
            <TouchableOpacity style={styles.primaryBtn} onPress={() => {
              if (Platform.OS === 'web') window.open('mailto:forest@imosapp.com?subject=iMOs%20Inquiry', '_blank');
            }} data-testid="contact-email-btn">
              <Ionicons name="mail" size={18} color="#000" />
              <Text style={styles.primaryBtnText}>Contact Us</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.secondaryBtn} onPress={() => navigateTo('/auth/signup')} data-testid="signup-btn">
              <Text style={styles.secondaryBtnText}>Sign Up Free</Text>
              <Ionicons name="arrow-forward" size={16} color="#C9A962" />
            </TouchableOpacity>
          </View>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <View style={styles.footerLogo}>
            <Text style={styles.footerLogoI}>i</Text><Text style={styles.footerLogoM}>M</Text><Text style={styles.footerLogoO}>O</Text><Text style={styles.footerLogoS}>s</Text>
          </View>
          <Text style={styles.footerText}>Relationship Management System</Text>
          <Text style={styles.footerCopy}>&copy; {new Date().getFullYear()} iMOs. All rights reserved.</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  scroll: { paddingBottom: 40 },
  // Hero
  hero: { alignItems: 'center', paddingTop: Platform.OS === 'web' ? 60 : 80, paddingBottom: 40, paddingHorizontal: 24 },
  logoBadge: { flexDirection: 'row', marginBottom: 8 },
  logoI: { fontSize: 48, fontWeight: '900', color: '#FF3B30' },
  logoM: { fontSize: 48, fontWeight: '900', color: '#FFD60A' },
  logoO: { fontSize: 48, fontWeight: '900', color: '#34C759' },
  logoS: { fontSize: 48, fontWeight: '900', color: '#007AFF' },
  tagline: { fontSize: 14, color: '#8E8E93', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 16 },
  heroText: { fontSize: 18, color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 26, maxWidth: 400, marginBottom: 28 },
  heroBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 28, borderRadius: 28,
  },
  heroBtnText: { fontSize: 16, fontWeight: '700', color: '#000' },
  // Value Props
  valueProps: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12, paddingHorizontal: 16, marginBottom: 32 },
  valueProp: { width: width > 500 ? '45%' : '44%', backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)' },
  valueIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  valueTitle: { fontSize: 15, fontWeight: '600', color: '#FFF', marginBottom: 4 },
  valueDesc: { fontSize: 12, color: '#8E8E93', lineHeight: 17 },
  // Sections
  section: { paddingHorizontal: 16, marginBottom: 24 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10, paddingLeft: 4 },
  sectionIcon: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  pageCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#1C1C1E', borderRadius: 12, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  pageIcon: { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  pageInfo: { flex: 1 },
  pageTitle: { fontSize: 15, fontWeight: '600', color: '#FFF' },
  pageDesc: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  pageBadge: { backgroundColor: '#C9A96225', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, marginRight: 8 },
  pageBadgeText: { fontSize: 10, fontWeight: '600', color: '#C9A962' },
  // Contact CTA
  contactSection: { alignItems: 'center', paddingVertical: 40, paddingHorizontal: 24, marginTop: 8 },
  contactTitle: { fontSize: 24, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 10 },
  contactDesc: { fontSize: 14, color: '#8E8E93', textAlign: 'center', lineHeight: 21, maxWidth: 360, marginBottom: 24 },
  contactBtns: { flexDirection: 'row', gap: 12 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 12, paddingHorizontal: 24, borderRadius: 24 },
  primaryBtnText: { fontSize: 15, fontWeight: '600', color: '#000' },
  secondaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 12, paddingHorizontal: 20, borderRadius: 24, borderWidth: 1, borderColor: '#C9A96240' },
  secondaryBtnText: { fontSize: 15, fontWeight: '500', color: '#C9A962' },
  // Footer
  footer: { alignItems: 'center', paddingTop: 40, paddingBottom: 20, borderTopWidth: 1, borderTopColor: '#1C1C1E', marginHorizontal: 16 },
  footerLogo: { flexDirection: 'row', marginBottom: 4 },
  footerLogoI: { fontSize: 20, fontWeight: '800', color: '#FF3B30' },
  footerLogoM: { fontSize: 20, fontWeight: '800', color: '#FFD60A' },
  footerLogoO: { fontSize: 20, fontWeight: '800', color: '#34C759' },
  footerLogoS: { fontSize: 20, fontWeight: '800', color: '#007AFF' },
  footerText: { fontSize: 11, color: '#6E6E73', letterSpacing: 1, marginBottom: 8 },
  footerCopy: { fontSize: 11, color: '#3A3A3C' },
});
