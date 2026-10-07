import React from 'react';
import { View, Text, TouchableOpacity, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { StepTitle, SourceTag, money, miles } from './shared';

type Props = { colors: any; appraisal: any; onEdit: (step: string) => void };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');

// Draft summary. Inspection, market data and manager approval arrive in the next releases; the record is already on the customer.
export const ReviewStep = ({ colors, appraisal, onEdit }: Props) => {
  const router = useRouter();
  const v = appraisal.vehicle || {};
  const i = appraisal.inspection;
  const insp = !i ? 'Not started' : ['queued', 'processing'].includes(i.status) ? 'Jessi is inspecting…' : i.status === 'failed' ? 'Last run failed — tap to retry'
    : i.final_overall_label ? `${i.final_overall_label}${i.overridden ? ' (overridden)' : ''} · ${i.confirmed} confirmed${i.pending ? `, ${i.pending} to review` : ''}${i.possible ? `, ${i.possible} possible` : ''}` : 'Media added, not analyzed';
  const Row = ({ icon, label, value, step, testId }: { icon: any; label: string; value: string; step?: string; testId: string }) => (
    <TouchableOpacity disabled={!step} onPress={() => step && onEdit(step)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(testId)}>
      <Ionicons name={icon} size={18} color={GOLD} />
      <Text style={{ width: 92, fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>{label.toUpperCase()}</Text>
      <Text style={{ flex: 1, fontSize: 15, fontWeight: '600', color: colors.text }} numberOfLines={2}>{value || '—'}</Text>
      {step ? <Ionicons name="create-outline" size={16} color={colors.textSecondary} /> : null}
    </TouchableOpacity>
  );
  return (
    <View style={{ gap: 12 }}>
      <StepTitle colors={colors} title="Draft saved" sub="Everything is on the customer's record. Next releases add market data and manager approval right here." />
      <View style={{ borderRadius: 16, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('review-card')}>
        <Row icon="car-sport" label="Vehicle" value={appraisal.vehicle_label || ''} step={appraisal.is_reappraisal ? undefined : 'identity'} testId="review-vehicle" />
        <Row icon="barcode-outline" label="VIN" value={appraisal.vin || 'No VIN on file'} testId="review-vin" />
        <Row icon="speedometer" label="Mileage" value={appraisal.mileage_confirmed != null ? miles(appraisal.mileage_confirmed) + (appraisal.mileage_detected != null && appraisal.mileage_detected !== appraisal.mileage_confirmed ? ` (Jessi read ${miles(appraisal.mileage_detected)})` : '') : ''} step="mileage" testId="review-mileage" />
        <Row icon="cash-outline" label="Customer wants" value={appraisal.customer_expected_value ? money(appraisal.customer_expected_value) : appraisal.expectation_asked === false ? 'Has not named a number' : ''} step="expectation" testId="review-expectation" />
        <Row icon="scan" label="Inspection" value={insp} step="inspection" testId="review-inspection" />
        <Row icon={appraisal.mode === 'customer_sent' ? 'cloud-upload-outline' : 'location-outline'} label="Captured" value={appraisal.mode_label} step={appraisal.vehicle_id ? undefined : 'mode'} testId="review-mode" />
        <Row icon="person-outline" label="Customer" value={appraisal.contact_name} testId="review-customer" />
        {appraisal.is_reappraisal ? <Row icon="refresh" label="Reappraisal" value={`Vehicle first appraised ${when(appraisal.history?.[appraisal.history.length - 1]?.created_at)}`} testId="review-reappraisal" /> : null}
      </View>
      {appraisal.media?.length ? (
        <View style={{ gap: 8 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>MEDIA · {appraisal.media.length}</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {appraisal.media.map((m: any) => (
              <View key={m.id} style={{ width: 104, gap: 4 }} {...tid(`review-media-${m.id}`)}>
                <View style={{ width: 104, height: 78, borderRadius: 10, overflow: 'hidden', backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }}>
                  {m.thumb_url ? <Image source={{ uri: resolvePhotoUrl(m.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : <Ionicons name={m.kind === 'video' ? 'videocam' : 'image'} size={22} color={GOLD} />}
                </View>
                <Text style={{ fontSize: 11, fontWeight: '700', color: colors.text }} numberOfLines={1}>{m.role_label}</Text>
                <SourceTag source={m.source} colors={colors} />
              </View>
            ))}
          </View>
        </View>
      ) : null}
      {appraisal.history?.length > 1 ? (
        <View style={{ gap: 6 }} {...tid('review-history')}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>APPRAISAL HISTORY</Text>
          {appraisal.history.map((h: any) => (
            <View key={h.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 }}>
              <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: h.id === appraisal.id ? GOLD : colors.border }} />
              <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{when(h.created_at)}{h.mileage_confirmed != null ? ` · ${miles(h.mileage_confirmed)}` : ''}{h.approved_value ? ` · Dealer offer ${money(h.approved_value)}` : ''}{h.customer_expected_value ? ` · Wanted ${money(h.customer_expected_value)}` : ''}{h.id === appraisal.id ? ' · this one' : ` · ${h.status}`}</Text>
            </View>
          ))}
        </View>
      ) : null}
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TouchableOpacity onPress={() => router.push(`/contact/${appraisal.contact_id}` as any)} style={{ flex: 1, height: 50, borderRadius: 14, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('review-open-contact')}>
          <Ionicons name="person" size={16} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Open {appraisal.contact_name?.split(' ')[0] || 'contact'}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => router.replace('/appraisals' as any)} style={{ flex: 1, height: 50, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('review-done')}>
          <Ionicons name="checkmark" size={18} color="#0B0B0D" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#0B0B0D' }}>Done for now</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};
