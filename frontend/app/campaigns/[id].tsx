import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Switch, ActivityIndicator, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { showAlert } from '../../services/alert';
import api, { campaignsAPI } from '../../services/api';
import { SmartTagPicker } from '../../components/SmartTagPicker';
import { SheetShell, Eyebrow, OptionRow, GoldButton, Segmented, Chip } from '../../components/campaigns/Sheet';
import { TouchEditorSheet } from '../../components/campaigns/TouchEditorSheet';
import { TouchTimeline } from '../../components/campaigns/TouchTimeline';
import { PeopleInPlan, Enrollment } from '../../components/campaigns/PeopleInPlan';
import { useQuickLinks } from '../../components/campaigns/useQuickLinks';
import {
  Touch, normalizeTouches, touchesToSequences, newTouch, touchMinutes, summarizeTouches, isDateCampaign, dateTypeOf, DATE_TYPES,
  REPLY_MODES, REPLY_SHORT, DELIVERY_MODES, isAutoDelivery, tagColor, scopeLabel, DEFAULT_SAMPLE, Sample, GOLD, GREEN, RED, AMBER, tid,
} from '../../components/campaigns/utils';

type Sheet = 'touch' | 'replies' | 'trigger' | 'delivery' | 'rename' | null;

export default function CampaignEditorScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const user = useAuthStore(s => s.user);
  const { showToast } = useToast();
  const quickLinks = useQuickLinks(user);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [campaign, setCampaign] = useState<any>(null);
  const [canEdit, setCanEdit] = useState(true);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [tags, setTags] = useState<any[]>([]);
  const [workflow, setWorkflow] = useState<any>(null);
  const [workflows, setWorkflows] = useState<any[]>([]);

  const [name, setName] = useState('');
  const [triggerType, setTriggerType] = useState<'tag' | 'date'>('tag');
  const [triggerTag, setTriggerTag] = useState('');
  const [dateType, setDateType] = useState('');
  const [active, setActive] = useState(true);
  const [aiAssistMode, setAiAssistMode] = useState('auto_reply');
  const [escThreshold, setEscThreshold] = useState(2);
  const [escTimeout, setEscTimeout] = useState(15);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [deliveryMode, setDeliveryMode] = useState('auto');
  const [inboundDefault, setInboundDefault] = useState(false);
  const [touches, setTouches] = useState<Touch[]>([]);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState(false);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [editing, setEditing] = useState<{ touch: Touch; index: number; isNew: boolean } | null>(null);

  const mark = <T,>(setter: (v: T) => void) => (v: T) => { setter(v); setDirty(true); };

  const load = useCallback(async () => {
    if (!id || !user?._id) return;
    try {
      const [data, enr, perm, tagList, wfs] = await Promise.all([
        campaignsAPI.get(user._id, id),
        campaignsAPI.getEnrollments(user._id, id).catch(() => []),
        api.get(`/campaigns/${user._id}/permissions`).then(r => r.data).catch(() => ({ allowed: true })),
        api.get(`/tags/${user._id}`).then(r => r.data || []).catch(() => []),
        api.get(`/workflows/${user._id}`).then(r => r.data?.workflows || []).catch(() => []),
      ]);
      setCampaign(data);
      setEnrollments(enr || []);
      setCanEdit(!!perm?.allowed);
      setTags(tagList);
      setWorkflows(wfs);
      setName(data.name || '');
      const dateBased = isDateCampaign(data);
      setTriggerType(dateBased ? 'date' : 'tag');
      setTriggerTag(data.trigger_tag || '');
      setDateType(dateTypeOf(data));
      setActive(data.active ?? true);
      setAiAssistMode(data.ai_assist_mode || (data.ai_enabled ? 'auto_reply' : 'off'));
      setEscThreshold(data.escalation_threshold || 2);
      setEscTimeout(data.escalation_timeout_minutes || 15);
      setAiEnabled(!!data.ai_enabled);
      setDeliveryMode(isAutoDelivery(data.delivery_mode) ? 'auto' : 'manual');
      setInboundDefault(data.is_inbound_default === true);
      setTouches(normalizeTouches(data.sequences, data.message_template));
      setDirty(false);
    } catch (e: any) {
      if (e?.response?.status === 404) setNotFound(true);
      else showToast(e?.response?.data?.detail || 'Could not load campaign', 'error');
    } finally { setLoading(false); }
  }, [id, user?._id]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    setWorkflow(triggerType === 'tag' && triggerTag ? workflows.find((w: any) => w.tag === triggerTag.toLowerCase()) || null : null);
  }, [workflows, triggerTag, triggerType]);

  const triggerLabel = triggerType === 'date' ? (DATE_TYPES.find(d => d.id === dateType)?.name.toLowerCase() || 'the date') : (triggerTag || 'the tag');
  const triggerColor = triggerType === 'date' ? (DATE_TYPES.find(d => d.id === dateType)?.color || AMBER) : tagColor(triggerTag);
  const livePeople = enrollments.filter(e => e.status === 'active' || e.status === 'paused');
  const sample: Sample = useMemo(() => ({
    ...DEFAULT_SAMPLE,
    first_name: livePeople[0]?.contact_name?.split(' ')[0] || DEFAULT_SAMPLE.first_name,
    my_name: (user as any)?.first_name || (user as any)?.name?.split(' ')[0] || DEFAULT_SAMPLE.my_name,
    company: (user as any)?.company || (user as any)?.store_name || DEFAULT_SAMPLE.company,
  }), [livePeople.length, user?._id]);
  const mismatch = workflow?.jessi_mode && workflow.jessi_mode !== aiAssistMode ? workflow.jessi_mode : null;

  const save = async () => {
    if (!name.trim()) { showToast('Give the plan a name', 'error'); return; }
    const bad = touches.findIndex(t => (t.actionType === 'message' && !t.message.trim()) || (t.actionType === 'send_card' && !t.cardType));
    if (bad >= 0) { showToast(`Touch ${bad + 1} is not finished yet`, 'error'); return; }
    setSaving(true);
    try {
      await campaignsAPI.update(user!._id, id!, {
        name: name.trim(),
        trigger_tag: triggerType === 'tag' ? triggerTag : '',
        type: triggerType === 'date' ? dateType : (isDateCampaign(campaign) ? 'custom' : campaign?.type || 'custom'),
        date_type: triggerType === 'date' ? dateType : '',
        active,
        ai_assist_mode: aiAssistMode,
        escalation_threshold: escThreshold,
        escalation_timeout_minutes: escTimeout,
        ai_enabled: aiEnabled,
        delivery_mode: deliveryMode,
        sequences: touchesToSequences(touches),
      });
      setDirty(false);
      showToast('Plan saved', 'success');
      load();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not save', 'error');
    } finally { setSaving(false); }
  };

  const goBack = () => {
    const leave = () => (router.canGoBack() ? router.back() : router.replace('/campaigns' as any));
    if (!dirty) return leave();
    showAlert('Unsaved changes', 'Save your changes to this plan?', [
      { text: 'Discard', style: 'destructive', onPress: leave },
      { text: 'Keep editing', style: 'cancel' },
      { text: 'Save', onPress: async () => { await save(); leave(); } },
    ]);
  };

  const toggleLive = async (v: boolean) => {
    setActive(v);
    try { await campaignsAPI.update(user!._id, id!, { active: v }); showToast(v ? 'Plan is live' : 'Plan paused', 'success'); }
    catch (e: any) { setActive(!v); showToast(e?.response?.data?.detail || 'Could not update', 'error'); }
  };

  const toggleInbound = async (v: boolean) => {
    setInboundDefault(v);
    try {
      if (v) await api.post(`/campaigns/${user!._id}/${id}/set-inbound-default`);
      else await api.delete(`/campaigns/${user!._id}/${id}/set-inbound-default`);
      showToast(v ? 'New inbound texters will join this plan' : 'Inbound default cleared', 'success');
    } catch (e: any) { setInboundDefault(!v); showToast(e?.response?.data?.detail || 'Could not update', 'error'); }
  };

  const openTouch = (touch: Touch, index: number, isNew = false) => { setEditing({ touch, index, isNew }); setSheet('touch'); };
  const addAfter = (index: number) => openTouch(newTouch(touches[index]), index + 1, true);
  const commitTouch = (t: Touch) => {
    const list = editing?.isNew ? [...touches.slice(0, editing.index), t, ...touches.slice(editing.index)] : touches.map((x, i) => (i === editing!.index ? t : x));
    setTouches([...list].sort((a, b) => touchMinutes(a) - touchMinutes(b)));
    setDirty(true); setSheet(null); setEditing(null);
  };
  const removeTouch = () => {
    if (!editing || editing.isNew) { setSheet(null); setEditing(null); return; }
    setTouches(touches.filter((_, i) => i !== editing.index)); setDirty(true); setSheet(null); setEditing(null);
  };

  const removePerson = (e: Enrollment) => showAlert('Remove from plan?', `${e.contact_name} will stop getting these texts.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Remove', style: 'destructive', onPress: async () => {
      try { await api.delete(`/campaigns/${user!._id}/${id}/enrollments/${e._id}`); setEnrollments(p => p.filter(x => x._id !== e._id)); showToast(`${e.contact_name} removed`); }
      catch { showToast('Could not remove', 'error'); }
    } },
  ]);
  const removeEveryone = () => showAlert('Remove everyone?', `Stops all pending texts for ${livePeople.length} people. This cannot be undone.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Remove all', style: 'destructive', onPress: async () => {
      try { await api.delete(`/campaigns/${user!._id}/${id}/enrollments`); setEnrollments(p => p.map(e => (e.status === 'active' || e.status === 'paused' ? { ...e, status: 'cancelled' } : e))); showToast('Everyone removed'); }
      catch { showToast('Could not remove', 'error'); }
    } },
  ]);
  const duplicate = async () => {
    try { const c = await campaignsAPI.duplicate(user!._id, id!); showToast(`Copied as "${c.name}"`, 'success'); router.replace(`/campaigns/${c._id || c.id}` as any); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not duplicate', 'error'); }
  };
  const del = () => showAlert('Delete this plan?', `"${name}" and everyone in it will be removed.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: async () => {
      try { await campaignsAPI.delete(user!._id, id!); router.replace('/campaigns' as any); }
      catch (e: any) { showToast(e?.response?.data?.detail || 'Could not delete', 'error'); }
    } },
  ]);

  if (loading) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ActivityIndicator style={{ marginTop: 80 }} color={GOLD} /></SafeAreaView>;
  if (notFound || !campaign) return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', gap: 12 }} edges={['top']}>
      <Ionicons name="alert-circle-outline" size={44} color={colors.textTertiary} />
      <Text style={{ fontSize: 16, color: colors.text, fontWeight: '700' }}>Campaign not found</Text>
      <TouchableOpacity onPress={() => router.replace('/campaigns' as any)} {...tid('campaign-back-to-list')}><Text style={{ color: GOLD, fontWeight: '700' }}>Back to campaigns</Text></TouchableOpacity>
    </SafeAreaView>
  );

  const Row = ({ icon, color, title, sub, onPress, right, testId }: { icon: any; color: string; title: string; sub?: string; onPress?: () => void; right?: React.ReactNode; testId: string }) => (
    <TouchableOpacity onPress={onPress} disabled={!onPress} activeOpacity={0.7} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11 }} {...tid(testId)}>
      <View style={{ width: 30, alignItems: 'center' }}><Ionicons name={icon} size={19} color={color} /></View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{title}</Text>
        {sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>{sub}</Text> : null}
      </View>
      {right ?? (onPress ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null)}
    </TouchableOpacity>
  );
  const Divider = () => <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 42 }} />;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, gap: 8 }}>
        <TouchableOpacity onPress={goBack} hitSlop={8} style={{ padding: 4 }} {...tid('campaign-back')}><Ionicons name="chevron-back" size={26} color={colors.text} /></TouchableOpacity>
        <TouchableOpacity style={{ flex: 1, alignItems: 'center' }} onPress={() => canEdit && setSheet('rename')} disabled={!canEdit} {...tid('campaign-title')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }} numberOfLines={1}>{name || 'Untitled plan'}</Text>
            {canEdit ? <Ionicons name="pencil" size={13} color={colors.textTertiary} /> : null}
          </View>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>Campaign · {scopeLabel(campaign)}{canEdit ? '' : ' · view only'}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={save} disabled={!canEdit || !dirty || saving} hitSlop={8} style={{ minWidth: 52, alignItems: 'flex-end', padding: 4, opacity: canEdit && dirty ? 1 : 0.35 }} {...tid('campaign-save')}>
          {saving ? <ActivityIndicator size="small" color={GOLD} /> : <Text style={{ fontSize: 16, fontWeight: '800', color: GOLD }}>Save</Text>}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 16 }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: active ? GREEN + '55' : colors.border, paddingHorizontal: 14, paddingVertical: 12 }} {...tid('campaign-live-card')}>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: active ? GREEN : colors.textTertiary }} />
              <Text style={{ fontSize: 13, fontWeight: '800', letterSpacing: 0.6, color: active ? GREEN : colors.textSecondary }}>{active ? 'LIVE' : 'PAUSED'}</Text>
            </View>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 3 }}>{summarizeTouches(touches)} · {livePeople.length} {livePeople.length === 1 ? 'person' : 'people'} in it</Text>
          </View>
          <Switch value={active} onValueChange={toggleLive} disabled={!canEdit} trackColor={{ true: GREEN }} {...tid('campaign-live-switch')} />
        </View>

        <TouchableOpacity onPress={() => canEdit && setSheet('trigger')} disabled={!canEdit} activeOpacity={0.8} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 14 }} {...tid('campaign-trigger-card')}>
          <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: triggerColor + '22', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={triggerType === 'date' ? ((DATE_TYPES.find(d => d.id === dateType)?.icon as any) || 'calendar') : 'pricetag'} size={18} color={triggerColor} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>
              {triggerType === 'date'
                ? (DATE_TYPES.find(d => d.id === dateType)?.phrase || 'Pick a date')
                : triggerTag ? <>When a contact is tagged <Text style={{ color: triggerColor }}>{triggerTag}</Text></> : 'Pick the tag that starts this'}
            </Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
              {triggerType === 'date' ? 'Runs the morning of the date for contacts with that date on file' : triggerTag ? 'Applied by you, a quick action, or any rep in the store' : 'Nothing starts until a trigger is set'}
            </Text>
          </View>
          {canEdit ? <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Change</Text> : null}
        </TouchableOpacity>

        {mismatch && canEdit ? (
          <View style={{ flexDirection: 'row', gap: 10, backgroundColor: AMBER + '1A', borderRadius: 14, borderWidth: 1, borderColor: AMBER + '55', padding: 12 }} {...tid('campaign-mismatch')}>
            <Ionicons name="warning" size={18} color={AMBER} style={{ marginTop: 1 }} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>
                <Text style={{ fontWeight: '800', color: AMBER }}>Heads up: </Text>the {workflow.label} workflow says <Text style={{ fontWeight: '700' }}>{REPLY_SHORT[mismatch]}</Text>, but this plan says {REPLY_SHORT[aiAssistMode]}. The workflow wins for replies.
              </Text>
              <TouchableOpacity onPress={() => { setAiAssistMode(mismatch); setDirty(true); }} style={{ marginTop: 6 }} {...tid('campaign-mismatch-fix')}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Match the workflow</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : null}

        <View style={{ gap: 8 }}>
          <Eyebrow colors={colors}>WHAT HAPPENS</Eyebrow>
          <View style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12 }}>
            <Row icon="sparkles" color={GOLD} title={REPLY_SHORT[aiAssistMode] || 'Replies'} testId="campaign-replies-row"
              sub={aiAssistMode === 'auto_reply' ? 'Books, answers questions, hands off to you when she needs a human.' : aiAssistMode === 'draft_only' ? 'Every reply waits for your approval.' : aiAssistMode === 'auto_with_approval' ? `Auto for the first ${escThreshold} replies, then holds for you.` : 'Replies land in your inbox like any other text.'}
              onPress={canEdit ? () => setSheet('replies') : undefined} />
            <Divider />
            <Row icon="create-outline" color={GOLD} title={aiEnabled ? 'Jessi personalizes each text' : 'Texts send exactly as written'} testId="campaign-personalize-row"
              sub={aiEnabled ? 'She rewrites each touch in your voice using what she knows about the customer.' : 'Only the {fields} get filled in.'}
              right={<Switch value={aiEnabled} onValueChange={mark(setAiEnabled)} disabled={!canEdit} trackColor={{ true: GOLD }} {...tid('campaign-personalize-switch')} />} />
            <Divider />
            <Row icon={deliveryMode === 'auto' ? 'paper-plane-outline' : 'hand-left-outline'} color={GREEN} title={DELIVERY_MODES.find(d => d.value === deliveryMode)?.label || ''} testId="campaign-delivery-row"
              sub={deliveryMode === 'auto' ? 'From your tracking number, timed from when the tag is added. Never overnight.' : 'Each touch shows up as a task with the text ready to go.'}
              onPress={canEdit ? () => setSheet('delivery') : undefined} />
            <Divider />
            <Row icon="chatbox-ellipses-outline" color="#5AC8FA" title="New inbound texters join this plan" testId="campaign-inbound-row"
              sub={inboundDefault ? 'Anyone who texts your number for the first time is enrolled here.' : 'Turn on to make this the plan for first-time inbound texts.'}
              right={<Switch value={inboundDefault} onValueChange={toggleInbound} disabled={!canEdit} trackColor={{ true: '#5AC8FA' }} {...tid('campaign-inbound-switch')} />} />
            {workflow && (workflow.stop_tags?.length || workflow.clear_hot) ? (
              <>
                <Divider />
                <Row icon="stop-circle-outline" color={AMBER} title={`${workflow.label} tag also ${workflow.stop_tags?.length ? `stops ${workflow.stop_tags.length > 1 ? `${workflow.stop_tags.slice(0, -1).join(', ')} & ${workflow.stop_tags.slice(-1)}` : workflow.stop_tags[0]} follow-ups` : 'clears the hot flag'}`} sub={`From the store's ${workflow.label} workflow.`} testId="campaign-workflow-row"
                  onPress={() => router.push('/workflows' as any)} right={<Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>Workflows</Text>} />
              </>
            ) : null}
          </View>
        </View>

        <View style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Eyebrow colors={colors} style={{ flex: 1 }}>TIMELINE · {touches.length} {touches.length === 1 ? 'TOUCH' : 'TOUCHES'}</Eyebrow>
            {touches.length ? <Chip label={preview ? `Previewing as ${sample.first_name}` : 'Preview'} icon={preview ? 'eye' : 'eye-outline'} active={preview} colors={colors} testId="campaign-preview-toggle" onPress={() => setPreview(p => !p)} /> : null}
          </View>
          {touches.length === 0 ? (
            <View style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 18, alignItems: 'center', gap: 10 }} {...tid('campaign-no-touches')}>
              <Ionicons name="chatbubbles-outline" size={28} color={colors.textTertiary} />
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 }}>No touches yet. Add the first text that goes out when someone is tagged {triggerLabel}.</Text>
              {canEdit ? <GoldButton label="Add the first touch" icon="add" onPress={() => openTouch(newTouch(), 0, true)} testId="campaign-add-first-touch" /> : null}
            </View>
          ) : (
            <TouchTimeline touches={touches} aiPersonalizes={aiEnabled} preview={preview} sample={sample} editable={canEdit} colors={colors} onEdit={openTouch} onAddAfter={addAfter} />
          )}
        </View>

        <PeopleInPlan enrollments={enrollments} triggerLabel={triggerType === 'tag' ? triggerTag : ''} colors={colors} onRemove={removePerson} onRemoveAll={removeEveryone} />

        {canEdit ? (
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 8 }}>
            <TouchableOpacity onPress={duplicate} style={{ flex: 1, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('campaign-duplicate')}>
              <Ionicons name="copy-outline" size={16} color={colors.textSecondary} /><Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary }}>Duplicate</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={del} style={{ flex: 1, height: 44, borderRadius: 12, borderWidth: 1, borderColor: RED + '55', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('campaign-delete')}>
              <Ionicons name="trash-outline" size={16} color={RED} /><Text style={{ fontSize: 13, fontWeight: '700', color: RED }}>Delete plan</Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </ScrollView>

      {dirty && canEdit ? (
        <View style={{ position: 'absolute', left: 16, right: 16, bottom: 20 }} pointerEvents="box-none">
          <GoldButton label={saving ? 'Saving…' : 'Save changes'} onPress={save} disabled={saving} testId="campaign-save-bar" icon="checkmark" />
        </View>
      ) : null}

      {sheet === 'touch' && editing ? (
        <TouchEditorSheet touch={editing.touch} index={editing.index} isFirst={editing.index === 0} triggerLabel={triggerLabel} canRemove={!editing.isNew && touches.length > 0}
          campaignId={id!} quickLinks={quickLinks} aiPersonalizes={aiEnabled} colors={colors} onDone={commitTouch} onRemove={removeTouch} onClose={() => { setSheet(null); setEditing(null); }} />
      ) : null}

      {sheet === 'replies' ? (
        <SheetShell title="Who handles replies?" subtitle="Applies to everyone in this plan." onClose={() => setSheet(null)} testId="replies-sheet" colors={colors}
          footer={<GoldButton label="Done" onPress={() => setSheet(null)} testId="replies-done" />}>
          <View style={{ gap: 8 }}>
            {REPLY_MODES.map(m => <OptionRow key={m.value} label={m.label} sub={m.sub} selected={aiAssistMode === m.value} onPress={() => { setAiAssistMode(m.value); setDirty(true); }} testId={`replies-${m.value}`} colors={colors} />)}
          </View>
          {aiAssistMode === 'auto_with_approval' ? (
            <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, gap: 12 }}>
              <Stepper label="Hand to me after this many replies" value={escThreshold} min={1} step={1} onChange={v => { setEscThreshold(v); setDirty(true); }} colors={colors} testId="esc-threshold" />
              <Stepper label="Escalate to a manager after (minutes)" value={escTimeout} min={5} step={5} onChange={v => { setEscTimeout(v); setDirty(true); }} colors={colors} testId="esc-timeout" />
            </View>
          ) : null}
          {workflow?.jessi_mode ? <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Your store's {workflow.label} workflow sets Jessi to "{REPLY_SHORT[workflow.jessi_mode]}" the moment the tag is added. Keep these matched so nothing surprises you.</Text> : null}
        </SheetShell>
      ) : null}

      {sheet === 'delivery' ? (
        <SheetShell title="How do the texts go out?" onClose={() => setSheet(null)} testId="delivery-sheet" colors={colors} footer={<GoldButton label="Done" onPress={() => setSheet(null)} testId="delivery-done" />}>
          <View style={{ gap: 8 }}>
            {DELIVERY_MODES.map(m => <OptionRow key={m.value} label={m.label} sub={m.sub} selected={deliveryMode === m.value} onPress={() => { setDeliveryMode(m.value); setDirty(true); }} testId={`delivery-${m.value}`} colors={colors} />)}
          </View>
        </SheetShell>
      ) : null}

      {sheet === 'trigger' ? (
        <SheetShell title="What starts this plan?" onClose={() => setSheet(null)} testId="trigger-sheet" colors={colors} footer={<GoldButton label="Done" onPress={() => setSheet(null)} testId="trigger-done" />}>
          <Segmented colors={colors} testId="trigger-type" value={triggerType} onChange={v => { setTriggerType(v as any); setDirty(true); }}
            options={[{ value: 'tag', label: 'A tag', icon: 'pricetag' }, { value: 'date', label: 'A date', icon: 'calendar' }]} />
          {triggerType === 'tag' ? (
            <SmartTagPicker tags={tags} selectedTag={triggerTag} onSelect={t => { setTriggerTag(t); setDirty(true); }} onTagCreated={t => setTags(p => [...p, { name: t, color: GOLD }])} userId={user?._id || ''} colors={colors} userRole={user?.role} />
          ) : (
            <View style={{ gap: 8 }}>
              {DATE_TYPES.map(d => <OptionRow key={d.id} label={d.name} sub={d.phrase} selected={dateType === d.id} onPress={() => { setDateType(d.id); setDirty(true); }} testId={`trigger-date-${d.id}`} colors={colors} />)}
            </View>
          )}
        </SheetShell>
      ) : null}

      {sheet === 'rename' ? (
        <SheetShell title="Name this plan" onClose={() => setSheet(null)} testId="rename-sheet" colors={colors} footer={<GoldButton label="Done" onPress={() => setSheet(null)} testId="rename-done" />}>
          <TextInput value={name} onChangeText={mark(setName)} autoFocus placeholder="Sold Follow-Up" placeholderTextColor={colors.textTertiary}
            style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 16, fontWeight: '700', color: colors.text, borderWidth: 1, borderColor: colors.border }} {...tid('rename-input')} />
        </SheetShell>
      ) : null}
    </SafeAreaView>
  );
}

const Stepper = ({ label, value, min, step, onChange, colors, testId }: { label: string; value: number; min: number; step: number; onChange: (v: number) => void; colors: any; testId: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
    <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{label}</Text>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <TouchableOpacity onPress={() => onChange(Math.max(min, value - step))} style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid(`${testId}-minus`)}><Ionicons name="remove" size={16} color={colors.text} /></TouchableOpacity>
      <Text style={{ fontSize: 16, fontWeight: '800', color: GOLD, minWidth: 28, textAlign: 'center' }} {...tid(`${testId}-value`)}>{value}</Text>
      <TouchableOpacity onPress={() => onChange(value + step)} style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid(`${testId}-plus`)}><Ionicons name="add" size={16} color={colors.text} /></TouchableOpacity>
    </View>
  </View>
);
