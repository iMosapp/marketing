import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { tid } from '../scripts/shared';

export type ScheduledSend = {
  id: string;
  body: string;
  status: 'pending' | 'processing' | 'sent' | 'failed' | 'cancelled' | string;
  send_at: string | null;
  sent_at: string | null;
  event_type: string;
  has_media: boolean;
  error?: string | null;
};

const ACCENT = '#C9A962';

const fmtTime = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

export const describeSend = (s: ScheduledSend) => {
  if (s.event_type === 'review_request_sent') return { icon: 'star-outline', color: '#FF9500', label: 'Review request' };
  if (s.event_type === 'congrats_card_sent') {
    return s.has_media
      ? { icon: 'image-outline', color: '#34C759', label: 'Delivery photo (MMS)' }
      : { icon: 'gift-outline', color: ACCENT, label: 'Digital card link' };
  }
  return { icon: 'chatbubble-outline', color: '#5AC8FA', label: 'Text' };
};

export const statusLine = (s: ScheduledSend) => {
  if (s.status === 'sent') return { text: `Sent ${fmtTime(s.sent_at || s.send_at)}`, color: '#34C759', done: true };
  if (s.status === 'failed') return { text: 'Failed', color: '#FF3B30', done: false };
  if (s.status === 'cancelled') return { text: 'Cancelled', color: '#8E8E93', done: false };
  if (s.status === 'processing') return { text: 'Sending now', color: ACCENT, done: false };
  return { text: `Sending ${fmtTime(s.send_at)}`, color: ACCENT, done: false };
};

export function useScheduledSends(userId?: string, contactId?: string, active = true) {
  const [rows, setRows] = useState<ScheduledSend[] | null>(null);
  useEffect(() => {
    if (!active || !userId || !contactId) return;
    let stop = false;
    let timer: any;
    const tick = async () => {
      try {
        const res = await api.get(`/messages/scheduled/${userId}/${contactId}`);
        if (stop) return;
        const list: ScheduledSend[] = Array.isArray(res.data) ? res.data : [];
        setRows(list);
        const waiting = list.some(r => r.status === 'pending' || r.status === 'processing');
        if (waiting) timer = setTimeout(tick, 10000);
      } catch {
        if (!stop) timer = setTimeout(tick, 15000);
      }
    };
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [userId, contactId, active]);
  return rows;
}

export const ScheduledSendRow = ({ send }: { send: ScheduledSend }) => {
  const { colors } = useThemeStore();
  const d = describeSend(send);
  const st = statusLine(send);
  return (
    <View style={styles.row} {...tid(`scheduled-send-${send.id}`)}>
      <View style={[styles.icon, { backgroundColor: d.color + '20' }]}>
        <Ionicons name={d.icon as any} size={16} color={d.color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[styles.label, { color: colors.text }]}>{d.label}</Text>
        {!!send.body && (
          <Text style={[styles.body, { color: colors.textSecondary }]} numberOfLines={2} {...tid(`scheduled-send-body-${send.id}`)}>{send.body}</Text>
        )}
        {send.status === 'failed' && !!send.error && (
          <Text style={[styles.body, { color: '#FF3B30' }]} numberOfLines={2}>{send.error}</Text>
        )}
      </View>
      <View style={styles.statusWrap}>
        {st.done && <Ionicons name="checkmark-circle" size={14} color={st.color} />}
        <Text style={[styles.status, { color: st.color }]} {...tid(`scheduled-send-status-${send.id}`)}>{st.text}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 8, gap: 10 },
  icon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  label: { fontSize: 14, fontWeight: '600' },
  body: { fontSize: 12, marginTop: 2, lineHeight: 16 },
  statusWrap: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingTop: 2, maxWidth: 130 },
  status: { fontSize: 13, fontWeight: '600', textAlign: 'right' },
});
