import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

export const BookOfBusinessCard = ({ userId }: { userId: string }) => {
  const { colors } = useThemeStore();
  const router = useRouter();
  const [summary, setSummary] = useState<any>(null);
  const [touch, setTouch] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) return;
    Promise.all([
      api.get(`/relationship-health/${userId}/summary`).then(r => setSummary(r.data)).catch(() => setSummary(null)),
      api.get(`/home/touch-mix/${userId}`).then(r => setTouch(r.data)).catch(() => setTouch(null)),
    ]).finally(() => setLoading(false));
  }, [userId]);

  if (loading) {
    return (
      <View style={{ marginHorizontal: 16, marginBottom: 20, backgroundColor: colors.card, borderRadius: 16, padding: 20, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }}>
        <ActivityIndicator color="#C9A962" />
      </View>
    );
  }
  if (!summary || !summary.total) return null;

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={() => router.push('/book-of-business' as any)}
      style={{ marginHorizontal: 16, marginBottom: 20, backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border }}
      testID="book-of-business-card"
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 14 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>Your Book of Business</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
            {summary.total} relationships · {summary.needs_attention} need attention
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.borderLight} />
      </View>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {(summary.buckets || []).map((b: any) => (
          <View key={b.key} style={{ flex: 1, alignItems: 'center', backgroundColor: `${b.color}14`, borderRadius: 12, paddingVertical: 10, gap: 2 }}>
            <Text style={{ fontSize: 20, fontWeight: '900', color: b.color }}>{b.count}</Text>
            <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary }} numberOfLines={1}>{b.label}</Text>
          </View>
        ))}
      </View>
      {summary.advocates > 0 ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12 }} testID="book-of-business-advocates">
          <Ionicons name="heart" size={13} color="#0A84FF" />
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>
            <Text style={{ fontWeight: '800', color: '#0A84FF' }}>{summary.advocates}</Text>
            {' '}advocate{summary.advocates !== 1 ? 's' : ''} across every group - worth a thank you
          </Text>
        </View>
      ) : null}
      {touch && touch.total > 0 ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12 }}>
          <Ionicons name="heart" size={13} color="#C9A962" />
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>
            This week{' '}
            <Text style={{ fontWeight: '800', color: '#C9A962' }}>{touch.relationship_pct}%</Text>
            {' '}of your {touch.total} message{touch.total !== 1 ? 's' : ''} were real relationship touches
          </Text>
        </View>
      ) : null}
    </TouchableOpacity>
  );
};
