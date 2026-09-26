import React from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Props = {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  testID: string;
  count?: number;
  total?: number;
  autoFocus?: boolean;
  everywhere?: boolean;
};

// The one search box every admin list uses: always visible, filters as you type, clear x, optional "N of M" and a jump to Find anything.
export const ListSearch = ({ value, onChange, placeholder, testID, count, total, autoFocus, everywhere = true }: Props) => {
  const { colors } = useThemeStore();
  const router = useRouter();
  const q = value.trim();
  return (
    <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6, gap: 6 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, height: 42, paddingHorizontal: 12, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}>
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <TextInput
          style={{ flex: 1, fontSize: 16, color: colors.text, paddingVertical: 0 }}
          placeholder={placeholder}
          placeholderTextColor={colors.textSecondary}
          value={value}
          onChangeText={onChange}
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
          clearButtonMode="never"
          autoFocus={autoFocus}
          {...tid(testID)}
        />
        {value.length > 0 ? (
          <TouchableOpacity onPress={() => onChange('')} hitSlop={8} {...tid(`${testID}-clear`)}>
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        ) : null}
      </View>
      {q && count != null ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 4 }}>
          <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid(`${testID}-count`)}>
            {count} of {total ?? count} match{count === 1 ? '' : 'es'}
          </Text>
          {everywhere ? (
            <TouchableOpacity onPress={() => router.push({ pathname: '/admin/search', params: { q } } as any)} hitSlop={8} {...tid(`${testID}-everywhere`)}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.accent }}>Search everywhere</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}
    </View>
  );
};
