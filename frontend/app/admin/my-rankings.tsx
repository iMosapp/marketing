import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { adminAPI } from '../../services/api';

const METRICS = [
  { value: 'contacts_added', label: 'Contacts', icon: 'person-add' },
  { value: 'messages_sent', label: 'Messages', icon: 'chatbubbles' },
  { value: 'calls_made', label: 'Calls', icon: 'call' },
  { value: 'deals_closed', label: 'Deals', icon: 'trophy' },
];

const SCOPES = [
  { value: 'state', label: 'State', icon: 'location' },
  { value: 'region', label: 'Region', icon: 'map' },
  { value: 'country', label: 'National', icon: 'globe' },
];

export default function MyRankingsScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [selectedMetric, setSelectedMetric] = useState<string>('contacts_added');
  const [selectedScope, setSelectedScope] = useState<string>('state');
  const [settings, setSettings] = useState({
    leaderboard_visible: false,
    compare_scope: 'state',
    state: '',
    country: 'US',
  });
  const [userRank, setUserRank] = useState<number | null>(null);
  const [totalInScope, setTotalInScope] = useState(0);
  const [userState, setUserState] = useState('');
  const [userRegion, setUserRegion] = useState('');
  const [settingsLoading, setSettingsLoading] = useState(false);
  
  useFocusEffect(
    useCallback(() => {
      if (user?._id) {
        loadSettings();
        loadLeaderboard();
      }
    }, [user?._id])
  );
  
  useEffect(() => {
    if (user?._id) {
      loadLeaderboard();
    }
  }, [selectedMetric, selectedScope]);
  
  const loadSettings = async () => {
    if (!user?._id) return;
    try {
      const data = await adminAPI.getLeaderboardSettings(user._id);
      setSettings(data);
      setSelectedScope(data.compare_scope || 'state');
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };
  
  const loadLeaderboard = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const data = await adminAPI.getRegionalLeaderboard(user._id, selectedScope, selectedMetric);
      setLeaderboard(data.leaderboard || []);
      setUserRank(data.user_rank);
      setTotalInScope(data.total_in_scope || 0);
      setUserState(data.user_state || '');
      setUserRegion(data.user_region || '');
    } catch (error) {
      console.error('Failed to load leaderboard:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadLeaderboard();
    setRefreshing(false);
  };
  
  const toggleVisibility = async (value: boolean) => {
    if (!user?._id) return;
    try {
      setSettingsLoading(true);
      await adminAPI.updateLeaderboardSettings(user._id, { leaderboard_visible: value });
      setSettings(prev => ({ ...prev, leaderboard_visible: value }));
      // Reload leaderboard to reflect visibility change
      await loadLeaderboard();
    } catch (error) {
      console.error('Failed to update visibility:', error);
    } finally {
      setSettingsLoading(false);
    }
  };
  
  const updateScope = async (scope: string) => {
    if (!user?._id) return;
    setSelectedScope(scope);
    try {
      await adminAPI.updateLeaderboardSettings(user._id, { compare_scope: scope });
      setSettings(prev => ({ ...prev, compare_scope: scope }));
    } catch (error) {
      console.error('Failed to update scope:', error);
    }
  };
  
  const getRankStyle = (rank: number) => {
    switch (rank) {
      case 1: return { bg: '#FFD60A20', color: '#FFD60A', icon: 'trophy' };
      case 2: return { bg: '#C0C0C020', color: '#C0C0C0', icon: 'medal' };
      case 3: return { bg: '#CD7F3220', color: '#CD7F32', icon: 'medal' };
      default: return { bg: '#2C2C2E', color: '#8E8E93', icon: null };
    }
  };
  
  const getMetricInfo = (metric: string) => {
    return METRICS.find(m => m.value === metric) || METRICS[0];
  };
  
  const getScopeLabel = () => {
    if (selectedScope === 'state') return userState || 'your state';
    if (selectedScope === 'region') return userRegion || 'your region';
    return 'the country';
  };
  
  const renderLeaderboardItem = ({ item, index }: { item: any; index: number }) => {
    const rank = item.rank || index + 1;
    const rankStyle = getRankStyle(rank);
    const isCurrentUser = item.is_you || user?._id === item.user_id;
    
    return (
      <View style={[styles.leaderboardItem, isCurrentUser && styles.currentUserItem]}>
        {/* Rank */}
        <View style={[styles.rankBadge, { backgroundColor: rankStyle.bg }]}>
          {rank <= 3 ? (
            <Ionicons name={rankStyle.icon as any} size={20} color={rankStyle.color} />
          ) : (
            <Text style={[styles.rankText, { color: rankStyle.color }]}>{rank}</Text>
          )}
        </View>
        
        {/* User Info */}
        <View style={styles.userInfo}>
          <View style={styles.userAvatar}>
            <Text style={styles.avatarText}>
              {item.name?.split(' ').map((n: string) => n[0]).join('').slice(0, 2) || '?'}
            </Text>
          </View>
          <View style={styles.userDetails}>
            <Text style={styles.userName}>
              {isCurrentUser ? 'You' : item.name}
              {isCurrentUser && !item.is_you && <Text style={styles.youBadge}> (You)</Text>}
            </Text>
            {item.state && (
              <Text style={styles.userLocation}>{item.state}</Text>
            )}
          </View>
        </View>
        
        {/* Score */}
        <View style={styles.scoreContainer}>
          <Text style={styles.scoreValue}>{item.metric_value || 0}</Text>
          <Text style={styles.scoreLabel}>{getMetricInfo(selectedMetric).label}</Text>
        </View>
      </View>
    );
  };
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>My Rankings</Text>
        <View style={{ width: 28 }} />
      </View>
      
      {/* Visibility Toggle */}
      <View style={styles.visibilitySection}>
        <View style={styles.visibilityRow}>
          <View style={styles.visibilityInfo}>
            <Ionicons name="eye" size={22} color={settings.leaderboard_visible ? '#34C759' : '#8E8E93'} />
            <View style={styles.visibilityTextContainer}>
              <Text style={styles.visibilityLabel}>Show me on leaderboards</Text>
              <Text style={styles.visibilityDescription}>
                {settings.leaderboard_visible 
                  ? 'Other independents can see your ranking'
                  : 'Your ranking is hidden from others'}
              </Text>
            </View>
          </View>
          <Switch
            value={settings.leaderboard_visible}
            onValueChange={toggleVisibility}
            trackColor={{ false: '#3A3A3C', true: '#34C759' }}
            thumbColor="#FFF"
            disabled={settingsLoading}
          />
        </View>
      </View>
      
      {/* Scope Selector */}
      <View style={styles.scopeSection}>
        <Text style={styles.sectionLabel}>Compare with</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scopeScroll}>
          {SCOPES.map(scope => (
            <TouchableOpacity 
              key={scope.value}
              style={[styles.scopeChip, selectedScope === scope.value && styles.scopeChipActive]}
              onPress={() => updateScope(scope.value)}
            >
              <Ionicons 
                name={scope.icon as any} 
                size={18} 
                color={selectedScope === scope.value ? '#FFF' : '#8E8E93'} 
              />
              <Text style={[styles.scopeText, selectedScope === scope.value && styles.scopeTextActive]}>
                {scope.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>
      
      {/* Metric Selector */}
      <View style={styles.metricSelector}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.metricScroll}>
          {METRICS.map(metric => (
            <TouchableOpacity 
              key={metric.value}
              style={[styles.metricChip, selectedMetric === metric.value && styles.metricChipActive]}
              onPress={() => setSelectedMetric(metric.value)}
            >
              <Ionicons 
                name={metric.icon as any} 
                size={18} 
                color={selectedMetric === metric.value ? '#FFF' : '#8E8E93'} 
              />
              <Text style={[styles.metricText, selectedMetric === metric.value && styles.metricTextActive]}>
                {metric.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>
      
      {/* Your Rank Summary */}
      {userRank ? (
        <View style={styles.rankSummary}>
          <View style={styles.rankSummaryMain}>
            <Ionicons name="ribbon" size={24} color="#FFD60A" />
            <Text style={styles.rankSummaryText}>
              You're <Text style={styles.rankNumber}>#{userRank}</Text> of {totalInScope}
            </Text>
          </View>
          <Text style={styles.rankSummarySubtext}>
            in {getScopeLabel()} for {getMetricInfo(selectedMetric).label.toLowerCase()}
          </Text>
        </View>
      ) : settings.leaderboard_visible ? (
        <View style={styles.rankSummary}>
          <Ionicons name="search" size={24} color="#8E8E93" />
          <Text style={styles.noRankText}>
            No ranking data found for {getScopeLabel()}
          </Text>
        </View>
      ) : (
        <View style={styles.rankSummary}>
          <Ionicons name="eye-off" size={24} color="#8E8E93" />
          <Text style={styles.noRankText}>
            Enable visibility to see your ranking
          </Text>
        </View>
      )}
      
      {/* Leaderboard List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          data={leaderboard}
          renderItem={renderLeaderboardItem}
          keyExtractor={(item) => item.user_id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="people-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No rankings yet</Text>
              <Text style={styles.emptySubtext}>
                {settings.leaderboard_visible 
                  ? `Be the first to rank in ${getScopeLabel()}! Add contacts, send messages, and close deals.`
                  : 'Enable visibility above to compare with other independents in your area.'}
              </Text>
            </View>
          )}
          ListHeaderComponent={() => (
            leaderboard.length > 0 ? (
              <Text style={styles.listHeader}>
                Top performers in {getScopeLabel()}
              </Text>
            ) : null
          )}
        />
      )}
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
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
  },
  visibilitySection: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  visibilityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  visibilityInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 12,
  },
  visibilityTextContainer: {
    flex: 1,
  },
  visibilityLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  visibilityDescription: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  scopeSection: {
    paddingTop: 12,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  sectionLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  scopeScroll: {
    paddingHorizontal: 16,
  },
  scopeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#1C1C1E',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    marginRight: 8,
  },
  scopeChipActive: {
    backgroundColor: '#34C759',
  },
  scopeText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  scopeTextActive: {
    color: '#FFF',
  },
  metricSelector: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  metricScroll: {
    paddingHorizontal: 16,
  },
  metricChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#1C1C1E',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    marginRight: 8,
  },
  metricChipActive: {
    backgroundColor: '#007AFF',
  },
  metricText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  metricTextActive: {
    color: '#FFF',
  },
  rankSummary: {
    alignItems: 'center',
    paddingVertical: 20,
    paddingHorizontal: 16,
    backgroundColor: '#1C1C1E',
    margin: 16,
    marginBottom: 0,
    borderRadius: 16,
  },
  rankSummaryMain: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  rankSummaryText: {
    fontSize: 18,
    color: '#FFF',
  },
  rankNumber: {
    fontWeight: 'bold',
    fontSize: 24,
    color: '#FFD60A',
  },
  rankSummarySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 4,
  },
  noRankText: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  listHeader: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 12,
  },
  listContent: {
    padding: 16,
  },
  leaderboardItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  currentUserItem: {
    borderWidth: 2,
    borderColor: '#007AFF',
  },
  rankBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  rankText: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  userInfo: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  avatarText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
  userDetails: {
    flex: 1,
  },
  userName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  youBadge: {
    color: '#007AFF',
    fontWeight: '500',
  },
  userLocation: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  scoreContainer: {
    alignItems: 'flex-end',
  },
  scoreValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
  },
  scoreLabel: {
    fontSize: 11,
    color: '#8E8E93',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyText: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    paddingHorizontal: 32,
  },
});
