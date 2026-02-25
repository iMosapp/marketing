import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

export default function InviteTeamScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [sending, setSending] = useState(false);
  const [recentInvites, setRecentInvites] = useState<any[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(true);
  
  // Form state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('user');
  const [successMessage, setSuccessMessage] = useState('');

  // Available roles based on current user's role
  const getRoleOptions = () => {
    if (user?.role === 'super_admin') {
      return [
        { value: 'org_admin', label: 'Org Admin', icon: 'shield-checkmark', desc: 'Full org access', color: '#007AFF' },
        { value: 'store_manager', label: 'Store Manager', icon: 'storefront', desc: 'Manages a store', color: '#34C759' },
        { value: 'user', label: 'Team Member', icon: 'person', desc: 'Standard access', color: '#C9A962' },
        { value: 'individual', label: 'Individual', icon: 'person-circle', desc: 'Solo account', color: '#AF52DE' },
      ];
    }
    if (user?.role === 'org_admin') {
      return [
        { value: 'store_manager', label: 'Store Manager', icon: 'storefront', desc: 'Manages a store', color: '#34C759' },
        { value: 'user', label: 'Team Member', icon: 'person', desc: 'Standard access', color: '#C9A962' },
      ];
    }
    return [
      { value: 'user', label: 'Team Member', icon: 'person', desc: 'Standard access', color: '#C9A962' },
    ];
  };

  const roleOptions = getRoleOptions();

  useFocusEffect(
    useCallback(() => {
      loadRecentInvites();
    }, [user?._id])
  );

  const loadRecentInvites = async () => {
    if (!user?._id) return;
    try {
      setLoadingRecent(true);
      const res = await api.get('/admin/users', { headers: { 'X-User-ID': user._id } });
      // Show recently created users as "invites"
      const recent = (res.data || [])
        .filter((u: any) => u._id !== user._id)
        .sort((a: any, b: any) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
        .slice(0, 5);
      setRecentInvites(recent);
    } catch (error) {
      console.error('Failed to load recent invites:', error);
    } finally {
      setLoadingRecent(false);
    }
  };

  const handleSendInvite = async () => {
    if (!name.trim()) {
      showSimpleAlert('Name Required', 'Please enter the person\'s name');
      return;
    }
    if (!email.trim() || !email.includes('@')) {
      showSimpleAlert('Valid Email Required', 'Please enter a valid email address');
      return;
    }

    setSending(true);
    setSuccessMessage('');
    try {
      const res = await api.post('/admin/users/create', {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        role: role === 'individual' ? 'user' : role,
        send_invite: true,
        // Individual = no org/store; otherwise inherit from current user context
        ...(role !== 'individual' && user?.organization_id ? { organization_id: user.organization_id } : {}),
        ...(role !== 'individual' && role === 'user' && user?.store_id ? { store_id: user.store_id } : {}),
      }, {
        headers: { 'X-User-ID': user?._id }
      });

      const data = res.data;
      if (data.success) {
        const inviteSent = data.invite_sent ? 'Email invitation sent!' : 'User created (email not configured).';
        setSuccessMessage(`${name.trim()} has been invited as ${roleOptions.find(r => r.value === role)?.label}. ${inviteSent}`);
        setName('');
        setEmail('');
        setRole('user');
        loadRecentInvites();
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to send invitation';
      showSimpleAlert('Error', detail);
    } finally {
      setSending(false);
    }
  };

  const getRoleBadgeColor = (r: string) => {
    switch (r) {
      case 'super_admin': return '#FF3B30';
      case 'org_admin': return '#007AFF';
      case 'store_manager': return '#34C759';
      case 'individual': return '#AF52DE';
      default: return '#8E8E93';
    }
  };

  const getRoleLabel = (r: string) => {
    switch (r) {
      case 'super_admin': return 'Super Admin';
      case 'org_admin': return 'Org Admin';
      case 'store_manager': return 'Manager';
      case 'individual': return 'Individual';
      default: return 'Team Member';
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Invite Team</Text>
        <View style={{ width: 40 }} />
      </View>
      
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Invite Form */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="person-add" size={22} color="#C9A962" />
            <Text style={styles.sectionTitle}>Send Invitation</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Create a new team member and send them an email with login credentials
          </Text>

          {successMessage ? (
            <View style={styles.successBanner}>
              <Ionicons name="checkmark-circle" size={22} color="#34C759" />
              <Text style={styles.successText}>{successMessage}</Text>
            </View>
          ) : null}

          <View style={styles.formGroup}>
            <Text style={styles.inputLabel}>Full Name *</Text>
            <View style={styles.inputRow}>
              <Ionicons name="person-outline" size={18} color="#8E8E93" />
              <TextInput
                style={styles.textInput}
                value={name}
                onChangeText={setName}
                placeholder="John Smith"
                placeholderTextColor="#6E6E73"
                autoCapitalize="words"
              />
            </View>
          </View>

          <View style={styles.formGroup}>
            <Text style={styles.inputLabel}>Email Address *</Text>
            <View style={styles.inputRow}>
              <Ionicons name="mail-outline" size={18} color="#8E8E93" />
              <TextInput
                style={styles.textInput}
                value={email}
                onChangeText={setEmail}
                placeholder="john@company.com"
                placeholderTextColor="#6E6E73"
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>
          </View>

          <View style={styles.formGroup}>
            <Text style={styles.inputLabel}>Role</Text>
            <View style={styles.roleSelector}>
              {roleOptions.map((opt) => {
                const isActive = role === opt.value;
                return (
                  <TouchableOpacity
                    key={opt.value}
                    style={[
                      styles.roleOption,
                      isActive && styles.roleOptionActive,
                      isActive && { borderColor: opt.color },
                    ]}
                    onPress={() => setRole(opt.value)}
                  >
                    <View style={[styles.roleIconWrap, { backgroundColor: (isActive ? opt.color : '#3A3A3C') + '25' }]}>
                      <Ionicons name={opt.icon as any} size={18} color={isActive ? opt.color : '#8E8E93'} />
                    </View>
                    <View style={styles.roleTextWrap}>
                      <Text style={[styles.roleOptionText, isActive && styles.roleOptionTextActive]}>{opt.label}</Text>
                      <Text style={styles.roleDesc}>{opt.desc}</Text>
                    </View>
                    <View style={[styles.roleRadio, isActive && styles.roleRadioActive, isActive && { borderColor: opt.color }]}>
                      {isActive ? <View style={[styles.roleRadioDot, { backgroundColor: opt.color }]} /> : null}
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          <TouchableOpacity
            style={[styles.sendButton, sending && { opacity: 0.6 }]}
            onPress={handleSendInvite}
            disabled={sending}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#000" />
            ) : (
              <>
                <Ionicons name="send" size={18} color="#000" />
                <Text style={styles.sendButtonText}>Send Invite Email</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Recent Team Members */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="people" size={22} color="#007AFF" />
            <Text style={styles.sectionTitle}>Recent Team Members</Text>
          </View>

          {loadingRecent ? (
            <ActivityIndicator size="small" color="#C9A962" style={{ marginVertical: 20 }} />
          ) : recentInvites.length === 0 ? (
            <Text style={styles.emptyText}>No team members yet. Send your first invite above!</Text>
          ) : (
            recentInvites.map((member: any) => (
              <View key={member._id} style={styles.memberRow}>
                <View style={styles.memberAvatar}>
                  <Text style={styles.memberAvatarText}>
                    {(member.name || '?').split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)}
                  </Text>
                </View>
                <View style={styles.memberInfo}>
                  <Text style={styles.memberName}>{member.name}</Text>
                  <Text style={styles.memberEmail}>{member.email}</Text>
                </View>
                <View style={[styles.roleBadge, { backgroundColor: getRoleBadgeColor(member.role) + '20' }]}>
                  <Text style={[styles.roleBadgeText, { color: getRoleBadgeColor(member.role) }]}>
                    {getRoleLabel(member.role)}
                  </Text>
                </View>
              </View>
            ))
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
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
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  content: {
    padding: 16,
  },
  section: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  sectionDescription: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 16,
  },
  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: 'rgba(52, 199, 89, 0.15)',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
  },
  successText: {
    flex: 1,
    color: '#34C759',
    fontSize: 14,
    lineHeight: 20,
  },
  formGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 8,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    paddingHorizontal: 14,
    gap: 10,
  },
  textInput: {
    flex: 1,
    fontSize: 16,
    color: '#FFF',
    paddingVertical: 14,
  },
  roleSelector: {
    flexDirection: 'column',
    gap: 8,
  },
  roleOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#2C2C2E',
    borderWidth: 1.5,
    borderColor: 'transparent',
    gap: 12,
  },
  roleOptionActive: {
    backgroundColor: '#1A1A1A',
  },
  roleIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  roleTextWrap: {
    flex: 1,
  },
  roleOptionText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#8E8E93',
  },
  roleOptionTextActive: {
    color: '#FFF',
  },
  roleDesc: {
    fontSize: 12,
    color: '#6E6E73',
    marginTop: 1,
  },
  roleRadio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: '#3A3A3C',
    alignItems: 'center',
    justifyContent: 'center',
  },
  roleRadioActive: {
    borderWidth: 2,
  },
  roleRadioDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  sendButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 16,
    borderRadius: 25,
    gap: 8,
    marginTop: 4,
  },
  sendButtonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },
  emptyText: {
    color: '#6E6E73',
    fontSize: 14,
    textAlign: 'center',
    paddingVertical: 20,
  },
  memberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
    gap: 12,
  },
  memberAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  memberAvatarText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '500',
  },
  memberEmail: {
    color: '#8E8E93',
    fontSize: 13,
    marginTop: 2,
  },
  roleBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  roleBadgeText: {
    fontSize: 12,
    fontWeight: '600',
  },
});
