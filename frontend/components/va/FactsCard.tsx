import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, RED, tid } from '../scripts/shared';

export type VaConfig = {
  available: boolean; industry: { key: string; label: string; source: 'store' | 'profile' | 'default'; store_name?: string | null }; can_pick_industry: boolean;
  industries: { key: string; label: string }[]; scenarios: { label: string; icon: string; message: string }[]; hold: string[]; safe: string[]; tone: string;
  facts: { store: number; mine: number; store_name?: string | null; can_edit_store: boolean };
};
type Fact = { id: string; text: string; added_by_name?: string | null; at?: string | null };
type Facts = { store: Fact[]; mine: Fact[]; store_id: string | null; store_name: string | null; can_edit_store: boolean; max: number };
type Scope = 'store' | 'mine';

export function useVaConfig() {
  const [config, setConfig] = useState<VaConfig | null | undefined>(undefined);
  const load = useCallback(async () => {
    try { const r = await api.get('/va/config'); setConfig(r.data); return r.data as VaConfig; }
    catch { setConfig(null); return null; }
  }, []);
  useEffect(() => { load(); }, [load]);
  return { config, reload: load, setConfig };
}

function FactRow({ f, scope, canEdit, onSave, onDelete, colors }: { f: Fact; scope: Scope; canEdit: boolean; onSave: (t: string) => Promise<void>; onDelete: () => void; colors: any }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(f.text);
  const [busy, setBusy] = useState(false);
  const save = async () => { setBusy(true); try { await onSave(text); setEditing(false); } finally { setBusy(false); } };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }} {...tid(`va-fact-${scope}-${f.id}`)}>
      <Ionicons name="checkmark-circle" size={16} color={GOLD} style={{ marginTop: 2 }} />
      {editing ? (
        <View style={{ flex: 1 }}>
          <TextInput value={text} onChangeText={setText} multiline autoFocus maxLength={240}
            style={{ color: colors.text, fontSize: 14, lineHeight: 20, borderWidth: 1, borderColor: `${GOLD}66`, borderRadius: 10, padding: 10, backgroundColor: colors.bg }} {...tid(`va-fact-edit-input-${f.id}`)} />
          <View style={{ flexDirection: 'row', gap: 12, marginTop: 6 }}>
            <TouchableOpacity onPress={save} disabled={busy} {...tid(`va-fact-save-${f.id}`)}><Text style={{ color: GOLD, fontWeight: '700', fontSize: 13 }}>{busy ? 'Saving…' : 'Save'}</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => { setText(f.text); setEditing(false); }} {...tid(`va-fact-cancel-${f.id}`)}><Text style={{ color: colors.textSecondary, fontSize: 13 }}>Cancel</Text></TouchableOpacity>
          </View>
        </View>
      ) : (
        <Text style={{ flex: 1, color: colors.text, fontSize: 14, lineHeight: 20 }} {...tid(`va-fact-text-${f.id}`)}>{f.text}{f.added_by_name && scope === 'store' ? <Text style={{ color: colors.textSecondary, fontSize: 11 }}>  · {f.added_by_name}</Text> : null}</Text>
      )}
      {canEdit && !editing && (
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <TouchableOpacity onPress={() => setEditing(true)} hitSlop={8} {...tid(`va-fact-edit-${f.id}`)}><Ionicons name="pencil" size={15} color={colors.textSecondary} /></TouchableOpacity>
          <TouchableOpacity onPress={onDelete} hitSlop={8} {...tid(`va-fact-delete-${f.id}`)}><Ionicons name="trash-outline" size={15} color={RED} /></TouchableOpacity>
        </View>
      )}
    </View>
  );
}

function FactList({ scope, title, sub, facts, canEdit, max, reload, colors }: { scope: Scope; title: string; sub: string; facts: Fact[]; canEdit: boolean; max: number; reload: (f: Facts) => void; colors: any }) {
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = async (fn: () => Promise<any>) => {
    setBusy(true); setError('');
    try { const r = await fn(); reload(r.data); return true; }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not save that'); return false; }
    finally { setBusy(false); }
  };
  const add = async () => { if (draft.trim().length < 3) return; if (await run(() => api.post('/va/facts', { text: draft.trim(), scope }))) setDraft(''); };
  const del = (f: Fact) => showConfirm('Remove this fact?', `Your VA will stop answering with: "${f.text}"`, () => { run(() => api.delete(`/va/facts/${f.id}`, { params: { scope } })); }, undefined, 'Remove');
  return (
    <View style={{ marginTop: 14 }} {...tid(`va-facts-${scope}`)}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>{title.toUpperCase()} · {facts.length}</Text>
      <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 17 }}>{sub}</Text>
      {facts.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary, fontStyle: 'italic', marginTop: 8 }} {...tid(`va-facts-${scope}-empty`)}>Nothing here yet.</Text>}
      {facts.map(f => (
        <FactRow key={f.id} f={f} scope={scope} canEdit={canEdit} colors={colors}
          onSave={async (t) => { await run(() => api.put(`/va/facts/${f.id}`, { text: t, scope })); }} onDelete={() => del(f)} />
      ))}
      {canEdit && facts.length < max && (
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, marginTop: 10 }}>
          <TextInput value={draft} onChangeText={setDraft} multiline maxLength={240} placeholder={scope === 'store' ? 'e.g. We take walk-ins weekdays until 6' : 'e.g. I am off Sundays, text me Monday'} placeholderTextColor={colors.textSecondary}
            style={{ flex: 1, color: colors.text, fontSize: 14, lineHeight: 20, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, backgroundColor: colors.bg, minHeight: 42 }} {...tid(`va-fact-input-${scope}`)} />
          <TouchableOpacity onPress={add} disabled={busy || draft.trim().length < 3} style={{ backgroundColor: draft.trim().length < 3 ? colors.border : GOLD, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 11 }} {...tid(`va-fact-add-${scope}`)}>
            {busy ? <ActivityIndicator size="small" color="#000" /> : <Text style={{ fontWeight: '800', color: '#000', fontSize: 13 }}>Add</Text>}
          </TouchableOpacity>
        </View>
      )}
      {!!error && <Text style={{ color: RED, fontSize: 12, marginTop: 6 }} {...tid(`va-facts-${scope}-error`)}>{error}</Text>}
    </View>
  );
}

export function FactsCard({ config: given, onConfig }: { config?: VaConfig | null; onConfig?: (c: VaConfig) => void }) {
  const { colors } = useThemeStore();
  const own = useVaConfig();
  const config = given === undefined ? own.config : given;
  const [facts, setFacts] = useState<Facts | null>(null);
  const [open, setOpen] = useState(false);
  const [pickBusy, setPickBusy] = useState(false);
  const load = useCallback(async () => { try { const r = await api.get('/va/facts'); setFacts(r.data); } catch { setFacts(null); } }, []);
  useEffect(() => { if (config?.available) load(); }, [config?.available, load]);
  if (!config || !config.available) return null;
  const pick = async (key: string) => {
    setPickBusy(true);
    try { const r = await api.put('/va/industry', { industry: key }); own.setConfig(r.data); onConfig?.(r.data); } catch {} finally { setPickBusy(false); }
  };
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: `${GOLD}55`, marginBottom: 16 } as const;
  return (
    <View style={card} {...tid('va-facts-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="layers" size={20} color={GOLD} /></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Things my VA may answer</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17, marginTop: 3 }}>Your VA only states specifics that are written here. Anything else (prices, availability, policies) it hands to you.</Text>
        </View>
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, flexWrap: 'wrap' }} {...tid('va-industry-row')}>
        <Ionicons name="business" size={14} color={GOLD} />
        <Text style={{ fontSize: 13, color: colors.text, fontWeight: '700' }} {...tid('va-industry-label')}>{config.industry.label}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>{config.industry.source === 'store' ? `· set on ${config.industry.store_name || 'your store'}` : config.industry.source === 'profile' ? '· your pick' : '· pick yours below'}</Text>
      </View>
      {config.can_pick_industry && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 }} {...tid('va-industry-picker')}>
          {config.industries.map(i => {
            const on = i.key === config.industry.key;
            return (
              <TouchableOpacity key={i.key} onPress={() => pick(i.key)} disabled={pickBusy || on} style={{ borderRadius: 14, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD : 'transparent' }} {...tid(`va-industry-${i.key}`)}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: on ? '#000' : colors.textSecondary }}>{i.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      )}
      <TouchableOpacity onPress={() => setOpen(o => !o)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 10 }} {...tid('va-hold-toggle')}>
        <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{open ? 'Hide' : 'What always goes to me'}</Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={13} color={GOLD} />
      </TouchableOpacity>
      {open && (
        <View style={{ marginTop: 6 }} {...tid('va-hold-list')}>
          {config.hold.map((h, i) => <Text key={i} style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 18 }}>· {h}</Text>)}
        </View>
      )}
      {facts === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 14 }} /> : (
        <>
          {facts.store_id && (
            <FactList scope="store" title={`${facts.store_name || 'Store'} facts`} sub={facts.can_edit_store ? 'Everyone on the team gets these. Hours, what to bring, walk-ins, rules, links.' : 'Set by your manager. Ask them to add or change one.'}
              facts={facts.store} canEdit={facts.can_edit_store} max={facts.max} reload={setFacts} colors={colors} />
          )}
          <FactList scope="mine" title="My facts" sub="Only your VA uses these. Your schedule, your links, how you like to work." facts={facts.mine} canEdit max={facts.max} reload={setFacts} colors={colors} />
        </>
      )}
    </View>
  );
}
