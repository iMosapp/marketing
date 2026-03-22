import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { WebModal } from '../../components/WebModal';

import { useThemeStore } from '../../store/themeStore';
interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  phone?: string;
}

interface TransferPreview {
  from_user: User;
  items_to_transfer: {
    contacts: number;
    conversations: number;
    tasks: number;
    campaign_enrollments: number;
  };
  total: number;
}

interface TransferHistory {
  id: string;
  from_user: string;
  to_user: string;
  initiated_by: string;
  reason?: string;
  transfers: {
    contacts?: number;
    conversations?: number;
    tasks?: number;
    campaign_enrollments?: number;
  };
  status: string;
  started_at?: string;
  completed_at?: string;
}

export default function BulkTransferPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [transferHistory, setTransferHistory] = useState<TransferHistory[]>([]);
  
  // Transfer state
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [selectedFromUser, setSelectedFromUser] = useState<User | null>(null);
  const [selectedToUser, setSelectedToUser] = useState<User | null>(null);
  const [transferPreview, setTransferPreview] = useState<TransferPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [transferring, setTransferring] = useState(false);
  
  // Transfer options
  const [transferContacts, setTransferContacts] = useState(true);
  const [transferConversations, setTransferConversations] = useState(true);
  const [transferTasks, setTransferTasks] = useState(true);
  const [transferCampaigns, setTransferCampaigns] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [usersRes, historyRes] = await Promise.all([
        api.get(`/admin/team/users?user_id=${user?._id}`),
        api.get(`/admin/team/bulk-transfer/history?user_id=${user?._id}`),
      ]);
      setUsers(usersRes.data);
      setTransferHistory(historyRes.data);
    } catch (error) {
      console.error('Error loading transfer data:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const loadTransferPreview = async (fromUser: User) => {
    setLoadingPreview(true);
    try {
      const res = await api.get(
        `/admin/team/bulk-transfer/preview?from_user_id=${fromUser.id}&user_id=${user?._id}`
      );
      setTransferPreview(res.data);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to load transfer preview');
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleSelectFromUser = (u: User) => {
    setSelectedFromUser(u);
    setSelectedToUser(null);
    loadTransferPreview(u);
  };

  const handleExecuteTransfer = async () => {
    if (!selectedFromUser || !selectedToUser) {
      showSimpleAlert('Error', 'Please select both source and destination users');
      return;
    }
    
    showConfirm(
      'Confirm Transfer',
      `Transfer all data from ${selectedFromUser.name} to ${selectedToUser.name}? This cannot be undone.`,
      async () => {
        setTransferring(true);
        try {
          const result = await api.post(`/admin/team/bulk-transfer?user_id=${user?._id}`, {
            from_user_id: selectedFromUser.id,
            to_user_id: selectedToUser.id,
            transfer_contacts: transferContacts,
            transfer_conversations: transferConversations,
            transfer_tasks: transferTasks,
            transfer_campaigns: transferCampaigns,
            reason: 'Bulk transfer initiated from admin panel',
          });
          
          showSimpleAlert('Success', result.data.message);
          setShowTransferModal(false);
          resetTransferState();
          loadData();
        } catch (error: any) {
          showSimpleAlert('Error', error.response?.data?.detail || 'Transfer failed');
        } finally {
          setTransferring(false);
        }
      }
    );
  };

  const resetTransferState = () => {
    setSelectedFromUser(null);
    setSelectedToUser(null);
    setTransferPreview(null);
    setTransferContacts(true);
    setTransferConversations(true);
    setTransferTasks(true);
    setTransferCampaigns(true);
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getAvailableToUsers = () => {
    if (!selectedFromUser) return [];
    return users.filter(u => u.id !== selectedFromUser.id);
  };

  const renderUserSelector = (
    label: string,
    selected: User | null,
    onSelect: (u: User) => void,
    availableUsers: User[]
  ) => (
    <View style={styles.selectorSection}>
      <Text style={styles.selectorLabel}>{label}</Text>
      {selected ? (
        <TouchableOpacity
          style={styles.selectedUser}
          onPress={() => onSelect(null as any)}
        >
          <View style={styles.userAvatar}>
            <Text style={styles.userAvatarText}>
              {selected.name.split(' ').map(n => n[0]).join('')}
            </Text>
          </View>
          <View style={styles.userInfo}>
            <Text style={styles.userName}>{selected.name}</Text>
            <Text style={styles.userEmail}>{selected.email}</Text>
          </View>
          <Ionicons name="close-circle" size={24} color={colors.textSecondary} />
        </TouchableOpacity>
      ) : (
        <ScrollView style={styles.userList} nestedScrollEnabled>
          {availableUsers.map((u) => (
            <TouchableOpacity
              key={u.id}
              style={styles.userOption}
              onPress={() => onSelect(u)}
              data-testid={`select-${label.toLowerCase().replace(' ', '-')}-${u.id}`}
            >
              <View style={styles.userAvatar}>
                <Text style={styles.userAvatarText}>
                  {u.name.split(' ').map(n => n[0]).join('')}
                </Text>
              </View>
              <View style={styles.userInfo}>
                <Text style={styles.userName}>{u.name}</Text>
                <Text style={styles.userEmail}>{u.email}</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
    </View>
  );

  const renderTransferOption = (
    label: string,
    count: number,
    enabled: boolean,
    onToggle: () => void
  ) => (
    <TouchableOpacity
      style={[styles.optionRow, enabled && styles.optionRowEnabled]}
      onPress={onToggle}
    >
      <View style={styles.optionInfo}>
        <Text style={styles.optionLabel}>{label}</Text>
        <Text style={styles.optionCount}>{count} items</Text>
      </View>
      <View style={[styles.checkbox, enabled && styles.checkboxEnabled]}>
        {enabled && <Ionicons name="checkmark" size={16} color={colors.text} />}
      </View>
    </TouchableOpacity>
  );

  const renderHistoryItem = (item: TransferHistory) => (
    <View key={item.id} style={styles.historyItem}>
      <View style={styles.historyHeader}>
        <View style={styles.historyFlow}>
          <Text style={styles.historyUser}>{item.from_user}</Text>
          <Ionicons name="arrow-forward" size={16} color={colors.textSecondary} />
          <Text style={styles.historyUser}>{item.to_user}</Text>
        </View>
        <View style={[
          styles.statusBadge,
          item.status === 'completed' && styles.statusCompleted,
          item.status === 'in_progress' && styles.statusProgress,
        ]}>
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>
      
      <View style={styles.historyStats}>
        {item.transfers.contacts && (
          <Text style={styles.historyStatItem}>{item.transfers.contacts} contacts</Text>
        )}
        {item.transfers.conversations && (
          <Text style={styles.historyStatItem}>{item.transfers.conversations} conversations</Text>
        )}
        {item.transfers.tasks && (
          <Text style={styles.historyStatItem}>{item.transfers.tasks} tasks</Text>
        )}
      </View>
      
      <View style={styles.historyFooter}>
        <Text style={styles.historyDate}>{formatDate(item.completed_at || item.started_at)}</Text>
        <Text style={styles.historyInitiator}>by {item.initiated_by}</Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Bulk Transfer</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {loading ? (
          <ActivityIndicator color="#007AFF" style={{ marginTop: 40 }} />
        ) : (
          <>
            {/* Info Banner */}
            <View style={styles.infoBanner}>
              <Ionicons name="swap-horizontal" size={24} color="#FF9500" />
              <View style={styles.infoContent}>
                <Text style={styles.infoTitle}>Transfer Customer Data</Text>
                <Text style={styles.infoText}>
                  Transfer all contacts, conversations, tasks, and campaigns from one user to another.
                  Use this when a team member leaves or changes roles.
                </Text>
              </View>
            </View>

            {/* Start Transfer Button */}
            <TouchableOpacity
              style={styles.startButton}
              onPress={() => setShowTransferModal(true)}
              data-testid="start-transfer-btn"
            >
              <Ionicons name="swap-horizontal-outline" size={24} color={colors.text} />
              <Text style={styles.startButtonText}>Start New Transfer</Text>
            </TouchableOpacity>

            {/* Transfer History */}
            <View style={styles.historySection}>
              <Text style={styles.sectionTitle}>Transfer History</Text>
              
              {transferHistory.length === 0 ? (
                <View style={styles.emptyHistory}>
                  <Ionicons name="time-outline" size={48} color={colors.surface} />
                  <Text style={styles.emptyText}>No transfers yet</Text>
                </View>
              ) : (
                transferHistory.map(renderHistoryItem)
              )}
            </View>

            <View style={{ height: 100 }} />
          </>
        )}
      </ScrollView>

      {/* Transfer Modal */}
      <WebModal visible={showTransferModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Bulk Transfer</Text>
              <TouchableOpacity onPress={() => {
                setShowTransferModal(false);
                resetTransferState();
              }}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            
            <ScrollView style={styles.modalBody}>
              {/* Step 1: Select From User */}
              {renderUserSelector(
                'Transfer FROM',
                selectedFromUser,
                handleSelectFromUser,
                users
              )}
              
              {/* Step 2: Show Preview & Select To User */}
              {selectedFromUser && (
                <>
                  {loadingPreview ? (
                    <ActivityIndicator color="#007AFF" style={{ marginVertical: 20 }} />
                  ) : transferPreview && (
                    <>
                      {/* Preview Summary */}
                      <View style={styles.previewCard}>
                        <Text style={styles.previewTitle}>Items to Transfer</Text>
                        {renderTransferOption(
                          'Contacts',
                          transferPreview.items_to_transfer.contacts,
                          transferContacts,
                          () => setTransferContacts(!transferContacts)
                        )}
                        {renderTransferOption(
                          'Conversations',
                          transferPreview.items_to_transfer.conversations,
                          transferConversations,
                          () => setTransferConversations(!transferConversations)
                        )}
                        {renderTransferOption(
                          'Tasks',
                          transferPreview.items_to_transfer.tasks,
                          transferTasks,
                          () => setTransferTasks(!transferTasks)
                        )}
                        {renderTransferOption(
                          'Campaign Enrollments',
                          transferPreview.items_to_transfer.campaign_enrollments,
                          transferCampaigns,
                          () => setTransferCampaigns(!transferCampaigns)
                        )}
                        <View style={styles.totalRow}>
                          <Text style={styles.totalLabel}>Total Items</Text>
                          <Text style={styles.totalValue}>{transferPreview.total}</Text>
                        </View>
                      </View>
                      
                      {/* Select To User */}
                      {renderUserSelector(
                        'Transfer TO',
                        selectedToUser,
                        setSelectedToUser,
                        getAvailableToUsers()
                      )}
                    </>
                  )}
                </>
              )}
            </ScrollView>
            
            {/* Execute Button */}
            {selectedFromUser && selectedToUser && (
              <TouchableOpacity
                style={[styles.executeButton, transferring && styles.executeButtonDisabled]}
                onPress={handleExecuteTransfer}
                disabled={transferring}
                data-testid="execute-transfer-btn"
              >
                {transferring ? (
                  <ActivityIndicator color={colors.text} />
                ) : (
                  <>
                    <Ionicons name="swap-horizontal" size={20} color={colors.text} />
                    <Text style={styles.executeButtonText}>Execute Transfer</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
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
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    width: 40,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  infoBanner: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  infoContent: {
    flex: 1,
    marginLeft: 12,
  },
  infoTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  infoText: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  startButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF9500',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    gap: 10,
  },
  startButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  historySection: {
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  emptyHistory: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 12,
  },
  historyItem: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  historyFlow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  historyUser: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.text,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    backgroundColor: colors.surface,
  },
  statusCompleted: {
    backgroundColor: '#34C75920',
  },
  statusProgress: {
    backgroundColor: '#FF950020',
  },
  statusText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  historyStats: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  historyStatItem: {
    fontSize: 15,
    color: colors.textSecondary,
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  historyFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  historyDate: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  historyInitiator: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
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
    maxHeight: 500,
  },
  selectorSection: {
    marginBottom: 20,
  },
  selectorLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
  },
  selectedUser: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF20',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  userList: {
    maxHeight: 200,
  },
  userOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007AFF30',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  userAvatarText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  userInfo: {
    flex: 1,
  },
  userName: {
    fontSize: 17,
    fontWeight: '500',
    color: colors.text,
  },
  userEmail: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  previewCard: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  previewTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#3C3C3E',
  },
  optionRowEnabled: {},
  optionInfo: {},
  optionLabel: {
    fontSize: 17,
    color: colors.text,
  },
  optionCount: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.textSecondary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxEnabled: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3C3C3E',
  },
  totalLabel: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  totalValue: {
    fontSize: 19,
    fontWeight: '700',
    color: '#FF9500',
  },
  executeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF3B30',
    borderRadius: 12,
    padding: 16,
    margin: 16,
    gap: 8,
  },
  executeButtonDisabled: {
    opacity: 0.5,
  },
  executeButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
});
