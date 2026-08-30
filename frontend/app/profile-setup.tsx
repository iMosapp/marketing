/**
 * profile-setup.tsx — Streamlined Phase 1 onboarding.
 *
 * 3 screens, done in under 3 minutes:
 *   1. Your Info      → confirm name + job title + profile photo
 *   2. Your Bio       → one text box + AI-generate button
 *   3. Send Your Card → enter a contact name + phone → sends VCF + card link
 *
 * After tapping "Send" (or skipping), onboarding_complete = true → home.
 * The full persona wizard remains at /settings/persona for power users.
 */

import React, { useState, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, Platform, Animated, Linking,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';
import { resolveUserPhotoUrlHiRes } from '../utils/photoUrl';

const PROD_BASE = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
const TOTAL_STEPS = 3;

// ── tiny progress dots ──────────────────────────────────────────────────────
function StepDots({ step }: { step: number }) {
  return (
    <View style={{ flexDirection: 'row', gap: 7, justifyContent: 'center', marginBottom: 28 }}>
      {[1, 2, 3].map(i => (
        <View key={i} style={{
          width: i === step ? 22 : 8, height: 8,
          borderRadius: 4,
          backgroundColor: i === step ? '#C9A962' : i < step ? '#C9A96260' : '#33333350',
        }} />
      ))}
    </View>
  );
}

export default function ProfileSetupScreen() {
  const router   = useRouter();
  const { user, setUser } = useAuthStore();
  const [step, setStep]   = useState(1);
  const [saving, setSaving] = useState(false);
  const fadeAnim = useRef(new Animated.Value(1)).current;

  // Step 1
  const [name,  setName]  = useState(user?.name || '');
  const [title, setTitle] = useState((user as any)?.persona?.title || (user as any)?.title || '');
  const [photoUploading, setPhotoUploading] = useState(false);

  // Step 2
  const [bio, setBio]           = useState((user as any)?.persona?.bio || '');
  const [generatingBio, setGeneratingBio] = useState(false);

  // Step 3
  const [recipientName,  setRecipientName]  = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [cardSent, setCardSent] = useState(false);

  const photoUrl = resolveUserPhotoUrlHiRes(user as any);

  // ── Helpers ────────────────────────────────────────────────────────────────
  const animateStep = (next: number) => {
    Animated.sequence([
      Animated.timing(fadeAnim, { toValue: 0, duration: 120, useNativeDriver: true }),
      Animated.timing(fadeAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
    ]).start();
    setStep(next);
  };

  // ── Step 1: save name + title ──────────────────────────────────────────────
  const saveStep1 = async () => {
    if (!name.trim()) { showSimpleAlert('Required', 'Please enter your name.'); return; }
    setSaving(true);
    try {
      const persona = { ...(user as any)?.persona, title: title.trim() };
      await api.patch(`/users/${user!._id}`, { name: name.trim(), persona });
      setUser({ ...user!, name: name.trim(), persona } as any);
      animateStep(2);
    } catch { showSimpleAlert('Error', 'Could not save. Please try again.'); }
    finally { setSaving(false); }
  };

  // ── Step 2: save bio ───────────────────────────────────────────────────────
  const saveStep2 = async () => {
    setSaving(true);
    try {
      const persona = { ...(user as any)?.persona, bio: bio.trim(), title: title.trim() };
      await api.patch(`/users/${user!._id}`, { persona });
      setUser({ ...user!, persona } as any);
      animateStep(3);
    } catch { showSimpleAlert('Error', 'Could not save bio.'); }
    finally { setSaving(false); }
  };

  // ── Step 2: AI generate bio ────────────────────────────────────────────────
  const generateBio = async () => {
    setGeneratingBio(true);
    try {
      const res = await api.post(`/profile/${user!._id}/generate-bio`, {
        name: name.trim(),
        title: title.trim(),
      });
      setBio(res.data?.bio || '');
    } catch { showSimpleAlert('Error', 'Could not generate bio. Try again or write your own!'); }
    finally { setGeneratingBio(false); }
  };

  // ── Photo upload ───────────────────────────────────────────────────────────
  const pickPhoto = async () => {
    if (Platform.OS === 'web') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.onchange = async (e: any) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setPhotoUploading(true);
        try {
          const fd = new FormData();
          fd.append('file', file);
          const res = await api.post(`/profile/${user!._id}/photo`, fd);
          if (res.data?.photo_url || res.data?.url) {
            const photoUrl = res.data.photo_url || res.data.url;
            setUser({ ...user!, photo_url: photoUrl } as any);
          }
        } catch { showSimpleAlert('Error', 'Photo upload failed.'); }
        finally { setPhotoUploading(false); }
      };
      input.click();
    } else {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') { showSimpleAlert('Permission needed', 'Allow photo access to upload your photo.'); return; }
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.85, allowsEditing: true, aspect: [1, 1] });
      if (result.canceled || !result.assets?.[0]) return;
      setPhotoUploading(true);
      try {
        const asset = result.assets[0];
        const fd = new FormData();
        fd.append('file', { uri: asset.uri, name: 'photo.jpg', type: asset.mimeType || 'image/jpeg' } as any);
        const res = await api.post(`/profile/${user!._id}/photo`, fd);
        if (res.data?.photo_url || res.data?.url) {
          setUser({ ...user!, photo_url: res.data.photo_url || res.data.url } as any);
        }
      } catch { showSimpleAlert('Error', 'Photo upload failed.'); }
      finally { setPhotoUploading(false); }
    }
  };

  // ── Step 3: send card via native SMS ──────────────────────────────────────
  const sendCard = async () => {
    const phone = recipientPhone.replace(/\D/g, '');
    if (!phone) { showSimpleAlert('Required', 'Enter a phone number to send to.'); return; }

    const cardUrl   = `${PROD_BASE}/card/${user!._id}`;
    const vcfUrl    = `${PROD_BASE}/api/profile/${user!._id}/vcard.vcf`;
    const firstName = (user?.name || '').split(' ')[0] || 'me';
    const recipFirst = (recipientName.trim().split(' ')[0]) || 'there';

    const smsBody = `Hey ${recipFirst}! It was great connecting with you. Tap here to save my contact info: ${vcfUrl} — and here's my digital card with everything about me: ${cardUrl}`;

    const smsUrl = Platform.OS === 'ios'
      ? `sms:${phone}&body=${encodeURIComponent(smsBody)}`
      : `sms:${phone}?body=${encodeURIComponent(smsBody)}`;

    // Log it server-side (non-blocking)
    try {
      const conv = await api.post(`/messages/conversations/${user!._id}`, { contact_phone: `+1${phone}` });
      const convId = conv.data?._id || conv.data?.id;
      if (convId) {
        api.post(`/messages/send/${user!._id}/${convId}`, {
          conversation_id: convId,
          content: smsBody,
          channel: 'sms_personal',
          event_type: 'digital_card_sent',
        }).catch(() => {});
      }
    } catch {}

    // Open native SMS (the actual send)
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      window.location.href = smsUrl;
    } else {
      Linking.openURL(smsUrl).catch(() => {});
    }

    setCardSent(true);
  };

  // ── Mark complete + go home ────────────────────────────────────────────────
  const finish = async () => {
    try {
      await api.post(`/auth/complete-onboarding`, {
        user_id: user!._id,
        name: name.trim(),
        bio: bio.trim(),
      });
      setUser({ ...user!, onboarding_complete: true } as any);
    } catch {}
    router.replace('/(tabs)/home');
  };

  // ══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════════
  return (
    <View style={s.root}>
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <ScrollView
          contentContainerStyle={s.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Animated.View style={{ opacity: fadeAnim, flex: 1 }}>

            {/* ── STEP 1: Name + Photo ──────────────────────────────────── */}
            {step === 1 && (
              <View style={s.stepWrap}>
                <Text style={s.eyebrow}>Step 1 of 3</Text>
                <Text style={s.heading}>Let's get you set up</Text>
                <Text style={s.sub}>This is what customers will see on your digital card.</Text>

                <StepDots step={1} />

                {/* Photo upload */}
                <TouchableOpacity style={s.avatarWrap} onPress={pickPhoto} disabled={photoUploading}>
                  {photoUrl ? (
                    <Image source={{ uri: photoUrl }} style={s.avatar} contentFit="cover" />
                  ) : (
                    <View style={[s.avatar, s.avatarPlaceholder]}>
                      <Ionicons name="person" size={44} color="#C9A962" />
                    </View>
                  )}
                  <View style={s.avatarBadge}>
                    {photoUploading
                      ? <ActivityIndicator size="small" color="#fff" />
                      : <Ionicons name="camera" size={16} color="#fff" />
                    }
                  </View>
                </TouchableOpacity>
                <Text style={s.avatarHint}>
                  {photoUrl ? 'Tap to change photo' : 'Tap to upload your photo'}
                </Text>

                {/* Name */}
                <Text style={s.label}>Your Name</Text>
                <TextInput
                  style={s.input}
                  value={name}
                  onChangeText={setName}
                  placeholder="Forest Ward"
                  placeholderTextColor="#666"
                  autoCapitalize="words"
                  data-testid="onboard-name-input"
                />

                {/* Title */}
                <Text style={s.label}>Job Title <Text style={s.optional}>(optional)</Text></Text>
                <TextInput
                  style={s.input}
                  value={title}
                  onChangeText={setTitle}
                  placeholder="Sales Director, Service Advisor, etc."
                  placeholderTextColor="#666"
                  autoCapitalize="words"
                  data-testid="onboard-title-input"
                />

                <TouchableOpacity style={s.primaryBtn} onPress={saveStep1} disabled={saving} data-testid="step1-next">
                  {saving ? <ActivityIndicator color="#000" /> : (
                    <><Text style={s.primaryBtnText}>Next</Text><Ionicons name="arrow-forward" size={18} color="#000" style={{ marginLeft: 6 }} /></>
                  )}
                </TouchableOpacity>
              </View>
            )}

            {/* ── STEP 2: Bio ───────────────────────────────────────────── */}
            {step === 2 && (
              <View style={s.stepWrap}>
                <Text style={s.eyebrow}>Step 2 of 3</Text>
                <Text style={s.heading}>Tell your story</Text>
                <Text style={s.sub}>This shows on your digital card. Keep it personal — customers connect with real people.</Text>

                <StepDots step={2} />

                <TextInput
                  style={[s.input, s.bioInput]}
                  value={bio}
                  onChangeText={setBio}
                  placeholder={`Hi, I'm ${name.split(' ')[0] || 'Forest'}. Tell customers a bit about yourself — your experience, what you love about your work, something personal…`}
                  placeholderTextColor="#555"
                  multiline
                  numberOfLines={6}
                  textAlignVertical="top"
                  data-testid="onboard-bio-input"
                />

                <TouchableOpacity style={s.aiBtn} onPress={generateBio} disabled={generatingBio} data-testid="generate-bio-btn">
                  {generatingBio ? (
                    <><ActivityIndicator size="small" color="#C9A962" /><Text style={s.aiBtnText}>Writing your bio…</Text></>
                  ) : (
                    <><Ionicons name="sparkles" size={16} color="#C9A962" /><Text style={s.aiBtnText}>Write it for me with AI</Text></>
                  )}
                </TouchableOpacity>

                <View style={s.rowBtns}>
                  <TouchableOpacity style={s.backBtn} onPress={() => animateStep(1)}>
                    <Ionicons name="arrow-back" size={18} color="#C9A962" />
                  </TouchableOpacity>
                  <TouchableOpacity style={[s.primaryBtn, { flex: 1 }]} onPress={saveStep2} disabled={saving} data-testid="step2-next">
                    {saving ? <ActivityIndicator color="#000" /> : (
                      <><Text style={s.primaryBtnText}>Next</Text><Ionicons name="arrow-forward" size={18} color="#000" style={{ marginLeft: 6 }} /></>
                    )}
                  </TouchableOpacity>
                </View>

                <TouchableOpacity style={s.skipLink} onPress={() => animateStep(3)}>
                  <Text style={s.skipText}>Skip for now</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* ── STEP 3: Send First Card ───────────────────────────────── */}
            {step === 3 && (
              <View style={s.stepWrap}>
                {!cardSent ? (
                  <>
                    <Text style={s.eyebrow}>Step 3 of 3</Text>
                    <View style={s.celebrationIcon}>
                      <Ionicons name="card" size={44} color="#C9A962" />
                    </View>
                    <Text style={s.heading}>Your card is ready!</Text>
                    <Text style={s.sub}>
                      Send it to someone right now. They'll get a text to save your contact and open your digital card — all in one tap.
                    </Text>

                    <StepDots step={3} />

                    {/* Preview card chip */}
                    <View style={s.cardPreview}>
                      <View style={s.cardPreviewAvatar}>
                        {photoUrl
                          ? <Image source={{ uri: photoUrl }} style={{ width: 40, height: 40, borderRadius: 20 }} contentFit="cover" />
                          : <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="person" size={22} color="#C9A962" /></View>
                        }
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.cardPreviewName}>{name || 'Your Name'}</Text>
                        {title ? <Text style={s.cardPreviewTitle}>{title}</Text> : null}
                      </View>
                      <Ionicons name="checkmark-circle" size={22} color="#34C759" />
                    </View>

                    <Text style={s.label}>Send to (name)</Text>
                    <TextInput
                      style={s.input}
                      value={recipientName}
                      onChangeText={setRecipientName}
                      placeholder="Customer name"
                      placeholderTextColor="#666"
                      autoCapitalize="words"
                      data-testid="recipient-name-input"
                    />

                    <Text style={s.label}>Their phone number</Text>
                    <TextInput
                      style={s.input}
                      value={recipientPhone}
                      onChangeText={setRecipientPhone}
                      placeholder="(801) 555-1234"
                      placeholderTextColor="#666"
                      keyboardType="phone-pad"
                      data-testid="recipient-phone-input"
                    />

                    <Text style={s.sendNote}>
                      They'll get a text to save your contact info + a link to your digital card.
                    </Text>

                    <TouchableOpacity style={s.sendBtn} onPress={sendCard} data-testid="send-card-btn">
                      <Ionicons name="send" size={18} color="#000" />
                      <Text style={s.sendBtnText}>Send My Card</Text>
                    </TouchableOpacity>

                    <View style={[s.rowBtns, { marginTop: 12 }]}>
                      <TouchableOpacity style={s.backBtn} onPress={() => animateStep(2)}>
                        <Ionicons name="arrow-back" size={18} color="#C9A962" />
                      </TouchableOpacity>
                    </View>

                    <TouchableOpacity style={s.skipLink} onPress={finish}>
                      <Text style={s.skipText}>Skip — I'll send it later</Text>
                    </TouchableOpacity>
                  </>
                ) : (
                  /* ── Sent! confirmation ── */
                  <View style={s.doneWrap}>
                    <View style={s.celebrationIcon}>
                      <Ionicons name="checkmark-circle" size={64} color="#34C759" />
                    </View>
                    <Text style={s.heading}>Card sent!</Text>
                    <Text style={s.sub}>
                      {recipientName ? `${recipientName.split(' ')[0]} will` : 'They\'ll'} get a text to save your contact and open your card.{'\n\n'}
                      Welcome to I'm On Social — you're live.
                    </Text>
                    <TouchableOpacity style={s.primaryBtn} onPress={finish} data-testid="finish-onboarding-btn">
                      <Text style={s.primaryBtnText}>Go to my dashboard</Text>
                      <Ionicons name="arrow-forward" size={18} color="#000" style={{ marginLeft: 6 }} />
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            )}

          </Animated.View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root:           { flex: 1, backgroundColor: '#0A0A0A' },
  scroll:         { flexGrow: 1, padding: 24, paddingTop: 16 },
  stepWrap:       { flex: 1 },

  eyebrow:        { fontSize: 12, fontWeight: '700', color: '#C9A962', textTransform: 'uppercase', letterSpacing: 1.5, textAlign: 'center', marginBottom: 8 },
  heading:        { fontSize: 30, fontWeight: '800', color: '#FFFFFF', textAlign: 'center', marginBottom: 10, lineHeight: 36 },
  sub:            { fontSize: 15, color: '#8E8E93', textAlign: 'center', lineHeight: 22, marginBottom: 28, paddingHorizontal: 8 },

  // Avatar
  avatarWrap:     { alignSelf: 'center', marginBottom: 8, position: 'relative' },
  avatar:         { width: 110, height: 110, borderRadius: 55, borderWidth: 3, borderColor: '#C9A962' },
  avatarPlaceholder: { backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' },
  avatarBadge:    { position: 'absolute', bottom: 2, right: 2, width: 32, height: 32, borderRadius: 16, backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#0A0A0A' },
  avatarHint:     { textAlign: 'center', fontSize: 13, color: '#636366', marginBottom: 24 },

  // Inputs
  label:          { fontSize: 13, fontWeight: '600', color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8, marginTop: 4 },
  optional:       { fontWeight: '400', textTransform: 'none', letterSpacing: 0, color: '#636366' },
  input:          { backgroundColor: '#1C1C1E', borderRadius: 12, padding: 16, fontSize: 17, color: '#FFFFFF', borderWidth: 1, borderColor: '#2C2C2E', marginBottom: 16 },
  bioInput:       { minHeight: 130, textAlignVertical: 'top' },

  // AI button
  aiBtn:          { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderWidth: 1, borderColor: '#C9A96240', borderRadius: 12, padding: 13, marginBottom: 20, backgroundColor: '#C9A96210' },
  aiBtnText:      { fontSize: 15, fontWeight: '600', color: '#C9A962' },

  // Buttons
  primaryBtn:     { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#C9A962', borderRadius: 14, padding: 17, marginBottom: 4 },
  primaryBtnText: { fontSize: 18, fontWeight: '800', color: '#000' },
  backBtn:        { width: 50, height: 52, borderRadius: 14, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#2C2C2E', marginRight: 10 },
  rowBtns:        { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  skipLink:       { alignItems: 'center', paddingVertical: 14 },
  skipText:       { fontSize: 14, color: '#636366' },

  // Card preview
  cardPreview:    { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14, marginBottom: 22, borderWidth: 1, borderColor: '#C9A96230' },
  cardPreviewAvatar: {},
  cardPreviewName: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  cardPreviewTitle: { fontSize: 13, color: '#8E8E93', marginTop: 2 },

  // Send
  sendNote:       { fontSize: 13, color: '#636366', textAlign: 'center', lineHeight: 19, marginBottom: 16, paddingHorizontal: 8 },
  sendBtn:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', borderRadius: 14, padding: 18, marginBottom: 4 },
  sendBtnText:    { fontSize: 18, fontWeight: '800', color: '#000' },

  // Done
  doneWrap:       { alignItems: 'center', paddingTop: 20 },
  celebrationIcon:{ width: 90, height: 90, borderRadius: 45, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center', alignSelf: 'center', marginBottom: 20 },
});
