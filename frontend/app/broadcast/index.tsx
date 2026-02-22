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

  const renderBroadcast = ({ item }: { item: Broadcast }) => {
    const statusColor = getStatusColor(item.status);
    const statusIcon = getStatusIcon(item.status);
    
    return (
      <TouchableOpacity 
        style={styles.broadcastCard}
        onPress={() => router.push(`/broadcast/${item.id}`)}
        activeOpacity={0.7}
      >
        <View style={[styles.iconContainer, { backgroundColor: `${statusColor}20` }]}>
          <Ionicons name={statusIcon as any} size={24} color={statusColor} />
        </View>
        
        <View style={styles.broadcastContent}>
          <View style={styles.broadcastHeader}>
            <Text style={styles.broadcastName} numberOfLines={1}>{item.name}</Text>
            <View style={[styles.statusBadge, { backgroundColor: `${statusColor}20` }]}>
              <Text style={[styles.statusText, { color: statusColor }]}>
                {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
              </Text>
            </View>
          </View>
          
          <Text style={styles.broadcastMessage} numberOfLines={2}>{item.message}</Text>
          
          <View style={styles.statsRow}>
            <View style={styles.stat}>
              <Ionicons name="people" size={14} color="#8E8E93" />
              <Text style={styles.statText}>{item.recipient_count} recipients</Text>
            </View>
            {item.status === 'sent' && (
              <View style={styles.stat}>
                <Ionicons name="checkmark-done" size={14} color="#34C759" />
                <Text style={styles.statText}>{item.sent_count} sent</Text>
              </View>
            )}
            {item.media_urls?.length > 0 && (
              <View style={styles.stat}>
                <Ionicons name="image" size={14} color="#8E8E93" />
                <Text style={styles.statText}>{item.media_urls.length}</Text>
              </View>
            )}
          </View>
        </View>
      </TouchableOpacity>
    );
  };

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
    </Pressable>
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
      {/* Header - matching Campaigns style */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.title}>Broadcasts</Text>
        
        <TouchableOpacity
          onPress={() => router.push('/broadcast/new')}
          style={styles.addButton}
        >
          <Ionicons name="add-circle" size={32} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Stats Banner - matching Campaigns style */}
      <View style={styles.statsBanner}>
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{stats?.total_messages_sent || 0}</Text>
          <Text style={styles.statLabel}>Total Sent</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{stats?.scheduled || 0}</Text>
          <Text style={styles.statLabel}>Scheduled</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{stats?.draft || 0}</Text>
          <Text style={styles.statLabel}>Drafts</Text>
        </View>
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
            <Ionicons name="megaphone-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No broadcasts yet</Text>
            <Text style={styles.emptySubtext}>Create your first broadcast message</Text>
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
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
  },
  addButton: {
    padding: 4,
  },
  statsBanner: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    marginHorizontal: 16,
    marginVertical: 16,
    borderRadius: 12,
    padding: 20,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statDivider: {
    width: 1,
    backgroundColor: '#2C2C2E',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  broadcastCard: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'flex-start',
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  broadcastContent: {
    flex: 1,
  },
  broadcastHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  broadcastName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    flex: 1,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    gap: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  broadcastMessage: {
    fontSize: 13,
    color: '#8E8E93',
    lineHeight: 18,
    marginBottom: 12,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 16,
  },
  stat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 15,
    color: '#8E8E93',
    textAlign: 'center',
  },
});
