import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, useWindowDimensions } from 'react-native';
import { useRouter, usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const PROD_BASE = 'https://app.imosapp.com';

const NAV_LINKS = [
  {
    label: 'Products',
    children: [
      { section: 'Your Digital Presence' },
      { label: 'Digital Cards', path: '/imos/digital-card', icon: 'card', color: '#007AFF', desc: 'Shareable, trackable business cards' },
      { label: 'Personal Reviews', path: '/imos/reviews', icon: 'star', color: '#D4AD00', desc: 'Portable reputation that travels with you' },
      { label: 'Link Pages & Showcase', path: '/imos/showcase', icon: 'share-social', color: '#34C759', desc: 'All your socials in one link' },
      { section: 'Engagement' },
      { label: 'Congrats Cards', path: '/imos/congrats-template', icon: 'image', color: '#FF2D55', desc: 'Celebrate every sale automatically' },
      { label: 'Automated Campaigns', path: '/imos/date-triggers', icon: 'rocket', color: '#FF9500', desc: 'Birthdays, anniversaries, follow-ups' },
      { label: 'Inbox & Messaging', path: '/imos/inbox', icon: 'chatbubble-ellipses', color: '#5856D6', desc: 'SMS, email, all in one place' },
      { section: 'Intelligence' },
      { label: 'Jessi AI Assistant', path: '/imos/jessi', icon: 'sparkles', color: '#AF52DE', desc: 'AI-powered relationship intelligence' },
      { label: 'Leaderboards & Analytics', path: '/imos/leaderboard', icon: 'trophy', color: '#FF3B30', desc: 'Track performance across teams' },
    ],
  },
  {
    label: 'Solutions',
    children: [
      { section: 'By Role' },
      { label: 'For Organizations', path: '/imos/organizations', icon: 'business', color: '#007AFF', desc: 'Structure teams, stores & reputation' },
      { label: 'For Individuals', path: '/imos/individuals', icon: 'person', color: '#C9A962', desc: 'Own your personal brand & reviews' },
      { section: 'By Industry' },
      { label: 'Automotive', path: '/imos/salespresentation', icon: 'car-sport', color: '#34C759', desc: 'Built for dealerships & sales teams' },
      { label: 'Sales Teams', path: '/imos/hub', icon: 'briefcase', color: '#FF9500', desc: 'Any industry, any team size' },
    ],
  },
  {
    label: 'Resources',
    children: [
      { label: 'Training Hub', path: '/imos/training', icon: 'school', color: '#007AFF', desc: 'Courses, videos & best practices' },
      { label: 'Help Center', path: '/imos/help', icon: 'help-circle', color: '#34C759', desc: 'Guides, FAQs & support' },
      { label: 'App Directory', path: '/imos/app-directory', icon: 'grid', color: '#AF52DE', desc: 'Explore all iMOs features' },
      { label: 'Sales Deck', path: '/imos/presentation', icon: 'easel', color: '#FF9500', desc: 'See what iMOs can do for you' },
    ],
  },
  { label: 'Pricing', path: '/imos/pricing' },
];

export function getShareUrl(path: string) {
  return `${PROD_BASE}${path}`;
}

export function ImosHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const [menuOpen, setMenuOpen] = useState(false);

  const navigate = (path: string) => {
    setMenuOpen(false);
    router.push(path as any);
  };

  const isActive = (path: string) => {
    if (path === '/imos') return pathname === '/imos' || pathname === '/imos/';
    return pathname.startsWith(path);
  };

  return (
    <View style={styles.headerOuter}>
      <View style={[styles.headerInner, isDesktop && { maxWidth: 1100 }]}>
        {/* Logo */}
        <TouchableOpacity onPress={() => navigate('/imos')} style={styles.logoWrap} data-testid="imos-header-logo">
          <Text style={styles.logoI}>i</Text>
          <Text style={styles.logoM}>M</Text>
          <Text style={styles.logoO}>O</Text>
          <Text style={styles.logoS}>s</Text>
        </TouchableOpacity>

        {isDesktop ? (
          <>
            {/* Desktop Nav */}
            <View style={styles.navRow}>
              {NAV_LINKS.map((item: any) => {
                if (item.path) {
                  return (
                    <TouchableOpacity key={item.label} onPress={() => navigate(item.path)} data-testid={`nav-${item.label.toLowerCase()}`}>
                      <Text style={[styles.navLink, isActive(item.path) && styles.navLinkActive]}>{item.label}</Text>
                    </TouchableOpacity>
                  );
                }
                return (
                  <TouchableOpacity key={item.label} onPress={() => navigate(item.children?.find((c: any) => c.path)?.path || '/imos')} data-testid={`nav-${item.label.toLowerCase()}`}>
                    <Text style={styles.navLink}>{item.label}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            {/* CTA */}
            <View style={styles.ctaRow}>
              <TouchableOpacity onPress={() => navigate('/imos/login')} style={styles.signInBtn} data-testid="header-login-btn">
                <Text style={styles.signInBtnText}>Sign In</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.signupBtn} onPress={() => navigate('/imos/demo')} data-testid="header-demo-btn">
                <Text style={styles.signupBtnText}>Get Demo</Text>
              </TouchableOpacity>
            </View>
          </>
        ) : (
          /* Mobile Hamburger */
          <TouchableOpacity onPress={() => setMenuOpen(!menuOpen)} style={styles.hamburger} data-testid="header-menu-toggle">
            <Ionicons name={menuOpen ? 'close' : 'menu'} size={26} color="#1D1D1F" />
          </TouchableOpacity>
        )}
      </View>

      {/* Mobile Dropdown */}
      {!isDesktop && menuOpen && (
        <View style={styles.mobileMenu}>
          {NAV_LINKS.map((item: any) => {
            const target = item.path || item.children?.find((c: any) => c.path)?.path || '/imos';
            return (
              <TouchableOpacity key={item.label} onPress={() => navigate(target)} style={styles.mobileMenuItem} data-testid={`mobile-nav-${item.label.toLowerCase()}`}>
                <Text style={styles.mobileMenuText}>{item.label}</Text>
              </TouchableOpacity>
            );
          })}
          <View style={styles.mobileDivider} />
          <TouchableOpacity onPress={() => navigate('/imos/login')} style={styles.mobileMenuItem}>
            <Text style={styles.mobileMenuText}>Sign In</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigate('/imos/demo')} style={[styles.mobileMenuItem, styles.mobileSignup]}>
            <Text style={styles.mobileSignupText}>Get Demo</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

export function ImosFooter() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  const navigate = (path: string) => router.push(path as any);

  return (
    <View style={styles.footer}>
      <View style={[styles.footerInner, isDesktop && { maxWidth: 1100, flexDirection: 'row', justifyContent: 'space-between' }]}>
        {/* Brand */}
        <View style={styles.footerBrand}>
          <View style={styles.footerLogoRow}>
            <Text style={[styles.fChar, { color: '#FF3B30' }]}>i</Text>
            <Text style={[styles.fChar, { color: '#FFD60A' }]}>M</Text>
            <Text style={[styles.fChar, { color: '#34C759' }]}>O</Text>
            <Text style={[styles.fChar, { color: '#007AFF' }]}>s</Text>
          </View>
          <Text style={styles.footerTagline}>Social Relationship OS</Text>
          <Text style={styles.footerSub}>Meet the New Way{'\n'}to Be On Social.</Text>
        </View>

        {/* Links */}
        <View style={[styles.footerLinks, isDesktop && { flexDirection: 'row', gap: 48 }]}>
          <View style={styles.footerCol}>
            <Text style={styles.footerColTitle}>Product</Text>
            <TouchableOpacity onPress={() => navigate('/imos/features')}><Text style={styles.footerLink}>Features</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/pricing')}><Text style={styles.footerLink}>Pricing</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/salespresentation')}><Text style={styles.footerLink}>Why Use iMOs</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/hub')}><Text style={styles.footerLink}>Solutions</Text></TouchableOpacity>
          </View>
          <View style={styles.footerCol}>
            <Text style={styles.footerColTitle}>Company</Text>
            <TouchableOpacity onPress={() => navigate('/imos/privacy')}><Text style={styles.footerLink}>Privacy Policy</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/terms')}><Text style={styles.footerLink}>Terms of Service</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => { if (Platform.OS === 'web') window.location.href = 'mailto:forest@imosapp.com'; }}>
              <Text style={styles.footerLink}>Contact Us</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.footerCol}>
            <Text style={styles.footerColTitle}>Get Started</Text>
            <TouchableOpacity onPress={() => navigate('/imos/demo')}><Text style={styles.footerLink}>Schedule a Demo</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/signup')}><Text style={styles.footerLink}>Start 14-Day Free Trial</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/login')}><Text style={styles.footerLink}>Sign In</Text></TouchableOpacity>
          </View>
        </View>
      </View>

      <View style={styles.footerBottom}>
        <Text style={styles.footerCopy}>&copy; {new Date().getFullYear()} iMOs. All rights reserved.</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  /* ===== HEADER ===== */
  headerOuter: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.06)',
    ...(Platform.OS === 'web' ? { position: 'sticky' as any, top: 0, zIndex: 100, backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' } : {}),
  },
  headerInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
    alignSelf: 'center',
    width: '100%',
  },
  logoWrap: { flexDirection: 'row' },
  logoI: { fontSize: 26, fontWeight: '900', color: '#FF3B30' },
  logoM: { fontSize: 26, fontWeight: '900', color: '#FFD60A' },
  logoO: { fontSize: 26, fontWeight: '900', color: '#34C759' },
  logoS: { fontSize: 26, fontWeight: '900', color: '#007AFF' },
  navRow: { flexDirection: 'row', alignItems: 'center', gap: 32 },
  navLink: { fontSize: 14, fontWeight: '500', color: '#6E6E73' },
  navLinkActive: { color: '#007AFF', fontWeight: '600' },
  ctaRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  loginLink: { fontSize: 14, fontWeight: '500', color: '#6E6E73' },
  signInBtn: { paddingVertical: 9, paddingHorizontal: 20, borderRadius: 980 },
  signInBtnText: { fontSize: 14, fontWeight: '600', color: '#1D1D1F' },
  signupBtn: { backgroundColor: '#007AFF', paddingVertical: 9, paddingHorizontal: 22, borderRadius: 980 },
  signupBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  hamburger: { padding: 4 },
  /* Mobile Menu */
  mobileMenu: {
    backgroundColor: '#FFF',
    borderTopWidth: 1,
    borderTopColor: 'rgba(0,0,0,0.06)',
    paddingHorizontal: 20,
    paddingBottom: 16,
  },
  mobileMenuItem: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.04)' },
  mobileMenuText: { fontSize: 16, fontWeight: '500', color: '#1D1D1F' },
  mobileDivider: { height: 1, backgroundColor: 'rgba(0,0,0,0.06)', marginVertical: 4 },
  mobileSignup: { backgroundColor: '#007AFF', borderRadius: 14, alignItems: 'center', marginTop: 12, paddingVertical: 14, borderBottomWidth: 0 },
  mobileSignupText: { fontSize: 16, fontWeight: '700', color: '#FFF' },

  /* ===== FOOTER ===== */
  footer: {
    backgroundColor: '#F5F5F7',
    borderTopWidth: 1,
    borderTopColor: 'rgba(0,0,0,0.06)',
    paddingTop: 40,
  },
  footerInner: { paddingHorizontal: 20, alignSelf: 'center', width: '100%' },
  footerBrand: { marginBottom: 32 },
  footerLogoRow: { flexDirection: 'row', marginBottom: 6 },
  fChar: { fontSize: 24, fontWeight: '800' },
  footerTagline: { fontSize: 12, color: '#86868B', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 8 },
  footerSub: { fontSize: 14, color: '#6E6E73', lineHeight: 20 },
  footerLinks: { gap: 24, marginBottom: 32 },
  footerCol: { gap: 8 },
  footerColTitle: { fontSize: 12, fontWeight: '700', color: '#1D1D1F', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 },
  footerLink: { fontSize: 14, color: '#86868B' },
  footerBottom: { borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.06)', paddingVertical: 20, alignItems: 'center' },
  footerCopy: { fontSize: 12, color: '#86868B' },
});
