import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { Chip, GRADE_COLORS, SEVERITY_COLORS } from './shared';
import { InspectionCoverage } from './InspectionCoverage';

type Props = { colors: any; appraisalId: string; report: any; grades: Record<string, string>; onChanged: () => void; showToast: (m: string, t?: any) => void };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// AI VEHICLE INSPECTION report: overall + per category, confirmed and possible issues, coverage, why, and the human override.
export const ConditionReport = ({ colors, appraisalId, report: r, grades, onChanged, showToast }: Props) => {
  const [overriding, setOverriding] = useState(false);
  const [pick, setPick] = useState<string>(r.final_overall || 'good');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const color = GRADE_COLORS[r.final_overall] || GOLD;
  const send = async (overall: string | null) => {
    setSaving(true);
    try { await api.post(`/appraisals/${appraisalId}/inspection/override`, { overall, reason }); setOverriding(false); setReason(''); onChanged(); }
    catch (e) { showToast(errText(e, 'Could not change the grade'), 'error'); }
    finally { setSaving(false); }
  };
  const Issue = ({ f, possible }: { f: any; possible?: boolean }) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 }} {...tid(`report-issue-${f.id}`)}>
      <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: possible ? '#FF9500' : SEVERITY_COLORS[f.severity] }} />
      <Text style={{ flex: 1, fontSize: 13.5, color: colors.text }}><Text style={{ fontWeight: '800' }}>{f.location_label}</Text>  {possible ? `Possible ${f.subtype_label} — Needs Review` : `${f.severity_label} ${f.subtype_label}`}</Text>
      {f.sources?.includes('customer_supplied') ? <Ionicons name="cloud-download-outline" size={13} color="#5AC8FA" /> : null}
    </View>
  );
  const Section = ({ title, items, possible, empty }: any) => (
    <View style={{ gap: 2 }}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginTop: 6 }}>{title} · {items.length}</Text>
      {items.length ? items.map((f: any) => <Issue key={f.id} f={f} possible={possible} />) : <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{empty}</Text>}
    </View>
  );
  return (
    <View style={{ gap: 12 }} {...tid('condition-report')}>
      <View style={{ borderRadius: 18, padding: 16, backgroundColor: colors.card, borderWidth: 1.5, borderColor: color, gap: 10 }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>AI VEHICLE INSPECTION</Text>
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 10 }}>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Overall condition</Text>
            <Text style={{ fontSize: 30, fontWeight: '800', color }} {...tid('report-overall')}>{(r.final_overall_label || '—').toUpperCase()}</Text>
          </View>
          {r.overridden ? <Chip label={`Set by ${r.override?.by_name?.split(' ')[0] || 'manager'} · AI said ${grades[r.computed_overall] || r.computed_overall}`} color="#AF52DE" icon="shield-checkmark" testId="report-overridden" /> : r.ai_overall !== r.final_overall ? <Chip label={`Jessi: ${r.ai_overall_label}`} color={GOLD} testId="report-ai-grade" /> : <Chip label="Jessi agrees" color={GOLD} testId="report-ai-grade" />}
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} {...tid('report-categories')}>
          {Object.entries(r.categories || {}).map(([k, c]: any) => (
            <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: colors.bg, borderRadius: 10, paddingHorizontal: 9, paddingVertical: 6, borderWidth: 1, borderColor: colors.border }} {...tid(`report-category-${k}`)}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{c.label}</Text>
              <Text style={{ fontSize: 12, fontWeight: '800', color: GRADE_COLORS[c.final] || colors.textSecondary }}>{(c.final_label || '—').toUpperCase()}</Text>
            </View>
          ))}
        </View>
        <Section title="CONFIRMED ISSUES" items={r.confirmed} empty="Nothing confirmed yet." />
        {r.pending?.length ? <Section title="JESSI FOUND · NEEDS YOUR CALL" items={r.pending} empty="" /> : null}
        <Section title="POSSIBLE ISSUES" items={r.possible} possible empty="None." />
        {r.override?.reason ? <Text style={{ fontSize: 12.5, color: colors.text, fontStyle: 'italic' }} {...tid('report-override-reason')}>Override: "{r.override.reason}" — {r.override.by_name}, {when(r.override.at)}</Text> : null}
        <View style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8, gap: 4 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>WHY THIS GRADE</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }} {...tid('report-reason')}>{r.reason}</Text>
          {r.impression ? <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }}>Jessi: {r.impression}</Text> : null}
          {r.poor_quality_media?.length ? <Text style={{ fontSize: 12.5, color: '#FF9500' }} {...tid('report-poor-quality')}>Blurry video: {r.poor_quality_media.join(', ')} — few usable frames came out of it. A steadier, slower lap would help.</Text> : null}
        </View>
        {!overriding ? (
          <TouchableOpacity onPress={() => { setPick(r.final_overall || 'good'); setOverriding(true); }} style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 4 }} {...tid('report-override-btn')}>
            <Ionicons name="create-outline" size={14} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>{r.overridden ? 'Change or clear the override' : 'Override overall condition'}</Text>
          </TouchableOpacity>
        ) : (
          <View style={{ gap: 8 }} {...tid('override-form')}>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              {Object.entries(grades).map(([k, l]) => (
                <TouchableOpacity key={k} onPress={() => setPick(k)} style={{ flex: 1, paddingVertical: 8, borderRadius: 10, alignItems: 'center', backgroundColor: pick === k ? GRADE_COLORS[k] : colors.bg, borderWidth: 1, borderColor: pick === k ? GRADE_COLORS[k] : colors.border }} {...tid(`override-grade-${k}`)}>
                  <Text style={{ fontSize: 12, fontWeight: '800', color: pick === k ? '#0B0B0D' : colors.text }}>{l}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput value={reason} onChangeText={setReason} placeholder="Why? (kept on the record)" placeholderTextColor={colors.textSecondary} style={{ height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 12, fontSize: 14 }} {...tid('override-reason')} />
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <TouchableOpacity onPress={() => send(pick)} disabled={saving || reason.trim().length < 3} accessibilityState={{ disabled: saving || reason.trim().length < 3 }} style={{ flex: 1, height: 42, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: reason.trim().length < 3 ? 0.5 : 1 }} {...tid('override-save')}><Text style={{ fontWeight: '800', color: '#0B0B0D' }}>Set condition</Text></TouchableOpacity>
              {r.overridden ? <TouchableOpacity onPress={() => send(null)} disabled={saving} style={{ height: 42, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('override-clear')}><Text style={{ fontWeight: '700', color: colors.text }}>Clear</Text></TouchableOpacity> : null}
              <TouchableOpacity onPress={() => setOverriding(false)} style={{ height: 42, paddingHorizontal: 14, alignItems: 'center', justifyContent: 'center' }} {...tid('override-cancel')}><Text style={{ fontWeight: '700', color: colors.textSecondary }}>Cancel</Text></TouchableOpacity>
            </View>
          </View>
        )}
      </View>
      <InspectionCoverage colors={colors} coverage={r.coverage} compact />
    </View>
  );
};
