import React, {
  useState } from 'react';
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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import DateTimePicker from '@react-native-community/datetimepicker';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../../store/authStore';
import { campaignsAPI } from '../../services/api';
import api from '../../services/api';
import { format, addDays, addMonths } from 'date-fns';
import { WebModal } from '../../components/WebModal';
import { useToast } from '../../components/common/Toast';
import { showAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
import { PersonalizeButton } from '../../components/PersonalizeButton';
import { SmartTagPicker } from '../../components/SmartTagPicker';
interface SequenceStep {
  id: string;
  message: string;
  delayHours: number;
  delayDays: number;
  delayMonths: number;
  delayMinutes: number;
  media_urls: string[];
  channel: string;
  ai_generated: boolean;
  step_context: string;
}

export default function CampaignBuilderScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
const { showToast } = useToast();
  const [showTemplates, setShowTemplates] = useState(true);
  const [prebuiltTemplates, setPrebuiltTemplates] = useState<any[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
    const [campaign, setCampaign] = useState({
    name: '',
    type: 'tag' as 'tag' | 'date',
    dateType: '' as '' | 'birthday' | 'anniversary' | 'sold_date',
    triggerTag: '',
    selectedTags: [] as string[],
    active: true,
    sendTime: new Date(new Date().setHours(10, 0, 0, 0)),
    deliveryMode: 'manual' as 'manual' | 'automated',
    aiEnabled: false,
    ownershipLevel: 'user' as 'user' | 'store' | 'org',
  });
  
  const [sequences, setSequences] = useState<SequenceStep[]>([
    { id: '1', message: '', delayHours: 0, delayDays: 0, delayMonths: 0, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: '' },
  ]);
  
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploadingMedia, setUploadingMedia] = useState<string | null>(null);
  const [generatingAI, setGeneratingAI] = useState<string | null>(null);
  const [tags, setTags] = useState<string[]>([]);

  // Fetch tags from API
  React.useEffect(() => {
    if (!user?._id) return;
    api.get(`/tags/${user._id}`).then(res => {
      const tagNames = (res.data || []).map((t: any) => t.name || t);
      setTags(tagNames.length > 0 ? tagNames : ['sold', 'lead', 'hot', 'customer', 'service_due', 'referral', 'vip']);
    }).catch(() => {
      setTags(['sold', 'lead', 'hot', 'customer', 'service_due', 'referral', 'vip']);
    });
  }, [user?._id]);

  // Fetch pre-built templates
  React.useEffect(() => {
    api.get('/campaigns/templates/prebuilt').then(res => {
      setPrebuiltTemplates(res.data || []);
    }).catch(() => {}).finally(() => setLoadingTemplates(false));
  }, []);

  const selectPrebuiltTemplate = async (templateId: string) => {
    try {
      const res = await api.get(`/campaigns/templates/prebuilt/${templateId}`);
      const tpl = res.data;
      setCampaign({
        ...campaign,
        name: tpl.name,
        type: 'tag',
        triggerTag: tpl.trigger_tag || '',
        selectedTags: tpl.trigger_tag ? [tpl.trigger_tag] : [],
        deliveryMode: tpl.delivery_mode || 'manual',
        aiEnabled: tpl.ai_enabled ?? true,
      });
      setSequences(
        (tpl.sequences || []).map((s: any, i: number) => ({
          id: String(i + 1),
          message: s.message_template || '',
          delayHours: s.delay_hours || 0,
          delayDays: s.delay_days || 0,
          delayMonths: s.delay_months || 0,
          media_urls: s.media_urls || [],
          channel: s.channel || 'sms',
          ai_generated: s.ai_generated ?? false,
          step_context: s.step_context || '',
        }))
      );
      setShowTemplates(false);
      showToast(`Loaded "${tpl.name}" template`, 'success');
    } catch (e) {
      showToast('Failed to load template', 'error');
    }
  };
  
  const availableTags = tags;
  
  const soldFollowupTemplates: SequenceStep[] = [
    { id: '1', message: "Hey {first_name}! Just wanted to check in - how are you enjoying your new ride? Let me know if you have any questions!", delayHours: 0, delayDays: 3, delayMonths: 0, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: 'Initial check-in after purchase' },
    { id: '2', message: "Hi {first_name}! It's been about a month since your purchase. Everything running smoothly? I'm here if you need anything!", delayHours: 0, delayDays: 0, delayMonths: 1, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: '1 month follow-up' },
    { id: '3', message: "Hey {first_name}! Quick check-in at the 3 month mark. How's everything treating you? Don't forget to schedule your first service if you haven't already!", delayHours: 0, delayDays: 0, delayMonths: 3, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: '3 month check-in' },
    { id: '4', message: "Happy 6 months, {first_name}! Hope you're still loving it. Let me know if there's anything I can help with!", delayHours: 0, delayDays: 0, delayMonths: 6, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: '6 month milestone' },
    { id: '5', message: "Can you believe it's been a year, {first_name}?! Time flies! If you know anyone looking for a great deal, send them my way!", delayHours: 0, delayDays: 0, delayMonths: 12, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: '1 year anniversary' },
  ];

  const DATE_TYPES = [
    { id: 'birthday', name: 'Birthday', icon: 'gift', color: '#FF9500', description: 'Auto-send on their birthday every year', defaultMsg: "Happy birthday, {first_name}! Hope you have an amazing day!" },
    { id: 'anniversary', name: 'Purchase Anniversary', icon: 'heart', color: '#FF3B30', description: 'Celebrate the date they bought from you', defaultMsg: "Happy anniversary on your purchase, {first_name}! Hope it's still treating you well!" },
    { id: 'sold_date', name: 'Sold Date', icon: 'calendar', color: '#34C759', description: 'Trigger messages based on purchase date', defaultMsg: "Hey {first_name}! Checking in since your purchase. How's everything going?" },
  ];

  const handleTriggerTypeSelect = (triggerType: 'tag' | 'date') => {
    setCampaign(prev => ({ ...prev, type: triggerType, dateType: '', triggerTag: '' }));
    if (triggerType === 'tag') {
      setSequences([{ id: '1', message: '', delayHours: 0, delayDays: 0, delayMonths: 0, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: '' }]);
    }
  };

  const handleDateTypeSelect = (dateType: string) => {
    const dt = DATE_TYPES.find(d => d.id === dateType);
    setCampaign(prev => ({ ...prev, dateType: dateType as any, name: prev.name || dt?.name || '' }));
    setSequences([{
      id: '1', message: dt?.defaultMsg || '', delayHours: 0, delayDays: 0, delayMonths: 0, delayMinutes: 0,
      media_urls: [], channel: 'sms', ai_generated: false, step_context: dt?.name || '',
    }]);
  };

  const handleTagTemplateSelect = (template: 'sold_followup' | 'check_in' | 'custom') => {
    if (template === 'sold_followup') {
      setSequences(soldFollowupTemplates);
      setCampaign(prev => ({ ...prev, name: prev.name || 'Sold Follow-up', triggerTag: 'Sold' }));
    } else if (template === 'check_in') {
      setSequences([{ id: '1', message: "Hey {first_name}! Just checking in to see how things are going. Is there anything I can help with?", delayHours: 0, delayDays: 0, delayMonths: 0, delayMinutes: 0, media_urls: [], channel: 'sms', ai_generated: false, step_context: 'Check-in' }]);
      setCampaign(prev => ({ ...prev, name: prev.name || 'Check-in Campaign', triggerTag: 'Follow Up' }));
    }
  };
  
  const toggleTag = (tag: string) => {
    if (campaign.selectedTags.includes(tag)) {
      setCampaign({
        ...campaign,
        selectedTags: campaign.selectedTags.filter((t) => t !== tag),
      });
    } else {
      setCampaign({
        ...campaign,
        selectedTags: [...campaign.selectedTags, tag],
      });
    }
  };
  
  const addSequenceStep = () => {
    const newId = String(sequences.length + 1);
    const lastStep = sequences[sequences.length - 1];
    setSequences([
      ...sequences,
      { 
        id: newId, 
        message: '', 
        delayHours: 0,
        delayDays: 0, 
        delayMonths: lastStep.delayMonths + 1,
        media_urls: [],
        channel: lastStep.channel || 'sms',
        ai_generated: campaign.aiEnabled,
        step_context: '',
      },
    ]);
  };
  
  const removeSequenceStep = (id: string) => {
    if (sequences.length > 1) {
      setSequences(sequences.filter(s => s.id !== id));
    }
  };
  
  const updateSequenceStep = (id: string, field: keyof SequenceStep, value: any) => {
    setSequences(sequences.map(s => 
      s.id === id ? { ...s, [field]: value } : s
    ));
  };
  
  const pickMediaForStep = async (stepId: string) => {
    try {
      // Request permissions
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        showAlert('Permission Required', 'Please allow access to your photo library to attach media.');
        return;
      }
      
      // Launch image picker
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
          // Create form data for upload
          const formData = new FormData();
          const filename = asset.uri.split('/').pop() || 'image.jpg';
          const match = /\.(\w+)$/.exec(filename);
          const type = match ? `image/${match[1]}` : 'image/jpeg';
          
          formData.append('file', {
            uri: asset.uri,
            name: filename,
            type,
          } as any);
          
          // Upload the image
          const uploadResponse = await api.post('/media/upload', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          });
          
          if (uploadResponse.data.url) {
            // Add URL to the step's media_urls
            setSequences(sequences.map(s => 
              s.id === stepId 
                ? { ...s, media_urls: [...s.media_urls, uploadResponse.data.url] }
                : s
            ));
          }
        } catch (uploadError) {
          console.error('Upload error:', uploadError);
          // For now, use the local URI as a fallback
          setSequences(sequences.map(s => 
            s.id === stepId 
              ? { ...s, media_urls: [...s.media_urls, asset.uri] }
              : s
          ));
        }
      }
    } catch (error) {
      console.error('Error picking media:', error);
      showAlert('Error', 'Failed to select image. Please try again.');
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
  };
  
  const getDelayLabel = (step: SequenceStep, index: number) => {
    const parts = [];
    if (step.delayMonths > 0) parts.push(`${step.delayMonths}mo`);
    if (step.delayDays > 0) parts.push(`${step.delayDays}d`);
    if (step.delayHours > 0) parts.push(`${step.delayHours}hr`);
    if ((step.delayMinutes || 0) > 0) parts.push(`${step.delayMinutes}min`);
    if (parts.length === 0) return index === 0 ? 'Immediately when triggered' : 'Immediately (from enrollment)';
    const timeStr = parts.join(' ');
    return `${timeStr} from enrollment`;
  };
  
  const handleTimeChange = (event: any, selectedDate?: Date) => {
    if (Platform.OS === 'android') {
      setShowTimePicker(false);
    }
    if (selectedDate) {
      setCampaign({ ...campaign, sendTime: selectedDate });
    }
  };
  
  const handleSave = async () => {
    if (!campaign.name) {
      showToast('Please enter a campaign name', 'error');
      return;
    }
    
    if (sequences.some(s => !s.message.trim())) {
      showToast('Please fill in all message templates', 'error');
      return;
    }
    
    if (campaign.type === 'tag' && campaign.selectedTags.length === 0 && !campaign.triggerTag) {
      showToast('Please select a trigger tag', 'error');
      return;
    }

    if (campaign.type === 'date' && !campaign.dateType) {
      showToast('Please select a date type', 'error');
      return;
    }
    
    if (!user) {
      showToast('Please log in to create campaigns', 'error');
      return;
    }
    
    try {
      setSaving(true);
      
      const campaignData = {
        name: campaign.name,
        type: campaign.type === 'date' ? campaign.dateType : (campaign.type || 'custom'),
        trigger_tag: campaign.type === 'tag' ? (campaign.triggerTag || campaign.selectedTags[0]) : '',
        segment_tags: campaign.type === 'tag' ? campaign.selectedTags : [],
        date_type: campaign.type === 'date' ? campaign.dateType : '',
        sequences: sequences.map((s, index) => ({
          step: index + 1,
          message_template: s.message,
          delay_hours: s.delayHours,
          delay_days: s.delayDays,
          delay_months: s.delayMonths,
          delay_minutes: s.delayMinutes || 0,
          media_urls: s.media_urls,
          channel: s.channel,
          ai_generated: s.ai_generated,
          step_context: s.step_context,
        })),
        send_time: format(campaign.sendTime, 'HH:mm'),
        active: campaign.active,
        delivery_mode: campaign.deliveryMode,
        ai_enabled: campaign.aiEnabled,
        ownership_level: campaign.ownershipLevel,
      };
      
      await campaignsAPI.create(user._id, campaignData);
      
      showToast(`Campaign created with ${sequences.length} message${sequences.length > 1 ? 's' : ''} in sequence!`, 'success');
      router.replace('/campaigns');
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Failed to create campaign';
      showToast(errorMessage, 'error');
      console.error('Create campaign error:', error);
    } finally {
      setSaving(false);
    }
  };
  
  // Template picker icon mapping
  const getTemplateIcon = (icon: string): string => {
    const map: Record<string, string> = {
      car: 'car-sport', refresh: 'refresh-circle', construct: 'construct',
      people: 'people', diamond: 'diamond',
    };
    return map[icon] || icon;
  };

  // ===== TEMPLATE PICKER SCREEN =====
  if (showTemplates) {
    return (
      <SafeAreaView style={styles.container} edges={['top']} data-testid="template-picker">
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="close" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>New Campaign</Text>
          <TouchableOpacity onPress={() => setShowTemplates(false)} data-testid="skip-templates-btn">
            <Text style={{ color: '#007AFF', fontSize: 17, fontWeight: '600' }}>Build Custom</Text>
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 4 }}>
            Start with a Template
          </Text>
          <Text style={{ fontSize: 16, color: colors.textSecondary, marginBottom: 20, lineHeight: 20 }}>
            Choose a proven campaign sequence or build your own from scratch. Templates come pre-loaded with timing, AI-powered personalization, and messages that sound like a real conversation.
          </Text>

          {loadingTemplates ? (
            <ActivityIndicator size="large" color="#007AFF" style={{ marginTop: 40 }} />
          ) : (
            prebuiltTemplates.map((tpl: any) => (
              <TouchableOpacity
                key={tpl.id}
                style={styles.templateCard}
                onPress={() => selectPrebuiltTemplate(tpl.id)}
                data-testid={`template-${tpl.id}`}
              >
                <View style={{ flexDirection: 'row', gap: 14, alignItems: 'flex-start' }}>
                  <View style={[styles.templateIcon, { backgroundColor: tpl.color + '18' }]}>
                    <Ionicons name={getTemplateIcon(tpl.icon) as any} size={24} color={tpl.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.templateName}>{tpl.name}</Text>
                    <Text style={styles.templateDesc}>{tpl.description}</Text>
                    <View style={styles.templateMeta}>
                      <View style={styles.templateMetaChip}>
                        <Ionicons name="layers" size={12} color={colors.textSecondary} />
                        <Text style={styles.templateMetaText}>{tpl.step_count} steps</Text>
                      </View>
                      <View style={styles.templateMetaChip}>
                        <Ionicons name="time" size={12} color={colors.textSecondary} />
                        <Text style={styles.templateMetaText}>{tpl.total_duration}</Text>
                      </View>
                      <View style={[styles.templateMetaChip, { backgroundColor: tpl.color + '15' }]}>
                        <Ionicons name="pricetag" size={12} color={tpl.color} />
                        <Text style={[styles.templateMetaText, { color: tpl.color }]}>{tpl.trigger_tag}</Text>
                      </View>
                      {tpl.ai_enabled && (
                        <View style={[styles.templateMetaChip, { backgroundColor: '#FFD60A15' }]}>
                          <Ionicons name="sparkles" size={12} color="#FFD60A" />
                          <Text style={[styles.templateMetaText, { color: '#FFD60A' }]}>AI</Text>
                        </View>
                      )}
                    </View>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.borderLight} style={{ marginTop: 4 }} />
                </View>
              </TouchableOpacity>
            ))
          )}

          {/* Build Custom option */}
          <TouchableOpacity
            style={[styles.templateCard, { borderStyle: 'dashed', borderColor: colors.borderLight }]}
            onPress={() => setShowTemplates(false)}
            data-testid="build-custom-btn"
          >
            <View style={{ flexDirection: 'row', gap: 14, alignItems: 'center' }}>
              <View style={[styles.templateIcon, { backgroundColor: colors.surface }]}>
                <Ionicons name="add" size={24} color={colors.textSecondary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.templateName}>Build From Scratch</Text>
                <Text style={styles.templateDesc}>Create a fully custom campaign with your own timing, messages, and triggers.</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.borderLight} />
            </View>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ===== MAIN CAMPAIGN BUILDER =====
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="close" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.headerTitle}>New Campaign</Text>
        
        <TouchableOpacity onPress={handleSave} style={styles.saveButton} disabled={saving} testID="create-campaign-btn" data-testid="create-campaign-btn">
          {saving ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <Text style={styles.saveButtonText}>Create</Text>
          )}
        </TouchableOpacity>
      </View>
      
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Campaign Name */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Campaign Name</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., Sold Customer Follow-up"
            placeholderTextColor={colors.textSecondary}
            value={campaign.name}
            onChangeText={(text) => setCampaign({ ...campaign, name: text })}
          />
        </View>
        
        {/* Trigger Type — Tag vs Date */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>What triggers this campaign?</Text>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <TouchableOpacity
              style={[
                styles.modeCard,
                campaign.type === 'tag' && { borderColor: '#007AFF50', backgroundColor: '#007AFF08' },
              ]}
              onPress={() => handleTriggerTypeSelect('tag')}
              data-testid="trigger-type-tag"
            >
              <Ionicons name="pricetag" size={24} color={campaign.type === 'tag' ? '#007AFF' : colors.textSecondary} />
              <Text style={[styles.modeTitle, campaign.type === 'tag' && { color: '#007AFF' }]}>Tag-Based</Text>
              <Text style={styles.modeDesc}>Starts when a tag is applied to a contact (e.g., "Sold", "VIP")</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.modeCard,
                campaign.type === 'date' && { borderColor: '#FF950050', backgroundColor: '#FF950008' },
              ]}
              onPress={() => handleTriggerTypeSelect('date')}
              data-testid="trigger-type-date"
            >
              <Ionicons name="calendar" size={24} color={campaign.type === 'date' ? '#FF9500' : colors.textSecondary} />
              <Text style={[styles.modeTitle, campaign.type === 'date' && { color: '#FF9500' }]}>Date-Based</Text>
              <Text style={styles.modeDesc}>Fires on a special date like Birthday, Anniversary, or Sold Date</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Tag Trigger — show SmartTagPicker */}
        {campaign.type === 'tag' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Trigger Tag</Text>
            <Text style={styles.sectionDescription}>
              Campaign starts when this tag is applied to a contact
            </Text>
            <SmartTagPicker
              tags={availableTags}
              selectedTag={campaign.triggerTag}
              onSelect={(tag) => setCampaign({ ...campaign, triggerTag: tag })}
              onTagCreated={(tag) => setTags(prev => [...prev, tag])}
              userId={user?._id || ''}
              colors={colors}
            />
          </View>
        )}

        {/* Date Trigger — show date type picker */}
        {campaign.type === 'date' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Which Date?</Text>
            <Text style={styles.sectionDescription}>
              Campaign triggers based on this date field on each contact. Contacts with this date filled in will be auto-enrolled.
            </Text>
            <View style={{ gap: 8 }}>
              {DATE_TYPES.map((dt) => (
                <TouchableOpacity
                  key={dt.id}
                  style={[
                    {
                      flexDirection: 'row', alignItems: 'center', gap: 12,
                      backgroundColor: colors.card, borderRadius: 12, padding: 14,
                      borderWidth: 2, borderColor: campaign.dateType === dt.id ? dt.color : colors.surface,
                    },
                    campaign.dateType === dt.id && { backgroundColor: `${dt.color}08` },
                  ]}
                  onPress={() => handleDateTypeSelect(dt.id)}
                  data-testid={`date-type-${dt.id}`}
                >
                  <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: `${dt.color}20`, alignItems: 'center', justifyContent: 'center' }}>
                    <Ionicons name={dt.icon as any} size={22} color={dt.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 17, fontWeight: '600', color: campaign.dateType === dt.id ? dt.color : colors.text }}>{dt.name}</Text>
                    <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 2 }}>{dt.description}</Text>
                  </View>
                  {campaign.dateType === dt.id && (
                    <Ionicons name="checkmark-circle" size={22} color={dt.color} />
                  )}
                </TouchableOpacity>
              ))}
            </View>
            {campaign.dateType && (
              <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: '#34C75910', borderRadius: 10, padding: 10, marginTop: 10, borderWidth: 1, borderColor: '#34C75920' }}>
                <Ionicons name="flash" size={16} color="#34C759" />
                <Text style={{ fontSize: 14, color: '#34C759', flex: 1, lineHeight: 17 }}>
                  Contacts with a {DATE_TYPES.find(d => d.id === campaign.dateType)?.name || 'date'} on file will be automatically enrolled in this campaign.
                </Text>
              </View>
            )}
          </View>
        )}
        
        {/* Delivery Mode */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Delivery Mode</Text>
          <Text style={styles.sectionDescription}>
            How should campaign messages be sent?
          </Text>
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 8 }}>
            <TouchableOpacity
              style={[styles.modeCard, campaign.deliveryMode === 'automated' && styles.modeCardActive]}
              onPress={() => setCampaign({ ...campaign, deliveryMode: 'automated' })}
              data-testid="delivery-mode-automated"
            >
              <Ionicons name="flash" size={24} color={campaign.deliveryMode === 'automated' ? '#34C759' : colors.textSecondary} />
              <Text style={[styles.modeTitle, campaign.deliveryMode === 'automated' && { color: '#34C759' }]}>Automated</Text>
              <Text style={styles.modeDesc}>AI assistant sends & replies for you. Randomized between 10am-12pm.</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modeCard, campaign.deliveryMode === 'manual' && styles.modeCardActive]}
              onPress={() => setCampaign({ ...campaign, deliveryMode: 'manual' })}
              data-testid="delivery-mode-manual"
            >
              <Ionicons name="hand-left" size={24} color={campaign.deliveryMode === 'manual' ? '#007AFF' : colors.textSecondary} />
              <Text style={[styles.modeTitle, campaign.deliveryMode === 'manual' && { color: '#007AFF' }]}>Manual</Text>
              <Text style={styles.modeDesc}>Get notified when it's time. Review, personalize, then hit send.</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* AI Features Toggle */}
        <View style={styles.section}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <View style={{ flex: 1 }}>
              <Text style={styles.sectionTitle}>AI-Powered Messages</Text>
              <Text style={styles.sectionDescription}>
                AI generates personalized messages using your contact's activity history and your communication style
              </Text>
            </View>
            <TouchableOpacity
              style={[styles.toggleButton, campaign.aiEnabled && styles.toggleButtonActive]}
              onPress={() => setCampaign({ ...campaign, aiEnabled: !campaign.aiEnabled })}
              data-testid="ai-toggle"
            >
              <View style={[styles.toggleKnob, campaign.aiEnabled && styles.toggleKnobActive]} />
            </TouchableOpacity>
          </View>
          {campaign.aiEnabled && (
            <View style={styles.aiInfoBox}>
              <Ionicons name="sparkles" size={16} color="#FFD60A" />
              <Text style={styles.aiInfoText}>
                Each step can use AI to personalize messages based on the contact's history. Templates you write will be used as starting points.
              </Text>
            </View>
          )}
        </View>

        {/* Ownership Level (admin only) */}
        {user?.role === 'super_admin' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Campaign Level</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
              {[
                { key: 'user', label: 'Personal', icon: 'person' },
                { key: 'store', label: 'Store', icon: 'storefront' },
                { key: 'org', label: 'Organization', icon: 'business' },
              ].map(level => (
                <TouchableOpacity
                  key={level.key}
                  style={[styles.levelChip, campaign.ownershipLevel === level.key && styles.levelChipActive]}
                  onPress={() => setCampaign({ ...campaign, ownershipLevel: level.key as any })}
                  data-testid={`level-${level.key}`}
                >
                  <Ionicons name={level.icon as any} size={16} color={campaign.ownershipLevel === level.key ? '#FFF' : colors.textSecondary} />
                  <Text style={[styles.levelChipText, campaign.ownershipLevel === level.key && { color: colors.text }]}>{level.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {/* Message Sequence */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <View>
              <Text style={styles.sectionTitle}>Message Sequence</Text>
              <Text style={styles.sectionDescription}>
                {sequences.length} message{sequences.length > 1 ? 's' : ''} in this campaign
              </Text>
            </View>
            <TouchableOpacity style={styles.addStepButton} onPress={addSequenceStep}>
              <Ionicons name="add-circle" size={24} color="#007AFF" />
              <Text style={styles.addStepText}>Add</Text>
            </TouchableOpacity>
          </View>
          
          {sequences.map((step, index) => (
            <View key={step.id} style={styles.sequenceCard}>
              <View style={styles.sequenceHeader}>
                <View style={styles.stepBadge}>
                  <Text style={styles.stepNumber}>{index + 1}</Text>
                </View>
                <Text style={styles.stepDelay}>{getDelayLabel(step, index)}</Text>
                {sequences.length > 1 && (
                  <TouchableOpacity 
                    style={styles.removeStepButton}
                    onPress={() => removeSequenceStep(step.id)}
                  >
                    <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                  </TouchableOpacity>
                )}
              </View>
              
              {/* Delay Controls — shown for ALL steps including step 1 */}
              {/* Delay controls — preset chips + compact custom fields, ABSOLUTE from enrollment */}
              {(() => {
                const isFirstStep = index === 0;
                const PRESETS = isFirstStep
                  ? [{ label: 'Now', mo: 0, d: 0, h: 0, m: 0 }, { label: '15 min', mo: 0, d: 0, h: 0, m: 15 }, { label: '30 min', mo: 0, d: 0, h: 0, m: 30 }, { label: '1 hr', mo: 0, d: 0, h: 1, m: 0 }, { label: '1 day', mo: 0, d: 1, h: 0, m: 0 }]
                  : [{ label: '15 min', mo: 0, d: 0, h: 0, m: 15 }, { label: '30 min', mo: 0, d: 0, h: 0, m: 30 }, { label: '1 hr', mo: 0, d: 0, h: 1, m: 0 }, { label: '1 day', mo: 0, d: 1, h: 0, m: 0 }, { label: '3 days', mo: 0, d: 3, h: 0, m: 0 }, { label: '1 week', mo: 0, d: 7, h: 0, m: 0 }, { label: '2 weeks', mo: 0, d: 14, h: 0, m: 0 }, { label: '1 month', mo: 1, d: 0, h: 0, m: 0 }, { label: '3 months', mo: 3, d: 0, h: 0, m: 0 }, { label: '6 months', mo: 6, d: 0, h: 0, m: 0 }, { label: '1 year', mo: 12, d: 0, h: 0, m: 0 }];
                const activePreset = PRESETS.find(p => p.mo === step.delayMonths && p.d === step.delayDays && p.h === step.delayHours && p.m === (step.delayMinutes || 0));
                const apply = (p: typeof PRESETS[0]) => { updateSequenceStep(step.id, 'delayMonths', p.mo); updateSequenceStep(step.id, 'delayDays', p.d); updateSequenceStep(step.id, 'delayHours', p.h); updateSequenceStep(step.id, 'delayMinutes', p.m); };
                return (
                  <View style={{ marginBottom: 10 }}>
                    <Text style={[styles.delayLabel, { marginBottom: 6 }]}>
                      {isFirstStep ? 'From enrollment' : 'From enrollment date'}
                    </Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
                      <View style={{ flexDirection: 'row', gap: 6 }}>
                        {PRESETS.map(p => (
                          <TouchableOpacity key={p.label} onPress={() => apply(p)}
                            style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: activePreset?.label === p.label ? '#C9A962' : colors.surface, borderWidth: 1, borderColor: activePreset?.label === p.label ? '#C9A962' : colors.borderLight }}>
                            <Text style={{ fontSize: 13, fontWeight: activePreset?.label === p.label ? '700' : '500', color: activePreset?.label === p.label ? '#000' : colors.text }}>{p.label}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </ScrollView>
                    <View style={{ flexDirection: 'row', gap: 6 }}>
                      {[{ key: 'delayMonths', label: 'Mo', max: 24 }, { key: 'delayDays', label: 'Days', max: 365 }, { key: 'delayHours', label: 'Hrs', max: 23 }, { key: 'delayMinutes', label: 'Min', max: 59 }].map(({ key, label, max }) => (
                        <View key={key} style={{ flex: 1, alignItems: 'center' }}>
                          <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 3, fontWeight: '600' }}>{label}</Text>
                          <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, borderRadius: 8, borderWidth: 1, borderColor: colors.borderLight, overflow: 'hidden' }}>
                            <TouchableOpacity style={{ padding: 6 }} onPress={() => updateSequenceStep(step.id, key, Math.max(0, ((step as any)[key] ?? 0) - 1))}>
                              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '700' }}>−</Text>
                            </TouchableOpacity>
                            <Text style={{ fontSize: 13, color: colors.text, fontWeight: '700', minWidth: 20, textAlign: 'center' }}>{(step as any)[key] ?? 0}</Text>
                            <TouchableOpacity style={{ padding: 6 }} onPress={() => updateSequenceStep(step.id, key, Math.min(max, ((step as any)[key] ?? 0) + 1))}>
                              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '700' }}>+</Text>
                            </TouchableOpacity>
                          </View>
                        </View>
                      ))}
                    </View>
                  </View>
                );
              })()}
              
              {/* Channel + AI per step */}
              <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10 }}>
                {/* Channel selector */}
                {['sms', 'email'].map(ch => (
                  <TouchableOpacity
                    key={ch}
                    style={[
                      { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: colors.surface },
                      step.channel === ch && { backgroundColor: '#007AFF' },
                    ]}
                    onPress={() => updateSequenceStep(step.id, 'channel', ch)}
                  >
                    <Ionicons name={ch === 'sms' ? 'chatbubble' : 'mail'} size={14} color={step.channel === ch ? '#FFF' : colors.textSecondary} />
                    <Text style={{ fontSize: 14, fontWeight: '600', color: step.channel === ch ? '#FFF' : colors.textSecondary }}>
                      {ch === 'sms' ? 'SMS' : 'Email'}
                    </Text>
                  </TouchableOpacity>
                ))}
                {/* AI toggle per step */}
                {campaign.aiEnabled && (
                  <TouchableOpacity
                    style={[
                      { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: colors.surface, marginLeft: 'auto' },
                      step.ai_generated && { backgroundColor: '#FFD60A20', borderWidth: 1, borderColor: '#FFD60A50' },
                    ]}
                    onPress={() => updateSequenceStep(step.id, 'ai_generated', !step.ai_generated)}
                  >
                    <Ionicons name="sparkles" size={14} color={step.ai_generated ? '#FFD60A' : colors.textSecondary} />
                    <Text style={{ fontSize: 14, fontWeight: '600', color: step.ai_generated ? '#FFD60A' : colors.textSecondary }}>
                      {step.ai_generated ? 'AI On' : 'AI Off'}
                    </Text>
                  </TouchableOpacity>
                )}
              </View>

              {/* AI context hint */}
              {campaign.aiEnabled && step.ai_generated && (
                <TextInput
                  style={[styles.messageInput, { minHeight: 40, marginBottom: 6 }]}
                  placeholder="AI context: e.g. 'Thank them for the purchase, mention their vehicle'"
                  placeholderTextColor="#6E6E73"
                  value={step.step_context}
                  onChangeText={(text) => updateSequenceStep(step.id, 'step_context', text)}
                />
              )}

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
                placeholder="Enter your message... Use the Personalize button above"
                placeholderTextColor={colors.textSecondary}
                value={step.message}
                onChangeText={(text) => updateSequenceStep(step.id, 'message', text)}
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />
              <Text style={styles.charCount}>{step.message.length} / 500</Text>
              
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
            </View>
          ))}
          
          <View style={styles.variableHint}>
            <Ionicons name="information-circle" size={16} color={colors.textSecondary} />
            <Text style={styles.variableHintText}>
              Use {'{name}'} and {'{vehicle}'} for personalization
            </Text>
          </View>
        </View>
        
        {/* Send Time */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Send Time</Text>
          <TouchableOpacity 
            style={styles.timePickerButton}
            onPress={() => setShowTimePicker(true)}
          >
            <Ionicons name="time-outline" size={24} color="#007AFF" />
            <Text style={styles.timeText}>{format(campaign.sendTime, 'h:mm a')}</Text>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
          <Text style={styles.timeHint}>Messages will be sent at this time in the contact's timezone</Text>
        </View>
        
        {showTimePicker && (
          Platform.OS === 'ios' ? (
            <WebModal transparent animationType="slide">
              <View style={styles.pickerModal}>
                <View style={styles.pickerContainer}>
                  <View style={styles.pickerHeader}>
                    <TouchableOpacity onPress={() => setShowTimePicker(false)}>
                      <Text style={styles.pickerCancel}>Cancel</Text>
                    </TouchableOpacity>
                    <Text style={styles.pickerTitle}>Select Time</Text>
                    <TouchableOpacity onPress={() => setShowTimePicker(false)}>
                      <Text style={styles.pickerDone}>Done</Text>
                    </TouchableOpacity>
                  </View>
                  <DateTimePicker
                    value={campaign.sendTime}
                    mode="time"
                    display="spinner"
                    onChange={handleTimeChange}
                    style={styles.timePicker}
                    textColor="#FFF"
                  />
                </View>
              </View>
            </WebModal>
          ) : (
            <DateTimePicker
              value={campaign.sendTime}
              mode="time"
              display="default"
              onChange={handleTimeChange}
            />
          )
        )}
        
        {/* Active Toggle */}
        <View style={styles.section}>
          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Active Campaign</Text>
              <Text style={styles.toggleDescription}>
                Start sending messages when contacts are tagged
              </Text>
            </View>
            <Switch
              value={campaign.active}
              onValueChange={(value) => setCampaign({ ...campaign, active: value })}
              trackColor={{ false: colors.borderLight, true: '#34C759' }}
              thumbColor="#FFF"
            />
          </View>
        </View>
        
        {/* Preview */}
        <View style={styles.previewSection}>
          <Text style={styles.previewTitle}>Campaign Preview</Text>
          <View style={styles.timeline}>
            {sequences.map((step, index) => {
              let timeLabel = 'Day 1';
              if (index > 0) {
                const totalDays = step.delayDays + (step.delayMonths * 30);
                if (step.delayMonths > 0) {
                  timeLabel = `Month ${step.delayMonths}${step.delayDays > 0 ? ` + ${step.delayDays}d` : ''}`;
                } else if (step.delayDays > 0) {
                  timeLabel = `Day ${step.delayDays}`;
                }
              }
              
              return (
                <View key={step.id} style={styles.timelineItem}>
                  <View style={styles.timelineDot} />
                  {index < sequences.length - 1 && <View style={styles.timelineLine} />}
                  <View style={styles.timelineContent}>
                    <Text style={styles.timelineTime}>{timeLabel}</Text>
                    <Text style={styles.timelineMessage} numberOfLines={2}>
                      {step.message || 'Empty message'}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>
        </View>
        
        {/* Compliance Notice */}
        <View style={styles.complianceNotice}>
          <Ionicons name="shield-checkmark" size={20} color="#34C759" />
          <Text style={styles.complianceText}>
            All messages respect quiet hours (9pm-9am) and opt-out preferences. Contacts can reply STOP at any time.
          </Text>
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
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  saveButton: {
    backgroundColor: '#007AFF',
    borderRadius: 18,
    paddingHorizontal: 16,
    paddingVertical: 8,
    minHeight: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveButtonText: {
    fontSize: 17,
    fontWeight: '700',
    color: '#FFF',
  },
  scrollContent: {
    padding: 16,
  },
  section: {
    marginBottom: 28,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionDescription: {
    fontSize: 16,
    color: colors.textSecondary,
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
  typeScroll: {
    marginHorizontal: -16,
    paddingHorizontal: 16,
  },
  typeCard: {
    width: 140,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginRight: 12,
    borderWidth: 2,
    borderColor: colors.surface,
  },
  typeIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  typeName: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  typeDesc: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  tagGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tagButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 20,
    paddingVertical: 10,
    paddingHorizontal: 16,
    gap: 6,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  tagButtonActive: {
    backgroundColor: '#007AFF20',
    borderColor: '#007AFF',
  },
  tagButtonText: {
    fontSize: 16,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  tagButtonTextActive: {
    color: '#007AFF',
  },
  addStepButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  addStepText: {
    fontSize: 17,
    color: '#007AFF',
    fontWeight: '600',
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
  },
  stepBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  stepNumber: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  stepDelay: {
    flex: 1,
    fontSize: 16,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  removeStepButton: {
    padding: 4,
  },
  delayRow: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 12,
  },
  delayInput: {
    flex: 1,
  },
  delayLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 6,
    textAlign: 'center',
  },
  delayControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 4,
  },
  delayButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  delayValue: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
    width: 40,
    textAlign: 'center',
  },
  messageInput: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 12,
    fontSize: 17,
    color: colors.text,
    minHeight: 80,
  },
  charCount: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'right',
    marginTop: 4,
  },
  variableHint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
  },
  variableHintText: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  timePickerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  timeText: {
    flex: 1,
    fontSize: 18,
    color: colors.text,
    fontWeight: '500',
  },
  timeHint: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 8,
  },
  pickerModal: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  pickerContainer: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingBottom: 34,
  },
  pickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  pickerCancel: {
    fontSize: 18,
    color: colors.textSecondary,
  },
  pickerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  pickerDone: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
  timePicker: {
    height: 200,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  toggleInfo: {
    flex: 1,
    marginRight: 16,
  },
  toggleLabel: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  toggleDescription: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  previewSection: {
    marginBottom: 24,
  },
  previewTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 16,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  timeline: {
    paddingLeft: 8,
  },
  timelineItem: {
    flexDirection: 'row',
    marginBottom: 0,
  },
  timelineDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#007AFF',
    marginTop: 4,
  },
  timelineLine: {
    position: 'absolute',
    left: 5,
    top: 16,
    width: 2,
    height: '100%',
    backgroundColor: colors.surface,
  },
  timelineContent: {
    flex: 1,
    marginLeft: 16,
    paddingBottom: 20,
  },
  timelineTime: {
    fontSize: 15,
    fontWeight: '600',
    color: '#007AFF',
    marginBottom: 4,
  },
  timelineMessage: {
    fontSize: 16,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  complianceNotice: {
    flexDirection: 'row',
    backgroundColor: '#34C75915',
    borderRadius: 12,
    padding: 16,
    gap: 12,
    alignItems: 'flex-start',
  },
  complianceText: {
    flex: 1,
    fontSize: 15,
    color: '#34C759',
    lineHeight: 18,
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
  // Delivery mode cards
  modeCard: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 14,
    alignItems: 'center',
    gap: 6,
    borderWidth: 1.5,
    borderColor: colors.surface,
  },
  modeCardActive: {
    borderColor: '#007AFF50',
    backgroundColor: '#007AFF08',
  },
  modeTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  modeDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 15,
  },
  // Toggle switch
  toggleButton: {
    width: 48,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.borderLight,
    justifyContent: 'center',
    paddingHorizontal: 2,
  },
  toggleButtonActive: {
    backgroundColor: '#34C759',
  },
  toggleKnob: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.card,
  },
  toggleKnobActive: {
    alignSelf: 'flex-end',
  },
  // AI info box
  aiInfoBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#FFD60A10',
    borderRadius: 10,
    padding: 10,
    marginTop: 10,
    borderWidth: 1,
    borderColor: '#FFD60A20',
  },
  aiInfoText: {
    fontSize: 14,
    color: colors.border,
    flex: 1,
    lineHeight: 17,
  },
  // Level chips
  levelChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 18,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  levelChipActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  levelChipText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  // Template picker styles
  templateCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  templateIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  templateName: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  templateDesc: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: 3,
  },
  templateMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 8,
  },
  templateMetaChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    backgroundColor: colors.surface,
  },
  templateMetaText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
});
