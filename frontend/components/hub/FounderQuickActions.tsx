// Founder quick actions under the pins: sign someone up (two ways) and show them quick wins.
import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const ACTIONS = [
  { id: 'signup-customer', icon: 'rocket', title: 'Sign up a customer', sub: 'New company, Founding Partner Pilot', route: '/onboarding/new-account', color: GOLD },
  { id: 'signup-jessi', icon: 'chatbubbles', title: 'Onboard with Jessi', sub: 'She texts, calls, builds their card', route: '/admin/users?add=1&jessi=1', color: '#AF52DE' },
  { id: 'quick-wins', icon: 'trophy', title: 'Show quick wins', sub: 'Three 2-minute wins to demo live', route: '/admin/quick-wins', color: '#34C759' },
];

export const FounderQuickActions = ({ colors }: { colors: any }) => {
  const router = useRouter();
  return (
    <View style={{ marginHorizontal: 16, marginBottom: 12 }} {...tid('founder-quick-actions')}>
      <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 1.4, color: GOLD, textTransform: 'uppercase', marginBottom: 6 }}>Quick actions</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {ACTIONS.map(a => (
          <TouchableOpacity key={a.id} onPress={() => router.push(a.route as any)} activeOpacity={0.8}
            style={{ flex: 1, minWidth: 0, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 12, gap: 8 }}
            {...tid(`quick-action-${a.id}`)}>
            <View style={{ width: 32, height: 32, borderRadius: 10, backgroundColor: `${a.color}22`, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={a.icon as any} size={18} color={a.color} />
            </View>
            <Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }} numberOfLines={2}>{a.title}</Text>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 15 }} numberOfLines={2}>{a.sub}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
};
