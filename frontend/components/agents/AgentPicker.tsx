import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';

export type AgentLite = { id: string; name: string; title: string; tagline: string; avatar_color: string; tone: string; status: string; used_count: number; language: string };

export const AgentAvatar = ({ agent, size = 36 }: { agent: { name: string; avatar_color: string }; size?: number }) => (
  <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: (agent.avatar_color || GOLD) + '30', borderWidth: 2, borderColor: agent.avatar_color || GOLD, alignItems: 'center', justifyContent: 'center' }}>
    <Text style={{ color: agent.avatar_color || GOLD, fontWeight: '800', fontSize: size * 0.42 }}>{(agent.name || 'A').charAt(0).toUpperCase()}</Text>
  </View>
);

export const useAgents = () => {
  const [agents, setAgents] = useState<AgentLite[] | null>(null);
  const [canEdit, setCanEdit] = useState(false);
  useEffect(() => { api.get('/agents').then(r => { setAgents(r.data.agents || []); setCanEdit(!!r.data.can_edit); }).catch(() => setAgents([])); }, []);
  return { agents, canEdit };
};

type Props = { value: string; onChange: (id: string) => void; colors: any; noneLabel?: string; noneSub?: string; testId?: string; disabled?: boolean };

// Pick an agent from the Agent Hub for a widget, lead source or inbox. "None" = the default Jessi / rep behavior.
export const AgentPicker = ({ value, onChange, colors, noneLabel = 'No agent (default Jessi)', noneSub, testId = 'agent-picker', disabled }: Props) => {
  const router = useRouter();
  const { agents } = useAgents();
  if (agents === null) return <ActivityIndicator color={GOLD} style={{ marginVertical: 10 }} />;
  const active = agents.filter(a => a.status !== 'archived');
  const Row = ({ on, onPress, children, id }: { on: boolean; onPress: () => void; children: React.ReactNode; id: string }) => (
    <TouchableOpacity onPress={onPress} disabled={disabled} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: on ? GOLD : 'transparent', opacity: disabled ? 0.6 : 1 }} {...tid(id)}>
      {children}
      <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={18} color={on ? GOLD : colors.textSecondary} />
    </TouchableOpacity>
  );
  return (
    <View style={{ gap: 6 }} {...tid(testId)}>
      <Row on={!value} onPress={() => onChange('')} id={`${testId}-none`}>
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: colors.border, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="sparkles-outline" size={18} color={colors.textSecondary} /></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{noneLabel}</Text>
          {noneSub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{noneSub}</Text> : null}
        </View>
      </Row>
      {active.map(a => (
        <Row key={a.id} on={value === a.id} onPress={() => onChange(a.id)} id={`${testId}-${a.id}`}>
          <AgentAvatar agent={a} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{a.name}{a.title ? <Text style={{ fontWeight: '500', color: colors.textSecondary }}> · {a.title}</Text> : null}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>{a.tagline || a.tone}{a.status === 'draft' ? ' · draft' : ''}{a.used_count ? ` · working in ${a.used_count} place${a.used_count === 1 ? '' : 's'}` : ''}</Text>
          </View>
        </Row>
      ))}
      {active.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary, paddingVertical: 4 }} {...tid(`${testId}-empty`)}>No agents in the Agent Hub yet.</Text> : null}
      <TouchableOpacity onPress={() => router.push('/admin/agents' as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6 }} {...tid(`${testId}-manage`)}>
        <Ionicons name="people-circle-outline" size={16} color={GOLD} />
        <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Open the Agent Hub</Text>
      </TouchableOpacity>
    </View>
  );
};
