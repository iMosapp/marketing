import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Modal, Switch, TextInput, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { useToast } from '../components/common/Toast';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, 'data-testid': id } as any);

type Wf = {
  tag: string; label: string; blurb?: string; date_based: boolean; jessi_mode: string | null; clear_hot: boolean; stop_campaigns: boolean;
  stop_tags: string[]; campaign_mode: 'auto' | 'custom'; customized: boolean; instant: string[]; instant_note?: string;
  campaigns: { id: string; name: string; steps: number; ai_enabled: boolean; scope: string }[];
  timeline: { when: string; what: string; campaign?: string; kind: string; preview?: string; ai?: boolean }[];
  editable: boolean; updated_by_name?: string;
};

const JESSI_LABEL: Record<string, string> = { auto_reply: 'Jessi answers replies', draft_only: 'Jessi drafts, you approve', off: 'You handle replies' };
const TAG_COLOR: Record<string, string> = { sold: '#34C759', working: '#007AFF', met: '#5AC8FA', 'lost contact': '#FF9500', vip: GOLD, birthday: '#FF2D55', anniversary: '#AF52DE' };

export default function WorkflowsScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [data, setData] = useState<{ scope: any; editable: boolean; workflows: Wf[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<string>('sold');
  const [editing, setEditing] = useState<Wf | null>(null);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/workflows/${user._id}`);
      setData(res.data);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not load workflows', 'error');
    } finally { setLoading(false); }
  }, [user?._id]);
  useEffect(() => { load(); }, [load]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} {...tid('workflows-back')}><Ionicons name="chevron-back" size={26} color={colors.text} /></TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>Workflows</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>
            {data?.scope?.shared ? `What happens when anyone at ${data.scope.store_name || 'your store'} tags a contact` : 'What happens when you tag a contact'}
            {data && !data.editable ? ' · view only' : ''}
          </Text>
        </View>
      </View>
      {loading || !data ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />}>
          {data.workflows.map(wf => (
            <WorkflowCard key={wf.tag} wf={wf} colors={colors} expanded={open === wf.tag} onToggle={() => setOpen(open === wf.tag ? '' : wf.tag)} onEdit={() => setEditing(wf)} />
          ))}
          <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginTop: 8 }}>
            {data.editable ? 'You can edit these because you are a manager or admin. Changes apply to every rep in the store immediately.' : 'Only store managers and admins can change workflows.'}
          </Text>
        </ScrollView>
      )}
      {editing && user?._id && (
        <EditSheet wf={editing} userId={user._id} colors={colors} onClose={() => setEditing(null)} onSaved={(w) => { setEditing(null); setData(d => d ? { ...d, workflows: d.workflows.map(x => x.tag === w.tag ? w : x) } : d); showToast(`${w.label} workflow saved for the store`, 'success'); }} />
      )}
    </SafeAreaView>
  );
}

function WorkflowCard({ wf, colors, expanded, onToggle, onEdit }: { wf: Wf; colors: any; expanded: boolean; onToggle: () => void; onEdit: () => void }) {
  const color = TAG_COLOR[wf.tag] || '#8E8E93';
  const summary = useMemo(() => {
    if (wf.date_based) return 'Sends day-of';
    const parts: string[] = [];
    if (wf.campaigns.length) parts.push(`${wf.campaigns.reduce((n, c) => n + c.steps, 0)} touches`);
    else parts.push('no campaign attached');
    if (wf.jessi_mode) parts.push(JESSI_LABEL[wf.jessi_mode]);
    if (wf.stop_tags.length) parts.push(`stops ${wf.stop_tags.join('/')}`);
    return parts.join(' · ');
  }, [wf]);
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: expanded ? color + '66' : colors.border, overflow: 'hidden' }} {...tid(`workflow-card-${wf.tag.replace(/\s+/g, '-')}`)}>
      <TouchableOpacity onPress={onToggle} style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }} {...tid(`workflow-toggle-${wf.tag.replace(/\s+/g, '-')}`)}>
        <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: color + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="pricetag" size={18} color={color} />
        </View>
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>When tagged {wf.label}</Text>
            {wf.customized ? <View style={{ paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, backgroundColor: GOLD + '22' }}><Text style={{ fontSize: 10, fontWeight: '800', color: GOLD }}>STORE RULE</Text></View> : null}
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{summary}</Text>
        </View>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {expanded && (
        <View style={{ paddingHorizontal: 16, paddingBottom: 16, gap: 12 }}>
          {wf.blurb ? <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{wf.blurb}</Text> : null}
          {(wf.stop_tags.length > 0 || wf.clear_hot) && (
            <Row icon="stop-circle-outline" color="#FF9500" colors={colors} text={`First: ${wf.stop_tags.length ? `removes ${wf.stop_tags.join(', ')} and stops their follow-ups` : ''}${wf.stop_tags.length && wf.clear_hot ? '; ' : ''}${wf.clear_hot ? 'clears the hot-lead flag' : ''}`} />
          )}
          {wf.jessi_mode ? <Row icon={wf.jessi_mode === 'off' ? 'person-outline' : 'sparkles'} color={GOLD} colors={colors} text={`${JESSI_LABEL[wf.jessi_mode]}${wf.jessi_mode === 'auto_reply' ? ' automatically, escalates to the rep when she needs a human. Inbox shows Auto.' : '.'}`} /> : null}
          {wf.campaigns.map(c => (
            <Row key={c.id} icon="rocket-outline" color="#AF52DE" colors={colors} text={`Enrolls in ${c.name} (${c.steps} touches${c.scope === 'store' ? ', store-wide' : c.scope === 'org' ? ', org-wide' : ', personal'})`} />
          ))}
          {!wf.date_based && wf.campaigns.length === 0 ? <Row icon="alert-circle-outline" color="#FF3B30" colors={colors} text="No campaign is attached to this tag yet. Nothing will be sent." /> : null}
          {wf.campaign_mode === 'auto' && wf.campaigns.length > 1 ? <Row icon="warning-outline" color="#FF9500" colors={colors} text={`${wf.campaigns.length} campaigns fire on this tag (${wf.campaigns.reduce((n, c) => n + c.steps, 0)} texts total). If that's too many, a manager can pick exactly which ones.`} /> : null}

          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginTop: 4 }}>TIMELINE</Text>
          <View style={{ gap: 0 }}>
            {wf.timeline.length === 0 && wf.date_based ? <Text style={{ fontSize: 13, color: colors.textSecondary }}>The message goes out on the date itself, not when the tag is added.</Text> : null}
            {wf.timeline.map((t, i) => (
              <View key={i} style={{ flexDirection: 'row', gap: 12, paddingVertical: 6 }} {...tid(`workflow-${wf.tag.replace(/\s+/g, '-')}-step-${i}`)}>
                <View style={{ width: 74 }}><Text style={{ fontSize: 12, fontWeight: '800', color: t.kind === 'instant' ? '#34C759' : GOLD }}>{t.when}</Text></View>
                <View style={{ width: 8, alignItems: 'center' }}>
                  <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: t.kind === 'instant' ? '#34C759' : '#AF52DE', marginTop: 4 }} />
                  {i < wf.timeline.length - 1 ? <View style={{ flex: 1, width: 2, backgroundColor: colors.border, marginTop: 2 }} /> : null}
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 13, color: colors.text, fontWeight: '600' }}>{t.what}{t.ai ? ' · Jessi personalizes' : ''}</Text>
                  {t.preview ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={2}>"{t.preview}"</Text> : null}
                  {t.campaign ? <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 1 }}>{t.campaign}</Text> : null}
                </View>
              </View>
            ))}
          </View>
          {wf.instant_note && wf.instant.length ? <Text style={{ fontSize: 11, color: colors.textSecondary }}>{wf.instant_note}</Text> : null}
          {wf.editable && !wf.date_based ? (
            <TouchableOpacity onPress={onEdit} style={{ height: 44, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, marginTop: 4 }} {...tid(`workflow-edit-${wf.tag.replace(/\s+/g, '-')}`)}>
              <Ionicons name="create-outline" size={18} color="#111" />
              <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Edit store workflow</Text>
            </TouchableOpacity>
          ) : null}
          {wf.updated_by_name ? <Text style={{ fontSize: 11, color: colors.textSecondary }}>Last changed by {wf.updated_by_name}</Text> : null}
        </View>
      )}
    </View>
  );
}

const Row = ({ icon, color, text, colors }: { icon: any; color: string; text: string; colors: any }) => (
  <View style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
    <Ionicons name={icon} size={18} color={color} style={{ marginTop: 1 }} />
    <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }}>{text}</Text>
  </View>
);

function EditSheet({ wf, userId, colors, onClose, onSaved }: { wf: Wf; userId: string; colors: any; onClose: () => void; onSaved: (w: Wf) => void }) {
  const [jessi, setJessi] = useState<string>(wf.jessi_mode || 'off');
  const [mode, setMode] = useState<'auto' | 'custom'>(wf.campaign_mode);
  const [ids, setIds] = useState<string[]>(wf.campaigns.map(c => c.id));
  const [stopTags, setStopTags] = useState<string>(wf.stop_tags.join(', '));
  const [stopCampaigns, setStopCampaigns] = useState(wf.stop_campaigns);
  const [clearHot, setClearHot] = useState(wf.clear_hot);
  const [options, setOptions] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const { showToast } = useToast();

  useEffect(() => { api.get(`/workflows/${userId}/campaign-options`).then(r => setOptions(r.data?.campaigns || [])).catch(() => {}); }, [userId]);

  const save = async () => {
    setSaving(true);
    try {
      const body: any = { jessi_mode: jessi, stop_campaigns: stopCampaigns, clear_hot: clearHot, stop_tags: stopTags.split(',').map(t => t.trim()).filter(Boolean) };
      body.campaign_ids = mode === 'custom' ? ids : [];
      const res = await api.put(`/workflows/${userId}/${encodeURIComponent(wf.tag)}`, body);
      onSaved(res.data);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not save', 'error');
    } finally { setSaving(false); }
  };
  const reset = async () => {
    setSaving(true);
    try { const res = await api.delete(`/workflows/${userId}/${encodeURIComponent(wf.tag)}`); onSaved(res.data); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not reset', 'error'); }
    finally { setSaving(false); }
  };
  const Opt = ({ label, sub, selected, onPress, testId }: any) => (
    <TouchableOpacity onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, backgroundColor: selected ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: selected ? GOLD : 'transparent' }} {...tid(testId)}>
      <Ionicons name={selected ? 'radio-button-on' : 'radio-button-off'} size={18} color={selected ? GOLD : colors.textSecondary} />
      <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{label}</Text>{sub ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>{sub}</Text> : null}</View>
    </TouchableOpacity>
  );
  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%' }} {...tid('workflow-edit-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
            <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>Edit "{wf.label}" workflow</Text>
            <TouchableOpacity onPress={onClose} {...tid('workflow-edit-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40, gap: 18 }}>
            <View style={{ gap: 8 }}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>WHO HANDLES REPLIES</Text>
              <Opt label="Jessi answers automatically" sub="She texts back, books, and escalates to the rep when a human is needed. Inbox shows Auto." selected={jessi === 'auto_reply'} onPress={() => setJessi('auto_reply')} testId="workflow-jessi-auto" />
              <Opt label="Jessi drafts, rep approves" sub="Nothing goes out until the rep taps send." selected={jessi === 'draft_only'} onPress={() => setJessi('draft_only')} testId="workflow-jessi-draft" />
              <Opt label="Rep handles replies" sub="Campaign texts still go out; replies wait for the rep." selected={jessi === 'off'} onPress={() => setJessi('off')} testId="workflow-jessi-off" />
            </View>
            <View style={{ gap: 8 }}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>CAMPAIGN(S) TO ENROLL</Text>
              <Opt label={`Automatic: every active campaign triggered by "${wf.label}"`} sub="Store versions win over same-named personal copies." selected={mode === 'auto'} onPress={() => setMode('auto')} testId="workflow-campaigns-auto" />
              <Opt label="Pick exactly which campaigns" selected={mode === 'custom'} onPress={() => setMode('custom')} testId="workflow-campaigns-custom" />
              {mode === 'custom' && (
                <View style={{ gap: 6, paddingLeft: 8 }}>
                  {options.length === 0 ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>No active campaigns visible to this store.</Text> : options.map(o => {
                    const on = ids.includes(o.id);
                    return (
                      <TouchableOpacity key={o.id} onPress={() => setIds(on ? ids.filter(i => i !== o.id) : [...ids, o.id])} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }} {...tid(`workflow-campaign-opt-${o.id}`)}>
                        <Ionicons name={on ? 'checkbox' : 'square-outline'} size={20} color={on ? GOLD : colors.textSecondary} />
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 14, color: colors.text, fontWeight: '600' }}>{o.name}</Text>
                          <Text style={{ fontSize: 11, color: colors.textSecondary }}>{o.steps} touches · trigger "{o.trigger_tag || 'none'}" · {o.scope}{o.ai_enabled ? ' · AI writes' : ''}</Text>
                        </View>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              )}
            </View>
            <View style={{ gap: 8 }}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>WHEN THIS TAG IS ADDED, ALSO…</Text>
              <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, gap: 10 }}>
                <Text style={{ fontSize: 13, color: colors.text, fontWeight: '600' }}>Remove these tags (comma separated)</Text>
                <TextInput value={stopTags} onChangeText={setStopTags} placeholder="Working, Met, Lost Contact" placeholderTextColor={colors.textSecondary} style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 10, color: colors.text, fontSize: 14 }} {...tid('workflow-stop-tags')} />
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>Stop the campaigns those tags started</Text>
                  <Switch value={stopCampaigns} onValueChange={setStopCampaigns} trackColor={{ true: GOLD }} {...tid('workflow-stop-campaigns')} />
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>Clear the hot buying-intent flag</Text>
                  <Switch value={clearHot} onValueChange={setClearHot} trackColor={{ true: GOLD }} {...tid('workflow-clear-hot')} />
                </View>
              </View>
            </View>
            <TouchableOpacity onPress={save} disabled={saving} style={{ height: 50, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: saving ? 0.6 : 1 }} {...tid('workflow-save')}>
              <Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>{saving ? 'Saving…' : 'Save for the whole store'}</Text>
            </TouchableOpacity>
            {wf.customized ? (
              <TouchableOpacity onPress={reset} disabled={saving} style={{ alignItems: 'center', paddingVertical: 8 }} {...tid('workflow-reset')}>
                <Text style={{ fontSize: 13, color: colors.textSecondary }}>Reset to built-in defaults</Text>
              </TouchableOpacity>
            ) : null}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
