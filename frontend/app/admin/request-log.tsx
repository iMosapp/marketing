// Request Log: Forest's asks, verbatim, with status. Rendered live from memory/REQUEST_LOG.md. Owner-only unless shared in Owner Settings.
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, ScrollView, ActivityIndicator, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import api from '../../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
type Entry = { n: number; date: string; status: string; prompt: string; notes: string };
const STATUS: Record<string, string> = { DONE: '#34C759', DEPLOY: '#FF9F0A', USER: '#FF453A', answered: '#8E8E93' };
const colorFor = (s: string) => (s.includes('DEPLOY') ? STATUS.DEPLOY : s.startsWith('USER') ? STATUS.USER : s.startsWith('DONE') ? STATUS.DONE : STATUS.answered);

export default function RequestLogScreen() {
  const { colors } = useThemeStore();
  const [data, setData] = useState<{ entries: Entry[]; tail: string; missing?: boolean } | null>(null);
  const [err, setErr] = useState('');
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState<'all' | 'open' | 'done'>('all');

  useEffect(() => { api.get('/owner/request-log').then(r => setData(r.data)).catch(e => setErr(e?.response?.status === 403 ? 'This log is only visible to the owner.' : 'Could not load the log.')); }, []);

  const rows = useMemo(() => {
    const all = [...(data?.entries || [])].reverse();
    const needle = q.trim().toLowerCase();
    return all.filter(e => (filter === 'all' || (filter === 'done' ? e.status.startsWith('DONE') && !e.status.includes('DEPLOY') : !(e.status.startsWith('DONE') && !e.status.includes('DEPLOY'))))
      && (!needle || `${e.prompt} ${e.notes} ${e.status} ${e.date}`.toLowerCase().includes(needle)));
  }, [data, q, filter]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('request-log-screen')}>
      <ScreenHeader title="Request Log" subtitle={data ? `${data.entries.length} asks · your exact words` : 'Your exact words, with status'} testID="request-log-header" />
      {err ? <Text style={{ margin: 20, color: '#FF453A' }} {...tid('request-log-error')}>{err}</Text> : !data ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
        <>
          <View style={{ paddingHorizontal: 14, gap: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12 }}>
              <Ionicons name="search" size={16} color={colors.textSecondary} />
              <TextInput value={q} onChangeText={setQ} placeholder="Search what you asked" placeholderTextColor={colors.textTertiary} style={{ flex: 1, fontSize: 14, color: colors.text, paddingVertical: 10 }} {...tid('request-log-search')} />
            </View>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              {(['all', 'open', 'done'] as const).map(f => (
                <TouchableOpacity key={f} onPress={() => setFilter(f)} style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, backgroundColor: filter === f ? `${GOLD}22` : colors.card, borderWidth: 1, borderColor: filter === f ? GOLD : colors.border }} {...tid(`request-log-filter-${f}`)}>
                  <Text style={{ fontSize: 12.5, fontWeight: '700', color: filter === f ? GOLD : colors.textSecondary }}>{f === 'all' ? 'All' : f === 'open' ? 'Still open / needs deploy' : 'Done'}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 60, gap: 10 }}>
            {data.missing && <Text style={{ color: colors.textSecondary, fontSize: 13 }}>The log file is not in this deployment yet. It appears after the next push that includes memory/REQUEST_LOG.md.</Text>}
            {rows.map(e => (
              <View key={e.n} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 8 }} {...tid(`request-log-entry-${e.n}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>#{e.n}</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{e.date}</Text>
                  <View style={{ flex: 1 }} />
                  <View style={{ backgroundColor: `${colorFor(e.status)}22`, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 }}><Text style={{ fontSize: 11, fontWeight: '800', color: colorFor(e.status) }}>{e.status}</Text></View>
                </View>
                <View style={{ borderLeftWidth: 2, borderLeftColor: GOLD, paddingLeft: 10 }}>
                  <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }} {...tid(`request-log-prompt-${e.n}`)}>{e.prompt}</Text>
                </View>
                {!!e.notes && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }}>{e.notes}</Text>}
              </View>
            ))}
            {!!data.tail && filter === 'all' && !q && (
              <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 6 }} {...tid('request-log-tail')}>
                {data.tail.split('\n').map((l, i) => l.startsWith('## ') ? <Text key={i} style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.6, marginTop: i ? 10 : 0 }}>{l.slice(3).toUpperCase()}</Text>
                  : l.startsWith('- ') ? <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 19 }}>• {l.slice(2).replace(/\*\*/g, '')}</Text> : null)}
              </View>
            )}
          </ScrollView>
        </>
      )}
    </SafeAreaView>
  );
}
