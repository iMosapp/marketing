import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Pressable,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { format } from 'date-fns';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';

interface Broadcast {
  id: string;
  name: string;
  message: string;
  status: 'draft' | 'scheduled' | 'sending' | 'sent' | 'failed';
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  scheduled_at: string | null;
  sent_at: string | null;
  created_at: string;
  media_urls: string[];
}

interface Stats {
  draft: number;
  scheduled: number;
  sending: number;
  sent: number;
  failed: number;
  total_messages_sent: number;
  total_messages_failed: number;
}

export default function BroadcastListScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<string>('all');

  const fetchData = useCallback(async () => {
    if (!user?._id) {
      setLoading(false);
      return;
    }
    
    try {
      const [broadcastsRes, statsRes] = await Promise.all([
        api.get(`/broadcast?user_id=${user._id}${filter !== 'all' ? `&status=${filter}` : ''}`),
        api.get(`/broadcast/stats?user_id=${user._id}`)
      ]);
      
      if (broadcastsRes.data.success) {
        setBroadcasts(broadcastsRes.data.broadcasts);
      }
      if (statsRes.data.success) {
        setStats(statsRes.data.stats);
      }
    } catch (error) {
      console.error('Error fetching broadcasts:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id, filter]);

  useFocusEffect(
    useCallback(() => {
      fetchData();
    }, [fetchData])
  );

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft': return '#8E8E93';
      case 'scheduled': return '#FF9500';
      case 'sending': return '#007AFF';
      case 'sent': return '#34C759';
      case 'failed': return '#FF3B30';
      default: return '#8E8E93';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'draft': return 'document-outline';
      case 'scheduled': return 'time-outline';
      case 'sending': return 'paper-plane-outline';
      case 'sent': return 'checkmark-circle-outline';
      case 'failed': return 'alert-circle-outline';
      default: return 'document-outline';
    }
  };

  const renderBroadcast = ({ item }: { item: Broadcast }) => (
    <Pressable
      style={styles.broadcastCard}
      onPress={() => router.push(`/broadcast/${item.id}`)}
      testID={`broadcast-card-${item.id}`}
    >
      <View style={styles.broadcastHeader}>
        <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(item.status)}20` }]}>
          <Ionicons name={getStatusIcon(item.status)} size={14} color={getStatusColor(item.status)} />
          <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>
            {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
          </Text>
        </View>
        {item.media_urls?.length > 0 && (
          <View style={styles.mediaIndicator}>
            <Ionicons name="image" size={14} color="#8E8E93" />
          </View>
        )}
      </View>
      
      <Text style={styles.broadcastName}>{item.name}</Text>
      <Text style={styles.broadcastMessage} numberOfLines={2}>{item.message}</Text>
      
      <View style={styles.broadcastMeta}>
        <View style={styles.metaItem}>
          <Ionicons name="people-outline" size={14} color="#8E8E93" />
          <Text style={styles.metaText}>{item.recipient_count} recipients</Text>
        </View>
        
        {item.status === 'sent' && (
          <View style={styles.metaItem}>
            <Ionicons name="checkmark-done" size={14} color="#34C759" />
            <Text style={styles.metaText}>{item.sent_count} sent</Text>
          </View>
        )}
        
        {item.scheduled_at && item.status === 'scheduled' && (
          <View style={styles.metaItem}>
            <Ionicons name="calendar-outline" size={14} color="#FF9500" />
            <Text style={styles.metaText}>
              {format(new Date(item.scheduled_at), 'MMM d, h:mm a')}
            </Text>
          </View>
        )}
        
        {item.sent_at && item.status === 'sent' && (
          <View style={styles.metaItem}>
            <Ionicons name="time-outline" size={14} color="#8E8E93" />
            <Text style={styles.metaText}>
              Sent {format(new Date(item.sent_at), 'MMM d, h:mm a')}
            </Text>
          </View>
        )}
      </View>
    </Pressable>
  );

  const FilterButton = ({ value, label, count }: { value: string; label: string; count?: number }) => (
    <Pressable
      style={[styles.filterButton, filter === value && styles.filterButtonActive]}
      onPress={() => setFilter(value)}
      testID={`filter-btn-${value}`}
    >
      <Text style={[styles.filterButtonText, filter === value && styles.filterButtonTextActive]}>
        {label}
      </Text>
      {count !== undefined && count > 0 && (
        <View style={[styles.filterCount, filter === value && styles.filterCountActive]}>
          <Text style={[styles.filterCountText, filter === value && styles.filterCountTextActive]}>
            {count}
          </Text>
        </View>
      )}
    </WebSafePressable>
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

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <WebSafePressable onPress={() => router.back()} style={styles.backButton} testID="back-btn">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </WebSafePressable>
        <Text style={styles.headerTitle}>Broadcasts</Text>
        {IS_WEB ? (
          <button
            type="button"
            onClick={() => router.push('/broadcast/new')}
            data-testid="new-broadcast-btn"
            style={{
              background: '#007AFF',
              border: 'none',
              borderRadius: 20,
              padding: '8px 16px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Ionicons name="add" size={20} color="#FFF" />
            <Text style={{ color: '#FFF', fontWeight: '600' }}>New</Text>
          </button>
        ) : (
          <TouchableOpacity
            style={styles.newButton}
            onPress={() => router.push('/broadcast/new')}
          >
            <Ionicons name="add" size={20} color="#FFF" />
            <Text style={styles.newButtonText}>New</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Stats Cards */}
      {stats && (
        <View style={styles.statsContainer}>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{stats.total_messages_sent}</Text>
            <Text style={styles.statLabel}>Total Sent</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{stats.scheduled}</Text>
            <Text style={styles.statLabel}>Scheduled</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{stats.draft}</Text>
            <Text style={styles.statLabel}>Drafts</Text>
          </View>
        </View>
      )}

      {/* Filters */}
      <View style={styles.filtersContainer}>
        <FilterButton value="all" label="All" />
        <FilterButton value="draft" label="Drafts" count={stats?.draft} />
        <FilterButton value="scheduled" label="Scheduled" count={stats?.scheduled} />
        <FilterButton value="sent" label="Sent" count={stats?.sent} />
      </View>

      <FlatList
        data={broadcasts}
        renderItem={renderBroadcast}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <View style={styles.emptyIcon}>
              <Ionicons name="megaphone-outline" size={48} color="#3A3A3C" />
            </View>
            <Text style={styles.emptyTitle}>No broadcasts yet</Text>
            <Text style={styles.emptySubtitle}>
              Create your first broadcast to send messages to multiple contacts at once
            </Text>
            <WebSafePressable
              style={styles.createButton}
              onPress={() => router.push('/broadcast/new')}
              testID="create-broadcast-btn"
            >
              <Text style={styles.createButtonText}>Create Broadcast</Text>
            </WebSafePressable>
          </View>
        )}
      />
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
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  newButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 6,
  },
  newButtonText: {
    color: '#FFF',
    fontWeight: '600',
  },
  statsContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 16,
    gap: 12,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#007AFF',
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
  filtersContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 8,
  },
  filterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
    gap: 6,
  },
  filterButtonActive: {
    backgroundColor: '#007AFF',
  },
  filterButtonText: {
    fontSize: 14,
    color: '#8E8E93',
  },
  filterButtonTextActive: {
    color: '#FFF',
  },
  filterCount: {
    backgroundColor: '#3A3A3C',
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  filterCountActive: {
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  filterCountText: {
    fontSize: 12,
    color: '#8E8E93',
  },
  filterCountTextActive: {
    color: '#FFF',
  },
  listContent: {
    padding: 16,
    paddingTop: 8,
  },
  broadcastCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  broadcastHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  mediaIndicator: {
    padding: 4,
  },
  broadcastName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  broadcastMessage: {
    fontSize: 14,
    color: '#8E8E93',
    lineHeight: 20,
    marginBottom: 12,
  },
  broadcastMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  metaText: {
    fontSize: 12,
    color: '#8E8E93',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 60,
    paddingHorizontal: 32,
  },
  emptyIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    marginBottom: 24,
  },
  createButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
  },
  createButtonText: {
    color: '#FFF',
    fontWeight: '600',
    fontSize: 16,
  },
});
