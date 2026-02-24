import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
  Image,
  LayoutAnimation,
  UIManager,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert } from '../../services/alert';
import api from '../../services/api';

// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const COLLAPSED_SECTIONS_KEY = 'collapsed_sections';

interface MenuItem {
  id: string;
  icon: string;
  title: string;
  subtitle?: string;
  color: string;
  route?: string;
  onPress?: () => void;
  badge?: number;
  adminOnly?: boolean;
}

interface MenuSection {
  id: string;
  title: string;
  icon: string;
  color: string;
  items: MenuItem[];
  adminOnly?: boolean;
}

export default function MoreScreen() {
  const router = useRouter();
  const { user, logout, isImpersonating, stopImpersonation, originalUser } = useAuthStore();
  const [pendingUsersCount, setPendingUsersCount] = useState(0);
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const [exitingImpersonation, setExitingImpersonation] = useState(false);

  // Check if user is admin
  const isAdmin = user?.role === 'super_admin' || user?.role === 'org_admin' || user?.role === 'store_manager';
  const isSuperAdmin = user?.role === 'super_admin' || originalUser?.role === 'super_admin';

  useFocusEffect(
    useCallback(() => {
      loadCollapsedSections();
      if (isSuperAdmin) {
        fetchPendingCount();
      }
    }, [isSuperAdmin])
  );

  const loadCollapsedSections = async () => {
    try {
      const saved = await AsyncStorage.getItem(COLLAPSED_SECTIONS_KEY);
      if (saved) {
        setCollapsedSections(new Set(JSON.parse(saved)));
      }
    } catch (error) {
      console.error('Failed to load collapsed sections:', error);
    }
  };

  const toggleSection = async (sectionId: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    const newCollapsed = new Set(collapsedSections);
    if (newCollapsed.has(sectionId)) {
      newCollapsed.delete(sectionId);
    } else {
      newCollapsed.add(sectionId);
    }
    setCollapsedSections(newCollapsed);
    await AsyncStorage.setItem(COLLAPSED_SECTIONS_KEY, JSON.stringify([...newCollapsed]));
  };

  const fetchPendingCount = async () => {
    try {
      const response = await api.get('/admin/pending-users');
      setPendingUsersCount(response.data?.length || 0);
    } catch (error) {
      console.error('Failed to fetch pending count:', error);
    }
  };

  const handleLogout = () => {
    showSimpleAlert('Sign Out', 'Are you sure you want to sign out?');
    logout();
    router.replace('/auth/login');
  };

  const handleExitImpersonation = async () => {
    if (exitingImpersonation) return;
    setExitingImpersonation(true);
    try {
      await stopImpersonation();
      router.replace('/admin/users');
    } catch (error) {
      showSimpleAlert('Error', 'Failed to exit impersonation');
    } finally {
      setExitingImpersonation(false);
    }
  };

  // Define menu sections
  const menuSections: MenuSection[] = [
    {
      id: 'quick-actions',
      title: 'Quick Actions',
      icon: 'flash',
      color: '#FFD60A',
      items: [
        { id: 'training', icon: 'school', title: 'Training Hub', subtitle: 'Learn how to use iMos', color: '#FF9500', route: '/training-hub' },
        { id: 'jessi', icon: 'sparkles', title: 'Ask Jessi', subtitle: 'Your AI assistant', color: '#C9A962', route: '/jessie' },
        { id: 'broadcast', icon: 'megaphone', title: 'Broadcast', subtitle: 'Send mass messages', color: '#FF9500', route: '/broadcast' },
        { id: 'tasks', icon: 'checkmark-done', title: 'Tasks & Reminders', subtitle: 'Manage follow-ups', color: '#34C759', route: '/tasks' },
      ],
    },
    {
      id: 'sales-marketing',
      title: 'Sales & Marketing',
      icon: 'trending-up',
      color: '#34C759',
      items: [
        { id: 'lead-sources', icon: 'git-branch', title: 'Lead Sources', subtitle: 'Manage inbound leads', color: '#5856D6', route: '/admin/lead-sources' },
        { id: 'sms-campaigns', icon: 'chatbubbles', title: 'SMS Campaigns', subtitle: 'Automated follow-ups', color: '#FF2D55', route: '/campaigns' },
        { id: 'email-campaigns', icon: 'mail', title: 'Email Campaigns', subtitle: 'Email sequences', color: '#AF52DE', route: '/campaigns/email' },
        { id: 'campaign-dashboard', icon: 'speedometer', title: 'Campaign Dashboard', subtitle: 'View enrollments', color: '#5AC8FA', route: '/campaigns/dashboard' },
        { id: 'review-links', icon: 'star', title: 'Review Links', subtitle: 'Get customer reviews', color: '#FFD60A', route: '/settings/review-links' },
        { id: 'congrats', icon: 'gift', title: 'Congrats Cards', subtitle: 'Celebrate purchases', color: '#C9A962', route: '/settings/congrats-template' },
      ],
    },
    {
      id: 'communications',
      title: 'Communications',
      icon: 'chatbubble-ellipses',
      color: '#007AFF',
      items: [
        { id: 'sms-templates', icon: 'document-text', title: 'SMS Templates', subtitle: 'Quick response templates', color: '#FFD60A', route: '/settings/templates' },
        { id: 'email-templates', icon: 'mail-outline', title: 'Email Templates', subtitle: 'Email response templates', color: '#34C759', route: '/settings/email-templates' },
        { id: 'brand-kit', icon: 'color-palette', title: 'Brand Kit', subtitle: 'Email branding & colors', color: '#AF52DE', route: '/settings/brand-kit' },
        { id: 'tags', icon: 'pricetags', title: 'Contact Tags', subtitle: 'Organize contacts', color: '#FF9500', route: '/settings/tags' },
      ],
    },
    {
      id: 'performance',
      title: 'Performance & Analytics',
      icon: 'bar-chart',
      color: '#5856D6',
      items: [
        { id: 'analytics', icon: 'stats-chart', title: 'Analytics', subtitle: 'Performance metrics', color: '#34C759', route: '/analytics' },
        { id: 'reports', icon: 'bar-chart', title: 'Reports', subtitle: 'Detailed reports', color: '#007AFF', route: '/reports' },
        { id: 'email-analytics', icon: 'pie-chart', title: 'Email Analytics', subtitle: 'Opens, clicks & engagement', color: '#FF2D55', route: '/settings/email-analytics' },
        { id: 'leaderboard', icon: 'trophy', title: 'Leaderboard', subtitle: 'Team rankings', color: '#FFD60A', route: '/admin/leaderboard', adminOnly: true },
      ],
    },
    {
      id: 'administration',
      title: 'Administration',
      icon: 'shield',
      color: '#FF3B30',
      adminOnly: true,
      items: [
        { id: 'users', icon: 'people', title: 'Manage Users', subtitle: 'Add, edit, remove users', color: '#007AFF', route: '/admin/users', badge: pendingUsersCount },
        { id: 'organizations', icon: 'business', title: 'Organizations', subtitle: 'Manage organizations', color: '#5856D6', route: '/admin/organizations' },
        { id: 'stores', icon: 'storefront', title: 'Stores', subtitle: 'Manage store locations', color: '#34C759', route: '/admin/stores' },
        { id: 'agreements', icon: 'document', title: 'Partner Agreements', subtitle: 'Reseller & referral contracts', color: '#FF9500', route: '/admin/partner-agreements' },
        { id: 'quotes', icon: 'receipt', title: 'Quotes', subtitle: 'Subscription quotes', color: '#C9A962', route: '/admin/quotes' },
        { id: 'pending-users', icon: 'person-add', title: 'Pending Approvals', subtitle: 'Review new signups', color: '#FF3B30', route: '/admin/pending-users', badge: pendingUsersCount },
      ],
    },
    {
      id: 'settings',
      title: 'Settings',
      icon: 'settings',
      color: '#8E8E93',
      items: [
        { id: 'my-profile', icon: 'card', title: 'My Digital Card', subtitle: 'Photo, bio & socials', color: '#007AFF', route: '/settings/my-profile' },
        { id: 'persona', icon: 'person', title: 'AI Persona', subtitle: 'Communication style', color: '#AF52DE', route: '/settings/persona' },
        { id: 'security', icon: 'shield-checkmark', title: 'Security', subtitle: 'Password & Face ID', color: '#FF3B30', route: '/settings/security' },
        { id: 'calendar', icon: 'calendar', title: 'Calendar', subtitle: 'Connect calendars', color: '#007AFF', route: '/settings/calendar' },
        { id: 'integrations', icon: 'git-network', title: 'Integrations', subtitle: 'API keys & webhooks', color: '#5856D6', route: '/settings/integrations' },
        { id: 'notifications', icon: 'notifications', title: 'Notifications', subtitle: 'Alerts & sounds', color: '#FF9500', onPress: () => showSimpleAlert('Coming Soon', 'Notification settings coming soon') },
      ],
    },
  ];

  // Filter sections based on admin status
  const visibleSections = menuSections.filter(section => !section.adminOnly || isAdmin);

  const renderMenuItem = (item: MenuItem) => {
    if (item.adminOnly && !isAdmin) return null;
    
    return (
      <TouchableOpacity
        key={item.id}
        style={styles.menuItem}
        onPress={() => item.route ? router.push(item.route as any) : item.onPress?.()}
      >
        <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
          <Ionicons name={item.icon as any} size={22} color={item.color} />
        </View>
        <View style={styles.menuContent}>
          <Text style={styles.menuTitle}>{item.title}</Text>
          {item.subtitle && <Text style={styles.menuSubtitle}>{item.subtitle}</Text>}
        </View>
        {item.badge && item.badge > 0 ? (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{item.badge}</Text>
          </View>
        ) : (
          <Ionicons name="chevron-forward" size={18} color="#6E6E73" />
        )}
      </TouchableOpacity>
    );
  };

  const getInitials = () => {
    if (!user?.name) return '?';
    return user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Impersonation Banner */}
        {isImpersonating && (
          <TouchableOpacity style={styles.impersonationBanner} onPress={handleExitImpersonation}>
            <Ionicons name="eye" size={20} color="#FFF" />
            <Text style={styles.impersonationText}>
              Viewing as {user?.name} • Tap to exit
            </Text>
          </TouchableOpacity>
        )}

        {/* Profile Card */}
        <TouchableOpacity
          style={styles.profileCard}
          onPress={() => router.push('/my-account')}
          activeOpacity={0.7}
        >
          <View style={styles.profileAvatarContainer}>
            {user?.photo_url ? (
              <Image source={{ uri: user.photo_url }} style={styles.profileAvatarImage} />
            ) : (
              <View style={styles.profileAvatar}>
                <Text style={styles.profileAvatarText}>{getInitials()}</Text>
              </View>
            )}
            <View style={styles.editBadge}>
              <Ionicons name="pencil" size={10} color="#FFF" />
            </View>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{user?.name || 'Guest'}</Text>
            <Text style={styles.profileEmail}>{user?.email || ''}</Text>
            {user?.role && user.role !== 'user' && (
              <View style={styles.roleBadge}>
                <Ionicons name="shield-checkmark" size={12} color="#34C759" />
                <Text style={styles.roleText}>
                  {user.role === 'super_admin' ? 'Super Admin' :
                   user.role === 'org_admin' ? 'Org Admin' :
                   user.role === 'store_manager' ? 'Manager' : ''}
                </Text>
              </View>
            )}
          </View>
          <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
        </TouchableOpacity>

        {/* Customize Button */}
        <TouchableOpacity
          style={styles.customizeButton}
          onPress={() => router.push('/customize-menu')}
        >
          <Ionicons name="options" size={18} color="#007AFF" />
          <Text style={styles.customizeText}>Customize Menu</Text>
        </TouchableOpacity>

        {/* Menu Sections */}
        {visibleSections.map(section => (
          <View key={section.id} style={styles.section}>
            {/* Section Header - Clickable to expand/collapse */}
            <TouchableOpacity
              style={styles.sectionHeader}
              onPress={() => toggleSection(section.id)}
              activeOpacity={0.7}
            >
              <View style={[styles.sectionIcon, { backgroundColor: `${section.color}20` }]}>
                <Ionicons name={section.icon as any} size={20} color={section.color} />
              </View>
              <Text style={styles.sectionTitle}>{section.title}</Text>
              <View style={styles.sectionCount}>
                <Text style={styles.sectionCountText}>{section.items.filter(i => !i.adminOnly || isAdmin).length}</Text>
              </View>
              <Ionicons
                name={collapsedSections.has(section.id) ? 'chevron-down' : 'chevron-up'}
                size={20}
                color="#8E8E93"
              />
            </TouchableOpacity>

            {/* Section Items - Collapsible */}
            {!collapsedSections.has(section.id) && (
              <View style={styles.sectionItems}>
                {section.items.map(item => renderMenuItem(item))}
              </View>
            )}
          </View>
        ))}

        {/* Legal Section */}
        <View style={styles.legalSection}>
          <TouchableOpacity style={styles.legalLink} onPress={() => router.push('/terms')}>
            <Text style={styles.legalText}>Terms of Service</Text>
          </TouchableOpacity>
          <Text style={styles.legalDivider}>•</Text>
          <TouchableOpacity style={styles.legalLink} onPress={() => router.push('/privacy')}>
            <Text style={styles.legalText}>Privacy Policy</Text>
          </TouchableOpacity>
        </View>

        {/* Sign Out */}
        <TouchableOpacity style={styles.signOutButton} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={22} color="#FF3B30" />
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  scrollContent: {
    paddingBottom: 20,
  },
  impersonationBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF9500',
    padding: 12,
    gap: 8,
  },
  impersonationText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    margin: 16,
    padding: 16,
    borderRadius: 16,
  },
  profileAvatarContainer: {
    position: 'relative',
    marginRight: 14,
  },
  profileAvatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileAvatarImage: {
    width: 56,
    height: 56,
    borderRadius: 28,
  },
  profileAvatarText: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
  },
  editBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#1C1C1E',
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
  },
  profileEmail: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#34C75920',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginTop: 6,
  },
  roleText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#34C759',
  },
  customizeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 10,
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
  },
  customizeText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#007AFF',
  },
  section: {
    marginBottom: 8,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#1C1C1E',
    marginHorizontal: 16,
    borderRadius: 12,
  },
  sectionIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  sectionTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '700',
    color: '#FFF',
  },
  sectionCount: {
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    marginRight: 8,
  },
  sectionCountText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
  },
  sectionItems: {
    backgroundColor: '#1C1C1E',
    marginHorizontal: 16,
    marginTop: 2,
    borderRadius: 12,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  menuSubtitle: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 1,
  },
  badge: {
    backgroundColor: '#FF3B30',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    minWidth: 24,
    alignItems: 'center',
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFF',
  },
  legalSection: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 20,
    gap: 12,
  },
  legalLink: {
    padding: 4,
  },
  legalText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  legalDivider: {
    fontSize: 13,
    color: '#6E6E73',
  },
  signOutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginHorizontal: 16,
    padding: 16,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#FF3B3040',
  },
  signOutText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF3B30',
  },
});
