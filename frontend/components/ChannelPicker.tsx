import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Modal, Clipboard, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Linking } from 'react-native';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import { useToast } from './common/Toast';
import api from '../services/api';

type Channel = {
  id: string; name: string; icon: string; color: string;
  url_scheme: string; requires_phone: boolean;
};

type ChannelPickerProps = {
  message: string;
  phone?: string;
  email?: string;
  link?: string;
  onSent?: (channelId: string) => void;
  visible: boolean;
  onClose: () => void;
};

const IS_WEB = Platform.OS === 'web';

function buildUrl(scheme: string, params: { phone?: string; phone_clean?: string; email?: string; message: string; link?: string }): string {
  let url = scheme;
  url = url.replace('{phone}', encodeURIComponent(params.phone || ''));
  url = url.replace('{phone_clean}', (params.phone || '').replace(/\D/g, ''));
  url = url.replace('{email}', encodeURIComponent(params.email || ''));
  url = url.replace('{message}', encodeURIComponent(params.message));
  url = url.replace('{link}', encodeURIComponent(params.link || ''));

  // iOS SMS uses & separator, Android uses ?
  if (url.startsWith('sms:') && IS_WEB && typeof window !== 'undefined') {
    const ua = window.navigator.userAgent.toLowerCase();
    if (/iphone|ipad|ipod/.test(ua)) {
      url = url.replace('?body=', '&body=');
    }
  }
  return url;
}

export default function ChannelPicker({ message, phone, email, link, onSent, visible, onClose }: ChannelPickerProps) {
  const colors = useThemeStore((s) => s.colors);
  const user = useAuthStore((s) => s.user);
  const { showToast } = useToast();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!loaded && user?._id) {
      api.get(`/messaging-channels/user/${user._id}`)
        .then(res => {
          setChannels(res.data.channels || []);
          setLoaded(true);
        })
        .catch(() => {
          // Fallback to SMS only
          setChannels([{ id: 'sms', name: 'SMS / iMessage', icon: 'chatbubble-ellipses', color: '#34C759', url_scheme: 'sms:{phone}?body={message}', requires_phone: true }]);
          setLoaded(true);
        });
    }
  }, [user?._id, loaded]);

  const handleSelect = useCallback((ch: Channel) => {
    const params = {
      phone: phone || '',
      phone_clean: (phone || '').replace(/\D/g, ''),
      email: email || '',
      message,
      link: link || '',
    };

    if (ch.id === 'clipboard') {
      if (IS_WEB && typeof navigator !== 'undefined' && navigator.clipboard) {
        navigator.clipboard.writeText(message);
      } else {
        Clipboard.setString(message);
      }
      showToast('Copied to clipboard!', 'success');
      onSent?.('clipboard');
      onClose();
      return;
    }

    // For external apps: copy message to clipboard first so user can paste
    try {
      if (IS_WEB && typeof navigator !== 'undefined' && navigator.clipboard) {
        navigator.clipboard.writeText(message);
      } else {
        Clipboard.setString(message);
      }
    } catch {}

    const url = buildUrl(ch.url_scheme, params);

    if (IS_WEB && typeof window !== 'undefined') {
      window.open(url, '_blank');
    } else {
      Linking.openURL(url).catch(() => {
        showToast(`Could not open ${ch.name}`, 'error');
      });
    }
    showToast(`Message copied & opening ${ch.name}... Paste to send!`, 'success');
    onSent?.(ch.id);
    onClose();
  }, [message, phone, email, link, onSent, onClose]);

  // Auto-send: If only 1 channel, skip the picker
  useEffect(() => {
    if (visible && loaded && channels.length === 1) {
      handleSelect(channels[0]);
    }
  }, [visible, loaded, channels.length]);

  // Don't show modal for single channel (auto-send handles it)
  if (!visible || !loaded || channels.length <= 1) return null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={onClose}>
        <View style={[styles.sheet, { backgroundColor: colors.card, borderColor: colors.surface }]} data-testid="channel-picker-modal">
          <View style={styles.handle} />
          <Text style={[styles.sheetTitle, { color: colors.text }]}>Send via</Text>

          <View style={styles.grid}>
            {channels.map(ch => {
              const disabled = ch.requires_phone && !phone;
              return (
                <TouchableOpacity
                  key={ch.id}
                  onPress={() => !disabled && handleSelect(ch)}
                  disabled={disabled}
                  style={[styles.channelBtn, disabled && { opacity: 0.3 }]}
                  data-testid={`channel-option-${ch.id}`}
                >
                  <View style={[styles.channelCircle, { backgroundColor: `${ch.color}18` }]}>
                    <Ionicons name={ch.icon as any} size={24} color={ch.color} />
                  </View>
                  <Text style={[styles.channelLabel, { color: colors.text }]} numberOfLines={1}>{ch.name.split(' /')[0]}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <TouchableOpacity onPress={onClose} style={[styles.cancelRow, { borderColor: colors.surface }]} data-testid="cancel-channel-picker">
            <Text style={{ color: colors.textSecondary, fontSize: 14, fontWeight: '600' }}>Cancel</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>
    </Modal>
  );
}

// Hook for easy integration
export function useChannelPicker() {
  const [state, setState] = useState<{ visible: boolean; message: string; phone?: string; email?: string; link?: string; onSent?: (ch: string) => void }>({
    visible: false, message: '',
  });

  const open = useCallback((params: { message: string; phone?: string; email?: string; link?: string; onSent?: (ch: string) => void }) => {
    setState({ visible: true, ...params });
  }, []);

  const close = useCallback(() => {
    setState(prev => ({ ...prev, visible: false }));
  }, []);

  return { ...state, open, close };
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, borderWidth: 1, borderBottomWidth: 0, padding: 20, paddingBottom: 30 },
  handle: { width: 36, height: 4, borderRadius: 2, backgroundColor: '#666', alignSelf: 'center', marginBottom: 16 },
  sheetTitle: { fontSize: 17, fontWeight: '700', textAlign: 'center', marginBottom: 16 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 16 },
  channelBtn: { alignItems: 'center', width: 72, gap: 6 },
  channelCircle: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center' },
  channelLabel: { fontSize: 11, fontWeight: '600', textAlign: 'center' },
  cancelRow: { marginTop: 16, paddingTop: 14, borderTopWidth: 1, alignItems: 'center' },
});
