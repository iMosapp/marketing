import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { GOLD, tid, errText } from '../../inbox/ownership';
import { showConfirm } from '../../../services/alert';
import { money } from '../shared';

type Mode = 'change' | 'request_info' | 'decline' | null;
type Props = { colors: any; appraisal: any; onDecided: (desk: any) => void; showToast: (m: string, t?: any, d?: number) => void };
const META: Record<string, { title: string; hint: string; placeholder: string; color: string; cta: string }> = {
  change: { title: 'Approve a different value', hint: 'The suggested ACV stays on the record next to your number.', placeholder: 'Why (optional, the rep sees it)', color: '#34C759', cta: 'Approve this value' },
  request_info: { title: 'Ask the salesperson for more', hint: 'Sends it back; the rep fixes it and resubmits.', placeholder: 'What do you need? Photos of the tailgate, a second odometer shot…', color: '#FF9500', cta: 'Send back' },
  decline: { title: 'Decline this trade', hint: 'The rep can still record what the customer said.', placeholder: 'Why (the rep sees it)', color: '#FF3B30', cta: 'Decline' },
};

// Four decisions, no menus: Approve as suggested · Change value · Ask for more · Decline. Reason inline, confirm once.
export const DeskDecisionBar = ({ colors, appraisal: a, onDecided, showToast }: Props) => {
  const [mode, setMode] = useState<Mode>(null);
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const suggested = a.suggested_acv;
  const send = async (action: string, body: any) => {
    setBusy(true);
    try { const d = (await api.post(`/appraisals/${a.id}/decide`, { action, ...body })).data; onDecided(d); setMode(null); setValue(''); setReason(''); showToast(action === 'request_info' ? 'Sent back to the salesperson' : action === 'decline' ? 'Declined' : `Approved ${money(d.approved_value)}`, 'success', 3500); }
    catch (e) { showToast(errText(e, 'Could not record that decision'), 'error', 5000); }
    finally { setBusy(false); }
  };
  const approve = () => showConfirm(`Approve ${money(suggested)}?`, `${a.contact_name} · ${a.vehicle_label}. The suggested ACV becomes the approved trade value.`, () => send('approve', {}), undefined, 'Approve');
  const confirm = () => {
    if (!mode) return;
    if (mode === 'change') {
      const n = parseInt(value.replace(/\D/g, ''), 10);
      if (!n) { showToast('Enter the approved trade value', 'error'); return; }
      const delta = suggested != null ? n - suggested : null;
      showConfirm(`Approve ${money(n)}?`, delta != null ? `${delta >= 0 ? '+' : '-'}${money(Math.abs(delta))} vs the suggested ${money(suggested)}.` : 'There was no suggested value; this becomes the trade value.', () => send('change', { value: n, reason }), undefined, 'Approve');
      return;
    }
    if (reason.trim().length < 3) { showToast(mode === 'decline' ? 'Give the rep a reason' : 'Tell the rep what you need', 'error'); return; }
    send(mode, { reason });
  };
  if (!a.abilities?.decide) {
    return a.abilities?.decide_blocked_reason ? <Text style={{ fontSize: 12.5, color: colors.textSecondary, textAlign: 'center', padding: 12 }} {...tid('decide-blocked')}>{a.abilities.decide_blocked_reason}</Text> : null;
  }
  const m = mode ? META[mode] : null;
  return (
    <View style={{ borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg, padding: 12, gap: 10 }} {...tid('decision-bar')}>
      {m ? (
        <View style={{ gap: 8 }} {...tid(`decision-form-${mode}`)}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>{m.title}</Text>
            <TouchableOpacity onPress={() => setMode(null)} hitSlop={10} {...tid('decision-cancel')}><Ionicons name="close" size={22} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>{m.hint}</Text>
          {mode === 'change' ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, height: 52, borderRadius: 14, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1.5, borderColor: m.color }}>
              <Text style={{ fontSize: 20, fontWeight: '800', color: colors.textSecondary }}>$</Text>
              <TextInput value={value} onChangeText={t => setValue(t.replace(/\D/g, '').slice(0, 7))} keyboardType="number-pad" placeholder={suggested != null ? `${suggested}` : 'Trade value'} placeholderTextColor={colors.textSecondary} style={{ flex: 1, fontSize: 20, fontWeight: '800', color: colors.text }} autoFocus {...tid('decision-value')} />
              {suggested != null ? <Text style={{ fontSize: 11, color: colors.textSecondary }}>suggested {money(suggested)}</Text> : null}
            </View>
          ) : null}
          <TextInput value={reason} onChangeText={setReason} placeholder={m.placeholder} placeholderTextColor={colors.textSecondary} multiline autoFocus={mode !== 'change'} style={{ minHeight: 56, borderRadius: 14, padding: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, color: colors.text, fontSize: 14, textAlignVertical: 'top' }} {...tid('decision-reason')} />
          <TouchableOpacity onPress={confirm} disabled={busy} style={{ height: 50, borderRadius: 14, backgroundColor: m.color, alignItems: 'center', justifyContent: 'center', opacity: busy ? 0.6 : 1 }} {...tid('decision-confirm')}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text style={{ fontSize: 15, fontWeight: '800', color: '#fff' }}>{m.cta}</Text>}
          </TouchableOpacity>
        </View>
      ) : (
        <>
          <TouchableOpacity onPress={approve} disabled={busy || suggested == null} style={{ height: 54, borderRadius: 16, backgroundColor: suggested == null ? colors.border : '#34C759', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('decide-approve')}>
            <Ionicons name="checkmark-circle" size={20} color="#fff" />
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#fff' }}>{suggested != null ? `Approve ${money(suggested)}` : 'No suggested value: enter one'}</Text>
          </TouchableOpacity>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Small colors={colors} icon="create" label="Change value" color="#34C759" onPress={() => setMode('change')} testId="decide-change" />
            <Small colors={colors} icon="help-circle" label="Ask for more" color="#FF9500" onPress={() => setMode('request_info')} testId="decide-request-info" />
            <Small colors={colors} icon="close-circle" label="Decline" color="#FF3B30" onPress={() => setMode('decline')} testId="decide-decline" />
          </View>
        </>
      )}
    </View>
  );
};

const Small = ({ colors, icon, label, color, onPress, testId }: { colors: any; icon: any; label: string; color: string; onPress: () => void; testId: string }) => (
  <TouchableOpacity onPress={onPress} style={{ flex: 1, height: 46, borderRadius: 14, borderWidth: 1, borderColor: color, backgroundColor: color + '14', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 5 }} {...tid(testId)}>
    <Ionicons name={icon} size={15} color={color} /><Text style={{ fontSize: 12.5, fontWeight: '800', color }} numberOfLines={1}>{label}</Text>
  </TouchableOpacity>
);
