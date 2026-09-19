/**
 * One store's texting compliance: status timeline (Business profile → A2P → Brand → Campaign, Caller ID alongside), the
 * business / representative / campaign / Caller ID forms, the numbers it covers, and Save · Submit · Check now · Reset.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, TextInput, Switch, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useAuthStore } from '../../../store/authStore';
import { ScreenHeader } from '../../../components/common/ScreenHeader';
import api from '../../../services/api';
import { showSimpleAlert, showConfirm } from '../../../services/alert';

const GOLD = '#C9A962';
const STEPS = [
  { key: 'profile', label: 'Business profile', hint: 'Legal name, EIN, address, authorized rep' },
  { key: 'a2p', label: 'A2P profile', hint: 'Messaging profile on top of the business' },
  { key: 'brand', label: 'Brand', hint: 'TCR brand registration (fee applies live)' },
  { key: 'campaign', label: 'Campaign', hint: 'Use case, samples, opt-in; numbers attached' },
];

function Field({ label, value, onChange, colors, s, testid, multiline, placeholder, keyboardType, hint, secure }: any) {
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={s.label}>{label}</Text>
      <TextInput value={value ?? ''} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.textTertiary} multiline={multiline} keyboardType={keyboardType} autoCapitalize="none" secureTextEntry={secure}
        style={[s.input, multiline && { minHeight: 84, textAlignVertical: 'top' }]} testID={testid} dataSet={{ testid } as any} />
      {hint ? <Text style={s.hint}>{hint}</Text> : null}
    </View>
  );
}

function Chips({ label, value, options, onChange, colors, s, testid }: any) {
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={s.label}>{label}</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {options.map((o: any) => {
          const key = typeof o === 'string' ? o : o.key;
          const text = typeof o === 'string' ? o : o.label;
          const on = value === key;
          return (
            <TouchableOpacity key={key} onPress={() => onChange(key)} style={{ paddingHorizontal: 11, paddingVertical: 7, borderRadius: 14, backgroundColor: on ? GOLD : colors.bg, borderWidth: 1, borderColor: on ? GOLD : colors.border }}
              testID={`${testid}-${key}`} dataSet={{ testid: `${testid}-${key}` } as any}>
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? '#000' : colors.text }}>{text}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

export default function StoreCompliance() {
  const { storeId } = useLocalSearchParams<{ storeId: string }>();
  const { colors } = useThemeStore();
  const user = useAuthStore((st) => st.user);
  const router = useRouter();
  const s = getS(colors);
  const [data, setData] = useState<any>(null);
  const [opts, setOpts] = useState<any>(null);
  const [rec, setRec] = useState<any>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const isSuper = user?.role === 'super_admin';

  const load = useCallback(async () => {
    try {
      const [r, o] = await Promise.all([api.get(`/admin/compliance/${storeId}`), api.get('/admin/compliance/options')]);
      setData(r.data);
      setRec(r.data.record);
      setOpts(o.data);
    } catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not load this store.'); }
  }, [storeId]);
  useEffect(() => { load(); }, [load]);

  const set = (block: string, key: string, v: any) => setRec((r: any) => ({ ...r, [block]: { ...(r[block] || {}), [key]: v } }));
  const setSample = (i: number, v: string) => setRec((r: any) => { const samples = [...(r.campaign?.samples || [])]; samples[i] = v; return { ...r, campaign: { ...r.campaign, samples } }; });

  const save = async (): Promise<boolean> => {
    setBusy('save');
    try {
      const r = await api.put(`/admin/compliance/${storeId}`, { business: rec.business, rep: rec.rep, campaign: rec.campaign, cnam: rec.cnam });
      setRec((cur: any) => ({ ...cur, ...r.data.record, business: { ...r.data.record.business, ein: '' } }));
      setData((d: any) => ({ ...d, missing: r.data.missing }));
      return true;
    } catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not save.'); return false; }
    finally { setBusy(null); }
  };

  const act = async (what: 'submit' | 'check' | 'reset') => {
    if (what === 'submit' && !(await save())) return;
    if (what === 'reset') {
      const ok = await showConfirm('Reset registration?', 'Back to draft. Form data is kept; Twilio resources are left untouched.');
      if (!ok) return;
    }
    setBusy(what);
    try {
      await api.post(`/admin/compliance/${storeId}/${what}`);
      await load();
    } catch (e: any) { showSimpleAlert(what === 'submit' ? 'Not submitted' : 'Error', e?.response?.data?.detail || 'Something went wrong.'); }
    finally { setBusy(null); }
  };

  if (!data || !rec || !opts) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <ScreenHeader title="Texting Compliance" testID="store-compliance-header" />
        <ActivityIndicator size="large" color={GOLD} style={{ marginTop: 80 }} />
      </SafeAreaView>
    );
  }
  const summ = data.summary || {};
  const stage: string = rec.stage || 'draft';
  const status: string = rec.status || 'not_started';
  const stageIdx = STEPS.findIndex(x => x.key === stage);
  const inReview = !['draft', 'complete'].includes(stage) && !['rejected', 'error'].includes(status);
  const missing: string[] = data.missing || [];
  const cnamStatus = rec.statuses?.cnam;
  const b = rec.business || {}, rp = rec.rep || {}, c = rec.campaign || {}, cn = rec.cnam || {};
  const modeLabel = (data.settings?.mode || 'dry_run').replace('_', ' ');

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScreenHeader title={data.store?.name || 'Store'} subtitle={`Texting compliance · ${modeLabel}`} testID="store-compliance-header" />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }} keyboardShouldPersistTaps="handled">
          {/* Timeline */}
          <View style={s.card} testID="compliance-timeline">
            {STEPS.map((step, i) => {
              const done = stage === 'complete' || i < stageIdx;
              const current = i === stageIdx && stage !== 'complete';
              const bad = current && ['rejected', 'error'].includes(status);
              const color = bad ? '#FF3B30' : done ? '#34C759' : current ? '#FF9500' : colors.textTertiary;
              return (
                <View key={step.key} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 6 }} testID={`compliance-step-${step.key}`} dataSet={{ testid: `compliance-step-${step.key}`, state: bad ? 'bad' : done ? 'done' : current ? 'current' : 'todo' } as any}>
                  <Ionicons name={bad ? 'close-circle' : done ? 'checkmark-circle' : current ? 'time' : 'ellipse-outline'} size={18} color={color} style={{ marginTop: 1 }} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 14, fontWeight: '700', color: done || current ? colors.text : colors.textSecondary }}>{step.label}{current ? ` · ${status}` : ''}</Text>
                    <Text style={{ fontSize: 12, color: colors.textTertiary }}>{step.hint}{rec.statuses?.[step.key === 'profile' ? 'customer_profile' : step.key === 'a2p' ? 'a2p_product' : step.key] ? ` · Twilio: ${rec.statuses[step.key === 'profile' ? 'customer_profile' : step.key === 'a2p' ? 'a2p_product' : step.key]}` : ''}</Text>
                  </View>
                </View>
              );
            })}
            <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.border, marginTop: 4 }} testID="compliance-step-cnam" dataSet={{ testid: 'compliance-step-cnam' } as any}>
              <Ionicons name={cnamStatus === 'twilio-approved' ? 'checkmark-circle' : cnamStatus ? 'time' : 'ellipse-outline'} size={18} color={cnamStatus === 'twilio-approved' ? '#34C759' : cnamStatus ? '#FF9500' : colors.textTertiary} style={{ marginTop: 1 }} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Caller ID name{cn.enabled === false ? ' · off' : cn.display_name ? ` · ${cn.display_name}` : ''}</Text>
                <Text style={{ fontSize: 12, color: colors.textTertiary }}>{cnamStatus ? `Twilio: ${cnamStatus}` : 'Goes in once the business profile is approved. Voice only, optional.'}</Text>
              </View>
            </View>
            {!!rec.error && (
              <View style={{ marginTop: 10, backgroundColor: '#FF3B3015', borderRadius: 10, padding: 10, flexDirection: 'row', gap: 8 }} testID="compliance-error" dataSet={{ testid: 'compliance-error' } as any}>
                <Ionicons name="alert-circle" size={16} color="#FF3B30" />
                <Text style={{ flex: 1, fontSize: 13, color: '#FF3B30', lineHeight: 18 }}>{rec.error}</Text>
              </View>
            )}
            {inReview && (
              <Text style={{ marginTop: 10, fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }} testID="compliance-in-review-note">
                In Twilio's hands. We check every 10 minutes; edits you make now are kept for a resubmit.{summ.last_checked_at ? ` Last check ${new Date(summ.last_checked_at).toLocaleString()}.` : ''}
              </Text>
            )}
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 12 }}>
              <TouchableOpacity onPress={() => act('submit')} disabled={!!busy || inReview || stage === 'complete'} style={[s.btn, { backgroundColor: GOLD, opacity: inReview || stage === 'complete' ? 0.4 : 1 }]} testID="compliance-submit-btn" dataSet={{ testid: 'compliance-submit-btn' } as any}>
                {busy === 'submit' ? <ActivityIndicator color="#000" /> : <Text style={s.btnText}>{['rejected', 'error'].includes(status) ? 'Fix & resubmit' : 'Submit to Twilio'}</Text>}
              </TouchableOpacity>
              {stage !== 'draft' && (
                <TouchableOpacity onPress={() => act('check')} disabled={!!busy} style={[s.btn, { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }]} testID="compliance-check-btn" dataSet={{ testid: 'compliance-check-btn' } as any}>
                  {busy === 'check' ? <ActivityIndicator color={colors.text} /> : <Text style={[s.btnText, { color: colors.text }]}>Check now</Text>}
                </TouchableOpacity>
              )}
              {isSuper && stage !== 'draft' && (
                <TouchableOpacity onPress={() => act('reset')} disabled={!!busy} style={[s.btn, { flex: 0, paddingHorizontal: 12, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }]} testID="compliance-reset-btn" dataSet={{ testid: 'compliance-reset-btn' } as any}>
                  <Ionicons name="refresh" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
            </View>
            {missing.length > 0 && stage === 'draft' && (
              <Text style={{ marginTop: 8, fontSize: 12, color: '#FF9500' }} testID="compliance-missing">Still needed: {missing.map(m => m.replace('.', ' → ').replace(/_/g, ' ')).join(', ')}</Text>
            )}
          </View>

          {/* Numbers */}
          <View style={s.card} testID="compliance-numbers">
            <Text style={s.cardTitle}>Numbers covered ({(rec.numbers || []).length})</Text>
            {(rec.numbers || []).length === 0 && <Text style={s.hint}>No rep on this store has a Twilio number yet. Numbers bought later are attached automatically.</Text>}
            {(rec.numbers || []).map((n: any) => (
              <Text key={n.sid} style={{ fontSize: 13, color: colors.text, paddingVertical: 3 }}>{n.number} <Text style={{ color: colors.textTertiary }}>· {n.owner || 'pool'}</Text></Text>
            ))}
          </View>

          {/* Business */}
          <View style={s.card} testID="compliance-business">
            <Text style={s.cardTitle}>Business (as filed with the IRS)</Text>
            <Field label="Legal business name" value={b.legal_name} onChange={(v: string) => set('business', 'legal_name', v)} colors={colors} s={s} testid="cf-legal-name" />
            <Field label={`EIN${b.has_ein ? ` · on file ${b.ein_masked}` : ''}`} value={b.ein} onChange={(v: string) => set('business', 'ein', v)} colors={colors} s={s} testid="cf-ein" placeholder={b.has_ein ? 'Leave blank to keep the one on file' : '12-3456789'} keyboardType="numbers-and-punctuation" hint="Must match the IRS letter exactly; most rejections are an EIN / legal name mismatch." />
            <Chips label="Business type" value={b.business_type} options={opts.business_types} onChange={(v: string) => set('business', 'business_type', v)} colors={colors} s={s} testid="cf-business-type" />
            <Chips label="Company type" value={b.company_type || 'private'} options={[{ key: 'private', label: 'Private' }, { key: 'public', label: 'Public' }, { key: 'non-profit', label: 'Non-profit' }]} onChange={(v: string) => set('business', 'company_type', v)} colors={colors} s={s} testid="cf-company-type" />
            <Field label="Website" value={b.website} onChange={(v: string) => set('business', 'website', v)} colors={colors} s={s} testid="cf-website" placeholder="https://" />
            <Field label="Street" value={b.street} onChange={(v: string) => set('business', 'street', v)} colors={colors} s={s} testid="cf-street" />
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 2 }}><Field label="City" value={b.city} onChange={(v: string) => set('business', 'city', v)} colors={colors} s={s} testid="cf-city" /></View>
              <View style={{ flex: 1 }}><Field label="State" value={b.state} onChange={(v: string) => set('business', 'state', v)} colors={colors} s={s} testid="cf-state" placeholder="UT" /></View>
              <View style={{ flex: 1 }}><Field label="ZIP" value={b.postal_code} onChange={(v: string) => set('business', 'postal_code', v)} colors={colors} s={s} testid="cf-zip" /></View>
            </View>
          </View>

          {/* Authorized representative */}
          <View style={s.card} testID="compliance-rep">
            <Text style={s.cardTitle}>Authorized representative</Text>
            <Text style={[s.hint, { marginBottom: 10 }]}>Someone at the dealership who can vouch for the registration (GM, owner, controller). Twilio may email them.</Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1 }}><Field label="First name" value={rp.first_name} onChange={(v: string) => set('rep', 'first_name', v)} colors={colors} s={s} testid="cf-rep-first" /></View>
              <View style={{ flex: 1 }}><Field label="Last name" value={rp.last_name} onChange={(v: string) => set('rep', 'last_name', v)} colors={colors} s={s} testid="cf-rep-last" /></View>
            </View>
            <Field label="Email" value={rp.email} onChange={(v: string) => set('rep', 'email', v)} colors={colors} s={s} testid="cf-rep-email" keyboardType="email-address" />
            <Field label="Phone" value={rp.phone} onChange={(v: string) => set('rep', 'phone', v)} colors={colors} s={s} testid="cf-rep-phone" keyboardType="phone-pad" placeholder="+1 801 555 0100" />
            <Field label="Title" value={rp.title} onChange={(v: string) => set('rep', 'title', v)} colors={colors} s={s} testid="cf-rep-title" placeholder="General Manager" />
            <Chips label="Position" value={rp.job_position} options={opts.job_positions} onChange={(v: string) => set('rep', 'job_position', v)} colors={colors} s={s} testid="cf-rep-position" />
          </View>

          {/* Campaign */}
          <View style={s.card} testID="compliance-campaign">
            <Text style={s.cardTitle}>Campaign (what the reps text)</Text>
            <Chips label="Use case" value={c.use_case} options={Object.entries(opts.use_cases || {}).map(([k, v]) => ({ key: k, label: String(v).split(' (')[0] }))} onChange={(v: string) => set('campaign', 'use_case', v)} colors={colors} s={s} testid="cf-use-case" />
            <Text style={[s.hint, { marginTop: -6, marginBottom: 12 }]}>{opts.use_cases?.[c.use_case]}</Text>
            <Field label="Description" value={c.description} onChange={(v: string) => set('campaign', 'description', v)} colors={colors} s={s} testid="cf-description" multiline />
            <Field label="How customers opt in (message flow)" value={c.message_flow} onChange={(v: string) => set('campaign', 'message_flow', v)} colors={colors} s={s} testid="cf-message-flow" multiline />
            {[0, 1, 2].map(i => (
              <Field key={i} label={`Sample message ${i + 1}${i > 1 ? ' (optional)' : ''}`} value={c.samples?.[i] || ''} onChange={(v: string) => setSample(i, v)} colors={colors} s={s} testid={`cf-sample-${i}`} multiline hint={i === 0 ? 'Name the dealership, keep it real, end with STOP instructions.' : undefined} />
            ))}
            <Field label="Privacy policy URL" value={c.privacy_url} onChange={(v: string) => set('campaign', 'privacy_url', v)} colors={colors} s={s} testid="cf-privacy-url" placeholder="https://dealer.com/privacy" />
            <Field label="Terms URL" value={c.terms_url} onChange={(v: string) => set('campaign', 'terms_url', v)} colors={colors} s={s} testid="cf-terms-url" placeholder="https://dealer.com/terms" hint="Both pages must be public and mention texting." />
            <Field label="Opt-in confirmation text" value={c.opt_in_message} onChange={(v: string) => set('campaign', 'opt_in_message', v)} colors={colors} s={s} testid="cf-opt-in" multiline />
            <Field label="Opt-out (STOP) reply" value={c.opt_out_message} onChange={(v: string) => set('campaign', 'opt_out_message', v)} colors={colors} s={s} testid="cf-opt-out" multiline />
            <Field label="HELP reply" value={c.help_message} onChange={(v: string) => set('campaign', 'help_message', v)} colors={colors} s={s} testid="cf-help" multiline />
          </View>

          {/* Caller ID */}
          <View style={s.card} testID="compliance-cnam">
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>Caller ID name (CNAM)</Text>
              <Switch value={cn.enabled !== false} onValueChange={(v: boolean) => set('cnam', 'enabled', v)} trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }} thumbColor={cn.enabled !== false ? '#34C759' : '#f4f3f4'} testID="cf-cnam-enabled" dataSet={{ testid: 'cf-cnam-enabled' } as any} />
            </View>
            <Text style={[s.hint, { marginVertical: 8 }]}>What shows on the customer's phone when a rep calls. 15 characters, letters and numbers, shown in caps. US local numbers only; mobile carriers show it when they choose to.</Text>
            {cn.enabled !== false && (
              <Field label="Display name" value={cn.display_name} onChange={(v: string) => set('cnam', 'display_name', v.toUpperCase().slice(0, 15))} colors={colors} s={s} testid="cf-cnam-name" placeholder="SMITH HARLEY" />
            )}
          </View>

          <TouchableOpacity onPress={save} disabled={!!busy} style={[s.btn, { backgroundColor: GOLD, marginBottom: 12 }]} testID="compliance-save-btn" dataSet={{ testid: 'compliance-save-btn' } as any}>
            {busy === 'save' ? <ActivityIndicator color="#000" /> : <Text style={s.btnText}>Save</Text>}
          </TouchableOpacity>

          {(rec.history || []).length > 0 && (
            <View style={s.card}>
              <TouchableOpacity onPress={() => setShowHistory(v => !v)} style={{ flexDirection: 'row', alignItems: 'center' }} testID="compliance-history-toggle" dataSet={{ testid: 'compliance-history-toggle' } as any}>
                <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>History ({rec.history.length})</Text>
                <Ionicons name={showHistory ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
              </TouchableOpacity>
              {showHistory && [...rec.history].reverse().map((h: any, i: number) => (
                <Text key={i} style={{ fontSize: 12, color: colors.textSecondary, paddingTop: 6 }}>{new Date(h.at).toLocaleString()} · {h.stage} · {h.status}{h.note ? ` · ${h.note}` : ''}</Text>
              ))}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 14 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 10 },
  label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.6, color: colors.textSecondary, marginBottom: 6, textTransform: 'uppercase' },
  hint: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginTop: 4 },
  input: { backgroundColor: colors.bg, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  btn: { flex: 1, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  btnText: { fontSize: 15, fontWeight: '800', color: '#000' },
});
