import React from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

type Props = {
  colors: any;
  query: string;
  onChangeQuery: (q: string) => void;
  countLabel: string;
  hasMatches: boolean;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
};

export const ThreadSearchBar = ({ colors, query, onChangeQuery, countLabel, hasMatches, onPrev, onNext, onClose }: Props) => (
  <View
    style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.surface }}
    data-testid="thread-search-bar"
  >
    <Ionicons name="search" size={16} color={colors.textSecondary} />
    <TextInput
      style={{ flex: 1, fontSize: 15, color: colors.textPrimary, paddingVertical: 4 }}
      placeholder="Search this conversation…"
      placeholderTextColor={colors.textSecondary}
      value={query}
      onChangeText={onChangeQuery}
      autoFocus
      autoCapitalize="none"
      data-testid="thread-search-input"
    />
    <Text style={{ fontSize: 12, color: colors.textSecondary, fontWeight: '600', minWidth: 30, textAlign: 'center' }} data-testid="thread-search-count">
      {countLabel}
    </Text>
    <TouchableOpacity onPress={onPrev} disabled={!hasMatches} style={{ padding: 4, opacity: hasMatches ? 1 : 0.3 }} data-testid="thread-search-prev">
      <Ionicons name="chevron-up" size={18} color={colors.accent} />
    </TouchableOpacity>
    <TouchableOpacity onPress={onNext} disabled={!hasMatches} style={{ padding: 4, opacity: hasMatches ? 1 : 0.3 }} data-testid="thread-search-next">
      <Ionicons name="chevron-down" size={18} color={colors.accent} />
    </TouchableOpacity>
    <TouchableOpacity onPress={onClose} style={{ padding: 4 }} data-testid="thread-search-close">
      <Ionicons name="close" size={18} color={colors.textSecondary} />
    </TouchableOpacity>
  </View>
);
