import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter } from './_components';

const HERO_FEATURES = [
  { icon: 'card', color: '#007AFF', label: 'Digital Cards' },
  { icon: 'star', color: '#FFD60A', label: 'Personal Reviews' },
  { icon: 'share-social', color: '#34C759', label: 'Social Links' },
  { icon: 'camera', color: '#C9A962', label: 'Congrats Cards' },
  { icon: 'rocket', color: '#FF9500', label: 'Campaigns' },
  { icon: 'trophy', color: '#AF52DE', label: 'Reputation' },
];

const STATS = [
  { value: 'Own', label: 'your reputation — it moves with you, wherever you go' },
  { value: 'Build', label: 'personal credibility that outlasts any company' },
  { value: 'Connect', label: 'every customer touchpoint under one social presence' },
];

const HOW_IT_WORKS = [
  {
    tag: 'ORGANIZATIONS',
    title: 'Structure Your Entire Social Presence.',
    desc: 'Manage teams, accounts, and individuals under one roof. Track review performance, social engagement, and reputation data across your entire organization.',
    bullets: ['Team & account management', 'Reputation data at every level', 'Unified social presence'],
    icon: 'business',
    color: '#007AFF',
  },
  {
    tag: 'INDIVIDUALS',
    title: 'Every Person Gets Their Own Brand.',
    desc: 'Digital business card. Review profile. Social links. Personal rating. Customer feedback history. No more hiding behind the company logo.',
    bullets: ['Personal digital card & review profile', 'Portable reputation that stays with you', 'Direct customer feedback history'],
    icon: 'person',
    color: '#C9A962',
  },
  {
    tag: 'THE EXPERIENCE',
    title: 'Not "Leave a Review." It\'s "We Appreciate You."',
    desc: 'A sale happens. A Congrats Card is sent. The customer lands on a branded page with social links, Google reviews, direct feedback, and a future engagement path. It feels celebratory. Intentional. Human.',
    bullets: ['Branded celebratory experience', 'All social links in one place', 'Google review + direct feedback'],
    icon: 'heart',
    color: '#FF2D55',
  },
  {
    tag: 'PERSONAL REVIEWS',
    title: 'Reputation That\'s Portable.',
    desc: 'Not just public Google reviews — direct feedback that lives on your digital card, builds your personal credibility, and stays with you long-term. Even if you switch stores or industries.',
    bullets: ['Reviews live on your digital card', 'Personal credibility that travels', 'Strengthens your individual brand'],
    icon: 'star',
    color: '#FFD60A',
  },
  {
    tag: 'AUTOMATED CAMPAIGNS',
    title: 'Nobody Gets Forgotten. Ever.',
    desc: 'Birthday messages, anniversary follow-ups, holiday greetings, sold-date sequences — all automated. Customers feel remembered without any manual effort from your team.',
    bullets: ['Birthdays & anniversaries', 'Tag-triggered workflows', 'Customers feel remembered'],
    icon: 'rocket',
    color: '#FF9500',
  },
];

export default function ImosHome() {
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

          {/* ========== HERO ========== */}
          <View style={[s.hero, isDesktop && s.heroDesktop]}>
            <Text style={[s.heroLabel, isDesktop && { fontSize: 14 }]}>i'M ON SOCIAL</Text>
            <Text style={[s.heroTitle, isDesktop && { fontSize: 52, lineHeight: 58 }]}>
              Meet the New Way{'\n'}
              <Text style={{ color: '#C9A962' }}>to Be On Social.</Text>
            </Text>
            <Text style={[s.heroSub, isDesktop && { fontSize: 18, maxWidth: 560 }]}>
              In a world where companies automate everything, iMOs protects the relationship. Give organizations, teams, and individuals control of their digital presence, reviews, and customer connections.
            </Text>

            {/* Feature Icons Row */}
            <View style={[s.heroIcons, isDesktop && { gap: 32 }]}>
              {HERO_FEATURES.map((f) => (
                <View key={f.label} style={s.heroIconItem}>
                  <View style={[s.heroIconCircle, { backgroundColor: `${f.color}15` }]}>
                    <Ionicons name={f.icon as any} size={isDesktop ? 24 : 20} color={f.color} />
                  </View>
                  <Text style={s.heroIconLabel}>{f.label}</Text>
                </View>
              ))}
            </View>

            {/* CTA */}
            <View style={s.heroCTAs}>
              <TouchableOpacity style={s.primaryBtn} onPress={() => navigate('/imos/demo')} data-testid="hero-demo-btn">
                <Ionicons name="calendar" size={20} color="#000" />
                <Text style={s.primaryBtnText}>Schedule a Demo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.secondaryBtn} onPress={() => navigate('/imos/signup')} data-testid="hero-trial-btn">
                <Text style={s.secondaryBtnText}>Start 14-Day Free Trial</Text>
                <Ionicons name="arrow-forward" size={16} color="#C9A962" />
              </TouchableOpacity>
            </View>
          </View>

          {/* ========== STATS ========== */}
          <View style={[s.statsSection, isDesktop && s.statsDesktop]}>
            {STATS.map((stat, i) => (
              <View key={i} style={[s.statCard, isDesktop && { flex: 1 }]}>
                <Text style={s.statValue}>{stat.value}</Text>
                <Text style={s.statLabel}>{stat.label}</Text>
              </View>
            ))}
          </View>

          {/* ========== HOW IT WORKS ========== */}
          <View style={s.howSection}>
            <Text style={[s.sectionLabel]}>THE SOCIAL RELATIONSHIP OS</Text>
            <Text style={[s.sectionTitle, isDesktop && { fontSize: 36 }]}>
              A Reputation Operating System for Humans
            </Text>
          </View>

          {HOW_IT_WORKS.map((item, i) => (
            <View key={i} style={[s.featureRow, isDesktop && s.featureRowDesktop, isDesktop && i % 2 === 1 && { flexDirection: 'row-reverse' }]}>
              {/* Icon/Visual Side */}
              <View style={[s.featureVisual, isDesktop && { flex: 1 }]}>
                <View style={[s.featureBigIcon, { backgroundColor: `${item.color}10`, borderColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={isDesktop ? 64 : 48} color={item.color} />
                </View>
              </View>
              {/* Text Side */}
              <View style={[s.featureText, isDesktop && { flex: 1 }]}>
                <Text style={[s.featureTag, { color: item.color }]}>{item.tag}</Text>
                <Text style={[s.featureTitle, isDesktop && { fontSize: 28 }]}>{item.title}</Text>
                <Text style={s.featureDesc}>{item.desc}</Text>
                <View style={s.bulletList}>
                  {item.bullets.map((b, bi) => (
                    <View key={bi} style={s.bulletRow}>
                      <Ionicons name="checkmark-circle" size={18} color={item.color} />
                      <Text style={s.bulletText}>{b}</Text>
                    </View>
                  ))}
                </View>
              </View>
            </View>
          ))}

          <View style={s.bottomCTA}>
            <Text style={[s.bottomCTATitle, isDesktop && { fontSize: 36 }]}>
              Own Your Relationships.{'\n'}Own Your Reputation.
            </Text>
            <Text style={s.bottomCTASub}>
              Send congrats cards. Collect reviews. Share your socials. Build your reputation. The new way to be on social starts here.
            </Text>
            <View style={s.bottomCTABtns}>
              <TouchableOpacity style={s.primaryBtn} onPress={() => navigate('/imos/demo')} data-testid="bottom-demo-btn">
                <Ionicons name="calendar" size={20} color="#000" />
                <Text style={s.primaryBtnText}>Schedule a Demo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.secondaryBtn} onPress={() => navigate('/imos/signup')} data-testid="bottom-trial-btn">
                <Text style={s.secondaryBtnText}>Start 14-Day Free Trial</Text>
                <Ionicons name="arrow-forward" size={16} color="#C9A962" />
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

  /* HERO */
  hero: { alignItems: 'center', paddingTop: 48, paddingBottom: 40, paddingHorizontal: 20 },
  heroDesktop: { paddingTop: 72, paddingBottom: 56 },
  heroLabel: { fontSize: 11, fontWeight: '700', color: '#C9A962', letterSpacing: 2, marginBottom: 16 },
  heroTitle: { fontSize: 32, fontWeight: '900', color: '#FFF', textAlign: 'center', lineHeight: 40, marginBottom: 20 },
  heroSub: { fontSize: 16, color: 'rgba(255,255,255,0.7)', textAlign: 'center', lineHeight: 24, maxWidth: 480, marginBottom: 32 },
  heroIcons: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 16, marginBottom: 36 },
  heroIconItem: { alignItems: 'center', gap: 6, width: 90 },
  heroIconCircle: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  heroIconLabel: { fontSize: 11, color: 'rgba(255,255,255,0.5)', textAlign: 'center', fontWeight: '500' },
  heroCTAs: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12 },
  primaryBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 28, borderRadius: 28,
  },
  primaryBtnText: { fontSize: 15, fontWeight: '700', color: '#000' },
  secondaryBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 14, paddingHorizontal: 24, borderRadius: 28,
    borderWidth: 1, borderColor: 'rgba(201,169,98,0.3)',
  },
  secondaryBtnText: { fontSize: 15, fontWeight: '600', color: '#C9A962' },

  /* STATS */
  statsSection: {
    flexDirection: 'column', gap: 12, paddingHorizontal: 20, paddingVertical: 32,
    backgroundColor: 'rgba(255,255,255,0.02)', borderTopWidth: 1, borderBottomWidth: 1,
    borderColor: 'rgba(255,255,255,0.05)',
  },
  statsDesktop: { flexDirection: 'row', gap: 20, paddingVertical: 40 },
  statCard: {
    backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 16, padding: 24,
    alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)',
  },
  statValue: { fontSize: 40, fontWeight: '900', color: '#C9A962', marginBottom: 6 },
  statLabel: { fontSize: 14, color: 'rgba(255,255,255,0.6)', textAlign: 'center', lineHeight: 20 },

  /* HOW IT WORKS */
  howSection: { alignItems: 'center', paddingTop: 48, paddingBottom: 16, paddingHorizontal: 20 },
  sectionLabel: { fontSize: 11, fontWeight: '700', color: '#C9A962', letterSpacing: 2, marginBottom: 12 },
  sectionTitle: { fontSize: 28, fontWeight: '800', color: '#FFF', textAlign: 'center', lineHeight: 36 },

  featureRow: { paddingHorizontal: 20, paddingVertical: 32, gap: 24 },
  featureRowDesktop: { flexDirection: 'row', alignItems: 'center', gap: 48, paddingVertical: 48 },
  featureVisual: { alignItems: 'center' },
  featureBigIcon: {
    width: 140, height: 140, borderRadius: 32, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
  },
  featureText: {},
  featureTag: { fontSize: 11, fontWeight: '700', letterSpacing: 2, marginBottom: 8 },
  featureTitle: { fontSize: 22, fontWeight: '800', color: '#FFF', lineHeight: 30, marginBottom: 12 },
  featureDesc: { fontSize: 15, color: 'rgba(255,255,255,0.65)', lineHeight: 23, marginBottom: 16 },
  bulletList: { gap: 8 },
  bulletRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  bulletText: { fontSize: 14, color: 'rgba(255,255,255,0.8)', fontWeight: '500' },

  /* BOTTOM CTA */
  bottomCTA: {
    alignItems: 'center', paddingVertical: 56, paddingHorizontal: 20,
    backgroundColor: 'rgba(201,169,98,0.04)', borderTopWidth: 1, borderColor: 'rgba(201,169,98,0.1)',
  },
  bottomCTATitle: { fontSize: 28, fontWeight: '800', color: '#FFF', textAlign: 'center', marginBottom: 12, lineHeight: 36 },
  bottomCTASub: { fontSize: 15, color: 'rgba(255,255,255,0.6)', textAlign: 'center', lineHeight: 22, maxWidth: 400, marginBottom: 28 },
  bottomCTABtns: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12 },
});
