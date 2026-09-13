import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { ImportScriptSheet } from '../scripts/ImportScriptSheet';
import { VOICES } from '../scripts/shared';
import { Sheet, Field, Label, Chip, GoldButton, DEPTS, deptLabel, GOLD, RED, PURPLE, tid, type Challenge, type Client } from './shared';

const blank = { title: '', department: 'sales', purpose: '', body: '', points: '', name: '', voice: 'female', summary: '', goals: '', objections: '', opening_line: '' };

// The challenge pool: global scenarios every client gets + scenarios written for this client only.
export const ChallengesTab = ({ client, colors }: { client: Client; colors: any }) => {
  const { showToast } = useToast();
  const [rows, setRows] = useState<Challenge[] | null>(null);
  const [open, setOpen] = useState<Challenge | null>(null);
  const [sheet, setSheet] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [f, setF] = useState<any>(blank);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));

  const load = async () => { try { const r = await api.get(`/shop-clients/${client.id}/challenges`); setRows(r.data.challenges); } catch { setRows([]); } };
  useEffect(() => { load(); }, [client.id]);

  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/shop-clients/${client.id}/challenges`, { title: f.title, department: f.department, purpose: f.purpose, body: f.body, success_points: f.points.split('\n').map((x: string) => x.trim()).filter(Boolean),
        persona: { name: f.name, voice: f.voice, summary: f.summary, goals: f.goals, objections: f.objections.split('\n').map((x: string) => x.trim()).filter(Boolean), opening_line: f.opening_line } });
      setSheet(false); setF(blank); load(); showToast('Challenge added for this client', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };
  const remove = (c: Challenge) => showConfirm(c.client_specific ? 'Delete this challenge?' : 'Hide this global challenge?', c.client_specific ? 'Only this client had it.' : 'It disappears from every client\'s pool.', async () => {
    try { await api.delete(`/shop-clients/challenges/${c.id}`); setOpen(null); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, c.client_specific ? 'Delete' : 'Hide');

  return (
    <View style={{ gap: 16 }}>
      <TouchableOpacity onPress={() => { setF(blank); setSheet(true); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: GOLD + '1A', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('challenge-add')}>
        <Ionicons name="sparkles" size={20} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Write a challenge just for {client.name}</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Type it or paste one, Jessi shapes it. Use {'{vehicle}'} and {'{store}'} so it fits their inventory.</Text></View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Every shop picks a challenge the person has not had yet, fills in one of the client's vehicles, and adds 0 to 2 random curveballs. Once someone has had them all, the rotation starts over with the oldest.</Text>
      {rows === null ? <ActivityIndicator color={GOLD} /> : DEPTS.map(d => {
        const list = rows.filter(r => r.department === d.key);
        return (
          <View key={d.key} style={{ gap: 8 }}>
            <Label t={`${d.label.toUpperCase()} · ${list.length} IN THE POOL`} colors={colors} />
            {list.map(c => (
              <TouchableOpacity key={c.id} onPress={() => setOpen(c)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: c.client_specific ? PURPLE + '88' : colors.border, padding: 12, gap: 4 }} {...tid(`challenge-${c.id}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }}>{c.title}</Text>
                  {c.client_specific && <View style={{ paddingHorizontal: 8, height: 22, borderRadius: 11, backgroundColor: PURPLE + '22', justifyContent: 'center' }}><Text style={{ fontSize: 10.5, fontWeight: '800', color: PURPLE }}>THIS CLIENT</Text></View>}
                </View>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={2}>{c.purpose}</Text>
                {c.persona?.name && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Shopper: {c.persona.name} · "{c.persona.opening_line}"</Text>}
              </TouchableOpacity>
            ))}
          </View>
        );
      })}

      <Sheet visible={!!open} onClose={() => setOpen(null)} title={open?.title || ''} colors={colors} testID="challenge-detail" footer={open ? <GoldButton label={open.client_specific ? 'Delete challenge' : 'Hide from every client'} onPress={() => remove(open)} testID="challenge-delete" outline color={RED} icon="trash-outline" /> : undefined}>
        {open && (
          <>
            <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{deptLabel(open.department).toUpperCase()}{open.runtime ? ` · ${open.runtime}` : ''}</Text>
            {!!open.purpose && <Text style={{ fontSize: 14.5, color: colors.textSecondary, fontStyle: 'italic', lineHeight: 20 }}>{open.purpose}</Text>}
            <View style={{ gap: 4 }}><Label t="WHAT A GREAT REP DOES" colors={colors} /><Text style={{ fontSize: 14.5, color: colors.text, lineHeight: 21 }}>{open.body}</Text></View>
            {open.success_points?.length > 0 && <View style={{ gap: 4 }}><Label t="GRADED POINTS" colors={colors} />{open.success_points.map((p, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text }}>• {p}</Text>)}</View>}
            {open.persona && (
              <View style={{ gap: 4, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border }}>
                <Label t={`THE SHOPPER · ${open.persona.name}`} colors={colors} />
                <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{open.persona.summary}</Text>
                {!!open.persona.goals && <Text style={{ fontSize: 13, color: colors.textSecondary }}>Wants: {open.persona.goals}</Text>}
                {!!open.persona.opening_line && <Text style={{ fontSize: 13, color: colors.textSecondary }}>Opens with: "{open.persona.opening_line}"</Text>}
                {(open.persona.objections || []).map((o: string, i: number) => <Text key={i} style={{ fontSize: 13, color: colors.textSecondary }}>Pushback: {o}</Text>)}
              </View>
            )}
          </>
        )}
      </Sheet>

      <Sheet visible={sheet} onClose={() => setSheet(false)} title={`New challenge for ${client.name}`} colors={colors} testID="challenge-sheet" footer={<GoldButton label="Add to this client's pool" onPress={save} busy={busy} disabled={!f.title.trim() || !f.body.trim() || !f.name.trim() || !f.opening_line.trim()} testID="challenge-save" />}>
        <TouchableOpacity onPress={() => setImportOpen(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('challenge-import')}>
          <Ionicons name="clipboard-outline" size={18} color={GOLD} /><Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>Paste a scenario and let Jessi fill this in</Text><Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
        </TouchableOpacity>
        <Field label="TITLE" value={f.title} onChange={(v: string) => set('title', v)} colors={colors} placeholder="Shopper: asks about a lifted Wrangler" testID="challenge-title" />
        <View style={{ gap: 8 }}><Label t="DEPARTMENT" colors={colors} /><View style={{ flexDirection: 'row', gap: 8 }}>{DEPTS.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`challenge-dept-${d.key}`} />)}</View></View>
        <Field label="PURPOSE (ONE LINE)" value={f.purpose} onChange={(v: string) => set('purpose', v)} colors={colors} placeholder="What this shop tests" testID="challenge-purpose" />
        <Field label="WHAT A GREAT REP DOES (GRADED FOR SCRIPT ADHERENCE)" value={f.body} onChange={(v: string) => set('body', v)} colors={colors} multiline placeholder="Answer the question, ask for the name and number, offer two times…" testID="challenge-body" />
        <Field label="GRADED POINTS (ONE PER LINE)" value={f.points} onChange={(v: string) => set('points', v)} colors={colors} multiline placeholder={'Answers with store and name\nOffers two appointment times'} testID="challenge-points" />
        <View style={{ gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: GOLD + '55' }}>
          <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>The shopper Jessi plays</Text>
          <Field label="NAME" value={f.name} onChange={(v: string) => set('name', v)} colors={colors} placeholder="Jo Rivera" testID="challenge-persona-name" />
          <View style={{ gap: 6 }}><Label t="VOICE" colors={colors} /><View style={{ flexDirection: 'row', gap: 6 }}>{VOICES.map(v => <Chip key={v.key} label={v.label} small active={f.voice === v.key} onPress={() => set('voice', v.key)} colors={colors} testID={`challenge-voice-${v.key}`} />)}</View></View>
          <Field label="WHO THEY ARE" value={f.summary} onChange={(v: string) => set('summary', v)} colors={colors} multiline placeholder="32, weekend off-roader, saw {vehicle} on {store}'s site" testID="challenge-persona-summary" />
          <Field label="WHAT THEY WANT" value={f.goals} onChange={(v: string) => set('goals', v)} colors={colors} placeholder="Know if a lift is doable and what it costs" testID="challenge-persona-goals" />
          <Field label="OPENING LINE (SAID RIGHT AFTER THE REP ANSWERS)" value={f.opening_line} onChange={(v: string) => set('opening_line', v)} colors={colors} placeholder="Hey, do you guys do lift kits on {vehicle}?" testID="challenge-persona-opening" />
          <Field label="OBJECTIONS (ONE PER LINE)" value={f.objections} onChange={(v: string) => set('objections', v)} colors={colors} multiline placeholder={'Can you just give me a price?\nThe shop down the road is cheaper'} testID="challenge-persona-objections" />
        </View>
      </Sheet>
      <ImportScriptSheet visible={importOpen} colors={colors} onClose={() => setImportOpen(false)} onImported={(d) => {
        setF({ ...f, title: d.title || f.title, department: d.category === 'Service' ? 'service' : f.department, purpose: d.purpose || '', body: d.body || '', points: (d.success_points || []).join('\n'), name: d.persona?.name || '', voice: d.persona?.voice || 'female',
          summary: d.persona?.summary || '', goals: d.persona?.goals || '', objections: (d.persona?.objections || []).join('\n'), opening_line: d.persona?.opening_line || '' });
        setImportOpen(false);
      }} />
    </View>
  );
};
