import React from 'react';
import { Text } from 'react-native';
import { tid } from '../inbox/ownership';
import { Section, Label, Hint } from '../inbox/InboxEditorParts';
import { Field, ToggleRow } from './parts';

type Props = { form: any; set: (section: string, patch: any) => void; colors: any };

export const DoorsTab = ({ form, set, colors }: Props) => {
  const t = form.doors.text, c = form.doors.call, ch = form.doors.chat || {}, cp = form.copy;
  const setT = (p: any) => set('doors', { text: { ...t, ...p } });
  const setC = (p: any) => set('doors', { call: { ...c, ...p } });
  const setCh = (p: any) => set('doors', { chat: { ...ch, ...p } });
  return (
    <>
      <Section colors={colors} testId="widget-section-chat-door">
        <ToggleRow label="Chat now (Jessi)" hint="Jessi answers hours, inventory and store questions from the Jessi tab. Prices, payments and anything on her never-answer list go to a real person by text." value={!!ch.on} onChange={v => setCh({ on: v })} colors={colors} testId="widget-door-chat-on" />
        {ch.on ? (
          <>
            <Field label="Door title" value={ch.label || ''} onChange={v => setCh({ label: v })} colors={colors} testId="widget-chat-label" maxLength={40} />
            <Field label="One-liner under it" value={ch.intro || ''} onChange={v => setCh({ intro: v })} multiline colors={colors} testId="widget-chat-intro" />
            <Field label="Typing box placeholder" value={ch.placeholder || ''} onChange={v => setCh({ placeholder: v })} colors={colors} testId="widget-chat-placeholder" maxLength={60} />
            <Field label="'Talk to a person' link" hint="Always shown under the chat so nobody feels stuck with a bot." value={ch.human || ''} onChange={v => setCh({ human: v })} colors={colors} testId="widget-chat-human" maxLength={40} />
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 8, lineHeight: 16 }}>What Jessi knows and says lives on the Jessi tab.</Text>
          </>
        ) : null}
      </Section>
      <Section colors={colors} testId="widget-section-text-door">
        <ToggleRow label="Text us" hint="Visitor leaves name + mobile (+ optional message). They get your intake text from the store line and a rep picks it up in the Inbox." value={!!t.on} onChange={v => setT({ on: v })} colors={colors} testId="widget-door-text-on" />
        {t.on ? (
          <>
            <Field label="Door title" value={t.label} onChange={v => setT({ label: v })} colors={colors} testId="widget-text-label" maxLength={40} />
            <Field label="One-liner under it" value={t.intro} onChange={v => setT({ intro: v })} multiline colors={colors} testId="widget-text-intro" />
            <Field label="Button" value={t.button} onChange={v => setT({ button: v })} colors={colors} testId="widget-text-button" maxLength={30} />
            <Field label="After they send" value={t.success} onChange={v => setT({ success: v })} colors={colors} testId="widget-text-success" />
            <ToggleRow label="Ask for a message" hint="Off = just name and number, one tap faster." value={t.ask_message !== false} onChange={v => setT({ ask_message: v })} colors={colors} testId="widget-text-ask-message" />
          </>
        ) : null}
      </Section>

      <Section colors={colors} testId="widget-section-call-door">
        <ToggleRow label="Call me now" hint="Every rep in the ring group gets a call at once. First to press 1 is bridged to the visitor within seconds." value={!!c.on} onChange={v => setC({ on: v })} colors={colors} testId="widget-door-call-on" />
        {c.on ? (
          <>
            <Field label="Door title" value={c.label} onChange={v => setC({ label: v })} colors={colors} testId="widget-call-label" maxLength={40} />
            <Field label="One-liner under it" value={c.intro} onChange={v => setC({ intro: v })} multiline colors={colors} testId="widget-call-intro" />
            <Field label="Button" value={c.button} onChange={v => setC({ button: v })} colors={colors} testId="widget-call-button" maxLength={30} />
            <Field label="While the team's phones ring" value={c.success_ringing} onChange={v => setC({ success_ringing: v })} colors={colors} testId="widget-call-ringing" />
            <Field label="When a rep picks up" hint="{rep} becomes the rep's first name." value={c.success_connected} onChange={v => setC({ success_connected: v })} colors={colors} testId="widget-call-connected" />
            <Field label="Nobody could take it" value={c.missed} onChange={v => setC({ missed: v })} multiline colors={colors} testId="widget-call-missed" />
            <Field label="Store is closed" value={c.after_hours} onChange={v => setC({ after_hours: v })} multiline colors={colors} testId="widget-call-after-hours" />
          </>
        ) : null}
      </Section>

      <Section colors={colors} testId="widget-section-copy">
        <Label colors={colors}>Window text</Label>
        <Hint colors={colors}>{'{store}'} becomes your store name.</Hint>
        <Field label="Title" value={cp.title} onChange={v => set('copy', { title: v })} colors={colors} testId="widget-copy-title" top={false} />
        <Field label="Name field" value={cp.name_label} onChange={v => set('copy', { name_label: v })} colors={colors} testId="widget-copy-name" />
        <Field label="Phone field" value={cp.phone_label} onChange={v => set('copy', { phone_label: v })} colors={colors} testId="widget-copy-phone" />
        <Field label="Message field" value={cp.message_label} onChange={v => set('copy', { message_label: v })} colors={colors} testId="widget-copy-message" />
        <Field label="Consent line (fine print)" hint="Keep the STOP language: it is what makes the first text compliant." value={cp.optin} onChange={v => set('copy', { optin: v })} multiline colors={colors} testId="widget-copy-optin" />
        {!t.on && !c.on && !ch.on ? <Text style={{ fontSize: 12, color: '#FF9500', marginTop: 8 }} {...tid('widget-doors-all-off')}>All three doors are off, so the bubble will not show on your site.</Text> : null}
      </Section>
    </>
  );
};
