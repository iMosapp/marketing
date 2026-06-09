import React, { useState, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput,
  Image, ActivityIndicator, ScrollView, Platform, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as MediaLibrary from 'expo-media-library';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const IS_WEB = Platform.OS === 'web';
const ACCENT = '#C9A962';

export default function SoldWizardScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const {
    contact_id,
    contact_name,
    contact_phone,
    contact_vehicle,
  } = useLocalSearchParams<{
    contact_id: string;
    contact_name: string;
    contact_phone: string;
    contact_vehicle: string;
  }>();

  const [step, setStep] = useState(1); // 1 = photo, 2 = notes, 3 = confirm, 4 = success
  const [photo, setPhoto] = useState<{ uri: string; type: string; name: string } | null>(null);
  const [note, setNote] = useState('');
  const [vehicle, setVehicle] = useState(contact_vehicle || '');
  const [submitting, setSubmitting] = useState(false);
  const scaleAnim = useRef(new Animated.Value(0)).current;

  const pickPhotoFromCamera = async () => {
    if (!IS_WEB) {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        showSimpleAlert('Permission Denied', 'Camera access is required to take a delivery photo.');
        return;
      }
      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false,
        quality: 0.85,
      });
      if (!result.canceled && result.assets[0]) {
        const a = result.assets[0];
        setPhoto({ uri: a.uri, type: a.mimeType || 'image/jpeg', name: a.fileName || 'delivery.jpg' });
        setStep(2);
      }
    } else {
      // Web fallback: open file picker
      pickPhotoFromLibrary();
    }
  };

  const pickPhotoFromLibrary = async () => {
    if (!IS_WEB) {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        showSimpleAlert('Permission Denied', 'Photo library access is required.');
        return;
      }
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: false,
      quality: 0.85,
    });
    if (!result.canceled && result.assets[0]) {
      const a = result.assets[0];
      setPhoto({ uri: a.uri, type: a.mimeType || 'image/jpeg', name: a.fileName || 'delivery.jpg' });
      setStep(2);
    }
  };

  const handleMarkSold = async () => {
    if (!user?._id || !contact_id) return;
    setSubmitting(true);
    try {
      // 1. Save vehicle info if updated
      if (vehicle && vehicle !== contact_vehicle) {
        await api.put(`/contacts/${user._id}/${contact_id}`, { vehicle }).catch(() => {});
      }

      // 2. Save delivery note if entered
      if (note.trim()) {
        await api.post(`/contacts/${user._id}/${contact_id}/log-event`, {
          event_type: 'note_added',
          description: `Delivery note: ${note.trim()}`,
          icon: 'document-text',
          color: ACCENT,
        }).catch(() => {});
      }

      // 3. Upload delivery photo and log event
      if (photo) {
        try {
          const formData = new FormData();
          formData.append('event_type', 'delivery_photo');
          formData.append('description', `Delivery photo — ${vehicle || contact_name || 'SOLD'}`);
          formData.append('color', '#34C759');
          if (IS_WEB) {
            const resp = await fetch(photo.uri);
            const blob = await resp.blob();
            formData.append('photo', blob, photo.name);
          } else {
            formData.append('photo', { uri: photo.uri, type: photo.type, name: photo.name } as any);
          }
          await api.post(`/contacts/${user._id}/${contact_id}/log-event-photo`, formData).catch(() => {});

          // Save to camera roll on native
          if (!IS_WEB) {
            const { status } = await MediaLibrary.requestPermissionsAsync();
            if (status === 'granted') {
              await MediaLibrary.saveToLibraryAsync(photo.uri).catch(() => {});
            }
          }
        } catch (photoErr) {
          console.log('Delivery photo upload failed (non-fatal):', photoErr);
        }
      }

      // 4. Apply "Sold" tag — this triggers the Sold campaign automatically
      const currentTagsRes = await api.get(`/contacts/${user._id}/${contact_id}`);
      const existingTags: string[] = currentTagsRes.data?.tags || [];
      if (!existingTags.includes('Sold')) {
        const updatedTags = [...existingTags, 'Sold'];
        await api.patch(`/contacts/${user._id}/${contact_id}/tags`, { tags: updatedTags });
      }

      // 5. Show success
      setStep(4);
      Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true, tension: 60, friction: 8 }).start();

    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Something went wrong';
      showSimpleAlert('Error', typeof detail === 'string' ? detail : 'Could not complete SOLD. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const s = getStyles(colors);
  const firstName = (contact_name || '').split(' ')[0] || 'them';

  // ── STEP 1: Delivery Photo ──
  if (step === 1) {
    return (
      <SafeAreaView style={s.container} edges={['top', 'bottom']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} data-testid="sold-back-btn">
            <Ionicons name="close" size={28} color={colors.text} />
          </TouchableOpacity>
          <View style={s.stepPills}>
            {[1, 2, 3].map(n => (
              <View key={n} style={[s.stepPill, step >= n && s.stepPillActive]} />
            ))}
          </View>
          <View style={{ width: 28 }} />
        </View>

        <ScrollView contentContainerStyle={s.stepContent} showsVerticalScrollIndicator={false}>
          <View style={s.iconCircle}>
            <Ionicons name="camera" size={52} color={ACCENT} />
          </View>
          <Text style={s.stepTitle}>Capture the Moment</Text>
          <Text style={s.stepSubtitle}>
            Snap a delivery photo with {firstName}. It gets saved to your camera roll and logged to their contact.
          </Text>

          {photo ? (
            <View style={s.photoPreviewWrap}>
              <Image source={{ uri: photo.uri }} style={s.photoPreview} resizeMode="cover" />
              <TouchableOpacity style={s.photoRetake} onPress={() => setPhoto(null)} data-testid="sold-photo-retake">
                <Ionicons name="refresh" size={16} color="#FFF" />
                <Text style={{ color: '#FFF', fontSize: 14, fontWeight: '600' }}>Retake</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={s.photoActions}>
              <TouchableOpacity style={s.cameraBtnPrimary} onPress={pickPhotoFromCamera} data-testid="sold-take-photo">
                <Ionicons name="camera" size={22} color="#000" />
                <Text style={s.cameraBtnPrimaryText}>Take Photo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.cameraBtnSecondary} onPress={pickPhotoFromLibrary} data-testid="sold-pick-photo">
                <Ionicons name="images-outline" size={20} color={ACCENT} />
                <Text style={[s.cameraBtnSecondaryText, { color: ACCENT }]}>Choose from Library</Text>
              </TouchableOpacity>
            </View>
          )}

          {photo && (
            <TouchableOpacity style={[s.nextBtn, { backgroundColor: ACCENT }]} onPress={() => setStep(2)} data-testid="sold-step1-next">
              <Text style={s.nextBtnText}>Next</Text>
              <Ionicons name="arrow-forward" size={20} color="#000" />
            </TouchableOpacity>
          )}

          <TouchableOpacity style={s.skipLink} onPress={() => setStep(2)} data-testid="sold-skip-photo">
            <Text style={s.skipLinkText}>Skip Photo</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── STEP 2: Quick Note ──
  if (step === 2) {
    return (
      <SafeAreaView style={s.container} edges={['top', 'bottom']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => setStep(1)} data-testid="sold-step2-back">
            <Ionicons name="chevron-back" size={28} color={colors.text} />
          </TouchableOpacity>
          <View style={s.stepPills}>
            {[1, 2, 3].map(n => (
              <View key={n} style={[s.stepPill, step >= n && s.stepPillActive]} />
            ))}
          </View>
          <View style={{ width: 28 }} />
        </View>

        <ScrollView contentContainerStyle={s.stepContent} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <View style={s.iconCircle}>
            <Ionicons name="document-text" size={44} color={ACCENT} />
          </View>
          <Text style={s.stepTitle}>Quick Deal Notes</Text>
          <Text style={s.stepSubtitle}>
            Add details so Jessi can personalize future follow-ups. All optional.
          </Text>

          <View style={s.fieldGroup}>
            <Text style={s.fieldLabel}>VEHICLE SOLD</Text>
            <TextInput
              style={s.input}
              placeholder="e.g. 2024 Toyota Camry XSE"
              placeholderTextColor={colors.textSecondary}
              value={vehicle}
              onChangeText={setVehicle}
              data-testid="sold-vehicle-input"
            />
          </View>

          <View style={s.fieldGroup}>
            <Text style={s.fieldLabel}>DELIVERY NOTE <Text style={{ fontWeight: '400', color: colors.textTertiary }}>(optional)</Text></Text>
            <TextInput
              style={[s.input, { height: 100, textAlignVertical: 'top', paddingTop: 12 }]}
              placeholder={`e.g. ${firstName} was referred by John Smith. First-time buyer. Loves the red color.`}
              placeholderTextColor={colors.textSecondary}
              value={note}
              onChangeText={setNote}
              multiline
              data-testid="sold-note-input"
            />
          </View>

          <TouchableOpacity
            style={[s.nextBtn, { backgroundColor: ACCENT, marginTop: 8 }]}
            onPress={() => setStep(3)}
            data-testid="sold-step2-next"
          >
            <Text style={s.nextBtnText}>Next</Text>
            <Ionicons name="arrow-forward" size={20} color="#000" />
          </TouchableOpacity>
          <TouchableOpacity style={s.skipLink} onPress={() => setStep(3)} data-testid="sold-skip-notes">
            <Text style={s.skipLinkText}>Skip</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── STEP 3: Confirm ──
  if (step === 3) {
    return (
      <SafeAreaView style={s.container} edges={['top', 'bottom']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => setStep(2)} data-testid="sold-step3-back">
            <Ionicons name="chevron-back" size={28} color={colors.text} />
          </TouchableOpacity>
          <View style={s.stepPills}>
            {[1, 2, 3].map(n => (
              <View key={n} style={[s.stepPill, step >= n && s.stepPillActive]} />
            ))}
          </View>
          <View style={{ width: 28 }} />
        </View>

        <ScrollView contentContainerStyle={s.stepContent} showsVerticalScrollIndicator={false}>
          {/* Contact summary */}
          <View style={s.confirmContact}>
            <View style={s.confirmAvatar}>
              <Text style={s.confirmAvatarText}>{(contact_name || '?')[0].toUpperCase()}</Text>
            </View>
            <View>
              <Text style={s.confirmName}>{contact_name}</Text>
              {vehicle ? <Text style={s.confirmVehicle}>{vehicle}</Text> : null}
            </View>
          </View>

          {photo ? (
            <Image source={{ uri: photo.uri }} style={s.confirmPhoto} resizeMode="cover" />
          ) : null}

          {/* Campaign sequence preview */}
          <View style={s.campaignPreview}>
            <Text style={s.campaignPreviewTitle}>Your Sold Campaign Starts Now</Text>
            {[
              { delay: 'Immediately', icon: 'card-outline', label: 'VCF sent — customer saves your number', color: '#007AFF' },
              { delay: '3 min', icon: 'link', label: 'Digital card link sent', color: ACCENT },
              { delay: '30 min', icon: 'star-outline', label: 'Review request sent', color: '#FF9500' },
              { delay: '7 days', icon: 'chatbubble-outline', label: 'Check-in text', color: '#34C759' },
              { delay: '21 days', icon: 'people-outline', label: 'Referral ask', color: '#AF52DE' },
            ].map((item, i) => (
              <View key={i} style={s.campaignStep}>
                <View style={[s.campaignStepIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={16} color={item.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.campaignStepLabel}>{item.label}</Text>
                </View>
                <Text style={[s.campaignStepDelay, { color: item.color }]}>{item.delay}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity
            style={[s.soldBtn, submitting && { opacity: 0.6 }]}
            onPress={handleMarkSold}
            disabled={submitting}
            data-testid="sold-confirm-btn"
          >
            {submitting ? (
              <ActivityIndicator size="small" color="#000" />
            ) : (
              <>
                <Ionicons name="checkmark-circle" size={24} color="#000" />
                <Text style={s.soldBtnText}>MARK SOLD!</Text>
              </>
            )}
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── STEP 4: Success ──
  return (
    <SafeAreaView style={s.container} edges={['top', 'bottom']}>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }}>
        <Animated.View style={[s.successCircle, { transform: [{ scale: scaleAnim }] }]}>
          <Ionicons name="checkmark" size={56} color="#FFF" />
        </Animated.View>
        <Text style={s.successTitle}>SOLD!</Text>
        <Text style={s.successSub}>
          {contact_name}'s campaign has started. VCF is on its way — your number will be saved in seconds.
        </Text>

        <View style={s.successTimeline}>
          {[
            { label: 'VCF sent', color: '#007AFF', done: true },
            { label: 'Digital card in ~3 min', color: ACCENT, done: false },
            { label: 'Review request in ~30 min', color: '#FF9500', done: false },
          ].map((item, i) => (
            <View key={i} style={s.successTimelineRow}>
              <Ionicons
                name={item.done ? 'checkmark-circle' : 'time-outline'}
                size={18}
                color={item.color}
              />
              <Text style={[s.successTimelineText, { color: item.done ? item.color : colors.text }]}>{item.label}</Text>
            </View>
          ))}
        </View>

        <TouchableOpacity
          style={[s.nextBtn, { backgroundColor: ACCENT, marginTop: 32 }]}
          onPress={() => router.back()}
          data-testid="sold-done-btn"
        >
          <Text style={s.nextBtnText}>Done</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: colors.surface,
  },
  stepPills: { flexDirection: 'row', gap: 6 },
  stepPill: { width: 28, height: 4, borderRadius: 2, backgroundColor: colors.surface },
  stepPillActive: { backgroundColor: ACCENT },
  stepContent: { padding: 24, alignItems: 'center', paddingBottom: 40 },
  iconCircle: {
    width: 100, height: 100, borderRadius: 50,
    backgroundColor: `${ACCENT}20`, alignItems: 'center', justifyContent: 'center',
    marginBottom: 20,
  },
  stepTitle: { fontSize: 26, fontWeight: '800', color: colors.text, textAlign: 'center', marginBottom: 8 },
  stepSubtitle: { fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 22, marginBottom: 28 },
  photoActions: { width: '100%', gap: 12, marginBottom: 16 },
  cameraBtnPrimary: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    backgroundColor: ACCENT, borderRadius: 14, paddingVertical: 18, width: '100%',
  },
  cameraBtnPrimaryText: { fontSize: 18, fontWeight: '700', color: '#000' },
  cameraBtnSecondary: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    borderWidth: 1.5, borderColor: ACCENT, borderRadius: 14, paddingVertical: 16, width: '100%',
  },
  cameraBtnSecondaryText: { fontSize: 17, fontWeight: '600' },
  photoPreviewWrap: { width: '100%', borderRadius: 16, overflow: 'hidden', marginBottom: 20, position: 'relative' },
  photoPreview: { width: '100%', height: 280, borderRadius: 16 },
  photoRetake: {
    position: 'absolute', bottom: 12, right: 12,
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(0,0,0,0.6)', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
  },
  nextBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderRadius: 14, paddingVertical: 18, width: '100%',
  },
  nextBtnText: { fontSize: 18, fontWeight: '700', color: '#000' },
  skipLink: { marginTop: 16, paddingVertical: 8 },
  skipLinkText: { fontSize: 16, color: colors.textSecondary },
  fieldGroup: { width: '100%', marginBottom: 16 },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: '#6E6E73', letterSpacing: 1, marginBottom: 6 },
  input: {
    backgroundColor: colors.card, borderRadius: 10, padding: 14,
    fontSize: 16, color: colors.text, borderWidth: 1.5, borderColor: colors.surface, width: '100%',
  },
  confirmContact: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: colors.card, borderRadius: 14, padding: 16, width: '100%', marginBottom: 16,
  },
  confirmAvatar: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: `${ACCENT}25`, alignItems: 'center', justifyContent: 'center',
  },
  confirmAvatarText: { fontSize: 22, fontWeight: '700', color: ACCENT },
  confirmName: { fontSize: 18, fontWeight: '700', color: colors.text },
  confirmVehicle: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  confirmPhoto: { width: '100%', height: 180, borderRadius: 14, marginBottom: 16 },
  campaignPreview: {
    width: '100%', backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 24,
    borderWidth: 1, borderColor: `${ACCENT}30`,
  },
  campaignPreviewTitle: { fontSize: 15, fontWeight: '700', color: ACCENT, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.5 },
  campaignStep: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  campaignStepIcon: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  campaignStepLabel: { fontSize: 14, color: colors.text, flex: 1 },
  campaignStepDelay: { fontSize: 12, fontWeight: '700' },
  soldBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    backgroundColor: ACCENT, borderRadius: 16, paddingVertical: 20, width: '100%',
  },
  soldBtnText: { fontSize: 20, fontWeight: '800', color: '#000', letterSpacing: 0.5 },
  successCircle: {
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center', marginBottom: 24,
  },
  successTitle: { fontSize: 42, fontWeight: '900', color: ACCENT, marginBottom: 8 },
  successSub: { fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 22, marginBottom: 24 },
  successTimeline: {
    width: '100%', backgroundColor: colors.card, borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: `${ACCENT}30`, gap: 12,
  },
  successTimelineRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  successTimelineText: { fontSize: 15, fontWeight: '500' },
});
