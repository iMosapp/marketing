import React, { useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

interface HelpArticle {
  id: string;
  icon: string;
  title: string;
  category: string;
  steps: string[];
  tip?: string;
  navPath?: string;
}

const HELP_ARTICLES: HelpArticle[] = [
  {
    id: 'change-logo',
    icon: 'image-outline',
    title: 'How to Change Your Store Logo',
    category: 'Branding',
    steps: [
      'Go to More > Settings > Store Profile',
      'Under "ACCOUNT LOGO", tap the logo area or "Choose Image"',
      'Select a square image (recommended: 512x512px, max 5MB)',
      'Your new logo will automatically update on Digital Business Cards, Review Pages, Emails, The Showroom, and Congrats Cards',
    ],
    tip: 'Use a square PNG with a transparent background for the best results across all placements.',
    navPath: '/settings/store-profile',
  },
  {
    id: 'brand-kit',
    icon: 'color-palette-outline',
    title: 'How to Set Up Your Brand Kit',
    category: 'Branding',
    steps: [
      'Go to More > Templates & Branding > Brand Kit',
      'Set your brand colors (primary color is used in emails & cards)',
      'Add your social media links (Facebook, Instagram, Twitter, LinkedIn)',
      'These settings are used across all customer-facing pages and emails',
    ],
    tip: 'Your brand colors affect email headers, card accents, and review page themes.',
    navPath: '/settings/brand-kit',
  },
  {
    id: 'send-email',
    icon: 'mail-outline',
    title: 'How to Send an Email from the Inbox',
    category: 'Messaging',
    steps: [
      'Open a conversation from the Inbox tab',
      'Tap the mode banner to switch from SMS to Email',
      'If the contact has no email on file, you\'ll be prompted to enter one',
      'Type your message or attach a template (Digital Card, Review Invite, etc.)',
      'Tap Send — the email will be delivered via your branded template',
    ],
    tip: 'To switch back to SMS, tap the "SMS" button on the mode banner or close the email prompt.',
  },
  {
    id: 'share-showroom',
    icon: 'images-outline',
    title: 'How to Share Your Showroom',
    category: 'Social Proof',
    steps: [
      'Go to More > Performance section > "Share Showroom Link"',
      'Tap to copy your public Showroom URL to clipboard',
      'Share this link on social media, in your email signature, or on business cards',
      'Your Showroom automatically displays your delivery photos and customer reviews',
    ],
    tip: 'You can also view your Showroom by tapping "The Showroom" tile above the share link.',
    navPath: '/showcase',
  },
  {
    id: 'leaderboard',
    icon: 'trophy-outline',
    title: 'How the Leaderboard Works',
    category: 'Gamification',
    steps: [
      'Go to More > Performance section > Leaderboard',
      'Use the tabs at the top to switch scope: My Store, All Stores, or Global',
      'Use category pills (Cards, Reviews, Congrats, etc.) to filter rankings by activity type',
      'Each user is ranked by their count in the selected category, not the combined total',
      'Gold, Silver, and Bronze badges are awarded to the top 3 performers',
    ],
    tip: 'The leaderboard updates in real-time as activity is logged. Use the month selector to view past performance.',
  },
  {
    id: 'congrats-card',
    icon: 'gift-outline',
    title: 'How to Send a Congrats Card',
    category: 'Cards',
    steps: [
      'Open a customer\'s Contact Details page',
      'Tap the "Congrats" quick action button',
      'Take or select a delivery photo with the customer',
      'The card is automatically generated with your branding and a shareable link',
      'Send the link via SMS or Email from the Inbox',
    ],
    tip: 'Congrats cards automatically appear on your Showroom page — great for social proof!',
  },
  {
    id: 'birthday-card',
    icon: 'calendar-outline',
    title: 'How Birthday Cards Work',
    category: 'Cards',
    steps: [
      'Birthday cards are automatically created when a contact has a birthday on file',
      'The system checks daily and generates a personalized birthday card',
      'You can also trigger a card by adding a "birthday" tag to a contact',
      'Each card gets a unique shareable link for the customer',
    ],
    tip: 'Make sure your contacts have their birthday field filled in for automatic card generation.',
  },
  {
    id: 'store-profile',
    icon: 'storefront-outline',
    title: 'How to Update Store Information',
    category: 'Settings',
    steps: [
      'Go to More > Settings > Store Profile',
      'Update your store name, address, phone number, and website',
      'Upload or change your store logo (used everywhere in the app)',
      'Set your store slug for custom public URLs (e.g., review pages)',
      'Save your changes — they take effect immediately across all features',
    ],
    navPath: '/settings/store-profile',
  },
];

const CATEGORIES = ['All', 'Branding', 'Messaging', 'Social Proof', 'Gamification', 'Cards', 'Settings'];

export default function HelpPage() {
  const router = useRouter();
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = selectedCategory === 'All'
    ? HELP_ARTICLES
    : HELP_ARTICLES.filter(a => a.category === selectedCategory);

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="help-back-btn">
          <Ionicons name="chevron-back" size={24} color="#F2F2F7" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Help Center</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.catScroll} contentContainerStyle={s.catRow}>
        {CATEGORIES.map(cat => (
          <TouchableOpacity
            key={cat}
            style={[s.catPill, selectedCategory === cat && s.catPillActive]}
            onPress={() => setSelectedCategory(cat)}
            data-testid={`help-cat-${cat.toLowerCase().replace(/\s/g, '-')}`}
          >
            <Text style={[s.catText, selectedCategory === cat && s.catTextActive]}>{cat}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView style={s.list} contentContainerStyle={s.listContent}>
        {filtered.map(article => {
          const isOpen = expandedId === article.id;
          return (
            <View key={article.id} style={s.card} data-testid={`help-article-${article.id}`}>
              <TouchableOpacity
                style={s.cardHeader}
                onPress={() => setExpandedId(isOpen ? null : article.id)}
                activeOpacity={0.7}
              >
                <View style={s.iconWrap}>
                  <Ionicons name={article.icon as any} size={20} color="#C9A962" />
                </View>
                <View style={s.titleCol}>
                  <Text style={s.articleTitle}>{article.title}</Text>
                  <Text style={s.articleCategory}>{article.category}</Text>
                </View>
                <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={18} color="#636366" />
              </TouchableOpacity>

              {isOpen && (
                <View style={s.stepsContainer}>
                  {article.steps.map((step, i) => (
                    <View key={i} style={s.stepRow}>
                      <View style={s.stepNum}>
                        <Text style={s.stepNumText}>{i + 1}</Text>
                      </View>
                      <Text style={s.stepText}>{step}</Text>
                    </View>
                  ))}
                  {article.tip && (
                    <View style={s.tipBox}>
                      <Ionicons name="bulb-outline" size={16} color="#FFD60A" />
                      <Text style={s.tipText}>{article.tip}</Text>
                    </View>
                  )}
                  {article.navPath && (
                    <TouchableOpacity
                      style={s.goBtn}
                      onPress={() => router.push(article.navPath as any)}
                      data-testid={`help-go-${article.id}`}
                    >
                      <Text style={s.goBtnText}>Go to this setting</Text>
                      <Ionicons name="arrow-forward" size={16} color="#007AFF" />
                    </TouchableOpacity>
                  )}
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: '#F2F2F7', letterSpacing: 0.5 },
  catScroll: { maxHeight: 44, marginBottom: 8 },
  catRow: { paddingHorizontal: 16, gap: 8 },
  catPill: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: '#1C1C1E' },
  catPillActive: { backgroundColor: '#C9A962' },
  catText: { fontSize: 12, fontWeight: '600', color: '#AEAEB2' },
  catTextActive: { color: '#000' },
  list: { flex: 1 },
  listContent: { paddingHorizontal: 16, paddingBottom: 40 },
  card: { backgroundColor: '#1C1C1E', borderRadius: 14, marginBottom: 8, overflow: 'hidden' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, paddingHorizontal: 14, gap: 12 },
  iconWrap: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#C9A96215', justifyContent: 'center', alignItems: 'center' },
  titleCol: { flex: 1 },
  articleTitle: { fontSize: 14, fontWeight: '700', color: '#F2F2F7' },
  articleCategory: { fontSize: 11, color: '#636366', marginTop: 2 },
  stepsContainer: { paddingHorizontal: 14, paddingBottom: 14, gap: 10 },
  stepRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  stepNum: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#C9A96230', justifyContent: 'center', alignItems: 'center', marginTop: 1 },
  stepNumText: { fontSize: 11, fontWeight: '800', color: '#C9A962' },
  stepText: { flex: 1, fontSize: 13, color: '#D1D1D6', lineHeight: 20 },
  tipBox: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: '#FFD60A10', borderRadius: 10, padding: 10, marginTop: 4 },
  tipText: { flex: 1, fontSize: 12, color: '#FFD60A', lineHeight: 18 },
  goBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 6, paddingVertical: 8, borderRadius: 10, backgroundColor: '#007AFF15' },
  goBtnText: { fontSize: 13, fontWeight: '600', color: '#007AFF' },
});
