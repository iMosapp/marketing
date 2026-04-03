import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { tasksAPI, contactsAPI } from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';

export default function NewTaskScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [task, setTask] = useState({
    type: 'callback' as 'callback' | 'follow_up' | 'appointment' | 'other',
    title: '',
    description: '',
    contact: null as { id: string; name: string } | null,
    dueDate: new Date(),
    dueTime: '10:00',
    priority: 'medium' as 'low' | 'medium' | 'high',
  });
  
  const [saving, setSaving] = useState(false);

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<any>(null);

  // Contact search state
  const [showContactSearch, setShowContactSearch] = useState(false);
  const [contactQuery, setContactQuery] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);

  // Date picker state
  const [showDatePicker, setShowDatePicker] = useState(false);
  
  const taskTypes = [
    { id: 'callback', name: 'Call Back', icon: 'call', color: '#007AFF' },
    { id: 'follow_up', name: 'Follow Up', icon: 'chatbubble', color: '#34C759' },
    { id: 'appointment', name: 'Appointment', icon: 'calendar', color: '#FF9500' },
    { id: 'other', name: 'Other', icon: 'checkmark-circle', color: colors.textSecondary },
  ];

  // Voice recording functions
  const startRecording = async () => {
    if (!IS_WEB) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = () => { stream.getTracks().forEach(t => t.stop()); };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => setRecordingSeconds(s => s + 1), 1000);
    } catch (err) {
      showSimpleAlert('Error', 'Microphone access denied. Please allow microphone access.');
    }
  };

  const stopAndTranscribe = async () => {
    if (!mediaRecorderRef.current) return;
    clearInterval(timerRef.current);
    setIsRecording(false);
    setIsTranscribing(true);

    const recorder = mediaRecorderRef.current;
    const blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        recorder.stream.getTracks().forEach(t => t.stop());
        resolve(new Blob(chunksRef.current, { type: 'audio/webm' }));
      };
      recorder.stop();
    });

    try {
      // Step 1: Transcribe
      const formData = new FormData();
      formData.append('file', blob, 'task-voice.webm');
      const transcribeResp = await api.post('/voice/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const transcribedText = transcribeResp.data?.text;
      if (!transcribedText) {
        showSimpleAlert('Error', 'Could not transcribe audio. Please try again or type manually.');
        setIsTranscribing(false);
        return;
      }

      // Step 2: Parse task details with AI
      const parseResp = await api.post('/voice/parse-task', { text: transcribedText });
      const parsed = parseResp.data;

      // Update task state with parsed fields
      setTask(prev => ({
        ...prev,
        title: parsed.title || prev.title,
        description: parsed.description || prev.description,
        type: (['callback', 'follow_up', 'appointment', 'other'].includes(parsed.type) ? parsed.type : prev.type) as any,
        priority: (['low', 'medium', 'high'].includes(parsed.priority) ? parsed.priority : prev.priority) as any,
        dueDate: parsed.due_date ? new Date(parsed.due_date) : prev.dueDate,
        dueTime: parsed.due_time || prev.dueTime,
      }));
    } catch (err) {
      console.error('Voice task error:', err);
      showSimpleAlert('Error', 'Failed to process voice input. Please try again.');
    } finally {
      setIsTranscribing(false);
    }
  };

  // Contact search
  const loadContacts = async () => {
    if (!user) return;
    setContactsLoading(true);
    try {
      const data = await contactsAPI.getAll(user._id);
      setContacts(Array.isArray(data) ? data : (data?.contacts || []));
    } catch {}
    setContactsLoading(false);
  };

  const filteredContacts = contacts.filter(c => {
    const q = contactQuery.toLowerCase();
    if (!q) return true;
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q) || (c.phone || '').includes(q) || (c.email || '').toLowerCase().includes(q) || `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase().includes(q);
  });
  
  const handleSave = async () => {
    if (!task.title) {
      showSimpleAlert('Error', 'Please enter a task title');
      return;
    }
    if (!user) {
      showSimpleAlert('Error', 'Please log in to create tasks');
      return;
    }
    try {
      setSaving(true);
      const [hours, minutes] = task.dueTime.split(':');
      const dueDateTime = new Date(task.dueDate);
      dueDateTime.setHours(parseInt(hours), parseInt(minutes));
      const taskData = {
        type: task.type,
        title: task.title,
        description: task.description,
        contact_id: task.contact?.id,
        due_date: dueDateTime,
        priority: task.priority,
      };
      await tasksAPI.create(user._id, taskData);
      showAlert('Success', 'Task created!', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Failed to create task';
      showSimpleAlert('Error', errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const formatSecs = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  // Simple date options
  const dateOptions = [
    { label: 'Today', date: new Date() },
    { label: 'Tomorrow', date: (() => { const d = new Date(); d.setDate(d.getDate() + 1); return d; })() },
    { label: 'In 2 Days', date: (() => { const d = new Date(); d.setDate(d.getDate() + 2); return d; })() },
    { label: 'In 3 Days', date: (() => { const d = new Date(); d.setDate(d.getDate() + 3); return d; })() },
    { label: 'Next Week', date: (() => { const d = new Date(); d.setDate(d.getDate() + 7); return d; })() },
    { label: 'In 2 Weeks', date: (() => { const d = new Date(); d.setDate(d.getDate() + 14); return d; })() },
  ];
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="new-task-back-btn">
          <Ionicons name="close" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>New Task</Text>
        <TouchableOpacity onPress={handleSave} style={styles.saveButton} disabled={saving} data-testid="new-task-save-btn">
          {saving ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <Text style={styles.saveButtonText}>Create</Text>
          )}
        </TouchableOpacity>
      </View>
      
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Voice Input */}
        <View style={styles.voiceSection} data-testid="voice-task-section">
          {isTranscribing ? (
            <View style={styles.voiceProcessing}>
              <ActivityIndicator size="small" color="#C9A962" />
              <Text style={[styles.voiceProcessingText, { color: colors.textSecondary }]}>Processing voice...</Text>
            </View>
          ) : isRecording ? (
            <TouchableOpacity style={styles.voiceRecordingBtn} onPress={stopAndTranscribe} data-testid="voice-stop-btn">
              <View style={styles.recordingPulse}>
                <Ionicons name="stop" size={20} color="#FFF" />
              </View>
              <Text style={styles.recordingText}>Recording {formatSecs(recordingSeconds)}...</Text>
              <Text style={[styles.recordingHint, { color: colors.textTertiary }]}>Tap to stop</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={[styles.voiceBtn, { backgroundColor: colors.card, borderColor: colors.border }]} onPress={startRecording} data-testid="voice-start-btn">
              <Ionicons name="mic" size={22} color="#C9A962" />
              <View style={{ flex: 1 }}>
                <Text style={[styles.voiceBtnText, { color: colors.text }]}>Add task by voice</Text>
                <Text style={[styles.voiceBtnHint, { color: colors.textTertiary }]}>Speak the task details and AI will fill in the fields</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
            </TouchableOpacity>
          )}
        </View>

        {/* Task Type */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Task Type</Text>
          <View style={styles.typeGrid}>
            {taskTypes.map((type) => (
              <TouchableOpacity
                key={type.id}
                style={[styles.typeCard, task.type === type.id && styles.typeCardActive, { borderColor: task.type === type.id ? type.color : colors.surface }]}
                onPress={() => setTask({ ...task, type: type.id as any })}
                data-testid={`task-type-${type.id}`}
              >
                <Ionicons name={type.icon as any} size={28} color={task.type === type.id ? type.color : colors.textSecondary} />
                <Text style={[styles.typeName, task.type === type.id && { color: type.color }]}>{type.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
        
        {/* Title */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Title</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., Call John about test drive"
            placeholderTextColor={colors.textSecondary}
            value={task.title}
            onChangeText={(text) => setTask({ ...task, title: text })}
            data-testid="task-title-input"
          />
        </View>
        
        {/* Description */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Description (Optional)</Text>
          <TextInput
            style={styles.textArea}
            placeholder="Add details..."
            placeholderTextColor={colors.textSecondary}
            value={task.description}
            onChangeText={(text) => setTask({ ...task, description: text })}
            multiline
            numberOfLines={4}
            textAlignVertical="top"
            data-testid="task-description-input"
          />
        </View>
        
        {/* Contact */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Related Contact (Optional)</Text>
          <TouchableOpacity
            style={styles.selectButton}
            onPress={() => { setShowContactSearch(true); loadContacts(); }}
            data-testid="task-contact-select"
          >
            <Ionicons name="person" size={20} color="#007AFF" />
            <Text style={[styles.selectButtonText, !task.contact && { color: colors.textSecondary }]}>
              {task.contact ? task.contact.name : 'Search by name, phone, or email'}
            </Text>
            {task.contact ? (
              <TouchableOpacity onPress={() => setTask({ ...task, contact: null })} data-testid="task-contact-clear">
                <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
              </TouchableOpacity>
            ) : (
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            )}
          </TouchableOpacity>
        </View>
        
        {/* Due Date & Time */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Due Date & Time</Text>
          <TouchableOpacity
            style={[styles.input, styles.dateButton]}
            onPress={() => setShowDatePicker(!showDatePicker)}
            data-testid="task-date-btn"
          >
            <Ionicons name="calendar" size={20} color="#007AFF" />
            <Text style={styles.dateText}>
              {task.dueDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
            </Text>
            <View style={{ flex: 1 }} />
            <TextInput
              style={[styles.timeInputInline, { color: colors.text }]}
              placeholder="10:00"
              placeholderTextColor={colors.textSecondary}
              value={task.dueTime}
              onChangeText={(text) => setTask({ ...task, dueTime: text })}
              data-testid="task-time-input"
            />
          </TouchableOpacity>
          {showDatePicker && (
            <View style={styles.dateOptions}>
              {dateOptions.map((opt) => (
                <TouchableOpacity
                  key={opt.label}
                  style={[styles.dateChip, task.dueDate.toDateString() === opt.date.toDateString() && styles.dateChipActive]}
                  onPress={() => { setTask({ ...task, dueDate: opt.date }); setShowDatePicker(false); }}
                  data-testid={`date-option-${opt.label.toLowerCase().replace(/\s/g, '-')}`}
                >
                  <Text style={[styles.dateChipText, task.dueDate.toDateString() === opt.date.toDateString() && styles.dateChipTextActive]}>{opt.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>
        
        {/* Priority */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Priority</Text>
          <View style={styles.priorityRow}>
            {(['low', 'medium', 'high'] as const).map((priority) => (
              <TouchableOpacity
                key={priority}
                style={[styles.priorityButton, task.priority === priority && styles.priorityButtonActive]}
                onPress={() => setTask({ ...task, priority })}
                data-testid={`task-priority-${priority}`}
              >
                <View style={[styles.priorityDot, { backgroundColor: priority === 'high' ? '#FF3B30' : priority === 'medium' ? '#FF9500' : colors.textSecondary }]} />
                <Text style={[styles.priorityText, task.priority === priority && styles.priorityTextActive]}>
                  {priority.charAt(0).toUpperCase() + priority.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </ScrollView>

      {/* Contact Search Modal */}
      {showContactSearch && (
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: colors.bg }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Select Contact</Text>
              <TouchableOpacity onPress={() => setShowContactSearch(false)} data-testid="contact-search-close">
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
            </View>
            <TextInput
              style={[styles.searchInput, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
              placeholder="Search by name, phone, or email..."
              placeholderTextColor={colors.textTertiary}
              value={contactQuery}
              onChangeText={setContactQuery}
              autoFocus
              data-testid="contact-search-input"
            />
            <ScrollView style={styles.contactList}>
              {contactsLoading ? (
                <ActivityIndicator size="small" color="#007AFF" style={{ marginTop: 20 }} />
              ) : filteredContacts.length === 0 ? (
                <Text style={[styles.emptyText, { color: colors.textSecondary }]}>No contacts found</Text>
              ) : (
                filteredContacts.slice(0, 50).map((c) => (
                  <TouchableOpacity
                    key={c._id || c.id}
                    style={[styles.contactRow, { borderBottomColor: colors.border }]}
                    onPress={() => {
                      setTask({ ...task, contact: { id: c._id || c.id, name: `${c.first_name || ''} ${c.last_name || ''}`.trim() } });
                      setShowContactSearch(false);
                      setContactQuery('');
                    }}
                    data-testid={`contact-option-${c._id || c.id}`}
                  >
                    <View style={styles.contactAvatar}>
                      <Text style={styles.contactAvatarText}>{(c.first_name || '?')[0]}{(c.last_name || '')[0] || ''}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.contactName, { color: colors.text }]}>{c.first_name} {c.last_name}</Text>
                      {c.phone && <Text style={[styles.contactDetail, { color: colors.textTertiary }]}>{c.phone}</Text>}
                      {c.email && <Text style={[styles.contactDetail, { color: colors.textTertiary }]}>{c.email}</Text>}
                    </View>
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.surface },
  backButton: { padding: 4 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  saveButton: { padding: 4 },
  saveButtonText: { fontSize: 18, fontWeight: '600', color: '#007AFF' },
  scrollContent: { padding: 16 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: colors.textSecondary, marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.5 },

  // Voice section
  voiceSection: { marginBottom: 24 },
  voiceBtn: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, borderRadius: 12, borderWidth: 1 },
  voiceBtnText: { fontSize: 17, fontWeight: '600' },
  voiceBtnHint: { fontSize: 14, marginTop: 2 },
  voiceRecordingBtn: { alignItems: 'center', padding: 20, borderRadius: 12, backgroundColor: 'rgba(255,59,48,0.08)', borderWidth: 1, borderColor: 'rgba(255,59,48,0.3)' },
  recordingPulse: { width: 48, height: 48, borderRadius: 24, backgroundColor: '#FF3B30', justifyContent: 'center', alignItems: 'center', marginBottom: 8 },
  recordingText: { fontSize: 18, fontWeight: '600', color: '#FF3B30' },
  recordingHint: { fontSize: 14, marginTop: 4 },
  voiceProcessing: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, padding: 20, borderRadius: 12, backgroundColor: 'rgba(201,169,98,0.08)', borderWidth: 1, borderColor: 'rgba(201,169,98,0.3)' },
  voiceProcessingText: { fontSize: 16, fontWeight: '500' },

  // Task types
  typeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  typeCard: { flex: 1, minWidth: 140, backgroundColor: colors.card, borderRadius: 12, padding: 16, alignItems: 'center', borderWidth: 2, borderColor: colors.surface },
  typeCardActive: { borderWidth: 2 },
  typeName: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, marginTop: 6 },

  // Inputs
  input: { backgroundColor: colors.card, borderRadius: 12, padding: 16, fontSize: 18, color: colors.text, borderWidth: 1, borderColor: colors.surface },
  textArea: { backgroundColor: colors.card, borderRadius: 12, padding: 16, fontSize: 18, color: colors.text, borderWidth: 1, borderColor: colors.surface, height: 100 },
  selectButton: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: colors.surface, gap: 12 },
  selectButtonText: { flex: 1, fontSize: 18, color: colors.text },

  // Date
  dateButton: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  dateText: { fontSize: 18, color: colors.text },
  timeInputInline: { fontSize: 18, fontWeight: '600', textAlign: 'right', width: 60 },
  dateOptions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  dateChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.surface },
  dateChipActive: { backgroundColor: '#007AFF', borderColor: '#007AFF' },
  dateChipText: { fontSize: 15, fontWeight: '500', color: colors.textSecondary },
  dateChipTextActive: { color: '#FFF' },

  // Priority
  priorityRow: { flexDirection: 'row', gap: 12 },
  priorityButton: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: colors.card, borderRadius: 12, padding: 12, gap: 8, borderWidth: 1, borderColor: colors.surface },
  priorityButtonActive: { backgroundColor: colors.surface, borderColor: '#007AFF' },
  priorityDot: { width: 10, height: 10, borderRadius: 5 },
  priorityText: { fontSize: 16, fontWeight: '600', color: colors.textSecondary },
  priorityTextActive: { color: colors.text },

  // Contact Search Modal
  modalOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 100 },
  modalContent: { flex: 1, marginTop: 60, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 19, fontWeight: '700' },
  searchInput: { borderRadius: 10, padding: 12, fontSize: 18, borderWidth: 1, marginBottom: 12 },
  contactList: { flex: 1 },
  contactRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, gap: 12 },
  contactAvatar: { width: 40, height: 40, borderRadius: 10, backgroundColor: '#007AFF', justifyContent: 'center', alignItems: 'center' },
  contactAvatarText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
  contactName: { fontSize: 17, fontWeight: '600' },
  contactDetail: { fontSize: 14, marginTop: 1 },
  emptyText: { textAlign: 'center', marginTop: 20, fontSize: 16 },
});
