import React, { useCallback, useEffect, useState } from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useCompliance } from '../../store/complianceStore';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, GREEN, RADIUS, RED, SPACE, TYPE, tid, tint } from '../ui/tokens';
import { SCOPE_LABEL } from './consentParts';

const PILL: Record<string, { label: string; color: string }> = {
  granted: { label: 'Granted', color: GREEN },
  revoked: { label: 'Revoked', color: RED },
  unknown: { label: 'Unknown', color: '#8E8E93' },
};
const fmt = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');

/** Contact page: what this contact agreed to by text (per scope), opt-out status, and a one-tap way to record consent. */
export function ConsentStatusCard({ contactId, name }: { contactId: string; name?: string }) {
  const { colors } = useThemeStore();
  const requestConsent = useCompliance(s => s.requestConsent);
  const consentRev = useCompliance(s => s.consentRev);
  const [data, setData] = useState<any>(null);
  const load = useCallback(() => { api.get(`/consent/contact/${contactId}`).then(r => setData(r.data)).catch(() => setData(null)); }, [contactId]);
  useEffect(() => { load(); }, [load, consentRev]);
  if (!data) return null;

  const record = async () => {
    const unknown = Object.keys(SCOPE_LABEL).filter(s => s !== 'marketing' && data.state?.[s]?.status !== 'granted');
    await requestConsent({ code: 'manual', manual: true, needs: unknown, contact_id: contactId, phone: undefined, name });
  };

  return (
    <View style={{ marginHorizontal: 16, marginBottom: 12, padding: SPACE.md, borderRadius: RADIUS.md, backgroundColor: colors.card, borderWidth: 1, borderColor: data.opted_out ? RED : colors.border, gap: 8 }} {...tid('contact-consent-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="shield-checkmark-outline" size={18} color={GOLD} />
        <Text style={{ flex: 1, fontSize: TYPE.body, fontWeight: '800', color: colors.text }}>Texting permission</Text>
        {!data.opted_out && (
          <TouchableOpacity onPress={record} {...tid('contact-consent-record')} style={{ paddingVertical: 4, paddingHorizontal: 10, borderRadius: 14, backgroundColor: tint(GOLD, 0.15) }}>
            <Text style={{ fontSize: TYPE.sub, fontWeight: '800', color: GOLD }}>Record</Text>
          </TouchableOpacity>
        )}
      </View>
      {data.opted_out ? (
        <Text style={{ fontSize: TYPE.sub, color: RED, lineHeight: 19 }} {...tid('contact-consent-opted-out')}>
          Opted out{data.opt_out?.since ? ` on ${fmt(data.opt_out.since)}` : ''}. No texts can be sent. Only they can turn texts back on, by texting START.
        </Text>
      ) : null}
      {Object.keys(SCOPE_LABEL).map(s => {
        const st = data.state?.[s] || { status: 'unknown' };
        const p = PILL[st.status] || PILL.unknown;
        return (
          <View key={s} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`contact-consent-${s}`)}>
            <Text style={{ flex: 1, fontSize: TYPE.sub, color: colors.text }}>{SCOPE_LABEL[s]}</Text>
            {st.status === 'granted' && st.at ? <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary }}>{fmt(st.at)}{st.captured_by ? ` · ${st.captured_by}` : ''}</Text> : null}
            <View style={{ paddingVertical: 2, paddingHorizontal: 8, borderRadius: 10, backgroundColor: tint(p.color, 0.15) }}>
              <Text style={{ fontSize: TYPE.caption, fontWeight: '800', color: p.color }} {...tid(`contact-consent-${s}-status`)}>{p.label}</Text>
            </View>
          </View>
        );
      })}
      {data.last_customer_text_at ? (
        <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary }}>They last texted you {fmt(data.last_customer_text_at)}: replies within {data.reply_window_days} days are allowed. Marketing still needs opt-in.</Text>
      ) : null}
    </View>
  );
}
