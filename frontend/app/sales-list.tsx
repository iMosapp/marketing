import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const LABEL: Record<string, string> = {
  sold: 'Sold This Month',
  referrals: 'Referrals This Month',
  repeats: 'Repeat Buyers',
};

export default function SalesListScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const { type = 'sold', month, year } = useLocalSearchParams<{ type: string; month: string; year: string }>();

  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    api.get(`/users/${user._id}/sold-contacts`, {
      params: { filter_type: type, month: month || 0, year: year || 0 }
    }).then(r => setContacts(r.data.contacts || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user?._id, type, month, year]);

  const now = new Date();
  const monthLabel = new Date(
    parseInt(year || String(now.getFullYear())),
    parseInt(month || String(now.getMonth() + 1)) - 1
  ).toLocaleString('default', { month: 'long', year: 'numeric' });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text }}>{LABEL[type] || 'Sales List'}</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>{monthLabel}</Text>
        </View>
        <View style={{ backgroundColor: '#C9A96220', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10 }}>
          <Text style={{ fontSize: 16, fontWeight: '800', color: '#C9A962' }}>{contacts.length}</Text>
        </View>
      </View>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      ) : contacts.length === 0 ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }}>
          <Ionicons name="trophy-outline" size={48} color={colors.borderLight} />
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginTop: 16 }}>No records yet</Text>
          <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 8 }}>
            {type === 'sold' ? 'Use the SOLD wizard to log deliveries' : `No ${type} recorded this month`}
          </Text>
        </View>
      ) : (
        <FlatList
          data={contacts}
          keyExtractor={item => item._id}
          contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 32 }}
          renderItem={({ item }) => (
            <TouchableOpacity
              onPress={() => router.push(`/contact/${item._id}` as any)}
              style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.surface, gap: 12 }}
              data-testid={`sales-list-contact-${item._id}`}
            >
              {/* Avatar */}
              <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ fontSize: 18, fontWeight: '700', color: '#C9A962' }}>
                  {(item.name || '?')[0].toUpperCase()}
                </Text>
              </View>

              {/* Info */}
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{item.name}</Text>
                {item.vehicle ? (
                  <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>{item.vehicle}</Text>
                ) : null}
                {item.referred_by_name && type === 'referrals' ? (
                  <Text style={{ fontSize: 12, color: '#007AFF', marginTop: 2 }}>
                    <Ionicons name="person" size={11} color="#007AFF" /> Referred by {item.referred_by_name}
                  </Text>
                ) : null}
                {type === 'repeats' && item.sold_count > 1 ? (
                  <Text style={{ fontSize: 12, color: '#AF52DE', marginTop: 2 }}>
                    {item.sold_count}x buyer
                  </Text>
                ) : null}
              </View>

              {/* Date + chevron */}
              <View style={{ alignItems: 'flex-end', gap: 4 }}>
                {item.date_sold ? (
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>
                    {new Date(item.date_sold).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </Text>
                ) : null}
                <Ionicons name="chevron-forward" size={16} color={colors.borderLight} />
              </View>
            </TouchableOpacity>
          )}
        />
      )}
    </SafeAreaView>
  );
}
