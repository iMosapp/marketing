import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';
import { money, miles } from '../appraisal/shared';

type Props = { contactId: string; colors: any };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const OWN: Record<string, string> = { owns: 'Still owns vehicle', traded: 'Traded in', sold: 'Sold elsewhere', unknown: 'Unknown' };

// Contact → Vehicles: every car we know they own, last appraisal, what we offered, what they wanted, and REAPPRAISE on the same vehicle.
export default function VehiclesSection({ contactId, colors }: Props) {
  const router = useRouter();
  const [data, setData] = useState<{ vehicles: any[]; can_appraise: boolean } | null>(null);
  const load = useCallback(() => { api.get(`/appraisals/vehicles/${contactId}`).then(r => setData(r.data)).catch(() => setData({ vehicles: [], can_appraise: false })); }, [contactId]);
  useEffect(() => { load(); }, [load]);
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
        const last = v.appraisals?.[0];
        return (
          <View key={v.id} style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10, gap: 6 }} {...tid(`vehicle-${v.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>{v.label}</Text>
              <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary }}>{OWN[v.ownership_status] || ''}</Text>
            </View>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{[v.vin ? `VIN ${v.vin}` : 'No VIN', v.current_mileage != null ? `${miles(v.current_mileage)} as of ${when(v.mileage_as_of)}` : null].filter(Boolean).join(' · ')}</Text>
            {last ? (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
                <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ color: colors.textSecondary }}>Last appraisal </Text>{when(last.created_at)}</Text>
                {last.approved_value ? <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ color: colors.textSecondary }}>Dealer offer </Text>{money(last.approved_value)}</Text> : null}
                {last.customer_expected_value ? <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ color: colors.textSecondary }}>Customer wanted </Text>{money(last.customer_expected_value)}</Text> : null}
                <Text style={{ fontSize: 12.5, color: GOLD, fontWeight: '700' }}>{v.appraisal_count} appraisal{v.appraisal_count === 1 ? '' : 's'}</Text>
              </View>
            ) : null}
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {last ? <TouchableOpacity onPress={() => router.push(`/appraisal/${last.id}` as any)} style={{ flex: 1, height: 36, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`vehicle-open-${v.id}`)}><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>Open latest</Text></TouchableOpacity> : null}
              {data.can_appraise ? <TouchableOpacity onPress={() => router.push(`/appraisals/new?contact_id=${contactId}&vehicle_id=${v.id}` as any)} style={{ flex: 1, height: 36, borderRadius: 10, backgroundColor: GOLD + '22', borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 5 }} {...tid(`vehicle-reappraise-${v.id}`)}><Ionicons name="refresh" size={13} color={GOLD} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Reappraise</Text></TouchableOpacity> : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}
