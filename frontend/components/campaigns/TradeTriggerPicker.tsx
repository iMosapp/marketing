import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';

export const TRADE_TRIGGER_LABELS: Record<string, string> = {
  'trade_appraisal.submitted': 'Trade appraisal submitted to the desk', 'trade_appraisal.approved': 'Trade value approved', 'trade_appraisal.accepted': 'Customer accepted the trade value',
  'trade_appraisal.wants_more': 'Customer wants more', 'trade_appraisal.thinking': 'Customer is thinking about it', 'trade_appraisal.not_trading': 'Customer is not trading',
  'trade_appraisal.closed': 'Trade appraisal closed (any outcome)', 'trade_appraisal.reappraised': 'Vehicle reappraised',
};
export const tradeTriggerSummary = (events: string[]) => (events.length === 0 ? 'Pick a trade appraisal moment' : events.length === 1 ? (TRADE_TRIGGER_LABELS[events[0]] || events[0]) : `${events.length} trade appraisal moments`);

// Third kind of trigger: a moment in a trade appraisal. Lists the events and the {trade_*} merge fields, with the org's money rule spelled out.
export const TradeTriggerPicker = ({ colors, selected, onChange, disabled }: { colors: any; selected: string[]; onChange: (events: string[]) => void; disabled?: boolean }) => {
  const [opts, setOpts] = useState<any | null>(null);
  useEffect(() => { api.get('/appraisals/campaign-options').then(r => setOpts(r.data)).catch(() => setOpts({ triggers: TRADE_TRIGGER_LABELS, merge_fields: {}, allow_trade_values: false })); }, []);
  const triggers: Record<string, string> = opts?.triggers || TRADE_TRIGGER_LABELS;
  const toggle = (k: string) => onChange(selected.includes(k) ? selected.filter(e => e !== k) : [...selected, k]);
  return (
    <View style={{ gap: 10 }} {...tid('trade-trigger-picker')}>
      <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>The plan starts for the customer the moment one of these happens on their trade appraisal. Store or organization plans win over a personal copy with the same name.</Text>
      <View style={{ gap: 6 }}>
        {Object.entries(triggers).map(([k, label]) => { const on = selected.includes(k); return (
          <TouchableOpacity key={k} onPress={() => !disabled && toggle(k)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 11, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`trade-trigger-${k.split('.')[1]}`)}>
            <Ionicons name={on ? 'checkbox' : 'square-outline'} size={18} color={on ? GOLD : colors.textSecondary} />
            <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }}>{label}</Text>
          </TouchableOpacity>
        ); })}
      </View>
      <View style={{ borderRadius: 12, padding: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 6 }} {...tid('trade-tags-help')}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>TAGS ADDED AUTOMATICALLY (USE THEM AS "A TAG" TRIGGERS OR IN CONTACT FILTERS)</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {Object.entries(opts?.tags || {}).map(([k, help]: any) => (
            <View key={k} style={{ borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }} {...tid(`trade-tag-${k}`)}>
              <Text style={{ fontSize: 11.5, fontWeight: '700', color: colors.text }}>{k}</Text>
              <Text style={{ fontSize: 10.5, color: colors.textSecondary }}>{help}</Text>
            </View>
          ))}
        </View>
        <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }}>Every submitted trade adds trade-appraised. Each outcome replaces the customer's trade tags with the current one plus a gap bucket, so a customer is always in exactly one trade group. Switch off under Appraisal Rules › After the customer answers.</Text>
      </View>
      <View style={{ borderRadius: 12, padding: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 6 }} {...tid('trade-merge-fields')}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>MERGE FIELDS YOU CAN USE IN THE TEXTS</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {Object.entries(opts?.merge_fields || {}).map(([k, ex]: any) => (
            <View key={k} style={{ borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }}>
              <Text style={{ fontSize: 11.5, fontWeight: '700', color: GOLD }}>{`{${k}}`}</Text>
              <Text style={{ fontSize: 10.5, color: colors.textSecondary }}>{ex}</Text>
            </View>
          ))}
        </View>
        <Text style={{ fontSize: 11.5, fontWeight: '700', color: opts?.allow_trade_values ? '#FF9500' : '#34C759' }} {...tid('trade-money-rule')}>
          {opts?.allow_trade_values ? 'Your organization allows dollar amounts in automated messages, so the money fields fill in.' : 'Your organization keeps dollar amounts out of automated messages: the money fields render blank. An org admin can change this under Appraisal Rules.'}
        </Text>
      </View>
    </View>
  );
};
