import React from 'react';
import { ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { showConfirm } from '../../services/alert';
import { GOLD, tid } from '../ui/tokens';

type Row = { key: string; icon: any; title: string; subtitle: string; color: string; route: string };

/** Pilot "More": only what a pilot customer needs. The full tool hub stays untouched for everyone else. */
export function pilotRows(user: any): Row[] {
  const owner = !!user?.pilot_owner;
  const pp = user?.pilot_program;
  const billingSub = pp?.state === 'active' ? `Founding Partner Pilot · ${pp.days_left} days left` : pp?.state === 'completed' ? 'Your pilot period ended · continue here' : pp?.state === 'converted' ? 'Card saved · plan, invoices and payment method' : 'Your plan, invoices and payment method';
  return [
    { key: 'profile', icon: 'id-card', title: 'My Profile & Card', subtitle: 'Photo, title, bio and your digital card', color: GOLD, route: '/my-account' },
    ...(owner ? [
      { key: 'billing', icon: 'card', title: 'Billing', subtitle: billingSub, color: '#34C759', route: '/settings/billing' },
      { key: 'team', icon: 'person-add', title: 'Invite Your Team', subtitle: 'Add a teammate to one of your seats', color: '#007AFF', route: '/settings/invite-team' },
    ] : []),
    ...(owner || ['org_admin', 'store_manager', 'admin', 'manager'].includes(user?.role) ? [
      { key: 'my_team', icon: 'people', title: 'My Team', subtitle: 'Setup, texting readiness and this week\'s activity', color: '#34C759', route: '/my-team' },
    ] : []),
    { key: 'notifications', icon: 'notifications', title: 'Notifications', subtitle: 'Push, text alerts and quiet times', color: '#FF9F0A', route: '/settings/notifications' },
    { key: 'settings', icon: 'settings', title: 'Settings', subtitle: 'Password, Face ID, dark mode', color: '#8E8E93', route: '/settings' },
    { key: 'feedback', icon: 'chatbox-ellipses', title: 'Send Feedback', subtitle: 'A question, a problem or a suggestion', color: '#5856D6', route: '/report-bug?from=more' },
    { key: 'help', icon: 'help-circle', title: 'Help & Support', subtitle: 'How-to guides, ask a question', color: '#32ADE6', route: '/help' },
  ];
}

export function PilotMore() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { user, logout } = useAuthStore();
  const rows = pilotRows(user);
  const signOut = () => showConfirm('Sign out?', 'You can sign back in any time with your email and password.', () => { logout(); router.replace('/auth/login' as any); }, undefined, 'Sign out');
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('more-pilot')}>
      <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12 }}>
        <Text style={{ fontSize: 28, fontWeight: '800', color: colors.text }}>More</Text>
        {(user as any)?.organization_name ? <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>{(user as any).organization_name}</Text> : null}
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 10 }}>
        <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          {rows.map((r, i) => (
            <TouchableOpacity key={r.key} onPress={() => router.push(r.route as any)} activeOpacity={0.7}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }} {...tid(`pilot-more-${r.key}`)}>
              <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: r.color + '22', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name={r.icon} size={18} color={r.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15.5, fontWeight: '700', color: colors.text }}>{r.title}</Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 1 }}>{r.subtitle}</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          ))}
        </View>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18, paddingHorizontal: 4 }}>Need something that is not here? Send feedback and we will get right back to you.</Text>
        <TouchableOpacity onPress={signOut} style={{ marginTop: 10, height: 46, borderRadius: 14, borderWidth: 1, borderColor: '#FF3B3055', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('pilot-more-sign-out')}>
          <Ionicons name="log-out-outline" size={18} color="#FF3B30" />
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#FF3B30' }}>Sign out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}
