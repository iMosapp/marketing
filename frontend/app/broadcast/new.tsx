import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Pressable,
  TextInput,
  ScrollView,
  ActivityIndicator,
  Alert,
  Platform,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import DateTimePicker from '@react-native-community/datetimepicker';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

// Web-safe pressable component for interactive elements
const WebSafePressable = (props: { onPress?: () => void; style?: any; children?: React.ReactNode; testID?: string; disabled?: boolean }) => {
  const { onPress, style, children, testID, disabled } = props;
  if (IS_WEB) {
    return (
      <button
        type="button"
        data-testid={testID}
        disabled={disabled}
        onClick={(e: React.MouseEvent) => {
          e.preventDefault();
          e.stopPropagation();
          if (!disabled && onPress) onPress();
        }}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          margin: 0,
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          WebkitTapHighlightColor: 'transparent',
          touchAction: 'manipulation',
          ...style,
        }}
      >
        {children}
      </button>
    );
  }
  return (
    <Pressable onPress={onPress} style={style} testID={testID} disabled={disabled}>
      {children}
    </Pressable>
  );
};

interface Tag {
  id: string;
  name: string;
  color: string;
}

interface FilterState {
  tags: string[];
  exclude_tags: string[];
  purchase_month: number | null;
  purchase_year: number | null;
  days_since_purchase: number | null;
  days_since_contact: number | null;
  custom_date_start: string | null;
  custom_date_end: string | null;
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const PRESET_FILTERS = [
  { label: '30 days ago', days: 30 },
  { label: '90 days ago', days: 90 },
  { label: '6 months ago', days: 180 },
  { label: '1 year ago', days: 365 },
  { label: '2 years ago', days: 730 },
  { label: '3 years ago', days: 1095 },
];

export default function NewBroadcastScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  
  // Form state
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');
  const [mediaUrls, setMediaUrls] = useState<string[]>([]);
  const [selectedImages, setSelectedImages] = useState<{ uri: string; type: string; name: string }[]>([]);
  
  // Scheduling
  const [scheduleType, setScheduleType] = useState<'now' | 'later'>('now');
  const [scheduledDate, setScheduledDate] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);
  
  // Filters
  const [filters, setFilters] = useState<FilterState>({
    tags: [],
    exclude_tags: [],
    purchase_month: null,
    purchase_year: null,
    days_since_purchase: null,
    days_since_contact: null,
    custom_date_start: null,
    custom_date_end: null,
  });
  
  // Available tags
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  
  // Preview
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  
  // Submission
  const [submitting, setSubmitting] = useState(false);
  
  // Expanded sections
  const [expandedSections, setExpandedSections] = useState({
    tags: true,
    dateFilters: false,
    schedule: false,
  });

  useEffect(() => {
    fetchTags();
  }, []);

  useEffect(() => {
    // Debounce preview
    const timeout = setTimeout(() => {
      previewRecipients();
    }, 500);
    return () => clearTimeout(timeout);
  }, [filters]);

  const fetchTags = async () => {
    try {
      const res = await api.get(`/tags?user_id=${user?._id}`);
      if (res.data.success) {
        setAvailableTags(res.data.tags);
      }
    } catch (error) {
      console.error('Error fetching tags:', error);
    }
  };

  const previewRecipients = async () => {
    if (!user?._id) return;
    
    setPreviewLoading(true);
    try {
      const params = new URLSearchParams({ user_id: user._id });
      if (filters.tags.length > 0) params.append('tags', filters.tags.join(','));
      if (filters.exclude_tags.length > 0) params.append('exclude_tags', filters.exclude_tags.join(','));
      if (filters.purchase_month) params.append('purchase_month', filters.purchase_month.toString());
      if (filters.purchase_year) params.append('purchase_year', filters.purchase_year.toString());
      if (filters.days_since_purchase) params.append('days_since_purchase', filters.days_since_purchase.toString());
      if (filters.days_since_contact) params.append('days_since_contact', filters.days_since_contact.toString());
      if (filters.custom_date_start) params.append('custom_date_start', filters.custom_date_start);
      if (filters.custom_date_end) params.append('custom_date_end', filters.custom_date_end);
      
      const res = await api.get(`/broadcast/preview?${params.toString()}`);
      if (res.data.success) {
        setPreviewCount(res.data.count);
      }
    } catch (error) {
      console.error('Error previewing:', error);
    } finally {
      setPreviewLoading(false);
    }
  };

  const toggleTag = (tagName: string, type: 'include' | 'exclude') => {
    if (type === 'include') {
      setFilters(prev => ({
        ...prev,
        tags: prev.tags.includes(tagName)
          ? prev.tags.filter(t => t !== tagName)
          : [...prev.tags, tagName],
        exclude_tags: prev.exclude_tags.filter(t => t !== tagName), // Remove from exclude
      }));
    } else {
      setFilters(prev => ({
        ...prev,
        exclude_tags: prev.exclude_tags.includes(tagName)
          ? prev.exclude_tags.filter(t => t !== tagName)
          : [...prev.exclude_tags, tagName],
        tags: prev.tags.filter(t => t !== tagName), // Remove from include
      }));
    }
  };

  const pickImage = async () => {
    if (IS_WEB) {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Photo library access is required.');
        return;
      }
    }
    
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      quality: 0.8,
    });
    
    if (!result.canceled && result.assets) {
      const newImages = result.assets.map(asset => ({
        uri: asset.uri,
        type: asset.mimeType || 'image/jpeg',
        name: asset.fileName || `image_${Date.now()}.jpg`,
      }));
      setSelectedImages(prev => [...prev, ...newImages]);
    }
  };

  const removeImage = (index: number) => {
    setSelectedImages(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (sendNow: boolean = false) => {
    if (!name.trim()) {
      Alert.alert('Missing Name', 'Please enter a name for this broadcast');
      return;
    }
    if (!message.trim()) {
      Alert.alert('Missing Message', 'Please enter a message to send');
      return;
    }
    if (previewCount === 0) {
      Alert.alert('No Recipients', 'No contacts match your selected filters');
      return;
    }
    
    setSubmitting(true);
    
    try {
      // Upload images first if any
      const uploadedUrls: string[] = [];
      for (const img of selectedImages) {
        const formData = new FormData();
        if (IS_WEB) {
          const response = await fetch(img.uri);
          const blob = await response.blob();
          formData.append('file', blob, img.name);
        } else {
          formData.append('file', {
            uri: img.uri,
            type: img.type,
            name: img.name,
          } as any);
        }
        
        // Upload to your media endpoint (you may need to create this)
        // For now, we'll use the base64 URL directly
        uploadedUrls.push(img.uri);
      }
      
      const broadcastData = {
        name: name.trim(),
        message: message.trim(),
        filters,
        media_urls: uploadedUrls,
        scheduled_at: scheduleType === 'later' ? scheduledDate.toISOString() : null,
      };
      
      const res = await api.post(`/broadcast?user_id=${user?._id}`, broadcastData);
      
      if (res.data.success) {
        if (sendNow) {
          // Send immediately
          await api.post(`/broadcast/${res.data.broadcast.id}/send?user_id=${user?._id}`);
          Alert.alert('Success', 'Broadcast sent successfully!');
        } else {
          Alert.alert('Success', scheduleType === 'later' ? 'Broadcast scheduled!' : 'Broadcast saved as draft');
        }
        router.back();
      }
    } catch (error: any) {
      console.error('Error creating broadcast:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to create broadcast');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const SectionHeader = ({ title, section, icon }: { title: string; section: keyof typeof expandedSections; icon: string }) => (
    <WebSafePressable
      style={styles.sectionHeader}
      onPress={() => toggleSection(section)}
      testID={`section-${section}`}
    >
      <View style={styles.sectionHeaderLeft}>
        <Ionicons name={icon as any} size={20} color="#007AFF" />
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      <Ionicons
        name={expandedSections[section] ? 'chevron-up' : 'chevron-down'}
        size={20}
        color="#8E8E93"
      />
    </WebSafePressable>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <WebSafePressable onPress={() => router.back()} style={styles.backButton} testID="back-btn">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </WebSafePressable>
        <Text style={styles.headerTitle}>New Broadcast</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Name */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Broadcast Name</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., May Customer Appreciation"
            placeholderTextColor="#6E6E73"
            value={name}
            onChangeText={setName}
          />
        </View>

        {/* Message */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Message</Text>
          <TextInput
            style={[styles.input, styles.messageInput]}
            placeholder="Type your broadcast message..."
            placeholderTextColor="#6E6E73"
            value={message}
            onChangeText={setMessage}
            multiline
            textAlignVertical="top"
          />
          <Text style={styles.charCount}>{message.length}/160</Text>
        </View>

        {/* Media Attachments */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Media Attachments</Text>
          <View style={styles.mediaContainer}>
            {selectedImages.map((img, index) => (
              <View key={index} style={styles.mediaPreview}>
                <Image source={{ uri: img.uri }} style={styles.mediaImage} />
                <WebSafePressable
                  style={styles.mediaRemove}
                  onPress={() => removeImage(index)}
                  testID={`remove-image-${index}`}
                >
                  <Ionicons name="close-circle" size={24} color="#FF3B30" />
                </WebSafePressable>
              </View>
            ))}
            <WebSafePressable 
              style={styles.addMediaButton} 
              onPress={pickImage}
              testID="add-photo-btn"
            >
              <Ionicons name="add-circle-outline" size={32} color="#007AFF" />
              <Text style={styles.addMediaText}>Add Photo</Text>
            </WebSafePressable>
          </View>
        </View>

        {/* Tags Section */}
        <View style={styles.section}>
          <SectionHeader title="Filter by Tags" section="tags" icon="pricetags-outline" />
          {expandedSections.tags && (
            <View style={styles.sectionContent}>
              {availableTags.length === 0 ? (
                <Text style={styles.noTagsText}>No tags available. Create tags in your contacts.</Text>
              ) : (
                <>
                  <Text style={styles.filterLabel}>Include contacts with these tags:</Text>
                  <View style={styles.tagsContainer}>
                    {availableTags.map(tag => (
                      <WebSafePressable
                        key={tag.id}
                        style={[
                          styles.tagChip,
                          filters.tags.includes(tag.name) && styles.tagChipSelected,
                        ]}
                        onPress={() => toggleTag(tag.name, 'include')}
                        testID={`tag-include-${tag.id}`}
                      >
                        <Text style={[
                          styles.tagChipText,
                          filters.tags.includes(tag.name) && styles.tagChipTextSelected,
                        ]}>
                          {tag.name}
                        </Text>
                      </WebSafePressable>
                    ))}
                  </View>
                  
                  <Text style={[styles.filterLabel, { marginTop: 16 }]}>Exclude contacts with these tags:</Text>
                  <View style={styles.tagsContainer}>
                    {availableTags.map(tag => (
                      <WebSafePressable
                        key={`exclude-${tag.id}`}
                        style={[
                          styles.tagChip,
                          filters.exclude_tags.includes(tag.name) && styles.tagChipExcluded,
                        ]}
                        onPress={() => toggleTag(tag.name, 'exclude')}
                        testID={`tag-exclude-${tag.id}`}
                      >
                        <Text style={[
                          styles.tagChipText,
                          filters.exclude_tags.includes(tag.name) && styles.tagChipTextSelected,
                        ]}>
                          {tag.name}
                        </Text>
                      </WebSafePressable>
                    ))}
                  </View>
                </>
              )}
            </View>
          )}
        </View>

        {/* Date Filters Section */}
        <View style={styles.section}>
          <SectionHeader title="Filter by Purchase Date" section="dateFilters" icon="calendar-outline" />
          {expandedSections.dateFilters && (
            <View style={styles.sectionContent}>
              <Text style={styles.filterLabel}>Customers who purchased:</Text>
              
              {/* Quick Presets */}
              <View style={styles.presetsContainer}>
                {PRESET_FILTERS.map(preset => (
                  <WebSafePressable
                    key={preset.days}
                    style={[
                      styles.presetButton,
                      filters.days_since_purchase === preset.days && styles.presetButtonActive,
                    ]}
                    onPress={() => setFilters(prev => ({
                      ...prev,
                      days_since_purchase: prev.days_since_purchase === preset.days ? null : preset.days,
                      purchase_month: null,
                      purchase_year: null,
                    }))}
                    testID={`preset-${preset.days}`}
                  >
                    <Text style={[
                      styles.presetText,
                      filters.days_since_purchase === preset.days && styles.presetTextActive,
                    ]}>
                      {preset.label}
                    </Text>
                  </WebSafePressable>
                ))}
              </View>
              
              {/* Month/Year Filter */}
              <Text style={[styles.filterLabel, { marginTop: 16 }]}>Or filter by specific month:</Text>
              <View style={styles.monthYearContainer}>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {MONTHS.map((month, index) => (
                    <WebSafePressable
                      key={month}
                      style={[
                        styles.monthButton,
                        filters.purchase_month === index + 1 && styles.monthButtonActive,
                      ]}
                      onPress={() => setFilters(prev => ({
                        ...prev,
                        purchase_month: prev.purchase_month === index + 1 ? null : index + 1,
                        days_since_purchase: null,
                      }))}
                      testID={`month-${month}`}
                    >
                      <Text style={[
                        styles.monthText,
                        filters.purchase_month === index + 1 && styles.monthTextActive,
                      ]}>
                        {month.slice(0, 3)}
                      </Text>
                    </WebSafePressable>
                  ))}
                </ScrollView>
              </View>
              
              {/* Year Input */}
              <View style={styles.yearInputContainer}>
                <Text style={styles.filterLabel}>Year:</Text>
                <TextInput
                  style={styles.yearInput}
                  placeholder="e.g., 2023"
                  placeholderTextColor="#6E6E73"
                  value={filters.purchase_year?.toString() || ''}
                  onChangeText={(text) => setFilters(prev => ({
                    ...prev,
                    purchase_year: text ? parseInt(text) : null,
                    days_since_purchase: null,
                  }))}
                  keyboardType="number-pad"
                  maxLength={4}
                />
              </View>
            </View>
          )}
        </View>

        {/* Schedule Section */}
        <View style={styles.section}>
          <SectionHeader title="Schedule" section="schedule" icon="time-outline" />
          {expandedSections.schedule && (
            <View style={styles.sectionContent}>
              <View style={styles.scheduleOptions}>
                <WebSafePressable
                  style={[styles.scheduleOption, scheduleType === 'now' && styles.scheduleOptionActive]}
                  onPress={() => setScheduleType('now')}
                  testID="schedule-now"
                >
                  <Ionicons
                    name={scheduleType === 'now' ? 'radio-button-on' : 'radio-button-off'}
                    size={20}
                    color={scheduleType === 'now' ? '#007AFF' : '#8E8E93'}
                  />
                  <Text style={[styles.scheduleOptionText, scheduleType === 'now' && styles.scheduleOptionTextActive]}>
                    Save as draft (send manually)
                  </Text>
                </WebSafePressable>
                
                <WebSafePressable
                  style={[styles.scheduleOption, scheduleType === 'later' && styles.scheduleOptionActive]}
                  onPress={() => setScheduleType('later')}
                  testID="schedule-later"
                >
                  <Ionicons
                    name={scheduleType === 'later' ? 'radio-button-on' : 'radio-button-off'}
                    size={20}
                    color={scheduleType === 'later' ? '#007AFF' : '#8E8E93'}
                  />
                  <Text style={[styles.scheduleOptionText, scheduleType === 'later' && styles.scheduleOptionTextActive]}>
                    Schedule for later
                  </Text>
                </WebSafePressable>
              </View>
              
              {scheduleType === 'later' && (
                <View style={styles.dateTimeContainer}>
                  <WebSafePressable
                    style={styles.dateTimeButton}
                    onPress={() => setShowDatePicker(true)}
                    testID="date-picker-btn"
                  >
                    <Ionicons name="calendar" size={20} color="#007AFF" />
                    <Text style={styles.dateTimeText}>
                      {scheduledDate.toLocaleDateString()}
                    </Text>
                  </WebSafePressable>
                  
                  <WebSafePressable
                    style={styles.dateTimeButton}
                    onPress={() => setShowTimePicker(true)}
                    testID="time-picker-btn"
                  >
                    <Ionicons name="time" size={20} color="#007AFF" />
                    <Text style={styles.dateTimeText}>
                      {scheduledDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </Text>
                  </WebSafePressable>
                </View>
              )}
              
              {showDatePicker && (
                <DateTimePicker
                  value={scheduledDate}
                  mode="date"
                  display="default"
                  minimumDate={new Date()}
                  onChange={(event, date) => {
                    setShowDatePicker(false);
                    if (date) setScheduledDate(date);
                  }}
                />
              )}
              
              {showTimePicker && (
                <DateTimePicker
                  value={scheduledDate}
                  mode="time"
                  display="default"
                  onChange={(event, date) => {
                    setShowTimePicker(false);
                    if (date) setScheduledDate(date);
                  }}
                />
              )}
            </View>
          )}
        </View>

        {/* Recipients Preview */}
        <View style={styles.previewCard}>
          <View style={styles.previewHeader}>
            <Ionicons name="people" size={24} color="#007AFF" />
            <Text style={styles.previewTitle}>Recipients Preview</Text>
          </View>
          {previewLoading ? (
            <ActivityIndicator size="small" color="#007AFF" style={{ marginTop: 8 }} />
          ) : (
            <Text style={styles.previewCount}>
              {previewCount !== null ? `${previewCount} contacts will receive this broadcast` : 'Configure filters to see recipient count'}
            </Text>
          )}
        </View>

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          <WebSafePressable
            style={styles.saveButton}
            onPress={() => handleSubmit(false)}
            disabled={submitting}
            testID="save-draft-btn"
          >
            {submitting ? (
              <ActivityIndicator size="small" color="#007AFF" />
            ) : (
              <>
                <Ionicons name="save-outline" size={20} color="#007AFF" />
                <Text style={styles.saveButtonText}>
                  {scheduleType === 'later' ? 'Schedule' : 'Save Draft'}
                </Text>
              </>
            )}
          </WebSafePressable>
          
          <WebSafePressable
            style={[styles.sendButton, (previewCount === 0 || submitting) && styles.sendButtonDisabled]}
            onPress={() => handleSubmit(true)}
            disabled={previewCount === 0 || submitting}
            testID="send-now-btn"
          >
            {submitting ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="send" size={20} color="#FFF" />
                <Text style={styles.sendButtonText}>Send Now</Text>
              </>
            )}
          </WebSafePressable>
        </View>
        
        <View style={{ height: 40 }} />
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
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  messageInput: {
    height: 120,
    paddingTop: 14,
  },
  charCount: {
    fontSize: 12,
    color: '#6E6E73',
    textAlign: 'right',
    marginTop: 4,
  },
  mediaContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  mediaPreview: {
    width: 80,
    height: 80,
    borderRadius: 12,
    overflow: 'hidden',
    position: 'relative',
  },
  mediaImage: {
    width: '100%',
    height: '100%',
  },
  mediaRemove: {
    position: 'absolute',
    top: -8,
    right: -8,
  },
  addMediaButton: {
    width: 80,
    height: 80,
    borderRadius: 12,
    backgroundColor: '#1C1C1E',
    borderWidth: 2,
    borderColor: '#2C2C2E',
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
  },
  addMediaText: {
    fontSize: 10,
    color: '#007AFF',
    marginTop: 4,
  },
  section: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    marginBottom: 16,
    overflow: 'hidden',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
  },
  sectionHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  sectionContent: {
    padding: 16,
    paddingTop: 0,
  },
  filterLabel: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 10,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tagChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#2C2C2E',
  },
  tagChipSelected: {
    backgroundColor: '#007AFF',
  },
  tagChipExcluded: {
    backgroundColor: '#FF3B30',
  },
  tagChipText: {
    fontSize: 14,
    color: '#FFF',
  },
  tagChipTextSelected: {
    fontWeight: '600',
  },
  noTagsText: {
    fontSize: 14,
    color: '#6E6E73',
    fontStyle: 'italic',
  },
  presetsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  presetButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#2C2C2E',
  },
  presetButtonActive: {
    backgroundColor: '#007AFF',
  },
  presetText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  presetTextActive: {
    color: '#FFF',
    fontWeight: '600',
  },
  monthYearContainer: {
    marginTop: 8,
  },
  monthButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: '#2C2C2E',
    marginRight: 8,
  },
  monthButtonActive: {
    backgroundColor: '#007AFF',
  },
  monthText: {
    fontSize: 14,
    color: '#8E8E93',
  },
  monthTextActive: {
    color: '#FFF',
    fontWeight: '600',
  },
  yearInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    gap: 12,
  },
  yearInput: {
    flex: 1,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 12,
    fontSize: 16,
    color: '#FFF',
  },
  scheduleOptions: {
    gap: 12,
  },
  scheduleOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 14,
    borderRadius: 12,
    backgroundColor: '#2C2C2E',
  },
  scheduleOptionActive: {
    backgroundColor: 'rgba(0, 122, 255, 0.15)',
  },
  scheduleOptionText: {
    fontSize: 15,
    color: '#8E8E93',
  },
  scheduleOptionTextActive: {
    color: '#FFF',
  },
  dateTimeContainer: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
  },
  dateTimeButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 14,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
  },
  dateTimeText: {
    fontSize: 15,
    color: '#FFF',
  },
  previewCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    marginBottom: 16,
  },
  previewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  previewTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  previewCount: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  saveButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
    backgroundColor: 'rgba(0, 122, 255, 0.15)',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  saveButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  sendButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
    backgroundColor: '#007AFF',
    borderRadius: 14,
  },
  sendButtonDisabled: {
    backgroundColor: '#3A3A3C',
  },
  sendButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
});
