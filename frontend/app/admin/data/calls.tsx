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

interface Call {
  _id: string;
  contact_name?: string;
  contact_phone?: string;
  user_name?: string;
  direction: 'inbound' | 'outbound';
  duration?: number;
  status: string;
  created_at: string;
}

export default function CallsDataScreen() {
  const router = useRouter();
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadCalls = async () => {
    try {
      const response = await api.get('/admin/data/calls');
      setCalls(response.data || []);
    } catch (error) {
      console.error('Failed to load calls:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadCalls();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadCalls();
  }, []);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const renderCall = ({ item }: { item: Call }) => (
    <View style={styles.callItem}>
      <View style={[styles.directionIcon, { backgroundColor: item.direction === 'inbound' ? '#34C75920' : '#007AFF20' }]}>
        <Ionicons 
          name={item.direction === 'inbound' ? 'call' : 'call-outline'} 
          size={18} 
          color={item.direction === 'inbound' ? '#34C759' : '#007AFF'} 
        />
      </View>
      <View style={styles.callContent}>
        <View style={styles.callHeader}>
          <Text style={styles.contactName}>{item.contact_name || item.contact_phone || 'Unknown'}</Text>
          <Text style={styles.duration}>{formatDuration(item.duration)}</Text>
        </View>
        <Text style={styles.userName}>via {item.user_name || 'System'}</Text>
        <View style={styles.callFooter}>
          <Text style={[styles.status, { color: item.status === 'completed' ? '#34C759' : '#FF9500' }]}>
            {item.status}
          </Text>
          <Text style={styles.date}>{format(new Date(item.created_at), 'MMM d, h:mm a')}</Text>
        </View>
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#34C759" />
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
        <Text style={styles.title}>Calls</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{calls.length}</Text>
        </View>
      </View>

      <FlatList
        data={calls}
        renderItem={renderCall}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#34C759" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="call-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No calls yet</Text>
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
    backgroundColor: '#34C75920',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#34C759',
    fontSize: 13,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  callItem: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  directionIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  callContent: {
    flex: 1,
  },
  callHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  contactName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  duration: {
    fontSize: 14,
    fontWeight: '500',
    color: '#34C759',
  },
  userName: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  callFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
  },
  status: {
    fontSize: 12,
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  date: {
    fontSize: 12,
    color: '#8E8E93',
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
