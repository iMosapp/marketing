import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Platform, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useCompliance } from '../../store/complianceStore';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, RADIUS, RED, SPACE, TYPE, tid, tint } from '../ui/tokens';
import { MethodPicker, OptInLinkBox, ScopeToggle } from './consentParts';

const ALL_SCOPES = ['requested_info', 'transactional', 'marketing'];

/** Global host (app/_layout.tsx): opens whenever a send is refused for consent or opt-out, or a contact card asks to record consent. */
export function ConsentSheetHost() {
  const ask = useCompliance(s => s.ask);
  if (!ask) return null;
  return <ConsentSheet key={`${ask.phone || ''}:${ask.contact_id || ''}:${ask.code}`} />;
}

function ConsentSheet() {
  const { colors } = useThemeStore();
  const ask = useCompliance(s => s.ask)!;
  const settle = useCompliance(s => s.settle);
  const optedOut = ask.code === 'opted_out';
  const needs = ask.needs || [];
  const [stmts, setStmts] = useState<any>(null);
  const [scopes, setScopes] = useState<string[]>(needs.filter(s => s !== 'marketing'));
  const [method, setMethod] = useState(needs.includes('marketing') ? 'written_signature' : 'verbal_in_person');
  const [reference, setReference] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (optedOut) return;
    api.get('/consent/statements', { params: ask.contact_id ? { contact_id: ask.contact_id } : {} }).then(r => setStmts(r.data)).catch(() => {});
  }, []);

  const toggle = (s: string) => setScopes(p => (p.includes(s) ? p.filter(x => x !== s) : [...p, s]));
  const verbalMarketing = scopes.includes('marketing') && method === 'verbal_in_person';
  const missingEvidence = method === 'written_signature' && !reference.trim();
  const canRecord = scopes.length > 0 && !verbalMarketing && !missingEvidence && !busy;
  const who = ask.name || (ask.phone ? `the number ending ${ask.phone.slice(-4)}` : 'this contact');

  const record = async () => {
    setBusy(true); setErr('');
    const body: any = { scopes, method, source: ask.manual ? 'contact_card' : 'composer', statement_version: stmts?.version };
    if (method === 'written_signature') body.evidence = { reference: reference.trim() };
    try {
      if (ask.contact_id) await api.post(`/consent/contact/${ask.contact_id}`, body);
      else await api.post('/consent/phone', { ...body, phone: ask.phone });
      settle(true);
    } catch (e: any) {
      const d = e?.response?.data?.detail;
      setErr((d && typeof d === 'object' ? d.message : d) || 'Could not record consent. Try again.');
    } finally { setBusy(false); }
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={() => settle(false)}>
      <View style={{ flex: 1, backgroundColor: '#00000099', justifyContent: 'flex-end' }}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, maxHeight: '92%', width: '100%', maxWidth: 640, alignSelf: 'center' }} {...tid('consent-sheet')}>
          <ScrollView contentContainerStyle={{ padding: SPACE.lg, paddingBottom: Platform.OS === 'ios' ? 40 : SPACE.lg, gap: SPACE.md }} keyboardShouldPersistTaps="handled">
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: tint(optedOut ? RED : GOLD, 0.15) }}>
                <Ionicons name={optedOut ? 'hand-left' : 'shield-checkmark'} size={18} color={optedOut ? RED : GOLD} />
              </View>
              <Text style={{ flex: 1, fontSize: TYPE.section, fontWeight: '800', color: colors.text }} {...tid('consent-sheet-title')}>
                {optedOut ? 'This contact opted out' : ask.manual ? 'Record texting permission' : 'Permission needed to text'}
              </Text>
            </View>
            <Text style={{ fontSize: TYPE.body, color: colors.textSecondary, lineHeight: 21 }} {...tid('consent-sheet-message')}>
              {optedOut ? ask.message : ask.manual ? `What has ${who} agreed to receive by text?` : `${ask.message || 'No consent is recorded yet.'} Ask ${who}, then record their answer.`}
            </Text>
            {!optedOut && (
              <>
                {ALL_SCOPES.map(s => <ScopeToggle key={s} scope={s} on={scopes.includes(s)} onPress={() => toggle(s)} colors={colors} statement={stmts?.scopes?.[s]?.text} />)}
                <Text style={{ fontSize: TYPE.label, fontWeight: '800', color: colors.textTertiary, letterSpacing: 1, marginTop: 4 }}>HOW THEY AGREED</Text>
                <MethodPicker value={method} onChange={setMethod} colors={colors} />
                {method === 'written_signature' && (
                  <TextInput value={reference} onChangeText={setReference} placeholder="Form reference (e.g. deal jacket #, form ID)" placeholderTextColor={colors.textTertiary}
                    style={{ borderWidth: 1, borderColor: colors.border, borderRadius: RADIUS.sm, padding: 12, fontSize: TYPE.body, color: colors.text }} {...tid('consent-evidence-input')} />
                )}
                {verbalMarketing && (
                  <Text style={{ fontSize: TYPE.sub, color: RED, lineHeight: 19 }} {...tid('consent-marketing-warning')}>
                    A verbal OK can't authorize marketing texts. Use a signed form, or let them opt in on their own phone below.
                  </Text>
                )}
                {ask.contact_id ? <OptInLinkBox contactId={ask.contact_id} colors={colors} /> : null}
                {err ? <Text style={{ fontSize: TYPE.sub, color: RED }} {...tid('consent-sheet-error')}>{err}</Text> : null}
                <TouchableOpacity onPress={record} disabled={!canRecord} {...tid('consent-record-btn')}
                  style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: GOLD, borderRadius: RADIUS.md, paddingVertical: 15, opacity: canRecord ? 1 : 0.45 }}>
                  {busy ? <ActivityIndicator color="#111" /> : <Ionicons name="checkmark-circle" size={20} color="#111" />}
                  <Text style={{ fontSize: TYPE.body, fontWeight: '800', color: '#111' }}>{ask.manual ? 'They agreed · Save' : 'They agreed · Save and send'}</Text>
                </TouchableOpacity>
              </>
            )}
            <TouchableOpacity onPress={() => settle(false)} style={{ alignItems: 'center', paddingVertical: 10 }} {...tid('consent-cancel-btn')}>
              <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: colors.textSecondary }}>{optedOut ? 'OK' : 'Not now'}</Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
