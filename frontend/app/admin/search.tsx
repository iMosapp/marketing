import React, { useCallback, useEffect, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../../store/authStore';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Keyboard } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { ListSearch } from '../../components/common/ListSearch';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Row = { id: string; name: string; subtitle?: string; active?: boolean; store_id?: string };
type Results = { q: string; organizations: Row[]; stores: Row[]; users: Row[]; widgets: Row[]; lead_sources: Row[]; contacts: Row[] };
type Recent = { group: keyof Omit<Results, 'q'>; id: string; name: string; subtitle?: string; at: number };
const RECENT_MAX = 8;

const GROUPS: { key: keyof Omit<Results, 'q'>; title: string; icon: any; color: string; href: (r: Row) => string }[] = [
  { key: 'organizations', title: 'Organizations', icon: 'business', color: '#007AFF', href: r => `/admin/organizations/${r.id}` },
  { key: 'stores', title: 'Accounts', icon: 'storefront', color: '#34C759', href: r => `/admin/stores/${r.id}` },
  { key: 'users', title: 'Team members', icon: 'people', color: '#FF9500', href: r => `/admin/users/${r.id}` },
  { key: 'widgets', title: 'Website widgets', icon: 'chatbubble-ellipses', color: '#C9A962', href: r => `/admin/website-widget/${r.id}` },
  { key: 'lead_sources', title: 'Lead sources', icon: 'git-branch', color: '#5856D6', href: r => `/admin/lead-sources/${r.id}` },
  { key: 'contacts', title: 'Customers', icon: 'person', color: '#FF2D55', href: r => `/thread/${r.id}` },
];

// Find anything: one box that searches organizations, accounts, team members, widgets and lead sources and jumps to the record.
export default function AdminSearch() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { q: initial } = useLocalSearchParams<{ q?: string }>();
  const { user } = useAuthStore();
  const [q, setQ] = useState(String(initial || ''));
  const [recent, setRecent] = useState<Recent[]>([]);
  const storeKey = `imos.recent_finds.${user?._id || 'anon'}`;

  useEffect(() => { AsyncStorage.getItem(storeKey).then(v => { try { setRecent(v ? JSON.parse(v) : []); } catch { setRecent([]); } }); }, [storeKey]);
  const remember = useCallback(async (group: Recent['group'], r: Row) => {
    const next = [{ group, id: r.id, name: r.name, subtitle: r.subtitle, at: Date.now() }, ...recent.filter(x => !(x.group === group && x.id === r.id))].slice(0, RECENT_MAX);
    setRecent(next); AsyncStorage.setItem(storeKey, JSON.stringify(next)).catch(() => {});
  }, [recent, storeKey]);
  const forget = () => { setRecent([]); AsyncStorage.removeItem(storeKey).catch(() => {}); };
  const open = (group: Recent['group'], r: Row) => { const g = GROUPS.find(x => x.key === group)!; remember(group, r); router.push(g.href(r) as any); };
  const [res, setRes] = useState<Results | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<any>(null);
  const seq = useRef(0);

  useEffect(() => {
    const term = q.trim();
    if (timer.current) clearTimeout(timer.current);
    if (term.length < 2) { setRes(null); setBusy(false); return; }
    setBusy(true);
    timer.current = setTimeout(async () => {
      const n = ++seq.current;
      try {
        const r = await api.get('/admin/search', { params: { q: term } });
        if (n === seq.current) setRes(r.data);
      } catch { if (n === seq.current) setRes(null); }
      finally { if (n === seq.current) setBusy(false); }
    }, 280);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [q]);

  const total = res ? GROUPS.reduce((a, g) => a + (res[g.key]?.length || 0), 0) : 0;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Find anything" subtitle="Organizations, accounts, people, customers, widgets" testID="admin-search-header" />
      <ListSearch value={q} onChange={setQ} placeholder="Name, email, phone, city, widget key…" testID="admin-search-input" autoFocus everywhere={false} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingTop: 4, paddingBottom: 60, gap: 18 }} keyboardShouldPersistTaps="handled" onScrollBeginDrag={Keyboard.dismiss}>
        {q.trim().length < 2 ? (
          recent.length ? (
            <View style={{ gap: 8 }} {...tid('admin-search-recent')}>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>RECENT</Text>
                <TouchableOpacity onPress={forget} hitSlop={8} {...tid('admin-search-recent-clear')}><Text style={{ fontSize: 12, fontWeight: '700', color: colors.accent }}>Clear</Text></TouchableOpacity>
              </View>
              <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
                {recent.map((r, i) => { const g = GROUPS.find(x => x.key === r.group) || GROUPS[0]; return (
                  <TouchableOpacity key={`${r.group}-${r.id}`} onPress={() => open(r.group, r)} activeOpacity={0.7}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 12, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }} {...tid(`admin-search-recent-${r.group}-${r.id}`)}>
                    <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: g.color + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={g.icon} size={16} color={g.color} /></View>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }} numberOfLines={1}>{r.name}</Text>
                      <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>{g.title}{r.subtitle ? ` · ${r.subtitle}` : ''}</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                  </TouchableOpacity>
                ); })}
              </View>
            </View>
          ) : (
          <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 40, lineHeight: 20 }} {...tid('admin-search-hint')}>
            Type at least two characters.{'\n'}Try a store name, a rep's last name, a customer's phone number, an email or a widget key.
          </Text>
          )
        ) : busy && !res ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
        ) : res && total === 0 ? (
          <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 40 }} {...tid('admin-search-empty')}>Nothing matches "{res.q}".</Text>
        ) : res ? GROUPS.filter(g => res[g.key]?.length).map(g => (
          <View key={g.key} style={{ gap: 8 }} {...tid(`admin-search-group-${g.key}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Ionicons name={g.icon} size={14} color={g.color} />
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{g.title.toUpperCase()} · {res[g.key].length}{res[g.key].length >= 8 ? '+' : ''}</Text>
            </View>
            <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
              {res[g.key].map((r, i) => (
                <TouchableOpacity key={r.id} onPress={() => open(g.key, r)} activeOpacity={0.7}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 12, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }} {...tid(`admin-search-row-${g.key}-${r.id}`)}>
                  <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: g.color + '22', alignItems: 'center', justifyContent: 'center' }}>
                    <Ionicons name={g.icon} size={16} color={g.color} />
                  </View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={{ fontSize: 15, fontWeight: '700', color: r.active === false ? colors.textSecondary : colors.text }} numberOfLines={1}>{r.name}{r.active === false ? '  · inactive' : ''}</Text>
                    {r.subtitle ? <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>{r.subtitle}</Text> : null}
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
