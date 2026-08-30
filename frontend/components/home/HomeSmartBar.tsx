import React from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';

export interface HomeSmartItem {
  key: string;
  label: string;
  icon: string;
  color: string;
  value: string | number;
  onPress: () => void;
}

export function HomeSmartBar({ items }: { items: HomeSmartItem[] }) {
  const { colors } = useThemeStore();

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={{ flexGrow: 0, flexShrink: 0 }}
      contentContainerStyle={{ paddingHorizontal: 16, gap: 8, paddingBottom: 14 }}
      testID="home-smart-bar"
      dataSet={{ testid: 'home-smart-bar' } as any}
    >
      {items.map((it) => (
        <TouchableOpacity
          key={it.key}
          onPress={it.onPress}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: 8,
            backgroundColor: colors.card,
            borderRadius: 14,
            paddingHorizontal: 10,
            paddingVertical: 7,
            borderWidth: 1,
            borderColor: 'transparent',
          }}
          testID={`home-smart-${it.key}`}
          dataSet={{ testid: `home-smart-${it.key}` } as any}
        >
          <View style={{
            width: 26, height: 26, borderRadius: 13,
            backgroundColor: it.color + '22',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <Ionicons name={it.icon as any} size={13} color={it.color} />
          </View>
          <View>
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, fontWeight: '800', color: colors.text, lineHeight: 17 }}>
              {it.value}
            </Text>
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, lineHeight: 12 }}>
              {it.label}
            </Text>
          </View>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}
