import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Image,
  ActivityIndicator,
  Platform,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert } from '../../services/alert';

const IS_WEB = Platform.OS === 'web';

const COLORS = {
  background: '#000000',
  card: '#1C1C1E',
  textPrimary: '#FFFFFF',
  textSecondary: '#8E8E93',
  accent: '#007AFF',
  border: '#2C2C2E',
  success: '#34C759',
  gold: '#C9A962',
};

export default function CreateCongratsCardPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [photo, setPhoto] = useState<{uri: string, type: string, name: string} | null>(null);
  const [creating, setCreating] = useState(false);
  const [createdCard, setCreatedCard] = useState<{card_id: string, share_url: string} | null>(null);
  const [matchModalVisible, setMatchModalVisible] = useState(false);
  const [matchInfo, setMatchInfo] = useState<any>(null);
  const [pendingSharePlatform, setPendingSharePlatform] = useState<string | null>(null);

  const pickPhoto = async () => {
    if (IS_WEB) {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
      });
      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        setPhoto({ uri: asset.uri, type: asset.mimeType || 'image/jpeg', name: asset.fileName || 'photo.jpg' });
      }
    } else {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        showSimpleAlert('Permission Denied', 'Photo library access is required.');
        return;
      }
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
      });
      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        setPhoto({ uri: asset.uri, type: asset.mimeType || 'image/jpeg', name: asset.fileName || 'photo.jpg' });
      }
    }
  };

  const createCard = async () => {
    if (!customerName.trim()) {
      showSimpleAlert('Required', 'Please enter the customer name');
      return;
    }
    if (!photo) {
      showSimpleAlert('Required', 'Please add a customer photo');
      return;
    }
    if (!user?._id) return;

    setCreating(true);
    try {
      const formData = new FormData();
      formData.append('salesman_id', user._id);
      formData.append('customer_name', customerName.trim());
      if (customerPhone.trim()) formData.append('customer_phone', customerPhone.trim());
      if (customMessage.trim()) formData.append('custom_message', customMessage.trim());

      if (IS_WEB) {
        const response = await fetch(photo.uri);
        const blob = await response.blob();
        formData.append('photo', blob, photo.name || 'photo.jpg');
      } else {
        formData.append('photo', { uri: photo.uri, type: photo.type, name: photo.name } as any);
      }

      const res = await api.post('/congrats/create', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const cardId = res.data?.card_id;
      // Always use production URL for sharing
      const shareUrl = `https://app.imosapp.com/congrats/${cardId}`;

      setCreatedCard({ card_id: cardId, share_url: shareUrl });
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to create card';
      showSimpleAlert('Error', typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setCreating(false);
    }
  };

  const handleCopyLink = async () => {
    if (!createdCard) return;
    try {
      if (IS_WEB) {
        await navigator.clipboard.writeText(createdCard.share_url);
      } else {
        const Clipboard = require('expo-clipboard');
        await Clipboard.setStringAsync(createdCard.share_url);
      }
      showSimpleAlert('Copied', 'Link copied to clipboard');
    } catch {
      showSimpleAlert('Error', 'Failed to copy link');
    }
  };

  const handleShare = async (platform: string) => {
    if (!createdCard) return;
    const url = createdCard.share_url;
    const text = `Check out this congrats card for ${customerName}!`;
    let shareUrl = '';

    switch (platform) {
      case 'facebook':
        shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
        break;
      case 'twitter':
        shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
        break;
      case 'sms': {
        const isApple = /iPad|iPhone|iPod|Macintosh/.test(navigator.userAgent);
        const sep = isApple ? '&' : '?';
        const phone = customerPhone.trim();
        shareUrl = phone
          ? `sms:${phone}${sep}body=${encodeURIComponent(text + ' ' + url)}`
          : `sms:${sep === '&' ? '&' : '?'}body=${encodeURIComponent(text + ' ' + url)}`;
        break;
      }
      case 'email':
        shareUrl = `mailto:?subject=${encodeURIComponent('Congrats Card')}&body=${encodeURIComponent(text + '\n\n' + url)}`;
        break;
    }

    if (IS_WEB) {
      // Use anchor-click technique to bypass popup blockers for sms:/mailto:
      if (platform === 'sms' || platform === 'email') {
        const a = document.createElement('a');
        a.href = shareUrl;
        a.target = '_self';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } else {
        window.open(shareUrl, '_blank');
      }
    } else {
      Linking.openURL(shareUrl);
    }

    // Log contact event if we have a phone number
    if (customerPhone.trim() && user?._id) {
      try {
        const res = await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
          phone: customerPhone.trim(),
          name: customerName.trim(),
          event_type: 'congrats_card_sent',
          event_title: 'Congrats Card Sent',
          event_description: `Sent congrats card via ${platform}`,
          event_icon: 'gift',
          event_color: '#C9A962',
        });
        if (res.data.needs_confirmation) {
          setMatchInfo(res.data);
          setPendingSharePlatform(platform);
          setMatchModalVisible(true);
        }
      } catch (err) {
        console.error('Failed to log congrats event:', err);
      }
    }
  };

  const resolveCongratsMatch = async (action: string) => {
    setMatchModalVisible(false);
    if (!user?._id || !pendingSharePlatform) return;
    try {
      await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
        phone: customerPhone.trim(),
        name: customerName.trim(),
        event_type: 'congrats_card_sent',
        event_title: 'Congrats Card Sent',
        event_description: `Sent congrats card via ${pendingSharePlatform}`,
        event_icon: 'gift',
        event_color: '#C9A962',
        force_action: action,
      });
    } catch {}
    setMatchInfo(null);
    setPendingSharePlatform(null);
  };

  const handleDownload = () => {
    if (!createdCard) return;
    const imageUrl = `https://app.imosapp.com/api/congrats/card/${createdCard.card_id}/image`;
    if (IS_WEB) {
      window.open(imageUrl, '_blank');
    } else {
      Linking.openURL(imageUrl);
    }
  };

  const handleViewCard = () => {
    if (!createdCard) return;
    if (IS_WEB) {
      window.open(createdCard.share_url, '_blank');
    } else {
      Linking.openURL(createdCard.share_url);
    }
  };

  // ---- Created state: show sharing options ----
  if (createdCard) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={28} color={COLORS.accent} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Card Created!</Text>
          <View style={{ width: 28 }} />
        </View>
        <ScrollView style={styles.scrollContent} contentContainerStyle={{ alignItems: 'center', paddingBottom: 40 }}>
          <View style={styles.successIcon}>
            <Ionicons name="checkmark-circle" size={64} color={COLORS.success} />
          </View>
          <Text style={styles.successTitle}>Congrats Card Ready!</Text>
          <Text style={styles.successSubtitle}>Share it with {customerName}</Text>

          {/* Card Link */}
          <View style={styles.linkBox}>
            <Text style={styles.linkText} numberOfLines={1}>{createdCard.share_url}</Text>
          </View>

          {/* Action Buttons */}
          <View style={styles.actionGrid}>
            <TouchableOpacity style={styles.actionBtn} onPress={handleCopyLink}>
              <View style={[styles.actionIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="copy-outline" size={24} color="#007AFF" />
              </View>
              <Text style={styles.actionLabel}>Copy Link</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.actionBtn} onPress={handleDownload}>
              <View style={[styles.actionIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="download-outline" size={24} color="#34C759" />
              </View>
              <Text style={styles.actionLabel}>Download</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.actionBtn} onPress={handleViewCard}>
              <View style={[styles.actionIcon, { backgroundColor: '#C9A96220' }]}>
                <Ionicons name="eye-outline" size={24} color="#C9A962" />
              </View>
              <Text style={styles.actionLabel}>View Card</Text>
            </TouchableOpacity>
          </View>

          {/* Share to Social */}
          <Text style={styles.sectionLabel}>SHARE VIA</Text>
          <View style={styles.shareRow}>
            <TouchableOpacity style={styles.shareBtn} onPress={() => handleShare('sms')}>
              <View style={[styles.shareIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="chatbubble" size={22} color="#34C759" />
              </View>
              <Text style={styles.shareLabel}>SMS</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.shareBtn} onPress={() => handleShare('email')}>
              <View style={[styles.shareIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="mail" size={22} color="#007AFF" />
              </View>
              <Text style={styles.shareLabel}>Email</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.shareBtn} onPress={() => handleShare('facebook')}>
              <View style={[styles.shareIcon, { backgroundColor: '#1877F220' }]}>
                <Ionicons name="logo-facebook" size={22} color="#1877F2" />
              </View>
              <Text style={styles.shareLabel}>Facebook</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.shareBtn} onPress={() => handleShare('twitter')}>
              <View style={[styles.shareIcon, { backgroundColor: '#1DA1F220' }]}>
                <Ionicons name="logo-twitter" size={22} color="#1DA1F2" />
              </View>
              <Text style={styles.shareLabel}>Twitter</Text>
            </TouchableOpacity>
          </View>

          {/* Create Another */}
          <TouchableOpacity 
            style={styles.createAnotherBtn}
            onPress={() => { setCreatedCard(null); setPhoto(null); setCustomerName(''); setCustomMessage(''); setCustomerPhone(''); }}
          >
            <Ionicons name="add-circle-outline" size={20} color={COLORS.accent} />
            <Text style={styles.createAnotherText}>Create Another Card</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ---- Creation form ----
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color={COLORS.accent} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Create Congrats Card</Text>
        <View style={{ width: 28 }} />
      </View>
      <ScrollView style={styles.scrollContent} contentContainerStyle={{ paddingBottom: 40 }}>
        {/* Photo */}
        <Text style={styles.fieldLabel}>CUSTOMER PHOTO *</Text>
        <TouchableOpacity style={styles.photoPicker} onPress={pickPhoto}>
          {photo ? (
            <Image source={{ uri: photo.uri }} style={styles.photoPreview} />
          ) : (
            <View style={styles.photoPlaceholder}>
              <Ionicons name="camera" size={36} color={COLORS.textSecondary} />
              <Text style={styles.photoPlaceholderText}>Tap to add photo</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Send To */}
        <Text style={styles.fieldLabel}>SEND TO (OPTIONAL)</Text>
        <TextInput
          style={styles.input}
          value={customerName}
          onChangeText={setCustomerName}
          placeholder="Recipient Name"
          placeholderTextColor={COLORS.textSecondary}
        />
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 8, width: '100%' }}>
          <TextInput
            style={[styles.input, { flex: 1, minWidth: 0 }]}
            value={customerPhone}
            onChangeText={setCustomerPhone}
            placeholder="Phone"
            placeholderTextColor={COLORS.textSecondary}
            keyboardType="phone-pad"
          />
          <TextInput
            style={[styles.input, { flex: 1, minWidth: 0 }]}
            value={customerEmail}
            onChangeText={setCustomerEmail}
            placeholder="Email"
            placeholderTextColor={COLORS.textSecondary}
            keyboardType="email-address"
            autoCapitalize="none"
          />
        </View>

        {/* Custom Message (optional) */}
        <Text style={[styles.fieldLabel, { marginTop: 16 }]}>CUSTOM MESSAGE (OPTIONAL)</Text>
        <TextInput
          style={[styles.input, { height: 100, textAlignVertical: 'top' }]}
          value={customMessage}
          onChangeText={setCustomMessage}
          placeholder="Add a personal message..."
          placeholderTextColor={COLORS.textSecondary}
          multiline
        />

        {/* Create Button */}
        <TouchableOpacity 
          style={[styles.createBtn, (!customerName.trim() || !photo || creating) && styles.createBtnDisabled]}
          onPress={createCard}
          disabled={!customerName.trim() || !photo || creating}
        >
          {creating ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <>
              <Ionicons name="gift" size={20} color="#FFF" />
              <Text style={styles.createBtnText}>Create & Share Card</Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>

      {/* Contact Match Modal */}
      {matchModalVisible && matchInfo && (
        <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
          <View style={{ backgroundColor: '#1C1C1E', borderRadius: 16, padding: 24, width: '90%', maxWidth: 380 }} data-testid="congrats-match-modal">
            <View style={{ alignItems: 'center', marginBottom: 16 }}>
              <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: '#FF950015', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="person-circle" size={44} color="#FF9500" />
              </View>
            </View>
            <Text style={{ fontSize: 18, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 8 }}>Contact Already Exists</Text>
            <Text style={{ fontSize: 14, color: '#8E8E93', textAlign: 'center', marginBottom: 16 }}>A contact with this number already exists:</Text>
            <View style={{ backgroundColor: '#2C2C2E', borderRadius: 10, padding: 14, alignItems: 'center' }}>
              <Text style={{ fontSize: 10, fontWeight: '700', color: '#6E6E73', letterSpacing: 1, marginBottom: 6 }}>EXISTING CONTACT</Text>
              <Text style={{ fontSize: 17, fontWeight: '600', color: '#FFF' }}>{matchInfo.existing_name}</Text>
              {matchInfo.phone ? <Text style={{ fontSize: 13, color: '#8E8E93', marginTop: 2 }}>{matchInfo.phone}</Text> : null}
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginVertical: 12 }}>
              <View style={{ flex: 1, height: 1, backgroundColor: '#2C2C2E' }} />
              <Text style={{ fontSize: 12, color: '#6E6E73', marginHorizontal: 12 }}>You entered</Text>
              <View style={{ flex: 1, height: 1, backgroundColor: '#2C2C2E' }} />
            </View>
            <View style={{ backgroundColor: '#2C2C2E', borderRadius: 10, padding: 14, alignItems: 'center', marginBottom: 20 }}>
              <Text style={{ fontSize: 17, fontWeight: '600', color: '#FF9500' }}>{matchInfo.provided_name}</Text>
            </View>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#2C2C2E', padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveCongratsMatch('use_existing')}>
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
              <Text style={{ fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 }}>Use Existing Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#2C2C2E', padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveCongratsMatch('update_name')}>
              <Ionicons name="create" size={20} color="#007AFF" />
              <Text style={{ fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 }}>Update to "{matchInfo.provided_name}"</Text>
            </TouchableOpacity>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#2C2C2E', padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveCongratsMatch('create_new')}>
              <Ionicons name="person-add" size={20} color="#FF9500" />
              <Text style={{ fontSize: 15, color: '#FFF', fontWeight: '500', flex: 1 }}>Create New Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setMatchModalVisible(false); setMatchInfo(null); }} style={{ marginTop: 4, padding: 12, alignItems: 'center' }}>
              <Text style={{ fontSize: 15, color: '#8E8E93' }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  scrollContent: { flex: 1, paddingHorizontal: 20 },
  fieldLabel: { fontSize: 10, fontWeight: '700', color: '#6E6E73', marginTop: 16, marginBottom: 6, letterSpacing: 1, textTransform: 'uppercase' },
  input: {
    backgroundColor: COLORS.card,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
    color: COLORS.textPrimary,
    borderWidth: 1.5,
    borderColor: '#3A3A3C',
  },
  photoPicker: { alignItems: 'center', marginBottom: 8 },
  photoPreview: { width: 160, height: 160, borderRadius: 32, borderWidth: 3, borderColor: COLORS.gold },
  photoPlaceholder: {
    width: 160, height: 160, borderRadius: 32,
    backgroundColor: COLORS.card,
    borderWidth: 2, borderColor: COLORS.border, borderStyle: 'dashed',
    justifyContent: 'center', alignItems: 'center',
  },
  photoPlaceholderText: { fontSize: 13, color: COLORS.textSecondary, marginTop: 8 },
  createBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.gold,
    borderRadius: 12,
    paddingVertical: 16,
    marginTop: 30,
    gap: 8,
  },
  createBtnDisabled: { opacity: 0.5 },
  createBtnText: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  // Success state
  successIcon: { marginTop: 30, marginBottom: 16 },
  successTitle: { fontSize: 24, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  successSubtitle: { fontSize: 16, color: COLORS.textSecondary, marginBottom: 24 },
  linkBox: {
    backgroundColor: COLORS.card,
    borderRadius: 10,
    padding: 14,
    width: '100%',
    marginBottom: 24,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  linkText: { fontSize: 14, color: COLORS.accent },
  actionGrid: { flexDirection: 'row', justifyContent: 'center', gap: 20, marginBottom: 30, width: '100%' },
  actionBtn: { alignItems: 'center', width: 80 },
  actionIcon: {
    width: 56, height: 56, borderRadius: 16,
    justifyContent: 'center', alignItems: 'center',
    marginBottom: 8,
  },
  actionLabel: { fontSize: 12, color: COLORS.textPrimary, fontWeight: '500' },
  sectionLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, alignSelf: 'flex-start', marginBottom: 12, letterSpacing: 0.5 },
  shareRow: { flexDirection: 'row', justifyContent: 'center', gap: 24, marginBottom: 30, width: '100%' },
  shareBtn: { alignItems: 'center', width: 64 },
  shareIcon: { width: 48, height: 48, borderRadius: 24, justifyContent: 'center', alignItems: 'center', marginBottom: 6 },
  shareLabel: { fontSize: 11, color: COLORS.textSecondary },
  createAnotherBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.accent,
    width: '100%',
  },
  createAnotherText: { fontSize: 15, color: COLORS.accent, fontWeight: '600' },
});
