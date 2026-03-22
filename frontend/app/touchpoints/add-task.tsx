import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, ActivityIndicator, FlatList, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { tasksAPI, contactsAPI } from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const PRIORITIES = [
  { key: 'high', label: 'High', selClass: 'rgba(255,59,48,0.1)', selColor: '#FF3B30', selBorder: 'rgba(255,59,48,0.3)' },
  { key: 'medium', label: 'Medium', selClass: 'rgba(255,255,255,0.03)', selColor: '#636366', selBorder: '#2C2C2E' },
  { key: 'low', label: 'Low', selClass: 'rgba(142,142,147,0.08)', selColor: '#8E8E93', selBorder: '#3A3A3C' },
];
const ACTIONS = [
  { key: 'call', label: 'Call', icon: 'call' },
  { key: 'text', label: 'Text', icon: 'chatbubble' },
  { key: 'email', label: 'Email', icon: 'mail' },
  { key: 'card', label: 'Card', icon: 'gift' },
  { key: 'other', label: 'Other', icon: 'create-outline' },
];

function getInitials(name: string) {
  const parts = (name || '?').split(' ').filter(Boolean);
  return (parts[0]?.[0] || '?').toUpperCase() + (parts[1]?.[0] || '').toUpperCase();
}

export default function AddTaskScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const params = useLocalSearchParams<{ contactId?: string; contactName?: string; contactPhone?: string }>();
  const user = useAuthStore((s) => s.user);

  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [priority, setPriority] = useState('high');
  const [actionType, setActionType] = useState('call');
  const [saving, setSaving] = useState(false);

  // Contact
  const [contact, setContact] = useState<{ id: string; name: string; phone: string } | null>(null);
  const [showContactPicker, setShowContactPicker] = useState(false);
  const [contactsList, setContactsList] = useState<any[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  const [contactsLoading, setContactsLoading] = useState(false);

  // Date/Time
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(9, 0, 0, 0);
  const [dueDate, setDueDate] = useState(tomorrow);

  useEffect(() => {
    if (params.contactId) {
      setContact({ id: params.contactId, name: params.contactName || '', phone: params.contactPhone || '' });
    }
  }, [params.contactId]);

  const loadContacts = async () => {
    if (!user?._id) return;
    setContactsLoading(true);
    try {
      const data = await contactsAPI.getAll(user._id);
      setContactsList(data || []);
    } catch {}
    setContactsLoading(false);
  };

  const filteredContacts = contactsList.filter(c => {
    const q = contactSearch.toLowerCase();
    if (!q) return true;
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q) || (c.phone || '').includes(q);
  });

  const handleSave = async () => {
    if (!title.trim()) { showSimpleAlert('Required', 'Please enter what needs to be done.'); return; }
    if (!user?._id) return;
    setSaving(true);
    try {
      await tasksAPI.create(user._id, {
        title: title.trim(),
        description: notes.trim(),
        contact_id: contact?.id || '',
        contact_name: contact?.name || '',
        contact_phone: contact?.phone || '',
        priority,
        action_type: actionType,
        due_date: dueDate.toISOString(),
        type: 'manual',
      });
      router.replace('/touchpoints' as any);
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to create task');
    }
    setSaving(false);
  };

  const formatDate = (d: Date) => {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const tom = new Date(today); tom.setDate(tom.getDate() + 1);
    const dayStr = d.toDateString() === today.toDateString() ? 'Today' : d.toDateString() === tom.toDateString() ? 'Tomorrow' : '';
    const dateStr = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    return dayStr ? `${dayStr}, ${dateStr}` : dateStr;
  };
  const formatTime = (d: Date) => d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4, marginRight: 8 }} data-testid="add-task-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1 }}>Add Task</Text>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
        {/* Contact */}
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>CONTACT</Text>
        <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          {contact ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, paddingHorizontal: 16 }}>
              <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(201,169,98,0.12)', alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ fontWeight: '700', fontSize: 16, color: colors.accent }}>{getInitials(contact.name)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>{contact.name}</Text>
                {contact.phone ? <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 1 }}>{contact.phone}</Text> : null}
              </View>
              <TouchableOpacity onPress={() => { setShowContactPicker(true); loadContacts(); }} data-testid="change-contact-btn">
                <Text style={{ fontSize: 15, color: colors.accent, fontWeight: '600' }}>Change</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity onPress={() => { setShowContactPicker(true); loadContacts(); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, paddingHorizontal: 16 }} data-testid="select-contact-btn">
              <Ionicons name="person-add-outline" size={20} color={colors.accent} />
              <Text style={{ flex: 1, fontSize: 18, color: '#48484A' }}>Select a contact</Text>
              <Text style={{ fontSize: 15, color: colors.accent, fontWeight: '600' }}>Choose</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Task Details */}
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>TASK DETAILS</Text>
        <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          <TextInput
            style={{ padding: 14, paddingHorizontal: 16, fontSize: 18, color: colors.text }}
            placeholder="What needs to be done?"
            placeholderTextColor="#48484A"
            value={title}
            onChangeText={setTitle}
            data-testid="task-title-input"
          />
          <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 16 }} />
          <TextInput
            style={{ padding: 14, paddingHorizontal: 16, fontSize: 16, color: colors.text }}
            placeholder="Notes (optional)"
            placeholderTextColor="#48484A"
            value={notes}
            onChangeText={setNotes}
            data-testid="task-notes-input"
          />
        </View>

        {/* When */}
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>WHEN</Text>
        <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', padding: 12, paddingHorizontal: 16, gap: 10 }}>
            <Ionicons name="calendar-outline" size={20} color={colors.accent} />
            <Text style={{ flex: 1, fontSize: 18, color: colors.text }}>{formatDate(dueDate)}</Text>
            <TouchableOpacity onPress={() => {
              const next = new Date(dueDate);
              next.setDate(next.getDate() + 1);
              setDueDate(next);
            }} data-testid="change-date-btn">
              <Text style={{ fontSize: 15, color: colors.accent, fontWeight: '600' }}>Change</Text>
            </TouchableOpacity>
          </View>
          <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 16 }} />
          <View style={{ flexDirection: 'row', alignItems: 'center', padding: 12, paddingHorizontal: 16, gap: 10 }}>
            <Ionicons name="time-outline" size={20} color={colors.accent} />
            <Text style={{ flex: 1, fontSize: 18, color: colors.text }}>{formatTime(dueDate)}</Text>
            <TouchableOpacity onPress={() => {
              const next = new Date(dueDate);
              next.setHours(next.getHours() + 1);
              setDueDate(next);
            }} data-testid="change-time-btn">
              <Text style={{ fontSize: 15, color: colors.accent, fontWeight: '600' }}>Change</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Priority */}
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>PRIORITY</Text>
        <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          <View style={{ flexDirection: 'row', gap: 8, padding: 12, paddingHorizontal: 16 }}>
            {PRIORITIES.map(p => {
              const sel = priority === p.key;
              return (
                <TouchableOpacity
                  key={p.key}
                  onPress={() => setPriority(p.key)}
                  style={{
                    flex: 1, padding: 10, borderRadius: 10, alignItems: 'center', borderWidth: 1,
                    backgroundColor: sel ? p.selClass : 'rgba(255,255,255,0.03)',
                    borderColor: sel ? p.selBorder : colors.border,
                  }}
                  data-testid={`priority-${p.key}`}
                >
                  <Text style={{ fontSize: 16, fontWeight: '600', color: sel ? p.selColor : '#636366' }}>{p.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* Action Type */}
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }}>PRIMARY ACTION</Text>
        <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
          <View style={{ flexDirection: 'row', gap: 8, padding: 12, paddingHorizontal: 16 }}>
            {ACTIONS.map(a => {
              const sel = actionType === a.key;
              return (
                <TouchableOpacity
                  key={a.key}
                  onPress={() => setActionType(a.key)}
                  style={{
                    flex: 1, padding: 10, paddingVertical: 10, borderRadius: 10, alignItems: 'center', borderWidth: 1,
                    backgroundColor: sel ? 'rgba(201,169,98,0.1)' : 'rgba(255,255,255,0.03)',
                    borderColor: sel ? 'rgba(201,169,98,0.3)' : colors.border,
                  }}
                  data-testid={`action-${a.key}`}
                >
                  <Ionicons name={a.icon as any} size={20} color={sel ? colors.accent : '#636366'} style={{ marginBottom: 3 }} />
                  <Text style={{ fontSize: 13, fontWeight: '600', color: sel ? colors.accent : '#636366' }}>{a.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* Save */}
        <TouchableOpacity
          onPress={handleSave}
          disabled={saving}
          style={{ marginHorizontal: 16, marginTop: 24, padding: 16, borderRadius: 14, backgroundColor: colors.accent, alignItems: 'center' }}
          activeOpacity={0.8}
          data-testid="save-task-btn"
        >
          {saving ? <ActivityIndicator color="#000" /> : <Text style={{ fontSize: 18, fontWeight: '700', color: '#000' }}>Save Task</Text>}
        </TouchableOpacity>
        <Text style={{ fontSize: 14, color: '#48484A', textAlign: 'center', padding: 8, paddingHorizontal: 16 }}>Task will appear in Today's Touchpoints on the due date</Text>
      </ScrollView>

      {/* Contact Picker Modal */}
      <Modal visible={showContactPicker} animationType="slide" transparent={false}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
            <TouchableOpacity onPress={() => setShowContactPicker(false)} style={{ padding: 4 }} data-testid="contact-picker-back">
              <Ionicons name="chevron-back" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' }}>Select Contact</Text>
            <View style={{ width: 32 }} />
          </View>
          <View style={{ paddingHorizontal: 16, paddingVertical: 8 }}>
            <TextInput
              style={{ backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, fontSize: 17, color: colors.text }}
              placeholder="Search contacts..."
              placeholderTextColor={colors.textTertiary}
              value={contactSearch}
              onChangeText={setContactSearch}
              autoFocus
              data-testid="contact-picker-search"
            />
          </View>
          {contactsLoading ? <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} /> : (
            <FlatList
              data={filteredContacts}
              keyExtractor={(item) => item._id}
              style={{ flex: 1, paddingHorizontal: 16 }}
              renderItem={({ item }) => {
                const name = `${item.first_name || ''} ${item.last_name || ''}`.trim() || item.phone || 'Unknown';
                return (
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 0.5, borderBottomColor: colors.border, gap: 10 }}
                    onPress={() => {
                      setContact({ id: item._id, name, phone: item.phone || '' });
                      setShowContactPicker(false);
                      setContactSearch('');
                    }}
                    data-testid={`pick-contact-${item._id}`}
                  >
                    <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: `${colors.accent}20`, alignItems: 'center', justifyContent: 'center' }}>
                      <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 16 }}>{getInitials(name)}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{name}</Text>
                      {item.phone ? <Text style={{ fontSize: 14, color: colors.textSecondary }}>{item.phone}</Text> : null}
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                );
              }}
              ListEmptyComponent={<Text style={{ textAlign: 'center', color: colors.textSecondary, marginTop: 24, fontSize: 16 }}>{contactSearch ? 'No contacts found' : 'No contacts yet'}</Text>}
            />
          )}
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}
