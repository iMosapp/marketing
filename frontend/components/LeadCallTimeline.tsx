import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';
import { whenLabel } from './admin/LeadTimingControls';

const GOLD = '#C9A962';

const OUTCOME: Record<string, { label: string; color: string; icon: string }> = {
  claimed:   { label: 'Pressed 1, claimed and bridged', color: '#34C759', icon: 'checkmark-circle' },
  passed:    { label: 'Answered, passed', color: '#FF9500', icon: 'arrow-redo-outline' },
  late:      { label: 'Pressed 1 too late', color: '#FF9500', icon: 'time-outline' },
  answered:  { label: 'Answered, no keypress', color: '#FF9500', icon: 'ear-outline' },
  no_answer: { label: 'No answer', color: '#8E8E93', icon: 'call-outline' },
  ringing:   { label: 'Ringing', color: GOLD, icon: 'call' },
  no_phone:  { label: 'No phone on profile, skipped', color: '#FF3B30', icon: 'alert-circle-outline' },
  failed:    { label: 'Call failed', color: '#FF3B30', icon: 'close-circle-outline' },
};

const mmss = (s?: number | null) => s == null ? '' : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
const reasons = (r: string[] = []) => r.map(x => x === 'store_closed' ? 'store closed' : 'texting window').join(' + ');

export const LeadCallTimeline = ({ conversationId, colors }: { conversationId: string; colors: any }) => {
  const [data, setData] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/lead-sources/call-timeline/${conversationId}`);
      setData(res.data);
    } catch (e: any) {
      if ([403, 404].includes(e?.response?.status)) setHidden(true);
    }
  }, [conversationId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!data?.job || data.job.status !== 'active') return;
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [data?.job?.status, load]);

  if (hidden || !data || (!data.job && !data.plan)) return null;
  const job = data.job;
  const plan = data.plan || {};

  let title = 'Lead routing';
  let sub = '';
  let tone = GOLD;
  if (!job) {
    title = plan.jessi_on ? 'Text only · Jessi answering replies' : 'Text only · reps answer replies';
    sub = data.intake?.sent_at ? `Intake text sent ${whenLabel(data.intake.sent_at)}` : data.intake?.scheduled_for ? `Intake text goes out ${whenLabel(data.intake.scheduled_for)}` : 'No intake text';
  } else if (job.status === 'claimed') {
    title = `Claimed by ${job.claimed_by_name || 'a rep'} in ${mmss(job.time_to_claim_seconds)}`;
    sub = `${job.claimed_via === 'phone' ? 'Pressed 1 on the call' : 'Claimed in the app'} · attempt ${job.calls.filter((c: any) => c.outcome === 'claimed')[0]?.attempt || job.attempt_index || 1} of ${job.attempts.length}`;
    tone = '#34C759';
  } else if (job.status === 'handled') {
    title = 'Call ladder skipped';
    sub = 'A rep already texted this lead before the morning ring';
    tone = '#8E8E93';
  } else if (job.status === 'exhausted') {
    title = `Nobody claimed after ${job.attempts.length} attempt${job.attempts.length === 1 ? '' : 's'}`;
    sub = 'Everyone on the ladder got an Unclaimed lead push';
    tone = '#FF3B30';
  } else if (job.deferred && job.attempt_index === 0) {
    title = `Call ladder rings ${whenLabel(job.next_attempt_at || job.deferred_until)}`;
    sub = `Held: ${reasons(job.deferred_reasons)}${plan.jessi_on ? ' · Jessi answering until then' : ''}`;
    tone = '#FF9500';
  } else {
    title = `Ringing attempt ${Math.min(job.attempt_index, job.attempts.length)} of ${job.attempts.length}`;
    sub = job.next_attempt_at && job.attempt_index < job.attempts.length ? `Next attempt ${whenLabel(job.next_attempt_at)}` : 'Waiting for a rep to press 1';
  }

  const rows: { at: string | null; icon: string; color: string; text: string }[] = [];
  rows.push({ at: data.received_at, icon: 'download-outline', color: colors.textSecondary, text: `Lead received${data.is_test ? ' (test)' : ''}` });
  if (data.intake?.sent_at) rows.push({ at: data.intake.sent_at, icon: 'chatbubble-ellipses-outline', color: '#34C759', text: 'Intake text sent' });
  else if (data.intake?.scheduled_for) rows.push({ at: data.intake.scheduled_for, icon: 'chatbubble-ellipses-outline', color: '#FF9500', text: 'Intake text scheduled (texting window)' });
  if (job?.was_deferred && job.deferred_until) rows.push({ at: job.deferred_until, icon: 'moon-outline', color: '#FF9500', text: `Ladder ${job.deferred ? 'held' : 'was held'} until opening (${reasons(job.deferred_reasons)})` });
  (job?.calls || []).forEach((c: any) => {
    const o = OUTCOME[c.outcome] || OUTCOME.ringing;
    rows.push({ at: c.at, icon: o.icon, color: o.color, text: `Attempt ${c.attempt} · ${c.name} · ${o.label}${c.error ? ` (${c.error})` : ''}` });
  });
  if (job?.claimed_at) rows.push({ at: job.claimed_at, icon: 'trophy-outline', color: '#34C759', text: `${job.claimed_by_name || 'Rep'} claimed the lead (${job.claimed_via === 'phone' ? 'phone' : 'app'})` });
  if (job?.exhausted_at && job.status === 'exhausted') rows.push({ at: job.exhausted_at, icon: 'alert-circle-outline', color: '#FF3B30', text: 'Ladder exhausted, team alerted' });
  if (data.first_human_reply_at) rows.push({ at: data.first_human_reply_at, icon: 'person-outline', color: '#34C759', text: 'First human reply' });
  rows.sort((a, b) => new Date(a.at || 0).getTime() - new Date(b.at || 0).getTime());

  return (
    <View style={{ marginHorizontal: 12, marginTop: 6, marginBottom: 4, borderRadius: 14, borderWidth: 1, borderColor: tone + '55', backgroundColor: colors.card || colors.surface, overflow: 'hidden' }} testID="lead-call-timeline" dataSet={{ testid: 'lead-call-timeline' } as any}>
      <TouchableOpacity onPress={() => setOpen(o => !o)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12 }} testID="lead-call-timeline-toggle" dataSet={{ testid: 'lead-call-timeline-toggle' } as any}>
        <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: tone + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name={job ? 'call' : 'chatbubbles-outline'} size={16} color={tone} />
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{title}</Text>
          {sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }} numberOfLines={2}>{sub}</Text> : null}
        </View>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
      </TouchableOpacity>
      {open && (
        <View style={{ paddingHorizontal: 12, paddingBottom: 12, gap: 8 }} testID="lead-call-timeline-rows" dataSet={{ testid: 'lead-call-timeline-rows' } as any}>
          {rows.map((r, i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
              <Text style={{ width: 62, fontSize: 11, color: colors.textSecondary, marginTop: 2 }}>{whenLabel(r.at)}</Text>
              <Ionicons name={r.icon as any} size={14} color={r.color} style={{ marginTop: 1 }} />
              <Text style={{ flex: 1, fontSize: 12, color: colors.text, lineHeight: 17 }}>{r.text}</Text>
            </View>
          ))}
          {data.sms_consent?.opted_in ? (
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 2 }}>Texting consent: opted in via {data.sms_consent.source === 'website_form' ? 'website form' : data.sms_consent.source} {whenLabel(data.sms_consent.at)}</Text>
          ) : null}
        </View>
      )}
    </View>
  );
};
