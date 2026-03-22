import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { WebModal } from '../../components/WebModal';

import { useThemeStore } from '../../store/themeStore';
interface PendingUser {
  _id: string;
  name: string;
  email: string;
  phone?: string;
  requested_role: string;
  organization_id?: string;
  organization_name?: string;
  status: string;
  created_at: string;
}

interface Organization {
  _id: string;
  name: string;
}

interface Store {
  _id: string;
  name: string;
}

const ROLES = [
  { id: 'user', label: 'Sales Rep', color: '#007AFF' },
  { id: 'store_manager', label: 'Account Manager', color: '#34C759' },
  { id: 'org_admin', label: 'Org Admin', color: '#FF9500' },
];

export default function PendingUsersScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pendingUsers, setPendingUsers] = useState<PendingUser[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  
  // Approval modal
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<PendingUser | null>(null);
  const [approvalData, setApprovalData] = useState({
    role: 'user',
    organization_id: '',
    store_id: '',
    mvpline_number: '',
  });
  const [actionLoading, setActionLoading] = useState(false);
  
  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [])
  );
  
  const loadData = async () => {
    try {
      setLoading(true);
      const [usersRes, orgsRes] = await Promise.all([
        api.get('/admin/pending-users'),
        api.get('/admin/organizations'),
      ]);
      setPendingUsers(usersRes.data);
      setOrganizations(orgsRes.data);
    } catch (error) {
      console.error('Failed to load pending users:', error);
      showSimpleAlert('Error', 'Failed to load pending users');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };
  
  const loadStores = async (orgId: string) => {
    try {
      const res = await api.get(`/admin/stores?organization_id=${orgId}`);
      setStores(res.data);
    } catch (error) {
      console.error('Failed to load stores:', error);
    }
  };
  
  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };
  
  const openApprovalModal = (user: PendingUser) => {
    setSelectedUser(user);
    setApprovalData({
      role: 'user',
      organization_id: user.organization_id || '',
      store_id: '',
      mvpline_number: '',
    });
    if (user.organization_id) {
      loadStores(user.organization_id);
    }
    setShowApprovalModal(true);
  };
  
  const handleApprove = async () => {
    if (!selectedUser) return;
    
    setActionLoading(true);
    try {
      await api.put(`/admin/pending-users/${selectedUser._id}/approve`, approvalData);
      showSimpleAlert('Success', `${selectedUser.name} has been approved and configured`);
      setShowApprovalModal(false);
      loadData();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to approve user');
    } finally {
      setActionLoading(false);
    }
  };
  
  const handleReject = (user: PendingUser) => {
    showConfirm(
      'Reject User',
      `Are you sure you want to reject ${user.name}'s application? This will delete their account.`,
      async () => {
        try {
          await api.put(`/admin/pending-users/${user._id}/reject`);
          showSimpleAlert('User Rejected', 'The application has been rejected');
          loadData();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to reject user');
        }
      },
      undefined,
      'Reject',
      'Cancel'
    );
  };
  
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };
  
  const renderUser = ({ item }: { item: PendingUser }) => (
    <View style={styles.userCard} data-testid={`pending-user-${item._id}`}>
      <View style={styles.userHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {item.name?.split(' ').map(n => n[0]).join('').substring(0, 2) || '?'}
          </Text>
        </View>
        <View style={styles.userInfo}>
          <Text style={styles.userName}>{item.name}</Text>
          <Text style={styles.userEmail}>{item.email}</Text>
          {item.phone && <Text style={styles.userPhone}>{item.phone}</Text>}
        </View>
        <View style={styles.pendingBadge}>
          <Text style={styles.pendingBadgeText}>PENDING</Text>
        </View>
      </View>
      
      <View style={styles.userDetails}>
        <View style={styles.detailRow}>
          <Ionicons name="briefcase" size={16} color={colors.textSecondary} />
          <Text style={styles.detailLabel}>Requested Role:</Text>
          <Text style={styles.detailValue}>{item.requested_role || 'Not specified'}</Text>
        </View>
        
        <View style={styles.detailRow}>
          <Ionicons name="business" size={16} color={colors.textSecondary} />
          <Text style={styles.detailLabel}>Organization:</Text>
          <Text style={styles.detailValue}>{item.organization_name || 'Not assigned'}</Text>
        </View>
        
        <View style={styles.detailRow}>
          <Ionicons name="time" size={16} color={colors.textSecondary} />
          <Text style={styles.detailLabel}>Applied:</Text>
          <Text style={styles.detailValue}>{formatDate(item.created_at)}</Text>
        </View>
      </View>
      
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.rejectButton}
          onPress={() => handleReject(item)}
          data-testid={`reject-btn-${item._id}`}
        >
          <Ionicons name="close-circle" size={20} color="#FF3B30" />
          <Text style={styles.rejectButtonText}>Reject</Text>
        </TouchableOpacity>
        
        <TouchableOpacity
          style={styles.approveButton}
          onPress={() => openApprovalModal(item)}
          data-testid={`approve-btn-${item._id}`}
        >
          <Ionicons name="checkmark-circle" size={20} color={colors.text} />
          <Text style={styles.approveButtonText}>Configure & Approve</Text>
        </TouchableOpacity>
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
        <Text style={styles.title}>Pending Users</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{pendingUsers.length}</Text>
        </View>
      </View>
      
      {/* Content */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          data={pendingUsers}
          renderItem={renderUser}
          keyExtractor={item => item._id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="checkmark-circle" size={64} color="#34C759" />
              <Text style={styles.emptyTitle}>All Caught Up!</Text>
              <Text style={styles.emptyText}>No pending user applications</Text>
            </View>
          )}
        />
      )}
      
      {/* Approval Modal */}
      <WebModal visible={showApprovalModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Configure & Approve</Text>
              <TouchableOpacity onPress={() => setShowApprovalModal(false)}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            
            <ScrollView style={styles.modalBody}>
              {selectedUser && (
                <>
                  <View style={styles.userSummary}>
                    <Text style={styles.userSummaryName}>{selectedUser.name}</Text>
                    <Text style={styles.userSummaryEmail}>{selectedUser.email}</Text>
                    <Text style={styles.userSummaryRole}>
                      Requested: {selectedUser.requested_role}
                    </Text>
                  </View>
                  
                  {/* Role Selection */}
                  <Text style={styles.fieldLabel}>Assign Role</Text>
                  <View style={styles.roleOptions}>
                    {ROLES.map(role => (
                      <TouchableOpacity
                        key={role.id}
                        style={[
                          styles.roleOption,
                          approvalData.role === role.id && styles.roleOptionSelected,
                          { borderColor: role.color }
                        ]}
                        onPress={() => setApprovalData({ ...approvalData, role: role.id })}
                      >
                        <Text style={[
                          styles.roleOptionText,
                          approvalData.role === role.id && { color: role.color }
                        ]}>
                          {role.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  
                  {/* Organization */}
                  <Text style={styles.fieldLabel}>Organization</Text>
                  <View style={styles.pickerWrapper}>
                    {organizations.map(org => (
                      <TouchableOpacity
                        key={org._id}
                        style={[
                          styles.orgOption,
                          approvalData.organization_id === org._id && styles.orgOptionSelected
                        ]}
                        onPress={() => {
                          setApprovalData({ ...approvalData, organization_id: org._id, store_id: '' });
                          loadStores(org._id);
                        }}
                      >
                        <Text style={[
                          styles.orgOptionText,
                          approvalData.organization_id === org._id && styles.orgOptionTextSelected
                        ]}>
                          {org.name}
                        </Text>
                        {approvalData.organization_id === org._id && (
                          <Ionicons name="checkmark" size={18} color="#007AFF" />
                        )}
                      </TouchableOpacity>
                    ))}
                  </View>
                  
                  {/* Store */}
                  {stores.length > 0 && (
                    <>
                      <Text style={styles.fieldLabel}>Assign to Store (Optional)</Text>
                      <View style={styles.pickerWrapper}>
                        <TouchableOpacity
                          style={[
                            styles.orgOption,
                            !approvalData.store_id && styles.orgOptionSelected
                          ]}
                          onPress={() => setApprovalData({ ...approvalData, store_id: '' })}
                        >
                          <Text style={[
                            styles.orgOptionText,
                            !approvalData.store_id && styles.orgOptionTextSelected
                          ]}>
                            No Store (Org Level)
                          </Text>
                        </TouchableOpacity>
                        {stores.map(store => (
                          <TouchableOpacity
                            key={store._id}
                            style={[
                              styles.orgOption,
                              approvalData.store_id === store._id && styles.orgOptionSelected
                            ]}
                            onPress={() => setApprovalData({ ...approvalData, store_id: store._id })}
                          >
                            <Text style={[
                              styles.orgOptionText,
                              approvalData.store_id === store._id && styles.orgOptionTextSelected
                            ]}>
                              {store.name}
                            </Text>
                            {approvalData.store_id === store._id && (
                              <Ionicons name="checkmark" size={18} color="#007AFF" />
                            )}
                          </TouchableOpacity>
                        ))}
                      </View>
                    </>
                  )}
                  
                  {/* Phone Number */}
                  <Text style={styles.fieldLabel}>i'M On Social</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="+1 (555) 123-4567"
                    placeholderTextColor={colors.textSecondary}
                    value={approvalData.mvpline_number}
                    onChangeText={(text) => setApprovalData({ ...approvalData, mvpline_number: text })}
                    keyboardType="phone-pad"
                  />
                  <Text style={styles.hint}>
                    Assign a Twilio number for direct messaging. Can be configured later.
                  </Text>
                </>
              )}
            </ScrollView>
            
            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.cancelModalButton}
                onPress={() => setShowApprovalModal(false)}
              >
                <Text style={styles.cancelModalButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.approveModalButton}
                onPress={handleApprove}
                disabled={actionLoading}
              >
                {actionLoading ? (
                  <ActivityIndicator color={colors.text} />
                ) : (
                  <>
                    <Ionicons name="checkmark" size={20} color={colors.text} />
                    <Text style={styles.approveModalButtonText}>Approve User</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </WebModal>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
    gap: 12,
  },
  backButton: {
    width: 40,
  },
  title: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  countBadge: {
    backgroundColor: '#FF3B30',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    minWidth: 28,
    alignItems: 'center',
  },
  countText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    padding: 16,
    paddingBottom: 100,
  },
  userCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  userHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#FF950030',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  avatarText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FF9500',
  },
  userInfo: {
    flex: 1,
  },
  userName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  userEmail: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  userPhone: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  pendingBadge: {
    backgroundColor: '#FF950030',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  pendingBadgeText: {
    color: '#FF9500',
    fontSize: 12,
    fontWeight: '700',
  },
  userDetails: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    gap: 8,
    marginBottom: 12,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  detailLabel: {
    color: colors.textSecondary,
    fontSize: 15,
  },
  detailValue: {
    flex: 1,
    color: colors.text,
    fontSize: 15,
    fontWeight: '500',
    textAlign: 'right',
  },
  actions: {
    flexDirection: 'row',
    gap: 10,
  },
  rejectButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#FF3B3020',
    gap: 6,
  },
  rejectButtonText: {
    color: '#FF3B30',
    fontSize: 17,
    fontWeight: '600',
  },
  approveButton: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#34C759',
    gap: 6,
  },
  approveButtonText: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    fontSize: 21,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  emptyText: {
    fontSize: 17,
    color: colors.textSecondary,
    marginTop: 6,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '85%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  modalTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  modalBody: {
    padding: 16,
    maxHeight: 450,
  },
  userSummary: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    alignItems: 'center',
  },
  userSummaryName: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  userSummaryEmail: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 4,
  },
  userSummaryRole: {
    fontSize: 15,
    color: '#FF9500',
    marginTop: 8,
    fontWeight: '500',
  },
  fieldLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    marginBottom: 10,
    marginTop: 16,
  },
  roleOptions: {
    flexDirection: 'row',
    gap: 8,
  },
  roleOption: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: '#3C3C3E',
    alignItems: 'center',
  },
  roleOptionSelected: {
    backgroundColor: '#007AFF20',
  },
  roleOptionText: {
    color: colors.textSecondary,
    fontSize: 15,
    fontWeight: '600',
  },
  pickerWrapper: {
    gap: 6,
  },
  orgOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 12,
    borderRadius: 10,
    backgroundColor: colors.surface,
  },
  orgOptionSelected: {
    backgroundColor: '#007AFF20',
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  orgOptionText: {
    color: colors.text,
    fontSize: 17,
  },
  orgOptionTextSelected: {
    color: '#007AFF',
    fontWeight: '600',
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    color: colors.text,
  },
  hint: {
    fontSize: 14,
    color: colors.textTertiary,
    marginTop: 6,
  },
  modalFooter: {
    flexDirection: 'row',
    padding: 16,
    gap: 10,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
  },
  cancelModalButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: colors.surface,
    alignItems: 'center',
  },
  cancelModalButtonText: {
    color: colors.textSecondary,
    fontSize: 18,
    fontWeight: '600',
  },
  approveModalButton: {
    flex: 2,
    flexDirection: 'row',
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#34C759',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  approveModalButtonText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
  },
});
