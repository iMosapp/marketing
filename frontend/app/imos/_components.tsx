import React, { useState, useRef, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, useWindowDimensions, Image } from 'react-native';
import { useRouter, usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const PROD_BASE = 'https://app.imonsocial.com';

const NAV_LINKS = [
  {
    label: 'Products',
    children: [
      { section: 'Your Digital Presence' },
      { label: 'Digital Cards', path: '/imos/digital-card', icon: 'card', color: '#007AFF', desc: 'Shareable, trackable business cards' },
      { label: 'Personal Reviews', path: '/imos/reviews', icon: 'star', color: '#D4AD00', desc: 'Portable reputation that travels with you' },
      { label: 'Link Pages', path: '/imos/showcase', icon: 'share-social', color: '#34C759', desc: 'All your socials in one link' },
      { section: 'Engagement' },
      { label: 'Congrats Cards', path: '/imos/congrats-template', icon: 'image', color: '#FF2D55', desc: 'Celebrate every sale automatically' },
      { label: 'Automated Campaigns', path: '/imos/date-triggers', icon: 'rocket', color: '#FF9500', desc: 'Birthdays, follow-ups, on autopilot' },
      { label: 'Inbox & Messaging', path: '/imos/inbox', icon: 'chatbubble-ellipses', color: '#5856D6', desc: 'SMS, email, all in one place' },
      { section: 'Intelligence' },
      { label: 'Jessi AI', path: '/imos/jessi', icon: 'sparkles', color: '#AF52DE', desc: 'AI-powered relationship insights' },
      { label: 'Leaderboards', path: '/imos/leaderboard', icon: 'trophy', color: '#FF3B30', desc: 'Track performance across teams' },
    ],
  },
  {
    label: 'Solutions',
    children: [
      { section: 'By Role' },
      { label: 'For Organizations', path: '/imos/organizations', icon: 'business', color: '#007AFF', desc: 'Manage teams, stores & reputation' },
      { label: 'For Individuals', path: '/imos/individuals', icon: 'person', color: '#C9A962', desc: 'Own your personal brand' },
      { section: 'By Industry' },
      { label: 'Automotive', path: '/imos/salespresentation', icon: 'car-sport', color: '#34C759', desc: 'Built for dealerships' },
      { label: 'Sales Teams', path: '/imos/hub', icon: 'briefcase', color: '#FF9500', desc: 'Any industry, any size' },
    ],
  },
  {
    label: 'Resources',
    children: [
      { label: 'Training Hub', path: '/imos/training', icon: 'school', color: '#007AFF', desc: 'Courses, videos & best practices' },
      { label: 'Help Center', path: '/imos/help', icon: 'help-circle', color: '#34C759', desc: 'Guides, FAQs & support' },
      { label: 'Sales Deck', path: '/imos/presentation', icon: 'easel', color: '#FF9500', desc: 'See what we can do for you' },
    ],
  },
  { label: 'Pricing', path: '/imos/pricing' },
];

export function getShareUrl(path: string) {
  return `${PROD_BASE}${path}`;
}

function DropdownMenu({ item, onNavigate }: { item: any; onNavigate: (p: string) => void }) {
  return (
    <View style={dd.wrap}>
      <View style={dd.inner}>
        {item.children.map((child: any, i: number) => {
          if (child.section) {
            return <Text key={i} style={dd.sectionLabel}>{child.section}</Text>;
          }
          return (
            <TouchableOpacity key={i} style={dd.item} onPress={() => onNavigate(child.path)} data-testid={`dd-${child.label?.toLowerCase().replace(/\s+/g, '-')}`}>
              <View style={[dd.icon, { backgroundColor: child.color + '14' }]}>
                <Ionicons name={child.icon as any} size={17} color={child.color} />
              </View>
              <View style={dd.text}>
                <Text style={dd.name}>{child.label}</Text>
                <Text style={dd.desc}>{child.desc}</Text>
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

export function ImosHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const closeTimerRef = useRef<any>(null);

  const navigate = (path: string) => {
    setMenuOpen(false);
    setActiveDropdown(null);
    router.push(path as any);
  };

  const handleMouseEnter = useCallback((label: string) => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    setActiveDropdown(label);
  }, []);

  const handleMouseLeave = useCallback(() => {
    closeTimerRef.current = setTimeout(() => setActiveDropdown(null), 200);
  }, []);

  return (
    <View style={h.outer}>
      <View style={[h.inner, isDesktop && { maxWidth: 1200 }]}>
        <TouchableOpacity onPress={() => navigate('/imos')} data-testid="imos-header-logo">
          <Image source={require('../../public/new-logo-512-transparent.png')} style={{ width: 80, height: 80 }} resizeMode="contain" />
        </TouchableOpacity>

        {isDesktop ? (
          <>
            <View style={h.navRow}>
              {NAV_LINKS.map((item: any) => {
                if (item.path) {
                  return (
                    <TouchableOpacity key={item.label} onPress={() => navigate(item.path)} data-testid={`nav-${item.label.toLowerCase()}`}>
                      <Text style={h.navLink}>{item.label}</Text>
                    </TouchableOpacity>
                  );
                }
                const isOpen = activeDropdown === item.label;
                return (
                  <View
                    key={item.label}
                    style={h.navItem}
                    {...(Platform.OS === 'web' ? {
                      onMouseEnter: () => handleMouseEnter(item.label),
                      onMouseLeave: handleMouseLeave,
                    } : {})}
                  >
                    <TouchableOpacity
                      onPress={() => setActiveDropdown(isOpen ? null : item.label)}
                      style={h.navTrigger}
                      data-testid={`nav-${item.label.toLowerCase()}`}
                    >
                      <Text style={h.navLink}>{item.label}</Text>
                      <Ionicons name="chevron-down" size={10} color="#86868B" style={isOpen ? { transform: [{ rotate: '180deg' }] } : undefined} />
                    </TouchableOpacity>
                    {isOpen && <DropdownMenu item={item} onNavigate={navigate} />}
                  </View>
                );
              })}
            </View>
            <View style={h.ctaRow}>
              <TouchableOpacity onPress={() => navigate('/imos/login')} style={h.signInBtn} data-testid="header-login-btn">
                <Text style={h.signInText}>Sign In</Text>
              </TouchableOpacity>
              <TouchableOpacity style={h.demoBtn} onPress={() => navigate('/imos/demo')} data-testid="header-demo-btn">
                <Text style={h.demoBtnText}>Get a Demo</Text>
              </TouchableOpacity>
            </View>
          </>
        ) : (
          <TouchableOpacity onPress={() => setMenuOpen(!menuOpen)} style={h.hamburger} data-testid="header-menu-toggle">
            <Ionicons name={menuOpen ? 'close' : 'menu'} size={26} color="#1D1D1F" />
          </TouchableOpacity>
        )}
      </View>

      {!isDesktop && menuOpen && (
        <View style={h.mobileMenu}>
          {NAV_LINKS.map((item: any) => {
            const target = item.path || item.children?.find((c: any) => c.path)?.path || '/imos';
            return (
              <TouchableOpacity key={item.label} onPress={() => navigate(target)} style={h.mobileItem} data-testid={`mobile-nav-${item.label.toLowerCase()}`}>
                <Text style={h.mobileItemText}>{item.label}</Text>
              </TouchableOpacity>
            );
          })}
          <View style={{ height: 1, backgroundColor: 'rgba(0,0,0,0.06)', marginVertical: 4 }} />
          <TouchableOpacity onPress={() => navigate('/imos/login')} style={h.mobileItem}>
            <Text style={h.mobileItemText}>Sign In</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigate('/imos/demo')} style={h.mobileCta}>
            <Text style={h.mobileCtaText}>Get a Demo</Text>
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
    <View style={f.footer}>
      <View style={[f.inner, isDesktop && { maxWidth: 1200, flexDirection: 'row', justifyContent: 'space-between' }]}>
        <View style={f.brand}>
          <Image source={require('../../public/new-logo-512-transparent.png')} style={{ width: 48, height: 48, marginBottom: 8 }} resizeMode="contain" />
          <Text style={f.tagline}>The relationship engine for sales professionals.</Text>
          <Text style={f.sub}>Build a reputation that's yours forever.</Text>
        </View>
        <View style={[f.links, isDesktop && { flexDirection: 'row', gap: 48 }]}>
          <View style={f.col}>
            <Text style={f.colTitle}>Product</Text>
            <TouchableOpacity onPress={() => navigate('/imos/digital-card')}><Text style={f.link}>Digital Cards</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/reviews')}><Text style={f.link}>Personal Reviews</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/inbox')}><Text style={f.link}>Inbox</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/date-triggers')}><Text style={f.link}>Automations</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/leaderboard')}><Text style={f.link}>Leaderboards</Text></TouchableOpacity>
          </View>
          <View style={f.col}>
            <Text style={f.colTitle}>Company</Text>
            <TouchableOpacity onPress={() => navigate('/imos/organizations')}><Text style={f.link}>For Teams</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/pricing')}><Text style={f.link}>Pricing</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/privacy')}><Text style={f.link}>Privacy</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/terms')}><Text style={f.link}>Terms</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => { if (Platform.OS === 'web') window.location.href = 'mailto:forest@imonsocial.com'; }}>
              <Text style={f.link}>Contact</Text>
            </TouchableOpacity>
          </View>
          <View style={f.col}>
            <Text style={f.colTitle}>Get Started</Text>
            <TouchableOpacity onPress={() => navigate('/imos/demo')}><Text style={f.link}>Schedule a Demo</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/signup')}><Text style={f.link}>Start Free Trial</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/login')}><Text style={f.link}>Sign In</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/training')}><Text style={f.link}>Training</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => navigate('/imos/help')}><Text style={f.link}>Help Center</Text></TouchableOpacity>
          </View>
        </View>
      </View>
      <View style={f.bottom}>
        <Text style={f.copy}>&copy; 2026 i'M On Social. All rights reserved.</Text>
      </View>
    </View>
  );
}

const h = StyleSheet.create({
  outer: {
    backgroundColor: 'rgba(255,255,255,0.96)',
    ...(Platform.OS === 'web' ? { position: 'sticky' as any, top: 0, zIndex: 100, backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' } as any : {}),
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.06)',
  },
  inner: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 24, paddingVertical: 10, alignSelf: 'center', width: '100%' },
  navRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  navItem: { position: 'relative' as any },
  navTrigger: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  navLink: { fontSize: 14, fontWeight: '500', color: '#555' },
  ctaRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  signInBtn: { paddingVertical: 9, paddingHorizontal: 20, borderRadius: 980 },
  signInText: { fontSize: 14, fontWeight: '600', color: '#1D1D1F' },
  demoBtn: { backgroundColor: '#007AFF', paddingVertical: 9, paddingHorizontal: 22, borderRadius: 980 },
  demoBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  hamburger: { padding: 4 },
  mobileMenu: { backgroundColor: '#FFF', borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.06)', paddingHorizontal: 20, paddingBottom: 16 },
  mobileItem: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.04)' },
  mobileItemText: { fontSize: 16, fontWeight: '500', color: '#1D1D1F' },
  mobileCta: { backgroundColor: '#007AFF', borderRadius: 14, alignItems: 'center', marginTop: 12, paddingVertical: 14 },
  mobileCtaText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});

const dd = StyleSheet.create({
  wrap: {
    position: 'absolute' as any,
    top: '100%',
    left: '50%',
    ...(Platform.OS === 'web' ? { transform: 'translateX(-50%)' } as any : {}),
    paddingTop: 8,
    minWidth: 300,
    zIndex: 200,
  },
  inner: {
    backgroundColor: '#FFF',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.1)',
    padding: 10,
    ...(Platform.OS === 'web' ? { boxShadow: '0 20px 60px rgba(0,0,0,0.12)' } as any : { elevation: 12 }),
  },
  sectionLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1.2, color: '#888', paddingHorizontal: 14, paddingTop: 10, paddingBottom: 4 },
  item: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 10, paddingHorizontal: 14, borderRadius: 12 },
  icon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  text: {},
  name: { fontSize: 14, fontWeight: '600', color: '#111' },
  desc: { fontSize: 12, color: '#888', lineHeight: 16 },
});

const f = StyleSheet.create({
  footer: { backgroundColor: '#F8F9FB', borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.06)', paddingTop: 48 },
  inner: { paddingHorizontal: 24, alignSelf: 'center', width: '100%' },
  brand: { marginBottom: 32 },
  tagline: { fontSize: 14, color: '#555', lineHeight: 20, marginBottom: 4 },
  sub: { fontSize: 14, color: '#888', lineHeight: 20 },
  links: { gap: 24, marginBottom: 32 },
  col: { gap: 10 },
  colTitle: { fontSize: 12, fontWeight: '700', color: '#111', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 },
  link: { fontSize: 14, color: '#888' },
  bottom: { borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.06)', paddingVertical: 20, alignItems: 'center' },
  copy: { fontSize: 12, color: '#888' },
});
