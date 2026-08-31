import React from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../store/themeStore';

const SECTIONS = [
  {
    icon: 'brain',
    color: '#AF52DE',
    title: 'What is GEO?',
    content: 'GEO (Generative Engine Optimization) is the practice of making sure YOU appear when AI tools like ChatGPT, Google Gemini, Perplexity, and Claude answer questions like "who is the best car salesperson near Salt Lake City?"',
    example: 'When a customer asks an AI chatbot for a salesperson recommendation in your area — GEO determines whether your name comes up. SEO gets you on Google. GEO gets you in the AI answer itself.',
  },
  {
    icon: 'sparkles',
    color: '#C9A962',
    title: 'GEO vs SEO vs AEO',
    content: 'Three different engines, three different optimization strategies:\n\n• SEO — Google/Bing search rankings (blue links)\n• AEO — Featured snippets and People Also Ask boxes\n• GEO — AI-generated answers (ChatGPT, Gemini, Perplexity, Copilot)\n\nGEO is the newest and fastest-growing channel. As more people skip Google and ask AI for recommendations, GEO becomes your most valuable visibility investment.',
    tips: [
      'SEO gets you on page 1 of Google. GEO gets you in the AI answer before Google is even opened.',
      'AI tools synthesize answers from structured, authoritative, consistent content across the web.',
      'A strong GEO profile means when someone asks an AI who should I buy a car from in my city — your name is in the response.',
      'GEO builds over time. Every review, every shared link, every consistent mention adds to your AI citation authority.',
    ],
  },
  {
    icon: 'person-circle',
    color: '#AF52DE',
    title: '1. AI Identity Completeness',
    weight: '20 points',
    why: 'AI models build knowledge graphs — linked maps of people, employers, and locations. The more complete and consistent your identity data is, the more confidently AI tools will include you in answers.',
    steps: [
      { text: 'Use your full name exactly as you want to be cited — consistency across all platforms is critical', route: '/my-account', btn: 'My Account' },
      { text: 'Set your job title precisely (e.g., "Senior Sales Consultant, Ford") — AI uses this to match queries like "Ford salesperson near me"', route: '/my-account', btn: 'My Account' },
      { text: 'Write a 50+ word bio with your name, city, employer, and specialty mentioned naturally — AI reads this as authoritative context', route: '/settings/persona', btn: 'AI Persona' },
      { text: 'Connect LinkedIn — it is the single highest-weight professional network in AI training data', route: '/settings/brand-kit', btn: 'Brand Kit' },
      { text: 'Add Facebook and Instagram — cross-platform social presence confirms your entity to AI knowledge graphs', route: '/settings/brand-kit', btn: 'Brand Kit' },
    ],
  },
  {
    icon: 'chatbubbles',
    color: '#007AFF',
    title: '2. Conversational Signals',
    weight: '20 points',
    why: 'Generative AI is trained on human conversation. Customer reviews, natural language bios, and Q&A-style content are exactly the kind of text LLMs learn from — and cite when answering recommendations.',
    steps: [
      { text: 'Get 10+ customer reviews — AI tools use review volume and rating as a credibility proxy when making recommendations', route: '/settings/review-links', btn: 'Review Links' },
      { text: 'Aim for 4.5+ star average — AI recommendation algorithms favor highly-rated professionals', route: '/settings/review-links', btn: 'Review Links' },
      { text: 'Add your specialties to your AI Persona (e.g., "trucks, trade-ins, first-time buyers") — AI matches these to queries', route: '/settings/persona', btn: 'AI Persona' },
      { text: 'Add a personal motto or catchphrase — unique, memorable language is more likely to be cited verbatim by AI', route: '/settings/persona', btn: 'AI Persona' },
    ],
  },
  {
    icon: 'share-social',
    color: '#FF9500',
    title: '3. AI Content Distribution',
    weight: '20 points',
    why: 'Every link you share through I\'m On Social contains embedded JSON-LD structured data — the machine-readable format AI search engines use to build their knowledge. More shares = more citation seeds.',
    steps: [
      { text: 'Share your digital card regularly — each share creates a Schema.org/Person page with your full identity attached', route: '/quick-send/digitalcard', btn: 'Digital Card' },
      { text: 'Run active SMS campaigns — consistent outreach builds a real-world engagement pattern that AI engines detect', route: '/campaigns', btn: 'Campaigns' },
      { text: 'Create tracking links — each clicked link is another data point confirming your digital presence', route: '/settings/link-page', btn: 'Link Page' },
    ],
  },
  {
    icon: 'link',
    color: '#34C759',
    title: '4. Citation Authority',
    weight: '20 points',
    why: 'AI models verify your existence by cross-referencing multiple sources. The more platforms that consistently mention your name + employer + location, the more confident AI is that you\'re a real, authoritative expert worth citing.',
    steps: [
      { text: 'Connect your dealership\'s website — verified employer domains are the top trust signal in AI knowledge graphs', route: '', btn: '' },
      { text: 'Add your Google/DealerRater review profile link — external review platforms are heavily indexed by AI training data', route: '/settings/review-links', btn: 'Review Links' },
      { text: 'Activate your public link page — another crawlable, structured page that confirms your identity', route: '/settings/link-page', btn: 'Link Page' },
      { text: 'Get customers to download your vCard — each saved contact is a real-world entity confirmation', route: '', btn: '' },
    ],
  },
  {
    icon: 'flash',
    color: '#C9A962',
    title: '5. Generative Freshness',
    weight: '20 points',
    why: 'AI models weight recent activity over stale profiles. A salesperson who added 10 contacts last month and sent 50 messages looks like an active practitioner. One who has not engaged in months looks dormant.',
    steps: [
      { text: 'Add new contacts regularly — new relationships signal that you\'re actively building your business', route: '', btn: '' },
      { text: 'Send messages consistently — active messaging patterns confirm you\'re a real, engaged professional', route: '', btn: '' },
      { text: 'Log in to the app daily — session activity contributes to your freshness signal', route: '', btn: '' },
      { text: 'Run campaigns with active enrollments — ongoing campaigns show AI engines you\'re consistently reaching customers', route: '/campaigns', btn: 'Campaigns' },
    ],
  },
];

export default function GEOGuideScreen() {
  const router = useRouter();
  const { mode: theme } = useThemeStore();
  const isDark = theme === 'dark';
  const bg = isDark ? '#000' : '#F2F2F7';
  const cardBg = isDark ? '#1C1C1E' : '#FFF';
  const textPrimary = isDark ? '#FFF' : '#000';
  const textSecondary = isDark ? '#8E8E93' : '#6C6C70';
  const border = isDark ? '#2C2C2E' : '#E5E5EA';

  return (
    <SafeAreaView style={[s.container, { backgroundColor: bg }]}>
      <View style={[s.header, { borderBottomColor: border }]}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="geo-guide-back-btn">
          <Ionicons name="chevron-back" size={26} color={textPrimary} />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: textPrimary }]}>GEO Guide</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={s.scroll}>
        <View style={[s.hero, { backgroundColor: '#AF52DE20', borderColor: '#AF52DE40' }]}>
          <Text style={s.heroEmoji}>🤖</Text>
          <Text style={[s.heroTitle, { color: textPrimary }]}>Generative Engine Optimization</Text>
          <Text style={[s.heroSub, { color: textSecondary }]}>
            Get your name cited by ChatGPT, Gemini, and Perplexity when customers ask AI for salesperson recommendations.
          </Text>
        </View>

        {SECTIONS.map((sec, i) => (
          <View key={i} style={[s.card, { backgroundColor: cardBg }]}>
            <View style={[s.iconWrap, { backgroundColor: sec.color + '20' }]}>
              <Ionicons name={sec.icon as any} size={24} color={sec.color} />
            </View>
            <View style={s.cardBody}>
              <View style={s.titleRow}>
                <Text style={[s.cardTitle, { color: textPrimary }]}>{sec.title}</Text>
                {sec.weight && (
                  <View style={[s.weightBadge, { backgroundColor: sec.color + '20' }]}>
                    <Text style={[s.weightText, { color: sec.color }]}>{sec.weight}</Text>
                  </View>
                )}
              </View>
              {sec.content && <Text style={[s.cardContent, { color: textSecondary }]}>{sec.content}</Text>}
              {sec.example && (
                <View style={[s.example, { backgroundColor: sec.color + '15', borderLeftColor: sec.color }]}>
                  <Text style={[s.exampleText, { color: textSecondary }]}>💡 {sec.example}</Text>
                </View>
              )}
              {sec.why && <Text style={[s.whyText, { color: textSecondary }]}>{sec.why}</Text>}
              {sec.tips && (
                <View style={s.tipsList}>
                  {sec.tips.map((t, ti) => (
                    <View key={ti} style={s.tipRow}>
                      <Ionicons name="checkmark-circle" size={16} color={sec.color} style={{ marginTop: 2 }} />
                      <Text style={[s.tipText, { color: textSecondary }]}>{t}</Text>
                    </View>
                  ))}
                </View>
              )}
              {sec.steps && (
                <View style={s.stepsList}>
                  {sec.steps.map((st, si) => (
                    <View key={si} style={[s.step, { borderLeftColor: sec.color + '60' }]}>
                      <Text style={[s.stepNum, { color: sec.color }]}>{si + 1}</Text>
                      <View style={{ flex: 1 }}>
                        <Text style={[s.stepText, { color: textSecondary }]}>{st.text}</Text>
                        {st.route && st.btn ? (
                          <TouchableOpacity
                            onPress={() => router.push(st.route as any)}
                            style={[s.stepBtn, { backgroundColor: sec.color + '20' }]}
                          >
                            <Text style={[s.stepBtnText, { color: sec.color }]}>{st.btn} →</Text>
                          </TouchableOpacity>
                        ) : null}
                      </View>
                    </View>
                  ))}
                </View>
              )}
            </View>
          </View>
        ))}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container:   { flex: 1 },
  header:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1 },
  backBtn:     { width: 40, alignItems: 'flex-start' },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  scroll:      { padding: 16, paddingBottom: 40 },
  hero:        { borderRadius: 20, padding: 24, alignItems: 'center', marginBottom: 20, borderWidth: 1 },
  heroEmoji:   { fontSize: 40, marginBottom: 8 },
  heroTitle:   { fontSize: 22, fontWeight: '800', textAlign: 'center', marginBottom: 8 },
  heroSub:     { fontSize: 15, lineHeight: 22, textAlign: 'center' },
  card:        { borderRadius: 16, padding: 16, marginBottom: 14, gap: 12 },
  iconWrap:    { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardBody:    { gap: 10 },
  titleRow:    { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  cardTitle:   { fontSize: 17, fontWeight: '700', flex: 1 },
  weightBadge: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3 },
  weightText:  { fontSize: 12, fontWeight: '700' },
  cardContent: { fontSize: 14, lineHeight: 21 },
  example:     { borderLeftWidth: 3, paddingLeft: 12, paddingVertical: 8, borderRadius: 4 },
  exampleText: { fontSize: 13, lineHeight: 20, fontStyle: 'italic' },
  whyText:     { fontSize: 13, lineHeight: 20 },
  tipsList:    { gap: 8 },
  tipRow:      { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  tipText:     { fontSize: 13, lineHeight: 20, flex: 1 },
  stepsList:   { gap: 10 },
  step:        { flexDirection: 'row', gap: 10, borderLeftWidth: 2, paddingLeft: 12, paddingVertical: 4, alignItems: 'flex-start' },
  stepNum:     { fontSize: 13, fontWeight: '800', width: 16, marginTop: 1 },
  stepText:    { fontSize: 13, lineHeight: 20 },
  stepBtn:     { alignSelf: 'flex-start', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5, marginTop: 6 },
  stepBtnText: { fontSize: 12, fontWeight: '700' },
});
