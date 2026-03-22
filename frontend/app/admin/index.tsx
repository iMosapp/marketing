import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  Animated,
  LayoutAnimation,
  UIManager,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const TIME_FILTERS = [
  { label: '7D', value: '7d' },
  { label: '30D', value: '30d' },
  { label: '90D', value: '90d' },
  { label: 'All', value: 'all' },
];

type MenuItem = {
  icon: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  color: string;
  badge?: number;
  value?: string | number;
};

type Section = {
  id: string;
  title: string;
  icon: string;
  color: string;
  items: MenuItem[];
  defaultExpanded?: boolean;
};

// Activity Ticker Component
const ActivityTicker = ({ activities }: { activities: any[] }) => {
  const scrollX = useRef(new Animated.Value(0)).current;
  const [tickerWidth, setTickerWidth] = useState(0);
  
  useEffect(() => {
    if (activities.length === 0 || tickerWidth === 0) return;
    
    const contentWidth = activities.length * 300;
    
    const animation = Animated.loop(
      Animated.timing(scrollX, {
        toValue: -contentWidth,
        duration: activities.length * 5000,
        useNativeDriver: true,
      })
    );
    
    animation.start();
    return () => animation.stop();
  }, [activities, tickerWidth]);
  
  if (activities.length === 0) {
    return (
      <View style={tickerStyles.container}>
        <View style={tickerStyles.emptyTicker}>
          <Ionicons name="pulse" size={14} color="#8E8E93" />
          <Text style={tickerStyles.emptyText}>Activity will appear here</Text>
        </View>
      </View>
    );
  }
  
  const formatTime = (timestamp: string) => {
    if (!timestamp) return '';
    const now = new Date();
    const time = new Date(timestamp);
    const diff = Math.floor((now.getTime() - time.getTime()) / 1000);
    
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };
  
  return (
    <View 
      style={tickerStyles.container}
      onLayout={(e) => setTickerWidth(e.nativeEvent.layout.width)}
    >
      <Animated.View 
        style={[
          tickerStyles.tickerContent,
          { transform: [{ translateX: scrollX }] }
        ]}
      >
        {[...activities, ...activities].map((activity, index) => (
          <View key={index} style={tickerStyles.tickerItem}>
            <Ionicons 
              name={activity.icon as any} 
              size={14} 
              color={activity.color || '#007AFF'} 
            />
            <Text style={tickerStyles.tickerText} numberOfLines={1}>
              {activity.text}
            </Text>
            <Text style={tickerStyles.tickerTime}>
              {formatTime(activity.timestamp)}
            </Text>
          </View>
        ))}
      </Animated.View>
    </View>
  );
};

const tickerStyles = StyleSheet.create({
  container: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    marginBottom: 16,
    overflow: 'hidden',
    height: 36,
  },
  tickerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 36,
  },
  tickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    gap: 8,
    minWidth: 280,
  },
  tickerText: {
    color: '#FFFFFF',
    fontSize: 15,
    flex: 1,
  },
  tickerTime: {
    color: '#8E8E93',
    fontSize: 13,
  },
  emptyTicker: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 36,
    gap: 8,
  },
  emptyText: {
    color: '#8E8E93',
    fontSize: 15,
  },
});

export default function AdminDashboard() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [dataStats, setDataStats] = useState<any>(null);
  const [timeRange, setTimeRange] = useState('all');
  const [activities, setActivities] = useState<any[]>([]);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['customers', 'data']));
  const [migrating, setMigrating] = useState(false);
  const [migrateResult, setMigrateResult] = useState<string | null>(null);
  
  // Role checks
  const isSuperAdmin = user?.role === 'super_admin';
  const isOrgAdmin = user?.role === 'org_admin';
  const isStoreManager = user?.role === 'store_manager';
  const isRegularUser = user?.role === 'user' || !user?.role;
  
  // Data scope
  const organizationId = (isSuperAdmin || isOrgAdmin || isStoreManager) ? user?.organization_id : null;
  const storeId = isStoreManager ? user?.store_id : null;
  
  useFocusEffect(
    useCallback(() => {
      loadAllStats();
      loadActivities();
    }, [user, timeRange])
  );
  
  useEffect(() => {
    const interval = setInterval(() => {
      loadActivities();
    }, 30000);
    return () => clearInterval(interval);
  }, [organizationId]);
  
  const loadActivities = async () => {
    try {
      let params = '?limit=15';
      if (organizationId) {
        params += `&organization_id=${organizationId}`;
      }
      const res = await api.get(`/admin/activity/recent${params}`);
      setActivities(res.data);
    } catch (error) {
      console.error('Failed to load activities:', error);
    }
  };
  
  const loadAllStats = async () => {
    try {
      setLoading(true);
      
      let dataParams = `time_range=${timeRange}`;
      if (organizationId) {
        dataParams += `&organization_id=${organizationId}`;
      }
      
      const [detailedRes, dataRes] = await Promise.all([
        api.get('/admin/stats/detailed'),
        api.get(`/admin/stats/data?${dataParams}`),
      ]);
      setStats(detailedRes.data);
      setDataStats(dataRes.data);
    } catch (error) {
      console.error('Failed to load admin stats:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadAllStats();
    setRefreshing(false);
  };
  
  const handleMigrateImages = async () => {
    setMigrating(true);
    setMigrateResult('Starting...');
    let totalProcessed = 0;
    let lastRemaining = 999;
    
    for (let i = 0; i < 100; i++) {
      try {
        const res = await api.post('/images/migrate-now', { user_id: user?._id });
        const d = res.data;
        if (d.status === 'error') {
          setMigrateResult(`Error: ${d.detail}`);
          break;
        }
        totalProcessed += (d.processed || 0);
        const remaining = d.remaining || 0;
        if (d.processed === 0 || remaining === 0) {
          setMigrateResult(`Done! ${totalProcessed} images migrated.`);
          break;
        }
        lastRemaining = remaining;
        setMigrateResult(`${totalProcessed} done, ${remaining} left...`);
      } catch (e: any) {
        setMigrateResult(`Paused at ${totalProcessed}. Tap again to continue.`);
        break;
      }
    }
    setMigrating(false);
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
  
  const handleBack = () => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/(tabs)');
    }
  };

  // Build sections based on user role
  const buildSections = (): Section[] => {
    const sections: Section[] = [];
    
    // CUSTOMERS Section - Super Admin & Org Admin see full hierarchy
    if (isSuperAdmin || isOrgAdmin) {
      const customerItems: MenuItem[] = [];
      
      if (isSuperAdmin) {
        customerItems.push({
          icon: 'business',
          title: 'Organizations',
          subtitle: `${stats?.orgs_active || 0} active, ${stats?.orgs_inactive || 0} inactive`,
          onPress: () => router.push('/admin/organizations'),
          color: '#007AFF',
        });
      }
      
      customerItems.push({
        icon: 'storefront',
        title: 'Accounts',
        subtitle: `${stats?.stores_active || 0} active, ${stats?.stores_inactive || 0} inactive`,
        onPress: () => router.push('/admin/stores'),
        color: '#34C759',
      });
      
      customerItems.push({
        icon: 'people',
        title: 'Users',
        subtitle: `${stats?.users_active || 0} active, ${stats?.users_inactive || 0} inactive`,
        onPress: () => router.push('/admin/users'),
        color: '#FF9500',
      });
      
      if (isSuperAdmin) {
        customerItems.push({
          icon: 'person',
          title: 'Individuals',
          subtitle: `${stats?.individuals_active || 0} active, ${stats?.individuals_inactive || 0} inactive`,
          onPress: () => router.push('/admin/individuals'),
          color: '#AF52DE',
        });
        customerItems.push({
          icon: 'rocket',
          title: 'Onboarding Hub',
          subtitle: 'Create accounts, add teams, onboard partners',
          onPress: () => router.push('/admin/onboarding-hub' as any),
          color: '#FF2D55',
        });
        customerItems.push({
          icon: 'pulse',
          title: 'Account Health',
          subtitle: 'Retention dashboard & engagement tracking',
          onPress: () => router.push('/admin/account-health' as any),
          color: '#00C7BE',
        });
      }
      
      sections.push({
        id: 'customers',
        title: 'Customer Infrastructure',
        icon: 'business',
        color: '#007AFF',
        defaultExpanded: true,
        items: customerItems,
      });
    }
    
    // MY STORES Section - Store Managers see their stores and team
    if (isStoreManager) {
      sections.push({
        id: 'mystores',
        title: 'My Stores & Team',
        icon: 'storefront',
        color: '#34C759',
        defaultExpanded: true,
        items: [
          {
            icon: 'storefront',
            title: 'My Accounts',
            subtitle: 'Stores I manage',
            onPress: () => router.push('/admin/stores'),
            color: '#34C759',
          },
          {
            icon: 'people',
            title: 'My Team',
            subtitle: `${stats?.users_active || 0} team members`,
            onPress: () => router.push('/admin/users'),
            color: '#FF9500',
          },
          {
            icon: 'person-add',
            title: 'Manage Team',
            subtitle: 'Add, remove & manage',
            onPress: () => router.push('/admin/manage-team'),
            color: '#007AFF',
          },
        ],
      });
    }
    
    // MY ACCOUNT Section - Regular Users see only their profile
    if (isRegularUser) {
      sections.push({
        id: 'myaccount',
        title: 'My Account',
        icon: 'person',
        color: '#007AFF',
        defaultExpanded: true,
        items: [
          {
            icon: 'person-circle',
            title: 'My Profile',
            subtitle: 'View & edit your profile',
            onPress: () => router.push('/my-account'),
            color: '#007AFF',
          },
          {
            icon: 'card',
            title: 'My Digital Card',
            subtitle: 'View & share your card',
            onPress: () => router.push(`/card/${user?._id}`),
            color: '#5856D6',
          },
          {
            icon: 'stats-chart',
            title: 'My Performance',
            subtitle: 'Your metrics & rankings',
            onPress: () => router.push('/my-rankings'),
            color: '#34C759',
          },
        ],
      });
    }
    
    // DATA Section - All admin roles can see (scoped)
    if (isSuperAdmin || isOrgAdmin || isStoreManager) {
      sections.push({
        id: 'data',
        title: 'Data & Analytics',
        icon: 'stats-chart',
        color: '#34C759',
        items: [
          {
            icon: 'chatbubbles',
            title: 'Messages',
            subtitle: 'SMS & email messages',
            value: dataStats?.total_messages?.toLocaleString() || '0',
            onPress: () => router.push('/admin/data/messages'),
            color: '#007AFF',
          },
          {
            icon: 'call',
            title: 'Calls',
            subtitle: 'Phone call logs',
            value: dataStats?.total_calls?.toLocaleString() || '0',
            onPress: () => router.push('/admin/data/calls'),
            color: '#34C759',
          },
          {
            icon: 'sparkles',
            title: 'AI Interactions',
            subtitle: 'Jessi AI usage',
            value: dataStats?.ai_messages?.toLocaleString() || '0',
            onPress: () => router.push('/admin/data/ai-messages'),
            color: '#AF52DE',
          },
          {
            icon: 'person',
            title: 'Contacts',
            subtitle: 'Total contacts',
            value: dataStats?.total_contacts?.toLocaleString() || '0',
            onPress: () => router.push('/admin/contacts'),
            color: '#FF9500',
          },
          {
            icon: 'card',
            title: 'Card Shares',
            subtitle: 'Digital card shares',
            value: dataStats?.card_shares?.toLocaleString() || '0',
            onPress: () => router.push('/admin/data/card-shares'),
            color: '#FF2D55',
          },
          {
            icon: 'gift',
            title: 'Congrats Cards',
            subtitle: 'Thank you cards sent',
            value: dataStats?.congrats_cards?.toLocaleString() || '0',
            onPress: () => router.push('/admin/data/congrats-cards'),
            color: '#C9A962',
          },
          {
            icon: 'rocket',
            title: 'Campaigns',
            subtitle: 'Active campaigns',
            value: dataStats?.total_campaigns?.toLocaleString() || '0',
            onPress: () => router.push('/admin/data/campaigns'),
            color: '#FF3B30',
          },
        ],
      });
    }
    
    // TOOLS Section - Available to admins
    if (isSuperAdmin || isOrgAdmin || isStoreManager) {
      const toolItems: MenuItem[] = [
        {
          icon: 'sparkles',
          title: 'AI Follow-ups',
          subtitle: 'AI-powered outreach suggestions',
          onPress: () => router.push('/(tabs)/ai-outreach' as any),
          color: '#AF52DE',
          badge: 0,  // Will be updated with pending count
        },
        {
          icon: 'settings',
          title: 'Campaign Settings',
          subtitle: 'AI vs template mode, tone, data sources',
          onPress: () => router.push('/campaign-config'),
          color: '#C9A962',
        },
        {
          icon: 'key',
          title: 'Permission Templates',
          subtitle: 'Role presets & feature access control',
          onPress: () => router.push('/permission-templates'),
          color: '#5856D6',
        },
        {
          icon: 'flame',
          title: 'Hot Leads',
          subtitle: 'Customers engaging right now',
          onPress: () => router.push('/admin/hot-leads'),
          color: '#FF3B30',
        },
        {
          icon: 'people-circle',
          title: 'Team Engagement',
          subtitle: 'Hot leads across your entire team',
          onPress: () => router.push('/admin/team-engagement'),
          color: '#C9A962',
          managerOnly: true,
        },
        {
          icon: 'trophy',
          title: 'Leaderboards',
          subtitle: isStoreManager ? 'My team rankings' : 'Performance rankings',
          onPress: () => router.push('/admin/leaderboard'),
          color: '#FFD60A',
        },
        {
          icon: 'pulse',
          title: 'Activity Feed',
          subtitle: isStoreManager ? 'My team activity' : 'Recent team activity',
          onPress: () => router.push('/(tabs)/activity-feed' as any),
          color: '#5AC8FA',
        },
        {
          icon: 'book',
          title: 'Training & SOPs',
          subtitle: 'Internal procedures & guides',
          onPress: () => router.push('/admin/sop'),
          color: '#34C759',
        },
        {
          icon: 'school',
          title: 'Manage Training Hub',
          subtitle: 'Edit LMS tracks, lessons & roles',
          onPress: () => router.push('/admin/manage-training'),
          color: '#AF52DE',
          indent: true,
        },
      ];
      
      if (isStoreManager) {
        toolItems.push({
          icon: 'document-text',
          title: 'My Agreement',
          subtitle: 'View your signed agreement',
          onPress: () => router.push('/admin/my-agreement'),
          color: '#007AFF',
        });
        toolItems.push({
          icon: 'receipt',
          title: 'My Invoices',
          subtitle: 'View invoices & payments',
          onPress: () => router.push('/admin/my-invoices'),
          color: '#34C759',
        });
      }
      
      sections.push({
        id: 'tools',
        title: 'Tools',
        icon: 'construct',
        color: '#FF9500',
        items: toolItems,
      });
    }
    
    return sections;
  };

  const renderMenuItem = (item: MenuItem, index: number, isLast: boolean) => (
    <TouchableOpacity
      key={`${item.title}-${index}`}
      style={[styles.menuItem, isLast && { borderBottomWidth: 0 }]}
      onPress={item.onPress}
      data-testid={`menu-item-${item.title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
        <Ionicons name={item.icon as any} size={22} color={item.color} />
        {item.badge && item.badge > 0 && (
          <View style={styles.badgeDot}>
            <Text style={styles.badgeText}>{item.badge > 9 ? '9+' : item.badge}</Text>
          </View>
        )}
      </View>
      <View style={styles.menuContent}>
        <Text style={styles.menuTitle}>{item.title}</Text>
        <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
      </View>
      {item.value && (
        <Text style={[styles.menuValue, { color: item.color }]}>{item.value}</Text>
      )}
      <Ionicons name="chevron-forward" size={18} color="#6E6E73" />
    </TouchableOpacity>
  );

  const renderSection = (section: Section) => {
    const isExpanded = expandedSections.has(section.id);
    const itemCount = section.items.length;

    return (
      <View key={section.id} style={styles.collapsibleSection} data-testid={`section-${section.id}`}>
        <TouchableOpacity
          style={styles.sectionHeader}
          onPress={() => toggleSection(section.id)}
          activeOpacity={0.7}
          data-testid={`section-header-${section.id}`}
        >
          <View style={[styles.sectionIcon, { backgroundColor: `${section.color}20` }]}>
            <Ionicons name={section.icon as any} size={20} color={section.color} />
          </View>
          <View style={styles.sectionTitleContainer}>
            <Text style={styles.sectionTitleText}>{section.title}</Text>
            <Text style={styles.sectionCount}>{itemCount} items</Text>
          </View>
          <Ionicons 
            name={isExpanded ? 'chevron-up' : 'chevron-down'} 
            size={20} 
            color={colors.textSecondary} 
          />
        </TouchableOpacity>
        
        {isExpanded && (
          <View style={styles.sectionContent}>
            {section.items.map((item, index) => 
              renderMenuItem(item, index, index === section.items.length - 1)
            )}
          </View>
        )}
      </View>
    );
  };
  
  // Time Filter Pills Component
  const TimeFilterPills = () => (
    <View style={styles.timeFilterContainer}>
      {TIME_FILTERS.map((filter) => (
        <TouchableOpacity
          key={filter.value}
          style={[
            styles.timeFilterPill,
            timeRange === filter.value && styles.timeFilterPillActive
          ]}
          onPress={() => setTimeRange(filter.value)}
        >
          <Text style={[
            styles.timeFilterText,
            timeRange === filter.value && styles.timeFilterTextActive
          ]}>
            {filter.label}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  // Get role display name
  const getRoleDisplay = () => {
    if (isSuperAdmin) return 'Super Admin';
    if (isOrgAdmin) return 'Organization Admin';
    if (isStoreManager) return 'Store Manager';
    return 'Team Member';
  };
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>Loading dashboard...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const sections = buildSections();
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={handleBack} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.title}>Admin Dashboard</Text>
          <View style={styles.roleBadge}>
            <Ionicons name="shield-checkmark" size={12} color="#34C759" />
            <Text style={styles.roleText}>{getRoleDisplay()}</Text>
          </View>
        </View>
        <View style={{ width: 28 }} />
      </View>
      
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {/* Activity Ticker - for admins only */}
        {(isSuperAdmin || isOrgAdmin || isStoreManager) && (
          <ActivityTicker activities={activities} />
        )}
        
        {/* Quick Stats Cards - Super Admin Only */}
        {isSuperAdmin && (
          <View style={styles.quickStatsContainer}>
            <Text style={styles.quickStatsTitle}>Quick Overview</Text>
            <View style={styles.quickStatsGrid}>
              <TouchableOpacity 
                style={styles.quickStatCard}
                onPress={() => router.push('/admin/organizations')}
                data-testid="stat-organizations"
              >
                <View style={[styles.quickStatIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="business" size={24} color="#007AFF" />
                </View>
                <Text style={styles.quickStatValue}>
                  {(stats?.orgs_active || 0) + (stats?.orgs_inactive || 0)}
                </Text>
                <Text style={styles.quickStatLabel}>Organizations</Text>
                <Text style={styles.quickStatSubtext}>
                  {stats?.orgs_active || 0} active
                </Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.quickStatCard}
                onPress={() => router.push('/admin/stores')}
                data-testid="stat-accounts"
              >
                <View style={[styles.quickStatIcon, { backgroundColor: '#34C75920' }]}>
                  <Ionicons name="storefront" size={24} color="#34C759" />
                </View>
                <Text style={styles.quickStatValue}>
                  {(stats?.stores_active || 0) + (stats?.stores_inactive || 0)}
                </Text>
                <Text style={styles.quickStatLabel}>Accounts</Text>
                <Text style={styles.quickStatSubtext}>
                  {stats?.stores_active || 0} active
                </Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.quickStatCard}
                onPress={() => router.push('/admin/users')}
                data-testid="stat-users"
              >
                <View style={[styles.quickStatIcon, { backgroundColor: '#FF950020' }]}>
                  <Ionicons name="people" size={24} color="#FF9500" />
                </View>
                <Text style={styles.quickStatValue}>
                  {(stats?.users_active || 0) + (stats?.users_inactive || 0)}
                </Text>
                <Text style={styles.quickStatLabel}>Users</Text>
                <Text style={styles.quickStatSubtext}>
                  {stats?.users_active || 0} active
                </Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.quickStatCard}
                onPress={() => router.push('/admin/users')}
                data-testid="stat-employees"
              >
                <View style={[styles.quickStatIcon, { backgroundColor: '#AF52DE20' }]}>
                  <Ionicons name="person" size={24} color="#AF52DE" />
                </View>
                <Text style={styles.quickStatValue}>
                  {stats?.total_employees || stats?.users_active || 0}
                </Text>
                <Text style={styles.quickStatLabel}>Employees</Text>
                <Text style={styles.quickStatSubtext}>
                  Company directory
                </Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.quickStatCard}
                onPress={() => router.push('/admin/partner-agreements')}
                data-testid="stat-agreements"
              >
                <View style={[styles.quickStatIcon, { backgroundColor: '#FF2D5520' }]}>
                  <Ionicons name="document-text" size={24} color="#FF2D55" />
                </View>
                <Text style={styles.quickStatValue}>
                  {stats?.partner_agreements || 0}
                </Text>
                <Text style={styles.quickStatLabel}>Agreements</Text>
                <Text style={styles.quickStatSubtext}>
                  Partner contracts
                </Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.quickStatCard}
                onPress={() => router.push('/admin/individuals')}
                data-testid="stat-individuals"
              >
                <View style={[styles.quickStatIcon, { backgroundColor: '#5856D620' }]}>
                  <Ionicons name="person-circle" size={24} color="#5856D6" />
                </View>
                <Text style={styles.quickStatValue}>
                  {(stats?.individuals_active || 0) + (stats?.individuals_inactive || 0)}
                </Text>
                <Text style={styles.quickStatLabel}>Individuals</Text>
                <Text style={styles.quickStatSubtext}>
                  {stats?.individuals_active || 0} active
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
        
        {/* Time Filter - show above data section */}
        {(isSuperAdmin || isOrgAdmin || isStoreManager) && (
          <View style={styles.filterRow}>
            <Text style={styles.filterLabel}>Data Range:</Text>
            <TimeFilterPills />
          </View>
        )}
        
        {/* All Collapsible Sections */}
        {sections.map(section => renderSection(section))}
        
        {/* Empty state for regular users */}
        {isRegularUser && sections.length === 0 && (
          <View style={styles.emptyState}>
            <Ionicons name="person-circle" size={64} color={colors.textSecondary} />
            <Text style={styles.emptyTitle}>Welcome, {user?.name}!</Text>
            <Text style={styles.emptyText}>
              Your personal dashboard shows your performance and settings.
            </Text>
          </View>
        )}
        
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    color: colors.textSecondary,
    fontSize: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  headerCenter: {
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
    backgroundColor: '#34C75920',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  roleText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#34C759',
  },
  content: {
    padding: 16,
  },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  filterLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  timeFilterContainer: {
    flexDirection: 'row',
    gap: 6,
  },
  timeFilterPill: {
    paddingHorizontal: 18,
    paddingVertical: 8,
    borderRadius: 16,
    backgroundColor: colors.surface,
  },
  timeFilterPillActive: {
    backgroundColor: '#007AFF',
  },
  timeFilterText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  timeFilterTextActive: {
    color: colors.text,
  },
  // Quick Stats Styles
  quickStatsContainer: {
    marginBottom: 20,
  },
  quickStatsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  quickStatsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  quickStatCard: {
    width: '31%',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
  },
  quickStatIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  quickStatValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 2,
  },
  quickStatLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  quickStatSubtext: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  // Collapsible Section Styles
  collapsibleSection: {
    marginBottom: 12,
    backgroundColor: colors.card,
    borderRadius: 12,
    overflow: 'hidden',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
  },
  sectionIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  sectionTitleContainer: {
    flex: 1,
  },
  sectionTitleText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  sectionCount: {
    fontSize: 14,
    color: '#6E6E73',
    marginTop: 1,
  },
  sectionContent: {
    borderTopWidth: 1,
    borderTopColor: colors.surface,
    marginLeft: 20,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    position: 'relative',
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 17,
    fontWeight: '500',
    color: colors.text,
    marginBottom: 1,
  },
  menuSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  menuValue: {
    fontSize: 17,
    fontWeight: '700',
    marginRight: 10,
  },
  badgeDot: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: '#FF3B30',
    width: 18,
    height: 18,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.card,
  },
  badgeText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '700',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 21,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
});
