import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { openUrl } from './ReportView';
import { fmtPhone, GOLD, GREEN, tid, type Client } from './shared';

type State = { name: string; org: string; phone_number: string; url: string; vcf_url: string; mms: boolean; sms_preview: string; sent: number; total: number; people: { id: string; ok: boolean | null }[] };

// The shop number as a contact the whole team can save: copy the link for your own phone, or text it to everyone from here.
export const ContactCardPanel = ({ client, colors, refreshKey, onSent }: { client: Client; colors: any; refreshKey: number; onSent: () => void }) => {
  const { showToast } = useToast();
  const [s, setS] = useState<State | null>(null);
  const [busy, setBusy] = useState(false);
  const [showText, setShowText] = useState(false);
  const load = useCallback(() => { api.get(`/shop-clients/${client.id}/contact-card`).then(r => setS(r.data)).catch(() => {}); }, [client.id]);
  useEffect(load, [load, refreshKey]);
  if (!s) return null;

  const copy = async () => { await Clipboard.setStringAsync(s.url); showToast('Contact link copied. Paste it into any text.', 'success'); };
  const copyText = async () => { await Clipboard.setStringAsync(s.sms_preview); showToast('Message copied', 'success'); };
  const send = (onlyNew: boolean) => {
    const ids = onlyNew ? s.people.filter(p => !p.ok).map(p => p.id) : [];
    const n = onlyNew ? ids.length : s.total;
    showConfirm(`Text the contact card to ${n} ${n === 1 ? 'person' : 'people'}?`, `Each one gets a text from ${fmtPhone(s.phone_number)}${s.mms ? ' with the contact attached' : ''} and a link to save "${s.name}" to their phone.`, async () => {
      setBusy(true);
      try {
        const r = await api.post(`/shop-clients/${client.id}/contact-card/send`, { target_ids: ids });
        showToast(r.data.failed.length ? `Sent to ${r.data.sent}, ${r.data.failed.length} failed: ${r.data.failed.map((f: any) => f.name.split(' ')[0]).join(', ')}` : `Contact card sent to ${r.data.sent} ${r.data.sent === 1 ? 'person' : 'people'}`, r.data.failed.length ? 'error' : 'success');
        load(); onSent();
      } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not send', 'error'); }
      finally { setBusy(false); }
    }, undefined, 'Send');
  };
  const newCount = s.people.filter(p => !p.ok).length;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }} {...tid('contact-card-panel')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Ionicons name="person-circle-outline" size={20} color={GOLD} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Contact card for the team</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('contact-card-sub')}>Saves as "{s.name}" · {fmtPhone(s.phone_number)}{s.total ? ` · sent to ${s.sent} of ${s.total}` : ''}</Text>
        </View>
        {s.total > 0 && s.sent === s.total && <Ionicons name="checkmark-circle" size={20} color={GREEN} />}
      </View>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }} numberOfLines={1} {...tid('contact-card-url')}>{s.url}</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TouchableOpacity onPress={() => send(false)} disabled={busy || !s.total} style={{ flex: 1, height: 36, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: busy || !s.total ? 0.5 : 1 }} {...tid('contact-card-send-all')}>
          {busy ? <ActivityIndicator color="#111" size="small" /> : <><Ionicons name="paper-plane" size={14} color="#111" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Text everyone{s.total ? ` (${s.total})` : ''}</Text></>}
        </TouchableOpacity>
        <TouchableOpacity onPress={copy} style={{ height: 36, paddingHorizontal: 12, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('contact-card-copy')}><Ionicons name="link" size={14} color={colors.text} /><Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Copy link</Text></TouchableOpacity>
        <TouchableOpacity onPress={() => openUrl(s.url)} style={{ width: 36, height: 36, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('contact-card-open')}><Ionicons name="open-outline" size={16} color={colors.text} /></TouchableOpacity>
      </View>
      {newCount > 0 && s.sent > 0 && <TouchableOpacity onPress={() => send(true)} disabled={busy} {...tid('contact-card-send-new')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Only text the {newCount} who haven't got it</Text></TouchableOpacity>}
      <TouchableOpacity onPress={() => setShowText(v => !v)} {...tid('contact-card-toggle-text')}><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.textSecondary }}>{showText ? 'Hide the message' : 'See the message they get'}</Text></TouchableOpacity>
      {showText && (
        <View style={{ gap: 6 }}>
          <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18, backgroundColor: colors.background, borderRadius: 10, padding: 10 }} {...tid('contact-card-sms-preview')}>{s.sms_preview}</Text>
          <TouchableOpacity onPress={copyText} {...tid('contact-card-copy-text')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Copy message to send from my own phone</Text></TouchableOpacity>
        </View>
      )}
    </View>
  );
};
