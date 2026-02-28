import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { format, isToday, isTomorrow, isPast } from 'date-fns';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { tasksAPI, contactsAPI } from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';

export default function TasksScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [tasks, setTasks] = useState<any[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [filter, setFilter] = useState<'active' | 'completed' | 'all'>('active');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  
  useEffect(() => {
    loadTasks();
    loadContacts();
  }, [user, filter]);
  
  const loadTasks = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      const completed = filter === 'completed' ? true : filter === 'active' ? false : undefined;
      const data = await tasksAPI.getAll(user._id, completed);
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadContacts = async () => {
    if (!user) return;
    try {
      const data = await contactsAPI.getAll(user._id);
      setContacts(data);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await loadTasks();
    setRefreshing(false);
  };
  
  const filteredTasks = tasks.filter((task) => {
    if (filter === 'active') return !task.completed;
    if (filter === 'completed') return task.completed;
    return true;
  });

  // Get contact info for a task
  const getTaskContact = (task: any) => {
    if (task.contact) return task.contact;
    if (task.contact_id) {
      const contact = contacts.find(c => c._id === task.contact_id || c.id === task.contact_id);
      if (contact) {
        return {
          _id: contact._id || contact.id,
          name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
          phone: contact.phone,
        };
      }
    }
    return null;
  };

  // Execute the task action
  const executeTaskAction = async (task: any) => {
    const contact = getTaskContact(task);
    const taskType = task.type?.toLowerCase() || 'task';

    // If task is already completed, just show details
    if (task.completed) {
      showSimpleAlert('Task Completed', `This task was already completed.`);
      return;
    }

    // Handle different task types
    switch (taskType) {
      case 'call':
      case 'callback':
        if (contact?.phone) {
          // Navigate to dialer or make call
          showConfirm(
            'Call Contact',
            `Call ${contact.name} at ${contact.phone}?`,
            async () => {
              const phoneUrl = Platform.OS === 'ios' ? `telprompt:${contact.phone}` : `tel:${contact.phone}`;
              try {
                await Linking.openURL(phoneUrl);
                // Mark task as complete after call initiated
                await completeTask(task._id || task.id);
              } catch (error) {
                showSimpleAlert('Error', 'Unable to make phone call');
              }
            },
            undefined,
            'Call Now',
            'Cancel'
          );
        } else {
          // Navigate to dialer
          router.push('/(tabs)/dialer');
        }
        break;

      case 'follow_up':
      case 'message':
      case 'text':
      case 'sms':
        if (contact?._id) {
          // Navigate to message thread
          router.push({
            pathname: `/thread/${contact._id}`,
            params: {
              contact_name: contact.name,
              contact_phone: contact.phone || '',
              contact_email: contact.email || contact.email_work || '',
              task_id: task._id || task.id, // Pass task ID to mark complete after sending
            }
          });
        } else {
          // Navigate to inbox to start a new message
          router.push('/(tabs)/inbox');
        }
        break;

      case 'appointment':
      case 'meeting':
      case 'schedule':
        if (contact?._id) {
          // Navigate to contact detail to schedule
          router.push({
            pathname: `/contact/${contact._id}`,
            params: { action: 'schedule' }
          });
        } else {
          showSimpleAlert('Schedule', 'Open your calendar to schedule this appointment.');
        }
        break;

      default:
        // Generic task - just offer to complete it
        showConfirm(
          'Complete Task',
          `Mark "${task.title}" as complete?`,
          async () => {
            await completeTask(task._id || task.id);
          },
          undefined,
          'Complete',
          'Not Yet'
        );
        break;
    }
  };

  const completeTask = async (id: string) => {
    if (!user) return;
    
    // Satisfying haptic for task completion
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    
    try {
      await tasksAPI.update(user._id, id, { completed: true });
      setTasks(tasks.map((t) => 
        (t._id === id || t.id === id) ? { ...t, completed: true } : t
      ));
      showSimpleAlert('Task Complete', 'Great job! Task marked as done.');
    } catch (error) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      console.error('Failed to complete task:', error);
      showSimpleAlert('Error', 'Failed to complete task');
    }
  };
  
  const toggleTask = async (id: string) => {
    if (!user) return;
    
    const task = tasks.find(t => t._id === id || t.id === id);
    if (!task) return;
    
    // Light haptic for toggle
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    try {
      await tasksAPI.update(user._id, id, { completed: !task.completed });
      setTasks(tasks.map((t) => 
        (t._id === id || t.id === id) ? { ...t, completed: !t.completed } : t
      ));
    } catch (error) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      console.error('Failed to update task:', error);
      showSimpleAlert('Error', 'Failed to update task');
    }
  };
  
  const deleteTask = async (id: string) => {
    // Warning haptic for destructive action
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
    
    showConfirm(
      'Delete Task',
      'Are you sure you want to delete this task?',
      async () => {
        if (!user) return;
        try {
          await tasksAPI.delete(user._id, id);
          setTasks(tasks.filter((t) => t._id !== id && t.id !== id));
        } catch (error) {
          console.error('Failed to delete task:', error);
          showSimpleAlert('Error', 'Failed to delete task');
        }
      },
      undefined,
      'Delete',
      'Cancel'
    );
  };
  
  const getTaskIcon = (type: string) => {
    const taskType = type?.toLowerCase() || 'task';
    switch (taskType) {
      case 'call':
      case 'callback':
        return { icon: 'call', color: '#007AFF' };
      case 'follow_up':
      case 'message':
      case 'text':
      case 'sms':
        return { icon: 'chatbubble', color: '#34C759' };
      case 'appointment':
      case 'meeting':
      case 'schedule':
        return { icon: 'calendar', color: '#FF9500' };
      default:
        return { icon: 'checkmark-circle', color: '#8E8E93' };
    }
  };

  const getActionLabel = (type: string) => {
    const taskType = type?.toLowerCase() || 'task';
    switch (taskType) {
      case 'call':
      case 'callback':
        return 'Tap to call';
      case 'follow_up':
      case 'message':
      case 'text':
      case 'sms':
        return 'Tap to message';
      case 'appointment':
      case 'meeting':
      case 'schedule':
        return 'Tap to schedule';
      default:
        return 'Tap to complete';
    }
  };
  
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return '#FF3B30';
      case 'medium':
        return '#FF9500';
      case 'low':
        return '#8E8E93';
      default:
        return '#8E8E93';
    }
  };
  
  const formatDueDate = (date: Date) => {
    if (isToday(date)) return 'Today';
    if (isTomorrow(date)) return 'Tomorrow';
    if (isPast(date)) return `Overdue - ${format(date, 'MMM d')}`;
    return format(date, 'MMM d, h:mm a');
  };
  
  const getDueDateColor = (date: Date, completed: boolean) => {
    if (completed) return '#8E8E93';
    if (isPast(date) && !isToday(date)) return '#FF3B30';
    if (isToday(date)) return '#FF9500';
    return '#8E8E93';
  };
  
  const renderTask = ({ item }: { item: typeof tasks[0] }) => {
    const iconData = getTaskIcon(item.type);
    const isOverdue = isPast(item.due_date) && !isToday(item.due_date) && !item.completed;
    const contact = getTaskContact(item);
    const actionLabel = getActionLabel(item.type);
    
    return (
      <TouchableOpacity 
        style={[styles.taskCard, item.completed && styles.taskCardCompleted]}
        onPress={() => executeTaskAction(item)}
        activeOpacity={0.7}
      >
        <TouchableOpacity
          style={styles.checkbox}
          onPress={() => toggleTask(item._id || item.id)}
        >
          {item.completed ? (
            <Ionicons name="checkmark-circle" size={28} color="#34C759" />
          ) : (
            <View style={styles.checkboxEmpty} />
          )}
        </TouchableOpacity>
        
        <View style={styles.taskContent}>
          <View style={styles.taskHeader}>
            <View style={[styles.taskIcon, { backgroundColor: `${iconData.color}20` }]}>
              <Ionicons name={iconData.icon as any} size={16} color={iconData.color} />
            </View>
            <Text
              style={[
                styles.taskTitle,
                item.completed && styles.taskTitleCompleted,
              ]}
            >
              {item.title}
            </Text>
            <View
              style={[
                styles.priorityDot,
                { backgroundColor: getPriorityColor(item.priority) },
              ]}
            />
          </View>
          
          {item.description && (
            <Text
              style={[
                styles.taskDescription,
                item.completed && styles.taskDescriptionCompleted,
              ]}
              numberOfLines={2}
            >
              {item.description}
            </Text>
          )}
          
          <View style={styles.taskFooter}>
            <View style={styles.taskMeta}>
              <Ionicons
                name="time"
                size={14}
                color={getDueDateColor(item.due_date, item.completed)}
              />
              <Text
                style={[
                  styles.dueDate,
                  { color: getDueDateColor(item.due_date, item.completed) },
                  isOverdue && styles.overdue,
                ]}
              >
                {formatDueDate(item.due_date)}
              </Text>
            </View>
            
            {contact && (
              <View style={styles.contactChip}>
                <Ionicons name="person" size={12} color="#007AFF" />
                <Text style={styles.contactName}>{contact.name}</Text>
              </View>
            )}
          </View>

          {/* Action hint for incomplete tasks */}
          {!item.completed && (
            <View style={styles.actionHint}>
              <Ionicons name="arrow-forward-circle" size={14} color={iconData.color} />
              <Text style={[styles.actionHintText, { color: iconData.color }]}>
                {actionLabel}
              </Text>
            </View>
          )}
        </View>
        
        <TouchableOpacity
          style={styles.deleteButton}
          onPress={() => deleteTask(item._id || item.id)}
        >
          <Ionicons name="trash-outline" size={20} color="#FF3B30" />
        </TouchableOpacity>
      </TouchableOpacity>
    );
  };
  
  const activeTasks = tasks.filter((t) => !t.completed);
  const overdueTasks = activeTasks.filter(
    (t) => isPast(t.due_date) && !isToday(t.due_date)
  );
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.title}>Tasks</Text>
        
        <TouchableOpacity
          onPress={() => router.push('/tasks/new')}
          style={styles.addButton}
        >
          <Ionicons name="add-circle" size={32} color="#007AFF" />
        </TouchableOpacity>
      </View>
      
      {/* Stats */}
      <View style={styles.statsContainer}>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{activeTasks.length}</Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>
        {overdueTasks.length > 0 && (
          <View style={[styles.statBox, styles.statBoxOverdue]}>
            <Ionicons name="alert-circle" size={20} color="#FF3B30" />
            <Text style={[styles.statValue, { color: '#FF3B30' }]}>
              {overdueTasks.length}
            </Text>
            <Text style={[styles.statLabel, { color: '#FF3B30' }]}>Overdue</Text>
          </View>
        )}
      </View>
      
      {/* Filter */}
      <View style={styles.filterContainer}>
        {(['active', 'completed', 'all'] as const).map((f) => (
          <TouchableOpacity
            key={f}
            style={[
              styles.filterButton,
              filter === f && styles.filterButtonActive,
            ]}
            onPress={() => setFilter(f)}
          >
            <Text
              style={[
                styles.filterText,
                filter === f && styles.filterTextActive,
              ]}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      
      {/* Task List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          data={filteredTasks}
          renderItem={renderTask}
          keyExtractor={(item) => item._id || item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#007AFF"
            />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyState}>
              <Ionicons name="checkmark-done-circle" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No tasks found</Text>
              <Text style={styles.emptySubtext}>
                {filter === 'active'
                  ? "You're all caught up!"
                  : 'Create a task to get started'}
              </Text>
            </View>
          )}
        />
      )}
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
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
  },
  addButton: {
    padding: 4,
  },
  statsContainer: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
  },
  statBox: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  statBoxOverdue: {
    borderWidth: 1,
    borderColor: '#FF3B30',
  },
  statValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
    textTransform: 'uppercase',
  },
  filterContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 8,
    marginBottom: 16,
  },
  filterButton: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
  },
  filterButtonActive: {
    backgroundColor: '#007AFF',
  },
  filterText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  filterTextActive: {
    color: '#FFF',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  taskCard: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'flex-start',
  },
  taskCardCompleted: {
    opacity: 0.6,
  },
  checkbox: {
    marginRight: 12,
    paddingTop: 2,
  },
  checkboxEmpty: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: '#8E8E93',
  },
  taskContent: {
    flex: 1,
  },
  taskHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 8,
  },
  taskIcon: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  taskTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  taskTitleCompleted: {
    textDecorationLine: 'line-through',
    color: '#8E8E93',
  },
  priorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  taskDescription: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 12,
    lineHeight: 20,
  },
  taskDescriptionCompleted: {
    textDecorationLine: 'line-through',
  },
  taskFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  taskMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  dueDate: {
    fontSize: 13,
    fontWeight: '600',
  },
  overdue: {
    fontWeight: 'bold',
  },
  contactChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF20',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  contactName: {
    fontSize: 12,
    color: '#007AFF',
    fontWeight: '600',
  },
  deleteButton: {
    padding: 8,
    marginLeft: 8,
  },
  actionHint: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    gap: 6,
  },
  actionHintText: {
    fontSize: 12,
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 15,
    color: '#8E8E93',
  },
});
