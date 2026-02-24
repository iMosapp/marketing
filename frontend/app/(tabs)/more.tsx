import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  Pressable,
  StyleSheet,
  ScrollView,
  Platform,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../../store/authStore';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import { WebSafeButton } from '../../components/WebSafeButton';
import api from '../../services/api';

const HIDDEN_ITEMS_KEY = 'hidden_menu_items';

export default function MoreScreen() {
  const router = useRouter();
  const { user, logout, isImpersonating, stopImpersonation, originalUser } = useAuthStore();
  const [pendingUsersCount, setPendingUsersCount] = useState(0);
  const [exitingImpersonation, setExitingImpersonation] = useState(false);
  const [hiddenItems, setHiddenItems] = useState<Set<string>>(new Set());
  
  // Load hidden items and pending count
  useFocusEffect(
    useCallback(() => {
      loadHiddenItems();
      if (user?.role === 'super_admin' || originalUser?.role === 'super_admin') {
        fetchPendingCount();
      }
    }, [user?.role, originalUser?.role])
  );
  
  const loadHiddenItems = async () => {
    try {
      const saved = await AsyncStorage.getItem(HIDDEN_ITEMS_KEY);
      if (saved) {
        setHiddenItems(new Set(JSON.parse(saved)));
      }
    } catch (error) {
      console.error('Failed to load hidden items:', error);
    }
  };
  
  const fetchPendingCount = async () => {
    try {
      const res = await api.get('/admin/pending-users/count');
      setPendingUsersCount(res.data.count);
    } catch (error) {
      console.error('Failed to fetch pending users count:', error);
    }
  };
  
  const handleExitImpersonation = async () => {
    setExitingImpersonation(true);
    try {
      await stopImpersonation();
      showSimpleAlert('Success', `You are now logged back in as ${originalUser?.name}`);
      router.replace('/(tabs)/inbox');
    } catch (error) {
      showSimpleAlert('Error', 'Failed to exit impersonation');
    } finally {
      setExitingImpersonation(false);
    }
  };
  
  const handleLogout = async () => {
    try {
      await logout();
      if (Platform.OS === 'web') {
        window.location.href = '/auth/login';
      } else {
        router.replace('/auth/login');
      }
    } catch (e) {
      console.error('Logout error:', e);
      if (Platform.OS === 'web') {
        window.location.href = '/auth/login';
      }
    }
  };
  
  // Check if user has admin access
  const isAdmin = user?.role === 'super_admin' || user?.role === 'org_admin' || user?.role === 'store_manager';
  
  const menuItems = [
    {
      id: 'training-hub',
      icon: 'school',
      title: 'Training Hub',
      subtitle: 'Learn how to use iMos',
      onPress: () => router.push('/training-hub'),
      color: '#FF9500',
      alwaysShow: true,
    },
    {
      id: 'ask-jessi',
      icon: 'sparkles',
      title: 'Ask Jessi',
      subtitle: 'Your AI assistant for iMos help',
      onPress: () => router.push('/jessie'),
      color: '#C9A962',
    },
    {
      id: 'digital-card',
      icon: 'card',
      title: 'My Digital Card',
      subtitle: 'Photo, bio, socials & card preview',
      onPress: () => router.push('/settings/my-profile'),
      color: '#007AFF',
    },
    {
      id: 'ai-persona',
      icon: 'person',
      title: 'AI Persona Settings',
      subtitle: 'Edit your AI communication style',
      onPress: () => router.push('/settings/persona'),
      color: '#AF52DE',
    },
    {
      id: 'tasks',
      icon: 'checkmark-done',
      title: 'Tasks & Reminders',
      subtitle: 'Manage follow-ups and to-dos',
      onPress: () => router.push('/tasks'),
      color: '#34C759',
    },
    {
      id: 'notifications',
      icon: 'notifications',
      title: 'Notifications',
      subtitle: 'Manage alerts and escalations',
      onPress: () => showSimpleAlert('Notifications', 'Feature coming soon'),
      color: '#FF9500',
    },
    {
      id: 'broadcast',
      icon: 'megaphone',
      title: 'Broadcast',
      subtitle: 'One-time mass messaging',
      onPress: () => router.push('/broadcast'),
      color: '#FF9500',
    },
    {
      id: 'lead-sources',
      icon: 'git-branch',
      title: 'Lead Sources',
      subtitle: 'Manage inbound leads & routing',
      onPress: () => router.push('/admin/lead-sources'),
      color: '#5856D6',
    },
    {
      id: 'sms-campaigns',
      icon: 'chatbubbles',
      title: 'SMS Campaigns',
      subtitle: 'Automated SMS follow-ups',
      onPress: () => router.push('/campaigns'),
      color: '#FF2D55',
    },
    {
      id: 'email-campaigns',
      icon: 'mail',
      title: 'Email Campaigns',
      subtitle: 'Automated email follow-ups',
      onPress: () => router.push('/campaigns/email'),
      color: '#AF52DE',
    },
    {
      id: 'campaign-dashboard',
      icon: 'speedometer',
      title: 'Campaign Dashboard',
      subtitle: 'View enrollments and pending messages',
      onPress: () => router.push('/campaigns/dashboard'),
      color: '#5AC8FA',
    },
    {
      id: 'analytics',
      icon: 'stats-chart',
      title: 'Analytics',
      subtitle: 'View your performance metrics',
      onPress: () => router.push('/analytics'),
      color: '#34C759',
    },
    {
      id: 'reports',
      icon: 'bar-chart',
      title: 'Reports',
      subtitle: 'Detailed performance reports',
      onPress: () => router.push('/reports'),
      color: '#007AFF',
    },
    {
      id: 'security',
      icon: 'shield-checkmark',
      title: 'Security',
      subtitle: 'Face ID, password settings',
      onPress: () => router.push('/settings/security'),
      color: '#FF3B30',
    },
    {
      id: 'sms-email-toggle',
      icon: 'swap-horizontal-outline',
      title: 'SMS / Email Toggle',
      subtitle: 'Choose toggle style and default mode',
      onPress: () => router.push('/settings/toggle-style'),
      color: '#5AC8FA',
    },
    {
      id: 'templates',
      icon: 'document-text',
      title: 'SMS Templates',
      subtitle: 'Create and manage SMS templates',
      onPress: () => router.push('/settings/templates'),
      color: '#FFD60A',
    },
    {
      id: 'email-templates',
      icon: 'mail-outline',
      title: 'Email Templates',
      subtitle: 'Create and manage email templates',
      onPress: () => router.push('/settings/email-templates'),
      color: '#34C759',
    },
    {
      id: 'brand-kit',
      icon: 'color-palette',
      title: 'Brand Kit',
      subtitle: 'Customize email branding & colors',
      onPress: () => router.push('/settings/brand-kit'),
      color: '#AF52DE',
    },
    {
      id: 'email-analytics',
      icon: 'bar-chart',
      title: 'Email Analytics',
      subtitle: 'Track opens, clicks & engagement',
      onPress: () => router.push('/settings/email-analytics'),
      color: '#FF2D55',
    },
    {
      id: 'invite-team',
      icon: 'people-outline',
      title: 'Invite Team',
      subtitle: 'Send invites via email or SMS',
      onPress: () => router.push('/settings/invite-team'),
      color: '#34C759',
    },
    {
      id: 'tags',
      icon: 'pricetags',
      title: 'Contact Tags',
      subtitle: 'Organize contacts with tags',
      onPress: () => router.push('/settings/tags'),
      color: '#FF9500',
    },
    {
      id: 'calendar',
      icon: 'calendar-outline',
      title: 'Calendar',
      subtitle: 'Connect Google & device calendars',
      onPress: () => router.push('/settings/calendar'),
      color: '#007AFF',
    },
    {
      icon: 'star-outline',
      title: 'Review Links',
      subtitle: 'Google, Facebook, Yelp review links',
      onPress: () => router.push('/settings/review-links'),
      color: '#FFD60A',
    },
    {
      icon: 'chatbubbles-outline',
      title: 'Review Approvals',
      subtitle: 'Approve customer reviews for your landing page',
      onPress: () => router.push('/settings/review-approvals'),
      color: '#AF52DE',
    },
    {
      icon: 'gift-outline',
      title: 'Congrats Card Style',
      subtitle: 'Customize your thank you cards',
      onPress: () => router.push('/settings/congrats-template'),
      color: '#C9A962',
    },
    {
      icon: 'git-network',
      title: 'Integrations',
      subtitle: 'API keys, webhooks, CRM & DMS',
      onPress: () => router.push('/settings/integrations'),
      color: '#5856D6',
    },
    {
      icon: 'settings',
      title: 'Settings',
      subtitle: 'App preferences and account',
      onPress: () => showSimpleAlert('Settings', 'Feature coming soon'),
      color: '#8E8E93',
    },
  ];
  
  // Check if user is an independent (no organization)
  const isIndependent = !user?.organization_id;
  
  // Add independent menu item for users without an organization
  const independentMenuItems = isIndependent ? [
    {
      icon: 'trophy',
      title: 'My Rankings',
      subtitle: 'Compare with other pros in your area',
      onPress: () => router.push('/admin/my-rankings'),
      color: '#FFD60A',
    },
  ] : [];
  
  // Add admin menu items for users with admin access
  const adminMenuItems = isAdmin ? [
    {
      icon: 'shield-checkmark',
      title: 'Admin Panel',
      subtitle: 'Manage organizations, accounts, and users',
      onPress: () => router.push('/admin'),
      color: '#34C759',
    },
  ] : [];
  
  // Super admin only menu items
  const superAdminMenuItems = user?.role === 'super_admin' ? [
    {
      icon: 'person-add',
      title: 'Pending Users',
      subtitle: 'Review and approve new signups',
      onPress: () => router.push('/admin/pending-users'),
      color: '#FF3B30',
      badge: pendingUsersCount,
    },
    {
      icon: 'document-text',
      title: 'Partner Agreements',
      subtitle: 'Manage reseller & referral contracts',
      onPress: () => router.push('/admin/partner-agreements'),
      color: '#FF9500',
    },
    {
      icon: 'people',
      title: 'Company Directory',
      subtitle: 'Team members, performance & leaderboards',
      onPress: () => router.push('/admin/directory'),
      color: '#AF52DE',
    },
    {
      icon: 'mail',
      title: 'Shared Inboxes',
      subtitle: 'Assign multiple users to phone numbers',
      onPress: () => router.push('/admin/shared-inboxes'),
      color: '#007AFF',
    },
    {
      icon: 'swap-horizontal',
      title: 'Bulk Transfer',
      subtitle: 'Transfer contacts between users',
      onPress: () => router.push('/admin/bulk-transfer'),
      color: '#FF3B30',
    },
    {
      icon: 'call',
      title: 'Phone Assignments',
      subtitle: 'Assign Twilio numbers to users',
      onPress: () => router.push('/admin/phone-assignments'),
      color: '#32ADE6',
    },
    {
      icon: 'documents',
      title: 'View Quotes',
      subtitle: 'View & manage subscription quotes',
      onPress: () => router.push('/admin/quotes'),
      color: '#30B0C7',
    },
    {
      icon: 'receipt',
      title: 'Create Quote',
      subtitle: 'Generate subscription quotes',
      onPress: () => router.push('/admin/create-quote'),
      color: '#34C759',
    },
    {
      icon: 'ticket',
      title: 'Discount Codes',
      subtitle: 'Generate & manage discount codes',
      onPress: () => router.push('/admin/discount-codes'),
      color: '#5856D6',
    },
  ] : [];
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>More</Text>
        </View>
        
        {/* Impersonation Banner */}
        {isImpersonating && (
          <TouchableOpacity 
            style={styles.impersonationBanner}
            onPress={handleExitImpersonation}
            disabled={exitingImpersonation}
          >
            <View style={styles.impersonationContent}>
              <Ionicons name="person-circle" size={24} color="#FFF" />
              <View style={styles.impersonationTextContainer}>
                <Text style={styles.impersonationTitle}>Impersonating {user?.name}</Text>
                <Text style={styles.impersonationSubtitle}>Tap to return to {originalUser?.name}</Text>
              </View>
            </View>
            <Ionicons name="close-circle" size={28} color="#FFF" />
          </TouchableOpacity>
        )}
        
        <TouchableOpacity 
          style={styles.profileCard}
          onPress={() => router.push('/my-account')}
          activeOpacity={0.7}
          data-testid="profile-card"
        >
          <View style={styles.profileAvatarContainer}>
            {user?.photo_url ? (
              <Image source={{ uri: user.photo_url }} style={styles.profileAvatarImage} />
            ) : (
              <View style={styles.profileAvatar}>
                <Text style={styles.profileAvatarText}>
                  {user?.name
                    ?.split(' ')
                    .map((n) => n[0])
                    .join('')
                    .toUpperCase() || '?'}
                </Text>
              </View>
            )}
            <View style={styles.editBadge}>
              <Ionicons name="pencil" size={10} color="#FFF" />
            </View>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{user?.name || 'Guest'}</Text>
            <Text style={styles.profileEmail}>{user?.email || ''}</Text>
            <View style={styles.profileNumberContainer}>
              <Image 
                source={require('../../assets/images/imos-logo-white-v3.png')}
                style={styles.profileLogoSmall}
                resizeMode="contain"
              />
              <Text style={styles.profileNumber}>{user?.mvpline_number || '+1555XXXXXXX'}</Text>
            </View>
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
          <View style={styles.profileChevron}>
            <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
          </View>
        </TouchableOpacity>
        
        {/* Admin Section */}
        {adminMenuItems.length > 0 && (
          <View style={styles.menuSection}>
            <Text style={styles.sectionTitle}>Administration</Text>
            {adminMenuItems.map((item, index) => (
              <TouchableOpacity
                key={`admin-${index}`}
                style={styles.menuItem}
                onPress={item.onPress}
              >
                <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={24} color={item.color} />
                </View>
                <View style={styles.menuContent}>
                  <Text style={styles.menuTitle}>{item.title}</Text>
                  <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
            ))}
            {superAdminMenuItems.map((item, index) => (
              <TouchableOpacity
                key={`super-${index}`}
                style={styles.menuItem}
                onPress={item.onPress}
              >
                <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={24} color={item.color} />
                  {item.badge > 0 && (
                    <View style={styles.badgeDot}>
                      <Text style={styles.badgeText}>{item.badge > 9 ? '9+' : item.badge}</Text>
                    </View>
                  )}
                </View>
                <View style={styles.menuContent}>
                  <Text style={styles.menuTitle}>{item.title}</Text>
                  <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
                </View>
                {item.badge > 0 && (
                  <View style={styles.notificationBadge}>
                    <Text style={styles.notificationBadgeText}>{item.badge}</Text>
                  </View>
                )}
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
            ))}
          </View>
        )}
        
        {/* Independent Section */}
        {independentMenuItems.length > 0 && (
          <View style={styles.menuSection}>
            <Text style={styles.sectionTitle}>Performance</Text>
            {independentMenuItems.map((item, index) => (
              <TouchableOpacity
                key={`sole-${index}`}
                style={styles.menuItem}
                onPress={item.onPress}
              >
                <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={24} color={item.color} />
                </View>
                <View style={styles.menuContent}>
                  <Text style={styles.menuTitle}>{item.title}</Text>
                  <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
            ))}
          </View>
        )}
        
        <View style={styles.menuSection}>
          <Text style={styles.sectionTitle}>Features</Text>
          {menuItems.map((item, index) => (
            <TouchableOpacity
              key={index}
              style={styles.menuItem}
              onPress={item.onPress}
            >
              <View style={styles.menuIcon}>
                <Ionicons name={item.icon as any} size={24} color={item.color || '#007AFF'} />
              </View>
              <View style={styles.menuContent}>
                <Text style={styles.menuTitle}>{item.title}</Text>
                <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
            </TouchableOpacity>
          ))}
        </View>
        
        {/* Legal Section */}
        <View style={styles.menuSection}>
          <Text style={styles.sectionTitle}>Legal</Text>
          <TouchableOpacity
            style={styles.menuItem}
            onPress={() => router.push('/terms')}
            data-testid="terms-of-service-link"
          >
            <View style={styles.menuIcon}>
              <Ionicons name="document-text" size={24} color="#8E8E93" />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Terms of Service</Text>
              <Text style={styles.menuSubtitle}>Usage terms and conditions</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.menuItem, { borderBottomWidth: 0 }]}
            onPress={() => router.push('/privacy')}
            data-testid="privacy-policy-link"
          >
            <View style={styles.menuIcon}>
              <Ionicons name="shield-checkmark" size={24} color="#8E8E93" />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Privacy Policy</Text>
              <Text style={styles.menuSubtitle}>How we protect your data</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
          </TouchableOpacity>
        </View>
        
        {/* Sign Out Button */}
        <TouchableOpacity
          style={styles.logoutButton}
          onPress={handleLogout}
          data-testid="logout-button"
        >
          <Ionicons name="log-out-outline" size={22} color="#FF3B30" />
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>
        
        <View style={styles.versionContainer}>
          <Image 
            source={require('../../assets/images/imos-logo-white-v3.png')}
            style={styles.versionLogo}
            resizeMode="contain"
          />
          <Text style={styles.version}>v1.0.0</Text>
        </View>
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
    paddingBottom: 32,
  },
  header: {
    padding: 16,
  },
  title: {
    fontSize: 34,
    fontWeight: 'bold',
    color: '#FFF',
  },
  impersonationBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#5856D6',
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 14,
    borderRadius: 12,
  },
  impersonationContent: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  impersonationTextContainer: {
    marginLeft: 12,
    flex: 1,
  },
  impersonationTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  impersonationSubtitle: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  profileCard: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    marginHorizontal: 16,
    marginBottom: 24,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  profileAvatarContainer: {
    position: 'relative',
    marginRight: 16,
  },
  profileAvatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileAvatarImage: {
    width: 64,
    height: 64,
    borderRadius: 32,
  },
  profileAvatarText: {
    color: '#FFF',
    fontSize: 24,
    fontWeight: '600',
  },
  editBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#1C1C1E',
  },
  profileInfo: {
    flex: 1,
  },
  profileChevron: {
    marginLeft: 8,
  },
  profileSignOutButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FF3B3015',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },
  profileName: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  profileEmail: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 2,
  },
  profileNumberContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  profileLogoSmall: {
    width: 32,
    height: 12,
  },
  profileNumber: {
    fontSize: 12,
    color: '#007AFF',
    fontWeight: '600',
  },
  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 6,
    backgroundColor: '#34C75920',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  roleText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#34C759',
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  menuSection: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  menuIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  menuSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    gap: 8,
    cursor: 'pointer',
  },
  logoutButtonPressed: {
    opacity: 0.7,
    backgroundColor: '#2C2C2E',
  },
  logoutText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FF3B30',
  },
  versionContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
    gap: 6,
  },
  versionLogo: {
    width: 40,
    height: 16,
  },
  version: {
    fontSize: 12,
    color: '#8E8E93',
  },
  badgeDot: {
    position: 'absolute',
    top: -2,
    right: -2,
    backgroundColor: '#FF3B30',
    width: 18,
    height: 18,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#1C1C1E',
  },
  badgeText: {
    color: '#FFF',
    fontSize: 10,
    fontWeight: '700',
  },
  notificationBadge: {
    backgroundColor: '#FF3B30',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
    marginRight: 8,
    minWidth: 24,
    alignItems: 'center',
  },
  notificationBadgeText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '700',
  },
});