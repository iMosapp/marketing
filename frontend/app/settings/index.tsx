import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { showConfirm } from '../../services/alert';
import { tid } from '../../components/scripts/shared';

type Row = { key: string; icon: any; title: string; subtitle: string; color: string; route: string };

const ROWS: Row[] = [
  { key: 'notifications', icon: 'notifications', title: 'Notifications', subtitle: 'Push, text alerts and quiet times', color: '#FF9F0A', route: '/settings/notifications' },
  { key: 'schedule', icon: 'time', title: 'My Schedule', subtitle: 'Work hours, when the app stays quiet', color: '#32ADE6', route: '/settings/schedule' },
  { key: 'calendar', icon: 'calendar', title: 'Calendar Sync', subtitle: 'Connect Google or Apple calendar', color: '#007AFF', route: '/settings/calendar' },
  { key: 'security', icon: 'lock-closed', title: 'Security', subtitle: 'Password and Face ID', color: '#8E8E93', route: '/settings/security' },
  { key: 'account', icon: 'person', title: 'My Info', subtitle: 'Name, cell, email, photo', color: '#C9A962', route: '/my-account' },
  { key: 'help', icon: 'help-circle', title: 'Help Center', subtitle: 'How-to guides, ask a question', color: '#34C759', route: '/help' },
  { key: 'bug', icon: 'bug', title: 'Report a Bug', subtitle: 'Flag an issue or share feedback', color: '#FF453A', route: '/report-bug' },
];

// The one Settings screen a rep needs: the few things they adjust themselves. Everything else is a manager's call.
export default function SettingsIndex() {
  const router = useRouter();
  const { colors, mode, toggle } = useThemeStore();
  const { logout } = useAuthStore();
  const signOut = () => showConfirm('Sign out?', 'You can sign back in any time with Face ID or your password.', () => { logout(); }, undefined, 'Sign out');
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Settings" testID="settings-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 10 }} {...tid('settings-index')}>
        <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          {ROWS.map((r, i) => (
            <TouchableOpacity key={r.key} onPress={() => router.push(r.route as any)} activeOpacity={0.7}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }} {...tid(`settings-row-${r.key}`)}>
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
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderTopWidth: 1, borderTopColor: colors.border }} {...tid('settings-row-theme')}>
            <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: (mode === 'dark' ? '#5856D6' : '#FF9500') + '22', alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={mode === 'dark' ? 'moon' : 'sunny'} size={18} color={mode === 'dark' ? '#5856D6' : '#FF9500'} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15.5, fontWeight: '700', color: colors.text }}>Dark mode</Text>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 1 }}>{mode === 'dark' ? 'On' : 'Off'}</Text>
            </View>
            <Switch value={mode === 'dark'} onValueChange={toggle} trackColor={{ true: '#C9A962', false: colors.border }} {...tid('settings-theme-switch')} />
          </View>
        </View>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18, paddingHorizontal: 4 }}>Want another tool on your Tools tab? Ask your manager; they can switch it on for you in a tap.</Text>
        <TouchableOpacity onPress={signOut} style={{ marginTop: 10, height: 46, borderRadius: 14, borderWidth: 1, borderColor: '#FF3B3055', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('settings-sign-out')}>
          <Ionicons name="log-out-outline" size={18} color="#FF3B30" />
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#FF3B30' }}>Sign out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}
