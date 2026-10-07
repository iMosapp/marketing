import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { money, miles } from '../../components/appraisal/shared';

type Group = 'all' | 'drafts' | 'waiting' | 'approved' | 'completed';
const GROUPS: { key: Group; label: string }[] = [{ key: 'all', label: 'Recent' }, { key: 'drafts', label: 'Drafts' }, { key: 'waiting', label: 'Waiting for manager' }, { key: 'approved', label: 'Approved' }, { key: 'completed', label: 'Completed' }];
const STATUS_LABEL: Record<string, string> = { draft: 'Draft', analyzing: 'Inspecting', ready: 'Ready', submitted: 'Waiting for manager', needs_info: 'Manager wants more', approved: 'Approved', changed: 'Approved (changed)', declined: 'Declined', presented: 'Presented', closed: 'Closed' };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');

// Trade Appraisal home: start one, pick up a draft, search by customer / VIN / stock / vehicle / salesperson.
export default function AppraisalsHome() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [group, setGroup] = useState<Group>('all');
  const [q, setQ] = useState('');
  const [rows, setRows] = useState<any[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = (await api.get('/appraisals', { params: { group: group === 'all' ? undefined : group, q: q.trim() || undefined } })).data;
      setRows(d.appraisals || []); setCounts(d.counts || {});
    } catch (e: any) {
      if (e?.response?.status === 403) { showToast(e.response.data?.detail || 'Not switched on for you', 'error', 5000); router.back(); return; }
      showToast(errText(e, 'Could not load appraisals'), 'error'); setRows([]);
    } finally { setRefreshing(false); }
  }, [group, q]);
  useEffect(() => { const t = setTimeout(load, q ? 250 : 0); return () => clearTimeout(t); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('appraisals-home')}>
      <ScreenHeader title="Trade Appraisal" subtitle="Scan, inspect, value, get it approved" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />} keyboardShouldPersistTaps="handled">
        <TouchableOpacity onPress={() => router.push('/appraisals/new' as any)} activeOpacity={0.85} style={{ borderRadius: 18, padding: 18, backgroundColor: GOLD, flexDirection: 'row', alignItems: 'center', gap: 14 }} {...tid('start-appraisal')}>
          <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: '#0B0B0D22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="car-sport" size={24} color="#0B0B0D" /></View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 18, fontWeight: '800', color: '#0B0B0D' }}>Start new appraisal</Text>
            <Text style={{ fontSize: 12.5, color: '#0B0B0D99', marginTop: 2 }}>Customer → VIN → mileage → inspection → value. About 3 minutes at the car.</Text>
          </View>
          <Ionicons name="arrow-forward" size={22} color="#0B0B0D" />
        </TouchableOpacity>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, height: 46, borderRadius: 14, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}>
          <Ionicons name="search" size={16} color={colors.textSecondary} />
          <TextInput value={q} onChangeText={setQ} placeholder="Customer, VIN, stock #, vehicle, salesperson" placeholderTextColor={colors.textSecondary} style={{ flex: 1, color: colors.text, fontSize: 14 }} autoCorrect={false} {...tid('appraisals-search')} />
          {q ? <TouchableOpacity onPress={() => setQ('')} {...tid('appraisals-search-clear')}><Ionicons name="close-circle" size={18} color={colors.textSecondary} /></TouchableOpacity> : null}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
          {GROUPS.map(g => { const on = group === g.key; const n = g.key === 'all' ? undefined : counts[g.key]; return (
            <TouchableOpacity key={g.key} onPress={() => setGroup(g.key)} style={{ height: 32, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD + '22' : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid(`appraisals-group-${g.key}`)}>
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{g.label}{typeof n === 'number' && n > 0 ? ` · ${n}` : ''}</Text>
            </TouchableOpacity>
          ); })}
        </ScrollView>

        {rows === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 24 }} /> : rows.length === 0 ? (
          <Text style={{ textAlign: 'center', color: colors.textSecondary, fontSize: 13, paddingVertical: 24, lineHeight: 19 }} {...tid('appraisals-empty')}>{q ? 'Nothing matches that search.' : group === 'all' ? 'No appraisals yet. Start one above; it takes about three minutes at the car.' : `Nothing ${GROUPS.find(g => g.key === group)?.label.toLowerCase()} right now.`}</Text>
        ) : rows.map(a => (
          <TouchableOpacity key={a.id} onPress={() => router.push(`/appraisal/${a.id}` as any)} activeOpacity={0.85} style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 6 }} {...tid(`appraisal-row-${a.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '1F', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={a.is_reappraisal ? 'refresh' : 'car-sport'} size={18} color={GOLD} /></View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1}>{a.vehicle_label || 'Vehicle not identified yet'}</Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{a.contact_name}{a.mileage_confirmed != null ? ` · ${miles(a.mileage_confirmed)}` : ''}{a.customer_expected_value ? ` · wants ${money(a.customer_expected_value)}` : ''}</Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 3 }}>
                <View style={{ backgroundColor: a.status === 'draft' ? colors.border : GOLD + '22', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 }}><Text style={{ fontSize: 10.5, fontWeight: '800', color: a.status === 'draft' ? colors.textSecondary : GOLD }}>{STATUS_LABEL[a.status] || a.status}</Text></View>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{when(a.updated_at)} · {a.user_name?.split(' ')[0]}</Text>
              </View>
            </View>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
