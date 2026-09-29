import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, useWindowDimensions, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../../services/api';
import { useAuthStore } from '../../../store/authStore';
import { GOLD, GREEN, RED, tid } from '../../../components/mystery-shops/shared';
import { GuideEditor } from '../../../components/mystery-shops/GuideEditor';

// Read-along call guide: big type, one thumb. Tap a KPI when you hit it, tap a scorecard row when you earned it; the header keeps the tally.
type Block = { kind: 'say' | 'ask' | 'label' | 'note' | 'warn' | 'list'; text: string };
type Section = { title: string; blocks: Block[]; kpi: string[] };
type Guide = { title: string; industry_label: string; department_label: string; kpi_chain: string[]; kpi_note: string; sections: Section[]; scorecard: { label: string; points: number }[]; total: number; source: string };

const C = { bg: '#0E0F12', card: '#17191E', border: '#262932', text: '#F4F1E8', dim: '#9A9A94', quote: '#FFFFFF' };

export default function CallGuideScreen() {
  const { industry, department, s: token } = useLocalSearchParams<{ industry: string; department: string; s?: string }>();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const role = useAuthStore(s => s.user?.role);
  const isAdmin = role === 'super_admin' || role === 'org_admin';
  const [g, setG] = useState<Guide | null>(null);
  const [err, setErr] = useState('');
  const [hit, setHit] = useState<Set<string>>(new Set());
  const [earned, setEarned] = useState<Set<number>>(new Set());
  const [big, setBig] = useState(true);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!industry || !department) return;
    setErr(''); setG(null);
    api.get(`/public/call-guide/${industry}/${department}`, { timeout: 120000 })
      .then(r => setG(r.data))
      .catch(e => setErr(e?.response?.data?.detail || 'Could not load this guide'));
  }, [industry, department]);

  const kpiTotal = useMemo(() => (g?.sections || []).reduce((n, s) => n + s.kpi.length, 0), [g]);
  const score = useMemo(() => (g?.scorecard || []).reduce((n, r, i) => n + (earned.has(i) ? r.points : 0), 0), [g, earned]);
  const toggleHit = (k: string) => setHit(prev => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const toggleEarned = (i: number) => setEarned(prev => { const n = new Set(prev); n.has(i) ? n.delete(i) : n.add(i); return n; });
  const reset = () => { setHit(new Set()); setEarned(new Set()); };
  const pad = Math.max(16, (width - 720) / 2);
  const f = big ? 1 : 0.85;

  if (editing && g) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }} edges={['top', 'bottom']}>
        <GuideEditor guide={g as any} industry={String(industry)} department={String(department)} onSaved={ng => { setG(ng as any); setEditing(false); reset(); }} onClose={() => setEditing(false)} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }} edges={['top', 'bottom']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: C.bg }} {...tid('guide-topbar')}>
        {router.canGoBack() && <TouchableOpacity onPress={() => router.back()} hitSlop={10} {...tid('guide-back')}><Ionicons name="chevron-back" size={24} color={GOLD} /></TouchableOpacity>}
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 1 }} numberOfLines={1}>{g ? `${g.department_label.toUpperCase()} CALL GUIDE` : 'CALL GUIDE'}</Text>
          <Text style={{ fontSize: 12.5, color: C.dim }} numberOfLines={1} {...tid('guide-tally')}>{g ? `${hit.size} of ${kpiTotal} KPIs · self-score ${score} / ${g.total || 100}` : ' '}</Text>
        </View>
        {isAdmin && !!g && <TouchableOpacity onPress={() => setEditing(true)} hitSlop={8} {...tid('guide-edit-btn')}><Ionicons name="create-outline" size={21} color={GOLD} /></TouchableOpacity>}
        <TouchableOpacity onPress={() => setBig(b => !b)} hitSlop={8} {...tid('guide-text-size')}><Ionicons name="text" size={20} color={C.dim} /></TouchableOpacity>
        <TouchableOpacity onPress={reset} hitSlop={8} {...tid('guide-reset')}><Ionicons name="refresh" size={20} color={C.dim} /></TouchableOpacity>
      </View>
      {!g && !err && <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 }} {...tid('guide-loading')}><ActivityIndicator color={GOLD} /><Text style={{ color: C.dim, fontSize: 13, textAlign: 'center', paddingHorizontal: 30 }}>Pulling up the guide. The first time a department is opened Jessi writes it, which takes about a minute.</Text></View>}
      {!!err && <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 30 }}><Text style={{ color: RED, fontSize: 15, textAlign: 'center' }} {...tid('guide-error')}>{err}</Text></View>}
      {g && (
        <ScrollView contentContainerStyle={{ paddingHorizontal: pad, paddingTop: 18, paddingBottom: 60, gap: 14 }} {...tid('guide-scroll')}>
          <GuideHeader g={g} f={f} />
          {g.sections.map((s, i) => <GuideSection key={i} n={i + 1} s={s} f={f} hit={hit} onHit={toggleHit} />)}
          <Scorecard g={g} f={f} earned={earned} onToggle={toggleEarned} score={score} />
          <Text style={{ fontSize: 11.5, color: C.dim, textAlign: 'center', marginTop: 8 }} {...tid('guide-source-note')}>{g.source === 'ai' ? 'Drafted by Jessi from this department\u2019s scorecard.' : g.source === 'custom' ? 'Edited by your admin.' : 'Customer Engagement Standard.'} Checkmarks stay on this device only.</Text>
        </ScrollView>
      )}
      {!!token && g && <PendingCallBar token={token} />}
    </SafeAreaView>
  );
}

// The call behind the texted link: countdown, or ring it now with I'm ready.
type Pending = { state: 'none' | 'countdown' | 'waiting' | 'calling' | 'live' | 'done' | 'over'; rings_in_s?: number | null; first_name?: string; score_pct?: number | null };
const PendingCallBar = ({ token }: { token: string }) => {
  const [p, setP] = useState<Pending | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/public/call-guide/pending/${token}`).then(r => { setP(r.data); setLeft(r.data?.rings_in_s ?? null); }).catch(() => {});
  useEffect(() => { load(); const iv = setInterval(load, 5000); return () => clearInterval(iv); }, [token]);
  useEffect(() => { if (left == null || left <= 0) return; const t = setTimeout(() => setLeft(l => (l == null ? null : Math.max(0, l - 1))), 1000); return () => clearTimeout(t); }, [left]);
  const ready = async () => { setBusy(true); try { const r = await api.post(`/public/call-guide/ready/${token}`); setP(r.data); setLeft(null); } catch {} finally { setBusy(false); } };
  if (!p || p.state === 'none') return null;
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  const canRing = p.state === 'countdown' || p.state === 'waiting';
  const line = p.state === 'countdown' ? (left && left > 0 ? `Your practice call rings in ${mmss(left)}` : 'Your practice call is ringing any second') :
    p.state === 'waiting' ? 'Your practice call is waiting for you' : p.state === 'calling' ? 'Calling you now, pick up!' : p.state === 'live' ? 'You are on the call. Go get 100.' :
    p.state === 'done' ? (p.score_pct != null ? `Call done: ${p.score_pct}%. Your scorecard is on its way.` : 'Call done. Your scorecard is on its way.') : 'This practice call is over.';
  return (
    <View style={{ borderTopWidth: 1, borderTopColor: GOLD + '66', backgroundColor: '#14161A', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 14, gap: 10 }} {...tid('guide-pending-bar')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Ionicons name={p.state === 'calling' || p.state === 'live' ? 'call' : p.state === 'done' ? 'checkmark-circle' : 'time'} size={20} color={p.state === 'done' ? GREEN : GOLD} />
        <Text style={{ flex: 1, fontSize: 15, fontWeight: '700', color: C.text }} {...tid('guide-pending-line')}>{line}</Text>
      </View>
      {canRing && (
        <TouchableOpacity onPress={ready} disabled={busy} style={{ backgroundColor: GOLD, borderRadius: 14, paddingVertical: 15, alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 8, opacity: busy ? 0.7 : 1 }} {...tid('guide-ready-btn')}>
          {busy ? <ActivityIndicator color="#111" /> : <Ionicons name="call" size={20} color="#111" />}
          <Text style={{ fontSize: 17, fontWeight: '900', color: '#111' }}>I{'\u2019'}m ready, call me now</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const GuideHeader = ({ g, f }: { g: Guide; f: number }) => (
  <View style={{ gap: 10, marginBottom: 6 }} {...tid('guide-header')}>
    <Text style={{ fontSize: 24 * f, fontWeight: '900', color: C.text, letterSpacing: -0.3 }}>{g.title}</Text>
    <View style={{ backgroundColor: GOLD + '14', borderRadius: 14, borderWidth: 1, borderColor: GOLD + '55', padding: 14, gap: 8 }}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1.2 }}>PRIMARY KPI</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 }} {...tid('guide-kpi-chain')}>
        {g.kpi_chain.map((k, i) => (
          <React.Fragment key={i}>
            {i > 0 && <Ionicons name="arrow-forward" size={14 * f} color={GOLD} />}
            <Text style={{ fontSize: 15 * f, fontWeight: '900', color: C.text, letterSpacing: 0.6 }}>{k}</Text>
          </React.Fragment>
        ))}
      </View>
      {!!g.kpi_note && <Text style={{ fontSize: 14 * f, lineHeight: 21 * f, color: C.text, opacity: 0.85 }}>{g.kpi_note}</Text>}
    </View>
  </View>
);

const GuideSection = ({ n, s, f, hit, onHit }: { n: number; s: Section; f: number; hit: Set<string>; onHit: (k: string) => void }) => (
  <View style={{ backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: C.border, padding: 16, gap: 10 }} {...tid(`guide-section-${n}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontWeight: '900', color: '#111', fontSize: 14 }}>{n}</Text></View>
      <Text style={{ fontSize: 18 * f, fontWeight: '900', color: C.text, flex: 1 }}>{s.title}</Text>
    </View>
    {s.blocks.map((b, i) => <BlockRow key={i} b={b} f={f} />)}
    {s.kpi.length > 0 && (
      <View style={{ marginTop: 6, gap: 6 }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1.2 }}>KPI</Text>
        {s.kpi.map((k, j) => {
          const key = `${n}-${j}`; const on = hit.has(key);
          return (
            <TouchableOpacity key={j} onPress={() => onHit(key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} {...tid(`guide-kpi-${n}-${j}`)}>
              <Ionicons name={on ? 'checkmark-circle' : 'ellipse-outline'} size={24 * f} color={on ? GREEN : C.dim} />
              <Text style={{ flex: 1, fontSize: 15 * f, color: on ? C.text : C.dim, fontWeight: on ? '700' : '500', textDecorationLine: on ? 'line-through' : 'none' }}>{k}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
    )}
  </View>
);

const BlockRow = ({ b, f }: { b: Block; f: number }) => {
  if (b.kind === 'say') return <View style={{ borderLeftWidth: 3, borderLeftColor: GOLD, paddingLeft: 12, paddingVertical: 2 }}><Text style={{ fontSize: 18 * f, lineHeight: 26 * f, color: C.quote, fontWeight: '600' }}>{'\u201C'}{b.text}{'\u201D'}</Text></View>;
  if (b.kind === 'ask') return <View style={{ flexDirection: 'row', gap: 8, paddingLeft: 4 }}><Text style={{ fontSize: 16 * f, lineHeight: 24 * f, color: GOLD }}>?</Text><Text style={{ flex: 1, fontSize: 16 * f, lineHeight: 24 * f, color: C.text }}>{'\u201C'}{b.text}{'\u201D'}</Text></View>;
  if (b.kind === 'label') return <Text style={{ fontSize: 12 * f, fontWeight: '800', color: C.dim, letterSpacing: 0.8, marginTop: 6 }}>{b.text.toUpperCase()}</Text>;
  if (b.kind === 'warn') return <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: RED + '14', borderRadius: 10, padding: 10 }}><Ionicons name="close-circle" size={18 * f} color={RED} /><Text style={{ flex: 1, fontSize: 14 * f, lineHeight: 20 * f, color: C.text, fontWeight: '600' }}>{b.text}</Text></View>;
  if (b.kind === 'list') return <View style={{ flexDirection: 'row', gap: 8, paddingLeft: 6 }}><Text style={{ fontSize: 14 * f, lineHeight: 21 * f, color: GOLD }}>{'\u2022'}</Text><Text style={{ flex: 1, fontSize: 14 * f, lineHeight: 21 * f, color: C.text }}>{b.text}</Text></View>;
  return <Text style={{ fontSize: 14 * f, lineHeight: 21 * f, color: C.text, opacity: 0.8, fontStyle: 'italic' }}>{b.text}</Text>;
};

const Scorecard = ({ g, f, earned, onToggle, score }: { g: Guide; f: number; earned: Set<number>; onToggle: (i: number) => void; score: number }) => (
  <View style={{ backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: GOLD + '66', padding: 16, gap: 8, marginTop: 6 }} {...tid('guide-scorecard')}>
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
      <Text style={{ fontSize: 18 * f, fontWeight: '900', color: C.text }}>{g.department_label} KPI scorecard</Text>
      <Text style={{ fontSize: 20 * f, fontWeight: '900', color: score >= 90 ? GREEN : score >= 70 ? GOLD : C.text }} {...tid('guide-self-score')}>{score} / {g.total || 100}</Text>
    </View>
    <Text style={{ fontSize: 12.5, color: C.dim }}>Tap each line you earned on the call.</Text>
    {g.scorecard.map((r, i) => {
      const on = earned.has(i);
      return (
        <TouchableOpacity key={i} onPress={() => onToggle(i)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderTopWidth: 1, borderTopColor: C.border }} {...tid(`guide-score-${i}`)}>
          <Ionicons name={on ? 'checkmark-circle' : 'ellipse-outline'} size={22 * f} color={on ? GREEN : C.dim} />
          <Text style={{ flex: 1, fontSize: 15 * f, color: C.text, fontWeight: on ? '800' : '500' }}>{r.label}</Text>
          <Text style={{ fontSize: 15 * f, fontWeight: '900', color: on ? GREEN : C.dim, minWidth: 34, textAlign: 'right' }}>{r.points}</Text>
        </TouchableOpacity>
      );
    })}
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderTopColor: GOLD + '66', paddingTop: 10 }}>
      <Text style={{ fontSize: 14 * f, fontWeight: '900', color: GOLD, letterSpacing: 1 }}>TOTAL</Text>
      <Text style={{ fontSize: 14 * f, fontWeight: '900', color: GOLD }}>{g.total || 100}</Text>
    </View>
    {Platform.OS === 'web' && <Text style={{ fontSize: 11.5, color: C.dim, marginTop: 4 }}>Add this page to your home screen to open it in one tap before every call.</Text>}
  </View>
);
