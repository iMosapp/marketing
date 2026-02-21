import React, { useState } from 'react';
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
import { tasksAPI } from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';

export default function NewTaskScreen() {
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
  
  const taskTypes = [
    { id: 'callback', name: 'Call Back', icon: 'call', color: '#007AFF' },
    { id: 'follow_up', name: 'Follow Up', icon: 'chatbubble', color: '#34C759' },
    { id: 'appointment', name: 'Appointment', icon: 'calendar', color: '#FF9500' },
    { id: 'other', name: 'Other', icon: 'checkmark-circle', color: '#8E8E93' },
  ];
  
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
      
      // Combine date and time for due_date
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
      console.error('Create task error:', error);
    } finally {
      setSaving(false);
    }
  };
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="close" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.headerTitle}>New Task</Text>
        
        <TouchableOpacity onPress={handleSave} style={styles.saveButton} disabled={saving}>
          {saving ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <Text style={styles.saveButtonText}>Create</Text>
          )}
        </TouchableOpacity>
      </View>
      
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Task Type */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Task Type</Text>
          <View style={styles.typeGrid}>
            {taskTypes.map((type) => (
              <TouchableOpacity
                key={type.id}
                style={[
                  styles.typeCard,
                  task.type === type.id && styles.typeCardActive,
                  { borderColor: type.color },
                ]}
                onPress={() => setTask({ ...task, type: type.id as any })}
              >
                <Ionicons
                  name={type.icon as any}
                  size={28}
                  color={task.type === type.id ? type.color : '#8E8E93'}
                />
                <Text
                  style={[
                    styles.typeName,
                    task.type === type.id && { color: type.color },
                  ]}
                >
                  {type.name}
                </Text>
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
            placeholderTextColor="#8E8E93"
            value={task.title}
            onChangeText={(text) => setTask({ ...task, title: text })}
          />
        </View>
        
        {/* Description */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Description (Optional)</Text>
          <TextInput
            style={styles.textArea}
            placeholder="Add details..."
            placeholderTextColor="#8E8E93"
            value={task.description}
            onChangeText={(text) => setTask({ ...task, description: text })}
            multiline
            numberOfLines={4}
            textAlignVertical="top"
          />
        </View>
        
        {/* Contact */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Related Contact (Optional)</Text>
          <TouchableOpacity
            style={styles.selectButton}
            onPress={() => Alert.alert('Select Contact', 'Contact picker coming soon')}
          >
            <Ionicons name="person" size={20} color="#007AFF" />
            <Text style={styles.selectButtonText}>
              {task.contact ? task.contact.name : 'Select contact'}
            </Text>
            <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
          </TouchableOpacity>
        </View>
        
        {/* Due Date & Time */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Due Date & Time</Text>
          
          <View style={styles.dateTimeRow}>
            <TouchableOpacity
              style={[styles.input, styles.dateButton]}
              onPress={() => Alert.alert('Date Picker', 'Date picker coming soon')}
            >
              <Ionicons name="calendar" size={20} color="#007AFF" />
              <Text style={styles.dateText}>
                {task.dueDate.toLocaleDateString()}
              </Text>
            </TouchableOpacity>
            
            <TextInput
              style={[styles.input, styles.timeInput]}
              placeholder="10:00"
              placeholderTextColor="#8E8E93"
              value={task.dueTime}
              onChangeText={(text) => setTask({ ...task, dueTime: text })}
            />
          </View>
        </View>
        
        {/* Priority */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Priority</Text>
          <View style={styles.priorityRow}>
            {(['low', 'medium', 'high'] as const).map((priority) => (
              <TouchableOpacity
                key={priority}
                style={[
                  styles.priorityButton,
                  task.priority === priority && styles.priorityButtonActive,
                ]}
                onPress={() => setTask({ ...task, priority })}
              >
                <View
                  style={[
                    styles.priorityDot,
                    {
                      backgroundColor:
                        priority === 'high'
                          ? '#FF3B30'
                          : priority === 'medium'
                          ? '#FF9500'
                          : '#8E8E93',
                    },
                  ]}
                />
                <Text
                  style={[
                    styles.priorityText,
                    task.priority === priority && styles.priorityTextActive,
                  ]}
                >
                  {priority.charAt(0).toUpperCase() + priority.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  saveButton: {
    padding: 4,
  },
  saveButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  scrollContent: {
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  typeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  typeCard: {
    flex: 1,
    minWidth: 140,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#2C2C2E',
  },
  typeCardActive: {
    borderWidth: 2,
  },
  typeName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginTop: 8,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  textArea: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
    height: 100,
  },
  selectButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2C2C2E',
    gap: 12,
  },
  selectButtonText: {
    flex: 1,
    fontSize: 16,
    color: '#FFF',
  },
  dateTimeRow: {
    flexDirection: 'row',
    gap: 12,
  },
  dateButton: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  dateText: {
    fontSize: 16,
    color: '#FFF',
  },
  timeInput: {
    flex: 1,
    textAlign: 'center',
  },
  priorityRow: {
    flexDirection: 'row',
    gap: 12,
  },
  priorityButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  priorityButtonActive: {
    backgroundColor: '#2C2C2E',
    borderColor: '#007AFF',
  },
  priorityDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  priorityText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  priorityTextActive: {
    color: '#FFF',
  },
});
