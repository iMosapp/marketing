import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../common/Toast';
import { ScoreRing } from '../../scorecards/ScoreRing';
import { CallDetailSheet } from '../CallsTab';
import { Sheet, Label, Bar, GoldButton, fmtWhen, fmtPhone, scoreColor, channelIcon, GOLD, GREEN, RED, AMBER, tid } from '../shared';
import { CHANNELS, LEAD_STATUS, PART_LABEL, isOpen, untilText, minsText, firstMinutes, channelTone, type LeadShop } from './shared';

type Props = { id: string | null; onClose: () => void; colors: any; onChanged: () => void };

const IdentityCard = ({ shop, colors, onDelivered }: { shop: LeadShop; colors: any; onDelivered: () => void }) => {
  const { showToast } = useToast();
  const c = shop.identity_card!;
  const rows: [string, string][] = [['Name', c.name], ['Cell', fmtPhone(c.phone)], ['Email', c.email], ['Interested in', c.offering || ''], ['Message', c.message]].filter(r => r[1]) as [string, string][];
  const copy = async (v: string, l: string) => { await Clipboard.setStringAsync(v); showToast(`${l} copied`, 'success'); };
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: AMBER + '88', padding: 12, gap: 8 }} {...tid('lead-identity-card')}>
      <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Type this into the store's website form</Text>
      {rows.map(([l, v]) => (
        <TouchableOpacity key={l} onPress={() => copy(v, l)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`lead-identity-${l.toLowerCase().replace(/\s+/g, '-')}`)}>
          <Text style={{ width: 92, fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{l.toUpperCase()}</Text>
          <Text style={{ flex: 1, fontSize: 13.5, color: colors.text }} selectable>{v}</Text>
          <Ionicons name="copy-outline" size={15} color={GOLD} />
        </TouchableOpacity>
      ))}
      <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{c.note}</Text>
      <GoldButton label="I submitted the form, start the clock" onPress={onDelivered} icon="play" testID="lead-delivered" />
    </View>
  );
};

const ScoreBlock = ({ shop, colors }: { shop: LeadShop; colors: any }) => {
  const sc = shop.score!;
  return (
    <View style={{ gap: 12 }} {...tid('lead-score')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
        <ScoreRing pct={sc.overall} size={76} colors={colors} label="overall" testID="lead-score-ring" />
        <View style={{ flex: 1, gap: 3 }}>
          <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Process {sc.process}%{sc.quality != null ? ` · Conversations ${sc.quality}%` : ' · no conversation to grade'}</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{sc.no_contact ? 'Nobody contacted the lead.' : `${sc.day1_calls} call${sc.day1_calls === 1 ? '' : 's'} on day one · reached out on ${sc.contact_days} of ${sc.want_days} day${sc.want_days === 1 ? '' : 's'}`}</Text>
        </View>
      </View>
      {!!sc.summary && <Text style={{ fontSize: 14.5, color: colors.text, lineHeight: 21 }} {...tid('lead-score-summary')}>{sc.summary}</Text>}
      <View style={{ gap: 6 }}>
        {Object.entries(sc.parts).map(([k, v]) => (
          <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`lead-part-${k}`)}>
            <Text style={{ width: 118, fontSize: 12.5, fontWeight: '700', color: colors.text }}>{PART_LABEL[k] || k}</Text>
            <Bar pct={v} color={scoreColor(v)} colors={colors} />
            <Text style={{ width: 40, textAlign: 'right', fontSize: 12.5, fontWeight: '800', color: scoreColor(v) }}>{v}%</Text>
          </View>
        ))}
      </View>
      {!!sc.wins?.length && <View style={{ gap: 4 }}><Label t="WHAT WENT RIGHT" colors={{ textSecondary: GREEN }} />{sc.wins.map((t, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>• {t}</Text>)}</View>}
      {!!sc.coaching?.length && <View style={{ gap: 4 }}><Label t="FIX THIS" colors={colors} />{sc.coaching.map((t, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>• {t}</Text>)}</View>}
    </View>
  );
};

const ChannelRows = ({ shop, colors }: { shop: LeadShop; colors: any }) => (
  <View style={{ gap: 6 }} {...tid('lead-channels')}>
    {CHANNELS.map(c => {
      const required = shop.process.channels.includes(c.key); const m = firstMinutes(shop, c.key); const n = shop.counts?.[c.key] || 0; const tone = channelTone(shop, c.key);
      const pc = shop.score?.per_channel?.[c.key];
      return (
        <View key={c.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 10 }} {...tid(`lead-channel-${c.key}`)}>
          <Ionicons name={c.icon} size={16} color={required ? tone : colors.textSecondary} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>{c.label}{!required ? <Text style={{ fontWeight: '600', color: colors.textSecondary }}> · not promised</Text> : ''}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{m == null ? (shop.status === 'completed' ? (pc?.auto_reply_only ? 'Only an auto-reply, nobody wrote' : 'Never') : 'Nothing yet') : `First ${c.key === 'call' ? 'call' : c.key} after ${minsText(m)}`} · promised {(shop.process as any)[`first_${c.key}_min`]} min{n ? ` · ${n} touch${n === 1 ? '' : 'es'}` : ''}{pc && pc.count > pc.human_count && !pc.auto_reply_only ? ` · ${pc.count - pc.human_count} auto-reply` : ''}</Text>
          </View>
          {pc?.speed_pts != null && <Text style={{ fontSize: 15, fontWeight: '800', color: scoreColor(pc.speed_pts) }}>{pc.speed_pts}%</Text>}
        </View>
      );
    })}
  </View>
);

const ICON: Record<string, any> = { call: 'call', text: 'chatbubbles', email: 'mail', lead: 'paper-plane' };
const Timeline = ({ shop, colors }: { shop: LeadShop; colors: any }) => (
  <View style={{ gap: 6 }} {...tid('lead-timeline')}>
    <Label t="TIMELINE" colors={colors} />
    {shop.events.map((e, i) => (
      <View key={i} style={{ flexDirection: 'row', gap: 10, opacity: e.automated || e.kind.startsWith('late') ? 0.6 : 1 }} {...tid(`lead-event-${i}`)}>
        <Text style={{ width: 62, fontSize: 11.5, fontWeight: '800', color: GOLD, paddingTop: 2 }}>{e.since || fmtWhen(e.at)}</Text>
        <Ionicons name={e.kind === 'graded' ? 'ribbon' : ICON[e.channel] || 'ellipse'} size={14} color={e.kind === 'graded' ? GREEN : colors.textSecondary} style={{ paddingTop: 2 }} />
        <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }}>{e.summary}</Text>
      </View>
    ))}
  </View>
);

export const LeadShopDetailSheet = ({ id, onClose, colors, onChanged }: Props) => {
  const { showToast } = useToast();
  const [d, setD] = useState<LeadShop | null>(null);
  const [err, setErr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showAdf, setShowAdf] = useState(false);
  const [openCall, setOpenCall] = useState<string | null>(null);
  const load = () => api.get(`/lead-shops/${id}`).then(r => setD(r.data)).catch(() => setErr(true));
  useEffect(() => { setD(null); setErr(false); setShowAdf(false); if (id) load(); }, [id]);
  useEffect(() => { if (!d || !isOpen(d)) return; const t = setInterval(load, d.status === 'closing' ? 5000 : 30000); return () => clearInterval(t); }, [d?.status, id]);
  const act = async (fn: () => Promise<any>, ok: string) => { setBusy(true); try { await fn(); showToast(ok, 'success'); await load(); onChanged(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not do that', 'error'); } finally { setBusy(false); } };
  const delivered = () => act(() => api.post(`/lead-shops/${id}/delivered`), 'Clock started');
  const close = () => d && showConfirm('Close this lead shop now?', `The clock stops, any live text or email thread is graded on what happened so far, and ${d.persona.first}'s number goes back in the pool. Calls that come in later are logged as late.`, () => act(() => api.post(`/lead-shops/${id}/close`), 'Closing and grading'), undefined, 'Close & grade');
  const rescore = () => act(() => api.post(`/lead-shops/${id}/rescore`), 'Re-scored');
  const remove = () => d && showConfirm('Delete this lead shop?', 'The timeline and score are removed. Graded conversations are kept.', () => act(async () => { await api.delete(`/lead-shops/${id}`); onClose(); }, 'Deleted'), undefined, 'Delete');
  const st = d ? LEAD_STATUS[d.status] : null;
  return (
    <Sheet visible={!!id} onClose={onClose} title={d ? `${d.persona.name} · ${d.source_name}` : 'Lead shop'} colors={colors} testID="lead-detail">
      {err ? <Text style={{ color: RED }}>Could not load this lead shop.</Text> : !d || !st ? <ActivityIndicator color={GOLD} /> : (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, height: 24, borderRadius: 12, backgroundColor: st.color + '22' }} {...tid(`lead-detail-status-${d.status}`)}><Ionicons name={st.icon} size={12} color={st.color} /><Text style={{ fontSize: 11, fontWeight: '800', color: st.color }}>{st.label}{d.status === 'live' ? ` · ${untilText(d.expires_at)}` : ''}</Text></View>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{d.department} · {d.window_label} window · {d.method === 'adf' ? 'ADF to CRM' : 'web form'}</Text>
          </View>
          <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }} {...tid('lead-detail-persona')}>{d.persona.name} · {fmtPhone(d.persona.phone)} · {d.persona.email}{d.persona.offering ? `\nAsking about ${d.persona.offering}` : ''}{d.script_title ? `\n${d.script_title}` : ''}</Text>
          {d.started_at && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Lead landed {fmtWhen(d.started_at)}{d.closed_at ? ` · closed ${fmtWhen(d.closed_at)}` : d.expires_at ? ` · closes ${fmtWhen(d.expires_at)}` : ''}</Text>}
          {d.status === 'pending_delivery' && d.identity_card && <IdentityCard shop={d} colors={colors} onDelivered={delivered} />}
          {d.status === 'completed' && d.score && <ScoreBlock shop={d} colors={colors} />}
          {d.status === 'closing' && <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('lead-detail-grading')}>Grading the conversations, the score lands in a minute.</Text>}
          <ChannelRows shop={d} colors={colors} />
          {!!d.conversations?.length && (
            <View style={{ gap: 6 }}>
              <Label t={`CONVERSATIONS · ${d.conversations.length}`} colors={colors} />
              {d.conversations.map(c => (
                <TouchableOpacity key={c.id} onPress={() => setOpenCall(c.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 10 }} {...tid(`lead-convo-${c.id}`)}>
                  <Ionicons name={c.channel === 'call' ? 'call' : channelIcon(c)} size={16} color={GOLD} />
                  <View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>{c.channel === 'call' ? 'Call' : c.channel === 'email' ? 'Email thread' : 'Text thread'} <Text style={{ fontWeight: '600', color: colors.textSecondary }}>· {c.status}</Text></Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>{fmtWhen(c.started_at || c.scheduled_for)}{c.turns ? ` · ${c.turns} turns` : ''}</Text></View>
                  <Text style={{ fontSize: 16, fontWeight: '800', color: scoreColor(c.score_pct) }}>{c.score_pct != null ? `${c.score_pct}%` : '–'}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
          <Timeline shop={d} colors={colors} />
          {!!d.adf_preview && (
            <View style={{ gap: 6 }}>
              <TouchableOpacity onPress={() => setShowAdf(v => !v)} {...tid('lead-adf-toggle')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{showAdf ? 'Hide' : 'Show'} the lead as the CRM received it</Text></TouchableOpacity>
              {showAdf && <Text selectable style={{ fontSize: 10.5, color: colors.textSecondary, fontFamily: 'Courier', lineHeight: 14, backgroundColor: colors.card, borderRadius: 10, padding: 10 }} {...tid('lead-adf-preview')}>{d.adf_preview}</Text>}
            </View>
          )}
          {!!d.notes && <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Notes: {d.notes}</Text>}
          <View style={{ gap: 8 }}>
            {(d.status === 'live' || d.status === 'pending_delivery') && <GoldButton label="Close now & grade" onPress={close} busy={busy} outline icon="stop-circle-outline" testID="lead-close" />}
            {d.status === 'completed' && <GoldButton label="Re-score" onPress={rescore} busy={busy} outline icon="refresh" testID="lead-rescore" />}
            {d.status !== 'live' && d.status !== 'closing' && <GoldButton label="Delete" onPress={remove} busy={busy} outline color={RED} icon="trash-outline" testID="lead-delete" />}
          </View>
          <CallDetailSheet id={openCall} onClose={() => setOpenCall(null)} colors={colors} />
        </>
      )}
    </Sheet>
  );
};
