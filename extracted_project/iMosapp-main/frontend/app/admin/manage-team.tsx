import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Modal,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

export default function ManageTeamScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [teamMembers, setTeamMembers] = useState<any[]>([]);
  const [storeInfo, setStoreInfo] = useState<any>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [adding, setAdding] = useState(false);
  
  // New user form
  const [newUser, setNewUser] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'user',
  });
  
  useFocusEffect(
    useCallback(() => {
      loadTeamData();
    }, [user?._id, user?.store_id])
  );
  
  const loadTeamData = async () => {
    try {
      setLoading(true);
      
      // Get store info with pricing
      if (user?.store_id) {
        try {
          const storeRes = await api.get(`/admin/stores/${user.store_id}`);
          setStoreInfo(storeRes.data);
        } catch (e) {
          console.log('Could not load store info');
        }
      }
      
      // Get team members for this store
      const storeIds = user?.store_ids || (user?.store_id ? [user.store_id] : []);
      if (storeIds.length > 0) {
        const usersRes = await api.get('/admin/users', {
          params: { store_ids: storeIds.join(',') }
        });
        setTeamMembers(usersRes.data || []);
      }
    } catch (error) {
      console.error('Failed to load team data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadTeamData();
    setRefreshing(false);
  };
  
  const handleBack = () => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/admin');
    }
  };
  
  const handleAddUser = async () => {
    // Validation
    if (!newUser.name.trim()) {
      Alert.alert('Error', 'Please enter the team member\'s name');
      return;
    }
    if (!newUser.email.trim() || !newUser.email.includes('@')) {
      Alert.alert('Error', 'Please enter a valid email address');
      return;
    }
    if (!newUser.phone.trim()) {
      Alert.alert('Error', 'Please enter a phone number');
      return;
    }
    
    // Confirm with pricing
    const costPerSeat = storeInfo?.pricing?.per_seat || 99;
    
    Alert.alert(
      'Confirm New Team Member',
      `Adding ${newUser.name} will add $${costPerSeat}/month to your subscription.\n\nThey will receive a welcome SMS with onboarding instructions.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Add & Send Invite', 
          onPress: async () => {
            try {
              setAdding(true);
              
              const res = await api.post('/admin/users/add-team-member', {
                name: newUser.name.trim(),
                email: newUser.email.trim().toLowerCase(),
                phone: newUser.phone.trim(),
                role: newUser.role,
                store_id: user?.store_id,
                added_by: user?._id,
              });
              
              Alert.alert(
                'Team Member Added!',
                `${newUser.name} has been added to your team. They will receive a welcome SMS with instructions to complete their onboarding.`,
                [{ text: 'OK' }]
              );
              
              // Reset form and close modal
              setNewUser({ name: '', email: '', phone: '', role: 'user' });
              setShowAddModal(false);
              
              // Refresh team list
              loadTeamData();
            } catch (error: any) {
              console.error('Failed to add user:', error);
              Alert.alert('Error', error.response?.data?.detail || 'Failed to add team member');
            } finally {
              setAdding(false);
            }
          }
        }
      ]
    );
  };
  
  const handleDeactivateUser = (member: any) => {
    Alert.alert(
      'Deactivate Team Member',
      `Are you sure you want to deactivate ${member.name}?\n\nThey will no longer be able to access the app, and your subscription will be reduced by $${storeInfo?.pricing?.per_seat || 99}/month.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Deactivate',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.put(`/admin/users/${member._id}/status`, {
                status: 'inactive',
                deactivated_by: user?._id,
              });
              
              Alert.alert('Deactivated', `${member.name} has been deactivated.`);
              loadTeamData();
            } catch (error: any) {
              Alert.alert('Error', error.response?.data?.detail || 'Failed to deactivate user');
            }
          }
        }
      ]
    );
  };
  
  const handleReactivateUser = async (member: any) => {
    Alert.alert(
      'Reactivate Team Member',
      `Reactivating ${member.name} will add $${storeInfo?.pricing?.per_seat || 99}/month to your subscription.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reactivate',
          onPress: async () => {
            try {
              await api.put(`/admin/users/${member._id}/status`, {
                status: 'active',
                reactivated_by: user?._id,
              });
              
              Alert.alert('Reactivated', `${member.name} has been reactivated.`);
              loadTeamData();
            } catch (error: any) {
              Alert.alert('Error', error.response?.data?.detail || 'Failed to reactivate user');
            }
          }
        }
      ]
    );
  };
  
  const activeMembers = teamMembers.filter(m => m.status !== 'inactive');
  const inactiveMembers = teamMembers.filter(m => m.status === 'inactive');
  const costPerSeat = storeInfo?.pricing?.per_seat || 99;
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      </SafeAreaView>
    );
  }
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={handleBack} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Manage Team</Text>
        <TouchableOpacity onPress={() => setShowAddModal(true)} style={styles.addButton}>
          <Ionicons name="person-add" size={24} color="#34C759" />
        </TouchableOpacity>
      </View>
      
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {/* Billing Summary */}
        <View style={styles.billingSummary}>
          <View style={styles.billingRow}>
            <Text style={styles.billingLabel}>Active Team Members</Text>
            <Text style={styles.billingValue}>{activeMembers.length}</Text>
          </View>
          <View style={styles.billingRow}>
            <Text style={styles.billingLabel}>Cost per Seat</Text>
            <Text style={styles.billingValue}>${costPerSeat}/mo</Text>
          </View>
          <View style={[styles.billingRow, styles.billingTotal]}>
            <Text style={styles.billingTotalLabel}>Monthly Total</Text>
            <Text style={styles.billingTotalValue}>
              ${(activeMembers.length * costPerSeat).toFixed(0)}/mo
            </Text>
          </View>
        </View>
        
        {/* Add Team Member CTA */}
        <TouchableOpacity style={styles.addCTA} onPress={() => setShowAddModal(true)}>
          <View style={styles.addCTAIcon}>
            <Ionicons name="person-add" size={24} color="#000" />
          </View>
          <View style={styles.addCTAContent}>
            <Text style={styles.addCTATitle}>Add Team Member</Text>
            <Text style={styles.addCTASubtitle}>+${costPerSeat}/month per user</Text>
          </View>
          <Ionicons name="chevron-forward" size={24} color="#8E8E93" />
        </TouchableOpacity>
        
        {/* Active Team Members */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ACTIVE TEAM ({activeMembers.length})</Text>
          
          {activeMembers.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>No active team members</Text>
            </View>
          ) : (
            activeMembers.map((member) => (
              <View key={member._id} style={styles.memberCard}>
                <View style={styles.memberAvatar}>
                  <Text style={styles.memberInitials}>
                    {member.name?.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)}
                  </Text>
                </View>
                <View style={styles.memberInfo}>
                  <Text style={styles.memberName}>{member.name}</Text>
                  <Text style={styles.memberEmail}>{member.email}</Text>
                  <View style={styles.memberMeta}>
                    <View style={[
                      styles.roleBadge,
                      member.role === 'store_manager' && styles.roleBadgeManager
                    ]}>
                      <Text style={styles.roleBadgeText}>
                        {member.role === 'store_manager' ? 'Manager' : 'Sales Rep'}
                      </Text>
                    </View>
                    {member.onboarding_complete === false && (
                      <View style={styles.pendingBadge}>
                        <Ionicons name="time" size={12} color="#FF9500" />
                        <Text style={styles.pendingBadgeText}>Onboarding</Text>
                      </View>
                    )}
                  </View>
                </View>
                {member._id !== user?._id && (
                  <TouchableOpacity
                    style={styles.actionButton}
                    onPress={() => handleDeactivateUser(member)}
                  >
                    <Ionicons name="person-remove" size={20} color="#FF3B30" />
                  </TouchableOpacity>
                )}
              </View>
            ))
          )}
        </View>
        
        {/* Inactive Team Members */}
        {inactiveMembers.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>INACTIVE ({inactiveMembers.length})</Text>
            
            {inactiveMembers.map((member) => (
              <View key={member._id} style={[styles.memberCard, styles.memberCardInactive]}>
                <View style={[styles.memberAvatar, styles.memberAvatarInactive]}>
                  <Text style={styles.memberInitials}>
                    {member.name?.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)}
                  </Text>
                </View>
                <View style={styles.memberInfo}>
                  <Text style={[styles.memberName, styles.memberNameInactive]}>{member.name}</Text>
                  <Text style={styles.memberEmail}>{member.email}</Text>
                </View>
                <TouchableOpacity
                  style={[styles.actionButton, styles.reactivateButton]}
                  onPress={() => handleReactivateUser(member)}
                >
                  <Ionicons name="refresh" size={20} color="#34C759" />
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}
        
        <View style={{ height: 40 }} />
      </ScrollView>
      
      {/* Add User Modal */}
      <Modal
        visible={showAddModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowAddModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ flex: 1 }}
        >
          <View style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <TouchableOpacity onPress={() => setShowAddModal(false)}>
                <Text style={styles.modalCancel}>Cancel</Text>
              </TouchableOpacity>
              <Text style={styles.modalTitle}>Add Team Member</Text>
              <TouchableOpacity onPress={handleAddUser} disabled={adding}>
                {adding ? (
                  <ActivityIndicator size="small" color="#007AFF" />
                ) : (
                  <Text style={styles.modalSave}>Add</Text>
                )}
              </TouchableOpacity>
            </View>
            
            <ScrollView style={styles.modalContent} keyboardShouldPersistTaps="handled">
              {/* Cost Notice */}
              <View style={styles.costNotice}>
                <Ionicons name="information-circle" size={20} color="#007AFF" />
                <Text style={styles.costNoticeText}>
                  Adding a new team member will add <Text style={styles.costHighlight}>${costPerSeat}/month</Text> to your subscription.
                </Text>
              </View>
              
              {/* Name */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Full Name *</Text>
                <TextInput
                  style={styles.textInput}
                  value={newUser.name}
                  onChangeText={(text) => setNewUser(prev => ({ ...prev, name: text }))}
                  placeholder="John Smith"
                  placeholderTextColor="#6E6E73"
                  autoCapitalize="words"
                />
              </View>
              
              {/* Email */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email Address *</Text>
                <TextInput
                  style={styles.textInput}
                  value={newUser.email}
                  onChangeText={(text) => setNewUser(prev => ({ ...prev, email: text }))}
                  placeholder="john@example.com"
                  placeholderTextColor="#6E6E73"
                  keyboardType="email-address"
                  autoCapitalize="none"
                />
              </View>
              
              {/* Phone */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Phone Number *</Text>
                <TextInput
                  style={styles.textInput}
                  value={newUser.phone}
                  onChangeText={(text) => setNewUser(prev => ({ ...prev, phone: text }))}
                  placeholder="(555) 123-4567"
                  placeholderTextColor="#6E6E73"
                  keyboardType="phone-pad"
                />
              </View>
              
              {/* Role */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Role</Text>
                <View style={styles.roleSelector}>
                  <TouchableOpacity
                    style={[styles.roleOption, newUser.role === 'user' && styles.roleOptionSelected]}
                    onPress={() => setNewUser(prev => ({ ...prev, role: 'user' }))}
                  >
                    <Ionicons 
                      name="person" 
                      size={20} 
                      color={newUser.role === 'user' ? '#000' : '#8E8E93'} 
                    />
                    <Text style={[
                      styles.roleOptionText,
                      newUser.role === 'user' && styles.roleOptionTextSelected
                    ]}>Sales Rep</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.roleOption, newUser.role === 'store_manager' && styles.roleOptionSelected]}
                    onPress={() => setNewUser(prev => ({ ...prev, role: 'store_manager' }))}
                  >
                    <Ionicons 
                      name="shield" 
                      size={20} 
                      color={newUser.role === 'store_manager' ? '#000' : '#8E8E93'} 
                    />
                    <Text style={[
                      styles.roleOptionText,
                      newUser.role === 'store_manager' && styles.roleOptionTextSelected
                    ]}>Manager</Text>
                  </TouchableOpacity>
                </View>
              </View>
              
              {/* What happens next */}
              <View style={styles.infoBox}>
                <Text style={styles.infoBoxTitle}>What happens next?</Text>
                <View style={styles.infoStep}>
                  <View style={styles.infoStepNum}><Text style={styles.infoStepNumText}>1</Text></View>
                  <Text style={styles.infoStepText}>Account is created with temporary password</Text>
                </View>
                <View style={styles.infoStep}>
                  <View style={styles.infoStepNum}><Text style={styles.infoStepNumText}>2</Text></View>
                  <Text style={styles.infoStepText}>Welcome SMS sent with app download link</Text>
                </View>
                <View style={styles.infoStep}>
                  <View style={styles.infoStepNum}><Text style={styles.infoStepNumText}>3</Text></View>
                  <Text style={styles.infoStepText}>They complete onboarding training</Text>
                </View>
                <View style={styles.infoStep}>
                  <View style={styles.infoStepNum}><Text style={styles.infoStepNumText}>4</Text></View>
                  <Text style={styles.infoStepText}>Ready to start using the app!</Text>
                </View>
              </View>
              
              <View style={{ height: 100 }} />
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
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
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  addButton: {
    padding: 4,
  },
  content: {
    padding: 16,
  },
  billingSummary: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  billingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  billingLabel: {
    fontSize: 15,
    color: '#8E8E93',
  },
  billingValue: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  billingTotal: {
    borderTopWidth: 1,
    borderTopColor: '#3C3C3E',
    marginTop: 8,
    paddingTop: 16,
  },
  billingTotalLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  billingTotalValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#C9A962',
  },
  addCTA: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  addCTAIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#34C759',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  addCTAContent: {
    flex: 1,
  },
  addCTATitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  addCTASubtitle: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 12,
    letterSpacing: 0.5,
  },
  emptyState: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 15,
    color: '#6E6E73',
  },
  memberCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  memberCardInactive: {
    opacity: 0.7,
  },
  memberAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#3C3C3E',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  memberAvatarInactive: {
    backgroundColor: '#2C2C2E',
  },
  memberInitials: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  memberNameInactive: {
    color: '#8E8E93',
  },
  memberEmail: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  memberMeta: {
    flexDirection: 'row',
    marginTop: 6,
    gap: 8,
  },
  roleBadge: {
    backgroundColor: '#3C3C3E',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  roleBadgeManager: {
    backgroundColor: 'rgba(201,169,98,0.2)',
  },
  roleBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#FFF',
  },
  pendingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,149,0,0.2)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    gap: 4,
  },
  pendingBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#FF9500',
  },
  actionButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,59,48,0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  reactivateButton: {
    backgroundColor: 'rgba(52,199,89,0.1)',
  },
  // Modal Styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  modalCancel: {
    fontSize: 17,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  modalSave: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  costNotice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(0,122,255,0.1)',
    borderRadius: 12,
    padding: 14,
    marginBottom: 24,
    gap: 10,
  },
  costNoticeText: {
    flex: 1,
    fontSize: 14,
    color: '#007AFF',
    lineHeight: 20,
  },
  costHighlight: {
    fontWeight: '700',
  },
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#3C3C3E',
  },
  roleSelector: {
    flexDirection: 'row',
    gap: 12,
  },
  roleOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingVertical: 14,
    gap: 8,
    borderWidth: 2,
    borderColor: '#3C3C3E',
  },
  roleOptionSelected: {
    backgroundColor: '#C9A962',
    borderColor: '#C9A962',
  },
  roleOptionText: {
    fontSize: 15,
    fontWeight: '500',
    color: '#8E8E93',
  },
  roleOptionTextSelected: {
    color: '#000',
  },
  infoBox: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  infoBoxTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 14,
  },
  infoStep: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  infoStepNum: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#34C759',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  infoStepNumText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#000',
  },
  infoStepText: {
    flex: 1,
    fontSize: 14,
    color: '#8E8E93',
  },
});
