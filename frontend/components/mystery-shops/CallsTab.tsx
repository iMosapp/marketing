import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { CallRecordingPlayer } from '../CallRecordingPlayer';
import { CriteriaChecklist } from '../scorecards/CriteriaChecklist';
import { ScoreRing } from '../scorecards/ScoreRing';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { Sheet, Label, StatusChip, GoldButton, ChannelPill, deptLabel, deptsOfClient, perMonthText, fmtWhen, monthLabel, shiftMonth, scoreColor, replyDur, minutesSince, isTextLive, isThread, channelIcon, channelWord, channelLabel, GOLD, RED, GREEN, tid, type ShopCall, type Client } from './shared';
import { makeT, fmtWhenL, type Lang } from './i18n';

type Props = { client: Client; colors: any; month: string; onMonth: (m: string) => void; refreshKey: number; onChanged: () => void };

export const CallsTab = ({ client, colors, month, onMonth, refreshKey, onChanged }: Props) => {
  const { showToast } = useToast();
  const depts = deptsOfClient(client);
  const [calls, setCalls] = useState<ShopCall[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);

  const load = async () => { try { const r = await api.get(`/shop-clients/${client.id}/calls`, { params: { month } }); setCalls(r.data.calls); } catch { setCalls([]); } };
  useEffect(() => { load(); }, [client.id, month, refreshKey]);
  // phone shops move fast (4s); a text thread can sit for hours waiting on the rep, so poll gently
  useEffect(() => { const live = (calls || []).filter(c => ['dialing', 'live', 'ending', 'grading'].includes(c.status)); if (!live.length) return; const t = setInterval(load, live.some(c => !isThread(c)) ? 4000 : 15000); return () => clearInterval(t); }, [calls]);

  const plan = async () => {
    setPlanning(true);
    try { const r = await api.post(`/shop-clients/${client.id}/plan-month`, { month }); const { text: tc, ...c } = (r.data.created || {}) as Record<string, any>; const n = Object.values(c).reduce((s: number, x: any) => s + (x || 0), 0) + Object.values(tc || {}).reduce((s: number, x: any) => s + (x || 0), 0); showToast(n ? `Scheduled ${perMonthText(c, ' + ', depts)} shops${tc ? ` + ${perMonthText(tc, ' + ', depts)} by text` : ''}` : 'This month is already fully scheduled', 'success'); load(); onChanged(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not schedule', 'error'); }
    finally { setPlanning(false); }
  };
  const cancel = (c: ShopCall) => showConfirm('Remove this shop?', `${c.target_name} will not get this challenge. The planner can fill the slot again.`, async () => {
    try { await api.delete(`/shop-clients/calls/${c.id}`); load(); onChanged(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, 'Remove');
  const retry = async (c: ShopCall) => { try { await api.post(`/shop-clients/calls/${c.id}/retry`); showToast(c.channel === 'text' ? `Texting ${c.target_name.split(' ')[0]} now` : c.channel === 'email' ? `Emailing ${c.target_name.split(' ')[0]} now` : `Calling ${c.target_name.split(' ')[0]} now`, 'success'); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not retry', 'error'); } };
  const endText = (c: ShopCall) => showConfirm('End this text shop?', `${c.target_name.split(' ')[0]} gets no more texts from the shopper and the thread is graded on what happened so far${c.text?.replies ? '' : ' (no reply yet = 0%)'}.`, async () => {
    try { await api.post(`/shop-clients/calls/${c.id}/end`); showToast('Grading the thread', 'success'); load(); onChanged(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not end it', 'error'); }
  }, undefined, 'End & grade');
  const textLine = (c: ShopCall) => {
    if (!isThread(c)) return '';
    const t = c.text;
    if (isTextLive(c)) return t?.waiting_since ? ` · waiting on ${c.target_name.split(' ')[0]} for ${minutesSince(t.waiting_since)} min` : ' · shopper is replying';
    if (c.status === 'completed') return t?.first_reply_s == null ? ' · never replied' : ` · first reply ${replyDur(t.first_reply_s)} · ${t.replies} ${t.replies === 1 ? 'reply' : 'replies'}`;
    return '';
  };

  const done = (calls || []).filter(c => c.status === 'completed');
  const upcoming = (calls || []).filter(c => ['scheduled', 'dialing', 'live', 'ending', 'grading'].includes(c.status)).sort((a, b) => (a.scheduled_for || '').localeCompare(b.scheduled_for || ''));
  const other = (calls || []).filter(c => !done.includes(c) && !upcoming.includes(c) && c.status !== 'canceled');

  const Row = ({ c }: { c: ShopCall }) => (
    <TouchableOpacity onPress={() => setOpen(c.id)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 6 }} {...tid(`shop-call-${c.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}><Ionicons name={channelIcon(c)} size={13} color={GOLD} {...tid(`shop-call-${channelWord(c)}-${c.id}`)} /> {c.target_name} <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· {channelLabel(c)} · {c.department_label || deptLabel(c.department, depts)}</Text></Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={1}>{c.script_title}{c.persona_name ? ` · ${c.customer_noun || client.customer_noun || 'shopper'} ${c.persona_name.split(' ')[0]}` : ''}</Text>
        </View>
        {c.status === 'completed' ? <Text style={{ fontSize: 20, fontWeight: '800', color: scoreColor(c.score_pct) }} {...tid(`shop-call-score-${c.id}`)}>{c.score_pct != null ? `${c.score_pct}%` : '–'}</Text> : <StatusChip status={c.status} colors={colors} channel={c.channel} />}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="time-outline" size={12} color={colors.textSecondary} />
        <Text style={{ fontSize: 12, color: colors.textSecondary, flex: 1 }} {...tid(`shop-call-line-${c.id}`)}>{c.status === 'completed' ? fmtWhen(c.ended_at || c.started_at) : c.status === 'scheduled' ? `Planned ${fmtWhen(c.scheduled_for)}` : fmtWhen(c.started_at || c.scheduled_for)}{c.attempts > 1 ? ` · ${c.attempts} tries` : ''}{c.fail_reason && c.status !== 'completed' ? ` · ${c.fail_reason}` : ''}{textLine(c)}</Text>
        {isTextLive(c) && <TouchableOpacity onPress={() => endText(c)} hitSlop={8} {...tid(`shop-call-end-${c.id}`)}><Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>End & grade</Text></TouchableOpacity>}
        {c.status === 'scheduled' && <TouchableOpacity onPress={() => cancel(c)} hitSlop={8} {...tid(`shop-call-cancel-${c.id}`)}><Ionicons name="close-circle-outline" size={18} color={colors.textSecondary} /></TouchableOpacity>}
        {(c.status === 'unreachable' || c.status === 'failed') && <TouchableOpacity onPress={() => retry(c)} hitSlop={8} {...tid(`shop-call-retry-${c.id}`)}><Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>Try again</Text></TouchableOpacity>}
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={{ gap: 16 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <TouchableOpacity onPress={() => onMonth(shiftMonth(month, -1))} hitSlop={8} {...tid('calls-month-prev')}><Ionicons name="chevron-back" size={22} color={GOLD} /></TouchableOpacity>
        <Text style={{ flex: 1, textAlign: 'center', fontSize: 15, fontWeight: '800', color: colors.text }} {...tid('calls-month-label')}>{monthLabel(month)}</Text>
        <TouchableOpacity onPress={() => onMonth(shiftMonth(month, 1))} hitSlop={8} {...tid('calls-month-next')}><Ionicons name="chevron-forward" size={22} color={GOLD} /></TouchableOpacity>
      </View>
      {!client.demo && <GoldButton label={`Schedule the rest of ${monthLabel(month).split(' ')[0]} (${perMonthText(client.plan.per_month, ' + ', depts)}${Object.values(client.plan.text_per_month || {}).some(n => n > 0) ? ` + ${perMonthText(client.plan.text_per_month, ' + ', depts)} by text` : ''})`} onPress={plan} busy={planning} icon="calendar" testID="calls-plan-month" outline />}
      {calls === null ? <ActivityIndicator color={GOLD} /> : done.length + upcoming.length + other.length === 0 ? <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20 }} {...tid('calls-empty')}>{client.demo ? 'No quick shops this month yet. Tap Shop anyone right now, or Shop now on someone under People.' : 'No shops this month yet. Add people, then schedule the month or tap Shop now on someone.'}</Text> : (
        <>
          {upcoming.length > 0 && <View style={{ gap: 8 }}><Label t={`COMING UP · ${upcoming.length}`} colors={colors} />{upcoming.map(c => <Row key={c.id} c={c} />)}</View>}
          {done.length > 0 && <View style={{ gap: 8 }}><Label t={`COMPLETED · ${done.length}`} colors={colors} />{done.map(c => <Row key={c.id} c={c} />)}</View>}
          {other.length > 0 && <View style={{ gap: 8 }}><Label t={`COULD NOT REACH · ${other.length}`} colors={colors} />{other.map(c => <Row key={c.id} c={c} />)}</View>}
        </>
      )}
      <CallDetailSheet id={open} onClose={() => setOpen(null)} colors={colors} />
    </View>
  );
};

export const CallDetailSheet = ({ id, onClose, colors, publicData, lang = 'en' }: { id: string | null; onClose: () => void; colors: any; publicData?: any; lang?: Lang }) => {
  const { showToast } = useToast();
  const tr = makeT(lang);
  const [d, setD] = useState<any>(null);
  useEffect(() => {
    if (!id) { setD(null); return; }
    if (publicData) { setD(publicData); return; }
    api.get(`/shop-clients/calls/${id}`).then(r => setD(r.data)).catch(() => setD({ error: true }));
  }, [id, publicData]);
  const ev = d?.evaluation || (d?.results ? d : null);
  const isText = isThread(d || {});
  const isEmail = d?.channel === 'email';
  const who = String(d?.customer_noun || (lang === 'nl' ? 'beller' : 'shopper'));
  const turns = d?.transcript_turns || (d?.transcript ? String(d.transcript).split('\n').filter(Boolean).map((l: string) => ({ role: l.startsWith('REP:') ? 'rep' : 'customer', text: l.replace(/^(REP|CUSTOMER):\s*/, '') })) : []);
  const speed = isText && d?.text ? (isTextLive(d) && d.text.first_reply_s == null ? `${d.status === 'live' ? 'Waiting on' : 'Wrapping up with'} ${(d.target_name || '').split(' ')[0]}${d.text.waiting_since ? ` · ${minutesSince(d.text.waiting_since)} min` : ''}` : d.text.first_reply_s == null ? tr('tx.noreply') : `${tr('tx.first', { d: replyDur(d.text.first_reply_s, lang) })}${d.text.max_reply_s != null && d.text.replies > 1 ? ` · ${tr('tx.slowest', { d: replyDur(d.text.max_reply_s, lang) })}` : ''} · ${tr('tx.replies', { n: d.text.replies })}`) : '';
  return (
    <Sheet visible={!!id} onClose={onClose} title={d?.target_name ? `${channelLabel(d, lang)} · ${d.target_name}` : tr('call.title')} colors={colors} testID="shop-call-detail">
      {!d ? <ActivityIndicator color={GOLD} /> : d.error ? <Text style={{ color: RED }}>{tr('call.load_error')}</Text> : (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
            <ScoreRing pct={d.score_pct} size={72} colors={colors} label={d.score_pct != null ? tr('call.score') : ''} />
            <View style={{ flex: 1, gap: 4 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <ChannelPill c={d} lang={lang} testID={isEmail ? 'shop-call-email-badge' : isText ? 'shop-call-text-badge' : 'shop-call-phone-badge'} />
                <StatusChip status={d.status} colors={colors} lang={lang} channel={d.channel} />
              </View>
              {!!d.script_title && <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }} {...tid('shop-call-script')}>{d.script_title}</Text>}
              {!!speed && <Text style={{ fontSize: 12.5, fontWeight: '700', color: isTextLive(d) && d.text?.first_reply_s == null ? GOLD : d.text?.first_reply_s == null ? RED : d.text.first_reply_s <= (isEmail ? 1800 : 300) ? GREEN : GOLD }} {...tid('shop-call-speed')}>{speed}</Text>}
              <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{fmtWhenL(d.ended_at || d.started_at || d.scheduled_for, lang)}{d.persona_name || d.persona?.name ? ` · ${who} ${(d.persona_name || d.persona?.name)}` : ''}{d.attempts > 1 ? ` · ${tr('call.tries', { n: d.attempts })}` : ''}</Text>
              {ev?.scorecard_name && <Text style={{ fontSize: 12, color: colors.textSecondary }}>{tr('call.graded_with', { name: ev.scorecard_name })}{d.adherence_pct != null ? ` · ${tr('call.script', { v: d.adherence_pct })}` : ''}</Text>}
              {!!d.fail_reason && d.status !== 'completed' && <Text style={{ fontSize: 12.5, color: RED }}>{d.fail_reason}</Text>}
            </View>
          </View>
          {!!d.curveballs?.length && <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{tr('call.curveballs', { items: d.curveballs.join('; ') })}</Text>}
          {!!d.score_url && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 10, borderWidth: 1, borderColor: colors.border }} {...tid('shop-call-score-link')}>
              <Ionicons name={d.score_sms_status && d.score_sms_status !== 'failed' ? 'chatbubble-ellipses' : 'link'} size={16} color={d.score_sms_status === 'failed' ? RED : GOLD} />
              <Text style={{ flex: 1, fontSize: 12.5, color: colors.textSecondary }} {...tid('shop-call-sms-status')}>{d.score_sms_status === 'failed' ? 'Scorecard text failed' : d.score_sms_status ? `Scorecard texted to ${d.target_name?.split(' ')[0]}` : 'Scorecard link'}{d.score_views ? ` · opened ${d.score_views}x` : ''}</Text>
              <TouchableOpacity onPress={async () => { await Clipboard.setStringAsync(d.score_url); showToast('Scorecard link copied', 'success'); }} hitSlop={8} {...tid('shop-call-score-copy')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Copy link</Text></TouchableOpacity>
            </View>
          )}
          {!!d.recording_url && <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 10, borderWidth: 1, borderColor: colors.border }} {...tid('shop-call-recording')}><CallRecordingPlayer url={resolvePhotoUrl(d.recording_url) || d.recording_url} tint={GOLD} textColor={colors.text} subColor={colors.textSecondary} trackColor={colors.border} /></View>}
          {ev && (
            <>
              {!!ev.summary && <Text style={{ fontSize: 14.5, color: colors.text, lineHeight: 21 }} {...tid('shop-call-summary')}>{ev.summary}</Text>}
              {ev.critical_misses?.length > 0 && <View style={{ backgroundColor: RED + '14', borderLeftWidth: 3, borderLeftColor: RED, borderRadius: 10, padding: 10, gap: 4 }}><Label t={tr('call.crit')} colors={{ textSecondary: RED }} />{ev.critical_misses.map((m: any, i: number) => <Text key={i} style={{ fontSize: 13.5, color: colors.text }}>• {typeof m === 'string' ? m : m.text}</Text>)}</View>}
              {ev.coaching?.length > 0 && <View style={{ gap: 4 }}><Label t={tr('call.coaching')} colors={colors} />{ev.coaching.map((t: string, i: number) => <Text key={i} style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>• {t}</Text>)}</View>}
              {ev.wins?.length > 0 && <View style={{ gap: 4 }}><Label t={tr('call.wins')} colors={{ textSecondary: GREEN }} />{ev.wins.map((t: string, i: number) => <Text key={i} style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>• {t}</Text>)}</View>}
              {ev.results?.length > 0 && <View style={{ gap: 6 }}><Label t={tr('call.scorecard')} colors={colors} /><CriteriaChecklist results={ev.results} colors={colors} canManage={false} /></View>}
            </>
          )}
          {turns.length > 0 && (
            <View style={{ gap: 6 }}>
              <Label t={tr('call.transcript')} colors={colors} />
              {turns.map((t: any, i: number) => (
                <View key={i} style={{ flexDirection: 'row', justifyContent: t.role === 'rep' ? 'flex-end' : 'flex-start' }}>
                  <View style={{ maxWidth: '86%', backgroundColor: t.role === 'rep' ? GOLD : colors.card, borderRadius: 14, padding: 10, borderWidth: t.role === 'rep' ? 0 : 1, borderColor: colors.border }}>
                    <Text style={{ fontSize: 10, fontWeight: '800', color: t.role === 'rep' ? '#11111199' : colors.textSecondary, marginBottom: 2 }}>{t.role === 'rep' ? (d.target_name || tr('call.rep')).toUpperCase() : who.toUpperCase()}</Text>
                    <Text style={{ fontSize: 14, lineHeight: 19, color: t.role === 'rep' ? '#111' : colors.text }}>{t.text}</Text>
                    {isText && t.role === 'rep' && t.delay_s != null && <Text style={{ fontSize: 10.5, color: '#11111199', marginTop: 3, textAlign: 'right' }}>{t.delay_s < 60 ? tr('tx.within') : tr('tx.after', { d: replyDur(t.delay_s, lang) })}</Text>}
                  </View>
                </View>
              ))}
            </View>
          )}
        </>
      )}
    </Sheet>
  );
};
