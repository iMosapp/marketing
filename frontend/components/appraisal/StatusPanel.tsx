import React, { useState } from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { showConfirm } from '../../services/alert';
import { BigButton, money, marketLabel } from './shared';
import { ValueBreakdown } from './ValueBreakdown';
import { OutcomeSheet } from './OutcomeSheet';
import { DeskNotified } from './DeskNotified';

type Props = { colors: any; appraisal: any; onSaved: (appraisal: any) => void; showToast: (m: string, t?: any, d?: number) => void };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');
const DECISION_LABEL: Record<string, string> = { approve: 'Approved as suggested', change: 'Approved with a different value', request_info: 'Asked for more', decline: 'Declined' };

// After submission the rep sees exactly where the appraisal stands and the one thing to do next (wait · present · record the outcome).
export const StatusPanel = ({ colors, appraisal: a, onSaved, showToast }: Props) => {
  const router = useRouter();
  const [sheet, setSheet] = useState(false);
  const [busy, setBusy] = useState(false);
  const w = a.workflow || {};
  const st = a.status;
  const approved = w.approved_value ?? a.approved_value;
  const adj = w.manager_adjustment;
  const waiting = st === 'submitted' || st === 'resubmitted';
  const banner = waiting
    ? { icon: 'hourglass', color: '#FF9500', title: st === 'resubmitted' ? 'Resubmitted, waiting for the desk' : 'Waiting for the desk', sub: `Sent ${when(w.submitted_at)} by ${w.submitted_by_name || 'you'}. The inputs are frozen until a manager answers.` }
    : st === 'approved' ? { icon: 'checkmark-circle', color: '#34C759', title: `Approved: ${money(approved)}`, sub: `${w.approved_by_name} approved the suggested number ${when(w.approved_at)}. Present it when you are with the customer.` }
    : st === 'changed' ? { icon: 'checkmark-circle', color: '#34C759', title: `Approved: ${money(approved)}`, sub: `${w.approved_by_name} changed it from the suggested ${money(adj?.system_suggested_acv)} (${(adj?.delta || 0) >= 0 ? '+' : '-'}${money(Math.abs(adj?.delta || 0))})${adj?.reason ? `: ${adj.reason}` : ''}.` }
    : st === 'declined' ? { icon: 'close-circle', color: '#FF3B30', title: 'Declined by the desk', sub: `${w.declined_by_name}: ${w.declined_reason}` }
    : st === 'presented' ? { icon: 'hand-left', color: GOLD, title: `Presented ${money(approved)}`, sub: `${when(w.presented_at)} by ${w.presented_by_name}. Record what the customer said.` }
    : st === 'closed' ? { icon: 'flag', color: GOLD, title: `Closed · ${w.outcome_label || a.outcome_label}`, sub: [a.customer_expected_value && a.outcome === 'wants_more' ? `Customer wants ${money(a.customer_expected_value)}${w.expectation_gap_final != null ? ` (${money(w.expectation_gap_final)} more)` : ''}` : null, w.outcome_note].filter(Boolean).join(' · ') || `Recorded ${when(w.outcome_at)}` }
    : { icon: 'information-circle', color: colors.textSecondary, title: a.abilities?.status_label || st, sub: '' };

  const present = () => showConfirm('Present this number?', `${money(approved)} goes on the record as presented to ${a.contact_name}. You will then record what they said.`, async () => {
    setBusy(true);
    try { const r = (await api.post(`/appraisals/${a.id}/present`)).data; onSaved({ ...r.appraisal, workflow: r.workflow, abilities: r.abilities }); showToast('Marked as presented', 'success'); }
    catch (e) { showToast(errText(e, 'Could not mark as presented'), 'error', 5000); }
    finally { setBusy(false); }
  }, undefined, 'Present');

  return (
    <View style={{ gap: 12 }} {...tid('status-panel')}>
      <View style={{ borderRadius: 16, padding: 14, backgroundColor: banner.color + '18', borderWidth: 1.5, borderColor: banner.color, gap: 4 }} {...tid(`status-banner-${st}`)}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name={banner.icon as any} size={22} color={banner.color} />
          <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }} {...tid('status-title')}>{banner.title}</Text>
        </View>
        {banner.sub ? <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }} {...tid('status-sub')}>{banner.sub}</Text> : null}
      </View>
      <DeskNotified colors={colors} rows={w.notified_managers} legacyCount={w.notified_manager_ids?.length || 0} waiting={waiting} testId="status-notified" />
      {a.abilities?.present ? <BigButton icon="hand-left" label={`Present ${money(approved)} to ${a.contact_name?.split(' ')[0] || 'the customer'}`} sub="Marks it presented; then record what they said" onPress={present} primary disabled={busy} testId="present-btn" colors={colors} /> : null}
      {a.abilities?.outcome ? <BigButton icon="chatbubble-ellipses" label="What did the customer say?" sub="Accepted · wants more · thinking · not trading" onPress={() => setSheet(true)} primary testId="outcome-btn" colors={colors} /> : null}
      {st === 'closed' && a.vehicle_id ? (
        <BigButton icon={a.outcome === 'accepted' ? 'swap-horizontal' : 'time-outline'} label={a.outcome === 'accepted' ? 'Trade done? Confirm it on the vehicle' : 'Vehicle history'}
          sub={a.outcome === 'accepted' ? 'An accepted offer is intent. The vehicle stays owned until you confirm the trade.' : 'Every appraisal on this vehicle, ownership, and Reappraise'} onPress={() => router.push(`/vehicle/${a.vehicle_id}` as any)} testId="open-vehicle-btn" colors={colors} />
      ) : null}
      <ValueBreakdown colors={colors} output={a.calculation?.output} marketRetail={a.market?.estimated_retail} marketLabel={marketLabel(a.market)}
        approvedValue={approved} approvedBy={w.approved_by_name} approvedPending={st === 'submitted' || st === 'resubmitted'} />
      {a.decisions?.length ? (
        <View style={{ borderRadius: 16, paddingHorizontal: 14, paddingVertical: 6, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('decisions-card')}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, paddingVertical: 8 }}>DESK DECISIONS</Text>
          {a.decisions.map((d: any) => (
            <View key={d.id} style={{ paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border, gap: 2 }} {...tid(`decision-${d.id}`)}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{DECISION_LABEL[d.action] || d.action}{d.manager_approved_value != null ? ` · ${money(d.manager_approved_value)}` : ''}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{d.manager_name} · {when(d.decided_at)}{d.reason ? ` · ${d.reason}` : ''}</Text>
            </View>
          ))}
        </View>
      ) : null}
      <OutcomeSheet colors={colors} appraisal={a} visible={sheet} onClose={() => setSheet(false)} onSaved={onSaved} showToast={showToast} />
    </View>
  );
};
