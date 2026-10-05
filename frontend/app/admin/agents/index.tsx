import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { ScreenHeader, HeaderTextButton } from '../../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../../components/inbox/ownership';
import { AgentAvatar } from '../../../components/agents/AgentPicker';

const STATUS: Record<string, { label: string; color: string }> = { active: { label: 'Active', color: '#34C759' }, draft: { label: 'Draft', color: '#FF9500' }, archived: { label: 'Archived', color: '#8E8E93' } };

// Agent Hub: the library of AI agents super admins build; every store picks from it.
export default function AgentHub() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [data, setData] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [picker, setPicker] = useState(false);
  const [creating, setCreating] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setData((await api.get('/agents', { params: { include_archived: showArchived } })).data); }
    catch (e) { showToast(errText(e, "Couldn't load the Agent Hub"), 'error'); }
  }, [showArchived]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const create = async (starterKey?: string) => {
    setCreating(starterKey || 'blank');
    try {
      const r = await api.post('/agents', starterKey ? { starter_key: starterKey } : { name: 'New agent', status: 'draft' });
      setPicker(false);
      router.push(`/admin/agents/${r.data.agent.id}` as any);
    } catch (e) { showToast(errText(e, 'Could not create the agent'), 'error', 3500); }
    finally { setCreating(null); }
  };

  const agents: any[] = data?.agents || [];
  const canEdit = !!data?.can_edit;
  const starters: any[] = data?.starters || [];
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Agent Hub" subtitle="AI agents you can put anywhere Jessi talks to customers" testID="agent-hub-header"
        right={canEdit ? <HeaderTextButton label="New" onPress={() => setPicker(true)} testID="agent-hub-new" color={GOLD} /> : undefined} />
      {!data ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 12 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={GOLD} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>
            {canEdit ? 'Build an agent once: who it is, how it talks, what it is trying to do, what it knows and what it hands to a person. Then put it on a website chat widget, a lead source or a shared inbox.' : 'Agents are built by the super admins. Pick one from any widget, lead source or inbox editor; tap one here to see its brief and try it.'}
          </Text>
          {agents.length === 0 ? (
            <View style={{ alignItems: 'center', paddingVertical: 40, paddingHorizontal: 24, gap: 12 }} {...tid('agent-hub-empty')}>
              <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="people-circle" size={36} color={GOLD} /></View>
              <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text, textAlign: 'center' }}>No agents yet</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 }}>Start from a template (Internet Sales, Service Scheduler, Website Concierge, After-Hours, Spanish, Demo Setter) and make it yours.</Text>
              {canEdit ? <TouchableOpacity onPress={() => setPicker(true)} style={{ marginTop: 8, height: 50, paddingHorizontal: 24, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('agent-hub-empty-new')}>
                <Ionicons name="add" size={20} color="#111" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Create your first agent</Text>
              </TouchableOpacity> : null}
            </View>
          ) : null}
          {agents.map(a => (
            <TouchableOpacity key={a.id} onPress={() => router.push(`/admin/agents/${a.id}` as any)} activeOpacity={0.8}
              style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10, borderLeftWidth: 4, borderLeftColor: a.avatar_color || GOLD, opacity: a.status === 'archived' ? 0.6 : 1 }} {...tid(`agent-card-${a.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <AgentAvatar agent={a} size={44} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>{a.name}</Text>
                  <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>{a.title || 'No title yet'}{a.tagline ? ` · ${a.tagline}` : ''}</Text>
                </View>
                <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: STATUS[a.status].color + '22' }} {...tid(`agent-status-${a.id}`)}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: STATUS[a.status].color }}>{STATUS[a.status].label}</Text>
                </View>
              </View>
              {a.goal ? <Text style={{ fontSize: 13, color: colors.text }} numberOfLines={1}><Text style={{ fontWeight: '700' }}>Job: </Text>{a.goal}</Text> : null}
              <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
                {a.tone.charAt(0).toUpperCase() + a.tone.slice(1)}{a.language !== 'auto' ? ` · ${{ en: 'English', es: 'Spanish', nl: 'Dutch' }[a.language as string] || a.language}` : ''} · {a.used_count ? `Working in ${a.used_count} place${a.used_count === 1 ? '' : 's'}` : 'Not deployed yet'}{a.hand_to_human?.length ? ` · hands off ${a.hand_to_human.length} topic${a.hand_to_human.length === 1 ? '' : 's'}` : ''}
              </Text>
            </TouchableOpacity>
          ))}
          <TouchableOpacity onPress={() => setShowArchived(v => !v)} style={{ alignSelf: 'center', paddingVertical: 10 }} {...tid('agent-hub-archived-toggle')}>
            <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{showArchived ? 'Hide archived' : 'Show archived'}</Text>
          </TouchableOpacity>
        </ScrollView>
      )}

      <Modal visible={picker} animationType="slide" transparent onRequestClose={() => setPicker(false)}>
        <TouchableOpacity activeOpacity={1} onPress={() => setPicker(false)} style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }}>
          <TouchableOpacity activeOpacity={1} style={{ backgroundColor: colors.card, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 18, paddingBottom: 34, maxHeight: '85%' }} {...tid('agent-starter-sheet')}>
            <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>New agent</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4, marginBottom: 12 }}>Start from a template and edit anything, or start blank.</Text>
            <ScrollView contentContainerStyle={{ gap: 8 }}>
              {starters.map(s => (
                <TouchableOpacity key={s.key} onPress={() => create(s.key)} disabled={!!creating} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 14, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }} {...tid(`agent-starter-${s.key}`)}>
                  <AgentAvatar agent={s} size={40} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{s.name} · {s.title}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={2}>{s.tagline}. Job: {s.goal}.</Text>
                  </View>
                  {creating === s.key ? <ActivityIndicator color={GOLD} /> : <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />}
                </TouchableOpacity>
              ))}
              <TouchableOpacity onPress={() => create()} disabled={!!creating} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 14, borderWidth: 1, borderColor: GOLD, borderStyle: 'dashed' }} {...tid('agent-starter-blank')}>
                <View style={{ width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: GOLD + '22' }}><Ionicons name="add" size={22} color={GOLD} /></View>
                <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>Blank agent</Text>
                {creating === 'blank' ? <ActivityIndicator color={GOLD} /> : null}
              </TouchableOpacity>
            </ScrollView>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}
