import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, useWindowDimensions } from 'react-native';
import { useRouter, usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const PROD_BASE = 'https://app.imosapp.com';

const NAV_LINKS = [
  { label: 'Features', path: '/imos/features' },
  { label: 'Solutions', path: '/imos/hub' },
  { label: 'Resources', path: '/imos/training' },
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
              {NAV_LINKS.map((link) => (
                <TouchableOpacity key={link.path} onPress={() => navigate(link.path)} data-testid={`nav-${link.label.toLowerCase()}`}>
                  <Text style={[styles.navLink, isActive(link.path) && styles.navLinkActive]}>
                    {link.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            {/* CTA */}
            <View style={styles.ctaRow}>
              <TouchableOpacity onPress={() => navigate('/auth/login')} style={styles.signInBtn} data-testid="header-login-btn">
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
            <Ionicons name={menuOpen ? 'close' : 'menu'} size={26} color="#FFF" />
          </TouchableOpacity>
        )}
      </View>

      {/* Mobile Dropdown */}
      {!isDesktop && menuOpen && (
        <View style={styles.mobileMenu}>
          {NAV_LINKS.map((link) => (
            <TouchableOpacity key={link.path} onPress={() => navigate(link.path)} style={styles.mobileMenuItem} data-testid={`mobile-nav-${link.label.toLowerCase()}`}>
              <Text style={[styles.mobileMenuText, isActive(link.path) && { color: '#C9A962' }]}>{link.label}</Text>
            </TouchableOpacity>
          ))}
          <View style={styles.mobileDivider} />
          <TouchableOpacity onPress={() => navigate('/auth/login')} style={styles.mobileMenuItem}>
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
          <Text style={styles.footerTagline}>Relationship Management System</Text>
          <Text style={styles.footerSub}>Old School Relationship Building.{'\n'}Modern Tools.</Text>
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
            <TouchableOpacity onPress={() => { if (Platform.OS === 'web') window.open('mailto:forest@imosapp.com', '_blank'); }}>
              <Text style={styles.footerLink}>Contact Us</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.footerCol}>
            <Text style={styles.footerColTitle}>Get Started</Text>
            <TouchableOpacity onPress={() => navigate('/imos/demo')}><Text style={styles.footerLink}>Schedule a Demo</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/auth/signup')}><Text style={styles.footerLink}>Start 14-Day Free Trial</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/auth/login')}><Text style={styles.footerLink}>Sign In</Text></TouchableOpacity>
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
    backgroundColor: '#000',
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.06)',
    ...(Platform.OS === 'web' ? { position: 'sticky' as any, top: 0, zIndex: 100 } : {}),
  },
  headerInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    alignSelf: 'center',
    width: '100%',
  },
  logoWrap: { flexDirection: 'row' },
  logoI: { fontSize: 26, fontWeight: '900', color: '#FF3B30' },
  logoM: { fontSize: 26, fontWeight: '900', color: '#FFD60A' },
  logoO: { fontSize: 26, fontWeight: '900', color: '#34C759' },
  logoS: { fontSize: 26, fontWeight: '900', color: '#007AFF' },
  navRow: { flexDirection: 'row', alignItems: 'center', gap: 28 },
  navLink: { fontSize: 14, fontWeight: '500', color: 'rgba(255,255,255,0.6)' },
  navLinkActive: { color: '#C9A962', fontWeight: '600' },
  ctaRow: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  loginLink: { fontSize: 14, fontWeight: '500', color: 'rgba(255,255,255,0.7)' },
  signInBtn: { paddingVertical: 8, paddingHorizontal: 20, borderRadius: 20, borderWidth: 1, borderColor: 'rgba(255,255,255,0.25)' },
  signInBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  signupBtn: { backgroundColor: '#C9A962', paddingVertical: 8, paddingHorizontal: 20, borderRadius: 20 },
  signupBtnText: { fontSize: 14, fontWeight: '700', color: '#000' },
  hamburger: { padding: 4 },
  /* Mobile Menu */
  mobileMenu: {
    backgroundColor: '#000',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.06)',
    paddingHorizontal: 20,
    paddingBottom: 16,
  },
  mobileMenuItem: { paddingVertical: 12 },
  mobileMenuText: { fontSize: 16, fontWeight: '500', color: 'rgba(255,255,255,0.8)' },
  mobileDivider: { height: 1, backgroundColor: 'rgba(255,255,255,0.06)', marginVertical: 4 },
  mobileSignup: { backgroundColor: '#C9A962', borderRadius: 12, alignItems: 'center', marginTop: 8, paddingVertical: 14 },
  mobileSignupText: { fontSize: 16, fontWeight: '700', color: '#000' },

  /* ===== FOOTER ===== */
  footer: {
    backgroundColor: '#000',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.06)',
    paddingTop: 40,
  },
  footerInner: { paddingHorizontal: 20, alignSelf: 'center', width: '100%' },
  footerBrand: { marginBottom: 32 },
  footerLogoRow: { flexDirection: 'row', marginBottom: 6 },
  fChar: { fontSize: 24, fontWeight: '800' },
  footerTagline: { fontSize: 12, color: '#6E6E73', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 8 },
  footerSub: { fontSize: 14, color: 'rgba(255,255,255,0.5)', lineHeight: 20 },
  footerLinks: { gap: 24, marginBottom: 32 },
  footerCol: { gap: 8 },
  footerColTitle: { fontSize: 13, fontWeight: '700', color: '#FFF', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 },
  footerLink: { fontSize: 14, color: 'rgba(255,255,255,0.5)' },
  footerBottom: { borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.06)', paddingVertical: 20, alignItems: 'center' },
  footerCopy: { fontSize: 12, color: '#3A3A3C' },
});
