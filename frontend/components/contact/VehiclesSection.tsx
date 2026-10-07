import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';
import { money, miles } from '../appraisal/shared';

type Props = { contactId: string; colors: any };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const OWN_COLOR: Record<string, string> = { owns: '#34C759', traded: GOLD, sold: '#8E8E93', no_longer_owns: '#8E8E93', unknown: '#FF9500' };

// Contact → Vehicles: long-term records. Ownership, trade intent, the last numbers, a reappraisal nudge, and REAPPRAISE on the same vehicle.
export default function VehiclesSection({ contactId, colors }: Props) {
  const router = useRouter();
  const [data, setData] = useState<{ vehicles: any[]; can_appraise: boolean } | null>(null);
  const load = useCallback(() => { api.get(`/appraisals/vehicles/${contactId}`).then(r => setData(r.data)).catch(() => setData({ vehicles: [], can_appraise: false })); }, [contactId]);
  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  if (!data || (!data.vehicles.length && !data.can_appraise)) return null;
  return (
    <View style={{ marginHorizontal: 16, marginTop: 12, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 }} {...tid('vehicles-section')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="car-sport" size={16} color={GOLD} />
        <Text style={{ flex: 1, fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>VEHICLES{data.vehicles.length ? ` · ${data.vehicles.length}` : ''}</Text>
        {data.can_appraise ? (
          <TouchableOpacity onPress={() => router.push(`/appraisals/new?contact_id=${contactId}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, height: 30, paddingHorizontal: 11, borderRadius: 15, backgroundColor: GOLD }} {...tid('vehicles-appraise')}>
            <Ionicons name="add" size={14} color="#0B0B0D" /><Text style={{ fontSize: 12, fontWeight: '800', color: '#0B0B0D' }}>Appraise a trade</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      {data.vehicles.length === 0 ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('vehicles-empty')}>No vehicles on file yet. Appraise a trade and it lands here with its history.</Text> : data.vehicles.map(v => {
        const last = v.last;
        const ownColor = OWN_COLOR[v.ownership_status] || colors.textSecondary;
        return (
          <TouchableOpacity key={v.id} onPress={() => router.push(`/vehicle/${v.id}` as any)} activeOpacity={0.85} style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10, gap: 6 }} {...tid(`vehicle-${v.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>{v.label}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: ownColor + '22', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 }} {...tid(`vehicle-ownership-${v.id}`)}>
                <Text style={{ fontSize: 10.5, fontWeight: '800', color: ownColor }}>{v.ownership_label}</Text>
              </View>
            </View>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{[v.vin ? `VIN ${v.vin_masked || v.vin}` : 'No VIN', v.current_mileage != null ? `${miles(v.current_mileage)} as of ${when(v.mileage_as_of)}` : null].filter(Boolean).join(' · ')}</Text>
            {v.trade_intent_label ? <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }} {...tid(`vehicle-intent-${v.id}`)}>{v.trade_intent_label}{v.trade_intent_status === 'accepted' && v.ownership_status === 'owns' ? ' · trade not confirmed yet' : ''}</Text> : null}
            {last ? (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }} {...tid(`vehicle-last-${v.id}`)}>
                <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ color: colors.textSecondary }}>Last </Text>{when(last.date)}{last.is_reappraisal ? ' (reappraisal)' : ''}</Text>
                {last.mileage != null ? <Text style={{ fontSize: 12.5, color: colors.text }}>{miles(last.mileage)}</Text> : null}
                {last.suggested_acv ? <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ color: colors.textSecondary }}>Suggested </Text>{money(last.suggested_acv)}</Text> : null}
                {last.approved_value ? <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ color: colors.textSecondary }}>Offered </Text>{money(last.approved_value)}</Text> : null}
                {last.customer_expected_value ? <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ color: colors.textSecondary }}>Wanted </Text>{money(last.customer_expected_value)}</Text> : null}
                <Text style={{ fontSize: 12.5, color: GOLD, fontWeight: '700' }}>{last.outcome_label || last.status_label} · {v.appraisal_count} appraisal{v.appraisal_count === 1 ? '' : 's'}</Text>
              </View>
            ) : null}
            {v.opportunity ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, borderRadius: 10, backgroundColor: '#FF950014', borderWidth: 1, borderColor: '#FF950055' }} {...tid(`vehicle-opportunity-${v.id}`)}>
                <Ionicons name="sparkles" size={13} color="#FF9500" /><Text style={{ flex: 1, fontSize: 12, fontWeight: '700', color: colors.text }}>Potential reappraisal · {v.opportunity.title}</Text>
              </View>
            ) : null}
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <TouchableOpacity onPress={() => router.push(`/vehicle/${v.id}` as any)} style={{ flex: 1, height: 36, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`vehicle-open-${v.id}`)}><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>History</Text></TouchableOpacity>
              {data.can_appraise && !v.open_appraisal_id ? <TouchableOpacity onPress={() => router.push(`/appraisals/new?contact_id=${contactId}&vehicle_id=${v.id}` as any)} style={{ flex: 1, height: 36, borderRadius: 10, backgroundColor: GOLD + '22', borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 5 }} {...tid(`vehicle-reappraise-${v.id}`)}><Ionicons name="refresh" size={13} color={GOLD} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Reappraise</Text></TouchableOpacity> : null}
              {v.open_appraisal_id ? <TouchableOpacity onPress={() => router.push(`/appraisal/${v.open_appraisal_id}` as any)} style={{ flex: 1, height: 36, borderRadius: 10, backgroundColor: GOLD + '22', borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid(`vehicle-continue-${v.id}`)}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Continue appraisal</Text></TouchableOpacity> : null}
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}
