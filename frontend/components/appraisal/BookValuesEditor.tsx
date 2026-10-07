import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { showConfirm } from '../../services/alert';
import { Chip, money } from './shared';

type Props = { colors: any; appraisalId: string; bookValues: any[]; sources: Record<string, string>; types: Record<string, string>; onChanged: (bv: any[]) => void; showToast: (m: string, t?: any) => void };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');

const Pick = ({ options, value, onPick, colors, prefix }: { options: Record<string, string>; value: string; onPick: (k: string) => void; colors: any; prefix: string }) => (
  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
    {Object.entries(options).map(([k, l]) => (
      <TouchableOpacity key={k} onPress={() => onPick(k)} style={{ borderRadius: 9, paddingHorizontal: 10, paddingVertical: 7, backgroundColor: value === k ? GOLD + '33' : colors.bg, borderWidth: 1, borderColor: value === k ? GOLD : colors.border }} {...tid(`${prefix}-${k}`)}>
        <Text style={{ fontSize: 12, fontWeight: '800', color: value === k ? GOLD : colors.text }}>{l}</Text>
      </TouchableOpacity>
    ))}
  </View>
);

// Manual Black Book / MMR / J.D. Power / KBB entries, each labelled by source next to the market data. Provider-populated later.
export const BookValuesEditor = ({ colors, appraisalId, bookValues, sources, types, onChanged, showToast }: Props) => {
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);
  const num = parseInt(String(editing?.value || '').replace(/\D/g, ''), 10);
  const start = (b?: any) => setEditing(b ? { ...b, value: String(b.value) } : { source: 'black_book', value_type: 'wholesale', value: '', note: '', source_label: '' });
  const save = async () => {
    setSaving(true);
    try {
      const body = { source: editing.source, value_type: editing.value_type, value: num, note: editing.note || '', source_label: editing.source === 'other' ? editing.source_label || '' : undefined };
      const r = editing.id ? (await api.patch(`/appraisals/${appraisalId}/book-values/${editing.id}`, body)).data : (await api.post(`/appraisals/${appraisalId}/book-values`, body)).data;
      onChanged(r.book_values); setEditing(null);
    } catch (e) { showToast(errText(e, 'Could not save that book value'), 'error'); }
    finally { setSaving(false); }
  };
  const remove = (b: any) => showConfirm('Remove this book value?', `${b.source_label} ${money(b.value)} comes off the appraisal.`, async () => {
    try { onChanged((await api.delete(`/appraisals/${appraisalId}/book-values/${b.id}`)).data.book_values); } catch (e) { showToast(errText(e, 'Could not remove it'), 'error'); }
  });
  return (
    <View style={{ gap: 8 }} {...tid('book-values')}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>BOOK VALUES · MANUAL ENTRY</Text>
      <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 10 }}>
        {bookValues.length ? bookValues.map((b: any) => (
          <View key={b.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`book-${b.id}`)}>
            <View style={{ flex: 1, gap: 3 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <Chip label={b.source_label} color="#AF52DE" testId={`book-source-${b.id}`} />
                <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary }}>{b.value_type_label}</Text>
              </View>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2}>{[b.note, `${b.entered_by_name || ''} ${when(b.entered_at)}`.trim()].filter(Boolean).join(' · ')}</Text>
            </View>
            <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} {...tid(`book-value-${b.id}`)}>{money(b.value)}</Text>
            <TouchableOpacity onPress={() => start(b)} hitSlop={8} {...tid(`book-edit-${b.id}`)}><Ionicons name="create-outline" size={18} color={GOLD} /></TouchableOpacity>
            <TouchableOpacity onPress={() => remove(b)} hitSlop={8} {...tid(`book-delete-${b.id}`)}><Ionicons name="trash-outline" size={18} color="#FF3B30" /></TouchableOpacity>
          </View>
        )) : !editing ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('book-empty')}>No book values yet. Add Black Book, MMR, J.D. Power or KBB when you have them; each shows next to the market data with its source.</Text> : null}
        {editing ? (
          <View style={{ gap: 10, paddingTop: 6, borderTopWidth: bookValues.length ? 1 : 0, borderTopColor: colors.border }} {...tid('book-form')}>
            <Pick options={sources} value={editing.source} onPick={k => setEditing({ ...editing, source: k })} colors={colors} prefix="book-src" />
            {editing.source === 'other' ? (
              <TextInput value={editing.source_label || ''} onChangeText={t => setEditing({ ...editing, source_label: t })} placeholder="Name the source (e.g. Auction sheet)" placeholderTextColor={colors.textSecondary}
                style={{ height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 12, fontSize: 14 }} {...tid('book-source-label')} />
            ) : null}
            <Pick options={types} value={editing.value_type} onPick={k => setEditing({ ...editing, value_type: k })} colors={colors} prefix="book-type" />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ fontSize: 22, fontWeight: '800', color: colors.textSecondary }}>$</Text>
              <TextInput value={editing.value} onChangeText={t => setEditing({ ...editing, value: t.replace(/[^\d]/g, '').slice(0, 7) })} keyboardType="number-pad" placeholder="24500" placeholderTextColor={colors.textSecondary} autoFocus
                style={{ flex: 1, height: 52, borderRadius: 12, borderWidth: 1.5, borderColor: num > 0 ? GOLD : colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 14, fontSize: 22, fontVariant: ['tabular-nums'] }} {...tid('book-value-input')} />
            </View>
            <TextInput value={editing.note || ''} onChangeText={t => setEditing({ ...editing, note: t })} placeholder="Note (optional): clean, rough, adjusted for miles…" placeholderTextColor={colors.textSecondary}
              style={{ height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 12, fontSize: 14 }} {...tid('book-note-input')} />
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <TouchableOpacity onPress={() => setEditing(null)} style={{ flex: 1, height: 46, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('book-cancel')}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={save} disabled={!(num > 0) || saving || (editing.source === 'other' && !(editing.source_label || '').trim())} style={{ flex: 1, height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: !(num > 0) || saving ? 0.5 : 1 }} {...tid('book-save')}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: '#0B0B0D' }}>{editing.id ? 'Save changes' : 'Add book value'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <TouchableOpacity onPress={() => start()} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 }} {...tid('book-add')}>
            <Ionicons name="add-circle" size={20} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>Add a book value</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};
