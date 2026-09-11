import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { showConfirm } from '../../services/alert';
import { ScreenHeader, HeaderTextButton } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText, fmtPhone, RepCard } from '../../components/inbox/ownership';
import { Section, Label, Hint, inputStyle, OptionRows, ColorPicker, MergeChips, MemberPicker, NumberPicker, ROUTING_OPTIONS, AI_MODE_OPTIONS, AFTER_CLOSE_OPTIONS } from '../../components/inbox/InboxEditorParts';

type Tab = 'setup' | 'team' | 'jessi' | 'closing';
const BLANK = { name: '', description: '', phone_number: '', color: '#C9A962', members: [] as string[], member_weights: {} as Record<string, number>, routing: 'jump_ball', daily_cap: 0,
  first_reply: "Thanks for texting {{lead_source}}, {{first_name}}! Someone will be right with you.", ai_mode: 'auto_reply', va_name: '', va_training: '', va_rules: '', va_handoff_rules: '',
  close_tag: 'Sold', after_close: 'move_to_rep', bridge_text: "Hi {first_name}, it's {rep_name}. This is my direct line, save it and text me here anytime." };

export default function InboxEditor() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const isNew = id === 'new';
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [form, setForm] = useState<any>(isNew ? { ...BLANK } : null);
  const [detail, setDetail] = useState<any>(null);
  const [options, setOptions] = useState<RepCard[]>([]);
  const [numbers, setNumbers] = useState<any[]>([]);
  const [tab, setTab] = useState<Tab>('setup');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!user?._id) return;
    const loads: Promise<any>[] = [api.get('/inboxes/members/options'), api.get('/inboxes/numbers', { params: isNew ? {} : { inbox_id: id } }).catch(() => ({ data: { numbers: [] } }))];
    if (!isNew) loads.push(api.get(`/inboxes/${id}`));
    Promise.all(loads).then(([opts, nums, det]) => {
      setOptions(opts.data.users || []);
      setNumbers(nums.data.numbers || []);
      if (det) {
        const d = det.data; setDetail(d);
        setForm({ name: d.name, description: d.description, phone_number: d.phone_number, color: d.color, members: d.members, member_weights: d.member_weights || {}, routing: d.routing, daily_cap: d.daily_cap,
          first_reply: d.first_reply, ai_mode: d.ai_mode, va_name: d.va_name, va_training: d.va_training, va_rules: d.va_rules, va_handoff_rules: d.va_handoff_rules,
          close_tag: d.close_tag, after_close: d.after_close, bridge_text: d.bridge_text });
      }
    }).catch((e: any) => { showToast(errText(e, 'Could not load inbox'), 'error'); if (e?.response?.status === 404) router.back(); });
  }, [id, user?._id]);

  const patch = (p: any) => { setForm((f: any) => ({ ...f, ...p })); setDirty(true); };
  const toggleMember = (uid: string) => patch({ members: form.members.includes(uid) ? form.members.filter((m: string) => m !== uid) : [...form.members, uid] });

  const save = async () => {
    if (!form.name.trim()) { showToast('Give the inbox a name', 'error'); setTab('setup'); return; }
    if (form.members.length === 0) { showToast('Put at least one rep on the inbox', 'error'); setTab('team'); return; }
    setSaving(true);
    try {
      const body = { ...form, daily_cap: Number(form.daily_cap) || 0 };
      const res = isNew ? await api.post('/inboxes', body) : await api.put(`/inboxes/${id}`, body);
      setDirty(false);
      showToast(isNew ? `${res.data.name} inbox created` : 'Inbox saved', 'success');
      if (isNew) router.replace(`/inboxes/${res.data.id}` as any); else setDetail(res.data);
    } catch (e: any) { showToast(errText(e, 'Could not save inbox'), 'error', 3500); }
    finally { setSaving(false); }
  };

  const remove = async (force = false) => {
    try {
      await api.delete(`/inboxes/${id}`, { params: force ? { force: true } : {} });
      showToast('Inbox deleted', 'success'); router.back();
    } catch (e: any) {
      if (e?.response?.status === 409 && !force) {
        showConfirm('Still busy', e.response.data.detail + '\n\nDelete anyway? Reps keep the threads they already own.', () => remove(true), undefined, 'Delete anyway');
      } else showToast(errText(e, 'Could not delete'), 'error');
    }
  };

  if (!form) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Inbox" testID="inbox-editor-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const input = inputStyle(colors);
  const canManage = isNew || detail?.can_manage;
  const noNumberMembers = options.filter(o => form.members.includes(o.id) && !o.has_number);
  const memberOptions: RepCard[] = [...options, ...((detail?.member_details || []) as RepCard[]).filter((m: RepCard) => !options.some(o => o.id === m.id))];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={isNew ? 'New inbox' : form.name || 'Inbox'} subtitle={isNew ? 'A shared number your team works together' : form.phone_number ? fmtPhone(form.phone_number) : 'No number yet'} testID="inbox-editor-header"
        right={canManage ? <HeaderTextButton label={saving ? 'Saving…' : isNew ? 'Create' : 'Save'} onPress={save} disabled={saving} testID="inbox-save" color={dirty || isNew ? GOLD : colors.textSecondary} /> : undefined} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 14 }} keyboardShouldPersistTaps="handled">
          <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
            {([['setup', 'Setup'], ['team', 'Team'], ['jessi', 'Jessi'], ['closing', 'Closing']] as const).map(([k, l]) => (
              <TouchableOpacity key={k} onPress={() => setTab(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center', backgroundColor: tab === k ? GOLD : 'transparent' }} {...tid(`inbox-tab-${k}`)}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: tab === k ? '#111' : colors.textSecondary }}>{l}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {tab === 'setup' && (
            <>
              <Section colors={colors} testId="inbox-section-setup">
                <Label colors={colors}>Inbox name</Label>
                <TextInput value={form.name} onChangeText={v => patch({ name: v })} placeholder="Sales, Service, Parts, BDC…" placeholderTextColor={colors.textSecondary} style={input} {...tid('inbox-name-input')} />
                <Label colors={colors} top>What it's for (optional)</Label>
                <TextInput value={form.description} onChangeText={v => patch({ description: v })} placeholder="One line the team will understand" placeholderTextColor={colors.textSecondary} style={input} {...tid('inbox-description-input')} />
                <Label colors={colors} top>Color</Label>
                <Hint colors={colors}>Shows on every thread from this inbox so reps know which hat they're wearing.</Hint>
                <ColorPicker value={form.color} onChange={c => patch({ color: c })} />
              </Section>
              <Section colors={colors} testId="inbox-section-number">
                <Label colors={colors}>Phone number</Label>
                <Hint colors={colors}>The Twilio number customers text. It can't already be a rep's personal line. Replies always go out from this number while the thread lives here.</Hint>
                <NumberPicker value={form.phone_number} numbers={numbers} onChange={v => patch({ phone_number: v })} colors={colors} fmt={fmtPhone} />
              </Section>
            </>
          )}

          {tab === 'team' && (
            <>
              <Section colors={colors} testId="inbox-section-members">
                <Label colors={colors}>Who works this inbox</Label>
                <Hint colors={colors}>Members see these threads in their Inbox and get pinged on new texts.{noNumberMembers.length ? ` Heads up: ${noNumberMembers.map(m => m.name.split(' ')[0]).join(', ')} ${noNumberMembers.length === 1 ? 'has' : 'have'} no personal number, so their sold threads stay on the shared line.` : ''}</Hint>
                <MemberPicker options={memberOptions} selected={form.members} weights={form.member_weights} weighted={form.routing === 'weighted_round_robin'} onToggle={toggleMember} onWeight={(uid, w) => patch({ member_weights: { ...form.member_weights, [uid]: w } })} colors={colors} />
              </Section>
              <Section colors={colors} testId="inbox-section-routing">
                <Label colors={colors}>When a new customer texts in</Label>
                <OptionRows options={ROUTING_OPTIONS} value={form.routing} onChange={v => patch({ routing: v })} colors={colors} testId="inbox-routing" />
                {form.routing !== 'jump_ball' && (
                  <View style={{ marginTop: 12 }}>
                    <Label colors={colors}>Daily cap per rep (0 = none)</Label>
                    <Hint colors={colors}>Once a rep hits the cap today, new customers skip to the next rep.</Hint>
                    <TextInput value={String(form.daily_cap ?? 0)} onChangeText={v => patch({ daily_cap: v.replace(/\D/g, '') })} keyboardType="number-pad" style={[input, { width: 100 }]} {...tid('inbox-daily-cap')} />
                  </View>
                )}
                <Hint colors={colors}>{'\n'}Known customers of a rep in your store always keep texting that rep's own line, no matter which number they use. Reps can also hand threads to each other from the thread's "Who's on this" sheet.</Hint>
              </Section>
            </>
          )}

          {tab === 'jessi' && (
            <>
              <Section colors={colors} testId="inbox-section-first-reply">
                <Label colors={colors}>Instant first reply</Label>
                <Hint colors={colors}>Sent the moment a brand-new customer texts this number. Blank = nothing automatic.</Hint>
                <MergeChips tokens={['{{first_name}}', '{{lead_source}}']} onInsert={t => patch({ first_reply: (form.first_reply || '') + t })} colors={colors} />
                <TextInput value={form.first_reply} onChangeText={v => patch({ first_reply: v })} multiline style={[input, { minHeight: 80, textAlignVertical: 'top' }]} placeholderTextColor={colors.textSecondary} {...tid('inbox-first-reply')} />
              </Section>
              <Section colors={colors} testId="inbox-section-ai">
                <Label colors={colors}>While nobody has claimed it</Label>
                <OptionRows options={AI_MODE_OPTIONS} value={form.ai_mode} onChange={v => patch({ ai_mode: v })} colors={colors} testId="inbox-ai-mode" />
              </Section>
              {form.ai_mode !== 'off' && (
                <Section colors={colors} testId="inbox-section-va">
                  <Label colors={colors}>Train this inbox's assistant</Label>
                  <Hint colors={colors}>Jessi speaks as the {form.name || 'department'} team, not as one rep, until someone claims. Once a rep owns the thread their own VA takes over.</Hint>
                  <Label colors={colors}>Assistant name (optional)</Label>
                  <TextInput value={form.va_name} onChangeText={v => patch({ va_name: v })} placeholder="Jessi" placeholderTextColor={colors.textSecondary} style={input} {...tid('inbox-va-name')} />
                  <Label colors={colors} top>What she should know</Label>
                  <TextInput value={form.va_training} onChangeText={v => patch({ va_training: v })} multiline placeholder="Hours, what this department handles, common questions and how to answer them…" placeholderTextColor={colors.textSecondary} style={[input, { minHeight: 100, textAlignVertical: 'top' }]} {...tid('inbox-va-training')} />
                  <Label colors={colors} top>Rules she must follow</Label>
                  <TextInput value={form.va_rules} onChangeText={v => patch({ va_rules: v })} multiline placeholder="Never quote prices. Always ask for the year and model…" placeholderTextColor={colors.textSecondary} style={[input, { minHeight: 70, textAlignVertical: 'top' }]} {...tid('inbox-va-rules')} />
                  <Label colors={colors} top>Hand to a human when</Label>
                  <TextInput value={form.va_handoff_rules} onChangeText={v => patch({ va_handoff_rules: v })} multiline placeholder="They ask for a manager, mention a complaint, or want to book…" placeholderTextColor={colors.textSecondary} style={[input, { minHeight: 70, textAlignVertical: 'top' }]} {...tid('inbox-va-handoff')} />
                </Section>
              )}
            </>
          )}

          {tab === 'closing' && (
            <>
              <Section colors={colors} testId="inbox-section-closing">
                <Label colors={colors}>Closing tag</Label>
                <Hint colors={colors}>When a contact from this inbox gets this tag, the thread is done being shared.</Hint>
                <TextInput value={form.close_tag} onChangeText={v => patch({ close_tag: v })} placeholder="Sold" placeholderTextColor={colors.textSecondary} style={[input, { width: 180 }]} {...tid('inbox-close-tag')} />
                <Label colors={colors} top>Then what happens</Label>
                <OptionRows options={AFTER_CLOSE_OPTIONS} value={form.after_close} onChange={v => patch({ after_close: v })} colors={colors} testId="inbox-after-close" />
              </Section>
              {form.after_close === 'move_to_rep' && (
                <Section colors={colors} testId="inbox-section-bridge">
                  <Label colors={colors}>Bridge text from the rep's line</Label>
                  <Hint colors={colors}>The customer's first text from the rep's own number, so they save it.</Hint>
                  <MergeChips tokens={['{first_name}', '{rep_name}', '{inbox_name}']} onInsert={t => patch({ bridge_text: (form.bridge_text || '') + t })} colors={colors} />
                  <TextInput value={form.bridge_text} onChangeText={v => patch({ bridge_text: v })} multiline style={[input, { minHeight: 80, textAlignVertical: 'top' }]} placeholderTextColor={colors.textSecondary} {...tid('inbox-bridge-text')} />
                </Section>
              )}
            </>
          )}

          {canManage && (
            <TouchableOpacity onPress={save} disabled={saving} style={{ height: 52, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: saving ? 0.6 : 1 }} {...tid('inbox-save-bottom')}>
              <Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>{saving ? 'Saving…' : isNew ? 'Create inbox' : 'Save inbox'}</Text>
            </TouchableOpacity>
          )}
          {!isNew && canManage && (
            <TouchableOpacity onPress={() => showConfirm('Delete this inbox?', `Texts to ${fmtPhone(form.phone_number) || 'its number'} will stop landing anywhere until you reassign the number.`, () => remove(false), undefined, 'Delete')}
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12 }} {...tid('inbox-delete-btn')}>
              <Ionicons name="trash-outline" size={16} color="#FF3B30" />
              <Text style={{ fontSize: 14, fontWeight: '700', color: '#FF3B30' }}>Delete inbox</Text>
            </TouchableOpacity>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
