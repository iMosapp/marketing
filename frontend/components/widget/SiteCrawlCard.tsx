import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { Section, Label, Hint, inputStyle } from '../inbox/InboxEditorParts';

type Props = { widgetId: string; siteUrl: string; colors: any; canManage: boolean; showToast: (m: string, t?: any, d?: number) => void; business?: boolean; onApplied: (r: { facts: any[]; kb: any; added_facts: number }) => void };

const Check = ({ on, label, sub, onPress, colors, testId }: { on: boolean; label: string; sub?: string; onPress: () => void; colors: any; testId: string }) => (
  <TouchableOpacity onPress={onPress} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 7 }} {...tid(testId)}>
    <Ionicons name={on ? 'checkbox' : 'square-outline'} size={22} color={on ? GOLD : colors.textSecondary} />
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 14, color: colors.text, lineHeight: 19 }}>{label}</Text>
      {sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{sub}</Text> : null}
    </View>
  </TouchableOpacity>
);

// "Let Jessi read your website": start a crawl, poll it, tick what to keep, apply.
export const SiteCrawlCard = ({ widgetId, siteUrl, colors, canManage, showToast, business, onApplied }: Props) => {
  const [url, setUrl] = useState(siteUrl);
  const [job, setJob] = useState<any>(null);
  const [site, setSite] = useState<{ pages: number; read_at: string | null } | null>(null);
  const [starting, setStarting] = useState(false);
  const [applying, setApplying] = useState(false);
  const [pick, setPick] = useState<{ facts: Record<number, boolean>; specials: Record<number, boolean>; notes: boolean }>({ facts: {}, specials: {}, notes: true });
  useEffect(() => { if (!url && siteUrl) setUrl(siteUrl); }, [siteUrl]);

  const refresh = useCallback(async () => {
    try {
      const r = (await api.get(`/widgets/${widgetId}/crawl`)).data;
      const j = r.job;
      setJob(j); setSite(r.site || null);
      if (j?.status === 'done' && j.draft) setPick({ facts: Object.fromEntries((j.draft.facts || []).map((_: any, i: number) => [i, true])), specials: Object.fromEntries((j.draft.specials || []).map((_: any, i: number) => [i, true])), notes: !!j.draft.notes });
    } catch {}
  }, [widgetId]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (job?.status !== 'running') return; const t = setInterval(refresh, 3000); return () => clearInterval(t); }, [job?.status, refresh]);

  const start = async () => {
    setStarting(true);
    try { setJob((await api.post(`/widgets/${widgetId}/crawl`, { url: url.trim(), mode: business ? 'business' : 'dealership' })).data); }
    catch (e: any) { showToast(errText(e, 'Could not read that site'), 'error', 3500); }
    finally { setStarting(false); }
  };
  const apply = async () => {
    const d = job.draft;
    const body = { job_id: job.id, facts: (d.facts || []).filter((_: any, i: number) => pick.facts[i]), specials: (d.specials || []).filter((_: any, i: number) => pick.specials[i]), notes: pick.notes ? d.notes : '' };
    setApplying(true);
    try { const r = (await api.post(`/widgets/${widgetId}/crawl/apply`, body)).data; onApplied(r); setJob({ ...job, applied_at: new Date().toISOString() }); showToast(`Added ${r.added_facts} facts${body.specials.length ? `, ${body.specials.length} specials` : ''}${body.notes ? ' and notes' : ''}. Notes and specials are saved already; the facts list updated above.`, 'success', 4000); }
    catch (e: any) { showToast(errText(e, 'Could not save those'), 'error', 3500); }
    finally { setApplying(false); }
  };
  const d = job?.draft;
  const nPick = Object.values(pick.facts).filter(Boolean).length + Object.values(pick.specials).filter(Boolean).length + (pick.notes && d?.notes ? 1 : 0);
  return (
    <Section colors={colors} testId="widget-section-crawl">
      <Label colors={colors}>Let Jessi read your website</Label>
      <Hint colors={colors}>{business ? 'She reads up to 40 pages of your site (pricing, features, integrations, about and contact first) and answers visitors straight from them, quoting plans and prices as written. She also drafts facts you can keep. Read it again whenever the site changes.' : 'She reads your home page plus about, hours, service and specials pages, then drafts store facts and specials. You tick what to keep.'}</Hint>
      {business ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10, padding: 10, borderRadius: 10, backgroundColor: colors.surface }} {...tid('widget-site-knowledge')}>
          <Ionicons name={site?.pages ? 'library' : 'library-outline'} size={18} color={site?.pages ? GOLD : colors.textSecondary} />
          <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{site?.pages ? `Jessi has read ${site.pages} page${site.pages === 1 ? '' : 's'} of your site${site.read_at ? ` · ${new Date(site.read_at).toLocaleDateString()}` : ''}` : 'Jessi has not read your site yet, so she only knows the facts above.'}</Text>
        </View>
      ) : null}
      {canManage ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TextInput value={url} onChangeText={setUrl} placeholder="www.yourdealership.com" placeholderTextColor={colors.textSecondary} autoCapitalize="none" autoCorrect={false} keyboardType="url" style={[inputStyle(colors), { flex: 1 }]} {...tid('widget-crawl-url')} />
          <TouchableOpacity onPress={start} disabled={starting || job?.status === 'running' || !url.trim()} style={{ height: 46, paddingHorizontal: 14, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: starting || job?.status === 'running' || !url.trim() ? 0.5 : 1 }} {...tid('widget-crawl-start')}>
            {starting ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>{job?.status === 'done' || site?.pages ? 'Read again' : 'Read my site'}</Text>}
          </TouchableOpacity>
        </View>
      ) : null}
      {job?.status === 'running' ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12 }} {...tid('widget-crawl-running')}>
          <ActivityIndicator color={GOLD} />
          <Text style={{ flex: 1, fontSize: 13, color: colors.textSecondary }}>{job.pages?.length ? `Read ${job.pages.length} page${job.pages.length === 1 ? '' : 's'}, Jessi is writing the draft…` : `Reading ${job.url}…`} {business ? 'A whole site takes a minute or two.' : 'Usually under a minute.'}</Text>
        </View>
      ) : null}
      {job?.status === 'failed' ? <Text style={{ fontSize: 13, color: '#FF3B30', marginTop: 10 }} {...tid('widget-crawl-error')}>{job.error || 'That did not work.'}</Text> : null}
      {job?.status === 'done' && d ? (
        <View style={{ marginTop: 10 }} {...tid('widget-crawl-draft')}>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 4 }}>From {job.pages?.length || 1} page{job.pages?.length === 1 ? '' : 's'} on {job.url}{job.applied_at ? ' · already added once' : ''}</Text>
          {d.hours_seen ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 6 }} {...tid('widget-crawl-hours')}>Hours on the site: {d.hours_seen}. Hours come from your Store Profile, update them there if these differ.</Text> : null}
          {d.facts?.length ? <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginTop: 6 }}>FACTS</Text> : null}
          {(d.facts || []).map((f: string, i: number) => <Check key={i} on={!!pick.facts[i]} label={f} onPress={() => setPick(p => ({ ...p, facts: { ...p.facts, [i]: !p.facts[i] } }))} colors={colors} testId={`widget-crawl-fact-${i}`} />)}
          {d.specials?.length ? <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginTop: 6 }}>SPECIALS</Text> : null}
          {(d.specials || []).map((s: any, i: number) => <Check key={s.id || i} on={!!pick.specials[i]} label={s.title} sub={[s.details, s.ends ? `ends ${s.ends}` : ''].filter(Boolean).join(' · ')} onPress={() => setPick(p => ({ ...p, specials: { ...p.specials, [i]: !p.specials[i] } }))} colors={colors} testId={`widget-crawl-special-${i}`} />)}
          {d.notes ? <><Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginTop: 6 }}>NOTES</Text><Check on={pick.notes} label={d.notes} onPress={() => setPick(p => ({ ...p, notes: !p.notes }))} colors={colors} testId="widget-crawl-notes" /></> : null}
          {!d.facts?.length && !d.specials?.length && !d.notes ? <Text style={{ fontSize: 13, color: colors.textSecondary }}>Jessi did not find anything worth keeping on those pages.</Text> : null}
          {canManage && nPick > 0 ? (
            <TouchableOpacity onPress={apply} disabled={applying} style={{ marginTop: 10, height: 44, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: applying ? 0.6 : 1 }} {...tid('widget-crawl-apply')}>
              {applying ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Add {nPick} to Jessi's knowledge</Text>}
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}
    </Section>
  );
};
