import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Image, RefreshControl } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api, { messagesAPI } from '../../services/api';
import { showAlert } from '../../services/alert';
import { CallRecordingPlayer } from '../CallRecordingPlayer';
import { GOLD, tid } from '../ui/tokens';
import { GreetingCard } from './GreetingSheet';

type Line = { phone: string; display: string; label: string; unheard: number; total: number };
export type Voicemail = {
  id: string; kind: 'voicemail' | 'missed'; from_phone: string; from_display: string; caller_name: string;
  contact_id?: string | null; contact_photo?: string | null; to_phone: string; to_display: string; line_label: string;
  duration: number; duration_display: string; transcript: string; transcript_status: string; play_url?: string | null;
  heard: boolean; created_at: string;
};

const timeAgo = (iso: string) => {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return 'now';
  if (d < 3600) return `${Math.floor(d / 60)}m`;
  if (d < 86400) return `${Math.floor(d / 3600)}h`;
  if (d < 7 * 86400) return `${Math.floor(d / 86400)}d`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

export const VoicemailInbox = ({ user, colors, active, onCall, onUnheard }: {
  user: any; colors: any; active: boolean; onCall: (phone: string) => void; onUnheard: (n: number) => void;
}) => {
  const router = useRouter();
  const [items, setItems] = useState<Voicemail[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [line, setLine] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const r = await api.get('/voicemails', { params: line ? { line } : {} });
      setItems(r.data?.items || []); setLines(r.data?.lines || []); onUnheard(r.data?.unheard ?? 0);
    } catch {}
    setLoading(false); setRefreshing(false);
  }, [line]);

  useEffect(() => { if (active) load(); }, [active, load]);

  const markHeard = async (v: Voicemail) => {
    if (v.heard) return;
    setItems(prev => prev.map(x => x.id === v.id ? { ...x, heard: true } : x));
    try { const r = await api.post(`/voicemails/${v.id}/heard`); onUnheard(r.data?.unheard ?? 0); } catch {}
  };
  const toggle = (v: Voicemail) => { const next = openId === v.id ? null : v.id; setOpenId(next); if (next) markHeard(v); };
  const remove = (v: Voicemail) => showAlert('Delete this voicemail?', `From ${v.caller_name}. This can't be undone.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: async () => {
      setItems(prev => prev.filter(x => x.id !== v.id)); setOpenId(null);
      try { const r = await api.delete(`/voicemails/${v.id}`); onUnheard(r.data?.unheard ?? 0); } catch {}
    } },
  ]);
  const text = async (v: Voicemail) => {
    try {
      if (v.contact_id) {
        const conv = await messagesAPI.createConversation(user._id, { contact_id: v.contact_id, contact_phone: v.from_phone });
        const cid = conv?._id || conv?.id;
        if (cid) { router.push(`/thread/${cid}` as any); return; }
      }
      router.push({ pathname: '/thread/new', params: { contact_name: v.caller_name, contact_phone: v.from_phone, is_new: 'true' } } as any);
    } catch { showAlert('Could not open a text thread', 'Try again from the contact.'); }
  };

  return (
    <View style={{ flex: 1, marginTop: 10 }} {...tid('voicemail-inbox')}>
      <GreetingCard user={user} colors={colors} />
      {lines.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 20, gap: 8, paddingBottom: 8 }} {...tid('voicemail-lines')}>
          {[{ phone: '', display: '', label: 'All lines', unheard: lines.reduce((a, l) => a + l.unheard, 0), total: 0 }, ...lines].map(l => {
            const on = line === l.phone;
            return (
              <TouchableOpacity key={l.phone || 'all'} onPress={() => setLine(l.phone)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 7, paddingHorizontal: 12, borderRadius: 16, backgroundColor: on ? GOLD : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`voicemail-line-${l.phone || 'all'}`)}>
                <Text style={{ fontSize: 13, fontWeight: '700', color: on ? '#0B0B0D' : colors.text }}>{l.label}{l.display ? ` · ${l.display}` : ''}</Text>
                {l.unheard > 0 ? <View style={{ minWidth: 18, height: 18, borderRadius: 9, paddingHorizontal: 5, backgroundColor: on ? '#0B0B0D' : GOLD, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 11, fontWeight: '800', color: on ? GOLD : '#0B0B0D' }}>{l.unheard}</Text></View> : null}
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      ) : null}

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={GOLD} />} {...tid('voicemail-list')}>
        {loading ? (
          <ActivityIndicator size="small" color={colors.textSecondary} style={{ marginTop: 40 }} />
        ) : items.length === 0 ? (
          <View style={{ alignItems: 'center', paddingTop: 40, paddingHorizontal: 24 }} {...tid('voicemail-empty')}>
            <Ionicons name="recording-outline" size={34} color={colors.textTertiary || colors.textSecondary} />
            <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 10 }}>No voicemails yet</Text>
            <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 4, textAlign: 'center', lineHeight: 20 }}>Calls to your line that you don't pick up land here, with the recording and a transcript.</Text>
          </View>
        ) : items.map((v, i) => {
          const open = openId === v.id;
          const missed = v.kind === 'missed';
          return (
            <View key={v.id} style={{ borderBottomWidth: 0.5, borderBottomColor: colors.border }} {...tid(`voicemail-row-${i}`)}>
              <TouchableOpacity onPress={() => toggle(v)} activeOpacity={0.6} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 12 }}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: missed ? '#FF3B3018' : `${GOLD}22`, alignItems: 'center', justifyContent: 'center', marginRight: 12, overflow: 'hidden' }}>
                  {v.contact_photo ? <Image source={{ uri: v.contact_photo }} style={{ width: 40, height: 40 }} /> : <Ionicons name={missed ? 'call-outline' : 'recording'} size={20} color={missed ? '#FF3B30' : GOLD} />}
                </View>
                <View style={{ flex: 1 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    {!v.heard ? <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: GOLD }} {...tid(`voicemail-unheard-${i}`)} /> : null}
                    <Text style={{ fontSize: 17, fontWeight: v.heard ? '500' : '800', color: colors.text, flexShrink: 1 }} numberOfLines={1}>{v.caller_name}</Text>
                  </View>
                  <Text style={{ fontSize: 13, color: missed ? '#FF3B30' : colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
                    {missed ? 'Missed · no message' : `Voicemail · ${v.duration_display}`}{'  ·  '}<Text style={{ color: colors.textSecondary }}>{v.line_label}</Text>
                  </Text>
                </View>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginLeft: 8 }}>{timeAgo(v.created_at)}</Text>
                <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textTertiary || colors.textSecondary} style={{ marginLeft: 6 }} />
              </TouchableOpacity>

              {open ? (
                <View style={{ paddingBottom: 14, gap: 12 }} {...tid(`voicemail-detail-${i}`)}>
                  {!missed ? (
                    <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12 }}>
                      {v.play_url ? <CallRecordingPlayer url={v.play_url} tint={GOLD} textColor={colors.text} subColor={colors.textSecondary} trackColor={colors.border} /> : null}
                      <Text style={{ fontSize: 15, lineHeight: 22, color: v.transcript ? colors.text : colors.textSecondary, marginTop: 10, fontStyle: v.transcript ? 'normal' : 'italic' }} {...tid(`voicemail-transcript-${i}`)}>
                        {v.transcript || (v.transcript_status === 'pending' ? 'Transcribing…' : 'No transcript for this one. Tap play to listen.')}
                      </Text>
                    </View>
                  ) : null}
                  <Text style={{ fontSize: 12, color: colors.textTertiary || colors.textSecondary }}>
                    {v.from_display} called {v.line_label.toLowerCase()} · {v.to_display} · {new Date(v.created_at).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 10 }}>
                    <TouchableOpacity onPress={() => onCall(v.from_phone)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 12, backgroundColor: '#34C759' }} {...tid(`voicemail-callback-${i}`)}>
                      <Ionicons name="call" size={16} color="#fff" /><Text style={{ color: '#fff', fontWeight: '700', fontSize: 14 }}>Call back</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => text(v)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 12, backgroundColor: '#007AFF' }} {...tid(`voicemail-text-${i}`)}>
                      <Ionicons name="chatbubble" size={16} color="#fff" /><Text style={{ color: '#fff', fontWeight: '700', fontSize: 14 }}>Text</Text>
                    </TouchableOpacity>
                    {v.contact_id ? (
                      <TouchableOpacity onPress={() => router.push(`/contact/${v.contact_id}` as any)} style={{ width: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid(`voicemail-contact-${i}`)}>
                        <Ionicons name="person" size={17} color={colors.text} />
                      </TouchableOpacity>
                    ) : null}
                    <TouchableOpacity onPress={() => remove(v)} style={{ width: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 12, backgroundColor: '#FF3B3018' }} {...tid(`voicemail-delete-${i}`)}>
                      <Ionicons name="trash-outline" size={17} color="#FF3B30" />
                    </TouchableOpacity>
                  </View>
                </View>
              ) : null}
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
};
