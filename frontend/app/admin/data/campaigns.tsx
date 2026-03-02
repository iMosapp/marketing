import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { format } from 'date-fns';
import api from '../../../services/api';

import { useThemeStore } from '../../../store/themeStore';
interface Campaign {
  _id: string;
  name: string;
  type?: string;
  status: string;
  sent_count?: number;
  open_count?: number;
  click_count?: number;
  store_name?: string;
  created_at: string;
}

export default function CampaignsDataScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadCampaigns = async () => {
    try {
      const response = await api.get('/admin/data/campaigns');
      setCampaigns(response.data || []);
    } catch (error) {
      console.error('Failed to load campaigns:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadCampaigns();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadCampaigns();
  }, []);

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active': return '#34C759';
      case 'completed': return '#007AFF';
      case 'draft': return colors.textSecondary;
      case 'paused': return '#FF9500';
      default: return colors.textSecondary;
    }
  };

  const renderCampaign = ({ item }: { item: Campaign }) => (
    <View style={styles.campaignItem}>
      <View style={styles.campaignIcon}>
        <Ionicons name="rocket" size={18} color="#FF3B30" />
      </View>
      <View style={styles.campaignContent}>
        <View style={styles.campaignHeader}>
          <Text style={styles.campaignName} numberOfLines={1}>{item.name}</Text>
          <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) + '20' }]}>
            <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>{item.status}</Text>
          </View>
        </View>
        {item.type && <Text style={styles.typeText}>{item.type}</Text>}
        {item.store_name && <Text style={styles.storeName}>{item.store_name}</Text>}
        <View style={styles.statsRow}>
          <View style={styles.stat}>
            <Ionicons name="paper-plane" size={12} color={colors.textSecondary} />
            <Text style={styles.statText}>{item.sent_count || 0}</Text>
          </View>
          <View style={styles.stat}>
            <Ionicons name="mail-open" size={12} color={colors.textSecondary} />
            <Text style={styles.statText}>{item.open_count || 0}</Text>
          </View>
          <View style={styles.stat}>
            <Ionicons name="hand-left" size={12} color={colors.textSecondary} />
            <Text style={styles.statText}>{item.click_count || 0}</Text>
          </View>
          <Text style={styles.date}>{format(new Date(item.created_at), 'MMM d')}</Text>
        </View>
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#FF3B30" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Campaigns</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{campaigns.length}</Text>
        </View>
      </View>

      <FlatList
        data={campaigns}
        renderItem={renderCampaign}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FF3B30" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="rocket-outline" size={64} color={colors.surface} />
            <Text style={styles.emptyText}>No campaigns yet</Text>
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
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  countBadge: {
    backgroundColor: '#FF3B3020',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#FF3B30',
    fontSize: 13,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  campaignItem: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  campaignIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#FF3B3020',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  campaignContent: {
    flex: 1,
  },
  campaignHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  campaignName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    flex: 1,
    marginRight: 8,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  typeText: {
    fontSize: 12,
    color: '#FF3B30',
    marginTop: 2,
  },
  storeName: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 12,
  },
  stat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  date: {
    fontSize: 12,
    color: '#6E6E73',
    marginLeft: 'auto',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 100,
  },
  emptyText: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 12,
  },
});
