import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Platform, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { BigButton, StepTitle, BusyBar, SourceTag, miles } from './shared';
import type { useAppraisalMedia, MediaSource } from '../../hooks/useAppraisalMedia';

type Props = { colors: any; appraisal: any; media: ReturnType<typeof useAppraisalMedia>; onSaved: (appraisal: any) => void; showToast: (m: string, t?: any) => void };

// SCAN ODOMETER · UPLOAD ODOMETER PHOTO · ENTER MANUALLY. Jessi's reading is shown, never silently accepted.
export const MileageStep = ({ colors, appraisal, media, onSaved, showToast }: Props) => {
  const reported = appraisal.customer_intake?.mileage;
  const customerOdo = (appraisal.media || []).find((m: any) => m.role === 'odometer_photo' && m.source === 'customer_supplied');
  const [detected, setDetected] = useState<{ mileage: number | null; confidence?: string; note?: string; photo?: any; reported?: boolean } | null>(
    appraisal.mileage_confirmed != null ? null
      : customerOdo?.reading?.mileage != null ? { mileage: customerOdo.reading.mileage, confidence: customerOdo.reading.confidence, note: reported != null && reported !== customerOdo.reading.mileage ? `The customer typed ${miles(reported)}; Jessi read ${miles(customerOdo.reading.mileage)} from their photo.` : 'Read from the odometer photo the customer sent through the trade link.', photo: customerOdo }
      : reported != null ? { mileage: reported, confidence: 'medium', note: 'Typed by the customer through the trade link.', reported: true, photo: customerOdo } : null);
  const [typed, setTyped] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const customerSent = appraisal.mode === 'customer_sent';
  const importSource: MediaSource = customerSent ? 'customer_supplied' : 'uploaded_by_rep';
  const prev = appraisal.is_reappraisal && appraisal.vehicle_record?.current_mileage;
  const prevAppr = appraisal.is_reappraisal ? appraisal.vehicle_record?.last_appraisal : null;

  const afterPhoto = (m: any) => {
    if (!m) return;
    const r = m.reading || {};
    setDetected({ mileage: r.mileage ?? null, confidence: r.confidence, note: r.note, photo: m });
    if (r.mileage == null) { showToast('Jessi could not read the odometer. Type it or try a clearer photo.', 'error', 4500); setEditing(true); }
  };
  const save = async (value: number, source: string) => {
    setSaving(true);
    try {
      const r = (await api.post(`/appraisals/${appraisal.id}/mileage`, { confirmed: value, detected: detected?.mileage ?? undefined, source })).data;
      onSaved(r.appraisal);
    } catch (e) { showToast(errText(e, 'Could not save the mileage'), 'error'); }
    finally { setSaving(false); }
  };
  const typedNum = parseInt(typed.replace(/\D/g, ''), 10);

  if (detected && !editing && detected.mileage != null) {
    return (
      <View style={{ gap: 12 }}>
        <StepTitle colors={colors} title={detected.reported ? 'Customer reported mileage' : 'Detected mileage'} sub="Confirm it or fix it. The number you confirm is what the appraisal uses." />
        <View style={{ borderRadius: 16, padding: 18, backgroundColor: colors.card, borderWidth: 1.5, borderColor: GOLD, gap: 8, alignItems: 'center' }} {...tid('odometer-detected-card')}>
          <Text style={{ fontSize: 36, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} {...tid('odometer-detected-value')}>{miles(detected.mileage)}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{detected.reported ? 'Reported by the customer' : `Read by Jessi · ${detected.confidence === 'high' ? 'high confidence' : detected.confidence === 'medium' ? 'medium confidence, double-check' : 'low confidence, double-check'}`}</Text>
            {detected.photo ? <SourceTag source={detected.photo.source} colors={colors} /> : detected.reported ? <SourceTag source="customer_supplied" colors={colors} /> : null}
          </View>
          {detected.note ? <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center' }}>{detected.note}</Text> : null}
          {detected.photo?.thumb_url ? <Image source={{ uri: resolvePhotoUrl(detected.photo.thumb_url) || '' }} style={{ width: '100%', height: 140, borderRadius: 10 }} resizeMode="cover" /> : null}
        </View>
        <BigButton colors={colors} icon="checkmark" label="Confirm" sub={miles(detected.mileage)} onPress={() => save(detected.mileage!, detected.reported ? 'customer_reported' : 'photo')} primary disabled={saving} testId="odometer-confirm" />
        <BigButton colors={colors} icon="create-outline" label="Edit" sub="Type the exact number" onPress={() => { setTyped(String(detected.mileage)); setEditing(true); }} disabled={saving} testId="odometer-edit" />
        <BusyBar text={saving ? 'Saving…' : media.busy} colors={colors} />
      </View>
    );
  }

  if (editing) {
    return (
      <View style={{ gap: 12 }}>
        <StepTitle colors={colors} title="Enter mileage" sub={prev ? `Last known: ${miles(prev)}. Enter what the odometer shows today.` : 'What the odometer shows, in miles.'} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <TextInput value={typed} onChangeText={t => setTyped(t.replace(/[^\d]/g, '').slice(0, 7))} keyboardType="number-pad" placeholder="47821" placeholderTextColor={colors.textSecondary} autoFocus
            style={{ flex: 1, height: 60, borderRadius: 14, borderWidth: 1.5, borderColor: typedNum > 0 ? GOLD : colors.border, backgroundColor: colors.card, color: colors.text, paddingHorizontal: 16, fontSize: 26, fontVariant: ['tabular-nums'] }} {...tid('odometer-input')} />
          <Text style={{ fontSize: 16, fontWeight: '700', color: colors.textSecondary }}>miles</Text>
        </View>
        {prev && typedNum > 0 && typedNum < prev ? <Text style={{ fontSize: 12, color: '#FF9500' }} {...tid('odometer-rollback-warning')}>That is lower than the {miles(prev)} we had before. Double-check the number.</Text> : null}
        <BigButton colors={colors} icon="checkmark" label="Save mileage" sub={typedNum > 0 ? miles(typedNum) : undefined} onPress={() => save(typedNum, detected?.mileage != null ? 'photo_edited' : 'manual')} primary disabled={!(typedNum > 0) || saving} testId="odometer-save" />
        <TouchableOpacity onPress={() => { setEditing(false); if (detected?.mileage == null) setDetected(null); }} style={{ alignSelf: 'center', padding: 8 }} {...tid('odometer-back')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Back</Text></TouchableOpacity>
        <BusyBar text={saving ? 'Saving…' : null} colors={colors} />
      </View>
    );
  }

  return (
    <View style={{ gap: 12 }}>
      <StepTitle colors={colors} title="Capture mileage" sub={customerSent ? "Import the odometer photo the customer sent, or type it." : 'Photograph the instrument cluster with the ignition on. Jessi reads the total, not the trip meter.'} />
      {prev ? <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 12, backgroundColor: GOLD + '14', borderWidth: 1, borderColor: GOLD + '55' }} {...tid('mileage-previous')}><Ionicons name="time-outline" size={16} color={GOLD} /><Text style={{ fontSize: 12.5, color: colors.text }}>Reappraisal · last known {miles(prev)}</Text></View> : null}
      {prevAppr && (prevAppr.suggested_acv || prevAppr.approved_value || prevAppr.customer_expected_value) ? (
        <View style={{ padding: 10, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 4 }} {...tid('previous-appraisal-card')}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>PREVIOUS APPRAISAL{prevAppr.appraised_at ? ` · ${new Date(prevAppr.appraised_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}` : ''}</Text>
          <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 18 }}>{[prevAppr.suggested_acv ? `Suggested $${Math.round(prevAppr.suggested_acv).toLocaleString()}` : null, prevAppr.approved_value ? `Offered $${Math.round(prevAppr.approved_value).toLocaleString()}` : null, prevAppr.customer_expected_value ? `Wanted $${Math.round(prevAppr.customer_expected_value).toLocaleString()}` : null, prevAppr.outcome_label ? `Customer: ${prevAppr.outcome_label}` : null].filter(Boolean).join(' · ')}</Text>
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Kept for reference only. This appraisal gets a fresh value from today's mileage, condition and market.</Text>
        </View>
      ) : null}
      {Platform.OS !== 'web' && !customerSent ? <BigButton colors={colors} icon="speedometer" label="Scan odometer" sub="Camera" onPress={() => media.capture('odometer_photo').then(afterPhoto)} primary disabled={!!media.busy} testId="mileage-scan" /> : null}
      <BigButton colors={colors} icon="image-outline" label={customerSent ? "Upload customer's odometer photo" : 'Upload odometer photo'} sub={customerSent ? 'From what they sent you' : 'From your photo library or Files'} onPress={() => media.importOne('odometer_photo', importSource).then(afterPhoto)} primary={customerSent || Platform.OS === 'web'} disabled={!!media.busy} testId="mileage-upload" />
      <BigButton colors={colors} icon="keypad-outline" label="Enter manually" onPress={() => setEditing(true)} disabled={!!media.busy} testId="mileage-manual" />
      <BusyBar text={media.busy} colors={colors} />
    </View>
  );
};
