/**
 * app/broadcast-card.tsx — Create a Shareable Card
 *
 * Simple: pick a photo → write a message → tap Create → copy the link.
 * Post the link on Facebook, Instagram, anywhere. Anyone who taps it sees the card.
 * No recipient required. No contact needed.
 */

import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, StyleSheet,
  ScrollView, Platform, ActivityIndicator, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';

const PROD_BASE = 'https://app.imonsocial.com';

export default function BroadcastCardScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();

  const [photo, setPhoto] = useState<{ uri: string; blob?: Blob } | null>(null);
  const [message, setMessage] = useState('');
  const [creating, setCreating] = useState(false);
  const [cardLink, setCardLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // ── Pick photo ────────────────────────────────────────────────────────────
  function pickPhoto() {
    if (Platform.OS === 'web') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.style.cssText = 'position:fixed;top:-9999px;opacity:0;';
      document.body.appendChild(input);
      input.onchange = async (e: any) => {
        const file = e.target.files?.[0];
        try { document.body.removeChild(input); } catch {}
        if (!file) return;
        const uri = URL.createObjectURL(file);
        setPhoto({ uri, blob: file });
      };
      input.addEventListener('cancel', () => { try { document.body.removeChild(input); } catch {} });
      input.click();
    } else {
      (async () => {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
          showSimpleAlert('Permission needed', 'Allow photo library access to add a photo to your card.');
          return;
        }
        const result = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          quality: 0.85,
        });
        if (!result.canceled && result.assets?.[0]) {
          setPhoto({ uri: result.assets[0].uri });
        }
      })();
    }
  }

  // ── Create card ───────────────────────────────────────────────────────────
  async function createCard() {
    if (!user?._id) return;
    if (!photo) { showSimpleAlert('Add a Photo', 'Pick a photo for your card first.'); return; }

    setCreating(true);
    try {
      const fd = new FormData();
      fd.append('salesman_id', user._id);
      fd.append('customer_name', '');
      fd.append('card_type', 'congrats');
      fd.append('generic', 'true');
      if (message.trim()) fd.append('custom_message', message.trim());

      // Attach photo
      if (Platform.OS === 'web' && photo.blob) {
        fd.append('photo', photo.blob, 'card-photo.jpg');
      } else if (photo.uri) {
        const ext = photo.uri.split('.').pop() || 'jpg';
        fd.append('photo', { uri: photo.uri, type: `image/${ext}`, name: `card.${ext}` } as any);
      }

      const res = await api.post('/congrats/create', fd);
      const cardId = res.data?.card_id;
      const link = res.data?.short_url || `${PROD_BASE}/congrats/${cardId}`;
      setCardLink(link);
      try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success); } catch {}
    } catch (err: any) {
      showSimpleAlert('Error', err?.response?.data?.detail || 'Failed to create card. Please try again.');
    } finally {
      setCreating(false);
    }
  }

  // ── Copy link ─────────────────────────────────────────────────────────────
  async function copyLink() {
    if (!cardLink) return;
    try {
      if (Platform.OS === 'web' && navigator.clipboard) {
        await navigator.clipboard.writeText(cardLink);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
      try { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success); } catch {}
    } catch {}
  }

  function openCard() {
    if (!cardLink) return;
    if (Platform.OS === 'web') window.open(cardLink, '_blank');
  }

  function reset() {
    setPhoto(null);
    setMessage('');
    setCardLink(null);
    setCopied(false);
  }

  const s = getStyles(colors);

  // ── After card is created — show the link ─────────────────────────────────
  if (cardLink) {
    return (
      <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
        <View style={[s.header, { borderBottomColor: colors.border }]}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
            <Ionicons name="chevron-back" size={26} color="#007AFF" />
          </TouchableOpacity>
          <Text style={[s.headerTitle, { color: colors.text }]}>Card Ready!</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView contentContainerStyle={s.scroll}>
          {/* Success icon */}
          <View style={s.successIcon}>
            <Ionicons name="checkmark-circle" size={64} color="#34C759" />
          </View>
          <Text style={[s.successTitle, { color: colors.text }]}>Your card is live</Text>
          <Text style={[s.successSub, { color: colors.textSecondary }]}>
            Copy the link and post it anywhere — Facebook, Instagram, iMessage, email. Anyone who taps the link will see your card.
          </Text>

          {/* The link — big and obvious */}
          <View style={[s.linkBox, { backgroundColor: colors.card, borderColor: '#C9A96240' }]}>
            <Ionicons name="link" size={18} color="#C9A962" style={{ marginRight: 8 }} />
            <Text style={[s.linkText, { color: colors.textSecondary }]} numberOfLines={2} selectable>{cardLink}</Text>
          </View>

          {/* COPY — the main action */}
          <TouchableOpacity
            style={[s.copyBtn, copied && { backgroundColor: '#34C759' }]}
            onPress={copyLink}
            testID="copy-card-link"
          >
            <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={22} color="#000" />
            <Text style={s.copyBtnText}>{copied ? 'Copied! Now paste it anywhere.' : 'Copy Link'}</Text>
          </TouchableOpacity>

          {/* Secondary: preview */}
          {Platform.OS === 'web' && (
            <TouchableOpacity style={[s.previewBtn, { borderColor: colors.border, backgroundColor: colors.card }]} onPress={openCard}>
              <Ionicons name="eye-outline" size={20} color={colors.text} />
              <Text style={[s.previewBtnText, { color: colors.text }]}>Preview Card</Text>
            </TouchableOpacity>
          )}

          {/* Tips */}
          <View style={[s.tipsBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[s.tipsTitle, { color: colors.textTertiary }]}>Where to paste the link:</Text>
            {[
              ['logo-facebook',  '#1877F2', 'Facebook — new post, story, or message'],
              ['logo-instagram', '#E1306C', 'Instagram — bio link or DM'],
              ['chatbubble',     '#34C759', 'iMessage — group text or individual'],
              ['mail',           '#007AFF', 'Email — newsletter or follow-up'],
            ].map(([icon, color, text]) => (
              <View key={icon as string} style={s.tipRow}>
                <Ionicons name={icon as any} size={16} color={color as string} />
                <Text style={[s.tipText, { color: colors.textSecondary }]}>{text as string}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity style={s.anotherBtn} onPress={reset}>
            <Ionicons name="add-circle-outline" size={18} color="#C9A962" />
            <Text style={{ color: '#C9A962', fontWeight: '700', fontSize: 16 }}>Create Another Card</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── Card creation form ────────────────────────────────────────────────────
  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <View style={[s.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="chevron-back" size={26} color="#007AFF" />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.text }]}>Create a Card</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
        <Text style={[s.explainer, { color: colors.textSecondary }]}>
          Add a photo and message. Tap Create — you'll get a link to post anywhere.
        </Text>

        {/* Step 1: Photo */}
        <View style={s.step}>
          <Text style={[s.stepLabel, { color: colors.textTertiary }]}>1. Add a photo</Text>
          {photo ? (
            <View style={s.photoPreviewWrap}>
              <Image source={{ uri: photo.uri }} style={s.photoPreview} resizeMode="cover" />
              <TouchableOpacity style={s.photoRemove} onPress={() => setPhoto(null)}>
                <Ionicons name="close-circle" size={26} color="#FF3B30" />
              </TouchableOpacity>
              <View style={s.photoReady}>
                <Ionicons name="checkmark-circle" size={16} color="#34C759" />
                <Text style={{ color: '#34C759', fontSize: 12, fontWeight: '600', marginLeft: 4 }}>Photo added</Text>
              </View>
            </View>
          ) : (
            <TouchableOpacity style={[s.photoPickBtn, { borderColor: colors.border, backgroundColor: colors.card }]} onPress={pickPhoto} testID="pick-photo">
              <Ionicons name="image-outline" size={28} color="#C9A962" />
              <Text style={[s.photoPickText, { color: '#C9A962' }]}>Tap to add a photo</Text>
              <Text style={[s.photoPickSub, { color: colors.textTertiary }]}>Pick from your camera roll</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Step 2: Message */}
        <View style={s.step}>
          <Text style={[s.stepLabel, { color: colors.textTertiary }]}>2. Write your message  <Text style={{ fontWeight: '400' }}>(optional)</Text></Text>
          <TextInput
            style={[s.messageInput, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
            value={message}
            onChangeText={setMessage}
            placeholder="e.g. This week only — 0% APR on all trucks!"
            placeholderTextColor={colors.textSecondary}
            multiline
            numberOfLines={4}
            textAlignVertical="top"
            testID="card-message"
          />
        </View>

        {/* Create button */}
        <TouchableOpacity
          style={[s.createBtn, (!photo || creating) && s.createBtnDisabled]}
          onPress={createCard}
          disabled={!photo || creating}
          testID="create-card-btn"
        >
          {creating ? (
            <>
              <ActivityIndicator color="#000" />
              <Text style={s.createBtnText}>Creating your card...</Text>
            </>
          ) : (
            <>
              <Ionicons name="sparkles" size={20} color="#000" />
              <Text style={s.createBtnText}>Create Card & Get Link</Text>
            </>
          )}
        </TouchableOpacity>

        {!photo && (
          <Text style={[s.hint, { color: colors.textTertiary }]}>Add a photo first to create your card</Text>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1 },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 19, fontWeight: '600' },
  scroll: { padding: 16, paddingBottom: 40 },
  explainer: { fontSize: 15, lineHeight: 22, marginBottom: 24 },

  step: { marginBottom: 24 },
  stepLabel: { fontSize: 14, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 },

  photoPickBtn: { borderRadius: 16, borderWidth: 2, borderStyle: 'dashed', padding: 36, alignItems: 'center', gap: 8 },
  photoPickText: { fontSize: 17, fontWeight: '700' },
  photoPickSub: { fontSize: 13 },
  photoPreviewWrap: { borderRadius: 16, overflow: 'hidden', position: 'relative', height: 220 },
  photoPreview: { width: '100%', height: 220 },
  photoRemove: { position: 'absolute', top: 10, right: 10 },
  photoReady: { position: 'absolute', bottom: 10, left: 10, flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 20, paddingHorizontal: 10, paddingVertical: 5 },

  messageInput: { borderRadius: 14, borderWidth: 1, padding: 14, fontSize: 17, minHeight: 100 },

  createBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#C9A962', borderRadius: 16, paddingVertical: 18, marginTop: 8 },
  createBtnDisabled: { opacity: 0.5 },
  createBtnText: { fontSize: 18, fontWeight: '800', color: '#000' },
  hint: { fontSize: 13, textAlign: 'center', marginTop: 8 },

  // Success screen
  successIcon: { alignItems: 'center', paddingVertical: 24 },
  successTitle: { fontSize: 28, fontWeight: '800', textAlign: 'center', marginBottom: 10 },
  successSub: { fontSize: 15, textAlign: 'center', lineHeight: 22, marginBottom: 24 },
  linkBox: { flexDirection: 'row', alignItems: 'center', borderRadius: 12, borderWidth: 1, padding: 14, marginBottom: 16 },
  linkText: { flex: 1, fontSize: 14 },
  copyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#C9A962', borderRadius: 16, paddingVertical: 18, marginBottom: 12 },
  copyBtnText: { fontSize: 18, fontWeight: '800', color: '#000' },
  previewBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderWidth: 1, borderRadius: 14, paddingVertical: 14, marginBottom: 24 },
  previewBtnText: { fontSize: 16, fontWeight: '600' },
  tipsBox: { borderRadius: 14, borderWidth: 1, padding: 16, gap: 10, marginBottom: 24 },
  tipsTitle: { fontSize: 13, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 },
  tipRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  tipText: { fontSize: 14 },
  anotherBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14 },
});
