import React, { useState, useMemo } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';

interface TagItem {
  name: string;
  color?: string;
  scope?: string;
}

interface Props {
  tags: (string | TagItem)[];
  selectedTag: string;
  onSelect: (tag: string) => void;
  onTagCreated?: (tag: string) => void;
  userId: string;
  colors: any;
  userRole?: string;  // to show scope picker for admins
}

const TAG_COLORS = ['#FF3B30','#FF9500','#FFCC00','#34C759','#007AFF','#5856D6','#AF52DE','#FF2D55','#C9A962','#00C7BE'];

export function SmartTagPicker({ tags, selectedTag, onSelect, onTagCreated, userId, colors, userRole }: Props) {
  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);
  const [newTagColor, setNewTagColor] = useState('#C9A962');
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [newTagScope, setNewTagScope] = useState<'personal' | 'account'>('personal');

  const isAdmin = userRole === 'super_admin' || userRole === 'org_admin' || userRole === 'store_manager';

  // Normalize tags to objects
  const normalizedTags: TagItem[] = useMemo(() =>
    tags.map(t => typeof t === 'string' ? { name: t } : t)
  , [tags]);

  const tagNames = normalizedTags.map(t => t.name);

  const filtered = useMemo(() => {
    if (!search.trim()) return normalizedTags;
    return normalizedTags.filter(t => t.name.toLowerCase().includes(search.toLowerCase().trim()));
  }, [normalizedTags, search]);

  const exactMatch = tagNames.some(n => n.toLowerCase() === search.trim().toLowerCase());
  const canCreate = search.trim().length > 1 && !exactMatch;

  const handleCreate = async () => {
    const name = search.trim();
    if (!name || creating) return;
    setCreating(true);
    try {
      await api.post(`/tags/${userId}`, {
        name,
        color: newTagColor,
        icon: 'pricetag',
        scope: newTagScope,
      });
      onTagCreated?.(name);
      onSelect(name);
      setSearch('');
      setShowColorPicker(false);
    } catch (e: any) {
      // Tag already exists or auto-created — just select it
      onSelect(name);
      setSearch('');
    } finally {
      setCreating(false);
    }
  };

  return (
    <View>
      {/* Info banner */}
      <View style={[s.helperBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Ionicons name="information-circle-outline" size={16} color="#C9A962" />
        <Text style={[s.helperText, { color: colors.textSecondary }]}>
          When this tag is applied to a contact, this campaign starts automatically.
        </Text>
      </View>

      {/* Search / create input */}
      <View style={[s.searchBox, { backgroundColor: colors.card, borderColor: selectedTag ? '#C9A962' : colors.border }]}>
        <Ionicons name="search" size={16} color={colors.textSecondary} />
        <TextInput
          style={[s.searchInput, { color: colors.text }]}
          placeholder="Search tags or type to create new…"
          placeholderTextColor={colors.textSecondary}
          value={search}
          onChangeText={setSearch}
          autoCapitalize="words"
          returnKeyType="done"
          data-testid="tag-search-input"
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => { setSearch(''); setShowColorPicker(false); }}>
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Currently selected */}
      {selectedTag && !search && (
        <View style={[s.selectedBanner, { backgroundColor: '#C9A96215', borderColor: '#C9A962' }]}>
          <Ionicons name="checkmark-circle" size={18} color="#C9A962" />
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#C9A962', flex: 1 }}>
            Trigger: <Text style={{ color: colors.text }}>{selectedTag}</Text>
          </Text>
          <TouchableOpacity onPress={() => onSelect('')}>
            <Ionicons name="close" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      )}

      {/* Create new tag option — appears when search text doesn't match any tag */}
      {canCreate && (
        <View>
          <TouchableOpacity
            style={[s.createRow, { borderColor: newTagColor }]}
            onPress={() => setShowColorPicker(prev => !prev)}
            data-testid="create-tag-btn"
          >
            <View style={[s.colorDot, { backgroundColor: newTagColor }]} />
            <Text style={[s.createText, { color: newTagColor }]}>
              Create "<Text style={{ fontWeight: '800' }}>{search.trim()}</Text>" as new tag
            </Text>
            <Ionicons name={showColorPicker ? 'chevron-up' : 'chevron-down'} size={16} color={newTagColor} />
          </TouchableOpacity>

          {showColorPicker && (
            <View style={[s.colorPanel, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {/* Color chips */}
              <Text style={{ fontSize: 12, color: colors.textSecondary, fontWeight: '600', marginBottom: 8 }}>TAG COLOR</Text>
              <View style={s.colorRow}>
                {TAG_COLORS.map(c => (
                  <TouchableOpacity key={c} onPress={() => setNewTagColor(c)}
                    style={[s.colorChip, { backgroundColor: c }, newTagColor === c && s.colorChipActive]}>
                    {newTagColor === c && <Ionicons name="checkmark" size={12} color="#fff" />}
                  </TouchableOpacity>
                ))}
              </View>

              {/* Scope picker — admins only */}
              {isAdmin && (
                <>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, fontWeight: '600', marginTop: 12, marginBottom: 8 }}>VISIBILITY</Text>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {[
                      { key: 'personal', label: 'Just Me', icon: 'person' },
                      { key: 'account', label: 'My Team', icon: 'storefront' },
                    ].map(s2 => (
                      <TouchableOpacity key={s2.key}
                        style={[s.scopeChip,
                          { borderColor: newTagScope === s2.key ? newTagColor : colors.border },
                          newTagScope === s2.key && { backgroundColor: newTagColor + '20' }
                        ]}
                        onPress={() => setNewTagScope(s2.key as any)}
                      >
                        <Ionicons name={s2.icon as any} size={14} color={newTagScope === s2.key ? newTagColor : colors.textSecondary} />
                        <Text style={{ fontSize: 13, fontWeight: '600', color: newTagScope === s2.key ? newTagColor : colors.textSecondary }}>
                          {s2.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}

              {/* Confirm create */}
              <TouchableOpacity
                style={[s.confirmBtn, { backgroundColor: newTagColor }]}
                onPress={handleCreate}
                disabled={creating}
                data-testid="confirm-create-tag"
              >
                {creating
                  ? <ActivityIndicator size="small" color="#fff" />
                  : <><Ionicons name="add-circle" size={18} color="#fff" /><Text style={s.confirmText}>Create &amp; Select Tag</Text></>
                }
              </TouchableOpacity>
            </View>
          )}
        </View>
      )}

      {/* Tag chips */}
      <View style={s.grid}>
        {filtered.map((tag) => {
          const isActive = selectedTag === tag.name;
          const tagColor = tag.color || '#8E8E93';
          return (
            <TouchableOpacity
              key={tag.name}
              style={[s.tag,
                { borderColor: isActive ? tagColor : colors.border, backgroundColor: isActive ? tagColor + '20' : colors.card },
              ]}
              onPress={() => { onSelect(isActive ? '' : tag.name); setSearch(''); }}
              data-testid={`tag-option-${tag.name}`}
            >
              <View style={[s.tagDot, { backgroundColor: tagColor }]} />
              <Text style={[s.tagText, { color: isActive ? tagColor : colors.text }, isActive && { fontWeight: '700' }]}>
                {tag.name}
              </Text>
              {isActive && <Ionicons name="checkmark-circle" size={14} color={tagColor} />}
            </TouchableOpacity>
          );
        })}
        {filtered.length === 0 && !canCreate && (
          <Text style={{ color: colors.textSecondary, fontSize: 15, padding: 8 }}>No tags match — type to create a new one</Text>
        )}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  helperBox:  { flexDirection: 'row', alignItems: 'flex-start', gap: 8, padding: 10, borderRadius: 8, borderWidth: 1, marginBottom: 10 },
  helperText: { flex: 1, fontSize: 14, lineHeight: 18 },
  searchBox:  { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5, marginBottom: 8 },
  searchInput:{ flex: 1, fontSize: 16, paddingVertical: 4 },
  selectedBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 10, borderWidth: 1, marginBottom: 10 },
  createRow:  { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 12, borderRadius: 10, borderWidth: 1.5, borderStyle: 'dashed', marginBottom: 8, backgroundColor: 'rgba(201,169,98,0.06)' },
  createText: { flex: 1, fontSize: 15 },
  colorDot:   { width: 16, height: 16, borderRadius: 8 },
  colorPanel: { borderRadius: 12, borderWidth: 1, padding: 14, marginBottom: 10 },
  colorRow:   { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  colorChip:  { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  colorChipActive: { borderWidth: 2, borderColor: '#fff' },
  scopeChip:  { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 8, borderRadius: 10, borderWidth: 1.5 },
  confirmBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 12, paddingVertical: 12, borderRadius: 10 },
  confirmText:{ fontSize: 16, fontWeight: '700', color: '#fff' },
  grid:       { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 4 },
  tag:        { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, borderWidth: 1.5 },
  tagDot:     { width: 8, height: 8, borderRadius: 4 },
  tagText:    { fontSize: 15, fontWeight: '500' },
  tagActive:  { fontWeight: '700' },
});
