import React, {
  useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Platform,
  Linking,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import * as Calendar from 'expo-calendar';
import { getCalendars, getSelectedCalendarId, setSelectedCalendarId } from '../../src/utils/calendar';
import { useToast } from '../../components/common/Toast';

import { useThemeStore } from '../../store/themeStore';
export default function CalendarSettingsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const params = useLocalSearchParams();
  const { user } = useAuthStore();
  
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [googleEmail, setGoogleEmail] = useState<string | null>(null);
  const [nativeCalendarPermission, setNativeCalendarPermission] = useState<string>('undetermined');
  const [connectingGoogle, setConnectingGoogle] = useState(false);
  const [deviceCalendars, setDeviceCalendars] = useState<Calendar.Calendar[]>([]);
  const [selectedCalendar, setSelectedCalendar] = useState<string | null>(null);
  const [showCalendarPicker, setShowCalendarPicker] = useState(false);

  useEffect(() => {
    if (user?._id) {
      loadCalendarStatus();
      checkNativeCalendarPermission();
    }
    
    // Check if just connected from OAuth callback
    if (params.connected === 'true') {
      loadCalendarStatus();
    }
  }, [params.connected, user?._id]);

  useEffect(() => {
    if (nativeCalendarPermission === 'granted') {
      loadDeviceCalendars();
    }
  }, [nativeCalendarPermission]);

  const loadDeviceCalendars = async () => {
    try {
      const calendars = await getCalendars();
      setDeviceCalendars(calendars);
      
      const savedCalendarId = await getSelectedCalendarId();
      if (savedCalendarId && calendars.find(c => c.id === savedCalendarId)) {
        setSelectedCalendar(savedCalendarId);
      } else if (calendars.length > 0) {
        // Default to primary or first calendar
        const primary = calendars.find(c => c.isPrimary) || calendars[0];
        setSelectedCalendar(primary.id);
        await setSelectedCalendarId(primary.id);
      }
    } catch (error) {
      console.error('Error loading device calendars:', error);
    }
  };

  const handleCalendarSelect = async (calendarId: string) => {
    setSelectedCalendar(calendarId);
    await setSelectedCalendarId(calendarId);
    setShowCalendarPicker(false);
  };

  const loadCalendarStatus = async () => {
    if (!user) return;
    
    try {
      const response = await api.get(`/calendar/status/${user._id}`);
      setGoogleConnected(response.data.connected);
      setGoogleEmail(response.data.google_email);
    } catch (error) {
      console.error('Failed to load calendar status:', error);
    } finally {
      setLoading(false);
    }
  };

  const checkNativeCalendarPermission = async () => {
    if (Platform.OS === 'web') {
      setNativeCalendarPermission('unavailable');
      return;
    }
    
    try {
      const { status } = await Calendar.getCalendarPermissionsAsync();
      setNativeCalendarPermission(status);
    } catch (error) {
      console.error('Failed to check calendar permission:', error);
      setNativeCalendarPermission('unavailable');
    }
  };

  const requestNativeCalendarPermission = async () => {
    if (Platform.OS === 'web') {
      Alert.alert('Not Available', 'Native calendar is only available on mobile devices.');
      return;
    }
    
    try {
      const { status } = await Calendar.requestCalendarPermissionsAsync();
      setNativeCalendarPermission(status);
      
      if (status === 'granted') {
        showToast('Calendar access granted! Appointments will be added to your device calendar.');
      } else {
        Alert.alert('Permission Denied', 'Please enable calendar access in your device settings.');
      }
    } catch (error) {
      console.error('Failed to request calendar permission:', error);
      Alert.alert('Error', 'Failed to request calendar permission.');
    }
  };

  const connectGoogleCalendar = async () => {
    if (!user) return;
    
    setConnectingGoogle(true);
    
    try {
      const response = await api.get(`/calendar/oauth/login/${user._id}`);
      const authUrl = response.data.authorization_url;
      
      if (Platform.OS === 'web') {
        window.location.href = authUrl;
      } else {
        await Linking.openURL(authUrl);
      }
    } catch (error: any) {
      console.error('Failed to start Google OAuth:', error);
      if (error.response?.status === 503) {
        Alert.alert(
          'Setup Required',
          'Google Calendar integration needs to be configured. Please contact your administrator to set up Google Calendar API credentials.'
        );
      } else {
        Alert.alert('Error', 'Failed to connect Google Calendar.');
      }
    } finally {
      setConnectingGoogle(false);
    }
  };

  const disconnectGoogleCalendar = async () => {
    if (!user) return;
    
    Alert.alert(
      'Disconnect Google Calendar',
      'Are you sure you want to disconnect your Google Calendar? New appointments will no longer sync.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/calendar/disconnect/${user._id}`);
              setGoogleConnected(false);
              setGoogleEmail(null);
            } catch (error) {
              console.error('Failed to disconnect calendar:', error);
              Alert.alert('Error', 'Failed to disconnect calendar.');
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color="#007AFF" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Calendar Settings</Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={styles.content}>
        {/* Google Calendar Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>GOOGLE CALENDAR</Text>
          
          <View style={styles.card}>
            <View style={styles.cardIcon}>
              <Ionicons 
                name="logo-google" 
                size={24} 
                color={googleConnected ? '#34C759' : colors.textSecondary} 
              />
            </View>
            
            <View style={styles.cardContent}>
              <Text style={styles.cardTitle}>
                {googleConnected ? 'Connected' : 'Not Connected'}
              </Text>
              {googleEmail && (
                <Text style={styles.cardSubtitle}>{googleEmail}</Text>
              )}
              {!googleConnected && (
                <Text style={styles.cardDescription}>
                  Connect to sync appointments with Google Calendar
                </Text>
              )}
            </View>

            <TouchableOpacity
              style={[
                styles.actionButton,
                googleConnected ? styles.disconnectButton : styles.connectButton,
              ]}
              onPress={googleConnected ? disconnectGoogleCalendar : connectGoogleCalendar}
              disabled={connectingGoogle}
            >
              {connectingGoogle ? (
                <ActivityIndicator size="small" color={colors.text} />
              ) : (
                <Text style={styles.actionButtonText}>
                  {googleConnected ? 'Disconnect' : 'Connect'}
                </Text>
              )}
            </TouchableOpacity>
          </View>
        </View>

        {/* Native Calendar Section */}
        {Platform.OS !== 'web' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>DEVICE CALENDAR</Text>
            
            <View style={styles.card}>
              <View style={styles.cardIcon}>
                <Ionicons 
                  name="calendar" 
                  size={24} 
                  color={nativeCalendarPermission === 'granted' ? '#34C759' : colors.textSecondary} 
                />
              </View>
              
              <View style={styles.cardContent}>
                <Text style={styles.cardTitle}>
                  {nativeCalendarPermission === 'granted' ? 'Access Granted' : 'Access Required'}
                </Text>
                <Text style={styles.cardDescription}>
                  {nativeCalendarPermission === 'granted' 
                    ? 'Appointments will be added to your device calendar'
                    : 'Allow access to add appointments to your calendar'
                  }
                </Text>
              </View>

              {nativeCalendarPermission !== 'granted' && (
                <TouchableOpacity
                  style={[styles.actionButton, styles.connectButton]}
                  onPress={requestNativeCalendarPermission}
                >
                  <Text style={styles.actionButtonText}>Enable</Text>
                </TouchableOpacity>
              )}
              
              {nativeCalendarPermission === 'granted' && (
                <Ionicons name="checkmark-circle" size={24} color="#34C759" />
              )}
            </View>

            {/* Calendar Selector - only shown when permission granted */}
            {nativeCalendarPermission === 'granted' && deviceCalendars.length > 0 && (
              <TouchableOpacity 
                style={[styles.card, { marginTop: 12 }]}
                onPress={() => setShowCalendarPicker(!showCalendarPicker)}
              >
                <View style={styles.cardIcon}>
                  <Ionicons name="albums-outline" size={24} color="#007AFF" />
                </View>
                
                <View style={styles.cardContent}>
                  <Text style={styles.cardTitle}>Default Calendar</Text>
                  <Text style={styles.cardDescription}>
                    {deviceCalendars.find(c => c.id === selectedCalendar)?.title || 'Select a calendar'}
                  </Text>
                </View>

                <Ionicons 
                  name={showCalendarPicker ? "chevron-up" : "chevron-down"} 
                  size={20} 
                  color={colors.textSecondary} 
                />
              </TouchableOpacity>
            )}

            {/* Calendar List */}
            {showCalendarPicker && (
              <View style={styles.calendarList}>
                {deviceCalendars.map((calendar) => (
                  <TouchableOpacity
                    key={calendar.id}
                    style={[
                      styles.calendarItem,
                      selectedCalendar === calendar.id && styles.calendarItemSelected,
                    ]}
                    onPress={() => handleCalendarSelect(calendar.id)}
                  >
                    <View 
                      style={[
                        styles.calendarColor, 
                        { backgroundColor: calendar.color || '#007AFF' }
                      ]} 
                    />
                    <Text style={styles.calendarName}>{calendar.title}</Text>
                    {calendar.isPrimary && (
                      <Text style={styles.primaryBadge}>Primary</Text>
                    )}
                    {selectedCalendar === calendar.id && (
                      <Ionicons name="checkmark" size={20} color="#007AFF" />
                    )}
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
        )}

        {/* Info Section */}
        <View style={styles.infoCard}>
          <Ionicons name="information-circle" size={20} color="#007AFF" />
          <Text style={styles.infoText}>
            When your AI sets an appointment with a contact, it will automatically be added to your connected calendars with the contact's details and a 15-minute reminder.
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    paddingLeft: 4,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  cardIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  cardContent: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  cardSubtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 2,
  },
  cardDescription: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 4,
  },
  actionButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 16,
    marginLeft: 12,
  },
  connectButton: {
    backgroundColor: '#007AFF',
  },
  disconnectButton: {
    backgroundColor: '#FF3B30',
  },
  actionButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  infoCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  infoText: {
    flex: 1,
    fontSize: 16,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  calendarList: {
    backgroundColor: colors.card,
    borderRadius: 12,
    marginTop: 8,
    overflow: 'hidden',
  },
  calendarItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  calendarItemSelected: {
    backgroundColor: colors.surface,
  },
  calendarColor: {
    width: 16,
    height: 16,
    borderRadius: 4,
    marginRight: 12,
  },
  calendarName: {
    flex: 1,
    fontSize: 18,
    color: colors.text,
  },
  primaryBadge: {
    fontSize: 14,
    color: colors.textSecondary,
    marginRight: 8,
    backgroundColor: '#3C3C3E',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
});
