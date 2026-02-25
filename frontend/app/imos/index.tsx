import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, Dimensions, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

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

// Phone Mockup Component with visible silver frame
function PhoneMockup() {
  return (
    <View style={phoneStyles.frame}>
      {/* Silver bezel frame */}
      <View style={phoneStyles.bezel}>
        {/* Notch */}
        <View style={phoneStyles.notch}>
          <View style={phoneStyles.notchPill} />
        </View>
        {/* Screen */}
        <View style={phoneStyles.screen}>
          {/* Status bar */}
          <View style={phoneStyles.statusBar}>
            <Text style={phoneStyles.statusTime}>9:41</Text>
            <View style={phoneStyles.statusIcons}>
              <Ionicons name="cellular" size={12} color="#FFF" />
              <Ionicons name="wifi" size={12} color="#FFF" />
              <Ionicons name="battery-full" size={12} color="#FFF" />
            </View>
          </View>
          {/* iMOs header */}
          <View style={phoneStyles.appHeader}>
            <Text style={phoneStyles.appName}>
              <Text style={{color:'#FF3B30'}}>i</Text>
              <Text style={{color:'#FFD60A'}}>M</Text>
              <Text style={{color:'#34C759'}}>O</Text>
              <Text style={{color:'#007AFF'}}>s</Text>
            </Text>
          </View>
          {/* Messages */}
          <View style={phoneStyles.messages}>
            <View style={phoneStyles.msgOut}>
              <Text style={phoneStyles.msgOutText}>Hey Sarah! It's been a year since you got your car! How's it treating you?</Text>
              <Text style={phoneStyles.msgTime}>10:32 AM</Text>
            </View>
            <View style={phoneStyles.msgIn}>
              <Text style={phoneStyles.msgInText}>Already a year?! It's been amazing! Best decision I made</Text>
              <Text style={phoneStyles.msgTimeIn}>10:34 AM</Text>
            </View>
            <View style={phoneStyles.msgOut}>
              <Text style={phoneStyles.msgOutText}>So glad! We're running a service special this month too</Text>
              <Text style={phoneStyles.msgTime}>10:35 AM</Text>
            </View>
            <View style={phoneStyles.msgIn}>
              <Text style={phoneStyles.msgInText}>Perfect timing — I'll stop by Saturday!</Text>
              <Text style={phoneStyles.msgTimeIn}>10:37 AM</Text>
            </View>
          </View>
          {/* Input bar */}
          <View style={phoneStyles.inputBar}>
            <View style={phoneStyles.inputField}>
              <Text style={phoneStyles.inputPlaceholder}>Message...</Text>
            </View>
            <View style={phoneStyles.sendBtn}>
              <Ionicons name="arrow-up" size={14} color="#FFF" />
            </View>
          </View>
        </View>
        {/* Home indicator */}
        <View style={phoneStyles.homeBar} />
      </View>
    </View>
  );
}

const phoneStyles = StyleSheet.create({
  frame: { alignItems: 'center', justifyContent: 'center' },
  bezel: {
    width: 220,
    height: 440,
    borderRadius: 32,
    backgroundColor: '#2A2A2E',
    borderWidth: 3,
    borderColor: '#888',
    padding: 6,
    // Shadow for depth
    ...(Platform.OS === 'web' ? {
      boxShadow: '0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1)',
    } : {}),
  },
  notch: { alignItems: 'center', paddingVertical: 4 },
  notchPill: { width: 60, height: 6, borderRadius: 3, backgroundColor: '#1A1A1E' },
  screen: {
    flex: 1,
    backgroundColor: '#0A0A12',
    borderRadius: 22,
    overflow: 'hidden',
    padding: 8,
  },
  statusBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 4, paddingBottom: 4 },
  statusTime: { fontSize: 10, fontWeight: '600', color: '#FFF' },
  statusIcons: { flexDirection: 'row', gap: 3 },
  appHeader: { alignItems: 'center', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#1C1C2E', marginBottom: 6 },
  appName: { fontSize: 14, fontWeight: '800' },
  messages: { flex: 1, gap: 6 },
  msgOut: { alignSelf: 'flex-end', backgroundColor: '#007AFF', borderRadius: 14, borderBottomRightRadius: 4, paddingHorizontal: 10, paddingVertical: 6, maxWidth: '82%' },
  msgOutText: { fontSize: 9, color: '#FFF', lineHeight: 13 },
  msgTime: { fontSize: 7, color: 'rgba(255,255,255,0.5)', alignSelf: 'flex-end', marginTop: 2 },
  msgIn: { alignSelf: 'flex-start', backgroundColor: '#2C2C3E', borderRadius: 14, borderBottomLeftRadius: 4, paddingHorizontal: 10, paddingVertical: 6, maxWidth: '82%' },
  msgInText: { fontSize: 9, color: '#FFF', lineHeight: 13 },
  msgTimeIn: { fontSize: 7, color: 'rgba(255,255,255,0.4)', marginTop: 2 },
  inputBar: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingTop: 6, borderTopWidth: 1, borderTopColor: '#1C1C2E' },
  inputField: { flex: 1, backgroundColor: '#1C1C2E', borderRadius: 14, paddingHorizontal: 10, paddingVertical: 5 },
  inputPlaceholder: { fontSize: 9, color: '#6E6E73' },
  sendBtn: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#007AFF', alignItems: 'center', justifyContent: 'center' },
  homeBar: { alignSelf: 'center', width: 80, height: 4, borderRadius: 2, backgroundColor: '#555', marginTop: 6 },
});

export default function ImosHubScreen() {
  const router = useRouter();
  const { width: screenWidth } = useWindowDimensions();
  const isDesktop = screenWidth > 900;
  const isTablet = screenWidth > 600 && screenWidth <= 900;

  const navigateTo = (path: string) => {
    router.push(path as any);
  };

  const contentMaxWidth = isDesktop ? 960 : isTablet ? 720 : undefined;

  return (
    <View style={styles.container}>
      <LinearGradient colors={['#0A0A1A', '#1A1A2E', '#0A0A1A']} style={StyleSheet.absoluteFill} />

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Centered content wrapper */}
        <View style={[styles.contentWrap, contentMaxWidth ? { maxWidth: contentMaxWidth, alignSelf: 'center', width: '100%' } : undefined]}>

          {/* Hero */}
          <View style={[styles.hero, isDesktop && styles.heroDesktop]}>
            <View style={[styles.heroText, isDesktop && { flex: 1, alignItems: 'flex-start' }]}>
              <View style={styles.logoBadge}>
                <Text style={styles.logoI}>i</Text>
                <Text style={styles.logoM}>M</Text>
                <Text style={styles.logoO}>O</Text>
                <Text style={styles.logoS}>s</Text>
              </View>
              <Text style={styles.tagline}>Relationship Management System</Text>
              <Text style={[styles.heroDesc, isDesktop && { textAlign: 'left' }]}>
                Empower your sales teams with tools that help them be the best in the business. Every customer relationship starts with a moment — iMOs ensures no moment is ever missed.
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

            {/* Phone Mockup - visible on tablet+ */}
            {(isDesktop || isTablet) && (
              <View style={styles.phoneWrap}>
                <PhoneMockup />
              </View>
            )}
          </View>

          {/* Value Props */}
          <View style={[styles.valueProps, isDesktop && styles.valuePropsDesktop]}>
            {[
              { icon: 'camera', color: '#34C759', title: 'Snap & Start', desc: 'One photo starts a lifetime of customer touchpoints' },
              { icon: 'repeat', color: '#007AFF', title: 'Never Forget', desc: 'Automated birthday, anniversary & sold date campaigns' },
              { icon: 'people', color: '#FF9500', title: 'Team Empowerment', desc: 'Tools that make your sales team unstoppable' },
              { icon: 'trending-up', color: '#AF52DE', title: 'Measurable Results', desc: 'More deals, better retention, real performance data' },
            ].map((p, i) => (
              <View key={i} style={[styles.valueProp, isDesktop && styles.valuePropDesktop]}>
                <View style={[styles.valueIcon, { backgroundColor: `${p.color}15` }]}>
                  <Ionicons name={p.icon as any} size={24} color={p.color} />
                </View>
                <Text style={styles.valueTitle}>{p.title}</Text>
                <Text style={styles.valueDesc}>{p.desc}</Text>
              </View>
            ))}
          </View>

          {/* Mobile Phone Mockup */}
          {!isDesktop && !isTablet && (
            <View style={styles.phoneMobileWrap}>
              <PhoneMockup />
            </View>
          )}

          {/* Page Directory */}
          {PUBLIC_PAGES.map((section) => (
            <View key={section.category} style={styles.section}>
              <View style={styles.sectionHeader}>
                <View style={[styles.sectionIcon, { backgroundColor: `${section.color}20` }]}>
                  <Ionicons name={section.icon as any} size={18} color={section.color} />
                </View>
                <Text style={styles.sectionTitle}>{section.category}</Text>
              </View>
              <View style={isDesktop ? styles.pageGridDesktop : undefined}>
                {section.pages.map((page) => (
                  <TouchableOpacity
                    key={page.path}
                    style={[styles.pageCard, isDesktop && styles.pageCardDesktop]}
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
              <Text style={[styles.fChar, { color: '#FF3B30' }]}>i</Text>
              <Text style={[styles.fChar, { color: '#FFD60A' }]}>M</Text>
              <Text style={[styles.fChar, { color: '#34C759' }]}>O</Text>
              <Text style={[styles.fChar, { color: '#007AFF' }]}>s</Text>
            </View>
            <Text style={styles.footerText}>Relationship Management System</Text>
            <Text style={styles.footerCopy}>&copy; {new Date().getFullYear()} iMOs. All rights reserved.</Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  scroll: { paddingBottom: 40 },
  contentWrap: { paddingHorizontal: 16 },
  // Hero
  hero: { alignItems: 'center', paddingTop: Platform.OS === 'web' ? 48 : 72, paddingBottom: 32 },
  heroDesktop: { flexDirection: 'row', alignItems: 'center', gap: 40, paddingTop: 60, paddingBottom: 48 },
  heroText: { alignItems: 'center' },
  logoBadge: { flexDirection: 'row', marginBottom: 8 },
  logoI: { fontSize: 48, fontWeight: '900', color: '#FF3B30' },
  logoM: { fontSize: 48, fontWeight: '900', color: '#FFD60A' },
  logoO: { fontSize: 48, fontWeight: '900', color: '#34C759' },
  logoS: { fontSize: 48, fontWeight: '900', color: '#007AFF' },
  tagline: { fontSize: 13, color: '#8E8E93', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 16 },
  heroDesc: { fontSize: 17, color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 26, maxWidth: 440, marginBottom: 28 },
  heroBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 28, borderRadius: 28,
  },
  heroBtnText: { fontSize: 16, fontWeight: '700', color: '#000' },
  phoneWrap: { alignItems: 'center' },
  phoneMobileWrap: { alignItems: 'center', paddingVertical: 24 },
  // Value Props
  valueProps: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12, marginBottom: 32 },
  valuePropsDesktop: { gap: 16 },
  valueProp: {
    width: '46%',
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
  },
  valuePropDesktop: { width: '22%' },
  valueIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  valueTitle: { fontSize: 15, fontWeight: '600', color: '#FFF', marginBottom: 4 },
  valueDesc: { fontSize: 12, color: '#8E8E93', lineHeight: 17 },
  // Sections
  section: { marginBottom: 24 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10, paddingLeft: 4 },
  sectionIcon: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  pageGridDesktop: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  pageCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#1C1C1E', borderRadius: 12, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  pageCardDesktop: { width: '48%', marginBottom: 0 },
  pageIcon: { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  pageInfo: { flex: 1 },
  pageTitle: { fontSize: 15, fontWeight: '600', color: '#FFF' },
  pageDesc: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  pageBadge: { backgroundColor: '#C9A96225', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, marginRight: 8 },
  pageBadgeText: { fontSize: 10, fontWeight: '600', color: '#C9A962' },
  // Contact CTA
  contactSection: { alignItems: 'center', paddingVertical: 40, marginTop: 8 },
  contactTitle: { fontSize: 24, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 10 },
  contactDesc: { fontSize: 14, color: '#8E8E93', textAlign: 'center', lineHeight: 21, maxWidth: 360, marginBottom: 24 },
  contactBtns: { flexDirection: 'row', gap: 12 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 12, paddingHorizontal: 24, borderRadius: 24 },
  primaryBtnText: { fontSize: 15, fontWeight: '600', color: '#000' },
  secondaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 12, paddingHorizontal: 20, borderRadius: 24, borderWidth: 1, borderColor: '#C9A96240' },
  secondaryBtnText: { fontSize: 15, fontWeight: '500', color: '#C9A962' },
  // Footer
  footer: { alignItems: 'center', paddingTop: 40, paddingBottom: 20, borderTopWidth: 1, borderTopColor: '#1C1C1E' },
  footerLogo: { flexDirection: 'row', marginBottom: 4 },
  fChar: { fontSize: 20, fontWeight: '800' },
  footerText: { fontSize: 11, color: '#6E6E73', letterSpacing: 1, marginBottom: 8 },
  footerCopy: { fontSize: 11, color: '#3A3A3C' },
});
