import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, GREEN, RED, tid } from '../scripts/shared';

type Row = { live_id: string; user_name?: string; mode: string; voice: string; status: string; started_at: string; seconds: number; cost_usd: number; close_reason?: string; turns: number; delegations: number; tools: string[] };
type Stats = Record<string, { sessions: number; minutes: number; cost_usd: number; reps: number }> & { open?: number };

const when = (iso: string) => { const d = new Date(iso); return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} ${d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`; };
const mins = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

// Recent live conversations with minutes and cost, plus one detail sheet with the transcript and what the brain did.
export const SessionsList = ({ refreshKey }: { refreshKey: number }) => {
  const { colors } = useThemeStore();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  useEffect(() => {
    api.get('/live-voice/admin/sessions?limit=25').then(r => { setRows(r.data.sessions || []); setStats(r.data.stats || null); }).catch(() => setRows([]));
  }, [refreshKey]);
  const openDetail = async (id: string) => { try { setDetail({ loading: true }); const r = await api.get(`/live-voice/admin/sessions/${id}`); setDetail(r.data); } catch { setDetail(null); } };
  const Stat = ({ k, label }: { k: string; label: string }) => {
    const s = stats?.[k] as any;
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, borderRadius: 12, padding: 10, borderWidth: 1, borderColor: colors.border }} {...tid(`voice-stat-${k}`)}>
        <Text style={{ fontSize: 10, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>{label}</Text>
        <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, marginTop: 3 }}>{s ? `${s.minutes} min` : '-'}</Text>
        <Text style={{ fontSize: 11, color: GOLD, fontWeight: '700' }}>{s ? `$${s.cost_usd.toFixed(2)} · ${s.sessions} talks` : ''}</Text>
      </View>
    );
  };
  return (
    <View {...tid('voice-sessions')}>
      <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
        <Stat k="today" label="TODAY" /><Stat k="week" label="7 DAYS" /><Stat k="month" label="30 DAYS" />
      </View>
      {rows === null ? <ActivityIndicator color={GOLD} /> : rows.length === 0 ? (
        <Text style={{ color: colors.textSecondary, fontSize: 13, textAlign: 'center', paddingVertical: 12 }} {...tid('voice-sessions-empty')}>No conversations yet. Audition her above and it shows up here.</Text>
      ) : rows.map(r => (
        <TouchableOpacity key={r.live_id} onPress={() => openDetail(r.live_id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`voice-session-${r.live_id}`)}>
          <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: r.mode === 'lab' ? `${GOLD}22` : `${GREEN}22`, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={r.mode === 'lab' ? 'flask' : 'mic'} size={15} color={r.mode === 'lab' ? GOLD : GREEN} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>{r.user_name || 'Someone'} · {r.voice}{r.status === 'open' ? ' · live now' : ''}</Text>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }}>{when(r.started_at)} · {r.turns} turns · {r.delegations} tool{r.delegations === 1 ? '' : 's'}{r.tools.length ? ` (${Array.from(new Set(r.tools)).join(', ')})` : ''}</Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>{mins(r.seconds)}</Text>
            <Text style={{ fontSize: 11, color: GOLD, fontWeight: '700' }}>${r.cost_usd.toFixed(2)}</Text>
          </View>
        </TouchableOpacity>
      ))}
      <Modal visible={!!detail} animationType="slide" onRequestClose={() => setDetail(null)}>
        <View style={{ flex: 1, backgroundColor: colors.bg }} {...tid('voice-session-detail')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }}>{detail?.user_name || 'Conversation'}{detail?.voice ? ` · ${detail.voice}` : ''}</Text>
            <TouchableOpacity onPress={() => setDetail(null)} hitSlop={10} {...tid('voice-session-detail-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
          </View>
          {detail?.loading ? <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} /> : (
            <ScrollView contentContainerStyle={{ padding: 16, gap: 8, paddingBottom: 50 }}>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{detail?.started_at ? when(detail.started_at) : ''} · {mins(detail?.seconds || 0)} · ${(detail?.cost_usd || 0).toFixed(2)} · {detail?.close_reason || detail?.status}</Text>
              {(detail?.transcript || []).map((t: any, i: number) => (
                <View key={i} style={{ alignSelf: t.role === 'rep' ? 'flex-end' : 'flex-start', maxWidth: '88%', backgroundColor: t.role === 'rep' ? colors.card : `${GOLD}1F`, borderRadius: 12, padding: 10, borderWidth: 1, borderColor: t.role === 'rep' ? colors.border : `${GOLD}40` }}>
                  <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{t.text}</Text>
                </View>
              ))}
              {(detail?.delegation_log || []).length > 0 && <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginTop: 10 }}>WHAT THE BRAIN DID</Text>}
              {(detail?.delegation_log || []).map((d: any, i: number) => (
                <View key={i} style={{ backgroundColor: colors.card, borderRadius: 12, padding: 10, borderWidth: 1, borderColor: colors.border }}>
                  <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{d.tool} · {d.ms} ms</Text>
                  {!!d.args && Object.keys(d.args).length > 0 && <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }}>{JSON.stringify(d.args)}</Text>}
                  <Text style={{ fontSize: 13, color: colors.text, marginTop: 4, lineHeight: 18 }}>{d.result}</Text>
                </View>
              ))}
              {detail && !detail.loading && (detail.transcript || []).length === 0 && <Text style={{ color: RED, fontSize: 12 }}>No transcript was saved for this session.</Text>}
            </ScrollView>
          )}
        </View>
      </Modal>
    </View>
  );
};
