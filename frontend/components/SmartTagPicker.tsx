import React, { useState, useMemo } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';

interface Props {
  tags: string[];
  selectedTag: string;
  onSelect: (tag: string) => void;
  onTagCreated?: (tag: string) => void;
  userId: string;
  colors: any;
}

export function SmartTagPicker({ tags, selectedTag, onSelect, onTagCreated, userId, colors }: Props) {
  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);

  const filtered = useMemo(() => {
    if (!search.trim()) return tags;
    return tags.filter(t => t.toLowerCase().includes(search.toLowerCase().trim()));
  }, [tags, search]);

  const canCreate = search.trim().length > 0 && !tags.some(t => t.toLowerCase() === search.trim().toLowerCase());

  const handleCreate = async () => {
    const name = search.trim();
    if (!name || creating) return;
    setCreating(true);
    try {
      await api.post(`/tags/${userId}`, { name, color: '#C9A962', icon: 'pricetag' });
      onTagCreated?.(name);
      onSelect(name);
      setSearch('');
    } catch (e: any) {
      // Tag might already exist in org — just select it
      onSelect(name);
      setSearch('');
    } finally {
      setCreating(false);
    }
  };

  return (
    <View>
      {/* Helper text */}
      <View style={[s.helperBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Ionicons name="information-circle-outline" size={16} color="#C9A962" />
        <Text style={[s.helperText, { color: colors.textSecondary }]}>
          When a contact gets this tag, the campaign automatically starts sending messages to them.
        </Text>
      </View>

      {/* Search / create input */}
      <View style={[s.searchBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Ionicons name="search" size={16} color={colors.textSecondary} />
        <TextInput
          style={[s.searchInput, { color: colors.text }]}
          placeholder="Search tags or type to create new..."
          placeholderTextColor={colors.textSecondary}
          value={search}
          onChangeText={setSearch}
          autoCapitalize="words"
          data-testid="tag-search-input"
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => setSearch('')}>
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Create new tag option */}
      {canCreate && (
        <TouchableOpacity
          style={[s.createRow, { borderColor: '#C9A962' }]}
          onPress={handleCreate}
          disabled={creating}
          data-testid="create-tag-btn"
        >
          {creating ? (
            <ActivityIndicator size="small" color="#C9A962" />
          ) : (
            <Ionicons name="add-circle" size={20} color="#C9A962" />
          )}
          <Text style={s.createText}>Create "<Text style={{ fontWeight: '700' }}>{search.trim()}</Text>" as new tag</Text>
        </TouchableOpacity>
      )}

      {/* Tag grid */}
      <View style={s.grid}>
        {filtered.map((tag) => {
          const isActive = selectedTag === tag;
          return (
            <TouchableOpacity
              key={tag}
              style={[s.tag, isActive && s.tagActive]}
              onPress={() => onSelect(tag)}
              data-testid={`tag-option-${tag}`}
            >
              <Text style={[s.tagText, isActive && s.tagTextActive]}>{tag}</Text>
              {isActive && <Ionicons name="checkmark-circle" size={14} color="#fff" />}
            </TouchableOpacity>
          );
        })}
        {filtered.length === 0 && !canCreate && (
          <Text style={{ color: colors.textSecondary, fontSize: 13, padding: 8 }}>No tags found</Text>
        )}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  helperBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    padding: 10, borderRadius: 8, borderWidth: 1, marginBottom: 10,
  },
  helperText: { flex: 1, fontSize: 12, lineHeight: 16 },
  searchBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, borderWidth: 1, marginBottom: 10,
  },
  searchInput: { flex: 1, fontSize: 14, paddingVertical: 4 },
  createRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10,
    borderWidth: 1, borderStyle: 'dashed', marginBottom: 10,
    backgroundColor: 'rgba(201,169,98,0.08)',
  },
  createText: { fontSize: 14, color: '#C9A962' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tag: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.08)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)',
    flexDirection: 'row', alignItems: 'center', gap: 4,
  },
  tagActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  tagText: { fontSize: 13, fontWeight: '500', color: '#aaa' },
  tagTextActive: { color: '#000', fontWeight: '600' },
});
