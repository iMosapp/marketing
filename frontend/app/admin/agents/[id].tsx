import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { showConfirm } from '../../../services/alert';
import { ScreenHeader, HeaderTextButton } from '../../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../../components/inbox/ownership';
import { Section, Label, Hint, inputStyle } from '../../../components/inbox/InboxEditorParts';
import { Chips } from '../../../components/widget/parts';
import { AgentAvatar } from '../../../components/agents/AgentPicker';
import { ListEditor } from '../../../components/agents/ListEditor';
import { TryAgent } from '../../../components/agents/TryAgent';
import { DeployPanel } from '../../../components/agents/DeployPanel';

type Tab = 'brief' | 'try' | 'deploy';
const COLORS = ['#C9A962', '#34C759', '#FF9500', '#AF52DE', '#FF3B30', '#007AFF', '#5856D6', '#FF2D55'];
const TONES = [{ value: 'friendly', label: 'Friendly' }, { value: 'professional', label: 'Professional' }, { value: 'casual', label: 'Casual' }, { value: 'energetic', label: 'Energetic' }, { value: 'direct', label: 'Direct' }];
const LANGS = [{ value: 'auto', label: "Store's language" }, { value: 'en', label: 'English' }, { value: 'es', label: 'Spanish' }, { value: 'nl', label: 'Dutch' }];

const Field = ({ label, hint, value, onChange, placeholder, multiline, colors, testId, maxLength, editable }: { label: string; hint?: string; value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean; colors: any; testId: string; maxLength?: number; editable: boolean }) => (
  <View>
    <Label colors={colors} top>{label}</Label>
    {hint ? <Hint colors={colors}>{hint}</Hint> : null}
    <TextInput value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.textSecondary} multiline={multiline} maxLength={maxLength} editable={editable}
      style={[inputStyle(colors), multiline ? { minHeight: 90, textAlignVertical: 'top' } : null, !editable ? { opacity: 0.8 } : null]} {...tid(testId)} />
  </View>
);

export default function AgentEditor() {
  const router = useRouter();
  const { id, tab: tabParam } = useLocalSearchParams<{ id: string; tab?: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [form, setForm] = useState<any>(null);
  const [usedBy, setUsedBy] = useState<any[]>([]);
  const [canEdit, setCanEdit] = useState(false);
  const [tab, setTab] = useState<Tab>((tabParam as Tab) || 'brief');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    api.get(`/agents/${id}`).then(r => { setForm(r.data.agent); setUsedBy(r.data.agent.used_by || []); setCanEdit(!!r.data.can_edit); })
      .catch((e: any) => { showToast(errText(e, 'Could not load the agent'), 'error'); if (e?.response?.status === 404) router.back(); });
  }, [id]);

  const patch = (p: any) => { setForm((f: any) => ({ ...f, ...p })); setDirty(true); };
  const save = async () => {
    if (!form.name.trim()) { showToast('Give the agent a name', 'error'); return; }
    setSaving(true);
    try {
      const { id: _i, used_by: _u, used_count: _c, created_at: _a, updated_at: _b, starter_key: _s, created_by_name: _n, ...body } = form;
      const r = await api.put(`/agents/${id}`, body);
      setForm(r.data.agent); setUsedBy(r.data.agent.used_by || []); setDirty(false);
      showToast(`${r.data.agent.name} saved. Live everywhere it is deployed.`, 'success');
    } catch (e: any) { showToast(errText(e, 'Could not save'), 'error', 3500); }
    finally { setSaving(false); }
  };
  const remove = () => {
    const deployed = usedBy.length > 0;
    showConfirm(deployed ? 'Archive this agent?' : 'Delete this agent?',
      deployed ? `${form.name} is working in ${usedBy.length} place${usedBy.length === 1 ? '' : 's'}. Archiving keeps those threads working but hides it from pickers.` : `${form.name} is not deployed anywhere, so it will be deleted for good.`,
      async () => {
        try { const r = await api.delete(`/agents/${id}`); showToast(r.data.archived ? 'Agent archived' : 'Agent deleted', 'success'); router.back(); }
        catch (e: any) { showToast(errText(e, 'Could not remove'), 'error'); }
      }, undefined, deployed ? 'Archive' : 'Delete');
  };

  if (!form) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const ro = !canEdit;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={form.name || 'New agent'} subtitle={form.title || (ro ? 'Read only · built by the super admins' : 'Agent Hub')} testID="agent-editor-header"
        right={canEdit ? <HeaderTextButton label={saving ? 'Saving…' : 'Save'} onPress={save} disabled={saving || !dirty} testID="agent-save" color={dirty ? GOLD : colors.textSecondary} /> : undefined} />
      <View style={{ flexDirection: 'row', paddingHorizontal: 16, paddingTop: 10, gap: 8 }}>
        {([['brief', 'Brief'], ['try', 'Try it'], ['deploy', 'Deploy']] as const).map(([k, l]) => (
          <TouchableOpacity key={k} onPress={() => setTab(k)} style={{ flex: 1, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: tab === k ? GOLD : colors.card, borderWidth: 1, borderColor: tab === k ? GOLD : colors.border }} {...tid(`agent-tab-${k}`)}>
            <Text style={{ fontSize: 13, fontWeight: '800', color: tab === k ? '#111' : colors.text }}>{l}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 90, gap: 14 }} keyboardShouldPersistTaps="handled">
          {tab === 'brief' && (
            <>
              <Section colors={colors} testId="agent-section-identity">
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 6 }}>
                  <AgentAvatar agent={form} size={52} />
                  <View style={{ flex: 1 }}>
                    <Label colors={colors}>Who it is</Label>
                    <Hint colors={colors}>The name and title customers see. Always an AI assistant; the chat shows a small AI tag next to the name.</Hint>
                  </View>
                </View>
                <Field label="Name" value={form.name} onChange={v => patch({ name: v })} placeholder="Ava" colors={colors} testId="agent-name" maxLength={40} editable={!ro} />
                <Field label="Title" value={form.title} onChange={v => patch({ title: v })} placeholder="Internet Sales Assistant" colors={colors} testId="agent-title" maxLength={60} editable={!ro} />
                <Field label="In a few words" value={form.tagline} onChange={v => patch({ tagline: v })} placeholder="Fast, warm, gets them in the door" colors={colors} testId="agent-tagline" maxLength={120} editable={!ro} />
                <Label colors={colors} top>Color</Label>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
                  {COLORS.map(c => (
                    <TouchableOpacity key={c} disabled={ro} onPress={() => patch({ avatar_color: c })} style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: c, alignItems: 'center', justifyContent: 'center', borderWidth: form.avatar_color === c ? 3 : 0, borderColor: '#fff' }} {...tid(`agent-color-${c.slice(1)}`)}>
                      {form.avatar_color === c ? <Ionicons name="checkmark" size={14} color="#111" /> : null}
                    </TouchableOpacity>
                  ))}
                </View>
                <Field label="Photo URL (optional)" hint="A square headshot. Shown in the website chat header when this agent is on a widget." value={form.photo_url} onChange={v => patch({ photo_url: v })} placeholder="https://…" colors={colors} testId="agent-photo" maxLength={300} editable={!ro} />
                <Label colors={colors} top>Status</Label>
                <Chips options={[{ value: 'active', label: 'Active' }, { value: 'draft', label: 'Draft' }, { value: 'archived', label: 'Archived' }]} value={form.status} onChange={v => !ro && patch({ status: v })} colors={colors} testId="agent-status" />
              </Section>

              <Section colors={colors} testId="agent-section-style">
                <Label colors={colors}>How it talks</Label>
                <Chips options={TONES} value={form.tone} onChange={v => !ro && patch({ tone: v })} colors={colors} testId="agent-tone" />
                <Label colors={colors} top>Length</Label>
                <Chips options={[{ value: 'short', label: 'Short (1 to 3 sentences)' }, { value: 'medium', label: 'A bit more room' }]} value={form.brevity} onChange={v => !ro && patch({ brevity: v })} colors={colors} testId="agent-brevity" />
                <Label colors={colors} top>Emojis</Label>
                <Chips options={[{ value: 'never', label: 'Never' }, { value: 'mirror', label: 'Only if the customer does' }]} value={form.emoji} onChange={v => !ro && patch({ emoji: v })} colors={colors} testId="agent-emoji" />
                <Label colors={colors} top>Language</Label>
                <Chips options={LANGS} value={form.language} onChange={v => !ro && patch({ language: v })} colors={colors} testId="agent-language" />
              </Section>

              <Section colors={colors} testId="agent-section-job">
                <Label colors={colors}>The job</Label>
                <Field label="What it is trying to get to" value={form.goal} onChange={v => patch({ goal: v })} placeholder="Set a time for the customer to come in" colors={colors} testId="agent-goal" maxLength={120} editable={!ro} />
                <Field label="How it works the conversation" hint="Plain English, like you are briefing a new hire. What to ask, in what order, what to offer, what to avoid." value={form.instructions} onChange={v => patch({ instructions: v })} multiline placeholder="Thank them, answer their question first, find out what they want and when they could come by, offer two specific times…" colors={colors} testId="agent-instructions" maxLength={2000} editable={!ro} />
                <ListEditor label="Always collect" hint="Gathered one at a time over the conversation, never as a form." items={form.always_collect || []} onChange={v => patch({ always_collect: v })} placeholder="A day and time to come in" colors={colors} testId="agent-collect" max={10} editable={!ro} />
              </Section>

              <Section colors={colors} testId="agent-section-knowledge">
                <Label colors={colors}>What it knows</Label>
                <Hint colors={colors}>On a widget it also knows the store's facts, specials and website. On a lead source or inbox it also knows the store and the customer's inquiry. Add what is specific to this agent here.</Hint>
                <Field label="Specialties" value={form.specialties} onChange={v => patch({ specialties: v })} placeholder="Trucks, trade-ins, towing, scheduling a visit" colors={colors} testId="agent-specialties" maxLength={200} editable={!ro} />
                <ListEditor label="Agent facts" hint="One plain sentence each. Quoted as written, never embellished." items={form.facts || []} onChange={v => patch({ facts: v })} placeholder="Loaners are free on repairs over two hours" colors={colors} testId="agent-facts" max={30} editable={!ro} />
              </Section>

              <Section colors={colors} testId="agent-section-guardrails">
                <Label colors={colors}>Guardrails</Label>
                <ListEditor label="Hand to a person when they bring up" hint="The agent says a teammate will take that part and does not answer it. On a widget this triggers the hand-off (name + mobile)." items={form.hand_to_human || []} onChange={v => patch({ hand_to_human: v })} placeholder="Price or payments" colors={colors} testId="agent-handoff" editable={!ro} />
                <ListEditor label="Never say or do" items={form.never_say || []} onChange={v => patch({ never_say: v })} placeholder="As an AI" colors={colors} testId="agent-never" editable={!ro} />
              </Section>

              <Section colors={colors} testId="agent-section-advanced">
                <Label colors={colors}>Advanced: owner's instructions</Label>
                <Hint colors={colors}>Optional. Anything you write here is placed at the top of the agent's brief and wins over the general style. Leave blank unless you know exactly what you want.</Hint>
                <TextInput value={form.custom_prompt} onChangeText={v => patch({ custom_prompt: v })} multiline editable={!ro} placeholder="Full instructions in your own words…" placeholderTextColor={colors.textSecondary} style={[inputStyle(colors), { minHeight: 110, textAlignVertical: 'top' }]} {...tid('agent-custom-prompt')} />
              </Section>

              {canEdit ? (
                <TouchableOpacity onPress={remove} style={{ alignSelf: 'center', flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 12 }} {...tid('agent-delete')}>
                  <Ionicons name="trash-outline" size={16} color="#FF3B30" />
                  <Text style={{ fontSize: 13, fontWeight: '700', color: '#FF3B30' }}>{usedBy.length ? 'Archive this agent' : 'Delete this agent'}</Text>
                </TouchableOpacity>
              ) : null}
            </>
          )}

          {tab === 'try' && (
            dirty ? <Section colors={colors} testId="agent-try-unsaved"><Text style={{ fontSize: 13, color: colors.textSecondary }}>Save your changes first so the practice run uses the brief you just wrote.</Text></Section>
              : <TryAgent agentId={String(id)} agent={form} colors={colors} showToast={showToast} />
          )}

          {tab === 'deploy' && <DeployPanel agentId={String(id)} agentName={form.name} colors={colors} showToast={showToast} canEdit={canEdit} usedBy={usedBy} onChanged={setUsedBy} />}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
