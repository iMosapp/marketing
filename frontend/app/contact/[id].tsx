import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Image,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
  FlatList,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Swipeable } from 'react-native-gesture-handler';
import { format, parseISO } from 'date-fns';
import { useAuthStore } from '../../store/authStore';
import { contactsAPI, campaignsAPI, tagsAPI } from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import VoiceInput from '../../components/VoiceInput';

const IS_WEB = Platform.OS === 'web';

interface CustomDateField {
  name: string;
  date: Date | null;
}

export default function ContactDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const user = useAuthStore((state) => state.user);
  const isNewContact = id === 'new';
  
  const [contact, setContact] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    photo: null as string | null,
    notes: '',
    vehicle: '',
    tags: [] as string[],
    referred_by: null as string | null,
    referred_by_name: null as string | null,
    referral_notes: '',
    referral_count: 0,
    // Date fields
    birthday: null as Date | null,
    anniversary: null as Date | null,
    date_sold: null as Date | null,
    custom_dates: [] as CustomDateField[],
  });
  
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(!isNewContact);
  
  // Date picker state
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [activeDateField, setActiveDateField] = useState<string | null>(null);
  const [activeDateLabel, setActiveDateLabel] = useState<string>('');
  const [tempDate, setTempDate] = useState(new Date());
  
  // Web date picker state (for platforms without native picker)
  const [webMonth, setWebMonth] = useState(new Date().getMonth());
  const [webDay, setWebDay] = useState(new Date().getDate());
  const [webYear, setWebYear] = useState(new Date().getFullYear());
  
  // Custom date field state - New flow: Date first, then label
  const [newCustomDateName, setNewCustomDateName] = useState('');
  const [pendingCustomDate, setPendingCustomDate] = useState<Date | null>(null);
  const [showCustomDateLabel, setShowCustomDateLabel] = useState(false);
  
  // Referral picker state
  const [showReferralPicker, setShowReferralPicker] = useState(false);
  const [allContacts, setAllContacts] = useState<any[]>([]);
  const [referrals, setReferrals] = useState<any[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  
  // Campaign enrollment state
  const [showCampaignPicker, setShowCampaignPicker] = useState(false);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [contactEnrollments, setContactEnrollments] = useState<any[]>([]);
  
  // Tag picker state
  const [availableTags, setAvailableTags] = useState<any[]>([]);
  const [showTagPicker, setShowTagPicker] = useState(false);
  const [tagSearch, setTagSearch] = useState('');

  useEffect(() => {
    if (!isNewContact && user) {
      loadContact();
      loadReferrals();
      loadCampaignsAndEnrollments();
      loadTags();
    }
  }, [id, user]);
  
  const loadTags = async () => {
    if (!user) return;
    try {
      const tagsData = await tagsAPI.getAll(user._id);
      setAvailableTags(tagsData);
    } catch (error) {
      console.error('Error loading tags:', error);
    }
  };
  
  const loadCampaignsAndEnrollments = async () => {
    if (!user || isNewContact) return;
    
    try {
      // Load all campaigns
      const campaignsData = await campaignsAPI.getAll(user._id);
      setCampaigns(campaignsData.filter((c: any) => c.active));
      
      // Load enrollments for each campaign and filter by this contact
      const allEnrollments: any[] = [];
      for (const campaign of campaignsData) {
        const enrollments = await campaignsAPI.getEnrollments(user._id, campaign._id);
        const contactEnroll = enrollments.find((e: any) => e.contact_id === id);
        if (contactEnroll) {
          allEnrollments.push({
            ...contactEnroll,
            campaign_name: campaign.name,
            campaign_type: campaign.type,
            total_steps: campaign.sequences?.length || 0,
          });
        }
      }
      setContactEnrollments(allEnrollments);
    } catch (error) {
      console.error('Failed to load campaigns:', error);
    }
  };
  
  const loadContact = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      const data = await contactsAPI.getById(user._id, id as string);
      
      // Parse date strings to Date objects
      const parseDate = (dateStr: string | null | undefined): Date | null => {
        if (!dateStr) return null;
        try {
          return new Date(dateStr);
        } catch {
          return null;
        }
      };
      
      // Parse custom dates
      const customDates = (data.custom_dates || []).map((cd: any) => ({
        name: cd.name,
        date: parseDate(cd.date),
      }));
      
      setContact({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        phone: data.phone || '',
        email: data.email || '',
        photo: data.photo || null,
        notes: data.notes || '',
        vehicle: data.vehicle || '',
        tags: data.tags || [],
        referred_by: data.referred_by || null,
        referred_by_name: data.referred_by_name || null,
        referral_notes: data.referral_notes || '',
        referral_count: data.referral_count || 0,
        // Date fields
        birthday: parseDate(data.birthday),
        anniversary: parseDate(data.anniversary),
        date_sold: parseDate(data.date_sold) || parseDate(data.purchase_date),
        custom_dates: customDates,
      });
    } catch (error) {
      console.error('Failed to load contact:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadReferrals = async () => {
    if (!user || isNewContact) return;
    
    try {
      const data = await contactsAPI.getReferrals(user._id, id as string);
      setReferrals(data || []);
    } catch (error) {
      console.error('Failed to load referrals:', error);
    }
  };
  
  const loadAllContacts = async () => {
    if (!user) return;
    
    try {
      const data = await contactsAPI.getAll(user._id);
      // Filter out current contact
      setAllContacts(data.filter((c: any) => c._id !== id));
    } catch (error) {
      console.error('Failed to load contacts:', error);
    }
  };
  
  const openReferralPicker = () => {
    loadAllContacts();
    setShowReferralPicker(true);
  };
  
  const openCampaignPicker = () => {
    setShowCampaignPicker(true);
  };
  
  const enrollInCampaign = async (campaign: any) => {
    if (!user) return;
    
    // Close modal immediately - no spinner needed
    setShowCampaignPicker(false);
    
    try {
      await campaignsAPI.enrollContact(user._id, campaign._id, id as string);
      showSimpleAlert('Enrolled!', `Contact enrolled in "${campaign.name}"`);
      loadCampaignsAndEnrollments();
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to enroll contact';
      showSimpleAlert('Error', message);
    }
  };
  
  const cancelEnrollment = async (enrollment: any) => {
    if (!user) return;
    try {
      await campaignsAPI.cancelEnrollment(user._id, enrollment.campaign_id, enrollment._id);
      // Immediately update local state to remove the enrollment
      setContactEnrollments(prev => prev.filter(e => e._id !== enrollment._id));
    } catch (error) {
      showSimpleAlert('Error', 'Failed to cancel enrollment');
    }
  };

  // Render delete action for swipeable (enrolled campaigns - swipe left to remove)
  const renderRightActions = (enrollment: any) => {
    return (
      <TouchableOpacity
        style={styles.swipeDeleteAction}
        onPress={() => cancelEnrollment(enrollment)}
      >
        <Ionicons name="trash" size={24} color="#FFF" />
        <Text style={styles.swipeDeleteText}>Remove</Text>
      </TouchableOpacity>
    );
  };
  
  // Render enroll action for swipeable (available campaigns - swipe right to add)
  const renderLeftActions = (campaign: any) => {
    return (
      <TouchableOpacity
        style={styles.swipeEnrollAction}
        onPress={() => enrollInCampaign(campaign)}
      >
        <Ionicons name="add-circle" size={24} color="#FFF" />
        <Text style={styles.swipeEnrollText}>Enroll</Text>
      </TouchableOpacity>
    );
  };
  
  // Get available campaigns (not yet enrolled)
  const availableCampaigns = campaigns.filter(c => 
    !contactEnrollments.some(e => e.campaign_id === c._id && e.status === 'active')
  );
  
  const selectReferrer = (referrer: any) => {
    setContact({
      ...contact,
      referred_by: referrer._id,
      referred_by_name: `${referrer.first_name} ${referrer.last_name || ''}`.trim(),
    });
    setShowReferralPicker(false);
  };
  
  const clearReferrer = () => {
    setContact({
      ...contact,
      referred_by: null,
      referred_by_name: null,
    });
  };
  
  const requestCameraPermission = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      showSimpleAlert(
        'Permission Required',
        'Camera permission is needed to take photos.'
      );
      return false;
    }
    return true;
  };
  
  const requestGalleryPermission = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      showSimpleAlert(
        'Permission Required',
        'Gallery access is needed to select photos.'
      );
      return false;
    }
    return true;
  };
  
  const takePhoto = async () => {
    const hasPermission = await requestCameraPermission();
    if (!hasPermission) return;
    
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });
    
    if (!result.canceled && result.assets[0].base64) {
      setContact({
        ...contact,
        photo: `data:image/jpeg;base64,${result.assets[0].base64}`,
      });
    }
  };
  
  const pickImage = async () => {
    const hasPermission = await requestGalleryPermission();
    if (!hasPermission) return;
    
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });
    
    if (!result.canceled && result.assets[0].base64) {
      setContact({
        ...contact,
        photo: `data:image/jpeg;base64,${result.assets[0].base64}`,
      });
    }
  };
  
  const showPhotoOptions = () => {
    showAlert('Add Photo', 'Choose an option', [
      {
        text: 'Take Photo',
        onPress: takePhoto,
      },
      {
        text: 'Choose from Gallery',
        onPress: pickImage,
      },
    ]);
  };

  // Date picker functions
  const openDatePicker = (field: string, currentDate: Date | null, label?: string) => {
    const dateToUse = currentDate || new Date();
    setActiveDateField(field);
    setActiveDateLabel(label || field);
    setTempDate(dateToUse);
    // Initialize web picker values
    setWebMonth(dateToUse.getMonth());
    setWebDay(dateToUse.getDate());
    setWebYear(dateToUse.getFullYear());
    setShowDatePicker(true);
  };

  const handleDateChange = (event: any, selectedDate?: Date) => {
    // On Android, the picker auto-dismisses after selection
    if (Platform.OS === 'android') {
      setShowDatePicker(false);
      if (event.type === 'set' && selectedDate && activeDateField) {
        // Handle new custom date flow on Android
        if (activeDateField === 'pending_custom') {
          handlePendingCustomDateSelected(selectedDate);
        } else {
          saveDateToField(selectedDate);
        }
      }
      return;
    }
    
    // On iOS, update the temp date (user will confirm with Done)
    if (selectedDate) {
      setTempDate(selectedDate);
    }
  };

  const saveDateToField = (dateToSave: Date) => {
    if (!activeDateField) return;
    
    if (activeDateField.startsWith('custom_')) {
      // Handle custom date fields
      const index = parseInt(activeDateField.replace('custom_', ''));
      const newCustomDates = [...contact.custom_dates];
      newCustomDates[index] = { ...newCustomDates[index], date: dateToSave };
      setContact({ ...contact, custom_dates: newCustomDates });
    } else {
      // Handle standard date fields
      setContact({ ...contact, [activeDateField]: dateToSave });
    }
  };

  const confirmDateSelection = () => {
    // For web, construct date from web picker values
    let dateToUse = tempDate;
    if (Platform.OS === 'web') {
      dateToUse = new Date(webYear, webMonth, webDay);
    }
    
    // Handle the new custom date flow (date picked first)
    if (activeDateField === 'pending_custom') {
      handlePendingCustomDateSelected(dateToUse);
      return;
    }
    
    saveDateToField(dateToUse);
    setShowDatePicker(false);
    setActiveDateField(null);
  };

  // Helper for web date picker
  const getDaysInMonth = (month: number, year: number) => {
    return new Date(year, month + 1, 0).getDate();
  };

  const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                  'July', 'August', 'September', 'October', 'November', 'December'];

  const cancelDateSelection = () => {
    setShowDatePicker(false);
    setActiveDateField(null);
  };

  const clearDate = (field: string) => {
    if (field.startsWith('custom_')) {
      const index = parseInt(field.replace('custom_', ''));
      const newCustomDates = [...contact.custom_dates];
      newCustomDates[index] = { ...newCustomDates[index], date: null };
      setContact({ ...contact, custom_dates: newCustomDates });
    } else {
      setContact({ ...contact, [field]: null });
    }
  };

  // New flow: Open date picker FIRST, then ask for label
  const openAddCustomDate = () => {
    setPendingCustomDate(null);
    setNewCustomDateName('');
    // Open date picker directly - date first, label second
    setTempDate(new Date());
    setActiveDateField('pending_custom');
    setActiveDateLabel('Select Date');
    setShowDatePicker(true);
  };

  // Called when date is picked for new custom field
  const handlePendingCustomDateSelected = (selectedDate: Date) => {
    setPendingCustomDate(selectedDate);
    setShowDatePicker(false);
    // Now show the label input modal
    setTimeout(() => {
      setShowCustomDateLabel(true);
    }, 300);
  };

  // Called when user confirms the label for the custom date
  const confirmCustomDateWithLabel = () => {
    if (!newCustomDateName.trim()) {
      showSimpleAlert('Error', 'Please enter a name for the date field');
      return;
    }
    
    if (!pendingCustomDate) {
      showSimpleAlert('Error', 'No date selected');
      return;
    }
    
    const newCustomDates = [...contact.custom_dates, { 
      name: newCustomDateName.trim(), 
      date: pendingCustomDate 
    }];
    setContact({ ...contact, custom_dates: newCustomDates });
    
    // Reset state
    setNewCustomDateName('');
    setPendingCustomDate(null);
    setShowCustomDateLabel(false);
  };

  const cancelCustomDateLabel = () => {
    setNewCustomDateName('');
    setPendingCustomDate(null);
    setShowCustomDateLabel(false);
  };

  const removeCustomDateField = (index: number) => {
    showConfirm(
      'Remove Date Field',
      `Remove "${contact.custom_dates[index].name}" field?`,
      () => {
        const newCustomDates = contact.custom_dates.filter((_, i) => i !== index);
        setContact({ ...contact, custom_dates: newCustomDates });
      },
      undefined,
      'Remove',
      'Cancel'
    );
  };

  const formatDateDisplay = (date: Date | null): string => {
    if (!date) return 'Not set';
    return format(date, 'MMM d, yyyy');
  };

  const getDateFieldLabel = (field: string): string => {
    switch (field) {
      case 'birthday': return 'Birthday';
      case 'anniversary': return 'Anniversary';
      case 'date_sold': return 'Date Sold';
      default:
        if (field.startsWith('custom_')) {
          const index = parseInt(field.replace('custom_', ''));
          return contact.custom_dates[index]?.name || 'Custom Date';
        }
        return 'Select Date';
    }
  };
  
  const addTagFromPicker = (tagName: string) => {
    if (!contact.tags.includes(tagName)) {
      setContact({
        ...contact,
        tags: [...contact.tags, tagName],
      });
    }
    setShowTagPicker(false);
    setTagSearch('');
  };
  
  const removeTag = (tag: string) => {
    setContact({
      ...contact,
      tags: contact.tags.filter((t) => t !== tag),
    });
  };
  
  // Filter tags that are not already assigned and match search
  const filteredAvailableTags = availableTags.filter(
    (tag) => 
      !contact.tags.includes(tag.name) &&
      tag.name.toLowerCase().includes(tagSearch.toLowerCase())
  );
  
  const handleSave = async () => {
    if (!contact.first_name || !contact.phone) {
      showSimpleAlert('Error', 'Name and phone number are required');
      return;
    }
    
    if (!user) {
      showSimpleAlert('Error', 'Please log in to save contacts');
      return;
    }
    
    try {
      setSaving(true);
      
      if (isNewContact) {
        await contactsAPI.create(user._id, contact);
      } else {
        await contactsAPI.update(user._id, id as string, contact);
      }
      
      showAlert('Success', 'Contact saved!', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Failed to save contact';
      showSimpleAlert('Error', errorMessage);
      console.error('Save contact error:', error);
    } finally {
      setSaving(false);
    }
  };
  
  const filteredContacts = allContacts.filter(c => {
    const name = `${c.first_name} ${c.last_name || ''}`.toLowerCase();
    return name.includes(contactSearch.toLowerCase());
  });
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="close" size={28} color="#007AFF" />
          </TouchableOpacity>
          
          <Text style={styles.headerTitle}>
            {isNewContact ? 'New Contact' : 'Edit Contact'}
          </Text>
          
          <TouchableOpacity onPress={handleSave} style={styles.saveButton} disabled={saving}>
            {saving ? (
              <ActivityIndicator size="small" color="#007AFF" />
            ) : (
              <Text style={styles.saveButtonText}>Save</Text>
            )}
          </TouchableOpacity>
        </View>
        
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Quick Status - Show for new contacts */}
          {isNewContact && (
            <View style={styles.quickStatusSection}>
              <Text style={styles.sectionTitle}>Customer Status</Text>
              <View style={styles.statusButtons}>
                <TouchableOpacity
                  style={[
                    styles.statusButton,
                    contact.tags.includes('lead') && styles.statusButtonActive,
                  ]}
                  onPress={() => {
                    if (contact.tags.includes('lead')) {
                      setContact({ ...contact, tags: contact.tags.filter(t => t !== 'lead') });
                    } else {
                      setContact({ ...contact, tags: [...contact.tags.filter(t => t !== 'sold'), 'lead'] });
                    }
                  }}
                >
                  <Ionicons name="flame" size={20} color={contact.tags.includes('lead') ? '#FF9500' : '#8E8E93'} />
                  <Text style={[styles.statusButtonText, contact.tags.includes('lead') && { color: '#FF9500' }]}>Lead</Text>
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={[
                    styles.statusButton,
                    contact.tags.includes('sold') && styles.statusButtonSold,
                  ]}
                  onPress={() => {
                    if (contact.tags.includes('sold')) {
                      // Removing sold tag - also clear date_sold
                      setContact({ 
                        ...contact, 
                        tags: contact.tags.filter(t => t !== 'sold'),
                        date_sold: null 
                      });
                    } else {
                      // Adding sold tag - prompt for date
                      setContact({ ...contact, tags: [...contact.tags.filter(t => t !== 'lead'), 'sold'] });
                      // Open date picker for Date Sold
                      setTimeout(() => {
                        openDatePicker('date_sold', null, 'Date Sold');
                      }, 300);
                    }
                  }}
                >
                  <Ionicons name="checkmark-circle" size={20} color={contact.tags.includes('sold') ? '#34C759' : '#8E8E93'} />
                  <Text style={[styles.statusButtonText, contact.tags.includes('sold') && { color: '#34C759' }]}>Sold</Text>
                </TouchableOpacity>
              </View>
              
              {/* Referral prompt when sold is selected */}
              {contact.tags.includes('sold') && !contact.referred_by && (
                <TouchableOpacity 
                  style={styles.referralPrompt}
                  onPress={openReferralPicker}
                >
                  <View style={styles.referralPromptIcon}>
                    <Ionicons name="gift" size={24} color="#34C759" />
                  </View>
                  <View style={styles.referralPromptContent}>
                    <Text style={styles.referralPromptTitle}>Who referred this customer?</Text>
                    <Text style={styles.referralPromptSubtitle}>Track referrals to reward your best advocates</Text>
                  </View>
                  <Ionicons name="add-circle" size={28} color="#34C759" />
                </TouchableOpacity>
              )}
              
              {/* Show selected referrer */}
              {contact.tags.includes('sold') && contact.referred_by_name && (
                <View style={styles.referrerBadge}>
                  <Ionicons name="people" size={18} color="#34C759" />
                  <Text style={styles.referrerBadgeText}>Referred by {contact.referred_by_name}</Text>
                  <TouchableOpacity onPress={clearReferrer}>
                    <Ionicons name="close-circle" size={20} color="#8E8E93" />
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}
          
          {/* Photo Section */}
          <View style={styles.photoSection}>
            <TouchableOpacity
              style={styles.photoContainer}
              onPress={showPhotoOptions}
            >
              {contact.photo ? (
                <Image source={{ uri: contact.photo }} style={styles.photo} />
              ) : (
                <View style={styles.photoPlaceholder}>
                  <Ionicons name="person" size={48} color="#8E8E93" />
                </View>
              )}
              <View style={styles.photoEditBadge}>
                <Ionicons name="camera" size={16} color="#FFF" />
              </View>
            </TouchableOpacity>
            <Text style={styles.photoLabel}>Tap to add photo</Text>
          </View>
          
          {/* Name Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Basic Info</Text>
            
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>First Name *</Text>
              <TextInput
                style={styles.input}
                placeholder="Enter first name"
                placeholderTextColor="#8E8E93"
                value={contact.first_name}
                onChangeText={(text) =>
                  setContact({ ...contact, first_name: text })
                }
              />
            </View>
            
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Last Name</Text>
              <TextInput
                style={styles.input}
                placeholder="Enter last name"
                placeholderTextColor="#8E8E93"
                value={contact.last_name}
                onChangeText={(text) =>
                  setContact({ ...contact, last_name: text })
                }
              />
            </View>
            
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Phone *</Text>
              <TextInput
                style={styles.input}
                placeholder="+1 (555) 123-4567"
                placeholderTextColor="#8E8E93"
                value={contact.phone}
                onChangeText={(text) => setContact({ ...contact, phone: text })}
                keyboardType="phone-pad"
              />
            </View>
            
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Email</Text>
              <TextInput
                style={styles.input}
                placeholder="email@example.com"
                placeholderTextColor="#8E8E93"
                value={contact.email}
                onChangeText={(text) => setContact({ ...contact, email: text })}
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>
          </View>
          
          {/* Vehicle Info */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Vehicle Info</Text>
            
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Vehicle</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 2023 Toyota RAV4"
                placeholderTextColor="#8E8E93"
                value={contact.vehicle}
                onChangeText={(text) =>
                  setContact({ ...contact, vehicle: text })
                }
              />
            </View>
          </View>
          
          {/* Important Dates Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Important Dates</Text>
            
            {/* Birthday */}
            <TouchableOpacity 
              style={styles.dateField}
              onPress={() => openDatePicker('birthday', contact.birthday)}
            >
              <View style={[styles.dateIcon, { backgroundColor: '#FF9500' + '20' }]}>
                <Ionicons name="gift" size={20} color="#FF9500" />
              </View>
              <View style={styles.dateInfo}>
                <Text style={styles.dateLabel}>Birthday</Text>
                <Text style={[styles.dateValue, !contact.birthday && styles.datePlaceholder]}>
                  {formatDateDisplay(contact.birthday)}
                </Text>
              </View>
              {contact.birthday && (
                <TouchableOpacity onPress={() => clearDate('birthday')} style={styles.clearDateButton}>
                  <Ionicons name="close-circle" size={22} color="#8E8E93" />
                </TouchableOpacity>
              )}
              <Ionicons name="calendar" size={22} color="#8E8E93" />
            </TouchableOpacity>
            
            {/* Anniversary */}
            <TouchableOpacity 
              style={styles.dateField}
              onPress={() => openDatePicker('anniversary', contact.anniversary)}
            >
              <View style={[styles.dateIcon, { backgroundColor: '#FF2D55' + '20' }]}>
                <Ionicons name="heart" size={20} color="#FF2D55" />
              </View>
              <View style={styles.dateInfo}>
                <Text style={styles.dateLabel}>Anniversary</Text>
                <Text style={[styles.dateValue, !contact.anniversary && styles.datePlaceholder]}>
                  {formatDateDisplay(contact.anniversary)}
                </Text>
              </View>
              {contact.anniversary && (
                <TouchableOpacity onPress={() => clearDate('anniversary')} style={styles.clearDateButton}>
                  <Ionicons name="close-circle" size={22} color="#8E8E93" />
                </TouchableOpacity>
              )}
              <Ionicons name="calendar" size={22} color="#8E8E93" />
            </TouchableOpacity>
            
            {/* Date Sold */}
            <TouchableOpacity 
              style={styles.dateField}
              onPress={() => openDatePicker('date_sold', contact.date_sold)}
            >
              <View style={[styles.dateIcon, { backgroundColor: '#34C759' + '20' }]}>
                <Ionicons name="car" size={20} color="#34C759" />
              </View>
              <View style={styles.dateInfo}>
                <Text style={styles.dateLabel}>Date Sold</Text>
                <Text style={[styles.dateValue, !contact.date_sold && styles.datePlaceholder]}>
                  {formatDateDisplay(contact.date_sold)}
                </Text>
              </View>
              {contact.date_sold && (
                <TouchableOpacity onPress={() => clearDate('date_sold')} style={styles.clearDateButton}>
                  <Ionicons name="close-circle" size={22} color="#8E8E93" />
                </TouchableOpacity>
              )}
              <Ionicons name="calendar" size={22} color="#8E8E93" />
            </TouchableOpacity>
            
            {/* Custom Date Fields */}
            {contact.custom_dates.map((customDate, index) => (
              <TouchableOpacity 
                key={index}
                style={styles.dateField}
                onPress={() => openDatePicker(`custom_${index}`, customDate.date)}
              >
                <View style={[styles.dateIcon, { backgroundColor: '#007AFF' + '20' }]}>
                  <Ionicons name="calendar-outline" size={20} color="#007AFF" />
                </View>
                <View style={styles.dateInfo}>
                  <Text style={styles.dateLabel}>{customDate.name}</Text>
                  <Text style={[styles.dateValue, !customDate.date && styles.datePlaceholder]}>
                    {formatDateDisplay(customDate.date)}
                  </Text>
                </View>
                {customDate.date && (
                  <TouchableOpacity onPress={() => clearDate(`custom_${index}`)} style={styles.clearDateButton}>
                    <Ionicons name="close-circle" size={22} color="#8E8E93" />
                  </TouchableOpacity>
                )}
                <TouchableOpacity onPress={() => removeCustomDateField(index)} style={styles.deleteDateButton}>
                  <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                </TouchableOpacity>
              </TouchableOpacity>
            ))}
            
            {/* Add Custom Date Button */}
            <TouchableOpacity 
              style={styles.addCustomDateButton}
              onPress={openAddCustomDate}
            >
              <Ionicons name="add-circle" size={22} color="#007AFF" />
              <Text style={styles.addCustomDateText}>Add Custom Date Field</Text>
            </TouchableOpacity>
          </View>
          
          {/* Referral Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Referral</Text>
            
            <TouchableOpacity 
              style={styles.referralSelector}
              onPress={openReferralPicker}
            >
              <View style={styles.referralIcon}>
                <Ionicons name="people" size={24} color="#34C759" />
              </View>
              <View style={styles.referralInfo}>
                <Text style={styles.referralLabel}>Referred By</Text>
                {contact.referred_by_name ? (
                  <Text style={styles.referralName}>{contact.referred_by_name}</Text>
                ) : (
                  <Text style={styles.referralPlaceholder}>Select who referred this contact</Text>
                )}
              </View>
              {contact.referred_by ? (
                <TouchableOpacity onPress={clearReferrer} style={styles.clearButton}>
                  <Ionicons name="close-circle" size={24} color="#8E8E93" />
                </TouchableOpacity>
              ) : (
                <Ionicons name="chevron-forward" size={24} color="#8E8E93" />
              )}
            </TouchableOpacity>
            
            {contact.referred_by && (
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Referral Notes</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., Met at John's BBQ, interested in SUVs"
                  placeholderTextColor="#8E8E93"
                  value={contact.referral_notes}
                  onChangeText={(text) =>
                    setContact({ ...contact, referral_notes: text })
                  }
                />
              </View>
            )}
            
            {/* Show referrals made by this contact */}
            {!isNewContact && contact.referral_count > 0 && (
              <View style={styles.referralStats}>
                <View style={styles.referralStatIcon}>
                  <Ionicons name="trophy" size={20} color="#FF9500" />
                </View>
                <Text style={styles.referralStatText}>
                  This contact has referred {contact.referral_count} customer{contact.referral_count > 1 ? 's' : ''}
                </Text>
              </View>
            )}
            
            {referrals.length > 0 && (
              <View style={styles.referralsList}>
                <Text style={styles.referralsTitle}>People Referred</Text>
                {referrals.map((ref, index) => (
                  <TouchableOpacity 
                    key={ref._id}
                    style={styles.referralItem}
                    onPress={() => router.push(`/contact/${ref._id}`)}
                  >
                    <View style={styles.referralAvatar}>
                      <Text style={styles.referralAvatarText}>
                        {ref.first_name?.[0]}{ref.last_name?.[0]}
                      </Text>
                    </View>
                    <View style={styles.referralItemInfo}>
                      <Text style={styles.referralItemName}>
                        {ref.first_name} {ref.last_name || ''}
                      </Text>
                      {ref.vehicle && (
                        <Text style={styles.referralItemVehicle}>{ref.vehicle}</Text>
                      )}
                    </View>
                    <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
          
          {/* Tags */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Tags</Text>
            
            {/* Current tags */}
            <View style={styles.tagContainer}>
              {contact.tags.map((tag, index) => {
                const tagInfo = availableTags.find(t => t.name === tag);
                return (
                  <TouchableOpacity
                    key={index}
                    style={[styles.tag, tagInfo?.color && { borderColor: tagInfo.color }]}
                    onPress={() => removeTag(tag)}
                  >
                    {tagInfo?.icon && (
                      <Ionicons name={tagInfo.icon as any} size={14} color={tagInfo.color || '#8E8E93'} style={{ marginRight: 4 }} />
                    )}
                    <Text style={[styles.tagText, tagInfo?.color && { color: tagInfo.color }]}>{tag}</Text>
                    <Ionicons name="close-circle" size={16} color="#8E8E93" style={{ marginLeft: 4 }} />
                  </TouchableOpacity>
                );
              })}
            </View>
            
            {/* Add tag button */}
            <TouchableOpacity 
              style={styles.addTagButtonLarge}
              onPress={() => {
                loadTags();
                setShowTagPicker(true);
              }}
              data-testid="add-tag-button"
            >
              <Ionicons name="pricetag-outline" size={20} color="#007AFF" />
              <Text style={styles.addTagButtonText}>Add Tag</Text>
            </TouchableOpacity>
          </View>
          
          {/* Campaigns Section - Only show for existing contacts */}
          {!isNewContact && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Campaigns</Text>
              
              {/* Current Enrollments - Swipe left to remove */}
              {contactEnrollments.length > 0 && (
                <View style={styles.enrollmentsList}>
                  <Text style={styles.enrollmentSubtitle}>Enrolled (swipe left to remove)</Text>
                  {contactEnrollments.map((enrollment, index) => (
                    <Swipeable
                      key={enrollment._id || index}
                      renderRightActions={() => renderRightActions(enrollment)}
                      overshootRight={false}
                    >
                      <View style={styles.enrollmentCard}>
                        <View style={styles.enrollmentIcon}>
                          <Ionicons 
                            name={enrollment.status === 'completed' ? 'checkmark-circle' : 'play-circle'} 
                            size={24} 
                            color={enrollment.status === 'completed' ? '#34C759' : '#007AFF'} 
                          />
                        </View>
                        <View style={styles.enrollmentInfo}>
                          <Text style={styles.enrollmentName}>{enrollment.campaign_name}</Text>
                          <Text style={styles.enrollmentStatus}>
                            {enrollment.status === 'completed' 
                              ? 'Completed' 
                              : `Step ${enrollment.current_step} of ${enrollment.total_steps}`}
                          </Text>
                          {enrollment.messages_sent?.length > 0 && (
                            <Text style={styles.enrollmentSent}>
                              {enrollment.messages_sent.length} message{enrollment.messages_sent.length !== 1 ? 's' : ''} sent
                            </Text>
                          )}
                        </View>
                        {enrollment.status === 'active' && (
                          <Ionicons name="chevron-back" size={16} color="#8E8E93" />
                        )}
                      </View>
                    </Swipeable>
                  ))}
                </View>
              )}
              
              {/* Available Campaigns - Swipe right to add */}
              {availableCampaigns.length > 0 && (
                <View style={styles.enrollmentsList}>
                  <Text style={styles.enrollmentSubtitle}>Available (swipe right to enroll)</Text>
                  {availableCampaigns.map((campaign, index) => (
                    <Swipeable
                      key={campaign._id || index}
                      renderLeftActions={() => renderLeftActions(campaign)}
                      overshootLeft={false}
                    >
                      <View style={styles.availableCampaignCard}>
                        <View style={[styles.enrollmentIcon, { backgroundColor: '#48484A20' }]}>
                          <Ionicons 
                            name="megaphone-outline" 
                            size={24} 
                            color="#8E8E93" 
                          />
                        </View>
                        <View style={styles.enrollmentInfo}>
                          <Text style={styles.availableCampaignName}>{campaign.name}</Text>
                          <Text style={styles.enrollmentStatus}>
                            {campaign.sequences?.length || 0} step{(campaign.sequences?.length || 0) !== 1 ? 's' : ''}
                            {campaign.type === 'birthday' && ' • Birthday'}
                            {campaign.type === 'anniversary' && ' • Anniversary'}
                          </Text>
                        </View>
                        <Ionicons name="chevron-forward" size={16} color="#8E8E93" />
                      </View>
                    </Swipeable>
                  ))}
                </View>
              )}
              
              {/* Enroll Button - Only show if there are available campaigns */}
              {availableCampaigns.length > 0 && (
                <TouchableOpacity 
                  style={styles.enrollButton}
                  onPress={openCampaignPicker}
                >
                  <Ionicons name="add-circle" size={24} color="#007AFF" />
                  <Text style={styles.enrollButtonText}>Enroll in Campaign</Text>
                </TouchableOpacity>
              )}
              
              {campaigns.length === 0 && contactEnrollments.length === 0 && (
                <Text style={styles.noCampaignsText}>
                  No active campaigns. Create a campaign first.
                </Text>
              )}
            </View>
          )}
          
          {/* Notes */}
          <View style={styles.section}>
            <View style={styles.notesHeader}>
              <Text style={[styles.sectionTitle, { marginBottom: 0 }]}>Notes</Text>
              <VoiceInput
                onTranscription={(text) => setContact({ ...contact, notes: contact.notes + ' ' + text })}
                size="small"
                color="#8E8E93"
              />
            </View>
            
            <TextInput
              style={[styles.input, styles.textArea]}
              placeholder="Add notes about this contact..."
              placeholderTextColor="#8E8E93"
              value={contact.notes}
              onChangeText={(text) => setContact({ ...contact, notes: text })}
              multiline
              numberOfLines={6}
              textAlignVertical="top"
            />
          </View>
          
          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
      
      {/* Referral Picker Modal */}
      <Modal
        visible={showReferralPicker}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowReferralPicker(false)}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Select Referrer</Text>
            <View style={{ width: 60 }} />
          </View>
          
          <View style={styles.modalSearch}>
            <Ionicons name="search" size={20} color="#8E8E93" />
            <TextInput
              style={styles.modalSearchInput}
              placeholder="Search contacts"
              placeholderTextColor="#8E8E93"
              value={contactSearch}
              onChangeText={setContactSearch}
            />
          </View>
          
          <FlatList
            data={filteredContacts}
            keyExtractor={(item) => item._id}
            renderItem={({ item }) => (
              <TouchableOpacity 
                style={styles.pickerItem}
                onPress={() => selectReferrer(item)}
              >
                <View style={styles.pickerAvatar}>
                  <Text style={styles.pickerAvatarText}>
                    {item.first_name?.[0]}{item.last_name?.[0] || ''}
                  </Text>
                </View>
                <View style={styles.pickerInfo}>
                  <Text style={styles.pickerName}>
                    {item.first_name} {item.last_name || ''}
                  </Text>
                  <Text style={styles.pickerPhone}>{item.phone}</Text>
                </View>
              </TouchableOpacity>
            )}
            ListEmptyComponent={() => (
              <View style={styles.emptyPicker}>
                <Text style={styles.emptyPickerText}>No contacts found</Text>
              </View>
            )}
          />
        </SafeAreaView>
      </Modal>
      
      {/* Campaign Picker Modal */}
      <Modal
        visible={showCampaignPicker}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowCampaignPicker(false)}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Enroll in Campaign</Text>
            <View style={{ width: 60 }} />
          </View>
          
          <FlatList
            data={campaigns.filter(c => 
              !contactEnrollments.some(e => e.campaign_id === c._id && e.status === 'active')
            )}
            keyExtractor={(item) => item._id}
            contentContainerStyle={{ padding: 16 }}
            renderItem={({ item }) => (
              <TouchableOpacity 
                style={styles.campaignPickerItem}
                onPress={() => enrollInCampaign(item)}
              >
                <View style={styles.campaignPickerIcon}>
                  <Ionicons name="calendar" size={24} color="#007AFF" />
                </View>
                <View style={styles.campaignPickerInfo}>
                  <Text style={styles.campaignPickerName}>{item.name}</Text>
                  <Text style={styles.campaignPickerSteps}>
                    {item.sequences?.length || 0} step{(item.sequences?.length || 0) !== 1 ? 's' : ''} • {item.type || 'custom'}
                  </Text>
                </View>
                <Ionicons name="add-circle" size={28} color="#007AFF" />
              </TouchableOpacity>
            )}
            ListEmptyComponent={() => (
              <View style={styles.emptyPicker}>
                <Ionicons name="calendar-outline" size={48} color="#2C2C2E" />
                <Text style={styles.emptyPickerText}>No available campaigns</Text>
                <Text style={styles.emptyPickerSubtext}>
                  {contactEnrollments.length > 0 
                    ? 'Contact is already enrolled in all active campaigns'
                    : 'Create a campaign first'}
                </Text>
              </View>
            )}
          />
        </SafeAreaView>
      </Modal>
      
      {/* Tag Picker Modal */}
      <Modal
        visible={showTagPicker}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => { setShowTagPicker(false); setTagSearch(''); }}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Select Tag</Text>
            <TouchableOpacity onPress={() => router.push('/settings/tags')}>
              <Text style={styles.modalAction}>Manage</Text>
            </TouchableOpacity>
          </View>
          
          {/* Search Input */}
          <View style={styles.tagSearchContainer}>
            <Ionicons name="search" size={20} color="#8E8E93" />
            <TextInput
              style={styles.tagSearchInput}
              placeholder="Search tags..."
              placeholderTextColor="#8E8E93"
              value={tagSearch}
              onChangeText={setTagSearch}
              autoCapitalize="none"
            />
            {tagSearch ? (
              <TouchableOpacity onPress={() => setTagSearch('')}>
                <Ionicons name="close-circle" size={20} color="#8E8E93" />
              </TouchableOpacity>
            ) : null}
          </View>
          
          <ScrollView style={styles.tagPickerList}>
            {filteredAvailableTags.length > 0 ? (
              filteredAvailableTags.map((tag) => (
                <TouchableOpacity 
                  key={tag._id}
                  style={styles.tagPickerItem}
                  onPress={() => addTagFromPicker(tag.name)}
                  data-testid={`tag-option-${tag.name}`}
                >
                  <View style={[styles.tagPickerIcon, { backgroundColor: `${tag.color}20` }]}>
                    <Ionicons name={tag.icon || 'pricetag'} size={20} color={tag.color} />
                  </View>
                  <View style={styles.tagPickerInfo}>
                    <Text style={styles.tagPickerName}>{tag.name}</Text>
                    <Text style={styles.tagPickerCount}>
                      {tag.contact_count || 0} contact{(tag.contact_count || 0) !== 1 ? 's' : ''}
                    </Text>
                  </View>
                  <Ionicons name="add-circle" size={28} color={tag.color} />
                </TouchableOpacity>
              ))
            ) : (
              <View style={styles.emptyPicker}>
                <Ionicons name="pricetag-outline" size={48} color="#2C2C2E" />
                <Text style={styles.emptyPickerText}>
                  {tagSearch ? 'No matching tags' : 'No tags available'}
                </Text>
                <Text style={styles.emptyPickerSubtext}>
                  {contact.tags.length > 0 
                    ? 'All available tags are assigned'
                    : 'Create tags in Settings > Tags'}
                </Text>
              </View>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Date Picker Modal */}
      {showDatePicker && (
        <Modal
          visible={showDatePicker}
          animationType={Platform.OS === 'web' ? 'none' : 'slide'}
          transparent={true}
          onRequestClose={cancelDateSelection}
        >
          <View style={styles.datePickerOverlay}>
            <TouchableOpacity 
              style={styles.datePickerDismiss} 
              activeOpacity={1} 
              onPress={cancelDateSelection}
            />
            <View style={[styles.datePickerModal, Platform.OS === 'web' && { minHeight: 400 }]}>
              <View style={styles.datePickerHeader}>
                <TouchableOpacity onPress={cancelDateSelection}>
                  <Text style={styles.datePickerCancel}>Cancel</Text>
                </TouchableOpacity>
                <Text style={styles.datePickerTitle}>
                  {activeDateLabel || getDateFieldLabel(activeDateField || '')}
                </Text>
                <TouchableOpacity onPress={confirmDateSelection}>
                  <Text style={styles.datePickerDone}>Done</Text>
                </TouchableOpacity>
              </View>
              
              {/* Web-specific date picker with dropdowns */}
              {Platform.OS === 'web' && (
                <View style={styles.webDatePickerContainer}>
                  {/* Month Picker */}
                  <View style={styles.webPickerColumn}>
                    <Text style={styles.webPickerLabel}>MONTH</Text>
                    <ScrollView style={styles.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {months.map((month, index) => (
                        <TouchableOpacity
                          key={month}
                          style={[
                            styles.webPickerItem,
                            webMonth === index && styles.webPickerItemSelected
                          ]}
                          onPress={() => {
                            setWebMonth(index);
                            const maxDays = getDaysInMonth(index, webYear);
                            if (webDay > maxDays) setWebDay(maxDays);
                          }}
                        >
                          <Text style={[
                            styles.webPickerItemText,
                            webMonth === index && styles.webPickerItemTextSelected
                          ]}>{month}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                  
                  {/* Day Picker */}
                  <View style={styles.webPickerColumn}>
                    <Text style={styles.webPickerLabel}>DAY</Text>
                    <ScrollView style={styles.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {Array.from({ length: getDaysInMonth(webMonth, webYear) }, (_, i) => i + 1).map(day => (
                        <TouchableOpacity
                          key={day}
                          style={[
                            styles.webPickerItem,
                            webDay === day && styles.webPickerItemSelected
                          ]}
                          onPress={() => setWebDay(day)}
                        >
                          <Text style={[
                            styles.webPickerItemText,
                            webDay === day && styles.webPickerItemTextSelected
                          ]}>{day}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                  
                  {/* Year Picker */}
                  <View style={styles.webPickerColumn}>
                    <Text style={styles.webPickerLabel}>YEAR</Text>
                    <ScrollView style={styles.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {Array.from({ length: 100 }, (_, i) => new Date().getFullYear() - 50 + i).map(year => (
                        <TouchableOpacity
                          key={year}
                          style={[
                            styles.webPickerItem,
                            webYear === year && styles.webPickerItemSelected
                          ]}
                          onPress={() => {
                            setWebYear(year);
                            const maxDays = getDaysInMonth(webMonth, year);
                            if (webDay > maxDays) setWebDay(maxDays);
                          }}
                        >
                          <Text style={[
                            styles.webPickerItemText,
                            webYear === year && styles.webPickerItemTextSelected
                          ]}>{year}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                </View>
              )}
              
              {/* Native date picker for iOS/Android only */}
              {Platform.OS !== 'web' && (
                <DateTimePicker
                  value={tempDate}
                  mode="date"
                  display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                  onChange={handleDateChange}
                  textColor="#FFFFFF"
                  themeVariant="dark"
                  style={styles.datePicker}
                  maximumDate={new Date(2100, 11, 31)}
                  minimumDate={new Date(1900, 0, 1)}
                />
              )}
              
              {/* Confirmation button for iOS and Web */}
              {(Platform.OS === 'ios' || Platform.OS === 'web') && (
                <View style={styles.datePickerActions}>
                  <TouchableOpacity 
                    style={styles.datePickerConfirmButton}
                    onPress={confirmDateSelection}
                  >
                    <Text style={styles.datePickerConfirmText}>
                      Select {Platform.OS === 'web' 
                        ? format(new Date(webYear, webMonth, webDay), 'MMM d, yyyy')
                        : format(tempDate, 'MMM d, yyyy')}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </View>
        </Modal>
      )}

      {/* Custom Date Label Modal - Shows AFTER date is picked */}
      <Modal
        visible={showCustomDateLabel}
        animationType="fade"
        transparent={true}
        onRequestClose={cancelCustomDateLabel}
      >
        <TouchableOpacity 
          style={styles.labelModalOverlay}
          activeOpacity={1} 
          onPress={cancelCustomDateLabel}
        >
          <TouchableOpacity 
            activeOpacity={1} 
            style={styles.labelModalContent}
            onPress={() => {}} 
          >
            <Text style={styles.customDateTitle}>Name This Date</Text>
            <Text style={styles.customDateSubtitle}>
              {pendingCustomDate ? format(pendingCustomDate, 'MMM d, yyyy') : ''}
            </Text>
            
            <TextInput
              style={styles.customDateInput}
              placeholder='e.g., "Lease Expiration"'
              placeholderTextColor="#8E8E93"
              value={newCustomDateName}
              onChangeText={setNewCustomDateName}
              returnKeyType="done"
              onSubmitEditing={confirmCustomDateWithLabel}
              blurOnSubmit={true}
            />
            
            <View style={styles.customDateButtons}>
              <TouchableOpacity 
                style={styles.customDateCancelButton}
                onPress={cancelCustomDateLabel}
              >
                <Text style={styles.customDateCancelText}>Cancel</Text>
              </TouchableOpacity>
              
              <TouchableOpacity 
                style={styles.customDateAddButton}
                onPress={confirmCustomDateWithLabel}
              >
                <Text style={styles.customDateAddText}>Save</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  keyboardView: {
    flex: 1,
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
  // Quick Status Section
  quickStatusSection: {
    marginBottom: 24,
  },
  statusButtons: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  statusButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    gap: 8,
    borderWidth: 2,
    borderColor: '#2C2C2E',
  },
  statusButtonActive: {
    borderColor: '#FF9500',
    backgroundColor: '#FF950015',
  },
  statusButtonSold: {
    borderColor: '#34C759',
    backgroundColor: '#34C75915',
  },
  statusButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#8E8E93',
  },
  referralPrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#34C75915',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#34C75930',
    borderStyle: 'dashed',
  },
  referralPromptIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#34C75920',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  referralPromptContent: {
    flex: 1,
  },
  referralPromptTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#34C759',
    marginBottom: 2,
  },
  referralPromptSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
  },
  referrerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#34C75920',
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 12,
    gap: 8,
    alignSelf: 'flex-start',
  },
  referrerBadgeText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#34C759',
  },
  photoSection: {
    alignItems: 'center',
    marginBottom: 32,
  },
  photoContainer: {
    position: 'relative',
    marginBottom: 8,
  },
  photo: {
    width: 120,
    height: 120,
    borderRadius: 60,
  },
  photoPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoEditBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: '#000',
  },
  photoLabel: {
    fontSize: 13,
    color: '#8E8E93',
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  notesHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 6,
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
    height: 120,
    paddingTop: 16,
  },
  // Referral styles
  referralSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  referralIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#34C75920',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  referralInfo: {
    flex: 1,
  },
  referralLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 2,
  },
  referralName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#34C759',
  },
  referralPlaceholder: {
    fontSize: 15,
    color: '#8E8E93',
  },
  clearButton: {
    padding: 4,
  },
  referralStats: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF950015',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    gap: 12,
  },
  referralStatIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#FF950020',
    alignItems: 'center',
    justifyContent: 'center',
  },
  referralStatText: {
    flex: 1,
    fontSize: 15,
    color: '#FF9500',
    fontWeight: '500',
  },
  referralsList: {
    marginTop: 8,
  },
  referralsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 12,
  },
  referralItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  referralAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  referralAvatarText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
  referralItemInfo: {
    flex: 1,
  },
  referralItemName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  referralItemVehicle: {
    fontSize: 13,
    color: '#8E8E93',
  },
  // Tags
  tagInputRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  tagInput: {
    flex: 1,
  },
  addTagButton: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  tagContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    paddingVertical: 6,
    paddingLeft: 12,
    paddingRight: 8,
    gap: 6,
  },
  tagText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '600',
  },
  addTagButtonLarge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    gap: 8,
    borderWidth: 1,
    borderColor: '#2C2C2E',
    borderStyle: 'dashed',
  },
  addTagButtonText: {
    fontSize: 15,
    fontWeight: '500',
    color: '#007AFF',
  },
  tagSearchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    margin: 16,
    paddingHorizontal: 12,
    gap: 8,
  },
  tagSearchInput: {
    flex: 1,
    padding: 12,
    fontSize: 16,
    color: '#FFF',
  },
  tagPickerList: {
    flex: 1,
    paddingHorizontal: 16,
  },
  tagPickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    marginBottom: 8,
  },
  tagPickerIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  tagPickerInfo: {
    flex: 1,
  },
  tagPickerName: {
    fontSize: 16,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 2,
  },
  tagPickerCount: {
    fontSize: 13,
    color: '#8E8E93',
  },
  // Modal styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalCancel: {
    fontSize: 17,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  modalAction: {
    fontSize: 17,
    color: '#007AFF',
  },
  modalSearch: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    margin: 16,
    paddingHorizontal: 12,
    gap: 8,
  },
  modalSearchInput: {
    flex: 1,
    padding: 12,
    fontSize: 16,
    color: '#FFF',
  },
  pickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  pickerAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  pickerAvatarText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  pickerInfo: {
    flex: 1,
  },
  pickerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  pickerPhone: {
    fontSize: 14,
    color: '#8E8E93',
  },
  emptyPicker: {
    padding: 32,
    alignItems: 'center',
  },
  emptyPickerText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 12,
  },
  emptyPickerSubtext: {
    fontSize: 14,
    color: '#636366',
    marginTop: 4,
    textAlign: 'center',
  },
  // Campaign enrollment styles
  enrollmentsList: {
    gap: 8,
    marginBottom: 16,
  },
  enrollmentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  enrollmentIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007AFF15',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  enrollmentInfo: {
    flex: 1,
  },
  enrollmentName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  enrollmentStatus: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  enrollmentSent: {
    fontSize: 12,
    color: '#34C759',
    marginTop: 2,
  },
  cancelEnrollButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#FF3B3015',
    alignItems: 'center',
    justifyContent: 'center',
  },
  swipeDeleteAction: {
    backgroundColor: '#FF3B30',
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
    borderRadius: 12,
    marginLeft: 8,
  },
  swipeDeleteText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '600',
    marginTop: 4,
  },
  swipeEnrollAction: {
    backgroundColor: '#34C759',
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
    borderRadius: 12,
    marginRight: 8,
  },
  swipeEnrollText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '600',
    marginTop: 4,
  },
  enrollmentSubtitle: {
    fontSize: 12,
    fontWeight: '500',
    color: '#8E8E93',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  availableCampaignCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
    borderStyle: 'dashed',
  },
  availableCampaignName: {
    fontSize: 15,
    fontWeight: '500',
    color: '#8E8E93',
  },
  enrollButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF15',
    borderRadius: 12,
    padding: 16,
    gap: 8,
    borderWidth: 1,
    borderColor: '#007AFF30',
    borderStyle: 'dashed',
  },
  enrollButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  noCampaignsText: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    marginTop: 12,
  },
  // Campaign picker modal styles
  campaignPickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  campaignPickerIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  campaignPickerInfo: {
    flex: 1,
  },
  campaignPickerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  campaignPickerSteps: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  // Date field styles
  dateField: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  dateIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  dateInfo: {
    flex: 1,
  },
  dateLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 2,
  },
  dateValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  datePlaceholder: {
    color: '#8E8E93',
    fontWeight: '400',
  },
  clearDateButton: {
    padding: 4,
    marginRight: 8,
  },
  deleteDateButton: {
    padding: 4,
    marginLeft: 4,
  },
  addCustomDateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF15',
    borderRadius: 12,
    padding: 14,
    gap: 8,
    borderWidth: 1,
    borderColor: '#007AFF30',
    borderStyle: 'dashed',
  },
  addCustomDateText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#007AFF',
  },
  // Date picker modal styles
  datePickerOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  datePickerDismiss: {
    flex: 1,
  },
  datePickerModal: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingBottom: Platform.OS === 'ios' ? 20 : 40,
    minHeight: Platform.OS === 'web' ? 350 : undefined,
  },
  datePickerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  datePickerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  datePickerCancel: {
    fontSize: 17,
    color: '#FF3B30',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  datePickerDone: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  datePicker: {
    height: 200,
    marginHorizontal: 10,
  },
  datePickerActions: {
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  datePickerConfirmButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  datePickerConfirmText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  // Label modal overlay - centered, doesn't move with keyboard
  labelModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-start',
    paddingTop: 150,
  },
  labelModalContent: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    marginHorizontal: 20,
    padding: 24,
  },
  // Custom date modal styles (legacy, kept for compatibility)
  customDateModal: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    margin: 20,
    padding: 24,
  },
  customDateTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
    marginBottom: 8,
  },
  customDateSubtitle: {
    fontSize: 15,
    color: '#007AFF',
    textAlign: 'center',
    marginBottom: 20,
    fontWeight: '600',
  },
  customDateInput: {
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
    marginBottom: 24,
  },
  customDateButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  customDateCancelButton: {
    flex: 1,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  customDateCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF3B30',
  },
  customDateAddButton: {
    flex: 1,
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  customDateAddText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  // Web date picker styles
  webDatePickerContainer: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingVertical: 16,
    gap: 12,
  },
  webPickerColumn: {
    flex: 1,
    alignItems: 'center',
  },
  webPickerLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  webPickerScroll: {
    maxHeight: 200,
    width: '100%',
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
  },
  webPickerItem: {
    paddingVertical: 10,
    paddingHorizontal: 12,
    alignItems: 'center',
  },
  webPickerItemSelected: {
    backgroundColor: '#007AFF',
    borderRadius: 6,
    marginHorizontal: 4,
  },
  webPickerItemText: {
    fontSize: 16,
    color: '#8E8E93',
  },
  webPickerItemTextSelected: {
    color: '#FFF',
    fontWeight: '600',
  },
});
