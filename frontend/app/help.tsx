import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../store/themeStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

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
    id: 'change-logo', icon: 'image-outline', title: 'How to Change Your Store Logo', category: 'Branding',
    steps: ['Go to More > Settings > Store Profile', 'Under "ACCOUNT LOGO", tap the logo area or "Choose Image"', 'Select a square image (recommended: 512x512px, max 5MB)', 'Your new logo will automatically update on Digital Business Cards, Review Pages, Emails, The Showcase, and Congrats Cards'],
    tip: 'Use a square PNG with a transparent background for the best results across all placements.', navPath: '/settings/store-profile',
  },
  {
    id: 'brand-kit', icon: 'color-palette-outline', title: 'How to Set Up Your Brand Kit', category: 'Branding',
    steps: ['Go to More > Templates & Branding > Brand Kit', 'Set your brand colors (primary color is used in emails & cards)', 'Add your social media links (Facebook, Instagram, Twitter, LinkedIn)', 'These settings are used across all customer-facing pages and emails'],
    tip: 'Your brand colors affect email headers, card accents, and review page themes.', navPath: '/settings/brand-kit',
  },
  {
    id: 'send-email', icon: 'mail-outline', title: 'How to Send an Email from the Inbox', category: 'Messaging',
    steps: ['Open a conversation from the Inbox tab', 'Tap the mode banner to switch from SMS to Email', 'If the contact has no email on file, you\'ll be prompted to enter one', 'Type your message or attach a template (Digital Card, Review Invite, etc.)', 'Tap Send'],
    tip: 'To switch back to SMS, tap the "SMS" button on the mode banner.',
  },
  {
    id: 'share-showroom', icon: 'images-outline', title: 'How to Share Your Showcase', category: 'Social Proof',
    steps: ['Go to Home > "My Showcase" tile', 'Tap to share your public Showcase URL via link, text, or email', 'Share this link on social media, in your email signature, or on business cards', 'Your Showcase automatically displays your delivery photos and customer reviews'],
    navPath: '/showcase',
  },
  {
    id: 'leaderboard', icon: 'trophy-outline', title: 'How the Leaderboard Works', category: 'Gamification',
    steps: ['Go to More > Performance section > Leaderboard', 'Use the tabs at the top to switch scope: My Store, All Stores, or Global', 'Use category pills to filter rankings by activity type', 'Gold, Silver, and Bronze badges are awarded to the top 3 performers'],
    tip: 'The leaderboard updates in real-time as activity is logged.',
  },
  {
    id: 'congrats-card', icon: 'gift-outline', title: 'How to Send a Congrats Card', category: 'Cards',
    steps: ['Open a customer\'s Contact Details page', 'Tap the "Congrats" quick action button', 'Take or select a delivery photo with the customer', 'The card is automatically generated with your branding and a shareable link', 'Send the link via SMS or Email from the Inbox'],
  },
  {
    id: 'add-tag', icon: 'pricetag-outline', title: 'How to Add Tags to a Contact', category: 'Contacts',
    steps: ['Open a contact\'s detail page', 'Find the Tags strip below the contact info', 'Tap the blue "+" button', 'Select a tag from the picker', 'The tag is saved immediately'],
    tip: 'You can search contacts by tag name from the Contacts tab.',
  },
  {
    id: 'automations', icon: 'calendar-outline', title: 'How Date Automations Work', category: 'Automations',
    steps: ['Open a contact\'s detail page', 'The Automations strip shows date triggers like Birthday, Anniversary, Sold Date', 'Tap any chip to edit the date or clear it', 'Date triggers can automatically send cards or messages on those dates'],
  },
  {
    id: 'store-profile', icon: 'storefront-outline', title: 'How to Update Store Information', category: 'Settings',
    steps: ['Go to More > Settings > Store Profile', 'Update your store name, address, phone number, and website', 'Upload or change your store logo', 'Set your store slug for custom public URLs', 'Save your changes'],
    navPath: '/settings/store-profile',
  },
  {
    id: 'campaigns', icon: 'rocket-outline', title: 'How to Create a Campaign', category: 'Campaigns',
    steps: ['Go to More > Campaigns > SMS or Email Campaigns', 'Tap "New Campaign" or the "+" button', 'Set the campaign name, target audience, and schedule', 'Compose your messages for each step in the sequence', 'Activate the campaign to start enrolling contacts'],
  },
  {
    id: 'broadcast', icon: 'megaphone-outline', title: 'How to Send a Broadcast', category: 'Campaigns',
    steps: ['Go to More > Campaigns > Broadcast', 'Select your target audience or choose contacts manually', 'Compose your message', 'Review and send the broadcast'],
  },
];

interface ChatMsg {
  role: 'user' | 'assistant';
  text: string;
}

export default function HelpPage() {
  const router = useRouter();
  const colors = useThemeStore(s => s.colors);
  const [query, setQuery] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAI, setShowAI] = useState(false);
  const chatRef = useRef<ScrollView>(null);

  // Filter articles by search query (match any word)
  const filtered = query.trim()
    ? (() => {
        const words = query.toLowerCase().split(/\s+/).filter(w => w.length > 2);
        if (words.length === 0) return HELP_ARTICLES;
        return HELP_ARTICLES.filter(a => {
          const text = `${a.title} ${a.category} ${a.steps.join(' ')}`.toLowerCase();
          return words.some(w => text.includes(w));
        });
      })()
    : HELP_ARTICLES;

  const askAI = async () => {
    const q = query.trim();
    if (!q || loading) return;
    setShowAI(true);
    setChatMessages(prev => [...prev, { role: 'user', text: q }]);
    setQuery('');
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/help-center/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { role: 'assistant', text: data.answer || 'No response.' }]);
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', text: 'Could not connect to the AI assistant. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (chatRef.current && chatMessages.length) {
      setTimeout(() => chatRef.current?.scrollToEnd?.({ animated: true }), 100);
    }
  }, [chatMessages]);

  return (
    <SafeAreaView style={[s.safe, { backgroundColor: colors.bg }]}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="help-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.text }]}>Help Center</Text>
        <TouchableOpacity onPress={() => { setShowAI(!showAI); if (!showAI && chatMessages.length === 0) setChatMessages([{ role: 'assistant', text: "Hi! I'm your iMOs assistant. Ask me anything about the app and I'll help you out." }]); }} style={[s.aiToggle, { backgroundColor: colors.card }]} data-testid="help-ai-toggle">
          <Ionicons name={showAI ? 'book-outline' : 'sparkles'} size={20} color={showAI ? colors.text : '#C9A962'} />
        </TouchableOpacity>
      </View>

      {/* Search Bar */}
      <View style={[s.searchWrap, { backgroundColor: colors.card }]}>
        <Ionicons name="search" size={18} color={colors.textTertiary} />
        <TextInput
          style={[s.searchInput, { color: colors.text }]}
          placeholder={showAI ? "Ask a question..." : "Search help articles..."}
          placeholderTextColor="#636366"
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={showAI ? askAI : undefined}
          returnKeyType={showAI ? 'send' : 'search'}
          data-testid="help-search-input"
        />
        {showAI && query.trim() ? (
          <TouchableOpacity onPress={askAI} style={s.sendBtn} data-testid="help-send-btn">
            <Ionicons name="send" size={16} color="#FFF" />
          </TouchableOpacity>
        ) : query ? (
          <TouchableOpacity onPress={() => setQuery('')} data-testid="help-clear-btn">
            <Ionicons name="close-circle" size={18} color="#636366" />
          </TouchableOpacity>
        ) : null}
      </View>

      {/* AI Chat or Articles */}
      {showAI ? (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView ref={chatRef} style={s.chatArea} contentContainerStyle={s.chatContent}>
            {chatMessages.map((msg, i) => (
              <View key={i} style={[s.chatBubble, msg.role === 'user' ? s.chatUser : [s.chatBot, { backgroundColor: colors.card }]]}>
                {msg.role === 'assistant' && (
                  <View style={s.botIcon}>
                    <Ionicons name="sparkles" size={12} color="#C9A962" />
                  </View>
                )}
                <Text style={[s.chatText, { color: colors.text }, msg.role === 'user' && s.chatTextUser]}>{msg.text}</Text>
              </View>
            ))}
            {loading && (
              <View style={[s.chatBubble, s.chatBot, { backgroundColor: colors.card }]}>
                <View style={s.botIcon}><Ionicons name="sparkles" size={12} color="#C9A962" /></View>
                <ActivityIndicator size="small" color="#C9A962" />
              </View>
            )}
          </ScrollView>
        </KeyboardAvoidingView>
      ) : (
        <ScrollView style={s.list} contentContainerStyle={s.listContent}>
          {filtered.length === 0 && (
            <View style={s.emptyState}>
              <Ionicons name="search-outline" size={40} color="#636366" />
              <Text style={s.emptyText}>No articles match "{query}"</Text>
              <TouchableOpacity style={s.askAIBtn} onPress={() => { setShowAI(true); setChatMessages([{ role: 'assistant', text: "Hi! I'm your iMOs assistant. Ask me anything about the app and I'll help you out." }]); askAI(); }}>
                <Ionicons name="sparkles" size={16} color="#C9A962" />
                <Text style={s.askAIText}>Ask AI instead</Text>
              </TouchableOpacity>
            </View>
          )}
          {filtered.map(article => {
            const isOpen = expandedId === article.id;
            return (
              <View key={article.id} style={[s.card, { backgroundColor: colors.card }]} data-testid={`help-article-${article.id}`}>
                <TouchableOpacity style={s.cardHeader} onPress={() => setExpandedId(isOpen ? null : article.id)} activeOpacity={0.7}>
                  <View style={s.iconWrap}>
                    <Ionicons name={article.icon as any} size={20} color="#C9A962" />
                  </View>
                  <View style={s.titleCol}>
                    <Text style={[s.articleTitle, { color: colors.text }]}>{article.title}</Text>
                    <Text style={s.articleCategory}>{article.category}</Text>
                  </View>
                  <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textTertiary} />
                </TouchableOpacity>
                {isOpen && (
                  <View style={s.stepsContainer}>
                    {article.steps.map((step, i) => (
                      <View key={i} style={s.stepRow}>
                        <View style={s.stepNum}><Text style={s.stepNumText}>{i + 1}</Text></View>
                        <Text style={[s.stepText, { color: colors.textSecondary }]}>{step}</Text>
                      </View>
                    ))}
                    {article.tip && (
                      <View style={s.tipBox}>
                        <Ionicons name="bulb-outline" size={16} color="#FFD60A" />
                        <Text style={s.tipText}>{article.tip}</Text>
                      </View>
                    )}
                    {article.navPath && (
                      <TouchableOpacity style={s.goBtn} onPress={() => router.push(article.navPath as any)} data-testid={`help-go-${article.id}`}>
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
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 18, fontWeight: '800', letterSpacing: 0.5 },
  aiToggle: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  // Search
  searchWrap: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, marginBottom: 12, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 12, gap: 10 },
  searchInput: { flex: 1, fontSize: 15, padding: 0 },
  sendBtn: { width: 30, height: 30, borderRadius: 15, backgroundColor: '#C9A962', justifyContent: 'center', alignItems: 'center' },
  // Chat
  chatArea: { flex: 1 },
  chatContent: { padding: 16, paddingBottom: 40, gap: 12 },
  chatBubble: { maxWidth: '85%', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 16, flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  chatUser: { alignSelf: 'flex-end', backgroundColor: '#007AFF', borderBottomRightRadius: 4 },
  chatBot: { alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
  botIcon: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#C9A96220', justifyContent: 'center', alignItems: 'center', marginTop: 1 },
  chatText: { flex: 1, fontSize: 14, lineHeight: 20 },
  chatTextUser: { color: '#FFF' },
  // Articles
  list: { flex: 1 },
  listContent: { paddingHorizontal: 16, paddingBottom: 40 },
  card: { borderRadius: 14, marginBottom: 8, overflow: 'hidden' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, paddingHorizontal: 14, gap: 12 },
  iconWrap: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#C9A96215', justifyContent: 'center', alignItems: 'center' },
  titleCol: { flex: 1 },
  articleTitle: { fontSize: 14, fontWeight: '700' },
  articleCategory: { fontSize: 11, color: '#636366', marginTop: 2 },
  stepsContainer: { paddingHorizontal: 14, paddingBottom: 14, gap: 10 },
  stepRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  stepNum: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#C9A96230', justifyContent: 'center', alignItems: 'center', marginTop: 1 },
  stepNumText: { fontSize: 11, fontWeight: '800', color: '#C9A962' },
  stepText: { flex: 1, fontSize: 13, lineHeight: 20 },
  tipBox: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: '#FFD60A10', borderRadius: 10, padding: 10, marginTop: 4 },
  tipText: { flex: 1, fontSize: 12, color: '#FFD60A', lineHeight: 18 },
  goBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 6, paddingVertical: 8, borderRadius: 10, backgroundColor: '#007AFF15' },
  goBtnText: { fontSize: 13, fontWeight: '600', color: '#007AFF' },
  // Empty state
  emptyState: { alignItems: 'center', justifyContent: 'center', paddingTop: 60, gap: 12 },
  emptyText: { fontSize: 14, color: '#636366' },
  askAIBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 20, backgroundColor: '#C9A96215', marginTop: 8 },
  askAIText: { fontSize: 14, fontWeight: '600', color: '#C9A962' },
});
