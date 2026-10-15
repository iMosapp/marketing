import React, { useState } from 'react';
import { Share, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import QRCode from 'react-native-qrcode-svg';
import api from '../../services/api';
import { copyToClipboard } from '../../utils/clipboard';
import { GOLD, GREEN, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';

export const SCOPE_LABEL: Record<string, string> = {
  requested_info: 'Requested information',
  transactional: 'Transactional updates',
  marketing: 'Marketing',
};
export const SCOPE_HINT: Record<string, string> = {
  requested_info: 'Photos, documents, quotes or details they asked for',
  transactional: 'Updates about their purchase, service or appointment',
  marketing: 'Promotions and offers. Needs written or digital opt-in',
};

export function ScopeToggle({ scope, on, onPress, colors, statement }: { scope: string; on: boolean; onPress: () => void; colors: any; statement?: string }) {
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.8} {...tid(`consent-scope-${scope}`)}
      style={{ flexDirection: 'row', gap: SPACE.md, padding: SPACE.md, borderRadius: RADIUS.sm, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? tint(GOLD, 0.08) : 'transparent' }}>
      <Ionicons name={on ? 'checkbox' : 'square-outline'} size={22} color={on ? GOLD : colors.textTertiary} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: colors.text }}>{SCOPE_LABEL[scope]}</Text>
        <Text style={{ fontSize: TYPE.caption, color: colors.textSecondary, lineHeight: 16 }}>{SCOPE_HINT[scope]}</Text>
        {on && statement ? <Text style={{ fontSize: TYPE.caption, color: colors.text, lineHeight: 17, marginTop: 4, fontStyle: 'italic' }} {...tid(`consent-statement-${scope}`)}>"{statement}"</Text> : null}
      </View>
    </TouchableOpacity>
  );
}

const METHODS = [
  { key: 'verbal_in_person', label: 'Verbal, in person', icon: 'chatbubble-ellipses-outline' },
  { key: 'written_signature', label: 'Signed form', icon: 'document-text-outline' },
];

export function MethodPicker({ value, onChange, colors }: { value: string; onChange: (m: string) => void; colors: any }) {
  return (
    <View style={{ flexDirection: 'row', gap: SPACE.sm }}>
      {METHODS.map(m => {
        const on = value === m.key;
        return (
          <TouchableOpacity key={m.key} onPress={() => onChange(m.key)} {...tid(`consent-method-${m.key}`)}
            style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: RADIUS.sm, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD : 'transparent' }}>
            <Ionicons name={m.icon as any} size={16} color={on ? '#111' : colors.textSecondary} />
            <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: on ? '#111' : colors.textSecondary }}>{m.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

// Marketing in person: the contact opts in on their own phone (scan or open the link), so the consent is theirs, not a rep's checkbox.
export function OptInLinkBox({ contactId, colors }: { contactId: string; colors: any }) {
  const [link, setLink] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const create = async () => {
    setBusy(true); setErr('');
    try { setLink((await api.post(`/consent/contact/${contactId}/opt-in-link`, { scopes: ['marketing'] })).data.url); }
    catch (e: any) { setErr(e?.response?.data?.detail?.message || 'Could not create the opt-in link.'); }
    finally { setBusy(false); }
  };
  if (!link) {
    return (
      <View style={{ gap: 6 }}>
        <TouchableOpacity onPress={create} disabled={busy} {...tid('consent-optin-link-create')}
          style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 12, borderRadius: RADIUS.sm, borderWidth: 1, borderColor: GOLD, opacity: busy ? 0.6 : 1 }}>
          <Ionicons name="qr-code-outline" size={18} color={GOLD} />
          <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: GOLD }}>Marketing: let them opt in on their phone</Text>
        </TouchableOpacity>
        {err ? <Text style={{ fontSize: TYPE.caption, color: '#FF3B30' }}>{err}</Text> : null}
      </View>
    );
  }
  return (
    <View style={{ alignItems: 'center', gap: SPACE.sm, padding: SPACE.md, borderRadius: RADIUS.sm, backgroundColor: tint(GREEN, 0.08) }} {...tid('consent-optin-link-box')}>
      <View style={{ padding: 8, backgroundColor: '#FFF', borderRadius: 8 }}><QRCode value={link} size={140} /></View>
      <Text selectable style={{ fontSize: TYPE.caption, color: colors.text, textAlign: 'center' }} {...tid('consent-optin-link-url')}>{link}</Text>
      <Text style={{ fontSize: TYPE.caption, color: colors.textSecondary, textAlign: 'center' }}>They scan this and agree on their own phone. Nothing is checked for them. The link works once, for 7 days.</Text>
      <View style={{ flexDirection: 'row', gap: SPACE.sm }}>
        <TouchableOpacity onPress={() => copyToClipboard(link)} {...tid('consent-optin-link-copy')} style={{ paddingVertical: 8, paddingHorizontal: 14, borderRadius: 16, backgroundColor: colors.card }}>
          <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: colors.text }}>Copy link</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => Share.share({ message: link }).catch(() => {})} {...tid('consent-optin-link-share')} style={{ paddingVertical: 8, paddingHorizontal: 14, borderRadius: 16, backgroundColor: colors.card }}>
          <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: colors.text }}>Share</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
