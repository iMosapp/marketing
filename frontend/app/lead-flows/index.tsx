import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { LeadFlowSummary, FlowStatsStrip, type LeadFlow } from '../../components/admin/LeadFlowSummary';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
type Template = { key: string; name: string; description: string; contact_mode: string; attempts: number };

export default function LeadFlowsLibrary() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [flows, setFlows] = useState<LeadFlow[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [picker, setPicker] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/lead-flows');
      setFlows(res.data.flows || []);
      setTemplates(res.data.templates || []);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not load lead flows', 'error');
    } finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { if (user?._id) load(); }, [user?._id, load]));

  const createFromTemplate = async (key: string | null) => {
    setBusy(key || 'blank');
    try {
      const res = await api.post('/lead-flows', key ? { template_key: key } : { name: 'New flow', contact_mode: 'text_only' });
      setPicker(false);
      router.push(`/lead-flows/${res.data.id}` as any);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not create flow', 'error');
    } finally { setBusy(null); }
  };
  const duplicate = async (f: LeadFlow) => {
    setBusy(f.id);
    try { const res = await api.post(`/lead-flows/${f.id}/duplicate`); setFlows(prev => [...prev, res.data]); showToast(`Copied "${f.name}"`, 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not duplicate', 'error'); }
    finally { setBusy(null); }
  };
  const remove = (f: LeadFlow) => {
    const msg = f.source_count ? `"${f.name}" is used by ${f.source_count} lead source(s). They keep their current settings but stop following this flow.` : `Delete "${f.name}"? This cannot be undone.`;
    showConfirm('Delete flow', msg, async () => {
      try { await api.delete(`/lead-flows/${f.id}?force=true`); setFlows(prev => prev.filter(x => x.id !== f.id)); showToast('Flow deleted', 'success'); }
      catch (e: any) { showToast(e?.response?.data?.detail || 'Could not delete', 'error'); }
    }, undefined, 'Delete');
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Lead Flows" subtitle="Reusable playbooks for new leads" testID="lead-flows-header"
        right={<HeaderIconButton icon="add-circle" onPress={() => setPicker(true)} testID="lead-flows-add" />} />
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>
            A flow decides what happens the second a lead comes in: the instant text, who rings and in what order, what Jessi does, and what happens when nobody answers. Attach one flow to any number of lead sources; edit it once and every source follows.
          </Text>
          {flows.length === 0 && (
            <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 20, alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.border }} {...tid('lead-flows-empty')}>
              <Ionicons name="git-network-outline" size={36} color={GOLD} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>No flows yet</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>Start from a proven template and tweak who rings.</Text>
            </View>
          )}
          {flows.map(f => (
            <View key={f.id} style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10 }} {...tid(`lead-flow-card-${f.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: (f.contact_mode === 'text_and_call' ? '#007AFF' : '#34C759') + '22', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={f.contact_mode === 'text_and_call' ? 'call' : 'chatbubble'} size={18} color={f.contact_mode === 'text_and_call' ? '#007AFF' : '#34C759'} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} {...tid(`lead-flow-name-${f.id}`)}>{f.name}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>
                    {f.contact_mode === 'text_and_call' ? `Text + Call · ${f.call_attempts.length} attempt${f.call_attempts.length === 1 ? '' : 's'}` : 'Text only'} · {f.source_count ? `used by ${f.source_count} source${f.source_count === 1 ? '' : 's'}` : 'not attached yet'}
                  </Text>
                </View>
              </View>
              {f.description ? <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{f.description}</Text> : null}
              <FlowStatsStrip stats={f.stats} colors={colors} testID={`lead-flow-stats-${f.id}`} />
              <LeadFlowSummary rows={f.summary} colors={colors} compact />
              {f.sources.length > 0 && (
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {f.sources.map(s => (
                    <TouchableOpacity key={s.id} onPress={() => router.push(`/admin/lead-sources/${s.id}` as any)} style={{ paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: GOLD + '22', borderWidth: 1, borderColor: GOLD + '66' }} {...tid(`lead-flow-source-${s.id}`)}>
                      <Text style={{ fontSize: 11, fontWeight: '700', color: GOLD }}>{s.name}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 2 }}>
                <TouchableOpacity onPress={() => router.push(`/lead-flows/${f.id}` as any)} style={{ flex: 1, height: 42, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`lead-flow-edit-${f.id}`)}>
                  <Ionicons name="create-outline" size={16} color="#111" />
                  <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => duplicate(f)} disabled={busy === f.id} style={{ height: 42, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`lead-flow-duplicate-${f.id}`)}>
                  <Ionicons name="copy-outline" size={16} color={colors.text} />
                  <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Duplicate</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => remove(f)} style={{ height: 42, width: 42, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`lead-flow-delete-${f.id}`)}>
                  <Ionicons name="trash-outline" size={16} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            </View>
          ))}
          <TouchableOpacity onPress={() => setPicker(true)} style={{ height: 50, borderRadius: 14, borderWidth: 1, borderStyle: 'dashed', borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('lead-flows-new')}>
            <Ionicons name="add" size={20} color={GOLD} />
            <Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>New flow</Text>
          </TouchableOpacity>
        </ScrollView>
      )}

      <Modal visible={picker} animationType="slide" transparent onRequestClose={() => setPicker(false)}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '85%' }} {...tid('lead-flow-template-sheet')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
              <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>Start a new flow</Text>
              <TouchableOpacity onPress={() => setPicker(false)} {...tid('lead-flow-template-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40, gap: 10 }}>
              {templates.map(t => (
                <TouchableOpacity key={t.key} onPress={() => createFromTemplate(t.key)} disabled={!!busy} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', gap: 12, alignItems: 'center' }} {...tid(`lead-flow-template-${t.key}`)}>
                  <Ionicons name={t.contact_mode === 'text_and_call' ? 'call' : 'chatbubble'} size={20} color={GOLD} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{t.name}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>{t.description}</Text>
                    <Text style={{ fontSize: 11, color: GOLD, marginTop: 4, fontWeight: '700' }}>{t.contact_mode === 'text_and_call' ? `${t.attempts} ring attempts, your store's reps and managers pre-filled` : 'No calls'}</Text>
                  </View>
                  {busy === t.key ? <ActivityIndicator color={GOLD} /> : <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />}
                </TouchableOpacity>
              ))}
              <TouchableOpacity onPress={() => createFromTemplate(null)} disabled={!!busy} style={{ alignItems: 'center', paddingVertical: 12 }} {...tid('lead-flow-template-blank')}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.textSecondary }}>Start from a blank flow</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
