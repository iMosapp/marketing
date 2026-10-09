import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { showConfirm } from '../../services/alert';
import { BigButton, money, marketLabel } from './shared';
import { ValueBreakdown } from './ValueBreakdown';
import { notifiedSummary } from './DeskNotified';

type Props = { colors: any; appraisal: any; onSaved: (appraisal: any) => void; showToast: (m: string, t?: any, d?: number) => void };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// The rep's last stop before the desk: a live preview of the dealership's number, then one tap to freeze it and send it to a manager.
export const SubmitPanel = ({ colors, appraisal, onSaved, showToast }: Props) => {
  const [calc, setCalc] = useState<any | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setCalc((await api.get(`/appraisals/${appraisal.id}/calculate`)).data); setErr(null); }
    catch (e) { setErr(errText(e, 'Could not calculate')); }
  }, [appraisal.id, appraisal.updated_at]);
  useEffect(() => { load(); }, [load]);

  const ni = appraisal.workflow?.needs_info_request;
  const resub = appraisal.status === 'needs_info';
  const o = calc?.output;
  const submit = () => {
    const line = o?.suggested_acv != null ? `Suggested ACV ${money(o.suggested_acv)}. ` : 'No starting value yet, so the manager will set the number. ';
    showConfirm(resub ? 'Resubmit to the desk?' : 'Send to the desk?', `${line}The inputs freeze until a manager answers.`, async () => {
      setBusy(true);
      try {
        const r = (await api.post(`/appraisals/${appraisal.id}/submit`)).data;
        if (r.notified) showToast(`Sent to the desk. ${notifiedSummary(r.notified_managers) || `${r.notified} manager${r.notified > 1 ? 's' : ''} notified`}.`, 'success', 5000);
        else showToast('Sent to the desk, but nobody was alerted: no manager at this store has appraisal approvals switched on. Ask your admin.', 'error', 7000);
        onSaved({ ...r.appraisal, workflow: r.workflow, abilities: r.abilities });
      } catch (e) { showToast(errText(e, 'Could not submit'), 'error', 5000); }
      finally { setBusy(false); }
    }, undefined, resub ? 'Resubmit' : 'Submit');
  };

  return (
    <View style={{ gap: 12 }} {...tid('submit-panel')}>
      {ni ? (
        <View style={{ borderRadius: 14, padding: 12, backgroundColor: '#FF950018', borderWidth: 1, borderColor: '#FF9500', gap: 4 }} {...tid('needs-info-banner')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}><Ionicons name="help-circle" size={16} color="#FF9500" /><Text style={{ fontSize: 11, fontWeight: '800', color: '#FF9500', letterSpacing: 0.6 }}>MANAGER WANTS MORE</Text></View>
          <Text style={{ fontSize: 14.5, fontWeight: '700', color: colors.text }}>{ni.reason}</Text>
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{ni.by_name} · {when(ni.at)}. Fix it on the steps above, then resubmit.</Text>
        </View>
      ) : null}
      {!calc && !err ? <ActivityIndicator color={GOLD} /> : null}
      {err ? <Text style={{ fontSize: 13, color: '#FF3B30' }} {...tid('calc-error')}>{err}</Text> : null}
      {o ? (
        <>
          <ValueBreakdown colors={colors} output={o} marketRetail={calc.market?.estimated_retail} marketLabel={marketLabel(calc.market)} approvedPending={false} />
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }} {...tid('calc-rules-line')}>Dealership rules: {calc.rules_source === 'default' ? "I'm On Social defaults" : calc.rules_source === 'store' ? `store override v${calc.rules_version}` : `organization default v${calc.rules_version}`}. Live preview; the number freezes when you submit.</Text>
        </>
      ) : null}
      <BigButton icon="paper-plane" label={resub ? 'Resubmit to the desk' : 'Submit for approval'} sub={o?.manager_review_required ? 'Flagged for a manager\u2019s eyes' : 'A manager approves, changes or declines'} onPress={submit} primary disabled={busy || !calc} testId="submit-appraisal" colors={colors} />
    </View>
  );
};
