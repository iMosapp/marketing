import React, {
  useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Switch,
  ActivityIndicator,
  Platform,
  Image,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import DateTimePicker from '@react-native-community/datetimepicker';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../../store/authStore';
import { campaignsAPI } from '../../services/api';
import api from '../../services/api';
import { format, parse } from 'date-fns';
import { useToast } from '../../components/common/Toast';
import { showAlert, showSimpleAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
import { PersonalizeButton } from '../../components/PersonalizeButton';
import { SmartTagPicker } from '../../components/SmartTagPicker';
interface SequenceStep {
  id: string;
  step: number;
  actionType: 'message' | 'send_card';
  cardType: string;
  message: string;
  message_template?: string;
  delayHours: number;
  delay_hours?: number;
  delayDays: number;
  delay_days?: number;
  delayMonths: number;
  delay_months?: number;
  media_urls: string[];
}

interface Enrollment {
  _id: string;
  contact_name: string;
  contact_phone: string;
  current_step: number;
  status: string;
  enrolled_at: string;
  next_send_at: string | null;
}

export default function CampaignDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const user = useAuthStore((state) => state.user);
  
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [campaign, setCampaign] = useState<any>(null);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  
  // Editable fields
  const [name, setName] = useState('');
  const [triggerTag, setTriggerTag] = useState('');
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [active, setActive] = useState(true);
  const [sequences, setSequences] = useState<SequenceStep[]>([]);
  const [sendTime, setSendTime] = useState(new Date(new Date().setHours(10, 0, 0, 0)));
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [uploadingMedia, setUploadingMedia] = useState<string | null>(null);
  const [previewCardType, setPreviewCardType] = useState<string | null>(null);
  
  useFocusEffect(
    useCallback(() => {
      if (id && user) {
        loadCampaign();
        // Load available tags
        api.get(`/tags/${user._id}`).then(r => {
          const tagNames = (r.data || []).map((t: any) => t.name || t);
          setAvailableTags(tagNames);
        }).catch(() => {});
      }
    }, [id, user])
  );
  
  const loadCampaign = async () => {
    if (!id || !user) return;
    
    try {
      setLoading(true);
      const data = await campaignsAPI.get(user._id, id);
      setCampaign(data);
      
      // Set editable fields
      setName(data.name || '');
      setTriggerTag(data.trigger_tag || '');
      setActive(data.active ?? true);
      
      // Parse send time
      if (data.send_time) {
        try {
          const [hours, minutes] = data.send_time.split(':');
          const time = new Date();
          time.setHours(parseInt(hours), parseInt(minutes), 0, 0);
          setSendTime(time);
        } catch (e) {
          console.error('Error parsing send time:', e);
        }
      }
      
      // Parse sequences
      const seqs = (data.sequences || []).map((s: any, idx: number) => ({
        id: String(idx + 1),
        step: s.step || idx + 1,
        actionType: s.action_type || 'message',
        cardType: s.card_type || '',
        message: s.message_template || s.message || '',
        delayHours: s.delay_hours || 0,
        delayDays: s.delay_days || 0,
        delayMonths: s.delay_months || 0,
        media_urls: s.media_urls || [],
      }));
      
      if (seqs.length === 0) {
        seqs.push({ id: '1', step: 1, actionType: 'message', cardType: '', message: data.message_template || '', delayHours: 0, delayDays: 0, delayMonths: 0, media_urls: [] });
      }
      
      setSequences(seqs);
      
      // Load enrollments
      const enrollmentsData = await campaignsAPI.getEnrollments(user._id, id);
      setEnrollments(enrollmentsData);
      
    } catch (error) {
      console.error('Failed to load campaign:', error);
      showSimpleAlert('Error', 'Failed to load campaign');
    } finally {
      setLoading(false);
    }
  };
  
  const getCampaignTypeInfo = (type: string) => {
    switch (type) {
      case 'birthday': return { icon: 'gift', color: '#FF9500', label: 'Birthday' };
      case 'anniversary': return { icon: 'heart', color: '#FF3B30', label: 'Anniversary' };
      case 'sold_followup': return { icon: 'car', color: '#34C759', label: 'Sold Follow-up' };
      case 'check_in': return { icon: 'chatbubble', color: '#007AFF', label: 'Check-in' };
      default: return { icon: 'create', color: colors.textSecondary, label: 'Custom' };
    }
  };
  
  const addSequenceStep = () => {
    const newId = String(sequences.length + 1);
    const lastStep = sequences[sequences.length - 1];
    setSequences([
      ...sequences,
      { 
        id: newId,
        step: sequences.length + 1,
        actionType: 'message',
        cardType: '',
        message: '', 
        delayHours: 0,
        delayDays: 0, 
        delayMonths: (lastStep?.delayMonths || 0) + 1,
        media_urls: [],
      },
    ]);
    setHasChanges(true);
  };
  
  const removeSequenceStep = (stepId: string) => {
    if (sequences.length > 1) {
      setSequences(sequences.filter(s => s.id !== stepId));
      setHasChanges(true);
    }
  };
  
  const updateSequenceStep = (stepId: string, field: keyof SequenceStep, value: any) => {
    setSequences(sequences.map(s => 
      s.id === stepId ? { ...s, [field]: value } : s
    ));
    setHasChanges(true);
  };
  
  const pickMediaForStep = async (stepId: string) => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        showSimpleAlert('Permission Required', 'Please allow access to your photo library.');
        return;
      }
      
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false,
        quality: 0.8,
        allowsMultipleSelection: false,
      });
      
      if (!result.canceled && result.assets && result.assets[0]) {
        const asset = result.assets[0];
        setUploadingMedia(stepId);
        
        try {
          const formData = new FormData();
          const filename = asset.uri.split('/').pop() || 'image.jpg';
          const match = /\.(\w+)$/.exec(filename);
          const type = match ? `image/${match[1]}` : 'image/jpeg';
          
          formData.append('file', { uri: asset.uri, name: filename, type } as any);
          
          const uploadResponse = await api.post('/media/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          
          if (uploadResponse.data.url) {
            setSequences(sequences.map(s => 
              s.id === stepId 
                ? { ...s, media_urls: [...s.media_urls, uploadResponse.data.url] }
                : s
            ));
            setHasChanges(true);
          }
        } catch (uploadError) {
          // Use local URI as fallback
          setSequences(sequences.map(s => 
            s.id === stepId 
              ? { ...s, media_urls: [...s.media_urls, asset.uri] }
              : s
          ));
          setHasChanges(true);
        }
      }
    } catch (error) {
      console.error('Error picking media:', error);
      showSimpleAlert('Error', 'Failed to select image.');
    } finally {
      setUploadingMedia(null);
    }
  };
  
  const removeMediaFromStep = (stepId: string, mediaIndex: number) => {
    setSequences(sequences.map(s => 
      s.id === stepId 
        ? { ...s, media_urls: s.media_urls.filter((_, idx) => idx !== mediaIndex) }
        : s
    ));
    setHasChanges(true);
  };
  
  const getDelayLabel = (step: SequenceStep, index: number) => {
    const parts = [];
    if (step.delayMonths > 0) {
      parts.push(`${step.delayMonths} month${step.delayMonths > 1 ? 's' : ''}`);
    }
    if (step.delayDays > 0) {
      parts.push(`${step.delayDays} day${step.delayDays > 1 ? 's' : ''}`);
    }
    if (step.delayHours > 0) {
      parts.push(`${step.delayHours} hour${step.delayHours > 1 ? 's' : ''}`);
    }
    
    if (parts.length === 0) {
      return index === 0 ? 'Immediately when triggered' : 'Immediately after previous';
    }
    return index === 0 ? `${parts.join(' ')} after trigger` : `After ${parts.join(' ')}`;
  };
  
  const handleSave = async () => {
    if (!name.trim()) {
      showSimpleAlert('Error', 'Please enter a campaign name');
      return;
    }
    
    if (sequences.some(s => s.actionType === 'message' && !s.message.trim())) {
      showSimpleAlert('Error', 'Please fill in all message templates');
      return;
    }
    
    if (sequences.some(s => s.actionType === 'send_card' && !s.cardType)) {
      showSimpleAlert('Error', 'Please select a card type for all card steps');
      return;
    }
    
    try {
      setSaving(true);
      
      const updateData = {
        name: name.trim(),
        trigger_tag: triggerTag,
        active,
        send_time: format(sendTime, 'HH:mm'),
        sequences: sequences.map((s, idx) => ({
          step: idx + 1,
          action_type: s.actionType,
          card_type: s.cardType,
          message_template: s.message,
          delay_hours: s.delayHours,
          delay_days: s.delayDays,
          delay_months: s.delayMonths,
          media_urls: s.media_urls,
        })),
      };
      
      await campaignsAPI.update(user!._id, id!, updateData);
      setHasChanges(false);
      showToast('Campaign updated successfully');
      
    } catch (error) {
      console.error('Failed to save campaign:', error);
      showSimpleAlert('Error', 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };
  
  const handleDelete = () => {
    showAlert(
      'Delete Campaign',
      `Are you sure you want to delete "${name}"? This will also remove all enrollments.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Delete', 
          style: 'destructive',
          onPress: async () => {
            try {
              setDeleting(true);
              await campaignsAPI.delete(user!._id, id!);
              router.back();
            } catch (error) {
              console.error('Failed to delete campaign:', error);
              showSimpleAlert('Error', 'Failed to delete campaign');
            } finally {
              setDeleting(false);
            }
          }
        },
      ]
    );
  };
  
  const handleTimeChange = (event: any, selectedDate?: Date) => {
    if (Platform.OS === 'android') {
      setShowTimePicker(false);
    }
    if (selectedDate) {
      setSendTime(selectedDate);
      setHasChanges(true);
    }
  };
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#007AFF';
      case 'completed': return '#34C759';
      case 'cancelled': return '#FF3B30';
      default: return colors.textSecondary;
    }
  };
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }
  
  if (!campaign) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={64} color="#FF3B30" />
          <Text style={styles.errorText}>Campaign not found</Text>
          <TouchableOpacity style={styles.backLink} onPress={() => router.back()}>
            <Text style={styles.backLinkText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }
  
  const typeInfo = getCampaignTypeInfo(campaign.type);
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.title} numberOfLines={1}>Edit Campaign</Text>
        
        <TouchableOpacity 
          onPress={handleSave} 
          disabled={saving || !hasChanges}
          style={styles.saveButton}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <Text style={[styles.saveText, !hasChanges && styles.saveTextDisabled]}>
              Save
            </Text>
          )}
        </TouchableOpacity>
      </View>
      
      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Campaign Type Badge */}
        <View style={styles.typeBadgeContainer}>
          <View style={[styles.typeBadge, { backgroundColor: `${typeInfo.color}20` }]}>
            <Ionicons name={typeInfo.icon as any} size={20} color={typeInfo.color} />
            <Text style={[styles.typeBadgeText, { color: typeInfo.color }]}>{typeInfo.label}</Text>
          </View>
        </View>
        
        {/* Campaign Name */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Campaign Name</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={(text) => { setName(text); setHasChanges(true); }}
            placeholder="Enter campaign name"
            placeholderTextColor="#6E6E73"
          />
        </View>
        
        {/* Trigger Tag */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Trigger Tag</Text>
          <SmartTagPicker
            tags={availableTags}
            selectedTag={triggerTag}
            onSelect={(tag) => { setTriggerTag(tag); setHasChanges(true); }}
            onTagCreated={(tag) => setAvailableTags(prev => [...prev, tag])}
            userId={user?._id || ''}
            colors={colors}
          />
        </View>

        {/* Active Toggle */}
        <View style={styles.toggleSection}>
          <View style={styles.toggleInfo}>
            <Text style={styles.toggleLabel}>Campaign Active</Text>
            <Text style={styles.toggleSubtext}>
              {active ? 'Enrollments will receive messages' : 'Messages paused'}
            </Text>
          </View>
          <Switch
            value={active}
            onValueChange={(value) => { setActive(value); setHasChanges(true); }}
            trackColor={{ false: colors.borderLight, true: '#34C75980' }}
            thumbColor={active ? '#34C759' : colors.textSecondary}
          />
        </View>
        
        {/* Send Time */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Daily Send Time</Text>
          <TouchableOpacity 
            style={styles.timeButton}
            onPress={() => setShowTimePicker(true)}
          >
            <Ionicons name="time-outline" size={20} color="#007AFF" />
            <Text style={styles.timeText}>{format(sendTime, 'h:mm a')}</Text>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
        
        {showTimePicker && (
          <DateTimePicker
            value={sendTime}
            mode="time"
            is24Hour={false}
            display={Platform.OS === 'ios' ? 'spinner' : 'default'}
            onChange={handleTimeChange}
            themeVariant="dark"
          />
        )}
        
        {/* Sequences Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionLabel}>Message Sequence</Text>
            <TouchableOpacity style={styles.addButton} onPress={addSequenceStep}>
              <Ionicons name="add-circle" size={28} color="#007AFF" />
            </TouchableOpacity>
          </View>
          
          {sequences.map((step, index) => (
            <View key={step.id} style={styles.sequenceCard}>
              <View style={styles.sequenceHeader}>
                <View style={styles.stepBadge}>
                  <Text style={styles.stepNumber}>{index + 1}</Text>
                </View>
                <Text style={styles.delayLabel}>{getDelayLabel(step, index)}</Text>
                {sequences.length > 1 && (
                  <TouchableOpacity 
                    onPress={() => removeSequenceStep(step.id)}
                    style={styles.removeButton}
                  >
                    <Ionicons name="close-circle" size={24} color="#FF3B30" />
                  </TouchableOpacity>
                )}
              </View>
              
              {/* Action Type Toggle */}
              <View style={styles.actionTypeRow}>
                <TouchableOpacity
                  style={[styles.actionTypeBtn, step.actionType === 'message' && styles.actionTypeBtnActive]}
                  onPress={() => { updateSequenceStep(step.id, 'actionType', 'message'); }}
                  data-testid={`step-${index}-type-message`}
                >
                  <Ionicons name="chatbubble-outline" size={16} color={step.actionType === 'message' ? '#FFF' : colors.textSecondary} />
                  <Text style={[styles.actionTypeBtnText, step.actionType === 'message' && styles.actionTypeBtnTextActive]}>Send Message</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.actionTypeBtn, step.actionType === 'send_card' && styles.actionTypeBtnActive]}
                  onPress={() => { updateSequenceStep(step.id, 'actionType', 'send_card'); }}
                  data-testid={`step-${index}-type-card`}
                >
                  <Ionicons name="gift-outline" size={16} color={step.actionType === 'send_card' ? '#FFF' : colors.textSecondary} />
                  <Text style={[styles.actionTypeBtnText, step.actionType === 'send_card' && styles.actionTypeBtnTextActive]}>Send Card</Text>
                </TouchableOpacity>
              </View>
              
              {/* Delay Controls — shown for ALL steps including step 1 */}
              <View style={styles.delayControls}>
                <View style={styles.delayInput}>
                  <Text style={styles.delayInputLabel}>Months</Text>
                  <View style={styles.stepper}>
                    <TouchableOpacity 
                      style={styles.stepperButton}
                      onPress={() => updateSequenceStep(step.id, 'delayMonths', Math.max(0, step.delayMonths - 1))}
                    >
                      <Ionicons name="remove" size={20} color={colors.text} />
                    </TouchableOpacity>
                    <Text style={styles.stepperValue}>{step.delayMonths}</Text>
                    <TouchableOpacity 
                      style={styles.stepperButton}
                      onPress={() => updateSequenceStep(step.id, 'delayMonths', step.delayMonths + 1)}
                    >
                      <Ionicons name="add" size={20} color={colors.text} />
                    </TouchableOpacity>
                  </View>
                </View>
                
                <View style={styles.delayInput}>
                  <Text style={styles.delayInputLabel}>Days</Text>
                  <View style={styles.stepper}>
                    <TouchableOpacity 
                      style={styles.stepperButton}
                      onPress={() => updateSequenceStep(step.id, 'delayDays', Math.max(0, step.delayDays - 1))}
                    >
                      <Ionicons name="remove" size={20} color={colors.text} />
                    </TouchableOpacity>
                    <Text style={styles.stepperValue}>{step.delayDays}</Text>
                    <TouchableOpacity 
                      style={styles.stepperButton}
                      onPress={() => updateSequenceStep(step.id, 'delayDays', step.delayDays + 1)}
                    >
                      <Ionicons name="add" size={20} color={colors.text} />
                    </TouchableOpacity>
                  </View>
                </View>

                <View style={styles.delayInput}>
                  <Text style={styles.delayInputLabel}>Hours</Text>
                  <View style={styles.stepper}>
                    <TouchableOpacity 
                      style={styles.stepperButton}
                      onPress={() => updateSequenceStep(step.id, 'delayHours', Math.max(0, step.delayHours - 1))}
                    >
                      <Ionicons name="remove" size={20} color={colors.text} />
                    </TouchableOpacity>
                    <Text style={styles.stepperValue}>{step.delayHours}</Text>
                    <TouchableOpacity 
                      style={styles.stepperButton}
                      onPress={() => updateSequenceStep(step.id, 'delayHours', step.delayHours + 1)}
                    >
                      <Ionicons name="add" size={20} color={colors.text} />
                    </TouchableOpacity>
                  </View>
                </View>
              </View>
              
              {step.actionType === 'send_card' ? (
                /* Card Type Picker */
                <View style={styles.cardPickerSection}>
                  <Text style={styles.cardPickerLabel}>Select Card Template</Text>
                  <View style={styles.cardPickerGrid}>
                    {[
                      { key: 'congrats', label: 'Congrats', icon: 'gift', color: '#C9A962' },
                      { key: 'birthday', label: 'Birthday', icon: 'balloon', color: '#FF2D55' },
                      { key: 'anniversary', label: 'Anniversary', icon: 'heart', color: '#FF6B6B' },
                      { key: 'thankyou', label: 'Thank You', icon: 'thumbs-up', color: '#34C759' },
                      { key: 'welcome', label: 'Welcome', icon: 'hand-left', color: '#007AFF' },
                      { key: 'holiday', label: 'Holiday', icon: 'snow', color: '#5AC8FA' },
                    ].map((card) => (
                      <TouchableOpacity
                        key={card.key}
                        style={[
                          styles.cardPickerItem,
                          step.cardType === card.key && { borderColor: card.color, borderWidth: 2 },
                        ]}
                        onPress={() => updateSequenceStep(step.id, 'cardType', card.key)}
                        data-testid={`step-${index}-card-${card.key}`}
                      >
                        <View style={[styles.cardPickerIcon, { backgroundColor: `${card.color}20` }]}>
                          <Ionicons name={card.icon as any} size={20} color={card.color} />
                        </View>
                        <Text style={[styles.cardPickerItemText, step.cardType === card.key && { color: card.color }]}>{card.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  {step.cardType ? (
                    <TouchableOpacity
                      style={styles.previewCardBtn}
                      onPress={() => setPreviewCardType(step.cardType)}
                      data-testid={`step-${index}-preview-card`}
                    >
                      <Ionicons name="eye-outline" size={16} color="#007AFF" />
                      <Text style={styles.previewCardBtnText}>Preview Card</Text>
                    </TouchableOpacity>
                  ) : null}
                </View>
              ) : (
                /* Message Input (existing) */
                <>
                  <View style={{ flexDirection: 'row', justifyContent: 'flex-end', marginBottom: 6 }}>
                    <PersonalizeButton
                      colors={colors}
                      onInsert={(tag) => {
                        updateSequenceStep(step.id, 'message', step.message + tag);
                      }}
                    />
                  </View>
                  <TextInput
                    style={styles.messageInput}
                    value={step.message}
                    onChangeText={(text) => updateSequenceStep(step.id, 'message', text)}
                    placeholder="Enter message template... Use the Personalize button above"
                    placeholderTextColor="#6E6E73"
                    multiline
                    numberOfLines={4}
                  />
                  
                  <Text style={styles.charCount}>{step.message.length}/320</Text>
                  
                  {/* Media Attachments */}
                  <View style={styles.mediaSection}>
                    <Text style={styles.mediaLabel}>Media Attachments</Text>
                    <View style={styles.mediaGrid}>
                      {step.media_urls.map((url, mediaIndex) => (
                        <View key={mediaIndex} style={styles.mediaPreview}>
                          <Image source={{ uri: url }} style={styles.mediaThumbnail} />
                          <TouchableOpacity 
                            style={styles.mediaRemoveButton}
                            onPress={() => removeMediaFromStep(step.id, mediaIndex)}
                          >
                            <Ionicons name="close-circle" size={22} color="#FF3B30" />
                          </TouchableOpacity>
                        </View>
                      ))}
                      {step.media_urls.length < 3 && (
                        <TouchableOpacity 
                          style={styles.addMediaButton}
                          onPress={() => pickMediaForStep(step.id)}
                          disabled={uploadingMedia === step.id}
                        >
                          {uploadingMedia === step.id ? (
                            <ActivityIndicator size="small" color="#007AFF" />
                          ) : (
                            <>
                              <Ionicons name="add-circle-outline" size={28} color="#007AFF" />
                              <Text style={styles.addMediaText}>Add Photo</Text>
                            </>
                          )}
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                </>
              )}
            </View>
          ))}
        </View>
        
        {/* Enrollments Section */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>
            Enrollments ({enrollments.length})
          </Text>
          
          {enrollments.length === 0 ? (
            <View style={styles.emptyEnrollments}>
              <Ionicons name="people-outline" size={32} color={colors.borderLight} />
              <Text style={styles.emptyText}>No contacts enrolled yet</Text>
            </View>
          ) : (
            <View style={styles.enrollmentsList}>
              {enrollments.slice(0, 5).map((enrollment) => (
                <TouchableOpacity 
                  key={enrollment._id} 
                  style={styles.enrollmentCard}
                  onPress={() => router.push(`/contact/${enrollment.contact_id}`)}
                >
                  <View style={styles.enrollmentInfo}>
                    <Text style={styles.enrollmentName}>{enrollment.contact_name}</Text>
                    <Text style={styles.enrollmentPhone}>{enrollment.contact_phone}</Text>
                  </View>
                  <View style={[styles.statusDot, { backgroundColor: getStatusColor(enrollment.status) }]} />
                </TouchableOpacity>
              ))}
              
              {enrollments.length > 5 && (
                <TouchableOpacity 
                  style={styles.viewAllButton}
                  onPress={() => router.push('/campaigns/dashboard')}
                >
                  <Text style={styles.viewAllText}>View All ({enrollments.length})</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>
        
        {/* Delete Button */}
        <TouchableOpacity 
          style={styles.deleteButton} 
          onPress={handleDelete}
          disabled={deleting}
        >
          {deleting ? (
            <ActivityIndicator size="small" color="#FF3B30" />
          ) : (
            <>
              <Ionicons name="trash-outline" size={20} color="#FF3B30" />
              <Text style={styles.deleteText}>Delete Campaign</Text>
            </>
          )}
        </TouchableOpacity>
        
        <View style={styles.bottomPadding} />
      </ScrollView>

      {/* Card Preview Modal */}
      <Modal visible={!!previewCardType} animationType="fade" transparent>
        <View style={styles.previewOverlay}>
          <View style={styles.previewContainer}>
            <TouchableOpacity style={styles.previewClose} onPress={() => setPreviewCardType(null)} data-testid="preview-card-close">
              <Ionicons name="close-circle" size={28} color={colors.text} />
            </TouchableOpacity>
            {(() => {
              const cards: Record<string, { label: string; icon: string; color: string; message: string; image: string }> = {
                congrats: { label: 'Congratulations!', icon: 'gift', color: '#C9A962', message: 'Congratulations on your incredible achievement! Wishing you continued success on this exciting journey.', image: 'confetti' },
                birthday: { label: 'Happy Birthday!', icon: 'balloon', color: '#FF2D55', message: 'Wishing you a wonderful birthday filled with joy, laughter, and all the things that make you happiest!', image: 'cake' },
                anniversary: { label: 'Happy Anniversary!', icon: 'heart', color: '#FF6B6B', message: "Celebrating this special milestone with you! Here's to many more wonderful memories ahead.", image: 'heart' },
                thankyou: { label: 'Thank You!', icon: 'thumbs-up', color: '#34C759', message: "Your kindness and generosity mean the world to me. I truly appreciate everything you've done!", image: 'star' },
                welcome: { label: 'Welcome!', icon: 'hand-left', color: '#007AFF', message: "We're thrilled to have you! Welcome to the family. We look forward to building a great relationship.", image: 'wave' },
                holiday: { label: 'Happy Holidays!', icon: 'snow', color: '#5AC8FA', message: 'Wishing you a season filled with warmth, happiness, and cherished moments with loved ones!', image: 'snowflake' },
              };
              const card = cards[previewCardType || 'congrats'];
              return (
                <View style={[styles.previewCard, { borderColor: card.color }]}>
                  <View style={[styles.previewCardHeader, { backgroundColor: card.color }]}>
                    <Ionicons name={card.icon as any} size={40} color={colors.text} />
                    <Text style={styles.previewCardTitle}>{card.label}</Text>
                  </View>
                  <View style={styles.previewCardBody}>
                    <Text style={styles.previewCardMessage}>{card.message}</Text>
                    <Text style={styles.previewCardPlaceholder}> - {'{ Contact Name }'}</Text>
                  </View>
                  <View style={styles.previewCardFooter}>
                    <Text style={styles.previewCardFooterText}>i'M On Social</Text>
                  </View>
                </View>
              );
            })()}
          </View>
        </View>
      </Modal>
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
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    flex: 1,
    textAlign: 'center',
    marginHorizontal: 8,
  },
  saveButton: {
    padding: 4,
    minWidth: 50,
    alignItems: 'flex-end',
  },
  saveText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  saveTextDisabled: {
    color: colors.borderLight,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    fontSize: 18,
    color: colors.text,
    marginTop: 16,
    marginBottom: 24,
  },
  backLink: {
    padding: 12,
  },
  backLinkText: {
    fontSize: 16,
    color: '#007AFF',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  typeBadgeContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  typeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 8,
  },
  typeBadgeText: {
    fontSize: 15,
    fontWeight: '600',
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  sectionLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    fontSize: 17,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  toggleSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  toggleInfo: {
    flex: 1,
  },
  toggleLabel: {
    fontSize: 17,
    fontWeight: '500',
    color: colors.text,
    marginBottom: 4,
  },
  toggleSubtext: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  timeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  timeText: {
    flex: 1,
    fontSize: 17,
    color: colors.text,
  },
  addButton: {
    padding: 4,
  },
  sequenceCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  sequenceHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 12,
  },
  stepBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumber: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.text,
  },
  delayLabel: {
    flex: 1,
    fontSize: 14,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  removeButton: {
    padding: 4,
  },
  delayControls: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 12,
  },
  delayInput: {
    flex: 1,
  },
  delayInputLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 8,
  },
  stepper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 8,
    overflow: 'hidden',
  },
  stepperButton: {
    padding: 10,
    backgroundColor: colors.borderLight,
  },
  stepperValue: {
    flex: 1,
    textAlign: 'center',
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  messageInput: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    color: colors.text,
    minHeight: 100,
    textAlignVertical: 'top',
  },
  charCount: {
    fontSize: 12,
    color: '#6E6E73',
    textAlign: 'right',
    marginTop: 8,
  },
  emptyEnrollments: {
    alignItems: 'center',
    padding: 24,
    backgroundColor: colors.card,
    borderRadius: 12,
  },
  emptyText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
  },
  enrollmentsList: {
    gap: 8,
  },
  enrollmentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
  },
  enrollmentInfo: {
    flex: 1,
  },
  enrollmentName: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.text,
  },
  enrollmentPhone: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  viewAllButton: {
    alignItems: 'center',
    padding: 12,
    backgroundColor: colors.card,
    borderRadius: 10,
  },
  viewAllText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '500',
  },
  deleteButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#FF3B30',
    gap: 8,
    marginTop: 16,
  },
  deleteText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#FF3B30',
  },
  bottomPadding: {
    height: 40,
  },
  // Media attachment styles
  mediaSection: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
  },
  mediaLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 8,
    fontWeight: '600',
  },
  mediaGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  mediaPreview: {
    width: 72,
    height: 72,
    borderRadius: 8,
    position: 'relative',
  },
  mediaThumbnail: {
    width: 72,
    height: 72,
    borderRadius: 8,
  },
  mediaRemoveButton: {
    position: 'absolute',
    top: -8,
    right: -8,
    backgroundColor: colors.bg,
    borderRadius: 11,
  },
  addMediaButton: {
    width: 72,
    height: 72,
    borderRadius: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
  },
  addMediaText: {
    fontSize: 10,
    color: '#007AFF',
    marginTop: 2,
    fontWeight: '600',
  },
  // Action type toggle
  actionTypeRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  actionTypeBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: colors.surface,
  },
  actionTypeBtnActive: {
    backgroundColor: '#007AFF',
  },
  actionTypeBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  actionTypeBtnTextActive: {
    color: colors.text,
  },
  // Card picker
  cardPickerSection: {
    marginTop: 4,
  },
  cardPickerLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 10,
    fontWeight: '600',
  },
  cardPickerGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  cardPickerItem: {
    width: '47%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderWidth: 1.5,
    borderColor: colors.borderLight,
  },
  cardPickerIcon: {
    width: 34,
    height: 34,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardPickerItemText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
    flex: 1,
  },
  previewCardBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 12,
    paddingVertical: 8,
    backgroundColor: '#007AFF15',
    borderRadius: 8,
  },
  previewCardBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#007AFF',
  },
  // Preview modal
  previewOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  previewContainer: {
    width: '100%',
    maxWidth: 360,
  },
  previewClose: {
    alignSelf: 'flex-end',
    marginBottom: 12,
  },
  previewCard: {
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: 2,
    backgroundColor: colors.card,
  },
  previewCardHeader: {
    alignItems: 'center',
    paddingVertical: 28,
    gap: 10,
  },
  previewCardTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.text,
  },
  previewCardBody: {
    padding: 20,
    gap: 12,
  },
  previewCardMessage: {
    fontSize: 15,
    lineHeight: 22,
    color: '#E0E0E0',
    textAlign: 'center',
  },
  previewCardPlaceholder: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    fontStyle: 'italic',
  },
  previewCardFooter: {
    borderTopWidth: 0.5,
    borderTopColor: colors.borderLight,
    paddingVertical: 10,
    alignItems: 'center',
  },
  previewCardFooterText: {
    fontSize: 11,
    color: '#6E6E73',
  },
});
