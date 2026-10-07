import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { showConfirm } from '../../services/alert';
import { BasisEditor } from '../../components/appraisal/rules/BasisEditor';
import { TargetGrossSection, ReconSection, MileageSection, AgeSection, ReserveSection, ReviewSection, RangeSection, FollowUpSection } from '../../components/appraisal/rules/RulesSections';
import { FollowUpTasksSection, MoneyInMessagesCard } from '../../components/appraisal/rules/FollowUpTasks';

const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// Dealership appraisal rules: organization default + per-store overrides, versioned. What the engine does with them is spelled out on every card.
export default function AppraisalRulesScreen() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [data, setData] = useState<any | null>(null);
  const [storeId, setStoreId] = useState<string | null>(null);
  const [rules, setRules] = useState<any | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (sid: string | null) => {
    try {
      const d = (await api.get('/appraisals/rules', { params: { store_id: sid || undefined } })).data;
      setData(d); setRules(JSON.parse(JSON.stringify(d.effective.rules))); setDirty(false);
    } catch (e: any) {
      if (e?.response?.status === 403) { showToast(e.response.data?.detail || 'Managers only', 'error', 5000); if (router.canGoBack()) router.back(); else router.replace('/(tabs)/more' as any); return; }
      showToast(errText(e, 'Could not load the rules'), 'error');
    }
  }, []);
  useEffect(() => {
    api.get('/appraisals/rules').then(r => {
      const d = r.data;
      const first = !d.org_editable && d.stores?.[0]?.id ? d.stores[0].id : null;
      setStoreId(first); setData(d); setRules(JSON.parse(JSON.stringify(d.effective.rules)));
      if (first) load(first);
    }).catch((e: any) => {
      if (e?.response?.status === 403) { showToast(e.response.data?.detail || 'Managers only', 'error', 5000); if (router.canGoBack()) router.back(); else router.replace('/(tabs)/more' as any); return; }
      showToast(errText(e, 'Could not load the rules'), 'error');
    });
  }, []);

  const pick = (sid: string | null) => {
    if (sid === storeId) return;
    if (dirty) { showConfirm('Discard unsaved changes?', 'Switching scope drops the edits you have not saved.', () => { setStoreId(sid); load(sid); }, undefined, 'Discard'); return; }
    setStoreId(sid); load(sid);
  };
  const set = (patch: any) => { setRules((r: any) => ({ ...r, ...patch })); setDirty(true); };
  const save = async () => {
    setSaving(true);
    try {
      const body = storeId ? { scope: 'store', store_id: storeId, rules } : { scope: 'org', organization_id: data.organization_id, rules };
      const d = (await api.put('/appraisals/rules', body)).data;
      setData(d); setRules(JSON.parse(JSON.stringify(d.effective.rules))); setDirty(false);
      showToast(`Saved as ${storeId ? 'store override' : 'organization default'} v${(storeId ? d.store : d.org)?.version}. Appraisals already submitted keep the rules they used.`, 'success', 5000);
    } catch (e) { showToast(errText(e, 'Could not save the rules'), 'error', 6000); }
    finally { setSaving(false); }
  };
  const removeOverride = () => showConfirm('Remove this store override?', 'The store goes back to the organization default (or I\u2019m On Social defaults).', async () => {
    try { const d = (await api.delete(`/appraisals/rules/store/${storeId}`)).data; setData(d); setRules(JSON.parse(JSON.stringify(d.effective.rules))); setDirty(false); showToast('Override removed', 'success'); }
    catch (e) { showToast(errText(e, 'Could not remove'), 'error'); }
  }, undefined, 'Remove');
  const setMoney = async (v: boolean) => {
    try {
      const r = (await api.put('/appraisals/org-settings', { allow_trade_values_in_automated_messages: v, organization_id: data?.organization_id })).data;
      setData((d: any) => ({ ...d, org_settings: { ...(d?.org_settings || {}), allow_trade_values_in_automated_messages: r.allow_trade_values_in_automated_messages } }));
      showToast(v ? 'Trade values may now appear in automated messages' : 'Trade values stay out of automated messages', 'success');
    } catch (e) { showToast(errText(e, 'Could not change that setting'), 'error', 5000); }
  };

  if (!data || !rules) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Appraisal Rules" /><ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /></SafeAreaView>;
  const eff = data.effective;
  const doc = storeId ? data.store : data.org;
  const p = { colors, rules, set, options: data.options };
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('appraisal-rules')}>
      <ScreenHeader title="Appraisal Rules" subtitle="How the suggested ACV is built" onBack={() => (router.canGoBack() ? router.back() : router.replace('/(tabs)/more' as any))} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 120, gap: 12 }} keyboardShouldPersistTaps="handled">
          <View style={{ gap: 6 }}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>EDITING</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
              {data.org_editable ? <Scope colors={colors} on={!storeId} label="Organization default" onPress={() => pick(null)} testId="rules-scope-org" /> : null}
              {(data.stores || []).map((s: any) => <Scope key={s.id} colors={colors} on={storeId === s.id} label={s.name} onPress={() => pick(s.id)} testId={`rules-scope-${s.id}`} />)}
            </ScrollView>
          </View>
          <View style={{ borderRadius: 14, padding: 12, backgroundColor: GOLD + '14', borderWidth: 1, borderColor: GOLD + '66', gap: 2 }} {...tid('rules-in-effect')}>
            <Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>{storeId ? 'This store uses: ' : 'In effect: '}{eff.scope_label}{eff.version ? ` v${eff.version}` : ''}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{doc ? `Last saved by ${doc.updated_by_name || 'a manager'} ${when(doc.updated_at)} · ${doc.history_count} earlier version${doc.history_count === 1 ? '' : 's'} kept` : storeId ? 'No override for this store yet. Saving creates one; the organization default stays as the fallback.' : 'No organization default saved yet. Saving creates version 1.'}</Text>
            {storeId && !data.store && eff.source === 'org' ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>You are looking at the organization default. Change anything and save to override it for this store only.</Text> : null}
          </View>
          {data.warnings?.length ? (
            <View style={{ borderRadius: 14, padding: 12, backgroundColor: '#FF950018', borderWidth: 1, borderColor: '#FF950066', gap: 4 }} {...tid('rules-warnings')}>
              {data.warnings.map((w: string, i: number) => <Text key={i} style={{ fontSize: 12.5, color: colors.text, lineHeight: 17 }}>⚠︎ {w}</Text>)}
            </View>
          ) : null}
          <BasisEditor colors={colors} basis={rules.basis} options={data.options.basis} onChange={b => set({ basis: b })} />
          <TargetGrossSection {...p} />
          <ReconSection {...p} />
          <MileageSection {...p} />
          <AgeSection {...p} />
          <ReserveSection {...p} />
          <ReviewSection {...p} />
          <RangeSection {...p} />
          <FollowUpSection {...p} />
          <FollowUpTasksSection colors={colors} rules={rules} set={set} />
          <MoneyInMessagesCard colors={colors} value={!!data.org_settings?.allow_trade_values_in_automated_messages} editable={!!data.org_settings?.editable} onChange={setMoney} mergeFields={data.options?.merge_fields || {}} />
          {storeId && data.store ? (
            <TouchableOpacity onPress={removeOverride} style={{ height: 44, alignItems: 'center', justifyContent: 'center' }} {...tid('rules-remove-override')}>
              <Text style={{ fontSize: 13, fontWeight: '800', color: '#FF3B30' }}>Remove this store's override</Text>
            </TouchableOpacity>
          ) : null}
        </ScrollView>
        <View style={{ position: 'absolute', left: 16, right: 16, bottom: 24 }}>
          <TouchableOpacity onPress={save} disabled={saving || !dirty || !data.can_edit} style={{ height: 54, borderRadius: 16, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: saving || !dirty || !data.can_edit ? 0.5 : 1, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 8, elevation: 4 }} {...tid('rules-save')}>
            {saving ? <ActivityIndicator color="#0B0B0D" /> : <><Ionicons name="save" size={18} color="#0B0B0D" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#0B0B0D' }}>{dirty ? `Save ${storeId ? 'store override' : 'organization default'}` : 'Saved'}</Text></>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const Scope = ({ colors, on, label, onPress, testId }: { colors: any; on: boolean; label: string; onPress: () => void; testId: string }) => (
  <TouchableOpacity onPress={onPress} style={{ height: 34, paddingHorizontal: 12, borderRadius: 17, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD + '22' : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid(testId)}>
    <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{label}</Text>
  </TouchableOpacity>
);
