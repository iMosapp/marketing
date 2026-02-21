import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { format } from 'date-fns';
import api from '../../../services/api';

interface CongratsCard {
  _id: string;
  customer_name: string;
  customer_photo_url?: string;
  salesman_id: string;
  salesman_name?: string;
  store_id: string;
  store_name?: string;
  custom_message?: string;
  card_url?: string;
  created_at: string;
  view_count?: number;
  share_count?: number;
}

export default function CongratsCardsDataScreen() {
  const router = useRouter();
  const [cards, setCards] = useState<CongratsCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadCards = async () => {
    try {
      const response = await api.get('/admin/congrats-cards');
      setCards(response.data || []);
    } catch (error) {
      console.error('Failed to load congrats cards:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadCards();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadCards();
  }, []);

  const renderCard = ({ item }: { item: CongratsCard }) => (
    <TouchableOpacity
      style={styles.cardItem}
      onPress={() => item.card_url && router.push(item.card_url as any)}
    >
      <View style={styles.cardContent}>
        {item.customer_photo_url ? (
          <Image 
            source={{ uri: item.customer_photo_url }} 
            style={styles.customerPhoto}
          />
        ) : (
          <View style={styles.customerPhotoPlaceholder}>
            <Ionicons name="person" size={24} color="#C9A962" />
          </View>
        )}
        
        <View style={styles.cardInfo}>
          <Text style={styles.customerName}>{item.customer_name}</Text>
          <Text style={styles.salesmanName}>
            From: {item.salesman_name || 'Unknown'}
          </Text>
          <Text style={styles.storeName}>{item.store_name || ''}</Text>
          <Text style={styles.date}>
            {format(new Date(item.created_at), 'MMM d, yyyy')}
          </Text>
        </View>
        
        <View style={styles.statsContainer}>
          <View style={styles.stat}>
            <Ionicons name="eye" size={14} color="#8E8E93" />
            <Text style={styles.statText}>{item.view_count || 0}</Text>
          </View>
          <View style={styles.stat}>
            <Ionicons name="share" size={14} color="#8E8E93" />
            <Text style={styles.statText}>{item.share_count || 0}</Text>
          </View>
        </View>
        
        <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
      </View>
    </TouchableOpacity>
  );

  const renderHeader = () => (
    <View style={styles.headerStats}>
      <View style={styles.headerStatCard}>
        <Ionicons name="gift" size={24} color="#C9A962" />
        <Text style={styles.headerStatValue}>{cards.length}</Text>
        <Text style={styles.headerStatLabel}>Total Cards</Text>
      </View>
      <View style={styles.headerStatCard}>
        <Ionicons name="eye" size={24} color="#007AFF" />
        <Text style={styles.headerStatValue}>
          {cards.reduce((sum, c) => sum + (c.view_count || 0), 0)}
        </Text>
        <Text style={styles.headerStatLabel}>Total Views</Text>
      </View>
      <View style={styles.headerStatCard}>
        <Ionicons name="share" size={24} color="#34C759" />
        <Text style={styles.headerStatValue}>
          {cards.reduce((sum, c) => sum + (c.share_count || 0), 0)}
        </Text>
        <Text style={styles.headerStatLabel}>Total Shares</Text>
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>Congrats Cards</Text>
          <View style={styles.backButton} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#C9A962" />
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
        <Text style={styles.title}>Congrats Cards</Text>
        <View style={styles.backButton} />
      </View>

      <FlatList
        data={cards}
        keyExtractor={(item) => item._id}
        renderItem={renderCard}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="gift-outline" size={64} color="#3A3A3C" />
            <Text style={styles.emptyText}>No congrats cards yet</Text>
            <Text style={styles.emptySubtext}>
              Cards created by your team will appear here
            </Text>
          </View>
        }
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#C9A962"
          />
        }
        contentContainerStyle={styles.listContent}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
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
    width: 44,
    alignItems: 'flex-start',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    padding: 16,
  },
  headerStats: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  headerStatCard: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  headerStatValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
    marginTop: 8,
  },
  headerStatLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
  cardItem: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    marginBottom: 10,
    overflow: 'hidden',
  },
  cardContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
  },
  customerPhoto: {
    width: 50,
    height: 50,
    borderRadius: 25,
    marginRight: 12,
  },
  customerPhotoPlaceholder: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: 'rgba(201,169,98,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  cardInfo: {
    flex: 1,
  },
  customerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  salesmanName: {
    fontSize: 13,
    color: '#C9A962',
    marginBottom: 2,
  },
  storeName: {
    fontSize: 12,
    color: '#8E8E93',
  },
  date: {
    fontSize: 11,
    color: '#6E6E73',
    marginTop: 4,
  },
  statsContainer: {
    flexDirection: 'row',
    gap: 12,
    marginRight: 12,
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
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
});
