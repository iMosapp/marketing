import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, ScrollView, Image, KeyboardAvoidingView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { BigButton, SEVERITY_COLORS } from './shared';

type Props = { colors: any; appraisalId: string; meta: { categories: Record<string, string>; subtypes: Record<string, Record<string, string>>; severities: Record<string, string> }; frames: any[]; finding?: any | null; onClose: () => void; onSaved: () => void; showToast: (m: string, t?: any) => void };

// ADD ISSUE / EDIT ISSUE. The AI's original call is never touched; edits are recorded with who and when.
export const FindingEditor = ({ colors, appraisalId, meta, frames, finding, onClose, onSaved, showToast }: Props) => {
  const [category, setCategory] = useState<string>(finding?.category || 'body');
  const [subtype, setSubtype] = useState<string>(finding?.subtype || 'dent');
  const [location, setLocation] = useState<string>(finding?.location_label || '');
  const [severity, setSeverity] = useState<string>(finding?.severity || 'minor');
  const [note, setNote] = useState<string>(finding?.explanation || '');
  const [frameIds, setFrameIds] = useState<string[]>((finding?.evidence || []).map((e: any) => e.frame_id));
  const [saving, setSaving] = useState(false);
  const subs = meta.subtypes[category] || {};

  const save = async () => {
    if (!location.trim()) { showToast('Where on the vehicle?', 'error'); return; }
    setSaving(true);
    try {
      const body = { category, subtype, location_label: location.trim(), severity, explanation: note.trim(), frame_ids: frameIds };
      if (finding) await api.patch(`/appraisals/${appraisalId}/inspection/findings/${finding.id}`, body);
      else await api.post(`/appraisals/${appraisalId}/inspection/findings`, body);
      onSaved(); onClose();
    } catch (e) { showToast(errText(e, 'Could not save that issue'), 'error'); }
    finally { setSaving(false); }
  };
  const Pill = ({ label, active, onPress, color, testId }: any) => (
    <TouchableOpacity onPress={onPress} style={{ paddingHorizontal: 11, paddingVertical: 7, borderRadius: 10, backgroundColor: active ? (color || GOLD) : colors.card, borderWidth: 1, borderColor: active ? (color || GOLD) : colors.border }} {...tid(testId)}>
      <Text style={{ fontSize: 12.5, fontWeight: '800', color: active ? '#0B0B0D' : colors.text }}>{label}</Text>
    </TouchableOpacity>
  );
  const Label = ({ t }: { t: string }) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginTop: 6 }}>{t}</Text>;

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: '#00000088' }}>
        <View style={{ maxHeight: '92%', backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 18, gap: 10 }} {...tid('finding-editor')}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>{finding ? 'Edit issue' : 'Add issue'}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('finding-editor-close')}><Ionicons name="close" size={22} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ gap: 6, paddingBottom: 8 }}>
            <Label t="CATEGORY" />
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{Object.entries(meta.categories).map(([k, l]) => <Pill key={k} label={l} active={category === k} onPress={() => { setCategory(k); setSubtype(Object.keys(meta.subtypes[k] || {})[0] || 'other'); }} testId={`editor-category-${k}`} />)}</View>
            <Label t="WHAT" />
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{Object.entries(subs).map(([k, l]) => <Pill key={k} label={l} active={subtype === k} onPress={() => setSubtype(k)} testId={`editor-subtype-${k}`} />)}</View>
            <Label t="WHERE ON THE VEHICLE" />
            <TextInput value={location} onChangeText={setLocation} placeholder="Passenger rear door, driver front wheel…" placeholderTextColor={colors.textSecondary}
              style={{ height: 46, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, color: colors.text, paddingHorizontal: 12, fontSize: 15 }} {...tid('editor-location')} />
            <Label t="SEVERITY" />
            <View style={{ flexDirection: 'row', gap: 6 }}>{Object.entries(meta.severities).map(([k, l]) => <Pill key={k} label={l} active={severity === k} color={SEVERITY_COLORS[k]} onPress={() => setSeverity(k)} testId={`editor-severity-${k}`} />)}</View>
            <Label t="NOTE" />
            <TextInput value={note} onChangeText={setNote} placeholder="What you see" placeholderTextColor={colors.textSecondary} multiline
              style={{ minHeight: 60, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, color: colors.text, padding: 12, fontSize: 14 }} {...tid('editor-note')} />
            {frames.length ? (
              <>
                <Label t={`EVIDENCE · tap frames that show it (${frameIds.length})`} />
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
                  {frames.map(fr => {
                    const on = frameIds.includes(fr.id);
                    return (
                      <TouchableOpacity key={fr.id} onPress={() => setFrameIds(p => (on ? p.filter(x => x !== fr.id) : [...p, fr.id]))} style={{ width: 92, height: 66, borderRadius: 8, overflow: 'hidden', borderWidth: 2, borderColor: on ? GOLD : colors.border }} {...tid(`editor-frame-${fr.id}`)}>
                        {fr.thumb_url ? <Image source={{ uri: resolvePhotoUrl(fr.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : null}
                        {on ? <View style={{ position: 'absolute', right: 4, top: 4, width: 18, height: 18, borderRadius: 9, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="checkmark" size={12} color="#0B0B0D" /></View> : null}
                        {fr.timestamp_label ? <Text style={{ position: 'absolute', left: 4, bottom: 3, fontSize: 9.5, fontWeight: '700', color: '#fff' }}>{fr.timestamp_label}</Text> : null}
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              </>
            ) : null}
            {finding?.ai_original ? <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 6 }}>Jessi originally said: {finding.ai_original.severity} {finding.ai_original.subtype?.replace(/_/g, ' ')} · {finding.ai_original.location_label} · {finding.ai_original.confidence} confidence. That stays on the record.</Text> : null}
          </ScrollView>
          <BigButton colors={colors} icon="checkmark" label={finding ? 'Save changes' : 'Add issue'} onPress={save} primary disabled={saving} testId="editor-save" />
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
