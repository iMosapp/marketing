import React, { useState, useEffect, useCallback, useRef } from 'react';
import { showAlert } from '../../services/alert';
import {
  View, Text, TouchableOpacity, StyleSheet, ActivityIndicator,
  ScrollView, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { campaignsAPI } from '../../services/api';
import Toggle from '../../components/Toggle';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

export default function CampaignsScreen() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();

  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [reorderMode, setReorderMode] = useState(false);
  const saveTimer = useRef<any>(null);

  useFocusEffect(useCallback(() => { loadCampaigns(); }, [user]));

  const loadCampaigns = async () => {
    if (!user) return;
    try {
      setLoading(true);
      const data = await campaignsAPI.getAll(user._id);
      setCampaigns(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const onRefresh = async () => { setRefreshing(true); await loadCampaigns(); setRefreshing(false); };

  const persistOrder = useCallback((ordered: any[]) => {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!user?._id) return;
      try {
        await api.post(`/campaigns/${user._id}/reorder`, {
          campaign_ids: ordered.map((c: any) => c._id || c.id),
        });
      } catch (e) { console.warn('Failed to save campaign order:', e); }
    }, 400);
  }, [user?._id]);

  const moveItem = (index: number, direction: 'up' | 'down') => {
    const newList = [...campaigns];
    const target = direction === 'up' ? index - 1 : index + 1;
    if (target < 0 || target >= newList.length) return;
    [newList[index], newList[target]] = [newList[target], newList[index]];
    setCampaigns(newList);
    persistOrder(newList);
  };

  const toggleCampaign = async (id: string) => {
    const campaign = campaigns.find(c => c._id === id || c.id === id);
    if (!campaign || !user?._id) return;
    const next = !campaign.active;
    setCampaigns(campaigns.map(c => (c._id === id || c.id === id) ? { ...c, active: next } : c));
    try { await campaignsAPI.update(user._id, id, { active: next }); }
    catch { setCampaigns(campaigns.map(c => (c._id === id || c.id === id) ? { ...c, active: !next } : c)); }
  };

  const getCampaignIcon = (type: string) => {
    switch (type) {
      case 'birthday': return { icon: 'gift', color: '#FF9500' };
      case 'anniversary': return { icon: 'heart', color: '#FF3B30' };
      case 'check_in': return { icon: 'chatbubble', color: '#007AFF' };
      default: return { icon: 'megaphone', color: '#34C759' };
    }
  };

  const formatDate = (d: Date | null) => {
    if (!d) return 'Never';
    const h = (Date.now() - d.getTime()) / 3600000;
    if (h < 24) return `${Math.floor(h)}h ago`;
    if (h < 168) return `${Math.floor(h / 24)}d ago`;
    return d.toLocaleDateString();
  };

  const scopeLabel = (c: any) =>
    c.scope === 'org' ? 'Org' : c.scope === 'account' || c.ownership_level === 'store' ? 'Account' : null;

  // Group campaigns by scope
  const grouped = {
    org:      campaigns.filter(c => c.scope === 'org'),
    account:  campaigns.filter(c => c.scope === 'account' || c.ownership_level === 'store'),
    personal: campaigns.filter(c => !c.scope || c.scope === 'personal'),
  };
  const hasGroups = grouped.org.length > 0 || grouped.account.length > 0;

  const renderCard = (item: any, idx: number, totalInGroup: number, groupCampaigns?: any[]) => {
    const iconData = getCampaignIcon(item.type);
    const sl = scopeLabel(item);
    const isFirst = idx === 0;
    const isLast = idx === totalInGroup - 1;

    return (
      <TouchableOpacity
        key={item._id || item.id}
        style={s.card}
        onPress={() => !reorderMode && router.push(`/campaigns/${item._id || item.id}`)}
        activeOpacity={reorderMode ? 1 : 0.85}
        data-testid={`campaign-card-${item._id}`}
      >
        {/* Reorder controls — only visible in reorder mode */}
        {reorderMode && groupCampaigns ? (
          <View style={s.reorderBtns}>
            <TouchableOpacity onPress={() => {
              const globalIdx = campaigns.indexOf(item);
              moveItem(globalIdx, 'up');
            }} disabled={isFirst} style={{ opacity: isFirst ? 0.25 : 1 }}>
              <Ionicons name="chevron-up" size={22} color="#C9A962" />
            </TouchableOpacity>
            <TouchableOpacity onPress={() => {
              const globalIdx = campaigns.indexOf(item);
              moveItem(globalIdx, 'down');
            }} disabled={isLast} style={{ opacity: isLast ? 0.25 : 1 }}>
              <Ionicons name="chevron-down" size={22} color="#C9A962" />
            </TouchableOpacity>
          </View>
        ) : (
          <Ionicons name="reorder-three" size={22} color={colors.textTertiary} style={{ marginRight: 2 }} />
        )}

        <View style={[s.iconBox, { backgroundColor: `${iconData.color}20` }]}>
          <Ionicons name={iconData.icon as any} size={24} color={iconData.color} />
        </View>

        <View style={s.content}>
          <View style={s.row}>
            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={s.name} numberOfLines={1}>{item.name}</Text>
              {sl && <View style={s.badge}><Text style={s.badgeTxt}>{sl}</Text></View>}
            </View>
            <Toggle value={item.active} onValueChange={() => toggleCampaign(item._id || item.id)} activeColor="#007AFF" />
          </View>
          <View style={s.stats}>
            <View style={s.stat}><Ionicons name="paper-plane" size={13} color={colors.textSecondary} />
              <Text style={s.statTxt}>{item.messages_sent_count || 0} sent</Text></View>
            <View style={s.stat}><Ionicons name="time" size={13} color={colors.textSecondary} />
              <Text style={s.statTxt}>{formatDate(item.last_sent_at ? new Date(item.last_sent_at) : null)}</Text></View>
            {item.enrollments_active > 0 && (
              <View style={s.stat}><Ionicons name="people" size={13} color={colors.textSecondary} />
                <Text style={s.statTxt}>{item.enrollments_active} active</Text></View>
            )}
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  const renderSection = (label: string, icon: string, items: any[]) => (
    <View key={label} style={{ marginBottom: 8 }}>
      <View style={s.sectionHeader}>
        <Ionicons name={icon as any} size={13} color="#C9A962" />
        <Text style={s.sectionLabel}>{label}</Text>
        <Text style={s.sectionCount}>{items.length}</Text>
      </View>
      {items.map((item, idx) => renderCard(item, idx, items.length, items))}
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.hBtn}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={s.title}>Campaigns</Text>
        <View style={{ flexDirection: 'row', gap: 4 }}>
          {campaigns.length > 1 && (
            <TouchableOpacity onPress={() => setReorderMode(r => !r)} style={[s.hBtn,
              reorderMode && { backgroundColor: '#C9A96220', borderRadius: 8 }]}>
              <Ionicons name={reorderMode ? 'checkmark' : 'reorder-three'} size={22}
                color={reorderMode ? '#C9A962' : '#007AFF'} />
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={() => router.push('/campaigns/dashboard')} style={s.hBtn}>
            <Ionicons name="speedometer-outline" size={24} color="#007AFF" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => router.push('/campaigns/new')} style={s.hBtn}>
            <Ionicons name="add-circle" size={32} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Stats */}
      <View style={s.statsBanner}>
        {[
          { label: 'Active', value: campaigns.filter(c => c.active).length, color: '#007AFF' },
          { label: 'Total Sent', value: campaigns.reduce((n, c) => n + (c.messages_sent_count || 0), 0), color: '#34C759' },
          { label: 'Campaigns', value: campaigns.length, color: '#C9A962' },
        ].map((st, i) => (
          <React.Fragment key={st.label}>
            {i > 0 && <View style={s.divider} />}
            <View style={s.statItem}>
              <Text style={[s.statVal, { color: st.color }]}>{st.value}</Text>
              <Text style={s.statLbl}>{st.label}</Text>
            </View>
          </React.Fragment>
        ))}
      </View>

      {reorderMode && (
        <View style={s.reorderBanner}>
          <Ionicons name="information-circle" size={15} color="#C9A962" />
          <Text style={s.reorderBannerTxt}>Tap ↑ ↓ to reorder · Tap ✓ to finish</Text>
        </View>
      )}

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color="#007AFF" /></View>
      ) : campaigns.length === 0 ? (
        <View style={s.center}>
          <Ionicons name="calendar-outline" size={64} color={colors.surface} />
          <Text style={[s.name, { marginTop: 12 }]}>No campaigns yet</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={s.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          scrollEnabled={true}
          keyboardShouldPersistTaps="handled"
        >
          {hasGroups ? (
            <>
              {grouped.org.length > 0 && renderSection('Org-Wide', 'business', grouped.org)}
              {grouped.account.length > 0 && renderSection('Account (Team)', 'storefront', grouped.account)}
              {grouped.personal.length > 0 && renderSection('My Campaigns', 'person', grouped.personal)}
            </>
          ) : (
            campaigns.map((item, idx) => renderCard(item, idx, campaigns.length, campaigns))
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container:     { flex: 1, backgroundColor: colors.bg },
  header:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  hBtn:          { padding: 4 },
  title:         { fontSize: 20, fontWeight: '700', color: colors.text },
  statsBanner:   { flexDirection: 'row', backgroundColor: colors.card, margin: 16, borderRadius: 16, padding: 20 },
  statItem:      { flex: 1, alignItems: 'center' },
  statVal:       { fontSize: 28, fontWeight: '800' },
  statLbl:       { fontSize: 11, color: colors.textSecondary, fontWeight: '600', textTransform: 'uppercase', marginTop: 2 },
  divider:       { width: 1, backgroundColor: colors.surface, marginHorizontal: 8 },
  reorderBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, marginHorizontal: 16, marginBottom: 4, backgroundColor: '#C9A96210', borderRadius: 8, padding: 8 },
  reorderBannerTxt: { fontSize: 13, color: '#C9A962', fontWeight: '600' },
  list:          { paddingHorizontal: 16, paddingBottom: 40 },
  center:        { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 60 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 4, marginTop: 4 },
  sectionLabel:  { fontSize: 12, fontWeight: '700', color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.8, flex: 1 },
  sectionCount:  { fontSize: 12, color: colors.textTertiary, fontWeight: '600' },
  card:          { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 16, padding: 14, marginBottom: 10, gap: 10, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 2 },
  reorderBtns:   { flexDirection: 'column', gap: 0, alignItems: 'center', marginRight: 2 },
  iconBox:       { width: 46, height: 46, borderRadius: 13, justifyContent: 'center', alignItems: 'center' },
  content:       { flex: 1 },
  row:           { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  name:          { fontSize: 16, fontWeight: '700', color: colors.text, flex: 1, marginRight: 6 },
  badge:         { backgroundColor: '#C9A96220', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  badgeTxt:      { fontSize: 11, color: '#C9A962', fontWeight: '700' },
  stats:         { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  stat:          { flexDirection: 'row', alignItems: 'center', gap: 4 },
  statTxt:       { fontSize: 13, color: colors.textSecondary },
});
