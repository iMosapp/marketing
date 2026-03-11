import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput,
  Modal, Animated, ScrollView, ActivityIndicator,
  KeyboardAvoidingView, Platform, Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { usePathname } from 'expo-router';
import { Audio } from 'expo-av';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';

const { height: SCREEN_H } = Dimensions.get('window');
const PANEL_H = Math.min(SCREEN_H * 0.75, 600);

// Friendly route labels for context
const ROUTE_LABELS: Record<string, string> = {
  '/(tabs)/home': 'Home Dashboard',
  '/(tabs)/contacts': 'Contacts List',
  '/(tabs)/inbox': 'Inbox / Messages',
  '/(tabs)/activity': 'Activity Feed',
  '/(tabs)/more': 'Menu',
  '/(tabs)/dialer': 'Dialer',
  '/(tabs)/touchpoints': 'Touchpoints',
  '/settings/brand-kit': 'Brand Kit Settings',
  '/settings/my-profile': 'My Profile',
  '/settings/tags': 'Tag Management',
  '/settings/templates': 'Templates',
  '/settings/email-templates': 'Email Templates',
  '/settings/review-links': 'Review Links',
  '/settings/date-triggers': 'Date Triggers',
  '/settings/store-profile': 'Store Profile',
  '/admin/manage-team': 'Manage Team',
  '/admin/leaderboard': 'Leaderboard',
  '/admin/hot-leads': 'Hot Leads',
  '/admin/crm-dashboard': 'CRM Dashboard',
  '/admin/activity-feed': 'Team Activity Feed',
};

function getPageLabel(pathname: string): string {
  if (ROUTE_LABELS[pathname]) return ROUTE_LABELS[pathname];
  // Expo Router may strip the (tabs) group — match without it
  const cleaned = pathname.replace('/(tabs)', '');
  for (const [route, label] of Object.entries(ROUTE_LABELS)) {
    const routeCleaned = route.replace('/(tabs)', '');
    if (cleaned === routeCleaned) return label;
  }
  // Pattern matching for dynamic routes
  if (pathname.includes('/contact/')) return 'Contact Record';
  if (pathname.includes('/thread/')) return 'Conversation Thread';
  if (pathname.includes('/settings')) return 'Settings';
  if (pathname.includes('/admin')) return 'Admin Panel';
  if (pathname.includes('/tasks')) return 'Tasks';
  if (pathname.includes('/home')) return 'Home Dashboard';
  if (pathname.includes('/contacts')) return 'Contacts List';
  if (pathname.includes('/inbox')) return 'Inbox / Messages';
  if (pathname.includes('/activity')) return 'Activity Feed';
  if (pathname.includes('/more')) return 'Menu';
  if (pathname.includes('/dialer')) return 'Dialer';
  if (pathname.includes('/touchpoints')) return 'Touchpoints';
  return '';
}

// Public routes where the button should NOT appear
const HIDDEN_ROUTES = ['/auth/', '/onboarding', '/timeline/', '/congrats/', '/review/', '/card/', '/l/', '/jessie'];

type Message = { role: 'user' | 'assistant'; text: string };

export default function JessieFloatingChat() {
  const { colors } = useThemeStore();
  const user = useAuthStore((s) => s.user);
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const scrollRef = useRef<ScrollView>(null);
  const slideAnim = useRef(new Animated.Value(0)).current;
  const soundRef = useRef<Audio.Sound | null>(null);

  // Slide animation
  useEffect(() => {
    Animated.timing(slideAnim, {
      toValue: open ? 1 : 0,
      duration: 250,
      useNativeDriver: true,
    }).start();
  }, [open]);

  // Stop any playing audio when panel closes
  useEffect(() => {
    if (!open && soundRef.current) {
      soundRef.current.stopAsync().catch(() => {});
      soundRef.current.unloadAsync().catch(() => {});
      soundRef.current = null;
      setSpeaking(false);
    }
  }, [open]);

  // Don't render on public/auth pages or if not logged in
  if (!user?._id) return null;
  if (HIDDEN_ROUTES.some((r) => pathname.startsWith(r))) return null;

  const pageLabel = getPageLabel(pathname);

  // Extract contact_id from pathname if on a contact record
  const contactId = pathname.includes('/contact/') ? pathname.split('/contact/')[1]?.split('/')[0] || '' : '';

  const playVoice = async (text: string) => {
    if (!voiceEnabled) return;
    try {
      // Stop any currently playing audio
      if (soundRef.current) {
        await soundRef.current.stopAsync().catch(() => {});
        await soundRef.current.unloadAsync().catch(() => {});
        soundRef.current = null;
      }
      setSpeaking(true);
      const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
      const res = await fetch(`${backendUrl}/api/jessie/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.slice(0, 4000) }),
      });
      if (!res.ok) throw new Error('TTS failed');
      const blob = await res.blob();
      const uri = URL.createObjectURL(blob);
      const { sound } = await Audio.Sound.createAsync({ uri });
      soundRef.current = sound;
      sound.setOnPlaybackStatusUpdate((status: any) => {
        if (status.didJustFinish) {
          setSpeaking(false);
          sound.unloadAsync().catch(() => {});
          soundRef.current = null;
        }
      });
      await sound.playAsync();
    } catch {
      setSpeaking(false);
    }
  };

  const sendMessage = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: msg }]);
    setLoading(true);

    try {
      // Step 1: Get text response instantly (no voice)
      const res = await api.post('/jessie/chat', {
        user_id: user._id,
        message: msg,
        include_voice: false,
        current_page: pageLabel || pathname,
        contact_id: contactId,
      }, { timeout: 30000 });

      const responseText = res.data.text;
      setMessages((prev) => [...prev, { role: 'assistant', text: responseText }]);

      // Step 2: Fire off TTS in background (non-blocking)
      if (voiceEnabled && responseText) {
        playVoice(responseText);
      }
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', text: "Sorry, I couldn't process that. Try again." }]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const handleOpen = () => {
    setOpen(true);
    // Add contextual greeting on first open
    if (messages.length === 0) {
      const name = user.name ? ' ' + user.name.split(' ')[0] : '';
      const contextMsg = pageLabel
        ? `Hey${name}! I see you're on the ${pageLabel}. How can I help?`
        : `Hey${name}! I'm Jessi, your AI assistant. Ask me anything about the app — I know every feature inside and out.`;
      setMessages([{ role: 'assistant', text: contextMsg }]);
    }
  };

  return (
    <>
      {/* Slim top bar — "Have questions? Ask Jessi" */}
      {!open && (
        <TouchableOpacity
          onPress={handleOpen}
          activeOpacity={0.7}
          style={[s.topBar, { top: insets.top, backgroundColor: colors.bg, borderBottomColor: colors.border }]}
          data-testid="jessi-top-bar"
        >
          <Text style={[s.topBarText, { color: colors.textSecondary || '#8E8E93' }]}>
            Have questions? Ask Jessi
          </Text>
        </TouchableOpacity>
      )}

      {/* Chat Panel Modal */}
      <Modal visible={open} transparent animationType="none" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity style={s.backdrop} activeOpacity={1} onPress={() => setOpen(false)} />
        <Animated.View
          style={[
            s.panel,
            { backgroundColor: colors.bg, borderColor: colors.border },
            {
              transform: [{
                translateY: slideAnim.interpolate({
                  inputRange: [0, 1],
                  outputRange: [PANEL_H, 0],
                }),
              }],
            },
          ]}
        >
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={{ flex: 1 }}
            keyboardVerticalOffset={0}
          >
            {/* Panel Header */}
            <View style={[s.panelHeader, { borderBottomColor: colors.border }]}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <View style={s.avatarSmall}>
                  <Ionicons name="chatbubble-ellipses" size={16} color="#000" />
                </View>
                <View>
                  <Text style={[s.panelTitle, { color: colors.text }]}>Jessi</Text>
                  {pageLabel ? (
                    <Text style={s.pageContext} numberOfLines={1}>{pageLabel}</Text>
                  ) : null}
                </View>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <TouchableOpacity
                  onPress={() => {
                    setVoiceEnabled(!voiceEnabled);
                    if (soundRef.current) {
                      soundRef.current.stopAsync().catch(() => {});
                      soundRef.current.unloadAsync().catch(() => {});
                      soundRef.current = null;
                      setSpeaking(false);
                    }
                  }}
                  data-testid="jessie-voice-toggle"
                  style={{ padding: 4 }}
                >
                  <Ionicons
                    name={voiceEnabled ? 'volume-high' : 'volume-mute'}
                    size={20}
                    color={voiceEnabled ? '#C9A962' : '#6E6E73'}
                  />
                </TouchableOpacity>
                <TouchableOpacity onPress={() => setOpen(false)} data-testid="jessie-close">
                  <Ionicons name="close" size={24} color={colors.textSecondary || '#8E8E93'} />
                </TouchableOpacity>
              </View>
            </View>

            {/* Messages */}
            <ScrollView
              ref={scrollRef}
              style={s.messagesArea}
              contentContainerStyle={s.messagesContent}
              onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
            >
              {messages.length === 0 && (
                <View style={s.emptyState}>
                  <Ionicons name="chatbubble-ellipses-outline" size={40} color="#C9A962" />
                  <Text style={[s.emptyTitle, { color: colors.text }]}>Ask Jessi anything</Text>
                  <Text style={[s.emptyHint, { color: colors.textSecondary || '#8E8E93' }]}>
                    How do I send a card? Where are my templates?{'\n'}How do I track my team?
                  </Text>
                </View>
              )}
              {messages.map((m, i) => (
                <View
                  key={i}
                  style={[
                    s.msgBubble,
                    m.role === 'user' ? s.userBubble : [s.assistantBubble, { backgroundColor: colors.card }],
                  ]}
                  data-testid={`jessie-msg-${i}`}
                >
                  <Text style={[s.msgText, { color: m.role === 'user' ? '#fff' : colors.text }]}>
                    {m.text}
                  </Text>
                  {m.role === 'assistant' && speaking && i === messages.length - 1 && (
                    <View style={s.speakingRow}>
                      <Ionicons name="volume-high" size={12} color="#C9A962" />
                      <Text style={s.speakingText}>Speaking...</Text>
                    </View>
                  )}
                </View>
              ))}
              {loading && (
                <View style={[s.msgBubble, s.assistantBubble, { backgroundColor: colors.card }]}>
                  <ActivityIndicator size="small" color="#C9A962" />
                </View>
              )}
            </ScrollView>

            {/* Input Bar */}
            <View style={[s.inputBar, { borderTopColor: colors.border, backgroundColor: colors.bg }]}>
              <TextInput
                style={[s.input, { backgroundColor: colors.card, color: colors.text }]}
                placeholder="Ask Jessi..."
                placeholderTextColor="#6E6E73"
                value={input}
                onChangeText={setInput}
                onSubmitEditing={sendMessage}
                returnKeyType="send"
                editable={!loading}
                data-testid="jessie-input"
              />
              <TouchableOpacity
                onPress={sendMessage}
                disabled={!input.trim() || loading}
                style={[s.sendBtn, (!input.trim() || loading) && { opacity: 0.4 }]}
                data-testid="jessie-send"
              >
                <Ionicons name="arrow-up-circle" size={36} color="#C9A962" />
              </TouchableOpacity>
            </View>
          </KeyboardAvoidingView>
        </Animated.View>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  topBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 22,
    zIndex: 9999,
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  topBarText: {
    fontSize: 11,
    fontWeight: '400',
    letterSpacing: 0.2,
  },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  panel: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: PANEL_H,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    borderBottomWidth: 0,
    overflow: 'hidden',
  },
  panelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  avatarSmall: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#C9A962',
    alignItems: 'center',
    justifyContent: 'center',
  },
  panelTitle: { fontSize: 16, fontWeight: '700' },
  pageContext: { fontSize: 11, color: '#8E8E93', marginTop: 1 },
  messagesArea: { flex: 1 },
  messagesContent: { padding: 16, gap: 10 },
  emptyState: { alignItems: 'center', paddingTop: 40, gap: 8 },
  emptyTitle: { fontSize: 17, fontWeight: '600' },
  emptyHint: { fontSize: 13, textAlign: 'center', lineHeight: 20 },
  msgBubble: { maxWidth: '85%', padding: 12, borderRadius: 16 },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#C9A962',
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
  },
  msgText: { fontSize: 14, lineHeight: 20 },
  speakingRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6 },
  speakingText: { fontSize: 11, color: '#C9A962', fontWeight: '500' },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    gap: 8,
  },
  input: {
    flex: 1,
    height: 40,
    borderRadius: 20,
    paddingHorizontal: 16,
    fontSize: 14,
  },
  sendBtn: { padding: 2 },
});
