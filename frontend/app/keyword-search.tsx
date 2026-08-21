import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { useThemeStore } from '../store/themeStore';

const timeLabel = (iso: string) => {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

const HighlightedSnippet = ({ text, query, colors }: { text: string; query: string; colors: any }) => {
  const q = query.trim().toLowerCase();
  if (!q || !text) return <Text style={{ fontSize: 13, color: colors.textSecondary }} numberOfLines={2}>{text}</Text>;
  const lower = text.toLowerCase();
  const parts: React.ReactNode[] = [];
  let i = 0;
  let idx = lower.indexOf(q);
  let key = 0;
  while (idx !== -1 && key < 20) {
    if (idx > i) parts.push(text.slice(i, idx));
    parts.push(
      <Text key={`h${key++}`} style={{ backgroundColor: '#FFD60A', color: '#000', fontWeight: '700' }}>
        {text.slice(idx, idx + q.length)}
      </Text>
    );
    i = idx + q.length;
    idx = lower.indexOf(q, i);
  }
  if (i < text.length) parts.push(text.slice(i));
  return <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} numberOfLines={2}>{parts}</Text>;
};

export default function KeywordSearchScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const { q: initialQ } = useLocalSearchParams();

  const [query, setQuery] = useState(typeof initialQ === 'string' ? initialQ : '');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef<any>(null);

  const doSearch = async (q: string) => {
    if (!user?._id || q.trim().length < 2) { setResults([]); setSearched(false); return; }
    try {
      setLoading(true);
      const res = await api.get(`/search/${user._id}/messages?q=${encodeURIComponent(q.trim())}&limit=50`);
      setResults(res.data?.results || []);
      setSearched(true);
    } catch (e) {
      console.error('Keyword search failed:', e);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 400);
    return () => clearTimeout(debounceRef.current);
  }, [query, user?._id]);

  const openResult = (item: any) => {
    if (item.conversation_id) {
      const params = new URLSearchParams();
      if (item.message_id) params.set('jumpToMsg', item.message_id);
      params.set('q', query.trim());
      router.push(`/thread/${item.conversation_id}?${params.toString()}` as any);
    } else if (item.contact_id) {
      router.push(`/contact/${item.contact_id}` as any);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4 }} data-testid="keyword-search-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.accent} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Keyword Search</Text>
        <TouchableOpacity onPress={() => router.push('/settings/keyword-rules' as any)} style={{ padding: 6 }} data-testid="keyword-search-rules-link">
          <Ionicons name="pricetags-outline" size={20} color="#5856D6" />
        </TouchableOpacity>
      </View>

      {/* Search input */}
      <View style={styles.searchWrap}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={18} color={colors.textSecondary} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search texts & call transcripts…"
            placeholderTextColor={colors.textTertiary}
            value={query}
            onChangeText={setQuery}
            autoFocus
            autoCapitalize="none"
            data-testid="keyword-search-input"
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => setQuery('')} data-testid="keyword-search-clear-btn">
              <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {loading ? (
        <View style={styles.centerWrap}><ActivityIndicator size="large" color={colors.accent} /></View>
      ) : !searched ? (
        <View style={styles.centerWrap}>
          <Ionicons name="chatbubbles-outline" size={44} color={colors.textTertiary} />
          <Text style={styles.hintTitle}>Find anything ever said</Text>
          <Text style={styles.hintText}>Type a keyword like "trade" or "gladiator" to search every text and call transcript — then jump straight to it.</Text>
        </View>
      ) : results.length === 0 ? (
        <View style={styles.centerWrap}>
          <Ionicons name="search-outline" size={44} color={colors.textTertiary} />
          <Text style={styles.hintTitle}>No matches</Text>
          <Text style={styles.hintText}>Nothing found for "{query.trim()}" in your messages or calls.</Text>
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item, idx) => item.message_id || `${item.conversation_id}-${idx}`}
          contentContainerStyle={{ paddingBottom: 40 }}
          ListHeaderComponent={
            <Text style={styles.resultCount} data-testid="keyword-search-result-count">
              {results.length} match{results.length === 1 ? '' : 'es'}
            </Text>
          }
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.resultRow} onPress={() => openResult(item)} activeOpacity={0.7} data-testid="keyword-search-result-row">
              <View style={[styles.sourceIcon, { backgroundColor: item.source === 'call' ? '#30D15820' : '#007AFF20' }]}>
                <Ionicons name={item.source === 'call' ? 'call' : 'chatbubble'} size={15} color={item.source === 'call' ? '#30D158' : '#007AFF'} />
              </View>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text style={styles.resultName} numberOfLines={1}>{item.contact_name}</Text>
                  <Text style={styles.resultTime}>{timeLabel(item.timestamp)}</Text>
                </View>
                <HighlightedSnippet text={item.snippet} query={query} colors={colors} />
                {item.auto_tags?.length > 0 && (
                  <View style={{ flexDirection: 'row', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                    {item.auto_tags.map((t: string) => (
                      <View key={t} style={styles.autoTag}>
                        <Ionicons name="pricetag" size={9} color="#5856D6" />
                        <Text style={styles.autoTagText}>{t}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
            </TouchableOpacity>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10 },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: colors.text, marginLeft: 6 },
  searchWrap: { paddingHorizontal: 16, paddingBottom: 10 },
  searchBar: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: colors.border },
  searchInput: { flex: 1, fontSize: 15, color: colors.text, padding: 0 },
  centerWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40, gap: 8 },
  hintTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginTop: 8 },
  hintText: { fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 },
  resultCount: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, marginHorizontal: 16, marginBottom: 8, letterSpacing: 0.4 },
  resultRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 12, marginHorizontal: 16, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  sourceIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  resultName: { fontSize: 14, fontWeight: '700', color: colors.text, flex: 1, marginRight: 8 },
  resultTime: { fontSize: 11, color: colors.textTertiary },
  autoTag: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#5856D615', borderRadius: 7, paddingHorizontal: 6, paddingVertical: 2 },
  autoTagText: { fontSize: 10, color: '#5856D6', fontWeight: '600' },
});
