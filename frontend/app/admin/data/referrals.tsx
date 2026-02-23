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

interface Referral {
  _id: string;
  referrer_name?: string;
  referee_name?: string;
  referee_phone?: string;
  status: string;
  store_name?: string;
  created_at: string;
}

export default function ReferralsDataScreen() {
  const router = useRouter();
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadReferrals = async () => {
    try {
      const response = await api.get('/admin/data/referrals');
      setReferrals(response.data || []);
    } catch (error) {
      console.error('Failed to load referrals:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadReferrals();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadReferrals();
  }, []);

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed': return '#34C759';
      case 'pending': return '#FF9500';
      case 'contacted': return '#007AFF';
      default: return '#8E8E93';
    }
  };

  const renderReferral = ({ item }: { item: Referral }) => (
    <View style={styles.referralItem}>
      <View style={styles.referralIcon}>
        <Ionicons name="git-network" size={18} color="#5856D6" />
      </View>
      <View style={styles.referralContent}>
        <View style={styles.referralHeader}>
          <Text style={styles.refereeName}>{item.referee_name || item.referee_phone || 'Unknown'}</Text>
          <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) + '20' }]}>
            <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>{item.status}</Text>
          </View>
        </View>
        <Text style={styles.referrerName}>Referred by: {item.referrer_name || 'Unknown'}</Text>
        {item.store_name && (
          <Text style={styles.storeName}>{item.store_name}</Text>
        )}
        <Text style={styles.date}>{format(new Date(item.created_at), 'MMM d, yyyy')}</Text>
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#5856D6" />
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
        <Text style={styles.title}>Referrals</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{referrals.length}</Text>
        </View>
      </View>

      <FlatList
        data={referrals}
        renderItem={renderReferral}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#5856D6" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="git-network-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No referrals yet</Text>
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
  countBadge: {
    backgroundColor: '#5856D620',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#5856D6',
    fontSize: 13,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  referralItem: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  referralIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#5856D620',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  referralContent: {
    flex: 1,
  },
  referralHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  refereeName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    flex: 1,
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
  referrerName: {
    fontSize: 13,
    color: '#AEAEB2',
    marginTop: 4,
  },
  storeName: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  date: {
    fontSize: 12,
    color: '#6E6E73',
    marginTop: 4,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 100,
  },
  emptyText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 12,
  },
});
