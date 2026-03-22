import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../store/themeStore';

const SECTIONS = [
  {
    icon: 'earth',
    color: '#007AFF',
    title: 'What is SEO & AEO?',
    content: 'SEO (Search Engine Optimization) helps customers find you on Google. AEO (Answer Engine Optimization) helps you show up when people ask AI assistants like ChatGPT or Siri for recommendations.',
    example: 'When someone searches "best car salesman near me" or asks an AI "who should I buy a car from in [your city]?" — a strong SEO/AEO profile puts YOU in the answer.',
  },
  {
    icon: 'person-circle',
    color: '#007AFF',
    title: '1. Complete Your Profile',
    weight: '20 points',
    why: 'Search engines and AI need basic information about you to recommend you. An incomplete profile is invisible online.',
    steps: [
      { text: 'Add a professional profile photo', route: '/my-account', btn: 'Go to My Account' },
      { text: 'Set your job title (e.g., "Senior Sales Consultant")', route: '/my-account', btn: 'Go to My Account' },
      { text: 'Add your phone number', route: '/my-account', btn: 'Go to My Account' },
      { text: 'Write your bio — tell customers who you are and why they should work with you', route: '/settings/persona', btn: 'Go to AI Persona' },
      { text: 'Connect your social media profiles (Facebook, Instagram, LinkedIn)', route: '/settings/brand-kit', btn: 'Go to Brand Kit' },
    ],
  },
  {
    icon: 'star',
    color: '#FFD60A',
    title: '2. Build Review Strength',
    weight: '20 points',
    why: 'Google and AI heavily rely on customer reviews to determine who to recommend. More 5-star reviews = higher ranking.',
    steps: [
      { text: 'After every sale, send your customer a review request using your review link', route: '/settings/review-links', btn: 'Get Review Link' },
      { text: 'Aim for at least 5 reviews to reach "Strong" status' },
      { text: 'Respond to every review — Google rewards engagement' },
      { text: 'Ask happy customers to mention specifics (your name, the dealership, the car model) — this improves keyword matching' },
    ],
  },
  {
    icon: 'share-social',
    color: '#AF52DE',
    title: '3. Distribute Your Content',
    weight: '20 points',
    why: 'Every time someone views your digital card or clicks a link you shared, it signals to search engines that you\'re relevant and active.',
    steps: [
      { text: 'Share your digital card after every customer interaction — text it, email it, or tap to share via NFC', route: '/settings/create-card', btn: 'View My Card' },
      { text: 'Post your link page on your social media profiles', route: '/settings/link-page', btn: 'My Link Page' },
      { text: 'Add your profile link to your email signature' },
      { text: 'Use tracking links (UTM) to see which channels drive the most views' },
    ],
  },
  {
    icon: 'search',
    color: '#34C759',
    title: '4. Boost Search Visibility',
    weight: '20 points',
    why: 'This measures whether people can actually find you through search engines and AI assistants. The more they visit your public pages, the higher you rank.',
    steps: [
      { text: 'Share your public profile link on social media at least once a week' },
      { text: 'Ask satisfied customers to Google your name + dealership and visit your page — this trains Google to show you' },
      { text: 'Make sure your dealership\'s Google Business Profile links to your personal page' },
      { text: 'Post customer photos with their new car to your showcase — each photo is a new searchable page', route: '/showroom-manage', btn: 'My Showcase' },
    ],
  },
  {
    icon: 'flash',
    color: '#FF9500',
    title: '5. Stay Active & Fresh',
    weight: '20 points',
    why: 'Search engines favor active profiles over dormant ones. Regular activity signals that you\'re a current, trustworthy professional.',
    steps: [
      { text: 'Add new contacts regularly — aim for 10+ per month' },
      { text: 'Send follow-up messages to your contacts consistently' },
      { text: 'Log in daily — even a quick check-in counts' },
      { text: 'Use campaigns to automate your follow-ups so activity never drops', route: '/campaigns', btn: 'SMS Campaigns' },
    ],
  },
  {
    icon: 'bulb',
    color: '#00C7BE',
    title: 'Pro Tips for Dealerships',
    content: '',
    tips: [
      'Have every salesperson complete their profile on Day 1 — it takes 5 minutes and starts building their online presence immediately.',
      'Run a monthly "SEO Challenge" — the salesperson with the highest score improvement gets a prize.',
      'Share customer photos consistently — each one becomes a searchable page that can rank for local car searches.',
      'The goal is 80+ score for every team member. At that level, your dealership dominates local search results.',
    ],
  },
];

export default function SEOGuideScreen() {
  const router = useRouter();
  const { theme } = useThemeStore();
  const isDark = theme === 'dark';

  const bg = isDark ? '#000' : '#F2F2F7';
  const cardBg = isDark ? '#1C1C1E' : '#FFF';
  const text = isDark ? '#FFF' : '#000';
  const textSec = isDark ? '#8E8E93' : '#6C6C70';
  const border = isDark ? '#2C2C2E' : '#E5E5EA';

  return (
    <SafeAreaView style={[s.container, { backgroundColor: bg }]} data-testid="seo-guide-screen">
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="seo-guide-back-btn">
          <Ionicons name="chevron-back" size={28} color={text} />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: text }]}>Improve Your Score</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView contentContainerStyle={s.scroll}>
        {SECTIONS.map((section, si) => (
          <View key={si} style={[s.card, { backgroundColor: cardBg }]}>
            <View style={s.cardHeader}>
              <View style={[s.iconWrap, { backgroundColor: section.color + '18' }]}>
                <Ionicons name={section.icon as any} size={22} color={section.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[s.cardTitle, { color: text }]}>{section.title}</Text>
                {section.weight && <Text style={[s.weight, { color: section.color }]}>{section.weight}</Text>}
              </View>
            </View>

            {section.why && <Text style={[s.why, { color: textSec }]}>{section.why}</Text>}
            {section.content && <Text style={[s.why, { color: textSec }]}>{section.content}</Text>}
            {section.example && (
              <View style={[s.exampleBox, { backgroundColor: isDark ? '#1a2332' : '#EBF5FF', borderColor: isDark ? '#1a3a5c' : '#B3D7FF' }]}>
                <Text style={[s.exampleText, { color: isDark ? '#6CB4FF' : '#0055AA' }]}>{section.example}</Text>
              </View>
            )}

            {section.steps && section.steps.map((step, i) => (
              <View key={i} style={[s.stepRow, i < section.steps!.length - 1 && { borderBottomWidth: 1, borderBottomColor: border }]}>
                <View style={s.stepNum}>
                  <Text style={[s.stepNumText, { color: section.color }]}>{i + 1}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[s.stepText, { color: text }]}>{step.text}</Text>
                  {step.route && (
                    <TouchableOpacity
                      style={[s.actionBtn, { backgroundColor: section.color + '15' }]}
                      onPress={() => router.push(step.route as any)}
                    >
                      <Text style={[s.actionBtnText, { color: section.color }]}>{step.btn}</Text>
                      <Ionicons name="arrow-forward" size={14} color={section.color} />
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            ))}

            {section.tips && section.tips.map((tip, i) => (
              <View key={i} style={[s.tipRow, { borderLeftColor: section.color }]}>
                <Text style={[s.tipText, { color: text }]}>{tip}</Text>
              </View>
            ))}
          </View>
        ))}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 19, fontWeight: '700' },
  scroll: { padding: 16 },
  card: { borderRadius: 16, padding: 18, marginBottom: 14 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 10 },
  iconWrap: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: 18, fontWeight: '700' },
  weight: { fontSize: 14, fontWeight: '600', marginTop: 1 },
  why: { fontSize: 16, lineHeight: 20, marginBottom: 12 },
  exampleBox: { padding: 12, borderRadius: 10, borderWidth: 1, marginBottom: 12 },
  exampleText: { fontSize: 15, fontStyle: 'italic', lineHeight: 18 },
  stepRow: { flexDirection: 'row', paddingVertical: 12, gap: 10 },
  stepNum: { width: 24, height: 24, borderRadius: 12, backgroundColor: '#F2F2F7', alignItems: 'center', justifyContent: 'center' },
  stepNumText: { fontSize: 14, fontWeight: '800' },
  stepText: { fontSize: 16, lineHeight: 19 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, alignSelf: 'flex-start', marginTop: 6 },
  actionBtnText: { fontSize: 15, fontWeight: '600' },
  tipRow: { borderLeftWidth: 3, paddingLeft: 12, paddingVertical: 8, marginBottom: 6 },
  tipText: { fontSize: 16, lineHeight: 19 },
});
