import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { money, miles } from '../../components/appraisal/shared';
import { OwnershipCard } from '../../components/appraisal/vehicle/OwnershipCard';
import { AppraisalHistoryList, ValueHistoryCard } from '../../components/appraisal/vehicle/VehicleHistory';

const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');

// One vehicle as a relationship record: who owns it, what we offered over time, what they wanted, and REAPPRAISE without re-entering the car.
export default function VehicleScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [v, setV] = useState<any | null>(null);
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setErr(null); setV((await api.get(`/appraisals/vehicle/${id}`)).data); }
    catch (e) { const t = errText(e, 'Could not open that vehicle'); setErr(t); showToast(t, 'error'); }
  }, [id]);
  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const setOwnership = async (status: string, note: string) => {
    try { setV((await api.put(`/appraisals/vehicle/${id}/ownership`, { status, note })).data); showToast('Vehicle updated', 'success'); }
    catch (e) { showToast(errText(e, 'Could not update the vehicle'), 'error', 5000); }
  };
  const reappraise = async () => {
    if (!v?.contact?.id) return;
    setStarting(true);
    try { const r = (await api.post('/appraisals', { contact_id: v.contact.id, mode: 'vehicle_here', vehicle_id: v.id })).data; router.push(`/appraisal/${r.appraisal.id}` as any); }
    catch (e) { showToast(errText(e, 'Could not start the reappraisal'), 'error', 5000); }
    finally { setStarting(false); }
  };

  if (!v) return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Vehicle" onBack={() => (router.canGoBack() ? router.back() : router.replace('/appraisals' as any))} />
      {err ? (
        <View style={{ padding: 24, alignItems: 'center', gap: 10 }} {...tid('vehicle-error')}>
          <Ionicons name="car-outline" size={34} color={colors.textSecondary} />
          <Text style={{ fontSize: 14, color: colors.text, textAlign: 'center' }}>{err}</Text>
          <TouchableOpacity onPress={() => router.replace('/appraisals' as any)} {...tid('vehicle-error-back')}><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Back to Trade Appraisal</Text></TouchableOpacity>
        </View>
      ) : <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} />}
    </SafeAreaView>
  );
  const last = v.last;
  const canReappraise = v.can_appraise && !v.open_appraisal_id && !['traded', 'sold', 'no_longer_owns'].includes(v.ownership_status);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('vehicle-screen')}>
      <ScreenHeader title={v.label || 'Vehicle'} subtitle={v.contact?.name || ''} onBack={() => (router.canGoBack() ? router.back() : router.replace(v.contact?.id ? `/contact/${v.contact.id}` : '/appraisals' as any))} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }}>
        <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 6 }} {...tid('vehicle-identity')}>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{[v.vin ? `VIN ${v.vin}` : 'No VIN on file', v.trim ? null : null, v.current_mileage != null ? `${miles(v.current_mileage)} as of ${when(v.mileage_as_of)}` : 'No mileage yet'].filter(Boolean).join(' · ')}</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>First seen {when(v.first_seen)} · {v.appraisal_count} appraisal{v.appraisal_count === 1 ? '' : 's'}{v.contact?.phone ? ` · ${v.contact.phone}` : ''}</Text>
          {v.contact?.id ? <TouchableOpacity onPress={() => router.push(`/contact/${v.contact.id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start' }} {...tid('vehicle-open-contact')}><Ionicons name="person" size={13} color={GOLD} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Open {v.contact.name?.split(' ')[0] || 'contact'}</Text></TouchableOpacity> : null}
        </View>

        {last ? (
          <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid('vehicle-last-card')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>LAST APPRAISAL · {when(last.date)}{last.is_reappraisal ? ' · REAPPRAISAL' : ''}</Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Num colors={colors} label="SUGGESTED" value={last.suggested_acv ? money(last.suggested_acv) : '—'} color={GOLD} />
              <Num colors={colors} label="OFFERED" value={last.approved_value ? money(last.approved_value) : '—'} sub={last.approved_by_name ? `by ${last.approved_by_name}` : undefined} color="#34C759" />
              <Num colors={colors} label="WANTED" value={last.customer_expected_value ? money(last.customer_expected_value) : '—'} sub={last.expectation_gap ? `${money(last.expectation_gap)} gap` : undefined} color="#FF9500" />
            </View>
            <Text style={{ fontSize: 12.5, color: colors.text }} {...tid('vehicle-last-outcome')}>{last.outcome_label ? `Customer: ${last.outcome_label}` : last.status_label}{last.mileage != null ? ` · ${miles(last.mileage)}` : ''}{last.condition_label ? ` · ${last.condition_label}` : ''}</Text>
          </View>
        ) : null}

        {v.opportunity ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, borderRadius: 14, backgroundColor: '#FF950014', borderWidth: 1, borderColor: '#FF950066' }} {...tid('vehicle-opportunity')}>
            <Ionicons name="sparkles" size={16} color="#FF9500" /><Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: colors.text, lineHeight: 18 }}>{v.opportunity.title}</Text>
          </View>
        ) : null}

        {canReappraise ? (
          <TouchableOpacity onPress={reappraise} disabled={starting} activeOpacity={0.85} style={{ borderRadius: 16, padding: 16, backgroundColor: GOLD, flexDirection: 'row', alignItems: 'center', gap: 12, opacity: starting ? 0.6 : 1 }} {...tid('vehicle-reappraise')}>
            <Ionicons name="refresh" size={22} color="#0B0B0D" />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 16, fontWeight: '800', color: '#0B0B0D' }}>Reappraise</Text>
              <Text style={{ fontSize: 12, color: '#0B0B0D99', marginTop: 2 }}>Same vehicle, new appraisal. Only fresh mileage, condition and market.</Text>
            </View>
            {starting ? <ActivityIndicator color="#0B0B0D" /> : <Ionicons name="arrow-forward" size={20} color="#0B0B0D" />}
          </TouchableOpacity>
        ) : v.open_appraisal_id ? (
          <TouchableOpacity onPress={() => router.push(`/appraisal/${v.open_appraisal_id}` as any)} style={{ borderRadius: 16, padding: 14, backgroundColor: GOLD + '22', borderWidth: 1, borderColor: GOLD, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('vehicle-continue')}>
            <Ionicons name="play" size={18} color={GOLD} /><Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: GOLD }}>An appraisal is in progress. Continue it.</Text><Ionicons name="chevron-forward" size={18} color={GOLD} />
          </TouchableOpacity>
        ) : null}

        <OwnershipCard colors={colors} vehicle={v} onSet={setOwnership} canEdit={!!v.can_appraise} />
        <ValueHistoryCard colors={colors} value={v.value_history} />
        <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 12 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>APPRAISAL HISTORY · OLDEST FIRST</Text>
          <AppraisalHistoryList colors={colors} history={v.history || []} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const Num = ({ colors, label, value, sub, color }: { colors: any; label: string; value: string; sub?: string; color: string }) => (
  <View style={{ flex: 1, gap: 1 }}>
    <Text style={{ fontSize: 9.5, fontWeight: '800', color, letterSpacing: 0.5 }}>{label}</Text>
    <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} numberOfLines={1}>{value}</Text>
    {sub ? <Text style={{ fontSize: 10.5, color: colors.textSecondary }} numberOfLines={1}>{sub}</Text> : null}
  </View>
);
