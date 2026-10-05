import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { Section, Label, Hint, inputStyle } from '../inbox/InboxEditorParts';

type Target = { id: string; name: string; store_name: string; on: boolean; other: string };
type Targets = { widgets: Target[]; lead_sources: Target[]; inboxes: Target[] };
type Props = { agentId: string; agentName: string; colors: any; showToast: (m: string, t?: any, d?: number) => void; onChanged: (usedBy: any[]) => void; canEdit: boolean; usedBy: any[] };

const KINDS: { key: keyof Targets; kind: string; label: string; icon: string; route: (id: string) => string }[] = [
  { key: 'widgets', kind: 'widget', label: 'Website chat widgets', icon: 'globe-outline', route: id => `/admin/website-widget/${id}` },
  { key: 'lead_sources', kind: 'lead_source', label: 'Lead sources (text replies)', icon: 'git-branch-outline', route: id => `/admin/lead-sources/${id}` },
  { key: 'inboxes', kind: 'inbox', label: 'Shared inboxes (until a rep claims)', icon: 'chatbubbles-outline', route: id => `/inboxes/${id}` },
];

// Where this agent is working, and switches to put it on (or take it off) any widget, lead source or inbox.
export const DeployPanel = ({ agentId, agentName, colors, showToast, onChanged, canEdit, usedBy }: Props) => {
  const router = useRouter();
  const [targets, setTargets] = useState<Targets | null>(null);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => { if (canEdit) api.get(`/agents/${agentId}/targets`).then(r => setTargets(r.data)).catch(() => setTargets({ widgets: [], lead_sources: [], inboxes: [] })); };
  useEffect(load, [agentId, canEdit]);

  const toggle = async (kind: string, key: keyof Targets, t: Target, on: boolean) => {
    setBusy(t.id);
    try {
      const r = await api.put(`/agents/${agentId}/deploy`, { kind, target_id: t.id, on });
      setTargets(tg => tg ? { ...tg, [key]: tg[key].map(x => x.id === t.id ? { ...x, on, other: on ? '' : x.other } : x) } : tg);
      onChanged(r.data.used_by || []);
      showToast(on ? `${agentName} is now on ${t.name}` : `${agentName} taken off ${t.name}`, 'success');
    } catch (e: any) { showToast(errText(e, 'Could not change that'), 'error', 3500); }
    finally { setBusy(null); }
  };

  const match = (t: Target) => !q.trim() || `${t.name} ${t.store_name}`.toLowerCase().includes(q.trim().toLowerCase());
  return (
    <>
      <Section colors={colors} testId="agent-used-by">
        <Label colors={colors}>Where {agentName || 'this agent'} is working</Label>
        {usedBy.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('agent-used-by-empty')}>Nowhere yet. {canEdit ? 'Turn it on below, or pick it from a widget, lead source or inbox editor.' : 'A super admin can deploy it, or pick it from your widget, lead source or inbox editor.'}</Text> : null}
        {usedBy.map(u => {
          const k = KINDS.find(x => x.kind === u.kind)!;
          return (
            <TouchableOpacity key={`${u.kind}-${u.id}`} onPress={() => router.push(k.route(u.id) as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }} {...tid(`agent-used-${u.kind}-${u.id}`)}>
              <Ionicons name={k.icon as any} size={18} color={GOLD} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{u.name}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary }}>{k.label.split(' (')[0]}{u.store_name ? ` · ${u.store_name}` : ''}</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          );
        })}
      </Section>
      {canEdit ? (
        <Section colors={colors} testId="agent-deploy">
          <Label colors={colors}>Put {agentName || 'this agent'} to work</Label>
          <Hint colors={colors}>Each place has one agent at a time. Turning this one on replaces whoever was there.</Hint>
          <TextInput value={q} onChangeText={setQ} placeholder="Search by name or store" placeholderTextColor={colors.textSecondary} style={inputStyle(colors)} {...tid('agent-deploy-search')} />
          {!targets ? <ActivityIndicator color={GOLD} style={{ marginTop: 12 }} /> : KINDS.map(k => {
            const rows = targets[k.key].filter(match);
            const isOpen = open[k.key] ?? (rows.length <= 8 || !!q.trim());
            return (
              <View key={k.key} style={{ marginTop: 12 }}>
                <TouchableOpacity onPress={() => setOpen(o => ({ ...o, [k.key]: !isOpen }))} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 }} {...tid(`agent-deploy-group-${k.kind}`)}>
                  <Ionicons name={k.icon as any} size={16} color={colors.textSecondary} />
                  <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{k.label.toUpperCase()} · {rows.length}{targets[k.key].filter(t => t.on).length ? ` · ${targets[k.key].filter(t => t.on).length} ON` : ''}</Text>
                  <Ionicons name={isOpen ? 'chevron-down' : 'chevron-forward'} size={16} color={colors.textSecondary} />
                </TouchableOpacity>
                {isOpen ? rows.slice(0, 60).map(t => (
                  <View key={t.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, paddingLeft: 24 }} {...tid(`agent-deploy-${k.kind}-${t.id}`)}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 14, color: colors.text }} numberOfLines={1}>{t.name}</Text>
                      <Text style={{ fontSize: 11, color: t.other ? '#FF9500' : colors.textSecondary }} numberOfLines={1}>{t.store_name || 'No store'}{t.other ? ` · ${t.other} is on it now` : ''}</Text>
                    </View>
                    {busy === t.id ? <ActivityIndicator color={GOLD} /> : <Switch value={t.on} onValueChange={v => toggle(k.kind, k.key, t, v)} trackColor={{ true: GOLD }} {...tid(`agent-deploy-switch-${k.kind}-${t.id}`)} />}
                  </View>
                )) : null}
                {isOpen && rows.length > 60 ? <Text style={{ fontSize: 11, color: colors.textSecondary, paddingLeft: 24 }}>Type to narrow it down, showing 60 of {rows.length}.</Text> : null}
                {isOpen && rows.length === 0 ? <Text style={{ fontSize: 12, color: colors.textSecondary, paddingLeft: 24 }}>None match.</Text> : null}
              </View>
            );
          })}
        </Section>
      ) : null}
    </>
  );
};
