import React from 'react';
import { Modal, View, Text, TouchableOpacity, ScrollView, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { resolveUserPhotoUrl } from '../../utils/photoUrl';
import { tid } from '../scripts/shared';
import { useAccountSheet } from './accountSheetStore';

const GOLD = '#C9A962';

type Item = { key: string; label: string; icon: string; route?: string; onPress?: () => void; danger?: boolean };
type Section = { title?: string; items: Item[] };

const ROLE_LABEL: Record<string, string> = { super_admin: 'Super admin', org_admin: 'Owner', store_manager: 'Manager', user: 'Sales', partner: 'Partner', reseller: 'Partner' };

/** Configuration lives here, daily work lives in the tabs. Sections grow with the role, nothing is duplicated. */
export const buildAccountSections = (user: any): Section[] => {
  const role = user?.role || 'user';
  const isManager = ['store_manager', 'org_admin', 'super_admin'].includes(role);
  const isOwner = ['org_admin', 'super_admin'].includes(role);
  const isSuper = role === 'super_admin';
  const isPartner = !!user?.partner_id || role === 'partner' || role === 'reseller';

  const sections: Section[] = [{
    items: [
      { key: 'profile', label: 'My Profile & Card', icon: 'person-circle-outline', route: '/my-profile' },
      { key: 'numbers', label: 'My Numbers', icon: 'stats-chart-outline', route: '/touchpoints/performance' },
      { key: 'va', label: 'My VA', icon: 'sparkles-outline', route: '/settings/virtual-assistant' },
      { key: 'notifications', label: 'Notifications', icon: 'notifications-outline', route: '/settings/notifications' },
      { key: 'settings', label: 'Settings', icon: 'settings-outline', route: '/settings' },
    ],
  }];

  if (isManager) {
    sections.push({
      title: 'MANAGE',
      items: [
        { key: 'team', label: 'Team', icon: 'people-outline', route: '/admin/users' },
        { key: 'reports', label: 'Reports & Performance', icon: 'stats-chart-outline', route: '/reports/team-performance' },
        { key: 'campaigns', label: 'Campaigns', icon: 'megaphone-outline', route: '/campaigns' },
        { key: 'templates', label: 'Templates', icon: 'document-text-outline', route: '/settings/templates' },
        { key: 'inboxes', label: 'Shared Inboxes', icon: 'file-tray-full-outline', route: '/inboxes' },
        { key: 'reviews', label: 'Reviews', icon: 'star-outline', route: '/settings/review-links' },
        { key: 'automations', label: 'Automations', icon: 'flash-outline', route: '/settings/keyword-rules' },
        { key: 'store', label: 'Account Settings', icon: 'storefront-outline', route: '/settings/store-profile' },
      ],
    });
  }
  if (isOwner) {
    sections.push({
      title: 'ACCOUNT',
      items: [
        { key: 'locations', label: 'Locations', icon: 'business-outline', route: '/admin/stores' },
        { key: 'invite', label: 'Invite Team', icon: 'person-add-outline', route: '/settings/invite-team' },
        { key: 'numbers', label: 'Phone Numbers', icon: 'call-outline', route: '/admin/twilio-numbers' },
        { key: 'compliance', label: 'Texting Compliance', icon: 'shield-checkmark-outline', route: '/admin/compliance' },
        { key: 'integrations', label: 'Integrations', icon: 'git-network-outline', route: '/settings/integrations' },
      ],
    });
  }
  if (isPartner) {
    sections.push({ title: 'PARTNER', items: [{ key: 'partner', label: 'Partner Portal', icon: 'briefcase-outline', route: '/partner/dashboard' }] });
  }
  if (isSuper) {
    sections.push({
      title: 'INTERNAL',
      items: [
        { key: 'admin', label: 'Admin Dashboard', icon: 'speedometer-outline', route: '/admin' },
        { key: 'orgs', label: 'Organizations', icon: 'globe-outline', route: '/admin/organizations' },
        { key: 'pending', label: 'Pending Users', icon: 'hourglass-outline', route: '/admin/pending-users' },
        { key: 'shops', label: 'Mystery Shops', icon: 'headset-outline', route: '/admin/mystery-shops' },
        { key: 'testlab', label: 'Test Lab', icon: 'flask-outline', route: '/admin/test-lab' },
      ],
    });
  }

  sections.push({
    title: isManager ? 'EVERYTHING ELSE' : undefined,
    items: [
      { key: 'tools', label: isManager ? 'All tools' : 'More tools', icon: 'grid-outline', route: '/(tabs)/more' },
      { key: 'help', label: 'Help & Support', icon: 'help-circle-outline', route: '/help' },
      { key: 'legal', label: 'Terms & Privacy', icon: 'document-lock-outline', route: '/terms' },
    ],
  });
  return sections;
};

export const AccountSheet = () => {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const { colors } = useThemeStore();
  const { visible, close } = useAccountSheet();
  if (!visible || !user) return null;
  const sections = buildAccountSections(user);
  const uri = resolveUserPhotoUrl(user as any);
  const go = (item: Item) => {
    close();
    if (item.onPress) return item.onPress();
    if (item.route) setTimeout(() => router.push(item.route as any), 40);
  };
  const signOut = async () => {
    close();
    await logout();
    router.replace('/auth/login' as any);
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={close}>
      <TouchableOpacity activeOpacity={1} onPress={close} style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' }}>
        <TouchableOpacity activeOpacity={1} style={{ maxHeight: '88%', backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, borderWidth: 1, borderColor: colors.border }} {...tid('account-sheet')}>
          <View style={{ alignSelf: 'center', width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border, marginTop: 8 }} />
          <TouchableOpacity onPress={() => go({ key: 'profile', label: '', icon: '', route: '/my-profile' })} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 20, paddingVertical: 16 }} {...tid('account-sheet-profile')}>
            {uri ? <Image source={{ uri }} style={{ width: 48, height: 48, borderRadius: 24 }} /> : (
              <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: 'rgba(201,169,98,0.16)', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="person" size={22} color={GOLD} />
              </View>
            )}
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }} numberOfLines={1}>{user.name || user.email}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary }} numberOfLines={1}>{ROLE_LABEL[user.role || 'user'] || 'Sales'}{(user as any).store_name ? ` · ${(user as any).store_name}` : ''}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
          </TouchableOpacity>

          <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 28 }} showsVerticalScrollIndicator={false}>
            {sections.map((sec, si) => (
              <View key={si} style={{ marginTop: si === 0 ? 0 : 18 }}>
                {!!sec.title && <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 1.4, color: GOLD, marginBottom: 6 }}>{sec.title}</Text>}
                {sec.items.map((item, i) => (
                  <TouchableOpacity key={item.key} onPress={() => go(item)}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 13, borderBottomWidth: i < sec.items.length - 1 ? 0.5 : 0, borderBottomColor: colors.border }}
                    {...tid(`account-item-${item.key}`)}>
                    <Ionicons name={item.icon as any} size={20} color={colors.textSecondary} />
                    <Text style={{ flex: 1, fontSize: 16, color: colors.text }}>{item.label}</Text>
                    <Ionicons name="chevron-forward" size={15} color={colors.border} />
                  </TouchableOpacity>
                ))}
              </View>
            ))}
            <TouchableOpacity onPress={signOut} style={{ marginTop: 22, paddingVertical: 13, alignItems: 'center', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,59,48,0.35)' }} {...tid('account-sign-out')}>
              <Text style={{ fontSize: 15, fontWeight: '700', color: '#FF3B30' }}>Sign Out</Text>
            </TouchableOpacity>
          </ScrollView>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
};
