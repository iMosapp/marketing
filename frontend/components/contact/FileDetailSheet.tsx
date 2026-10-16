import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, Image, TextInput, ActivityIndicator, Platform, Switch, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { showConfirm } from '../../services/alert';
import { GOLD, tid, errText } from '../inbox/ownership';
import { DocDates, fmtDay } from '../scan/DocDates';

type Props = { visible: boolean; file: any | null; userId?: string; colors: any; scanTypes: Record<string, string>; sensitiveTypes: string[]; ttlDays: number; contact?: any;
  onClose: () => void; onChanged: (f: any) => void; onDeleted: (id: string) => void; onApplied: () => void; showToast: (m: string, t?: any, d?: number) => void };

const RED = '#FF3B30';
const when = (iso: string) => { const d = new Date(iso); return isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); };

// One file: preview, what Jessi read, the details she can add to the contact, type, sensitive lock, delete.
// Only empty slots are pre-ticked: anything that would replace a saved value (a name, address, vehicle...) waits for the rep's tick.
const CURRENT: Record<string, (c: any) => string> = { first_name: c => c?.first_name || '', last_name: c => c?.last_name || '', company: c => c?.employer || '', title: c => c?.occupation || '',
  website: c => c?.personal_details?.website || '', address_street: c => c?.address_street || '', address_city: c => c?.address_city || '', address_state: c => c?.address_state || '', address_zip: c => c?.address_zip || '' };
const VEHICLE = ['vin', 'year', 'make', 'model', 'trim', 'mileage', 'color', 'plate'];
const ADDS = ['phone', 'phone_office', 'email'];   // added next to what is saved, never replace it
const hasValue = (k: string, c: any) => !!(CURRENT[k]?.(c) || (VEHICLE.includes(k) && c?.vehicle) || (k === 'birthday' && c?.birthday));

export const FileDetailSheet = ({ visible, file, userId, colors, scanTypes, sensitiveTypes, ttlDays, contact, onClose, onChanged, onDeleted, onApplied, showToast }: Props) => {
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [showText, setShowText] = useState(false);
  const [name, setName] = useState('');
  useEffect(() => { if (file) { setPicked(Object.keys(file.fields || {}).filter(k => !(file.applied || []).includes(k) && (ADDS.includes(k) || !hasValue(k, contact)))); setShowText(false); setName(file.title || file.name || ''); } }, [file?.id, contact?._id]);
  const url = useMemo(() => resolvePhotoUrl(file?.url) || '', [file?.url]);
  if (!file) return null;

  const patch = async (data: any) => {
    setBusy('patch');
    try { const r = await api.patch(`/contact-files/${userId}/${file.id}`, data); onChanged(r.data); }
    catch (e) { showToast(errText(e, 'Could not update'), 'error'); }
    finally { setBusy(null); }
  };
  const apply = async () => {
    if (!picked.length) return;
    setBusy('apply');
    try {
      const r = await api.post(`/contact-files/${userId}/${file.id}/apply`, { fields: picked });
      const n = Object.keys(r.data.applied || {}).length;
      showToast(n ? `${n} detail${n === 1 ? '' : 's'} added to the contact` : 'Nothing new to add', 'success');
      onChanged({ ...file, applied: [...(file.applied || []), ...Object.keys(r.data.applied || {})] }); onApplied();
    } catch (e) { showToast(errText(e, 'Could not add those details'), 'error'); }
    finally { setBusy(null); }
  };
  const remove = () => showConfirm('Delete this file?', file.sensitive ? 'The stored copy is destroyed right away.' : 'It is removed from the record for good.', async () => {
    try { await api.delete(`/contact-files/${userId}/${file.id}`); onDeleted(file.id); onClose(); }
    catch (e) { showToast(errText(e, 'Could not delete'), 'error'); }
  }, undefined, 'Delete');
  const open = () => { if (Platform.OS === 'web') (globalThis as any).open(url, '_blank'); else Linking.openURL(url).catch(() => showToast('Could not open it', 'error')); };
  const decide = async (key: string, decision: 'create' | 'dismiss') => {
    setBusy(key);
    try {
      const r = await api.post(`/contact-files/${userId}/${file.id}/reminders`, { key, decision });
      onChanged(r.data.file);
      if (decision === 'create') showToast(`Reminder set for ${fmtDay(r.data.reminder.due)}. It's in your Tasks.`, 'success', 3500);
    } catch (e) { showToast(errText(e, 'Could not set that reminder'), 'error'); }
    finally { setBusy(null); }
  };
  const setAsPhoto = async () => {
    setBusy('photo');
    try { await api.patch(`/contacts/${userId}/${file.contact_id}/profile-photo`, { photo_url: file.url }); showToast('Profile photo updated', 'success'); onApplied(); }
    catch (e) { showToast(errText(e, 'Could not set the profile photo'), 'error'); }
    finally { setBusy(null); }
  };
  const lockedType = sensitiveTypes.includes(file.scan_type);
  const fields: [string, string][] = Object.entries(file.fields || {}) as any;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%', paddingBottom: Platform.OS === 'ios' ? 28 : 12 }} {...tid('file-detail-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 8, gap: 10 }}>
            <TextInput value={name} onChangeText={setName} onBlur={() => { if (name.trim() && name.trim() !== (file.title || file.name)) patch({ title: name.trim() }); }} style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }} {...tid('file-name-input')} />
            <TouchableOpacity onPress={onClose} {...tid('file-detail-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ paddingHorizontal: 16, gap: 12, paddingBottom: 12 }}>
            <TouchableOpacity onPress={open} activeOpacity={0.9} style={{ borderRadius: 16, overflow: 'hidden', backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('file-preview')}>
              {file.kind === 'image' ? <Image source={{ uri: url }} style={{ width: '100%', height: 260 }} resizeMode="contain" />
                : <View style={{ height: 150, alignItems: 'center', justifyContent: 'center', gap: 8 }}><Ionicons name="document-text" size={44} color={GOLD} /><Text style={{ color: colors.textSecondary, fontSize: 13 }}>PDF · {file.pages || 1} page{file.pages === 1 ? '' : 's'} · tap to open</Text></View>}
            </TouchableOpacity>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{file.doc_label || file.scan_label} · {when(file.created_at)}{file.source === 'mms' ? ' · texted by the customer' : ''}{file.status === 'unread' ? ' · Jessi could not read this one' : ''}</Text>
            {file.kind === 'image' && !file.sensitive && file.scan_type === 'photo' && !file.doc_type && (
              <TouchableOpacity onPress={setAsPhoto} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start' }} {...tid('file-use-as-profile-photo')}>
                {busy === 'photo' ? <ActivityIndicator color={GOLD} size="small" /> : <Ionicons name="person-circle-outline" size={18} color={GOLD} />}
                <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Use as profile photo</Text>
              </TouchableOpacity>
            )}
            {file.summary ? <Text style={{ fontSize: 14.5, lineHeight: 21, color: colors.text }} {...tid('file-summary')}>{file.summary}</Text> : null}
            {file.text ? (
              <TouchableOpacity onPress={() => setShowText(s => !s)} {...tid('file-text-toggle')}><Text style={{ fontSize: 12.5, fontWeight: '700', color: GOLD }}>{showText ? 'Hide what Jessi read' : 'Show everything Jessi read'}</Text></TouchableOpacity>
            ) : null}
            {showText ? <Text style={{ fontSize: 13, lineHeight: 18, color: colors.textSecondary }} {...tid('file-text')}>{file.text}</Text> : null}
            {!file.sensitive && <DocDates dates={file.dates || []} reminders={file.reminders || []} colors={colors} busyKey={busy} onAdd={k => decide(k, 'create')} onDismiss={k => decide(k, 'dismiss')} />}

            {fields.length ? (
              <View style={{ gap: 6, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '55', padding: 12 }} {...tid('file-fields')}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>JESSI READ THESE DETAILS</Text>
                {fields.map(([k, v]) => { const done = (file.applied || []).includes(k); const on = picked.includes(k); const cur = CURRENT[k]?.(contact); const replaces = !done && cur && cur !== v; return (
                  <TouchableOpacity key={k} disabled={done} onPress={() => setPicked(p => on ? p.filter(x => x !== k) : [...p, k])} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} {...tid(`file-field-${k}`)}>
                    <Ionicons name={done ? 'checkmark-done-circle' : on ? 'checkbox' : 'square-outline'} size={20} color={done ? '#34C759' : on ? GOLD : colors.border} />
                    <Text style={{ fontSize: 12, color: colors.textSecondary, width: 82 }}>{file.field_labels?.[k] || k}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 14, color: done ? colors.textSecondary : colors.text }} numberOfLines={1}>{v}</Text>
                      {replaces ? <Text style={{ fontSize: 11, color: '#FF9500' }} numberOfLines={1} {...tid(`file-field-replaces-${k}`)}>replaces "{cur}"</Text> : null}
                    </View>
                  </TouchableOpacity>
                ); })}
                <TouchableOpacity onPress={apply} disabled={!picked.length || !!busy} style={{ marginTop: 4, height: 42, borderRadius: 12, backgroundColor: picked.length ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('file-apply')}>
                  {busy === 'apply' ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>{picked.length ? `Add ${picked.length} to the contact` : 'All added'}</Text>}
                </TouchableOpacity>
              </View>
            ) : null}

            <View style={{ gap: 6 }}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>WHAT IS IT</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                {Object.entries(scanTypes).map(([k, label]) => { const on = file.scan_type === k; return (
                  <TouchableOpacity key={k} onPress={() => !on && patch({ scan_type: k })} style={{ height: 30, paddingHorizontal: 11, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: on ? GOLD : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`file-type-${k}`)}>
                    <Text style={{ fontSize: 12, fontWeight: '700', color: on ? '#111' : colors.text }}>{label}</Text>
                  </TouchableOpacity>
                ); })}
              </View>
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: file.sensitive ? RED + '66' : colors.border, padding: 12 }} {...tid('file-sensitive-row')}>
              <Ionicons name={file.sensitive ? 'lock-closed' : 'lock-open-outline'} size={20} color={file.sensitive ? RED : colors.textSecondary} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Sensitive</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{file.sensitive ? `Only you can see it. Destroyed automatically on ${when(file.expires_at)}.${lockedType ? ' IDs, insurance cards and credit apps always stay sensitive.' : ''}` : `Visible to whoever can see this contact. Turn on for IDs and financial forms (auto-deletes in ${ttlDays} days).`}</Text>
              </View>
              <Switch value={!!file.sensitive} disabled={lockedType || !!busy} onValueChange={v => patch({ sensitive: v })} trackColor={{ true: RED }} {...tid('file-sensitive-switch')} />
            </View>

            <View style={{ flexDirection: 'row', gap: 10 }}>
              <TouchableOpacity onPress={open} style={{ flex: 1, height: 42, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('file-open')}>
                <Ionicons name="open-outline" size={16} color={colors.text} /><Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>Open full size</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={remove} style={{ height: 42, paddingHorizontal: 16, borderRadius: 12, borderWidth: 1, borderColor: RED + '66', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('file-delete')}>
                <Ionicons name="trash-outline" size={16} color={RED} /><Text style={{ fontSize: 13.5, fontWeight: '700', color: RED }}>Delete</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};
