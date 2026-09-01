import React, {
  useState, useEffect, useCallback } from 'react';
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
import { useRouter, useFocusEffect } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import DateTimePicker from '@react-native-community/datetimepicker';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { useToast } from '../../components/common/Toast';
import { showAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
import { PersonalizeButton } from '../../components/PersonalizeButton';
const IS_WEB = Platform.OS === 'web';

interface Tag {
  id: string;
  name: string;
  color: string;
}

interface FilterState {
  tags: string[];
  exclude_tags: string[];
  contact_ids: string[];
  purchase_month: number | null;
  purchase_year: number | null;
  days_since_purchase: number | null;
  days_since_contact: number | null;
  custom_date_start: string | null;
  custom_date_end: string | null;
  purchase_title_contains: string | null;
  purchase_category: string | null;
  purchase_history_year: number | null;
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
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  
  // Form state
const { showToast } = useToast();
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
    contact_ids: [],
    purchase_month: null,
    purchase_year: null,
    days_since_purchase: null,
    days_since_contact: null,
    custom_date_start: null,
    custom_date_end: null,
    purchase_title_contains: null,
    purchase_category: null,
    purchase_history_year: null,
  });
  
  // Available tags
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);

  // Pick specific contacts
  const [pickSearch, setPickSearch] = useState('');
  const [pickResults, setPickResults] = useState<any[]>([]);
  const [pickSearching, setPickSearching] = useState(false);
  const [selectedContacts, setSelectedContacts] = useState<{ id: string; name: string; phone: string }[]>([]);
  const [showExclude, setShowExclude] = useState(false);
  
  // Preview
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  
  // Submission
  const [submitting, setSubmitting] = useState(false);
  
  // Expanded sections
  const [expandedSections, setExpandedSections] = useState({
    tags: true,
    pickContacts: false,
    dateFilters: false,
    purchases: false,
    schedule: false,
  });

  // Jessi AI replies
  const [jessiReplies, setJessiReplies] = useState(false);

  useEffect(() => {
    fetchTags();
  }, []);

  // Refresh tags when returning from CSV list import
  useFocusEffect(useCallback(() => { fetchTags(); }, [user?._id]));

  // Debounced contact search for hand-picking recipients
  useEffect(() => {
    if (!user?._id || pickSearch.trim().length < 2) { setPickResults([]); return; }
    const t = setTimeout(async () => {
      setPickSearching(true);
      try {
        const r = await api.get(`/contacts/${user._id}`, { params: { search: pickSearch.trim(), limit: 15 } });
        const list = Array.isArray(r.data) ? r.data : (r.data?.contacts || []);
        setPickResults(list.filter((c: any) => c.phone));
      } catch {}
      setPickSearching(false);
    }, 400);
    return () => clearTimeout(t);
  }, [pickSearch, user?._id]);

  const togglePickContact = (c: any) => {
    const id = c._id || c.id;
    const exists = selectedContacts.some(s => s.id === id);
    const next = exists
      ? selectedContacts.filter(s => s.id !== id)
      : [...selectedContacts, { id, name: `${c.first_name || ''} ${c.last_name || ''}`.trim() || c.name || 'Unknown', phone: c.phone || '' }];
    setSelectedContacts(next);
    setFilters(prev => ({ ...prev, contact_ids: next.map(s => s.id) }));
  };

  useEffect(() => {
    const timeout = setTimeout(() => {
      previewRecipients();
    }, 500);
    return () => clearTimeout(timeout);
  }, [filters]);

  const fetchTags = async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/tags/${user._id}`);
      // Tags endpoint returns a direct array
      const tagList = Array.isArray(res.data) ? res.data : (res.data?.tags || []);
      setAvailableTags(tagList.map((t: any) => ({
        id: t._id || t.id,
        name: t.name,
        color: t.color || '#007AFF',
      })));
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
      if (filters.contact_ids.length > 0) params.append('contact_ids', filters.contact_ids.join(','));
      if (filters.purchase_month) params.append('purchase_month', filters.purchase_month.toString());
      if (filters.purchase_year) params.append('purchase_year', filters.purchase_year.toString());
      if (filters.days_since_purchase) params.append('days_since_purchase', filters.days_since_purchase.toString());
      if (filters.days_since_contact) params.append('days_since_contact', filters.days_since_contact.toString());
      if (filters.custom_date_start) params.append('custom_date_start', filters.custom_date_start);
      if (filters.custom_date_end) params.append('custom_date_end', filters.custom_date_end);
      if (filters.purchase_title_contains) params.append('purchase_title_contains', filters.purchase_title_contains);
      if (filters.purchase_category) params.append('purchase_category', filters.purchase_category);
      if (filters.purchase_history_year) params.append('purchase_history_year', filters.purchase_history_year.toString());
      
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
        showAlert('Permission Denied', 'Photo library access is required.');
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
      showAlert('Missing Name', 'Please enter a name for this broadcast');
      return;
    }
    if (!message.trim()) {
      showAlert('Missing Message', 'Please enter a message to send');
      return;
    }
    if (previewCount === 0) {
      showAlert('No Recipients', 'No contacts match your selected filters');
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
        jessi_replies: jessiReplies,
        stagger_seconds: 10,
      };
      
      const res = await api.post(`/broadcast?user_id=${user?._id}`, broadcastData);

      if (res.data.success) {
        if (sendNow && scheduleType !== 'later') {
          // Send immediately
          await api.post(`/broadcast/${res.data.broadcast.id}/send?user_id=${user?._id}`);
          showToast(`Broadcast queued for ${previewCount} contacts!`);
        } else if (scheduleType === 'later') {
          showToast(`Scheduled for ${scheduledDate.toLocaleDateString()} at ${scheduledDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
        } else {
          showToast('Saved as draft');
        }
        if ((router as any).canGoBack?.()) router.back();
        else router.replace('/broadcast' as any);
      }
    } catch (error: any) {
      console.error('Error creating broadcast:', error);
      showAlert('Error', error.response?.data?.detail || 'Failed to create broadcast');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const SectionHeader = ({ title, section, icon }: { title: string; section: keyof typeof expandedSections; icon: string }) => (
    <Pressable
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
        color={colors.textSecondary}
      />
    </Pressable>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton} testID="back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </Pressable>
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
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={styles.label}>Message</Text>
            <PersonalizeButton
              colors={colors}
              onInsert={(tag) => setMessage(prev => prev + tag)}
            />
          </View>
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
                <Pressable
                  style={styles.mediaRemove}
                  onPress={() => removeImage(index)}
                  testID={`remove-image-${index}`}
                >
                  <Ionicons name="close-circle" size={24} color="#FF3B30" />
                </Pressable>
              </View>
            ))}
            <Pressable 
              style={styles.addMediaButton} 
              onPress={pickImage}
              testID="add-photo-btn"
            >
              <Ionicons name="add-circle-outline" size={32} color="#007AFF" />
              <Text style={styles.addMediaText}>Add Photo</Text>
            </Pressable>
          </View>
        </View>

        {/* Tags Section */}
        <View style={styles.section}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, paddingBottom: 0 }}>
            <Pressable
              style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 }}
              onPress={() => toggleSection('tags')}
              testID="section-tags"
            >
              <Ionicons name="pricetags-outline" size={20} color="#007AFF" />
              <Text style={styles.sectionTitle}>Filter by Tags (Lists)</Text>
              <Ionicons name={expandedSections.tags ? 'chevron-up' : 'chevron-down'} size={20} color={colors.textSecondary} />
            </Pressable>
            <Pressable
              style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#34C75915', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 }}
              onPress={() => router.push('/contacts/import' as any)}
              testID="csv-import-btn"
            >
              <Ionicons name="cloud-upload-outline" size={15} color="#34C759" />
              <Text style={{ fontSize: 13, fontWeight: '600', color: '#34C759' }}>Upload List</Text>
            </Pressable>
          </View>
          {expandedSections.tags && (
            <View style={styles.sectionContent}>
              {availableTags.length === 0 ? (
                <Text style={styles.noTagsText}>No tags available. Create tags in your contacts.</Text>
              ) : (
                <>
                  <Text style={styles.filterLabel}>Include contacts with these tags:</Text>
                  <View style={styles.tagsContainer}>
                    {availableTags.map(tag => (
                      <Pressable
                        key={tag.id}
                        style={[
                          styles.tagChip,
                          filters.tags.includes(tag.name) && styles.tagChipSelected,
                        ]}
                        onPress={() => toggleTag(tag.name, 'include')}
                        testID={`tag-include-${tag.id}`}
                        {...({ dataSet: { testid: `tag-include-${tag.id}` } } as any)}
                      >
                        <Text style={[
                          styles.tagChipText,
                          filters.tags.includes(tag.name) && styles.tagChipTextSelected,
                        ]}>
                          {tag.name}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                  
                  <Pressable
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 16 }}
                    onPress={() => setShowExclude(v => !v)}
                    testID="toggle-exclude-tags"
                    {...({ dataSet: { testid: 'toggle-exclude-tags' } } as any)}
                  >
                    <Text style={styles.filterLabel}>
                      Exclude contacts with these tags{filters.exclude_tags.length > 0 ? ` (${filters.exclude_tags.length})` : ''}
                    </Text>
                    <Ionicons name={showExclude ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
                  </Pressable>
                  {(showExclude || filters.exclude_tags.length > 0) && (
                  <View style={styles.tagsContainer}>
                    {availableTags.map(tag => (
                      <Pressable
                        key={`exclude-${tag.id}`}
                        style={[
                          styles.tagChip,
                          filters.exclude_tags.includes(tag.name) && styles.tagChipExcluded,
                        ]}
                        onPress={() => toggleTag(tag.name, 'exclude')}
                        testID={`tag-exclude-${tag.id}`}
                        {...({ dataSet: { testid: `tag-exclude-${tag.id}` } } as any)}
                      >
                        <Text style={[
                          styles.tagChipText,
                          filters.exclude_tags.includes(tag.name) && styles.tagChipTextSelected,
                        ]}>
                          {tag.name}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                  )}
                </>
              )}
            </View>
          )}
        </View>

        {/* Pick Specific Contacts */}
        <View style={styles.section}>
          <Pressable
            style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16, paddingBottom: expandedSections.pickContacts ? 0 : 16 }}
            onPress={() => toggleSection('pickContacts')}
            testID="section-pick-contacts"
            {...({ dataSet: { testid: 'section-pick-contacts' } } as any)}
          >
            <Ionicons name="person-add-outline" size={20} color="#34C759" />
            <Text style={[styles.sectionTitle, { flex: 1 }]}>
              Pick Specific Contacts{selectedContacts.length > 0 ? ` (${selectedContacts.length})` : ''}
            </Text>
            <Ionicons name={expandedSections.pickContacts ? 'chevron-up' : 'chevron-down'} size={20} color={colors.textSecondary} />
          </Pressable>
          {expandedSections.pickContacts && (
            <View style={styles.sectionContent}>
              <Text style={styles.filterLabel}>Hand-pick who gets this blast — added on top of any tag filters:</Text>
              {selectedContacts.length > 0 && (
                <View style={[styles.tagsContainer, { marginBottom: 10 }]}>
                  {selectedContacts.map(c => (
                    <Pressable
                      key={c.id}
                      style={[styles.tagChip, { backgroundColor: '#34C75920', borderColor: '#34C759', flexDirection: 'row', alignItems: 'center', gap: 6 }]}
                      onPress={() => togglePickContact({ _id: c.id })}
                      testID={`picked-${c.id}`}
                      {...({ dataSet: { testid: `picked-${c.id}` } } as any)}
                    >
                      <Text style={[styles.tagChipText, { color: '#34C759' }]}>{c.name}</Text>
                      <Ionicons name="close-circle" size={15} color="#34C759" />
                    </Pressable>
                  ))}
                </View>
              )}
              <TextInput
                style={styles.input}
                placeholder="Search contacts by name or phone..."
                placeholderTextColor="#6E6E73"
                value={pickSearch}
                onChangeText={setPickSearch}
                testID="pick-contact-search"
                {...({ dataSet: { testid: 'pick-contact-search' } } as any)}
              />
              {pickSearching && <ActivityIndicator size="small" color="#34C759" style={{ marginTop: 10 }} />}
              {pickResults.map((c: any) => {
                const id = c._id || c.id;
                const isSel = selectedContacts.some(s => s.id === id);
                return (
                  <Pressable
                    key={id}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }}
                    onPress={() => togglePickContact(c)}
                    testID={`pick-result-${id}`}
                    {...({ dataSet: { testid: `pick-result-${id}` } } as any)}
                  >
                    <Ionicons name={isSel ? 'checkbox' : 'square-outline'} size={22} color={isSel ? '#34C759' : colors.textSecondary} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>
                        {`${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Unknown'}
                      </Text>
                      <Text style={{ fontSize: 12, color: colors.textSecondary }}>{c.phone}</Text>
                    </View>
                  </Pressable>
                );
              })}
            </View>
          )}
        </View>

        {/* Jessi AI Replies */}
        <View style={[styles.section, { marginBottom: 16 }]}>
          <Pressable
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16 }}
            onPress={() => setJessiReplies(v => !v)}
            testID="jessi-replies-toggle"
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 }}>
              <Ionicons name="sparkles" size={20} color="#AF52DE" />
              <View style={{ flex: 1 }}>
                <Text style={[styles.sectionTitle, { fontSize: 16 }]}>Let Jessi Handle Replies</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
                  Jessi auto-responds to everyone who replies, in your voice
                </Text>
              </View>
            </View>
            <View style={{
              width: 48, height: 28, borderRadius: 14,
              backgroundColor: jessiReplies ? '#AF52DE' : colors.surface,
              justifyContent: 'center', paddingHorizontal: 2,
            }}>
              <View style={{
                width: 24, height: 24, borderRadius: 12, backgroundColor: '#FFF',
                alignSelf: jessiReplies ? 'flex-end' : 'flex-start',
              }} />
            </View>
          </Pressable>
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
                  <Pressable
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
                  </Pressable>
                ))}
              </View>
              
              {/* Month/Year Filter */}
              <Text style={[styles.filterLabel, { marginTop: 16 }]}>Or filter by specific month:</Text>
              <View style={styles.monthYearContainer}>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {MONTHS.map((month, index) => (
                    <Pressable
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
                    </Pressable>
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

        {/* Filter by Purchase — search across purchase_history */}
        <View style={styles.section}>
          <Pressable
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, paddingBottom: 0 }}
            onPress={() => setExpandedSections(prev => ({ ...prev, purchases: !prev.purchases }))}
            testID="section-purchases"
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Ionicons name="bag-handle-outline" size={20} color="#007AFF" />
              <Text style={styles.sectionTitle}>Filter by Purchase</Text>
            </View>
            <Ionicons name={expandedSections.purchases ? 'chevron-up' : 'chevron-down'} size={20} color={colors.textSecondary} />
          </Pressable>
          {expandedSections.purchases && (
            <View style={[styles.sectionContent, { paddingTop: 16 }]}>
              <Text style={styles.filterLabel}>Purchase contains keyword:</Text>
              <TextInput
                style={[styles.input, { marginBottom: 4 }]}
                placeholder='e.g. "Road Glide" or "Term Life"'
                placeholderTextColor="#6E6E73"
                value={filters.purchase_title_contains || ''}
                onChangeText={t => setFilters(prev => ({ ...prev, purchase_title_contains: t || null }))}
                testID="purchase-title-filter"
              />
              <Text style={{ fontSize: 12, color: colors.textTertiary, marginBottom: 16 }}>
                Searches all purchase records — any industry, any product
              </Text>

              <Text style={styles.filterLabel}>Purchase Year:</Text>
              <TextInput
                style={[styles.yearInput, { marginBottom: 16 }]}
                placeholder="e.g. 2023"
                placeholderTextColor="#6E6E73"
                value={filters.purchase_history_year?.toString() || ''}
                onChangeText={t => setFilters(prev => ({ ...prev, purchase_history_year: t ? parseInt(t) : null }))}
                keyboardType="number-pad"
                maxLength={4}
                testID="purchase-year-filter"
              />

              <Text style={styles.filterLabel}>Category:</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                {[
                  { value: null,           label: 'Any' },
                  { value: 'vehicle',      label: 'Vehicle' },
                  { value: 'real_estate',  label: 'Real Estate' },
                  { value: 'insurance',    label: 'Insurance' },
                  { value: 'boat',         label: 'Boat / RV' },
                  { value: 'other',        label: 'Other' },
                ].map(opt => (
                  <Pressable
                    key={opt.label}
                    onPress={() => setFilters(prev => ({ ...prev, purchase_category: opt.value }))}
                    style={[
                      styles.presetButton,
                      filters.purchase_category === opt.value && styles.presetButtonActive,
                    ]}
                    testID={`purchase-cat-${opt.label}`}
                  >
                    <Text style={[
                      styles.presetText,
                      filters.purchase_category === opt.value && styles.presetTextActive,
                    ]}>{opt.label}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          )}
        </View>

        {/* Schedule Section */}
        <View style={styles.section}>
          <SectionHeader title="When to Send" section="schedule" icon="time-outline" />
          {expandedSections.schedule && (
            <View style={styles.sectionContent}>
              <View style={styles.scheduleOptions}>
                <Pressable
                  style={[styles.scheduleOption, scheduleType === 'now' && styles.scheduleOptionActive]}
                  onPress={() => setScheduleType('now')}
                  testID="schedule-now"
                >
                  <Ionicons
                    name={scheduleType === 'now' ? 'radio-button-on' : 'radio-button-off'}
                    size={20}
                    color={scheduleType === 'now' ? '#007AFF' : colors.textSecondary}
                  />
                  <View>
                    <Text style={[styles.scheduleOptionText, scheduleType === 'now' && styles.scheduleOptionTextActive]}>
                      Send Now
                    </Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                      Starts delivering immediately, staggered by 10s each
                    </Text>
                  </View>
                </Pressable>

                <Pressable
                  style={[styles.scheduleOption, scheduleType === 'later' && styles.scheduleOptionActive]}
                  onPress={() => setScheduleType('later')}
                  testID="schedule-later"
                >
                  <Ionicons
                    name={scheduleType === 'later' ? 'radio-button-on' : 'radio-button-off'}
                    size={20}
                    color={scheduleType === 'later' ? '#34C759' : colors.textSecondary}
                  />
                  <View>
                    <Text style={[styles.scheduleOptionText, scheduleType === 'later' && { color: '#34C759', fontWeight: '700' }]}>
                      Schedule for Later
                    </Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                      Auto-fires at the exact time you pick
                    </Text>
                  </View>
                </Pressable>
              </View>

              {scheduleType === 'later' && (
                <>
                  <View style={styles.dateTimeContainer}>
                    <Pressable
                      style={styles.dateTimeButton}
                      onPress={() => setShowDatePicker(true)}
                      testID="date-picker-btn"
                    >
                      <Ionicons name="calendar" size={20} color="#34C759" />
                      <Text style={styles.dateTimeText}>
                        {scheduledDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                      </Text>
                    </Pressable>

                    <Pressable
                      style={styles.dateTimeButton}
                      onPress={() => setShowTimePicker(true)}
                      testID="time-picker-btn"
                    >
                      <Ionicons name="time" size={20} color="#34C759" />
                      <Text style={styles.dateTimeText}>
                        {scheduledDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </Text>
                    </Pressable>
                  </View>

                  {/* Confirmation banner */}
                  <View style={{ backgroundColor: '#34C75912', borderRadius: 10, padding: 12, marginTop: 10, flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                    <Ionicons name="checkmark-circle" size={18} color="#34C759" />
                    <Text style={{ fontSize: 13, color: '#34C759', flex: 1 }}>
                      Will auto-send on{' '}
                      <Text style={{ fontWeight: '700' }}>
                        {scheduledDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })} at{' '}
                        {scheduledDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </Text>
                      {previewCount ? ` to ${previewCount} contacts` : ''}
                    </Text>
                  </View>
                </>
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
          <Pressable
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
                <Text style={styles.saveButtonText}>Save Draft</Text>
              </>
            )}
          </Pressable>

          <Pressable
            style={[
              styles.sendButton,
              scheduleType === 'later' && { backgroundColor: '#34C759' },
              (submitting) && styles.sendButtonDisabled,
            ]}
            onPress={() => handleSubmit(true)}
            disabled={submitting}
            testID="send-now-btn"
          >
            {submitting ? (
              <ActivityIndicator size="small" color={colors.text} />
            ) : (
              <>
                <Ionicons name={scheduleType === 'later' ? 'calendar' : 'send'} size={20} color={colors.text} />
                <Text style={styles.sendButtonText}>
                  {scheduleType === 'later'
                    ? `Schedule (${previewCount ?? '?'} contacts)`
                    : `Send Now (${previewCount ?? '?'})`}
                </Text>
              </>
            )}
          </Pressable>
        </View>
        
        <View style={{ height: 40 }} />
      </ScrollView>
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
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    fontSize: 18,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  messageInput: {
    height: 120,
    paddingTop: 14,
  },
  charCount: {
    fontSize: 14,
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
    backgroundColor: colors.card,
    borderWidth: 2,
    borderColor: colors.surface,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
  },
  addMediaText: {
    fontSize: 12,
    color: '#007AFF',
    marginTop: 4,
  },
  section: {
    backgroundColor: colors.card,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  sectionContent: {
    padding: 16,
    paddingTop: 0,
  },
  filterLabel: {
    fontSize: 15,
    color: colors.textSecondary,
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
    backgroundColor: colors.surface,
  },
  tagChipSelected: {
    backgroundColor: '#007AFF',
  },
  tagChipExcluded: {
    backgroundColor: '#FF3B30',
  },
  tagChipText: {
    fontSize: 16,
    color: colors.text,
  },
  tagChipTextSelected: {
    fontWeight: '600',
  },
  noTagsText: {
    fontSize: 16,
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
    backgroundColor: colors.surface,
  },
  presetButtonActive: {
    backgroundColor: '#007AFF',
  },
  presetText: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  presetTextActive: {
    color: colors.text,
    fontWeight: '600',
  },
  monthYearContainer: {
    marginTop: 8,
  },
  monthButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: colors.surface,
    marginRight: 8,
  },
  monthButtonActive: {
    backgroundColor: '#007AFF',
  },
  monthText: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  monthTextActive: {
    color: colors.text,
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
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    fontSize: 18,
    color: colors.text,
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
    backgroundColor: colors.surface,
  },
  scheduleOptionActive: {
    backgroundColor: 'rgba(0, 122, 255, 0.15)',
  },
  scheduleOptionText: {
    fontSize: 17,
    color: colors.textSecondary,
  },
  scheduleOptionTextActive: {
    color: colors.text,
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
    backgroundColor: colors.surface,
    borderRadius: 12,
  },
  dateTimeText: {
    fontSize: 17,
    color: colors.text,
  },
  previewCard: {
    backgroundColor: colors.card,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  previewCount: {
    fontSize: 16,
    color: colors.textSecondary,
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
    fontSize: 18,
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
    backgroundColor: colors.borderLight,
  },
  sendButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
});
