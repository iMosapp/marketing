import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../../store/authStore';
import api from '../../../services/api';

interface LeadSource {
  id: string;
  name: string;
  description: string;
  team_id: string;
  assignment_method: 'jump_ball' | 'round_robin' | 'weighted_round_robin';
  webhook_url: string;
  api_key: string;
  is_active: boolean;
  lead_count: number;
  created_at: string;
}

export default function LeadSourcesScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [sources, setSources] = useState<LeadSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSources = useCallback(async () => {
    if (!user?.store_id && !user?._id) {
      setLoading(false);
      return;
    }
    
    try {
      const storeId = user.store_id || user._id;
      const response = await api.get(`/lead-sources?store_id=${storeId}`);
      if (response.data.success) {
        setSources(response.data.lead_sources);
      }
    } catch (error) {
      console.error('Error fetching lead sources:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user]);

  useFocusEffect(
    useCallback(() => {
      fetchSources();
    }, [fetchSources])
  );

  const onRefresh = () => {
    setRefreshing(true);
    fetchSources();
  };

  const getAssignmentLabel = (method: string) => {
    switch (method) {
      case 'jump_ball': return 'Jump Ball';
      case 'round_robin': return 'Round Robin';
      case 'weighted_round_robin': return 'Weighted Round Robin';
      default: return method;
    }
  };

  const getAssignmentColor = (method: string) => {
    switch (method) {
      case 'jump_ball': return '#FF9500';
      case 'round_robin': return '#007AFF';
      case 'weighted_round_robin': return '#34C759';
      default: return '#8E8E93';
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      // For web, use navigator.clipboard
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        Alert.alert('Copied', `${label} copied to clipboard`);
      }
    } catch (error) {
      Alert.alert('Error', 'Could not copy to clipboard');
    }
  };

  const renderSource = ({ item }: { item: LeadSource }) => (
    <TouchableOpacity
      style={styles.sourceCard}
      onPress={() => router.push(`/admin/lead-sources/${item.id}`)}
      activeOpacity={0.7}
    >
      <View style={styles.sourceHeader}>
        <View style={styles.sourceInfo}>
          <View style={[styles.iconContainer, { backgroundColor: getAssignmentColor(item.assignment_method) + '20' }]}>
            <Ionicons name="git-branch-outline" size={24} color={getAssignmentColor(item.assignment_method)} />
          </View>
          <View style={styles.sourceText}>
            <Text style={styles.sourceName}>{item.name}</Text>
            <Text style={styles.sourceDescription} numberOfLines={1}>
              {item.description || 'No description'}
            </Text>
          </View>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: item.is_active ? '#34C75920' : '#FF3B3020' }]}>
          <Text style={[styles.statusText, { color: item.is_active ? '#34C759' : '#FF3B30' }]}>
            {item.is_active ? 'Active' : 'Inactive'}
          </Text>
        </View>
      </View>

      <View style={styles.sourceStats}>
        <View style={styles.statItem}>
          <Ionicons name="people" size={16} color="#8E8E93" />
          <Text style={styles.statText}>{item.lead_count} leads</Text>
        </View>
        <View style={[styles.methodBadge, { backgroundColor: getAssignmentColor(item.assignment_method) + '20' }]}>
          <Text style={[styles.methodText, { color: getAssignmentColor(item.assignment_method) }]}>
            {getAssignmentLabel(item.assignment_method)}
          </Text>
        </View>
      </View>

      <View style={styles.webhookSection}>
        <Text style={styles.webhookLabel}>Webhook URL:</Text>
        <TouchableOpacity 
          style={styles.webhookUrl}
          onPress={() => copyToClipboard(item.webhook_url, 'Webhook URL')}
        >
          <Text style={styles.webhookText} numberOfLines={1}>{item.webhook_url}</Text>
          <Ionicons name="copy-outline" size={16} color="#007AFF" />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
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
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Lead Sources</Text>
        <TouchableOpacity
          onPress={() => router.push('/admin/lead-sources/new')}
          style={styles.addButton}
        >
          <Ionicons name="add-circle" size={32} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <FlatList
        data={sources}
        renderItem={renderSource}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="git-branch-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No lead sources yet</Text>
            <Text style={styles.emptySubtext}>Create a lead source to receive leads from external systems</Text>
            <TouchableOpacity
              style={styles.createButton}
              onPress={() => router.push('/admin/lead-sources/new')}
            >
              <Ionicons name="add" size={20} color="#FFF" />
              <Text style={styles.createButtonText}>Create Lead Source</Text>
            </TouchableOpacity>
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
  listContent: {
    padding: 16,
    gap: 12,
  },
  sourceCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  sourceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  sourceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  sourceText: {
    flex: 1,
  },
  sourceName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  sourceDescription: {
    fontSize: 13,
    color: '#8E8E93',
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  sourceStats: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  methodBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  methodText: {
    fontSize: 12,
    fontWeight: '600',
  },
  webhookSection: {
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
    padding: 10,
  },
  webhookLabel: {
    fontSize: 11,
    color: '#8E8E93',
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  webhookUrl: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  webhookText: {
    fontSize: 12,
    color: '#007AFF',
    flex: 1,
    marginRight: 8,
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
    marginBottom: 24,
    paddingHorizontal: 32,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
    gap: 8,
  },
  createButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
