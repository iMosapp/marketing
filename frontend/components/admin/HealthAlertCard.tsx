import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Status = {
  enabled: boolean; email: string; schedule: string; recipients: string[];
  last_sent_at: string | null; last_counts: Record<string, number> | null; baseline_taken_at: string | null;
};

export function HealthAlertCard({ colors }: { colors: any }) {
  const { showToast } = useToast();
  const [status, setStatus] = useState<Status | null>(null);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => { api.get('/account-health/alerts/status').then(r => setStatus(r.data)).catch(() => {}); }, []);

  const toggle = async (enabled: boolean) => {
    setStatus(s => s ? { ...s, enabled } : s);
    try { await api.put('/account-health/alerts/settings', { enabled }); }
    catch { setStatus(s => s ? { ...s, enabled: !enabled } : s); showToast('Could not save', 'error'); }
  };

  const preview = async () => {
    setSending(true); setResult(null);
    try {
      const r = await api.post('/account-health/alerts/preview');
      const c = r.data?.counts || {};
      setResult(r.data?.sent
        ? `Sent to ${status?.email}. ${c.slipped_critical || 0} slipped to Critical, ${c.slipped_risk || 0} to At Risk, ${c.recovered || 0} recovered, ${c.still_critical || 0} still Critical.`
        : 'The email did not go out. Check the sender domain in Resend.');
    } catch (e: any) { setResult(e?.response?.data?.detail || 'Could not send the preview'); }
    setSending(false);
  };

  const lastLine = status?.last_sent_at
    ? `Last sent ${new Date(status.last_sent_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
    : status?.baseline_taken_at ? 'First comparison lands next Monday' : 'Not sent yet';

  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: GOLD + '55', padding: 14, marginBottom: 14 }} {...tid('health-alert-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="mail-unread" size={18} color={GOLD} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Monday alert email</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>Accounts that slipped to Critical since last week</Text>
        </View>
        {status ? (
          <Switch value={status.enabled} onValueChange={toggle} trackColor={{ true: GOLD, false: '#3A3A3C' }} thumbColor="#fff" {...tid('health-alert-toggle')} />
        ) : <ActivityIndicator size="small" color={GOLD} />}
      </View>
      <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 10 }} {...tid('health-alert-meta')}>
        {status?.schedule || 'Every Monday morning'} · {lastLine}{status?.recipients?.length ? ` · ${status.recipients.length} recipient${status.recipients.length === 1 ? '' : 's'}` : ''}
      </Text>
      <TouchableOpacity onPress={preview} disabled={sending || !status}
        style={{ marginTop: 12, alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: GOLD, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 9, opacity: sending ? 0.6 : 1 }}
        {...tid('health-alert-preview-btn')}>
        {sending ? <ActivityIndicator size="small" color="#000" /> : <Ionicons name="paper-plane" size={14} color="#000" />}
        <Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>{sending ? 'Sending...' : 'Send me a preview'}</Text>
      </TouchableOpacity>
      {result ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 8 }} {...tid('health-alert-result')}>{result}</Text> : null}
    </View>
  );
}
