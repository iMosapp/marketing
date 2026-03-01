import React, { useState, useRef } from 'react';
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
import { useRouter } from 'expo-router';
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
  const router = useRouter();
  const [recipientName, setRecipientName] = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [saving, setSaving] = useState(false);
  const [showQRView, setShowQRView] = useState(false);

  // Contact search state
  const [contactSuggestions, setContactSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const searchTimeout = useRef<NodeJS.Timeout | null>(null);

  const defaultShareText = shareText || `Check this out: ${shareUrl}`;

  const reset = () => {
    setRecipientName('');
    setRecipientPhone('');
    setRecipientEmail('');
    setShowQRView(false);
    setContactSuggestions([]);
    setShowSuggestions(false);
  };

  const close = () => {
    reset();
    onClose();
  };

  // Search contacts as user types — strict name-only match via backend
  const searchContacts = (query: string) => {
    setRecipientName(query);
    if (!userId || query.trim().length < 2) {
      setContactSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      try {
        const res = await api.get(`/contacts/${userId}?search=${encodeURIComponent(query.trim())}`);
        const matches = (res.data || []).slice(0, 5);
        setContactSuggestions(matches);
        setShowSuggestions(matches.length > 0);
      } catch {
        setContactSuggestions([]);
        setShowSuggestions(false);
      }
    }, 300);
  };

  const selectContact = (contact: any) => {
    setRecipientName(`${contact.first_name || ''} ${contact.last_name || ''}`.trim());
    setRecipientPhone(contact.phone || '');
    setRecipientEmail(contact.email || '');
    setContactSuggestions([]);
    setShowSuggestions(false);
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

  // Helper to navigate to thread with URL string format (reliable on web)
  const navigateToThread = (contactId: string, params: Record<string, string>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v) qs.set(k, v);
    }
    router.push(`/thread/${contactId}?${qs.toString()}` as any);
  };

  // Via Text — route through internal inbox for tracking
  const handleViaText = async () => {
    const phone = recipientPhone.trim();
    const name = recipientName.trim();
    if (!phone) {
      showSimpleAlert('Phone Required', 'Please enter a phone number to send via text.');
      return;
    }
    if (!userId) {
      // Fallback for non-logged-in: open native SMS
      const isApple = /iPad|iPhone|iPod|Macintosh/.test(navigator?.userAgent || '');
      const sep = isApple ? '&' : '?';
      const smsUrl = `sms:${phone}${sep}body=${encodeURIComponent(defaultShareText)}`;
      IS_WEB ? (window.location.href = smsUrl) : Linking.openURL(smsUrl);
      close();
      return;
    }
    setSaving(true);
    try {
      const res = await api.post(`/contacts/${userId}/find-or-create-and-log`, {
        phone, name: name || phone,
        event_type: eventType || 'link_shared',
        event_title: title,
        event_description: `Shared via text`,
        event_icon: 'share', event_color: '#007AFF',
      });
      const contactId = res.data.contact_id;
      close();
      navigateToThread(contactId, {
        contact_name: res.data.contact_name || name || phone,
        contact_phone: res.data.contact_phone || phone,
        mode: 'sms',
        prefill: defaultShareText,
      });
    } catch {
      showSimpleAlert('Error', 'Failed to find or create contact.');
    } finally { setSaving(false); }
  };

  // Via Email — route through internal inbox for tracking
  const handleViaEmail = async () => {
    const email = recipientEmail.trim();
    const name = recipientName.trim();
    if (!email) {
      showSimpleAlert('Email Required', 'Please enter an email address to send via email.');
      return;
    }
    if (!userId) {
      // Fallback for non-logged-in: open native email
      const subject = encodeURIComponent(title);
      const body = encodeURIComponent(`Hi!\n\n${defaultShareText}\n\n`);
      const mailto = `mailto:${email}?subject=${subject}&body=${body}`;
      IS_WEB ? (window.location.href = mailto) : Linking.openURL(mailto);
      close();
      return;
    }
    setSaving(true);
    try {
      const res = await api.post(`/contacts/${userId}/find-or-create-and-log`, {
        email, name: name || email,
        event_type: eventType || 'link_shared',
        event_title: title,
        event_description: `Shared via email`,
        event_icon: 'share', event_color: '#007AFF',
      });
      const contactId = res.data.contact_id;
      close();
      navigateToThread(contactId, {
        contact_name: res.data.contact_name || name || email,
        contact_email: res.data.contact_email || email,
        mode: 'email',
        prefill: defaultShareText,
      });
    } catch {
      showSimpleAlert('Error', 'Failed to find or create contact.');
    } finally { setSaving(false); }
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
          <View style={[styles.shareModal, { backgroundColor: colors.card }]}>
            <View style={[styles.shareModalHandle, { backgroundColor: colors.border }]} />
            <Text style={[styles.shareModalTitle, { color: colors.text }]}>{title}</Text>
            <Text style={[styles.shareModalSubtitle, { color: colors.textSecondary }]}>{subtitle}</Text>

            {/* Recipient Info */}
            <View style={styles.recipientSection}>
              <Text style={[styles.recipientLabel, { color: colors.textTertiary }]}>SEND TO (OPTIONAL)</Text>
              <View style={{ position: 'relative', zIndex: 10 }}>
                <TextInput
                  style={[styles.recipientInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.border }]}
                  placeholder="Search contact or type name..."
                  placeholderTextColor={colors.textTertiary}
                  value={recipientName}
                  onChangeText={searchContacts}
                  data-testid="share-recipient-name"
                />
                {showSuggestions && contactSuggestions.length > 0 && (
                  <View style={[styles.suggestionsDropdown, { backgroundColor: colors.cardAlt, borderColor: colors.border }]} data-testid="share-contact-suggestions">
                    {contactSuggestions.map((c: any) => (
                      <TouchableOpacity
                        key={c._id}
                        style={[styles.suggestionRow, { borderBottomColor: colors.border }]}
                        onPress={() => selectContact(c)}
                        data-testid={`suggestion-${c._id}`}
                      >
                        <View style={styles.suggestionAvatar}>
                          <Text style={styles.suggestionAvatarText}>{(c.first_name || '?')[0].toUpperCase()}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.suggestionName, { color: colors.text }]}>{c.first_name} {c.last_name || ''}</Text>
                          <Text style={[styles.suggestionDetail, { color: colors.textSecondary }]}>{c.phone || c.email || ''}</Text>
                        </View>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              </View>
              <TextInput
                style={[styles.recipientInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.border }]}
                placeholder="Phone"
                placeholderTextColor={colors.textTertiary}
                value={recipientPhone}
                onChangeText={setRecipientPhone}
                keyboardType="phone-pad"
                data-testid="share-recipient-phone"
              />
              <TextInput
                style={[styles.recipientInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.border }]}
                placeholder="Email"
                placeholderTextColor={colors.textTertiary}
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
                <Text style={[styles.shareOptionText, { color: colors.text }]}>Share Link</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.shareOption} onPress={handleCopyLink} data-testid="share-copy-link">
                <View style={[styles.shareOptionIcon, { backgroundColor: '#5856D620' }]}>
                  <Ionicons name="copy-outline" size={24} color="#5856D6" />
                </View>
                <Text style={[styles.shareOptionText, { color: colors.text }]}>Copy Link</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.shareOption} onPress={handleViaText} data-testid="share-via-text">
                <View style={[styles.shareOptionIcon, { backgroundColor: '#34C75920' }]}>
                  <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
                </View>
                <Text style={[styles.shareOptionText, { color: colors.text }]}>Via Text</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.shareOption} onPress={handleViaEmail} data-testid="share-via-email">
                <View style={[styles.shareOptionIcon, { backgroundColor: '#FF950020' }]}>
                  <Ionicons name="mail-outline" size={24} color="#FF9500" />
                </View>
                <Text style={[styles.shareOptionText, { color: colors.text }]}>Via Email</Text>
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
                  <Text style={[styles.shareOptionText, { color: colors.text }]}>Preview</Text>
                </TouchableOpacity>
              )}

              {showQR && (
                <TouchableOpacity style={styles.shareOption} onPress={handleShowQR} data-testid="share-show-qr">
                  <View style={[styles.shareOptionIcon, { backgroundColor: '#AF52DE20' }]}>
                    <Ionicons name="qr-code-outline" size={24} color="#AF52DE" />
                  </View>
                  <Text style={[styles.shareOptionText, { color: colors.text }]}>Show QR</Text>
                </TouchableOpacity>
              )}
            </View>

            <TouchableOpacity style={[styles.shareModalCancel, { backgroundColor: colors.bg }]} onPress={close}>
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
  suggestionsDropdown: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    marginTop: 4,
    maxHeight: 200,
    zIndex: 100,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#3A3A3C',
  },
  suggestionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 10,
    borderBottomWidth: 0.5,
    borderBottomColor: '#3A3A3C',
  },
  suggestionAvatar: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: '#C9A96220',
    alignItems: 'center',
    justifyContent: 'center',
  },
  suggestionAvatarText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#C9A962',
  },
  suggestionName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
  suggestionDetail: {
    fontSize: 12,
    color: '#8E8E93',
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
