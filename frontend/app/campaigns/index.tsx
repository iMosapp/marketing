import React, { useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, ScrollView, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { ScreenErrorBoundary } from '../../components/ScreenErrorBoundary';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import api, { campaignsAPI } from '../../services/api';
import { PlanCard } from '../../components/campaigns/PlanCard';
import { Eyebrow } from '../../components/campaigns/Sheet';
import { planIssues, GOLD, RED, tid } from '../../components/campaigns/utils';

function CampaignsScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [canEdit, setCanEdit] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try {
      const [list, perm, tpl] = await Promise.all([
        campaignsAPI.getAll(user._id),
        api.get(`/campaigns/${user._id}/permissions`).then(r => r.data).catch(() => ({ allowed: true })),
        api.get('/campaigns/templates/prebuilt').then(r => r.data).catch(() => []),
      ]);
      setCampaigns(list || []);
      setCanEdit(!!perm?.allowed);
      setTemplates(tpl || []);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not load campaigns', 'error');
    } finally { setLoading(false); }
  }, [user?._id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const toggleActive = async (c: any) => {
    const id = c._id || c.id;
    const next = !c.active;
    setCampaigns(cs => cs.map(x => (x._id || x.id) === id ? { ...x, active: next } : x));
    try { await campaignsAPI.update(user!._id, id, { active: next }); showToast(next ? `${c.name} is live` : `${c.name} paused`, 'success'); }
    catch (e: any) { setCampaigns(cs => cs.map(x => (x._id || x.id) === id ? { ...x, active: !next } : x)); showToast(e?.response?.data?.detail || 'Could not update', 'error'); }
  };

  const live = campaigns.filter(c => c.active).length;
  const people = campaigns.reduce((n, c) => n + (c.enrollments_active || 0), 0);
  const week = campaigns.reduce((n, c) => n + (c.sent_this_week || 0), 0);
  const needsFix = campaigns.filter(c => c.active && planIssues(c).length).length;

  const groups = [
    { key: 'org', label: 'ORG-WIDE', items: campaigns.filter(c => c.scope === 'org') },
    { key: 'store', label: 'STORE-WIDE', items: campaigns.filter(c => c.scope === 'account' || c.scope === 'store' || c.ownership_level === 'store') },
    { key: 'mine', label: 'MY PLANS', items: campaigns.filter(c => !c.scope || c.scope === 'personal') },
  ].filter(g => g.items.length);
  const grouped = groups.length > 1;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Campaigns" subtitle={canEdit ? 'Follow-up that runs itself when you tag someone' : 'View only'} testID="campaigns-header"
        right={<View style={{ flexDirection: 'row' }}>
          <HeaderIconButton icon="speedometer-outline" onPress={() => router.push('/campaigns/dashboard')} testID="campaigns-dashboard-btn" color={colors.textSecondary} />
          {canEdit ? <HeaderIconButton icon="add-circle" onPress={() => router.push('/campaigns/new')} testID="campaigns-new-btn" /> : null}
        </View>} />
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 18 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={GOLD} />}>
          <View style={{ flexDirection: 'row', gap: 8 }} {...tid('campaign-stats')}>
            {[
              { k: 'live', v: live, l: 'Live plans', c: colors.text },
              { k: 'people', v: people, l: 'People in plans', c: colors.text },
              { k: 'week', v: week, l: 'Texts this week', c: GOLD },
              { k: 'fix', v: needsFix, l: 'Needs fix', c: needsFix ? RED : colors.textSecondary },
            ].map(s => (
              <View key={s.k} style={{ flex: 1, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 10 }} {...tid(`campaign-stat-${s.k}`)}>
                <Text style={{ fontSize: 22, fontWeight: '800', color: s.c }}>{s.v}</Text>
                <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5, textTransform: 'uppercase', marginTop: 2 }}>{s.l}</Text>
              </View>
            ))}
          </View>

          {canEdit && templates.length ? (
            <View style={{ gap: 10 }}>
              <Eyebrow colors={colors}>START FROM A PROVEN PLAN</Eyebrow>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
                {templates.map(t => (
                  <TouchableOpacity key={t.id} onPress={() => router.push(`/campaigns/new?template=${t.id}` as any)} style={{ width: 168, backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, borderStyle: 'dashed', padding: 12, gap: 6 }} {...tid(`template-${t.id}`)}>
                    <View style={{ width: 32, height: 32, borderRadius: 10, backgroundColor: (t.color || GOLD) + '22', alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name={t.icon || 'rocket-outline'} size={16} color={t.color || GOLD} />
                    </View>
                    <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }} numberOfLines={2}>{t.name}</Text>
                    <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={2}>{t.step_count} touches · {t.total_duration}{t.ai_enabled ? ' · Jessi writes' : ''}</Text>
                  </TouchableOpacity>
                ))}
                <TouchableOpacity onPress={() => router.push('/campaigns/new')} style={{ width: 120, backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: GOLD + '66', padding: 12, gap: 6, justifyContent: 'center', alignItems: 'center' }} {...tid('template-blank')}>
                  <Ionicons name="add-circle" size={26} color={GOLD} />
                  <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD, textAlign: 'center' }}>Start blank</Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          ) : null}

          {campaigns.length === 0 ? (
            <View style={{ alignItems: 'center', paddingVertical: 40, gap: 8 }} {...tid('campaigns-empty')}>
              <Ionicons name="rocket-outline" size={44} color={colors.textTertiary} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>No plans yet</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 }}>Pick a proven plan above or start blank. Once it is live, tagging a contact does the rest.</Text>
            </View>
          ) : groups.map(g => (
            <View key={g.key} style={{ gap: 10 }}>
              {grouped ? <Eyebrow colors={colors}>{g.label} · {g.items.length}</Eyebrow> : <Eyebrow colors={colors}>YOUR PLANS · {g.items.length}</Eyebrow>}
              {g.items.map(c => (
                <PlanCard key={c._id || c.id} campaign={c} colors={colors} onPress={() => router.push(`/campaigns/${c._id || c.id}`)} onToggleActive={canEdit ? () => toggleActive(c) : undefined} />
              ))}
            </View>
          ))}
          {!canEdit ? <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center' }}>Only admins (or managers your admin enabled) can change campaigns.</Text> : null}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

export default function CampaignsScreenWithBoundary(props: any) {
  return <ScreenErrorBoundary screenName="Campaigns"><CampaignsScreen {...props} /></ScreenErrorBoundary>;
}
