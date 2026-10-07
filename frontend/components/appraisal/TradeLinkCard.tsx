import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Platform } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { miles } from './shared';

const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');
const ANSWER_LABELS: Record<string, Record<string, string>> = {
  overall: { excellent: 'Excellent', good: 'Good', fair: 'Fair', rough: 'Rough' }, accidents: { no: 'No accidents', yes: 'Accident / body work', unsure: 'Accidents: not sure' },
  warning_lights: { no: 'No warning lights', yes: 'Warning light on' }, tires: { good: 'Tires good', worn: 'Tires getting worn', replace: 'Tires need replacing' },
  smoke: { no: 'Not smoked in', yes: 'Smoked in' }, keys: { '2': '2+ keys', '1': '1 key' },
};
export const answerChips = (c: Record<string, string> | undefined) => Object.entries(c || {}).map(([k, v]) => ANSWER_LABELS[k]?.[v]).filter(Boolean) as string[];

// Customer not at the store: mint a 7-day link, text it or copy it, and watch what comes back. Everything the customer sends lands on this appraisal.
export const TradeLinkCard = ({ colors, appraisal, onSaved, showToast }: { colors: any; appraisal: any; onSaved: (a: any) => void; showToast: (m: string, t?: any, d?: number) => void }) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [open, setOpen] = useState(!!appraisal.intake);
  const it = appraisal.intake;
  const ci = appraisal.customer_intake;
  const live = it && !it.revoked_at && new Date(it.expires_at) > new Date();

  const act = async (channel: 'sms' | 'copy') => {
    setBusy(channel);
    try {
      const r = (await api.post(`/appraisals/${appraisal.id}/intake-link`, { channel })).data;
      onSaved(r.appraisal);
      if (channel === 'copy') { await Clipboard.setStringAsync(r.intake.short_url || r.intake.url); showToast('Link copied. Paste it into a text or email.', 'success'); }
      else showToast(`Texted the trade link to ${r.intake.sent_to}`, 'success');
    } catch (e) { showToast(errText(e, 'Could not create the link'), 'error', 6000); }
    finally { setBusy(null); }
  };
  const revoke = async () => {
    setBusy('off');
    try { const r = (await api.delete(`/appraisals/${appraisal.id}/intake-link`)).data; onSaved(r.appraisal); showToast('Link turned off', 'success'); }
    catch (e) { showToast(errText(e, 'Could not turn the link off'), 'error'); }
    finally { setBusy(null); }
  };

  if (!open) return (
    <TouchableOpacity onPress={() => setOpen(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '66', backgroundColor: GOLD + '0D', marginBottom: 14 }} {...tid('trade-link-open')}>
      <Ionicons name="phone-portrait-outline" size={18} color={GOLD} />
      <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: colors.text }}>Customer not here? Text them a secure link to send the VIN, mileage and photos.</Text>
      <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
    </TouchableOpacity>
  );
  return (
    <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: live ? GOLD + '88' : colors.border, gap: 10, marginBottom: 14 }} {...tid('trade-link-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="phone-portrait-outline" size={16} color={GOLD} />
        <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>CUSTOMER TRADE LINK</Text>
        {!it ? <TouchableOpacity onPress={() => setOpen(false)} {...tid('trade-link-close')}><Ionicons name="close" size={16} color={colors.textSecondary} /></TouchableOpacity> : null}
      </View>
      {!it ? <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }}>A private page for this one vehicle, good for 7 days. The customer types or photographs the VIN sticker and odometer, adds photos and answers six quick questions. No app, no login, no dollar amounts.</Text> : (
        <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 18 }} {...tid('trade-link-status')}>
          {it.revoked_at ? 'Link turned off' : it.sent_at ? `Texted ${when(it.sent_at)}${it.sent_to ? ` to ${it.sent_to}` : ''}` : `Created ${when(it.created_at)}`}
          {it.opened_at ? ` · opened ${when(it.opened_at)}` : live ? ' · not opened yet' : ''}{it.photo_count ? ` · ${it.photo_count} photo${it.photo_count === 1 ? '' : 's'}` : ''}{it.submitted_at ? ` · submitted ${when(it.submitted_at)}` : ''}
          {live ? ` · expires ${new Date(it.expires_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}` : ''}
        </Text>
      )}
      {ci ? (
        <View style={{ borderRadius: 12, padding: 10, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, gap: 4 }} {...tid('trade-link-intake')}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.4 }}>WHAT THE CUSTOMER SENT</Text>
          <Text style={{ fontSize: 13, color: colors.text }}>{[ci.vin ? `VIN ${ci.vin}` : null, ci.mileage != null ? `${miles(ci.mileage)} (reported)` : null, ci.zip ? `ZIP ${ci.zip}` : null, ci.photo_count ? `${ci.photo_count} photo${ci.photo_count === 1 ? '' : 's'}` : null].filter(Boolean).join(' · ') || 'Answers only'}</Text>
          {answerChips(ci.condition).length ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{answerChips(ci.condition).join(' · ')}</Text> : null}
          {ci.notes ? <Text style={{ fontSize: 12.5, color: colors.text, fontStyle: 'italic' }}>"{ci.notes}"</Text> : null}
          {ci.wants ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Has a number in mind: ${Math.round(ci.wants).toLocaleString()} (record it in the Expectation step if you ask)</Text> : null}
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Nothing here is confirmed until you confirm it in the steps.</Text>
        </View>
      ) : null}
      <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
        <TouchableOpacity onPress={() => act('sms')} disabled={!!busy} style={{ flex: 1, minWidth: 130, height: 42, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: busy ? 0.5 : 1 }} {...tid('trade-link-sms')}>
          <Ionicons name="chatbubble-ellipses" size={15} color="#0B0B0D" /><Text style={{ fontSize: 13.5, fontWeight: '800', color: '#0B0B0D' }}>{it?.sent_at ? 'Text again' : 'Text the link'}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => act('copy')} disabled={!!busy} style={{ flex: 1, minWidth: 110, height: 42, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: busy ? 0.5 : 1 }} {...tid('trade-link-copy')}>
          <Ionicons name={Platform.OS === 'web' ? 'copy-outline' : 'share-outline'} size={15} color={colors.text} /><Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>Copy link</Text>
        </TouchableOpacity>
        {live ? (
          <TouchableOpacity onPress={revoke} disabled={!!busy} style={{ height: 42, paddingHorizontal: 12, borderRadius: 12, alignItems: 'center', justifyContent: 'center', opacity: busy ? 0.5 : 1 }} {...tid('trade-link-revoke')}>
            <Text style={{ fontSize: 12.5, fontWeight: '700', color: '#FF3B30' }}>Turn off</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
};
