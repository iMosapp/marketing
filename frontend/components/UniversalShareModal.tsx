import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  TextInput,
  ActivityIndicator,
  Platform,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';

const IS_WEB = Platform.OS === 'web';

interface UniversalShareModalProps {
  visible: boolean;
  onClose: () => void;
  title: string;
  subtitle: string;
  shareUrl: string;
  shareText?: string;
  showPreview?: boolean;
  previewUrl?: string;
  showQR?: boolean;
  vCardUserId?: string;
  userId?: string;
  eventType?: string;
}

const copyText = async (text: string) => {
  try {
    if (IS_WEB && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
    } else if (IS_WEB) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
};

export function UniversalShareModal({
  visible,
  onClose,
  title,
  subtitle,
  shareUrl,
  shareText,
  showPreview = true,
  previewUrl,
  showQR = false,
  vCardUserId,
  userId,
  eventType,
}: UniversalShareModalProps) {
  const colors = useThemeStore((s) => s.colors);
  const [recipientName, setRecipientName] = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [saving, setSaving] = useState(false);
  const [showQRView, setShowQRView] = useState(false);

  const defaultShareText = shareText || `Check this out: ${shareUrl}`;

  const reset = () => {
    setRecipientName('');
    setRecipientPhone('');
    setRecipientEmail('');
    setShowQRView(false);
  };

  const close = () => {
    reset();
    onClose();
  };

  // Log share event
  const logEvent = async (platform: string) => {
    const phone = recipientPhone.trim();
    const email = recipientEmail.trim();
    const name = recipientName.trim();
    if (!userId || (!phone && !email)) return;
    try {
      await api.post(`/contacts/${userId}/find-or-create-and-log`, {
        phone, email, name,
        event_type: eventType || 'link_shared',
        event_title: title,
        event_description: `Shared via ${platform}`,
        event_icon: 'share',
        event_color: '#007AFF',
      });
    } catch {}
  };

  // Share Link (native share sheet)
  const handleShareLink = async () => {
    try {
      if (IS_WEB && navigator.share) {
        await navigator.share({ title, text: defaultShareText, url: shareUrl });
      } else {
        await copyText(shareUrl);
        showSimpleAlert('Link Copied!', 'Link has been copied to clipboard.');
      }
    } catch {}
    logEvent('share_link');
    close();
  };

  // Copy Link
  const handleCopyLink = async () => {
    await copyText(shareUrl);
    showSimpleAlert('Link Copied!', 'Link has been copied to clipboard.');
    logEvent('copy_link');
    close();
  };

  // Via Text
  const handleViaText = () => {
    const phone = recipientPhone.trim();
    const isApple = /iPad|iPhone|iPod|Macintosh/.test(navigator?.userAgent || '');
    const sep = isApple ? '&' : '?';
    const msg = encodeURIComponent(defaultShareText);
    const smsUrl = phone
      ? `sms:${phone}${sep}body=${msg}`
      : `sms:${sep === '&' ? '&' : '?'}body=${msg}`;
    IS_WEB ? (window.location.href = smsUrl) : Linking.openURL(smsUrl);
    logEvent('sms');
    close();
  };

  // Via Email
  const handleViaEmail = () => {
    const email = recipientEmail.trim();
    const subject = encodeURIComponent(title);
    const body = encodeURIComponent(`Hi!\n\n${defaultShareText}\n\n`);
    const mailto = email
      ? `mailto:${email}?subject=${subject}&body=${body}`
      : `mailto:?subject=${subject}&body=${body}`;
    IS_WEB ? (window.location.href = mailto) : Linking.openURL(mailto);
    logEvent('email');
    close();
  };

  // Save vCard
  const handleSaveVCard = async () => {
    if (!vCardUserId) return;
    setSaving(true);
    try {
      const res = await api.get(`/card/vcard/${vCardUserId}`);
      if (IS_WEB && res.data) {
        const vcardData = typeof res.data === 'string' ? res.data : res.data.vcard || '';
        const filename = res.data.filename || 'contact.vcf';
        const blob = new Blob([vcardData], { type: 'text/vcard' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showSimpleAlert('Downloaded!', 'vCard saved with all your links.');
      }
    } catch {
      showSimpleAlert('Error', 'Could not generate vCard.');
    }
    setSaving(false);
    logEvent('vcard');
    close();
  };

  // Show QR
  const handleShowQR = () => {
    setShowQRView(true);
  };

  if (showQRView) {
    return (
      <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
        <TouchableOpacity style={styles.modalOverlay} activeOpacity={1} onPress={close}>
          <TouchableOpacity activeOpacity={1} onPress={() => {}}>
            <View style={styles.shareModal}>
              <View style={styles.shareModalHandle} />
              <Text style={styles.shareModalTitle}>QR Code</Text>
              <Text style={styles.shareModalSubtitle}>Scan to open link</Text>
              <View style={styles.qrContainer}>
                {/* Simple QR code display using a table-based approach for web */}
                <View style={styles.qrPlaceholder}>
                  <Ionicons name="qr-code" size={160} color="#FFF" />
                </View>
                <Text style={[styles.qrUrl, { color: '#8E8E93' }]} numberOfLines={2}>{shareUrl}</Text>
              </View>
              <TouchableOpacity style={styles.shareModalCancel} onPress={() => setShowQRView(false)}>
                <Text style={styles.shareModalCancelText}>Back</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    );
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
      <TouchableOpacity style={styles.modalOverlay} activeOpacity={1} onPress={close}>
        <TouchableOpacity activeOpacity={1} onPress={() => {}}>
          <View style={styles.shareModal}>
            <View style={styles.shareModalHandle} />
            <Text style={styles.shareModalTitle}>{title}</Text>
            <Text style={styles.shareModalSubtitle}>{subtitle}</Text>

            {/* Recipient Info */}
            <View style={styles.recipientSection}>
              <Text style={styles.recipientLabel}>SEND TO (OPTIONAL)</Text>
              <TextInput
                style={styles.recipientInput}
                placeholder="Recipient Name"
                placeholderTextColor="#6E6E73"
                value={recipientName}
                onChangeText={setRecipientName}
                data-testid="share-recipient-name"
              />
              <TextInput
                style={styles.recipientInput}
                placeholder="Phone"
                placeholderTextColor="#6E6E73"
                value={recipientPhone}
                onChangeText={setRecipientPhone}
                keyboardType="phone-pad"
                data-testid="share-recipient-phone"
              />
              <TextInput
                style={styles.recipientInput}
                placeholder="Email"
                placeholderTextColor="#6E6E73"
                value={recipientEmail}
                onChangeText={setRecipientEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                data-testid="share-recipient-email"
              />
            </View>

            {/* Share Options Grid */}
            <View style={styles.shareOptionsGrid}>
              <TouchableOpacity style={styles.shareOption} onPress={handleShareLink} data-testid="share-via-link">
                <View style={[styles.shareOptionIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="share-outline" size={24} color="#007AFF" />
                </View>
                <Text style={styles.shareOptionText}>Share Link</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.shareOption} onPress={handleCopyLink} data-testid="share-copy-link">
                <View style={[styles.shareOptionIcon, { backgroundColor: '#5856D620' }]}>
                  <Ionicons name="copy-outline" size={24} color="#5856D6" />
                </View>
                <Text style={styles.shareOptionText}>Copy Link</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.shareOption} onPress={handleViaText} data-testid="share-via-text">
                <View style={[styles.shareOptionIcon, { backgroundColor: '#34C75920' }]}>
                  <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
                </View>
                <Text style={styles.shareOptionText}>Via Text</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.shareOption} onPress={handleViaEmail} data-testid="share-via-email">
                <View style={[styles.shareOptionIcon, { backgroundColor: '#FF950020' }]}>
                  <Ionicons name="mail-outline" size={24} color="#FF9500" />
                </View>
                <Text style={styles.shareOptionText}>Via Email</Text>
              </TouchableOpacity>

              {showPreview && (
                <TouchableOpacity style={styles.shareOption} onPress={() => {
                  const url = previewUrl || shareUrl;
                  if (IS_WEB) { window.open(url, '_blank'); } else { Linking.openURL(url); }
                  logEvent('preview');
                }} data-testid="share-preview">
                  <View style={[styles.shareOptionIcon, { backgroundColor: '#C9A96220' }]}>
                    <Ionicons name="eye-outline" size={24} color="#C9A962" />
                  </View>
                  <Text style={styles.shareOptionText}>Preview</Text>
                </TouchableOpacity>
              )}

              {showQR && (
                <TouchableOpacity style={styles.shareOption} onPress={handleShowQR} data-testid="share-show-qr">
                  <View style={[styles.shareOptionIcon, { backgroundColor: '#AF52DE20' }]}>
                    <Ionicons name="qr-code-outline" size={24} color="#AF52DE" />
                  </View>
                  <Text style={styles.shareOptionText}>Show QR</Text>
                </TouchableOpacity>
              )}
            </View>

            <TouchableOpacity style={styles.shareModalCancel} onPress={close}>
              <Text style={styles.shareModalCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'flex-end',
  },
  shareModal: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  shareModalHandle: {
    width: 40,
    height: 4,
    backgroundColor: '#3A3A3C',
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  shareModalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
    marginBottom: 4,
  },
  shareModalSubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    marginBottom: 24,
  },
  recipientSection: {
    marginBottom: 16,
    gap: 8,
  },
  recipientLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#6E6E73',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  recipientInput: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
    color: '#FFF',
    borderWidth: 1.5,
    borderColor: '#3A3A3C',
  },
  shareOptionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 16,
  },
  shareOption: {
    width: '30%',
    alignItems: 'center',
  },
  shareOptionIcon: {
    width: 60,
    height: 60,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  shareOptionText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#FFF',
    textAlign: 'center',
  },
  shareModalCancel: {
    marginTop: 24,
    paddingVertical: 16,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
  },
  shareModalCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF3B30',
    textAlign: 'center',
  },
  // QR
  qrContainer: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  qrPlaceholder: {
    width: 200,
    height: 200,
    backgroundColor: '#2C2C2E',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  qrUrl: {
    fontSize: 12,
    textAlign: 'center',
    paddingHorizontal: 20,
  },
});
