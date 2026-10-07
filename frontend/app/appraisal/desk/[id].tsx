import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { ScreenHeader, HeaderTextButton } from '../../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../../components/inbox/ownership';
import { Chip, money, miles, marketLabel } from '../../../components/appraisal/shared';
import { ValueBreakdown, ReferencesCard } from '../../../components/appraisal/ValueBreakdown';
import { DeskDecisionBar } from '../../../components/appraisal/desk/DeskDecisionBar';
import { CustomerWantsCard, ConditionCard, MarketCard, RepCard, CustomerIntakeCard, HistoryCard, ActivityCard } from '../../../components/appraisal/desk/DeskCards';

const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');
const ago = (s?: number | null) => (s == null ? '' : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : s < 86400 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} d`);
const STATUS_COLOR: Record<string, string> = { submitted: '#FF9500', resubmitted: '#FF9500', needs_info: '#FF9500', approved: '#34C759', changed: '#34C759', declined: '#FF3B30', presented: GOLD, closed: GOLD };
const DECISION_LABEL: Record<string, string> = { approve: 'Approved as suggested', change: 'Approved with a different value', request_info: 'Asked for more', decline: 'Declined' };

// Desk review: everything a manager needs in one scroll, the decision bar pinned at the bottom. Three numbers, three labels, never blended.
export default function DeskReview() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [a, setA] = useState<any | null>(null);

  const load = useCallback(async () => {
    try { setA((await api.get(`/appraisals/desk/${id}`)).data); }
    catch (e: any) {
      showToast(errText(e, e?.response?.status === 403 ? 'Appraisal approvals are not switched on for you' : 'Could not open that appraisal'), 'error', 5000);
      if (router.canGoBack()) router.back(); else router.replace('/appraisal/desk' as any);
    }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (!a) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Appraisal Desk" /><ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /></SafeAreaView>;
  const w = a.calculation?.output;
  const sc = STATUS_COLOR[a.status] || colors.textSecondary;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('desk-review')}>
      <ScreenHeader title={a.contact_name} subtitle={`${a.vehicle_label || 'Vehicle not identified'}${a.mileage_confirmed != null ? ` · ${miles(a.mileage_confirmed)}` : ''}`}
        onBack={() => (router.canGoBack() ? router.back() : router.replace('/appraisal/desk' as any))}
        right={<HeaderTextButton label="Rep view" onPress={() => router.push(`/appraisal/${a.id}` as any)} testID="desk-open-rep-view" />} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 24, gap: 12 }} keyboardShouldPersistTaps="handled">
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }} {...tid('desk-status-line')}>
            <Chip label={(a.status_label || a.status).toUpperCase()} color={sc} testId="desk-status-chip" />
            {a.waiting_s != null ? <Text style={{ fontSize: 12.5, fontWeight: '700', color: a.waiting_s > 3600 ? '#FF3B30' : colors.textSecondary }}>{ago(a.waiting_s)} waiting</Text> : null}
            <Text style={{ flex: 1, fontSize: 12.5, color: colors.textSecondary }} numberOfLines={2}>{a.status === 'submitted' || a.status === 'resubmitted' ? `Sent ${when(a.submitted_at)} by ${a.submitted_by_name || a.user_name}` : `${a.user_name} · updated ${when(a.updated_at)}`}{a.is_reappraisal ? ' · reappraisal' : ''}</Text>
          </View>
          {a.needs_info_request && a.status === 'needs_info' ? <Text style={{ fontSize: 13, color: '#FF9500', fontWeight: '700' }} {...tid('desk-needs-info-line')}>Waiting on the rep: {a.needs_info_request.reason}</Text> : null}
          {a.declined_reason && a.status === 'declined' ? <Text style={{ fontSize: 13, color: '#FF3B30', fontWeight: '700' }} {...tid('desk-declined-line')}>Declined: {a.declined_reason}</Text> : null}
          <ValueBreakdown colors={colors} output={w} marketRetail={a.market_retail ?? a.market?.snapshot?.estimated_retail} marketLabel={marketLabel(a.market?.snapshot)}
            approvedValue={a.approved_value} approvedBy={a.approved_by_name} approvedPending={a.status === 'submitted' || a.status === 'resubmitted'} showReferences={false} />
          {a.calculation ? <Text style={{ fontSize: 11.5, color: colors.textSecondary }} {...tid('desk-calc-line')}>Frozen at submission: calculation v{a.calculation.version} · rules {a.calculation.rules_source === 'default' ? "I'm On Social defaults" : `${a.calculation.rules_source} v${a.calculation.rules_version}`} · {when(a.calculation.created_at)}</Text> : null}
          <CustomerWantsCard colors={colors} a={a} />
          <ConditionCard colors={colors} inspection={a.inspection} />
          <MarketCard colors={colors} market={a.market} mileage={a.mileage_confirmed} />
          <ReferencesCard colors={colors} output={w} />
          <RepCard colors={colors} a={a} />
          <CustomerIntakeCard colors={colors} a={a} />
          <HistoryCard colors={colors} a={a} />
          {a.decisions?.length ? (
            <View style={{ borderRadius: 16, paddingHorizontal: 14, paddingVertical: 6, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('desk-decisions')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, paddingVertical: 8 }}>DECISIONS</Text>
              {a.decisions.map((d: any) => (
                <View key={d.id} style={{ paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border, gap: 2 }} {...tid(`desk-decision-${d.id}`)}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{DECISION_LABEL[d.action] || d.action}{d.manager_approved_value != null ? ` · ${money(d.manager_approved_value)}` : ''}{d.delta ? ` (${d.delta > 0 ? '+' : '-'}${money(Math.abs(d.delta))})` : ''}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{d.manager_name} · {when(d.decided_at)}{d.response_s != null ? ` · answered in ${ago(d.response_s)}` : ''}{d.reason ? ` · ${d.reason}` : ''}</Text>
                </View>
              ))}
            </View>
          ) : null}
          <ActivityCard colors={colors} rows={a.activity} />
          <TouchableOpacity onPress={() => router.push(`/contact/${a.contact_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, height: 44 }} {...tid('desk-open-contact')}>
            <Ionicons name="person" size={15} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Open {a.contact_name}</Text>
          </TouchableOpacity>
        </ScrollView>
        <DeskDecisionBar colors={colors} appraisal={a} onDecided={setA} showToast={showToast} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
