import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

type Slide = {
  id: string;
  title: string;
  subtitle?: string;
  content: string[];
  icon: string;
  accentColor: string;
  accentBg: string;
  stat?: { value: string; label: string };
  features?: { icon: string; text: string; desc?: string }[];
};

const SLIDES: Slide[] = [
  {
    id: 'intro',
    title: "i'M On Social",
    subtitle: 'The Relationship Engine for Sales Professionals',
    content: [
      'Your customers remember people, not companies.',
      "i'M On Social gives every salesperson a digital presence that builds trust, drives reviews, and keeps customers connected long after the sale.",
    ],
    icon: 'diamond',
    accentColor: '#007AFF',
    accentBg: 'rgba(0,122,255,.08)',
  },
  {
    id: 'problem',
    title: 'The Problem',
    subtitle: 'Relationships die after the transaction',
    content: [
      'The deal closes. The salesperson moves on. The customer is forgotten.',
      "Reviews go to the dealership, not the person who earned them. Follow-up is generic or nonexistent. There's no system to stay connected.",
    ],
    icon: 'alert-circle',
    accentColor: '#FF3B30',
    accentBg: 'rgba(255,59,48,.08)',
    stat: { value: '68%', label: 'of customers leave due to perceived indifference' },
  },
  {
    id: 'solution',
    title: 'The Solution',
    subtitle: "Give every person their own brand",
    content: [
      "i'M On Social is a structured social ecosystem. Organizations deploy it. Teams use it. Individuals own it.",
      'One platform that connects digital cards, personal reviews, automated follow-up, and AI — all under your brand.',
    ],
    icon: 'layers',
    accentColor: '#007AFF',
    accentBg: 'rgba(0,122,255,.08)',
    features: [
      { icon: 'business', text: 'Organizations', desc: 'Deploy across stores and teams' },
      { icon: 'people', text: 'Teams', desc: 'Shared visibility, unified brand' },
      { icon: 'person', text: 'Individuals', desc: 'Own their digital reputation' },
    ],
  },
  {
    id: 'digital-card',
    title: 'Digital Business Cards',
    subtitle: 'More than a card — it\'s a relationship starter',
    content: [
      'Every team member gets a shareable digital card with their photo, bio, social links, personal reviews, and a QR code.',
      'Customers save it, share it, and come back to it. Your people become discoverable.',
    ],
    icon: 'card',
    accentColor: '#5856D6',
    accentBg: 'rgba(88,86,214,.08)',
    features: [
      { icon: 'qr-code', text: 'Instant QR sharing' },
      { icon: 'star', text: 'Personal reviews built in' },
      { icon: 'share-social', text: 'All social links in one place' },
      { icon: 'download', text: 'Save to contacts (VCF)' },
    ],
  },
  {
    id: 'reviews',
    title: 'Personal Reviews',
    subtitle: 'Reputation that travels with you',
    content: [
      "Google reviews belong to the company. Personal reviews belong to the person who earned them.",
      "They live on the salesperson's digital card. They build credibility. They follow you — even if you change stores.",
    ],
    icon: 'star',
    accentColor: '#FF9500',
    accentBg: 'rgba(255,149,0,.08)',
    stat: { value: '4.2x', label: 'more trust when reviews are tied to a person' },
  },
  {
    id: 'automation',
    title: 'Nobody Gets Forgotten',
    subtitle: 'Automated campaigns that build loyalty',
    content: [
      'Birthday messages. Anniversary follow-ups. Sold-date sequences.',
      'Every customer feels remembered — without any manual effort from your team.',
    ],
    icon: 'rocket',
    accentColor: '#34C759',
    accentBg: 'rgba(52,199,89,.08)',
    features: [
      { icon: 'gift', text: 'Birthday & anniversary cards' },
      { icon: 'car-sport', text: 'Sold-date follow-up sequences' },
      { icon: 'pricetags', text: 'Tag-triggered workflows' },
      { icon: 'repeat', text: 'Lifetime engagement on autopilot' },
    ],
  },
  {
    id: 'congrats',
    title: 'Congrats Cards',
    subtitle: "Not 'Leave a Review' — it's 'We Appreciate You'",
    content: [
      'When a sale happens, send a branded congrats card. The customer lands on a celebration page with social links, Google review prompts, and a personal thank you.',
      'It feels intentional. Human. Shareable.',
    ],
    icon: 'heart',
    accentColor: '#FF2D55',
    accentBg: 'rgba(255,45,85,.08)',
  },
  {
    id: 'ai',
    title: 'AI That Works For You',
    subtitle: "Meet Jessi — your team's AI assistant",
    content: [
      'AI-powered message suggestions that sound like your people wrote them.',
      'Voice-to-text for quick notes. Smart tagging. Campaign enrollment.',
      "Jessi learns each person's communication style and adapts.",
    ],
    icon: 'sparkles',
    accentColor: '#AF52DE',
    accentBg: 'rgba(175,82,222,.08)',
  },
  {
    id: 'whitelabel',
    title: 'Your Brand. Our Engine.',
    subtitle: 'White-label ready for organizations',
    content: [
      "Deploy i'M On Social under your own brand. Your logo, your colors, your domain.",
      'Every account, every team member, one unified platform — powered by our infrastructure.',
    ],
    icon: 'color-palette',
    accentColor: '#5AC8FA',
    accentBg: 'rgba(90,200,250,.08)',
    features: [
      { icon: 'brush', text: 'Custom branding & colors' },
      { icon: 'globe', text: 'Custom domain support' },
      { icon: 'shield-checkmark', text: 'Enterprise security' },
      { icon: 'analytics', text: 'Org-wide analytics & reporting' },
    ],
  },
  {
    id: 'cta',
    title: "Ready to Own\nYour Reputation?",
    subtitle: 'The new way to be on social starts here',
    content: [
      "See why forward-thinking organizations trust i'M On Social to give their people the tools to build lasting customer relationships.",
    ],
    icon: 'arrow-forward-circle',
    accentColor: '#007AFF',
    accentBg: 'rgba(0,122,255,.08)',
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
      {/* Top Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.push('/imos' as any)} style={styles.closeBtn} data-testid="presentation-close">
          <Ionicons name="close" size={22} color="#86868B" />
        </TouchableOpacity>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${progress * 100}%`, backgroundColor: slide.accentColor }]} />
        </View>
        <Text style={styles.slideNum}>{currentSlide + 1}/{SLIDES.length}</Text>
      </View>

      {/* Slide Content */}
      <ScrollView contentContainerStyle={styles.slideScroll} showsVerticalScrollIndicator={false}>
        <View style={[styles.slideBody, isWide && { maxWidth: 660, alignSelf: 'center', width: '100%' }]}>
          <View style={[styles.iconWrap, { backgroundColor: slide.accentBg }]}>
            <Ionicons name={slide.icon as any} size={48} color={slide.accentColor} />
          </View>

          <Text style={styles.title}>{slide.title}</Text>

          {slide.subtitle && (
            <Text style={[styles.subtitle, { color: slide.accentColor }]}>{slide.subtitle}</Text>
          )}

          {slide.stat && (
            <View style={[styles.statCard, { borderColor: `${slide.accentColor}20` }]}>
              <Text style={[styles.statValue, { color: slide.accentColor }]}>{slide.stat.value}</Text>
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
                  <View style={[styles.featureIcon, { backgroundColor: slide.accentBg }]}>
                    <Ionicons name={f.icon as any} size={20} color={slide.accentColor} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.featureText}>{f.text}</Text>
                    {f.desc && <Text style={styles.featureDesc}>{f.desc}</Text>}
                  </View>
                </View>
              ))}
            </View>
          )}

          {slide.id === 'cta' && (
            <View style={styles.ctaSection}>
              <TouchableOpacity style={styles.ctaButton} onPress={() => {
                if (Platform.OS === 'web') window.location.href = "mailto:forest@imonsocial.com?subject=iM%20On%20Social%20Demo%20Request";
              }} data-testid="request-demo-btn">
                <Ionicons name="mail" size={20} color="#FFF" />
                <Text style={styles.ctaButtonText}>Request a Demo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.ctaSecondary} onPress={() => {
                if (Platform.OS === 'web') window.location.href = 'https://app.imonsocial.com/auth/signup';
              }} data-testid="start-trial-btn">
                <Text style={styles.ctaSecondaryText}>Start Free Trial</Text>
                <Ionicons name="arrow-forward" size={16} color="#007AFF" />
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Navigation */}
      <View style={styles.navBar}>
        <TouchableOpacity style={[styles.navBtn, currentSlide === 0 && { opacity: 0.25 }]} onPress={goPrev} disabled={currentSlide === 0} data-testid="slide-prev">
          <Ionicons name="chevron-back" size={24} color="#3A3A3C" />
        </TouchableOpacity>
        <View style={styles.dotsRow}>
          {SLIDES.map((_, i) => (
            <TouchableOpacity key={i} onPress={() => setCurrentSlide(i)}>
              <View style={[styles.dot, i === currentSlide && { backgroundColor: slide.accentColor, width: 20 }]} />
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity style={[styles.navBtn, currentSlide === SLIDES.length - 1 && { opacity: 0.25 }]} onPress={goNext} disabled={currentSlide === SLIDES.length - 1} data-testid="slide-next">
          <Ionicons name="chevron-forward" size={24} color="#3A3A3C" />
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
  closeBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F5F5F7', alignItems: 'center', justifyContent: 'center' },
  progressBar: { flex: 1, height: 3, backgroundColor: '#F0F0F5', borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 2 },
  slideNum: { color: '#AEAEB2', fontSize: 13, fontWeight: '500', minWidth: 36, textAlign: 'right' },
  slideScroll: { flexGrow: 1, justifyContent: 'center', paddingBottom: 20 },
  slideBody: { alignItems: 'center', paddingHorizontal: 28, paddingTop: 16 },
  iconWrap: { width: 88, height: 88, borderRadius: 44, alignItems: 'center', justifyContent: 'center', marginBottom: 24 },
  title: { fontSize: 34, fontWeight: '800', color: '#1D1D1F', textAlign: 'center', marginBottom: 8, lineHeight: 40, letterSpacing: -0.5 },
  subtitle: { fontSize: 17, fontWeight: '600', textAlign: 'center', marginBottom: 24 },
  statCard: { alignItems: 'center', backgroundColor: '#F8F9FB', borderRadius: 16, padding: 20, marginBottom: 20, width: '100%', maxWidth: 320, borderWidth: 1 },
  statValue: { fontSize: 52, fontWeight: '900', letterSpacing: -1 },
  statLabel: { fontSize: 14, color: '#6E6E73', marginTop: 4, textAlign: 'center' },
  contentLine: { fontSize: 16, color: '#3A3A3C', textAlign: 'center', lineHeight: 26, marginBottom: 12, maxWidth: 480 },
  featureGrid: { width: '100%', maxWidth: 440, gap: 10, marginTop: 16 },
  featureCard: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: '#F8F9FB', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#F0F0F5' },
  featureIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  featureText: { fontSize: 15, color: '#1D1D1F', fontWeight: '600' },
  featureDesc: { fontSize: 13, color: '#6E6E73', marginTop: 2 },
  ctaSection: { alignItems: 'center', marginTop: 32, gap: 16 },
  ctaButton: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#007AFF', paddingVertical: 16, paddingHorizontal: 40, borderRadius: 980 },
  ctaButtonText: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  ctaSecondary: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  ctaSecondaryText: { fontSize: 15, color: '#007AFF', fontWeight: '600' },
  navBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 24, paddingVertical: 16, paddingBottom: Platform.OS === 'web' ? 20 : 40, borderTopWidth: 1, borderTopColor: '#F0F0F5' },
  navBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#F5F5F7', alignItems: 'center', justifyContent: 'center' },
  dotsRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D1D1D6' },
  keyHint: { position: 'absolute', bottom: 6, left: 0, right: 0, textAlign: 'center', fontSize: 11, color: '#D1D1D6' },
});
