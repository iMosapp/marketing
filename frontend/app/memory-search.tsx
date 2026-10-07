import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, FlatList, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../services/api';
import { useThemeStore } from '../store/themeStore';
import { useMemorySearchStore } from '../store/memorySearchStore';
import { GOLD, tid } from '../components/scripts/shared';

type Hit = { source: 'text' | 'call' | 'memo' | 'note' | 'sale' | 'tag'; who: string; when_label: string; quote: string; why: string; conversation_id?: string | null };
type Result = { contact_id: string; name: string; first: string; phone: string; vehicle: string; strength: 'strong' | 'maybe'; when_label: string; when_spoken: string; best: Hit; hits: Hit[] };
type Res = { query: string; topic: string; terms: string[]; scanned: number; results: Result[] };

const ICON: Record<Hit['source'], any> = { text: 'chatbubble-ellipses-outline', call: 'call-outline', memo: 'mic-outline', note: 'document-text-outline', sale: 'pricetag-outline', tag: 'bookmark-outline' };
const LABEL: Record<Hit['source'], string> = { text: 'Text', call: 'Call transcript', memo: 'Voice memo', note: 'Note', sale: 'Sold record', tag: 'Tag' };
const EXAMPLES = ['who asked about a Tesla Model 3 around 20k', 'who did I sell a Tahoe to', 'who are my Harley riders', 'anyone looking for a truck to tow a camper', 'who mentioned a trade-in last month', 'who talked about financing with bad credit'];
const daysLabel = (d: number) => (d >= 360 ? 'this year' : d >= 170 ? 'last 6 months' : d >= 80 ? 'last 3 months' : d >= 40 ? 'last month' : `last ${d} days`);

// "Who mentioned X": Jessi hunts through texts, call transcripts, voice memos, notes, tags and sold records and comes back with the person, the quote and when.
// When Jessi already ran the hunt in a live session, her list arrives through memorySearchStore and renders at once: no second search, same people she just read out.
export default function MemorySearchScreen() {
  const router = useRouter();
  const { q, days: daysParam } = useLocalSearchParams<{ q?: string; days?: string }>();
  const { colors } = useThemeStore();
  const preload = useMemorySearchStore(s => s.preload);
  const [query, setQuery] = useState(typeof q === 'string' ? q : '');
  const [days, setDays] = useState<number | null>(typeof daysParam === 'string' && +daysParam > 0 ? +daysParam : null);
  const [res, setRes] = useState<Res | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const ran = useRef('');
  const shownPreload = useRef(0);

  const run = useCallback(async (text: string, d: number | null = days) => {
    const t = text.trim();
    if (t.length < 2) return;
    setBusy(true); setErr(''); setOpen(null);
    try {
      const r = await api.post('/memory/search', { query: t, days: d || undefined }, { timeout: 60000 });
      setRes(r.data);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Could not search right now. Try again in a moment.');
    } finally { setBusy(false); }
  }, [days]);

  // Jessi's list, if she just produced one for this query, beats a fresh search.
  useEffect(() => {
    if (!preload || preload.at === shownPreload.current) return;
    const want = (typeof q === 'string' ? q : query).trim().toLowerCase();
    if (preload.query !== want) return;
    shownPreload.current = preload.at;
    ran.current = typeof q === 'string' ? q : query;
    setQuery(preload.res?.query || want);
    setDays(preload.days ?? null);
    setRes(preload.res);
    setBusy(false); setErr(''); setOpen(null);
  }, [preload, q]);

  useEffect(() => {
    if (typeof q !== 'string' || !q.trim() || ran.current === q) return;
    ran.current = q;
    setQuery(q);
    const pre = useMemorySearchStore.getState().take(q);
    if (pre) { shownPreload.current = pre.at; setRes(pre.res); setDays(pre.days ?? null); return; }
    run(q, typeof daysParam === 'string' && +daysParam > 0 ? +daysParam : null);
  }, [q]);

  const renderItem = useCallback(({ item: r, index }: { item: Result; index: number }) => (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: r.strength === 'strong' ? GOLD + '88' : colors.border, padding: 14, gap: 8, marginBottom: 10 }} {...tid(`mention-result-${r.contact_id}`)}>
      <TouchableOpacity onPress={() => router.push(`/contact/${r.contact_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`mention-open-${r.contact_id}`)}>
        <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>{(r.first || r.name || '?')[0]}</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15.5, fontWeight: '800', color: colors.text }} numberOfLines={1}><Text style={{ color: colors.textTertiary, fontWeight: '700' }}>{index + 1}. </Text>{r.name}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 }}>
            {r.strength === 'strong' && <View style={{ backgroundColor: GOLD + '22', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 1 }} {...tid(`mention-strong-${r.contact_id}`)}><Text style={{ fontSize: 10, fontWeight: '800', color: GOLD, letterSpacing: 0.4 }}>STRONG MATCH</Text></View>}
            <Text style={{ fontSize: 12, color: colors.textSecondary, flexShrink: 1 }} numberOfLines={1}>{[r.vehicle, r.phone].filter(Boolean).join(' · ')}</Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      </TouchableOpacity>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Ionicons name={ICON[r.best.source] || 'ellipse-outline'} size={14} color={colors.textSecondary} />
        <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{r.best.source === 'tag' ? 'Tagged by you' : `${LABEL[r.best.source] || 'Record'} · ${r.best.when_label || 'undated'} · ${r.when_spoken}`}</Text>
      </View>
      <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19, fontStyle: 'italic' }} {...tid(`mention-quote-${r.contact_id}`)}>"{r.best.quote}"</Text>
      {!!r.best.why && r.best.why !== r.best.quote && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{r.best.why}</Text>}
      {r.hits.length > 1 && (
        <TouchableOpacity onPress={() => setOpen(open === r.contact_id ? null : r.contact_id)} {...tid(`mention-more-${r.contact_id}`)}>
          <Text style={{ fontSize: 12.5, fontWeight: '700', color: GOLD }}>{open === r.contact_id ? 'Hide' : `${r.hits.length - 1} more mention${r.hits.length > 2 ? 's' : ''}`}</Text>
        </TouchableOpacity>
      )}
      {open === r.contact_id && r.hits.slice(1).map((h, i) => (
        <View key={`${h.source}-${i}`} style={{ borderLeftWidth: 2, borderLeftColor: colors.border, paddingLeft: 10, gap: 3 }}>
          <Text style={{ fontSize: 11.5, fontWeight: '700', color: colors.textSecondary }}>{h.source === 'tag' ? 'Tag' : `${LABEL[h.source] || 'Record'} · ${h.when_label || 'undated'}`}</Text>
          <Text style={{ fontSize: 13, color: colors.text, fontStyle: 'italic', lineHeight: 18 }}>"{h.quote}"</Text>
        </View>
      ))}
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 2 }}>
        <TouchableOpacity onPress={() => router.push(`/thread/${r.contact_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: GOLD, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 8 }} {...tid(`mention-text-${r.contact_id}`)}>
          <Ionicons name="chatbubble" size={14} color="#000" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>Text {r.first || 'them'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  ), [colors, open, router]);

  const header = (
    <View style={{ gap: 10, paddingBottom: 4 }}>
      {!res && !busy && !err && (
        <View style={{ gap: 8 }} {...tid('memory-search-examples')}>
          <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5 }}>TRY</Text>
          {EXAMPLES.map(ex => (
            <TouchableOpacity key={ex} onPress={() => { setQuery(ex); run(ex, null); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12 }} {...tid('memory-search-example')}>
              <Ionicons name="sparkles-outline" size={15} color={GOLD} /><Text style={{ flex: 1, fontSize: 13.5, color: colors.text }}>{ex}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
      {busy && <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', marginTop: 20 }} {...tid('memory-search-busy')}>Reading through everything you have on record...</Text>}
      {!!err && <Text style={{ fontSize: 13, color: '#FF453A' }} {...tid('memory-search-error')}>{err}</Text>}
      {res && !busy && (
        <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <Text style={{ flex: 1, fontSize: 12.5, color: colors.textSecondary, minWidth: 180 }} {...tid('memory-search-summary')}>
            {res.results.length ? `${res.results.length} ${res.results.length === 1 ? 'person' : 'people'} mentioned ${res.topic}` : `Nobody on record mentioned ${res.topic}`}
            {res.terms.length ? ` · looked for: ${res.terms.join(', ')}` : ''}
          </Text>
          {!!days && (
            <TouchableOpacity onPress={() => { setDays(null); run(query, null); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: GOLD + '22', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 4 }} {...tid('memory-search-days')}>
              <Ionicons name="time-outline" size={12} color={GOLD} /><Text style={{ fontSize: 11.5, fontWeight: '700', color: GOLD }}>{daysLabel(days)} · tap for all time</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
    </View>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('memory-search-screen')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8, gap: 8 }}>
        <TouchableOpacity onPress={() => (router.canGoBack() ? router.back() : router.replace('/(tabs)/contacts' as any))} hitSlop={8} style={{ padding: 4 }} {...tid('memory-search-back')}><Ionicons name="chevron-back" size={26} color={colors.text} /></TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>Who mentioned...</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>Texts, calls, voice memos, notes, tags and what they bought</Text>
        </View>
      </View>
      <View style={{ marginHorizontal: 14, flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: Platform.OS === 'web' ? 8 : 4 }}>
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <TextInput value={query} onChangeText={setQuery} onSubmitEditing={() => run(query)} returnKeyType="search" placeholder="a 20k Tesla Model 3, a trade-in, a camper..." placeholderTextColor={colors.textTertiary}
          style={{ flex: 1, fontSize: 15, color: colors.text, paddingVertical: 8 }} autoFocus={!q} {...tid('memory-search-input')} />
        <TouchableOpacity onPress={() => run(query)} disabled={busy || query.trim().length < 2} style={{ backgroundColor: GOLD, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8, opacity: busy || query.trim().length < 2 ? 0.5 : 1 }} {...tid('memory-search-go')}>
          {busy ? <ActivityIndicator size="small" color="#000" /> : <Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>Find</Text>}
        </TouchableOpacity>
      </View>
      <FlatList
        data={res && !busy ? res.results : []}
        keyExtractor={r => r.contact_id}
        renderItem={renderItem}
        extraData={open}
        ListHeaderComponent={header}
        ListFooterComponent={res && !busy && !res.results.length ? <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('memory-search-empty')}>Try different words (the make instead of the model, the number written another way) or ask Jessi to widen the time frame.</Text> : null}
        contentContainerStyle={{ padding: 14, paddingBottom: 40 }}
        keyboardShouldPersistTaps="handled"
        initialNumToRender={12}
        windowSize={7}
        {...tid('memory-search-list')}
      />
    </SafeAreaView>
  );
}
