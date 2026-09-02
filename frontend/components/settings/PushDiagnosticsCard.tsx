import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

const GOLD = '#C9A962';

type Diag = {
  notification_mode: string;
  native_tokens: { platform: string; updated_at: string }[];
  web_subscriptions: number;
  quiet: { quiet_now: boolean; reason: string | null; timezone_used: string; local_time: string };
  held_pushes: number;
  recent: { title: string; outcome: string; at: string }[];
};

const OUTCOME_LABEL: Record<string, string> = {
  sent: 'Delivered to Apple/Google',
  expo_error: 'Rejected by push service',
  held_quiet_hours: 'Held (quiet hours)',
  skipped_sms_only_mode: 'Skipped (SMS-only mode)',
  no_native_token: 'No phone registered',
};

export const PushDiagnosticsCard = ({ userId, colors }: { userId: string; colors: any }) => {
  const [diag, setDiag] = useState<Diag | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const load = () => api.get(`/push/diagnose/${userId}`).then(r => setDiag(r.data)).catch(() => {});
  useEffect(() => { load(); }, [userId]);

  const sendTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await api.post(`/push/diagnose/${userId}/test`);
      if (r.data?.ok) {
        setTestResult('Test push sent. It should be on your lock screen within a few seconds.');
      } else if (r.data?.reason === 'no_native_token') {
        setTestResult(r.data.hint);
      } else {
        const first = r.data?.results?.[0] || {};
        setTestResult(`Push service rejected it: ${first.receipt_error || first.ticket_error || first.message || 'unknown error'}`);
      }
      load();
    } catch (e: any) {
      setTestResult(e?.response?.data?.detail || 'Could not run the test');
    } finally {
      setTesting(false);
    }
  };

  const phones = diag?.native_tokens?.length ?? 0;
  const problem = !!diag && (phones === 0 || diag.quiet.quiet_now || diag.notification_mode === 'sms');
  const last = diag?.recent?.[0];

  return (
    <View style={[st.card, { backgroundColor: colors.card, borderColor: problem ? '#FF950060' : GOLD + '40' }]} testID="push-diagnostics-card" dataSet={{ testid: 'push-diagnostics-card' } as any}>
      <View style={st.head}>
        <Ionicons name={problem ? 'alert-circle' : 'checkmark-circle'} size={20} color={problem ? '#FF9500' : '#34C759'} />
        <Text style={[st.title, { color: colors.text }]}>Push health check</Text>
        <TouchableOpacity onPress={load} hitSlop={10} testID="push-diag-refresh" dataSet={{ testid: 'push-diag-refresh' } as any}>
          <Ionicons name="refresh" size={18} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      {!diag ? (
        <ActivityIndicator color={GOLD} style={{ marginVertical: 8 }} />
      ) : (
        <View style={{ gap: 6 }}>
          <Line ok={phones > 0} colors={colors} text={phones > 0 ? `${phones} phone${phones > 1 ? 's' : ''} registered for alerts` : 'This phone is NOT registered for alerts'} />
          <Line ok={!diag.quiet.quiet_now} colors={colors} text={diag.quiet.quiet_now ? `Alerts are being HELD right now: ${diag.quiet.reason}` : `Not in quiet hours (${diag.quiet.local_time} ${diag.quiet.timezone_used})`} />
          <Line ok={diag.notification_mode !== 'sms'} colors={colors} text={diag.notification_mode === 'sms' ? 'Alert delivery is set to SMS only, pushes are skipped' : `Delivery mode: ${diag.notification_mode}`} />
          {diag.held_pushes > 0 && <Line ok={false} colors={colors} text={`${diag.held_pushes} alerts waiting in the held queue`} />}
          {last && (
            <Text style={[st.hint, { color: colors.textTertiary }]}>
              Last attempt: "{last.title}" · {OUTCOME_LABEL[last.outcome] || last.outcome}
            </Text>
          )}
        </View>
      )}

      <TouchableOpacity style={[st.btn, testing && { opacity: 0.6 }]} onPress={sendTest} disabled={testing} testID="push-diag-test-btn" dataSet={{ testid: 'push-diag-test-btn' } as any}>
        {testing ? <ActivityIndicator size="small" color="#000" /> : (
          <>
            <Ionicons name="paper-plane" size={15} color="#000" />
            <Text style={st.btnText}>Send me a test push</Text>
          </>
        )}
      </TouchableOpacity>
      {testResult && <Text style={[st.result, { color: colors.textSecondary }]} testID="push-diag-test-result" dataSet={{ testid: 'push-diag-test-result' } as any}>{testResult}</Text>}
      {Platform.OS === 'web' && phones === 0 && (
        <Text style={[st.hint, { color: colors.textTertiary }]}>Open this screen inside the iPhone app to register that phone.</Text>
      )}
    </View>
  );
};

const Line = ({ ok, text, colors }: { ok: boolean; text: string; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
    <Ionicons name={ok ? 'checkmark' : 'close'} size={15} color={ok ? '#34C759' : '#FF9500'} style={{ marginTop: 2 }} />
    <Text style={{ flex: 1, fontSize: 14, lineHeight: 19, color: ok ? colors.textSecondary : colors.text, fontWeight: ok ? '400' : '600' }}>{text}</Text>
  </View>
);

const st = StyleSheet.create({
  card: { borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, gap: 12 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { flex: 1, fontSize: 16, fontWeight: '700' },
  hint: { fontSize: 12, lineHeight: 16, marginTop: 2 },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: GOLD, borderRadius: 12, paddingVertical: 12 },
  btnText: { color: '#000', fontWeight: '700', fontSize: 15 },
  result: { fontSize: 13, lineHeight: 18 },
});
