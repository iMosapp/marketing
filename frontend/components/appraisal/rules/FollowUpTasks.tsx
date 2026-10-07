import React from 'react';
import { View, Text, Switch } from 'react-native';
import { GOLD, tid } from '../../inbox/ownership';
import { SectionCard, SwitchRow, NumField, TextField } from './fields';

const KINDS: { key: string; label: string; when: string }[] = [
  { key: 'wants_more', label: 'Customer wants more', when: 'when the outcome is Wants more' },
  { key: 'thinking', label: 'Customer is thinking', when: 'when the outcome is Thinking about it' },
  { key: 'manager_changed', label: 'Desk changed the value', when: 'when a manager approves a number other than the suggested one' },
  { key: 'reappraisal', label: 'Value getting old', when: 'daily, for vehicles still owned whose last value is 90+ days old' },
];

// Follow-up tasks go to the salesperson through the normal task list. Internal only: nothing here texts a customer.
export const FollowUpTasksSection = ({ colors, rules, set }: { colors: any; rules: any; set: (patch: any) => void }) => {
  const fu = rules.follow_up || {};
  const tasks = fu.tasks || {};
  const up = (k: string, p: any) => set({ follow_up: { ...fu, tasks: { ...tasks, [k]: { ...(tasks[k] || {}), ...p } } } });
  return (
    <SectionCard colors={colors} title="Follow-up tasks for the salesperson" hint="Tasks land on the rep's list with the customer, the vehicle and the appraisal linked. Placeholders: {first_name} {vehicle} {gap}." testId="rules-tasks">
      {KINDS.map(k => {
        const t = tasks[k.key] || {};
        return (
          <View key={k.key} style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8, gap: 8 }} {...tid(`task-rule-${k.key}`)}>
            <SwitchRow colors={colors} label={k.label} hint={`Task ${k.when}`} value={!!t.enabled} onChange={v => up(k.key, { enabled: v })} testId={`task-enabled-${k.key}`} />
            {t.enabled ? (
              <>
                <TextField colors={colors} label="Task title" value={t.title || ''} onChange={v => up(k.key, { title: v })} placeholder="Follow up with {first_name}" testId={`task-title-${k.key}`} />
                <TextField colors={colors} label="Details" value={t.description || ''} onChange={v => up(k.key, { description: v })} placeholder="What the rep should do" testId={`task-desc-${k.key}`} />
                {k.key !== 'reappraisal' ? <View style={{ flexDirection: 'row' }}><NumField colors={colors} label="Due in days" value={t.days ?? 0} onChange={v => up(k.key, { days: v ?? 0 })} prefix="" testId={`task-days-${k.key}`} /></View> : null}
              </>
            ) : null}
          </View>
        );
      })}
    </SectionCard>
  );
};

// Organization-level safety switch. Default OFF: automated texts never carry dollar amounts unless the organization decides otherwise.
export const MoneyInMessagesCard = ({ colors, value, editable, onChange, mergeFields }: { colors: any; value: boolean; editable: boolean; onChange: (v: boolean) => void; mergeFields: Record<string, string> }) => (
  <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1.5, borderColor: value ? '#FF9500' : colors.border, gap: 10 }} {...tid('rules-money-card')}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Dollar amounts in automated messages</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>Organization-wide. When off, {'{trade_approved_value}'}, {'{trade_customer_wants}'}, {'{trade_gap}'} and the other money fields render blank in every campaign text and email, and Jessi is told not to quote numbers. {editable ? '' : 'Only an organization admin can change this.'}</Text>
      </View>
      <Switch value={value} onValueChange={onChange} disabled={!editable} trackColor={{ true: '#FF9500' }} {...tid('rules-money-switch')} />
    </View>
    <Text style={{ fontSize: 12, fontWeight: '800', color: value ? '#FF9500' : '#34C759' }} {...tid('rules-money-state')}>{value ? 'ON: campaign texts may include trade values. Make sure your templates say what you mean.' : 'OFF (recommended): no trade values go out automatically.'}</Text>
    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>MERGE FIELDS FOR CAMPAIGNS</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
      {Object.entries(mergeFields || {}).map(([k, ex]) => (
        <View key={k} style={{ borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }} {...tid(`merge-field-${k}`)}>
          <Text style={{ fontSize: 11.5, fontWeight: '700', color: GOLD }}>{`{${k}}`}</Text>
          <Text style={{ fontSize: 10.5, color: colors.textSecondary }}>{ex}</Text>
        </View>
      ))}
    </View>
  </View>
);
