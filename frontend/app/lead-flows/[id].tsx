import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Switch, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderTextButton } from '../../components/common/ScreenHeader';
import { ContactModeToggle, LeadCallLadder } from '../../components/admin/LeadWorkflowControls';
import { AfterHoursRule, type StoreHours } from '../../components/admin/LeadTimingControls';
import { LeadFlowSummary, type LeadFlow } from '../../components/admin/LeadFlowSummary';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const MERGE = ['{{first_name}}', '{{vehicle}}', '{{lead_source}}', '{{rep_name}}'];
type Tab = 'steps' | 'settings' | 'automations';

export default function LeadFlowEditor() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [flow, setFlow] = useState<LeadFlow | null>(null);
  const [reps, setReps] = useState<any[]>([]);
  const [storeHours, setStoreHours] = useState<StoreHours | null>(null);
  const [tab, setTab] = useState<Tab>('steps');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [tagsClaim, setTagsClaim] = useState('');
  const [tagsNoAnswer, setTagsNoAnswer] = useState('');

  useEffect(() => {
    if (!id || !user?._id) return;
    Promise.all([api.get(`/lead-flows/${id}`), api.get('/lead-flows')]).then(([f, lib]) => {
      setFlow(f.data);
      setTagsClaim((f.data.tags_on_claim || []).join(', '));
      setTagsNoAnswer((f.data.tags_on_no_answer || []).join(', '));
      setReps((lib.data.reps || []).map((r: any) => ({ ...r, _id: r._id || r.id })));
      setStoreHours(lib.data.store_hours || null);
    }).catch((e: any) => showToast(e?.response?.data?.detail || 'Could not load flow', 'error'));
  }, [id, user?._id]);

  const patch = (p: Partial<LeadFlow>) => { setFlow(f => (f ? { ...f, ...p } : f)); setDirty(true); };
  const splitTags = (s: string) => s.split(',').map(t => t.trim()).filter(Boolean);

  const save = async () => {
    if (!flow) return;
    if (!flow.name.trim()) { showToast('Give the flow a name', 'error'); return; }
    if (flow.contact_mode === 'text_and_call' && !flow.call_attempts.some(a => a.user_ids.length)) { showToast('Add at least one rep to attempt 1', 'error'); setTab('steps'); return; }
    setSaving(true);
    try {
      const body: any = { ...flow, tags_on_claim: splitTags(tagsClaim), tags_on_no_answer: splitTags(tagsNoAnswer) };
      delete body.id; delete body.sources; delete body.source_count; delete body.summary; delete body.updated_by_name; delete body.template_key;
      body.workflow_user_ids = flow.contact_mode === 'text_only' ? (flow as any).workflow_user_ids || [] : [];
      const res = await api.put(`/lead-flows/${flow.id}`, body);
      setFlow(res.data); setDirty(false);
      showToast(res.data.synced_sources ? `Saved · ${res.data.synced_sources} lead source${res.data.synced_sources === 1 ? '' : 's'} updated` : 'Flow saved', 'success');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not save flow', 'error');
    } finally { setSaving(false); }
  };

  if (!flow) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Lead Flow" testID="lead-flow-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;

  const input = { backgroundColor: colors.surface, borderRadius: 12, padding: 12, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border } as const;
  const label = { fontSize: 13, fontWeight: '700' as const, color: colors.text, marginBottom: 6 };
  const hint = { fontSize: 12, color: colors.textSecondary, marginBottom: 8, lineHeight: 17 };
  const Section = ({ children }: { children: React.ReactNode }) => <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 4 }}>{children}</View>;
  const Toggle = ({ title, sub, value, onChange, testID }: { title: string; sub?: string; value: boolean; onChange: (v: boolean) => void; testID: string }) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8, gap: 12 }}>
      <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{title}</Text>{sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{sub}</Text> : null}</View>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: GOLD }} {...tid(testID)} />
    </View>
  );
  const MergeChips = ({ field }: { field: 'intake_text' | 'after_hours_text' | 'no_answer_text' }) => (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
      {MERGE.map(m => (
        <TouchableOpacity key={m} onPress={() => patch({ [field]: (flow[field] || '') + m } as any)} style={{ backgroundColor: colors.surface, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1, borderColor: colors.border }}>
          <Text style={{ fontSize: 11, fontWeight: '700', color: GOLD, fontFamily: 'monospace' }}>{m}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
  const visibleReps = reps.filter(r => r.role !== 'super_admin' || r._id === user?._id);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={flow.name || 'Lead Flow'} subtitle={flow.source_count ? `Used by ${flow.source_count} source${flow.source_count === 1 ? '' : 's'}` : 'Not attached to a source yet'} testID="lead-flow-header"
        right={<HeaderTextButton label={saving ? 'Saving…' : 'Save'} onPress={save} disabled={saving} testID="lead-flow-save" color={dirty ? GOLD : colors.textSecondary} />} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 14 }} keyboardShouldPersistTaps="handled">
          <Section>
            <Text style={label}>Flow name</Text>
            <TextInput value={flow.name} onChangeText={v => patch({ name: v })} placeholder="e.g. Website leads: ring all, then manager" placeholderTextColor={colors.textSecondary} style={input} {...tid('lead-flow-name')} />
            <Text style={[label, { marginTop: 10 }]}>What it's for (optional)</Text>
            <TextInput value={flow.description} onChangeText={v => patch({ description: v })} placeholder="One line your managers will understand" placeholderTextColor={colors.textSecondary} style={input} {...tid('lead-flow-description')} />
          </Section>

          <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
            {([['steps', 'Steps'], ['settings', 'Settings'], ['automations', 'Automations']] as const).map(([k, l]) => (
              <TouchableOpacity key={k} onPress={() => setTab(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center', backgroundColor: tab === k ? GOLD : 'transparent' }} {...tid(`lead-flow-tab-${k}`)}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: tab === k ? '#111' : colors.textSecondary }}>{l}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {tab === 'steps' && (
            <Section>
              <ContactModeToggle value={flow.contact_mode} onChange={v => patch({ contact_mode: v, call_attempts: v === 'text_and_call' && flow.call_attempts.length === 0 ? [{ user_ids: [], delay_seconds: 0, delivery: 'call' }] : flow.call_attempts })} colors={colors} />
              <View style={{ height: 14 }} />
              {flow.contact_mode === 'text_and_call' ? (
                <LeadCallLadder attempts={flow.call_attempts} reps={visibleReps} onChange={a => patch({ call_attempts: a })} colors={colors} max={6} allowPush />
              ) : (
                <View>
                  <Text style={label}>Who gets the push</Text>
                  <Text style={hint}>Everyone here is notified the second a lead lands. First to claim owns it.</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                    {visibleReps.map(r => {
                      const ids: string[] = (flow as any).workflow_user_ids || [];
                      const on = ids.includes(r._id);
                      return (
                        <TouchableOpacity key={r._id} onPress={() => patch({ workflow_user_ids: on ? ids.filter(i => i !== r._id) : [...ids, r._id] } as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, backgroundColor: on ? '#34C75922' : colors.surface, borderWidth: 1, borderColor: on ? '#34C759' : colors.border }} {...tid(`lead-flow-notify-${r._id}`)}>
                          {on && <Ionicons name="checkmark" size={13} color="#34C759" />}
                          <Text style={{ fontSize: 13, color: colors.text, fontWeight: on ? '700' : '500' }}>{r.name || r.email}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>
              )}
            </Section>
          )}

          {tab === 'settings' && (
            <>
              <Section>
                <AfterHoursRule mode={flow.after_hours_mode} windowStart={flow.text_window_start} windowEnd={flow.text_window_end} storeHours={storeHours}
                  onChange={p => patch(p as any)} onEditHours={() => router.push('/settings/store-profile' as any)} colors={colors} />
              </Section>
              <Section>
                <Text style={label}>Caller ID when ringing reps</Text>
                <Text style={hint}>The number the rep sees (and the customer sees on the bridged call).</Text>
                {([['rep', 'The rep\'s own business line', 'Replies land in that rep\'s inbox. Recommended.'], ['store', 'The store\'s main line', 'Falls back to the rep\'s line if the source has no number.']] as const).map(([v, t, s]) => (
                  <TouchableOpacity key={v} onPress={() => patch({ caller_id_mode: v })} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, marginBottom: 6, backgroundColor: flow.caller_id_mode === v ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: flow.caller_id_mode === v ? GOLD : 'transparent' }} {...tid(`lead-flow-callerid-${v}`)}>
                    <Ionicons name={flow.caller_id_mode === v ? 'radio-button-on' : 'radio-button-off'} size={18} color={flow.caller_id_mode === v ? GOLD : colors.textSecondary} />
                    <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{t}</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>{s}</Text></View>
                  </TouchableOpacity>
                ))}
              </Section>
              <Section>
                <Toggle title="Claim = call me" sub="When a rep claims in the app, ring their cell and bridge to the customer on press 1." value={flow.auto_call_on_claim} onChange={v => patch({ auto_call_on_claim: v })} testID="lead-flow-autocall" />
                <Toggle title="Push everyone on intake" sub="All reps on the flow get the new-lead push, not just the ones ringing." value={flow.notify_all_on_intake} onChange={v => patch({ notify_all_on_intake: v })} testID="lead-flow-notify-all" />
              </Section>
            </>
          )}

          {tab === 'automations' && (
            <>
              <Section>
                <Text style={label}>Instant intake text</Text>
                <Text style={hint}>Sent to the lead the moment it arrives (inside the texting window). Tap a field to insert it.</Text>
                <MergeChips field="intake_text" />
                <TextInput value={flow.intake_text} onChangeText={v => patch({ intake_text: v })} multiline style={[input, { minHeight: 90, textAlignVertical: 'top' }]} placeholder="Blank = no intake text" placeholderTextColor={colors.textSecondary} {...tid('lead-flow-intake-text')} />
                <Text style={[label, { marginTop: 14 }]}>After-hours version</Text>
                <Text style={hint}>Used instead of the intake text when the store is closed. Blank = same text as above.</Text>
                <MergeChips field="after_hours_text" />
                <TextInput value={flow.after_hours_text} onChangeText={v => patch({ after_hours_text: v })} multiline style={[input, { minHeight: 90, textAlignVertical: 'top' }]} placeholderTextColor={colors.textSecondary} {...tid('lead-flow-after-hours-text')} />
              </Section>
              <Section>
                <Toggle title="Jessi answers replies" sub="Until a rep claims. She escalates when a human is needed." value={flow.va_enabled} onChange={v => patch({ va_enabled: v })} testID="lead-flow-jessi" />
                {flow.va_enabled && (
                  <View style={{ marginTop: 6 }}>
                    <Text style={label}>What are these leads asking about? (optional)</Text>
                    <TextInput value={flow.inquiry_context} onChangeText={v => patch({ inquiry_context: v.slice(0, 300) })} multiline style={[input, { minHeight: 60, textAlignVertical: 'top' }]} placeholder="e.g. used trucks under $30k. Blank = automatic" placeholderTextColor={colors.textSecondary} {...tid('lead-flow-inquiry')} />
                  </View>
                )}
              </Section>
              <Section>
                <Text style={label}>When a rep claims</Text>
                <Text style={hint}>Tags added to the contact (comma separated). Tag workflows run too, so "Working" starts its campaign.</Text>
                <TextInput value={tagsClaim} onChangeText={v => { setTagsClaim(v); setDirty(true); }} style={input} placeholder="Working" placeholderTextColor={colors.textSecondary} {...tid('lead-flow-tags-claim')} />
              </Section>
              <Section>
                <Text style={label}>When nobody answers</Text>
                <Text style={hint}>After the last attempt rings out with no claim. The lead always stays in the shared queue.</Text>
                <Toggle title="Text the lead" sub="So they hear from us even when the floor is slammed." value={flow.exhausted_text_lead} onChange={v => patch({ exhausted_text_lead: v })} testID="lead-flow-exhausted-text" />
                {flow.exhausted_text_lead && (
                  <View>
                    <MergeChips field="no_answer_text" />
                    <TextInput value={flow.no_answer_text} onChangeText={v => patch({ no_answer_text: v })} multiline style={[input, { minHeight: 80, textAlignVertical: 'top' }]} placeholderTextColor={colors.textSecondary} {...tid('lead-flow-no-answer-text')} />
                  </View>
                )}
                <Toggle title="Alert the managers" sub="Push + alert to every manager on the store." value={flow.exhausted_push_manager} onChange={v => patch({ exhausted_push_manager: v })} testID="lead-flow-exhausted-push" />
                <Text style={[label, { marginTop: 8 }]}>Tags to add</Text>
                <TextInput value={tagsNoAnswer} onChangeText={v => { setTagsNoAnswer(v); setDirty(true); }} style={input} placeholder="Lost Contact" placeholderTextColor={colors.textSecondary} {...tid('lead-flow-tags-no-answer')} />
              </Section>
            </>
          )}

          <Section>
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 6 }}>WHAT THIS FLOW DOES {dirty ? '(saved version)' : ''}</Text>
            <LeadFlowSummary rows={flow.summary} colors={colors} testID="lead-flow-summary" />
            {flow.sources.length > 0 && (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                {flow.sources.map(s => (
                  <TouchableOpacity key={s.id} onPress={() => router.push(`/admin/lead-sources/${s.id}` as any)} style={{ paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: GOLD + '22', borderWidth: 1, borderColor: GOLD + '66' }}>
                    <Text style={{ fontSize: 11, fontWeight: '700', color: GOLD }}>{s.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </Section>

          <TouchableOpacity onPress={save} disabled={saving} style={{ height: 52, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: saving ? 0.6 : 1 }} {...tid('lead-flow-save-bottom')}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>{saving ? 'Saving…' : flow.source_count ? `Save and update ${flow.source_count} source${flow.source_count === 1 ? '' : 's'}` : 'Save flow'}</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
