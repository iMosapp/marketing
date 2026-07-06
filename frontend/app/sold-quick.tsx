import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput,
  Image, ActivityIndicator, Platform, Animated, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as MediaLibrary from 'expo-media-library';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';

const IS_WEB = Platform.OS === 'web';
const ACCENT = '#C9A962';
const APP_URL = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';

export default function SoldQuickScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();

  const [photo, setPhoto] = useState<{ uri: string; type: string; name: string } | null>(null);
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [lookingUp, setLookingUp] = useState(false);
  const checkAnim = useRef(new Animated.Value(0)).current;

  // Send type selector
  const [sendType, setSendType] = useState<'photo' | 'card'>('photo');
  const [congratsText, setCongratsText] = useState('CONGRATULATIONS!');
  // Referral tracking
  const [referredByName, setReferredByName] = useState('');
  const [referredById, setReferredById] = useState('');
  const [referralSearch, setReferralSearch] = useState('');
  const [referralResults, setReferralResults] = useState<any[]>([]);

  // Campaign selection
  const [availableCampaigns, setAvailableCampaigns] = useState<any[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('');
  const [selectedCampaignName, setSelectedCampaignName] = useState<string>('');

  useEffect(() => {
    if (!user?._id) return;
    api.get(`/campaigns/${user._id}?active=true`).then(res => {
      const camps = (res.data?.campaigns || res.data || []).filter((c: any) =>
        c.active && (
          c.trigger_tag?.toLowerCase() === 'sold' ||
          c.type?.includes('sold') ||
          c.name?.toLowerCase().includes('sold') ||
          c.name?.toLowerCase().includes('follow')
        )
      );
      setAvailableCampaigns(camps);
      if (camps.length > 0 && !selectedCampaignId) {
        setSelectedCampaignId(camps[0]._id || camps[0].id);
        setSelectedCampaignName(camps[0].name);
      }
    }).catch(() => {});
  }, [user?._id]);  const [showReferralSearch, setShowReferralSearch] = useState(false);

  // Referral contact search
  useEffect(() => {
    if (!referralSearch || referralSearch.length < 2 || !user?._id) { setReferralResults([]); return; }
    const t = setTimeout(async () => {
      try {
        const res = await api.get(`/contacts/${user._id}?search=${encodeURIComponent(referralSearch)}&limit=5`);
        const list = Array.isArray(res.data) ? res.data : res.data?.contacts || [];
        setReferralResults(list.slice(0, 5));
      } catch { setReferralResults([]); }
    }, 400);
    return () => clearTimeout(t);
  }, [referralSearch, user?._id]);

  // Auto-lookup contact by phone
  useEffect(() => {
    if (!user?._id || !customerPhone || customerPhone.replace(/\D/g, '').length < 10) return;
    if (customerName) return;
    const timer = setTimeout(async () => {
      try {
        setLookingUp(true);
        const res = await api.get(`/contacts/${user._id}/check-duplicate?phone=${encodeURIComponent(customerPhone)}`);
        const m = (res.data?.matches || [])[0];
        if (m) {
          const name = `${m.first_name || ''} ${m.last_name || ''}`.trim();
          if (name) setCustomerName(name);
        }
      } catch {}
      finally { setLookingUp(false); }
    }, 600);
    return () => clearTimeout(timer);
  }, [customerPhone, user?._id]);

  // Read any image (HEIC/PNG/JPEG) as blob and force JPEG type
  const toJpegBlob = async (uri: string): Promise<{ uri: string; type: string; name: string }> => {
    // On iOS, expo-image-picker with quality set converts to JPEG internally
    // Return the uri directly — FormData will handle it
    return { uri, type: 'image/jpeg', name: 'delivery.jpg' };
  };

  const takePhoto = async () => {
    try {
      if (!IS_WEB) {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') { showSimpleAlert('Permission Needed', 'Camera access is required.'); return; }
      }
      const result = await ImagePicker.launchCameraAsync({ quality: 0.6, allowsEditing: false, exif: false });
      if (!result.canceled && result.assets[0]) {
        const a = result.assets[0];
        // Save to camera roll immediately
        if (!IS_WEB) {
          try {
            const { status } = await MediaLibrary.requestPermissionsAsync();
            if (status === 'granted') await MediaLibrary.saveToLibraryAsync(a.uri);
          } catch {}
        }
        const converted = await toJpegBlob(a.uri);
        setPhoto(converted);
      }
    } catch (e) { showSimpleAlert('Error', 'Could not open camera.'); }
  };

  const pickFromLibrary = async () => {
    try {
      if (!IS_WEB) {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') { showSimpleAlert('Permission Needed', 'Photo library access is required.'); return; }
      }
      // quality:0.6 forces iOS to export as JPEG regardless of source format (HEIC etc.)
      const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.6, allowsEditing: false, exif: false });
      if (!result.canceled && result.assets[0]) {
        const a = result.assets[0];
        const converted = await toJpegBlob(a.uri);
        setPhoto(converted);
      }
    } catch (e) { showSimpleAlert('Error', 'Could not open photo library.'); }
  };

  const handleSend = async () => {
    if (!user?._id) return;
    if (!customerPhone.trim()) { showSimpleAlert('Phone Required', 'Enter the customer\'s phone number.'); return; }
    if (!customerName.trim()) { showSimpleAlert('Name Required', 'Enter the customer\'s name.'); return; }
    if (sendType === 'photo' && !photo) {
      showSimpleAlert('Photo Required', 'Please take a photo or choose from your camera roll to use the Delivery Photo option. Or switch to Digital Card.');
      return;
    }
    // Normalize to E.164 — prevents duplicate conversations from format mismatches
    const rawDigits = customerPhone.trim().replace(/\D/g, '');
    const normalizedPhone = rawDigits.length === 10 ? `+1${rawDigits}` : rawDigits.length === 11 && rawDigits[0] === '1' ? `+${rawDigits}` : normalizedPhone;
    setSending(true);
    try {
      // Step 1: Find or create contact
      const contactRes = await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
        name: customerName.trim(),
        phone: normalizedPhone,
        event_type: 'congrats_card_sent',
        event_title: 'Sold',
        ...(referredById ? { referred_by: referredById, referred_by_name: referredByName } : {}),
      });
      const contactId = contactRes.data.contact_id;

      // Create the congrats card (needed for Digital Card path and for the contact record)
      const cardFormData = new FormData();
      cardFormData.append('salesman_id', user._id);
      cardFormData.append('customer_name', customerName.trim());
      cardFormData.append('customer_phone', normalizedPhone);
      cardFormData.append('card_type', 'congrats');
      cardFormData.append('contact_id', contactId);
      cardFormData.append('tags', JSON.stringify(['Sold']));
      const cardRes = await api.post('/congrats/create', cardFormData, { headers: { 'X-User-ID': user._id } });
      const cardUrl = cardRes.data?.short_url || `${APP_URL}/congrats/${cardRes.data?.card_id}`;

      // Step 3: Get review link
      const rlRes = await api.get(`/users/${user._id}/review-links`).catch(() => ({ data: {} }));
      const reviewUrl = (rlRes.data as any)?.imos_review_url || (rlRes.data as any)?.review_url || '';

      // Step 4: VCF immediately
      const vcfUrl = `${APP_URL}/api/profile/${user._id}/vcard.vcf`;
      const firstName = customerName.trim().split(' ')[0];
      await api.post('/messages/twilio-send', {
        to: normalizedPhone,
        body: `Hi ${firstName}! This is ${user.name}, tap to save my number so you always have it.`,
        user_id: user._id,
        contact_id: contactId,
        media_urls: [vcfUrl],
        event_type: 'vcf_sent',
      }).catch(() => {});

      // Step 5: Congrats — 2 minutes
      // Photo: upload native photo and send as MMS (no overlay processing)
      // Card: send the digital card link
      if (sendType === 'photo') {
        let photoMediaUrl = '';
        if (photo) {
          try {
            const uploadForm = new FormData();
            if (IS_WEB) {
              const resp = await fetch(photo.uri);
              const blob = await resp.blob();
              uploadForm.append('file', blob, 'delivery.jpg');
            } else {
              uploadForm.append('file', { uri: photo.uri, type: 'image/jpeg', name: 'delivery.jpg' } as any);
            }
            const uploadRes = await api.post('/images/upload', uploadForm, {
              headers: { 'Content-Type': 'multipart/form-data' },
            });
            const path = uploadRes.data?.original_url || '';
            if (path) {
              // Append ?format=jpeg — Twilio needs JPEG, not WebP, for reliable MMS delivery
              const absPath = path.startsWith('http') ? path : `${APP_URL}${path}`;
              photoMediaUrl = `${absPath}?format=jpeg`;
            }
          } catch (e) {
            console.log('Photo upload failed:', e);
          }
        }
        await api.post('/messages/schedule-delayed', {
          to: normalizedPhone,
          body: congratsText.trim() || `Congratulations ${firstName}! It was a pleasure working with you today!`,
          user_id: user._id,
          contact_id: contactId,
          contact_name: customerName.trim(),
          delay_seconds: 120,
          ...(photoMediaUrl ? { media_urls: [photoMediaUrl] } : {}),
          event_type: 'congrats_card_sent',
        }).catch(() => {});
      } else {
        // Digital Card link
        await api.post('/messages/schedule-delayed', {
          to: normalizedPhone,
          body: `Congratulations ${firstName}! It was a pleasure working with you today. Here is your delivery card! ${cardUrl}`,
          user_id: user._id,
          contact_id: contactId,
          contact_name: customerName.trim(),
          delay_seconds: 120,
          event_type: 'congrats_card_sent',
        }).catch(() => {});
      }

      // Step 6: Review link — 5 minutes
      if (reviewUrl) {
        await api.post('/messages/schedule-delayed', {
          to: normalizedPhone,
          body: `Hey ${firstName}, if you wouldn't mind leaving a quick review I'd really appreciate it! ${reviewUrl}`,
          user_id: user._id,
          contact_id: contactId,
          contact_name: customerName.trim(),
          delay_seconds: 420,
          event_type: 'review_request_sent',
        }).catch(() => {});
      }

      // Step 7: Enroll in long-term follow-up campaign
      if (selectedCampaignId && contactId) {
        await api.post(`/campaigns/${user._id}/${selectedCampaignId}/enroll/${contactId}`)
          .catch(() => {});
      }

      // Success animation
      setDone(true);
      Animated.spring(checkAnim, { toValue: 1, useNativeDriver: true, tension: 60, friction: 8 }).start();
    } catch (err: any) {
      showSimpleAlert('Error', err?.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setSending(false);
    }
  };

  const s = styles(colors);

  // ── SUCCESS SCREEN ──
  if (done) {
    return (
      <SafeAreaView style={s.container} edges={['top', 'bottom']}>
        <View style={s.successWrap}>
          <Animated.View style={[s.successCircle, { transform: [{ scale: checkAnim }] }]}>
            <Ionicons name="checkmark" size={56} color="#FFF" />
          </Animated.View>
          <Text style={s.successTitle}>SOLD!</Text>
          <Text style={s.successSub}>Sequence started for {customerName.split(' ')[0]}</Text>
          <View style={s.timeline}>
            {[
              { icon: 'card-outline',    color: '#007AFF', label: 'VCF sent',                  time: 'Right now', done: true },
              { icon: 'image-outline',   color: '#34C759', label: 'Delivery photo (MMS)',         time: '~2 min',    done: false },
              { icon: 'gift-outline',    color: ACCENT,    label: 'Digital card link',          time: '~4 min',    done: false },
              { icon: 'star-outline',    color: '#FF9500', label: 'Review request',             time: '~7 min',    done: false },
              { icon: 'chatbubble-outline', color: '#34C759', label: '7-day check-in',          time: '1 week',    done: false },
              { icon: 'people-outline',  color: '#AF52DE', label: 'Referral ask',               time: '3 weeks',   done: false },
            ].map((item, i) => (
              <View key={i} style={s.timelineRow}>
                <View style={[s.timelineIcon, { backgroundColor: item.color + '20' }]}>
                  <Ionicons name={item.icon as any} size={16} color={item.color} />
                </View>
                <Text style={s.timelineLabel}>{item.label}</Text>
                <Text style={[s.timelineTime, { color: item.done ? '#34C759' : item.color }]}>
                  {item.done ? 'Sent ✓' : item.time}
                </Text>
              </View>
            ))}
          </View>
          <TouchableOpacity style={s.doneBtn} onPress={() => router.back()} data-testid="sold-quick-done">
            <Text style={s.doneBtnText}>Done</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // ── MAIN SCREEN ──
  return (
    <SafeAreaView style={s.container} edges={['top', 'bottom']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="sold-quick-back">
          <Ionicons name="close" size={28} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>New Sale</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>

        {/* Photo row */}
        {photo ? (
          <View style={s.photoPreviewWrap}>
            <Image source={{ uri: photo.uri }} style={s.photoPreview} resizeMode="cover" />
            <View style={s.photoActions}>
              <TouchableOpacity style={s.photoActionBtn} onPress={takePhoto} data-testid="sold-retake">
                <Ionicons name="camera" size={18} color="#FFF" />
                <Text style={s.photoActionText}>Retake</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.photoActionBtn, { backgroundColor: 'rgba(0,0,0,0.5)' }]} onPress={pickFromLibrary} data-testid="sold-pick-library">
                <Ionicons name="images" size={18} color="#FFF" />
                <Text style={s.photoActionText}>Library</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={s.photoButtons}>
            <TouchableOpacity style={s.photoBtnPrimary} onPress={takePhoto} data-testid="sold-camera">
              <Ionicons name="camera" size={28} color="#000" />
              <Text style={s.photoBtnPrimaryText}>Take Photo</Text>
              <Text style={s.photoBtnSub}>Delivery shot</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.photoBtnSecondary} onPress={pickFromLibrary} data-testid="sold-library">
              <Ionicons name="images-outline" size={26} color={ACCENT} />
              <Text style={[s.photoBtnPrimaryText, { color: ACCENT, fontSize: 16 }]}>Camera Roll</Text>
              <Text style={s.photoBtnSub}>Already taken</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Name */}
        <Text style={s.fieldLabel}>CUSTOMER NAME</Text>
        <TextInput
          style={s.input}
          placeholder="First and last name"
          placeholderTextColor={colors.textSecondary}
          value={customerName}
          onChangeText={setCustomerName}
          autoCapitalize="words"
          data-testid="sold-name"
        />

        {/* Phone */}
        <Text style={s.fieldLabel}>PHONE NUMBER</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <TextInput
            style={[s.input, { flex: 1 }]}
            placeholder="(801) 555-0100"
            placeholderTextColor={colors.textSecondary}
            value={customerPhone}
            onChangeText={setCustomerPhone}
            keyboardType="phone-pad"
            data-testid="sold-phone"
          />
          {lookingUp && <ActivityIndicator size="small" color={colors.textSecondary} />}
        </View>

        {/* Referred by (optional) */}
        <Text style={[s.fieldLabel, { marginTop: 16 }]}>REFERRED BY <Text style={{ color: colors.textTertiary, fontWeight: '400' }}>(optional)</Text></Text>
        {referredByName ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: ACCENT + '18', borderRadius: 12, padding: 12, gap: 10 }}>
            <Ionicons name="person-circle" size={22} color={ACCENT} />
            <Text style={{ flex: 1, fontSize: 16, fontWeight: '600', color: colors.text }}>{referredByName}</Text>
            <TouchableOpacity onPress={() => { setReferredByName(''); setReferredById(''); setReferralSearch(''); }} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
        ) : (
          <View>
            <TextInput
              style={s.input}
              placeholder="Search contacts..."
              placeholderTextColor={colors.textSecondary}
              value={referralSearch}
              onChangeText={setReferralSearch}
              onFocus={() => setShowReferralSearch(true)}
              data-testid="referral-search"
            />
            {referralResults.length > 0 && (
              <View style={{ backgroundColor: colors.card, borderRadius: 10, borderWidth: 1, borderColor: colors.surface, marginTop: 4, overflow: 'hidden' }}>
                {referralResults.map((c: any) => (
                  <TouchableOpacity
                    key={c._id}
                    style={{ flexDirection: 'row', alignItems: 'center', padding: 12, gap: 10, borderBottomWidth: 1, borderBottomColor: colors.surface }}
                    onPress={() => {
                      const name = c.name || `${c.first_name || ''} ${c.last_name || ''}`.trim();
                      setReferredById(c._id);
                      setReferredByName(name);
                      setReferralSearch('');
                      setReferralResults([]);
                    }}
                  >
                    <Ionicons name="person-outline" size={18} color={colors.textSecondary} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{c.name || `${c.first_name || ''} ${c.last_name || ''}`.trim()}</Text>
                      {c.phone && <Text style={{ fontSize: 12, color: colors.textSecondary }}>{c.phone}</Text>}
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
        )}

        {/* ── Send Type Selector ── */}
        <View style={{ marginTop: 24 }}>
          <Text style={s.fieldLabel}>CONGRATS FORMAT</Text>
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 8 }}>
            <TouchableOpacity
              style={[s.typeBtn, sendType === 'photo' && s.typeBtnActive]}
              onPress={() => setSendType('photo')}
              data-testid="send-type-photo"
            >
              <Ionicons name="image-outline" size={22} color={sendType === 'photo' ? '#000' : ACCENT} />
              <Text style={[s.typeBtnLabel, sendType === 'photo' && { color: '#000' }]}>Delivery Photo</Text>
              <Text style={[s.typeBtnSub, sendType === 'photo' && { color: '#00000099' }]}>Send the actual photo as MMS</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.typeBtn, sendType === 'card' && s.typeBtnActive]}
              onPress={() => setSendType('card')}
              data-testid="send-type-card"
            >
              <Ionicons name="gift-outline" size={22} color={sendType === 'card' ? '#000' : ACCENT} />
              <Text style={[s.typeBtnLabel, sendType === 'card' && { color: '#000' }]}>Digital Card</Text>
              <Text style={[s.typeBtnSub, sendType === 'card' && { color: '#00000099' }]}>Full card link experience</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Custom message with delivery photo */}
        {sendType === 'photo' && (
          <View style={{ marginTop: 14 }}>
            <Text style={s.fieldLabel}>MESSAGE WITH PHOTO</Text>
            <TextInput
              style={[s.input, { height: 80, textAlignVertical: 'top', paddingTop: 10 }]}
              value={congratsText}
              onChangeText={setCongratsText}
              placeholder={`Congratulations ${customerName.split(' ')[0] || 'there'}! It was a pleasure working with you today!`}
              placeholderTextColor={colors.textSecondary}
              multiline
              data-testid="congrats-text-input"
            />
          </View>
        )}

        {/* What will send */}
        <View style={s.sequencePreview}>
          <Text style={s.sequenceTitle}>What will be sent automatically</Text>
          {[
            { label: 'Your contact card (VCF)', time: 'Immediately', color: '#007AFF' },
            {
              label: sendType === 'photo' ? 'Delivery photo (MMS)' : 'Congrats card link',
              time: '~2 minutes', color: ACCENT,
            },
            { label: 'Review request', time: '~7 minutes', color: '#FF9500' },
          ].map((item, i) => (
            <View key={i} style={s.sequenceRow}>
              <View style={[s.sequenceDot, { backgroundColor: item.color }]} />
              <Text style={s.sequenceLabel}>{item.label}</Text>
              <Text style={[s.sequenceTime, { color: item.color }]}>{item.time}</Text>
            </View>
          ))}
        </View>

        {/* ── Long-term Campaign ── */}
        <View style={{ marginTop: 24 }}>
          <Text style={s.fieldLabel}>LONG-TERM FOLLOW-UP CAMPAIGN</Text>
          {availableCampaigns.length === 0 ? (
            <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.surface, marginTop: 8 }}>
              <Text style={{ fontSize: 14, color: colors.textSecondary }}>No Sold campaigns found. Create one in Hub → Campaigns.</Text>
            </View>
          ) : (
            <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.surface, marginTop: 8, overflow: 'hidden' }}>
              {availableCampaigns.map((c: any, i: number) => {
                const cid = c._id || c.id;
                const selected = selectedCampaignId === cid;
                return (
                  <TouchableOpacity
                    key={cid}
                    onPress={() => { setSelectedCampaignId(cid); setSelectedCampaignName(c.name); }}
                    style={{ flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12, borderBottomWidth: i < availableCampaigns.length - 1 ? 1 : 0, borderBottomColor: colors.surface }}
                    data-testid={`campaign-option-${cid}`}
                  >
                    <View style={{ width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: selected ? ACCENT : colors.border, backgroundColor: selected ? ACCENT : 'transparent', alignItems: 'center', justifyContent: 'center' }}>
                      {selected && <Ionicons name="checkmark" size={12} color="#000" />}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{c.name}</Text>
                      <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                        {(c.sequences || []).length} steps · starts day 7
                      </Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
          {selectedCampaignId && (
            <TouchableOpacity onPress={() => { setSelectedCampaignId(''); setSelectedCampaignName(''); }} style={{ marginTop: 6, alignSelf: 'flex-end' }}>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>Skip campaign enrollment</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Send button */}
        <TouchableOpacity
          style={[s.sendBtn, sending && { opacity: 0.6 }]}
          onPress={handleSend}
          disabled={sending}
          data-testid="sold-quick-send"
        >
          {sending
            ? <ActivityIndicator size="small" color="#000" />
            : <>
                <Ionicons name="checkmark-circle" size={24} color="#000" />
                <Text style={s.sendBtnText}>SEND SOLD SEQUENCE</Text>
              </>
          }
        </TouchableOpacity>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = (colors: any) => StyleSheet.create({
  container:       { flex: 1, backgroundColor: colors.bg },
  header:          { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.surface },
  headerTitle:     { fontSize: 19, fontWeight: '700', color: colors.text },
  body:            { padding: 20, paddingBottom: 40 },
  photoButtons:    { flexDirection: 'row', gap: 12, marginBottom: 24 },
  photoBtnPrimary: { flex: 1, backgroundColor: ACCENT, borderRadius: 16, paddingVertical: 22, alignItems: 'center', gap: 6 },
  photoBtnSecondary: { flex: 1, borderWidth: 2, borderColor: ACCENT, borderRadius: 16, paddingVertical: 22, alignItems: 'center', gap: 6 },
  photoBtnPrimaryText: { fontSize: 17, fontWeight: '700', color: '#000' },
  photoBtnSub:     { fontSize: 12, color: 'rgba(0,0,0,0.5)' },
  photoPreviewWrap: { borderRadius: 16, overflow: 'hidden', marginBottom: 24, position: 'relative', height: 220 },
  photoPreview:    { width: '100%', height: '100%' },
  photoActions:    { position: 'absolute', bottom: 10, right: 10, flexDirection: 'row', gap: 8 },
  photoActionBtn:  { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(0,0,0,0.65)', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20 },
  photoActionText: { color: '#FFF', fontSize: 14, fontWeight: '600' },
  fieldLabel:      { fontSize: 12, fontWeight: '700', color: '#6E6E73', letterSpacing: 1, marginBottom: 6, marginTop: 16 },
  input:           { backgroundColor: colors.card, borderRadius: 12, padding: 16, fontSize: 17, color: colors.text, borderWidth: 1.5, borderColor: colors.surface },
  sequencePreview: { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginTop: 24, borderWidth: 1, borderColor: ACCENT + '30' },
  sequenceTitle:   { fontSize: 13, fontWeight: '700', color: ACCENT, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.5 },
  sequenceRow:     { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  sequenceDot:     { width: 8, height: 8, borderRadius: 4, marginRight: 10 },
  sequenceLabel:   { flex: 1, fontSize: 14, color: colors.text },
  sequenceTime:    { fontSize: 13, fontWeight: '700' },
  sendBtn:         { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: ACCENT, borderRadius: 16, paddingVertical: 20, marginTop: 24 },
  sendBtnText:     { fontSize: 19, fontWeight: '800', color: '#000', letterSpacing: 0.5 },
  typeBtn: {
    flex: 1, borderWidth: 1.5, borderColor: ACCENT + '50', borderRadius: 14,
    padding: 14, alignItems: 'center', gap: 6, backgroundColor: ACCENT + '08',
  },
  typeBtnActive: {
    backgroundColor: ACCENT, borderColor: ACCENT,
  },
  typeBtnLabel: { fontSize: 14, fontWeight: '700', color: ACCENT, textAlign: 'center' },
  typeBtnSub:   { fontSize: 11, color: colors.textSecondary, textAlign: 'center', lineHeight: 15 },
  // Success
  successWrap:     { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28 },
  successCircle:   { width: 110, height: 110, borderRadius: 55, backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center', marginBottom: 20 },
  successTitle:    { fontSize: 40, fontWeight: '900', color: ACCENT, marginBottom: 6 },
  successSub:      { fontSize: 17, color: colors.textSecondary, textAlign: 'center', marginBottom: 28 },
  timeline:        { width: '100%', backgroundColor: colors.card, borderRadius: 16, padding: 18, borderWidth: 1, borderColor: ACCENT + '30', gap: 14 },
  timelineRow:     { flexDirection: 'row', alignItems: 'center', gap: 12 },
  timelineIcon:    { width: 34, height: 34, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  timelineLabel:   { flex: 1, fontSize: 14, color: colors.text },
  timelineTime:    { fontSize: 12, fontWeight: '700' },
  doneBtn:         { marginTop: 28, backgroundColor: ACCENT, borderRadius: 14, paddingVertical: 18, paddingHorizontal: 48 },
  doneBtnText:     { fontSize: 18, fontWeight: '700', color: '#000' },
});
