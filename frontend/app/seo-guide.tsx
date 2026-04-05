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
    content: 'SEO (Search Engine Optimization) helps customers find you on Google. AEO (Answer Engine Optimization) helps you show up when people ask AI assistants like ChatGPT, Perplexity, or Google AI for recommendations.',
    example: 'When someone searches "best car salesman near me" or asks an AI "who should I buy a car from in [your city]?" — a strong SEO/AEO profile puts YOUR name in the answer. We help make that happen automatically every time you share a link.',
  },
  {
    icon: 'rocket',
    color: '#C9A962',
    title: 'How We\'re Different',
    content: 'Most CRMs send a text link. We send a reputation signal.\n\nEvery link you share through i\'M On Social — your digital card, review request, showcase, campaign messages — is wrapped in invisible machine-readable data that search engines and AI tools use to build knowledge graphs about who you are and where you work.',
    tips: [
      'Your name, title, phone, and employer are attached to every link — so AI engines recognize you across the web.',
      'Your social profiles (LinkedIn, Instagram, Facebook) are linked together — one share connects your entire digital identity.',
      'Your customer reviews are embedded as a star rating — Google can show ⭐⭐⭐⭐⭐ next to your name in search results.',
      'Your store\'s website is cited as the authoritative source — creating a structured backlink that strengthens the dealership\'s domain.',
      'All of this happens automatically. You just tap Send.',
    ],
  },
  {
    icon: 'link',
    color: '#5856D6',
    title: 'What Happens Behind Every Link You Share',
    why: 'This is how we build your search presence without you doing anything extra. Every share is tracked, attributed, and structured for maximum visibility.',
    steps: [
      { text: 'Bot check — iMessage, Facebook, and Google preview bots are filtered out so your analytics are always clean and accurate.' },
      { text: 'Duplicate filter — same device clicking twice in 60 seconds counts as one. No click inflation.' },
      { text: 'Identity schema — your name, title, review score, store, and social links are embedded as JSON-LD structured data that AI search engines read to identify you.' },
      { text: 'Backlink citation — your store\'s website is included in the structured data, creating a citation that strengthens the dealership\'s domain authority.' },
      { text: 'UTM attribution — every campaign link carries utm_source=imonsocial&utm_medium=sms so your dealership\'s Google Analytics shows exactly where traffic came from.' },
      { text: 'Contact timeline — every click is logged to that specific customer\'s record so you can see who engaged and when.' },
    ],
  },
  {
    icon: 'person-circle',
    color: '#007AFF',
    title: '1. Complete Your Profile',
    weight: '20 points',
    why: 'Search engines and AI need basic information about you to recommend you. Every field you fill in becomes part of the identity signal attached to every link you share.',
    steps: [
      { text: 'Add a professional profile photo — appears in Google search results and iMessage previews', route: '/my-account', btn: 'Go to My Account' },
      { text: 'Set your job title (e.g., "Senior Sales Consultant") — AI engines use this to categorize what you do', route: '/my-account', btn: 'Go to My Account' },
      { text: 'Add your phone number — part of the NAP (Name, Address, Phone) consistency signal', route: '/my-account', btn: 'Go to My Account' },
      { text: 'Write your bio — use your name, dealership name, and city naturally. AI engines read this for local relevance.', route: '/settings/persona', btn: 'Go to AI Persona' },
      { text: 'Connect LinkedIn, Instagram, Facebook — these become your "sameAs" links, telling AI the person on your card = the person on LinkedIn', route: '/settings/brand-kit', btn: 'Go to Brand Kit' },
    ],
  },
  {
    icon: 'star',
    color: '#FFD60A',
    title: '2. Build Review Strength',
    weight: '20 points',
    why: 'Reviews are the #1 signal AI engines use to recommend a specific person. Your AggregateRating (star average + count) is now embedded in every digital card share — so Google can display your stars directly in search results.',
    steps: [
      { text: 'After every sale, send a review request using your tracked review link — the click is logged to the customer\'s record', route: '/settings/review-links', btn: 'Get Review Link' },
      { text: 'Approve reviews in your Review Center — only approved reviews appear in your schema data and on your card', route: '/settings/review-approvals', btn: 'Review Center' },
      { text: 'Aim for at least 5 reviews — that\'s when AggregateRating becomes visible in Google search results' },
      { text: 'Ask customers to mention your name, the dealership, and the city — this improves local keyword matching for AI answers' },
    ],
  },
  {
    icon: 'share-social',
    color: '#AF52DE',
    title: '3. Distribute Your Content',
    weight: '20 points',
    why: 'Every view of your digital card, every click on your review link, every showcase visit — these are all tracked and feed into your presence score. The more you share, the more signals you generate.',
    steps: [
      { text: 'Share your digital card after every customer interaction — each share embeds your full identity schema into that link', route: '/settings/card-templates', btn: 'View My Card' },
      { text: 'Post your link page on social media — links from your social profiles back to your card strengthen your identity graph', route: '/settings/link-page', btn: 'My Link Page' },
      { text: 'Add your profile link to your email signature — every email becomes a potential search signal' },
      { text: 'Use campaigns to send tracked links automatically — every campaign step generates attribution data', route: '/campaigns', btn: 'My Campaigns' },
    ],
  },
  {
    icon: 'search',
    color: '#34C759',
    title: '4. Boost Search Visibility',
    weight: '20 points',
    why: 'This measures whether real people are finding and visiting your public pages. Every visit is now tracked and counted toward your score — from both direct links and organic search.',
    steps: [
      { text: 'Share your public profile link on social media at least once a week — each post drives organic traffic that feeds your score' },
      { text: 'Ask satisfied customers to Google your name + dealership — repeat visits train Google to rank you higher' },
      { text: 'Make sure your dealership\'s Google Business Profile links to your personal page — this creates a cross-citation that Google rewards' },
      { text: 'Add photos to your showcase — each approved photo becomes a searchable, indexed page with your name attached', route: '/showroom-manage', btn: 'My Showcase' },
    ],
  },
  {
    icon: 'flash',
    color: '#FF9500',
    title: '5. Stay Active & Fresh',
    weight: '20 points',
    why: 'AI engines and search algorithms favor active professionals over dormant ones. Regular activity signals that you\'re a current, engaged, trustworthy person to work with.',
    steps: [
      { text: 'Add new contacts regularly — aim for 10+ per month' },
      { text: 'Send follow-up messages consistently — activity in the app is tracked and weighted' },
      { text: 'Log in daily — even checking Today\'s Touchpoints counts toward your freshness signal' },
      { text: 'Use campaigns to automate your follow-ups so activity never drops', route: '/campaigns', btn: 'SMS Campaigns' },
    ],
  },
  {
    icon: 'bulb',
    color: '#00C7BE',
    title: 'The Pitch for Your Store',
    content: '',
    tips: [
      '"When your salesperson sends a digital card through i\'M On Social, that link tells Google their name, their review score, their store, the store\'s website, and all their social profiles — packaged as invisible machine-readable data. Most CRMs send a text link. We send a reputation signal."',
      '"Every person on your sales team has a public page that is indexed by Google, cited on every share, and connected to your dealership\'s website. The more your team shares, the stronger your dealership\'s domain becomes."',
      '"Your team\'s reviews are embedded as star ratings in Google search results — automatically. No plugins, no agency, no extra work. Every approved review from a customer becomes a structured data signal the moment it\'s shared."',
      'Goal: 80+ score for every team member. At that level, your salespeople dominate local search results and show up in AI recommendations for your market.',
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
