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
  Alert,
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
import { useToast } from '../components/common/Toast';

interface SequenceStep {
  id: string;
  message: string;
  delayDays: number;
  delayMonths: number;
  media_urls: string[];
}

export default function CampaignBuilderScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
const { showToast } = useToast();
    const [campaign, setCampaign] = useState({
    name: '',
    type: 'check_in' as 'birthday' | 'anniversary' | 'check_in' | 'sold_followup' | 'custom',
    triggerTag: '',
    selectedTags: [] as string[],
    active: true,
    sendTime: new Date(new Date().setHours(10, 0, 0, 0)),
  });
  
  const [sequences, setSequences] = useState<SequenceStep[]>([
    { id: '1', message: '', delayDays: 0, delayMonths: 0, media_urls: [] },
  ]);
  
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploadingMedia, setUploadingMedia] = useState<string | null>(null);
  
  const availableTags = ['sold', 'lead', 'hot', 'customer', 'lease_end', 'service_due', 'referral', 'vip'];
  
  const campaignTypes = [
    { id: 'sold_followup', name: 'Sold Follow-up', icon: 'car', color: '#34C759', description: 'Check in with customers after purchase' },
    { id: 'birthday', name: 'Birthday', icon: 'gift', color: '#FF9500', description: 'Wish them happy birthday' },
    { id: 'anniversary', name: 'Anniversary', icon: 'heart', color: '#FF3B30', description: 'Celebrate purchase anniversary' },
    { id: 'check_in', name: 'Check-in', icon: 'chatbubble', color: '#007AFF', description: 'Regular touchpoints' },
    { id: 'custom', name: 'Custom', icon: 'create', color: '#8E8E93', description: 'Build your own' },
  ];
  
  const soldFollowupTemplates: SequenceStep[] = [
    { id: '1', message: "Hey {name}! Just wanted to check in - how are you enjoying your new {vehicle}? Let me know if you have any questions!", delayDays: 3, delayMonths: 0, media_urls: [] },
    { id: '2', message: "Hi {name}! It's been about a month with your {vehicle}. Everything running smoothly? I'm here if you need anything!", delayDays: 0, delayMonths: 1, media_urls: [] },
    { id: '3', message: "Hey {name}! Quick check-in at the 3 month mark. How's the {vehicle} treating you? Don't forget to schedule your first service if you haven't already!", delayDays: 0, delayMonths: 3, media_urls: [] },
    { id: '4', message: "Happy 6 months with your {vehicle}, {name}! Hope you're still loving it. Let me know if there's anything I can help with!", delayDays: 0, delayMonths: 6, media_urls: [] },
    { id: '5', message: "Can you believe it's been a year, {name}?! Time flies! How's the {vehicle}? If you know anyone looking for a great deal, send them my way!", delayDays: 0, delayMonths: 12, media_urls: [] },
  ];
  
  const handleTypeSelect = (type: typeof campaign.type) => {
    setCampaign({ ...campaign, type });
    
    // Pre-fill sequences for sold follow-up
    if (type === 'sold_followup') {
      setSequences(soldFollowupTemplates);
      setCampaign(prev => ({ ...prev, type, triggerTag: 'sold' }));
    } else if (type === 'birthday') {
      setSequences([{ id: '1', message: "Happy birthday, {name}! Hope you have an amazing day! If there's anything I can do for you, just let me know.", delayDays: 0, delayMonths: 0, media_urls: [] }]);
    } else if (type === 'anniversary') {
      setSequences([{ id: '1', message: "Happy anniversary on your {vehicle} purchase, {name}! Can you believe it's been a year? Hope it's still treating you well!", delayDays: 0, delayMonths: 0, media_urls: [] }]);
    } else {
      setSequences([{ id: '1', message: '', delayDays: 0, delayMonths: 0, media_urls: [] }]);
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
        delayDays: 0, 
        delayMonths: lastStep.delayMonths + 1,
        media_urls: [],
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
        Alert.alert('Permission Required', 'Please allow access to your photo library to attach media.');
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
      Alert.alert('Error', 'Failed to select image. Please try again.');
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
    if (index === 0) return 'Immediately when tagged';
    
    const parts = [];
    if (step.delayMonths > 0) {
      parts.push(`${step.delayMonths} month${step.delayMonths > 1 ? 's' : ''}`);
    }
    if (step.delayDays > 0) {
      parts.push(`${step.delayDays} day${step.delayDays > 1 ? 's' : ''}`);
    }
    
    return parts.length > 0 ? `After ${parts.join(' and ')}` : 'Same day';
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
      Alert.alert('Error', 'Please enter a campaign name');
      return;
    }
    
    if (sequences.some(s => !s.message.trim())) {
      Alert.alert('Error', 'Please fill in all message templates');
      return;
    }
    
    if (campaign.selectedTags.length === 0 && !campaign.triggerTag) {
      Alert.alert('Error', 'Please select at least one tag to target');
      return;
    }
    
    if (!user) {
      Alert.alert('Error', 'Please log in to create campaigns');
      return;
    }
    
    try {
      setSaving(true);
      
      const campaignData = {
        name: campaign.name,
        type: campaign.type,
        trigger_tag: campaign.triggerTag || campaign.selectedTags[0],
        segment_tags: campaign.selectedTags,
        sequences: sequences.map((s, index) => ({
          step: index + 1,
          message_template: s.message,
          delay_days: s.delayDays,
          delay_months: s.delayMonths,
          media_urls: s.media_urls,
        })),
        send_time: format(campaign.sendTime, 'HH:mm'),
        active: campaign.active,
      };
      
      await campaignsAPI.create(user._id, campaignData);
      
      Alert.alert('Success', `Campaign created with ${sequences.length} message${sequences.length > 1 ? 's' : ''} in sequence!`, [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Failed to create campaign';
      Alert.alert('Error', errorMessage);
      console.error('Create campaign error:', error);
    } finally {
      setSaving(false);
    }
  };
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="close" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.headerTitle}>New Campaign</Text>
        
        <TouchableOpacity onPress={handleSave} style={styles.saveButton} disabled={saving}>
          {saving ? (
            <ActivityIndicator size="small" color="#007AFF" />
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
            placeholderTextColor="#8E8E93"
            value={campaign.name}
            onChangeText={(text) => setCampaign({ ...campaign, name: text })}
          />
        </View>
        
        {/* Campaign Type */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Campaign Type</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.typeScroll}>
            {campaignTypes.map((type) => (
              <TouchableOpacity
                key={type.id}
                style={[
                  styles.typeCard,
                  campaign.type === type.id && { borderColor: type.color, backgroundColor: `${type.color}15` },
                ]}
                onPress={() => handleTypeSelect(type.id as any)}
              >
                <View style={[styles.typeIconContainer, { backgroundColor: `${type.color}20` }]}>
                  <Ionicons
                    name={type.icon as any}
                    size={24}
                    color={type.color}
                  />
                </View>
                <Text style={[styles.typeName, campaign.type === type.id && { color: type.color }]}>
                  {type.name}
                </Text>
                <Text style={styles.typeDesc} numberOfLines={2}>{type.description}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
        
        {/* Trigger Tag */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Trigger Tag</Text>
          <Text style={styles.sectionDescription}>
            Campaign starts when a contact gets this tag
          </Text>
          <View style={styles.tagGrid}>
            {availableTags.map((tag) => (
              <TouchableOpacity
                key={tag}
                style={[
                  styles.tagButton,
                  campaign.triggerTag === tag && styles.tagButtonActive,
                ]}
                onPress={() => setCampaign({ ...campaign, triggerTag: tag })}
              >
                <Text
                  style={[
                    styles.tagButtonText,
                    campaign.triggerTag === tag && styles.tagButtonTextActive,
                  ]}
                >
                  {tag}
                </Text>
                {campaign.triggerTag === tag && (
                  <Ionicons name="checkmark-circle" size={16} color="#007AFF" />
                )}
              </TouchableOpacity>
            ))}
          </View>
        </View>
        
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
              
              {index > 0 && (
                <View style={styles.delayRow}>
                  <View style={styles.delayInput}>
                    <Text style={styles.delayLabel}>Months</Text>
                    <View style={styles.delayControls}>
                      <TouchableOpacity 
                        style={styles.delayButton}
                        onPress={() => updateSequenceStep(step.id, 'delayMonths', Math.max(0, step.delayMonths - 1))}
                      >
                        <Ionicons name="remove" size={18} color="#FFF" />
                      </TouchableOpacity>
                      <Text style={styles.delayValue}>{step.delayMonths}</Text>
                      <TouchableOpacity 
                        style={styles.delayButton}
                        onPress={() => updateSequenceStep(step.id, 'delayMonths', step.delayMonths + 1)}
                      >
                        <Ionicons name="add" size={18} color="#FFF" />
                      </TouchableOpacity>
                    </View>
                  </View>
                  
                  <View style={styles.delayInput}>
                    <Text style={styles.delayLabel}>Days</Text>
                    <View style={styles.delayControls}>
                      <TouchableOpacity 
                        style={styles.delayButton}
                        onPress={() => updateSequenceStep(step.id, 'delayDays', Math.max(0, step.delayDays - 1))}
                      >
                        <Ionicons name="remove" size={18} color="#FFF" />
                      </TouchableOpacity>
                      <Text style={styles.delayValue}>{step.delayDays}</Text>
                      <TouchableOpacity 
                        style={styles.delayButton}
                        onPress={() => updateSequenceStep(step.id, 'delayDays', step.delayDays + 1)}
                      >
                        <Ionicons name="add" size={18} color="#FFF" />
                      </TouchableOpacity>
                    </View>
                  </View>
                </View>
              )}
              
              <TextInput
                style={styles.messageInput}
                placeholder="Enter your message..."
                placeholderTextColor="#8E8E93"
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
            <Ionicons name="information-circle" size={16} color="#8E8E93" />
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
            <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
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
              trackColor={{ false: '#3A3A3C', true: '#34C759' }}
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
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionDescription: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 12,
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
  typeScroll: {
    marginHorizontal: -16,
    paddingHorizontal: 16,
  },
  typeCard: {
    width: 140,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginRight: 12,
    borderWidth: 2,
    borderColor: '#2C2C2E',
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
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  typeDesc: {
    fontSize: 12,
    color: '#8E8E93',
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
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
    paddingVertical: 10,
    paddingHorizontal: 16,
    gap: 6,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  tagButtonActive: {
    backgroundColor: '#007AFF20',
    borderColor: '#007AFF',
  },
  tagButtonText: {
    fontSize: 14,
    color: '#8E8E93',
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
    fontSize: 15,
    color: '#007AFF',
    fontWeight: '600',
  },
  sequenceCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
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
    fontSize: 14,
    fontWeight: '700',
    color: '#FFF',
  },
  stepDelay: {
    flex: 1,
    fontSize: 14,
    color: '#8E8E93',
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
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 6,
    textAlign: 'center',
  },
  delayControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
    padding: 4,
  },
  delayButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#3A3A3C',
    alignItems: 'center',
    justifyContent: 'center',
  },
  delayValue: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    width: 40,
    textAlign: 'center',
  },
  messageInput: {
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    color: '#FFF',
    minHeight: 80,
  },
  charCount: {
    fontSize: 11,
    color: '#8E8E93',
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
    fontSize: 13,
    color: '#8E8E93',
  },
  timePickerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  timeText: {
    flex: 1,
    fontSize: 17,
    color: '#FFF',
    fontWeight: '500',
  },
  timeHint: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 8,
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
    paddingBottom: 34,
  },
  pickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  pickerCancel: {
    fontSize: 17,
    color: '#8E8E93',
  },
  pickerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  pickerDone: {
    fontSize: 17,
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
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
  },
  toggleInfo: {
    flex: 1,
    marginRight: 16,
  },
  toggleLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  toggleDescription: {
    fontSize: 13,
    color: '#8E8E93',
  },
  previewSection: {
    marginBottom: 24,
  },
  previewTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
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
    backgroundColor: '#2C2C2E',
  },
  timelineContent: {
    flex: 1,
    marginLeft: 16,
    paddingBottom: 20,
  },
  timelineTime: {
    fontSize: 13,
    fontWeight: '600',
    color: '#007AFF',
    marginBottom: 4,
  },
  timelineMessage: {
    fontSize: 14,
    color: '#8E8E93',
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
    fontSize: 13,
    color: '#34C759',
    lineHeight: 18,
  },
  // Media attachment styles
  mediaSection: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  mediaLabel: {
    fontSize: 12,
    color: '#8E8E93',
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
    backgroundColor: '#000',
    borderRadius: 11,
  },
  addMediaButton: {
    width: 72,
    height: 72,
    borderRadius: 8,
    backgroundColor: '#2C2C2E',
    borderWidth: 1,
    borderColor: '#3A3A3C',
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
});
