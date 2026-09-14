import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { GOLD, GREEN, RED, tid } from './shared';

type Digest = { enabled: boolean; email: string; store: { id: string; name: string } | null; last_week_label: string; next_send: string | null; recipients: number; recipient_names: string[]; last_sent_week: string | null; last_sent_at: string | null; last_error: string | null };

const fmtDay = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });

// Monday coaching digest: on by default for every manager, each one can turn theirs off, "Send me last week's now" for a preview.
export const DigestCard = ({ colors }: { colors: any }) => {
  const { showToast } = useToast();
  const [d, setD] = useState<Digest | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => { api.get('/scorecards/digest').then(r => setD(r.data)).catch(() => setD(null)); }, []);

  const toggle = async (enabled: boolean) => {
    setBusy('toggle');
    try { const r = await api.put('/scorecards/digest', { enabled }); setD(r.data); showToast(enabled ? 'You will get the digest every Monday' : 'Digest turned off for you', 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not update', 'error'); }
    finally { setBusy(null); }
  };
  const sendNow = async () => {
    setBusy('send');
    try { const r = await api.post('/scorecards/digest/send'); showToast(`Sent to ${d?.email}: ${r.data.summary}`, 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not send', 'error'); }
    finally { setBusy(null); }
  };

  if (!d) return null;
  const others = Math.max(0, d.recipients - (d.enabled ? 1 : 0));
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 10 }} {...tid('digest-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="mail-outline" size={19} color={GOLD} /></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }}>Monday coaching digest</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} {...tid('digest-status')}>
            {!d.store ? 'Your account is not on a store yet, so there is no team to digest.'
              : d.enabled ? `Every Monday at 8am to ${d.email}${others ? ` and ${others} other manager${others === 1 ? '' : 's'}` : ''}. Each rep's scores, what changed, unread coaching and the one thing to coach next.`
              : `Off for you.${d.recipients ? ` Still goes to ${d.recipients} other manager${d.recipients === 1 ? '' : 's'}.` : ''}`}
          </Text>
        </View>
        {!!d.store && (busy === 'toggle' ? <ActivityIndicator color={GOLD} /> : <Switch value={d.enabled} onValueChange={toggle} trackColor={{ true: GOLD }} {...tid('digest-toggle')} />)}
      </View>
      {!!d.store && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Text style={{ flex: 1, fontSize: 11.5, color: colors.textSecondary }} {...tid('digest-last')}>
            {d.last_error ? <Text style={{ color: RED }}>Last try failed: {d.last_error}</Text> : d.last_sent_at ? <Text style={{ color: GREEN }}>Last sent {new Date(d.last_sent_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</Text> : 'Not sent yet'}
            {d.next_send ? ` · next ${fmtDay(d.next_send)}` : ''}
          </Text>
          <TouchableOpacity onPress={sendNow} disabled={busy === 'send'} style={{ height: 36, paddingHorizontal: 12, borderRadius: 10, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('digest-send-now')}>
            {busy === 'send' ? <ActivityIndicator color={GOLD} size="small" /> : <><Ionicons name="paper-plane-outline" size={14} color={GOLD} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Send me {d.last_week_label} now</Text></>}
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
};
