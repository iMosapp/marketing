/**
 * app/broadcast-message.tsx — Quick Broadcast Tool
 *
 * Write a generic message (not addressed to anyone), optionally attach
 * one of your links, then copy to clipboard or share via any app.
 *
 * Use cases:
 *  - Weekly/monthly specials
 *  - Event announcements
 *  - Anything you want to blast out without it sounding personal
 */

import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, StyleSheet,
  ScrollView, Platform, Share, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';

const PROD_BASE = 'https://app.imonsocial.com';

export default function BroadcastMessageScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const s = getStyles(colors);

  const [message, setMessage] = useState('');
  const [selectedLink, setSelectedLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showLinkPicker, setShowLinkPicker] = useState(false);

  const storeSlug = (user as any)?.store_slug || null;
  const reviewUrl = storeSlug
    ? `${PROD_BASE}/review/${storeSlug}${user?._id ? `?sp=${user._id}` : ''}`
    : null;

  const QUICK_LINKS = [
    { label: 'My Digital Card',  icon: 'card',          url: user?._id ? `${PROD_BASE}/card/${user._id}` : null },
    { label: 'My Link Page',     icon: 'link',           url: user?._id ? `${PROD_BASE}/l/${user._id}` : null },
    { label: 'Review Link',      icon: 'star',           url: reviewUrl },
    { label: 'My Showcase',      icon: 'images',         url: user?._id ? `${PROD_BASE}/showcase/${user._id}` : null },
    { label: 'My Landing Page',  icon: 'globe-outline',  url: user?._id ? `${PROD_BASE}/p/${user._id}` : null },
  ].filter(l => l.url);

  // The full message that gets copied / shared
  const fullMessage = [
    message.trim(),
    selectedLink || '',
  ].filter(Boolean).join('\n\n');

  const charCount = fullMessage.length;

  async function handleCopy() {
    if (!fullMessage) return;
    if (Platform.OS === 'web' && navigator.clipboard) {
      await navigator.clipboard.writeText(fullMessage);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  async function handleShare() {
    if (!fullMessage) return;
    try {
      if (Platform.OS !== 'web') {
        await Share.share({ message: fullMessage });
      } else {
        // Web: try native share API, fall back to clipboard
        if (navigator.share) {
          await navigator.share({ text: fullMessage });
        } else {
          await handleCopy();
        }
      }
    } catch {}
  }

  const STARTER_TEMPLATES = [
    "🔥 This month only — check this out:",
    "📣 Quick update for everyone:",
    "🚗 Looking for your next vehicle? We've got something special:",
    "⭐ Happy with your experience? Leave us a quick review:",
    "👋 Hey! Just wanted to share something with you:",
  ];

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={[s.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="chevron-back" size={26} color="#007AFF" />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.text }]}>Quick Broadcast</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">

        {/* Explainer */}
        <View style={[s.infoCard, { backgroundColor: colors.card, borderColor: '#C9A96230' }]}>
          <Ionicons name="megaphone-outline" size={20} color="#C9A962" />
          <Text style={[s.infoText, { color: colors.textSecondary }]}>
            Write a message not addressed to anyone specific. Copy it and paste into any app — iMessage, Instagram, Facebook, email, anywhere.
          </Text>
        </View>

        {/* Message input */}
        <View style={s.section}>
          <View style={s.sectionHeader}>
            <Text style={[s.label, { color: colors.text }]}>Your Message</Text>
            <Text style={[s.charCount, { color: colors.textTertiary }]}>{message.length} chars</Text>
          </View>
          <TextInput
            style={[s.messageInput, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
            value={message}
            onChangeText={setMessage}
            placeholder="Type your message here... e.g. 'This month only — 0% APR on all trucks. Check it out:'"
            placeholderTextColor={colors.textSecondary}
            multiline
            numberOfLines={5}
            autoFocus
            textAlignVertical="top"
            testID="broadcast-message-input"
          />

          {/* Starter templates */}
          <Text style={[s.subLabel, { color: colors.textTertiary }]}>Quick starters:</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
            <View style={{ flexDirection: 'row', gap: 8, paddingBottom: 4 }}>
              {STARTER_TEMPLATES.map((t, i) => (
                <TouchableOpacity
                  key={i}
                  style={[s.starterChip, { backgroundColor: colors.card, borderColor: colors.border }]}
                  onPress={() => setMessage(t)}
                  testID={`starter-${i}`}
                >
                  <Text style={[s.starterText, { color: colors.textSecondary }]} numberOfLines={1}>{t}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        </View>

        {/* Attach a link */}
        <View style={s.section}>
          <Text style={[s.label, { color: colors.text }]}>Attach a Link  <Text style={{ color: colors.textTertiary, fontWeight: '400', fontSize: 14 }}>(optional)</Text></Text>

          {selectedLink ? (
            <View style={[s.selectedLink, { backgroundColor: colors.card, borderColor: '#C9A96240' }]}>
              <Ionicons name="link" size={16} color="#C9A962" />
              <Text style={[s.selectedLinkText, { color: '#C9A962' }]} numberOfLines={1}>{selectedLink}</Text>
              <TouchableOpacity onPress={() => setSelectedLink(null)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity
              style={[s.addLinkBtn, { borderColor: colors.border, backgroundColor: colors.card }]}
              onPress={() => setShowLinkPicker(!showLinkPicker)}
              testID="add-link-btn"
            >
              <Ionicons name={showLinkPicker ? 'chevron-up' : 'add-circle-outline'} size={18} color="#007AFF" />
              <Text style={s.addLinkText}>Add one of your links</Text>
            </TouchableOpacity>
          )}

          {showLinkPicker && !selectedLink && (
            <View style={[s.linkList, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {QUICK_LINKS.map((link, i) => (
                <TouchableOpacity
                  key={i}
                  style={[s.linkItem, i < QUICK_LINKS.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border }]}
                  onPress={() => { setSelectedLink(link.url!); setShowLinkPicker(false); }}
                  testID={`link-option-${i}`}
                >
                  <Ionicons name={link.icon as any} size={18} color="#007AFF" />
                  <View style={{ flex: 1 }}>
                    <Text style={[s.linkItemLabel, { color: colors.text }]}>{link.label}</Text>
                    <Text style={[s.linkItemUrl, { color: colors.textTertiary }]} numberOfLines={1}>{link.url}</Text>
                  </View>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>

        {/* Preview */}
        {fullMessage.length > 0 && (
          <View style={s.section}>
            <Text style={[s.label, { color: colors.text }]}>Preview</Text>
            <View style={[s.preview, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[s.previewText, { color: colors.text }]}>{fullMessage}</Text>
              <Text style={[s.previewCount, { color: colors.textTertiary }]}>{charCount} characters</Text>
            </View>
          </View>
        )}

        {/* Actions */}
        <View style={[s.actions, { borderTopColor: colors.border }]}>
          {/* Copy */}
          <TouchableOpacity
            style={[s.actionBtn, s.copyBtn, !fullMessage && s.actionDisabled]}
            onPress={handleCopy}
            disabled={!fullMessage}
            testID="copy-btn"
          >
            <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={20} color={copied ? '#34C759' : '#fff'} />
            <Text style={[s.actionBtnText, copied && { color: '#34C759' }]}>
              {copied ? 'Copied!' : 'Copy Message'}
            </Text>
          </TouchableOpacity>

          {/* Share */}
          <TouchableOpacity
            style={[s.actionBtn, s.shareBtn, { borderColor: colors.border, backgroundColor: colors.card }, !fullMessage && s.actionDisabled]}
            onPress={handleShare}
            disabled={!fullMessage}
            testID="share-btn"
          >
            <Ionicons name="share-outline" size={20} color={fullMessage ? '#007AFF' : colors.textTertiary} />
            <Text style={[s.actionBtnText, { color: fullMessage ? '#007AFF' : colors.textTertiary }]}>Share</Text>
          </TouchableOpacity>
        </View>

        {/* Tips */}
        <View style={[s.tips, { borderTopColor: colors.border }]}>
          <Text style={[s.tipsTitle, { color: colors.textTertiary }]}>Where to use it:</Text>
          {[
            ['logo-instagram', '#E1306C', 'Instagram — paste in caption or DM'],
            ['logo-facebook',  '#1877F2', 'Facebook — post, story, or group'],
            ['chatbubble',     '#34C759', 'iMessage / SMS — blast to your contacts'],
            ['mail',           '#007AFF', 'Email — paste into a marketing email'],
          ].map(([icon, color, text]) => (
            <View key={icon} style={s.tipRow}>
              <Ionicons name={icon as any} size={16} color={color as string} />
              <Text style={[s.tipText, { color: colors.textSecondary }]}>{text as string}</Text>
            </View>
          ))}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1 },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 19, fontWeight: '600' },
  scroll: { padding: 16, paddingBottom: 32 },

  infoCard: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, padding: 14, borderRadius: 12, borderWidth: 1, marginBottom: 20 },
  infoText: { flex: 1, fontSize: 14, lineHeight: 20 },

  section: { marginBottom: 20 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  label: { fontSize: 16, fontWeight: '700', marginBottom: 8 },
  subLabel: { fontSize: 13, marginTop: 10, marginBottom: 6 },
  charCount: { fontSize: 13 },

  messageInput: { borderRadius: 12, borderWidth: 1, padding: 14, fontSize: 17, minHeight: 130, lineHeight: 24 },

  starterChip: { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, borderWidth: 1, maxWidth: 220 },
  starterText: { fontSize: 13 },

  addLinkBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', padding: 12 },
  addLinkText: { fontSize: 16, color: '#007AFF', fontWeight: '600' },
  selectedLink: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 10, borderWidth: 1, padding: 12 },
  selectedLinkText: { flex: 1, fontSize: 14, fontWeight: '600' },
  linkList: { borderRadius: 12, borderWidth: 1, overflow: 'hidden', marginTop: 8 },
  linkItem: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14 },
  linkItemLabel: { fontSize: 16, fontWeight: '600', marginBottom: 2 },
  linkItemUrl: { fontSize: 12 },

  preview: { borderRadius: 12, borderWidth: 1, padding: 14 },
  previewText: { fontSize: 16, lineHeight: 24 },
  previewCount: { fontSize: 12, marginTop: 8, textAlign: 'right' },

  actions: { flexDirection: 'row', gap: 10, paddingTop: 16, borderTopWidth: 1, marginBottom: 20 },
  actionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 15, borderRadius: 14 },
  actionDisabled: { opacity: 0.4 },
  copyBtn: { backgroundColor: '#C9A962' },
  shareBtn: { borderWidth: 1 },
  actionBtnText: { fontSize: 17, fontWeight: '700', color: '#000' },

  tips: { paddingTop: 20, borderTopWidth: 1, gap: 10 },
  tipsTitle: { fontSize: 13, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 },
  tipRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  tipText: { fontSize: 14 },
});
