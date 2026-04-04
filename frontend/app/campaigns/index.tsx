import React, { useState, useEffect, useCallback, useRef } from 'react';
import { showAlert } from '../../services/alert';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
  ScrollView,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { campaignsAPI } from '../../services/api';
import Toggle from '../../components/Toggle';
import { useThemeStore } from '../../store/themeStore';
import DraggableFlatList, {
  ScaleDecorator,
  RenderItemParams,
} from 'react-native-draggable-flatlist';
import api from '../../services/api';

export default function CampaignsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const saveTimer = useRef<any>(null);

  useEffect(() => {
    loadCampaigns();
  }, [user]);

  const loadCampaigns = async () => {
    if (!user) return;
    try {
      setLoading(true);
      const data = await campaignsAPI.getAll(user._id);
      setCampaigns(data);
    } catch (error) {
      console.error('Failed to load campaigns:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadCampaigns();
    setRefreshing(false);
  };

  // Persist new order to backend (debounced 400ms after drag ends)
  const persistOrder = useCallback((ordered: any[]) => {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!user?._id) return;
      try {
        await api.post(`/campaigns/${user._id}/reorder`, {
          campaign_ids: ordered.map((c: any) => c._id || c.id),
        });
      } catch (e) {
        console.warn('Failed to save campaign order:', e);
      }
    }, 400);
  }, [user?._id]);

  const handleDragEnd = ({ data }: { data: any[] }) => {
    setCampaigns(data);
    persistOrder(data);
  };

  const toggleCampaign = async (id: string) => {
    const campaign = campaigns.find((c) => c._id === id || c.id === id);
    if (!campaign || !user?._id) return;
    const newActiveState = !campaign.active;
    setCampaigns(campaigns.map((c) => (c._id === id || c.id === id ? { ...c, active: newActiveState } : c)));
    try {
      await campaignsAPI.update(user._id, id, { active: newActiveState });
    } catch (error) {
      setCampaigns(campaigns.map((c) => (c._id === id || c.id === id ? { ...c, active: !newActiveState } : c)));
      showAlert('Error', 'Failed to update campaign status');
    }
  };

  const getCampaignIcon = (type: string) => {
    switch (type) {
      case 'birthday': return { icon: 'gift', color: '#FF9500' };
      case 'anniversary': return { icon: 'heart', color: '#FF3B30' };
      case 'check_in': return { icon: 'chatbubble', color: '#007AFF' };
      default: return { icon: 'create', color: '#34C759' };
    }
  };

  const formatDate = (date: Date | null) => {
    if (!date) return 'Never';
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    if (diffInHours < 24) return `${Math.floor(diffInHours)}h ago`;
    if (diffInHours < 168) return `${Math.floor(diffInHours / 24)}d ago`;
    return date.toLocaleDateString();
  };

  const renderItem = ({ item, drag, isActive }: RenderItemParams<any>) => {
    const iconData = getCampaignIcon(item.type);
    const scopeLabel = item.scope === 'org' ? 'Org' : item.scope === 'account' ? 'Account' : null;
    return (
      <ScaleDecorator>
        <TouchableOpacity
          style={[
            styles.campaignCard,
            isActive && { opacity: 0.9, shadowOpacity: 0.3, elevation: 8 },
          ]}
          onPress={() => !isActive && router.push(`/campaigns/${item._id || item.id}`)}
          activeOpacity={0.85}
          data-testid={`campaign-card-${item._id}`}
        >
          {/* Drag handle — long press to drag, short tap scrolls normally */}
          <TouchableOpacity
            onLongPress={drag}
            delayLongPress={300}
            style={styles.dragHandle}
            hitSlop={{ top: 10, bottom: 10, left: 6, right: 6 }}
          >
            <Ionicons name="reorder-three" size={22} color={isActive ? '#C9A962' : colors.textTertiary} />
          </TouchableOpacity>

          <View style={[styles.iconContainer, { backgroundColor: `${iconData.color}20` }]}>
            <Ionicons name={iconData.icon as any} size={24} color={iconData.color} />
          </View>

          <View style={styles.campaignContent}>
            <View style={styles.campaignHeader}>
              <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={styles.campaignName} numberOfLines={1}>{item.name}</Text>
                {scopeLabel && (
                  <View style={{ backgroundColor: '#C9A96220', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2 }}>
                    <Text style={{ fontSize: 11, color: '#C9A962', fontWeight: '700' }}>{scopeLabel}</Text>
                  </View>
                )}
              </View>
              <Toggle
                value={item.active}
                onValueChange={() => toggleCampaign(item._id || item.id)}
                activeColor="#007AFF"
              />
            </View>
            <View style={styles.statsRow}>
              <View style={styles.stat}>
                <Ionicons name="paper-plane" size={14} color={colors.textSecondary} />
                <Text style={styles.statText}>{item.messages_sent_count || 0} sent</Text>
              </View>
              <View style={styles.stat}>
                <Ionicons name="time" size={14} color={colors.textSecondary} />
                <Text style={styles.statText}>{formatDate(item.last_sent_at ? new Date(item.last_sent_at) : null)}</Text>
              </View>
              {(item.enrollments_active > 0) && (
                <View style={styles.stat}>
                  <Ionicons name="people" size={14} color={colors.textSecondary} />
                  <Text style={styles.statText}>{item.enrollments_active} active</Text>
                </View>
              )}
            </View>
          </View>
        </TouchableOpacity>
      </ScaleDecorator>
    );
  };

  // Group campaigns by scope
  const groupedCampaigns = {
    org:     campaigns.filter(c => c.scope === 'org'),
    account: campaigns.filter(c => c.scope === 'account' || c.ownership_level === 'store'),
    personal: campaigns.filter(c => !c.scope || c.scope === 'personal'),
  };
  const hasGroups = groupedCampaigns.org.length > 0 || groupedCampaigns.account.length > 0;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Campaigns</Text>
        <View style={styles.headerButtons}>
          <TouchableOpacity onPress={() => router.push('/campaigns/dashboard')} style={styles.dashboardButton}>
            <Ionicons name="speedometer-outline" size={24} color="#007AFF" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => router.push('/campaigns/new')} style={styles.addButton}>
            <Ionicons name="add-circle" size={32} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Stats Banner */}
      <View style={styles.statsBanner}>
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{campaigns.filter((c) => c.active).length}</Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{campaigns.reduce((sum, c) => sum + (c.messages_sent_count || 0), 0)}</Text>
          <Text style={styles.statLabel}>Total Sent</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{campaigns.length}</Text>
          <Text style={styles.statLabel}>Campaigns</Text>
        </View>
      </View>

      {/* Drag hint */}
      {campaigns.length > 1 && !loading && (
        <View style={{ paddingHorizontal: 16, paddingBottom: 6, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Ionicons name="reorder-three" size={14} color={colors.textTertiary} />
          <Text style={{ fontSize: 12, color: colors.textTertiary }}>Hold & drag to reorder</Text>
        </View>
      )}

      {/* Campaign List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : campaigns.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="calendar-outline" size={64} color={colors.surface} />
          <Text style={styles.emptyText}>No campaigns yet</Text>
          <Text style={styles.emptySubtext}>Create your first nurture campaign</Text>
        </View>
      ) : hasGroups ? (
        /* Grouped view: Account / Org sections + Personal */
        <ScrollView
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {groupedCampaigns.org.length > 0 && (
            <>
              <View style={styles.sectionHeader}><Ionicons name="business" size={14} color="#C9A962" /><Text style={styles.sectionLabel}>Org-Wide</Text></View>
              {groupedCampaigns.org.map(item => (
                <TouchableOpacity key={item._id} style={styles.campaignCard} onPress={() => router.push(`/campaigns/${item._id}`)} activeOpacity={0.85}>
                  <View style={[styles.iconContainer, { backgroundColor: `${getCampaignIcon(item.type).color}20` }]}><Ionicons name={getCampaignIcon(item.type).icon as any} size={24} color={getCampaignIcon(item.type).color} /></View>
                  <View style={styles.campaignContent}><View style={styles.campaignHeader}><Text style={styles.campaignName} numberOfLines={1}>{item.name}</Text><Toggle value={item.active} onValueChange={() => toggleCampaign(item._id)} activeColor="#007AFF" /></View><View style={styles.statsRow}><View style={styles.stat}><Ionicons name="paper-plane" size={14} color={colors.textSecondary} /><Text style={styles.statText}>{item.messages_sent_count || 0} sent</Text></View></View></View>
                </TouchableOpacity>
              ))}
            </>
          )}
          {groupedCampaigns.account.length > 0 && (
            <>
              <View style={styles.sectionHeader}><Ionicons name="storefront" size={14} color="#C9A962" /><Text style={styles.sectionLabel}>Account (Team)</Text></View>
              {groupedCampaigns.account.map(item => (
                <TouchableOpacity key={item._id} style={styles.campaignCard} onPress={() => router.push(`/campaigns/${item._id}`)} activeOpacity={0.85}>
                  <View style={[styles.iconContainer, { backgroundColor: `${getCampaignIcon(item.type).color}20` }]}><Ionicons name={getCampaignIcon(item.type).icon as any} size={24} color={getCampaignIcon(item.type).color} /></View>
                  <View style={styles.campaignContent}><View style={styles.campaignHeader}><Text style={styles.campaignName} numberOfLines={1}>{item.name}</Text><Toggle value={item.active} onValueChange={() => toggleCampaign(item._id)} activeColor="#007AFF" /></View><View style={styles.statsRow}><View style={styles.stat}><Ionicons name="paper-plane" size={14} color={colors.textSecondary} /><Text style={styles.statText}>{item.messages_sent_count || 0} sent</Text></View></View></View>
                </TouchableOpacity>
              ))}
            </>
          )}
          {groupedCampaigns.personal.length > 0 && (
            <>
              <View style={styles.sectionHeader}><Ionicons name="person" size={14} color="#C9A962" /><Text style={styles.sectionLabel}>My Campaigns</Text></View>
              <DraggableFlatList
                data={groupedCampaigns.personal}
                renderItem={renderItem}
                keyExtractor={(item) => item._id || item.id}
                onDragEnd={({ data }) => { setCampaigns([...groupedCampaigns.org, ...groupedCampaigns.account, ...data]); persistOrder([...groupedCampaigns.org, ...groupedCampaigns.account, ...data]); }}
                activationDistance={20}
                scrollEnabled={false}
              />
            </>
          )}
        </ScrollView>
      ) : (
        /* Simple view: all personal — full drag-and-drop */
        <View style={{ flex: 1 }}>
          <DraggableFlatList
            data={campaigns}
            renderItem={renderItem}
            keyExtractor={(item) => item._id || item.id}
            onDragEnd={handleDragEnd}
            contentContainerStyle={styles.listContent}
            onRefresh={onRefresh}
            refreshing={refreshing}
            activationDistance={20}
          />
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16, borderBottomWidth: 1, borderBottomColor: colors.surface,
  },
  backButton: { padding: 4 },
  title: { fontSize: 20, fontWeight: '700', color: colors.text },
  headerButtons: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dashboardButton: { padding: 4 },
  addButton: { padding: 4 },
  statsBanner: {
    flexDirection: 'row', backgroundColor: colors.card,
    margin: 16, borderRadius: 16, padding: 20,
  },
  statItem: { flex: 1, alignItems: 'center' },
  statValue: { fontSize: 28, fontWeight: '800', color: '#007AFF' },
  statLabel: { fontSize: 11, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', marginTop: 2 },
  statDivider: { width: 1, backgroundColor: colors.surface, marginHorizontal: 8 },
  listContent: { paddingHorizontal: 16, paddingBottom: 32 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 60 },
  emptyText: { fontSize: 18, fontWeight: '600', color: colors.text, marginTop: 16 },
  emptySubtext: { fontSize: 14, color: colors.textSecondary, marginTop: 6 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 4, marginTop: 8 },
  sectionLabel:  { fontSize: 13, fontWeight: '700', color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.8 },
  campaignCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.card, borderRadius: 16,
    padding: 16, marginBottom: 12, gap: 10,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  dragHandle: {
    paddingHorizontal: 2, paddingVertical: 4,
    justifyContent: 'center', alignItems: 'center',
  },
  iconContainer: { width: 48, height: 48, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  campaignContent: { flex: 1 },
  campaignHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  campaignName: { fontSize: 16, fontWeight: '700', color: colors.text, flex: 1, marginRight: 8 },
  statsRow: { flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  stat: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  statText: { fontSize: 13, color: colors.textSecondary },
});
