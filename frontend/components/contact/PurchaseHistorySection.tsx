/**
 * PurchaseHistorySection — shows all purchases for a contact,
 * with ability to add, edit and delete records.
 *
 * Works for any industry: vehicles, real estate, insurance, anything.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, Modal,
  ScrollView, ActivityIndicator, StyleSheet, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import DateTimePicker from '@react-native-community/datetimepicker';
import { format, parseISO } from 'date-fns';
import api from '../../services/api';

const CATEGORIES = [
  { value: 'vehicle',      label: 'Vehicle',      icon: 'car-outline' },
  { value: 'real_estate',  label: 'Real Estate',  icon: 'home-outline' },
  { value: 'insurance',    label: 'Insurance',    icon: 'shield-outline' },
  { value: 'boat',         label: 'Boat / RV',    icon: 'boat-outline' },
  { value: 'other',        label: 'Other',        icon: 'bag-handle-outline' },
];

interface Purchase {
  id: string;
  title: string;
  category: string;
  date?: string | null;
  notes?: string;
  migrated?: boolean;
}

interface Props {
  contactId: string;
  userId: string;
  colors: any;
}

export default function PurchaseHistorySection({ contactId, userId, colors }: Props) {
  const s = getStyles(colors);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Purchase | null>(null);
  const [saving, setSaving] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);

  // Form state
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('vehicle');
  const [date, setDate] = useState<Date | null>(null);
  const [notes, setNotes] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/contacts/${userId}/${contactId}/purchases`);
      setPurchases(res.data.purchases || []);
    } catch {
      setPurchases([]);
    } finally {
      setLoading(false);
    }
  }, [userId, contactId]);

  useEffect(() => { load(); }, [load]);

  function openAdd() {
    setEditing(null);
    setTitle('');
    setCategory('vehicle');
    setDate(null);
    setNotes('');
    setShowModal(true);
  }

  function openEdit(p: Purchase) {
    setEditing(p);
    setTitle(p.title);
    setCategory(p.category || 'vehicle');
    setDate(p.date ? parseISO(p.date) : null);
    setNotes(p.notes || '');
    setShowModal(true);
  }

  async function save() {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const payload = {
        title: title.trim(),
        category,
        date: date ? date.toISOString().split('T')[0] : null,
        notes: notes.trim(),
      };
      if (editing) {
        await api.put(`/contacts/${userId}/${contactId}/purchases/${editing.id}`, payload);
      } else {
        await api.post(`/contacts/${userId}/${contactId}/purchases`, payload);
      }
      setShowModal(false);
      await load();
    } catch (e: any) {
      console.error('Save purchase error', e);
    } finally {
      setSaving(false);
    }
  }

  async function deletePurchase(p: Purchase) {
    try {
      await api.delete(`/contacts/${userId}/${contactId}/purchases/${p.id}`);
      setPurchases(prev => prev.filter(x => x.id !== p.id));
    } catch {}
  }

  function catIcon(cat: string): string {
    return CATEGORIES.find(c => c.value === cat)?.icon || 'bag-handle-outline';
  }

  if (loading) {
    return (
      <View style={s.section}>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }

  return (
    <View style={s.section}>
      <View style={s.header}>
        <Text style={s.sectionTitle}>Purchase History</Text>
        <TouchableOpacity
          style={s.addBtn}
          onPress={openAdd}
          data-testid="add-purchase-btn"
        >
          <Ionicons name="add" size={16} color="#000" />
          <Text style={s.addBtnText}>Add</Text>
        </TouchableOpacity>
      </View>

      {purchases.length === 0 ? (
        <TouchableOpacity style={s.emptyCard} onPress={openAdd}>
          <Ionicons name="bag-handle-outline" size={22} color={colors.textTertiary} />
          <Text style={s.emptyText}>No purchases yet — tap to add one</Text>
        </TouchableOpacity>
      ) : (
        purchases.map((p, i) => (
          <View key={p.id} style={[s.purchaseRow, i < purchases.length - 1 && s.rowBorder]}>
            <View style={[s.iconWrap, { backgroundColor: colors.accent + '20' }]}>
              <Ionicons name={catIcon(p.category) as any} size={18} color={colors.accent} />
            </View>
            <View style={s.purchaseInfo}>
              <Text style={s.purchaseTitle}>{p.title}</Text>
              {p.date && (
                <Text style={s.purchaseDate}>
                  {(() => { try { return format(parseISO(p.date), 'MMM d, yyyy'); } catch { return p.date; } })()}
                </Text>
              )}
              {p.notes ? <Text style={s.purchaseNotes}>{p.notes}</Text> : null}
            </View>
            <View style={s.purchaseActions}>
              <TouchableOpacity onPress={() => openEdit(p)} style={s.actionBtn} data-testid={`edit-purchase-${p.id}`}>
                <Ionicons name="pencil-outline" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => deletePurchase(p)} style={s.actionBtn} data-testid={`delete-purchase-${p.id}`}>
                <Ionicons name="trash-outline" size={16} color="#FF3B30" />
              </TouchableOpacity>
            </View>
          </View>
        ))
      )}

      {/* Add/Edit Modal */}
      <Modal visible={showModal} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowModal(false)}>
        <View style={[s.modal, { backgroundColor: colors.bg }]}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowModal(false)}>
              <Text style={{ fontSize: 16, color: '#007AFF' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={[s.modalTitle, { color: colors.text }]}>
              {editing ? 'Edit Purchase' : 'Add Purchase'}
            </Text>
            <TouchableOpacity onPress={save} disabled={saving || !title.trim()}>
              {saving
                ? <ActivityIndicator size="small" color="#007AFF" />
                : <Text style={{ fontSize: 16, fontWeight: '700', color: title.trim() ? '#007AFF' : colors.textTertiary }}>Save</Text>
              }
            </TouchableOpacity>
          </View>

          <ScrollView style={{ padding: 16 }} keyboardShouldPersistTaps="handled">
            {/* Category chips */}
            <Text style={s.fieldLabel}>Type</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {CATEGORIES.map(c => (
                  <TouchableOpacity
                    key={c.value}
                    onPress={() => setCategory(c.value)}
                    style={[s.catChip, category === c.value && s.catChipActive]}
                    data-testid={`category-${c.value}`}
                  >
                    <Ionicons name={c.icon as any} size={15} color={category === c.value ? '#000' : colors.textSecondary} />
                    <Text style={[s.catChipText, { color: category === c.value ? '#000' : colors.textSecondary }]}>{c.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>

            {/* Title */}
            <Text style={s.fieldLabel}>What did they purchase?</Text>
            <TextInput
              style={[s.input, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]}
              value={title}
              onChangeText={setTitle}
              placeholder={
                category === 'vehicle' ? 'e.g. 2023 Harley Road Glide' :
                category === 'real_estate' ? 'e.g. 3BR Home at 123 Main St' :
                category === 'insurance' ? 'e.g. 20-Year Term Life Policy' :
                'Describe the purchase...'
              }
              placeholderTextColor={colors.textTertiary}
              autoFocus
              data-testid="purchase-title-input"
            />

            {/* Date */}
            <Text style={[s.fieldLabel, { marginTop: 16 }]}>Purchase Date</Text>
            <TouchableOpacity
              style={[s.datePicker, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => setShowDatePicker(true)}
              data-testid="purchase-date-btn"
            >
              <Ionicons name="calendar-outline" size={18} color={colors.accent} />
              <Text style={{ color: date ? colors.text : colors.textTertiary, fontSize: 16 }}>
                {date ? format(date, 'MMM d, yyyy') : 'Select date'}
              </Text>
              {date && (
                <TouchableOpacity onPress={() => setDate(null)} style={{ marginLeft: 'auto' }}>
                  <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
                </TouchableOpacity>
              )}
            </TouchableOpacity>

            {showDatePicker && (
              <DateTimePicker
                value={date || new Date()}
                mode="date"
                display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                maximumDate={new Date()}
                onChange={(_, d) => { setShowDatePicker(false); if (d) setDate(d); }}
              />
            )}

            {/* Notes */}
            <Text style={[s.fieldLabel, { marginTop: 16 }]}>Notes (optional)</Text>
            <TextInput
              style={[s.input, s.notesInput, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]}
              value={notes}
              onChangeText={setNotes}
              placeholder="Color, trim, VIN, policy #, etc."
              placeholderTextColor={colors.textTertiary}
              multiline
              data-testid="purchase-notes-input"
            />
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  section:       { marginTop: 8, marginBottom: 4 },
  header:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  sectionTitle:  { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8 },
  addBtn:        { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: colors.accent, borderRadius: 14, paddingHorizontal: 10, paddingVertical: 5 },
  addBtnText:    { fontSize: 13, fontWeight: '700', color: '#000' },
  emptyCard:     { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderStyle: 'dashed' },
  emptyText:     { fontSize: 13, color: colors.textTertiary, flex: 1 },
  purchaseRow:   { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 10 },
  rowBorder:     { borderBottomWidth: 1, borderBottomColor: colors.border },
  iconWrap:      { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  purchaseInfo:  { flex: 1 },
  purchaseTitle: { fontSize: 15, fontWeight: '600', color: colors.text, marginBottom: 2 },
  purchaseDate:  { fontSize: 13, color: colors.accent, fontWeight: '500' },
  purchaseNotes: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  purchaseActions: { flexDirection: 'row', gap: 4, alignItems: 'center' },
  actionBtn:     { padding: 6 },
  modal:         { flex: 1 },
  modalHeader:   { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border },
  modalTitle:    { fontSize: 16, fontWeight: '700' },
  fieldLabel:    { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 },
  input:         { borderRadius: 12, borderWidth: 1, padding: 14, fontSize: 16 },
  notesInput:    { minHeight: 80, textAlignVertical: 'top', paddingTop: 12 },
  datePicker:    { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, borderWidth: 1, padding: 14 },
  catChip:       { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  catChipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  catChipText:   { fontSize: 13, fontWeight: '600' },
});
