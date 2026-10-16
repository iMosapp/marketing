import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { SheetGrabber } from '../common/SheetGrabber';
import { GOLD, tid, errText } from '../inbox/ownership';
import { useScanUpload, ScanMatch, ScanResult, ScanSource } from '../../hooks/useScanWithJessi';
import { ScanReview } from './ScanReview';
import { ScanUpdateExisting } from './ScanUpdateExisting';

type Props = { visible: boolean; userId?: string; colors: any; onClose: () => void; showToast: (m: string, t?: any, d?: number) => void;
  onCreate: (scan: any, values: Record<string, string>) => void; onSaved: (contactId: string) => void };

const SOURCES: { key: ScanSource; icon: any; label: string; sub: string }[] = [
  { key: 'camera', icon: 'camera', label: 'Take a photo', sub: 'Card flat, in good light' },
  { key: 'library', icon: 'images-outline', label: 'Choose a photo', sub: 'From your photos' },
  { key: 'document', icon: 'document-attach-outline', label: 'Choose a file', sub: 'Photo or PDF' },
];

// Scan with Jessi: pick -> Jessi reads it -> review -> create a contact or update an existing one. Nothing is saved until the rep says so.
export const ScanWithJessiSheet = ({ visible, userId, colors, onClose, showToast, onCreate, onSaved }: Props) => {
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
  const save = async (fields: string[]) => {
    if (!res || !match) return;
    setSaving(true);
    try {
      const r = await api.post(`/scan/${userId}/${res.scan.id}/save`, { contact_id: match.id, fields, values });
      const n = Object.keys(r.data.applied || {}).length;
      showToast(n ? `${n} detail${n === 1 ? '' : 's'} added · card saved to ${match.name}'s Files` : `Card saved to ${match.name}'s Files`, 'success', 3500);
      reset(); onSaved(match.id);
    } catch (e) { showToast(errText(e, 'Could not save that'), 'error'); } finally { setSaving(false); }
  };
  const sources = SOURCES.filter(s => s.key !== 'camera' || Platform.OS !== 'web');
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
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2, marginBottom: 8 }}>Snap a business card. Jessi reads it and you check everything before it's saved.</Text>
              {up.busy ? (
                <View style={{ paddingVertical: 30, alignItems: 'center', gap: 10 }} {...tid('scan-busy')}>
                  <ActivityIndicator color={GOLD} /><Text style={{ color: colors.textSecondary }}>{up.busy}</Text>
                </View>
              ) : sources.map(s => (
                <TouchableOpacity key={s.key} onPress={() => up.run(s.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 }} {...tid(`scan-source-${s.key}`)}>
                  <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }}><Ionicons name={s.icon} size={19} color={GOLD} /></View>
                  <View><Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{s.label}</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{s.sub}</Text></View>
                </TouchableOpacity>
              ))}
            </>
          )}
          {res && !match && (
            <ScanReview scan={res.scan} values={values} setValue={(k, v) => setValues(p => ({ ...p, [k]: v }))} matches={res.matches} colors={colors}
              onCreate={() => { const r = res; reset(); onCreate(r.scan, values); }} onUpdate={setMatch} onDiscard={() => close()} />
          )}
          {res && match && (
            <ScanUpdateExisting match={match} values={values} labels={res.scan.labels || {}} colors={colors} busy={saving} onBack={() => setMatch(null)} onSave={save} />
          )}
        </ScrollView>
      </View>
    </Modal>
  );
};
