import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { GOLD, tid, errText, fmtPhone } from './ownership';
import { Section, Label, Hint } from './InboxEditorParts';

const GREEN = '#34C759', AMBER = '#FF9500', RED = '#FF3B30';
type Ringing = { kind: 'everyone' | 'some' | 'others' | 'none' | 'text_only'; attempts: number; names: string[]; missing: string[]; dynamic: boolean; no_cell?: string[] };
type Src = { id: string; name: string; kind: string; direct: boolean; lead_count: number; flow: { id: string; name: string } | null; contact_mode: string; routing: string; notify_everyone: boolean; ringing: Ringing; website_default: boolean; website_pages: string[] };
type Overview = { sources: Src[]; other_sources: { id: string; name: string; lead_count: number; inbox_name: string | null }[]; team: any[]; checklist: { number: boolean; members: number; members_without_number: number; members_without_cell: string[]; sources: number; ringing_ok: boolean | null; ai_mode: string } };

const list = (n: string[]) => (n.length <= 3 ? n.join(', ') : `${n.slice(0, 3).join(', ')} +${n.length - 3}`);

const ringText = (s: Src, inboxName: string) => {
  const r = s.ringing;
  if (r.kind === 'text_only') return { color: GREEN, icon: 'notifications' as const, text: s.notify_everyone ? `Text only: everyone on ${inboxName} gets the new-lead ping, first to claim owns it` : `Text only: the routed rep (${s.routing.replace(/_/g, ' ')}) gets the ping` };
  if (r.kind === 'everyone') return { color: GREEN, icon: 'call' as const, text: `Rings everyone on ${inboxName}${r.dynamic ? ' (new members ring automatically)' : ''}${r.attempts > 1 ? ` · ${r.attempts} attempts` : ''}` };
  if (r.kind === 'some') return { color: AMBER, icon: 'call' as const, text: `Rings ${list(r.names)} only. Never rings ${list(r.missing)}.` };
  if (r.kind === 'others') return { color: AMBER, icon: 'call' as const, text: `Rings ${list(r.names)}: nobody from this inbox.` };
  return { color: RED, icon: 'call-outline' as const, text: 'Set to call, but no phone is on the ladder yet.' };
};

const Row = ({ ok, warn, text, testId, colors }: { ok: boolean | null; warn?: boolean; text: string; testId: string; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(testId)}>
    <Ionicons name={ok === null ? 'remove-circle-outline' : ok ? 'checkmark-circle' : warn ? 'alert-circle' : 'close-circle'} size={17} color={ok === null ? colors.textSecondary : ok ? GREEN : warn ? AMBER : RED} />
    <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{text}</Text>
  </View>
);

// "Leads" tab of the inbox editor: the whole lead -> inbox -> ring -> claim chain for this team, with one-tap fixes.
export const InboxLeadsTab = ({ inboxId, inboxName, phone, colors, showToast, onGoTeam }: { inboxId: string; inboxName: string; phone: string; colors: any; showToast: (m: string, t?: any, ms?: number) => void; onGoTeam: () => void }) => {
  const router = useRouter();
  const [data, setData] = useState<Overview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const load = useCallback(() => api.get(`/inboxes/${inboxId}/leads`).then(r => setData(r.data)).catch((e: any) => showToast(errText(e, 'Could not load lead setup'), 'error')), [inboxId]);
  useEffect(() => { load(); }, [load]);

  const act = async (key: string, fn: () => Promise<any>, ok: (d: any) => string) => {
    setBusy(key);
    try { const r = await fn(); setData(r.data); showToast(ok(r.data), 'success', 3000); }
    catch (e: any) { showToast(errText(e, 'That did not work'), 'error', 3500); }
    finally { setBusy(null); }
  };
  const point = (sid: string) => act(`point-${sid}`, () => api.post(`/inboxes/${inboxId}/sources`, { source_id: sid }), () => `Leads from that source now land in ${inboxName}`);
  const unpoint = (s: Src) => showConfirm('Take this source off the inbox?', `New ${s.name} leads will stop landing in ${inboxName}. Nothing already here moves.`, () => act(`unpoint-${s.id}`, () => api.delete(`/inboxes/${inboxId}/sources/${s.id}`), () => `${s.name} no longer points here`), undefined, 'Remove');
  const ringAll = (s: Src) => act(`ring-${s.id}`, () => api.post(`/inboxes/${inboxId}/sources/${s.id}/ring-everyone`), d => (d.changed?.changed === 'flow' ? `Flow "${d.changed.name}" now rings everyone on the inbox first (every source using it)` : `${s.name} now rings everyone on the inbox first`));

  if (!data) return <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} />;
  const c = data.checklist;
  const real = data.sources.filter(s => !s.direct);
  const direct = data.sources.find(s => s.direct);
  return (
    <>
      <Section colors={colors} testId="inbox-leads-checklist">
        <Label colors={colors}>Is this team wired up?</Label>
        <Hint colors={colors}>A lead comes in on a lead source, lands in this inbox, the ladder rings the right phones, first to claim owns it. Jessi covers the gap.</Hint>
        <View style={{ gap: 8 }}>
          <Row ok={c.number} text={c.number ? `Texts to ${fmtPhone(phone)} land here` : 'No number yet: pick one under Setup'} testId="inbox-check-number" colors={colors} />
          <Row ok={c.members > 0} warn={c.members > 0 && (c.members_without_number > 0 || c.members_without_cell.length > 0)} testId="inbox-check-team" colors={colors}
            text={c.members === 0 ? 'Nobody on the team yet: add people under Team' : `${c.members} on the team${c.members_without_cell.length ? ` · no cell on profile, cannot ring: ${list(c.members_without_cell)}` : ''}${c.members_without_number ? ` · ${c.members_without_number} without a personal texting number` : ''}`} />
          <Row ok={c.sources > 0} warn={c.sources === 0} text={c.sources === 0 ? 'No lead source points here yet (website, ADF, Facebook...)' : `${c.sources} lead source${c.sources === 1 ? '' : 's'} send${c.sources === 1 ? 's' : ''} leads here`} testId="inbox-check-sources" colors={colors} />
          <Row ok={c.ringing_ok} warn={c.ringing_ok === false} text={c.ringing_ok === null ? 'No source rings phones (text + push only)' : c.ringing_ok ? 'Every calling source rings the whole team' : 'Some sources ring only part of the team'} testId="inbox-check-ringing" colors={colors} />
          <Row ok={true} text={c.ai_mode === 'off' ? 'Jessi is off: humans only' : 'Jessi replies until someone claims'} testId="inbox-check-jessi" colors={colors} />
        </View>
        {c.members === 0 && <TouchableOpacity onPress={onGoTeam} style={{ marginTop: 8 }} {...tid('inbox-leads-go-team')}><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Add the team →</Text></TouchableOpacity>}
      </Section>

      <Section colors={colors} testId="inbox-leads-sources">
        <Label colors={colors}>Lead sources that land here</Label>
        {direct && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 }} {...tid('inbox-source-direct')}>
            <Ionicons name="chatbubble" size={16} color={GREEN} />
            <Text style={{ flex: 1, fontSize: 13, color: colors.textSecondary }}>Texts straight to {fmtPhone(phone) || 'the inbox number'}: everyone on {inboxName} gets the ping, first to claim owns it.</Text>
          </View>
        )}
        {real.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary, paddingVertical: 6 }} {...tid('inbox-sources-empty')}>No lead source points here yet, so web or ADF leads never reach this team. Point one here below.</Text>}
        {real.map(s => {
          const r = ringText(s, inboxName);
          const fixable = s.contact_mode === 'text_and_call' && s.ringing.kind !== 'everyone';
          return (
            <View key={s.id} style={{ backgroundColor: colors.surface, borderRadius: 12, padding: 12, gap: 6, marginTop: 6 }} {...tid(`inbox-source-${s.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }}>{s.name}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{s.lead_count} lead{s.lead_count === 1 ? '' : 's'}</Text>
                <TouchableOpacity onPress={() => unpoint(s)} hitSlop={8} disabled={busy === `unpoint-${s.id}`} {...tid(`inbox-source-remove-${s.id}`)}><Ionicons name="close-circle-outline" size={18} color={colors.textSecondary} /></TouchableOpacity>
              </View>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{s.flow ? `Flow: ${s.flow.name}` : 'Own ladder on the source'}{s.website_default ? ' · website catch-all' : s.website_pages.length ? ` · ${s.website_pages.length} web pages` : ''}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 6 }}>
                <Ionicons name={r.icon} size={14} color={r.color} style={{ marginTop: 2 }} />
                <Text style={{ flex: 1, fontSize: 12.5, color: r.color, lineHeight: 17 }} {...tid(`inbox-source-ringing-${s.id}`)}>{r.text}{s.ringing.no_cell?.length ? ` No cell on profile: ${list(s.ringing.no_cell)}.` : ''}</Text>
              </View>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 2 }}>
                {fixable && (
                  <TouchableOpacity onPress={() => ringAll(s)} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 11, paddingVertical: 7, borderRadius: 12, backgroundColor: GOLD }} {...tid(`inbox-source-ring-all-${s.id}`)}>
                    {busy === `ring-${s.id}` ? <ActivityIndicator size="small" color="#111" /> : <Ionicons name="people" size={13} color="#111" />}
                    <Text style={{ fontSize: 12, fontWeight: '800', color: '#111' }}>Ring everyone on {inboxName}</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity onPress={() => router.push((s.flow ? `/lead-flows/${s.flow.id}` : `/admin/lead-sources/${s.id}`) as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 11, paddingVertical: 7, borderRadius: 12, borderWidth: 1, borderColor: colors.border }} {...tid(`inbox-source-open-${s.id}`)}>
                  <Ionicons name="open-outline" size={13} color={colors.text} />
                  <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{s.flow ? 'Edit flow' : 'Edit ladder'}</Text>
                </TouchableOpacity>
              </View>
            </View>
          );
        })}
        <TouchableOpacity onPress={() => setPicking(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, marginTop: 8, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', borderColor: GOLD }} {...tid('inbox-point-source-toggle')}>
          <Ionicons name={picking ? 'chevron-up' : 'add-circle-outline'} size={18} color={GOLD} />
          <Text style={{ color: GOLD, fontWeight: '700' }}>Point a lead source here</Text>
        </TouchableOpacity>
        {picking && (
          <View style={{ gap: 6, marginTop: 6 }}>
            {data.other_sources.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }}>Every lead source on this store already points here. New ones: Hub → Leads → Lead Sources.</Text>}
            {data.other_sources.map(o => (
              <TouchableOpacity key={o.id} onPress={() => point(o.id)} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 12, backgroundColor: colors.surface }} {...tid(`inbox-point-source-${o.id}`)}>
                {busy === `point-${o.id}` ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="arrow-forward-circle-outline" size={20} color={GOLD} />}
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{o.name}</Text>
                  <Text style={{ fontSize: 11, color: o.inbox_name ? AMBER : colors.textSecondary }}>{o.inbox_name ? `Currently lands in ${o.inbox_name}, tap to move it here` : `${o.lead_count} lead${o.lead_count === 1 ? '' : 's'} so far · not on any inbox`}</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </Section>
    </>
  );
};
