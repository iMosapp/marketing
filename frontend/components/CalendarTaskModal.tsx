/**
 * CalendarTaskModal — create a task/appointment straight from the Calendar screen.
 */
import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';
import { showSimpleAlert } from '../services/alert';
import { DateTimeField, ApptTypeRow } from './DateTimeField';

const GOLD = '#C9A962';

export default function CalendarTaskModal({ visible, onClose, colors, userId, defaultDate, onSaved }: any) {
  const [title, setTitle] = useState('');
  const [apptType, setApptType] = useState<string | null>(null);
  const [date, setDate] = useState<Date>(defaultDate || new Date());
  const [time, setTime] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [contact, setContact] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (visible) {
      setDate(defaultDate || new Date());
      setTitle(''); setTime(null); setApptType(null);
      setQuery(''); setResults([]); setContact(null);
    }
  }, [visible]);

  useEffect(() => {
    if (!query.trim() || query.trim().length < 2 || contact) { setResults([]); return; }
    let alive = true;
    const t = setTimeout(() => {
      api.get(`/contacts/${userId}?search=${encodeURIComponent(query.trim())}&limit=5`)
        .then(r => { if (alive) setResults(r.data?.contacts || r.data || []); })
        .catch(() => {});
    }, 250);
    return () => { alive = false; clearTimeout(t); };
  }, [query, contact, userId]);

  const save = async () => {
    if (!title.trim() || saving) return;
    setSaving(true);
    try {
      const due = new Date(date);
      if (time) { const [h, m] = time.split(':').map(Number); due.setHours(h, m, 0, 0); }
      else due.setHours(9, 0, 0, 0);
      await api.post(`/tasks/${userId}`, {
        title: title.trim(),
        contact_id: contact?._id || '',
        contact_name: contact ? `${contact.first_name || ''} ${contact.last_name || ''}`.trim() : '',
        contact_phone: contact?.phone || '',
        due_date: due.toISOString(),
        has_time: !!time,
        appointment_type: apptType,
        type: apptType ? 'appointment' : 'manual',
        priority: 'medium',
      });
      onSaved?.();
      onClose();
    } catch {
      showSimpleAlert('Error', 'Could not save. Try again.');
    } finally {
      setSaving(false);
    }
  };

  const label = { fontSize: 13, fontWeight: '700' as const, color: colors.textSecondary, textTransform: 'uppercase' as const, letterSpacing: 0.5, marginBottom: 8, marginTop: 16 };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border }}>
          <TouchableOpacity onPress={onClose} testID="cal-task-cancel" dataSet={{ testid: 'cal-task-cancel' } as any}>
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 17, color: GOLD }}>Cancel</Text>
          </TouchableOpacity>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>New Task</Text>
          <TouchableOpacity onPress={save} disabled={saving || !title.trim()} testID="cal-task-save" dataSet={{ testid: 'cal-task-save' } as any}>
            {saving ? <ActivityIndicator size="small" color={GOLD} /> : (
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 17, fontWeight: '700', color: title.trim() ? GOLD : colors.textTertiary }}>Save</Text>
            )}
          </TouchableOpacity>
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 48 }} keyboardShouldPersistTaps="handled">
          <Text maxFontSizeMultiplier={1.0} style={[label, { marginTop: 0 }]}>What do you need to do?</Text>
          <TextInput
            style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 17, color: colors.text, borderWidth: 1, borderColor: colors.border }}
            placeholder="e.g. Call Sam to follow up"
            placeholderTextColor={colors.textTertiary}
            value={title}
            onChangeText={setTitle}
            autoFocus
            returnKeyType="done"
            maxFontSizeMultiplier={1.0}
            testID="cal-task-title"
            dataSet={{ testid: 'cal-task-title' } as any}
          />

          <Text maxFontSizeMultiplier={1.0} style={label}>Appointment type <Text style={{ fontWeight: '400', textTransform: 'none' }}>(optional)</Text></Text>
          <ApptTypeRow colors={colors} value={apptType} onChange={setApptType} />

          <Text maxFontSizeMultiplier={1.0} style={label}>When?</Text>
          <DateTimeField colors={colors} date={date} setDate={setDate} time={time} setTime={setTime} />

          <Text maxFontSizeMultiplier={1.0} style={label}>Contact <Text style={{ fontWeight: '400', textTransform: 'none' }}>(optional)</Text></Text>
          {contact ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 10, padding: 12 }}>
              <Ionicons name="person-circle" size={20} color={GOLD} />
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, color: colors.text, fontWeight: '600', flex: 1 }}>
                {`${contact.first_name || ''} ${contact.last_name || ''}`.trim()}
              </Text>
              <TouchableOpacity onPress={() => { setContact(null); setQuery(''); }} testID="cal-task-clear-contact" dataSet={{ testid: 'cal-task-clear-contact' } as any}>
                <Ionicons name="close-circle" size={20} color={colors.textTertiary} />
              </TouchableOpacity>
            </View>
          ) : (
            <>
              <TextInput
                style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border }}
                placeholder="Search contacts..."
                placeholderTextColor={colors.textTertiary}
                value={query}
                onChangeText={setQuery}
                maxFontSizeMultiplier={1.0}
                testID="cal-task-contact-search"
                dataSet={{ testid: 'cal-task-contact-search' } as any}
              />
              {results.map((c: any) => (
                <TouchableOpacity
                  key={c._id}
                  onPress={() => { setContact(c); setResults([]); }}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, paddingHorizontal: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}
                  testID={`cal-task-contact-${c._id}`}
                  dataSet={{ testid: `cal-task-contact-${c._id}` } as any}
                >
                  <Ionicons name="person" size={15} color={colors.textSecondary} />
                  <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 15, color: colors.text }}>
                    {`${c.first_name || ''} ${c.last_name || ''}`.trim()}
                  </Text>
                </TouchableOpacity>
              ))}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}
