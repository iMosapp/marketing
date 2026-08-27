import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Modal, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';

// "What to send" sheet — full reason + AI-drafted ready-to-send message.
// item: { contact_id, first_name, last_name, phone, reason_key, reason_label, icon, color, context? }
export function DraftMessageSheet({ userId, item, onClose, onUsed }: {
  userId?: string;
  item: any | null;
  onClose: () => void;
  onUsed?: (item: any) => void;
}) {
  const { colors } = useThemeStore();
  const router = useRouter();
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchDraft = async (it: any) => {
    if (!userId || !it?.contact_id) return;
    setLoading(true);
    setMsg('');
    try {
      const res = await api.get(`/home/draft/${userId}/${it.contact_id}`, { params: { reason: it.reason_key || '', context: it.context || '' } });
      setMsg(res.data.message || '');
    } catch {
      setMsg(`Hey ${it.first_name || ''}! Just checking in, how's everything going?`.replace('  ', ' '));
    }
    setLoading(false);
  };

  useEffect(() => { if (item) fetchDraft(item); }, [item]);

  const useMessage = () => {
    if (!item) return;
    onUsed?.(item);
    onClose();
    const qs = new URLSearchParams();
    qs.set('contact_name', `${item.first_name || ''} ${item.last_name || ''}`.trim());
    if (item.phone) qs.set('contact_phone', item.phone);
    qs.set('mode', 'sms');
    qs.set('prefill', msg);
    router.push(`/thread/${item.contact_id}?${qs.toString()}` as any);
  };

  return (
    <Modal visible={!!item} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} activeOpacity={1} onPress={onClose}>
        <TouchableOpacity activeOpacity={1} onPress={() => {}}>
          <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34 }} data-testid="draft-sheet">
            <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: 'center', marginBottom: 16 }} />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: (item?.color || '#C9A962') + '20', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name={(item?.icon as any) || 'chatbubble'} size={19} color={item?.color || '#C9A962'} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }} data-testid="draft-sheet-name">
                  Text {`${item?.first_name || ''} ${item?.last_name || ''}`.trim() || 'them'}
                </Text>
                <Text style={{ fontSize: 13, color: item?.color || colors.textSecondary, fontWeight: '600', marginTop: 1 }}>
                  Why now: {item?.reason_label || 'Keep the relationship warm'}
                </Text>
              </View>
            </View>

            <View style={{ backgroundColor: colors.bg, borderRadius: 16, padding: 16, marginTop: 14, minHeight: 88, justifyContent: 'center', borderWidth: 1, borderColor: colors.border }}>
              {loading ? (
                <View style={{ alignItems: 'center', gap: 8 }}>
                  <ActivityIndicator color="#C9A962" />
                  <Text style={{ fontSize: 13, color: colors.textSecondary }}>Writing your message...</Text>
                </View>
              ) : (
                <Text style={{ fontSize: 16, color: colors.text, lineHeight: 23 }} data-testid="draft-message-text">{msg}</Text>
              )}
            </View>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 8, textAlign: 'center' }}>
              You can edit it before it sends
            </Text>

            <TouchableOpacity
              onPress={useMessage}
              disabled={loading}
              style={{ backgroundColor: loading ? colors.border : '#007AFF', borderRadius: 16, paddingVertical: 15, alignItems: 'center', marginTop: 14, flexDirection: 'row', justifyContent: 'center', gap: 8 }}
              data-testid="draft-send-btn"
            >
              <Ionicons name="paper-plane" size={17} color="#fff" />
              <Text style={{ fontSize: 16, fontWeight: '800', color: '#fff' }}>Use This Message</Text>
            </TouchableOpacity>

            <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
              <TouchableOpacity
                onPress={() => item && fetchDraft(item)}
                disabled={loading}
                style={{ flex: 1, borderRadius: 16, paddingVertical: 13, alignItems: 'center', borderWidth: 1, borderColor: colors.border, flexDirection: 'row', justifyContent: 'center', gap: 6 }}
                data-testid="draft-regenerate-btn"
              >
                <Ionicons name="refresh" size={15} color={colors.text} />
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Different Message</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => { const cid = item?.contact_id; onClose(); if (cid) router.push(`/contact/${cid}` as any); }}
                style={{ flex: 1, borderRadius: 16, paddingVertical: 13, alignItems: 'center', borderWidth: 1, borderColor: colors.border, flexDirection: 'row', justifyContent: 'center', gap: 6 }}
                data-testid="draft-view-contact-btn"
              >
                <Ionicons name="person" size={15} color={colors.text} />
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>View Contact</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}
