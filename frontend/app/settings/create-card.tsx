import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  Image, ActivityIndicator, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as MediaLibrary from 'expo-media-library';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
const IS_WEB = Platform.OS === 'web';
const BASE_URL = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';

// Fallback defaults per card type (used while template loads)
const TYPE_META = {
  congrats:    { label: 'Congrats Card',    icon: 'gift',       accent: '#C9A962', headline: 'Congratulations!',  message: 'Thank you for choosing us, {name}!' },
  birthday:    { label: 'Birthday Card',    icon: 'balloon',    accent: '#FF2D55', headline: 'Happy Birthday!',    message: 'Wishing you the happiest of birthdays, {name}!' },
  anniversary: { label: 'Anniversary Card', icon: 'heart',      accent: '#FF6B6B', headline: 'Happy Anniversary!', message: 'Celebrating this special milestone with you, {name}!' },
  thankyou:    { label: 'Thank You Card',   icon: 'thumbs-up',  accent: '#34C759', headline: 'Thank You!',         message: 'We truly appreciate your loyalty and trust, {name}!' },
  welcome:     { label: 'Welcome Card',     icon: 'hand-left',  accent: '#007AFF', headline: 'Welcome!',           message: "We're so excited to have you, {name}! Welcome to the family." },
  holiday:     { label: 'Holiday Card',     icon: 'snow',       accent: '#5AC8FA', headline: 'Happy Holidays!',    message: 'Warm wishes this holiday season, {name}!' },
};

export default function CreateCardPage() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const { type, prefillName, prefillPhone, prefillEmail, returnToThread, for_contact, return_to_contact, generic: genericParam } = useLocalSearchParams<{ type: string; prefillName: string; prefillPhone: string; prefillEmail: string; returnToThread: string; for_contact: string; return_to_contact: string; generic: string }>();
  const { user } = useAuthStore();
  const cardType = type || 'congrats';
  const baseMeta = TYPE_META[cardType] || { label: cardType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + ' Card', icon: 'create-outline', accent: '#C9A962', headline: cardType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), message: 'A special card for {name}!' };
  const isFromContact = !!return_to_contact || !!returnToThread;

  const [isGeneric, setIsGeneric] = useState(genericParam === 'true' || (!prefillName && !prefillPhone && !isFromContact));
  const [selectedType, setSelectedType] = useState(cardType);
  const [showTypePicker, setShowTypePicker] = useState(false);
  const [customTemplates, setCustomTemplates] = useState<any[]>([]);
  
  // Resolve meta for both standard and custom card types
  const customMeta = customTemplates.find(t => t.card_type === selectedType);
  const meta = TYPE_META[selectedType] || (customMeta ? {
    label: customMeta.headline || 'Custom Card',
    icon: 'gift',
    accent: customMeta.accent_color || '#C9A962',
    headline: customMeta.headline || 'Custom Card',
    message: customMeta.message || '',
  } : { label: 'Custom Card', icon: 'gift', accent: '#C9A962', headline: 'Custom Card', message: '' });
  
  // Load user's custom card templates — try store first, fall back to org
  useEffect(() => {
    const storeId = user?.store_id || (user as any)?.store_id;
    const orgId = user?.organization_id || (user as any)?.org_id;
    const entityId = storeId || orgId;
    if (!entityId) return;
    api.get(`/congrats/templates/all/${entityId}`)
      .then(res => {
        const all = res.data || [];
        const custom = all.filter((t: any) => !TYPE_META[t.card_type] && t.headline);
        setCustomTemplates(custom);
      })
      .catch(() => {});
  }, [user?.store_id, (user as any)?.organization_id]);

  const [template, setTemplate] = useState(null);
  const [customerName, setCustomerName] = useState(prefillName || '');
  const [customerPhone, setCustomerPhone] = useState(prefillPhone || '');
  const [customerEmail, setCustomerEmail] = useState(prefillEmail || '');
  const [customMessage, setCustomMessage] = useState('');
  const [photo, setPhoto] = useState(null);
  const [creating, setCreating] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [createdCard, setCreatedCard] = useState(null);
  const [matchModalVisible, setMatchModalVisible] = useState(false);
  const [matchInfo, setMatchInfo] = useState(null);
  const [pendingSharePlatform, setPendingSharePlatform] = useState(null);

  // Tag picker state
  const [availableTags, setAvailableTags] = useState([]);
  const [selectedTags, setSelectedTags] = useState([]);
  const [startCampaign, setStartCampaign] = useState(true);
  const [loadingTags, setLoadingTags] = useState(false);

  // Reactive meta — uses template values when loaded, falls back to selected type meta
  const accent = template?.accent_color || meta.accent;
  const headline = template?.headline || meta.headline;
  const message = template?.message || meta.message;
  const templateLabel = template?.headline || meta.label;

  useEffect(() => {
    if (user?.store_id) {
      api.get(`/congrats/template/${user.store_id}?card_type=${selectedType}`)
        .then(r => setTemplate(r.data.template))
        .catch(() => {});
    }
  }, [user?.store_id, cardType]);

  // Fetch available tags
  useEffect(() => {
    if (!user?._id) return;
    setLoadingTags(true);
    api.get(`/tags/${user._id}`)
      .then(r => setAvailableTags(r.data || []))
      .catch(() => {})
      .finally(() => setLoadingTags(false));
  }, [user?._id]);

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
    // Everything is optional — no recipient or photo required
    setShowPreview(true);
  };

  const createCard = async () => {
    // Read directly from store state — avoids any stale closure issue with user._id
    const storeUser = useAuthStore.getState().user;
    const userId = storeUser?._id || (storeUser as any)?.id || user?._id || '';
    if (!userId) {
      showSimpleAlert('Error', 'Not logged in. Please log out and log back in.');
      return;
    }
    // Treat as generic if no recipient name/phone entered
    const effectivelyGeneric = !customerName.trim() && !customerPhone.trim();
    setIsGeneric(effectivelyGeneric);
    setCreating(true);
    try {
      // Robust user ID — handles both _id and id field names
      const userId = user?._id || (user as any)?.id || '';
      if (!userId) {
        showSimpleAlert('Error', 'Could not get your user ID. Please log out and log back in.');
        setCreating(false);
        return;
      }
      const formData = new FormData();
      formData.append('salesman_id', userId);
      formData.append('customer_name', effectivelyGeneric ? '' : customerName.trim());
      formData.append('card_type', selectedType);
      if (effectivelyGeneric) formData.append('generic', 'true');
      if (customerPhone.trim()) formData.append('customer_phone', customerPhone.trim());
      if (customMessage.trim()) formData.append('custom_message', customMessage.trim());
      if (selectedTags.length > 0) {
        formData.append('tags', JSON.stringify(selectedTags));
        if (!startCampaign) formData.append('skip_campaign', 'true');
      }
      // Photo is optional for generic cards
      if (photo) {
        if (IS_WEB) {
          const response = await fetch(photo!.uri);
          const blob = await response.blob();
          formData.append('photo', blob, photo!.name || 'photo.jpg');
        } else {
          formData.append('photo', { uri: photo!.uri, type: photo!.type, name: photo!.name } as any);
        }
      }
      const res = await api.post('/congrats/create', formData);
      const cardId = res.data?.card_id;
      // Use the tracked short URL from the backend (enables contextual OG previews in iMessage)
      const shareUrl = res.data?.short_url || `${BASE_URL}/congrats/${cardId}${user?.ref_code ? `?ref=${user.ref_code}` : ''}`;
      setShowPreview(false);

      // Auto-save original photo to camera roll (native only - web doesn't need this)
      if (photo?.uri && !IS_WEB) {
        try {
          const { status } = await MediaLibrary.requestPermissionsAsync();
          if (status === 'granted') {
            await MediaLibrary.saveToLibraryAsync(photo.uri);
          }
        } catch (saveErr) {
          console.log('Auto-save photo to library failed:', saveErr);
        }
      }

      // If we came from an inbox thread, auto-return with the card link pre-filled
      if (returnToThread) {
        const prefillMsg = `Check out this ${meta.label.toLowerCase()} for ${customerName}! ${shareUrl}`;
        const qs = new URLSearchParams();
        if (customerName) qs.set('contact_name', customerName);
        if (customerPhone) qs.set('contact_phone', customerPhone);
        if (customerEmail) qs.set('contact_email', customerEmail);
        qs.set('prefill', prefillMsg);
        qs.set('event_type', `${cardType}_card_sent`);
        router.replace(`/thread/${returnToThread}?${qs.toString()}` as any);
        return;
      }

      // If we came from a contact page, go back and drop the URL in the composer
      if (return_to_contact && for_contact) {
        const prefillMsg = `Hey ${customerName}! ${shareUrl}`;
        const evtType = `${cardType}_card_sent`;
        router.replace(`/contact/${for_contact}?prefill=${encodeURIComponent(prefillMsg)}&event_type=${evtType}` as any);
        return;
      }

      setCreatedCard({ card_id: cardId, share_url: shareUrl });
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

  const navigateToThread = (contactId: string, cName: string, cPhone: string, cEmail: string, mode: string, prefillText: string) => {
    const params = new URLSearchParams();
    if (cName) params.set('contact_name', cName);
    if (cPhone) params.set('contact_phone', cPhone);
    if (cEmail) params.set('contact_email', cEmail);
    params.set('mode', mode);
    if (prefillText) params.set('prefill', prefillText);
    params.set('event_type', `${cardType}_card_sent`);
    const url = `/thread/${contactId}?${params.toString()}`;
    router.replace(url as any);
  };

  const handleShare = async (platform: string) => {
    if (!createdCard || !user?._id) return;
    const url = createdCard.share_url;
    const text = `Check out this ${meta.label.toLowerCase()} for ${customerName}! ${url}`;

    // For SMS and Email — route through internal inbox for tracking
    if (platform === 'sms' || platform === 'email') {
      // Validate: need phone for SMS, email for email
      if (platform === 'sms' && !customerPhone.trim()) {
        showSimpleAlert('Phone Required', 'Please enter a phone number to send via SMS.');
        return;
      }
      if (platform === 'email' && !customerEmail.trim()) {
        showSimpleAlert('Email Required', 'Please enter an email address to send via Email.');
        return;
      }

      try {
        // Find or create contact
        const payload: any = { name: customerName.trim(), event_type: `${cardType}_card_sent`, event_title: `${meta.label} Sent`, event_description: `Sent ${meta.label.toLowerCase()} via ${platform}`, event_icon: meta.icon, event_color: accent, event_channel: platform };
        if (customerPhone.trim()) payload.phone = customerPhone.trim();
        if (customerEmail.trim()) payload.email = customerEmail.trim();

        const res = await api.post(`/contacts/${user._id}/find-or-create-and-log`, payload);
        const contactId = res.data.contact_id;
        const cName = res.data.contact_name || customerName.trim();
        const cPhone = res.data.contact_phone || customerPhone.trim();
        const cEmail = res.data.contact_email || customerEmail.trim();

        if (res.data.needs_confirmation) {
          setMatchInfo(res.data);
          setPendingSharePlatform(platform);
          setMatchModalVisible(true);
          return;
        }

        // Navigate to inbox thread with pre-filled message
        navigateToThread(contactId, cName, cPhone, cEmail, platform, text);
      } catch (err: any) {
        const detail = err?.response?.data?.detail || '';
        if (detail.includes('Phone or email')) {
          showSimpleAlert('Missing Info', 'Please add a phone number or email for the recipient.');
        } else {
          showSimpleAlert('Error', 'Something went wrong. Please try again.');
        }
      }
      return;
    }

    // For social platforms — open external share links
    let shareUrl = '';
    switch (platform) {
      case 'facebook': shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`; break;
      case 'twitter': shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`; break;
    }
    if (IS_WEB) {
      if (navigator.share) { try { await navigator.share({ url }); } catch {} }
      else if (shareUrl) { window.open(shareUrl, '_blank'); }
      else { navigator.clipboard?.writeText(url); alert('Link copied!'); }
    } else { Linking.openURL(shareUrl); }
  };

  const resolveMatch = async (action: string) => {
    setMatchModalVisible(false);
    if (!user?._id || !pendingSharePlatform || !createdCard) return;
    const url = createdCard.share_url;
    const text = `Check out this ${meta.label.toLowerCase()} for ${customerName}! ${url}`;
    try {
      const payload: any = {
        name: customerName.trim(),
        event_type: `${cardType}_card_sent`, event_title: `${meta.label} Sent`,
        event_description: `Sent ${meta.label.toLowerCase()} via ${pendingSharePlatform}`,
        event_icon: meta.icon, event_color: accent, force_action: action, event_channel: pendingSharePlatform,
      };
      if (customerPhone.trim()) payload.phone = customerPhone.trim();
      if (customerEmail.trim()) payload.email = customerEmail.trim();

      const res = await api.post(`/contacts/${user._id}/find-or-create-and-log`, payload);
      const contactId = res.data.contact_id;
      navigateToThread(
        contactId,
        res.data.contact_name || customerName.trim(),
        res.data.contact_phone || customerPhone.trim(),
        res.data.contact_email || customerEmail.trim(),
        pendingSharePlatform,
        text
      );
    } catch (err) {
      showSimpleAlert('Error', 'Failed to process contact. Please try again.');
    }
    setMatchInfo(null); setPendingSharePlatform(null);
  };

  // ---- Created: share screen matching UniversalShareModal style ----
  if (createdCard) {
    const shareUrl = createdCard.share_url;
    const defaultShareText = `Check out this ${meta.label.toLowerCase()} for ${customerName}! ${shareUrl}`;

    const handleShareLink = async () => {
      try {
        if (IS_WEB && navigator.share) {
          await navigator.share({ title: meta.label, text: defaultShareText, url: shareUrl });
        } else {
          await navigator.clipboard?.writeText(shareUrl);
          showSimpleAlert('Link Copied!', 'Link has been copied to clipboard.');
        }
      } catch {}
    };

    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.shareModalInner}>
          <View style={s.shareHandle} />
          <Text style={s.shareTitle}>{isGeneric ? 'Your Card is Live!' : `Share ${meta.label}`}</Text>
          <Text style={s.shareSubtitle}>{isGeneric ? 'Copy the link and post it anywhere' : `Share it with ${customerName}`}</Text>

          {/* Generic mode: big prominent copy-link banner */}
          {isGeneric && (
            <TouchableOpacity
              style={{ backgroundColor: '#C9A962', borderRadius: 14, padding: 16, marginBottom: 20, flexDirection: 'row', alignItems: 'center', gap: 10 }}
              onPress={handleCopyLink}
              data-testid="generic-copy-link"
            >
              <Ionicons name="copy-outline" size={22} color="#000" />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 16, fontWeight: '700', color: '#000' }}>Copy Link to Share</Text>
                <Text style={{ fontSize: 12, color: '#00000080', marginTop: 2 }} numberOfLines={1}>{shareUrl}</Text>
              </View>
            </TouchableOpacity>
          )}

          {/* Pre-filled recipient section — hidden in generic mode */}
          {!isGeneric && (
            <View style={s.recipientSection}>
            <Text style={s.recipientLabel}>SEND TO (OPTIONAL)</Text>
            <TextInput style={s.recipientInput} placeholder="Recipient Name" placeholderTextColor="#6E6E73" value={customerName} onChangeText={setCustomerName} data-testid="card-share-name" />
            <TextInput style={s.recipientInput} placeholder="Phone" placeholderTextColor="#6E6E73" value={customerPhone} onChangeText={setCustomerPhone} keyboardType="phone-pad" data-testid="card-share-phone" />
            <TextInput style={s.recipientInput} placeholder="Email" placeholderTextColor="#6E6E73" value={customerEmail} onChangeText={setCustomerEmail} keyboardType="email-address" autoCapitalize="none" data-testid="card-share-email" />
          </View>
          )}

          {/* 2×3 action grid matching UniversalShareModal */}
          <View style={s.shareOptionsGrid}>
            <TouchableOpacity style={s.shareOption} onPress={handleShareLink} data-testid="card-share-link">
              <View style={[s.shareOptionIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="share-outline" size={24} color="#007AFF" />
              </View>
              <Text style={s.shareOptionText}>Share Link</Text>
            </TouchableOpacity>

            <TouchableOpacity style={s.shareOption} onPress={handleCopyLink} data-testid="card-copy-link">
              <View style={[s.shareOptionIcon, { backgroundColor: '#5856D620' }]}>
                <Ionicons name="copy-outline" size={24} color="#5856D6" />
              </View>
              <Text style={s.shareOptionText}>Copy Link</Text>
            </TouchableOpacity>

            <TouchableOpacity style={s.shareOption} onPress={() => handleShare('sms')} data-testid="card-share-sms">
              <View style={[s.shareOptionIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
              </View>
              <Text style={s.shareOptionText}>Via Text</Text>
            </TouchableOpacity>

            <TouchableOpacity style={s.shareOption} onPress={() => handleShare('email')} data-testid="card-share-email">
              <View style={[s.shareOptionIcon, { backgroundColor: '#FF950020' }]}>
                <Ionicons name="mail-outline" size={24} color="#FF9500" />
              </View>
              <Text style={s.shareOptionText}>Via Email</Text>
            </TouchableOpacity>

            <TouchableOpacity style={s.shareOption} onPress={() => { if (IS_WEB) { window.open(`/congrats/${createdCard.card_id}`, '_blank'); } else { Linking.openURL(`${BASE_URL}/congrats/${createdCard.card_id}`); } }} data-testid="card-share-preview">
              <View style={[s.shareOptionIcon, { backgroundColor: '#C9A96220' }]}>
                <Ionicons name="eye-outline" size={24} color="#C9A962" />
              </View>
              <Text style={s.shareOptionText}>Preview</Text>
            </TouchableOpacity>

            <TouchableOpacity style={s.shareOption} onPress={() => showSimpleAlert('QR Code', 'QR code feature coming soon!')} data-testid="card-share-qr">
              <View style={[s.shareOptionIcon, { backgroundColor: '#AF52DE20' }]}>
                <Ionicons name="qr-code-outline" size={24} color="#AF52DE" />
              </View>
              <Text style={s.shareOptionText}>Show QR</Text>
            </TouchableOpacity>
          </View>

          {/* Create Another + Cancel */}
          <TouchableOpacity style={s.createAnotherBtn} onPress={() => { setCreatedCard(null); setShowPreview(false); setPhoto(null); setCustomerName(''); setCustomMessage(''); setCustomerPhone(''); setCustomerEmail(''); setSelectedTags([]); setStartCampaign(true); }} data-testid="card-create-another">
            <Ionicons name="add-circle-outline" size={18} color={accent} />
            <Text style={[s.createAnotherText, { color: accent }]}>Create Another Card</Text>
          </TouchableOpacity>

          <TouchableOpacity style={s.cancelBtn} onPress={() => router.back()} data-testid="card-share-cancel">
            <Text style={s.cancelBtnText}>Cancel</Text>
          </TouchableOpacity>
        </View>

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
              <TouchableOpacity onPress={() => { setMatchModalVisible(false); setMatchInfo(null); }} style={{ marginTop: 4, padding: 12, alignItems: 'center' }}><Text style={{ fontSize: 17, color: colors.textSecondary }}>Cancel</Text></TouchableOpacity>
            </View>
          </View>
        )}
      </SafeAreaView>
    );
  }

  // ---- Preview ----
  if (showPreview) {
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
              {creating ? <ActivityIndicator size="small" color={colors.text} /> : <><Ionicons name="send" size={18} color={colors.text} /><Text style={s.previewSendText}>{isFromContact ? 'Create Card' : 'Create & Send'}</Text></>}
            </TouchableOpacity>
          </View>
          {selectedTags.length > 0 && (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 12, justifyContent: 'center' }} data-testid="card-preview-tags">
              {selectedTags.map(tag => {
                const tagObj = availableTags.find((t: any) => t.name === tag);
                return (
                  <View key={tag} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: `${tagObj?.color || accent}25`, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 }}>
                    <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: tagObj?.color || accent }} />
                    <Text style={{ fontSize: 14, color: tagObj?.color || accent, fontWeight: '600' }}>{tag}</Text>
                  </View>
                );
              })}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 6 }}>
                <Ionicons name={startCampaign ? 'megaphone' : 'megaphone-outline'} size={12} color={startCampaign ? '#34C759' : colors.textSecondary} />
                <Text style={{ fontSize: 13, color: startCampaign ? '#34C759' : colors.textSecondary }}>{startCampaign ? 'Campaign on' : 'Campaign off'}</Text>
              </View>
            </View>
          )}
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

        {/* Template picker — tap to change card type */}
        <Text style={s.fieldLabel}>CARD TYPE</Text>
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, borderWidth: 1.5, borderColor: accent, padding: 14, marginBottom: 20, gap: 12 }}
          onPress={() => setShowTypePicker(true)}
          data-testid="card-type-picker"
        >
          <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: accent + '25', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={meta.icon as any} size={22} color={accent} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>{meta.label}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>{meta.headline}</Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: accent + '20', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: accent }}>Change</Text>
            <Ionicons name="chevron-down" size={14} color={accent} />
          </View>
        </TouchableOpacity>

        {/* Type picker modal */}
        {showTypePicker && (
          <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 1000, justifyContent: 'flex-end' }}>
            <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 36 }}>
              <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text, marginBottom: 16 }}>Choose Card Type</Text>
              {Object.entries(TYPE_META).map(([key, t]) => (
                <TouchableOpacity
                  key={key}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 12, marginBottom: 8, backgroundColor: selectedType === key ? t.accent + '20' : colors.card, borderWidth: 1.5, borderColor: selectedType === key ? t.accent : colors.border }}
                  onPress={() => { setSelectedType(key); setShowTypePicker(false); }}
                  data-testid={`card-type-${key}`}
                >
                  <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: t.accent + '25', alignItems: 'center', justifyContent: 'center' }}>
                    <Ionicons name={t.icon as any} size={22} color={t.accent} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{t.label}</Text>
                    <Text style={{ fontSize: 13, color: colors.textSecondary }}>{t.headline}</Text>
                  </View>
                  {selectedType === key && <Ionicons name="checkmark-circle" size={22} color={t.accent} />}
                </TouchableOpacity>
              ))}
              {customTemplates.length > 0 && (
                <>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 8, marginBottom: 8 }}>My Custom Cards</Text>
                  {customTemplates.map((t: any) => (
                    <TouchableOpacity
                      key={t.card_type}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 12, marginBottom: 8, backgroundColor: selectedType === t.card_type ? '#C9A96220' : colors.card, borderWidth: 1.5, borderColor: selectedType === t.card_type ? '#C9A962' : colors.border }}
                      onPress={() => { setSelectedType(t.card_type); setTemplate(t); setShowTypePicker(false); }}
                      data-testid={`card-type-custom-${t.card_type}`}
                    >
                      <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: (t.accent_color || '#C9A962') + '25', alignItems: 'center', justifyContent: 'center' }}>
                        <Ionicons name="gift-outline" size={22} color={t.accent_color || '#C9A962'} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{t.headline}</Text>
                        <Text style={{ fontSize: 13, color: colors.textSecondary }}>Custom Card</Text>
                      </View>
                      {selectedType === t.card_type && <Ionicons name="checkmark-circle" size={22} color={t.accent_color || '#C9A962'} />}
                    </TouchableOpacity>
                  ))}
                </>
              )}
              <TouchableOpacity onPress={() => setShowTypePicker(false)} style={{ marginTop: 8, padding: 14, alignItems: 'center' }}>
                <Text style={{ fontSize: 17, color: colors.textSecondary }}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
        <Text style={s.fieldLabel}>{isGeneric ? 'CARD PHOTO (OPTIONAL)' : 'RECIPIENT PHOTO *'}</Text>
        <TouchableOpacity style={s.photoPicker} onPress={pickPhoto} data-testid="card-pick-photo">
          {photo ? <Image source={{ uri: photo.uri }} style={[s.photoPreview, { borderColor: accent }]} /> : (
            <View style={s.photoPlaceholder}><Ionicons name="camera" size={36} color={colors.textSecondary} /><Text style={s.photoPlaceholderText}>Tap to add photo</Text></View>
          )}
        </TouchableOpacity>
        {!isFromContact && (
          <>
            {/* Generic toggle — makes all contact fields optional */}
            <TouchableOpacity
              style={[{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 12, marginBottom: 14, borderWidth: 1 },
                isGeneric
                  ? { backgroundColor: accent + '20', borderColor: accent + '60' }
                  : { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => setIsGeneric(!isGeneric)}
              testID="generic-toggle"
            >
              <Ionicons
                name={isGeneric ? 'checkbox' : 'square-outline'}
                size={22}
                color={isGeneric ? accent : colors.textSecondary}
              />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Generic Card (no specific person)</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
                  Share with anyone — post to social, send in a group text, or copy the link
                </Text>
              </View>
            </TouchableOpacity>

            {!isGeneric && (
              <>
                <Text style={s.fieldLabel}>RECIPIENT NAME <Text style={{ color: colors.textTertiary, fontWeight: '400' }}>(optional — leave blank to share with anyone)</Text></Text>
                <TextInput style={s.input} value={customerName} onChangeText={setCustomerName} placeholder="Recipient Name" placeholderTextColor={colors.textSecondary} data-testid="card-recipient-name" />
                <Text style={[s.fieldLabel, { marginTop: 16 }]}>SEND TO (OPTIONAL)</Text>
                <TextInput style={s.input} value={customerPhone} onChangeText={setCustomerPhone} placeholder="Phone" placeholderTextColor={colors.textSecondary} keyboardType="phone-pad" />
                <TextInput style={[s.input, { marginTop: 8 }]} value={customerEmail} onChangeText={setCustomerEmail} placeholder="Email" placeholderTextColor={colors.textSecondary} keyboardType="email-address" autoCapitalize="none" />
              </>
            )}
          </>
        )}
        {isFromContact && customerName ? (
          <View style={{ marginTop: 8, marginBottom: 4 }}>
            <Text style={{ fontSize: 17, color: colors.textSecondary }}>For: <Text style={{ fontWeight: '600', color: colors.text }}>{customerName}</Text></Text>
          </View>
        ) : null}
        <Text style={[s.fieldLabel, { marginTop: 16 }]}>PERSONAL MESSAGE (OPTIONAL)</Text>
        <TextInput style={[s.input, { height: 100, textAlignVertical: 'top' }]} value={customMessage} onChangeText={setCustomMessage} placeholder="Add a personal message..." placeholderTextColor={colors.textSecondary} multiline />

        {/* Tag Picker */}
        <Text style={[s.fieldLabel, { marginTop: 20 }]}>APPLY TAG (OPTIONAL)</Text>
        <Text style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 8 }}>
          Applying a tag starts the associated follow-up campaign
        </Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 }} data-testid="card-tag-picker">
          {availableTags.map((tag: any) => {
            const isSelected = selectedTags.includes(tag.name);
            return (
              <TouchableOpacity
                key={tag._id || tag.name}
                onPress={() => {
                  setSelectedTags(prev =>
                    isSelected ? prev.filter(t => t !== tag.name) : [...prev, tag.name]
                  );
                }}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  paddingHorizontal: 12,
                  paddingVertical: 8,
                  borderRadius: 20,
                  borderWidth: 1.5,
                  borderColor: isSelected ? (tag.color || accent) : colors.border,
                  backgroundColor: isSelected ? `${tag.color || accent}20` : colors.card,
                  gap: 6,
                }}
                data-testid={`card-tag-${tag.name.toLowerCase().replace(/\s/g, '-')}`}
              >
                {isSelected && <Ionicons name="checkmark-circle" size={16} color={tag.color || accent} />}
                <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: tag.color || '#8E8E93' }} />
                <Text style={{ fontSize: 15, fontWeight: isSelected ? '600' : '400', color: isSelected ? (tag.color || accent) : colors.text }}>{tag.name}</Text>
              </TouchableOpacity>
            );
          })}
          {loadingTags && <ActivityIndicator size="small" color={colors.textSecondary} />}
          {!loadingTags && availableTags.length === 0 && (
            <Text style={{ fontSize: 15, color: colors.textSecondary, fontStyle: 'italic' }}>No tags available</Text>
          )}
        </View>

        {/* Campaign toggle — only shown when tags are selected */}
        {selectedTags.length > 0 && (
          <TouchableOpacity
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: colors.card,
              borderRadius: 10,
              paddingHorizontal: 14,
              paddingVertical: 12,
              marginTop: 8,
              borderWidth: 1,
              borderColor: colors.border,
            }}
            onPress={() => setStartCampaign(prev => !prev)}
            data-testid="card-campaign-toggle"
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 }}>
              <Ionicons name="megaphone-outline" size={18} color={startCampaign ? '#34C759' : colors.textSecondary} />
              <Text style={{ fontSize: 16, color: colors.text, flex: 1 }}>Start follow-up campaign</Text>
            </View>
            <View style={{
              width: 44, height: 26, borderRadius: 13,
              backgroundColor: startCampaign ? '#34C759' : colors.surface,
              justifyContent: 'center',
              paddingHorizontal: 2,
            }}>
              <View style={{
                width: 22, height: 22, borderRadius: 11,
                backgroundColor: '#FFF',
                alignSelf: startCampaign ? 'flex-end' : 'flex-start',
              }} />
            </View>
          </TouchableOpacity>
        )}

      <TouchableOpacity style={[s.createBtn, { backgroundColor: accent }, creating && { opacity: 0.5 }]} onPress={handlePreview} disabled={creating} data-testid="card-preview-btn">
          <Ionicons name="eye-outline" size={20} color={colors.text} /><Text style={s.createBtnText}>Preview Card</Text>
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
            <TouchableOpacity onPress={() => { setMatchModalVisible(false); setMatchInfo(null); }} style={{ marginTop: 4, padding: 12, alignItems: 'center' }}><Text style={{ fontSize: 17, color: colors.textSecondary }}>Cancel</Text></TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 28, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.surface },
  headerTitle: { fontSize: 19, fontWeight: '700', color: colors.text },
  scroll: { flex: 1, paddingHorizontal: 20 },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: '#6E6E73', marginTop: 16, marginBottom: 6, letterSpacing: 1 },
  input: { backgroundColor: colors.card, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 12, fontSize: 16, color: colors.text, borderWidth: 1.5, borderColor: colors.borderLight },
  photoPicker: { alignItems: 'center', marginBottom: 8 },
  photoPreview: { width: 160, height: 160, borderRadius: 32, borderWidth: 3 },
  photoPlaceholder: { width: 160, height: 160, borderRadius: 32, backgroundColor: colors.card, borderWidth: 2, borderColor: colors.surface, borderStyle: 'dashed', justifyContent: 'center', alignItems: 'center' },
  photoPlaceholderText: { fontSize: 15, color: '#8E8E93', marginTop: 8 },
  createBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderRadius: 12, paddingVertical: 16, marginTop: 30, gap: 8 },
  createBtnText: { fontSize: 18, fontWeight: '700', color: colors.text },
  // Share screen (matches UniversalShareModal)
  shareModalInner: { flex: 1, backgroundColor: colors.card, padding: 24, paddingBottom: 40 },
  shareHandle: { width: 40, height: 4, backgroundColor: colors.borderLight, borderRadius: 2, alignSelf: 'center', marginBottom: 20 },
  shareTitle: { fontSize: 21, fontWeight: '700', color: colors.text, textAlign: 'center', marginBottom: 4 },
  shareSubtitle: { fontSize: 16, color: '#8E8E93', textAlign: 'center', marginBottom: 24 },
  recipientSection: { marginBottom: 16, gap: 8 },
  recipientLabel: { fontSize: 12, fontWeight: '700', color: '#6E6E73', letterSpacing: 1 },
  recipientInput: { backgroundColor: colors.card, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 12, fontSize: 16, color: colors.text, borderWidth: 1.5, borderColor: colors.borderLight },
  shareOptionsGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 16 },
  shareOption: { width: '30%', alignItems: 'center' },
  shareOptionIcon: { width: 60, height: 60, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  shareOptionText: { fontSize: 14, fontWeight: '500', color: colors.text, textAlign: 'center' },
  createAnotherBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 24, paddingVertical: 14 },
  createAnotherText: { fontSize: 17, fontWeight: '600' },
  cancelBtn: { marginTop: 8, paddingVertical: 16, backgroundColor: colors.surface, borderRadius: 12 },
  cancelBtnText: { fontSize: 18, fontWeight: '600', color: '#FF3B30', textAlign: 'center' },
  // Preview
  previewCard: { backgroundColor: '#1A1A1A', borderRadius: 20, padding: 30, width: '100%', maxWidth: 380, alignItems: 'center', marginTop: 20, borderWidth: 1, borderColor: colors.surface },
  previewHeadline: { fontSize: 32, fontWeight: '800', marginBottom: 20, textAlign: 'center' },
  previewPhotoRing: { borderWidth: 4, borderRadius: 20, padding: 4, marginBottom: 16 },
  previewPhoto: { width: 140, height: 140, borderRadius: 16 },
  previewName: { fontSize: 24, fontWeight: '700', color: '#FFFFFF', marginBottom: 12, textAlign: 'center' },
  previewMessage: { fontSize: 17, color: '#FFFFFFCC', textAlign: 'center', lineHeight: 22, marginBottom: 12 },
  previewCustomBox: { borderLeftWidth: 3, paddingLeft: 14, paddingVertical: 6, width: '100%', marginBottom: 16 },
  previewCustomMsg: { fontSize: 16, fontStyle: 'italic', color: '#FFFFFFBB', lineHeight: 20 },
  previewDivider: { width: 50, height: 3, borderRadius: 2, marginVertical: 16 },
  previewSalesName: { fontSize: 18, fontWeight: '700', color: '#FFFFFF', marginBottom: 2 },
  previewSalesTitle: { fontSize: 15, fontWeight: '500' },
  previewActions: { flexDirection: 'row', gap: 12, marginTop: 24, width: '100%', maxWidth: 380 },
  previewEditBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 12, borderWidth: 1.5 },
  previewEditText: { fontSize: 18, fontWeight: '600' },
  previewSendBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 12 },
  previewSendText: { fontSize: 18, fontWeight: '700', color: colors.text },
  // Match modal
  modalOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', zIndex: 9999 },
  modalCard: { backgroundColor: colors.card, borderRadius: 16, padding: 24, width: '90%', maxWidth: 380 },
  modalTitle: { fontSize: 19, fontWeight: '700', color: colors.text, textAlign: 'center', marginBottom: 8 },
  modalSub: { fontSize: 16, color: '#8E8E93', textAlign: 'center', marginBottom: 16 },
  modalBox: { backgroundColor: colors.surface, borderRadius: 10, padding: 14, alignItems: 'center' },
  modalBoxLabel: { fontSize: 12, fontWeight: '700', color: '#6E6E73', letterSpacing: 1, marginBottom: 6 },
  modalBoxName: { fontSize: 18, fontWeight: '600', color: colors.text },
  modalBoxPhone: { fontSize: 15, color: '#8E8E93', marginTop: 2 },
  modalDivRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 12 },
  modalDivLine: { flex: 1, height: 1, backgroundColor: colors.surface },
  modalDivText: { fontSize: 14, color: '#6E6E73', marginHorizontal: 12 },
  modalAction: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 },
  modalActionText: { fontSize: 17, color: colors.text, fontWeight: '500', flex: 1 },
});
