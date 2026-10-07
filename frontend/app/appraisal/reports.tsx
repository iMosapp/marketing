import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { ReportFilters, Filters } from '../../components/appraisal/reports/ReportFilters';
import { StatTiles, BreakdownTable, FollowUpList, fmtS } from '../../components/appraisal/reports/ReportParts';

type Tab = 'numbers' | 'followup';

// Manager Trade Reports: facts (counts, averages, rates, breakdowns) and a follow-up view of opportunities. No scoring; the numbers speak.
export default function TradeReports() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>('numbers');
  const [filters, setFilters] = useState<Filters>({ days: 90 });
  const [summary, setSummary] = useState<any | null>(null);
  const [follow, setFollow] = useState<any | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const bail = (e: any) => {
    if (e?.response?.status === 403) { showToast(e.response.data?.detail || 'Managers only', 'error', 5000); if (router.canGoBack()) router.back(); else router.replace('/appraisals' as any); return true; }
    return false;
  };
  const loadSummary = useCallback(async () => {
    try {
      const params: any = { store_id: filters.store_id, user_id: filters.user_id, manager_id: filters.manager_id, outcome: filters.outcome, make: filters.make };
      if (filters.days) params.date_from = new Date(Date.now() - filters.days * 86400000).toISOString();
      setSummary((await api.get('/appraisals/reports/summary', { params })).data);
    } catch (e: any) { if (!bail(e)) showToast(errText(e, 'Could not load the report'), 'error'); }
    finally { setRefreshing(false); }
  }, [filters]);
  const loadFollow = useCallback(async () => {
    try { setFollow((await api.get('/appraisals/reports/followup')).data); }
    catch (e: any) { if (!bail(e)) showToast(errText(e, 'Could not load follow-ups'), 'error'); }
    finally { setRefreshing(false); }
  }, []);
  useEffect(() => { loadSummary(); }, [loadSummary]);
  useEffect(() => { if (tab === 'followup' && !follow) loadFollow(); }, [tab]);

  const set = (p: Partial<Filters>) => setFilters(f => ({ ...f, ...p }));
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('trade-reports')}>
      <ScreenHeader title="Trade Reports" subtitle={summary ? `${summary.counts.started} appraisal${summary.counts.started === 1 ? '' : 's'} in view` : 'Appraisal numbers and follow-ups'} onBack={() => (router.canGoBack() ? router.back() : router.replace('/appraisals' as any))}
        right={<HeaderIconButton icon="briefcase-outline" onPress={() => router.push('/appraisal/desk' as any)} testID="reports-desk-btn" />} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); tab === 'numbers' ? loadSummary() : loadFollow(); }} tintColor={GOLD} />}>
        <View style={{ flexDirection: 'row', gap: 6 }}>
          {([['numbers', 'Numbers'], ['followup', 'Follow-up']] as [Tab, string][]).map(([k, label]) => { const on = tab === k; return (
            <TouchableOpacity key={k} onPress={() => setTab(k)} style={{ flex: 1, height: 36, borderRadius: 18, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD + '22' : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid(`reports-tab-${k}`)}>
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{label}{k === 'followup' && follow ? ` · ${Object.values(follow.counts as Record<string, number>).reduce((a, b) => a + b, 0)}` : ''}</Text>
            </TouchableOpacity>
          ); })}
        </View>

        {tab === 'numbers' ? (!summary ? <ActivityIndicator color={GOLD} style={{ marginTop: 24 }} /> : (
          <>
            <ReportFilters colors={colors} filters={filters} set={set} options={summary.options} />
            <StatTiles colors={colors} counts={summary.counts} averages={summary.averages} rates={summary.rates} />
            <BreakdownTable colors={colors} title="By salesperson" rows={summary.by_salesperson} kind="rep" testId="report-by-rep" />
            <BreakdownTable colors={colors} title="By desk manager" rows={summary.by_manager} kind="manager" testId="report-by-manager" />
            <BreakdownTable colors={colors} title="By make" rows={summary.by_make} kind="make" testId="report-by-make" />
            <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16, textAlign: 'center' }}>Counts and averages only, for the appraisals you can see. Desk response = time from submit to the first decision{summary.averages.manager_response_s != null ? ` (${fmtS(summary.averages.manager_response_s)} on average)` : ''}.</Text>
          </>
        )) : (!follow ? <ActivityIndicator color={GOLD} style={{ marginTop: 24 }} /> : (
          <>
            <FollowUpList colors={colors} title="Waiting too long" hint={`Submitted more than ${Math.round(follow.thresholds.waiting_s / 3600)} hours ago with no decision.`} items={follow.waiting_too_long} kind="waiting" testId="followup-waiting" />
            <FollowUpList colors={colors} title="Large customer gaps" hint={`Customer wanted at least $${follow.thresholds.gap.toLocaleString()} more than we offered (last 90 days).`} items={follow.large_gaps} kind="gap" testId="followup-gaps" />
            <FollowUpList colors={colors} title="Large manager adjustments" hint={`Desk moved the value by $${follow.thresholds.adjustment.toLocaleString()} or ${follow.thresholds.adjustment_pct}% or more.`} items={follow.large_adjustments} kind="adjustment" testId="followup-adjustments" />
            <FollowUpList colors={colors} title="Wants more" hint="Closed as wants more in the last 6 months. A call plus a fresh value can bring these back." items={follow.wants_more} kind="outcome" testId="followup-wants-more" />
            <FollowUpList colors={colors} title="Still thinking" hint="Closed as thinking about it in the last 6 months." items={follow.thinking} kind="outcome" testId="followup-thinking" />
            <FollowUpList colors={colors} title="Vehicles to revisit" hint="Still owned, last value 90+ days old, no open appraisal." items={follow.revisit} kind="revisit" testId="followup-revisit" />
          </>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
