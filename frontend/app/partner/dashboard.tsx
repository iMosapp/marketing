import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';

export default function PartnerDashboard() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const user = useAuthStore((state) => state.user);
  const [orgs, setOrgs] = useState<any[]>([]);
  const [expandedOrg, setExpandedOrg] = useState<string | null>(null);
  const [orgStores, setOrgStores] = useState<Record<string, any[]>>({});
  const [orgUsers, setOrgUsers] = useState<Record<string, any[]>>({});

  useEffect(() => { loadData(); }, [user?._id]);

  const loadData = async () => {
    try {
      const res = await api.get('/partners/portal/orgs');
      setOrgs(Array.isArray(res.data) ? res.data : []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); setRefreshing(false); }
  };

  const toggleOrg = async (orgId: string) => {
    if (expandedOrg === orgId) { setExpandedOrg(null); return; }
    setExpandedOrg(orgId);
    if (!orgStores[orgId]) {
      try {
        const [storesRes, usersRes] = await Promise.all([
          api.get(`/partners/portal/orgs/${orgId}/stores`),
          api.get(`/partners/portal/orgs/${orgId}/users`),
        ]);
        setOrgStores(prev => ({ ...prev, [orgId]: storesRes.data || [] }));
        setOrgUsers(prev => ({ ...prev, [orgId]: usersRes.data || [] }));
      } catch (e) { console.error(e); }
    }
  };

  const getTotalUsers = (orgId: string) => orgUsers[orgId]?.length || 0;
  const getTotalStores = (orgId: string) => orgStores[orgId]?.length || 0;

  if (loading) return (
    <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}>
      <ActivityIndicator size="large" color="#C9A962" />
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Partner Portal</Text>
        <View style={{ width: 36 }} />
      </View>

      <ScrollView
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadData(); }} tintColor="#C9A962" />}
      >
        {/* Onboard Button */}
        <TouchableOpacity
          style={s.onboardBtn}
          onPress={() => router.push('/partner/onboard' as any)}
          activeOpacity={0.8}
          data-testid="partner-onboard-btn"
        >
          <View style={s.onboardIcon}>
            <Ionicons name="rocket" size={24} color="#000" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.onboardTitle}>Onboard New Location</Text>
            <Text style={s.onboardSub}>Add a store & team to an existing org</Text>
          </View>
          <Ionicons name="arrow-forward" size={22} color="#000" />
        </TouchableOpacity>

        {/* Training Hub Link */}
        <TouchableOpacity
          style={[s.onboardBtn, { backgroundColor: '#AF52DE' }]}
          onPress={() => router.push('/training-hub' as any)}
          activeOpacity={0.8}
          data-testid="partner-training-btn"
        >
          <View style={[s.onboardIcon, { backgroundColor: '#FFF' }]}>
            <Ionicons name="school" size={24} color="#AF52DE" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[s.onboardTitle, { color: '#FFF' }]}>Training Hub</Text>
            <Text style={[s.onboardSub, { color: 'rgba(255,255,255,0.8)' }]}>Learn how to sell, onboard, and support clients</Text>
          </View>
          <Ionicons name="arrow-forward" size={22} color="#FFF" />
        </TouchableOpacity>

        {/* Stats Row */}
        <View style={s.statsRow}>
          <View style={s.statCard}>
            <Text style={s.statNum}>{orgs.length}</Text>
            <Text style={s.statLabel}>Organizations</Text>
          </View>
          <View style={s.statCard}>
            <Text style={s.statNum}>{Object.values(orgStores).reduce((a, b) => a + b.length, 0)}</Text>
            <Text style={s.statLabel}>Locations</Text>
          </View>
          <View style={s.statCard}>
            <Text style={s.statNum}>{Object.values(orgUsers).reduce((a, b) => a + b.length, 0)}</Text>
            <Text style={s.statLabel}>Users</Text>
          </View>
        </View>

        {/* Organizations */}
        <Text style={s.sectionTitle}>Your Organizations</Text>
        {orgs.length === 0 ? (
          <View style={s.emptyState}>
            <Ionicons name="business-outline" size={40} color={colors.textTertiary} />
            <Text style={s.emptyText}>No organizations assigned yet.</Text>
            <Text style={s.emptySubtext}>Ask your admin to assign organizations to your partner account.</Text>
          </View>
        ) : (
          orgs.map(org => {
            const isExpanded = expandedOrg === org._id;
            const stores = orgStores[org._id] || [];
            const users = orgUsers[org._id] || [];
            return (
              <View key={org._id} style={s.orgCard} data-testid={`org-card-${org._id}`}>
                <TouchableOpacity style={s.orgHeader} onPress={() => toggleOrg(org._id)} activeOpacity={0.7}>
                  <View style={s.orgIconBox}>
                    <Ionicons name="business" size={20} color="#C9A962" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.orgName}>{org.name}</Text>
                    <Text style={s.orgMeta}>
                      {org.city ? `${org.city}, ${org.state}` : org.state || 'No location set'}
                      {isExpanded ? ` \u2022 ${stores.length} locations \u2022 ${users.length} users` : ''}
                    </Text>
                  </View>
                  <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={20} color={colors.textTertiary} />
                </TouchableOpacity>

                {isExpanded && (
                  <View style={s.orgBody}>
                    {/* Stores */}
                    <View style={s.subSection}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                        <Text style={s.subLabel}>Locations ({stores.length})</Text>
                      </View>
                      {stores.length === 0 ? (
                        <Text style={s.noDataText}>No locations yet</Text>
                      ) : stores.map(store => (
                        <View key={store._id} style={s.subItem}>
                          <Ionicons name="storefront-outline" size={16} color={colors.textSecondary} />
                          <View style={{ flex: 1, marginLeft: 8 }}>
                            <Text style={s.subItemTitle}>{store.name}</Text>
                            {store.city && <Text style={s.subItemMeta}>{store.city}, {store.state}</Text>}
                          </View>
                        </View>
                      ))}
                    </View>

                    {/* Users */}
                    <View style={s.subSection}>
                      <Text style={s.subLabel}>Team ({users.length})</Text>
                      {users.length === 0 ? (
                        <Text style={s.noDataText}>No users yet</Text>
                      ) : users.map(u => (
                        <View key={u._id} style={s.subItem}>
                          <View style={s.userAvatar}>
                            <Text style={{ fontSize: 13, fontWeight: '700', color: '#C9A962' }}>{(u.name || '?')[0]}</Text>
                          </View>
                          <View style={{ flex: 1, marginLeft: 8 }}>
                            <Text style={s.subItemTitle}>{u.name}</Text>
                            <Text style={s.subItemMeta}>{u.email} \u2022 {u.role}</Text>
                          </View>
                          <View style={[s.roleBadge, u.onboarding_complete === false && { backgroundColor: '#FF950020', borderColor: '#FF9500' }]}>
                            <Text style={[s.roleBadgeText, u.onboarding_complete === false && { color: '#FF9500' }]}>
                              {u.onboarding_complete === false ? 'Pending' : u.role === 'manager' ? 'Mgr' : u.role === 'admin' ? 'Admin' : 'User'}
                            </Text>
                          </View>
                        </View>
                      ))}
                    </View>

                    {/* Quick Add */}
                    <TouchableOpacity
                      style={s.quickAddBtn}
                      onPress={() => router.push(`/partner/onboard?org_id=${org._id}&org_name=${encodeURIComponent(org.name)}` as any)}
                      data-testid={`add-to-org-${org._id}`}
                    >
                      <Ionicons name="add-circle-outline" size={18} color="#C9A962" />
                      <Text style={{ fontSize: 16, fontWeight: '600', color: '#C9A962' }}>Add Location & Team</Text>
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 19, fontWeight: '700', color: colors.text },
  content: { padding: 16, paddingBottom: 40, maxWidth: 700, alignSelf: 'center', width: '100%' },
  onboardBtn: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#C9A962', borderRadius: 16, padding: 18, gap: 14, marginBottom: 16 },
  onboardIcon: { width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(0,0,0,0.15)', alignItems: 'center', justifyContent: 'center' },
  onboardTitle: { fontSize: 18, fontWeight: '700', color: '#000' },
  onboardSub: { fontSize: 15, color: 'rgba(0,0,0,0.6)', marginTop: 2 },
  statsRow: { flexDirection: 'row', gap: 10, marginBottom: 20 },
  statCard: { flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: colors.border },
  statNum: { fontSize: 24, fontWeight: '800', color: colors.text },
  statLabel: { fontSize: 13, color: colors.textSecondary, marginTop: 2, fontWeight: '500' },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 12 },
  emptyState: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyText: { fontSize: 18, fontWeight: '600', color: colors.textSecondary },
  emptySubtext: { fontSize: 15, color: colors.textTertiary, textAlign: 'center', maxWidth: 280 },
  orgCard: { backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, marginBottom: 12, overflow: 'hidden' },
  orgHeader: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  orgIconBox: { width: 40, height: 40, borderRadius: 10, backgroundColor: '#C9A96218', alignItems: 'center', justifyContent: 'center' },
  orgName: { fontSize: 18, fontWeight: '700', color: colors.text },
  orgMeta: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  orgBody: { borderTopWidth: 1, borderTopColor: colors.border, paddingHorizontal: 16, paddingBottom: 12 },
  subSection: { paddingTop: 12 },
  subLabel: { fontSize: 15, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 },
  noDataText: { fontSize: 15, color: colors.textTertiary, fontStyle: 'italic', paddingVertical: 4 },
  subItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border },
  subItemTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  subItemMeta: { fontSize: 14, color: colors.textSecondary, marginTop: 1 },
  userAvatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#C9A96218', alignItems: 'center', justifyContent: 'center' },
  roleBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border },
  roleBadgeText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase' },
  quickAddBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 12, marginTop: 12, borderRadius: 10, borderWidth: 2, borderColor: '#C9A96240', borderStyle: 'dashed' },
});
