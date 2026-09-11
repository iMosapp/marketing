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
import { CriteriaEditor } from '../../components/scorecards/CriteriaEditor';
import { GOLD, RED, tid, type Scorecard } from '../../components/scorecards/shared';

type Tab = 'checklist' | 'applies' | 'alerts';
type Opt = { id: string; name: string; sub?: string };

const inputStyle = (colors: any) => ({ backgroundColor: colors.surface, borderRadius: 12, padding: 12, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border } as const);
const labelStyle = (colors: any) => ({ fontSize: 13, fontWeight: '700' as const, color: colors.text, marginBottom: 6 });
const hintStyle = (colors: any) => ({ fontSize: 12, color: colors.textSecondary, marginBottom: 8, lineHeight: 17 });

// Hoisted so TextInputs inside keep focus across re-renders.
const Section = ({ children, colors }: { children: React.ReactNode; colors: any }) => <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 4 }}>{children}</View>;
const Toggle = ({ title, sub, value, onChange, testID, color = GOLD, colors }: { title: string; sub?: string; value: boolean; onChange: (v: boolean) => void; testID: string; color?: string; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8, gap: 12 }}>
    <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{title}</Text>{sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{sub}</Text> : null}</View>
    <Switch value={value} onValueChange={onChange} trackColor={{ true: color }} {...tid(testID)} />
  </View>
);
const Chips = ({ items, key_, empty, prefix, card, onToggle, colors }: { items: Opt[]; key_: 'user_ids' | 'inbox_ids' | 'source_ids'; empty: string; prefix: string; card: Scorecard; onToggle: (k: 'user_ids' | 'inbox_ids' | 'source_ids', v: string) => void; colors: any }) => (
  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
    {items.length === 0 && <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' }}>{empty}</Text>}
    {items.map(o => {
      const on = card.applies_to[key_].includes(o.id);
      return (
        <TouchableOpacity key={o.id} onPress={() => onToggle(key_, o.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, backgroundColor: on ? GOLD + '22' : colors.surface, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`${prefix}-${o.id}`)}>
          {on && <Ionicons name="checkmark" size={13} color={GOLD} />}
          <Text style={{ fontSize: 13, color: colors.text, fontWeight: on ? '700' : '500' }}>{o.name}</Text>
          {o.sub ? <Text style={{ fontSize: 10, color: colors.textSecondary }}>{o.sub}</Text> : null}
        </TouchableOpacity>
      );
    })}
  </View>
);

export default function ScorecardEditor() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [card, setCard] = useState<Scorecard | null>(null);
  const [reps, setReps] = useState<Opt[]>([]);
  const [inboxes, setInboxes] = useState<Opt[]>([]);
  const [sources, setSources] = useState<Opt[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [tab, setTab] = useState<Tab>('checklist');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [threshold, setThreshold] = useState('');

  useEffect(() => {
    if (!id || !user?._id) return;
    Promise.all([api.get(`/scorecards/${id}`), api.get('/scorecards')]).then(([c, lib]) => {
      setCard(c.data); setThreshold(c.data.alert_below_pct == null ? '' : String(c.data.alert_below_pct));
      setReps((c.data.reps || []).filter((r: any) => r.role !== 'super_admin' || r._id === user._id).map((r: any) => ({ id: r._id, name: r.name || r.email, sub: r.role === 'user' ? undefined : r.role.replace('_', ' ') })));
      setInboxes((c.data.inboxes || []).map((i: any) => ({ id: i.id, name: i.name })));
      setSources((c.data.sources || []).map((s: any) => ({ id: s.id, name: s.name })));
      setDepartments(lib.data.departments || []);
    }).catch((e: any) => showToast(e?.response?.data?.detail || 'Could not load scorecard', 'error'));
  }, [id, user?._id]);

  const patch = (p: Partial<Scorecard>) => { setCard(c => (c ? { ...c, ...p } : c)); setDirty(true); };
  const toggleApply = (key: 'user_ids' | 'inbox_ids' | 'source_ids', v: string) => {
    if (!card) return;
    const cur = card.applies_to[key];
    patch({ applies_to: { ...card.applies_to, [key]: cur.includes(v) ? cur.filter(x => x !== v) : [...cur, v] } });
  };

  const save = async () => {
    if (!card) return;
    if (!card.name.trim()) { showToast('Give the scorecard a name', 'error'); return; }
    const criteria = card.criteria.filter(c => c.text.trim());
    if (!criteria.length) { showToast('Add at least one criterion', 'error'); setTab('checklist'); return; }
    setSaving(true);
    try {
      const t = threshold.trim() === '' ? null : Math.max(0, Math.min(100, parseInt(threshold, 10) || 0));
      const body: any = { name: card.name, department: card.department, description: card.description, criteria, applies_to: card.applies_to, is_default: card.is_default,
        alert_on_critical: card.alert_on_critical, notify_rep: card.notify_rep, ...(t == null ? { clear_alert_below: true } : { alert_below_pct: t }) };
      const res = await api.put(`/scorecards/${card.id}`, body);
      setCard(c => ({ ...c!, ...res.data })); setDirty(false); showToast('Scorecard saved', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setSaving(false); }
  };

  if (!card) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Scorecard" testID="scorecard-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;

  const input = inputStyle(colors);
  const label = labelStyle(colors);
  const hint = hintStyle(colors);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={card.name || 'Scorecard'} subtitle={`${card.criteria.length} criteria · ${card.criteria.filter(c => c.critical).length} critical`} testID="scorecard-header"
        right={<HeaderTextButton label={saving ? 'Saving…' : 'Save'} onPress={save} disabled={saving} testID="scorecard-save" color={dirty ? GOLD : colors.textSecondary} />} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 14 }} keyboardShouldPersistTaps="handled">
          <Section colors={colors}>
            <Text style={label}>Scorecard name</Text>
            <TextInput value={card.name} onChangeText={v => patch({ name: v })} placeholder="e.g. Internet Sales Call" placeholderTextColor={colors.textSecondary} style={input} {...tid('scorecard-name')} />
            <Text style={[label, { marginTop: 10 }]}>Department</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
              {departments.map(d => (
                <TouchableOpacity key={d} onPress={() => patch({ department: d })} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, backgroundColor: card.department === d ? GOLD : colors.surface, borderWidth: 1, borderColor: card.department === d ? GOLD : colors.border }} {...tid(`scorecard-dept-${d.replace(/\s+/g, '-').toLowerCase()}`)}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: card.department === d ? '#111' : colors.text }}>{d}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput value={card.department} onChangeText={v => patch({ department: v })} placeholder="Or type your own" placeholderTextColor={colors.textSecondary} style={input} {...tid('scorecard-department')} />
            <Text style={[label, { marginTop: 10 }]}>What it's for (optional)</Text>
            <TextInput value={card.description} onChangeText={v => patch({ description: v })} placeholder="One line your managers will understand" placeholderTextColor={colors.textSecondary} style={input} {...tid('scorecard-description')} />
          </Section>

          <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
            {([['checklist', 'Checklist'], ['applies', 'Who it grades'], ['alerts', 'Alerts']] as const).map(([k, l]) => (
              <TouchableOpacity key={k} onPress={() => setTab(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center', backgroundColor: tab === k ? GOLD : 'transparent' }} {...tid(`scorecard-tab-${k}`)}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: tab === k ? '#111' : colors.textSecondary }}>{l}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {tab === 'checklist' && (
            <Section colors={colors}>
              <Text style={label}>What Jessi checks on every call</Text>
              <Text style={hint}>Write each item as something the rep should do. Weight makes an item count more toward the score. Critical items alert the managers when missed.</Text>
              <CriteriaEditor criteria={card.criteria} onChange={c => patch({ criteria: c })} colors={colors} />
            </Section>
          )}

          {tab === 'applies' && (
            <>
              <Section colors={colors}>
                <Toggle colors={colors} title="Default for the whole store" sub="Grades any recorded call that no other scorecard claims." value={card.is_default} onChange={v => patch({ is_default: v })} testID="scorecard-default" />
              </Section>
              <Section colors={colors}>
                <Text style={label}>Shared inboxes</Text>
                <Text style={hint}>Calls worked from these department numbers use this card first.</Text>
                <Chips colors={colors} card={card} onToggle={toggleApply} items={inboxes} key_="inbox_ids" empty="No shared inboxes on this store yet." prefix="scorecard-inbox" />
              </Section>
              <Section colors={colors}>
                <Text style={label}>Reps</Text>
                <Text style={hint}>Every recorded call these reps make or take.</Text>
                <Chips colors={colors} card={card} onToggle={toggleApply} items={reps} key_="user_ids" empty="No reps on this store yet." prefix="scorecard-rep" />
              </Section>
              <Section colors={colors}>
                <Text style={label}>Lead sources</Text>
                <Text style={hint}>Calls on threads that came in from these sources.</Text>
                <Chips colors={colors} card={card} onToggle={toggleApply} items={sources} key_="source_ids" empty="No lead sources on this store yet." prefix="scorecard-source" />
              </Section>
            </>
          )}

          {tab === 'alerts' && (
            <>
              <Section colors={colors}>
                <Toggle colors={colors} title="Alert managers on a critical miss" sub="Push + notification to the store's managers the minute a critical item is missed." value={card.alert_on_critical} onChange={v => patch({ alert_on_critical: v })} testID="scorecard-alert-critical" color={RED} />
                <Text style={[label, { marginTop: 8 }]}>Also alert when the score is below</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <TextInput value={threshold} onChangeText={v => { setThreshold(v.replace(/[^0-9]/g, '').slice(0, 3)); setDirty(true); }} keyboardType="number-pad" placeholder="off" placeholderTextColor={colors.textSecondary} style={[input, { width: 90, textAlign: 'center' }]} {...tid('scorecard-threshold')} />
                  <Text style={{ fontSize: 14, color: colors.textSecondary }}>% (blank = off)</Text>
                </View>
              </Section>
              <Section colors={colors}>
                <Toggle colors={colors} title="Tell the rep their score" sub="The rep gets a notification with the score and the top coaching tip after each graded call." value={card.notify_rep} onChange={v => patch({ notify_rep: v })} testID="scorecard-notify-rep" />
              </Section>
              <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17, paddingHorizontal: 4 }}>Managers can mute alerts for any single rep from that rep's Call Scores page. Pushes hold overnight (before 8 AM / after 9 PM) but the alert still lands in the bell.</Text>
            </>
          )}

          <TouchableOpacity onPress={save} disabled={saving} style={{ height: 52, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: saving ? 0.6 : 1 }} {...tid('scorecard-save-bottom')}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>{saving ? 'Saving…' : 'Save scorecard'}</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
