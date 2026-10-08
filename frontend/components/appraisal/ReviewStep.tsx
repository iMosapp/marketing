import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, tid } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { StepTitle, SourceTag, money, miles } from './shared';
import { SubmitPanel } from './SubmitPanel';
import { VoiceNotes } from './VoiceNotes';
import { MediaViewer } from './MediaViewer';

type Props = { colors: any; appraisal: any; onEdit: (step: string) => void; onSaved?: (appraisal: any) => void; showToast?: (m: string, t?: any, d?: number) => void; readOnly?: boolean };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');

// Value + summary. Editable: live suggested ACV and the Submit button on top of the rows. Read-only (after submission): just the frozen record.
export const ReviewStep = ({ colors, appraisal, onEdit, onSaved, showToast, readOnly }: Props) => {
  const router = useRouter();
  const [viewer, setViewer] = useState<number | null>(null);
  const v = appraisal.vehicle || {};
  const i = appraisal.inspection;
  const mk = appraisal.market;
  const market = !mk ? 'Not pulled yet' : `${mk.estimated_retail ? `Est. retail ${money(mk.estimated_retail)}` : 'No estimate'} · ${mk.comps_used || 0} comps · ${mk.live ? mk.provider_label : 'DEVELOPMENT DATA'}${appraisal.book_values?.length ? ` · ${appraisal.book_values.length} book value${appraisal.book_values.length > 1 ? 's' : ''}` : ''}`;
  const insp = !i ? 'Not started' : ['queued', 'processing'].includes(i.status) ? 'Jessi is inspecting…' : i.status === 'failed' ? 'Last run failed — tap to retry'
    : i.final_overall_label ? `${i.final_overall_label}${i.overridden ? ' (overridden)' : ''} · ${i.confirmed} confirmed${i.pending ? `, ${i.pending} to review` : ''}${i.possible ? `, ${i.possible} possible` : ''}` : 'Media added, not analyzed';
  const Row = ({ icon, label, value, step, testId }: { icon: any; label: string; value: string; step?: string; testId: string }) => (
    <TouchableOpacity disabled={!step || readOnly} onPress={() => step && onEdit(step)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(testId)}>
      <Ionicons name={icon} size={18} color={GOLD} />
      <Text style={{ width: 92, fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>{label.toUpperCase()}</Text>
      <Text style={{ flex: 1, fontSize: 15, fontWeight: '600', color: colors.text }} numberOfLines={2}>{value || '—'}</Text>
      {step && !readOnly ? <Ionicons name="create-outline" size={16} color={colors.textSecondary} /> : null}
    </TouchableOpacity>
  );
  return (
    <View style={{ gap: 12 }}>
      {readOnly ? <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginTop: 4 }}>WHAT WAS SUBMITTED</Text> : (
        <>
          <StepTitle colors={colors} title={appraisal.status === 'needs_info' ? 'Fix it and resubmit' : 'The dealership\u2019s number'} sub="Market data, book values and the customer's expectation stay side by side. The suggested ACV comes from your dealership's rules; a manager approves the real number." />
          {onSaved && showToast ? <SubmitPanel colors={colors} appraisal={appraisal} onSaved={onSaved} showToast={showToast} /> : null}
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginTop: 4 }}>EVERYTHING ON THIS APPRAISAL</Text>
        </>
      )}
      <View style={{ borderRadius: 16, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('review-card')}>
        <Row icon="car-sport" label="Vehicle" value={appraisal.vehicle_label || ''} step={appraisal.is_reappraisal ? undefined : 'identity'} testId="review-vehicle" />
        <Row icon="barcode-outline" label="VIN" value={appraisal.vin || 'No VIN on file'} testId="review-vin" />
        <Row icon="speedometer" label="Mileage" value={appraisal.mileage_confirmed != null ? miles(appraisal.mileage_confirmed) + (appraisal.mileage_detected != null && appraisal.mileage_detected !== appraisal.mileage_confirmed ? ` (Jessi read ${miles(appraisal.mileage_detected)})` : '') : ''} step="mileage" testId="review-mileage" />
        <Row icon="cash-outline" label="Customer wants" value={appraisal.customer_expected_value ? money(appraisal.customer_expected_value) : appraisal.expectation_asked === false ? 'Has not named a number' : ''} step="expectation" testId="review-expectation" />
        <Row icon="scan" label="Inspection" value={insp} step="inspection" testId="review-inspection" />
        <Row icon="stats-chart" label="Market" value={market} step="market" testId="review-market" />
        <Row icon={appraisal.mode === 'customer_sent' ? 'cloud-upload-outline' : 'location-outline'} label="Captured" value={appraisal.mode_label} step={appraisal.vehicle_id ? undefined : 'mode'} testId="review-mode" />
        <Row icon="person-outline" label="Customer" value={appraisal.contact_name} testId="review-customer" />
        {appraisal.notes ? <Row icon="document-text-outline" label="Notes" value={appraisal.notes} testId="review-notes" /> : null}
        {appraisal.is_reappraisal ? <Row icon="refresh" label="Reappraisal" value={`Vehicle first appraised ${when(appraisal.history?.[appraisal.history.length - 1]?.created_at)}`} testId="review-reappraisal" /> : null}
      </View>
      <VoiceNotes colors={colors} appraisal={appraisal} onSaved={onSaved} showToast={showToast} readOnly={readOnly} />
      {appraisal.media?.length ? (
        <View style={{ gap: 8 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>MEDIA · {appraisal.media.length}</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {appraisal.media.map((m: any, idx: number) => (
              <TouchableOpacity key={m.id} onPress={() => setViewer(idx)} activeOpacity={0.85} style={{ width: 104, gap: 4 }} {...tid(`review-media-${m.id}`)}>
                <View style={{ width: 104, height: 78, borderRadius: 10, overflow: 'hidden', backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }}>
                  {m.thumb_url ? <Image source={{ uri: resolvePhotoUrl(m.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : <Ionicons name={m.kind === 'video' ? 'videocam' : 'image'} size={22} color={GOLD} />}
                  {m.kind === 'video' ? <View style={{ position: 'absolute', left: 6, bottom: 6, backgroundColor: '#000000AA', borderRadius: 6, padding: 3 }}><Ionicons name="play" size={10} color="#fff" /></View> : null}
                </View>
                <Text style={{ fontSize: 11, fontWeight: '700', color: colors.text }} numberOfLines={1}>{m.role_label}</Text>
                <SourceTag source={m.source} colors={colors} />
              </TouchableOpacity>
            ))}
          </View>
          <MediaViewer colors={colors} media={appraisal.media} index={viewer} onClose={() => setViewer(null)} />
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
        <TouchableOpacity onPress={() => router.replace('/appraisals' as any)} style={{ flex: 1, height: 50, borderRadius: 14, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('review-done')}>
          <Ionicons name="list" size={18} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{readOnly ? 'All appraisals' : 'Finish later'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};
