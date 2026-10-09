import React, { useEffect, useState } from 'react';
import { View, Text, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../common/Toast';
import { Chip, GoldButton } from '../../mystery-shops/shared';
import { Card } from '../CcShell';
import { GOLD, RED, detail, tid, type MorningBrief as MB } from '../shared';

const HOURS = [5, 6, 7, 8, 9, 10];
export const hourLabel = (h: number) => `${((h + 11) % 12) + 1}:00 ${h < 12 ? 'AM' : 'PM'}`;
const deviceTz = () => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined; } catch { return undefined; } };
const fmt = (iso: string, opts: Intl.DateTimeFormatOptions, tz?: string) => { const d = new Date(iso); try { return d.toLocaleString(undefined, { ...opts, timeZone: tz }); } catch { return d.toLocaleString(undefined, opts); } };

// MORNING BRIEF: the Chief of Staff's operating review pushed to the founder's phone once a day at a local hour. One model call a day, counted against the team budget.
export const MorningBrief = ({ colors, onChanged }: { colors: any; onChanged?: () => void }) => {
  const { showToast } = useToast();
  const [mb, setMb] = useState<MB | null>(null);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const load = async () => { try { setMb((await api.get('/command-center/team/morning-brief')).data); } catch (e: any) { showToast(detail(e, 'Could not load the morning brief settings'), 'error'); } };
  useEffect(() => { load(); }, []);
  const save = async (body: any, msg: string) => {
    setBusy(true);
    try { setMb((await api.put('/command-center/team/morning-brief', body)).data); showToast(msg); onChanged?.(); } catch (e: any) { showToast(detail(e, 'Could not save'), 'error'); } finally { setBusy(false); }
  };
  const toggle = (v: boolean) => save(v ? { enabled: true, timezone: deviceTz() } : { enabled: false }, v ? 'Morning brief is on' : 'Morning brief is off');
  const sendNow = () => showConfirm('Send the brief now?', "The Chief of Staff writes today's operating review (one model call, about $0.03) and pushes the headline to your phone. It counts as today's brief.", async () => {
    setSending(true);
    try {
      const r = (await api.post('/command-center/team/morning-brief/send', {}, { timeout: 120000 })).data;
      showToast(r.pushed ? `Sent to ${r.pushed} device${r.pushed === 1 ? '' : 's'}` : 'Brief written. No phone reached by push, so it is waiting in your in-app alerts.', 'success', 6000);
      await load(); onChanged?.();
    } catch (e: any) { showToast(detail(e, 'The Chief of Staff could not write the brief'), 'error', 6000); } finally { setSending(false); }
  }, undefined, 'Send it');
  if (!mb) return <Card colors={colors} testID="cc-morning-card"><ActivityIndicator color={GOLD} /></Card>;
  const tz = mb.timezone.replace(/_/g, ' ');
  const next = mb.next_send ? fmt(mb.next_send, { weekday: 'short', hour: 'numeric', minute: '2-digit' }, mb.timezone) : '';
  const last = mb.last_sent_at ? fmt(mb.last_sent_at, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
  return (
    <Card colors={colors} accent={mb.enabled ? GOLD : undefined} testID="cc-morning-card">
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <Ionicons name="sunny" size={22} color={mb.enabled ? GOLD : colors.textSecondary} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Morning brief on your phone</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('cc-morning-status')}>{mb.enabled ? `On · next ${next} (${tz})` : 'Off. The Chief of Staff only writes the review when you ask.'}</Text>
        </View>
        <Switch value={mb.enabled} onValueChange={toggle} disabled={busy} trackColor={{ true: GOLD }} {...tid('cc-morning-switch')} />
      </View>
      <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 17 }}>Every morning the Chief of Staff reads the Command Center, pending decisions and readiness gaps, writes the operating review and pushes the headline to your phone. One model call a day, about $0.03, counted against the team budget.</Text>
      <View style={{ gap: 6 }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>WHEN · YOUR LOCAL TIME</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {HOURS.map(h => <Chip key={h} label={hourLabel(h)} active={mb.hour === h} onPress={() => save({ hour: h, timezone: deviceTz() }, `Brief at ${hourLabel(h)}`)} colors={colors} small testID={`cc-morning-hour-${h}`} />)}
        </View>
      </View>
      {(!!last || !!mb.last_error) && (
        <Text style={{ fontSize: 12, color: mb.last_error ? RED : colors.textSecondary, lineHeight: 16 }} {...tid('cc-morning-last')}>
          {mb.last_error ? `Last attempt failed: ${mb.last_error}` : `Last sent ${last}${mb.last_pushed ? ` to ${mb.last_pushed} device${mb.last_pushed === 1 ? '' : 's'}` : ' (no phone reached by push; it is in your in-app alerts)'}`}
        </Text>
      )}
      <GoldButton label="Send it now" icon="paper-plane" outline busy={sending} onPress={sendNow} testID="cc-morning-send" />
    </Card>
  );
};
