import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TextInput,
  SectionList,
  Modal,
  ScrollView,
  Alert,
  Platform,
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
  org_admin: 'Admin',
  store_manager: 'Manager',
  user: 'User',
};

const ROLE_ORDER = ['super_admin', 'org_admin', 'store_manager', 'user'];

export default function UsersScreen() {
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [users, setUsers] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  
  // Add User Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newUserName, setNewUserName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPhone, setNewUserPhone] = useState('');
  const [newUserRole, setNewUserRole] = useState('user');
  const [sendInvite, setSendInvite] = useState(true);
  const [creating, setCreating] = useState(false);
  
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

  const toggleSection = (role: string) => {
    setCollapsedSections(prev => ({
      ...prev,
      [role]: !prev[role]
    }));
  };

  const resetAddForm = () => {
    setNewUserName('');
    setNewUserEmail('');
    setNewUserPhone('');
    setNewUserRole('user');
    setSendInvite(true);
  };

  const handleCreateUser = async () => {
    if (!newUserName.trim()) {
      Alert.alert('Error', 'Please enter a name');
      return;
    }
    if (!newUserEmail.trim() || !newUserEmail.includes('@')) {
      Alert.alert('Error', 'Please enter a valid email');
      return;
    }

    setCreating(true);
    try {
      const response = await api.post('/admin/users/create', {
        name: newUserName.trim(),
        email: newUserEmail.trim().toLowerCase(),
        phone: newUserPhone.trim() || undefined,
        role: newUserRole,
        send_invite: sendInvite,
      });

      if (response.data.success) {
        const message = sendInvite 
          ? `User created! Login email sent to ${newUserEmail}`
          : `User created with temporary password: ${response.data.temp_password}`;
        
        if (Platform.OS === 'web') {
          alert(message);
        } else {
          Alert.alert('Success', message);
        }
        
        setShowAddModal(false);
        resetAddForm();
        loadUsers();
      }
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to create user';
      Alert.alert('Error', message);
    } finally {
      setCreating(false);
    }
  };
  };

  // Filter and group users
  const sections = useMemo(() => {
    const filteredUsers = users.filter(user => {
      if (!searchQuery.trim()) return true;
      const query = searchQuery.toLowerCase();
      return (
        user.name?.toLowerCase().includes(query) ||
        user.email?.toLowerCase().includes(query)
      );
    });

    const grouped: Record<string, any[]> = {};
    
    filteredUsers.forEach(user => {
      const role = user.role || 'user';
      if (!grouped[role]) {
        grouped[role] = [];
      }
      grouped[role].push(user);
    });

    return ROLE_ORDER
      .filter(role => grouped[role]?.length > 0)
      .map(role => ({
        title: ROLE_LABELS[role] || role,
        role: role,
        color: ROLE_COLORS[role] || '#8E8E93',
        data: collapsedSections[role] ? [] : grouped[role],
        count: grouped[role].length,
      }));
  }, [users, searchQuery, collapsedSections]);

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
      </View>
      <View style={[styles.statusDot, { backgroundColor: item.is_active !== false ? '#34C759' : '#FF3B30' }]} />
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );

  const renderSectionHeader = ({ section }: { section: any }) => (
    <TouchableOpacity 
      style={styles.sectionHeader}
      onPress={() => toggleSection(section.role)}
      activeOpacity={0.7}
    >
      <View style={[styles.sectionIcon, { backgroundColor: section.color + '20' }]}>
        <Ionicons 
          name={
            section.role === 'super_admin' ? 'shield-checkmark' :
            section.role === 'org_admin' ? 'person-circle' :
            section.role === 'store_manager' ? 'briefcase' : 'person'
          } 
          size={18} 
          color={section.color} 
        />
      </View>
      <Text style={styles.sectionTitle}>{section.title}</Text>
      <View style={[styles.countBadge, { backgroundColor: section.color + '20' }]}>
        <Text style={[styles.countText, { color: section.color }]}>{section.count}</Text>
      </View>
      <Ionicons 
        name={collapsedSections[section.role] ? 'chevron-down' : 'chevron-up'} 
        size={20} 
        color="#8E8E93" 
      />
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Users</Text>
        <TouchableOpacity onPress={() => setShowAddModal(true)} style={styles.addButton}>
          <Ionicons name="person-add" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>
      
      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={20} color="#8E8E93" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by name or email..."
            placeholderTextColor="#8E8E93"
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={20} color="#8E8E93" />
            </TouchableOpacity>
          )}
        </View>
      </View>
      
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <SectionList
          sections={sections}
          renderItem={renderUser}
          renderSectionHeader={renderSectionHeader}
          keyExtractor={(item) => item._id}
          contentContainerStyle={styles.listContent}
          stickySectionHeadersEnabled={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="people-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>
                {searchQuery ? 'No users found' : 'No users yet'}
              </Text>
              {searchQuery && (
                <Text style={styles.emptySubtext}>Try a different search term</Text>
              )}
            </View>
          )}
        />
      )}

      {/* Add User Modal */}
      <Modal
        visible={showAddModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowAddModal(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => { setShowAddModal(false); resetAddForm(); }}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Add User</Text>
            <TouchableOpacity onPress={handleCreateUser} disabled={creating}>
              {creating ? (
                <ActivityIndicator size="small" color="#007AFF" />
              ) : (
                <Text style={styles.modalSave}>Create</Text>
              )}
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalContent}>
            <Text style={styles.inputLabel}>Name *</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Full name"
              placeholderTextColor="#8E8E93"
              value={newUserName}
              onChangeText={setNewUserName}
              autoCapitalize="words"
            />

            <Text style={styles.inputLabel}>Email *</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="email@example.com"
              placeholderTextColor="#8E8E93"
              value={newUserEmail}
              onChangeText={setNewUserEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />

            <Text style={styles.inputLabel}>Phone (optional)</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="+1 555 123 4567"
              placeholderTextColor="#8E8E93"
              value={newUserPhone}
              onChangeText={setNewUserPhone}
              keyboardType="phone-pad"
            />

            <Text style={styles.inputLabel}>Role</Text>
            <View style={styles.roleSelector}>
              {ROLE_ORDER.map((role) => (
                <TouchableOpacity
                  key={role}
                  style={[
                    styles.roleOption,
                    newUserRole === role && { backgroundColor: ROLE_COLORS[role] + '30', borderColor: ROLE_COLORS[role] }
                  ]}
                  onPress={() => setNewUserRole(role)}
                >
                  <Text style={[
                    styles.roleOptionText,
                    newUserRole === role && { color: ROLE_COLORS[role] }
                  ]}>
                    {ROLE_LABELS[role]}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity 
              style={styles.inviteToggle}
              onPress={() => setSendInvite(!sendInvite)}
            >
              <View style={[styles.checkbox, sendInvite && styles.checkboxChecked]}>
                {sendInvite && <Ionicons name="checkmark" size={16} color="#FFF" />}
              </View>
              <View style={styles.inviteToggleText}>
                <Text style={styles.inviteToggleTitle}>Send login invitation email</Text>
                <Text style={styles.inviteToggleSubtitle}>
                  User will receive an email with login instructions
                </Text>
              </View>
            </TouchableOpacity>

            {!sendInvite && (
              <View style={styles.warningBox}>
                <Ionicons name="warning" size={20} color="#FF9500" />
                <Text style={styles.warningText}>
                  A temporary password will be generated. Make sure to share it with the user securely.
                </Text>
              </View>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>
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
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
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
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
    marginTop: 8,
  },
  sectionIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    flex: 1,
  },
  countBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 8,
  },
  countText: {
    fontSize: 14,
    fontWeight: '600',
  },
  userCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 12,
    marginBottom: 6,
    marginLeft: 16,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  userAvatarText: {
    fontSize: 14,
    fontWeight: '600',
  },
  userInfo: {
    flex: 1,
    marginLeft: 12,
  },
  userName: {
    fontSize: 15,
    fontWeight: '500',
    color: '#FFF',
  },
  userEmail: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
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
  emptySubtext: {
    color: '#6E6E73',
    fontSize: 14,
    marginTop: 4,
  },
  inactiveCard: {
    opacity: 0.6,
    backgroundColor: '#1A1A1A',
  },
  inactiveText: {
    color: '#8E8E93',
  },
});
