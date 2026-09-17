import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import api from '../../services/api';
import { useLiveJessiLauncher } from '../jessi/LiveJessiProvider';
import { VoicePicker, type Voice } from '../jessi/VoiceLabControls';
import { liveSupported, LIVE_UNSUPPORTED_BODY } from '../../hooks/useLiveJessi';
import { Sheet, Field, Label, Chip, GoldButton, tid, industries, industryOf, deptsFor, loadIndustries, stripTitlePrefix, type Challenge } from './shared';

type Props = { visible: boolean; onClose: () => void; colors: any };
type Options = { voices: Voice[]; configured: boolean; reason: string | null };
const blank = { industry: 'automotive', department: 'sales', script_id: null as string | null, direction: 'inbound' as 'inbound' | 'outbound', voice: '', store_name: '', offering: '' };

// Hear the GPT-Live shopper in the browser before a real shop call: same persona, curveballs and voices, you play the rep.
export const ShopperAuditionSheet = ({ visible, onClose, colors }: Props) => {
  const jessi = useLiveJessiLauncher();
  const [f, setF] = useState(blank);
  const [opts, setOpts] = useState<Options | null>(null);
  const [challenges, setChallenges] = useState<Challenge[] | null>(null);
  const [, setTick] = useState(0);
  const set = (k: string, v: any) => setF(x => ({ ...x, [k]: v }));
  const ind = industryOf(f.industry);
  const depts = deptsFor(f.industry);

  useEffect(() => {
    if (!visible) return;
    setF(blank);
    loadIndustries().then(() => setTick(t => t + 1));
    api.get('/shop-clients/audition/options').then(r => setOpts(r.data)).catch(() => setOpts({ voices: [], configured: false, reason: 'Could not load the voices' }));
  }, [visible]);
  useEffect(() => {
    if (!visible) return;
    setChallenges(null); set('script_id', null);
    api.get('/shop-clients/demo/challenges', { params: { industry: f.industry } }).then(r => setChallenges(r.data.challenges)).catch(() => setChallenges([]));
  }, [visible, f.industry]);
  useEffect(() => { set('script_id', null); }, [f.department]);
  const pickIndustry = (key: string) => setF(x => ({ ...x, industry: key, department: deptsFor(key)[0]?.key || x.department, script_id: null }));

  const pool = (challenges || []).filter(c => c.department === f.department);
  const picked = pool.find(c => c.id === f.script_id) || null;
  const rep = (depts.find(d => d.key === f.department)?.rep || 'a rep').replace(/^(a|an) /, '');
  const supported = liveSupported();
  const ready = !!opts?.configured && supported && (challenges === null || pool.length > 0);

  const fill = (s?: string) => (s || '').replace(/\{vehicle\}/g, f.offering.trim() || `the ${ind.offering.label.toLowerCase()}`).replace(/\{store\}/g, f.store_name.trim() || `your ${ind.business}`);
  const talk = () => {
    const who = picked?.persona?.name || 'The shopper';
    onClose();
    setTimeout(() => jessi.open({
      options: { mode: 'shopper', overrides: { industry: f.industry, department: f.department, script_id: f.script_id, direction: f.direction, voice: f.voice || null, store_name: f.store_name, offering: f.offering } },
      title: `Shopper · ${who}`, who,
      hint: f.direction === 'inbound' ? `The shopper is calling ${f.store_name || `your ${ind.business}`}. Pick up like you would at work: "Thanks for calling, this is ${rep === 'a rep' ? 'me' : rep}".` : `You just called ${who} back. Say hi and take it from there.`,
    }), 350);
  };

  return (
    <Sheet visible={visible} onClose={onClose} title="Hear the GPT-Live shopper" colors={colors} testID="audition-sheet" error={opts && !opts.configured ? (opts.reason || '') : !supported ? LIVE_UNSUPPORTED_BODY : ''}
      footer={<GoldButton label={ready ? `Talk to ${picked?.persona?.name || 'the shopper'}` : opts && !opts.configured ? 'Needs OPENAI_API_KEY on the server' : !supported ? 'Open this on the web to listen' : 'No challenges for this department'} onPress={talk} disabled={!ready} testID="audition-talk" icon="radio" />}>
      <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }} {...tid('audition-how')}>A real shop call in your browser, no phone, nothing graded or saved to a client. Pick the challenge and a voice, then you play {rep}: answer the phone, sell, dodge, interrupt her. She hangs up on her own when the conversation is over. Same persona, same curveballs, same rules the reps get.</Text>
      <View style={{ gap: 6 }}>
        <Label t="WHO CALLS WHO" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Chip label="Shopper calls you" active={f.direction === 'inbound'} onPress={() => set('direction', 'inbound')} colors={colors} testID="audition-direction-inbound" />
          <Chip label="You call her back" active={f.direction === 'outbound'} onPress={() => set('direction', 'outbound')} colors={colors} testID="audition-direction-outbound" />
        </View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="INDUSTRY" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{industries().map(i => <Chip key={i.key} label={i.label} small active={f.industry === i.key} onPress={() => pickIndustry(i.key)} colors={colors} testID={`audition-industry-${i.key}`} />)}</View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="DEPARTMENT" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{depts.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`audition-dept-${d.key}`} />)}</View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="CHALLENGE" colors={colors} />
        {challenges !== null && pool.length === 0 ? (
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('audition-no-challenges')}>No {ind.label.toLowerCase()} challenges for this department yet. Open the Challenge library and let Jessi write the starters first.</Text>
        ) : (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            <Chip label="Surprise me" small active={!f.script_id} onPress={() => set('script_id', null)} colors={colors} testID="audition-challenge-random" />
            {pool.map(c => <Chip key={c.id} label={stripTitlePrefix(c.title)} small active={f.script_id === c.id} onPress={() => set('script_id', c.id)} colors={colors} testID={`audition-challenge-${c.id}`} />)}
          </View>
        )}
        {!!picked && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('audition-persona')}>{picked.persona?.name}: {fill(picked.persona?.summary)} Opens with "{fill(picked.persona?.opening_line)}"</Text>}
      </View>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1 }}><Field label={`YOUR ${ind.business.toUpperCase()} (OPTIONAL)`} value={f.store_name} onChange={(v: string) => set('store_name', v)} colors={colors} placeholder={f.industry === 'automotive' ? 'LHM Jeep' : `The ${ind.business} name`} testID="audition-store" /></View>
        <View style={{ flex: 1 }}><Field label={`${ind.offering.label.toUpperCase()} (OPTIONAL)`} value={f.offering} onChange={(v: string) => set('offering', v)} colors={colors} placeholder={ind.offering.hint} testID="audition-offering" /></View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="HER VOICE" colors={colors} />
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>Leave it on Auto to hear the voice a real shop would pick for this persona.</Text>
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}><Chip label="Auto (like a real shop)" small active={!f.voice} onPress={() => set('voice', '')} colors={colors} testID="audition-voice-auto" /></View>
        {!!opts?.voices?.length && <VoicePicker voices={opts.voices} value={f.voice} onChange={(id) => set('voice', id)} />}
      </View>
    </Sheet>
  );
};
