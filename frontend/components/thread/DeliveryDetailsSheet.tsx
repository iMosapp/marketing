import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ActivityIndicator, Platform, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { SheetGrabber } from '../common/SheetGrabber';

type Delivery = {
  id: string; status?: string; twilio_status?: string; twilio_sid?: string | null;
  error_code?: string | null; error_message?: string | null; sent_at?: string; status_updated_at?: string;
  has_media: boolean; media_kinds: string[]; has_link: boolean; live_checked: boolean;
  explanation: { title: string; detail: string; action?: string | null; tone: 'good' | 'bad' | 'warn' | 'muted'; code?: string | null };
  can_resend_text: boolean; resent_as?: string | null;
};

type Props = { messageId: string | null; colors: any; onClose: () => void; onResent?: () => void };

const TONE: Record<string, { color: string; icon: string }> = {
  good: { color: '#34C759', icon: 'checkmark-done-circle' },
  bad: { color: '#FF453A', icon: 'alert-circle' },
  warn: { color: '#FF9F0A', icon: 'time' },
  muted: { color: '#8E8E93', icon: 'paper-plane' },
};

export const DeliveryDetailsSheet = ({ messageId, colors, onClose, onResent }: Props) => {
  const [data, setData] = useState<Delivery | null>(null);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (!messageId) { setData(null); return; }
    setLoading(true);
    api.get(`/messages/${messageId}/delivery`)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [messageId]);

  const resend = async () => {
    if (!messageId) return;
    setResending(true);
    try {
      await api.post(`/messages/${messageId}/resend-text`);
      onResent?.();
      onClose();
    } catch (e: any) {
      showSimpleAlert('Could not resend', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setResending(false);
    }
  };

  const copySid = async () => {
    if (!data?.twilio_sid) return;
    await Clipboard.setStringAsync(data.twilio_sid);
    showSimpleAlert('Copied', 'Twilio message ID copied.');
  };

  const tone = TONE[data?.explanation?.tone || 'muted'];
  const when = (v?: string) => (v ? format(new Date(v), 'MMM d, h:mm a') : '—');

  return (
    <Modal visible={!!messageId} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={s.overlay} activeOpacity={1} onPress={onClose} data-testid="delivery-sheet-overlay">
        <TouchableOpacity activeOpacity={1} style={[s.card, { backgroundColor: colors.card }]} data-testid="delivery-sheet">
          <SheetGrabber onClose={onClose} color={colors.border} style={{ marginTop: -6, marginBottom: 4 }} testID="delivery-sheet-grabber" />
          <View style={s.headRow}>
            <Text style={[s.title, { color: colors.text }]}>Delivery details</Text>
            <TouchableOpacity onPress={onClose} data-testid="delivery-sheet-close"><Ionicons name="close" size={22} color={colors.textSecondary} /></TouchableOpacity>
          </View>

          {loading || !data ? (
            <View style={{ paddingVertical: 30, alignItems: 'center' }}>
              {loading ? <ActivityIndicator color={colors.accent} /> : <Text style={{ color: colors.textSecondary }}>Couldn't load this message.</Text>}
            </View>
          ) : (
            <>
              <View style={[s.statusRow, { backgroundColor: `${tone.color}18`, borderColor: `${tone.color}55` }]} data-testid="delivery-status">
                <Ionicons name={tone.icon as any} size={22} color={tone.color} />
                <View style={{ flex: 1 }}>
                  <Text style={[s.statusTitle, { color: tone.color }]}>{data.explanation.title}{data.explanation.code ? `  ·  code ${data.explanation.code}` : ''}</Text>
                  <Text style={[s.statusDetail, { color: colors.text }]}>{data.explanation.detail}</Text>
                  {data.explanation.action ? <Text style={[s.statusAction, { color: colors.textSecondary }]}>What to do: {data.explanation.action}</Text> : null}
                </View>
              </View>

              <View style={s.facts}>
                <Fact label="Sent" value={when(data.sent_at)} colors={colors} />
                <Fact label="Carrier update" value={data.status_updated_at ? when(data.status_updated_at) : 'none yet'} colors={colors} />
                <Fact label="Twilio status" value={data.twilio_status || data.status || '—'} colors={colors} />
                <Fact label="Attachment" value={data.has_media ? data.media_kinds.join(', ') : 'none'} colors={colors} />
                {data.error_message ? <Fact label="Carrier said" value={data.error_message} colors={colors} /> : null}
                {data.live_checked ? <Text style={[s.live, { color: colors.textTertiary }]}>Checked with Twilio just now</Text> : null}
              </View>

              {data.resent_as ? (
                <Text style={[s.live, { color: '#34C759', marginBottom: 6 }]} data-testid="delivery-resent-note">Already resent as plain text.</Text>
              ) : null}

              <View style={s.btnRow}>
                {data.can_resend_text && (
                  <TouchableOpacity style={[s.btn, { backgroundColor: colors.accent }]} onPress={resend} disabled={resending} data-testid="delivery-resend-text-btn">
                    {resending ? <ActivityIndicator size="small" color="#000" /> : (<><Ionicons name="refresh" size={16} color="#000" /><Text style={s.btnText}>Resend as plain text</Text></>)}
                  </TouchableOpacity>
                )}
                {data.twilio_sid && !data.twilio_sid.startsWith('MOCK') ? (
                  <TouchableOpacity style={[s.btn, s.btnGhost, { borderColor: colors.border }]} onPress={copySid} data-testid="delivery-copy-sid-btn">
                    <Ionicons name="copy-outline" size={15} color={colors.textSecondary} />
                    <Text style={[s.btnText, { color: colors.textSecondary }]}>Copy Twilio ID</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            </>
          )}
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
};

const Fact = ({ label, value, colors }: { label: string; value: string; colors: any }) => (
  <View style={s.factRow}>
    <Text style={[s.factLabel, { color: colors.textTertiary }]}>{label}</Text>
    <Text style={[s.factValue, { color: colors.text }]} numberOfLines={3}>{value}</Text>
  </View>
);

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  card: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, paddingBottom: Platform.OS === 'ios' ? 34 : 22 },
  headRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  title: { fontSize: 17, fontWeight: '700' },
  statusRow: { flexDirection: 'row', gap: 12, alignItems: 'flex-start', borderRadius: 14, borderWidth: 1, padding: 14, marginBottom: 14 },
  statusTitle: { fontSize: 15, fontWeight: '700', marginBottom: 4 },
  statusDetail: { fontSize: 14, lineHeight: 19 },
  statusAction: { fontSize: 13, lineHeight: 18, marginTop: 6, fontWeight: '600' },
  facts: { gap: 8, marginBottom: 14 },
  factRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  factLabel: { fontSize: 13, fontWeight: '600' },
  factValue: { fontSize: 13, flex: 1, textAlign: 'right' },
  live: { fontSize: 12, marginTop: 2 },
  btnRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 12 },
  btnGhost: { backgroundColor: 'transparent', borderWidth: 1 },
  btnText: { fontSize: 14, fontWeight: '700', color: '#000' },
});
