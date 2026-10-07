import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Platform, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { BigButton, StepTitle, BusyBar, SourceTag } from './shared';
import type { useAppraisalMedia, MediaSource } from '../../hooks/useAppraisalMedia';

type Media = ReturnType<typeof useAppraisalMedia>;
type Props = { colors: any; appraisal: any; media: Media; onConfirmed: (appraisal: any) => void; showToast: (m: string, t?: any) => void };
type Detected = { vin: string; method: string; confidence?: string; validation?: any; vehicle?: any; photo?: any };
const VIN_FIELDS: [string, string][] = [['year', 'Year'], ['make', 'Make'], ['model', 'Model'], ['trim', 'Trim']];
const fixVin = (s: string) => s.toUpperCase().replace(/[^A-Z0-9]/g, '').replace(/I/g, '1').replace(/[OQ]/g, '0').slice(0, 17);

// SCAN VIN · UPLOAD VIN PHOTO · ENTER VIN MANUALLY · (future) SCAN LICENSE PLATE. Nothing is accepted until the rep confirms.
export const IdentityStep = ({ colors, appraisal, media, onConfirmed, showToast }: Props) => {
  const [phase, setPhase] = useState<'choose' | 'typing' | 'detected' | 'manual'>('choose');
  const [typed, setTyped] = useState('');
  const [det, setDet] = useState<Detected | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const customerSent = appraisal.mode === 'customer_sent';
  const importSource: MediaSource = customerSent ? 'customer_supplied' : 'uploaded_by_rep';

  const afterPhoto = (m: any) => {
    if (!m) return;
    const r = m.reading || {};
    if (!r.vin) { showToast('Jessi could not read a VIN in that photo. Try a closer, straighter shot or type it.', 'error', 4500); setDet({ vin: '', method: 'none', photo: m }); setPhase('typing'); return; }
    decode(r.vin, r.method === 'barcode' ? 'vin_photo_barcode' : 'vin_photo_ocr', r.confidence, m);
  };
  const decode = async (vin: string, method: string, confidence?: string, photo?: any) => {
    setSaving(true);
    try {
      const r = (await api.post('/appraisals/vin/decode', { vin })).data;
      setDet({ vin: r.vin, method, confidence, validation: r.validation, vehicle: r.vehicle, photo });
      setEdits({});
      setPhase('detected');
    } catch (e) { showToast(errText(e, 'Could not decode that VIN'), 'error'); }
    finally { setSaving(false); }
  };
  const confirm = async () => {
    if (!det) return;
    setSaving(true);
    try {
      const manual = Object.fromEntries(Object.entries(edits).filter(([, v]) => v.trim()));
      const r = (await api.post(`/appraisals/${appraisal.id}/vehicle`, { vin: det.validation?.valid ? det.vin : undefined, manual: Object.keys(manual).length ? manual : undefined, method: det.method })).data;
      onConfirmed(r.appraisal);
    } catch (e) { showToast(errText(e, 'Could not save the vehicle'), 'error'); }
    finally { setSaving(false); }
  };
  const confirmManual = async () => {
    setSaving(true);
    try {
      const r = (await api.post(`/appraisals/${appraisal.id}/vehicle`, { manual: edits, method: 'manual_vehicle' })).data;
      onConfirmed(r.appraisal);
    } catch (e) { showToast(errText(e, 'Give me at least the make and model'), 'error'); }
    finally { setSaving(false); }
  };

  const Field = ({ k, label, placeholder }: { k: string; label: string; placeholder?: string }) => (
    <View style={{ flex: 1, minWidth: 120 }}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginBottom: 4 }}>{label.toUpperCase()}</Text>
      <TextInput value={edits[k] ?? (det?.vehicle?.[k] != null ? String(det.vehicle[k]) : '')} onChangeText={t => setEdits(p => ({ ...p, [k]: t }))} placeholder={placeholder || label} placeholderTextColor={colors.textSecondary}
        keyboardType={k === 'year' ? 'number-pad' : 'default'} style={{ height: 44, borderRadius: 10, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, color: colors.text, paddingHorizontal: 12, fontSize: 15 }} {...tid(`vehicle-field-${k}`)} />
    </View>
  );

  if (phase === 'detected' && det) {
    const v = det.vehicle;
    const valid = !!det.validation?.valid;
    const decoded = !!v?.decode_ok;
    const conf = det.confidence === 'high' ? 'High confidence' : det.confidence === 'medium' ? 'Medium confidence, check each character' : det.confidence === 'low' ? 'Low confidence, check each character' : '';
    return (
      <View style={{ gap: 12 }}>
        <StepTitle colors={colors} title={valid ? 'VIN detected' : 'That VIN does not check out'} sub={valid ? 'Confirm it before we go on. Jessi never files a VIN without you.' : (det.validation?.errors || []).join('. ')} />
        <View style={{ borderRadius: 16, padding: 16, backgroundColor: colors.card, borderWidth: 1.5, borderColor: valid ? GOLD : '#FF3B30', gap: 8 }} {...tid('vin-detected-card')}>
          <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text, letterSpacing: 2, fontVariant: ['tabular-nums'] }} {...tid('vin-detected-value')}>{det.vin || '—'}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{det.method.startsWith('vin_photo') ? (det.method.endsWith('barcode') ? 'Read from the barcode' : 'Read by Jessi (OCR)') : 'Typed'}{conf ? ` · ${conf}` : ''}</Text>
            {det.photo ? <SourceTag source={det.photo.source} colors={colors} /> : null}
          </View>
          {det.photo?.thumb_url ? <Image source={{ uri: resolvePhotoUrl(det.photo.thumb_url) || '' }} style={{ width: '100%', height: 140, borderRadius: 10 }} resizeMode="cover" /> : null}
        </View>
        {valid ? (
          <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 10 }} {...tid('decoded-vehicle-card')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons name={decoded ? 'checkmark-circle' : 'alert-circle'} size={18} color={decoded ? '#34C759' : '#FF9500'} />
              <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>{decoded ? [v.year, v.make, v.model, v.trim || v.series].filter(Boolean).join(' ') : 'Decoder could not fill this in'}</Text>
            </View>
            {decoded ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{[v.body_class, v.engine, v.fuel, v.drivetrain].filter(Boolean).join(' · ')}{v.decoded_by === 'nhtsa_vpic' ? ' · NHTSA' : ''}</Text>
              : <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{v?.decode_message || 'Fill in what you know; the VIN is still saved.'}</Text>}
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{VIN_FIELDS.map(([k, l]) => <Field key={k} k={k} label={l} />)}</View>
          </View>
        ) : null}
        <BigButton colors={colors} icon="checkmark" label={valid ? 'Confirm VIN' : 'Use it anyway (fill the vehicle in)'} onPress={confirm} primary={valid} disabled={saving || (!valid && !(edits.make && edits.model))} testId="vin-confirm" />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TouchableOpacity onPress={() => (Platform.OS === 'web' ? media.importOne('vin_photo', importSource) : media.capture('vin_photo')).then(afterPhoto)} disabled={saving} style={{ flex: 1, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('vin-scan-again')}>
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Scan again</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => { setTyped(det.vin); setPhase('typing'); }} disabled={saving} style={{ flex: 1, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('vin-edit')}>
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Edit VIN</Text>
          </TouchableOpacity>
        </View>
        <BusyBar text={saving ? 'Saving the vehicle…' : media.busy} colors={colors} />
      </View>
    );
  }

  if (phase === 'typing') {
    const ok = typed.length === 17;
    return (
      <View style={{ gap: 12 }}>
        <StepTitle colors={colors} title="Enter the VIN" sub="17 characters. Letters I, O and Q are never in a VIN, so they are fixed as you type." />
        <TextInput value={typed} onChangeText={t => setTyped(fixVin(t))} autoCapitalize="characters" autoCorrect={false} placeholder="1FTFW1E50NFA12345" placeholderTextColor={colors.textSecondary} autoFocus
          style={{ height: 56, borderRadius: 14, borderWidth: 1.5, borderColor: ok ? GOLD : colors.border, backgroundColor: colors.card, color: colors.text, paddingHorizontal: 14, fontSize: 20, letterSpacing: 2 }} {...tid('vin-input')} />
        <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'right' }} {...tid('vin-count')}>{typed.length}/17</Text>
        <BigButton colors={colors} icon="search" label="Look it up" onPress={() => decode(typed, 'manual_vin')} primary disabled={!ok || saving} testId="vin-lookup" />
        <TouchableOpacity onPress={() => setPhase('choose')} style={{ alignSelf: 'center', padding: 8 }} {...tid('vin-typing-back')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Back</Text></TouchableOpacity>
        <BusyBar text={saving ? 'Decoding…' : null} colors={colors} />
      </View>
    );
  }

  if (phase === 'manual') {
    return (
      <View style={{ gap: 12 }}>
        <StepTitle colors={colors} title="Describe the vehicle" sub="No VIN handy? Year, make and model are enough to keep going; add the VIN later from the vehicle card." />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{VIN_FIELDS.map(([k, l]) => <Field key={k} k={k} label={l} />)}</View>
        <BigButton colors={colors} icon="checkmark" label="Save vehicle" onPress={confirmManual} primary disabled={saving || !(edits.make && edits.model)} testId="manual-vehicle-save" />
        <TouchableOpacity onPress={() => setPhase('choose')} style={{ alignSelf: 'center', padding: 8 }} {...tid('manual-back')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Back</Text></TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={{ gap: 12 }}>
      <StepTitle colors={colors} title="Identify the vehicle" sub={customerSent ? 'Import the VIN photo the customer sent, or type the VIN.' : 'Point the camera at the door-jamb label or the dash plate. Jessi reads the barcode or the characters.'} />
      {Platform.OS !== 'web' && !customerSent ? <BigButton colors={colors} icon="scan" label="Scan VIN" sub="Camera · barcode or printed characters" onPress={() => media.capture('vin_photo').then(afterPhoto)} primary disabled={!!media.busy} testId="identity-scan-vin" /> : null}
      <BigButton colors={colors} icon="image-outline" label={customerSent ? "Upload customer's VIN photo" : 'Upload VIN photo'} sub={customerSent ? 'From the photo they texted or emailed you' : 'From your photo library or Files'} onPress={() => media.importOne('vin_photo', importSource).then(afterPhoto)} primary={customerSent || Platform.OS === 'web'} disabled={!!media.busy} testId="identity-upload-vin" />
      <BigButton colors={colors} icon="keypad-outline" label="Enter VIN manually" sub="Type the 17 characters" onPress={() => setPhase('typing')} disabled={!!media.busy} testId="identity-type-vin" />
      <BigButton colors={colors} icon="car-outline" label="No VIN: describe the vehicle" sub="Year, make, model, trim" onPress={() => { setEdits({}); setDet(null); setPhase('manual'); }} disabled={!!media.busy} testId="identity-manual-vehicle" />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 14, borderWidth: 1, borderColor: colors.border, opacity: 0.55 }} {...tid('identity-plate-soon')}>
        <Ionicons name="pricetag-outline" size={18} color={colors.textSecondary} />
        <Text style={{ flex: 1, fontSize: 13, color: colors.textSecondary }}>Scan license plate</Text>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary }}>COMING SOON</Text>
      </View>
      <BusyBar text={media.busy || (saving ? 'Decoding…' : null)} colors={colors} />
    </View>
  );
};
