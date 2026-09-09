import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { LeadFlowSummary, type LeadFlow } from './LeadFlowSummary';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

// "Which Lead Flow runs this source?" card for the Lead Source page. Attaching copies the flow onto the source.
export const LeadFlowPicker = ({ sourceId, flow, colors, onChanged }: { sourceId: string; flow: LeadFlow | null; colors: any; onChanged: (flow: LeadFlow | null, workflow: any) => void }) => {
  const router = useRouter();
  const { showToast } = useToast();
  const [open, setOpen] = useState(false);
  const [flows, setFlows] = useState<LeadFlow[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open && flows === null) api.get('/lead-flows').then(r => setFlows(r.data.flows || [])).catch(() => setFlows([]));
  }, [open]);

  const attach = async (flowId: string | null) => {
    setBusy(true);
    try {
      const res = await api.put(`/lead-flows/source/${sourceId}`, { flow_id: flowId });
      onChanged(res.data.flow || null, res.data.lead_source?.workflow || {});
      setOpen(false);
      showToast(flowId ? `Now following "${res.data.flow?.name}"` : 'Flow detached. The source keeps its current settings.', 'success');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not update flow', 'error');
    } finally { setBusy(false); }
  };

  return (
    <View style={{ borderRadius: 14, borderWidth: 1, borderColor: flow ? GOLD + '88' : colors.border, backgroundColor: flow ? GOLD + '12' : colors.surface, padding: 14, gap: 10 }} {...tid('lead-flow-picker')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 34, height: 34, borderRadius: 10, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="git-network-outline" size={18} color={GOLD} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} {...tid('lead-flow-picker-title')}>{flow ? `Lead Flow: ${flow.name}` : 'Lead Flow'}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>
            {flow ? 'This source follows the flow. Intake text, ladder and after-hours rule are managed there.' : 'Use a reusable playbook from your library instead of setting this source up by hand.'}
          </Text>
        </View>
      </View>
      {flow ? (
        <>
          <LeadFlowSummary rows={flow.summary} colors={colors} compact testID="lead-flow-picker-summary" />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TouchableOpacity onPress={() => router.push(`/lead-flows/${flow.id}` as any)} style={{ flex: 1, height: 40, borderRadius: 10, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('lead-flow-picker-edit')}>
              <Ionicons name="create-outline" size={15} color="#111" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Edit flow</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setOpen(true)} style={{ height: 40, paddingHorizontal: 12, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('lead-flow-picker-change')}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Change</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => showConfirm('Detach flow?', 'The source keeps its current settings but stops following the flow.', () => attach(null), undefined, 'Detach')} style={{ height: 40, paddingHorizontal: 12, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('lead-flow-picker-detach')}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: '#FF3B30' }}>Detach</Text>
            </TouchableOpacity>
          </View>
        </>
      ) : (
        <TouchableOpacity onPress={() => setOpen(true)} style={{ height: 42, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('lead-flow-picker-use')}>
          <Ionicons name="albums-outline" size={16} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>Use a flow from the library</Text>
        </TouchableOpacity>
      )}

      <Modal visible={open} animationType="slide" transparent onRequestClose={() => setOpen(false)}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '85%' }} {...tid('lead-flow-picker-sheet')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
              <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>Pick a Lead Flow</Text>
              <TouchableOpacity onPress={() => setOpen(false)} {...tid('lead-flow-picker-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40, gap: 10 }}>
              {flows === null ? <ActivityIndicator color={GOLD} /> : flows.length === 0 ? (
                <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 12 }}>No flows in your library yet.</Text>
              ) : flows.map(f => {
                const on = flow?.id === f.id;
                return (
                  <TouchableOpacity key={f.id} onPress={() => attach(f.id)} disabled={busy || on} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: on ? GOLD : colors.border, gap: 6, opacity: on ? 0.7 : 1 }} {...tid(`lead-flow-picker-option-${f.id}`)}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Ionicons name={f.contact_mode === 'text_and_call' ? 'call' : 'chatbubble'} size={16} color={GOLD} />
                      <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>{f.name}</Text>
                      {on ? <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD }}>CURRENT</Text> : null}
                    </View>
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>{f.contact_mode === 'text_and_call' ? `Text + Call · ${f.call_attempts.length} attempts` : 'Text only'}{f.source_count ? ` · used by ${f.source_count}` : ''}</Text>
                    <LeadFlowSummary rows={f.summary.slice(0, 4)} colors={colors} compact />
                  </TouchableOpacity>
                );
              })}
              <TouchableOpacity onPress={() => { setOpen(false); router.push('/lead-flows' as any); }} style={{ alignItems: 'center', paddingVertical: 12, flexDirection: 'row', justifyContent: 'center', gap: 6 }} {...tid('lead-flow-picker-manage')}>
                <Ionicons name="albums-outline" size={16} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '700', color: GOLD }}>Manage the library</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
};
