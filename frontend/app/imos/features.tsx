import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter } from './_components';

const FEATURE_SECTIONS = [
  {
    title: 'Sales Empowerment',
    subtitle: 'Give your team the tools to close more deals',
    icon: 'flash',
    color: '#C9A962',
    features: [
      { icon: 'camera', title: 'Congrats Cards', desc: 'Snap a photo, create a branded card customers share on social media. Every deal becomes marketing.' },
      { icon: 'chatbubbles', title: 'Smart Messaging', desc: 'SMS and email from one inbox. AI-powered response suggestions. Never leave a customer waiting.' },
      { icon: 'call', title: 'Built-in Dialer', desc: 'Call directly from the app. Auto-log every interaction. Full call history at your fingertips.' },
      { icon: 'card', title: 'Digital Business Card', desc: 'Shareable digital card with bio, socials, and direct contact. Modern and professional.' },
    ],
  },
  {
    title: 'Automated Campaigns',
    subtitle: 'Set it and never forget a customer again',
    icon: 'rocket',
    color: '#007AFF',
    features: [
      { icon: 'gift', title: 'Birthday & Anniversary', desc: 'Automatic messages on every milestone. Customers feel remembered without any manual effort.' },
      { icon: 'car-sport', title: 'Sold Date Sequences', desc: 'Tag a customer as "Sold" and the follow-up campaign starts automatically. Lifetime engagement.' },
      { icon: 'snow', title: 'Holiday Campaigns', desc: '14+ pre-built holiday templates. Thanksgiving, Christmas, New Year — all automated.' },
      { icon: 'pricetags', title: 'Tag-Triggered Workflows', desc: 'Apply a tag, start a campaign. Simple rules that drive complex, multi-step follow-ups.' },
    ],
  },
  {
    title: 'AI-Powered Intelligence',
    subtitle: "Jessi — your team's AI assistant",
    icon: 'sparkles',
    color: '#AF52DE',
    features: [
      { icon: 'sparkles', title: 'AI Response Suggestions', desc: 'Jessi suggests replies that sound like your team wrote them. Faster, better communication.' },
      { icon: 'mic', title: 'Voice-to-Text', desc: 'Speak your notes on the lot. iMOs transcribes and logs everything automatically.' },
      { icon: 'school', title: 'Training Assistant', desc: 'New hires ask Jessi anything about the app. Interactive training that scales.' },
      { icon: 'bulb', title: 'Smart Tagging', desc: 'AI recommends tags and campaigns based on customer data. Less manual work, more accuracy.' },
    ],
  },
  {
    title: 'Management & Analytics',
    subtitle: 'Complete visibility without micromanaging',
    icon: 'shield-checkmark',
    color: '#FF9500',
    features: [
      { icon: 'trophy', title: 'Leaderboards', desc: 'Real-time performance rankings. Motivate your team with friendly competition.' },
      { icon: 'pulse', title: 'Activity Feeds', desc: 'See every customer touchpoint across your entire team. Nothing falls through the cracks.' },
      { icon: 'megaphone', title: 'Team Broadcast', desc: 'One message to your entire team. Announcements, updates, motivation — instantly.' },
      { icon: 'stats-chart', title: 'Analytics Dashboard', desc: 'Track deals, response times, campaign performance. Data-driven decisions.' },
    ],
  },
  {
    title: 'Enterprise Ready',
    subtitle: 'Scale from one store to a nationwide operation',
    icon: 'business',
    color: '#5AC8FA',
    features: [
      { icon: 'layers', title: 'Multi-Org Hierarchy', desc: 'Organizations, stores, teams — structured exactly how your business operates.' },
      { icon: 'color-palette', title: 'White-Label Ready', desc: 'Your brand, your colors, your domain. Powered by iMOs under the hood.' },
      { icon: 'people', title: 'Role-Based Onboarding', desc: 'Custom onboarding for every role. Admins, managers, salespeople — each gets what they need.' },
      { icon: 'shield', title: 'Security & Compliance', desc: 'Enterprise-grade security. Role-based access. Your data stays yours.' },
    ],
  },
];

export default function FeaturesScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 900 : undefined;

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

          <View style={s.titleSection}>
            <Text style={s.label}>PLATFORM</Text>
            <Text style={[s.title, isDesktop && { fontSize: 36 }]}>Features</Text>
            <Text style={s.subtitle}>Everything your team needs to build lasting customer relationships</Text>
          </View>

          {FEATURE_SECTIONS.map((section, si) => (
            <View key={si} style={s.featureSection}>
              <View style={s.sectionHead}>
                <View style={[s.sectionIcon, { backgroundColor: `${section.color}15` }]}>
                  <Ionicons name={section.icon as any} size={28} color={section.color} />
                </View>
                <Text style={s.sectionTitle}>{section.title}</Text>
                <Text style={[s.sectionSub, { color: section.color }]}>{section.subtitle}</Text>
              </View>
              <View style={[s.featureGrid, isDesktop && { flexDirection: 'row', flexWrap: 'wrap' }]}>
                {section.features.map((f, fi) => (
                  <View key={fi} style={[s.featureCard, isDesktop && { width: '48%' }]}>
                    <View style={[s.featureIcon, { backgroundColor: `${section.color}12` }]}>
                      <Ionicons name={f.icon as any} size={22} color={section.color} />
                    </View>
                    <Text style={s.featureTitle}>{f.title}</Text>
                    <Text style={s.featureDesc}>{f.desc}</Text>
                  </View>
                ))}
              </View>
            </View>
          ))}

          {/* CTA */}
          <View style={s.cta}>
            <Text style={s.ctaTitle}>See it in action</Text>
            <TouchableOpacity style={s.ctaBtn} onPress={() => router.push('/imos/salespresentation' as any)} data-testid="features-presentation-btn">
              <Ionicons name="play-circle" size={20} color="#000" />
              <Text style={s.ctaBtnText}>View Sales Presentation</Text>
            </TouchableOpacity>
          </View>

        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A12' },
  scroll: { paddingBottom: 0 },
  titleSection: { alignItems: 'center', paddingHorizontal: 24, paddingTop: 40, paddingBottom: 32 },
  label: { fontSize: 11, fontWeight: '700', color: '#C9A962', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#FFF', marginBottom: 8 },
  subtitle: { fontSize: 15, color: '#8E8E93', textAlign: 'center', lineHeight: 22, maxWidth: 360 },
  featureSection: { paddingHorizontal: 16, marginBottom: 36 },
  sectionHead: { alignItems: 'center', marginBottom: 18 },
  sectionIcon: { width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 22, fontWeight: '700', color: '#FFF', marginBottom: 4 },
  sectionSub: { fontSize: 14, fontWeight: '500' },
  featureGrid: { gap: 10 },
  featureCard: {
    backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)',
  },
  featureIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  featureTitle: { fontSize: 16, fontWeight: '600', color: '#FFF', marginBottom: 4 },
  featureDesc: { fontSize: 13, color: '#8E8E93', lineHeight: 19 },
  cta: { alignItems: 'center', paddingVertical: 40 },
  ctaTitle: { fontSize: 20, fontWeight: '700', color: '#FFF', marginBottom: 16 },
  ctaBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#C9A962', paddingVertical: 14, paddingHorizontal: 28, borderRadius: 28,
  },
  ctaBtnText: { fontSize: 16, fontWeight: '700', color: '#000' },
});
