import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Dimensions, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

const { width, height } = Dimensions.get('window');

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
    title: 'iMOs',
    subtitle: 'Relationship Management System',
    content: [
      'Empower your sales teams with tools that help them be the best in the business.',
      'Every customer interaction starts with a relationship. iMOs ensures no moment is ever missed.',
    ],
    icon: 'diamond',
    iconColor: '#C9A962',
    gradient: ['#0A0A1A', '#1A1A2E'],
  },
  {
    id: 'problem',
    title: 'The Problem',
    subtitle: 'Your teams are losing customers',
    content: [
      'Sales teams forget to follow up. Customers feel forgotten.',
      'Managers have no visibility into team activity.',
      'Every missed touchpoint is a lost deal and a lost relationship.',
      'The average dealership loses 68% of customers after the first year due to poor follow-up.',
    ],
    icon: 'alert-circle',
    iconColor: '#FF3B30',
    gradient: ['#1A0A0A', '#2E1A1A'],
    stat: { value: '68%', label: 'of customers lost to poor follow-up' },
  },
  {
    id: 'solution',
    title: 'The iMOs Difference',
    subtitle: 'Automated relationship management that never forgets',
    content: [
      'Every customer gets the attention they deserve — automatically.',
      'From the snap of a photo to a lifetime of loyalty, iMOs handles the rest.',
    ],
    icon: 'flash',
    iconColor: '#C9A962',
    gradient: ['#0A0A1A', '#16213E'],
    features: [
      { icon: 'camera', text: 'Snap a photo, start a relationship' },
      { icon: 'chatbubbles', text: 'Automated follow-up sequences' },
      { icon: 'calendar', text: 'Never miss a birthday or anniversary' },
      { icon: 'trending-up', text: 'Real-time team performance tracking' },
    ],
  },
  {
    id: 'snap',
    title: 'It All Starts With a Snap',
    subtitle: 'From photo to lifelong customer in seconds',
    content: [
      '1. Your salesperson takes a congrats photo with the customer',
      '2. Creates a beautiful branded card they can share on social media',
      '3. Tags the customer with "Sold" — campaign starts automatically',
      '4. Customer receives personalized follow-ups for life',
      'One snap. Infinite touchpoints. Zero effort after the first moment.',
    ],
    icon: 'camera',
    iconColor: '#34C759',
    gradient: ['#0A1A0A', '#162E1A'],
  },
  {
    id: 'automation',
    title: 'Set It & Never Forget It',
    subtitle: 'Automated campaigns that build loyalty',
    content: [
      'Birthday messages that make customers feel remembered',
      'Anniversary follow-ups that keep your brand top-of-mind',
      'Holiday greetings that show you care beyond the sale',
      'Sold-date sequences that turn one deal into a lifetime relationship',
    ],
    icon: 'rocket',
    iconColor: '#007AFF',
    gradient: ['#0A0A1A', '#0A1A2E'],
    features: [
      { icon: 'gift', text: 'Birthdays & Anniversaries' },
      { icon: 'car-sport', text: 'Sold Date Campaigns' },
      { icon: 'snow', text: '14+ Holiday Templates' },
      { icon: 'repeat', text: 'Recurring Lifetime Sequences' },
    ],
  },
  {
    id: 'ai',
    title: 'AI That Works For You',
    subtitle: 'Meet Jessi — your team\'s AI assistant',
    content: [
      'AI-powered response suggestions that sound like your people wrote them',
      'Voice-to-text for quick notes on the lot',
      'Smart tagging and campaign enrollment — zero manual work',
      'Jessi learns your team\'s communication style and adapts',
    ],
    icon: 'sparkles',
    iconColor: '#AF52DE',
    gradient: ['#1A0A2E', '#0A0A1A'],
  },
  {
    id: 'managers',
    title: 'Built For Managers',
    subtitle: 'Complete visibility, zero micromanagement',
    content: [
      'Real-time leaderboards show who\'s crushing it',
      'Activity feeds track every customer touchpoint',
      'Broadcast messages to the entire team instantly',
      'Onboarding that gets new hires productive in days, not weeks',
    ],
    icon: 'shield-checkmark',
    iconColor: '#FF9500',
    gradient: ['#1A150A', '#2E1A0A'],
    stat: { value: '3x', label: 'faster new hire onboarding' },
  },
  {
    id: 'retention',
    title: 'The Bottom Line',
    subtitle: 'Better relationships = better business',
    content: [],
    icon: 'trophy',
    iconColor: '#FFD60A',
    gradient: ['#1A1A0A', '#2E2E0A'],
    features: [
      { icon: 'people', text: 'Better sales team retention — they love the tools' },
      { icon: 'heart', text: 'Better customer retention — they feel valued' },
      { icon: 'cash', text: 'More deals — automated follow-up converts' },
      { icon: 'time', text: 'Tasks never forgotten — accountability built in' },
      { icon: 'star', text: 'Better reviews — happy customers share their experience' },
      { icon: 'analytics', text: 'Data-driven decisions — know what works' },
    ],
  },
  {
    id: 'whitelabel',
    title: 'Your Brand. Our Platform.',
    subtitle: 'White-label ready for organizations',
    content: [
      'Deploy iMOs under your own brand for your entire organization.',
      'Custom branding, your logo, your colors — powered by iMOs.',
      'Every store, every team member, one unified platform.',
      'Scalable from a single store to a nationwide enterprise.',
    ],
    icon: 'business',
    iconColor: '#5AC8FA',
    gradient: ['#0A1520', '#0A0A1A'],
    features: [
      { icon: 'color-palette', text: 'Custom branding & colors' },
      { icon: 'globe', text: 'Custom domain support' },
      { icon: 'layers', text: 'Multi-store, multi-org hierarchy' },
      { icon: 'shield', text: 'Enterprise security & compliance' },
    ],
  },
  {
    id: 'cta',
    title: 'Ready to Transform\nYour Team?',
    subtitle: 'Join the most forward-thinking organizations in the business',
    content: [
      'See why leading organizations trust iMOs to build lasting customer relationships.',
    ],
    icon: 'arrow-forward-circle',
    iconColor: '#C9A962',
    gradient: ['#0A0A1A', '#1A1A2E'],
  },
];

export default function PresentationScreen() {
  const router = useRouter();
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(true);
  const slide = SLIDES[currentSlide];
  const progress = (currentSlide + 1) / SLIDES.length;

  const goNext = useCallback(() => {
    if (currentSlide < SLIDES.length - 1) setCurrentSlide(s => s + 1);
  }, [currentSlide]);

  const goPrev = useCallback(() => {
    if (currentSlide > 0) setCurrentSlide(s => s - 1);
  }, [currentSlide]);

  // Keyboard navigation for web
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); goNext(); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); goPrev(); }
      if (e.key === 'Escape') { router.back(); }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [goNext, goPrev, router]);

  return (
    <View style={styles.container}>
      <LinearGradient colors={slide.gradient as any} style={StyleSheet.absoluteFill} />

      {/* Top Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.closeBtn} data-testid="presentation-close">
          <Ionicons name="close" size={22} color="rgba(255,255,255,0.6)" />
        </TouchableOpacity>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
        </View>
        <Text style={styles.slideNum}>{currentSlide + 1}/{SLIDES.length}</Text>
      </View>

      {/* Slide Content */}
      <ScrollView contentContainerStyle={styles.slideScroll} showsVerticalScrollIndicator={false}>
        <View style={styles.slideBody}>
          {/* Icon */}
          <View style={[styles.iconWrap, { backgroundColor: `${slide.iconColor}15` }]}>
            <Ionicons name={slide.icon as any} size={52} color={slide.iconColor} />
          </View>

          {/* Title */}
          <Text style={styles.title}>{slide.title}</Text>
          {slide.subtitle && <Text style={[styles.subtitle, { color: slide.iconColor }]}>{slide.subtitle}</Text>}

          {/* Stat */}
          {slide.stat && (
            <View style={styles.statCard}>
              <Text style={[styles.statValue, { color: slide.iconColor }]}>{slide.stat.value}</Text>
              <Text style={styles.statLabel}>{slide.stat.label}</Text>
            </View>
          )}

          {/* Content */}
          {slide.content.map((line, i) => (
            <Text key={i} style={styles.contentLine}>{line}</Text>
          ))}

          {/* Features */}
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

          {/* CTA Slide */}
          {slide.id === 'cta' && (
            <View style={styles.ctaSection}>
              <TouchableOpacity style={styles.ctaButton} onPress={() => {
                if (Platform.OS === 'web') window.open('mailto:forest@imosapp.com?subject=iMOs%20Demo%20Request', '_blank');
              }} data-testid="request-demo-btn">
                <Ionicons name="mail" size={20} color="#000" />
                <Text style={styles.ctaButtonText}>Request a Demo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.ctaSecondary} onPress={() => {
                if (Platform.OS === 'web') window.open(`${process.env.REACT_APP_BACKEND_URL || ''}/imos`, '_blank');
              }}>
                <Text style={styles.ctaSecondaryText}>Learn More</Text>
                <Ionicons name="arrow-forward" size={16} color="#C9A962" />
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Navigation */}
      <View style={styles.navBar}>
        <TouchableOpacity
          style={[styles.navBtn, currentSlide === 0 && { opacity: 0.3 }]}
          onPress={goPrev}
          disabled={currentSlide === 0}
          data-testid="slide-prev"
        >
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>

        {/* Dots */}
        <View style={styles.dotsRow}>
          {SLIDES.map((_, i) => (
            <TouchableOpacity key={i} onPress={() => setCurrentSlide(i)}>
              <View style={[styles.dot, i === currentSlide && { backgroundColor: slide.iconColor, width: 20 }]} />
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          style={[styles.navBtn, currentSlide === SLIDES.length - 1 && { opacity: 0.3 }]}
          onPress={goNext}
          disabled={currentSlide === SLIDES.length - 1}
          data-testid="slide-next"
        >
          <Ionicons name="chevron-forward" size={24} color="#FFF" />
        </TouchableOpacity>
      </View>

      {/* Keyboard hint on web */}
      {Platform.OS === 'web' && (
        <Text style={styles.keyHint}>Use arrow keys to navigate</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: Platform.OS === 'web' ? 20 : 56,
    paddingBottom: 8,
    gap: 12,
    zIndex: 10,
  },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  progressBar: {
    flex: 1,
    height: 3,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: { height: '100%', backgroundColor: '#C9A962', borderRadius: 2 },
  slideNum: { color: 'rgba(255,255,255,0.4)', fontSize: 13, fontWeight: '500', minWidth: 36, textAlign: 'right' },
  slideScroll: { flexGrow: 1, justifyContent: 'center', paddingBottom: 20 },
  slideBody: { alignItems: 'center', paddingHorizontal: 28, paddingTop: 16 },
  iconWrap: {
    width: 96,
    height: 96,
    borderRadius: 48,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  title: { fontSize: 32, fontWeight: '800', color: '#FFF', textAlign: 'center', marginBottom: 8, lineHeight: 38 },
  subtitle: { fontSize: 16, fontWeight: '600', textAlign: 'center', marginBottom: 20 },
  statCard: {
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    width: '100%',
    maxWidth: 300,
  },
  statValue: { fontSize: 48, fontWeight: '900' },
  statLabel: { fontSize: 14, color: 'rgba(255,255,255,0.7)', marginTop: 4 },
  contentLine: { fontSize: 16, color: 'rgba(255,255,255,0.85)', textAlign: 'center', lineHeight: 24, marginBottom: 10, maxWidth: 400 },
  featureGrid: { width: '100%', maxWidth: 400, gap: 10, marginTop: 12 },
  featureCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
  },
  featureIcon: { width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  featureText: { fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 },
  ctaSection: { alignItems: 'center', marginTop: 28, gap: 16 },
  ctaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#C9A962',
    paddingVertical: 16,
    paddingHorizontal: 36,
    borderRadius: 30,
  },
  ctaButtonText: { fontSize: 17, fontWeight: '700', color: '#000' },
  ctaSecondary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  ctaSecondaryText: { fontSize: 15, color: '#C9A962', fontWeight: '500' },
  navBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingVertical: 16,
    paddingBottom: Platform.OS === 'web' ? 20 : 40,
  },
  navBtn: { padding: 8 },
  dotsRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.25)' },
  keyHint: {
    position: 'absolute',
    bottom: 6,
    left: 0,
    right: 0,
    textAlign: 'center',
    fontSize: 11,
    color: 'rgba(255,255,255,0.2)',
  },
});
