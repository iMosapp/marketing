import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

type Slide = {
  id: string;
  title: string;
  subtitle?: string;
  content: string[];
  icon: string;
  iconColor: string;
  gradient: [string, string];
  stat?: { value: string; label: string };
  features?: { icon: string; text: string }[];
};

const SLIDES: Slide[] = [
  {
    id: 'intro',
    title: "i'M On Social",
    subtitle: 'Meet the New Way to Be On Social.',
    content: [
      "i'M On Social is a Social Relationship OS that gives organizations, teams, and individuals control of their digital presence, reviews, and customer connections.",
      'Own your reputation. Build your credibility. Connect every touchpoint under one social presence.',
    ],
    icon: 'diamond',
    iconColor: '#007AFF',
    gradient: ['#0A0A1A', '#1A1A2E'],
  },
  {
    id: 'problem',
    title: 'The Old World',
    subtitle: 'People disappear after the transaction',
    content: [
      'The customer buys. The salesperson moves on. The relationship fades.',
      'Reviews go to the company. Social profiles live scattered. Digital cards are static.',
      'Follow-up feels generic. Nobody feels remembered.',
    ],
    icon: 'alert-circle',
    iconColor: '#FF3B30',
    gradient: ['#1A0A0A', '#2E1A1A'],
    stat: { value: '68%', label: 'of customers lost to poor follow-up' },
  },
  {
    id: 'shift',
    title: 'The Shift',
    subtitle: "It's about ownership of reputation",
    content: [
      'Every organization. Every team. Every individual.',
      'All under one structured social ecosystem.',
      "i'M On Social",
    ],
    icon: 'swap-horizontal',
    iconColor: '#007AFF',
    gradient: ['#0A0A1A', '#16213E'],
    features: [
      { icon: 'business', text: 'Organizations  - structure teams, track reputation' },
      { icon: 'people', text: 'Teams  - shared visibility, unified brand' },
      { icon: 'person', text: 'Individuals  - their own digital brand' },
    ],
  },
  {
    id: 'experience',
    title: 'The Core Experience',
    subtitle: 'Not "Leave a Review"  - it\'s "We Appreciate You"',
    content: [
      '1. A sale happens',
      '2. A Congrats Card is sent',
      '3. Customer lands on a branded page with social links, Google reviews, and direct feedback',
      '4. It feels celebratory. Intentional. Human.',
    ],
    icon: 'heart',
    iconColor: '#FF2D55',
    gradient: ['#2E0A1A', '#1A0A1A'],
  },
  {
    id: 'power',
    title: 'Personal Reviews',
    subtitle: 'Reputation that\'s portable',
    content: [
      'Direct feedback that lives on your digital business card.',
      'Builds personal credibility. Strengthens your brand.',
      'Stays with you  - even if you switch stores or industries.',
    ],
    icon: 'star',
    iconColor: '#FFD60A',
    gradient: ['#1A1A0A', '#2E2E0A'],
    features: [
      { icon: 'card', text: 'Reviews live on your digital card' },
      { icon: 'shield-checkmark', text: 'Personal credibility that travels' },
      { icon: 'trending-up', text: 'Strengthens your individual brand' },
    ],
  },
  {
    id: 'automation',
    title: 'Nobody Gets Forgotten',
    subtitle: 'Automated campaigns that build loyalty',
    content: [
      'Birthday messages. Anniversary follow-ups. Holiday greetings.',
      'Sold-date sequences that turn one deal into a lifetime relationship.',
      'Customers feel remembered  - without any manual effort.',
    ],
    icon: 'rocket',
    iconColor: '#007AFF',
    gradient: ['#0A0A1A', '#0A1A2E'],
    features: [
      { icon: 'gift', text: 'Birthdays & Anniversaries' },
      { icon: 'car-sport', text: 'Sold Date Campaigns' },
      { icon: 'pricetags', text: 'Tag-triggered workflows' },
      { icon: 'repeat', text: 'Lifetime engagement sequences' },
    ],
  },
  {
    id: 'ai',
    title: 'AI That Works For You',
    subtitle: "Meet Jessi  - your team's AI assistant",
    content: [
      'AI-powered response suggestions that sound like your people wrote them.',
      'Voice-to-text for quick notes. Smart tagging and campaign enrollment.',
      "Jessi learns your team's communication style and adapts.",
    ],
    icon: 'sparkles',
    iconColor: '#AF52DE',
    gradient: ['#1A0A2E', '#0A0A1A'],
  },
  {
    id: 'trust',
    title: 'The Bigger Picture',
    subtitle: 'AI replaces transactions. Trust still wins.',
    content: [],
    icon: 'trophy',
    iconColor: '#FFD60A',
    gradient: ['#1A1A0A', '#2E2E0A'],
    features: [
      { icon: 'eye', text: 'Visibility  - be seen by every customer' },
      { icon: 'shield-checkmark', text: 'Credibility  - personal reviews build trust' },
      { icon: 'key', text: 'Ownership  - your reputation is yours' },
      { icon: 'infinite', text: 'Continuity  - it moves with you forever' },
      { icon: 'heart', text: 'Customers never forget the person' },
      { icon: 'trending-up', text: 'Your brand grows with every interaction' },
    ],
  },
  {
    id: 'whitelabel',
    title: 'Your Brand. Our Platform.',
    subtitle: 'White-label ready for organizations',
    content: [
      "Deploy i'M On Social under your own brand for your entire organization.",
      "Custom branding, your logo, your colors  - powered by i'M On Social.",
      'Every account, every team member, one unified platform.',
    ],
    icon: 'business',
    iconColor: '#5AC8FA',
    gradient: ['#0A1520', '#0A0A1A'],
    features: [
      { icon: 'color-palette', text: 'Custom branding & colors' },
      { icon: 'globe', text: 'Custom domain support' },
      { icon: 'layers', text: 'Multi-account, multi-org hierarchy' },
      { icon: 'shield', text: 'Enterprise security & compliance' },
    ],
  },
  {
    id: 'cta',
    title: 'Ready to Own\nYour Reputation?',
    subtitle: 'The new way to be on social starts here',
    content: [
      "See why forward-thinking organizations trust i'M On Social to give their people the tools to build lasting relationships.",
    ],
    icon: 'arrow-forward-circle',
    iconColor: '#007AFF',
    gradient: ['#0A0A1A', '#1A1A2E'],
  },
];

export default function SalesPresentationScreen() {
  const router = useRouter();
  const [currentSlide, setCurrentSlide] = useState(0);
  const slide = SLIDES[currentSlide];
  const progress = (currentSlide + 1) / SLIDES.length;
  const { width: screenW } = useWindowDimensions();
  const isWide = screenW > 700;

  const goNext = useCallback(() => {
    if (currentSlide < SLIDES.length - 1) setCurrentSlide(s => s + 1);
  }, [currentSlide]);

  const goPrev = useCallback(() => {
    if (currentSlide > 0) setCurrentSlide(s => s - 1);
  }, [currentSlide]);

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); goNext(); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); goPrev(); }
      if (e.key === 'Escape') { router.push('/imos' as any); }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [goNext, goPrev, router]);

  return (
    <View style={styles.container}>
      <LinearGradient colors={slide.gradient as any} style={StyleSheet.absoluteFill} />

      {/* Top Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.push('/imos' as any)} style={styles.closeBtn} data-testid="presentation-close">
          <Ionicons name="close" size={22} color="rgba(255,255,255,0.6)" />
        </TouchableOpacity>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
        </View>
        <Text style={styles.slideNum}>{currentSlide + 1}/{SLIDES.length}</Text>
      </View>

      {/* Slide Content */}
      <ScrollView contentContainerStyle={styles.slideScroll} showsVerticalScrollIndicator={false}>
        <View style={[styles.slideBody, isWide && { maxWidth: 640, alignSelf: 'center', width: '100%' }]}>
          <View style={[styles.iconWrap, { backgroundColor: `${slide.iconColor}15` }]}>
            <Ionicons name={slide.icon as any} size={52} color={slide.iconColor} />
          </View>
          <Text style={styles.title}>{slide.title}</Text>
          {slide.subtitle && <Text style={[styles.subtitle, { color: slide.iconColor }]}>{slide.subtitle}</Text>}
          {slide.stat && (
            <View style={styles.statCard}>
              <Text style={[styles.statValue, { color: slide.iconColor }]}>{slide.stat.value}</Text>
              <Text style={styles.statLabel}>{slide.stat.label}</Text>
            </View>
          )}
          {slide.content.map((line, i) => (
            <Text key={i} style={styles.contentLine}>{line}</Text>
          ))}
          {slide.features && (
            <View style={styles.featureGrid}>
              {slide.features.map((f, i) => (
                <View key={i} style={styles.featureCard}>
                  <View style={[styles.featureIcon, { backgroundColor: `${slide.iconColor}12` }]}>
                    <Ionicons name={f.icon as any} size={22} color={slide.iconColor} />
                  </View>
                  <Text style={styles.featureText}>{f.text}</Text>
                </View>
              ))}
            </View>
          )}
          {slide.id === 'cta' && (
            <View style={styles.ctaSection}>
              <TouchableOpacity style={styles.ctaButton} onPress={() => {
                if (Platform.OS === 'web') window.location.href = "mailto:forest@imonsocial.com?subject=iM%20On%20Social%20Demo%20Request";
              }} data-testid="request-demo-btn">
                <Ionicons name="mail" size={20} color="#000" />
                <Text style={styles.ctaButtonText}>Request a Demo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.ctaSecondary} onPress={() => router.push('/imos' as any)}>
                <Text style={styles.ctaSecondaryText}>i'M On Social</Text>
                <Ionicons name="arrow-forward" size={16} color="#007AFF" />
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Navigation */}
      <View style={styles.navBar}>
        <TouchableOpacity style={[styles.navBtn, currentSlide === 0 && { opacity: 0.3 }]} onPress={goPrev} disabled={currentSlide === 0} data-testid="slide-prev">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={styles.dotsRow}>
          {SLIDES.map((_, i) => (
            <TouchableOpacity key={i} onPress={() => setCurrentSlide(i)}>
              <View style={[styles.dot, i === currentSlide && { backgroundColor: slide.iconColor, width: 20 }]} />
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity style={[styles.navBtn, currentSlide === SLIDES.length - 1 && { opacity: 0.3 }]} onPress={goNext} disabled={currentSlide === SLIDES.length - 1} data-testid="slide-next">
          <Ionicons name="chevron-forward" size={24} color="#FFF" />
        </TouchableOpacity>
      </View>

      {Platform.OS === 'web' && (
        <Text style={styles.keyHint}>Use arrow keys to navigate</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  topBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingTop: Platform.OS === 'web' ? 20 : 56, paddingBottom: 8, gap: 12, zIndex: 10 },
  closeBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.08)', alignItems: 'center', justifyContent: 'center' },
  progressBar: { flex: 1, height: 3, backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: '#007AFF', borderRadius: 2 },
  slideNum: { color: 'rgba(255,255,255,0.4)', fontSize: 13, fontWeight: '500', minWidth: 36, textAlign: 'right' },
  slideScroll: { flexGrow: 1, justifyContent: 'center', paddingBottom: 20 },
  slideBody: { alignItems: 'center', paddingHorizontal: 28, paddingTop: 16 },
  iconWrap: { width: 96, height: 96, borderRadius: 48, alignItems: 'center', justifyContent: 'center', marginBottom: 24 },
  title: { fontSize: 32, fontWeight: '800', color: '#1D1D1F', textAlign: 'center', marginBottom: 8, lineHeight: 38 },
  subtitle: { fontSize: 16, fontWeight: '600', textAlign: 'center', marginBottom: 20 },
  statCard: { alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.06)', borderRadius: 16, padding: 20, marginBottom: 20, width: '100%', maxWidth: 300 },
  statValue: { fontSize: 48, fontWeight: '900' },
  statLabel: { fontSize: 14, color: '#6E6E73', marginTop: 4 },
  contentLine: { fontSize: 16, color: 'rgba(255,255,255,0.85)', textAlign: 'center', lineHeight: 24, marginBottom: 10, maxWidth: 400 },
  featureGrid: { width: '100%', maxWidth: 400, gap: 10, marginTop: 12 },
  featureCard: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: 'rgba(0,0,0,0.03)', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)' },
  featureIcon: { width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  featureText: { fontSize: 15, color: '#1D1D1F', fontWeight: '500', flex: 1 },
  ctaSection: { alignItems: 'center', marginTop: 28, gap: 16 },
  ctaButton: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#007AFF', paddingVertical: 16, paddingHorizontal: 36, borderRadius: 30 },
  ctaButtonText: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  ctaSecondary: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  ctaSecondaryText: { fontSize: 15, color: '#007AFF', fontWeight: '500' },
  navBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 24, paddingVertical: 16, paddingBottom: Platform.OS === 'web' ? 20 : 40 },
  navBtn: { padding: 8 },
  dotsRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.25)' },
  keyHint: { position: 'absolute', bottom: 6, left: 0, right: 0, textAlign: 'center', fontSize: 11, color: 'rgba(255,255,255,0.2)' },
});
