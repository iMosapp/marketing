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
import { useAuthStore } from '../store/authStore';
import { adminAPI } from '../services/api';
import { showSimpleAlert } from '../services/alert';

const METRICS = [
  { value: 'contacts_added', label: 'Contacts', icon: 'person-add' },
  { value: 'messages_sent', label: 'Messages', icon: 'chatbubbles' },
  { value: 'calls_made', label: 'Calls', icon: 'call' },
  { value: 'deals_closed', label: 'Deals', icon: 'trophy' },
];

const SCOPES = [
  { value: 'state', label: 'My State', icon: 'location' },
  { value: 'region', label: 'My Region', icon: 'map' },
  { value: 'country', label: 'Nationwide', icon: 'globe' },
];

export default function MyRankingsScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [settings, setSettings] = useState({
    leaderboard_visible: false,
    compare_scope: 'state',
    state: '',
    country: 'US',
  });
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [userRank, setUserRank] = useState<number | null>(null);
  const [totalInScope, setTotalInScope] = useState(0);
  const [selectedMetric, setSelectedMetric] = useState('contacts_added');
  const [selectedScope, setSelectedScope] = useState('state');
  const [savingSettings, setSavingSettings] = useState(false);
  
  useFocusEffect(
    useCallback(() => {
      if (user) {
        loadSettings();
      }
    }, [user])
  );
  
  useEffect(() => {
    if (user && settings.leaderboard_visible) {
      loadLeaderboard();
    }
  }, [selectedMetric, selectedScope, settings.leaderboard_visible]);
  
  const loadSettings = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      const data = await adminAPI.getLeaderboardSettings(user._id);
      setSettings(data);
      setSelectedScope(data.compare_scope || 'state');
      
      if (data.leaderboard_visible) {
        await loadLeaderboard();
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadLeaderboard = async () => {
    if (!user) return;
    
    try {
      const data = await adminAPI.getRegionalLeaderboard(user._id, selectedScope, selectedMetric);
      setLeaderboard(data.leaderboard || []);
      setUserRank(data.user_rank);
      setTotalInScope(data.total_in_scope);
    } catch (error) {
      console.error('Failed to load leaderboard:', error);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadSettings();
    setRefreshing(false);
  };
  
  const toggleVisibility = async (visible: boolean) => {
    if (!user?._id) {
      showSimpleAlert('Error', 'Please log in to update settings');
      return;
    }
    
    setSavingSettings(true);
    try {
      await adminAPI.updateLeaderboardSettings(user._id, { leaderboard_visible: visible });
      setSettings({ ...settings, leaderboard_visible: visible });
      
      if (visible) {
        await loadLeaderboard();
      }
    } catch (error) {
      console.error('Failed to update leaderboard settings:', error);
      showSimpleAlert('Error', 'Failed to update settings');
    } finally {
      setSavingSettings(false);
    }
  };
  
  const updateScope = async (scope: string) => {
    if (!user) return;
    
    setSelectedScope(scope);
    setSavingSettings(true);
    try {
      await adminAPI.updateLeaderboardSettings(user._id, { compare_scope: scope });
      setSettings({ ...settings, compare_scope: scope });
    } catch (error) {
      showSimpleAlert('Error', 'Failed to update scope');
    } finally {
      setSavingSettings(false);
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
  
  const getScopeLabel = (scope: string) => {
    const s = SCOPES.find(s => s.value === scope);
    if (scope === 'state' && settings.state) {
      return settings.state;
    }
    return s?.label || scope;
  };
  
  const renderLeaderboardItem = ({ item }: { item: any }) => {
    const rankStyle = getRankStyle(item.rank);
    
    return (
      <View style={[styles.leaderboardItem, item.is_you && styles.currentUserItem]}>
        <View style={[styles.rankBadge, { backgroundColor: rankStyle.bg }]}>
          {item.rank <= 3 ? (
            <Ionicons name={rankStyle.icon as any} size={18} color={rankStyle.color} />
          ) : (
            <Text style={[styles.rankText, { color: rankStyle.color }]}>{item.rank}</Text>
          )}
        </View>
        
        <View style={styles.userInfo}>
          <Text style={styles.userName}>
            {item.is_you ? 'You' : item.name}
          </Text>
          {item.state && <Text style={styles.userState}>{item.state}</Text>}
        </View>
        
        <Text style={styles.scoreValue}>{item.metric_value}</Text>
      </View>
    );
  };
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }
  
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
      
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {/* Visibility Setting */}
        <View style={styles.settingCard}>
          <View style={styles.settingHeader}>
            <View style={styles.settingIcon}>
              <Ionicons name="eye" size={24} color="#007AFF" />
            </View>
            <View style={styles.settingInfo}>
              <Text style={styles.settingTitle}>Show My Rankings</Text>
              <Text style={styles.settingDescription}>
                Opt-in to appear on regional leaderboards and see how you compare
              </Text>
            </View>
            {savingSettings ? (
              <ActivityIndicator size="small" color="#007AFF" />
            ) : (
              <Switch
                data-testid="leaderboard-visibility-toggle"
                value={settings.leaderboard_visible === true}
                onValueChange={(value) => toggleVisibility(value)}
                trackColor={{ false: '#3A3A3C', true: '#34C759' }}
                thumbColor="#FFF"
                disabled={savingSettings}
              />
            )}
          </View>
        </View>
        
        {settings.leaderboard_visible && (
          <>
            {/* Scope Selector */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Compare Against</Text>
              <View style={styles.scopeSelector}>
                {SCOPES.map(scope => (
                  <TouchableOpacity 
                    key={scope.value}
                    style={[styles.scopeButton, selectedScope === scope.value && styles.scopeButtonActive]}
                    onPress={() => updateScope(scope.value)}
                  >
                    <Ionicons 
                      name={scope.icon as any} 
                      size={20} 
                      color={selectedScope === scope.value ? '#FFF' : '#8E8E93'} 
                    />
                    <Text style={[styles.scopeText, selectedScope === scope.value && styles.scopeTextActive]}>
                      {scope.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
            
            {/* Metric Selector */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Ranking By</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
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
            
            {/* Your Rank Banner */}
            {userRank && (
              <View style={styles.yourRankCard}>
                <View style={styles.yourRankIcon}>
                  <Ionicons name="ribbon" size={32} color="#FFD60A" />
                </View>
                <View style={styles.yourRankInfo}>
                  <Text style={styles.yourRankLabel}>Your Rank in {getScopeLabel(selectedScope)}</Text>
                  <Text style={styles.yourRankNumber}>#{userRank}</Text>
                  <Text style={styles.yourRankTotal}>of {totalInScope} users</Text>
                </View>
              </View>
            )}
            
            {/* Leaderboard */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Top Performers - {getScopeLabel(selectedScope)}</Text>
              
              {leaderboard.length > 0 ? (
                leaderboard.slice(0, 10).map((item, index) => (
                  <View key={item.user_id || index}>
                    {renderLeaderboardItem({ item })}
                  </View>
                ))
              ) : (
                <View style={styles.emptyLeaderboard}>
                  <Ionicons name="people-outline" size={48} color="#2C2C2E" />
                  <Text style={styles.emptyText}>No users in your {selectedScope} yet</Text>
                  <Text style={styles.emptySubtext}>
                    Be the first to join the leaderboard in your area!
                  </Text>
                </View>
              )}
            </View>
          </>
        )}
        
        {!settings.leaderboard_visible && (
          <View style={styles.optInPrompt}>
            <Ionicons name="trophy-outline" size={64} color="#2C2C2E" />
            <Text style={styles.optInTitle}>See How You Stack Up</Text>
            <Text style={styles.optInDescription}>
              Turn on rankings to compare your performance against other sales professionals in your state, region, or nationwide.
            </Text>
          </View>
        )}
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
  content: {
    padding: 16,
  },
  settingCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  settingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  settingIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  settingInfo: {
    flex: 1,
    marginRight: 12,
  },
  settingTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  settingDescription: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 4,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  scopeSelector: {
    flexDirection: 'row',
    gap: 8,
  },
  scopeButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#1C1C1E',
    paddingVertical: 14,
    borderRadius: 12,
  },
  scopeButtonActive: {
    backgroundColor: '#34C759',
  },
  scopeText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
  },
  scopeTextActive: {
    color: '#FFF',
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
  yourRankCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFD60A10',
    borderRadius: 16,
    padding: 20,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#FFD60A30',
  },
  yourRankIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FFD60A20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  yourRankInfo: {
    flex: 1,
  },
  yourRankLabel: {
    fontSize: 14,
    color: '#FFD60A',
    fontWeight: '500',
  },
  yourRankNumber: {
    fontSize: 36,
    fontWeight: 'bold',
    color: '#FFF',
  },
  yourRankTotal: {
    fontSize: 14,
    color: '#8E8E93',
  },
  leaderboardItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 12,
    marginBottom: 6,
  },
  currentUserItem: {
    borderWidth: 2,
    borderColor: '#007AFF',
  },
  rankBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  rankText: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  userInfo: {
    flex: 1,
  },
  userName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  userState: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  scoreValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFF',
  },
  emptyLeaderboard: {
    alignItems: 'center',
    paddingVertical: 32,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 4,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  optInPrompt: {
    alignItems: 'center',
    paddingVertical: 48,
  },
  optInTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#FFF',
    marginTop: 16,
    marginBottom: 8,
  },
  optInDescription: {
    fontSize: 15,
    color: '#8E8E93',
    textAlign: 'center',
    paddingHorizontal: 24,
    lineHeight: 22,
  },
});
