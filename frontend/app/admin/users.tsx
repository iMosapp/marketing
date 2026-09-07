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
  Platform,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, useLocalSearchParams } from 'expo-router';
import * as Haptics from 'expo-haptics';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showSimpleAlert, showAlert } from '../../services/alert';
import { WebSafeButton } from '../../components/WebSafeButton';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { FS } from '../../constants/typography';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const ROLE_COLORS: Record<string, string> = {
  super_admin: '#FF3B30',
  org_admin: '#FF9500',
  admin: '#FF9500',
  store_manager: '#34C759',
  manager: '#34C759',
  user: '#C9A962',
};

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin',
  org_admin: 'Admin',
  admin: 'Admin',
  store_manager: 'Manager',
  manager: 'Manager',
  user: 'User',
};

// Map legacy/variant roles to their canonical group for display
const ROLE_GROUP_MAP: Record<string, string> = {
  super_admin: 'super_admin',
  org_admin: 'org_admin',
  admin: 'org_admin',
  store_manager: 'store_manager',
  manager: 'store_manager',
  user: 'user',
};

const ROLE_ORDER = ['super_admin', 'org_admin', 'store_manager', 'user'];

export default function UsersScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const params = useLocalSearchParams<{ importName?: string; importEmail?: string; importPhone?: string; importContactId?: string }>();
  
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
  const [newUserOrgId, setNewUserOrgId] = useState<string | null>(null);
  const [newUserStoreId, setNewUserStoreId] = useState<string | null>(null);
  const [sendInvite, setSendInvite] = useState(false); // Default to showing password
  const [creating, setCreating] = useState(false);
  const [createdUser, setCreatedUser] = useState<any>(null);
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  const [contactResults, setContactResults] = useState<any[]>([]);
  const [searchingContacts, setSearchingContacts] = useState(false);
  const [selectedContactId, setSelectedContactId] = useState<string | null>(null);
  useFocusEffect(
    useCallback(() => {
      loadUsers();
      loadOrganizations();
      loadStores();
      // Auto-open modal if coming from contact "Convert to User"
      if (params.importName) {
        setNewUserName(params.importName || '');
        setNewUserEmail(params.importEmail || '');
        setNewUserPhone(params.importPhone || '');
        setSelectedContactId(params.importContactId || null);
        setShowAddModal(true);
      }
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
  
  const loadOrganizations = async () => {
    try {
      const response = await api.get('/admin/organizations');
      setOrganizations(response.data || []);
    } catch (error) {
      console.error('Failed to load organizations:', error);
    }
  };
  
  const loadStores = async (orgId?: string) => {
    try {
      const url = orgId ? `/admin/stores?organization_id=${orgId}` : '/admin/stores';
      const response = await api.get(url);
      setStores(response.data || []);
    } catch (error) {
      console.error('Failed to load stores:', error);
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
    setNewUserOrgId(null);
    setNewUserStoreId(null);
    setSendInvite(false);
    setCreatedUser(null);
    setContactSearch('');
    setContactResults([]);
    setSelectedContactId(null);
  };

  const searchContacts = async (query: string) => {
    setContactSearch(query);
    if (query.trim().length < 2) { setContactResults([]); return; }
    setSearchingContacts(true);
    try {
      const response = await api.get(`/contacts/${user?._id}`, { params: { search: query.trim() } });
      const data = response.data;
      const contacts = Array.isArray(data) ? data : (data.contacts || []);
      setContactResults(contacts.slice(0, 5));
    } catch (e) {
      console.error('Contact search failed:', e);
    } finally {
      setSearchingContacts(false);
    }
  };

  const importFromContact = (contact: any) => {
    const firstName = contact.first_name || '';
    const lastName = contact.last_name || '';
    setNewUserName(`${firstName} ${lastName}`.trim());
    setNewUserEmail(contact.email || '');
    setNewUserPhone(contact.phone || '');
    setSelectedContactId(contact._id);
    setContactSearch('');
    setContactResults([]);
  };

  const handleCreateUser = async () => {
    if (!newUserName.trim()) {
      showAlert('Error', 'Please enter a name');
      return;
    }
    if (!newUserEmail.trim() || !newUserEmail.includes('@')) {
      showAlert('Error', 'Please enter a valid email');
      return;
    }

    setCreating(true);
    try {
      const nameParts = newUserName.trim().split(' ');
      const first_name = nameParts[0] || '';
      const last_name = nameParts.slice(1).join(' ') || '';
      
      const response = await api.post('/admin/users/create', {
        first_name,
        last_name,
        name: newUserName.trim(),
        email: newUserEmail.trim().toLowerCase(),
        phone: newUserPhone.trim() || undefined,
        role: newUserRole,
        organization_id: newUserOrgId || undefined,
        store_id: newUserStoreId || undefined,
        send_invite: sendInvite,
        source_contact_id: selectedContactId || undefined,
      });

      if (response.data.success) {
        setCreatedUser({
          name: newUserName.trim(),
          email: newUserEmail.trim().toLowerCase(),
          temp_password: response.data.temp_password,
          invite_sent: response.data.invite_sent,
        });
        loadUsers();
      }
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to create user';
      showAlert('Error', message);
    } finally {
      setCreating(false);
    }
  };

  const handleCopyPassword = async () => {
    if (createdUser?.temp_password) {
      try {
        if (Platform.OS === 'web') {
          await navigator.clipboard.writeText(createdUser.temp_password);
        } else {
          await Clipboard.setStringAsync(createdUser.temp_password);
        }
        showSimpleAlert('Copied', 'Password copied to clipboard');
      } catch (e) {
        showSimpleAlert('Error', 'Failed to copy to clipboard');
      }
    }
  };

  const handleCopyCredentials = async () => {
    if (createdUser) {
      const credentials = `Welcome to I'm On Social, ${createdUser.name}!\n\n1. Download the app: https://app.imonsocial.com\n2. Tap "Activate my account" and enter your mobile number\n3. Enter the code we text you and choose your password\n\nLogin email: ${createdUser.email}\nBackup password (only if the text doesn't arrive): ${createdUser.temp_password}`;
      try {
        if (Platform.OS === 'web') {
          await navigator.clipboard.writeText(credentials);
        } else {
          await Clipboard.setStringAsync(credentials);
        }
        showSimpleAlert('Copied', 'Credentials copied to clipboard');
      } catch (e) {
        showSimpleAlert('Error', 'Failed to copy to clipboard');
      }
    }
  };

  const handleCloseSuccessModal = () => {
    setCreatedUser(null);
    setShowAddModal(false);
    resetAddForm();
  };

  // Filter and group users - separate active and inactive
  const sections = useMemo(() => {
    const filteredUsers = users.filter(user => {
      if (!searchQuery.trim()) return true;
      const query = searchQuery.toLowerCase();
      return (
        user.name?.toLowerCase().includes(query) ||
        user.email?.toLowerCase().includes(query)
      );
    });

    // Separate active and inactive users
    const activeUsers = filteredUsers.filter(u => u.is_active !== false);
    const inactiveUsers = filteredUsers.filter(u => u.is_active === false);

    const grouped: Record<string, any[]> = {};
    
    activeUsers.forEach(user => {
      // Map variant roles to their canonical group
      const role = ROLE_GROUP_MAP[user.role] || 'user';
      if (!grouped[role]) {
        grouped[role] = [];
      }
      grouped[role].push(user);
    });

    const activeSections = ROLE_ORDER
      .filter(role => grouped[role]?.length > 0)
      .map(role => ({
        title: ROLE_LABELS[role] || role,
        role: role,
        color: ROLE_COLORS[role] || colors.textSecondary,
        data: collapsedSections[role] ? [] : grouped[role],
        count: grouped[role].length,
        isInactive: false,
      }));

    // Add inactive users section if any exist
    if (inactiveUsers.length > 0) {
      activeSections.push({
        title: 'Inactive Users',
        role: 'inactive',
        color: colors.textSecondary,
        data: collapsedSections['inactive'] ? [] : inactiveUsers,
        count: inactiveUsers.length,
        isInactive: true,
      });
    }

    return activeSections;
  }, [users, searchQuery, collapsedSections]);

  const renderUser = ({ item }: { item: any }) => (
    <TouchableOpacity 
      style={[styles.userCard, item.is_active === false && styles.inactiveCard]}
      onPress={() => router.push(`/admin/users/${item._id}`)}
      {...tid(`user-row-${item._id}`)}
    >
      {item.photo_url ? (
        <Image source={{ uri: item.photo_url }} style={styles.userAvatarPhoto} contentFit="cover" cachePolicy="memory-disk" />
      ) : (
        <View style={[styles.userAvatar, { backgroundColor: (ROLE_COLORS[item.role] || colors.textSecondary) + '30' }]}>
          <Text style={[styles.userAvatarText, { color: ROLE_COLORS[item.role] || colors.textSecondary }]}>
            {item.name?.split(' ').map((n: string) => n[0]).join('').substring(0, 2) || '?'}
          </Text>
        </View>
      )}
      <View style={styles.userInfo}>
        <Text style={[styles.userName, item.is_active === false && styles.inactiveText]} numberOfLines={1}>{item.name}</Text>
        <Text style={styles.userEmail} numberOfLines={1}>{item.email}</Text>
        {item.is_active === false && item.deletion_source && (
          <Text style={styles.deletionSource}>Deleted by: {item.deletion_source}</Text>
        )}
      </View>
      <View style={[styles.statusDot, { backgroundColor: item.is_active !== false ? '#34C759' : '#FF3B30' }]} />
      <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
    </TouchableOpacity>
  );

  const renderSectionHeader = ({ section }: { section: any }) => (
    <TouchableOpacity 
      style={[styles.sectionHeader, section.isInactive && styles.inactiveSectionHeader]}
      onPress={() => toggleSection(section.role)}
      activeOpacity={0.7}
      {...tid(`user-section-${section.role}`)}
    >
      <View style={[styles.sectionIcon, { backgroundColor: section.color + '20' }]}>
        <Ionicons 
          name={
            section.role === 'inactive' ? 'person-remove' :
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
        color={colors.textSecondary} 
      />
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScreenHeader
        title="Team Members"
        subtitle={loading ? undefined : `${users.filter(u => u.is_active !== false).length} active`}
        testID="team-members-header"
        right={<HeaderIconButton icon="person-add" onPress={() => setShowAddModal(true)} testID="add-user-btn" />}
      />

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={20} color={colors.textSecondary} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by name or email..."
            placeholderTextColor={colors.textSecondary}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCapitalize="none"
            autoCorrect={false}
            {...tid('user-search-input')}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')} {...tid('user-search-clear')}>
              <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
      </View>
      
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
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
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer} {...tid('users-empty')}>
              <Ionicons name="people-outline" size={52} color={colors.textTertiary} />
              <Text style={styles.emptyText}>
                {searchQuery ? 'No one matches that search' : 'No team members yet'}
              </Text>
              <Text style={styles.emptySubtext}>{searchQuery ? 'Try a name or email.' : 'Add your first rep to get them a login.'}</Text>
              <TouchableOpacity
                onPress={() => searchQuery ? setSearchQuery('') : setShowAddModal(true)}
                style={styles.emptyBtn}
                {...tid('users-empty-cta')}
              >
                <Text style={styles.emptyBtnText}>{searchQuery ? 'Clear search' : 'Add team member'}</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}

      {/* Add team member: fixed overlay on web, native Modal on the phone (the native branch used to render nothing) */}
      {(showAddModal && !createdUser) && (Platform.OS === 'web' ? (
        <View style={[styles.successOverlay, { position: 'fixed' as any, top: 0, left: 0, right: 0, bottom: 0, zIndex: 99998, paddingTop: 16 }]}>
          <View style={[styles.modalContainer, { maxWidth: 500, maxHeight: '85vh', borderRadius: 16, overflow: 'hidden' }]}>
          <View style={styles.modalHeader}>
            <WebSafeButton
              onPress={() => { setShowAddModal(false); resetAddForm(); }}
              variant="ghost"
              testID="modal-cancel"
            >
              <Text style={styles.modalCancel}>Cancel</Text>
            </WebSafeButton>
            <Text style={styles.modalTitle}>Add team member</Text>
            <WebSafeButton
              onPress={handleCreateUser}
              disabled={creating}
              loading={creating}
              variant="ghost"
              testID="modal-create"
            >
              <Text style={styles.modalSave}>Create</Text>
            </WebSafeButton>
          </View>

          <ScrollView style={styles.modalContent}>
            {/* Import from Contact */}
            <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: selectedContactId ? '#34C759' : colors.bg }}>
              <Text style={[styles.inputLabel, { marginBottom: 6, color: selectedContactId ? '#34C759' : colors.textSecondary }]}>
                {selectedContactId ? 'Imported from Contact' : 'Import from Contact'}
              </Text>
              {!selectedContactId ? (
                <>
                  <TextInput
                    style={styles.modalInput}
                    placeholder="Search contacts by name, email, phone..."
                    placeholderTextColor={colors.textSecondary}
                    value={contactSearch}
                    onChangeText={searchContacts}
                    autoCapitalize="none"
                    {...tid('contact-search-input')}
                  />
                  {searchingContacts && <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 4 }} />}
                  {contactResults.map((c) => (
                    <TouchableOpacity
                      key={c._id}
                      style={{ flexDirection: 'row', alignItems: 'center', padding: 10, borderRadius: 8, backgroundColor: colors.bg, marginTop: 6 }}
                      onPress={() => importFromContact(c)}
                      {...tid(`contact-result-${c._id}`)}
                    >
                      <Ionicons name="person-circle" size={32} color={colors.textSecondary} />
                      <View style={{ marginLeft: 10, flex: 1 }}>
                        <Text style={{ color: colors.text, fontWeight: '600', fontSize: 15 }}>{c.first_name} {c.last_name}</Text>
                        <Text style={{ color: colors.textSecondary, fontSize: 13 }}>{c.email || c.phone || ''}</Text>
                      </View>
                      <Ionicons name="arrow-forward-circle" size={22} color={colors.accent} />
                    </TouchableOpacity>
                  ))}
                </>
              ) : (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center' }}
                  onPress={() => { setSelectedContactId(null); setContactSearch(''); }}
                >
                  <Ionicons name="checkmark-circle" size={20} color="#34C759" />
                  <Text style={{ color: '#34C759', marginLeft: 6, fontSize: 14 }}>Contact linked. Tap to clear</Text>
                </TouchableOpacity>
              )}
            </View>

            <Text style={styles.inputLabel}>Name *</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Full name"
              placeholderTextColor={colors.textSecondary}
              value={newUserName}
              onChangeText={setNewUserName}
              autoCapitalize="words"
              {...tid('new-user-name')}
            />

            <Text style={styles.inputLabel}>Email *</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="email@example.com"
              placeholderTextColor={colors.textSecondary}
              value={newUserEmail}
              onChangeText={setNewUserEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              {...tid('new-user-email')}
            />

            <Text style={styles.inputLabel}>Phone (optional)</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="+1 555 123 4567"
              placeholderTextColor={colors.textSecondary}
              value={newUserPhone}
              onChangeText={setNewUserPhone}
              keyboardType="phone-pad"
              {...tid('new-user-phone')}
            />

            <Text style={styles.inputLabel}>Organization (optional)</Text>
            <View style={styles.pickerContainer}>
              <TouchableOpacity
                style={[styles.pickerOption, !newUserOrgId && styles.pickerOptionSelected]}
                onPress={() => {
                  setNewUserOrgId(null);
                  setNewUserStoreId(null);
                  loadStores();
                }}
              >
                <Text style={[styles.pickerOptionText, !newUserOrgId && styles.pickerOptionTextSelected]}>
                  Individual (No Org)
                </Text>
              </TouchableOpacity>
              {organizations.map((org) => (
                <TouchableOpacity
                  key={org._id}
                  style={[styles.pickerOption, newUserOrgId === org._id && styles.pickerOptionSelected]}
                  onPress={() => {
                    setNewUserOrgId(org._id);
                    setNewUserStoreId(null);
                    loadStores(org._id);
                  }}
                >
                  <Text style={[styles.pickerOptionText, newUserOrgId === org._id && styles.pickerOptionTextSelected]}>
                    {org.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {stores.length > 0 && (
              <>
                <Text style={styles.inputLabel}>Account (optional)</Text>
                <View style={styles.pickerContainer}>
                  <TouchableOpacity
                    style={[styles.pickerOption, !newUserStoreId && styles.pickerOptionSelected]}
                    onPress={() => setNewUserStoreId(null)}
                  >
                    <Text style={[styles.pickerOptionText, !newUserStoreId && styles.pickerOptionTextSelected]}>
                      No Store
                    </Text>
                  </TouchableOpacity>
                  {stores.map((store) => (
                    <TouchableOpacity
                      key={store._id}
                      style={[styles.pickerOption, newUserStoreId === store._id && styles.pickerOptionSelected]}
                      onPress={() => setNewUserStoreId(store._id)}
                    >
                      <Text style={[styles.pickerOptionText, newUserStoreId === store._id && styles.pickerOptionTextSelected]}>
                        {store.name}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            )}

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
                  {...tid(`new-user-role-${role}`)}
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
              {...tid('new-user-send-invite')}
            >
              <View style={[styles.checkbox, sendInvite && styles.checkboxChecked]}>
                {sendInvite && <Ionicons name="checkmark" size={16} color="#000" />}
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
          </View>
        </View>
      ) : (
        <Modal visible animationType="slide" presentationStyle="pageSheet" onRequestClose={() => { setShowAddModal(false); resetAddForm(); }}>
          <SafeAreaView style={styles.modalContainer} edges={['top']}>
          <View style={styles.modalHeader}>
            <WebSafeButton
              onPress={() => { setShowAddModal(false); resetAddForm(); }}
              variant="ghost"
              testID="modal-cancel"
            >
              <Text style={styles.modalCancel}>Cancel</Text>
            </WebSafeButton>
            <Text style={styles.modalTitle}>Add team member</Text>
            <WebSafeButton
              onPress={handleCreateUser}
              disabled={creating}
              loading={creating}
              variant="ghost"
              testID="modal-create"
            >
              <Text style={styles.modalSave}>Create</Text>
            </WebSafeButton>
          </View>

          <ScrollView style={styles.modalContent}>
            {/* Import from Contact */}
            <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: selectedContactId ? '#34C759' : colors.bg }}>
              <Text style={[styles.inputLabel, { marginBottom: 6, color: selectedContactId ? '#34C759' : colors.textSecondary }]}>
                {selectedContactId ? 'Imported from Contact' : 'Import from Contact'}
              </Text>
              {!selectedContactId ? (
                <>
                  <TextInput
                    style={styles.modalInput}
                    placeholder="Search contacts by name, email, phone..."
                    placeholderTextColor={colors.textSecondary}
                    value={contactSearch}
                    onChangeText={searchContacts}
                    autoCapitalize="none"
                    {...tid('contact-search-input')}
                  />
                  {searchingContacts && <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 4 }} />}
                  {contactResults.map((c) => (
                    <TouchableOpacity
                      key={c._id}
                      style={{ flexDirection: 'row', alignItems: 'center', padding: 10, borderRadius: 8, backgroundColor: colors.bg, marginTop: 6 }}
                      onPress={() => importFromContact(c)}
                      {...tid(`contact-result-${c._id}`)}
                    >
                      <Ionicons name="person-circle" size={32} color={colors.textSecondary} />
                      <View style={{ marginLeft: 10, flex: 1 }}>
                        <Text style={{ color: colors.text, fontWeight: '600', fontSize: 15 }}>{c.first_name} {c.last_name}</Text>
                        <Text style={{ color: colors.textSecondary, fontSize: 13 }}>{c.email || c.phone || ''}</Text>
                      </View>
                      <Ionicons name="arrow-forward-circle" size={22} color={colors.accent} />
                    </TouchableOpacity>
                  ))}
                </>
              ) : (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center' }}
                  onPress={() => { setSelectedContactId(null); setContactSearch(''); }}
                >
                  <Ionicons name="checkmark-circle" size={20} color="#34C759" />
                  <Text style={{ color: '#34C759', marginLeft: 6, fontSize: 14 }}>Contact linked. Tap to clear</Text>
                </TouchableOpacity>
              )}
            </View>

            <Text style={styles.inputLabel}>Name *</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Full name"
              placeholderTextColor={colors.textSecondary}
              value={newUserName}
              onChangeText={setNewUserName}
              autoCapitalize="words"
              {...tid('new-user-name')}
            />

            <Text style={styles.inputLabel}>Email *</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="email@example.com"
              placeholderTextColor={colors.textSecondary}
              value={newUserEmail}
              onChangeText={setNewUserEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              {...tid('new-user-email')}
            />

            <Text style={styles.inputLabel}>Phone (optional)</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="+1 555 123 4567"
              placeholderTextColor={colors.textSecondary}
              value={newUserPhone}
              onChangeText={setNewUserPhone}
              keyboardType="phone-pad"
              {...tid('new-user-phone')}
            />

            <Text style={styles.inputLabel}>Organization (optional)</Text>
            <View style={styles.pickerContainer}>
              <TouchableOpacity
                style={[styles.pickerOption, !newUserOrgId && styles.pickerOptionSelected]}
                onPress={() => {
                  setNewUserOrgId(null);
                  setNewUserStoreId(null);
                  loadStores();
                }}
              >
                <Text style={[styles.pickerOptionText, !newUserOrgId && styles.pickerOptionTextSelected]}>
                  Individual (No Org)
                </Text>
              </TouchableOpacity>
              {organizations.map((org) => (
                <TouchableOpacity
                  key={org._id}
                  style={[styles.pickerOption, newUserOrgId === org._id && styles.pickerOptionSelected]}
                  onPress={() => {
                    setNewUserOrgId(org._id);
                    setNewUserStoreId(null);
                    loadStores(org._id);
                  }}
                >
                  <Text style={[styles.pickerOptionText, newUserOrgId === org._id && styles.pickerOptionTextSelected]}>
                    {org.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {stores.length > 0 && (
              <>
                <Text style={styles.inputLabel}>Account (optional)</Text>
                <View style={styles.pickerContainer}>
                  <TouchableOpacity
                    style={[styles.pickerOption, !newUserStoreId && styles.pickerOptionSelected]}
                    onPress={() => setNewUserStoreId(null)}
                  >
                    <Text style={[styles.pickerOptionText, !newUserStoreId && styles.pickerOptionTextSelected]}>
                      No Store
                    </Text>
                  </TouchableOpacity>
                  {stores.map((store) => (
                    <TouchableOpacity
                      key={store._id}
                      style={[styles.pickerOption, newUserStoreId === store._id && styles.pickerOptionSelected]}
                      onPress={() => setNewUserStoreId(store._id)}
                    >
                      <Text style={[styles.pickerOptionText, newUserStoreId === store._id && styles.pickerOptionTextSelected]}>
                        {store.name}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            )}

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
                  {...tid(`new-user-role-${role}`)}
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
              {...tid('new-user-send-invite')}
            >
              <View style={[styles.checkbox, sendInvite && styles.checkboxChecked]}>
                {sendInvite && <Ionicons name="checkmark" size={16} color="#000" />}
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
      ))}

      {/* Success: credentials */}
      {!!createdUser && (Platform.OS === 'web' ? (
        <View style={[styles.successOverlay, { position: 'fixed' as any, top: 0, left: 0, right: 0, bottom: 0, zIndex: 99999, paddingTop: 16 }]}>
          <View style={styles.successModal}>
            <View style={styles.successIcon}>
              <Ionicons name="checkmark-circle" size={48} color="#34C759" />
            </View>
            
            <Text style={styles.successTitle}>Team member created</Text>
            <Text style={styles.successSubtitle}>
              {createdUser?.name} will get a text and email with activation steps: open the app, tap "Activate my account", verify with a 6-digit code, then choose a password.
            </Text>
            
            <View style={styles.credentialsBox}>
              <View style={styles.credentialRow}>
                <Text style={styles.credentialLabel}>Email:</Text>
                <Text style={styles.credentialValue}>{createdUser?.email}</Text>
              </View>
              {createdUser?.temp_password && (
                <View style={styles.credentialRow}>
                  <Text style={styles.credentialLabel}>Backup password:</Text>
                  <Text style={styles.credentialValue}>{createdUser?.temp_password}</Text>
                </View>
              )}
            </View>
            
            {createdUser?.temp_password && (
              <View style={styles.successActions}>
                <WebSafeButton
                  onPress={handleCopyPassword}
                  variant="secondary"
                  testID="copy-password"
                  style={{ flex: 1 }}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Ionicons name="copy-outline" size={18} color="#FFFFFF" />
                    <Text style={{ color: '#FFFFFF', fontWeight: '600' }}>Copy Backup</Text>
                  </View>
                </WebSafeButton>
                
                <WebSafeButton
                  onPress={handleCopyCredentials}
                  variant="primary"
                  testID="copy-all"
                  style={{ flex: 1 }}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Ionicons name="clipboard-outline" size={18} color="#FFFFFF" />
                    <Text style={{ color: '#FFFFFF', fontWeight: '600' }}>Copy All</Text>
                  </View>
                </WebSafeButton>
              </View>
            )}
            
            <WebSafeButton
              onPress={handleCloseSuccessModal}
              variant="ghost"
              testID="close-success"
              style={{ marginTop: 16 }}
            >
              <Text style={{ color: colors.accent, fontSize: FS.heading, fontWeight: '700' }}>Done</Text>
            </WebSafeButton>
          </View>
        </View>
      ) : (
        <Modal visible animationType="fade" transparent>
          <View style={styles.successOverlay}>
          <View style={styles.successModal}>
            <View style={styles.successIcon}>
              <Ionicons name="checkmark-circle" size={48} color="#34C759" />
            </View>
            
            <Text style={styles.successTitle}>Team member created</Text>
            <Text style={styles.successSubtitle}>
              {createdUser?.name} will get a text and email with activation steps: open the app, tap "Activate my account", verify with a 6-digit code, then choose a password.
            </Text>
            
            <View style={styles.credentialsBox}>
              <View style={styles.credentialRow}>
                <Text style={styles.credentialLabel}>Email:</Text>
                <Text style={styles.credentialValue}>{createdUser?.email}</Text>
              </View>
              {createdUser?.temp_password && (
                <View style={styles.credentialRow}>
                  <Text style={styles.credentialLabel}>Backup password:</Text>
                  <Text style={styles.credentialValue}>{createdUser?.temp_password}</Text>
                </View>
              )}
            </View>
            
            {createdUser?.temp_password && (
              <View style={styles.successActions}>
                <WebSafeButton
                  onPress={handleCopyPassword}
                  variant="secondary"
                  testID="copy-password"
                  style={{ flex: 1 }}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Ionicons name="copy-outline" size={18} color="#FFFFFF" />
                    <Text style={{ color: '#FFFFFF', fontWeight: '600' }}>Copy Backup</Text>
                  </View>
                </WebSafeButton>
                
                <WebSafeButton
                  onPress={handleCopyCredentials}
                  variant="primary"
                  testID="copy-all"
                  style={{ flex: 1 }}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Ionicons name="clipboard-outline" size={18} color="#FFFFFF" />
                    <Text style={{ color: '#FFFFFF', fontWeight: '600' }}>Copy All</Text>
                  </View>
                </WebSafeButton>
              </View>
            )}
            
            <WebSafeButton
              onPress={handleCloseSuccessModal}
              variant="ghost"
              testID="close-success"
              style={{ marginTop: 16 }}
            >
              <Text style={{ color: colors.accent, fontSize: FS.heading, fontWeight: '700' }}>Done</Text>
            </WebSafeButton>
          </View>
          </View>
        </Modal>
      ))}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: FS.body,
    color: colors.text,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    padding: 16,
    paddingTop: 4,
    paddingBottom: 40,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
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
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
    flex: 1,
  },
  countBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 8,
  },
  countText: {
    fontSize: FS.secondary,
    fontWeight: '800',
  },
  userCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    marginBottom: 8,
    marginLeft: 16,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  userAvatarPhoto: {
    width: 40,
    height: 40,
    borderRadius: 20,
  },
  userAvatarText: {
    fontSize: FS.body,
    fontWeight: '700',
  },
  userInfo: {
    flex: 1,
    minWidth: 0,
    marginLeft: 12,
  },
  userName: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
    flexShrink: 1,
  },
  userEmail: {
    fontSize: FS.secondary,
    color: colors.textSecondary,
    marginTop: 2,
    flexShrink: 1,
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
    paddingHorizontal: 32,
  },
  emptyText: {
    color: colors.text,
    fontSize: FS.heading,
    fontWeight: '700',
    marginTop: 16,
    textAlign: 'center',
  },
  emptySubtext: {
    color: colors.textSecondary,
    fontSize: FS.body,
    marginTop: 6,
    textAlign: 'center',
  },
  emptyBtn: {
    marginTop: 18,
    backgroundColor: colors.accent,
    borderRadius: 14,
    paddingHorizontal: 22,
    paddingVertical: 12,
  },
  emptyBtnText: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: '#000',
  },
  inactiveCard: {
    opacity: 0.6,
  },
  inactiveText: {
    color: colors.textSecondary,
  },
  deletionSource: {
    fontSize: 13,
    color: '#FF9500',
    marginTop: 2,
    fontStyle: 'italic',
  },
  inactiveSectionHeader: {
    marginTop: 24,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
    paddingTop: 24,
  },
  // Modal Styles
  modalContainer: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  modalCancel: {
    fontSize: FS.heading,
    color: colors.textSecondary,
  },
  modalTitle: {
    fontSize: FS.nav,
    fontWeight: '700',
    color: colors.text,
  },
  modalSave: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.accent,
  },
  modalContent: {
    padding: 16,
  },
  inputLabel: {
    fontSize: FS.secondary,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    marginTop: 16,
    marginLeft: 4,
  },
  modalInput: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    fontSize: FS.body,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  roleSelector: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  roleOption: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  roleOptionText: {
    fontSize: FS.body,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  inviteToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 24,
    padding: 16,
    backgroundColor: colors.card,
    borderRadius: 12,
    gap: 12,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxChecked: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  inviteToggleText: {
    flex: 1,
  },
  inviteToggleTitle: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
  },
  inviteToggleSubtitle: {
    fontSize: FS.secondary,
    color: colors.textSecondary,
    marginTop: 2,
  },
  warningBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginTop: 16,
    padding: 12,
    backgroundColor: '#FF950020',
    borderRadius: 10,
  },
  warningText: {
    flex: 1,
    fontSize: 15,
    color: '#FF9500',
    lineHeight: 18,
  },
  pickerContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  pickerOption: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  pickerOptionSelected: {
    backgroundColor: 'rgba(201,169,98,0.12)',
    borderColor: colors.accent,
  },
  pickerOptionText: {
    fontSize: FS.body,
    color: colors.textSecondary,
  },
  pickerOptionTextSelected: {
    color: colors.accent,
    fontWeight: '700',
  },
  // Success Modal Styles
  successOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  successModal: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 24,
    width: '100%',
    maxWidth: 400,
    alignItems: 'center',
  },
  successIcon: {
    marginBottom: 16,
  },
  successTitle: {
    fontSize: FS.title,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  successSubtitle: {
    fontSize: FS.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 20,
  },
  credentialsBox: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    width: '100%',
    marginBottom: 20,
  },
  credentialRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  credentialLabel: {
    fontSize: FS.body,
    color: colors.textSecondary,
    width: 80,
  },
  credentialValue: {
    fontSize: FS.body,
    color: colors.text,
    fontWeight: '600',
    flex: 1,
  },
  successActions: {
    flexDirection: 'row',
    gap: 12,
    width: '100%',
  },
});
