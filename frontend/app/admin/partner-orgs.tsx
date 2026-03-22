import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';

interface OrgItem {
  _id: string;
  name: string;
  slug?: string;
  stores?: StoreItem[];
}

interface StoreItem {
  _id: string;
  name: string;
  city?: string;
  state?: string;
  active: boolean;
  user_count?: number;
}

export default function PartnerOrgsScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const { id: partnerId, name: partnerName } = useLocalSearchParams<{ id: string; name: string }>();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [orgs, setOrgs] = useState<OrgItem[]>([]);
  const [orgStores, setOrgStores] = useState<Record<string, StoreItem[]>>({});

  // Link existing org
  const [showLinkOrg, setShowLinkOrg] = useState(false);
  const [allOrgs, setAllOrgs] = useState<any[]>([]);
  const [loadingAllOrgs, setLoadingAllOrgs] = useState(false);
  const [linkSearch, setLinkSearch] = useState('');

  // Create account modal
  const [showCreateAccount, setShowCreateAccount] = useState(false);
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [selectedOrgId, setSelectedOrgId] = useState('');
  const [newAccount, setNewAccount] = useState({ name: '', phone: '', city: '', state: '' });

  const loadPartnerOrgs = useCallback(async () => {
    if (!partnerId) return;
    try {
      const res = await api.get(`/admin/partners/${partnerId}/orgs`);
      const orgsList: OrgItem[] = res.data;
      setOrgs(orgsList);

      // Load stores for each org
      const storesMap: Record<string, StoreItem[]> = {};
      await Promise.all(
        orgsList.map(async (org) => {
          try {
            const storeRes = await api.get(`/admin/stores?organization_id=${org._id}`);
            storesMap[org._id] = storeRes.data;
          } catch { storesMap[org._id] = []; }
        })
      );
      setOrgStores(storesMap);
    } catch (e) {
      console.error('Failed to load partner orgs:', e);
    }
    setLoading(false);
  }, [partnerId]);

  useEffect(() => { loadPartnerOrgs(); }, [loadPartnerOrgs]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadPartnerOrgs();
    setRefreshing(false);
  };

  const loadAllOrgs = async () => {
    setLoadingAllOrgs(true);
    try {
      const res = await api.get('/admin/organizations');
      const linkedIds = new Set(orgs.map(o => o._id));
      setAllOrgs(res.data.filter((o: any) => !linkedIds.has(o._id)));
    } catch (e) { console.error(e); }
    setLoadingAllOrgs(false);
  };

  const handleLinkOrg = async (orgId: string, orgName: string) => {
    try {
      await api.post(`/admin/partners/${partnerId}/assign-org/${orgId}`);
      showSimpleAlert('Success', `${orgName} linked to ${partnerName}`);
      setShowLinkOrg(false);
      setLinkSearch('');
      loadPartnerOrgs();
    } catch (e) {
      showSimpleAlert('Error', 'Failed to link organization');
    }
  };

  const handleUnlinkOrg = (orgId: string, orgName: string) => {
    showConfirm(
      'Unlink Organization',
      `Remove "${orgName}" from ${partnerName}? The organization and its accounts will remain but will no longer be associated with this partner.`,
      async () => {
        try {
          await api.post(`/admin/partners/${partnerId}/unassign-org/${orgId}`);
          loadPartnerOrgs();
        } catch (e) {
          showSimpleAlert('Error', 'Failed to unlink organization');
        }
      },
      undefined,
      'Unlink',
      'Cancel'
    );
  };

  const openCreateAccount = (orgId: string) => {
    setSelectedOrgId(orgId);
    setNewAccount({ name: '', phone: '', city: '', state: '' });
    setShowCreateAccount(true);
  };

  const handleCreateAccount = async () => {
    if (!newAccount.name.trim()) {
      showSimpleAlert('Error', 'Account name is required');
      return;
    }
    setCreatingAccount(true);
    try {
      await api.post('/admin/stores', {
        name: newAccount.name.trim(),
        phone: newAccount.phone.trim(),
        city: newAccount.city.trim(),
        state: newAccount.state.trim(),
        organization_id: selectedOrgId,
        partner_id: partnerId,
      });
      showSimpleAlert('Success', 'Account created successfully');
      setShowCreateAccount(false);
      loadPartnerOrgs();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to create account';
      showSimpleAlert('Error', msg);
    }
    setCreatingAccount(false);
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.headerBtn} data-testid="back-button">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={s.headerTitle} numberOfLines={1}>{partnerName || 'Partner'}</Text>
          <Text style={s.headerSubtitle}>Organizations & Accounts</Text>
        </View>
        <TouchableOpacity
          onPress={() => { loadAllOrgs(); setShowLinkOrg(!showLinkOrg); }}
          style={s.headerBtn}
          data-testid="link-org-button"
        >
          <Ionicons name={showLinkOrg ? 'close' : 'link'} size={22} color="#C9A962" />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
      >
        {/* Link existing org panel */}
        {showLinkOrg && (
          <View style={s.linkPanel} data-testid="link-org-panel">
            <Text style={s.linkTitle}>Link Existing Organization</Text>
            <TextInput
              style={s.linkSearch}
              placeholder="Search organizations..."
              placeholderTextColor={colors.textSecondary}
              value={linkSearch}
              onChangeText={setLinkSearch}
              data-testid="link-org-search"
            />
            {loadingAllOrgs ? (
              <ActivityIndicator size="small" color="#C9A962" style={{ padding: 16 }} />
            ) : allOrgs.filter(o => !linkSearch || o.name?.toLowerCase().includes(linkSearch.toLowerCase())).length === 0 ? (
              <Text style={s.linkEmpty}>No unlinked organizations available</Text>
            ) : (
              allOrgs
                .filter(o => !linkSearch || o.name?.toLowerCase().includes(linkSearch.toLowerCase()))
                .slice(0, 8)
                .map(org => (
                  <TouchableOpacity
                    key={org._id}
                    style={s.linkItem}
                    onPress={() => handleLinkOrg(org._id, org.name)}
                    data-testid={`link-org-${org._id}`}
                  >
                    <Ionicons name="business-outline" size={20} color="#34C759" />
                    <Text style={s.linkItemName}>{org.name}</Text>
                    <Ionicons name="add-circle-outline" size={22} color="#007AFF" />
                  </TouchableOpacity>
                ))
            )}
          </View>
        )}

        {loading ? (
          <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 40 }} />
        ) : orgs.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="business-outline" size={48} color={colors.surface} />
            <Text style={s.emptyText}>No organizations linked</Text>
            <Text style={s.emptySub}>Link an existing organization or create accounts directly</Text>
            <TouchableOpacity
              style={s.emptyBtn}
              onPress={() => { loadAllOrgs(); setShowLinkOrg(true); }}
              data-testid="empty-link-org-button"
            >
              <Ionicons name="link" size={18} color="#000" />
              <Text style={s.emptyBtnText}>Link Organization</Text>
            </TouchableOpacity>
          </View>
        ) : (
          orgs.map(org => {
            const stores = orgStores[org._id] || [];
            return (
              <View key={org._id} style={s.orgCard} data-testid={`org-card-${org._id}`}>
                <View style={s.orgHeader}>
                  <TouchableOpacity
                    style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 }}
                    onPress={() => router.push(`/admin/organizations/${org._id}`)}
                  >
                    <View style={s.orgIcon}>
                      <Ionicons name="business" size={22} color="#C9A962" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.orgName}>{org.name}</Text>
                      <Text style={s.orgSub}>{stores.length} account{stores.length !== 1 ? 's' : ''}</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>

                {/* Stores/accounts list */}
                {stores.map(store => (
                  <TouchableOpacity
                    key={store._id}
                    style={s.storeRow}
                    onPress={() => router.push(`/admin/stores/${store._id}`)}
                    data-testid={`store-row-${store._id}`}
                  >
                    <Ionicons name="storefront" size={18} color="#34C759" />
                    <View style={{ flex: 1, marginLeft: 10 }}>
                      <Text style={s.storeName}>{store.name}</Text>
                      <Text style={s.storeLoc}>
                        {[store.city, store.state].filter(Boolean).join(', ') || 'No location'}
                      </Text>
                    </View>
                    <View style={[s.statusDot, { backgroundColor: store.active !== false ? '#34C759' : '#FF3B30' }]} />
                  </TouchableOpacity>
                ))}

                {/* Actions */}
                <View style={s.orgActions}>
                  <TouchableOpacity
                    style={s.createAccountBtn}
                    onPress={() => openCreateAccount(org._id)}
                    data-testid={`create-account-btn-${org._id}`}
                  >
                    <Ionicons name="add-circle" size={18} color="#007AFF" />
                    <Text style={s.createAccountText}>Create Account</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={s.unlinkBtn}
                    onPress={() => handleUnlinkOrg(org._id, org.name)}
                    data-testid={`unlink-org-btn-${org._id}`}
                  >
                    <Ionicons name="remove-circle-outline" size={16} color="#FF3B30" />
                    <Text style={s.unlinkText}>Unlink</Text>
                  </TouchableOpacity>
                </View>
              </View>
            );
          })
        )}
      </ScrollView>

      {/* Create Account Modal */}
      <Modal visible={showCreateAccount} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowCreateAccount(false)} data-testid="modal-cancel-btn">
              <Text style={s.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>New Account</Text>
            <TouchableOpacity onPress={handleCreateAccount} disabled={creatingAccount} data-testid="modal-create-btn">
              {creatingAccount ? (
                <ActivityIndicator size="small" color="#C9A962" />
              ) : (
                <Text style={s.modalSave}>Create</Text>
              )}
            </TouchableOpacity>
          </View>
          <ScrollView style={s.modalContent}>
            <Text style={s.inputLabel}>Account Name *</Text>
            <TextInput
              style={s.input}
              placeholder="e.g., Ken Garff Honda Downtown"
              placeholderTextColor={colors.textSecondary}
              value={newAccount.name}
              onChangeText={t => setNewAccount({ ...newAccount, name: t })}
              data-testid="new-account-name-input"
            />
            <Text style={s.inputLabel}>Phone</Text>
            <TextInput
              style={s.input}
              placeholder="+1 (555) 123-4567"
              placeholderTextColor={colors.textSecondary}
              value={newAccount.phone}
              onChangeText={t => setNewAccount({ ...newAccount, phone: t })}
              keyboardType="phone-pad"
              data-testid="new-account-phone-input"
            />
            <View style={{ flexDirection: 'row', gap: 12 }}>
              <View style={{ flex: 1 }}>
                <Text style={s.inputLabel}>City</Text>
                <TextInput
                  style={s.input}
                  placeholder="Salt Lake City"
                  placeholderTextColor={colors.textSecondary}
                  value={newAccount.city}
                  onChangeText={t => setNewAccount({ ...newAccount, city: t })}
                  data-testid="new-account-city-input"
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.inputLabel}>State</Text>
                <TextInput
                  style={s.input}
                  placeholder="UT"
                  placeholderTextColor={colors.textSecondary}
                  value={newAccount.state}
                  onChangeText={t => setNewAccount({ ...newAccount, state: t })}
                  maxLength={2}
                  autoCapitalize="characters"
                  data-testid="new-account-state-input"
                />
              </View>
            </View>
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card,
  },
  headerBtn: { padding: 4, minWidth: 44 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  headerSubtitle: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  scroll: { padding: 16 },

  // Link panel
  linkPanel: {
    backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 16,
    borderWidth: 1, borderColor: colors.surface,
  },
  linkTitle: { fontSize: 17, fontWeight: '600', color: colors.text, marginBottom: 10 },
  linkSearch: {
    backgroundColor: colors.surface, borderRadius: 10, padding: 12, fontSize: 17,
    color: colors.text, marginBottom: 10, borderWidth: 1, borderColor: colors.borderLight,
  },
  linkEmpty: { fontSize: 16, color: colors.textSecondary, textAlign: 'center', padding: 16 },
  linkItem: {
    flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10,
    borderTopWidth: 1, borderTopColor: colors.surface,
  },
  linkItemName: { flex: 1, fontSize: 17, color: colors.text, fontWeight: '500' },

  // Empty state
  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { fontSize: 19, color: '#8E8E93', marginTop: 12 },
  emptySub: { fontSize: 16, color: colors.textSecondary, marginTop: 4, textAlign: 'center', paddingHorizontal: 40 },
  emptyBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#C9A962',
    paddingHorizontal: 20, paddingVertical: 12, borderRadius: 12, marginTop: 20,
  },
  emptyBtnText: { fontSize: 17, fontWeight: '600', color: '#000' },

  // Org card
  orgCard: {
    backgroundColor: colors.card, borderRadius: 14, marginBottom: 16,
    borderWidth: 1, borderColor: colors.surface, overflow: 'hidden',
  },
  orgHeader: {
    flexDirection: 'row', alignItems: 'center', padding: 14,
    borderBottomWidth: 1, borderBottomColor: colors.surface,
  },
  orgIcon: {
    width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#C9A96215',
  },
  orgName: { fontSize: 18, fontWeight: '600', color: colors.text },
  orgSub: { fontSize: 15, color: colors.textSecondary, marginTop: 1 },

  // Store rows
  storeRow: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: colors.surface,
  },
  storeName: { fontSize: 16, fontWeight: '500', color: colors.text },
  storeLoc: { fontSize: 14, color: colors.textSecondary, marginTop: 1 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },

  // Org actions
  orgActions: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 12,
  },
  createAccountBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#007AFF15', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8,
  },
  createAccountText: { fontSize: 15, fontWeight: '600', color: '#007AFF' },
  unlinkBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 8,
  },
  unlinkText: { fontSize: 14, color: '#FF3B30', fontWeight: '500' },

  // Modal
  modalContainer: { flex: 1, backgroundColor: colors.bg },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16, borderBottomWidth: 1, borderBottomColor: colors.surface,
  },
  modalCancel: { fontSize: 18, color: '#007AFF' },
  modalTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  modalSave: { fontSize: 18, fontWeight: '600', color: '#C9A962' },
  modalContent: { padding: 16 },
  inputLabel: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 14 },
  input: {
    backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 18,
    color: colors.text, borderWidth: 1, borderColor: colors.surface,
  },
});
