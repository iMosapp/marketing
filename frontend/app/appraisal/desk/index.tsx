import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../../components/inbox/ownership';
import { money, miles } from '../../../components/appraisal/shared';

type Group = 'waiting' | 'sent_back' | 'decided';
const GROUPS: { key: Group; label: string }[] = [{ key: 'waiting', label: 'Waiting' }, { key: 'sent_back', label: 'Sent back' }, { key: 'decided', label: 'Decided' }];
const ago = (s?: number | null) => (s == null ? '' : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : s < 86400 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} d`);
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// The desk manager's queue: who is waiting (oldest first), what the system suggests, what the customer wants, who sent it.
export default function AppraisalDesk() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [group, setGroup] = useState<Group>('waiting');
  const [q, setQ] = useState('');
  const [rows, setRows] = useState<any[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = (await api.get('/appraisals/desk', { params: { group, q: q.trim() || undefined } })).data;
      setRows(d.appraisals || []); setCounts(d.counts || {});
    } catch (e: any) {
      if (e?.response?.status === 403) { showToast(e.response.data?.detail || 'Not switched on for you', 'error', 5000); if (router.canGoBack()) router.back(); else router.replace('/appraisals' as any); return; }
      showToast(errText(e, 'Could not load the desk'), 'error'); setRows([]);
    } finally { setRefreshing(false); }
  }, [group, q]);
  useEffect(() => { const t = setTimeout(load, q ? 250 : 0); return () => clearTimeout(t); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('appraisal-desk')}>
      <ScreenHeader title="Appraisal Desk" subtitle={counts.waiting ? `${counts.waiting} waiting for a decision` : 'Nothing waiting'} onBack={() => (router.canGoBack() ? router.back() : router.replace('/appraisals' as any))}
        right={<HeaderIconButton icon="options-outline" onPress={() => router.push('/admin/appraisal-rules' as any)} testID="desk-rules-btn" />} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', gap: 6 }}>
          {GROUPS.map(g => { const on = group === g.key; const n = counts[g.key]; return (
            <TouchableOpacity key={g.key} onPress={() => setGroup(g.key)} style={{ flex: 1, height: 36, borderRadius: 18, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD + '22' : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid(`desk-group-${g.key}`)}>
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{g.label}{typeof n === 'number' && n > 0 ? ` · ${n}` : ''}</Text>
            </TouchableOpacity>
          ); })}
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, height: 44, borderRadius: 14, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}>
          <Ionicons name="search" size={16} color={colors.textSecondary} />
          <TextInput value={q} onChangeText={setQ} placeholder="Customer, vehicle, VIN, salesperson" placeholderTextColor={colors.textSecondary} style={{ flex: 1, color: colors.text, fontSize: 14 }} autoCorrect={false} {...tid('desk-search')} />
        </View>
        {rows === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 24 }} /> : rows.length === 0 ? (
          <Text style={{ textAlign: 'center', color: colors.textSecondary, fontSize: 13, paddingVertical: 28, lineHeight: 19 }} {...tid('desk-empty')}>{group === 'waiting' ? 'Nothing waiting. Reps submit from the Value step; you get a notification the moment they do.' : group === 'sent_back' ? 'Nothing sent back to a rep right now.' : 'No decisions yet.'}</Text>
        ) : rows.map(a => (
          <TouchableOpacity key={a.id} onPress={() => router.push(`/appraisal/desk/${a.id}` as any)} activeOpacity={0.85} style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: a.manager_review_required && group === 'waiting' ? '#FF9500' : colors.border, gap: 10 }} {...tid(`desk-row-${a.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} numberOfLines={1}>{a.contact_name}</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{a.vehicle_label || 'Vehicle not identified'}{a.mileage_confirmed != null ? ` · ${miles(a.mileage_confirmed)}` : ''}</Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 3 }}>
                {group === 'waiting' ? <Text style={{ fontSize: 11.5, fontWeight: '800', color: (a.waiting_s || 0) > 3600 ? '#FF3B30' : colors.textSecondary }} {...tid(`desk-waiting-${a.id}`)}>{ago(a.waiting_s)} waiting</Text>
                  : <View style={{ backgroundColor: GOLD + '22', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 }}><Text style={{ fontSize: 10.5, fontWeight: '800', color: GOLD }}>{a.status_label}</Text></View>}
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{a.user_name?.split(' ')[0]} · {when(a.submitted_at || a.updated_at)}</Text>
              </View>
            </View>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Num colors={colors} label="SUGGESTED" value={a.suggested_acv != null ? money(a.suggested_acv) : 'Manager sets'} color={GOLD} />
              <Num colors={colors} label="CUSTOMER WANTS" value={a.customer_expected_value ? money(a.customer_expected_value) : 'No number'} sub={a.expectation_gap != null ? `${a.expectation_gap >= 0 ? '+' : '-'}${money(Math.abs(a.expectation_gap))} vs suggested` : undefined} color="#FF9500" />
              {a.approved_value != null ? <Num colors={colors} label="APPROVED" value={money(a.approved_value)} color="#34C759" /> : <Num colors={colors} label="MARKET" value={a.market_retail ? money(a.market_retail) : '—'} sub={a.market_retail && !a.market_live ? 'dev data' : undefined} color="#30B0C7" />}
            </View>
            {a.manager_review_required && group === 'waiting' ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid(`desk-flag-${a.id}`)}>
                <Ionicons name="eye" size={13} color="#FF9500" /><Text style={{ flex: 1, fontSize: 12, fontWeight: '700', color: '#FF9500' }} numberOfLines={2}>{(a.review_reasons || []).join(' · ') || 'Needs your eyes'}</Text>
              </View>
            ) : null}
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const Num = ({ colors, label, value, sub, color }: { colors: any; label: string; value: string; sub?: string; color: string }) => (
  <View style={{ flex: 1, gap: 1 }}>
    <Text style={{ fontSize: 9.5, fontWeight: '800', color, letterSpacing: 0.5 }}>{label}</Text>
    <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} numberOfLines={1}>{value}</Text>
    {sub ? <Text style={{ fontSize: 10.5, color: colors.textSecondary }} numberOfLines={1}>{sub}</Text> : null}
  </View>
);
