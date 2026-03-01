import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  Image, ActivityIndicator, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert } from '../../services/alert';

const IS_WEB = Platform.OS === 'web';
const BASE_URL = IS_WEB ? (typeof window !== 'undefined' ? window.location.origin : '') : 'https://app.imosapp.com';

// Fallback defaults per card type (used while template loads)
const TYPE_META: Record<string, { label: string; icon: string; accent: string; headline: string; message: string }> = {
  congrats:    { label: 'Congrats Card',    icon: 'gift',       accent: '#C9A962', headline: 'Congratulations!',  message: 'Thank you for choosing us, {name}!' },
  birthday:    { label: 'Birthday Card',    icon: 'balloon',    accent: '#FF2D55', headline: 'Happy Birthday!',    message: 'Wishing you the happiest of birthdays, {name}!' },
  anniversary: { label: 'Anniversary Card', icon: 'heart',      accent: '#FF6B6B', headline: 'Happy Anniversary!', message: 'Celebrating this special milestone with you, {name}!' },
  thankyou:    { label: 'Thank You Card',   icon: 'thumbs-up',  accent: '#34C759', headline: 'Thank You!',         message: 'We truly appreciate your loyalty and trust, {name}!' },
  welcome:     { label: 'Welcome Card',     icon: 'hand-left',  accent: '#007AFF', headline: 'Welcome!',           message: "We're so excited to have you, {name}! Welcome to the family." },
  holiday:     { label: 'Holiday Card',     icon: 'snow',       accent: '#5AC8FA', headline: 'Happy Holidays!',    message: 'Warm wishes this holiday season, {name}!' },
};

export default function CreateCardPage() {
  const router = useRouter();
  const { type } = useLocalSearchParams<{ type: string }>();
  const { user } = useAuthStore();
  const cardType = type || 'congrats';
  const meta = TYPE_META[cardType] || TYPE_META.congrats;

  const [template, setTemplate] = useState<any>(null);
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [photo, setPhoto] = useState<{ uri: string; type: string; name: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [createdCard, setCreatedCard] = useState<{ card_id: string; share_url: string } | null>(null);
  const [matchModalVisible, setMatchModalVisible] = useState(false);
  const [matchInfo, setMatchInfo] = useState<any>(null);
  const [pendingSharePlatform, setPendingSharePlatform] = useState<string | null>(null);

  const accent = template?.accent_color || meta.accent;
  const headline = template?.headline || meta.headline;
  const message = template?.message || meta.message;

  useEffect(() => {
    if (user?.store_id) {
      api.get(`/congrats/template/${user.store_id}?card_type=${cardType}`)
        .then(r => setTemplate(r.data.template))
        .catch(() => {});
    }
  }, [user?.store_id, cardType]);

  const pickPhoto = async () => {
    if (!IS_WEB) {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') { showSimpleAlert('Permission Denied', 'Photo library access is required.'); return; }
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: true, aspect: [1, 1], quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      const a = result.assets[0];
      setPhoto({ uri: a.uri, type: a.mimeType || 'image/jpeg', name: a.fileName || 'photo.jpg' });
    }
  };

  const handlePreview = () => {
    if (!customerName.trim()) { showSimpleAlert('Required', 'Please enter the recipient name'); return; }
    if (!photo) { showSimpleAlert('Required', 'Please add a photo'); return; }
    setShowPreview(true);
  };

  const createCard = async () => {
    if (!user?._id) return;
    setCreating(true);
    try {
      const formData = new FormData();
      formData.append('salesman_id', user._id);
      formData.append('customer_name', customerName.trim());
      formData.append('card_type', cardType);
      if (customerPhone.trim()) formData.append('customer_phone', customerPhone.trim());
      if (customMessage.trim()) formData.append('custom_message', customMessage.trim());
      if (IS_WEB) {
        const response = await fetch(photo!.uri);
        const blob = await response.blob();
        formData.append('photo', blob, photo!.name || 'photo.jpg');
      } else {
        formData.append('photo', { uri: photo!.uri, type: photo!.type, name: photo!.name } as any);
      }
      const res = await api.post('/congrats/create', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      const cardId = res.data?.card_id;
      setShowPreview(false);
      setCreatedCard({ card_id: cardId, share_url: `${BASE_URL}/congrats/${cardId}` });
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to create card';
      showSimpleAlert('Error', typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally { setCreating(false); }
  };

  const handleCopyLink = async () => {
    if (!createdCard) return;
    try {
      if (IS_WEB) { await navigator.clipboard.writeText(createdCard.share_url); }
      else { const C = require('expo-clipboard'); await C.setStringAsync(createdCard.share_url); }
      showSimpleAlert('Copied', 'Link copied to clipboard');
    } catch { showSimpleAlert('Error', 'Failed to copy link'); }
  };

  const handleShare = async (platform: string) => {
    if (!createdCard) return;
    const url = createdCard.share_url;
    const text = `Check out this ${meta.label.toLowerCase()} for ${customerName}!`;
    let shareUrl = '';
    switch (platform) {
      case 'facebook': shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`; break;
      case 'twitter': shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`; break;
      case 'sms': {
        const isApple = /iPad|iPhone|iPod|Macintosh/.test(navigator.userAgent);
        const sep = isApple ? '&' : '?';
        const ph = customerPhone.trim();
        shareUrl = ph ? `sms:${ph}${sep}body=${encodeURIComponent(text + ' ' + url)}` : `sms:${sep}body=${encodeURIComponent(text + ' ' + url)}`;
        break;
      }
      case 'email': shareUrl = `mailto:?subject=${encodeURIComponent(meta.label)}&body=${encodeURIComponent(text + '\n\n' + url)}`; break;
    }
    if (IS_WEB) {
      if (platform === 'sms' || platform === 'email') {
        const a = document.createElement('a'); a.href = shareUrl; a.target = '_self'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
      } else if (navigator.share) { try { await navigator.share({ url }); } catch {} }
      else { navigator.clipboard?.writeText(url); alert('Link copied!'); }
    } else { Linking.openURL(shareUrl); }

    if (customerPhone.trim() && user?._id) {
      try {
        const res = await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
          phone: customerPhone.trim(), name: customerName.trim(),
          event_type: `${cardType}_card_sent`, event_title: `${meta.label} Sent`,
          event_description: `Sent ${meta.label.toLowerCase()} via ${platform}`, event_icon: meta.icon, event_color: accent,
        });
        if (res.data.needs_confirmation) { setMatchInfo(res.data); setPendingSharePlatform(platform); setMatchModalVisible(true); }
      } catch {}
    }
  };

  const resolveMatch = async (action: string) => {
    setMatchModalVisible(false);
    if (!user?._id || !pendingSharePlatform) return;
    try {
      await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
        phone: customerPhone.trim(), name: customerName.trim(),
        event_type: `${cardType}_card_sent`, event_title: `${meta.label} Sent`,
        event_description: `Sent ${meta.label.toLowerCase()} via ${pendingSharePlatform}`,
        event_icon: meta.icon, event_color: accent, force_action: action,
      });
    } catch {}
    setMatchInfo(null); setPendingSharePlatform(null);
  };

  // ---- Created: sharing options ----
  if (createdCard) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} data-testid="card-share-back"><Ionicons name="chevron-back" size={28} color={accent} /></TouchableOpacity>
          <Text style={s.headerTitle}>Card Created!</Text>
          <View style={{ width: 28 }} />
        </View>
        <ScrollView style={s.scroll} contentContainerStyle={{ alignItems: 'center', paddingBottom: 40 }}>
          <View style={{ marginTop: 30, marginBottom: 16 }}><Ionicons name="checkmark-circle" size={64} color="#34C759" /></View>
          <Text style={s.successTitle}>{meta.label} Ready!</Text>
          <Text style={s.successSub}>Share it with {customerName}</Text>
          <View style={s.linkBox}><Text style={[s.linkText, { color: accent }]} numberOfLines={1}>{createdCard.share_url}</Text></View>
          <View style={s.actionGrid}>
            <TouchableOpacity style={s.actionBtn} onPress={handleCopyLink} data-testid="card-copy-link">
              <View style={[s.actionIcon, { backgroundColor: accent + '20' }]}><Ionicons name="copy-outline" size={24} color={accent} /></View>
              <Text style={s.actionLabel}>Copy Link</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.actionBtn} onPress={() => router.push(`/congrats/${createdCard.card_id}` as any)} data-testid="card-view">
              <View style={[s.actionIcon, { backgroundColor: accent + '20' }]}><Ionicons name="eye-outline" size={24} color={accent} /></View>
              <Text style={s.actionLabel}>View Card</Text>
            </TouchableOpacity>
          </View>
          <Text style={s.sectionLabel}>SHARE VIA</Text>
          <View style={s.shareRow}>
            {[
              { key: 'sms', icon: 'chatbubble', color: '#34C759', label: 'SMS' },
              { key: 'email', icon: 'mail', color: '#007AFF', label: 'Email' },
              { key: 'facebook', icon: 'logo-facebook', color: '#1877F2', label: 'Facebook' },
              { key: 'twitter', icon: 'logo-twitter', color: '#1DA1F2', label: 'Twitter' },
            ].map(p => (
              <TouchableOpacity key={p.key} style={s.shareBtn} onPress={() => handleShare(p.key)}>
                <View style={[s.shareIcon, { backgroundColor: p.color + '20' }]}><Ionicons name={p.icon as any} size={22} color={p.color} /></View>
                <Text style={s.shareLabel}>{p.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity style={[s.outlineBtn, { borderColor: accent }]} onPress={() => { setCreatedCard(null); setShowPreview(false); setPhoto(null); setCustomerName(''); setCustomMessage(''); setCustomerPhone(''); setCustomerEmail(''); }} data-testid="card-create-another">
            <Ionicons name="add-circle-outline" size={20} color={accent} /><Text style={[s.outlineBtnText, { color: accent }]}>Create Another</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ---- Preview ----
  if (showPreview && photo) {
    const previewMsg = message.replace('{customer_name}', customerName).replace('{name}', customerName);
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => setShowPreview(false)} data-testid="card-preview-back"><Ionicons name="chevron-back" size={28} color={accent} /></TouchableOpacity>
          <Text style={s.headerTitle}>Preview</Text>
          <View style={{ width: 28 }} />
        </View>
        <ScrollView style={s.scroll} contentContainerStyle={{ alignItems: 'center', paddingBottom: 40 }}>
          <View style={s.previewCard} data-testid="card-preview">
            <Text style={[s.previewHeadline, { color: accent }]}>{headline}</Text>
            <View style={[s.previewPhotoRing, { borderColor: accent }]}>
              <Image source={{ uri: photo.uri }} style={s.previewPhoto} />
            </View>
            <Text style={s.previewName}>{customerName}</Text>
            <Text style={s.previewMessage}>{previewMsg}</Text>
            {customMessage ? <View style={[s.previewCustomBox, { borderLeftColor: accent }]}><Text style={s.previewCustomMsg}>"{customMessage}"</Text></View> : null}
            <View style={[s.previewDivider, { backgroundColor: accent }]} />
            {user?.name && (
              <View style={{ alignItems: 'center' }}>
                <Text style={s.previewSalesName}>{user.name}</Text>
                <Text style={[s.previewSalesTitle, { color: accent }]}>{user.title || 'Sales Professional'}</Text>
              </View>
            )}
          </View>
          <View style={s.previewActions}>
            <TouchableOpacity style={[s.previewEditBtn, { borderColor: accent }]} onPress={() => setShowPreview(false)} data-testid="card-preview-edit">
              <Ionicons name="create-outline" size={20} color={accent} /><Text style={[s.previewEditText, { color: accent }]}>Edit</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.previewSendBtn, { backgroundColor: accent }, creating && { opacity: 0.5 }]} onPress={createCard} disabled={creating} data-testid="card-preview-send">
              {creating ? <ActivityIndicator size="small" color="#FFF" /> : <><Ionicons name="send" size={18} color="#FFF" /><Text style={s.previewSendText}>Create & Send</Text></>}
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ---- Form ----
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="card-form-back"><Ionicons name="chevron-back" size={28} color={accent} /></TouchableOpacity>
        <Text style={s.headerTitle}>{meta.label}</Text>
        <View style={{ width: 28 }} />
      </View>
      <ScrollView style={s.scroll} contentContainerStyle={{ paddingBottom: 40 }}>
        <Text style={s.fieldLabel}>RECIPIENT PHOTO *</Text>
        <TouchableOpacity style={s.photoPicker} onPress={pickPhoto} data-testid="card-pick-photo">
          {photo ? <Image source={{ uri: photo.uri }} style={[s.photoPreview, { borderColor: accent }]} /> : (
            <View style={s.photoPlaceholder}><Ionicons name="camera" size={36} color="#8E8E93" /><Text style={s.photoPlaceholderText}>Tap to add photo</Text></View>
          )}
        </TouchableOpacity>
        <Text style={s.fieldLabel}>RECIPIENT NAME *</Text>
        <TextInput style={s.input} value={customerName} onChangeText={setCustomerName} placeholder="Recipient Name" placeholderTextColor="#8E8E93" data-testid="card-recipient-name" />
        <Text style={[s.fieldLabel, { marginTop: 16 }]}>SEND TO (OPTIONAL)</Text>
        <TextInput style={s.input} value={customerPhone} onChangeText={setCustomerPhone} placeholder="Phone" placeholderTextColor="#8E8E93" keyboardType="phone-pad" />
        <TextInput style={[s.input, { marginTop: 8 }]} value={customerEmail} onChangeText={setCustomerEmail} placeholder="Email" placeholderTextColor="#8E8E93" keyboardType="email-address" autoCapitalize="none" />
        <Text style={[s.fieldLabel, { marginTop: 16 }]}>PERSONAL MESSAGE (OPTIONAL)</Text>
        <TextInput style={[s.input, { height: 100, textAlignVertical: 'top' }]} value={customMessage} onChangeText={setCustomMessage} placeholder="Add a personal message..." placeholderTextColor="#8E8E93" multiline />
        <TouchableOpacity style={[s.createBtn, { backgroundColor: accent }, (!customerName.trim() || !photo) && { opacity: 0.5 }]} onPress={handlePreview} disabled={!customerName.trim() || !photo} data-testid="card-preview-btn">
          <Ionicons name="eye-outline" size={20} color="#FFF" /><Text style={s.createBtnText}>Preview Card</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Contact Match Modal */}
      {matchModalVisible && matchInfo && (
        <View style={s.modalOverlay}>
          <View style={s.modalCard} data-testid="card-match-modal">
            <View style={{ alignItems: 'center', marginBottom: 16 }}><View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: '#FF950015', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="person-circle" size={44} color="#FF9500" /></View></View>
            <Text style={s.modalTitle}>Contact Already Exists</Text>
            <Text style={s.modalSub}>A contact with this number already exists:</Text>
            <View style={s.modalBox}><Text style={s.modalBoxLabel}>EXISTING CONTACT</Text><Text style={s.modalBoxName}>{matchInfo.existing_name}</Text>{matchInfo.phone ? <Text style={s.modalBoxPhone}>{matchInfo.phone}</Text> : null}</View>
            <View style={s.modalDivRow}><View style={s.modalDivLine} /><Text style={s.modalDivText}>You entered</Text><View style={s.modalDivLine} /></View>
            <View style={[s.modalBox, { marginBottom: 20 }]}><Text style={[s.modalBoxName, { color: '#FF9500' }]}>{matchInfo.provided_name}</Text></View>
            {[{ action: 'use_existing', icon: 'checkmark-circle', color: '#34C759', text: 'Use Existing Contact' }, { action: 'update_name', icon: 'create', color: '#007AFF', text: `Update to "${matchInfo.provided_name}"` }, { action: 'create_new', icon: 'person-add', color: '#FF9500', text: 'Create New Contact' }].map(opt => (
              <TouchableOpacity key={opt.action} style={s.modalAction} onPress={() => resolveMatch(opt.action)}><Ionicons name={opt.icon as any} size={20} color={opt.color} /><Text style={s.modalActionText}>{opt.text}</Text></TouchableOpacity>
            ))}
            <TouchableOpacity onPress={() => { setMatchModalVisible(false); setMatchInfo(null); }} style={{ marginTop: 4, padding: 12, alignItems: 'center' }}><Text style={{ fontSize: 15, color: '#8E8E93' }}>Cancel</Text></TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#2C2C2E' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  scroll: { flex: 1, paddingHorizontal: 20 },
  fieldLabel: { fontSize: 10, fontWeight: '700', color: '#6E6E73', marginTop: 16, marginBottom: 6, letterSpacing: 1 },
  input: { backgroundColor: '#1C1C1E', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 12, fontSize: 14, color: '#FFF', borderWidth: 1.5, borderColor: '#3A3A3C' },
  photoPicker: { alignItems: 'center', marginBottom: 8 },
  photoPreview: { width: 160, height: 160, borderRadius: 32, borderWidth: 3 },
  photoPlaceholder: { width: 160, height: 160, borderRadius: 32, backgroundColor: '#1C1C1E', borderWidth: 2, borderColor: '#2C2C2E', borderStyle: 'dashed', justifyContent: 'center', alignItems: 'center' },
  photoPlaceholderText: { fontSize: 13, color: '#8E8E93', marginTop: 8 },
  createBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderRadius: 12, paddingVertical: 16, marginTop: 30, gap: 8 },
  createBtnText: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  // Success
  successTitle: { fontSize: 24, fontWeight: '700', color: '#FFF', marginBottom: 6 },
  successSub: { fontSize: 16, color: '#8E8E93', marginBottom: 24 },
  linkBox: { backgroundColor: '#1C1C1E', borderRadius: 10, padding: 14, width: '100%', marginBottom: 24, borderWidth: 1, borderColor: '#2C2C2E' },
  linkText: { fontSize: 14 },
  actionGrid: { flexDirection: 'row', justifyContent: 'center', gap: 20, marginBottom: 30, width: '100%' },
  actionBtn: { alignItems: 'center', width: 80 },
  actionIcon: { width: 56, height: 56, borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  actionLabel: { fontSize: 12, color: '#FFF', fontWeight: '500' },
  sectionLabel: { fontSize: 12, fontWeight: '600', color: '#8E8E93', alignSelf: 'flex-start', marginBottom: 12, letterSpacing: 0.5 },
  shareRow: { flexDirection: 'row', justifyContent: 'center', gap: 24, marginBottom: 30, width: '100%' },
  shareBtn: { alignItems: 'center', width: 64 },
  shareIcon: { width: 48, height: 48, borderRadius: 24, justifyContent: 'center', alignItems: 'center', marginBottom: 6 },
  shareLabel: { fontSize: 11, color: '#8E8E93' },
  outlineBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, borderWidth: 1, width: '100%' },
  outlineBtnText: { fontSize: 15, fontWeight: '600' },
  // Preview
  previewCard: { backgroundColor: '#1A1A1A', borderRadius: 20, padding: 30, width: '100%', maxWidth: 380, alignItems: 'center', marginTop: 20, borderWidth: 1, borderColor: '#2C2C2E' },
  previewHeadline: { fontSize: 32, fontWeight: '800', marginBottom: 20, textAlign: 'center' },
  previewPhotoRing: { borderWidth: 4, borderRadius: 80, padding: 4, marginBottom: 16 },
  previewPhoto: { width: 140, height: 140, borderRadius: 70 },
  previewName: { fontSize: 24, fontWeight: '700', color: '#FFF', marginBottom: 12, textAlign: 'center' },
  previewMessage: { fontSize: 15, color: '#FFFFFFCC', textAlign: 'center', lineHeight: 22, marginBottom: 12 },
  previewCustomBox: { borderLeftWidth: 3, paddingLeft: 14, paddingVertical: 6, width: '100%', marginBottom: 16 },
  previewCustomMsg: { fontSize: 14, fontStyle: 'italic', color: '#FFFFFFBB', lineHeight: 20 },
  previewDivider: { width: 50, height: 3, borderRadius: 2, marginVertical: 16 },
  previewSalesName: { fontSize: 16, fontWeight: '700', color: '#FFF', marginBottom: 2 },
  previewSalesTitle: { fontSize: 13, fontWeight: '500' },
  previewActions: { flexDirection: 'row', gap: 12, marginTop: 24, width: '100%', maxWidth: 380 },
  previewEditBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 12, borderWidth: 1.5 },
  previewEditText: { fontSize: 16, fontWeight: '600' },
  previewSendBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 12 },
  previewSendText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  // Match modal
  modalOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', zIndex: 9999 },
  modalCard: { backgroundColor: '#1C1C1E', borderRadius: 16, padding: 24, width: '90%', maxWidth: 380 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 8 },
  modalSub: { fontSize: 14, color: '#8E8E93', textAlign: 'center', marginBottom: 16 },
  modalBox: { backgroundColor: '#2C2C2E', borderRadius: 10, padding: 14, alignItems: 'center' },
  modalBoxLabel: { fontSize: 10, fontWeight: '700', color: '#6E6E73', letterSpacing: 1, marginBottom: 6 },
  modalBoxName: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  modalBoxPhone: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  modalDivRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 12 },
  modalDivLine: { flex: 1, height: 1, backgroundColor: '#2C2C2E' },
  modalDivText: { fontSize: 12, color: '#6E6E73', marginHorizontal: 12 },
  modalAction: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#2C2C2E', padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 },
  modalActionText: { fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 },
});
