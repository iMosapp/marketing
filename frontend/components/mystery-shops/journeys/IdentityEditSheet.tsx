import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, GOLD, tid } from '../shared';
import { CHANNEL_WORD, type Identity, type JourneyOptions } from './shared';

type Props = { campaignId: string; identity: Identity | null; onClose: () => void; colors: any; opts: JourneyOptions | null; onSaved: () => void };

const lines = (v: string) => v.split('\n').map(x => x.trim()).filter(Boolean);

// Everything the admin may change about a virtual customer before (name, email) and during (how they behave) the shop.
export const IdentityEditSheet = ({ campaignId, identity, onClose, colors, opts, onSaved }: Props) => {
  const { showToast } = useToast();
  const [f, setF] = useState({ first: '', last: '', interest: '', goals: '', timeline: '', personality: '', channel_prefs: [] as string[], questions: '', objections: '', ai_instructions: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const set = (k: string, v: any) => setF(x => ({ ...x, [k]: v }));
  useEffect(() => {
    if (!identity) return;
    const p = identity.persona;
    setErr('');
    setF({ first: p.first || '', last: p.last || '', interest: p.offering || '', goals: p.goals || '', timeline: p.timeline || '', personality: p.personality || '', channel_prefs: p.channel_prefs || [], questions: (p.questions || []).join('\n'), objections: (p.objections || []).join('\n'), ai_instructions: p.ai_instructions || '' });
  }, [identity?.id]);
  const draft = identity?.status === 'draft';
  const togglePref = (c: string) => set('channel_prefs', f.channel_prefs.includes(c) ? f.channel_prefs.filter(x => x !== c) : [...f.channel_prefs, c]);
  const save = async () => {
    if (!identity) return;
    setBusy(true); setErr('');
    try {
      const body: any = { interest: f.interest.trim(), goals: f.goals.trim(), timeline: f.timeline.trim(), personality: f.personality.trim(), channel_prefs: f.channel_prefs, questions: lines(f.questions), objections: lines(f.objections), ai_instructions: f.ai_instructions.trim() };
      if (draft && (f.first.trim() !== identity.persona.first || f.last.trim() !== identity.persona.last)) { body.first = f.first.trim(); body.last = f.last.trim(); }
      await api.patch(`/journeys/${campaignId}/identities/${identity.id}`, body);
      showToast('Identity saved', 'success'); onClose(); onSaved();
    } catch (e: any) { setErr(e?.response?.data?.detail || 'Could not save'); }
    finally { setBusy(false); }
  };
  return (
    <Sheet visible={!!identity} onClose={onClose} title={identity ? `Edit ${identity.persona.first}` : 'Identity'} colors={colors} testID="identity-edit" error={err}
      footer={<GoldButton label="Save identity" onPress={save} busy={busy} icon="checkmark" testID="identity-edit-save" />}>
      {!!identity && (
        <>
          {draft ? (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1 }}><Field label="FIRST NAME" value={f.first} onChange={(v: string) => set('first', v)} colors={colors} testID="identity-edit-first" /></View>
              <View style={{ flex: 1 }}><Field label="LAST NAME" value={f.last} onChange={(v: string) => set('last', v)} colors={colors} testID="identity-edit-last" /></View>
            </View>
          ) : <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('identity-edit-locked')}>{identity.persona.name} · {identity.persona.email}. Name and email are locked: the store already has them.</Text>}
          {draft && <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('identity-edit-email')}>Email follows the name: {identity.persona.email}</Text>}
          <Field label="ASKING ABOUT" value={f.interest} onChange={(v: string) => set('interest', v)} colors={colors} placeholder="2022 Jeep Grand Cherokee" testID="identity-edit-interest" />
          <Field label="WHAT THEY WANT (THE MESSAGE IN THE LEAD)" value={f.goals} onChange={(v: string) => set('goals', v)} colors={colors} multiline testID="identity-edit-goals" />
          <View style={{ gap: 6 }}>
            <Label t="BUYING TIMELINE" colors={colors} />
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{(opts?.timelines || []).map(t => <Chip key={t} small label={t} active={f.timeline === t} onPress={() => set('timeline', t)} colors={colors} testID={`identity-edit-timeline-${t.replace(/[^a-z0-9]+/gi, '-')}`} />)}</View>
            <Field value={f.timeline} onChange={(v: string) => set('timeline', v)} colors={colors} placeholder="or write your own" testID="identity-edit-timeline" />
          </View>
          <View style={{ gap: 6 }}>
            <Label t="PERSONALITY" colors={colors} />
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{(opts?.personalities || []).map(t => <Chip key={t} small label={t.split(',')[0]} active={f.personality === t} onPress={() => set('personality', t)} colors={colors} testID={`identity-edit-personality-${t.split(',')[0].replace(/[^a-z0-9]+/gi, '-')}`} />)}</View>
            <Field value={f.personality} onChange={(v: string) => set('personality', v)} colors={colors} placeholder="direct and busy, wants numbers" testID="identity-edit-personality" />
          </View>
          <View style={{ gap: 6 }}>
            <Label t="PREFERS TO BE REACHED BY (TAP IN ORDER)" colors={colors} />
            <View style={{ flexDirection: 'row', gap: 6 }}>{['text', 'email', 'call'].map(c => { const i = f.channel_prefs.indexOf(c); return <Chip key={c} small label={i >= 0 ? `${i + 1}. ${CHANNEL_WORD[c]}` : CHANNEL_WORD[c]} active={i >= 0} onPress={() => togglePref(c)} colors={colors} testID={`identity-edit-pref-${c}`} />; })}</View>
          </View>
          <Field label="QUESTIONS THEY STILL NEED ANSWERED (ONE PER LINE)" value={f.questions} onChange={(v: string) => set('questions', v)} colors={colors} multiline placeholder={'Is it still available?\nWhat is the out-the-door price?'} testID="identity-edit-questions" />
          <Field label="OBJECTIONS THEY MAY RAISE (ONE PER LINE, OPTIONAL)" value={f.objections} onChange={(v: string) => set('objections', v)} colors={colors} multiline placeholder="The price online is higher than the other store" testID="identity-edit-objections" />
          <Field label="EXTRA INSTRUCTIONS FOR THE AI" value={f.ai_instructions} onChange={(v: string) => set('ai_instructions', v)} colors={colors} multiline placeholder="Mentions a trade only if asked. Works nights, cannot take calls before noon." testID="identity-edit-instructions" />
          <Text style={{ fontSize: 12, color: GOLD, lineHeight: 16 }} {...tid('identity-edit-nocommit')}>Hard rule, always on: never confirms an appointment, never commits to buy.</Text>
        </>
      )}
    </Sheet>
  );
};
