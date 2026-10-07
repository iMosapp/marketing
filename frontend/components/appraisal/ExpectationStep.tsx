import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { BigButton, StepTitle, BusyBar, money } from './shared';

type Props = { colors: any; appraisal: any; onSaved: (appraisal: any) => void; showToast: (m: string, t?: any) => void };

// "Has the customer told you what they expect for their trade?" Captured before the manager ever sees it; becomes relationship intel.
export const ExpectationStep = ({ colors, appraisal, onSaved, showToast }: Props) => {
  const [asked, setAsked] = useState<boolean | null>(appraisal.expectation_asked ?? null);
  const [value, setValue] = useState(appraisal.customer_expected_value ? String(appraisal.customer_expected_value) : '');
  const [saving, setSaving] = useState(false);
  const num = parseInt(value.replace(/\D/g, ''), 10);
  const save = async () => {
    setSaving(true);
    try {
      const r = (await api.post(`/appraisals/${appraisal.id}/expectation`, { asked: !!asked, value: asked && num > 0 ? num : null })).data;
      onSaved(r.appraisal);
    } catch (e) { showToast(errText(e, 'Could not save that'), 'error'); }
    finally { setSaving(false); }
  };
  return (
    <View style={{ gap: 12 }}>
      <StepTitle colors={colors} title="Has the customer told you what they expect for their trade?" sub="Their number goes on the manager's review and into the relationship record, so nobody has to ask twice." />
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {[[false, 'No'], [true, 'Yes']].map(([v, l]) => (
          <TouchableOpacity key={String(v)} onPress={() => setAsked(v as boolean)} style={{ flex: 1, height: 56, borderRadius: 14, borderWidth: 1.5, borderColor: asked === v ? GOLD : colors.border, backgroundColor: asked === v ? GOLD + '22' : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid(`expect-${l === 'Yes' ? 'yes' : 'no'}`)}>
            <Text style={{ fontSize: 17, fontWeight: '800', color: asked === v ? GOLD : colors.text }}>{l as string}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {asked ? (
        <View style={{ gap: 6 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>CUSTOMER EXPECTED VALUE</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ fontSize: 26, fontWeight: '800', color: colors.textSecondary }}>$</Text>
            <TextInput value={value} onChangeText={t => setValue(t.replace(/[^\d]/g, '').slice(0, 7))} keyboardType="number-pad" placeholder="32000" placeholderTextColor={colors.textSecondary} autoFocus
              style={{ flex: 1, height: 60, borderRadius: 14, borderWidth: 1.5, borderColor: num > 0 ? GOLD : colors.border, backgroundColor: colors.card, color: colors.text, paddingHorizontal: 16, fontSize: 26, fontVariant: ['tabular-nums'] }} {...tid('expect-value-input')} />
          </View>
          {num > 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('expect-preview')}>Customer wants {money(num)}</Text> : null}
        </View>
      ) : null}
      <BigButton colors={colors} icon="checkmark" label="Continue" onPress={save} primary disabled={asked === null || (asked && !(num > 0)) || saving} testId="expect-continue" />
      <BusyBar text={saving ? 'Saving…' : null} colors={colors} />
    </View>
  );
};
