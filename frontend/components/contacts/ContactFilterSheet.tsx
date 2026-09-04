import React from 'react';
import { View, Text, Modal, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';

interface Tag { _id: string; name: string; color: string; icon: string; contact_count: number; }

const GOLD = '#C9A962';

function Section({ title, children, colors }: any) {
  return (
    <View style={{ marginBottom: 18 }}>
      <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 8 }}>
        {title}
      </Text>
      {children}
    </View>
  );
}

function Segmented({ options, value, onChange, colors, testPrefix }: {
  options: { key: string; label: string; icon?: string }[];
  value: string;
  onChange: (v: string) => void;
  colors: any;
  testPrefix: string;
}) {
  return (
    <View style={{ flexDirection: 'row', backgroundColor: colors.bg, borderRadius: 10, padding: 3 }}>
      {options.map((opt) => (
        <TouchableOpacity
          key={opt.key}
          style={{
            flex: 1, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 5,
            paddingVertical: 8, borderRadius: 8,
            backgroundColor: value === opt.key ? GOLD : 'transparent',
          }}
          onPress={() => onChange(opt.key)}
          testID={`${testPrefix}-${opt.key}`} dataSet={{ testid: `${testPrefix}-${opt.key}` } as any}
        >
          {opt.icon ? <Ionicons name={opt.icon as any} size={13} color={value === opt.key ? '#000' : colors.textSecondary} /> : null}
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13, fontWeight: '600', color: value === opt.key ? '#000' : colors.textSecondary }}>
            {opt.label}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

export function ContactFilterSheet({
  visible, onClose, isManager,
  viewMode, onViewMode,
  sortMode, onSortMode,
  crmFilter, onCrmFilter,
  tags, selectedTag, onSelectTag,
  onReset,
}: {
  visible: boolean;
  onClose: () => void;
  isManager: boolean;
  viewMode: 'mine' | 'team';
  onViewMode: (v: 'mine' | 'team') => void;
  sortMode: 'alpha' | 'recent';
  onSortMode: (v: 'alpha' | 'recent') => void;
  crmFilter: 'all' | 'linked' | 'not_linked' | 'users';
  onCrmFilter: (v: 'all' | 'linked' | 'not_linked' | 'users') => void;
  tags: Tag[];
  selectedTag: string | null;
  onSelectTag: (t: string | null) => void;
  onReset: () => void;
}) {
  const { colors } = useThemeStore();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} activeOpacity={1} onPress={onClose}>
        <TouchableOpacity activeOpacity={1} onPress={() => {}}>
          <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34, maxHeight: 560 }} testID="contact-filter-sheet" dataSet={{ testid: "contact-filter-sheet" } as any}>
            <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: 'center', marginBottom: 14 }} />
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>Filters</Text>
              <TouchableOpacity onPress={onReset} testID="filter-reset-btn" dataSet={{ testid: "filter-reset-btn" } as any}>
                <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13, fontWeight: '600', color: GOLD }}>Reset</Text>
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              {isManager && (
                <Section title="WHOSE CONTACTS" colors={colors}>
                  <Segmented
                    options={[{ key: 'mine', label: 'My Contacts', icon: 'person' }, { key: 'team', label: 'Team', icon: 'people' }]}
                    value={viewMode}
                    onChange={(v) => onViewMode(v as any)}
                    colors={colors}
                    testPrefix="filter-view"
                  />
                </Section>
              )}

              <Section title="SORT BY" colors={colors}>
                <Segmented
                  options={[{ key: 'recent', label: 'Recent', icon: 'time-outline' }, { key: 'alpha', label: 'A - Z', icon: 'text-outline' }]}
                  value={sortMode}
                  onChange={(v) => onSortMode(v as any)}
                  colors={colors}
                  testPrefix="filter-sort"
                />
              </Section>

              <Section title="CRM STATUS" colors={colors}>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  {([
                    { key: 'all', label: 'All' },
                    { key: 'linked', label: 'CRM Linked' },
                    { key: 'not_linked', label: 'Not Linked' },
                    { key: 'users', label: 'App Users' },
                  ] as const).map((f) => (
                    <TouchableOpacity
                      key={f.key}
                      style={{
                        paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16,
                        backgroundColor: crmFilter === f.key ? GOLD : colors.bg,
                      }}
                      onPress={() => onCrmFilter(f.key)}
                      testID={`filter-crm-${f.key}`} dataSet={{ testid: `filter-crm-${f.key}` } as any}
                    >
                      <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13, fontWeight: '600', color: crmFilter === f.key ? '#000' : colors.textSecondary }}>
                        {f.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </Section>

              {tags.length > 0 && (
                <Section title="TAGS" colors={colors}>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                    {tags.map((tag) => (
                      <TouchableOpacity
                        key={tag._id}
                        style={{
                          flexDirection: 'row', alignItems: 'center', gap: 4,
                          paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16,
                          backgroundColor: selectedTag === tag.name ? tag.color : colors.bg,
                        }}
                        onPress={() => onSelectTag(selectedTag === tag.name ? null : tag.name)}
                        testID={`filter-tag-${tag.name}`} dataSet={{ testid: `filter-tag-${tag.name}` } as any}
                      >
                        <Ionicons name={tag.icon as any} size={12} color={selectedTag === tag.name ? '#FFF' : tag.color} />
                        <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13, fontWeight: '600', color: selectedTag === tag.name ? '#FFF' : tag.color }}>
                          {tag.name}
                        </Text>
                        {tag.contact_count > 0 && (
                          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, color: selectedTag === tag.name ? 'rgba(255,255,255,0.8)' : colors.textTertiary }}>
                            {tag.contact_count}
                          </Text>
                        )}
                      </TouchableOpacity>
                    ))}
                  </View>
                </Section>
              )}
            </ScrollView>

            <TouchableOpacity
              onPress={onClose}
              style={{ backgroundColor: GOLD, borderRadius: 16, paddingVertical: 14, alignItems: 'center', marginTop: 8 }}
              testID="filter-done-btn" dataSet={{ testid: "filter-done-btn" } as any}
            >
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 16, fontWeight: '800', color: '#000' }}>Done</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}
