import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { ImportScriptPanel } from '../scripts/ImportScriptSheet';
import { VoicePicker } from './VoicePicker';
const GENDERS = [{ key: 'female', label: 'Woman' }, { key: 'male', label: 'Man' }];
const AGES = [{ key: '', label: 'Any age' }, { key: 'young', label: 'Younger' }, { key: 'older', label: 'Older' }];
import { Sheet, Field, Label, Chip, GoldButton, GOLD, PURPLE, tid, useSheetScroll, industries, industryOf, industryOfDept, deptsFor, loadIndustries, type Challenge, type ChallengeDraft, type Dept } from './shared';

type Scope = { clientId?: string; clientName?: string; industry?: string; departments?: Dept[] };
type Props = { visible: boolean; onClose: () => void; colors: any; initial?: ChallengeDraft | Challenge | null; existing?: Challenge | null; scope?: Scope; onSaved: (c: Challenge) => void };
const blank = { title: '', industry: 'automotive', department: 'sales', direction: 'inbound', runtime: '', purpose: '', body: '', points: '', curveballs: '', guide_note: '', name: '', gender: 'female', age: '', live_voice: '', summary: '', goals: '', objections: '', opening_line: '' };

const toForm = (c: any) => ({ title: c.title || '', industry: c.industry || industryOfDept(c.department).key, department: c.department || 'sales', direction: c.direction === 'outbound' ? 'outbound' : 'inbound', runtime: c.runtime || '', purpose: c.purpose || '', body: c.body || '', points: (c.success_points || []).join('\n'), curveballs: (c.curveballs || []).join('\n'), guide_note: c.guide_note || '',
  name: c.persona?.name || '', gender: c.persona?.gender || (c.persona?.voice === 'male' ? 'male' : 'female'), age: c.persona?.voice === 'young' || c.persona?.voice === 'older' ? c.persona.voice : '', live_voice: c.persona?.live_voice || '', summary: c.persona?.summary || '', goals: c.persona?.goals || '', objections: (c.persona?.objections || []).join('\n'), opening_line: c.persona?.opening_line || '' });

// The paste-a-script panel lives inside the sheet (a second modal on top of a modal freezes iOS) and scrolls itself above the keyboard.
const ImportPanelInSheet = (props: { colors: any; onCancel: () => void; onImported: (d: any) => void; industry?: string; department?: string }) => {
  const sheet = useSheetScroll();
  return <ImportScriptPanel {...props} onFocusInput={(node) => sheet?.ensureVisible(node)} />;
};

// One editor for every way a challenge gets written: by hand, from a pasted script, from a Jessi draft, or editing an existing one.
export const ChallengeEditorSheet = ({ visible, onClose, colors, initial, existing, scope, onSaved }: Props) => {
  const { showToast } = useToast();
  const [f, setF] = useState<any>(blank);
  const [where, setWhere] = useState<'client' | 'library'>('library');
  const [importOpen, setImportOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [, setTick] = useState(0);
  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));
  const lines = (s: string) => s.split('\n').map((x: string) => x.trim()).filter(Boolean);
  const lockedIndustry = !!scope?.clientId || !!existing;
  const depts: Dept[] = scope?.departments?.length && scope.clientId ? scope.departments : deptsFor(f.industry);
  const pack = industryOf(f.industry);
  const pickIndustry = (key: string) => setF((x: any) => ({ ...x, industry: key, department: deptsFor(key)[0]?.key || x.department }));

  useEffect(() => {
    if (!visible) return;
    loadIndustries().then(() => setTick(t => t + 1));
    const base = existing ? toForm(existing) : initial ? toForm(initial) : { ...blank, industry: scope?.industry || blank.industry, department: (scope?.departments?.[0]?.key) || deptsFor(scope?.industry)[0]?.key || blank.department };
    setF(base);
    setWhere(existing ? (existing.client_specific ? 'client' : 'library') : scope?.clientId ? 'client' : 'library');
  }, [visible, existing?.id, initial?.title]);

  const save = async () => {
    setBusy(true);
    const payload = { title: f.title, department: f.department, direction: f.direction, runtime: f.runtime, purpose: f.purpose, body: f.body, success_points: lines(f.points), curveballs: lines(f.curveballs), guide_note: f.guide_note, generated_from: (initial as any)?.generated_from,
      persona: { name: f.name, gender: f.gender, voice: f.age || f.gender, live_voice: f.live_voice || null, summary: f.summary, goals: f.goals, objections: lines(f.objections), opening_line: f.opening_line } };
    try {
      const r = existing ? await api.put(`/shop-clients/challenges/${existing.id}`, payload) : where === 'client' && scope?.clientId ? await api.post(`/shop-clients/${scope.clientId}/challenges`, payload) : await api.post('/shop-clients/challenges', payload);
      showToast(existing ? 'Challenge updated' : where === 'client' ? `Added to ${scope?.clientName}'s pool` : 'Added to the library', 'success'); onSaved(r.data); onClose();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };

  const ready = f.title.trim() && f.body.trim() && f.name.trim() && f.opening_line.trim();
  return (
    <>
      <Sheet visible={visible} onClose={() => { setImportOpen(false); onClose(); }} title={existing ? 'Edit challenge' : 'New challenge'} colors={colors} testID="challenge-sheet"
        footer={<GoldButton label={existing ? 'Save changes' : where === 'client' ? `Add to ${scope?.clientName}'s pool` : 'Add to the library'} onPress={save} busy={busy} disabled={!ready} testID="challenge-save" />}>
        {!existing && !importOpen && (
          <TouchableOpacity onPress={() => setImportOpen(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('challenge-import')}>
            <Ionicons name="clipboard-outline" size={18} color={GOLD} /><Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>Paste a script (Word, email, PDF text) and let Jessi fill this in</Text><Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
        {!existing && importOpen && (
          <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: GOLD + '66' }}>
            <ImportPanelInSheet colors={colors} industry={f.industry} department={f.department} onCancel={() => setImportOpen(false)} onImported={(d) => {
              setF({ ...f, title: d.title || f.title, department: d.category === 'Service' && depts.some(x => x.key === 'service') ? 'service' : f.department, purpose: d.purpose || '', body: d.body || '', points: (d.success_points || []).join('\n'), name: d.persona?.name || '', voice: d.persona?.voice || 'female',
                summary: d.persona?.summary || '', goals: d.persona?.goals || '', objections: (d.persona?.objections || []).join('\n'), opening_line: d.persona?.opening_line || '' });
              setImportOpen(false);
            }} />
          </View>
        )}
        {!existing && !!scope?.clientId && (
          <View style={{ gap: 6 }}><Label t="WHERE IT LIVES" colors={colors} />
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Chip label="Global library (every client)" active={where === 'library'} onPress={() => setWhere('library')} colors={colors} testID="challenge-where-library" />
              <Chip label={`Only ${scope.clientName}`} active={where === 'client'} onPress={() => setWhere('client')} colors={colors} color={PURPLE} testID="challenge-where-client" />
            </View>
          </View>
        )}
        <Field label="TITLE" value={f.title} onChange={(v: string) => set('title', v)} colors={colors} placeholder={f.industry === 'automotive' ? 'Shopper: asks about a lifted Wrangler' : `${pack.customer.replace(/^\w/, c => c.toUpperCase())}: what the call is about`} testID="challenge-title" />
        {!lockedIndustry && <View style={{ gap: 8 }}><Label t="INDUSTRY" colors={colors} /><View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{industries().map(i => <Chip key={i.key} label={i.label} small active={f.industry === i.key} onPress={() => pickIndustry(i.key)} colors={colors} testID={`challenge-industry-${i.key}`} />)}</View></View>}
        <View style={{ gap: 8 }}><Label t="DEPARTMENT" colors={colors} /><View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{depts.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`challenge-dept-${d.key}`} />)}</View></View>
        <View style={{ gap: 6 }}><Label t="CALL DIRECTION (JESSI TELLS THE REP BEFORE IT STARTS)" colors={colors} />
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            <Chip label={`Inbound: they call the ${pack.place}`} active={f.direction === 'inbound'} onPress={() => set('direction', 'inbound')} colors={colors} testID="challenge-direction-inbound" />
            <Chip label="Outbound: rep calls them" active={f.direction === 'outbound'} onPress={() => set('direction', 'outbound')} colors={colors} testID="challenge-direction-outbound" />
          </View>
        </View>
        <Field label="PURPOSE (ONE LINE)" value={f.purpose} onChange={(v: string) => set('purpose', v)} colors={colors} placeholder="What this shop tests" testID="challenge-purpose" />
        <Field label="WHAT A GREAT REP DOES (GRADED FOR SCRIPT ADHERENCE)" value={f.body} onChange={(v: string) => set('body', v)} colors={colors} multiline placeholder="Answer the question, ask for the name and number, offer two times…" testID="challenge-body" />
        <Field label="GRADED POINTS (ONE PER LINE)" value={f.points} onChange={(v: string) => set('points', v)} colors={colors} multiline placeholder={'Answers with store and name\nOffers two appointment times'} testID="challenge-points" />
        <Field label="CURVEBALLS THE SHOPPER MAY THROW IN (ONE PER LINE, OPTIONAL)" value={f.curveballs} onChange={(v: string) => set('curveballs', v)} colors={colors} multiline placeholder={'You only have two minutes\nYou already have a quote from another store'} testID="challenge-curveballs" />
        <Field label="NOTE ON THE REP'S READ-ALONG GUIDE (OPTIONAL)" value={f.guide_note} onChange={(v: string) => set('guide_note', v)} colors={colors} multiline placeholder="Shown at the top of the guide when this shop is texted: who is calling and the two or three things to nail. No curveball spoilers." testID="challenge-guide-note" />
        <View style={{ gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: GOLD + '55' }}>
          <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>The {pack.customer} Jessi plays</Text>
          <Field label="NAME" value={f.name} onChange={(v: string) => set('name', v)} colors={colors} placeholder="Jo Rivera" testID="challenge-persona-name" />
          <View style={{ gap: 6 }}><Label t="VOICE · WHO THEY SOUND LIKE" colors={colors} />
            <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              {GENDERS.map(v => <Chip key={v.key} label={v.label} small active={f.gender === v.key} onPress={() => setF((x: any) => ({ ...x, gender: v.key, live_voice: '' }))} colors={colors} testID={`challenge-gender-${v.key}`} />)}
              <View style={{ width: 1, height: 18, backgroundColor: colors.border, marginHorizontal: 4 }} />
              {AGES.map(v => <Chip key={v.key || 'any'} label={v.label} small active={f.age === v.key} onPress={() => set('age', v.key)} colors={colors} testID={`challenge-age-${v.key || 'any'}`} />)}
            </View>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>The phone voice follows Woman / Man; age only changes the flavour. Keep it matching the name.</Text>
          </View>
          <View style={{ gap: 6 }}><Label t="EXACT VOICE · HEAR IT BEFORE YOU SAVE" colors={colors} />
            <VoicePicker gender={f.gender === 'male' ? 'male' : 'female'} value={f.live_voice} onChange={(v) => set('live_voice', v)} colors={colors} industry={f.industry} department={f.department}
              persona={{ name: f.name, gender: f.gender, voice: f.age || f.gender, summary: f.summary, opening_line: f.opening_line }} />
          </View>
          <Field label="WHO THEY ARE" value={f.summary} onChange={(v: string) => set('summary', v)} colors={colors} multiline placeholder={`32, busy parent, saw {offering} on {store}'s site`} testID="challenge-persona-summary" />
          <Field label="WHAT THEY WANT" value={f.goals} onChange={(v: string) => set('goals', v)} colors={colors} placeholder="Know if it is doable and what it costs" testID="challenge-persona-goals" />
          <Field label={f.direction === 'outbound' ? "OPENING LINE (HOW THEY ANSWER WHEN THE REP CALLS)" : "OPENING LINE (SAID RIGHT AFTER THE REP ANSWERS)"} value={f.opening_line} onChange={(v: string) => set('opening_line', v)} colors={colors} placeholder={`Hey, I'm calling about {offering}, is that still available?`} testID="challenge-persona-opening" />
          <Field label="OBJECTIONS (ONE PER LINE)" value={f.objections} onChange={(v: string) => set('objections', v)} colors={colors} multiline placeholder={'Can you just give me a price?\nThe place down the road is cheaper'} testID="challenge-persona-objections" />
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{'{offering}'} becomes one of the account's {pack.offering.plural} and {'{store}'} becomes the {pack.business} name on every call.</Text>
        </View>
      </Sheet>
    </>
  );
};
