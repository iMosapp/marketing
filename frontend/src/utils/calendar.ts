/**
 * Calendar utility functions for MVPLine
 * Handles native device calendar operations using expo-calendar
 */
import * as Calendar from 'expo-calendar';
import { Platform, Alert } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const SELECTED_CALENDAR_KEY = 'mvpline_selected_calendar';

export interface AppointmentDetails {
  title: string;
  contactName: string;
  contactPhone: string;
  notes?: string;
  startDate: Date;
  endDate?: Date;
  location?: string;
}

/**
 * Check if calendar permissions are granted
 */
export async function hasCalendarPermission(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  
  try {
    const { status } = await Calendar.getCalendarPermissionsAsync();
    return status === 'granted';
  } catch (error) {
    console.error('Error checking calendar permission:', error);
    return false;
  }
}

/**
 * Request calendar permissions
 */
export async function requestCalendarPermission(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  
  try {
    const { status } = await Calendar.requestCalendarPermissionsAsync();
    return status === 'granted';
  } catch (error) {
    console.error('Error requesting calendar permission:', error);
    return false;
  }
}

/**
 * Get all available calendars on the device
 */
export async function getCalendars(): Promise<Calendar.Calendar[]> {
  if (Platform.OS === 'web') return [];
  
  try {
    const hasPermission = await hasCalendarPermission();
    if (!hasPermission) return [];
    
    const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
    // Filter to only writable calendars
    return calendars.filter(cal => cal.allowsModifications);
  } catch (error) {
    console.error('Error getting calendars:', error);
    return [];
  }
}

/**
 * Get the user's preferred calendar ID from storage
 */
export async function getSelectedCalendarId(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(SELECTED_CALENDAR_KEY);
  } catch (error) {
    console.error('Error getting selected calendar:', error);
    return null;
  }
}

/**
 * Save the user's preferred calendar ID
 */
export async function setSelectedCalendarId(calendarId: string): Promise<void> {
  try {
    await AsyncStorage.setItem(SELECTED_CALENDAR_KEY, calendarId);
  } catch (error) {
    console.error('Error saving selected calendar:', error);
  }
}

/**
 * Get the default calendar (user's preference or system default)
 */
export async function getDefaultCalendar(): Promise<Calendar.Calendar | null> {
  if (Platform.OS === 'web') return null;
  
  try {
    const calendars = await getCalendars();
    if (calendars.length === 0) return null;
    
    // Check user preference
    const selectedId = await getSelectedCalendarId();
    if (selectedId) {
      const selected = calendars.find(cal => cal.id === selectedId);
      if (selected) return selected;
    }
    
    // Fall back to default calendar
    const defaultCalendar = calendars.find(cal => cal.isPrimary) || calendars[0];
    return defaultCalendar;
  } catch (error) {
    console.error('Error getting default calendar:', error);
    return null;
  }
}

/**
 * Create an event in the device calendar
 */
export async function createCalendarEvent(
  appointment: AppointmentDetails
): Promise<string | null> {
  if (Platform.OS === 'web') {
    console.log('Calendar events not supported on web');
    return null;
  }
  
  try {
    // Check permission
    const hasPermission = await hasCalendarPermission();
    if (!hasPermission) {
      const granted = await requestCalendarPermission();
      if (!granted) {
        Alert.alert(
          'Permission Required',
          'Calendar access is needed to add appointments. Please enable it in Settings.'
        );
        return null;
      }
    }
    
    // Get calendar
    const calendar = await getDefaultCalendar();
    if (!calendar) {
      Alert.alert(
        'No Calendar Found',
        'Please set up a calendar on your device to add appointments.'
      );
      return null;
    }
    
    // Default end time is 1 hour after start
    const endDate = appointment.endDate || new Date(appointment.startDate.getTime() + 60 * 60 * 1000);
    
    // Create event details
    const eventDetails: Calendar.Event = {
      title: appointment.title,
      startDate: appointment.startDate,
      endDate: endDate,
      notes: `Contact: ${appointment.contactName}\nPhone: ${appointment.contactPhone}${appointment.notes ? '\n\n' + appointment.notes : ''}`,
      location: appointment.location,
      alarms: [
        { relativeOffset: -15 }, // 15 minutes before
        { relativeOffset: -60 }, // 1 hour before
      ],
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };
    
    // Create the event
    const eventId = await Calendar.createEventAsync(calendar.id, eventDetails);
    
    console.log('Calendar event created:', eventId);
    return eventId;
  } catch (error) {
    console.error('Error creating calendar event:', error);
    Alert.alert('Error', 'Failed to create calendar event. Please try again.');
    return null;
  }
}

/**
 * Delete a calendar event
 */
export async function deleteCalendarEvent(eventId: string): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  
  try {
    await Calendar.deleteEventAsync(eventId);
    return true;
  } catch (error) {
    console.error('Error deleting calendar event:', error);
    return false;
  }
}

/**
 * Create an appointment from MVP outcome
 */
export async function createAppointmentFromMVP(
  contactName: string,
  contactPhone: string,
  appointmentTime: Date,
  notes?: string
): Promise<string | null> {
  const appointment: AppointmentDetails = {
    title: `Appointment with ${contactName}`,
    contactName,
    contactPhone,
    startDate: appointmentTime,
    notes: notes || 'Appointment scheduled by MVP',
  };
  
  return createCalendarEvent(appointment);
}
