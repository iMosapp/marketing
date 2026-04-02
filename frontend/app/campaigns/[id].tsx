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
  delayMinutes: number;
  delay_minutes?: number;
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
  const APP_BASE = 'https://app.imonsocial.com';

  // Quick links for campaign step builder — loaded once on mount
  const [quickLinks, setQuickLinks] = React.useState<{label:string;icon:string;color:string;url:string}[]>([]);
  React.useEffect(() => {
    if (!user?._id) return;
    const links: {label:string;icon:string;color:string;url:string}[] = [
      { label: 'Digital Card', icon: 'card-outline', color: '#C9A962', url: `${APP_BASE}/card/${user._id}` },
      { label: 'Link Page', icon: 'link-outline', color: '#007AFF', url: `${APP_BASE}/l/${user._id}` },
      { label: 'Showcase', icon: 'images-outline', color: '#34C759', url: `${APP_BASE}/showcase/${user._id}` },
    ];
    // Load review links if store exists
    const storeId = (user as any)?.store_id;
    if (storeId) {
      api.get(`/admin/stores/${storeId}`).then(r => {
        const rl = r.data?.review_links || {};
        if (rl.google) links.push({ label: 'Google Review', icon: 'star-outline', color: '#FF9500', url: rl.google });
        if (rl.yelp) links.push({ label: 'Yelp Review', icon: 'star-outline', color: '#D32323', url: rl.yelp });
        if (rl.facebook) links.push({ label: 'FB Review', icon: 'logo-facebook', color: '#1877F2', url: rl.facebook });
        setQuickLinks([...links]);
      }).catch(() => setQuickLinks(links));
    } else {
      setQuickLinks(links);
    }
  }, [user?._id]);
  
const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [duplicating, setDuplicating] = useState(false);
  const [campaign, setCampaign] = useState<any>(null);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  
  // Editable fields
  const [name, setName] = useState('');
  const [triggerTag, setTriggerTag] = useState('');
  const [triggerType, setTriggerType] = useState<'tag' | 'date'>('tag');
  const [dateType, setDateType] = useState('');
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
      
      // Determine trigger type from campaign data
      const isDateCampaign = ['birthday', 'anniversary', 'sold_date'].includes(data.type) || !!data.date_type;
      setTriggerType(isDateCampaign ? 'date' : 'tag');
      setDateType(data.date_type || (isDateCampaign ? data.type : ''));
      
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
        delayMinutes: s.delay_minutes || 0,
        media_urls: s.media_urls || [],
      }));
      
      if (seqs.length === 0) {
        seqs.push({ id: '1', step: 1, actionType: 'message', cardType: '', message: data.message_template || '', delayHours: 0, delayDays: 0, delayMonths: 0, delayMinutes: 0, media_urls: [] });
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
      case 'sold_date': return { icon: 'calendar', color: '#34C759', label: 'Sold Date' };
      case 'sold_followup': return { icon: 'car', color: '#34C759', label: 'Sold Follow-up' };
      case 'check_in': return { icon: 'chatbubble', color: '#007AFF', label: 'Check-in' };
      default: return { icon: 'pricetag', color: '#007AFF', label: triggerType === 'date' ? 'Date Campaign' : 'Tag Campaign' };
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
        delayMinutes: 0,
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
    if (step.delayMonths > 0) parts.push(`${step.delayMonths}mo`);
    if (step.delayDays > 0) parts.push(`${step.delayDays}d`);
    if (step.delayHours > 0) parts.push(`${step.delayHours}hr`);
    if ((step.delayMinutes || 0) > 0) parts.push(`${step.delayMinutes}min`);

    if (parts.length === 0) return index === 0 ? 'Immediately when triggered' : 'Immediately from enrollment';
    const timeStr = parts.join(' ');
    return `${timeStr} from enrollment`;
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
        trigger_tag: triggerType === 'tag' ? triggerTag : '',
        type: triggerType === 'date' ? dateType : (campaign?.type || 'custom'),
        date_type: triggerType === 'date' ? dateType : '',
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
          delay_minutes: s.delayMinutes || 0,
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

  const handleDuplicate = async () => {
    if (!user || !id) return;
    try {
      setDuplicating(true);
      const newCampaign = await campaignsAPI.duplicate(user._id, id);
      showToast(`Duplicated as "${newCampaign.name}"`, 'success');
      router.replace(`/campaigns/${newCampaign._id || newCampaign.id}`);
    } catch (error: any) {
      const msg = error?.response?.data?.detail || 'Failed to duplicate campaign';
      showToast(msg, 'error');
    } finally {
      setDuplicating(false);
    }
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
        
        {/* Trigger Type Toggle */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Trigger Type</Text>
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
            <TouchableOpacity
              style={[
                { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: colors.borderLight },
                triggerType === 'tag' && { backgroundColor: '#007AFF15', borderColor: '#007AFF' },
              ]}
              onPress={() => { setTriggerType('tag'); setHasChanges(true); }}
              data-testid="edit-trigger-type-tag"
            >
              <Ionicons name="pricetag" size={16} color={triggerType === 'tag' ? '#007AFF' : colors.textSecondary} />
              <Text style={{ fontSize: 15, fontWeight: '600', color: triggerType === 'tag' ? '#007AFF' : colors.textSecondary }}>Tag-Based</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: colors.borderLight },
                triggerType === 'date' && { backgroundColor: '#FF950015', borderColor: '#FF9500' },
              ]}
              onPress={() => { setTriggerType('date'); setHasChanges(true); }}
              data-testid="edit-trigger-type-date"
            >
              <Ionicons name="calendar" size={16} color={triggerType === 'date' ? '#FF9500' : colors.textSecondary} />
              <Text style={{ fontSize: 15, fontWeight: '600', color: triggerType === 'date' ? '#FF9500' : colors.textSecondary }}>Date-Based</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Tag Trigger */}
        {triggerType === 'tag' && (
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
        )}

        {/* Date Trigger */}
        {triggerType === 'date' && (
          <View style={styles.section}>
            <Text style={styles.sectionLabel}>Which Date?</Text>
            <View style={{ gap: 8 }}>
              {[
                { id: 'birthday', name: 'Birthday', icon: 'gift', color: '#FF9500' },
                { id: 'anniversary', name: 'Purchase Anniversary', icon: 'heart', color: '#FF3B30' },
                { id: 'sold_date', name: 'Sold Date', icon: 'calendar', color: '#34C759' },
              ].map((dt) => (
                <TouchableOpacity
                  key={dt.id}
                  style={[
                    { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 14, borderWidth: 2, borderColor: dateType === dt.id ? dt.color : colors.surface },
                    dateType === dt.id && { backgroundColor: `${dt.color}08` },
                  ]}
                  onPress={() => { setDateType(dt.id); setHasChanges(true); }}
                  data-testid={`edit-date-type-${dt.id}`}
                >
                  <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: `${dt.color}20`, alignItems: 'center', justifyContent: 'center' }}>
                    <Ionicons name={dt.icon as any} size={18} color={dt.color} />
                  </View>
                  <Text style={{ flex: 1, fontSize: 16, fontWeight: '600', color: dateType === dt.id ? dt.color : colors.text }}>{dt.name}</Text>
                  {dateType === dt.id && <Ionicons name="checkmark-circle" size={20} color={dt.color} />}
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

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
              
              {/* ── DELAY CONTROLS — Quick presets + custom fields ─────── */}
              {(() => {
                const isFirstStep = index === 0;
                const MIN_MINUTES = 15; // minimum for steps 2+ to ensure reliable scheduler delivery

                // Helper: total delay in minutes for validation
                const totalMinutes = (step.delayMonths || 0) * 30 * 24 * 60
                  + (step.delayDays || 0) * 24 * 60
                  + (step.delayHours || 0) * 60
                  + (step.delayMinutes || 0);
                const belowMinimum = !isFirstStep && totalMinutes > 0 && totalMinutes < MIN_MINUTES;

                // Step 1: can fire immediately. Steps 2+: minimum 15 min.
                const PRESETS = isFirstStep
                  ? [
                      { label: 'Now', mo: 0, d: 0, h: 0, m: 0 },
                      { label: '15 min', mo: 0, d: 0, h: 0, m: 15 },
                      { label: '30 min', mo: 0, d: 0, h: 0, m: 30 },
                      { label: '1 hr', mo: 0, d: 0, h: 1, m: 0 },
                      { label: '4 hrs', mo: 0, d: 0, h: 4, m: 0 },
                      { label: '1 day', mo: 0, d: 1, h: 0, m: 0 },
                    ]
                  : [
                      // Sub-15min options removed for steps 2+ — unreliable below scheduler interval
                      { label: '15 min', mo: 0, d: 0, h: 0, m: 15 },
                      { label: '30 min', mo: 0, d: 0, h: 0, m: 30 },
                      { label: '1 hr', mo: 0, d: 0, h: 1, m: 0 },
                      { label: '4 hrs', mo: 0, d: 0, h: 4, m: 0 },
                      { label: '1 day', mo: 0, d: 1, h: 0, m: 0 },
                      { label: '3 days', mo: 0, d: 3, h: 0, m: 0 },
                      { label: '1 week', mo: 0, d: 7, h: 0, m: 0 },
                      { label: '2 weeks', mo: 0, d: 14, h: 0, m: 0 },
                      { label: '1 month', mo: 1, d: 0, h: 0, m: 0 },
                      { label: '3 months', mo: 3, d: 0, h: 0, m: 0 },
                      { label: '6 months', mo: 6, d: 0, h: 0, m: 0 },
                      { label: '1 year', mo: 12, d: 0, h: 0, m: 0 },
                    ];
                const activePreset = PRESETS.find(p =>
                  p.mo === step.delayMonths && p.d === step.delayDays &&
                  p.h === step.delayHours && p.m === (step.delayMinutes || 0)
                );
                const applyPreset = (p: typeof PRESETS[0]) => {
                  updateSequenceStep(step.id, 'delayMonths', p.mo);
                  updateSequenceStep(step.id, 'delayDays', p.d);
                  updateSequenceStep(step.id, 'delayHours', p.h);
                  updateSequenceStep(step.id, 'delayMinutes', p.m);
                };
                return (
                  <View style={{ marginTop: 4 }}>
                    <Text style={[styles.delayInputLabel, { marginBottom: 4 }]}>
                      {isFirstStep ? 'From enrollment date' : 'From enrollment date'}
                    </Text>

                    {/* 15-min minimum warning for steps 2+ */}
                    {!isFirstStep && (
                      <Text style={{ fontSize: 11, color: colors.textTertiary, marginBottom: 8 }}>
                        Minimum 15 min — ensures reliable delivery
                      </Text>
                    )}

                    {/* Warning if custom value is below minimum */}
                    {belowMinimum && (
                      <TouchableOpacity
                        onPress={() => {
                          updateSequenceStep(step.id, 'delayMinutes', MIN_MINUTES);
                          updateSequenceStep(step.id, 'delayHours', 0);
                          updateSequenceStep(step.id, 'delayDays', 0);
                          updateSequenceStep(step.id, 'delayMonths', 0);
                        }}
                        style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FF9500' + '20', borderRadius: 8, padding: 8, marginBottom: 8, borderWidth: 1, borderColor: '#FF9500' + '40' }}
                      >
                        <Ionicons name="warning-outline" size={14} color="#FF9500" />
                        <Text style={{ fontSize: 12, color: '#FF9500', flex: 1 }}>
                          Delays under 15 min may not fire reliably. Tap to set 15 min.
                        </Text>
                      </TouchableOpacity>
                    )}
                    {/* Preset chips */}
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
                      <View style={{ flexDirection: 'row', gap: 6 }}>
                        {PRESETS.map(p => {
                          const isActive = activePreset?.label === p.label;
                          return (
                            <TouchableOpacity
                              key={p.label}
                              onPress={() => applyPreset(p)}
                              style={{
                                paddingHorizontal: 12, paddingVertical: 7,
                                borderRadius: 20,
                                backgroundColor: isActive ? '#C9A962' : colors.card,
                                borderWidth: 1,
                                borderColor: isActive ? '#C9A962' : colors.borderLight,
                              }}
                              data-testid={`delay-preset-${p.label}`}
                            >
                              <Text style={{ fontSize: 13, fontWeight: isActive ? '700' : '500', color: isActive ? '#000' : colors.text }}>
                                {p.label}
                              </Text>
                            </TouchableOpacity>
                          );
                        })}
                      </View>
                    </ScrollView>

                    {/* Custom fields — compact row, all 4 visible on any screen */}
                    <View style={{ flexDirection: 'row', gap: 6 }}>
                      {[
                        { key: 'delayMonths', label: 'Mo', max: 24 },
                        { key: 'delayDays', label: 'Days', max: 365 },
                        { key: 'delayHours', label: 'Hrs', max: 23 },
                        { key: 'delayMinutes', label: 'Min', max: 59 },
                      ].map(({ key, label, max }) => (
                        <View key={key} style={{ flex: 1, alignItems: 'center' }}>
                          <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 3, fontWeight: '600' }}>{label}</Text>
                          <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 8, borderWidth: 1, borderColor: colors.borderLight, overflow: 'hidden' }}>
                            <TouchableOpacity
                              style={{ padding: 6 }}
                              onPress={() => updateSequenceStep(step.id, key, Math.max(0, ((step as any)[key] ?? 0) - 1))}
                            >
                              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '700', lineHeight: 18 }}>−</Text>
                            </TouchableOpacity>
                            <Text style={{ fontSize: 13, color: colors.text, fontWeight: '700', minWidth: 20, textAlign: 'center' }}>
                              {(step as any)[key] ?? 0}
                            </Text>
                            <TouchableOpacity
                              style={{ padding: 6 }}
                              onPress={() => updateSequenceStep(step.id, key, Math.min(max, ((step as any)[key] ?? 0) + 1))}
                            >
                              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '700', lineHeight: 18 }}>+</Text>
                            </TouchableOpacity>
                          </View>
                        </View>
                      ))}
                    </View>
                  </View>
                );
              })()}
              
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

                  {/* Quick Link Insert — tap to append your tracked links */}
                  {quickLinks.length > 0 && (
                    <View style={{ marginTop: 8, marginBottom: 4 }}>
                      <Text style={{ fontSize: 11, color: colors.textTertiary, marginBottom: 5, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.4 }}>
                        Insert Link
                      </Text>
                      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                        <View style={{ flexDirection: 'row', gap: 6 }}>
                          {quickLinks.map(link => (
                            <TouchableOpacity
                              key={link.label}
                              onPress={() => updateSequenceStep(step.id, 'message', (step.message ? step.message + ' ' : '') + link.url)}
                              style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, backgroundColor: link.color + '18', borderWidth: 1, borderColor: link.color + '40' }}
                              data-testid={`insert-link-${link.label}`}
                            >
                              <Ionicons name={link.icon as any} size={13} color={link.color} />
                              <Text style={{ fontSize: 12, fontWeight: '600', color: link.color }}>{link.label}</Text>
                            </TouchableOpacity>
                          ))}
                        </View>
                      </ScrollView>
                    </View>
                  )}
                  
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
        
        {/* Duplicate Button */}
        <TouchableOpacity 
          style={styles.duplicateButton} 
          onPress={handleDuplicate}
          disabled={duplicating}
          testID="duplicate-campaign-btn"
          data-testid="duplicate-campaign-btn"
        >
          {duplicating ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : (
            <>
              <Ionicons name="copy-outline" size={20} color="#007AFF" />
              <Text style={styles.duplicateText}>Duplicate Campaign</Text>
            </>
          )}
        </TouchableOpacity>

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
    fontSize: 19,
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
    fontSize: 18,
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
    fontSize: 19,
    color: colors.text,
    marginTop: 16,
    marginBottom: 24,
  },
  backLink: {
    padding: 12,
  },
  backLinkText: {
    fontSize: 18,
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
    fontSize: 17,
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
    fontSize: 15,
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
    fontSize: 18,
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
    fontSize: 18,
    fontWeight: '500',
    color: colors.text,
    marginBottom: 4,
  },
  toggleSubtext: {
    fontSize: 15,
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
    fontSize: 18,
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
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  delayLabel: {
    flex: 1,
    fontSize: 16,
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
    fontSize: 14,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  messageInput: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 12,
    fontSize: 17,
    color: colors.text,
    minHeight: 100,
    textAlignVertical: 'top',
  },
  charCount: {
    fontSize: 14,
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
    fontSize: 16,
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
    fontSize: 17,
    fontWeight: '500',
    color: colors.text,
  },
  enrollmentPhone: {
    fontSize: 15,
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
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
  duplicateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#007AFF',
    gap: 8,
    marginTop: 16,
  },
  duplicateText: {
    fontSize: 18,
    fontWeight: '500',
    color: '#007AFF',
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
    fontSize: 18,
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
    fontSize: 14,
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
    fontSize: 12,
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
    fontSize: 15,
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
    fontSize: 14,
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
    fontSize: 15,
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
    fontSize: 15,
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
    fontSize: 17,
    lineHeight: 22,
    color: '#E0E0E0',
    textAlign: 'center',
  },
  previewCardPlaceholder: {
    fontSize: 16,
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
    fontSize: 13,
    color: '#6E6E73',
  },
});
