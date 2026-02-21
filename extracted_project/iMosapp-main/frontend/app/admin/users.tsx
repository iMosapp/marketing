import React, { useState, useCallback } from 'react';
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
import * as Haptics from 'expo-haptics';
import api from '../../services/api';

const ROLE_COLORS: Record<string, string> = {
  super_admin: '#FF3B30',
  org_admin: '#FF9500',
  store_manager: '#34C759',
  user: '#007AFF',
};

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin',
  org_admin: 'Org Admin',
  store_manager: 'Manager',
  user: 'Sales Rep',
};

export default function UsersScreen() {
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [users, setUsers] = useState<any[]>([]);
  
  useFocusEffect(
    useCallback(() => {
      loadUsers();
    }, [])
  );
  
  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/hierarchy/users');
      setUsers(response.data.users || []);
    } catch (error) {
      console.error('Failed to load users:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await loadUsers();
    setRefreshing(false);
  };

  // Separate active and inactive users
  const activeUsers = users.filter(u => u.is_active !== false);
  const inactiveUsers = users.filter(u => u.is_active === false);

  const renderUser = ({ item }: { item: any }) => (
    <TouchableOpacity 
      style={[styles.userCard, item.is_active === false && styles.inactiveCard]}
      onPress={() => router.push(`/admin/users/${item._id}`)}
    >
      <View style={[styles.userAvatar, { backgroundColor: (ROLE_COLORS[item.role] || '#8E8E93') + '30' }]}>
        <Text style={[styles.userAvatarText, { color: ROLE_COLORS[item.role] || '#8E8E93' }]}>
          {item.name?.split(' ').map((n: string) => n[0]).join('').substring(0, 2) || '?'}
        </Text>
      </View>
      <View style={styles.userInfo}>
        <Text style={[styles.userName, item.is_active === false && styles.inactiveText]}>{item.name}</Text>
        <Text style={styles.userEmail}>{item.email}</Text>
        {item.organization_name && (
          <Text style={styles.userOrg}>{item.organization_name}</Text>
        )}
      </View>
      <View style={styles.userMeta}>
        <View style={[styles.roleBadge, { backgroundColor: (ROLE_COLORS[item.role] || '#8E8E93') + '20' }]}>
          <Text style={[styles.roleBadgeText, { color: ROLE_COLORS[item.role] || '#8E8E93' }]}>
            {ROLE_LABELS[item.role] || item.role}
          </Text>
        </View>
        <View style={[styles.statusDot, { backgroundColor: item.is_active !== false ? '#34C759' : '#FF3B30' }]} />
      </View>
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );

  const renderSectionHeader = (title: string, count: number) => (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionCount}>{count}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Users</Text>
        <View style={{ width: 40 }} />
      </View>
      
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          data={[
            { type: 'header', title: 'Active Users', count: activeUsers.length },
            ...activeUsers.map(u => ({ type: 'user', ...u })),
            ...(inactiveUsers.length > 0 ? [
              { type: 'divider' },
              { type: 'header', title: 'Inactive Users', count: inactiveUsers.length },
              ...inactiveUsers.map(u => ({ type: 'user', ...u })),
            ] : []),
          ]}
          renderItem={({ item }) => {
            if (item.type === 'header') {
              return renderSectionHeader(item.title, item.count);
            }
            if (item.type === 'divider') {
              return <View style={styles.sectionDivider} />;
            }
            return renderUser({ item });
          }}
          keyExtractor={(item, index) => item._id || `section-${index}`}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="people-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No users yet</Text>
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    padding: 16,
  },
  userCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  userAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  userAvatarText: {
    fontSize: 16,
    fontWeight: '600',
  },
  userInfo: {
    flex: 1,
    marginLeft: 12,
  },
  userName: {
    fontSize: 16,
    fontWeight: '500',
    color: '#FFF',
  },
  userEmail: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  userOrg: {
    fontSize: 12,
    color: '#007AFF',
    marginTop: 2,
  },
  userMeta: {
    alignItems: 'flex-end',
    marginRight: 8,
  },
  roleBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginBottom: 4,
  },
  roleBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    color: '#8E8E93',
    fontSize: 16,
    marginTop: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 4,
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionCount: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  sectionDivider: {
    height: 1,
    backgroundColor: '#2C2C2E',
    marginVertical: 24,
    marginHorizontal: 16,
  },
  inactiveCard: {
    opacity: 0.6,
    backgroundColor: '#1A1A1A',
  },
  inactiveText: {
    color: '#8E8E93',
  },
});
