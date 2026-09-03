/**
 * Call Retry Cadence — per-rep timing for the "try them again" tasks Jessi creates after voicemail / no answer.
 * Live preview shows exactly what a miss right now would schedule.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Switch, StyleSheet, ActivityIndicator, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import api from '../../services/api';

const GOLD = '#C9A962';
const AMBER = '#FF9F0A';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Cadence = { enabled: boolean; first_minutes: number; second_hours: number; morning_hour: number; fourth_days: number; evening_cutoff: number; max_auto: number; just_tried_text?: string };
const DEFAULT_JUST_TRIED = "Hey {first_name}, it's {sender_name}. Just tried to give you a call, no rush at all. Call or text me back whenever works for you.";
const DEFAULTS: Cadence = { enabled: true, first_minutes: 30, second_hours: 3, morning_hour: 10, fourth_days: 2, evening_cutoff: 19, max_auto: 4 };

const hour12 = (h: number) => `${h % 12 || 12} ${h >= 12 ? 'PM' : 'AM'}`;

function Stepper({ label, hint, value, display, min, max, step = 1, onChange, colors, testid }: any) {
  const bump = (d: number) => onChange(Math.max(min, Math.min(max, value + d)));
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, gap: 10 }} {...tid(testid)}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{label}</Text>
        {hint ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{hint}</Text> : null}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border }}>
        <TouchableOpacity onPress={() => bump(-step)} disabled={value <= min} style={{ paddingHorizontal: 12, paddingVertical: 8, opacity: value <= min ? 0.35 : 1 }} {...tid(`${testid}-minus`)}>
          <Ionicons name="remove" size={18} color={GOLD} />
        </TouchableOpacity>
        <Text style={{ minWidth: 78, textAlign: 'center', fontSize: 14, fontWeight: '800', color: colors.text }} {...tid(`${testid}-value`)}>{display(value)}</Text>
        <TouchableOpacity onPress={() => bump(step)} disabled={value >= max} style={{ paddingHorizontal: 12, paddingVertical: 8, opacity: value >= max ? 0.35 : 1 }} {...tid(`${testid}-plus`)}>
          <Ionicons name="add" size={18} color={GOLD} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

export default function CallRetriesPage() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const router = useRouter();
  const { scope } = useLocalSearchParams<{ scope?: string }>();
  const storeMode = scope === 'store';
  const s = getStyles(colors);
  const [cadence, setCadence] = useState<Cadence>(DEFAULTS);
  const [preview, setPreview] = useState<any[]>([]);
  const [meta, setMeta] = useState<any>({});
  const [applyToAll, setApplyToAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = () => {
    if (!user?._id) return;
    api.get(`/calls/${user._id}/retry-cadence${storeMode ? '/store' : ''}`)
      .then(r => { setCadence({ ...DEFAULTS, ...r.data.cadence }); setPreview(r.data.preview || []); setMeta(r.data); })
      .catch((e: any) => showToast(e?.response?.data?.detail || 'Could not load', 'error'))
      .finally(() => setLoading(false));
  };
  useEffect(load, [user?._id, storeMode]);

  const patch = (p: Partial<Cadence>) => { setCadence(c => ({ ...c, ...p })); setDirty(true); };

  const save = async () => {
    if (!user?._id) return;
    setSaving(true);
    try {
      const r = storeMode
        ? await api.put(`/calls/${user._id}/retry-cadence/store`, { ...cadence, apply_to_all: applyToAll })
        : await api.put(`/calls/${user._id}/retry-cadence`, cadence);
      setCadence({ ...DEFAULTS, ...r.data.cadence });
      setPreview(r.data.preview || []);
      setDirty(false);
      if (storeMode) {
        showToast(applyToAll && r.data.overrides_cleared ? `Team default saved · ${r.data.overrides_cleared} rep${r.data.overrides_cleared === 1 ? '' : 's'} reset to it` : 'Team default saved', 'success');
        setApplyToAll(false);
        load();
      } else {
        setMeta((m: any) => ({ ...m, source: 'personal' }));
        showToast('Retry timing saved', 'success');
      }
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); } finally { setSaving(false); }
  };

  const useTeamDefault = async () => {
    if (!user?._id) return;
    setSaving(true);
    try {
      const r = await api.delete(`/calls/${user._id}/retry-cadence`);
      setCadence({ ...DEFAULTS, ...r.data.cadence }); setPreview(r.data.preview || []); setMeta((m: any) => ({ ...m, ...r.data })); setDirty(false);
      showToast('Back on the team default', 'success');
    } catch { showToast('Could not reset', 'error'); } finally { setSaving(false); }
  };

  const inheritedLabel = meta.source === 'store' ? "your store's default" : meta.source === 'global' ? 'the company default' : meta.source === 'default' ? 'the built-in default' : '';

  const localPreview = () => {
    // client-side echo so the numbers move as you tap; server preview replaces it on save
    const now = new Date();
    const fmt = (d: Date) => {
      const sameDay = d.toDateString() === now.toDateString();
      const tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1);
      const t = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      return sameDay ? `today ${t}` : d.toDateString() === tomorrow.toDateString() ? `tomorrow ${t}` : `${d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })} ${t}`;
    };
    const morning = (from: Date) => { const d = new Date(from); d.setDate(d.getDate() + 1); d.setHours(cadence.morning_hour, 0, 0, 0); while (d.getDay() === 0) d.setDate(d.getDate() + 1); return d; };
    const rows: { attempt: number; final: boolean; label: string }[] = [];
    for (let a = 1; a <= cadence.max_auto + 1; a++) {
      let d: Date;
      if (a > cadence.max_auto) d = morning(now);
      else if (a === 1) { d = new Date(now.getTime() + cadence.first_minutes * 60000); if (d.getHours() >= cadence.evening_cutoff + 1 || d.getHours() < 8) d = morning(now); }
      else if (a === 2) { d = new Date(now.getTime() + cadence.second_hours * 3600000); if (d.getHours() >= cadence.evening_cutoff || d.getHours() < 8) d = morning(now); }
      else if (a === 3) d = morning(now);
      else { d = new Date(now); d.setDate(d.getDate() + cadence.fourth_days); d.setHours(cadence.morning_hour, 0, 0, 0); while (d.getDay() === 0) d.setDate(d.getDate() + 1); }
      rows.push({ attempt: a, final: a > cadence.max_auto, label: fmt(d) });
    }
    return rows;
  };
  const rows = dirty ? localPreview() : preview;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.back} {...tid('call-retries-back')}>
          <Ionicons name="chevron-back" size={28} color={colors.accent} />
        </TouchableOpacity>
        <Text style={s.title}>{storeMode ? 'Team Call Retries' : 'Call Retries'}</Text>
        <TouchableOpacity onPress={save} disabled={saving || !dirty} style={[s.saveBtn, !dirty && { opacity: 0.4 }]} {...tid('call-retries-save')}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.saveBtnText}>Save</Text>}
        </TouchableOpacity>
      </View>

      {loading ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
          {storeMode ? (
            <View style={[s.card, { borderWidth: 1, borderColor: `${GOLD}55` }]} {...tid('store-cadence-info')}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name="people" size={16} color={GOLD} />
                <Text style={s.cardTitle}>Default for {meta.scope_name || 'your store'}</Text>
              </View>
              <Text style={s.cardSub}>
                New reps inherit this automatically. {meta.reps_total ?? 0} rep{meta.reps_total === 1 ? '' : 's'} on the team
                {meta.reps_with_override ? `, ${meta.reps_with_override} ${meta.reps_with_override === 1 ? 'has' : 'have'} their own timing.` : ', nobody has custom timing.'}
              </Text>
              {!!meta.reps_with_override && (
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 }}>
                  <Text style={{ fontSize: 14, color: colors.text, flex: 1, paddingRight: 12 }}>Also reset those {meta.reps_with_override} to this default when I save</Text>
                  <Switch value={applyToAll} onValueChange={v => { setApplyToAll(v); setDirty(true); }} trackColor={{ true: GOLD, false: colors.border }} thumbColor="#FFF" {...tid('store-cadence-apply-all')} />
                </View>
              )}
            </View>
          ) : (
            !!inheritedLabel && meta.source !== 'personal' && (
              <View style={[s.card, { flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: `${GOLD}44` }]} {...tid('cadence-source-banner')}>
                <Ionicons name="link" size={16} color={GOLD} />
                <Text style={{ fontSize: 13, color: colors.textSecondary, flex: 1 }}>You're using {inheritedLabel}. Change anything below to make it your own.</Text>
              </View>
            )
          )}
          {!storeMode && meta.source === 'personal' && (meta.store_cadence || meta.global_cadence) && (
            <View style={[s.card, { flexDirection: 'row', alignItems: 'center', gap: 10 }]} {...tid('cadence-source-banner')}>
              <Ionicons name="person" size={16} color={GOLD} />
              <Text style={{ fontSize: 13, color: colors.textSecondary, flex: 1 }}>These are your personal settings.</Text>
              <TouchableOpacity onPress={useTeamDefault} disabled={saving} {...tid('cadence-use-team-default')}>
                <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Use team default</Text>
              </TouchableOpacity>
            </View>
          )}

          <View style={s.card}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <View style={{ flex: 1, paddingRight: 12 }}>
                <Text style={s.cardTitle}>Auto "try again" reminders</Text>
                <Text style={s.cardSub}>When a call hits voicemail or nobody answers, Jessi schedules the next attempt{storeMode ? ' for the rep' : ' for you'}. A connected call clears the streak.</Text>
              </View>
              <Switch value={cadence.enabled} onValueChange={v => patch({ enabled: v })} trackColor={{ true: GOLD, false: colors.border }} thumbColor="#FFF" {...tid('call-retries-enabled')} />
            </View>
          </View>

          {cadence.enabled && (
            <>
              <View style={s.card}>
                <Text style={s.sectionLabel}>Timing</Text>
                <Stepper label="1st miss: try again in" value={cadence.first_minutes} display={(v: number) => `${v} min`} min={5} max={240} step={5} colors={colors} testid="cad-first" onChange={(v: number) => patch({ first_minutes: v })} />
                <Stepper label="2nd miss: later the same day" hint="Rolls to next morning if it lands after your cutoff" value={cadence.second_hours} display={(v: number) => `+${v} hr${v === 1 ? '' : 's'}`} min={1} max={8} colors={colors} testid="cad-second" onChange={(v: number) => patch({ second_hours: v })} />
                <Stepper label="3rd miss: next morning at" hint="Sundays are skipped" value={cadence.morning_hour} display={hour12} min={7} max={12} colors={colors} testid="cad-morning" onChange={(v: number) => patch({ morning_hour: v })} />
                <Stepper label="4th miss: wait" value={cadence.fourth_days} display={(v: number) => `${v} day${v === 1 ? '' : 's'}`} min={1} max={7} colors={colors} testid="cad-fourth" onChange={(v: number) => patch({ fourth_days: v })} />
              </View>

              <View style={s.card}>
                <Text style={s.sectionLabel}>Limits</Text>
                <Stepper label="Evening cutoff" hint="Retries after this time move to the next morning" value={cadence.evening_cutoff} display={hour12} min={16} max={22} colors={colors} testid="cad-cutoff" onChange={(v: number) => patch({ evening_cutoff: v })} />
                <Stepper label="Auto retries before 'text or park'" hint="After this many misses you get one final task instead of more calls" value={cadence.max_auto} display={(v: number) => `${v} tries`} min={1} max={6} colors={colors} testid="cad-max" onChange={(v: number) => patch({ max_auto: v })} />
              </View>
            </>
          )}

          {cadence.enabled && (
            <View style={s.card} {...tid('just-tried-card')}>
              <Text style={s.sectionLabel}>"Just tried you" text</Text>
              <Text style={[s.cardSub, { marginBottom: 8 }]}>One tap on a retry task sends this. Lead sources can override it in their workflow; it always waits for texting hours.</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                {['{first_name}', '{sender_name}', '{company}'].map(f => (
                  <TouchableOpacity key={f} onPress={() => patch({ just_tried_text: ((cadence.just_tried_text ?? DEFAULT_JUST_TRIED) + ' ' + f).trimStart() })}
                    style={{ backgroundColor: colors.surface, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1, borderColor: colors.border }}>
                    <Text style={{ fontSize: 11, fontWeight: '700', color: GOLD, fontFamily: 'monospace' }}>{f}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <TextInput
                value={cadence.just_tried_text ?? ''}
                onChangeText={v => patch({ just_tried_text: v.slice(0, 320) })}
                multiline
                placeholder={DEFAULT_JUST_TRIED}
                placeholderTextColor={colors.textSecondary}
                style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 12, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border, minHeight: 84, textAlignVertical: 'top' }}
                {...tid('just-tried-input')}
              />
              <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6 }}>{(cadence.just_tried_text || '').length}/320 · blank = built-in default</Text>
            </View>
          )}

          {cadence.enabled && (
            <View style={[s.card, { borderWidth: 1, borderColor: `${AMBER}55`, backgroundColor: `${AMBER}0D` }]} {...tid('call-retries-preview')}>
              <Text style={[s.sectionLabel, { color: AMBER }]}>If a call went to voicemail right now</Text>
              {rows.map((r: any) => (
                <View key={r.attempt} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }}>
                  <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: r.final ? colors.surface : `${AMBER}33`, alignItems: 'center', justifyContent: 'center' }}>
                    {r.final ? <Ionicons name="flag" size={12} color={colors.textSecondary} /> : <Text style={{ fontSize: 12, fontWeight: '800', color: AMBER }}>{r.attempt}</Text>}
                  </View>
                  <Text style={{ fontSize: 14, color: colors.text, flex: 1 }}>
                    {r.final ? 'Final "text or park" task ' : `Try again ${r.attempt === 1 ? '' : `(miss #${r.attempt}) `}`}
                    <Text style={{ fontWeight: '700', color: r.final ? colors.textSecondary : colors.text }}>{r.label}</Text>
                  </Text>
                </View>
              ))}
              {dirty && <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6 }}>Preview updates in your phone's time; save to lock it in.</Text>}
            </View>
          )}

          <TouchableOpacity onPress={() => patch({ ...DEFAULTS })} style={{ alignSelf: 'center', marginTop: 8, paddingVertical: 8, paddingHorizontal: 14 }} {...tid('call-retries-reset')}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Reset to built-in defaults (30 min · +3 hrs · 10 AM · 2 days)</Text>
          </TouchableOpacity>

          {!storeMode && meta.is_manager && (
            <TouchableOpacity onPress={() => router.push('/settings/call-retries?scope=store' as any)} style={[s.card, { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 16, borderWidth: 1, borderColor: `${GOLD}55` }]} {...tid('cadence-edit-store')}>
              <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="people" size={18} color={GOLD} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.cardTitle}>Team default</Text>
                <Text style={s.cardSub}>Set the timing every new rep starts with{meta.has_store ? '' : ' (company-wide)'}.</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  back: { width: 40 },
  title: { fontSize: 18, fontWeight: '700', color: colors.text },
  saveBtn: { backgroundColor: colors.accent, borderRadius: 10, paddingHorizontal: 18, paddingVertical: 8 },
  saveBtnText: { color: '#000', fontWeight: '700', fontSize: 15 },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 12 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 2 },
  cardSub: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  sectionLabel: { fontSize: 13, color: colors.textSecondary, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 },
});
