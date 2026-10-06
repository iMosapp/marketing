import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Image, ActivityIndicator, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../common/Toast';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { GOLD, tid, errText } from '../inbox/ownership';
import { useContactFileUpload, ScanHint } from '../../hooks/useContactFileUpload';
import { FileDetailSheet } from './FileDetailSheet';

const RED = '#FF3B30';
const SCANS: { hint: ScanHint; label: string; icon: any }[] = [
  { hint: 'business_card', label: 'Business card', icon: 'card-outline' },
  { hint: 'vin', label: 'VIN / odometer', icon: 'barcode-outline' },
  { hint: 'trade_in', label: 'Trade-in', icon: 'car-sport-outline' },
];

type Props = { contactId: string; colors: any; onContactChanged?: () => void };

// History › Files: everything filed on this contact (photos, PDFs, business cards, texted pictures). Jessi reads each one.
export default function FilesSection({ contactId, colors, onContactChanged }: Props) {
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const { width } = useWindowDimensions();
  const [files, setFiles] = useState<any[] | null>(null);
  const [meta, setMeta] = useState<{ scan_types: Record<string, string>; sensitive_types: string[]; ttl_days: number }>({ scan_types: {}, sensitive_types: [], ttl_days: 30 });
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user?._id || !contactId) return;
    try { const d = (await api.get(`/contact-files/${user._id}/contact/${contactId}`)).data; setFiles(d.files || []); setMeta({ scan_types: d.scan_types || {}, sensitive_types: d.sensitive_types || [], ttl_days: d.ttl_days || 30 }); }
    catch (e) { showToast(errText(e, 'Could not load files'), 'error'); setFiles([]); }
  }, [user?._id, contactId]);
  useEffect(() => { load(); }, [load]);

  const up = useContactFileUpload({ userId: user?._id, contactId, onSaved: (f) => { setFiles(prev => [f, ...(prev || [])]); showToast(f.title ? `Filed: ${f.title}` : 'Filed', 'success'); }, onError: (m) => showToast(m, 'error', 3500) });
  const cols = width >= 900 ? 5 : width >= 600 ? 4 : 3;
  const tile = Math.floor((Math.min(width, 1200) - 32 - (cols - 1) * 10) / cols);
  const open = files?.find(f => f.id === openId) || null;

  return (
    <View style={{ paddingHorizontal: 16, paddingBottom: 24, gap: 12 }} {...tid('files-section')}>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {Platform.OS !== 'web' ? (
          <TouchableOpacity onPress={() => up.pickCamera()} disabled={!!up.busy} style={{ flex: 1, height: 44, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('files-camera')}>
            <Ionicons name="camera" size={18} color="#111" /><Text style={{ fontSize: 13.5, fontWeight: '800', color: '#111' }}>Camera</Text>
          </TouchableOpacity>
        ) : null}
        <TouchableOpacity onPress={() => up.pickLibrary()} disabled={!!up.busy} style={{ flex: 1, height: 44, borderRadius: 12, backgroundColor: Platform.OS === 'web' ? GOLD : colors.card, borderWidth: 1, borderColor: Platform.OS === 'web' ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('files-library')}>
          <Ionicons name="images-outline" size={18} color={Platform.OS === 'web' ? '#111' : colors.text} /><Text style={{ fontSize: 13.5, fontWeight: '800', color: Platform.OS === 'web' ? '#111' : colors.text }}>Photos</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => up.pickDocument()} disabled={!!up.busy} style={{ flex: 1, height: 44, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('files-document')}>
          <Ionicons name="document-attach-outline" size={18} color={colors.text} /><Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>Files / PDF</Text>
        </TouchableOpacity>
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }} {...tid('files-scan-row')}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginRight: 2 }}>SCAN</Text>
        {SCANS.map(s => (
          <TouchableOpacity key={s.hint} onPress={() => up.scan(s.hint)} disabled={!!up.busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, height: 30, paddingHorizontal: 10, borderRadius: 15, borderWidth: 1, borderColor: GOLD + '77', backgroundColor: GOLD + '14' }} {...tid(`files-scan-${s.hint}`)}>
            <Ionicons name={s.icon} size={13} color={GOLD} /><Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{s.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {up.busy ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('files-busy')}>
          <ActivityIndicator color={GOLD} /><Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{up.busy}</Text>
        </View>
      ) : null}

      {files === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 16 }} /> : files.length === 0 ? (
        <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20, lineHeight: 19 }} {...tid('files-empty')}>
          Nothing filed yet. Snap a business card, a VIN plate or a trade-in, add a PDF, or just save a photo. Jessi reads every one so you can ask her about it later. Pictures the customer texts land here on their own.
        </Text>
      ) : (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }} {...tid('files-grid')}>
          {files.map(f => (
            <TouchableOpacity key={f.id} onPress={() => setOpenId(f.id)} activeOpacity={0.85} style={{ width: tile, gap: 5 }} {...tid(`file-tile-${f.id}`)}>
              <View style={{ width: tile, height: tile, borderRadius: 14, overflow: 'hidden', backgroundColor: colors.card, borderWidth: 1, borderColor: f.sensitive ? RED + '66' : colors.border, alignItems: 'center', justifyContent: 'center' }}>
                {f.thumb_url ? <Image source={{ uri: resolvePhotoUrl(f.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : <Ionicons name={f.kind === 'pdf' ? 'document-text' : 'image'} size={30} color={GOLD} />}
                {f.kind === 'pdf' ? <View style={{ position: 'absolute', left: 6, top: 6, backgroundColor: '#111c', borderRadius: 6, paddingHorizontal: 5, paddingVertical: 2 }}><Text style={{ fontSize: 10, fontWeight: '800', color: '#fff' }}>PDF</Text></View> : null}
                {f.sensitive ? <View style={{ position: 'absolute', right: 6, top: 6, backgroundColor: RED, borderRadius: 10, width: 20, height: 20, alignItems: 'center', justifyContent: 'center' }} {...tid(`file-lock-${f.id}`)}><Ionicons name="lock-closed" size={11} color="#fff" /></View> : null}
                {f.source === 'mms' ? <View style={{ position: 'absolute', left: 6, bottom: 6, backgroundColor: '#111c', borderRadius: 6, paddingHorizontal: 5, paddingVertical: 2, flexDirection: 'row', alignItems: 'center', gap: 3 }}><Ionicons name="chatbubble" size={9} color="#fff" /><Text style={{ fontSize: 10, fontWeight: '800', color: '#fff' }}>Texted</Text></View> : null}
              </View>
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }} numberOfLines={1}>{f.title || f.name}</Text>
              <Text style={{ fontSize: 10.5, color: colors.textSecondary }} numberOfLines={1}>{f.scan_label}{Object.keys(f.fields || {}).length && !(f.applied || []).length ? ' · details ready' : ''}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
      <FileDetailSheet visible={!!open} file={open} userId={user?._id} colors={colors} scanTypes={meta.scan_types} sensitiveTypes={meta.sensitive_types} ttlDays={meta.ttl_days}
        onClose={() => setOpenId(null)} onChanged={(nf) => setFiles(prev => (prev || []).map(x => x.id === nf.id ? { ...x, ...nf } : x))} onDeleted={(id) => setFiles(prev => (prev || []).filter(x => x.id !== id))}
        onApplied={() => onContactChanged?.()} showToast={showToast} />
    </View>
  );
}
