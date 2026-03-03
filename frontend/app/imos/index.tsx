import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter } from './_components';

const HERO_FEATURES = [
  { icon: 'card', color: '#007AFF', label: 'Digital Cards' },
  { icon: 'star', color: '#007AFF', label: 'Personal Reviews' },
  { icon: 'share-social', color: '#34C759', label: 'Social Links' },
  { icon: 'camera', color: '#007AFF', label: 'Congrats Cards' },
  { icon: 'rocket', color: '#FF9500', label: 'Campaigns' },
  { icon: 'trophy', color: '#AF52DE', label: 'Reputation' },
];

const STATS = [
  { value: 'Own', label: 'your reputation  - it moves with you, wherever you go' },
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
    color: '#007AFF',
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
    desc: 'Not just public Google reviews  - direct feedback that lives on your digital card, builds your personal credibility, and stays with you long-term. Even if you switch stores or industries.',
    bullets: ['Reviews live on your digital card', 'Personal credibility that travels', 'Strengthens your individual brand'],
    icon: 'star',
    color: '#007AFF',
  },
  {
    tag: 'AUTOMATED CAMPAIGNS',
    title: 'Nobody Gets Forgotten. Ever.',
    desc: 'Birthday messages, anniversary follow-ups, holiday greetings, sold-date sequences  - all automated. Customers feel remembered without any manual effort from your team.',
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
              <Text style={{ color: '#007AFF' }}>to Be On Social.</Text>
            </Text>
            <Text style={[s.heroSub, isDesktop && { fontSize: 18, maxWidth: 560 }]}>
              In a world where companies automate everything, i'M On Social protects the relationship. Give organizations, teams, and individuals control of their digital presence, reviews, and customer connections.
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
                <Ionicons name="arrow-forward" size={16} color="#007AFF" />
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

          {/* ========== THE PROBLEM ========== */}
          <View style={s.narrativeSection}>
            <View style={[s.narrativeCard, { borderColor: 'rgba(255,59,48,0.15)' }]}>
              <View style={[s.narrativeIconWrap, { backgroundColor: 'rgba(255,59,48,0.1)' }]}>
                <Ionicons name="alert-circle" size={32} color="#FF3B30" />
              </View>
              <Text style={[s.narrativeTag, { color: '#FF3B30' }]}>THE OLD WORLD</Text>
              <Text style={[s.narrativeTitle, isDesktop && { fontSize: 28 }]}>
                People Disappear After the Transaction.
              </Text>
              <View style={s.narrativeDivider} />
              <View style={s.narrativeLines}>
                <Text style={s.narrativeLine}>The customer buys. The salesperson moves on.</Text>
                <Text style={s.narrativeLine}>Reviews go to the company  - not the person.</Text>
                <Text style={s.narrativeLine}>Social profiles live scattered across platforms.</Text>
                <Text style={s.narrativeLine}>Follow-up feels generic. The relationship fades.</Text>
              </View>
              <View style={[s.narrativeHighlight, { backgroundColor: 'rgba(255,59,48,0.08)' }]}>
                <Text style={[s.narrativeHighlightText, { color: '#FF6B6B' }]}>
                  In a world full of automation, nobody feels remembered.
                </Text>
              </View>
            </View>
          </View>

          {/* ========== THE SHIFT ========== */}
          <View style={s.narrativeSection}>
            <View style={[s.narrativeCard, { borderColor: 'rgba(201,169,98,0.2)' }]}>
              <View style={[s.narrativeIconWrap, { backgroundColor: 'rgba(0,122,255,0.06)' }]}>
                <Ionicons name="swap-horizontal" size={32} color="#007AFF" />
              </View>
              <Text style={[s.narrativeTag, { color: '#007AFF' }]}>THE SHIFT</Text>
              <Text style={[s.narrativeTitle, isDesktop && { fontSize: 28 }]}>
                i'M On Social Isn't About Marketing.{'\n'}
                <Text style={{ color: '#007AFF' }}>It's About Ownership.</Text>
              </Text>
              <View style={s.narrativeDivider} />
              <View style={s.narrativeLines}>
                <Text style={s.narrativeLine}>Every organization. Every team. Every individual.</Text>
                <Text style={s.narrativeLine}>All under one structured social ecosystem.</Text>
              </View>
              <View style={s.narrativeColumnsWrap}>
                {[
                  { icon: 'business', color: '#007AFF', label: 'Organizations', desc: 'Teams, accounts, reputation data, social presence  - structured.' },
                  { icon: 'people', color: '#34C759', label: 'Teams', desc: 'Shared visibility. Unified brand. Individual ownership.' },
                  { icon: 'person', color: '#007AFF', label: 'Individuals', desc: 'Digital card. Reviews. Social links. Personal rating.' },
                ].map((col, ci) => (
                  <View key={ci} style={s.narrativeCol}>
                    <View style={[s.narrativeColIcon, { backgroundColor: `${col.color}15` }]}>
                      <Ionicons name={col.icon as any} size={22} color={col.color} />
                    </View>
                    <Text style={s.narrativeColLabel}>{col.label}</Text>
                    <Text style={s.narrativeColDesc}>{col.desc}</Text>
                  </View>
                ))}
              </View>
            </View>
          </View>

          {/* ========== THE POWER MOVE ========== */}
          <View style={s.narrativeSection}>
            <View style={[s.narrativeCard, { borderColor: 'rgba(255,214,10,0.15)' }]}>
              <View style={[s.narrativeIconWrap, { backgroundColor: 'rgba(255,214,10,0.1)' }]}>
                <Ionicons name="flash" size={32} color="#FFD60A" />
              </View>
              <Text style={[s.narrativeTag, { color: '#007AFF' }]}>THE POWER MOVE</Text>
              <Text style={[s.narrativeTitle, isDesktop && { fontSize: 28 }]}>
                Personal Reviews Change Everything.
              </Text>
              <View style={s.narrativeDivider} />
              <View style={s.narrativeLines}>
                <Text style={s.narrativeLine}>Direct feedback that lives on your digital business card.</Text>
                <Text style={s.narrativeLine}>Builds personal credibility. Strengthens your brand.</Text>
                <Text style={s.narrativeLine}>Stays with you  - even if you switch stores or industries.</Text>
              </View>
              <View style={[s.narrativeHighlight, { backgroundColor: 'rgba(255,214,10,0.08)' }]}>
                <Text style={[s.narrativeHighlightText, { color: '#007AFF' }]}>
                  Reputation becomes portable. That's powerful.
                </Text>
              </View>
            </View>
          </View>

          {/* ========== THE EMOTIONAL HOOK ========== */}
          <View style={s.narrativeSection}>
            <View style={[s.narrativeCard, { borderColor: 'rgba(0,122,255,0.15)' }]}>
              <View style={[s.narrativeIconWrap, { backgroundColor: 'rgba(0,122,255,0.1)' }]}>
                <Ionicons name="heart" size={32} color="#007AFF" />
              </View>
              <Text style={[s.narrativeTag, { color: '#007AFF' }]}>THE BIGGER PICTURE</Text>
              <Text style={[s.narrativeTitle, isDesktop && { fontSize: 28 }]}>
                AI Is Replacing Transactions.{'\n'}
                <Text style={{ color: '#007AFF' }}>But Trust Still Wins.</Text>
              </Text>
              <View style={s.narrativeDivider} />
              <View style={s.narrativeLines}>
                <Text style={s.narrativeLine}>Trust lives with people  - not logos.</Text>
              </View>
              <View style={s.narrativeGrid}>
                {[
                  { icon: 'eye', color: '#007AFF', text: 'Visibility' },
                  { icon: 'shield-checkmark', color: '#34C759', text: 'Credibility' },
                  { icon: 'key', color: '#007AFF', text: 'Ownership' },
                  { icon: 'infinite', color: '#AF52DE', text: 'Continuity' },
                ].map((g, gi) => (
                  <View key={gi} style={s.narrativeGridItem}>
                    <Ionicons name={g.icon as any} size={24} color={g.color} />
                    <Text style={s.narrativeGridText}>{g.text}</Text>
                  </View>
                ))}
              </View>
              <View style={[s.narrativeHighlight, { backgroundColor: 'rgba(0,122,255,0.08)' }]}>
                <Text style={[s.narrativeHighlightText, { color: '#5AC8FA' }]}>
                  i'M On Social gives individuals visibility, credibility, ownership, and continuity. Their reputation moves with them.
                </Text>
              </View>
            </View>
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
                <Ionicons name="arrow-forward" size={16} color="#007AFF" />
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
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingBottom: 0 },

  /* HERO */
  hero: { alignItems: 'center', paddingTop: 48, paddingBottom: 40, paddingHorizontal: 20 },
  heroDesktop: { paddingTop: 72, paddingBottom: 56 },
  heroLabel: { fontSize: 11, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 16 },
  heroTitle: { fontSize: 32, fontWeight: '900', color: '#1D1D1F', textAlign: 'center', lineHeight: 40, marginBottom: 20 },
  heroSub: { fontSize: 16, color: '#6E6E73', textAlign: 'center', lineHeight: 24, maxWidth: 480, marginBottom: 32 },
  heroIcons: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 16, marginBottom: 36 },
  heroIconItem: { alignItems: 'center', gap: 6, width: 90 },
  heroIconCircle: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  heroIconLabel: { fontSize: 11, color: '#86868B', textAlign: 'center', fontWeight: '500' },
  heroCTAs: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12 },
  primaryBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#007AFF', paddingVertical: 14, paddingHorizontal: 28, borderRadius: 980,
  },
  primaryBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  secondaryBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 14, paddingHorizontal: 24, borderRadius: 28,
    borderWidth: 1, borderColor: 'rgba(0,122,255,0.15)',
  },
  secondaryBtnText: { fontSize: 15, fontWeight: '600', color: '#007AFF' },

  /* STATS */
  statsSection: {
    flexDirection: 'column', gap: 12, paddingHorizontal: 20, paddingVertical: 32,
    backgroundColor: '#FAFAFA', borderTopWidth: 1, borderBottomWidth: 1,
    borderColor: 'rgba(0,0,0,0.05)',
  },
  statsDesktop: { flexDirection: 'row', gap: 20, paddingVertical: 40 },
  statCard: {
    backgroundColor: '#F5F5F7', borderRadius: 16, padding: 24,
    alignItems: 'center', borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)',
  },
  statValue: { fontSize: 40, fontWeight: '900', color: '#007AFF', marginBottom: 6 },
  statLabel: { fontSize: 14, color: '#6E6E73', textAlign: 'center', lineHeight: 20 },

  /* HOW IT WORKS */
  howSection: { alignItems: 'center', paddingTop: 48, paddingBottom: 16, paddingHorizontal: 20 },
  sectionLabel: { fontSize: 11, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 12 },
  sectionTitle: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', textAlign: 'center', lineHeight: 36 },

  featureRow: { paddingHorizontal: 20, paddingVertical: 32, gap: 24 },
  featureRowDesktop: { flexDirection: 'row', alignItems: 'center', gap: 48, paddingVertical: 48 },
  featureVisual: { alignItems: 'center' },
  featureBigIcon: {
    width: 140, height: 140, borderRadius: 32, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
  },
  featureText: {},
  featureTag: { fontSize: 11, fontWeight: '700', letterSpacing: 2, marginBottom: 8 },
  featureTitle: { fontSize: 22, fontWeight: '800', color: '#1D1D1F', lineHeight: 30, marginBottom: 12 },
  featureDesc: { fontSize: 15, color: '#6E6E73', lineHeight: 23, marginBottom: 16 },
  bulletList: { gap: 8 },
  bulletRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  bulletText: { fontSize: 14, color: '#3A3A3C', fontWeight: '500' },

  /* BOTTOM CTA */
  bottomCTA: {
    alignItems: 'center', paddingVertical: 56, paddingHorizontal: 20,
    backgroundColor: 'rgba(201,169,98,0.04)', borderTopWidth: 1, borderColor: 'rgba(0,122,255,0.06)',
  },
  bottomCTATitle: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', textAlign: 'center', marginBottom: 12, lineHeight: 36 },
  bottomCTASub: { fontSize: 15, color: '#6E6E73', textAlign: 'center', lineHeight: 22, maxWidth: 400, marginBottom: 28 },
  bottomCTABtns: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12 },

  /* NARRATIVE SECTIONS */
  narrativeSection: { paddingHorizontal: 20, paddingVertical: 12 },
  narrativeCard: {
    backgroundColor: '#FAFAFA', borderRadius: 24, padding: 28,
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)',
  },
  narrativeIconWrap: {
    width: 56, height: 56, borderRadius: 16,
    alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  narrativeTag: { fontSize: 11, fontWeight: '700', letterSpacing: 2, marginBottom: 10 },
  narrativeTitle: { fontSize: 22, fontWeight: '800', color: '#1D1D1F', lineHeight: 30, marginBottom: 16 },
  narrativeDivider: { height: 1, backgroundColor: 'rgba(0,0,0,0.06)', marginBottom: 16 },
  narrativeLines: { gap: 8, marginBottom: 16 },
  narrativeLine: { fontSize: 15, color: '#6E6E73', lineHeight: 23 },
  narrativeHighlight: {
    borderRadius: 12, padding: 16, marginTop: 4,
  },
  narrativeHighlightText: { fontSize: 15, fontWeight: '600', lineHeight: 22, textAlign: 'center' },
  narrativeColumnsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 8, marginBottom: 8 },
  narrativeCol: {
    flex: 1, minWidth: 150, backgroundColor: '#F5F5F7', borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.04)',
  },
  narrativeColIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  narrativeColLabel: { fontSize: 14, fontWeight: '700', color: '#1D1D1F', marginBottom: 4 },
  narrativeColDesc: { fontSize: 13, color: '#86868B', lineHeight: 18 },
  narrativeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 12 },
  narrativeGridItem: {
    width: '46%', flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#F5F5F7', borderRadius: 12, padding: 14,
  },
  narrativeGridText: { fontSize: 15, fontWeight: '600', color: '#1D1D1F' },
});
