import React, { useState } from 'react';
import { View, TextInput, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, tid } from '../scripts/shared';

// Typed twin of "who's looking at Harleys": one box on Home that hands the question to the Who Mentioned hunt.
export const AskJessiSearchBar = () => {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [text, setText] = useState('');
  const go = () => {
    const q = text.trim();
    router.push((q.length >= 2 ? `/memory-search?q=${encodeURIComponent(q)}` : '/memory-search') as any);
    setText('');
  };
  return (
    <View style={{ marginHorizontal: 16, marginTop: -6, marginBottom: 16, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 16, paddingHorizontal: 14, height: 48, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('home-ask-search')}>
      <Ionicons name="search" size={17} color={GOLD} />
      <TextInput
        value={text}
        onChangeText={setText}
        onSubmitEditing={go}
        returnKeyType="search"
        placeholder="Type it: who's looking at Harleys, who asked about a Tahoe"
        placeholderTextColor={colors.textSecondary}
        style={{ flex: 1, color: colors.text, fontSize: 14, paddingVertical: 0, ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as any) : {}) }}
        {...tid('home-ask-search-input')}
      />
      <TouchableOpacity onPress={go} hitSlop={8} {...tid('home-ask-search-go')}>
        <Ionicons name="arrow-forward-circle" size={26} color={GOLD} />
      </TouchableOpacity>
    </View>
  );
};
