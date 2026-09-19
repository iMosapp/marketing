/**
 * Admin -> Organizations -> [Organization] -> Communications -> Twilio.
 * Super admin: everything (subaccount, SIDs, provisioning, suspend / release, history). Org admin: the simplified Communications
 * view of their own organization (numbers, assignments, compliance + messaging status). Twilio stays invisible infrastructure.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useAuthStore } from '../../../store/authStore';
import { ScreenHeader, HeaderTextButton } from '../../../components/common/ScreenHeader';
import api from '../../../services/api';
import { GOLD, Pill, STATUS_COLOR, getS, tid } from '../../../components/org-twilio/shared';
import { StatusGrid } from '../../../components/org-twilio/StatusGrid';
import { ProvisioningCard } from '../../../components/org-twilio/ProvisioningCard';
import { NumbersTable } from '../../../components/org-twilio/NumbersTable';
import { AddNumberSheet } from '../../../components/org-twilio/AddNumberSheet';
import { UsageCard, AuditList } from '../../../components/org-twilio/UsageAudit';

export default function OrgTwilio() {
  const { orgId } = useLocalSearchParams<{ orgId: string }>();
  const { colors } = useThemeStore();
  const user = useAuthStore((st) => st.user);
  const router = useRouter();
  const s = getS(colors);
  const [view, setView] = useState<any>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [adding, setAdding] = useState(false);
  const isSuper = user?.role === 'super_admin';

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      const r = await api.get(`/admin/organizations/${orgId}/twilio`);
      setView(r.data);
      setError('');
    } catch (e: any) { setError(e?.response?.data?.detail || 'Could not load this organization.'); }
    finally { setRefreshing(false); }
  }, [orgId]);
  useEffect(() => { load(true); }, [load]);

  if (error) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <ScreenHeader title="Communications" testID="org-twilio-header" />
        <Text style={{ margin: 24, color: '#FF3B30', fontSize: 14 }} {...tid('org-twilio-error')}>{error}</Text>
      </SafeAreaView>
    );
  }
  if (!view) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <ScreenHeader title="Communications" testID="org-twilio-header" />
        <ActivityIndicator size="large" color={GOLD} style={{ marginTop: 80 }} />
      </SafeAreaView>
    );
  }
  const compliance: any[] = view.compliance || [];
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScreenHeader title={view.organization?.name || 'Organization'} subtitle={isSuper ? `Communications · Twilio · ${(view.settings?.mode || 'dry_run').replace('_', ' ')}` : 'Communications · texting'} testID="org-twilio-header"
        right={isSuper ? <HeaderTextButton label="Numbers" onPress={() => router.push('/admin/twilio-numbers' as any)} testID="org-twilio-all-numbers" /> : undefined} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load()} tintColor={GOLD} />} {...tid('org-twilio-screen')}>
        <StatusGrid view={view} colors={colors} s={s} />
        <ProvisioningCard orgId={orgId!} view={view} colors={colors} s={s} onChanged={(v) => setView(v)} />
        <NumbersTable orgId={orgId!} view={view} colors={colors} s={s} onAdd={() => setAdding(true)} onChanged={() => load(true)} />

        <View style={s.card} {...tid('compliance-list-card')}>
          <Text style={s.cardTitle}>Compliance by location</Text>
          {compliance.length === 0 && <Text style={s.hint} {...tid('compliance-list-empty')}>No locations on this organization yet.</Text>}
          {compliance.map((c: any, i: number) => {
            const status = c.stage === 'complete' ? 'APPROVED' : c.stage === 'draft' ? (c.missing > 0 ? 'INFORMATION_REQUIRED' : 'NOT_STARTED') : ['rejected', 'error'].includes(c.status) ? 'REJECTED' : 'PENDING';
            const color = STATUS_COLOR[status];
            return (
              <TouchableOpacity key={c.store_id} onPress={() => router.push(`/admin/compliance/${c.store_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }} {...tid(`compliance-store-${c.store_id}`)}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{c.store_name}{view.compliance_store_id === c.store_id ? ' · backs this org' : ''}</Text>
                  <Text style={{ fontSize: 12, color: colors.textTertiary }} numberOfLines={2}>{c.stage_label}{c.status && c.stage !== 'draft' ? ` · ${c.status}` : ''} · {c.next_action}</Text>
                </View>
                <Pill label={status === 'APPROVED' ? 'Approved' : status === 'PENDING' ? 'In review' : status === 'REJECTED' ? 'Rejected' : status === 'INFORMATION_REQUIRED' ? 'Info required' : 'Not started'} color={color} />
                <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} />
              </TouchableOpacity>
            );
          })}
        </View>

        <UsageCard usage={view.usage} colors={colors} s={s} />
        <AuditList entries={view.audit} colors={colors} s={s} />
        {isSuper && view.webhooks && (
          <View style={s.card} {...tid('webhooks-card')}>
            <Text style={s.cardTitle}>Webhooks set on every number</Text>
            <Text style={s.mono}>SMS · {view.webhooks.sms}</Text>
            <Text style={s.mono}>Voice · {view.webhooks.voice}</Text>
            <Text style={s.mono}>Status · {view.webhooks.status}</Text>
            <Text style={s.hint}>Webhook validation: {view.settings?.enforce_ready ? 'texting gated on MESSAGING READY' : 'texting not gated'}. Flags live under Phone Numbers → Settings.</Text>
          </View>
        )}
      </ScrollView>
      <AddNumberSheet orgId={orgId!} view={view} colors={colors} s={s} visible={adding} onClose={() => setAdding(false)} onBought={() => load(true)} />
    </SafeAreaView>
  );
}
