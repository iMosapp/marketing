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
interface CardShare {
  _id: string;
  user_name?: string;
  contact_name?: string;
  share_type?: string;
  view_count?: number;
  created_at: string;
}

export default function CardSharesDataScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const [shares, setShares] = useState<CardShare[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadShares = async () => {
    try {
      const response = await api.get('/admin/data/card-shares');
      setShares(response.data || []);
    } catch (error) {
      console.error('Failed to load card shares:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadShares();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadShares();
  }, []);

  const renderShare = ({ item }: { item: CardShare }) => (
    <View style={styles.shareItem}>
      <View style={styles.shareIcon}>
        <Ionicons name="card" size={18} color="#FF2D55" />
      </View>
      <View style={styles.shareContent}>
        <View style={styles.shareHeader}>
          <Text style={styles.userName}>{item.user_name || 'Unknown'}</Text>
          <Text style={styles.date}>{format(new Date(item.created_at), 'MMM d, h:mm a')}</Text>
        </View>
        {item.contact_name && (
          <Text style={styles.contactName}>Shared with: {item.contact_name}</Text>
        )}
        <View style={styles.shareFooter}>
          {item.share_type && (
            <View style={styles.typeBadge}>
              <Text style={styles.typeText}>{item.share_type}</Text>
            </View>
          )}
          <View style={styles.viewCount}>
            <Ionicons name="eye" size={12} color={colors.textSecondary} />
            <Text style={styles.viewText}>{item.view_count || 0} views</Text>
          </View>
        </View>
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#FF2D55" />
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
        <Text style={styles.title}>Card Shares</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{shares.length}</Text>
        </View>
      </View>

      <FlatList
        data={shares}
        renderItem={renderShare}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FF2D55" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="card-outline" size={64} color={colors.surface} />
            <Text style={styles.emptyText}>No card shares yet</Text>
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
    backgroundColor: '#FF2D5520',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#FF2D55',
    fontSize: 13,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  shareItem: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  shareIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#FF2D5520',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  shareContent: {
    flex: 1,
  },
  shareHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  userName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  date: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  contactName: {
    fontSize: 13,
    color: colors.textTertiary,
    marginTop: 4,
  },
  shareFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
  typeBadge: {
    backgroundColor: '#FF2D5530',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  typeText: {
    fontSize: 11,
    color: '#FF2D55',
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  viewCount: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  viewText: {
    fontSize: 12,
    color: colors.textSecondary,
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
