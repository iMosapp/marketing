import React from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';

export const SMART_LISTS = [
  { key: 'needs_attention', label: 'Needs\nAttention', icon: 'time' as const, color: '#FF9500' },
  { key: 'hot', label: 'Hot\nLeads', icon: 'flame' as const, color: '#FF453A' },
  { key: 'new_this_week', label: 'New This\nWeek', icon: 'person-add' as const, color: '#32ADE6' },
  { key: 'birthdays', label: 'Birthdays\nSoon', icon: 'gift' as const, color: '#AF52DE' },
];

export function SmartListBar({ counts, active, onSelect }: {
  counts: Record<string, number>;
  active: string | null;
  onSelect: (key: string | null) => void;
}) {
  const { colors } = useThemeStore();
  const allActive = !active;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={{ flexGrow: 0, flexShrink: 0 }}
      contentContainerStyle={{ paddingHorizontal: 16, gap: 8, paddingBottom: 10 }}
      testID="smart-list-bar" dataSet={{ testid: "smart-list-bar" } as any}
    >
      {/* All contacts — always visible escape hatch */}
      <TouchableOpacity
        onPress={() => onSelect(null)}
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 8,
          backgroundColor: allActive ? '#C9A96222' : colors.card,
          borderRadius: 14,
          paddingHorizontal: 10,
          paddingVertical: 7,
          borderWidth: 1,
          borderColor: allActive ? '#C9A962' : 'transparent',
        }}
        testID="smart-list-all" dataSet={{ testid: 'smart-list-all' } as any}
      >
        <View style={{
          width: 26, height: 26, borderRadius: 13,
          backgroundColor: '#C9A96222',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <Ionicons name="people" size={13} color="#C9A962" />
        </View>
        <View>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, fontWeight: '800', color: allActive ? '#C9A962' : colors.text, lineHeight: 17 }}>
            {counts.all ?? '—'}
          </Text>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 11, fontWeight: '600', color: colors.textSecondary, lineHeight: 13 }}>
            All Contacts
          </Text>
        </View>
      </TouchableOpacity>
      {SMART_LISTS.map((sl) => {
        const isActive = active === sl.key;
        const count = counts[sl.key] ?? 0;
        return (
          <TouchableOpacity
            key={sl.key}
            onPress={() => onSelect(isActive ? null : sl.key)}
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: 8,
              backgroundColor: isActive ? sl.color + '22' : colors.card,
              borderRadius: 14,
              paddingHorizontal: 10,
              paddingVertical: 7,
              borderWidth: 1,
              borderColor: isActive ? sl.color : 'transparent',
            }}
            testID={`smart-list-${sl.key}`} dataSet={{ testid: `smart-list-${sl.key}` } as any}
          >
            <View style={{
              width: 26, height: 26, borderRadius: 13,
              backgroundColor: sl.color + '22',
              alignItems: 'center', justifyContent: 'center',
            }}>
              <Ionicons name={sl.icon} size={13} color={sl.color} />
            </View>
            <View>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, fontWeight: '800', color: isActive ? sl.color : colors.text, lineHeight: 17 }}>
                {count}
              </Text>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 11, fontWeight: '600', color: colors.textSecondary, lineHeight: 13 }}>
                {sl.label.replace('\n', ' ')}
              </Text>
            </View>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}
