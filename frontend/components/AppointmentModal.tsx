import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Modal,
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import DateTimePicker from '@react-native-community/datetimepicker';
import { createCalendarEvent, hasCalendarPermission, requestCalendarPermission } from '../src/utils/calendar';
import api from '../services/api';

interface AppointmentModalProps {
  visible: boolean;
  onClose: () => void;
  onComplete: (appointmentCreated: boolean) => void;
  conversationId: string;
  contactName: string;
  contactPhone: string;
  userId: string;
}

export default function AppointmentModal({
  visible,
  onClose,
  onComplete,
  conversationId,
  contactName,
  contactPhone,
  userId,
}: AppointmentModalProps) {
  const [title, setTitle] = useState(`Appointment with ${contactName}`);
  const [date, setDate] = useState(new Date(Date.now() + 24 * 60 * 60 * 1000)); // Tomorrow
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [duration, setDuration] = useState(60); // minutes
  const [location, setLocation] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [addToCalendar, setAddToCalendar] = useState(true);
  const [hasCalendarAccess, setHasCalendarAccess] = useState(false);

  useEffect(() => {
    if (visible) {
      checkCalendarAccess();
      // Reset form
      setTitle(`Appointment with ${contactName}`);
      setDate(new Date(Date.now() + 24 * 60 * 60 * 1000));
      setDuration(60);
      setLocation('');
      setNotes('');
    }
  }, [visible, contactName]);

  const checkCalendarAccess = async () => {
    if (Platform.OS === 'web') {
      setHasCalendarAccess(false);
      return;
    }
    const hasAccess = await hasCalendarPermission();
    setHasCalendarAccess(hasAccess);
  };

  const handleDateChange = (event: any, selectedDate?: Date) => {
    setShowDatePicker(false);
    if (selectedDate) {
      const newDate = new Date(date);
      newDate.setFullYear(selectedDate.getFullYear());
      newDate.setMonth(selectedDate.getMonth());
      newDate.setDate(selectedDate.getDate());
      setDate(newDate);
    }
  };

  const handleTimeChange = (event: any, selectedTime?: Date) => {
    setShowTimePicker(false);
    if (selectedTime) {
      const newDate = new Date(date);
      newDate.setHours(selectedTime.getHours());
      newDate.setMinutes(selectedTime.getMinutes());
      setDate(newDate);
    }
  };

  const formatDate = (d: Date) => {
    return d.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatTime = (d: Date) => {
    return d.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const handleSave = async () => {
    if (!title.trim()) {
      Alert.alert('Error', 'Please enter a title for the appointment');
      return;
    }

    setSaving(true);

    try {
      const endDate = new Date(date.getTime() + duration * 60 * 1000);

      // Save to backend
      await api.post(`/calendar/appointments/${userId}`, {
        conversation_id: conversationId,
        contact_name: contactName,
        contact_phone: contactPhone,
        title: title.trim(),
        start_time: date.toISOString(),
        end_time: endDate.toISOString(),
        notes: notes.trim(),
        location: location.trim(),
      });

      // Add to native device calendar if enabled and on mobile
      if (addToCalendar && Platform.OS !== 'web') {
        if (!hasCalendarAccess) {
          const granted = await requestCalendarPermission();
          if (!granted) {
            Alert.alert(
              'Calendar Access Required',
              'Appointment saved but could not add to device calendar. Enable calendar access in settings.',
              [{ text: 'OK' }]
            );
            onComplete(true);
            return;
          }
        }

        const eventId = await createCalendarEvent({
          title: title.trim(),
          contactName,
          contactPhone,
          startDate: date,
          endDate: endDate,
          notes: notes.trim() || 'Scheduled by MVP',
          location: location.trim(),
        });

        if (eventId) {
          Alert.alert(
            'Appointment Created',
            'The appointment has been added to your calendar with reminders.',
            [{ text: 'OK' }]
          );
        }
      } else {
        Alert.alert('Appointment Saved', 'The appointment has been recorded.');
      }

      onComplete(true);
    } catch (error) {
      console.error('Failed to save appointment:', error);
      Alert.alert('Error', 'Failed to save appointment. Please try again.');
      setSaving(false);
    }
  };

  const handleSkip = () => {
    Alert.alert(
      'Skip Appointment',
      'Are you sure you want to skip scheduling? You can always schedule later from the conversation.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Skip',
          style: 'destructive',
          onPress: () => onComplete(false),
        },
      ]
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <Ionicons name="close" size={28} color="#FFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Schedule Appointment</Text>
          <TouchableOpacity
            onPress={handleSave}
            style={styles.saveButton}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#007AFF" />
            ) : (
              <Text style={styles.saveButtonText}>Save</Text>
            )}
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.content}>
          {/* MVP Notification */}
          <View style={styles.mvpBanner}>
            <Ionicons name="sparkles" size={20} color="#34C759" />
            <Text style={styles.mvpBannerText}>
              MVP has set an appointment with {contactName}
            </Text>
          </View>

          {/* Title Input */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Title</Text>
            <TextInput
              style={styles.textInput}
              value={title}
              onChangeText={setTitle}
              placeholder="Appointment title"
              placeholderTextColor="#8E8E93"
            />
          </View>

          {/* Date & Time */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Date & Time</Text>
            <View style={styles.dateTimeRow}>
              <TouchableOpacity
                style={styles.dateButton}
                onPress={() => setShowDatePicker(true)}
              >
                <Ionicons name="calendar-outline" size={20} color="#007AFF" />
                <Text style={styles.dateButtonText}>{formatDate(date)}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.timeButton}
                onPress={() => setShowTimePicker(true)}
              >
                <Ionicons name="time-outline" size={20} color="#007AFF" />
                <Text style={styles.dateButtonText}>{formatTime(date)}</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Duration */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Duration</Text>
            <View style={styles.durationRow}>
              {[30, 60, 90, 120].map((mins) => (
                <TouchableOpacity
                  key={mins}
                  style={[
                    styles.durationButton,
                    duration === mins && styles.durationButtonActive,
                  ]}
                  onPress={() => setDuration(mins)}
                >
                  <Text
                    style={[
                      styles.durationButtonText,
                      duration === mins && styles.durationButtonTextActive,
                    ]}
                  >
                    {mins < 60 ? `${mins}m` : `${mins / 60}h`}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Location */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Location (optional)</Text>
            <TextInput
              style={styles.textInput}
              value={location}
              onChangeText={setLocation}
              placeholder="Add location"
              placeholderTextColor="#8E8E93"
            />
          </View>

          {/* Notes */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Notes (optional)</Text>
            <TextInput
              style={[styles.textInput, styles.notesInput]}
              value={notes}
              onChangeText={setNotes}
              placeholder="Add notes"
              placeholderTextColor="#8E8E93"
              multiline
              numberOfLines={3}
            />
          </View>

          {/* Add to Calendar Toggle */}
          {Platform.OS !== 'web' && (
            <TouchableOpacity
              style={styles.calendarToggle}
              onPress={() => setAddToCalendar(!addToCalendar)}
            >
              <View style={styles.calendarToggleLeft}>
                <Ionicons
                  name="calendar"
                  size={22}
                  color={addToCalendar ? '#34C759' : '#8E8E93'}
                />
                <View>
                  <Text style={styles.calendarToggleText}>
                    Add to Device Calendar
                  </Text>
                  <Text style={styles.calendarToggleSubtext}>
                    Create with 15min & 1hr reminders
                  </Text>
                </View>
              </View>
              <View
                style={[
                  styles.toggleSwitch,
                  addToCalendar && styles.toggleSwitchActive,
                ]}
              >
                <View
                  style={[
                    styles.toggleKnob,
                    addToCalendar && styles.toggleKnobActive,
                  ]}
                />
              </View>
            </TouchableOpacity>
          )}

          {/* Contact Info */}
          <View style={styles.contactInfo}>
            <Ionicons name="person-circle-outline" size={40} color="#8E8E93" />
            <View style={styles.contactDetails}>
              <Text style={styles.contactName}>{contactName}</Text>
              <Text style={styles.contactPhone}>{contactPhone}</Text>
            </View>
          </View>

          {/* Skip Button */}
          <TouchableOpacity style={styles.skipButton} onPress={handleSkip}>
            <Text style={styles.skipButtonText}>Skip for now</Text>
          </TouchableOpacity>
        </ScrollView>

        {/* Date Picker for iOS */}
        {showDatePicker && Platform.OS === 'ios' && (
          <Modal transparent animationType="slide">
            <View style={styles.pickerModal}>
              <View style={styles.pickerContainer}>
                <View style={styles.pickerHeader}>
                  <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                    <Text style={styles.pickerDone}>Done</Text>
                  </TouchableOpacity>
                </View>
                <DateTimePicker
                  value={date}
                  mode="date"
                  display="spinner"
                  onChange={handleDateChange}
                  minimumDate={new Date()}
                  style={{ backgroundColor: '#1C1C1E' }}
                  textColor="#FFF"
                />
              </View>
            </View>
          </Modal>
        )}

        {/* Date Picker for Android */}
        {showDatePicker && Platform.OS === 'android' && (
          <DateTimePicker
            value={date}
            mode="date"
            display="default"
            onChange={handleDateChange}
            minimumDate={new Date()}
          />
        )}

        {/* Time Picker for iOS */}
        {showTimePicker && Platform.OS === 'ios' && (
          <Modal transparent animationType="slide">
            <View style={styles.pickerModal}>
              <View style={styles.pickerContainer}>
                <View style={styles.pickerHeader}>
                  <TouchableOpacity onPress={() => setShowTimePicker(false)}>
                    <Text style={styles.pickerDone}>Done</Text>
                  </TouchableOpacity>
                </View>
                <DateTimePicker
                  value={date}
                  mode="time"
                  display="spinner"
                  onChange={handleTimeChange}
                  style={{ backgroundColor: '#1C1C1E' }}
                  textColor="#FFF"
                />
              </View>
            </View>
          </Modal>
        )}

        {/* Time Picker for Android */}
        {showTimePicker && Platform.OS === 'android' && (
          <DateTimePicker
            value={date}
            mode="time"
            display="default"
            onChange={handleTimeChange}
          />
        )}

        {/* Web fallback date/time inputs */}
        {Platform.OS === 'web' && (showDatePicker || showTimePicker) && (
          <Modal transparent animationType="fade">
            <View style={styles.webPickerModal}>
              <View style={styles.webPickerContainer}>
                <Text style={styles.webPickerTitle}>
                  {showDatePicker ? 'Select Date' : 'Select Time'}
                </Text>
                <input
                  type={showDatePicker ? 'date' : 'time'}
                  value={
                    showDatePicker
                      ? date.toISOString().split('T')[0]
                      : date.toTimeString().slice(0, 5)
                  }
                  onChange={(e) => {
                    if (showDatePicker) {
                      const [year, month, day] = e.target.value.split('-');
                      const newDate = new Date(date);
                      newDate.setFullYear(parseInt(year), parseInt(month) - 1, parseInt(day));
                      setDate(newDate);
                    } else {
                      const [hours, minutes] = e.target.value.split(':');
                      const newDate = new Date(date);
                      newDate.setHours(parseInt(hours), parseInt(minutes));
                      setDate(newDate);
                    }
                  }}
                  style={{
                    fontSize: 18,
                    padding: 12,
                    borderRadius: 8,
                    border: '1px solid #3C3C3E',
                    backgroundColor: '#2C2C2E',
                    color: '#FFF',
                    marginBottom: 16,
                  }}
                />
                <TouchableOpacity
                  style={styles.webPickerButton}
                  onPress={() => {
                    setShowDatePicker(false);
                    setShowTimePicker(false);
                  }}
                >
                  <Text style={styles.webPickerButtonText}>Done</Text>
                </TouchableOpacity>
              </View>
            </View>
          </Modal>
        )}
      </View>
    </Modal>
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
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  closeButton: {
    width: 40,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  saveButton: {
    width: 50,
    alignItems: 'flex-end',
  },
  saveButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  mvpBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#34C75915',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    gap: 10,
  },
  mvpBannerText: {
    flex: 1,
    fontSize: 15,
    color: '#34C759',
    fontWeight: '500',
  },
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    paddingLeft: 4,
  },
  textInput: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  notesInput: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  dateTimeRow: {
    flexDirection: 'row',
    gap: 12,
  },
  dateButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    gap: 10,
  },
  timeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    gap: 10,
  },
  dateButtonText: {
    fontSize: 16,
    color: '#FFF',
  },
  durationRow: {
    flexDirection: 'row',
    gap: 10,
  },
  durationButton: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
  },
  durationButtonActive: {
    backgroundColor: '#007AFF',
  },
  durationButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#8E8E93',
  },
  durationButtonTextActive: {
    color: '#FFF',
  },
  calendarToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
  },
  calendarToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  calendarToggleText: {
    fontSize: 16,
    color: '#FFF',
    fontWeight: '500',
  },
  calendarToggleSubtext: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  toggleSwitch: {
    width: 50,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#3C3C3E',
    padding: 2,
    justifyContent: 'center',
  },
  toggleSwitchActive: {
    backgroundColor: '#34C759',
  },
  toggleKnob: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: '#FFF',
  },
  toggleKnobActive: {
    alignSelf: 'flex-end',
  },
  contactInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    gap: 12,
  },
  contactDetails: {
    flex: 1,
  },
  contactName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  contactPhone: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 2,
  },
  skipButton: {
    alignItems: 'center',
    paddingVertical: 16,
    marginBottom: 40,
  },
  skipButtonText: {
    fontSize: 15,
    color: '#8E8E93',
  },
  pickerModal: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  pickerContainer: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  pickerHeader: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  pickerDone: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  webPickerModal: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.7)',
  },
  webPickerContainer: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    minWidth: 280,
  },
  webPickerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 20,
  },
  webPickerButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 40,
  },
  webPickerButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
});
