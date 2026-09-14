import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { monthLabel, GOLD, GREEN, RED, tid } from './shared';

export type AutoReport = { enabled: boolean; to: string; last_sent_month?: string | null; last_sent_week?: string | null; last_sent_at: string | null; last_sent_to?: string | null; last_error?: string | null; next_send?: string | null };

const fmtDay = (iso?: string | null) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');

// Report tab schedules: the monthly PDF on the 1st and the Monday digest. Same card, different endpoint + copy.
export const AutoReportCard = ({ clientId, value, month, colors, onChanged, kind = 'monthly' }: { clientId: string; value: AutoReport; month: string; colors: any; onChanged: (v: AutoReport) => void; kind?: 'monthly' | 'weekly' }) => {
  const { showToast } = useToast();
  const [to, setTo] = useState(value.to || '');
  const [busy, setBusy] = useState<'toggle' | 'to' | 'send' | null>(null);
  useEffect(() => { setTo(value.to || ''); }, [value.to]);
  const weekly = kind === 'weekly';
  const base = `/shop-clients/${clientId}/report/${weekly ? 'weekly' : 'auto'}`;
  const key = weekly ? 'weekly_digest' : 'auto_report';
  const t = tid(`${weekly ? 'weekly-digest' : 'auto-report'}`);
  const id = (suffix: string) => tid(`${weekly ? 'weekly-digest' : 'auto-report'}-${suffix}`);

  const save = async (patch: { enabled?: boolean; to?: string }, k: 'toggle' | 'to') => {
    setBusy(k);
    try { const r = await api.put(base, patch); onChanged(r.data[key]); if (patch.enabled !== undefined) showToast(patch.enabled ? (weekly ? 'Monday digest is on' : 'Monthly report email is on') : (weekly ? 'Monday digest is off' : 'Monthly report email is off'), 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(null); }
  };
  const sendNow = async () => {
    setBusy('send');
    try {
      const r = await api.post(weekly ? `${base}/send` : `/shop-clients/${clientId}/report/send`, weekly ? { to: to.trim() || undefined } : { month, to: to.trim() || undefined });
      onChanged(r.data[key]); showToast(`${weekly ? `Digest (${r.data.label})` : `${r.data.month_label} report`} sent to ${r.data.to}`, 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'The email did not go out', 'error'); }
    finally { setBusy(null); }
  };
  const next = fmtDay(value.next_send);
  const last = value.last_error ? `Last try failed: ${value.last_error}`
    : (weekly ? value.last_sent_week : value.last_sent_month)
      ? `Last sent: ${weekly ? `week ${(value.last_sent_week || '').split('-W')[1]}` : `${monthLabel(value.last_sent_month || '')} report`}${value.last_sent_to ? ` to ${value.last_sent_to}` : ''}${value.last_sent_at ? ` on ${new Date(value.last_sent_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}` : ''}`
      : 'Never sent yet';

  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: value.enabled ? GREEN + '66' : colors.border, padding: 14, gap: 10 }} {...t}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{weekly ? 'Monday digest: last week\'s shops and scores' : 'Email the PDF to the GM on the 1st'}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16, marginTop: 2 }} {...id('status')}>
            {value.enabled
              ? weekly ? `On · a short email every Monday${next ? ` (next ${next})` : ''} after 8 AM store time: who was shopped, the scores, one line each. No PDF.`
                : `On · last month's report goes out ${next ? `${next} ` : ''}after 8 AM store time with a one-line summary and the live link`
              : weekly ? 'Off · for stores that want a faster loop than the monthly PDF. Turn it on and the GM gets last week\'s shops every Monday morning.'
                : 'Off · nothing is sent automatically. Turn it on and the GM gets last month\'s report the morning of the 1st.'}
          </Text>
        </View>
        {busy === 'toggle' ? <ActivityIndicator color={GOLD} /> : (
          <Switch value={value.enabled} onValueChange={v => save({ enabled: v, to: to.trim() || undefined }, 'toggle')} trackColor={{ true: GREEN, false: colors.border }} thumbColor="#fff" {...id('toggle')} />
        )}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="mail-outline" size={16} color={colors.textSecondary} />
        <TextInput value={to} onChangeText={setTo} onBlur={() => { if (to.trim().toLowerCase() !== (value.to || '').toLowerCase()) save({ to: to.trim() }, 'to'); }} placeholder="GM's email" placeholderTextColor={colors.textSecondary}
          autoCapitalize="none" keyboardType="email-address" style={{ flex: 1, fontSize: 14, color: colors.text, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 10, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface || colors.bg }} {...id('to')} />
        {busy === 'to' && <ActivityIndicator color={GOLD} size="small" />}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <TouchableOpacity onPress={sendNow} disabled={!!busy} style={{ height: 36, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...id('send-now')}>
          {busy === 'send' ? <ActivityIndicator color={GOLD} size="small" /> : <Ionicons name="paper-plane-outline" size={14} color={GOLD} />}
          <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>{weekly ? "Send last week's digest now" : `Send ${monthLabel(month)} now`}</Text>
        </TouchableOpacity>
        <Text style={{ flex: 1, fontSize: 11.5, color: value.last_error ? RED : colors.textSecondary }} {...id('last')}>{last}</Text>
      </View>
    </View>
  );
};
