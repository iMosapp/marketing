import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { SheetGrabber } from '../common/SheetGrabber';
import { GOLD, tid, errText } from '../inbox/ownership';
import { useScanUpload, ScanMatch, ScanResult, ScanSource, ScanMode } from '../../hooks/useScanWithJessi';
import { ScanReview } from './ScanReview';
import { ScanDocReview } from './ScanDocReview';
import { ScanUpdateExisting } from './ScanUpdateExisting';
import { PickedContact } from './ScanContactPicker';

type Props = { visible: boolean; userId?: string; colors: any; onClose: () => void; showToast: (m: string, t?: any, d?: number) => void;
  onCreate: (scan: any, values: Record<string, string>, reminders?: string[]) => void; onSaved: (contactId: string) => void; initialMode?: ScanMode };

const SOURCES: { key: ScanSource; icon: any; label: string; sub: Record<ScanMode, string> }[] = [
  { key: 'camera', icon: 'camera', label: 'Take a photo', sub: { card: 'Card flat, in good light', document: 'The whole page, in good light' } },
  { key: 'library', icon: 'images-outline', label: 'Choose a photo', sub: { card: 'From your photos', document: 'A photo or a screenshot' } },
  { key: 'document', icon: 'document-attach-outline', label: 'Choose a file', sub: { card: 'Photo or PDF', document: 'PDF or photo' } },
];
const MODES: { key: ScanMode; label: string; intro: string }[] = [
  { key: 'card', label: 'Business card', intro: "Snap a business card. Jessi reads it and you check everything before it's saved." },
  { key: 'document', label: 'Quote or document', intro: 'A quote, invoice, service paper or screenshot. Jessi pulls out the key dates and suggests reminders. Nothing is sent.' },
];
const DOC_FIELDS = ['first_name', 'last_name', 'phone', 'email', 'company'];   // a document's own address / title is usually the seller's

// Scan with Jessi: pick -> Jessi reads it -> review -> create a contact, update an existing one, or file a document. Nothing is saved until the rep says so.
export const ScanWithJessiSheet = ({ visible, userId, colors, onClose, showToast, onCreate, onSaved, initialMode = 'card' }: Props) => {
  const [mode, setMode] = useState<ScanMode>(initialMode);
  const [res, setRes] = useState<ScanResult | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [match, setMatch] = useState<ScanMatch | null>(null);
  const [saving, setSaving] = useState(false);
  const up = useScanUpload(userId, r => { setRes(r); setValues({ ...(r.scan.fields || {}) }); setMatch(null); }, m => showToast(m, 'error', 3500));
  const reset = () => { setRes(null); setValues({}); setMatch(null); };
  const close = (discard = true) => {
    if (discard && res?.scan?.id && !res.scan.contact_id) api.delete(`/scan/${userId}/${res.scan.id}`).catch(() => {});
    reset(); onClose();
  };
  const post = async (c: PickedContact, body: any, done: (r: any) => string) => {
    if (!res) return;
    setSaving(true);
    try {
      const r = await api.post(`/scan/${userId}/${res.scan.id}/save`, { contact_id: c.id, ...body });
      showToast(done(r.data), 'success', 3500);
      reset(); onSaved(c.id);
    } catch (e) { showToast(errText(e, 'Could not save that'), 'error'); } finally { setSaving(false); }
  };
  const saveCard = (fields: string[]) => match && post(match, { fields, values }, d => {
    const n = Object.keys(d.applied || {}).length;
    return n ? `${n} detail${n === 1 ? '' : 's'} added · card saved to ${match.name}'s Files` : `Card saved to ${match.name}'s Files`;
  });
  const saveDoc = (c: PickedContact, reminders: string[]) => post(c, { fields: [], values: {}, reminders }, d => {
    const n = (d.reminders || []).length;
    return `Saved to ${c.name}'s Files${n ? ` · ${n} reminder${n === 1 ? '' : 's'} set` : ''}`;
  });
  const createFrom = (scan: any, v: Record<string, string>, reminders?: string[]) => { reset(); onCreate(scan, v, reminders); };
  const sources = SOURCES.filter(s => s.key !== 'camera' || Platform.OS !== 'web');
  const intro = MODES.find(m => m.key === mode)!.intro;
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={() => close()}>
      <TouchableOpacity activeOpacity={1} onPress={() => close()} style={{ flex: 1, backgroundColor: '#0008' }} {...tid('scan-backdrop')} />
      <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: 18, paddingBottom: 28, maxHeight: '88%' }} {...tid('scan-sheet')}>
        <SheetGrabber onClose={() => close()} color={colors.border} />
        <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          {!res && (
            <>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <Ionicons name="scan" size={20} color={GOLD} />
                <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>Scan with Jessi</Text>
              </View>
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 10, backgroundColor: colors.card, borderRadius: 12, padding: 3 }} {...tid('scan-mode-switch')}>
                {MODES.map(m => { const on = m.key === mode; return (
                  <TouchableOpacity key={m.key} disabled={!!up.busy} onPress={() => setMode(m.key)} style={{ flex: 1, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: on ? GOLD : 'transparent' }} {...tid(`scan-mode-${m.key}`)}>
                    <Text style={{ fontSize: 13, fontWeight: '800', color: on ? '#111' : colors.textSecondary }}>{m.label}</Text>
                  </TouchableOpacity>
                ); })}
              </View>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 8, marginBottom: 8, lineHeight: 17 }} {...tid('scan-intro')}>{intro}</Text>
              {up.busy ? (
                <View style={{ paddingVertical: 30, alignItems: 'center', gap: 10 }} {...tid('scan-busy')}>
                  <ActivityIndicator color={GOLD} /><Text style={{ color: colors.textSecondary }}>{up.busy}</Text>
                </View>
              ) : sources.map(s => (
                <TouchableOpacity key={s.key} onPress={() => up.run(s.key, mode)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 }} {...tid(`scan-source-${s.key}`)}>
                  <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}><Ionicons name={s.icon} size={19} color={GOLD} /></View>
                  <View><Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{s.label}</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{s.sub[mode]}</Text></View>
                </TouchableOpacity>
              ))}
            </>
          )}
          {res && !match && res.scan.is_card && (
            <ScanReview scan={res.scan} values={values} setValue={(k, v) => setValues(p => ({ ...p, [k]: v }))} matches={res.matches} colors={colors}
              onCreate={() => createFrom(res.scan, values)} onUpdate={setMatch} onDiscard={() => close()} />
          )}
          {res && !res.scan.is_card && (
            <ScanDocReview scan={res.scan} matches={res.matches} userId={userId} colors={colors} busy={saving} onSave={saveDoc} onDiscard={() => close()}
              onCreate={r => createFrom(res.scan, Object.fromEntries(DOC_FIELDS.filter(k => values[k]).map(k => [k, values[k]])), r)} />
          )}
          {res && match && (
            <ScanUpdateExisting match={match} values={values} labels={res.scan.labels || {}} colors={colors} busy={saving} onBack={() => setMatch(null)} onSave={saveCard} />
          )}
        </ScrollView>
      </View>
    </Modal>
  );
};
