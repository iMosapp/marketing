/** Store page: the client onboarding form. Status, who it went to, Send / Remind, copy link, and the send + event timeline. */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const pill = { height: 40, borderRadius: 12, paddingHorizontal: 14, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 } as const;
export const OB_COLOR: Record<string, string> = { not_sent: '#8E8E93', sent: '#FF9500', opened: '#FF9500', in_progress: '#FF9500', returned_incomplete: '#FF9500', returned: '#34C759', stalled: '#FF3B30', reviewed: '#34C759' };
const when = (v: any) => v ? new Date(v).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';

export function OnboardingPill({ status, label }: { status: string; label: string }) {
  const color = OB_COLOR[status] || '#8E8E93';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, height: 24, borderRadius: 12, backgroundColor: `${color}20`, alignSelf: 'flex-start' }} {...tid('onboarding-pill')}>
      <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: color }} />
      <Text style={{ fontSize: 12, fontWeight: '700', color }}>{label}</Text>
    </View>
  );
}

type Props = { storeId: string; onboarding: any; formUrl: string; events: any[]; colors: any; s: any; locked: boolean; onChanged: () => Promise<void> };

export const OnboardingCard = ({ storeId, onboarding, formUrl, events, colors, s, locked, onChanged }: Props) => {
  const [open, setOpen] = useState<'send' | 'remind' | null>(null);
  const [email, setEmail] = useState(onboarding?.contact?.email || '');
  const [phone, setPhone] = useState(onboarding?.contact?.phone || '');
  const [channel, setChannel] = useState('both');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const ob = onboarding || {};
  const sends: any[] = ob.sent || [];

  const send = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/admin/compliance/${storeId}/${open === 'remind' ? 'remind' : 'send-form'}`, { email, phone, channel, note });
      const failed = (r.data.results || []).filter((x: any) => !x.ok);
      if (failed.length) showSimpleAlert('Partly sent', failed.map((x: any) => `${x.channel}: ${x.error || 'failed'}`).join('\n'));
      setOpen(null); setNote('');
      await onChanged();
    } catch (e: any) { showSimpleAlert('Not sent', e?.response?.data?.detail || 'Something went wrong.'); }
    finally { setBusy(false); }
  };
  const copy = async () => { await Clipboard.setStringAsync(formUrl); showSimpleAlert('Copied', 'The client form link is on your clipboard.'); };

  return (
    <View style={s.card} {...tid('onboarding-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>1 · Client form</Text>
        <OnboardingPill status={ob.status} label={ob.status_label || ''} />
      </View>
      <Text style={s.hint} {...tid('onboarding-contact')}>
        {ob.contact?.name || ob.contact?.email || ob.contact?.phone ? `To ${[ob.contact?.name, ob.contact?.email, ob.contact?.phone].filter(Boolean).join(' · ')}` : 'No client contact yet. Add an email or cell below.'}
        {ob.first_sent_at ? ` · first sent ${when(ob.first_sent_at)}` : ''}{ob.reminders_sent ? ` · ${ob.reminders_sent} reminder${ob.reminders_sent === 1 ? '' : 's'}` : ''}{ob.opened_at ? ` · opened ${when(ob.opened_at)}` : ''}{ob.returned_at ? ` · returned ${when(ob.returned_at)}` : ''}
      </Text>
      {!!ob.returned_missing?.length && (
        <Text style={{ fontSize: 12.5, color: '#FF9500', marginTop: 6 }} {...tid('onboarding-returned-missing')}>Client still owes: {ob.returned_missing.map((m: string) => m.replace('.', ' → ').replace(/_/g, ' ')).join(', ')}</Text>
      )}
      {!locked && (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <TouchableOpacity onPress={() => setOpen(open === 'send' ? null : 'send')} style={[pill, { backgroundColor: GOLD }]} {...tid('onboarding-send-btn')}>
            <Text style={s.btnText}>{ob.first_sent_at ? 'Re-send form' : 'Send form'}</Text>
          </TouchableOpacity>
          {!!ob.first_sent_at && ob.status !== 'returned' && ob.status !== 'reviewed' && (
            <TouchableOpacity onPress={() => setOpen(open === 'remind' ? null : 'remind')} style={[pill, { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }]} {...tid('onboarding-remind-btn')}>
              <Text style={[s.btnText, { color: colors.text }]}>{ob.returned_missing?.length ? 'Send the gaps' : 'Remind now'}</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={copy} style={[pill, { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', gap: 6 }]} {...tid('onboarding-copy-link')}>
            <Ionicons name="link" size={15} color={colors.textSecondary} /><Text style={[s.btnText, { color: colors.text }]}>Copy link</Text>
          </TouchableOpacity>
        </View>
      )}
      {open && (
        <View style={{ marginTop: 12, gap: 8, backgroundColor: colors.bg, borderRadius: 12, padding: 12 }} {...tid('onboarding-send-form')}>
          <Text style={s.label}>{open === 'remind' ? 'Reminder goes to' : 'Form goes to'}</Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TextInput value={email} onChangeText={setEmail} placeholder="gm@dealer.com" placeholderTextColor={colors.textTertiary} autoCapitalize="none" keyboardType="email-address" style={[s.input, { flex: 1.4 }]} {...tid('onboarding-send-email')} />
            <TextInput value={phone} onChangeText={setPhone} placeholder="+1 801 555 0100" placeholderTextColor={colors.textTertiary} keyboardType="phone-pad" style={[s.input, { flex: 1 }]} {...tid('onboarding-send-phone')} />
          </View>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {[['both', 'Text + email'], ['text', 'Text only'], ['email', 'Email only']].map(([k, l]) => (
              <TouchableOpacity key={k} onPress={() => setChannel(k)} style={{ paddingHorizontal: 11, paddingVertical: 7, borderRadius: 14, backgroundColor: channel === k ? GOLD : colors.card, borderWidth: 1, borderColor: channel === k ? GOLD : colors.border }} {...tid(`onboarding-channel-${k}`)}>
                <Text style={{ fontSize: 12.5, fontWeight: '700', color: channel === k ? '#000' : colors.text }}>{l}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput value={note} onChangeText={setNote} placeholder="Optional personal note added to the message" placeholderTextColor={colors.textTertiary} style={s.input} {...tid('onboarding-send-note')} />
          <TouchableOpacity onPress={send} disabled={busy} style={[s.btn, { backgroundColor: GOLD }]} {...tid('onboarding-send-go')}>
            {busy ? <ActivityIndicator color="#000" /> : <Text style={s.btnText}>{open === 'remind' ? 'Send reminder' : 'Send now'}</Text>}
          </TouchableOpacity>
        </View>
      )}
      {(sends.length > 0 || (events || []).length > 0) && (
        <View style={{ marginTop: 12 }}>
          <TouchableOpacity onPress={() => setShowLog(v => !v)} style={{ flexDirection: 'row', alignItems: 'center' }} {...tid('onboarding-log-toggle')}>
            <Text style={{ flex: 1, fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>ACTIVITY ({sends.length + (events || []).length})</Text>
            <Ionicons name={showLog ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
          </TouchableOpacity>
          {showLog && [...sends.map(x => ({ at: x.at, text: `${x.kind || 'send'} by ${x.channel} to ${x.to}: ${x.ok ? 'delivered to carrier' : 'failed, ' + (x.error || '')}` })), ...(events || []).map(e => ({ at: e.at, text: `${e.title}. ${e.message}` }))]
            .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()).slice(0, 25).map((x, i) => (
              <Text key={i} style={{ fontSize: 12, color: colors.textSecondary, paddingTop: 6, lineHeight: 17 }} {...tid(`onboarding-log-${i}`)}>{when(x.at)} · {x.text}</Text>
            ))}
        </View>
      )}
    </View>
  );
};
