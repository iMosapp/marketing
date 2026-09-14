import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import api, { API_BASE_URL } from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { ClientSheet } from '../../../components/mystery-shops/ClientSheet';
import { PeopleTab } from '../../../components/mystery-shops/PeopleTab';
import { CallsTab } from '../../../components/mystery-shops/CallsTab';
import { ChallengesTab } from '../../../components/mystery-shops/ChallengesTab';
import { BillingTab } from '../../../components/mystery-shops/BillingTab';
import { ReportView, openUrl, type Report } from '../../../components/mystery-shops/ReportView';
import { AutoReportCard, type AutoReport } from '../../../components/mystery-shops/AutoReportCard';
import { Chip, GoldButton, monthKey, monthLabel, shiftMonth, perMonthText, deptsOfClient, loadIndustries, GOLD, RED, tid, type Client, type Person } from '../../../components/mystery-shops/shared';

const TABS = [['people', 'People'], ['calls', 'Shops'], ['challenges', 'Challenges'], ['report', 'Report'], ['billing', 'Billing']] as const;
type Tab = typeof TABS[number][0];

export default function MysteryShopClient() {
  const router = useRouter();
  const { id, tab: tabParam } = useLocalSearchParams<{ id: string; tab?: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [client, setClient] = useState<Client | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [reportUrl, setReportUrl] = useState('');
  const [kickoffUrl, setKickoffUrl] = useState('');
  const [kickoff, setKickoff] = useState<any>({});
  const [autoReport, setAutoReport] = useState<AutoReport | null>(null);
  const [tab, setTab] = useState<Tab>((TABS.some(t => t[0] === tabParam) ? tabParam : 'people') as Tab);
  const [month, setMonth] = useState(monthKey());
  const [edit, setEdit] = useState(false);
  const [callsKey, setCallsKey] = useState(0);
  const [report, setReport] = useState<Report | null>(null);
  const [reportBusy, setReportBusy] = useState(false);

  const load = useCallback(async () => {
    loadIndustries();
    try { const r = await api.get(`/shop-clients/${id}`); setClient(r.data.client); setPeople(r.data.people); setReportUrl(r.data.report_url); setKickoffUrl(r.data.kickoff_url || ''); setKickoff(r.data.kickoff || {}); setAutoReport(r.data.auto_report || null); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); router.back(); }
  }, [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  const loadReport = useCallback(async () => {
    setReportBusy(true);
    try { const r = await api.get(`/shop-clients/${id}/report`, { params: { month } }); setReport(r.data); } catch { setReport(null); }
    finally { setReportBusy(false); }
  }, [id, month]);
  useEffect(() => { if (tab === 'report') loadReport(); }, [tab, month, loadReport]);

  const pause = () => client && showConfirm(client.active ? 'Pause this client?' : 'Resume this client?', client.active ? 'Scheduled shops stop dialing until you resume.' : 'The planner picks the month back up.', async () => {
    await api.put(`/shop-clients/${client.id}`, { active: !client.active }); load();
  }, undefined, client.active ? 'Pause' : 'Resume');
  const remove = () => client && showConfirm(`Delete ${client.name}?`, 'People, scheduled shops and the report link are removed. Completed evaluations are kept.', async () => {
    await api.delete(`/shop-clients/${client.id}`); router.back();
  }, undefined, 'Delete');
  const copyReport = async () => { await Clipboard.setStringAsync(reportUrl); showToast('Report link copied', 'success'); };
  const rotate = () => showConfirm('New report link?', 'The old link stops working. Send the new one to the store.', async () => { const r = await api.post(`/shop-clients/${id}/report/rotate-link`); setReportUrl(r.data.report_url); showToast('New link ready', 'success'); }, undefined, 'Replace link');

  if (!client) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Client" testID="shop-client-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const tabs = client.demo ? TABS.filter(t => t[0] !== 'billing') : TABS;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={client.name} subtitle={client.demo ? 'Anyone you shop without a client account · not billed' : `${client.industry && client.industry !== 'automotive' ? `${client.industry_label} · ` : ''}${perMonthText(client.plan.per_month, ' + ', deptsOfClient(client))} / mo${client.active ? '' : ' · PAUSED'}`} testID="shop-client-header"
        right={client.demo ? undefined : <View style={{ flexDirection: 'row' }}><HeaderIconButton icon={client.active ? 'pause-circle-outline' : 'play-circle-outline'} onPress={pause} testID="shop-client-pause" /><HeaderIconButton icon="create-outline" onPress={() => setEdit(true)} testID="shop-client-edit" /></View>} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 8, paddingVertical: 8 }} style={{ flexGrow: 0, flexShrink: 0 }}>
        {tabs.map(([k, l]) => <Chip key={k} label={l} active={tab === k} onPress={() => setTab(k)} colors={colors} testID={`shop-tab-${k}`} />)}
      </ScrollView>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 16 }} keyboardShouldPersistTaps="handled">
        {tab === 'people' && <PeopleTab client={client} people={people} colors={colors} onChanged={load} onShopStarted={() => { setCallsKey(k => k + 1); setTab('calls'); }} kickoffUrl={client.demo ? undefined : kickoffUrl} kickoff={kickoff} />}
        {tab === 'calls' && <CallsTab client={client} colors={colors} month={month} onMonth={setMonth} refreshKey={callsKey} onChanged={load} />}
        {tab === 'challenges' && <ChallengesTab client={client} colors={colors} />}
        {tab === 'report' && (
          <View style={{ gap: 14 }}>
            <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: GOLD + '66', padding: 14, gap: 10 }} {...tid('report-share-card')}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Store report link <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· no login, send it to the GM</Text></Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1} {...tid('report-share-url')}>{reportUrl}</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity onPress={copyReport} style={{ flex: 1, height: 38, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('report-copy-link')}><Ionicons name="link" size={14} color="#111" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Copy link</Text></TouchableOpacity>
                <TouchableOpacity onPress={() => openUrl(`${API_BASE_URL}/public/shop-report/${client.report_token}.pdf?month=${month}`)} style={{ flex: 1, height: 38, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('report-open-pdf')}><Ionicons name="document" size={14} color={colors.text} /><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>PDF</Text></TouchableOpacity>
                <TouchableOpacity onPress={rotate} style={{ width: 38, height: 38, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('report-rotate-link')}><Ionicons name="refresh" size={16} color={colors.text} /></TouchableOpacity>
              </View>
            </View>
            {!client.demo && autoReport && <AutoReportCard clientId={String(id)} value={autoReport} month={month} colors={colors} onChanged={setAutoReport} />}
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <TouchableOpacity onPress={() => setMonth(shiftMonth(month, -1))} hitSlop={8} {...tid('report-month-prev')}><Ionicons name="chevron-back" size={22} color={GOLD} /></TouchableOpacity>
              <Text style={{ flex: 1, textAlign: 'center', fontSize: 15, fontWeight: '800', color: colors.text }} {...tid('report-month-label')}>{monthLabel(month)}</Text>
              <TouchableOpacity onPress={() => setMonth(shiftMonth(month, 1))} hitSlop={8} {...tid('report-month-next')}><Ionicons name="chevron-forward" size={22} color={GOLD} /></TouchableOpacity>
            </View>
            {reportBusy || !report ? <ActivityIndicator color={GOLD} /> : <ReportView report={report} colors={colors} personPath={targetId => `/shop-clients/${id}/people/${targetId}/history`} />}
          </View>
        )}
        {tab === 'billing' && <BillingTab client={client} colors={colors} onChanged={load} />}
        {tab === 'people' && <GoldButton label="Delete client" onPress={remove} testID="shop-client-delete" outline color={RED} icon="trash-outline" />}
      </ScrollView>
      <ClientSheet visible={edit} onClose={() => setEdit(false)} colors={colors} client={client} onSaved={() => load()} />
    </SafeAreaView>
  );
}
