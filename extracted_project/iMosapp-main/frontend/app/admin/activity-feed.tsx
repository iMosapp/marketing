import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { adminAPI } from '../../services/api';
import { format, formatDistanceToNow } from 'date-fns';

interface Activity {
  type: string;
  icon: string;
  color: string;
  message: string;
  timestamp: string;
  user_id: string;
  entity_id: string;
}

export default function ActivityFeedScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [userRole, setUserRole] = useState<string>('user');
  
  useFocusEffect(
    useCallback(() => {
      if (user?._id) {
        loadActivities();
      }
    }, [user?._id])
  );
  
  const loadActivities = async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const data = await adminAPI.getActivityFeed(user._id, 50);
      setActivities(data.activities || []);
      setUserRole(data.user_role || 'user');
    } catch (error) {
      console.error('Failed to load activities:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadActivities();
    setRefreshing(false);
  };
  
  const formatTime = (timestamp: string) => {
    if (!timestamp) return '';
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
      
      if (diffHours < 24) {
        return formatDistanceToNow(date, { addSuffix: true });
      } else if (diffHours < 168) {
        return format(date, 'EEEE h:mm a');
      } else {
        return format(date, 'MMM d, yyyy');
      }
    } catch {
      return '';
    }
  };
  
  const getIconName = (iconName: string): keyof typeof Ionicons.glyphMap => {
    const iconMap: Record<string, keyof typeof Ionicons.glyphMap> = {
      'person-add': 'person-add',
      'chatbubble': 'chatbubble',
      'checkmark-circle': 'checkmark-circle',
      'rocket': 'rocket',
      'call': 'call',
      'trophy': 'trophy',
    };
    return iconMap[iconName] || 'ellipse';
  };
  
  const getRoleLabel = () => {
    switch (userRole) {
      case 'super_admin': return 'Platform-wide Activity';
      case 'org_admin': return 'Organization Activity';
      case 'store_manager': return 'Store Activity';
      default: return 'Your Activity';
    }
  };
  
  const renderActivity = ({ item }: { item: Activity }) => (
    <View style={styles.activityItem} data-testid={`activity-item-${item.type}`}>
      <View style={[styles.activityIcon, { backgroundColor: `${item.color}20` }]}>
        <Ionicons name={getIconName(item.icon)} size={20} color={item.color} />
      </View>
      <View style={styles.activityContent}>
        <Text style={styles.activityMessage}>{item.message}</Text>
        <Text style={styles.activityTime}>{formatTime(item.timestamp)}</Text>
      </View>
    </View>
  );
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Team Activity</Text>
        <TouchableOpacity onPress={onRefresh} style={styles.refreshButton}>
          <Ionicons name="refresh" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>
      
      {/* Role Badge */}
      <View style={styles.roleBadge}>
        <Ionicons 
          name={userRole === 'super_admin' ? 'globe' : userRole === 'org_admin' ? 'business' : userRole === 'store_manager' ? 'storefront' : 'person'} 
          size={16} 
          color="#8E8E93" 
        />
        <Text style={styles.roleBadgeText}>{getRoleLabel()}</Text>
      </View>
      
      {/* Activity List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          data={activities}
          renderItem={renderActivity}
          keyExtractor={(item, index) => `${item.entity_id}-${index}`}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="pulse-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No recent activity</Text>
              <Text style={styles.emptySubtext}>
                {userRole === 'user' 
                  ? 'Start adding contacts and sending messages to see your activity here.'
                  : 'Team activity will appear here as your team members take actions.'}
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
  refreshButton: {
    padding: 4,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
  },
  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    backgroundColor: '#1C1C1E',
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  roleBadgeText: {
    fontSize: 13,
    color: '#8E8E93',
    fontWeight: '500',
  },
  listContent: {
    padding: 16,
  },
  activityItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  activityIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  activityContent: {
    flex: 1,
  },
  activityMessage: {
    fontSize: 15,
    color: '#FFF',
    lineHeight: 20,
  },
  activityTime: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
  emptyContainer: {
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
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    paddingHorizontal: 32,
    lineHeight: 20,
  },
});
