import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter } from './_components';

const REVIEW_FEATURES = [
  {
    icon: 'link',
    color: '#FFD60A',
    title: 'One Link, Every Review Site',
    desc: 'Send customers a single branded link that shows all your review platforms — Google, Yelp, Facebook, DealerRater, and more. No confusion, no friction.',
  },
  {
    icon: 'analytics',
    color: '#007AFF',
    title: 'Track Every Click',
    desc: 'Know which salesperson sent the link, which platform customers chose, and how many reviews you\'re generating — all in real time.',
  },
  {
    icon: 'shield-checkmark',
    color: '#34C759',
    title: 'Approval Before Publishing',
    desc: 'Every review submitted through your card or landing page goes to a pending queue. You approve what shows up on your public pages.',
  },
  {
    icon: 'card',
    color: '#AF52DE',
    title: 'Built Into Digital Cards',
    desc: 'Individual and dealership-level cards include a feedback section. Customers leave reviews right from your digital business card.',
  },
  {
    icon: 'chatbubble-ellipses',
    color: '#FF9500',
    title: 'Share via Text or Email',
    desc: 'One tap from My Account sends a pre-written review request to any customer via text or email with your personal tracking link.',
  },
  {
    icon: 'business',
    color: '#C9A962',
    title: 'Account-Level Dealership Card',
    desc: 'A branded public page for your dealership with team roster, approved testimonials, and a leave-a-review section. Perfect for managers to share.',
  },
];

const HOW_STEPS = [
  { step: '1', title: 'Configure your review links', desc: 'Add your Google, Yelp, Facebook, and other review platform URLs in Store Settings.' },
  { step: '2', title: 'Share with customers', desc: 'Tap "Share Review Link" from My Account. Send via text, email, or share the link however you want.' },
  { step: '3', title: 'Customers choose & review', desc: 'They see a clean branded page with all your review sites. One tap takes them directly to their preferred platform.' },
  { step: '4', title: 'Track & approve', desc: 'Monitor clicks per platform and per salesperson. Approve direct feedback before it shows on your public pages.' },
];

export default function ImosReviews() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const isWide = width > 1000;
  const maxW = isWide ? 1100 : isDesktop ? 900 : undefined;

  const navigate = (path: string) => router.push(path as any);

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

          {/* Hero */}
          <View style={[s.hero, isDesktop && { paddingTop: 72 }]}>
            <View style={s.heroIconWrap}>
              <Ionicons name="star" size={40} color="#FFD60A" />
            </View>
            <Text style={s.heroLabel}>REVIEWS & REPUTATION</Text>
            <Text style={[s.heroTitle, isDesktop && { fontSize: 48, lineHeight: 54 }]}>
              Turn Happy Customers Into{'\n'}
              <Text style={{ color: '#FFD60A' }}>5-Star Reviews.</Text>
            </Text>
            <Text style={[s.heroSub, isDesktop && { fontSize: 18, maxWidth: 560 }]}>
              One branded link. Every review site. Full tracking. Approval control. Built right into your digital cards and customer workflows.
            </Text>
            <View style={s.heroCTAs}>
              <TouchableOpacity style={s.primaryBtn} onPress={() => navigate('/imos/demo')} data-testid="reviews-demo-btn">
                <Ionicons name="calendar" size={20} color="#000" />
                <Text style={s.primaryBtnText}>Schedule a Demo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.outlineBtn} onPress={() => navigate('/review/imos-demo')} data-testid="reviews-preview-btn">
                <Ionicons name="eye" size={18} color="#FFD60A" />
                <Text style={s.outlineBtnText}>See Live Example</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Features Grid */}
          <View style={s.featuresSection}>
            <Text style={s.sectionLabel}>FEATURES</Text>
            <Text style={[s.sectionTitle, isDesktop && { fontSize: 32 }]}>
              Everything You Need to Build Your Reputation
            </Text>
            <View style={[s.featuresGrid, isDesktop && { flexDirection: 'row', flexWrap: 'wrap' }]}>
              {REVIEW_FEATURES.map((f, i) => (
                <View key={i} style={[s.featureCard, isDesktop && { width: '48%' }]}>
                  <View style={[s.featureIconWrap, { backgroundColor: `${f.color}12` }]}>
                    <Ionicons name={f.icon as any} size={24} color={f.color} />
                  </View>
                  <Text style={s.featureCardTitle}>{f.title}</Text>
                  <Text style={s.featureCardDesc}>{f.desc}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* How It Works */}
          <View style={s.howSection}>
            <Text style={s.sectionLabel}>HOW IT WORKS</Text>
            <Text style={[s.sectionTitle, isDesktop && { fontSize: 32 }]}>
              From Share to 5 Stars in 4 Steps
            </Text>
            <View style={[s.stepsContainer, isDesktop && { flexDirection: 'row' }]}>
              {HOW_STEPS.map((step, i) => (
                <View key={i} style={[s.stepCard, isDesktop && { flex: 1 }]}>
                  <View style={s.stepNumber}>
                    <Text style={s.stepNumberText}>{step.step}</Text>
                  </View>
                  <Text style={s.stepTitle}>{step.title}</Text>
                  <Text style={s.stepDesc}>{step.desc}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* Bottom CTA */}
          <View style={s.bottomCTA}>
            <Text style={[s.bottomTitle, isDesktop && { fontSize: 36 }]}>
              Start Collecting More Reviews Today
            </Text>
            <Text style={s.bottomSub}>
              Your customers are already happy. Give them the easiest path to telling the world.
            </Text>
            <View style={s.heroCTAs}>
              <TouchableOpacity style={s.primaryBtn} onPress={() => navigate('/imos/demo')} data-testid="reviews-bottom-demo-btn">
                <Ionicons name="calendar" size={20} color="#000" />
                <Text style={s.primaryBtnText}>Schedule a Demo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.outlineBtn} onPress={() => navigate('/imos/signup')} data-testid="reviews-bottom-trial-btn">
                <Text style={s.outlineBtnText}>Start Free Trial</Text>
                <Ionicons name="arrow-forward" size={16} color="#FFD60A" />
              </TouchableOpacity>
            </View>
          </View>

        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  scroll: { paddingBottom: 0 },

  hero: { alignItems: 'center', paddingTop: 48, paddingBottom: 40, paddingHorizontal: 20 },
  heroIconWrap: {
    width: 72, height: 72, borderRadius: 20, backgroundColor: 'rgba(255,214,10,0.1)',
    alignItems: 'center', justifyContent: 'center', marginBottom: 20, borderWidth: 1, borderColor: 'rgba(255,214,10,0.2)',
  },
  heroLabel: { fontSize: 11, fontWeight: '700', color: '#FFD60A', letterSpacing: 2, marginBottom: 16 },
  heroTitle: { fontSize: 32, fontWeight: '900', color: '#FFF', textAlign: 'center', lineHeight: 40, marginBottom: 20 },
  heroSub: { fontSize: 16, color: 'rgba(255,255,255,0.7)', textAlign: 'center', lineHeight: 24, maxWidth: 480, marginBottom: 32 },
  heroCTAs: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12 },
  primaryBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 28, borderRadius: 28,
  },
  primaryBtnText: { fontSize: 15, fontWeight: '700', color: '#000' },
  outlineBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 14, paddingHorizontal: 24, borderRadius: 28,
    borderWidth: 1, borderColor: 'rgba(255,214,10,0.3)',
  },
  outlineBtnText: { fontSize: 15, fontWeight: '600', color: '#FFD60A' },

  sectionLabel: { fontSize: 11, fontWeight: '700', color: '#C9A962', letterSpacing: 2, marginBottom: 12 },
  sectionTitle: { fontSize: 28, fontWeight: '800', color: '#FFF', textAlign: 'center', lineHeight: 36, marginBottom: 32 },

  featuresSection: { alignItems: 'center', paddingTop: 48, paddingHorizontal: 20 },
  featuresGrid: { gap: 16, width: '100%' },
  featureCard: {
    backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 16, padding: 24,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)',
  },
  featureIconWrap: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  featureCardTitle: { fontSize: 17, fontWeight: '700', color: '#FFF', marginBottom: 6 },
  featureCardDesc: { fontSize: 14, color: 'rgba(255,255,255,0.6)', lineHeight: 21 },

  howSection: { alignItems: 'center', paddingTop: 56, paddingHorizontal: 20 },
  stepsContainer: { gap: 16, width: '100%' },
  stepCard: {
    backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 16, padding: 24,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)', alignItems: 'center',
  },
  stepNumber: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,214,10,0.15)',
    alignItems: 'center', justifyContent: 'center', marginBottom: 12,
  },
  stepNumberText: { fontSize: 16, fontWeight: '800', color: '#FFD60A' },
  stepTitle: { fontSize: 16, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 6 },
  stepDesc: { fontSize: 13, color: 'rgba(255,255,255,0.55)', textAlign: 'center', lineHeight: 19 },

  bottomCTA: {
    alignItems: 'center', paddingVertical: 56, paddingHorizontal: 20, marginTop: 32,
    backgroundColor: 'rgba(255,214,10,0.03)', borderTopWidth: 1, borderColor: 'rgba(255,214,10,0.1)',
  },
  bottomTitle: { fontSize: 28, fontWeight: '800', color: '#FFF', textAlign: 'center', marginBottom: 12, lineHeight: 36 },
  bottomSub: { fontSize: 15, color: 'rgba(255,255,255,0.6)', textAlign: 'center', lineHeight: 22, maxWidth: 400, marginBottom: 28 },
});
