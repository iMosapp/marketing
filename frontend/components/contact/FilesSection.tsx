import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Image, ActivityIndicator, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../common/Toast';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { GOLD, tid } from '../inbox/ownership';
import { useContactFileUpload } from '../../hooks/useContactFileUpload';
import type { ContactFilesStore } from '../../hooks/useContactFiles';
import { FileDetailSheet } from './FileDetailSheet';
import { AddFileSheet } from './AddFileSheet';

const RED = '#FF3B30';
type Filter = 'all' | 'photos' | 'pdfs' | 'cards' | 'vehicles' | 'locked';
const FILTERS: { key: Filter; label: string; test: (f: any) => boolean }[] = [
  { key: 'all', label: 'All', test: () => true },
  { key: 'photos', label: 'Photos', test: f => f.kind !== 'pdf' && !['business_card', 'vin', 'trade_in', 'id_document', 'insurance_card', 'credit_app'].includes(f.scan_type) },
  { key: 'pdfs', label: 'PDFs', test: f => f.kind === 'pdf' },
  { key: 'cards', label: 'Cards', test: f => f.scan_type === 'business_card' },
  { key: 'vehicles', label: 'Vehicles', test: f => f.scan_type === 'vin' || f.scan_type === 'trade_in' },
  { key: 'locked', label: 'Locked', test: f => !!f.sensitive },
];
const summaryLine = (files: any[]) => {
  const n = (k: Filter) => files.filter(FILTERS.find(x => x.key === k)!.test).length;
  const parts = [[n('photos'), 'photo'], [n('pdfs'), 'PDF'], [n('cards'), 'card'], [n('vehicles'), 'vehicle'], [n('locked'), 'locked']] as [number, string][];
  return [`${files.length} file${files.length === 1 ? '' : 's'}`, ...parts.filter(([c]) => c > 0).map(([c, w]) => `${c} ${w}${c === 1 || w === 'locked' ? '' : 's'}`)].join(' · ');
};

type Props = { contactId: string; colors: any; store: ContactFilesStore; contact?: any; onContactChanged?: () => void };

// History › Files: everything filed on this contact (photos, PDFs, business cards, texted pictures). Jessi reads each one.
export default function FilesSection({ contactId, colors, store, contact, onContactChanged }: Props) {
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const { width } = useWindowDimensions();
  const { files, setFiles, meta } = store;
  const [openId, setOpenId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');
  const up = useContactFileUpload({ userId: user?._id, contactId, onSaved: (f) => {
    setFiles(prev => [f, ...(prev || [])]); showToast(f.title ? `Filed: ${f.title}` : 'Filed', 'success');
    if ((f.scan_type === 'business_card' && !f.sensitive && Object.keys(f.fields || {}).length) || f.reminders?.length) setOpenId(f.id);   // straight to review
  }, onError: (m) => showToast(m, 'error', 3500) });
  const cols = width >= 900 ? 5 : width >= 600 ? 4 : 3;
  const tile = Math.floor((Math.min(width, 1200) - 32 - (cols - 1) * 10) / cols);
  const open = files?.find(f => f.id === openId) || null;

  const shown = (files || []).filter(FILTERS.find(x => x.key === filter)!.test);
  const chips = FILTERS.filter(x => x.key === 'all' || (files || []).some(x.test));

  return (
    <View style={{ paddingHorizontal: 16, paddingBottom: 24, gap: 12 }} {...tid('files-section')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Text style={{ flex: 1, fontSize: 12.5, color: colors.textSecondary }} numberOfLines={1} {...tid('files-summary')}>{files ? (files.length ? summaryLine(files) : 'Nothing filed yet') : ' '}</Text>
        <TouchableOpacity onPress={() => setAdding(true)} disabled={!!up.busy} style={{ height: 38, paddingHorizontal: 16, borderRadius: 19, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: up.busy ? 0.6 : 1 }} {...tid('files-add')}>
          <Ionicons name="add" size={18} color="#111" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Add</Text>
        </TouchableOpacity>
      </View>
      {files && files.length > 0 && chips.length > 1 ? (
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }} {...tid('files-filter-row')}>
          {chips.map(c => { const on = filter === c.key; const n = c.key === 'all' ? files.length : files.filter(c.test).length; return (
            <TouchableOpacity key={c.key} onPress={() => setFilter(c.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, height: 30, paddingHorizontal: 11, borderRadius: 15, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD + '22' : 'transparent' }} {...tid(`files-filter-${c.key}`)}>
              {c.key === 'locked' ? <Ionicons name="lock-closed" size={11} color={on ? GOLD : colors.textSecondary} /> : null}
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{c.label} · {n}</Text>
            </TouchableOpacity>
          ); })}
        </View>
      ) : null}
      {up.busy ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('files-busy')}>
          <ActivityIndicator color={GOLD} /><Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{up.busy}</Text>
        </View>
      ) : null}

      {files === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 16 }} /> : files.length === 0 ? (
        <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20, lineHeight: 19 }} {...tid('files-empty')}>
          Tap Add to snap a business card, a VIN plate or a trade-in, drop in a PDF, or save a photo. Jessi reads every one so you can ask her about it later. Pictures the customer texts land here on their own.
        </Text>
      ) : (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }} {...tid('files-grid')}>
          {shown.map(f => (
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
      <AddFileSheet visible={adding} onClose={() => setAdding(false)} colors={colors} up={up} />
      <FileDetailSheet visible={!!open} file={open} userId={user?._id} colors={colors} scanTypes={meta.scan_types} sensitiveTypes={meta.sensitive_types} ttlDays={meta.ttl_days} contact={contact}
        onClose={() => setOpenId(null)} onChanged={(nf) => setFiles(prev => (prev || []).map(x => x.id === nf.id ? { ...x, ...nf } : x))} onDeleted={(id) => setFiles(prev => (prev || []).filter(x => x.id !== id))}
        onApplied={() => onContactChanged?.()} showToast={showToast} />
    </View>
  );
}
