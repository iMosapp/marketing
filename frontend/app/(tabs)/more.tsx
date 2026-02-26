import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
  Image,
  Animated,
  LayoutAnimation,
  UIManager,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert } from '../../services/alert';
import api from '../../services/api';
import { NotificationBell } from '../../components/notifications/NotificationBell';

// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

type MenuItem = {
  icon: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  color: string;
  badge?: number;
};

type Section = {
  id: string;
  title: string;
  icon: string;
  color: string;
  items: MenuItem[];
  defaultExpanded?: boolean;
};

export default function MoreScreen() {
  const router = useRouter();
  const { user, logout, isImpersonating, stopImpersonation, originalUser } = useAuthStore();
  const [pendingUsersCount, setPendingUsersCount] = useState(0);
  const [exitingImpersonation, setExitingImpersonation] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  
  // Load pending count for super admins
  useFocusEffect(
    useCallback(() => {
      if (user?.role === 'super_admin' || originalUser?.role === 'super_admin') {
        fetchPendingCount();
      }
    }, [user?.role, originalUser?.role])
  );
  
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
  
  const toggleSection = (sectionId: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sectionId)) {
        newSet.delete(sectionId);
      } else {
        newSet.add(sectionId);
      }
      return newSet;
    });
  };
  
  // Check user roles
  const isAdmin = user?.role === 'super_admin' || user?.role === 'org_admin' || user?.role === 'store_manager';
  const isSuperAdmin = user?.role === 'super_admin';
  const isIndependent = !user?.organization_id;

  // Define all sections with their items
  const sections: Section[] = [
    // Essentials - Always show, expanded by default
    {
      id: 'essentials',
      title: 'Essentials',
      icon: 'star',
      color: '#FFD60A',
      defaultExpanded: true,
      items: [
        {
          icon: 'school',
          title: 'Training Hub',
          subtitle: 'Learn how to use iMos',
          onPress: () => router.push('/training-hub'),
          color: '#FF9500',
        },
        {
          icon: 'sparkles',
          title: 'Ask Jessi',
          subtitle: 'Your AI assistant',
          onPress: () => router.push('/jessie'),
          color: '#C9A962',
        },
        {
          icon: 'checkmark-done',
          title: 'Tasks & Reminders',
          subtitle: 'Manage follow-ups',
          onPress: () => router.push('/tasks'),
          color: '#34C759',
        },
      ],
    },
    // Communication Tools
    {
      id: 'communication',
      title: 'Communication',
      icon: 'chatbubbles',
      color: '#007AFF',
      items: [
        {
          icon: 'call',
          title: 'Phone',
          subtitle: 'Dialer & call log',
          onPress: () => router.push('/(tabs)/dialer'),
          color: '#32ADE6',
        },
        {
          icon: 'megaphone',
          title: 'Broadcast',
          subtitle: 'Mass messaging',
          onPress: () => router.push('/broadcast'),
          color: '#FF9500',
        },
        {
          icon: 'chatbubbles',
          title: 'SMS Campaigns',
          subtitle: 'Automated SMS follow-ups',
          onPress: () => router.push('/campaigns'),
          color: '#FF2D55',
        },
        {
          icon: 'mail',
          title: 'Email Campaigns',
          subtitle: 'Automated email follow-ups',
          onPress: () => router.push('/campaigns/email'),
          color: '#AF52DE',
        },
        {
          icon: 'speedometer',
          title: 'Campaign Dashboard',
          subtitle: 'View enrollments',
          onPress: () => router.push('/campaigns/dashboard'),
          color: '#5AC8FA',
        },
        {
          icon: 'calendar-outline',
          title: 'Date Triggers',
          subtitle: 'Birthdays, anniversaries, holidays',
          onPress: () => router.push('/settings/date-triggers'),
          color: '#FF9500',
        },
      ],
    },
    // Templates & Branding
    {
      id: 'templates',
      title: 'Templates & Branding',
      icon: 'color-palette',
      color: '#AF52DE',
      items: [
        {
          icon: 'document-text',
          title: 'SMS Templates',
          subtitle: 'Create SMS templates',
          onPress: () => router.push('/settings/templates'),
          color: '#FFD60A',
        },
        {
          icon: 'mail-outline',
          title: 'Email Templates',
          subtitle: 'Create email templates',
          onPress: () => router.push('/settings/email-templates'),
          color: '#34C759',
        },
        {
          icon: 'color-palette',
          title: 'Brand Kit',
          subtitle: 'Email branding & colors',
          onPress: () => router.push('/settings/brand-kit'),
          color: '#AF52DE',
        },
        {
          icon: 'gift-outline',
          title: 'Congrats Cards',
          subtitle: 'Thank you card style',
          onPress: () => router.push('/settings/congrats-template'),
          color: '#C9A962',
        },
      ],
    },
    // Performance & Analytics
    {
      id: 'performance',
      title: 'Performance',
      icon: 'stats-chart',
      color: '#34C759',
      items: [
        {
          icon: 'stats-chart',
          title: 'Analytics',
          subtitle: 'Performance metrics',
          onPress: () => router.push('/analytics'),
          color: '#34C759',
        },
        {
          icon: 'bar-chart',
          title: 'Reports',
          subtitle: 'Detailed reports',
          onPress: () => router.push('/reports'),
          color: '#007AFF',
        },
        {
          icon: 'bar-chart',
          title: 'Email Analytics',
          subtitle: 'Opens, clicks, engagement',
          onPress: () => router.push('/settings/email-analytics'),
          color: '#FF2D55',
        },
        ...(isIndependent ? [{
          icon: 'trophy',
          title: 'My Rankings',
          subtitle: 'Compare with other pros',
          onPress: () => router.push('/admin/my-rankings'),
          color: '#FFD60A',
        }] : []),
      ],
    },
    // Contacts & Leads
    {
      id: 'contacts',
      title: 'Contacts & Leads',
      icon: 'people',
      color: '#5856D6',
      items: [
        {
          icon: 'git-branch',
          title: 'Lead Sources',
          subtitle: 'Inbound leads & routing',
          onPress: () => router.push('/admin/lead-sources'),
          color: '#5856D6',
        },
        {
          icon: 'pricetags',
          title: 'Contact Tags',
          subtitle: 'Organize with tags',
          onPress: () => router.push('/settings/tags'),
          color: '#FF9500',
        },
        {
          icon: 'star-outline',
          title: 'Review Links',
          subtitle: 'Google, Facebook, Yelp',
          onPress: () => router.push('/settings/review-links'),
          color: '#FFD60A',
        },
        {
          icon: 'chatbubbles-outline',
          title: 'Review Approvals',
          subtitle: 'Approve customer reviews',
          onPress: () => router.push('/settings/review-approvals'),
          color: '#AF52DE',
        },
      ],
    },
    // Profile & AI
    {
      id: 'profile',
      title: 'Profile & AI',
      icon: 'person',
      color: '#FF9500',
      items: [
        {
          icon: 'card',
          title: 'My Digital Card',
          subtitle: 'Bio, socials & preview',
          onPress: () => router.push('/settings/my-profile'),
          color: '#007AFF',
        },
        {
          icon: 'person',
          title: 'AI Persona',
          subtitle: 'Communication style',
          onPress: () => router.push('/settings/persona'),
          color: '#AF52DE',
        },
        {
          icon: 'sparkles',
          title: 'Train Jessi AI',
          subtitle: 'Chat with your AI assistant',
          onPress: () => router.push('/jessie'),
          color: '#C9A962',
        },
      ],
    },
    // Settings & Security
    {
      id: 'settings',
      title: 'Settings',
      icon: 'settings',
      color: '#8E8E93',
      items: [
        {
          icon: 'shield-checkmark',
          title: 'Security',
          subtitle: 'Face ID, passwords',
          onPress: () => router.push('/settings/security'),
          color: '#FF3B30',
        },
        {
          icon: 'notifications',
          title: 'Notifications',
          subtitle: 'Alerts & escalations',
          onPress: () => showSimpleAlert('Notifications', 'Feature coming soon'),
          color: '#FF9500',
        },
        {
          icon: 'swap-horizontal-outline',
          title: 'SMS / Email Toggle',
          subtitle: 'Toggle style & default',
          onPress: () => router.push('/settings/toggle-style'),
          color: '#5AC8FA',
        },
        {
          icon: 'calendar-outline',
          title: 'Calendar',
          subtitle: 'Connect calendars',
          onPress: () => router.push('/settings/calendar'),
          color: '#007AFF',
        },
        {
          icon: 'git-network',
          title: 'Integrations',
          subtitle: 'API keys & webhooks',
          onPress: () => router.push('/settings/integrations'),
          color: '#5856D6',
        },
      ],
    },
  ];

  // Admin section - only for admins
  const adminSection: Section | null = isAdmin ? {
    id: 'admin',
    title: 'Administration',
    icon: 'shield-checkmark',
    color: '#FF3B30',
    items: [
      {
        icon: 'shield-checkmark',
        title: 'Admin Dashboard',
        subtitle: 'Overview & activity',
        onPress: () => router.push('/admin'),
        color: '#34C759',
      },
      {
        icon: 'map-outline',
        title: 'App Directory',
        subtitle: 'Browse & share pages',
        onPress: () => router.push('/admin/app-directory'),
        color: '#5AC8FA',
      },
      {
        icon: 'person-add',
        title: 'Invite Team',
        subtitle: 'Send invitations',
        onPress: () => router.push('/settings/invite-team'),
        color: '#C9A962',
      },
      // Organizations - super_admin only
      ...(isSuperAdmin ? [{
        icon: 'business',
        title: 'Organizations',
        subtitle: 'Manage organizations',
        onPress: () => router.push('/admin/organizations'),
        color: '#007AFF',
      }] : []),
      // Accounts (Stores) - org_admin and above
      ...(isSuperAdmin || user?.role === 'org_admin' ? [{
        icon: 'storefront',
        title: 'Accounts',
        subtitle: 'Manage store accounts',
        onPress: () => router.push('/admin/stores'),
        color: '#34C759',
      }] : []),
      // Users - org_admin and above
      ...(isSuperAdmin || user?.role === 'org_admin' || user?.role === 'store_manager' ? [{
        icon: 'people',
        title: 'Users',
        subtitle: 'Manage team members',
        onPress: () => router.push('/admin/users'),
        color: '#FF9500',
      }] : []),
      ...(isSuperAdmin ? [
        {
          icon: 'person',
          title: 'Individuals',
          subtitle: 'Independent users',
          onPress: () => router.push('/admin/individuals'),
          color: '#AF52DE',
        },
        {
          icon: 'person-add',
          title: 'Pending Users',
          subtitle: 'Approve new signups',
          onPress: () => router.push('/admin/pending-users'),
          color: '#FF3B30',
          badge: pendingUsersCount,
        },
        {
          icon: 'document-text',
          title: 'Partner Agreements',
          subtitle: 'Reseller contracts',
          onPress: () => router.push('/admin/partner-agreements'),
          color: '#FF9500',
        },
        {
          icon: 'people',
          title: 'Company Directory',
          subtitle: 'Team & leaderboards',
          onPress: () => router.push('/admin/directory'),
          color: '#AF52DE',
        },
        {
          icon: 'mail',
          title: 'Shared Inboxes',
          subtitle: 'Phone number users',
          onPress: () => router.push('/admin/shared-inboxes'),
          color: '#007AFF',
        },
        {
          icon: 'swap-horizontal',
          title: 'Bulk Transfer',
          subtitle: 'Transfer contacts',
          onPress: () => router.push('/admin/bulk-transfer'),
          color: '#FF3B30',
        },
        {
          icon: 'call',
          title: 'Phone Assignments',
          subtitle: 'Twilio numbers',
          onPress: () => router.push('/admin/phone-assignments'),
          color: '#32ADE6',
        },
        {
          icon: 'documents',
          title: 'View Quotes',
          subtitle: 'Subscription quotes',
          onPress: () => router.push('/admin/quotes'),
          color: '#30B0C7',
        },
        {
          icon: 'receipt',
          title: 'Create Quote',
          subtitle: 'Generate quotes',
          onPress: () => router.push('/admin/create-quote'),
          color: '#34C759',
        },
        {
          icon: 'ticket',
          title: 'Discount Codes',
          subtitle: 'Manage discounts',
          onPress: () => router.push('/admin/discount-codes'),
          color: '#5856D6',
        },
      ] : []),
    ],
  } : null;

  // Combine all sections
  const allSections = adminSection ? [adminSection, ...sections] : sections;

  const renderMenuItem = (item: MenuItem, index: number) => (
    <TouchableOpacity
      key={`${item.title}-${index}`}
      style={styles.menuItemCard}
      onPress={item.onPress}
      activeOpacity={0.7}
      data-testid={`menu-item-${item.title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
        <Ionicons name={item.icon as any} size={20} color={item.color} />
      </View>
      <View style={styles.menuContent}>
        <Text style={styles.menuTitle}>{item.title}</Text>
        <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
      </View>
      {item.badge && item.badge > 0 && (
        <View style={styles.notificationBadge}>
          <Text style={styles.notificationBadgeText}>{item.badge}</Text>
        </View>
      )}
      <Ionicons name="chevron-forward" size={18} color="#8E8E93" />
    </TouchableOpacity>
  );

  const renderSection = (section: Section) => {
    const isExpanded = expandedSections.has(section.id);
    const itemCount = section.items.length;

    return (
      <View key={section.id} style={styles.sectionWrapper} data-testid={`section-${section.id}`}>
        {/* Section Header Card */}
        <TouchableOpacity
          style={styles.sectionHeaderCard}
          onPress={() => toggleSection(section.id)}
          activeOpacity={0.7}
          data-testid={`section-header-${section.id}`}
        >
          <View style={[styles.sectionIcon, { backgroundColor: `${section.color}20` }]}>
            <Ionicons name={section.icon as any} size={20} color={section.color} />
          </View>
          <Text style={styles.sectionTitleText}>{section.title}</Text>
          <Ionicons 
            name={isExpanded ? 'chevron-up' : 'chevron-down'} 
            size={20} 
            color="#8E8E93" 
          />
        </TouchableOpacity>
        
        {/* Indented Child Item Cards */}
        {isExpanded && section.items.map((item, index) => 
          renderMenuItem(item, index)
        )}
      </View>
    );
  };
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Impersonation Banner */}
        {isImpersonating && (
          <TouchableOpacity 
            style={styles.impersonationBanner}
            onPress={handleExitImpersonation}
            disabled={exitingImpersonation}
            data-testid="impersonation-banner"
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
        
        {/* Profile Card - Digital Card Style */}
        <View style={styles.profileCardContainer}>
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
            </View>
            <View style={styles.profileInfo}>
              <Text style={styles.profileName}>{user?.name || 'Guest'}</Text>
              {user?.title ? (
                <Text style={styles.profileTitle}>{user.title}</Text>
              ) : null}
              <Text style={styles.profileEmail}>{user?.email || ''}</Text>
              {user?.phone && (
                <Text style={styles.profilePhone}>{user.phone}</Text>
              )}
            </View>
            <Ionicons name="chevron-forward" size={18} color="#555" />
          </TouchableOpacity>
          
          {/* Stacked Bell + Logout */}
          <View style={styles.profileActions}>
            <NotificationBell />
            <TouchableOpacity
              style={styles.profileSignOutBtn}
              onPress={handleLogout}
              data-testid="logout-button"
            >
              <Ionicons name="log-out-outline" size={18} color="#FF3B30" />
            </TouchableOpacity>
          </View>
        </View>
        
        {/* All Collapsible Sections */}
        {allSections.map(section => renderSection(section))}
        
        {/* Legal Section - Always visible, not collapsible */}
        <View style={styles.legalSection}>
          <TouchableOpacity
            style={styles.legalItem}
            onPress={() => router.push('/terms')}
            data-testid="terms-of-service-link"
          >
            <Ionicons name="document-text" size={18} color="#6E6E73" />
            <Text style={styles.legalText}>Terms of Service</Text>
          </TouchableOpacity>
          <Text style={styles.legalDivider}>•</Text>
          <TouchableOpacity
            style={styles.legalItem}
            onPress={() => router.push('/privacy')}
            data-testid="privacy-policy-link"
          >
            <Ionicons name="shield-checkmark" size={18} color="#6E6E73" />
            <Text style={styles.legalText}>Privacy Policy</Text>
          </TouchableOpacity>
        </View>
        
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
  bellContainer: {
    position: 'absolute',
    top: Platform.OS === 'web' ? 12 : 8,
    right: 16,
    zIndex: 9999,
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
  profileCardContainer: {
    flexDirection: 'row',
    alignItems: 'stretch',
    marginHorizontal: 16,
    marginBottom: 16,
    gap: 8,
  },
  profileCard: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: '#1A1A1A',
    padding: 16,
    borderRadius: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  profileActions: {
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  profileSignOutBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileAvatarContainer: {
    position: 'relative',
    marginRight: 14,
  },
  profileAvatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileAvatarImage: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: 2,
    borderColor: '#C9A962',
  },
  profileAvatarText: {
    color: '#FFF',
    fontSize: 20,
    fontWeight: '600',
  },
  // Section Wrapper
    flex: 1,
  },
  profileName: {
    fontSize: 17,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 2,
    letterSpacing: 0.2,
  },
  profileTitle: {
    fontSize: 11,
    color: '#C9A962',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  profileEmail: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 1,
  },
  profilePhone: {
    fontSize: 12,
    color: '#8E8E93',
  },
  // Section Wrapper
  sectionWrapper: {
    marginHorizontal: 16,
    marginBottom: 8,
  },
  // Section Header Card (standalone card)
  sectionHeaderCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  sectionIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  sectionTitleText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    flex: 1,
  },
  countBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 8,
  },
  countText: {
    fontSize: 14,
    fontWeight: '600',
  },
  // Indented child item card
  menuItemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 12,
    marginBottom: 6,
    marginLeft: 16,
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
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 1,
  },
  menuSubtitle: {
    fontSize: 12,
    color: '#8E8E93',
  },
  notificationBadge: {
    backgroundColor: '#FF3B30',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginRight: 8,
    minWidth: 22,
    alignItems: 'center',
  },
  notificationBadgeText: {
    color: '#FFF',
    fontSize: 11,
    fontWeight: '700',
  },
  // Legal Section
  legalSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 8,
    gap: 12,
  },
  legalItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legalText: {
    fontSize: 13,
    color: '#6E6E73',
  },
  legalDivider: {
    fontSize: 13,
    color: '#3A3A3C',
  },
  versionContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    marginBottom: 8,
    gap: 6,
  },
  versionLogo: {
    width: 36,
    height: 14,
  },
  version: {
    fontSize: 12,
    color: '#6E6E73',
  },
});