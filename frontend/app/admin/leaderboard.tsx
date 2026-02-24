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
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { adminAPI } from '../../services/api';

const METRICS = [
  { value: 'contacts_added', label: 'Contacts', icon: 'person-add' },
  { value: 'messages_sent', label: 'Messages', icon: 'chatbubbles' },
  { value: 'calls_made', label: 'Calls', icon: 'call' },
  { value: 'deals_closed', label: 'Deals', icon: 'trophy' },
];

export default function LeaderboardScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<string>('');
  const [selectedStore, setSelectedStore] = useState<string>('');
  const [selectedMetric, setSelectedMetric] = useState<string>('contacts_added');
  
  useFocusEffect(
    useCallback(() => {
      loadOrganizations();
    }, [])
  );
  
  useEffect(() => {
    if (selectedOrg) {
      loadStores(selectedOrg);
      loadLeaderboard(selectedOrg, selectedStore, selectedMetric);
    }
  }, [selectedOrg, selectedStore, selectedMetric]);
  
  const loadOrganizations = async () => {
    try {
      const data = await adminAPI.listOrganizations();
      setOrganizations(data);
      if (data.length > 0) {
        setSelectedOrg(data[0]._id);
      } else {
        setLoading(false);
      }
    } catch (error) {
      console.error('Failed to load organizations:', error);
      setLoading(false);
    }
  };
  
  const loadStores = async (orgId: string) => {
    try {
      const data = await adminAPI.listStores(orgId);
      setStores(data);
    } catch (error) {
      console.error('Failed to load stores:', error);
    }
  };
  
  const loadLeaderboard = async (orgId: string, storeId?: string, metric?: string) => {
    try {
      setLoading(true);
      const data = await adminAPI.getLeaderboard(orgId, storeId || undefined, metric);
      setLeaderboard(data.leaderboard || []);
    } catch (error) {
      console.error('Failed to load leaderboard:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (selectedOrg) {
      await loadLeaderboard(selectedOrg, selectedStore, selectedMetric);
    }
    setRefreshing(false);
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
  
  const renderLeaderboardItem = ({ item, index }: { item: any; index: number }) => {
    const rank = item.rank || index + 1;
    const rankStyle = getRankStyle(rank);
    const isCurrentUser = user?._id === item.user_id;
    
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
          {item.photo_url ? (
            <Image source={{ uri: item.photo_url }} style={styles.userAvatarPhoto} />
          ) : (
            <View style={styles.userAvatar}>
              <Text style={styles.avatarText}>
                {item.name?.split(' ').map((n: string) => n[0]).join('').slice(0, 2) || '?'}
              </Text>
            </View>
          )}
          <View style={styles.userDetails}>
            <Text style={styles.userName}>
              {item.name}
              {isCurrentUser && <Text style={styles.youBadge}> (You)</Text>}
            </Text>
            {item.store_name && (
              <Text style={styles.userStore}>{item.store_name}</Text>
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
  
  // Find current user's rank
  const currentUserRank = leaderboard.find(item => item.user_id === user?._id)?.rank;
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Leaderboard</Text>
        <View style={{ width: 28 }} />
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
      
      {/* Organization/Store Filter */}
      <View style={styles.filters}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterScroll}>
          {organizations.map(org => (
            <TouchableOpacity 
              key={org._id}
              style={[styles.filterChip, selectedOrg === org._id && styles.filterChipActive]}
              onPress={() => {
                setSelectedOrg(org._id);
                setSelectedStore('');
              }}
            >
              <Text style={[styles.filterText, selectedOrg === org._id && styles.filterTextActive]}>
                {org.name}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        
        {stores.length > 0 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterScroll}>
            <TouchableOpacity 
              style={[styles.filterChip, styles.filterChipSmall, !selectedStore && styles.filterChipActive]}
              onPress={() => setSelectedStore('')}
            >
              <Text style={[styles.filterText, !selectedStore && styles.filterTextActive]}>All Stores</Text>
            </TouchableOpacity>
            {stores.map(store => (
              <TouchableOpacity 
                key={store._id}
                style={[styles.filterChip, styles.filterChipSmall, selectedStore === store._id && styles.filterChipActive]}
                onPress={() => setSelectedStore(store._id)}
              >
                <Text style={[styles.filterText, selectedStore === store._id && styles.filterTextActive]}>
                  {store.name}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}
      </View>
      
      {/* Current User's Rank Banner */}
      {currentUserRank && (
        <View style={styles.yourRankBanner}>
          <Ionicons name="ribbon" size={20} color="#FFD60A" />
          <Text style={styles.yourRankText}>
            You're ranked <Text style={styles.yourRankNumber}>#{currentUserRank}</Text> in {getMetricInfo(selectedMetric).label}!
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
              <Ionicons name="trophy-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No rankings yet</Text>
              <Text style={styles.emptySubtext}>
                Start adding contacts, sending messages, and closing deals to climb the leaderboard!
              </Text>
            </View>
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
  filters: {
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  filterScroll: {
    paddingHorizontal: 16,
    paddingVertical: 4,
  },
  filterChip: {
    backgroundColor: '#1C1C1E',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 16,
    marginRight: 8,
  },
  filterChipSmall: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  filterChipActive: {
    backgroundColor: '#34C759',
  },
  filterText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  filterTextActive: {
    color: '#FFF',
    fontWeight: '600',
  },
  yourRankBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFD60A20',
    paddingVertical: 12,
    paddingHorizontal: 16,
    gap: 8,
  },
  yourRankText: {
    fontSize: 14,
    color: '#FFD60A',
  },
  yourRankNumber: {
    fontWeight: 'bold',
    fontSize: 16,
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
  userAvatarPhoto: {
    width: 40,
    height: 40,
    borderRadius: 20,
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
  userStore: {
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
