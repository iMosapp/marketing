import React, { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, SPACE, TYPE, tid } from '../ui/tokens';
import { ScopeToggle } from './consentParts';

export const VERBAL_SCOPES = ['requested_info', 'transactional'];

/** Add Contact: optional verbal consent (requested info / transactional). Nothing checked = consent stays UNKNOWN. */
export function NewContactConsent({ value, onChange, colors }: { value: string[]; onChange: (v: string[]) => void; colors: any }) {
  const [stmts, setStmts] = useState<any>(null);
  useEffect(() => { api.get('/consent/statements').then(r => setStmts(r.data)).catch(() => {}); }, []);
  const toggle = (s: string) => onChange(value.includes(s) ? value.filter(x => x !== s) : [...value, s]);
  return (
    <View style={{ marginHorizontal: 16, marginBottom: 12, gap: SPACE.sm }} {...tid('new-contact-consent')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Ionicons name="shield-checkmark-outline" size={16} color={GOLD} />
        <Text style={{ fontSize: TYPE.sub, fontWeight: '800', color: colors.text }}>Texting permission</Text>
        <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary }}>optional · verbal, in person</Text>
      </View>
      {VERBAL_SCOPES.map(s => <ScopeToggle key={s} scope={s} on={value.includes(s)} onPress={() => toggle(s)} colors={colors} statement={stmts?.scopes?.[s]?.text} />)}
      <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary, lineHeight: 16 }}>
        Leave unchecked if you haven't asked yet. Marketing texts need their own opt-in: open the contact after saving and tap Record.
      </Text>
    </View>
  );
}
