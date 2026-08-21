/**
 * AddTaskModal — quick task creation for a contact.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

export default function AddTaskModal(props: any) {
  const {
    colors, visible, onClose, contact,
    newTaskTitle, setNewTaskTitle, newTaskNotes, setNewTaskNotes,
    newTaskDue, setNewTaskDue, newTaskPriority, setNewTaskPriority,
    savingTask, handleSaveTask,
  } = props;

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border }}>
          <TouchableOpacity onPress={onClose}>
            <Text style={{ fontSize: 17, color: '#007AFF' }}>Cancel</Text>
          </TouchableOpacity>
          <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Add Task</Text>
          <TouchableOpacity onPress={handleSaveTask} disabled={savingTask || !newTaskTitle.trim()} data-testid="save-task-btn">
            {savingTask ? <ActivityIndicator size="small" color="#007AFF" /> : (
              <Text style={{ fontSize: 17, fontWeight: '700', color: newTaskTitle.trim() ? '#007AFF' : colors.textTertiary }}>Save</Text>
            )}
          </TouchableOpacity>
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
          {/* Contact badge */}
          {contact && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 10, padding: 12, marginBottom: 16 }}>
              <Ionicons name="person-circle" size={20} color="#007AFF" />
              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '600' }}>
                {`${contact.first_name || ''} ${contact.last_name || ''}`.trim()}
              </Text>
            </View>
          )}

          {/* Task title */}
          <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>What do you need to do?</Text>
          <TextInput
            style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 17, color: colors.text, borderWidth: 1, borderColor: colors.border, marginBottom: 16 }}
            placeholder={`e.g. Text ${contact?.first_name || 'them'} about Friday's conversation`}
            placeholderTextColor={colors.textTertiary}
            value={newTaskTitle}
            onChangeText={setNewTaskTitle}
            autoFocus
            returnKeyType="done"
            data-testid="task-title-input"
          />

          {/* Due date */}
          <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>When?</Text>
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            {([
              { key: 'today',    label: 'Today' },
              { key: 'tomorrow', label: 'Tomorrow' },
              { key: 'thisweek', label: 'This Week' },
            ] as const).map(opt => (
              <TouchableOpacity
                key={opt.key}
                onPress={() => setNewTaskDue(opt.key)}
                style={{ paddingHorizontal: 18, paddingVertical: 10, borderRadius: 20, borderWidth: 1.5,
                  borderColor: newTaskDue === opt.key ? '#FF9500' : colors.border,
                  backgroundColor: newTaskDue === opt.key ? '#FF950020' : colors.card }}
              >
                <Text style={{ fontSize: 15, fontWeight: '600', color: newTaskDue === opt.key ? '#FF9500' : colors.text }}>{opt.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Priority */}
          <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>Priority</Text>
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
            {([
              { key: 'low',    label: 'Low',    color: '#34C759' },
              { key: 'medium', label: 'Medium', color: '#FF9500' },
              { key: 'high',   label: 'High',   color: '#FF3B30' },
            ] as const).map(p => (
              <TouchableOpacity
                key={p.key}
                onPress={() => setNewTaskPriority(p.key)}
                style={{ flex: 1, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5, alignItems: 'center',
                  borderColor: newTaskPriority === p.key ? p.color : colors.border,
                  backgroundColor: newTaskPriority === p.key ? p.color + '20' : colors.card }}
              >
                <Text style={{ fontSize: 14, fontWeight: '600', color: newTaskPriority === p.key ? p.color : colors.text }}>{p.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Notes */}
          <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>Notes <Text style={{ fontWeight: '400', textTransform: 'none' }}>(optional)</Text></Text>
          <TextInput
            style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14, fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border, minHeight: 80, textAlignVertical: 'top' }}
            placeholder="Any context or details..."
            placeholderTextColor={colors.textTertiary}
            value={newTaskNotes}
            onChangeText={setNewTaskNotes}
            multiline
            data-testid="task-notes-input"
          />
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}
