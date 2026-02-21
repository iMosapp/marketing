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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { 
  hasPermission, 
  canViewAdminSection, 
  getDataScope,
} from '../../utils/permissions';

const TILE_HEIGHT = 64; // Uniform height for all tiles

const TIME_FILTERS = [
  { label: '7D', value: '7d' },
  { label: '30D', value: '30d' },
  { label: '90D', value: '90d' },
  { label: 'All', value: 'all' },
];

// Activity Ticker Component
const ActivityTicker = ({ activities }: { activities: any[] }) => {
  const scrollX = useRef(new Animated.Value(0)).current;
  const [tickerWidth, setTickerWidth] = useState(0);
  
  useEffect(() => {
    if (activities.length === 0 || tickerWidth === 0) return;
    
    // Calculate total content width
    const contentWidth = activities.length * 300; // Approximate width per item
    
    // Animate the ticker
    const animation = Animated.loop(
      Animated.timing(scrollX, {
        toValue: -contentWidth,
        duration: activities.length * 5000, // 5 seconds per item
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
  
  // Format relative time
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
        {/* Duplicate activities for seamless loop */}
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
    borderRadius: 8,
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
    color: '#FFF',
    fontSize: 13,
    flex: 1,
  },
  tickerTime: {
    color: '#8E8E93',
    fontSize: 11,
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
    fontSize: 13,
  },
});

export default function AdminDashboard() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [dataStats, setDataStats] = useState<any>(null);
  const [timeRange, setTimeRange] = useState('all');
  const [activities, setActivities] = useState<any[]>([]);
  const [trainingProgress, setTrainingProgress] = useState<any>(null);
  const [trainingExpanded, setTrainingExpanded] = useState(false);
  
  // Scroll position persistence
  const scrollViewRef = useRef<ScrollView>(null);
  const scrollPositionRef = useRef(0);
  
  // Check user's data scope and permissions
  const dataScope = getDataScope(user);
  const isSuperAdmin = user?.role === 'super_admin';
  const isOrgAdmin = user?.role === 'org_admin';
  const isStoreManager = user?.role === 'store_manager';
  const organizationId = dataScope === 'organization' || dataScope === 'store' ? user?.organization_id : null;
  const storeId = dataScope === 'store' ? user?.store_id : null;
  
  // Permission checks for sections
  const canViewCustomers = canViewAdminSection(user, 'customers');
  const canViewData = canViewAdminSection(user, 'data');
  const canViewTools = canViewAdminSection(user, 'tools');
  const canViewInternal = canViewAdminSection(user, 'internal');
  
  useFocusEffect(
    useCallback(() => {
      loadAllStats();
      loadActivities();
      loadTrainingProgress();
      
      // Restore scroll position when returning to this screen
      if (scrollPositionRef.current > 0 && scrollViewRef.current) {
        setTimeout(() => {
          scrollViewRef.current?.scrollTo({ y: scrollPositionRef.current, animated: false });
        }, 100);
      }
    }, [user, timeRange])
  );
  
  // Save scroll position when scrolling
  const handleScroll = (event: any) => {
    scrollPositionRef.current = event.nativeEvent.contentOffset.y;
  };
  
  // Refresh activities periodically
  useEffect(() => {
    const interval = setInterval(() => {
      loadActivities();
    }, 30000); // Every 30 seconds
    
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
  
  const loadTrainingProgress = async () => {
    if (!user?._id) return;
    try {
      let params = '';
      if (organizationId) {
        params += `?organization_id=${organizationId}`;
      }
      if (storeId) {
        params += params ? `&store_id=${storeId}` : `?store_id=${storeId}`;
      }
      const res = await api.get(`/sop/team/progress${params}`, {
        headers: { 'X-User-ID': user._id }
      });
      setTrainingProgress(res.data);
    } catch (error) {
      console.error('Failed to load training progress:', error);
    }
  };
  
  const loadAllStats = async () => {
    try {
      setLoading(true);
      
      // Build query params - org admins see only their org's data
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
  
  const handleTimeRangeChange = (value: string) => {
    setTimeRange(value);
  };
  
  // Full-width tile for Customers section - no circular backgrounds
  const CustomerTile = ({ icon, label, active, inactive, color, onPress }: any) => (
    <TouchableOpacity style={styles.tile} onPress={onPress}>
      <Ionicons name={icon} size={26} color={color} />
      <Text style={styles.tileLabel}>{label}</Text>
      <View style={styles.tileCountsStacked}>
        <Text style={styles.activeCountTextPlain}>{active}</Text>
        <Text style={styles.inactiveCountTextPlain}>{inactive}</Text>
      </View>
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );
  
  // Data bar component - uniform height, no background on numbers
  const DataBar = ({ icon, label, value, color, onPress }: any) => (
    <TouchableOpacity style={styles.tile} onPress={onPress}>
      <Ionicons name={icon} size={26} color={color} />
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={[styles.dataValuePlain, { color }]}>{value?.toLocaleString() || 0}</Text>
      <Ionicons name="chevron-forward" size={18} color="#8E8E93" />
    </TouchableOpacity>
  );
  
  // Tool card - uniform height
  const ToolCard = ({ icon, title, subtitle, color, onPress }: any) => (
    <TouchableOpacity style={styles.tile} onPress={onPress}>
      <Ionicons name={icon} size={26} color={color} />
      <View style={styles.toolInfo}>
        <Text style={styles.tileLabel}>{title}</Text>
        {subtitle && <Text style={styles.toolSubtitle}>{subtitle}</Text>}
      </View>
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );
  
  // Time Filter Pills
  const TimeFilterPills = () => (
    <View style={styles.timeFilterContainer}>
      {TIME_FILTERS.map((filter) => (
        <TouchableOpacity
          key={filter.value}
          style={[
            styles.timeFilterPill,
            timeRange === filter.value && styles.timeFilterPillActive
          ]}
          onPress={() => handleTimeRangeChange(filter.value)}
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
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }
  
  // Handle back navigation properly for web
  const handleBack = () => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/(tabs)');
    }
  };
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={handleBack} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Admin</Text>
        <View style={{ width: 28 }} />
      </View>
      
      <ScrollView
        ref={scrollViewRef}
        contentContainerStyle={styles.content}
        onScroll={handleScroll}
        scrollEventThrottle={16}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {/* Activity Ticker */}
        <ActivityTicker activities={activities} />
        
        {/* CUSTOMERS Section - Only visible to org_admin and above */}
        {canViewCustomers && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>CUSTOMERS</Text>
            
            {/* Organizations - super_admin only */}
            {hasPermission(user, 'view_organizations') && (
              <CustomerTile 
                icon="business" 
                label="Organizations"
                active={stats?.orgs_active || 0}
                inactive={stats?.orgs_inactive || 0}
                color="#007AFF"
                onPress={() => router.push('/admin/organizations')}
              />
            )}
            
            {/* Stores - org_admin and above only (managers see it in their own section) */}
            {(hasPermission(user, 'view_all_stores') || hasPermission(user, 'view_org_stores')) && (
              <CustomerTile 
                icon="storefront" 
                label="Stores"
                active={stats?.stores_active || 0}
                inactive={stats?.stores_inactive || 0}
                color="#34C759"
                onPress={() => router.push('/admin/stores')}
              />
            )}
            
            {/* Users - org_admin and above */}
            {(hasPermission(user, 'view_all_users') || hasPermission(user, 'view_org_users')) && (
              <CustomerTile 
                icon="people" 
                label="Users"
                active={stats?.users_active || 0}
                inactive={stats?.users_inactive || 0}
                color="#FF9500"
                onPress={() => router.push('/admin/users')}
              />
            )}
            
            {/* Individuals - super_admin only */}
            {hasPermission(user, 'view_individuals') && (
              <CustomerTile 
                icon="person" 
                label="Individuals"
                active={stats?.individuals_active || 0}
                inactive={stats?.individuals_inactive || 0}
                color="#AF52DE"
                onPress={() => router.push('/admin/individuals')}
              />
            )}
          </View>
        )}
        
        {/* MY STORES Section - For store managers */}
        {isStoreManager && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>MY STORES</Text>
            
            <CustomerTile 
              icon="storefront" 
              label="My Stores"
              active={stats?.stores_active || 0}
              inactive={0}
              color="#34C759"
              onPress={() => router.push('/admin/stores')}
            />
            
            <CustomerTile 
              icon="people" 
              label="My Team"
              active={stats?.users_active || 0}
              inactive={stats?.users_inactive || 0}
              color="#FF9500"
              onPress={() => router.push('/admin/users')}
            />
          </View>
        )}
        
        {/* DATA Section */}
        {canViewData && (
        <View style={styles.section}>
          <View style={styles.dataSectionHeader}>
            <Text style={styles.sectionTitleInline}>DATA</Text>
            <TimeFilterPills />
          </View>
          
          <DataBar 
            icon="chatbubbles" 
            label="Messages"
            value={dataStats?.total_messages}
            color="#007AFF"
            onPress={() => router.push('/admin/data/messages')}
          />
          <DataBar 
            icon="call" 
            label="Calls"
            value={dataStats?.total_calls}
            color="#34C759"
            onPress={() => router.push('/admin/data/calls')}
          />
          <DataBar 
            icon="sparkles" 
            label="MVP"
            value={dataStats?.ai_messages}
            color="#AF52DE"
            onPress={() => router.push('/admin/data/ai-messages')}
          />
          <DataBar 
            icon="person" 
            label="Contacts"
            value={dataStats?.total_contacts}
            color="#FF9500"
            onPress={() => router.push('/admin/contacts')}
          />
          <DataBar 
            icon="card" 
            label="Card Shares"
            value={dataStats?.card_shares}
            color="#FF2D55"
            onPress={() => router.push('/admin/data/card-shares')}
          />
          <DataBar 
            icon="gift" 
            label="Congrats Cards"
            value={dataStats?.congrats_cards}
            color="#C9A962"
            onPress={() => router.push('/admin/data/congrats-cards')}
          />
          <DataBar 
            icon="git-network" 
            label="Referrals"
            value={dataStats?.total_referrals}
            color="#5856D6"
            onPress={() => router.push('/admin/data/referrals')}
          />
          <DataBar 
            icon="rocket" 
            label="Campaigns"
            value={dataStats?.total_campaigns}
            color="#FF3B30"
            onPress={() => router.push('/admin/data/campaigns')}
          />
          <DataBar 
            icon="star" 
            label="Review Templates Sent"
            value={dataStats?.review_templates_sent}
            color="#FFD60A"
            onPress={() => router.push('/admin/data/review-templates')}
          />
          <DataBar 
            icon="share" 
            label="Referral Templates Sent"
            value={dataStats?.referral_templates_sent}
            color="#5856D6"
            onPress={() => router.push('/admin/data/referral-templates')}
          />
          <DataBar 
            icon="checkmark-circle" 
            label="Sold Templates Sent"
            value={dataStats?.sold_templates_sent}
            color="#34C759"
            onPress={() => router.push('/admin/data/sold-templates')}
          />
        </View>
        )}
        
        {/* MY ACCOUNT Section - For store managers */}
        {isStoreManager && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>MY ACCOUNT</Text>
          
          <ToolCard 
            icon="people" 
            title="Manage Team"
            subtitle="Add, remove & manage team members"
            color="#FF9500"
            onPress={() => router.push('/admin/manage-team')}
          />
          <ToolCard 
            icon="document-text" 
            title="My Agreement"
            subtitle="View your signed agreement"
            color="#007AFF"
            onPress={() => router.push('/admin/my-agreement')}
          />
          <ToolCard 
            icon="receipt" 
            title="My Invoices"
            subtitle="View invoices & payment history"
            color="#34C759"
            onPress={() => router.push('/admin/my-invoices')}
          />
        </View>
        )}
        
        {/* TOOLS Section */}
        {canViewTools && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>TOOLS</Text>
          
          {/* Training & SOPs - available to all admin roles */}
          <ToolCard 
            icon="book" 
            title="Training & SOPs"
            subtitle="Internal procedures & guides"
            color="#34C759"
            onPress={() => router.push('/admin/sop')}
          />
          
          {/* Training Progress Widget */}
          {trainingProgress && trainingProgress.total_sops > 0 && (
            <TouchableOpacity 
              style={styles.trainingWidget}
              onPress={() => router.push('/admin/sop')}
              activeOpacity={0.7}
            >
              <View style={styles.trainingWidgetHeader}>
                <Ionicons name="school" size={20} color="#34C759" />
                <Text style={styles.trainingWidgetTitle}>Team Training Progress</Text>
                <View style={styles.trainingRateBadge}>
                  <Text style={styles.trainingRateText}>{trainingProgress.summary?.completion_rate || 0}%</Text>
                </View>
              </View>
              
              <View style={styles.trainingSummary}>
                <View style={styles.trainingStatItem}>
                  <Text style={styles.trainingStatValue}>{trainingProgress.summary?.fully_trained || 0}</Text>
                  <Text style={styles.trainingStatLabel}>Complete</Text>
                </View>
                <View style={styles.trainingStatDivider} />
                <View style={styles.trainingStatItem}>
                  <Text style={[styles.trainingStatValue, { color: '#FF9500' }]}>{trainingProgress.summary?.in_progress || 0}</Text>
                  <Text style={styles.trainingStatLabel}>In Progress</Text>
                </View>
                <View style={styles.trainingStatDivider} />
                <View style={styles.trainingStatItem}>
                  <Text style={[styles.trainingStatValue, { color: '#FF3B30' }]}>{trainingProgress.summary?.not_started || 0}</Text>
                  <Text style={styles.trainingStatLabel}>Not Started</Text>
                </View>
              </View>
              
              {trainingProgress.team_members?.slice(0, 3).map((member: any) => (
                <View key={member._id} style={styles.trainingMemberRow}>
                  <View style={styles.trainingMemberInfo}>
                    <Text style={styles.trainingMemberName} numberOfLines={1}>{member.name}</Text>
                    <Text style={styles.trainingMemberStats}>{member.completed}/{member.total} completed</Text>
                  </View>
                  <View style={styles.trainingProgressBar}>
                    <View style={[styles.trainingProgressFill, { width: `${member.percentage}%` }]} />
                  </View>
                  <Text style={[
                    styles.trainingMemberPercent,
                    member.percentage === 100 ? { color: '#34C759' } : 
                    member.percentage > 0 ? { color: '#FF9500' } : { color: '#FF3B30' }
                  ]}>{member.percentage}%</Text>
                </View>
              ))}
              
              {trainingProgress.team_members?.length > 3 && (
                <Text style={styles.trainingMoreText}>
                  +{trainingProgress.team_members.length - 3} more team members
                </Text>
              )}
            </TouchableOpacity>
          )}
          
          {/* Billing - super_admin only */}
          {hasPermission(user, 'view_billing') && (
            <ToolCard 
              icon="card" 
              title="Billing & Revenue"
              subtitle="Payments, MRR & commissions"
              color="#34C759"
              onPress={() => router.push('/admin/billing')}
            />
          )}
          
          {/* Revenue Forecast - super_admin only */}
          {hasPermission(user, 'view_revenue_forecast') && (
            <ToolCard 
              icon="trending-up" 
              title="Revenue Forecast"
              subtitle="Sales projections & commissions"
              color="#007AFF"
              onPress={() => router.push('/admin/forecasting')}
            />
          )}
          
          {/* Pending Users - org_admin and above only */}
          {hasPermission(user, 'approve_users') && (
            <ToolCard 
              icon="person-add" 
              title="Pending Users"
              subtitle="Review and approve signups"
              color="#FF9500"
              onPress={() => router.push('/admin/pending-users')}
            />
          )}
          
          {/* Leaderboards - everyone with admin access */}
          <ToolCard 
            icon="trophy" 
            title="Leaderboards"
            subtitle={isStoreManager ? "My team rankings" : "Performance rankings"}
            color="#FFD60A"
            onPress={() => router.push('/admin/leaderboard')}
          />
          
          {/* Activity - all admin roles can see (scoped to their access) */}
          {hasPermission(user, 'view_activity_feed') && (
            <ToolCard 
              icon="pulse" 
              title="Activity"
              subtitle={isStoreManager ? "My team activity" : "Recent team activity"}
              color="#5AC8FA"
              onPress={() => router.push('/admin/activity-feed')}
            />
          )}
          
          {/* Training Preview - everyone with admin access */}
          {hasPermission(user, 'view_training_preview') && (
            <ToolCard 
              icon="school" 
              title="Training Preview"
              subtitle="Watch the new user onboarding"
              color="#C9A962"
              onPress={() => router.push('/admin/training-preview')}
            />
          )}
        </View>
        )}
        
        {/* INTERNAL Section - Super Admin Only */}
        {canViewInternal && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>INTERNAL</Text>
          
          <ToolCard 
            icon="book" 
            title="Training & SOPs"
            subtitle="Internal procedures & guides"
            color="#34C759"
            onPress={() => router.push('/admin/sop')}
          />
          <ToolCard 
            icon="settings" 
            title="Onboarding Settings"
            subtitle="Branding, messages & automation"
            color="#FF2D55"
            onPress={() => router.push('/admin/onboarding-settings')}
          />
          <ToolCard 
            icon="call" 
            title="Phone Assignments"
            subtitle="Manage MVPLine numbers"
            color="#5AC8FA"
            onPress={() => router.push('/admin/phone-assignments')}
          />
          <ToolCard 
            icon="document-text" 
            title="Partner Agreements"
            subtitle="Commission agreements"
            color="#AF52DE"
            onPress={() => router.push('/admin/partner-agreements')}
          />
          <ToolCard 
            icon="pricetag" 
            title="Discount Codes"
            subtitle="Manage promo codes"
            color="#FF9500"
            onPress={() => router.push('/admin/discount-codes')}
          />
          <ToolCard 
            icon="document" 
            title="Quotes"
            subtitle="Manage quotes & proposals"
            color="#007AFF"
            onPress={() => router.push('/admin/quotes')}
          />
        </View>
        )}
        
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  content: {
    padding: 16,
  },
  // Section
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    letterSpacing: 0.5,
    marginBottom: 12,
    marginLeft: 4,
  },
  sectionTitleInline: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    letterSpacing: 0.5,
    marginLeft: 4,
  },
  // Uniform Tile Style (used for all tiles)
  tile: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 18,
    marginBottom: 8,
    minHeight: TILE_HEIGHT,
  },
  tileLabel: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
    color: '#FFF',
    marginLeft: 14,
  },
  tileCounts: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginRight: 10,
  },
  tileCountsStacked: {
    alignItems: 'flex-end',
    marginRight: 10,
  },
  activeCountBadge: {
    backgroundColor: '#34C75930',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 10,
  },
  activeCountText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#34C759',
  },
  activeCountTextPlain: {
    fontSize: 16,
    fontWeight: '700',
    color: '#34C759',
  },
  inactiveCountBadge: {
    backgroundColor: '#FF3B3030',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 10,
  },
  inactiveCountText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FF3B30',
  },
  inactiveCountTextPlain: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FF3B30',
    marginTop: 2,
  },
  // Tool info (for subtitle)
  toolInfo: {
    flex: 1,
    marginLeft: 14,
  },
  toolSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  // Data value badge (kept for backwards compatibility)
  dataValue: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 10,
    marginRight: 10,
  },
  dataValueText: {
    fontSize: 15,
    fontWeight: '700',
  },
  // Plain data value - no background
  dataValuePlain: {
    fontSize: 16,
    fontWeight: '700',
    marginRight: 10,
  },
  // Data section header with filter
  dataSectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  // Time Filter Pills
  timeFilterContainer: {
    flexDirection: 'row',
    gap: 6,
  },
  timeFilterPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: '#2C2C2E',
  },
  timeFilterPillActive: {
    backgroundColor: '#007AFF',
  },
  timeFilterText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
  },
  timeFilterTextActive: {
    color: '#FFF',
  },
  // Training Progress Widget
  trainingWidget: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  trainingWidgetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  trainingWidgetTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    marginLeft: 10,
    flex: 1,
  },
  trainingRateBadge: {
    backgroundColor: '#34C75930',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  trainingRateText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#34C759',
  },
  trainingSummary: {
    flexDirection: 'row',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    paddingVertical: 14,
    marginBottom: 16,
  },
  trainingStatItem: {
    flex: 1,
    alignItems: 'center',
  },
  trainingStatValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#34C759',
  },
  trainingStatLabel: {
    fontSize: 11,
    color: '#8E8E93',
    marginTop: 2,
  },
  trainingStatDivider: {
    width: 1,
    backgroundColor: '#3A3A3C',
  },
  trainingMemberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  trainingMemberInfo: {
    flex: 1,
  },
  trainingMemberName: {
    fontSize: 14,
    fontWeight: '500',
    color: '#FFF',
  },
  trainingMemberStats: {
    fontSize: 11,
    color: '#8E8E93',
    marginTop: 2,
  },
  trainingProgressBar: {
    width: 60,
    height: 6,
    backgroundColor: '#3A3A3C',
    borderRadius: 3,
    marginHorizontal: 10,
    overflow: 'hidden',
  },
  trainingProgressFill: {
    height: '100%',
    backgroundColor: '#34C759',
    borderRadius: 3,
  },
  trainingMemberPercent: {
    fontSize: 13,
    fontWeight: '600',
    width: 40,
    textAlign: 'right',
    color: '#8E8E93',
  },
  trainingMoreText: {
    fontSize: 12,
    color: '#007AFF',
    textAlign: 'center',
    marginTop: 12,
  },
});
