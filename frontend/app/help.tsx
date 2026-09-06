import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  SafeAreaView, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';

const API = Platform.OS === 'web'
  ? ''
  : (process.env.EXPO_PUBLIC_BACKEND_URL || process.env.REACT_APP_BACKEND_URL || 'https://app.imonsocial.com');

interface HelpArticle {
  id: string;
  icon: string;
  title: string;
  category: string;
  steps: string[];
  tip?: string;
  navPath?: string;
  managerOnly?: boolean;
}

const HELP_ARTICLES: HelpArticle[] = [
  {
    id: 'morning-routine', icon: 'sunny-outline', title: 'What do I do every morning?', category: 'Home',
    steps: ['Open the app. Home shows three cards and nothing else you need to think about', 'Do This Next: tap the gold button to do the one action already chosen for you, or Skip', 'Your 3 for Today: tap Text on each card (the message is already written), or Check if you handled it, or X to skip', 'Needs a Reply: tap any row with a red WAITING badge and answer the customer', 'Done. Log any sale during the day with the gold + then SOLD!'],
    tip: 'Finishing all three cards keeps your streak alive. Streaks are what managers look at first.',
  },
  {
    id: 'jessi-handoff', icon: 'sparkles-outline', title: 'Jessi replied to my customer. Now what?', category: 'Jessi (AI)',
    steps: ['Nothing, if the thread is in the AI filter. Jessi answers inbound texts within seconds, in your voice, 24/7', 'When she hands off you get a You\'re Needed alert and the thread shows a red WAITING badge', 'Open the thread. The gold banner has two buttons: Take Over (you reply, she stays quiet) and All Good (customer just said thanks, clear the flag)', 'After Take Over, tap Resume AI when you are done so she picks the customer back up', 'To pause her for everyone, tap AI ON at the top of Home. Tap again to resume'],
    tip: 'Teach her how you talk under Tools > Settings > My VA, then tap Hear Your VA in Action.', navPath: '/settings/virtual-assistant',
  },
  {
    id: 'send-card', icon: 'id-card-outline', title: 'How do I send my Digital Card?', category: 'My Brand',
    steps: ['Tools > My Brand > Share My Card, pick the contact, send', 'In person: tap the QR icon at the top of Home and let the customer scan it', 'To see or fix your card: Tools > My Brand > My Digital Card > View'],
    tip: 'Your card pulls photo, title and bio from Tools > Settings > My Profile. Change it once, it updates everywhere.', navPath: '/quick-send/digitalcard',
  },
  {
    id: 'get-reviews', icon: 'star-outline', title: 'How do I ask for a review?', category: 'My Brand',
    steps: ['Tools > My Brand > Get Reviews', 'Pick the customer. They get a text with your review link (Google first)', 'Best moment: right after delivery. Send again three days later if they did not tap'],
    navPath: '/quick-send/review',
  },
  {
    id: 'lot-photos', icon: 'camera-outline', title: 'How do I send a vehicle to a customer?', category: 'Inventory',
    steps: ['Gold + on Home > Send Photo', 'Pick the customer, then pick the vehicle from the lot (or take a photo)', 'The customer gets photos and a short lot link', 'The moment they open it you get an alert like "Sarah just opened the Tacoma" with a text already written. Send it while they are looking'],
    tip: 'Tools > Inventory > Hot This Week shows which vehicles shoppers opened most.', navPath: '/quick-send/photo',
  },
  {
    id: 'voice-note', icon: 'mic-outline', title: 'How do I save what I learned about a customer?', category: 'Contacts',
    steps: ['Gold + on Home > Voice Note (or the mic in any thread)', 'Pick the customer and talk: family, hobbies, trips, birthdays, what they bought', 'The app turns it into memory chips on the contact and follow-ups that show up later in Your 3 for Today'],
    tip: 'Do it in the parking lot right after the handshake. Thirty seconds now saves you the awkward "remind me" text later.',
  },
  {
    id: 'log-sale', icon: 'trophy-outline', title: 'How do I log a sale?', category: 'Contacts',
    steps: ['Gold + on Home > SOLD!', 'Pick the customer and the vehicle, snap the delivery photo', 'That one tap sets the anniversary, schedules the review ask and check-ins, and can post the photo to your Showcase'],
    navPath: '/sold-quick',
  },
  {
    id: 'birthday', icon: 'gift-outline', title: 'How do I add a birthday?', category: 'Contacts',
    steps: ['Open the contact > Details tab > Important Dates', 'Tap the orange Add birthday row and pick the date', 'Turn on the birthday text toggle if you want the app to send it for you every year'],
  },
  {
    id: 'import-contacts', icon: 'cloud-upload-outline', title: 'How do I import my phone contacts?', category: 'Contacts',
    steps: ['Contacts tab > Import Contacts', 'Follow the iPhone or Google guide to export a file, then upload it', 'Birthdays come along. Nothing auto-sends until you turn a toggle on'],
    navPath: '/contacts/import',
  },
  {
    id: 'alerts', icon: 'notifications-outline', title: 'Where did that notification go?', category: 'Alerts',
    steps: ['Tap the bell at the top of Home. Every push you receive is also listed here', 'NOW means a customer is waiting or looking right now. TODAY before you leave. LATER is nice to have', 'Swipe left to dismiss, swipe right to snooze until tomorrow morning, tap the gold button to handle it'],
    navPath: '/notifications',
  },
  {
    id: 'no-push', icon: 'alert-circle-outline', title: 'I am not getting push notifications', category: 'Alerts',
    steps: ['Tools > Settings > Notifications > Push Health Check > Send me a test push', 'Read the card: it tells you what is off', 'Most often iPhone Settings > Notifications > i\'M On Social is turned off, or quiet hours are on', 'Quiet hours are in the same screen. Alerts that arrive overnight are held and summarized in the morning'],
    navPath: '/settings/notifications',
  },
  {
    id: 'templates', icon: 'document-text-outline', title: 'How do I save a text I send every day?', category: 'Inbox',
    steps: ['Tools > Settings > My Templates > add one', 'In any thread, tap the document icon to drop it in', 'Templates can include the customer\'s first name automatically'],
    navPath: '/settings/templates',
  },
  {
    id: 'profile', icon: 'person-outline', title: 'How do I change my photo, title or bio?', category: 'Settings',
    steps: ['Tools > tap Profile next to your name (or Tools > Settings > My Profile)', 'Headshot, title, two-sentence bio', 'This powers your Digital Card, Link Page, Landing Page and Showcase'],
    navPath: '/my-profile',
  },
  // ── Manager only ──
  {
    id: 'onboard-rep', icon: 'person-add-outline', title: 'How do I onboard a new rep?', category: 'Managers', managerOnly: true,
    steps: ['Tools > Set Up > Invite Team: first name, last name, email, mobile number, role Salesperson, Send', 'They get a text and an email with the App Store link and three steps (install, Activate my account, enter the code, set a password)', 'Tools > Set Up > Phone Numbers > Buy: pick the rep under Assign to, area code, Search, Buy & assign', 'Have them finish Tools > Learning > Training Hub > Sales Team Onboarding (8 lessons, 30 minutes)'],
    tip: 'No activation text means the mobile number on the account has a typo. Fix it under Team Members and resend.', navPath: '/settings/invite-team',
  },
  {
    id: 'phone-numbers', icon: 'call-outline', title: 'How do I buy, move or release a phone number?', category: 'Managers', managerOnly: true,
    steps: ['Tools > Set Up > Phone Numbers is the only place numbers live', 'Buy: pick the rep (or Number pool), enter an area code, Search, Buy & assign. Texting, calling and Jessi are wired automatically', 'Reassign: pick another rep or Move to Pool. Customers never notice', 'Needs a fix: tap Fix. Release returns the number to the carrier and cannot be undone'],
    navPath: '/admin/twilio-numbers',
  },
  {
    id: 'store-setup', icon: 'storefront-outline', title: 'What does Jessi need from the store?', category: 'Managers', managerOnly: true,
    steps: ['Tools > Set Up > Store Profile: logo, address, hours (hours also drive the after-hours lead rule)', 'Tools > Manage > Inventory Feed: connect HomeNet, vAuto, a catalog link or SFTP, then Pull now', 'Tools > Leads > Lead Source Config: each source green, texting window and call ladder set', 'Tools > Manage > Review Links: the Google link your reps\' Get Reviews button uses'],
    navPath: '/settings/store-profile',
  },
  {
    id: 'what-reps-see', icon: 'eye-outline', title: 'Why do my reps see less than I do?', category: 'Managers', managerOnly: true,
    steps: ['Salespeople get a focused app: three Home cards plus Tools with Today, My Brand, Inventory, Learning, Settings', 'Tap View as Rep on your Tools screen to preview exactly what they get', 'To give one rep more: Tools > Set Up > Team Members > open the rep > Permissions'],
    navPath: '/admin/users',
  },
  {
    id: 'weekly-rhythm', icon: 'calendar-outline', title: 'What should I look at every week?', category: 'Managers', managerOnly: true,
    steps: ['Home > Leads Waiting: claim anything unanswered from the weekend', 'Home > AI Reply Health: anything Jessi failed to send, with the reason', 'Tools > My Performance > Leaderboard and Team Tasks: touches, replies, reviews, overdue follow-ups by rep', 'Home > Hot This Week: what shoppers opened most. Tell the floor'],
    tip: 'Three numbers matter: reply time on WAITING threads, touches per rep per day, reviews earned over review requests sent.',
  },
  {
    id: 'rep-leaves', icon: 'swap-horizontal-outline', title: 'A rep left. How do I keep the relationships?', category: 'Managers', managerOnly: true,
    steps: ['Tools > Set Up > Phone Numbers: Reassign their number to the new rep or Move to Pool', 'Have your iMOS admin move the contacts (Tools > Admin > Bulk Transfer); notes, dates and history come along', 'Tools > Set Up > Team Members: open the rep and Deactivate'],
    navPath: '/admin/twilio-numbers',
  },
  {
    id: 'change-logo', icon: 'image-outline', title: 'How do I change the store logo?', category: 'Managers', managerOnly: true,
    steps: ['Tools > Set Up > Store Profile', 'Tap the logo area under Account Logo and choose a square image (512x512 recommended, max 5MB)', 'It updates on every Digital Card, review page, email, Showcase and congrats card'],
    tip: 'A square PNG with a transparent background looks best everywhere.', navPath: '/settings/store-profile',
  },
  {
    id: 'broadcast', icon: 'megaphone-outline', title: 'How do I send a mass text?', category: 'Managers', managerOnly: true,
    steps: ['Tools > My Brand > Broadcast (or Tools > Campaigns > Broadcast)', 'Pick tags or hand-pick contacts, write the message, attach a photo if you like', 'Sends go out from your tracking number, staggered. Delivery results show per recipient afterwards'],
    navPath: '/broadcast',
  },
];

const MANAGER_ROLES = ['manager', 'admin', 'store_manager', 'org_admin', 'super_admin'];

interface ChatMsg {
  role: 'user' | 'assistant';
  text: string;
}

export default function HelpPage() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAI, setShowAI] = useState(false);
  const chatRef = useRef<ScrollView>(null);

  const isManager = MANAGER_ROLES.includes(user?.role || '') || !!(user as any)?.partner_id;
  const visibleArticles = HELP_ARTICLES.filter(a => !a.managerOnly || isManager);

  // Filter articles by search query (match any word)
  const filtered = query.trim()
    ? (() => {
        const words = query.toLowerCase().split(/\s+/).filter(w => w.length > 2);
        if (words.length === 0) return visibleArticles;
        return visibleArticles.filter(a => {
          const text = `${a.title} ${a.category} ${a.steps.join(' ')}`.toLowerCase();
          return words.some(w => text.includes(w));
        });
      })()
    : visibleArticles;

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
        body: JSON.stringify({ question: q, user_id: user?._id || '' }),
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
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} testID="help-back-btn" dataSet={{ testid: 'help-back-btn' } as any}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.text }]}>Help Center</Text>
        <TouchableOpacity onPress={() => { setShowAI(!showAI); if (!showAI && chatMessages.length === 0) setChatMessages([{ role: 'assistant', text: 'Ask me anything about the app. Where is something, how to do it, what a button does.' }]); }} style={[s.aiToggle, { backgroundColor: colors.card }]} testID="help-ai-toggle" dataSet={{ testid: 'help-ai-toggle' } as any}>
          <Ionicons name={showAI ? 'book-outline' : 'sparkles'} size={20} color={showAI ? colors.text : '#C9A962'} />
        </TouchableOpacity>
      </View>

      {/* Search Bar */}
      <View style={[s.searchWrap, { backgroundColor: colors.card }]}>
        <Ionicons name="search" size={18} color={colors.textTertiary} />
        <TextInput
          style={[s.searchInput, { color: colors.text }]}
          placeholder={showAI ? "Ask a question..." : "Search help articles..."}
          placeholderTextColor={colors.textTertiary}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={showAI ? askAI : undefined}
          returnKeyType={showAI ? 'send' : 'search'}
          testID="help-search-input" dataSet={{ testid: 'help-search-input' } as any}
        />
        {showAI && query.trim() ? (
          <TouchableOpacity onPress={askAI} style={s.sendBtn} testID="help-send-btn" dataSet={{ testid: 'help-send-btn' } as any}>
            <Ionicons name="send" size={16} color={colors.text} />
          </TouchableOpacity>
        ) : query ? (
          <TouchableOpacity onPress={() => setQuery('')} testID="help-clear-btn" dataSet={{ testid: 'help-clear-btn' } as any}>
            <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
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
              <Ionicons name="search-outline" size={40} color={colors.textTertiary} />
              <Text style={s.emptyText}>No articles match "{query}"</Text>
              <TouchableOpacity style={s.askAIBtn} onPress={() => { setShowAI(true); setChatMessages([{ role: 'assistant', text: 'Ask me anything about the app.' }]); askAI(); }}>
                <Ionicons name="sparkles" size={16} color="#C9A962" />
                <Text style={s.askAIText}>Ask AI instead</Text>
              </TouchableOpacity>
            </View>
          )}
          {filtered.map(article => {
            const isOpen = expandedId === article.id;
            return (
              <View key={article.id} style={[s.card, { backgroundColor: colors.card }]} testID={`help-article-${article.id}`} dataSet={{ testid: `help-article-${article.id}` } as any}>
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
                      <TouchableOpacity style={s.goBtn} onPress={() => router.push(article.navPath as any)} testID={`help-go-${article.id}`} dataSet={{ testid: `help-go-${article.id}` } as any}>
                        <Text style={s.goBtnText}>Take me there</Text>
                        <Ionicons name="arrow-forward" size={16} color="#C9A962" />
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
  headerTitle: { fontSize: 19, fontWeight: '800', letterSpacing: 0.5 },
  aiToggle: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  // Search
  searchWrap: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, marginBottom: 12, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 12, gap: 10 },
  searchInput: { flex: 1, fontSize: 17, padding: 0 },
  sendBtn: { width: 30, height: 30, borderRadius: 15, backgroundColor: '#C9A962', justifyContent: 'center', alignItems: 'center' },
  // Chat
  chatArea: { flex: 1 },
  chatContent: { padding: 16, paddingBottom: 40, gap: 12 },
  chatBubble: { maxWidth: '85%', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 16, flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  chatUser: { alignSelf: 'flex-end', backgroundColor: '#C9A962', borderBottomRightRadius: 4 },
  chatBot: { alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
  botIcon: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#C9A96220', justifyContent: 'center', alignItems: 'center', marginTop: 1 },
  chatText: { flex: 1, fontSize: 16, lineHeight: 20 },
  chatTextUser: { color: '#000000' },
  // Articles
  list: { flex: 1 },
  listContent: { paddingHorizontal: 16, paddingBottom: 40 },
  card: { borderRadius: 14, marginBottom: 8, overflow: 'hidden' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, paddingHorizontal: 14, gap: 12 },
  iconWrap: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#C9A96215', justifyContent: 'center', alignItems: 'center' },
  titleCol: { flex: 1 },
  articleTitle: { fontSize: 16, fontWeight: '700' },
  articleCategory: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  stepsContainer: { paddingHorizontal: 14, paddingBottom: 14, gap: 10 },
  stepRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  stepNum: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#C9A96230', justifyContent: 'center', alignItems: 'center', marginTop: 1 },
  stepNumText: { fontSize: 13, fontWeight: '800', color: '#C9A962' },
  stepText: { flex: 1, fontSize: 15, lineHeight: 20 },
  tipBox: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: '#FFD60A10', borderRadius: 10, padding: 10, marginTop: 4 },
  tipText: { flex: 1, fontSize: 14, color: '#FFD60A', lineHeight: 18 },
  goBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 6, paddingVertical: 8, borderRadius: 10, backgroundColor: '#C9A96218' },
  goBtnText: { fontSize: 15, fontWeight: '600', color: '#C9A962' },
  // Empty state
  emptyState: { alignItems: 'center', justifyContent: 'center', paddingTop: 60, gap: 12 },
  emptyText: { fontSize: 16, color: '#8E8E93' },
  askAIBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 20, backgroundColor: '#C9A96215', marginTop: 8 },
  askAIText: { fontSize: 16, fontWeight: '600', color: '#C9A962' },
});
