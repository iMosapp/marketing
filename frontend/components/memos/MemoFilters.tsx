import React from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';

export type MemoView = 'unattached' | 'attached';
type Props = {
  view: MemoView; onView: (v: MemoView) => void; counts: { unattached: number; attached: number };
  q: string; onQ: (s: string) => void; tags: string[]; activeTag: string | null; onTag: (t: string | null) => void;
  tagColor: (t: string) => string; colors: any;
};

// Top of the Voice Memos list: To file / Attached, search, and one chip per tag in use.
export const MemoFilters = ({ view, onView, counts, q, onQ, tags, activeTag, onTag, tagColor, colors }: Props) => (
  <View style={{ gap: 10 }} {...tid('memo-filters')}>
    <View style={{ flexDirection: 'row', backgroundColor: colors.card, borderRadius: 12, padding: 3, borderWidth: 1, borderColor: colors.border }}>
      {([['unattached', 'To file'], ['attached', 'Attached']] as [MemoView, string][]).map(([v, label]) => (
        <TouchableOpacity key={v} onPress={() => onView(v)} style={{ flex: 1, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: view === v ? GOLD : 'transparent' }} {...tid(`memo-view-${v}`)}>
          <Text style={{ fontSize: 13.5, fontWeight: '800', color: view === v ? '#111' : colors.textSecondary }}>{label} · {counts[v]}</Text>
        </TouchableOpacity>
      ))}
    </View>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 44, borderWidth: 1, borderColor: colors.border }}>
      <Ionicons name="search" size={17} color={colors.textSecondary} />
      <TextInput value={q} onChangeText={onQ} placeholder="Search titles, summaries, transcripts, names, tags" placeholderTextColor={colors.textSecondary} style={{ flex: 1, color: colors.text, fontSize: 14 }} autoCorrect={false} {...tid('memo-search')} />
      {q ? <TouchableOpacity onPress={() => onQ('')} hitSlop={8} {...tid('memo-search-clear')}><Ionicons name="close-circle" size={18} color={colors.textSecondary} /></TouchableOpacity> : null}
    </View>
    {tags.length ? (
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }} {...tid('memo-tag-filter')}>
        <TouchableOpacity onPress={() => onTag(null)} style={{ height: 30, paddingHorizontal: 12, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: !activeTag ? GOLD : colors.card, borderWidth: 1, borderColor: !activeTag ? GOLD : colors.border }} {...tid('memo-tag-filter-all')}>
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: !activeTag ? '#111' : colors.text }}>All</Text>
        </TouchableOpacity>
        {tags.map(t => { const on = activeTag?.toLowerCase() === t.toLowerCase(); const c = tagColor(t); return (
          <TouchableOpacity key={t} onPress={() => onTag(on ? null : t)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, height: 30, paddingHorizontal: 11, borderRadius: 15, backgroundColor: on ? c : colors.card, borderWidth: 1, borderColor: on ? c : colors.border }} {...tid(`memo-tag-filter-${t}`)}>
            <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: on ? '#fff' : c }} />
            <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? '#fff' : colors.text }}>{t}</Text>
          </TouchableOpacity>
        ); })}
      </ScrollView>
    ) : null}
  </View>
);
