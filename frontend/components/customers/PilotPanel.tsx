import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import type { PilotAction } from './PilotSheet';
import { BillingModeNotice, conversionOn } from './BillingModeNotice';

const fmt = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const money = (n?: number) => (typeof n === 'number' ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '');

type Props = { orgId: string; row: any; colors: any; busy: boolean; act: (fn: () => Promise<any>, okTitle?: string) => Promise<any>; onAction: (a: PilotAction) => void };

/** Founder panel for a Founding Partner Pilot: clock, reminders, potential MRR, continue link, extend / end / resume. */
export function PilotPanel({ orgId, row, colors, busy, act, onAction }: Props) {
  const p = row.pilot_program || {};
  const c = row.customer || {};
  const mrr = row.mrr || {};
  const sendLink = () => act(async () => {
    const res = await api.post(`/customers/${orgId}/payment-link`, { send: true });
    showSimpleAlert('Continue link sent', `Text ${res.data.sent?.sms_sent ? 'sent' : 'not sent'} · email ${res.data.sent?.email_sent ? 'sent' : 'not sent'}.${res.data.first_charge_on ? ` First charge ${fmt(res.data.first_charge_on)}.` : ''}`);
    return res;
  });
  const copyLink = () => act(async () => {
    const res = await api.post(`/customers/${orgId}/payment-link`, { send: false });
    await Clipboard.setStringAsync(res.data.url);
    showSimpleAlert('Continue link copied', 'Paste it into a text or email. The card is saved on Stripe; the first charge lands the day after the pilot ends.');
    return res;
  });

  const lines: string[] = [];
  if (p.state === 'pending') lines.push('Clock starts the day the owner activates their account (90 complimentary days).');
  if (p.state === 'active') lines.push(`Day ${p.day} of ${p.days} · ${p.days_left} days left · ends ${fmt(p.ends_at)} · started ${fmt(p.started_at)}`);
  if (p.state === 'completed') lines.push(`Pilot period over since ${fmt(p.ends_at)} · access continues · nothing was charged · decide: continue, extend or end`);
  if (p.state === 'ended') lines.push(`Ended ${fmt(p.ended_at)} · everyone at the company is blocked · data kept${p.ended_days_ago >= 365 ? ' · older than 12 months, review' : ' for 12 months, then review'}`);
  lines.push(`Agreed pricing after the pilot: ${money(mrr.amount)}/mo (${c.plan_name}${c.seats_extra ? ` + ${c.seats_extra} extra seat${c.seats_extra === 1 ? '' : 's'}` : ''}) · potential MRR, not billed`);
  if (p.reminders_sent?.length) lines.push(`Founder reminders sent: day ${p.reminders_sent.join(', day ')}`);
  if (p.extensions?.length) lines.push(`Extended ${p.extensions.length}x (+${p.extensions.reduce((s: number, e: any) => s + (e.days || 0), 0)} days)`);

  const Btn = ({ label, onPress, testID, icon, tone = 'plain' }: { label: string; onPress: () => void; testID: string; icon: any; tone?: 'gold' | 'plain' | 'red' | 'green' }) => {
    const fg = tone === 'gold' ? '#111' : tone === 'red' ? '#FF3B30' : tone === 'green' ? '#111' : colors.text;
    const bg = tone === 'gold' ? '#C9A962' : tone === 'green' ? '#34C759' : colors.card;
    return (
      <TouchableOpacity onPress={onPress} disabled={busy} data-testid={testID}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 10, borderWidth: 1, borderColor: tone === 'red' ? '#FF3B30' : bg === colors.card ? colors.border : bg, backgroundColor: bg, opacity: busy ? 0.6 : 1 }}>
        <Ionicons name={icon} size={15} color={fg} />
        <Text style={{ fontSize: 13, fontWeight: '600', color: fg }}>{label}</Text>
      </TouchableOpacity>
    );
  };
  const live = (p.state === 'active' || p.state === 'completed') && conversionOn(row.billing_config);
  return (
    <View style={{ gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: p.state === 'ended' ? '#FF3B30' : '#C9A962', padding: 14 }} data-testid="pilot-panel">
      <Text style={{ fontSize: 13, fontWeight: '700', color: '#8E8E93', letterSpacing: 1.2 }}>FOUNDING PARTNER PILOT · {String(p.state || '').toUpperCase()}</Text>
      {lines.map((l, i) => <Text key={i} style={{ fontSize: 14, color: colors.text, lineHeight: 19 }} data-testid={`pilot-line-${i}`}>{l}</Text>)}
      <BillingModeNotice config={row.billing_config} colors={colors} />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {live ? <Btn label="Send continue link" onPress={sendLink} testID="pilot-send-link" icon="paper-plane" tone="gold" /> : null}
        {live ? <Btn label="Copy continue link" onPress={copyLink} testID="pilot-copy-link" icon="copy" /> : null}
        {p.state !== 'ended' ? <Btn label="Extend pilot" onPress={() => onAction('extend')} testID="pilot-extend" icon="time" /> : null}
        {p.state !== 'ended' ? <Btn label="End pilot" onPress={() => onAction('end')} testID="pilot-end" icon="stop-circle" tone="red" /> : null}
        {p.state === 'ended' ? <Btn label="Resume access" onPress={() => onAction('resume')} testID="pilot-resume" icon="play-circle" tone="green" /> : null}
        {live ? <Btn label="Check Stripe" onPress={() => act(() => api.post(`/customers/${orgId}/sync-billing`), 'Synced with Stripe')} testID="pilot-check" icon="refresh" /> : null}
      </View>
    </View>
  );
}
