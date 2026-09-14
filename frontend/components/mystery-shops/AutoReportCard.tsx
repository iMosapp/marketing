import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { monthLabel, GOLD, GREEN, RED, tid } from './shared';

export type AutoReport = { enabled: boolean; to: string; last_sent_month: string | null; last_sent_at: string | null; last_sent_to?: string | null; last_error?: string | null; next_send?: string | null };

// Report tab: "email the PDF to the GM on the 1st" toggle, where it goes, and a Send-now for this month's view.
export const AutoReportCard = ({ clientId, value, month, colors, onChanged }: { clientId: string; value: AutoReport; month: string; colors: any; onChanged: (v: AutoReport) => void }) => {
  const { showToast } = useToast();
  const [to, setTo] = useState(value.to || '');
  const [busy, setBusy] = useState<'toggle' | 'to' | 'send' | null>(null);
  useEffect(() => { setTo(value.to || ''); }, [value.to]);

  const save = async (patch: { enabled?: boolean; to?: string }, kind: 'toggle' | 'to') => {
    setBusy(kind);
    try { const r = await api.put(`/shop-clients/${clientId}/report/auto`, patch); onChanged(r.data.auto_report); if (patch.enabled !== undefined) showToast(patch.enabled ? 'Monthly report email is on' : 'Monthly report email is off', 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(null); }
  };
  const sendNow = async () => {
    setBusy('send');
    try { const r = await api.post(`/shop-clients/${clientId}/report/send`, { month, to: to.trim() || undefined }); onChanged(r.data.auto_report); showToast(`${r.data.month_label} report sent to ${r.data.to}`, 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'The email did not go out', 'error'); }
    finally { setBusy(null); }
  };
  const nextLabel = value.next_send ? new Date(`${value.next_send}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';

  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: value.enabled ? GREEN + '66' : colors.border, padding: 14, gap: 10 }} {...tid('auto-report-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Email the PDF to the GM on the 1st</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16, marginTop: 2 }} {...tid('auto-report-status')}>
            {value.enabled
              ? `On · last month's report goes out ${nextLabel ? `${nextLabel} ` : ''}after 8 AM store time with a one-line summary and the live link`
              : 'Off · nothing is sent automatically. Turn it on and the GM gets last month\'s report the morning of the 1st.'}
          </Text>
        </View>
        {busy === 'toggle' ? <ActivityIndicator color={GOLD} /> : (
          <Switch value={value.enabled} onValueChange={v => save({ enabled: v, to: to.trim() || undefined }, 'toggle')} trackColor={{ true: GREEN, false: colors.border }} thumbColor="#fff" {...tid('auto-report-toggle')} />
        )}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="mail-outline" size={16} color={colors.textSecondary} />
        <TextInput value={to} onChangeText={setTo} onBlur={() => { if (to.trim().toLowerCase() !== (value.to || '').toLowerCase()) save({ to: to.trim() }, 'to'); }} placeholder="GM's email" placeholderTextColor={colors.textSecondary}
          autoCapitalize="none" keyboardType="email-address" style={{ flex: 1, fontSize: 14, color: colors.text, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 10, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface || colors.bg }} {...tid('auto-report-to')} />
        {busy === 'to' && <ActivityIndicator color={GOLD} size="small" />}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <TouchableOpacity onPress={sendNow} disabled={!!busy} style={{ height: 36, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('auto-report-send-now')}>
          {busy === 'send' ? <ActivityIndicator color={GOLD} size="small" /> : <Ionicons name="paper-plane-outline" size={14} color={GOLD} />}
          <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Send {monthLabel(month)} now</Text>
        </TouchableOpacity>
        <Text style={{ flex: 1, fontSize: 11.5, color: value.last_error ? RED : colors.textSecondary }} {...tid('auto-report-last')}>
          {value.last_error ? `Last try failed: ${value.last_error}` : value.last_sent_month ? `Last sent: ${monthLabel(value.last_sent_month)} report${value.last_sent_to ? ` to ${value.last_sent_to}` : ''}${value.last_sent_at ? ` on ${new Date(value.last_sent_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}` : ''}` : 'Never sent yet'}
        </Text>
      </View>
    </View>
  );
};
