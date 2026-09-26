import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid, RepCard, fmtPhone } from '../inbox/ownership';
import { Section, Label, Hint, MemberPicker, MergeChips } from '../inbox/InboxEditorParts';
import { Chips, Field, ToggleRow, Stepper } from './parts';

const METHODS = [{ value: 'round_robin', label: 'Take turns' }, { value: 'jump_ball', label: 'First to claim' }, { value: 'weighted_round_robin', label: 'Weighted turns' }];
const TOKENS = ['{{first_name}}', '{{store_name}}'];

type Props = { form: any; set: (section: string, patch: any) => void; colors: any; reps: RepCard[]; inboxes: { id: string; name: string; phone_number?: string }[]; storeName: string | null; storeHours: any };

export const RoutingTab = ({ form, set, colors, reps, inboxes, storeName, storeHours }: Props) => {
  const r = form.routing;
  const ids: string[] = r.call_user_ids || [];
  const toggle = (uid: string) => set('routing', { call_user_ids: ids.includes(uid) ? ids.filter(x => x !== uid) : [...ids, uid] });
  const noCell = reps.filter(p => ids.includes(p.id) && !(p.phone || '').trim());
  const insert = (field: string, tok: string) => set('routing', { [field]: `${r[field] || ''}${r[field] && !r[field].endsWith(' ') ? ' ' : ''}${tok}` });
  return (
    <>
      <Section colors={colors} testId="widget-section-ring">
        <Label colors={colors}>Who rings on "Call me now"</Label>
        <Hint colors={colors}>Everyone checked gets a call at the same moment. The first to press 1 is bridged to the visitor; the other phones stop ringing. Reps off shift (Team Availability) are skipped automatically.</Hint>
        <MemberPicker options={reps} selected={ids} weights={{}} weighted={false} onToggle={toggle} onWeight={() => {}} colors={colors} storeName={storeName || undefined}
          onSelectMany={sel => set('routing', { call_user_ids: sel.length ? Array.from(new Set([...ids, ...sel])) : ids.filter(i => !reps.some(p => p.id === i && p.on_team !== false)) })} />
        {noCell.length ? <Text style={{ fontSize: 12, color: '#FF9500', marginTop: 8, lineHeight: 16 }} {...tid('widget-ring-no-cell')}>{noCell.map(p => p.name.split(' ')[0]).join(', ')} {noCell.length === 1 ? 'has' : 'have'} no cell number on their profile, so their phone cannot ring.</Text> : null}
        {ids.length === 0 ? <Text style={{ fontSize: 12, color: '#FF3B30', marginTop: 8 }} {...tid('widget-ring-empty')}>Nobody is in the ring group. Call requests will be texted and turned into a callback task instead.</Text> : null}
        <Stepper label="Ring the team for" value={Number(r.ring_seconds)} onChange={v => set('routing', { ring_seconds: v })} min={15} max={90} step={5} unit="s" colors={colors} testId="widget-ring-seconds" />
      </Section>

      <Section colors={colors} testId="widget-section-hours">
        <Label colors={colors}>When the store is closed</Label>
        <Chips options={[{ value: 'store', label: 'Text now, call when we open', icon: 'time-outline' }, { value: 'always', label: 'Ring the team anyway', icon: 'call-outline' }]} value={form.hours.mode} onChange={v => set('hours', { mode: v })} colors={colors} testId="widget-hours" />
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 8, lineHeight: 16 }} {...tid('widget-hours-status')}>
          {storeHours?.configured ? `Store hours are set (${storeHours.timezone}). Right now: ${storeHours.open_now ? 'open' : 'closed'}.` : 'No store hours on file yet, so the store counts as always open. Set them under Store Profile.'}
        </Text>
      </Section>

      <Section colors={colors} testId="widget-section-from">
        <Label colors={colors}>"Text us" goes out from</Label>
        <Chips options={[{ value: 'store_line', label: 'The store line', icon: 'business-outline' }, { value: 'rep_line', label: "The rep's own line", icon: 'person-outline' }]} value={r.text_send_from} onChange={v => set('routing', { text_send_from: v })} colors={colors} testId="widget-send-from" />
        {r.text_send_from === 'store_line' ? (
          <View style={{ marginTop: 10, gap: 6 }}>
            {inboxes.length === 0 ? (
              <Text style={{ fontSize: 12, color: '#FF9500', lineHeight: 16 }} {...tid('widget-no-inbox')}>No shared inbox on this store yet, so texts go out from the assigned rep's line. Create one under Inboxes to give the store a shared number.</Text>
            ) : inboxes.map(ib => {
              const on = r.inbox_id === ib.id;
              return (
                <TouchableOpacity key={ib.id} onPress={() => set('routing', { inbox_id: on ? '' : ib.id })} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: on ? GOLD : 'transparent' }} {...tid(`widget-inbox-${ib.id}`)}>
                  <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={18} color={on ? GOLD : colors.textSecondary} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{ib.name}</Text>
                    <Text style={{ fontSize: 11, color: ib.phone_number ? colors.textSecondary : '#FF9500' }}>{ib.phone_number ? fmtPhone(ib.phone_number) : 'No number yet'}</Text>
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        ) : null}
        <Label colors={colors} top>Then hand the thread to</Label>
        <Chips options={METHODS} value={r.assignment_method} onChange={v => set('routing', { assignment_method: v })} colors={colors} testId="widget-method" />
        <ToggleRow label="Ping everyone in the ring group on a new text" value={!!r.notify_all} onChange={v => set('routing', { notify_all: v })} colors={colors} testId="widget-notify-all" />
      </Section>

      <Section colors={colors} testId="widget-section-texts">
        <Label colors={colors}>Automatic texts</Label>
        <Hint colors={colors}>Sent the moment the visitor submits. Tap a token to insert it.</Hint>
        <MergeChips tokens={TOKENS} onInsert={t => insert('intake_text', t)} colors={colors} />
        <Field label='After "Text us"' value={r.intake_text} onChange={v => set('routing', { intake_text: v })} multiline colors={colors} testId="widget-intake-text" top={false} />
        <Field label='After "Call me now" (while we ring the team)' value={r.call_intake_text} onChange={v => set('routing', { call_intake_text: v })} multiline colors={colors} testId="widget-call-intake-text" />
        <Field label="Nobody could take the call" value={r.missed_text} onChange={v => set('routing', { missed_text: v })} multiline colors={colors} testId="widget-missed-text" />
        <Field label="Store closed" value={r.after_hours_text} onChange={v => set('routing', { after_hours_text: v })} multiline colors={colors} testId="widget-after-hours-text" />
      </Section>
    </>
  );
};
