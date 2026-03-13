import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

type Action = {
  id: string;
  icon: string;
  title: string;
  desc: string;
  color: string;
  route: string;
  params?: Record<string, string>;
  roles: string[]; // which roles can see this
};

const ACTIONS: Action[] = [
  {
    id: 'org_store',
    icon: 'business',
    title: 'New Organization & Store',
    desc: 'Full setup wizard: create org, store, team, branding, templates, tags',
    color: '#FF2D55',
    route: '/admin/setup-wizard',
    roles: ['super_admin'],
  },
  {
    id: 'add_store',
    icon: 'storefront',
    title: 'Add Store to Existing Org',
    desc: 'Add a new store location under an organization you manage',
    color: '#34C759',
    route: '/admin/setup-wizard',
    roles: ['super_admin', 'org_admin'],
  },
  {
    id: 'add_team',
    icon: 'people',
    title: 'Add Team Members',
    desc: 'Invite salespeople, managers, or admins to a store',
    color: '#FF9500',
    route: '/settings/invite-team',
    roles: ['super_admin', 'org_admin', 'store_manager'],
  },
  {
    id: 'individual',
    icon: 'person-add',
    title: 'Add Individual Account',
    desc: 'Create a standalone account (not tied to an organization)',
    color: '#AF52DE',
    route: '/admin/individuals',
    roles: ['super_admin'],
  },
  {
    id: 'partner_onboard',
    icon: 'briefcase',
    title: 'Partner / Reseller Onboard',
    desc: 'Set up a new store for a partner or reseller organization',
    color: '#5856D6',
    route: '/partner/onboard',
    roles: ['super_admin', 'org_admin'],
  },
  {
    id: 'white_label',
    icon: 'color-palette',
    title: 'White Label Partner',
    desc: 'Create or manage a white-label branded instance',
    color: '#00C7BE',
    route: '/admin/white-label',
    roles: ['super_admin'],
  },
  {
    id: 'internal_employee',
    icon: 'shield',
    title: 'Internal i\'M On Social Employee',
    desc: 'Add an internal team member with admin privileges',
    color: '#007AFF',
    route: '/admin/setup-wizard',
    roles: ['super_admin'],
  },
];

const GUIDE_STEPS = [
  { num: 1, title: 'Organization & Store', icon: 'business', color: '#007AFF', desc: 'Create or select org, add store location, industry, contact info' },
  { num: 2, title: 'Branding', icon: 'color-palette', color: '#AF52DE', desc: 'Upload logo, set brand color, email footer' },
  { num: 3, title: 'Team Roster', icon: 'people', color: '#FF9500', desc: 'Add team members, assign roles, temp passwords generated' },
  { num: 4, title: 'Review Links', icon: 'star', color: '#FFCC00', desc: 'Google Reviews, Facebook, Yelp, DealerRater URLs' },
  { num: 5, title: 'Message Templates', icon: 'chatbubbles', color: '#34C759', desc: 'Toggle pre-loaded templates, add custom ones' },
  { num: 6, title: 'Tags', icon: 'pricetags', color: '#5856D6', desc: 'Create tags for organizing contacts' },
  { num: 7, title: 'Handoff', icon: 'checkmark-circle', color: '#34C759', desc: 'Review config, see remaining items, finish' },
];

const AFTER_STEPS = [
  { icon: 'key', color: '#FF9500', text: 'New user logs in with temp password → forced to set new password' },
  { icon: 'document-text', color: '#007AFF', text: 'User must review & accept Terms of Service' },
  { icon: 'school', color: '#5856D6', text: 'Onboarding slides walk them through the app' },
  { icon: 'home', color: '#34C759', text: 'User lands on their Home screen, ready to go' },
];

export default function OnboardingHub() {
  const router = useRouter();
  const colors = useThemeStore((s) => s.colors);
  const user = useAuthStore((s) => s.user);
  const role = user?.role || 'user';
  const [recentAccounts, setRecentAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(false);

  const visibleActions = ACTIONS.filter(a => a.roles.includes(role));

  useEffect(() => {
    loadRecent();
  }, []);

  const loadRecent = async () => {
    try {
      const res = await api.get('/admin/hierarchy/users?limit=5&sort=created_at');
      const users = Array.isArray(res.data) ? res.data : [];
      setRecentAccounts(users.slice(0, 5));
    } catch {}
    setLoading(false);
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={[styles.title, { color: colors.text }]}>Onboarding Hub</Text>
            <Text style={[styles.subtitle, { color: colors.textSecondary }]}>All account creation in one place</Text>
          </View>
        </View>

        {/* Quick Actions */}
        <Text style={[styles.sectionTitle, { color: colors.text }]}>What do you need to do?</Text>
        <View style={styles.actionsGrid}>
          {visibleActions.map((action) => (
            <TouchableOpacity
              key={action.id}
              style={[styles.actionCard, { backgroundColor: colors.card, borderColor: colors.surface }]}
              onPress={() => router.push(action.route as any)}
            >
              <View style={[styles.actionIconWrap, { backgroundColor: `${action.color}15` }]}>
                <Ionicons name={action.icon as any} size={24} color={action.color} />
              </View>
              <Text style={[styles.actionTitle, { color: colors.text }]}>{action.title}</Text>
              <Text style={[styles.actionDesc, { color: colors.textSecondary }]}>{action.desc}</Text>
              <View style={[styles.actionArrow, { backgroundColor: `${action.color}15` }]}>
                <Ionicons name="arrow-forward" size={14} color={action.color} />
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Quick-Reference Guide */}
        <TouchableOpacity
          style={[styles.guideToggle, { backgroundColor: colors.card, borderColor: colors.surface }]}
          onPress={() => setShowGuide(!showGuide)}
        >
          <Ionicons name="book" size={20} color="#5856D6" />
          <Text style={[styles.guideToggleText, { color: colors.text }]}>Setup Wizard Quick-Reference Guide</Text>
          <Ionicons name={showGuide ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
        </TouchableOpacity>

        {showGuide && (
          <View style={styles.guideContent}>
            <Text style={[styles.guideSectionTitle, { color: colors.text }]}>The 7-Step Wizard</Text>
            {GUIDE_STEPS.map((step) => (
              <View key={step.num} style={[styles.guideStep, { backgroundColor: colors.card, borderColor: colors.surface }]}>
                <View style={[styles.guideStepNum, { backgroundColor: `${step.color}20` }]}>
                  <Text style={[styles.guideStepNumText, { color: step.color }]}>{step.num}</Text>
                </View>
                <Ionicons name={step.icon as any} size={16} color={step.color} />
                <View style={{ flex: 1 }}>
                  <Text style={[styles.guideStepTitle, { color: colors.text }]}>{step.title}</Text>
                  <Text style={[styles.guideStepDesc, { color: colors.textSecondary }]}>{step.desc}</Text>
                </View>
              </View>
            ))}

            <Text style={[styles.guideSectionTitle, { color: colors.text, marginTop: 16 }]}>After Setup</Text>
            <View style={[styles.afterBox, { backgroundColor: colors.card, borderColor: colors.surface }]}>
              {AFTER_STEPS.map((a, i) => (
                <View key={i} style={[styles.afterRow, i < AFTER_STEPS.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.surface }]}>
                  <View style={[styles.afterDot, { backgroundColor: `${a.color}20` }]}>
                    <Ionicons name={a.icon as any} size={14} color={a.color} />
                  </View>
                  <Text style={[styles.afterText, { color: colors.textSecondary }]}>{a.text}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Recently Created */}
        {!loading && recentAccounts.length > 0 && (
          <>
            <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 24 }]}>Recently Added Users</Text>
            {recentAccounts.map((u: any, i: number) => (
              <View key={i} style={[styles.recentRow, { backgroundColor: colors.card, borderColor: colors.surface }]}>
                <View style={[styles.recentAvatar, { backgroundColor: '#007AFF20' }]}>
                  <Text style={{ color: '#007AFF', fontWeight: '700', fontSize: 13 }}>
                    {(u.name || u.email || '?')[0].toUpperCase()}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.recentName, { color: colors.text }]}>{u.name || u.email}</Text>
                  <Text style={[styles.recentMeta, { color: colors.textSecondary }]}>{u.role} {u.store_name ? `at ${u.store_name}` : ''}</Text>
                </View>
                <View style={[styles.statusPill, { backgroundColor: u.is_active ? '#34C75920' : '#FF3B3020' }]}>
                  <Text style={{ fontSize: 10, fontWeight: '600', color: u.is_active ? '#34C759' : '#FF3B30' }}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </Text>
                </View>
              </View>
            ))}
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, maxWidth: 800, alignSelf: 'center' as any, width: '100%' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 20 },
  backBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: '700' },
  subtitle: { fontSize: 13, marginTop: 2 },
  sectionTitle: { fontSize: 16, fontWeight: '700', marginBottom: 12 },
  actionsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 20 },
  actionCard: { width: '48%' as any, minWidth: 160, borderRadius: 14, borderWidth: 1, padding: 16, position: 'relative' as any },
  actionIconWrap: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  actionTitle: { fontSize: 14, fontWeight: '700', marginBottom: 4 },
  actionDesc: { fontSize: 11, lineHeight: 16 },
  actionArrow: { position: 'absolute' as any, top: 14, right: 14, width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  guideToggle: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 12, borderWidth: 1, marginBottom: 8 },
  guideToggleText: { fontSize: 14, fontWeight: '600', flex: 1 },
  guideContent: { marginBottom: 12 },
  guideSectionTitle: { fontSize: 14, fontWeight: '700', marginBottom: 8 },
  guideStep: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 10, borderWidth: 1, marginBottom: 6 },
  guideStepNum: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  guideStepNumText: { fontSize: 12, fontWeight: '800' },
  guideStepTitle: { fontSize: 13, fontWeight: '600' },
  guideStepDesc: { fontSize: 11, marginTop: 1 },
  afterBox: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  afterRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12 },
  afterDot: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  afterText: { fontSize: 12, flex: 1, lineHeight: 17 },
  recentRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 10, borderWidth: 1, marginBottom: 6 },
  recentAvatar: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
  recentName: { fontSize: 13, fontWeight: '600' },
  recentMeta: { fontSize: 11, marginTop: 1 },
  statusPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
});
