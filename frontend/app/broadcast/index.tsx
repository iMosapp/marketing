import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
interface Broadcast {
  id: string;
  name: string;
  message: string;
  status: 'draft' | 'scheduled' | 'sending' | 'sent' | 'failed';
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  delivered_count?: number;
  undelivered_count?: number;
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
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    if (!user?._id) {
      setLoading(false);
      return;
    }
    
    try {
      const [broadcastsRes, statsRes] = await Promise.all([
        api.get(`/broadcast?user_id=${user._id}`),
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
  }, [user?._id]);

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
      case 'draft': return colors.textSecondary;
      case 'scheduled': return '#FF9500';
      case 'sending': return colors.accent;
      case 'sent': return '#34C759';
      case 'failed': return '#FF3B30';
      default: return colors.textSecondary;
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
              <Ionicons name="people" size={14} color={colors.textSecondary} />
              <Text style={styles.statText}>{item.recipient_count} recipients</Text>
            </View>
            {['sent', 'sending', 'failed'].includes(item.status) && item.sent_count > 0 && (
              <View style={styles.stat} testID={`broadcast-delivered-${item.id}`} {...({ dataSet: { testid: `broadcast-delivered-${item.id}` } } as any)}>
                <Ionicons name="checkmark-done" size={14} color="#34C759" />
                <Text style={styles.statText}>
                  {(item.delivered_count || 0) > 0
                    ? `${item.delivered_count} of ${item.sent_count} delivered`
                    : `${item.sent_count} sent`}
                </Text>
              </View>
            )}
            {(item.undelivered_count || 0) + (item.failed_count || 0) > 0 && (
              <View style={styles.stat}>
                <Ionicons name="alert-circle" size={14} color="#FF3B30" />
                <Text style={[styles.statText, { color: '#FF3B30' }]}>{(item.undelivered_count || 0) + (item.failed_count || 0)} failed</Text>
              </View>
            )}
            {item.media_urls?.length > 0 && (
              <View style={styles.stat}>
                <Ionicons name="image" size={14} color={colors.textSecondary} />
                <Text style={styles.statText}>{item.media_urls.length}</Text>
              </View>
            )}
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ScreenHeader title="Broadcasts" testID="broadcasts-header" />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScreenHeader title="Broadcasts" testID="broadcasts-header"
        right={<HeaderIconButton icon="add-circle" onPress={() => router.push('/broadcast/new')} testID="broadcasts-new-btn" />} />

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
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="megaphone-outline" size={56} color={colors.textTertiary} />
            <Text style={styles.emptyText}>No broadcasts yet</Text>
            <Text style={styles.emptySubtext}>Send one message to a group of customers at once.</Text>
            <TouchableOpacity onPress={() => router.push('/broadcast/new')} style={styles.emptyBtn} testID="broadcasts-empty-new-btn" {...({ dataSet: { testid: 'broadcasts-empty-new-btn' } } as any)}>
              <Text style={styles.emptyBtnText}>New Broadcast</Text>
            </TouchableOpacity>
          </View>
        )}
      />
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
  },
  statsBanner: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    marginHorizontal: 16,
    marginVertical: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 18,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 26,
    fontWeight: '800',
    color: colors.accent,
    marginBottom: 2,
  },
  statLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  statDivider: {
    width: 1,
    backgroundColor: colors.surface,
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  broadcastCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
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
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
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
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  broadcastMessage: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: 12,
  },
  statsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  stat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    marginTop: 14,
    marginBottom: 4,
  },
  emptySubtext: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  emptyBtn: {
    marginTop: 16,
    backgroundColor: colors.accent,
    borderRadius: 14,
    paddingHorizontal: 22,
    paddingVertical: 12,
  },
  emptyBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#000',
  },
});
