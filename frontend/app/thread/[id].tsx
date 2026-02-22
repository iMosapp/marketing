import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
  Modal,
  ScrollView,
  Image,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { format } from 'date-fns';
import { Audio } from 'expo-av';
import * as ImagePicker from 'expo-image-picker';
import * as Haptics from 'expo-haptics';
import AISuggestion from '../../components/AISuggestion';
import { useAuthStore } from '../../store/authStore';
import { messagesAPI, templatesAPI } from '../../services/api';
import api from '../../services/api';

// Web platform detection
const IS_WEB = Platform.OS === 'web';

// Web-safe button component for toolbar
const WebToolButton: React.FC<{
  onPress: () => void;
  disabled?: boolean;
  testID?: string;
  isRecording?: boolean;
  children: React.ReactNode;
}> = ({ onPress, disabled, testID, isRecording, children }) => {
  if (IS_WEB) {
    return (
      <button
        type="button"
        onClick={onPress}
        disabled={disabled}
        data-testid={testID}
        style={{
          padding: 8,
          background: isRecording ? 'rgba(255, 59, 48, 0.2)' : 'none',
          border: 'none',
          borderRadius: 8,
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: disabled ? 0.5 : 1,
          WebkitTapHighlightColor: 'transparent',
        }}
      >
        {children}
      </button>
    );
  }
  return (
    <TouchableOpacity
      style={[{ padding: 8 }, isRecording && { backgroundColor: 'rgba(255, 59, 48, 0.2)', borderRadius: 8 }]}
      onPress={onPress}
      disabled={disabled}
      data-testid={testID}
    >
      {children}
    </TouchableOpacity>
  );
};

interface Message {
  _id: string;
  content: string;
  sender: 'user' | 'contact' | 'ai';
  timestamp: string;
  media_urls?: string[];
  has_media?: boolean;
  ai_generated?: boolean;
  intent_detected?: string;
}

interface ConversationInfo {
  contact_name: string;
  contact_phone: string;
  ai_enabled: boolean;
  ai_mode: string;
  status: string;
}

interface Template {
  _id: string;
  name: string;
  content: string;
  category?: string;
}

export default function ThreadScreen() {
  const router = useRouter();
  const { id, contact_name, contact_phone } = useLocalSearchParams();
  const user = useAuthStore((state) => state.user);
  const flatListRef = useRef<FlatList>(null);
  
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sending, setSending] = useState(false);
  const [aiMode, setAiMode] = useState<'auto_reply' | 'assisted' | 'draft_only' | 'off'>('assisted');
  const [showAISuggestion, setShowAISuggestion] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState({
    text: '',
    intent: '',
  });
  const [loadingAI, setLoadingAI] = useState(false);
  const [conversationStatus, setConversationStatus] = useState<'active' | 'closed'>('active');
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showReviewLinks, setShowReviewLinks] = useState(false);
  const [reviewLinks, setReviewLinks] = useState<Record<string, string>>({});
  const [customLinkName, setCustomLinkName] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedMedia, setSelectedMedia] = useState<{uri: string, type: string, name: string} | null>(null);
  const [sendingMedia, setSendingMedia] = useState(false);
  
  // Template tracking for analytics
  const [selectedTemplateInfo, setSelectedTemplateInfo] = useState<{
    template_id: string;
    template_type: string;
    template_name: string;
  } | null>(null);
  
  // Digital Business Card state
  const [showBusinessCard, setShowBusinessCard] = useState(false);
  const [showLandingPageOptions, setShowLandingPageOptions] = useState(false);
  const [campaigns, setCampaigns] = useState<{id: string, name: string, type: string}[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(null);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  
  // Congrats Card state
  const [showCongratsCardModal, setShowCongratsCardModal] = useState(false);
  const [congratsPhoto, setCongratsPhoto] = useState<{uri: string, type: string, name: string} | null>(null);
  const [congratsCustomerName, setCongratsCustomerName] = useState('');
  const [congratsCustomMessage, setCongratsCustomMessage] = useState('');
  const [creatingCongratsCard, setCreatingCongratsCard] = useState(false);

  // Load templates from API
  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    if (!user?._id) return;
    try {
      const data = await templatesAPI.getAll(user._id);
      setTemplates(data);
    } catch (error) {
      console.error('Error loading templates:', error);
      // Fallback to defaults if API fails
      setTemplates([
        { _id: '1', name: 'Greeting', content: 'Hi {name}! Thanks for reaching out. How can I help you today?' },
        { _id: '2', name: 'Follow Up', content: 'Hi {name}, I wanted to follow up on our conversation. Do you have any questions?' },
        { _id: '3', name: 'Appointment', content: 'Hi {name}, I\'d love to schedule a time to chat. What works best for you?' },
        { _id: '4', name: 'Thank You', content: 'Thank you so much for your time today, {name}! Please let me know if you need anything else.' },
        { _id: '5', name: 'Review Request', content: 'Hi {name}! If you had a great experience, we\'d really appreciate a review. Here\'s the link: ' },
      ]);
    }
  };

  // Load review links
  useEffect(() => {
    loadReviewLinks();
  }, []);

  // Keyboard shortcuts for web (power users)
  useEffect(() => {
    if (Platform.OS !== 'web') return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Enter to send
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        if (message.trim() && !sending) {
          handleSend();
        }
      }
      // Ctrl/Cmd + Shift + T to open templates (Shift avoids browser new tab)
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'T') {
        e.preventDefault();
        setShowTemplates(true);
        setShowAttachMenu(false);
      }
      // Ctrl/Cmd + Shift + R to open review links (Shift avoids browser refresh)
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'R') {
        e.preventDefault();
        setShowReviewLinks(true);
        setShowAttachMenu(false);
      }
      // Ctrl/Cmd + Shift + A to get AI suggestion
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'A') {
        if (aiMode !== 'off' && !loadingAI) {
          e.preventDefault();
          loadAISuggestion();
        }
      }
      // Escape to close modals
      if (e.key === 'Escape') {
        setShowTemplates(false);
        setShowReviewLinks(false);
        setShowAttachMenu(false);
        setShowSettings(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [message, sending, aiMode, loadingAI]);

  const loadReviewLinks = async () => {
    if (!user) return;
    try {
      const response = await messagesAPI.getReviewLinks(user._id);
      setReviewLinks(response.review_links || {});
      setCustomLinkName(response.custom_link_name || '');
    } catch (error) {
      console.log('No review links configured');
    }
  };
  
  const conversationId = id as string;
  const contactName = (contact_name as string) || 'Contact';
  const contactPhone = (contact_phone as string) || '';
  const [actualConversationId, setActualConversationId] = useState<string | null>(null);
  
  useEffect(() => {
    if (user?._id && id) {
      ensureConversation();
    }
  }, [id, user?._id]);
  
  // Ensure we have a conversation (create if needed)
  const ensureConversation = async () => {
    if (!id || !user?._id) return;
    
    try {
      // First try to load the thread directly (assuming id is a conversation id)
      const data = await messagesAPI.getThread(id as string);
      setMessages(data || []);
      setActualConversationId(id as string);
      
      if (data && data.length > 0 && data[data.length - 1].sender === 'contact' && aiMode !== 'off') {
        loadAISuggestion();
      }
    } catch (error) {
      // If that fails, id might be a contact_id - create/get conversation
      console.log('Thread not found, checking if this is a contact ID...');
      try {
        const response = await api.post(`/messages/conversations/${user._id}`, {
          contact_id: id,
          contact_phone: contactPhone,
        });
        const convId = response.data._id;
        setActualConversationId(convId);
        
        // Load messages for the conversation
        const msgs = await messagesAPI.getThread(convId);
        setMessages(msgs || []);
      } catch (err) {
        console.error('Failed to create/get conversation:', err);
        setMessages([]);
      }
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const convId = actualConversationId || id as string;
      const data = await messagesAPI.getThread(convId);
      setMessages(data || []);
    } catch (error) {
      console.error('Failed to refresh messages:', error);
    } finally {
      setRefreshing(false);
    }
  };
  
  const loadMessages = async () => {
    const convId = actualConversationId || id as string;
    if (!convId) return;
    
    try {
      setLoading(true);
      const data = await messagesAPI.getThread(convId);
      setMessages(data || []);
      
      // Auto-load AI suggestion when there are messages from contacts
      if (data && data.length > 0) {
        const lastMessage = data[data.length - 1];
        if (lastMessage.sender === 'contact' && aiMode !== 'off') {
          loadAISuggestion();
        }
      }
    } catch (error) {
      console.error('Failed to load messages:', error);
      // Show empty state if no messages
      setMessages([]);
    } finally {
      setLoading(false);
    }
  };
  
  const loadAISuggestion = async () => {
    if (!conversationId || aiMode === 'off') return;
    
    try {
      setLoadingAI(true);
      const data = await messagesAPI.getAISuggestion(conversationId);
      if (data?.suggestion) {
        setAiSuggestion({
          text: data.suggestion,
          intent: data.intent || '',
        });
        setShowAISuggestion(true);
      }
    } catch (error) {
      console.error('Failed to get AI suggestion:', error);
    } finally {
      setLoadingAI(false);
    }
  };
  
  const handleSend = async (textToSend?: string) => {
    const contentToSend = textToSend || message.trim();
    if (!contentToSend || !user) return;
    
    // Light haptic when sending message
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    try {
      setSending(true);
      
      // Optimistically add the message to the UI
      const optimisticMessage: Message = {
        _id: `temp_${Date.now()}`,
        content: contentToSend,
        sender: 'user',
        timestamp: new Date().toISOString(),
        ai_generated: false,
      };
      
      setMessages((prev) => [...prev, optimisticMessage]);
      setMessage('');
      setShowAISuggestion(false);
      
      // Scroll to bottom
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
      
      // Build message payload with template info if available
      const convId = actualConversationId || conversationId;
      const messagePayload: any = {
        conversation_id: convId,
        content: contentToSend,
      };
      
      // Include template tracking info if a template was used
      if (selectedTemplateInfo) {
        messagePayload.template_id = selectedTemplateInfo.template_id;
        messagePayload.template_type = selectedTemplateInfo.template_type;
        messagePayload.template_name = selectedTemplateInfo.template_name;
      }
      
      // Send to backend
      await messagesAPI.send(user._id, messagePayload);
      
      // Clear template info after sending
      setSelectedTemplateInfo(null);
      
      // Reload messages to get the real one from backend
      await loadMessages();
      
    } catch (error: any) {
      console.error('Failed to send message:', error);
      Alert.alert('Error', 'Failed to send message. Please try again.');
      // Remove optimistic message on error
      setMessages((prev) => prev.filter((m) => !m._id.startsWith('temp_')));
    } finally {
      setSending(false);
    }
  };
  
  const handleAcceptAISuggestion = () => {
    handleSend(aiSuggestion.text);
  };
  
  const handleEditAISuggestion = () => {
    setMessage(aiSuggestion.text);
    setShowAISuggestion(false);
  };

  const selectTemplate = (template: {_id: string; name: string; content: string; category?: string}) => {
    // Replace {name} with contact's first name
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    const content = template.content.replace(/{name}/g, firstName);
    setMessage(content);
    
    // Map template category to template_type for analytics
    const categoryToType: Record<string, string> = {
      'review_request': 'review',
      'review': 'review',
      'referral': 'referral',
      'sold': 'sold',
      'congratulations': 'sold',
      'greeting': 'greeting',
      'follow_up': 'follow_up',
      'appointment': 'appointment',
      'thank_you': 'thank_you',
    };
    
    const templateType = categoryToType[template.category || ''] || template.category || 'general';
    
    // Store template info for analytics tracking when message is sent
    setSelectedTemplateInfo({
      template_id: template._id,
      template_type: templateType,
      template_name: template.name,
    });
    
    setShowTemplates(false);
    setShowAttachMenu(false);
  };

  const handleAttachPhoto = () => {
    setShowAttachMenu(false);
    
    // On web, directly open image picker (no camera option)
    if (IS_WEB) {
      pickImage();
      return;
    }
    
    Alert.alert(
      'Add Photo',
      'Choose an option',
      [
        { text: 'Take Photo', onPress: takePhoto },
        { text: 'Choose from Library', onPress: pickImage },
        { text: 'Create Congrats Card', onPress: () => setShowCongratsCardModal(true) },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  const handleAttachVideo = () => {
    setShowAttachMenu(false);
    Alert.alert('Coming Soon', 'Video attachments will be available in a future update.');
  };

  const insertReviewLink = (platformId: string, url: string, platformName: string) => {
    const linkText = url;
    setMessage(prev => prev + (prev ? ' ' : '') + linkText);
    setShowReviewLinks(false);
    setShowAttachMenu(false);
  };

  // Digital Business Card functions
  const openBusinessCardPicker = async () => {
    if (!user?._id) return;
    
    setLoadingCampaigns(true);
    setShowBusinessCard(true);
    
    try {
      const response = await api.get(`/card/campaigns/${user._id}`);
      setCampaigns(response.data);
    } catch (error) {
      console.error('Error loading campaigns:', error);
      setCampaigns([]);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const sendBusinessCardLink = () => {
    if (!user?._id) return;
    
    // Haptic feedback for action
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    // Build the card URL - use the api baseURL and strip /api
    const baseUrl = api.defaults.baseURL?.replace('/api', '') || 'https://reports-analytics-1.preview.emergentagent.com';
    let cardUrl = `${baseUrl}/card/${user._id}`;
    
    // Add campaign and contact params for tracking
    const params = [];
    if (selectedCampaign) params.push(`campaign=${selectedCampaign}`);
    if (id) params.push(`contact=${id}`);
    if (params.length > 0) cardUrl += `?${params.join('&')}`;
    
    // Insert message with link
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    const cardMessage = `Hey ${firstName}! Here's my digital business card - save my contact info: ${cardUrl}`;
    
    // Close modals first, then set message
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    setSelectedCampaign(null);
    
    // Set message after a short delay to ensure modal is closed
    setTimeout(() => {
      setMessage(cardMessage);
    }, 100);
  };

  const sendVCardLink = () => {
    if (!user?._id) return;
    
    // Haptic feedback for action
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    // Build the vCard download URL
    const baseUrl = api.defaults.baseURL?.replace('/api', '') || 'https://reports-analytics-1.preview.emergentagent.com';
    const vcardUrl = `${baseUrl}/api/card/vcard/${user._id}`;
    
    // Insert message with link
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    const cardMessage = `Hey ${firstName}! Tap here to save my contact info directly to your phone: ${vcardUrl}`;
    
    // Close modals first
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    
    // Set message after a short delay to ensure modal is closed
    setTimeout(() => {
      setMessage(cardMessage);
    }, 100);
  };

  // Congrats Card Functions
  const pickCongratsPhoto = async () => {
    Alert.alert(
      'Add Customer Photo',
      'Choose an option',
      [
        {
          text: 'Take Photo',
          onPress: async () => {
            const { status } = await ImagePicker.requestCameraPermissionsAsync();
            if (status !== 'granted') {
              Alert.alert('Permission Denied', 'Camera access is required to take photos.');
              return;
            }
            const result = await ImagePicker.launchCameraAsync({
              allowsEditing: true,
              aspect: [1, 1],
              quality: 0.8,
            });
            if (!result.canceled && result.assets[0]) {
              const asset = result.assets[0];
              setCongratsPhoto({
                uri: asset.uri,
                type: asset.mimeType || 'image/jpeg',
                name: asset.fileName || 'photo.jpg',
              });
            }
          },
        },
        {
          text: 'Choose from Library',
          onPress: async () => {
            const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
            if (status !== 'granted') {
              Alert.alert('Permission Denied', 'Photo library access is required.');
              return;
            }
            const result = await ImagePicker.launchImageLibraryAsync({
              mediaTypes: ImagePicker.MediaTypeOptions.Images,
              allowsEditing: true,
              aspect: [1, 1],
              quality: 0.8,
            });
            if (!result.canceled && result.assets[0]) {
              const asset = result.assets[0];
              setCongratsPhoto({
                uri: asset.uri,
                type: asset.mimeType || 'image/jpeg',
                name: asset.fileName || 'image.jpg',
              });
            }
          },
        },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  const createCongratsCard = async () => {
    if (!congratsPhoto || !congratsCustomerName.trim() || !user?._id) {
      Alert.alert('Missing Info', 'Please add a photo and enter the customer name.');
      return;
    }

    // Premium haptic feedback on button press
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    setCreatingCongratsCard(true);
    try {
      const formData = new FormData();
      formData.append('salesman_id', user._id);
      formData.append('customer_name', congratsCustomerName.trim());
      formData.append('customer_phone', contact_phone as string || '');
      if (congratsCustomMessage.trim()) {
        formData.append('custom_message', congratsCustomMessage.trim());
      }
      formData.append('photo', {
        uri: congratsPhoto.uri,
        type: congratsPhoto.type,
        name: congratsPhoto.name,
      } as any);

      const response = await api.post('/congrats/create', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.success) {
        // Success haptic feedback - feels satisfying!
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        
        // Use short URL if available, otherwise fall back to full URL
        const cardUrl = response.data.short_url || response.data.card_url || 
          `${api.defaults.baseURL?.replace('/api', '')}/congrats/${response.data.card_id}`;
        
        // Insert message with short link
        const firstName = congratsCustomerName.split(' ')[0];
        const cardMessage = `Hey ${firstName}! 🎉 We made this special thank you card just for you: ${cardUrl}`;
        
        setMessage(cardMessage);
        
        // Reset state
        setShowCongratsCardModal(false);
        setCongratsPhoto(null);
        setCongratsCustomerName('');
        setCongratsCustomMessage('');
        
        Alert.alert('Card Created!', 'The congrats card link has been added to your message. Hit send to share it!');
      }
    } catch (error: any) {
      // Error haptic feedback
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      console.error('Error creating congrats card:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to create congrats card');
    } finally {
      setCreatingCongratsCard(false);
    }
  };

  const closeCongratsModal = () => {
    setShowCongratsCardModal(false);
    setCongratsPhoto(null);
    setCongratsCustomerName('');
    setCongratsCustomMessage('');
  };

  const handleVoiceToText = async () => {
    if (Platform.OS === 'web') {
      Alert.alert('Not Available', 'Voice-to-text is only available on mobile devices.');
      return;
    }
    
    try {
      if (isRecording) {
        // Stop recording and transcribe
        setIsRecording(false);
        
        if (recordingRef.current) {
          setTranscribing(true);
          
          await recordingRef.current.stopAndUnloadAsync();
          const uri = recordingRef.current.getURI();
          recordingRef.current = null;
          
          if (uri) {
            // Create form data to send to backend
            const formData = new FormData();
            formData.append('file', {
              uri,
              type: 'audio/m4a',
              name: 'recording.m4a',
            } as any);
            
            try {
              const response = await api.post('/voice/transcribe', formData, {
                headers: {
                  'Content-Type': 'multipart/form-data',
                },
              });
              
              if (response.data.success && response.data.text) {
                // Append transcribed text to message
                setMessage(prev => prev ? `${prev} ${response.data.text}` : response.data.text);
              } else if (response.data.success && !response.data.text) {
                // Empty transcription (silence) - no error, just don't add anything
                // Could optionally show a toast: "No speech detected"
              } else {
                Alert.alert('Transcription Error', response.data.error || 'Failed to transcribe audio');
              }
            } catch (error: any) {
              console.error('Transcription error:', error);
              Alert.alert('Error', 'Failed to transcribe audio. Please try again.');
            }
          }
          
          setTranscribing(false);
        }
      } else {
        // Start recording
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permission Denied', 'Microphone permission is required for voice recording.');
          return;
        }
        
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
        });
        
        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
        await recording.startAsync();
        
        recordingRef.current = recording;
        setIsRecording(true);
      }
    } catch (error) {
      console.error('Recording error:', error);
      setIsRecording(false);
      setTranscribing(false);
      Alert.alert('Error', 'Failed to record audio. Please try again.');
    }
  };
  
  const pickImage = async () => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Photo library access is required to send images.');
        return;
      }
      
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        quality: 0.8,
      });
      
      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        setSelectedMedia({
          uri: asset.uri,
          type: asset.mimeType || 'image/jpeg',
          name: asset.fileName || 'image.jpg',
        });
      }
    } catch (error) {
      console.error('Image picker error:', error);
      Alert.alert('Error', 'Failed to select image');
    }
  };
  
  const takePhoto = async () => {
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Camera access is required to take photos.');
        return;
      }
      
      const result = await ImagePicker.launchCameraAsync({
        allowsEditing: true,
        quality: 0.8,
      });
      
      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        setSelectedMedia({
          uri: asset.uri,
          type: asset.mimeType || 'image/jpeg',
          name: asset.fileName || 'photo.jpg',
        });
      }
    } catch (error) {
      console.error('Camera error:', error);
      Alert.alert('Error', 'Failed to take photo');
    }
  };
  
  const sendMMS = async () => {
    const convId = actualConversationId || id as string;
    if (!selectedMedia || !user?._id || !convId) {
      Alert.alert('Error', 'Unable to send - missing required data');
      return;
    }
    
    setSendingMedia(true);
    try {
      const formData = new FormData();
      formData.append('content', message || '');
      formData.append('media', {
        uri: selectedMedia.uri,
        type: selectedMedia.type,
        name: selectedMedia.name,
      } as any);
      
      const response = await api.post(
        `/messages/send-mms/${user._id}/${convId}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      
      // Add message to list
      setMessages(prev => [...prev, {
        _id: response.data._id,
        content: message,
        sender: 'user',
        timestamp: new Date().toISOString(),
        media_urls: response.data.media_urls,
        has_media: true,
      }]);
      
      setMessage('');
      setSelectedMedia(null);
      
      // Show success or warning
      if (response.data.status === 'sent') {
        // Success - no alert needed
      } else if (response.data.status === 'failed') {
        Alert.alert('Delivery Issue', 'Message saved but delivery failed: ' + (response.data.error || 'Unknown error'));
      }
    } catch (error: any) {
      console.error('MMS send error:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to send MMS';
      Alert.alert('Error', errorMsg);
    } finally {
      setSendingMedia(false);
    }
  };
  
  const clearSelectedMedia = () => {
    setSelectedMedia(null);
  };
  
  const toggleConversationStatus = () => {
    const newStatus = conversationStatus === 'active' ? 'closed' : 'active';
    setConversationStatus(newStatus);
    Alert.alert(
      'Conversation ' + (newStatus === 'closed' ? 'Closed' : 'Reopened'),
      newStatus === 'closed'
        ? 'This conversation has been marked as complete.'
        : 'This conversation is now active again.'
    );
  };
  
  const toggleAIMode = () => {
    const modes: Array<'auto_reply' | 'assisted' | 'draft_only' | 'off'> = [
      'auto_reply',
      'assisted',
      'draft_only',
      'off',
    ];
    const currentIndex = modes.indexOf(aiMode);
    const nextMode = modes[(currentIndex + 1) % modes.length];
    setAiMode(nextMode);
    
    // Hide AI suggestion if turning off
    if (nextMode === 'off') {
      setShowAISuggestion(false);
    } else if (messages.length > 0) {
      // Load AI suggestion when turning on
      loadAISuggestion();
    }
  };
  
  const getAIModeLabel = () => {
    switch (aiMode) {
      case 'auto_reply':
        return 'AI: Auto-Reply';
      case 'assisted':
        return 'AI: Assisted';
      case 'draft_only':
        return 'AI: Drafts Only';
      case 'off':
        return 'AI: Off';
      default:
        return 'AI Mode';
    }
  };
  
  const getAIModeColor = () => {
    switch (aiMode) {
      case 'auto_reply':
        return '#34C759';
      case 'assisted':
        return '#007AFF';
      case 'draft_only':
        return '#8E8E93';
      case 'off':
        return '#FF3B30';
    }
  };
  
  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.sender === 'user' || item.sender === 'ai';
    const timestamp = item.timestamp ? new Date(item.timestamp) : new Date();
    const hasMedia = item.has_media && item.media_urls && item.media_urls.length > 0;
    
    return (
      <View
        style={[
          styles.messageContainer,
          isUser ? styles.userMessageContainer : styles.contactMessageContainer,
        ]}
      >
        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userMessageBubble : styles.contactMessageBubble,
          ]}
        >
          {item.ai_generated && (
            <View style={styles.aiIndicator}>
              <Ionicons name="sparkles" size={12} color="#34C759" />
              <Text style={styles.aiIndicatorText}>AI sent this</Text>
            </View>
          )}
          
          {/* Render attached images */}
          {hasMedia && (
            <View style={styles.mediaContainer}>
              {item.media_urls?.map((url, index) => (
                <View key={index} style={styles.mediaImageWrapper}>
                  <Image 
                    source={{ uri: url }} 
                    style={styles.mediaImage}
                    resizeMode="cover"
                    defaultSource={{ uri: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==' }}
                  />
                </View>
              ))}
            </View>
          )}
          
          {/* Show image icon if media exists but no text content */}
          {hasMedia && !item.content && (
            <View style={styles.mediaOnlyIndicator}>
              <Ionicons name="image" size={14} color={isUser ? "#fff" : "#8E8E93"} />
              <Text style={[styles.mediaOnlyText, isUser && { color: '#fff' }]}>Photo</Text>
            </View>
          )}
          
          {/* Text content */}
          {item.content ? (
            <Text style={[styles.messageText, isUser && styles.userMessageText]}>
              {item.content}
            </Text>
          ) : null}
          
          {item.intent_detected && (
            <View style={styles.intentBadge}>
              <Ionicons name="flag" size={10} color="#FF9500" />
              <Text style={styles.intentText}>{item.intent_detected}</Text>
            </View>
          )}
          
          <Text
            style={[
              styles.messageTime,
              isUser ? styles.userMessageTime : styles.contactMessageTime,
            ]}
          >
            {format(timestamp, 'h:mm a')}
          </Text>
        </View>
      </View>
    );
  };
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <View style={styles.headerInfo}>
          <Text style={styles.headerName}>{contactName}</Text>
          <Text style={styles.headerPhone}>{contactPhone}</Text>
        </View>
        
        <TouchableOpacity onPress={() => setShowSettings(true)} style={styles.settingsButton}>
          <Ionicons name="ellipsis-horizontal" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>
      
      {/* Messages */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          ref={flatListRef}
          data={messages}
          renderItem={renderMessage}
          keyExtractor={(item) => item._id}
          contentContainerStyle={styles.messagesList}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#007AFF"
            />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="chatbubble-outline" size={48} color="#2C2C2E" />
              <Text style={styles.emptyText}>No messages yet</Text>
              <Text style={styles.emptySubtext}>Start the conversation!</Text>
            </View>
          )}
          onContentSizeChange={() => {
            if (messages.length > 0) {
              flatListRef.current?.scrollToEnd({ animated: false });
            }
          }}
        />
      )}
      
      {/* AI Suggestion */}
      {showAISuggestion && aiMode !== 'off' && aiSuggestion.text && (
        <AISuggestion
          suggestion={aiSuggestion.text}
          intent={aiSuggestion.intent}
          onAccept={handleAcceptAISuggestion}
          onEdit={handleEditAISuggestion}
          onDismiss={() => setShowAISuggestion(false)}
        />
      )}
      
      {/* Loading AI indicator */}
      {loadingAI && (
        <View style={styles.aiLoadingContainer}>
          <ActivityIndicator size="small" color="#34C759" />
          <Text style={styles.aiLoadingText}>AI is thinking...</Text>
        </View>
      )}
      
      {/* Input Area - Large contained box with all tools inside */}
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={0}
      >
        <View style={styles.composerContainer}>
          {/* Main composer box */}
          <View style={styles.composerBox}>
            {/* Media Preview */}
            {selectedMedia && (
              <View style={styles.mediaPreview}>
                <Image source={{ uri: selectedMedia.uri }} style={styles.mediaPreviewImage} />
                <TouchableOpacity
                  style={styles.mediaPreviewRemove}
                  onPress={clearSelectedMedia}
                >
                  <Ionicons name="close-circle" size={24} color="#FF3B30" />
                </TouchableOpacity>
                <Text style={styles.mediaPreviewText}>Photo attached - tap send to send MMS</Text>
              </View>
            )}
            
            {/* Text input area */}
            <TextInput
              style={styles.composerInput}
              placeholder={selectedMedia ? "Add a caption (optional)..." : "Type your message..."}
              placeholderTextColor="#6E6E73"
              value={message}
              onChangeText={setMessage}
              multiline
              maxLength={1000}
            />
            
            {/* Bottom toolbar inside the box */}
            <View style={styles.composerToolbar}>
              {/* Left side tools */}
              <View style={styles.composerTools}>
                <TouchableOpacity
                  style={styles.toolButton}
                  onPress={handleAttachPhoto}
                >
                  <Ionicons name="image-outline" size={22} color="#8E8E93" />
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.toolButton}
                  onPress={() => setShowTemplates(true)}
                >
                  <Ionicons name="document-text-outline" size={22} color="#8E8E93" />
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.toolButton}
                  onPress={() => setShowReviewLinks(true)}
                >
                  <Ionicons name="star-outline" size={22} color="#8E8E93" />
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.toolButton}
                  onPress={openBusinessCardPicker}
                  data-testid="business-card-btn"
                >
                  <Ionicons name="card-outline" size={22} color="#8E8E93" />
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={[styles.toolButton, isRecording && styles.recordingButton]}
                  onPress={handleVoiceToText}
                  disabled={transcribing}
                  data-testid="voice-to-text-btn"
                >
                  {transcribing ? (
                    <ActivityIndicator size="small" color="#007AFF" />
                  ) : (
                    <Ionicons
                      name={isRecording ? 'stop-circle' : 'mic-outline'}
                      size={22}
                      color={isRecording ? '#FF3B30' : '#8E8E93'}
                    />
                  )}
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.toolButton}
                  onPress={loadAISuggestion}
                  disabled={loadingAI || aiMode === 'off'}
                >
                  <Ionicons
                    name="sparkles"
                    size={20}
                    color={aiMode === 'off' ? '#3C3C3E' : '#34C759'}
                  />
                </TouchableOpacity>
              </View>
              
              {/* Send button */}
              <TouchableOpacity
                style={[styles.composerSendButton, ((!message.trim() && !selectedMedia) || sending || sendingMedia) && styles.composerSendButtonDisabled]}
                onPress={() => selectedMedia ? sendMMS() : handleSend()}
                disabled={(!message.trim() && !selectedMedia) || sending || sendingMedia}
              >
                {sending || sendingMedia ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Ionicons
                    name="send"
                    size={18}
                    color={(message.trim() || selectedMedia) ? '#FFF' : '#6E6E73'}
                  />
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
      
      {/* Review Links Modal - Fixed layout with scrollable content */}
      <Modal
        visible={showReviewLinks}
        animationType="slide"
        transparent={true}
      >
        <TouchableOpacity 
          style={styles.modalOverlay} 
          activeOpacity={1} 
          onPress={() => setShowReviewLinks(false)}
        >
          <View style={styles.templatesModal} onStartShouldSetResponder={() => true}>
            <View style={styles.modalHeader}>
              <View style={styles.modalHandle} />
              <Text style={styles.modalTitle}>Insert Review Link</Text>
            </View>
            
            {Object.keys(reviewLinks).length === 0 ? (
              <View style={styles.emptyReviews}>
                <Ionicons name="star-outline" size={48} color="#8E8E93" />
                <Text style={styles.emptyReviewsText}>No review links configured</Text>
                <TouchableOpacity
                  style={styles.setupReviewsButton}
                  onPress={() => {
                    setShowReviewLinks(false);
                    router.push('/settings/review-links');
                  }}
                >
                  <Text style={styles.setupReviewsButtonText}>Set Up Review Links</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <FlatList
                data={Object.entries(reviewLinks).filter(([_, url]) => url)}
                keyExtractor={([platformId]) => platformId}
                style={styles.templatesList}
                contentContainerStyle={styles.templatesListContent}
                renderItem={({ item: [platformId, url] }) => {
                  const platformNames: Record<string, {name: string; icon: string; color: string}> = {
                    google: { name: 'Google Reviews', icon: 'logo-google', color: '#4285F4' },
                    facebook: { name: 'Facebook', icon: 'logo-facebook', color: '#1877F2' },
                    yelp: { name: 'Yelp', icon: 'star', color: '#D32323' },
                    trustpilot: { name: 'Trustpilot', icon: 'shield-checkmark', color: '#00B67A' },
                    custom: { name: customLinkName || 'Custom Link', icon: 'link', color: '#8E8E93' },
                  };
                  const platform = platformNames[platformId] || platformNames.custom;
                  
                  return (
                    <TouchableOpacity
                      style={styles.templateItem}
                      onPress={() => insertReviewLink(platformId, url, platform.name)}
                    >
                      <View style={[styles.templateIcon, { backgroundColor: `${platform.color}20` }]}>
                        <Ionicons name={platform.icon as any} size={20} color={platform.color} />
                      </View>
                      <View style={styles.templateContent}>
                        <Text style={styles.templateName}>{platform.name}</Text>
                        <Text style={styles.templatePreview} numberOfLines={1}>{url}</Text>
                      </View>
                      <Ionicons name="add-circle" size={24} color="#007AFF" />
                    </TouchableOpacity>
                  );
                }}
              />
            )}
            
            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.modalCloseButton}
                onPress={() => setShowReviewLinks(false)}
              >
                <Text style={styles.modalCloseButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>
      
      {/* Templates Modal - Fixed layout with scrollable content */}
      <Modal
        visible={showTemplates}
        animationType="slide"
        presentationStyle="pageSheet"
        transparent={true}
      >
        <TouchableOpacity 
          style={styles.modalOverlay} 
          activeOpacity={1} 
          onPress={() => setShowTemplates(false)}
        >
          <View style={styles.templatesModal} onStartShouldSetResponder={() => true}>
            <View style={styles.modalHeader}>
              <View style={styles.modalHandle} />
              <Text style={styles.modalTitle}>Message Templates</Text>
            </View>
            
            <FlatList
              data={templates}
              keyExtractor={(item) => item._id}
              style={styles.templatesList}
              contentContainerStyle={styles.templatesListContent}
              showsVerticalScrollIndicator={true}
              renderItem={({ item: template }) => (
                <TouchableOpacity
                  style={styles.templateItem}
                  onPress={() => selectTemplate(template)}
                >
                  <View style={styles.templateIcon}>
                    <Ionicons name="document-text" size={20} color="#007AFF" />
                  </View>
                  <View style={styles.templateContent}>
                    <Text style={styles.templateName}>{template.name}</Text>
                    <Text style={styles.templatePreview} numberOfLines={2}>
                      {template.content}
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                </TouchableOpacity>
              )}
              ListEmptyComponent={() => (
                <View style={styles.emptyTemplates}>
                  <Ionicons name="document-text-outline" size={48} color="#8E8E93" />
                  <Text style={styles.emptyTemplatesText}>No templates yet</Text>
                </View>
              )}
            />
            
            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.modalCloseButton}
                onPress={() => setShowTemplates(false)}
              >
                <Text style={styles.modalCloseButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>
      
      {/* Digital Business Card Modal */}
      <Modal
        visible={showBusinessCard}
        animationType="slide"
        presentationStyle="pageSheet"
        transparent={true}
      >
        <TouchableOpacity 
          style={styles.modalOverlay} 
          activeOpacity={1} 
          onPress={() => setShowBusinessCard(false)}
        >
          <View style={styles.templatesModal} onStartShouldSetResponder={() => true}>
            <View style={styles.modalHeader}>
              <View style={styles.modalHandle} />
              <Text style={styles.modalTitle}>Share Business Card</Text>
            </View>
            
            <View style={styles.cardModalContent}>
              <View style={styles.cardPreview}>
                <Ionicons name="card" size={48} color="#007AFF" />
                <Text style={styles.cardPreviewTitle}>Your Digital Business Card</Text>
                <Text style={styles.cardPreviewDesc}>
                  Choose how you'd like to share your contact information
                </Text>
              </View>
              
              {/* Share Options */}
              <View style={styles.shareOptionsContainer}>
                <TouchableOpacity
                  style={styles.shareOptionCard}
                  onPress={sendVCardLink}
                  data-testid="share-vcf-btn"
                >
                  <View style={styles.shareOptionIcon}>
                    <Ionicons name="person-add" size={28} color="#34C759" />
                  </View>
                  <View style={styles.shareOptionContent}>
                    <Text style={styles.shareOptionTitle}>Share Contact (VCF)</Text>
                    <Text style={styles.shareOptionDesc}>
                      Send a direct link to save your contact info to their phone
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.shareOptionCard}
                  onPress={sendBusinessCardLink}
                  data-testid="share-landing-btn"
                >
                  <View style={styles.shareOptionIcon}>
                    <Ionicons name="globe-outline" size={28} color="#007AFF" />
                  </View>
                  <View style={styles.shareOptionContent}>
                    <Text style={styles.shareOptionTitle}>Share Landing Page</Text>
                    <Text style={styles.shareOptionDesc}>
                      Send your full digital card with socials, bio & more
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                </TouchableOpacity>
              </View>
              
              {/* Landing Page Options (Campaign Picker) */}
              {showLandingPageOptions && (
                <View style={styles.landingPageOptions}>
                  <View style={styles.landingPageOptionsHeader}>
                    <TouchableOpacity onPress={() => setShowLandingPageOptions(false)}>
                      <Ionicons name="arrow-back" size={24} color="#007AFF" />
                    </TouchableOpacity>
                    <Text style={styles.landingPageOptionsTitle}>Landing Page Options</Text>
                  </View>
                  
                  <Text style={styles.campaignPickerLabel}>Start them on a campaign (optional):</Text>
                  
                  {loadingCampaigns ? (
                    <ActivityIndicator size="small" color="#007AFF" style={{ marginVertical: 20 }} />
                  ) : campaigns.length === 0 ? (
                    <View style={styles.noCampaigns}>
                      <Text style={styles.noCampaignsText}>No active campaigns</Text>
                      <Text style={styles.noCampaignsSubtext}>Create campaigns in the Campaigns tab</Text>
                    </View>
                  ) : (
                    <ScrollView 
                      horizontal 
                      showsHorizontalScrollIndicator={false}
                      style={styles.campaignScroller}
                      contentContainerStyle={styles.campaignScrollerContent}
                    >
                      <TouchableOpacity
                        style={[
                          styles.campaignChip,
                          !selectedCampaign && styles.campaignChipSelected
                        ]}
                        onPress={() => setSelectedCampaign(null)}
                      >
                        <Text style={[
                          styles.campaignChipText,
                          !selectedCampaign && styles.campaignChipTextSelected
                        ]}>None</Text>
                      </TouchableOpacity>
                      
                      {campaigns.map((campaign) => (
                        <TouchableOpacity
                          key={campaign.id}
                          style={[
                            styles.campaignChip,
                            selectedCampaign === campaign.id && styles.campaignChipSelected
                          ]}
                          onPress={() => setSelectedCampaign(campaign.id)}
                        >
                          <Text style={[
                            styles.campaignChipText,
                            selectedCampaign === campaign.id && styles.campaignChipTextSelected
                          ]}>{campaign.name}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  )}
                  
                  <TouchableOpacity
                    style={styles.sendCardButton}
                    onPress={sendBusinessCardLink}
                    data-testid="send-card-btn"
                  >
                    <Ionicons name="paper-plane" size={20} color="#FFF" />
                    <Text style={styles.sendCardButtonText}>
                      {selectedCampaign ? 'Send Card + Start Campaign' : 'Send Landing Page'}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
            
            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.modalCloseButton}
                onPress={() => {
                  setShowBusinessCard(false);
                  setShowLandingPageOptions(false);
                }}
              >
                <Text style={styles.modalCloseButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>
      
      {/* Congrats Card Modal */}
      <Modal
        visible={showCongratsCardModal}
        animationType="slide"
        presentationStyle="pageSheet"
        transparent={true}
      >
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ flex: 1 }}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
        >
          <View style={styles.congratsModalOverlay}>
            <TouchableOpacity 
              style={styles.congratsModalBackdrop} 
              activeOpacity={1} 
              onPress={closeCongratsModal}
            />
            <View style={styles.congratsModal} onStartShouldSetResponder={() => true}>
              <View style={styles.modalHeader}>
                <View style={styles.modalHandle} />
                <Text style={styles.modalTitle}>Create Congrats Card</Text>
              </View>
              
              <ScrollView 
                style={styles.congratsModalContent}
                contentContainerStyle={styles.congratsModalScrollContent}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
              >
                {/* Photo Upload */}
                <TouchableOpacity
                  style={styles.congratsPhotoUpload}
                  onPress={pickCongratsPhoto}
                  data-testid="congrats-photo-upload"
                >
                  {congratsPhoto ? (
                    <Image source={{ uri: congratsPhoto.uri }} style={styles.congratsPhotoPreview} />
                  ) : (
                    <View style={styles.congratsPhotoPlaceholder}>
                      <Ionicons name="camera" size={40} color="#8E8E93" />
                      <Text style={styles.congratsPhotoText}>Tap to add customer photo</Text>
                    </View>
                  )}
                </TouchableOpacity>
                
                {/* Customer Name */}
                <Text style={styles.congratsLabel}>Customer Name *</Text>
                <TextInput
                  style={styles.congratsInput}
                  placeholder="Enter customer name"
                  placeholderTextColor="#6E6E73"
                  value={congratsCustomerName}
                  onChangeText={setCongratsCustomerName}
                  returnKeyType="next"
                  data-testid="congrats-customer-name-input"
                />
                
                {/* Custom Message (Optional) */}
                <Text style={styles.congratsLabel}>Personal Note (Optional)</Text>
                <TextInput
                  style={[styles.congratsInput, styles.congratsTextArea]}
                  placeholder="Add a personal message..."
                  placeholderTextColor="#6E6E73"
                  value={congratsCustomMessage}
                  onChangeText={setCongratsCustomMessage}
                  multiline
                  numberOfLines={3}
                  returnKeyType="done"
                  blurOnSubmit={true}
                  data-testid="congrats-message-input"
                />
                
                {/* Preview Info */}
                <View style={styles.congratsPreviewBox}>
                  <Ionicons name="gift" size={24} color="#C9A962" />
                  <Text style={styles.congratsPreviewText}>
                    Your customer will receive a beautiful branded thank you card they can download and share on social media!
                  </Text>
                </View>
                
                {/* Create Button */}
                <TouchableOpacity
                  style={[
                    styles.congratsCreateButton,
                    (!congratsPhoto || !congratsCustomerName.trim()) && styles.congratsCreateButtonDisabled
                  ]}
                  onPress={createCongratsCard}
                  disabled={!congratsPhoto || !congratsCustomerName.trim() || creatingCongratsCard}
                  data-testid="congrats-create-btn"
                >
                  {creatingCongratsCard ? (
                    <ActivityIndicator size="small" color="#000" />
                  ) : (
                    <>
                      <Ionicons name="sparkles" size={20} color="#000" />
                      <Text style={styles.congratsCreateButtonText}>Create Card & Send Link</Text>
                    </>
                  )}
                </TouchableOpacity>
              </ScrollView>
              
              <View style={styles.congratsModalFooter}>
                <TouchableOpacity
                  style={styles.modalCloseButton}
                  onPress={closeCongratsModal}
                  data-testid="congrats-cancel-btn"
                >
                  <Text style={styles.modalCloseButtonText}>Cancel</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
      
      {/* Settings Modal */}
      <Modal
        visible={showSettings}
        animationType="slide"
        presentationStyle="pageSheet"
        transparent={true}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHandle} />
            
            <Text style={styles.modalTitle}>Conversation Settings</Text>
            
            {/* AI Mode Selection */}
            <Text style={styles.modalSectionTitle}>AI Assistant Mode</Text>
            
            <TouchableOpacity 
              style={[styles.modeOption, aiMode === 'auto_reply' && styles.modeOptionActive]}
              onPress={() => setAiMode('auto_reply')}
            >
              <View style={[styles.modeIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="flash" size={20} color="#34C759" />
              </View>
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Auto-Reply</Text>
                <Text style={styles.modeDesc}>AI handles conversation automatically</Text>
              </View>
              {aiMode === 'auto_reply' && (
                <Ionicons name="checkmark-circle" size={24} color="#34C759" />
              )}
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={[styles.modeOption, aiMode === 'assisted' && styles.modeOptionActive]}
              onPress={() => setAiMode('assisted')}
            >
              <View style={[styles.modeIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="sparkles" size={20} color="#007AFF" />
              </View>
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Assisted</Text>
                <Text style={styles.modeDesc}>AI suggests, you approve before sending</Text>
              </View>
              {aiMode === 'assisted' && (
                <Ionicons name="checkmark-circle" size={24} color="#007AFF" />
              )}
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={[styles.modeOption, aiMode === 'draft_only' && styles.modeOptionActive]}
              onPress={() => setAiMode('draft_only')}
            >
              <View style={[styles.modeIcon, { backgroundColor: '#8E8E9320' }]}>
                <Ionicons name="document-text" size={20} color="#8E8E93" />
              </View>
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Drafts Only</Text>
                <Text style={styles.modeDesc}>AI creates drafts but doesn't send</Text>
              </View>
              {aiMode === 'draft_only' && (
                <Ionicons name="checkmark-circle" size={24} color="#8E8E93" />
              )}
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={[styles.modeOption, aiMode === 'off' && styles.modeOptionActive]}
              onPress={() => setAiMode('off')}
            >
              <View style={[styles.modeIcon, { backgroundColor: '#FF3B3020' }]}>
                <Ionicons name="flash-off" size={20} color="#FF3B30" />
              </View>
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Off</Text>
                <Text style={styles.modeDesc}>No AI assistance</Text>
              </View>
              {aiMode === 'off' && (
                <Ionicons name="checkmark-circle" size={24} color="#FF3B30" />
              )}
            </TouchableOpacity>
            
            {/* Conversation Status */}
            <Text style={[styles.modalSectionTitle, { marginTop: 24 }]}>Conversation Status</Text>
            
            <TouchableOpacity 
              style={styles.statusOption}
              onPress={() => {
                toggleConversationStatus();
                setShowSettings(false);
              }}
            >
              <View style={[styles.modeIcon, { backgroundColor: conversationStatus === 'closed' ? '#34C75920' : '#8E8E9320' }]}>
                <Ionicons 
                  name={conversationStatus === 'closed' ? 'refresh' : 'checkmark-done'} 
                  size={20} 
                  color={conversationStatus === 'closed' ? '#34C759' : '#8E8E93'} 
                />
              </View>
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>
                  {conversationStatus === 'closed' ? 'Reopen Conversation' : 'Mark as Complete'}
                </Text>
                <Text style={styles.modeDesc}>
                  {conversationStatus === 'closed' ? 'Resume this conversation' : 'Close this conversation'}
                </Text>
              </View>
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={styles.closeModalButton}
              onPress={() => setShowSettings(false)}
            >
              <Text style={styles.closeModalText}>Done</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
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
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  headerInfo: {
    flex: 1,
    marginLeft: 8,
  },
  headerName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  headerPhone: {
    fontSize: 13,
    color: '#8E8E93',
  },
  settingsButton: {
    padding: 8,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  messagesList: {
    padding: 16,
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 4,
  },
  messageContainer: {
    marginBottom: 8,
  },
  userMessageContainer: {
    alignItems: 'flex-end',
  },
  contactMessageContainer: {
    alignItems: 'flex-start',
  },
  messageBubble: {
    maxWidth: '75%',
    borderRadius: 18,
    padding: 12,
  },
  userMessageBubble: {
    backgroundColor: '#007AFF',
    borderBottomRightRadius: 4,
  },
  contactMessageBubble: {
    backgroundColor: '#1C1C1E',
    borderBottomLeftRadius: 4,
  },
  aiIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 6,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#34C75930',
  },
  aiIndicatorText: {
    fontSize: 11,
    color: '#34C759',
    fontWeight: '600',
  },
  messageText: {
    fontSize: 16,
    color: '#FFF',
    lineHeight: 22,
  },
  userMessageText: {
    color: '#FFF',
  },
  intentBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF950020',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    gap: 4,
    marginTop: 8,
    alignSelf: 'flex-start',
  },
  intentText: {
    fontSize: 11,
    color: '#FF9500',
    fontWeight: '600',
  },
  messageTime: {
    fontSize: 11,
    marginTop: 4,
  },
  userMessageTime: {
    color: '#FFF',
    opacity: 0.7,
  },
  contactMessageTime: {
    color: '#8E8E93',
  },
  aiLoadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 8,
    gap: 8,
  },
  aiLoadingText: {
    fontSize: 13,
    color: '#34C759',
    fontWeight: '500',
  },
  attachMenu: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#1C1C1E',
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    gap: 24,
    justifyContent: 'center',
  },
  attachOption: {
    alignItems: 'center',
    gap: 4,
  },
  attachOptionText: {
    fontSize: 12,
    color: '#8E8E93',
  },
  attachButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  inputWrapper: {
    flexDirection: 'row',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    alignItems: 'flex-end',
    gap: 8,
  },
  iconButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inputBox: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
    paddingLeft: 16,
    paddingRight: 8,
    paddingVertical: 8,
    minHeight: 40,
    maxHeight: 120,
  },
  inputField: {
    flex: 1,
    fontSize: 16,
    color: '#FFF',
    maxHeight: 100,
    paddingTop: 0,
    paddingBottom: 0,
  },
  micButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recordingButton: {
    backgroundColor: '#FF3B3020',
    borderRadius: 8,
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    alignItems: 'flex-end',
    gap: 8,
  },
  suggestButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  input: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 16,
    color: '#FFF',
    maxHeight: 100,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: '#1C1C1E',
  },
  
  // New Composer Box Styles
  composerContainer: {
    padding: 12,
    paddingBottom: 20,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  composerBox: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#2C2C2E',
    overflow: 'hidden',
  },
  mediaPreview: {
    padding: 12,
    backgroundColor: '#0A0A0A',
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
    alignItems: 'center',
  },
  mediaPreviewImage: {
    width: 120,
    height: 120,
    borderRadius: 12,
    marginBottom: 8,
  },
  mediaPreviewRemove: {
    position: 'absolute',
    top: 8,
    right: 8,
  },
  mediaPreviewText: {
    fontSize: 12,
    color: '#8E8E93',
  },
  // MMS Image styles in message bubbles
  mediaContainer: {
    marginBottom: 8,
    maxWidth: 220,
  },
  mediaImageWrapper: {
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 4,
    backgroundColor: '#1C1C1E',
  },
  mediaImage: {
    width: 200,
    height: 200,
    borderRadius: 12,
    backgroundColor: '#2C2C2E',
  },
  mediaImageError: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  mediaErrorText: {
    color: '#8E8E93',
    fontSize: 12,
    marginTop: 4,
  },
  mediaOnlyIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 4,
  },
  mediaOnlyText: {
    fontSize: 14,
    color: '#8E8E93',
  },
  composerInput: {
    fontSize: 16,
    color: '#FFF',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
    minHeight: 48,
    maxHeight: 120,
    textAlignVertical: 'top',
  },
  composerToolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    backgroundColor: '#151515',
  },
  composerTools: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  toolButton: {
    width: 40,
    height: 36,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  composerSendButton: {
    width: 40,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  composerSendButtonDisabled: {
    backgroundColor: '#2C2C2E',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-start',
    paddingTop: 20,
  },
  templatesModal: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    marginHorizontal: 10,
    flex: 1,
    marginBottom: 20,
  },
  modalHeader: {
    paddingTop: 12,
    paddingBottom: 16,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalHandle: {
    width: 36,
    height: 5,
    backgroundColor: '#3C3C3E',
    borderRadius: 3,
    alignSelf: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    textAlign: 'center',
  },
  templatesList: {
    flex: 1,
  },
  templatesListContent: {
    padding: 16,
    paddingBottom: 8,
  },
  modalFooter: {
    padding: 16,
    paddingBottom: 32,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  modalCloseButton: {
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  modalCloseButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FF3B30',
  },
  emptyTemplates: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyTemplatesText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 12,
  },
  modalSectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  modeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  modeOptionActive: {
    backgroundColor: '#3A3A3C',
  },
  modeIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  modeInfo: {
    flex: 1,
  },
  modeName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  modeDesc: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  statusOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
  },
  closeModalButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    marginTop: 24,
    alignItems: 'center',
  },
  closeModalText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  // Settings Modal specific
  modalContent: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  templateItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  templateIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  templateContent: {
    flex: 1,
  },
  templateName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  templatePreview: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  emptyReviews: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  emptyReviewsText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 12,
    marginBottom: 20,
  },
  setupReviewsButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 20,
  },
  setupReviewsButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  // Business Card Modal Styles
  cardModalContent: {
    padding: 20,
  },
  cardPreview: {
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 16,
    padding: 24,
    marginBottom: 20,
  },
  cardPreviewTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 12,
  },
  cardPreviewDesc: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  campaignPickerLabel: {
    fontSize: 15,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 12,
  },
  campaignScroller: {
    maxHeight: 50,
    marginBottom: 20,
  },
  campaignScrollerContent: {
    paddingRight: 20,
  },
  campaignChip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#2C2C2E',
    borderRadius: 20,
    marginRight: 10,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  campaignChipSelected: {
    backgroundColor: '#007AFF20',
    borderColor: '#007AFF',
  },
  campaignChipText: {
    fontSize: 14,
    color: '#8E8E93',
    fontWeight: '500',
  },
  campaignChipTextSelected: {
    color: '#007AFF',
  },
  noCampaigns: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  noCampaignsText: {
    fontSize: 15,
    color: '#8E8E93',
  },
  noCampaignsSubtext: {
    fontSize: 13,
    color: '#6E6E73',
    marginTop: 4,
  },
  sendCardButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  sendCardButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  // Share Options Styles
  shareOptionsContainer: {
    marginTop: 20,
    gap: 12,
  },
  shareOptionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 14,
    padding: 16,
  },
  shareOptionIcon: {
    width: 50,
    height: 50,
    borderRadius: 12,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  shareOptionContent: {
    flex: 1,
  },
  shareOptionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 4,
  },
  shareOptionDesc: {
    fontSize: 13,
    color: '#8E8E93',
    lineHeight: 18,
  },
  landingPageOptions: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  landingPageOptionsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    gap: 12,
  },
  landingPageOptionsTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  // Congrats Card Modal Styles
  congratsModalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  congratsModalBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  congratsModal: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '80%',
  },
  congratsModalContent: {
    flexGrow: 0,
    flexShrink: 1,
  },
  congratsModalScrollContent: {
    padding: 20,
    paddingBottom: 24,
  },
  congratsModalFooter: {
    padding: 16,
    paddingBottom: Platform.OS === 'ios' ? 34 : 20,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    backgroundColor: '#1C1C1E',
  },
  congratsPhotoUpload: {
    width: 150,
    height: 150,
    borderRadius: 75,
    alignSelf: 'center',
    marginBottom: 24,
    overflow: 'hidden',
    borderWidth: 3,
    borderColor: '#C9A962',
    borderStyle: 'dashed',
  },
  congratsPhotoPreview: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  congratsPhotoPlaceholder: {
    width: '100%',
    height: '100%',
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  congratsPhotoText: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 10,
  },
  congratsLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 8,
    marginTop: 8,
  },
  congratsInput: {
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
    marginBottom: 12,
  },
  congratsTextArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  congratsPreviewBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#C9A96220',
    borderRadius: 12,
    padding: 16,
    marginVertical: 16,
    gap: 12,
  },
  congratsPreviewText: {
    flex: 1,
    fontSize: 13,
    color: '#C9A962',
    lineHeight: 20,
  },
  congratsCreateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    borderRadius: 12,
    padding: 16,
    gap: 8,
    marginTop: 8,
  },
  congratsCreateButtonDisabled: {
    opacity: 0.5,
  },
  congratsCreateButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
});
