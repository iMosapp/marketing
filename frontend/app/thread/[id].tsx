import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Pressable,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
  ScrollView,
  RefreshControl,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { format } from 'date-fns';
import { Audio } from 'expo-av';
import * as ImagePicker from 'expo-image-picker';
import * as MediaLibrary from 'expo-media-library';
import * as Haptics from 'expo-haptics';
import { Image } from 'expo-image';
import AsyncStorage from '@react-native-async-storage/async-storage';
import AISuggestion from '../../components/AISuggestion';
import ChannelPicker, { useChannelPicker } from '../../components/ChannelPicker';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { messagesAPI, templatesAPI, emailAPI } from '../../services/api';
import api from '../../services/api';
import { showSimpleAlert, showAlert, showConfirm } from '../../services/alert';
import { PersonalizeButton } from '../../components/PersonalizeButton';

// Web platform detection
const IS_WEB = Platform.OS === 'web';

// Dark Mode Colors
const COLORS = {
  background: '#000000',
  surface: '#1C1C1E',
  elevated: '#2C2C2E',
  accent: '#007AFF',
  textPrimary: '#FFFFFF',
  textSecondary: '#8E8E93',
  textTertiary: '#636366',
  border: '#2C2C2E',
};

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
  channel?: string;
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
  const { id, contact_name, contact_phone, contact_email, contact_photo: paramPhoto, mode, prefill, event_type: paramEventType } = useLocalSearchParams();
  const user = useAuthStore((state) => state.user);
  const flatListRef = useRef<FlatList>(null);
  
  // Color mode state - theme-aware
  const [messageMode, setMessageMode] = useState<'sms' | 'email'>('sms');
  const channelPicker = useChannelPicker();
  const themeColors = useThemeStore(s => s.colors);
  const themeMode = useThemeStore(s => s.mode);
  const colors = themeMode === 'light' ? {
    background: themeColors.bg,
    surface: themeColors.card,
    elevated: themeColors.surface || themeColors.card,
    accent: '#007AFF',
    textPrimary: themeColors.text,
    textSecondary: themeColors.textSecondary,
    textTertiary: themeColors.textTertiary || '#8E8E93',
    border: themeColors.border,
    userBubbleBg: 'rgba(0,122,255,0.1)',
    userBubbleBorder: 'rgba(0,122,255,0.2)',
    contactBubbleBg: themeColors.card,
    contactBubbleBorder: themeColors.border,
  } : {
    ...COLORS,
    userBubbleBg: '#1A2A4A',
    userBubbleBorder: '#1E3A6E',
    contactBubbleBg: COLORS.surface,
    contactBubbleBorder: '#2A2A2A',
  };
  const styles = getStyles(colors);
  
  const [message, setMessage] = useState('');
  const [inputHeight, setInputHeight] = useState(36);
  const [pendingEventType, setPendingEventType] = useState<string | null>(
    typeof paramEventType === 'string' ? paramEventType : null
  );
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
  const [storeSlug, setStoreSlug] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedMedia, setSelectedMedia] = useState<{uri: string, type: string, name: string} | null>(null);
  const [sendingMedia, setSendingMedia] = useState(false);
  
  // Load message preferences or use navigation mode
  useEffect(() => {
    // If mode was passed from navigation, use that
    if (mode === 'email' || mode === 'sms') {
      // Trust the explicitly requested mode  - don't fall back.
      // The email availability check happens at send time (handleSend).
      setMessageMode(mode as 'sms' | 'email');
      AsyncStorage.setItem('message_mode', mode as string);
    } else if (mode === 'review' || mode === 'card' || mode === 'congrats') {
      // Don't force SMS  - load user's preferred mode first
      AsyncStorage.getItem('message_mode').then((savedMode) => {
        if (savedMode === 'email' && (contact_email || savedContactEmail)) {
          setMessageMode('email');
        } else {
          setMessageMode('sms');
        }
      }).catch(() => setMessageMode('sms'));
      setTimeout(() => {
        if (mode === 'review') setShowReviewLinks(true);
        else if (mode === 'card') setShowBusinessCard(true);
        else if (mode === 'congrats') setShowCongratsCardModal(true);
      }, 800);
    } else {
      loadMessagePreferences();
    }
  }, [mode]);

  // Pre-fill message from share flow
  useEffect(() => {
    if (prefill && typeof prefill === 'string') {
      setMessage(prefill);
    }
  }, [prefill]);
  
  const loadMessagePreferences = async () => {
    try {
      const savedMode = await AsyncStorage.getItem('message_mode');
      if (savedMode === 'sms' || savedMode === 'email') {
        // Trust saved preference  - email check happens at send time
        setMessageMode(savedMode);
      }
    } catch (error) {
      // Fallback to SMS mode
      console.log('Using default SMS mode');
    }
  };
  
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
  const [showPhotoOptionsModal, setShowPhotoOptionsModal] = useState(false);
  const [showCardTypePicker, setShowCardTypePicker] = useState(false);
  const [showEmailPrompt, setShowEmailPrompt] = useState(false);
  const [selectedCardType, setSelectedCardType] = useState('congrats');
  const CARD_TYPES = [
    { key: 'congrats', label: 'Congrats', icon: 'trophy', color: '#C9A962' },
    { key: 'birthday', label: 'Birthday', icon: 'gift', color: '#FF2D55' },
    { key: 'anniversary', label: 'Anniversary', icon: 'heart', color: '#AF52DE' },
    { key: 'thankyou', label: 'Thank You', icon: 'thumbs-up', color: '#34C759' },
    { key: 'welcome', label: 'Welcome', icon: 'hand-left', color: '#007AFF' },
    { key: 'holiday', label: 'Holiday', icon: 'snow', color: '#5AC8FA' },
  ];

  // Relationship Intel state
  const [intelData, setIntelData] = useState<any>(null);
  const [showIntel, setShowIntel] = useState(false);
  const [intelGenerating, setIntelGenerating] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);
  const [promptEmail, setPromptEmail] = useState('');
  const [savedContactEmail, setSavedContactEmail] = useState<string | null>(null);
  const hasEmail = !!(contact_email || savedContactEmail);
  const [congratsPhoto, setCongratsPhoto] = useState<{uri: string, type: string, name: string} | null>(null);
  const [congratsCustomerName, setCongratsCustomerName] = useState('');
  const [congratsCustomMessage, setCongratsCustomMessage] = useState('');
  const [creatingCongratsCard, setCreatingCongratsCard] = useState(false);
  const [congratsSelectedTags, setCongratsSelectedTags] = useState<string[]>([]);
  const [congratsCampaigns, setCongratsCampaigns] = useState<{id: string, name: string, trigger_tag: string}[]>([]);

  // Contact creation tracking (for send flow)
  const [contactCreated, setContactCreated] = useState(false);
  const [createdContactId, setCreatedContactId] = useState<string | null>(null);
  
  // Tags for congrats card
  const [availableTags, setAvailableTags] = useState<{_id: string, name: string, color: string}[]>([]);

  // Check if current user is admin/manager
  const isAdmin = user?.role === 'super_admin' || user?.role === 'org_admin' || user?.role === 'store_manager';

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

  // Load review links (depends on user for store slug fetch)
  useEffect(() => {
    if (user) {
      loadReviewLinks();
    }
  }, [user]);

  // Keyboard shortcuts for web (power users)
  useEffect(() => {
    if (Platform.OS !== 'web') return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Enter to send (without Shift for new line)
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        // Only if focused on message input area
        const target = e.target as HTMLElement;
        if (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.getAttribute('contenteditable')) {
          e.preventDefault();
          if (message.trim() && !sending) {
            handleSend();
          }
        }
      }
      // Ctrl/Cmd + Enter also sends (alternative)
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
    let userLinks: Record<string, string> = {};
    let userCustomName = '';
    try {
      const response = await messagesAPI.getReviewLinks(user._id);
      userLinks = response.review_links || {};
      userCustomName = response.custom_link_name || '';
    } catch (error) {
      console.log('No user-level review links');
    }
    // Fetch store slug + store-level review links
    try {
      if ((user as any).store_slug) {
        setStoreSlug((user as any).store_slug);
      }
      if (user.store_id) {
        const storeRes = await api.get(`/admin/stores/${user.store_id}`, {
          headers: { 'X-User-ID': user._id }
        });
        const storeData = storeRes.data;
        if (storeData) {
          const slug = storeData.slug;
          if (slug) {
            setStoreSlug(slug);
          } else if (storeData.name) {
            setStoreSlug(storeData.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
          }
          // Merge store-level review links with user-level (user overrides store)
          const storeLinks = storeData.review_links || {};
          const merged: Record<string, string> = {};
          for (const [key, val] of Object.entries(storeLinks)) {
            if (key === 'custom' && Array.isArray(val)) {
              for (const item of val as any[]) {
                if (item?.url) {
                  merged['custom'] = item.url;
                  if (item.name) setCustomLinkName(item.name);
                  break;
                }
              }
            } else if (typeof val === 'string' && val) {
              merged[key] = val;
            }
          }
          for (const [key, val] of Object.entries(userLinks)) {
            if (typeof val === 'string' && val) merged[key] = val;
          }
          setReviewLinks(merged);
          setCustomLinkName(userCustomName || storeData.custom_link_name || '');
          return;
        }
      }
    } catch {}
    // Fallback to user-level only
    setReviewLinks(userLinks);
    setCustomLinkName(userCustomName);
  };

  const conversationId = id as string;
  const contactName = (contact_name as string) || 'Contact';
  const contactPhone = (contact_phone as string) || '';
  const [actualConversationId, setActualConversationId] = useState<string | null>(null);
  // Initialize with param photo if available, will be overwritten by API if different
  const [contactPhoto, setContactPhoto] = useState<string | null>((paramPhoto as string) || null);
  const [contactIdForNav, setContactIdForNav] = useState<string | null>(null);
  
  useEffect(() => {
    if (user?._id && id) {
      ensureConversation();
      loadContactInfo();
    }
  }, [id, user?._id]);
  
  // Load contact info including photo
  const loadContactInfo = async () => {
    if (!id) return;
    try {
      const response = await api.get(`/messages/conversation/${id}/info`);
      if (response.data?.contact_id) {
        setContactIdForNav(response.data.contact_id);
      }
      if (response.data?.contact_photo) {
        setContactPhoto(response.data.contact_photo);
      }
      // Check if contact email exists in conversation info
      const loadedEmail = response.data?.contact_email || response.data?.contact_email_work;
      if (loadedEmail && !savedContactEmail) {
        setSavedContactEmail(loadedEmail);
      }
    } catch (error) {
      // Contact photo not available from conversation - try loading from contact directly
      // id is likely a contact_id, not a conversation_id
      try {
        const contactResponse = await api.get(`/contacts/${user?._id}/${id}`);
        if (contactResponse.data?.photo_thumbnail || contactResponse.data?.photo_url || contactResponse.data?.photo) {
          setContactPhoto(contactResponse.data.photo_thumbnail || contactResponse.data.photo_url || contactResponse.data.photo);
        }
        // Load email from contact record if available  - check both fields
        const contactEmail = contactResponse.data?.email || contactResponse.data?.email_work;
        if (contactEmail && !savedContactEmail) {
          setSavedContactEmail(contactEmail);
        }
        // Since we loaded from contact directly, id IS the contact_id
        if (!contactIdForNav) {
          setContactIdForNav(id as string);
        }
      } catch (e) {
        console.log('Contact photo not available');
      }
    }
  };
  
  // Ensure we have a conversation (create if needed)
  const ensureConversation = async () => {
    if (!id || !user?._id) return;
    
    try {
      // First try to load the thread directly (assuming id is a conversation id)
      const data = await messagesAPI.getThread(id as string);
      setMessages(data || []);
      setActualConversationId(id as string);
      
      // Auto-mark as read when opening a conversation
      try { await messagesAPI.markAsRead(id as string); } catch {}
      
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
        
        // id is confirmed as a contact_id — set it for intel loading
        if (!contactIdForNav) {
          setContactIdForNav(id as string);
        }
        
        // Auto-mark as read when opening a conversation
        try { await messagesAPI.markAsRead(convId); } catch {}
        
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

  // Relationship Intel functions
  const loadIntel = async () => {
    if (!user?._id || !contactIdForNav) return;
    try {
      const res = await api.get(`/contact-intel/${user._id}/${contactIdForNav}`);
      if (res.data?.summary) setIntelData(res.data);
    } catch {}
  };

  const generateIntel = async () => {
    if (!user?._id || !contactIdForNav) return;
    setIntelGenerating(true);
    setShowIntel(true);
    try {
      const res = await api.post(`/contact-intel/${user._id}/${contactIdForNav}`);
      setIntelData(res.data);
      // Scroll to top so user sees the refreshed intel
      if (Platform.OS === 'web') {
        setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 100);
      }
    } catch (e: any) {
      console.error('Intel generation failed:', e);
    } finally {
      setIntelGenerating(false);
    }
  };

  // Load intel when contact ID is available
  useEffect(() => {
    if (user?._id && contactIdForNav) loadIntel();
  }, [user?._id, contactIdForNav]);

  
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
    let contentToSend = textToSend || message.trim();
    if (!contentToSend || !user) return;
    
    // Resolve personalization merge tags
    const firstName = (contact_name as string || '').split(' ')[0] || '';
    const nameParts = (contact_name as string || '').split(' ');
    const lastName = nameParts.length > 1 ? nameParts.slice(1).join(' ') : '';
    contentToSend = contentToSend
      .replace(/\{first_name\}/g, firstName)
      .replace(/\{last_name\}/g, lastName)
      .replace(/\{full_name\}/g, (contact_name as string) || '')
      .replace(/\{phone\}/g, (contact_phone as string) || '')
      .replace(/\{email\}/g, (contact_email as string) || savedContactEmail || '')
      .replace(/\{my_name\}/g, (user as any).name || '')
      .replace(/\{my_phone\}/g, (user as any).phone || '')
      .replace(/\{company\}/g, (user as any).organization_name || '')
      .replace(/\{date_sold\}/g, '')
      .replace(/\{name\}/g, firstName);
    
    // Block email send if contact has no email - check API as fallback
    if (messageMode === 'email' && !hasEmail) {
      try {
        const res = await api.get(`/messages/conversation/${actualConversationId || conversationId}/info`);
        if (res.data?.contact_email) {
          setSavedContactEmail(res.data.contact_email);
          // Continue with send  - don't return
        } else {
          setShowEmailPrompt(true);
          return;
        }
      } catch {
        setShowEmailPrompt(true);
        return;
      }
    }
    
    // Light haptic when sending message
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    // Check if user has a Twilio number for SMS mode
    const hasTwilioNumber = !!(user as any).mvpline_number;
    const isPersonalSMS = messageMode === 'sms' && !hasTwilioNumber;
    
    // PERSONAL SMS FLOW: Log the event reliably BEFORE opening native SMS.
    // Previous approach used raw fetch+keepalive which iOS PWA kills on navigation.
    // Now we await the API call first, then open SMS.
    if (isPersonalSMS && contactPhone) {
      // Optimistic UI update
      const optimisticMessage: Message = {
        _id: `temp_${Date.now()}`,
        content: contentToSend,
        sender: 'user',
        timestamp: new Date().toISOString(),
        ai_generated: false,
        channel: 'sms_personal',
      };
      setMessages((prev) => [...prev, optimisticMessage]);
      setMessage('');
      setInputHeight(36);
      setShowAISuggestion(false);
      setSending(true);
      
      // 1. Ensure we have a valid CONVERSATION ID (not a contact ID)
      let convId = actualConversationId;
      if (!convId) {
        try {
          const convRes = await api.post(`/messages/conversations/${user._id}`, {
            contact_id: id,
            contact_phone: contactPhone,
          });
          convId = convRes.data._id;
          setActualConversationId(convId);
        } catch (e) {
          console.error('Failed to ensure conversation:', e);
        }
      }
      
      // 2. Log event + save message via the regular API (awaited = guaranteed)
      let eventLogged = false;
      if (convId) {
        const messagePayload: any = {
          conversation_id: convId,
          content: contentToSend,
          channel: 'sms_personal',
          // For personal SMS, DON'T pass pendingEventType — the card-specific event
          // (e.g. holiday_card_sent) is already logged by the card creation flow.
          // The SMS send itself should always be tracked as 'personal_sms' for attribution.
        };
        if (selectedTemplateInfo) {
          messagePayload.template_id = selectedTemplateInfo.template_id;
          messagePayload.template_type = selectedTemplateInfo.template_type;
          messagePayload.template_name = selectedTemplateInfo.template_name;
        }
        try {
          await api.post(`/messages/send/${user._id}/${convId}`, messagePayload);
          eventLogged = true;
        } catch (e) {
          console.error('Messages send failed, will use fallback:', e);
        }
      }
      
      // 3. Fallback: if main send failed, log event directly via contact_events
      if (!eventLogged) {
        const cid = contactIdForNav || (id as string);
        if (cid) {
          const apiBase = IS_WEB ? '/api' : `${process.env.EXPO_PUBLIC_BACKEND_URL || ''}/api`;
          const eventPayload = JSON.stringify({
            event_type: 'personal_sms',
            title: 'SMS Sent',
            description: `Sent SMS to ${contactName}`,
            channel: 'sms_personal',
            category: 'message',
          });
          // Use sendBeacon (most reliable for pre-navigation), with fetch fallback
          try {
            if (IS_WEB && typeof navigator !== 'undefined' && navigator.sendBeacon) {
              const blob = new Blob([eventPayload], { type: 'application/json' });
              navigator.sendBeacon(`${apiBase}/contacts/${user._id}/${cid}/events`, blob);
            } else {
              fetch(`${apiBase}/contacts/${user._id}/${cid}/events`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: eventPayload,
                keepalive: true,
              }).catch(() => {});
            }
          } catch {}
        }
      }
      
      // 4. Open channel picker (shows all org-enabled channels: SMS, WhatsApp, Messenger, etc.)
      channelPicker.open({
        message: contentToSend,
        phone: contactPhone,
        email: (contact_email as string) || savedContactEmail || '',
        onSent: (ch) => {
          // Update the just-logged event with the actual channel used
          const cid = contactIdForNav || (id as string);
          if (cid && user?._id) {
            api.patch(`/contacts/${user._id}/${cid}/events/latest-channel`, { channel: ch }).catch(() => {});
          }
        },
      });
      
      setSelectedTemplateInfo(null);
      setPendingEventType(null);
      setSending(false);
      return;
    }
    
    // REGULAR FLOW: Email, Twilio SMS, etc. (no page navigation)
    try {
      setSending(true);
      
      // Ensure we have a valid conversation ID before sending
      let convId = actualConversationId || conversationId;
      if (!convId) {
        throw new Error('No conversation ID available');
      }
      
      // If convId might be a contact ID (ensureConversation not yet complete), wait for it
      if (!actualConversationId && id) {
        try {
          const convRes = await api.post(`/messages/conversations/${user._id}`, {
            contact_id: id,
            contact_phone: contactPhone,
          });
          convId = convRes.data._id;
          setActualConversationId(convId);
        } catch {
          // Fallback  - use what we have
        }
      }
      
      // Optimistically add the message to the UI
      const optimisticMessage: Message = {
        _id: `temp_${Date.now()}`,
        content: contentToSend,
        sender: 'user',
        timestamp: new Date().toISOString(),
        ai_generated: false,
        channel: messageMode,
      };
      
      setMessages((prev) => [...prev, optimisticMessage]);
      setMessage('');
      setInputHeight(36);
      setShowAISuggestion(false);
      
      // Scroll to bottom
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
      
      // Build message payload with template info if available
      const messagePayload: any = {
        conversation_id: convId,
        content: contentToSend,
        channel: messageMode,
      };
      if (pendingEventType) messagePayload.event_type = pendingEventType;
      
      // Include template tracking info if a template was used
      if (selectedTemplateInfo) {
        messagePayload.template_id = selectedTemplateInfo.template_id;
        messagePayload.template_type = selectedTemplateInfo.template_type;
        messagePayload.template_name = selectedTemplateInfo.template_name;
      }
      
      // Send to backend (logs the message regardless of send method)
      const sendResult = await messagesAPI.send(user._id, messagePayload);
      
      // Check if backend reported a failure (e.g., email not sent)
      if (sendResult?.status === 'failed') {
        const errorMsg = sendResult?.error || 'Message failed to send';
        console.error('[SEND] Backend reported failure:', errorMsg);
        showAlert(
          'Send Failed', 
          messageMode === 'email' 
            ? `Email could not be delivered: ${errorMsg}`
            : `Message failed: ${errorMsg}`
        );
        // Remove optimistic message since it actually failed
        setMessages((prev) => prev.filter((m) => !m._id.startsWith('temp_')));
      }
      
      // Clear template info after sending
      setSelectedTemplateInfo(null);
      setPendingEventType(null);
      
      // Mark conversation as read after sending (we just responded)
      try { await messagesAPI.markAsRead(actualConversationId || id as string); } catch {}
      
      // Reload messages to get the real one from backend
      await loadMessages();
      
    } catch (error: any) {
      console.error('Failed to send message:', error);
      showAlert('Error', 'Failed to send message. Please try again.');
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
    
    // On web, show attachment options modal instead of Alert
    if (IS_WEB) {
      setShowPhotoOptionsModal(true);
      return;
    }
    
    showAlert(
      'Add Photo',
      undefined,
      [
        { text: 'Photo Library', onPress: pickImage },
        { text: 'Take Photo', onPress: takePhoto },
        { text: 'Create Card', onPress: () => openCongratsModal() },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  const handleAttachVideo = () => {
    setShowAttachMenu(false);
    showAlert('Coming Soon', 'Video attachments will be available in a future update.');
  };

  const insertReviewLink = (platformId: string, url: string, platformName: string) => {
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    const reviewMessage = `Hey ${firstName}! We'd love your feedback. Leave us a review here: ${url}`;
    // Pre-fill message in composer  - user taps Send to trigger native SMS
    setShowReviewLinks(false);
    setShowAttachMenu(false);
    setMessage(reviewMessage);
    setPendingEventType('review_request_sent');
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
    
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    const baseUrl = 'https://app.imonsocial.com';
    let cardUrl = `${baseUrl}/card/${user._id}`;
    
    const params = [];
    if (selectedCampaign) params.push(`campaign=${selectedCampaign}`);
    if (id) params.push(`contact=${id}`);
    if (params.length > 0) cardUrl += `?${params.join('&')}`;
    
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    const cardMessage = `Hey ${firstName}! Here's my digital business card - save my contact info: ${cardUrl}`;
    
    // Close modal and pre-fill message in composer
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    setSelectedCampaign(null);
    setMessage(cardMessage);
    setPendingEventType('digital_card_sent');
  };

  const sendVCardLink = () => {
    if (!user?._id) return;
    
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    const baseUrl = 'https://app.imonsocial.com';
    const vcardUrl = `${baseUrl}/api/card/vcard/${user._id}`;
    
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    const cardMessage = `Hey ${firstName}! Tap here to save my contact info directly to your phone: ${vcardUrl}`;
    
    // Close modal and pre-fill message in composer
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    setMessage(cardMessage);
    setPendingEventType('vcard_sent');
  };

  const sendShowcaseLink = () => {
    if (!user?._id) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const baseUrl = 'https://app.imonsocial.com';
    const showcaseUrl = `${baseUrl}/showcase/${user._id}`;
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    const msg = `Hey ${firstName}! Check out some of our happy customers: ${showcaseUrl}`;
    setShowBusinessCard(false);
    setMessage(msg);
    setPendingEventType('showcase_shared');
  };

  const sendLinkPageLink = async () => {
    if (!user?._id) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const baseUrl = 'https://app.imonsocial.com';
    const firstName = (contact_name as string || '').split(' ')[0] || 'there';
    try {
      const resp = await api.get(`/linkpage/user/${user._id}`);
      const username = resp.data?.username;
      if (username) {
        const url = `${baseUrl}/l/${username}`;
        const msg = `Hey ${firstName}! Here are all my links: ${url}`;
        setShowBusinessCard(false);
        setMessage(msg);
        setPendingEventType('link_page_shared');
      } else {
        showAlert('Not Set Up', 'Set up your Link Page in Settings first');
      }
    } catch {
      showAlert('Not Set Up', 'Set up your Link Page in Settings first');
    }
  };

  // Congrats Card Functions
  const pickCongratsPhoto = async () => {
    // On web, directly open file picker
    if (IS_WEB) {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        showAlert('Permission Denied', 'Photo library access is required.');
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
      return;
    }
    
    showAlert(
      'Add Customer Photo',
      'Choose an option',
      [
        {
          text: 'Take Photo',
          onPress: async () => {
            const { status } = await ImagePicker.requestCameraPermissionsAsync();
            if (status !== 'granted') {
              showAlert('Permission Denied', 'Camera access is required to take photos.');
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
          text: 'Photo Library',
          onPress: async () => {
            const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
            if (status !== 'granted') {
              showAlert('Permission Denied', 'Photo library access is required.');
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
      showSimpleAlert('Missing Info', 'Please add a photo and enter the customer name.');
      return;
    }

    // Premium haptic feedback on button press
    if (!IS_WEB) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    setCreatingCongratsCard(true);
    try {
      const formData = new FormData();
      formData.append('salesman_id', user._id);
      formData.append('customer_name', congratsCustomerName.trim());
      formData.append('customer_phone', contact_phone as string || '');
      formData.append('card_type', selectedCardType);
      if (congratsCustomMessage.trim()) {
        formData.append('custom_message', congratsCustomMessage.trim());
      }
      
      // Handle photo differently for web vs mobile
      if (IS_WEB) {
        // On web, convert the URI to a Blob/File
        const response = await fetch(congratsPhoto.uri);
        const blob = await response.blob();
        formData.append('photo', blob, congratsPhoto.name || 'photo.jpg');
      } else {
        formData.append('photo', {
          uri: congratsPhoto.uri,
          type: congratsPhoto.type,
          name: congratsPhoto.name,
        } as any);
      }

      const response = await api.post('/congrats/create', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.success) {
        // Success haptic feedback - feels satisfying!
        if (!IS_WEB) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        
        // Auto-save original photo to camera roll
        if (congratsPhoto?.uri) {
          try {
            if (!IS_WEB) {
              const { status } = await MediaLibrary.requestPermissionsAsync();
              if (status === 'granted') {
                await MediaLibrary.saveToLibraryAsync(congratsPhoto.uri);
              }
            }
          } catch (saveErr) {
            console.log('Auto-save photo to library failed:', saveErr);
          }
        }
        
        // Apply selected tags to the contact and trigger campaign enrollment
        if (congratsSelectedTags.length > 0 && (id || createdContactId)) {
          const contactId = id || createdContactId;
          try {
            // Fetch current contact data first
            const contactRes = await api.get(`/contacts/${user._id}/${contactId}`);
            const currentContact = contactRes.data;
            // Merge new tags with existing
            const existingTags = currentContact.tags || [];
            const mergedTags = [...new Set([...existingTags, ...congratsSelectedTags])];
            // Update contact with merged tags via PUT
            await api.put(`/contacts/${user._id}/${contactId}`, {
              ...currentContact,
              tags: mergedTags,
            });
            
            const matchingCampaigns = congratsSelectedTags
              .map(t => getCampaignForTag(t))
              .filter(Boolean);
            if (matchingCampaigns.length > 0) {
              const campaignNames = matchingCampaigns.map(c => c!.name).join(', ');
              console.log(`Tags applied, auto-enrolling in campaigns: ${campaignNames}`);
            }
          } catch (tagErr) {
            console.error('Failed to apply tags:', tagErr);
          }
        }
        
        // Get the card image URL for MMS
        const cardImageUrl = `https://app.imonsocial.com/api/congrats/card/${response.data.card_id}/image`;
        
        // Use short URL if available, otherwise fall back to production URL
        const cardUrl = response.data.short_url || response.data.card_url || 
          `https://app.imonsocial.com/congrats/${response.data.card_id}`;
        
        // Insert message with both the image and short link
        const firstName = congratsCustomerName.split(' ')[0];
        const cardTypeInfo = CARD_TYPES.find(ct => ct.key === selectedCardType) || CARD_TYPES[0];
        const cardMessages: Record<string, string> = {
          congrats: `Hey ${firstName}! Congrats on your new purchase! We made this special card just for you:\n\n${cardUrl}\n\nDownload & share it!`,
          birthday: `Happy Birthday, ${firstName}! We made a special birthday card just for you:\n\n${cardUrl}\n\nHave an amazing day!`,
          anniversary: `Happy Anniversary, ${firstName}! Celebrating this milestone with a special card:\n\n${cardUrl}\n\nHere's to many more!`,
          thankyou: `Hey ${firstName}! Just wanted to say thank you! We made this card for you:\n\n${cardUrl}\n\nWe appreciate you!`,
          welcome: `Welcome, ${firstName}! So glad to have you with us! Here's a special welcome card:\n\n${cardUrl}`,
          holiday: `Happy Holidays, ${firstName}! We made a special card for you:\n\n${cardUrl}\n\nWishing you all the best!`,
        };
        const cardMessage = cardMessages[selectedCardType] || cardMessages.congrats;
        
        setPendingEventType(`${selectedCardType}_card_sent`);
        setMessage(cardMessage);
        
        // Reset state
        setShowCongratsCardModal(false);
        setCongratsPhoto(null);
        setCongratsCustomerName('');
        setCongratsCustomMessage('');
        setCongratsSelectedTags([]);
        
        // Show success message
        const tagMsg = congratsSelectedTags.length > 0
          ? `\n\nTags applied: ${congratsSelectedTags.join(', ')}${
              congratsSelectedTags.some(t => getCampaignForTag(t))
                ? ' - Campaign auto-started!'
                : ''
            }`
          : '';
        const photoUpdateMsg = response.data.contact_photo_updated 
          ? "\n\nContact's profile photo has been updated!"
          : "";
        showSimpleAlert('Card Created!', `Your ${cardTypeInfo.label.toLowerCase()} card link has been added to your message. Hit send to share it!${photoUpdateMsg}${tagMsg}`);
      }
    } catch (error: any) {
      // Error haptic feedback
      if (!IS_WEB) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      console.error('Error creating congrats card:', error);
      const errMsg = typeof error === 'string' ? error 
        : error?.response?.data?.detail 
        || error?.message 
        || 'Failed to create congrats card';
      showSimpleAlert('Error', errMsg);
    } finally {
      setCreatingCongratsCard(false);
    }
  };

  const closeCongratsModal = () => {
    setShowCongratsCardModal(false);
    setCongratsPhoto(null);
    setCongratsCustomerName('');
    setCongratsCustomMessage('');
    setCongratsSelectedTags([]);
    setSelectedCardType('congrats');
  };

  const openCongratsModal = async () => {
    setShowCongratsCardModal(true);
    setCongratsSelectedTags([]);
    // Load campaigns with trigger_tags so we can show which campaigns tags activate
    if (user?._id) {
      try {
        const res = await api.get(`/campaigns/${user._id}`);
        const activeCampaigns = (res.data || [])
          .filter((c: any) => c.active && c.trigger_tag)
          .map((c: any) => ({ id: c._id, name: c.name, trigger_tag: c.trigger_tag }));
        setCongratsCampaigns(activeCampaigns);
      } catch { setCongratsCampaigns([]); }
      // Ensure tags are loaded
      if (availableTags.length === 0) {
        try {
          const response = await api.get(`/tags/${user._id}`);
          setAvailableTags(response.data || []);
        } catch {}
      }
    }
  };

  const toggleCongratsTag = (tagName: string) => {
    setCongratsSelectedTags(prev =>
      prev.includes(tagName) ? prev.filter(t => t !== tagName) : [...prev, tagName]
    );
  };

  const getCampaignForTag = (tagName: string) => {
    return congratsCampaigns.find(c => c.trigger_tag.toLowerCase() === tagName.toLowerCase());
  };

  const handleVoiceToText = async () => {
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
            
            if (IS_WEB) {
              // On web, audioUri is a blob URL - fetch it and create proper file
              const response = await fetch(uri);
              const blob = await response.blob();
              formData.append('file', blob, 'recording.webm');
            } else {
              formData.append('file', {
                uri,
                type: 'audio/m4a',
                name: 'recording.m4a',
              } as any);
            }
            
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
              } else {
                showAlert('Transcription Error', response.data.error || 'Failed to transcribe audio');
              }
            } catch (error: any) {
              console.error('Transcription error:', error);
              showAlert('Error', 'Failed to transcribe audio. Please try again.');
            }
          }
          
          setTranscribing(false);
        }
      } else {
        // Start recording
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          showAlert('Permission Denied', 'Microphone permission is required for voice recording.');
          return;
        }
        
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
        });
        
        // Platform-specific recording options
        const recordingOptions = IS_WEB 
          ? {
              ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
              isMeteringEnabled: false,
              web: {
                mimeType: 'audio/webm;codecs=opus',
                bitsPerSecond: 128000,
              },
            }
          : Audio.RecordingOptionsPresets.HIGH_QUALITY;
        
        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync(recordingOptions);
        await recording.startAsync();
        
        recordingRef.current = recording;
        setIsRecording(true);
        
        // On web, auto-stop after 30 seconds since there's no visual feedback
        if (IS_WEB) {
          setTimeout(() => {
            if (recordingRef.current && isRecording) {
              handleVoiceToText(); // Stop recording
            }
          }, 30000);
        }
      }
    } catch (error) {
      console.error('Recording error:', error);
      setIsRecording(false);
      setTranscribing(false);
      if (IS_WEB) {
        showAlert('Microphone Error', 'Could not access microphone. Please ensure you have granted microphone permission in your browser.');
      } else {
        showAlert('Error', 'Failed to record audio. Please try again.');
      }
    }
  };
  
  const pickImage = async () => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        showAlert('Permission Denied', 'Photo library access is required to send images.');
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
      showAlert('Error', 'Failed to select image');
    }
  };
  
  const takePhoto = async () => {
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        showAlert('Permission Denied', 'Camera access is required to take photos.');
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
      showAlert('Error', 'Failed to take photo');
    }
  };
  
  const sendMMS = async () => {
    const convId = actualConversationId || id as string;
    if (!selectedMedia || !user?._id || !convId) {
      showAlert('Error', 'Unable to send - missing required data');
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
      setInputHeight(36);
      setSelectedMedia(null);
      
      // Show success or warning
      if (response.data.status === 'sent') {
        // Success - no alert needed
      } else if (response.data.status === 'failed') {
        showAlert('Delivery Issue', 'Message saved but delivery failed: ' + (response.data.error || 'Unknown error'));
      }
    } catch (error: any) {
      console.error('MMS send error:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to send MMS';
      showAlert('Error', errorMsg);
    } finally {
      setSendingMedia(false);
    }
  };
  
  const clearSelectedMedia = () => {
    setSelectedMedia(null);
  };
  
  const toggleConversationStatus = async () => {
    const newStatus = conversationStatus === 'active' ? 'closed' : 'active';
    const convId = actualConversationId || id as string;
    setConversationStatus(newStatus);
    
    // Persist to database
    try {
      await api.put(`/messages/conversations/${user._id}/${convId}`, { status: newStatus });
    } catch (error) {
      console.error('Failed to update conversation status:', error);
    }
    
    showAlert(
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
        return colors.textSecondary;
      case 'off':
        return '#FF3B30';
    }
  };
  
  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.sender === 'user' || item.sender === 'ai';
    const timestamp = item.timestamp ? new Date(item.timestamp) : new Date();
    const hasMedia = item.has_media && item.media_urls && item.media_urls.length > 0;
    
    // Detect rich content types
    const content = item.content || '';
    const eventType = (item as any).event_type || '';
    const contentLower = content.toLowerCase();
    const isReviewLink = content.includes('/review/') || contentLower.includes('review link') || eventType.includes('review');
    const isDigitalCard = content.includes('/card/') || content.includes('/p/') || contentLower.includes('digital card') || contentLower.includes('digital business card') || contentLower.includes('save my contact') || eventType === 'digital_card_shared' || eventType === 'digital_card_sent';
    
    // Detect card type from event_type first, then fall back to URL/content analysis
    let detectedCardType = '';
    const KNOWN_CARD_TYPES = ['congrats', 'birthday', 'anniversary', 'thankyou', 'welcome', 'holiday'];
    
    // Helper: detect card type from message text content
    const detectFromContent = (text: string): string => {
      if (text.includes('holiday card') || text.includes('happy holiday')) return 'holiday';
      if (text.includes('birthday card') || text.includes('happy birthday')) return 'birthday';
      if (text.includes('anniversary card') || text.includes('happy anniversary')) return 'anniversary';
      if (text.includes('thank you card') || text.includes('thankyou card')) return 'thankyou';
      if (text.includes('welcome card')) return 'welcome';
      return '';
    };
    
    if (eventType.includes('_card_sent') || eventType.includes('_card_shared')) {
      const typeFromEvent = eventType.replace('_card_sent', '').replace('_card_shared', '');
      if (KNOWN_CARD_TYPES.includes(typeFromEvent) && typeFromEvent !== 'congrats') {
        // Specific card type like birthday_card_sent — trust it
        detectedCardType = typeFromEvent;
      } else if (typeFromEvent === 'congrats') {
        // Generic congrats_card_sent — check content for the REAL type
        // If this is actually a digital card, don't mislabel it as congrats
        if (!isDigitalCard) {
          detectedCardType = detectFromContent(contentLower) || 'congrats';
        }
      }
      // digital_card_sent/shared and other non-card types fall through (detectedCardType stays '')
    } else if (content.includes('/congrats/')) {
      if (!isDigitalCard) {
        detectedCardType = detectFromContent(contentLower) || 'congrats';
      }
    } else if (!isDigitalCard && (contentLower.includes('congrats') || contentLower.includes('congratulations'))) {
      detectedCardType = 'congrats';
    }
    const isCongratsCard = detectedCardType !== '';
    const isRichContent = isReviewLink || isCongratsCard || isDigitalCard;
    
    // Card type display config
    const CARD_DISPLAY: Record<string, { icon: string; color: string; label: string }> = {
      congrats: { icon: 'trophy', color: '#C9A962', label: 'Congrats Card' },
      birthday: { icon: 'gift', color: '#FF2D55', label: 'Birthday Card' },
      anniversary: { icon: 'heart', color: '#AF52DE', label: 'Anniversary Card' },
      thankyou: { icon: 'thumbs-up', color: '#34C759', label: 'Thank You Card' },
      welcome: { icon: 'hand-left', color: '#007AFF', label: 'Welcome Card' },
      holiday: { icon: 'snow', color: '#5AC8FA', label: 'Holiday Card' },
    };
    
    // Choose icon and color for rich content
    let richIcon = 'chatbubble';
    let richColor = '#007AFF';
    let richLabel = 'Message';
    if (isReviewLink) { richIcon = 'star'; richColor = '#FFD60A'; richLabel = 'Review Link'; }
    else if (isDigitalCard) { richIcon = 'card'; richColor = '#5856D6'; richLabel = 'Digital Card'; }
    else if (isCongratsCard) {
      const cardDisplay = CARD_DISPLAY[detectedCardType] || CARD_DISPLAY.congrats;
      richIcon = cardDisplay.icon; richColor = cardDisplay.color; richLabel = cardDisplay.label;
    }
    
    return (
      <View
        style={[
          styles.messageContainer,
          isUser ? styles.userMessageContainer : styles.contactMessageContainer,
        ]}
      >
        {/* Sender label */}
        <Text style={[styles.senderLabel, isUser ? styles.senderLabelRight : styles.senderLabelLeft]}>
          {isUser ? (item.ai_generated ? 'Jessi AI' : 'You') : (contactName?.toString() || 'Contact')} · {format(timestamp, 'h:mm a')}
        </Text>
        
        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userMessageBubble : styles.contactMessageBubble,
            isRichContent && styles.richMessageBubble,
            isRichContent && { borderLeftColor: richColor },
          ]}
        >
          {/* Rich content header */}
          {isRichContent && (
            <View style={styles.richContentHeader}>
              <View style={[styles.richContentIcon, { backgroundColor: `${richColor}20` }]}>
                <Ionicons name={richIcon as any} size={14} color={richColor} />
              </View>
              <Text style={[styles.richContentLabel, { color: richColor }]}>{richLabel}</Text>
            </View>
          )}
          
          {item.ai_generated && !isRichContent && (
            <View style={styles.aiIndicator}>
              <Ionicons name="sparkles" size={12} color="#34C759" />
              <Text style={styles.aiIndicatorText}>AI</Text>
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
                    contentFit="cover"
                    cachePolicy="memory-disk"
                    transition={200}
                  />
                </View>
              ))}
            </View>
          )}
          
          {/* Show image icon if media exists but no text content */}
          {hasMedia && !item.content && (
            <View style={styles.mediaOnlyIndicator}>
              <Ionicons name="image" size={14} color={isUser ? "#fff" : colors.textSecondary} />
              <Text style={[styles.mediaOnlyText, isUser && { color: colors.text }]}>Photo</Text>
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
          
          {item.channel === 'sms_personal' && isUser && (
            <View style={styles.personalSmsBadge}>
              <Ionicons name="phone-portrait-outline" size={10} color={colors.textSecondary} />
              <Text style={styles.personalSmsText}>Sent from your phone</Text>
            </View>
          )}
          
          {item.channel === 'email' && isUser && (
            <View style={styles.personalSmsBadge}>
              <Ionicons name="mail-outline" size={10} color="#AF52DE" />
              <Text style={[styles.personalSmsText, { color: '#AF52DE' }]}>Sent via email</Text>
            </View>
          )}
        </View>
      </View>
    );
  };
  
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color={colors.accent} />
        </TouchableOpacity>
        
        {/* Contact Avatar */}
        {contactPhoto ? (
          <Image source={{ uri: contactPhoto }} style={styles.headerAvatar} />
        ) : (
          <View style={[styles.headerAvatarPlaceholder, { backgroundColor: colors.accent }]}>
            <Text style={styles.headerAvatarText}>
              {contactName.split(' ').map(n => n[0] || '').join('').toUpperCase().slice(0, 2) || '?'}
            </Text>
          </View>
        )}
        
        <View style={styles.headerInfo}>
          <TouchableOpacity onPress={() => router.push(`/contact/${contactIdForNav || id}` as any)} data-testid="thread-contact-name-link">
            <Text style={[styles.headerName, { color: colors.textPrimary }]}>{contactName}</Text>
          </TouchableOpacity>
          <Text style={[styles.headerPhone, { color: colors.textSecondary }]}>{contactPhone}</Text>
        </View>
        
        <TouchableOpacity onPress={() => setShowSettings(true)} style={styles.settingsButton}>
          <Ionicons name="ellipsis-horizontal" size={24} color={colors.accent} />
        </TouchableOpacity>
      </View>
      
      {/* SMS/Email Mode Indicator Banner */}
      <View style={[
        styles.modeBanner, 
        { 
          backgroundColor: messageMode === 'sms' ? '#007AFF15' : '#34C75915',
          borderColor: messageMode === 'sms' ? '#007AFF30' : '#34C75930',
        }
      ]}>
        <Ionicons 
          name={messageMode === 'sms' ? 'chatbubble' : 'mail'} 
          size={16} 
          color={messageMode === 'sms' ? '#007AFF' : '#34C759'} 
        />
        <Text style={styles.modeBannerText}>
          {messageMode === 'sms' ? 'Message Mode' : 'Email Mode'}
        </Text>
        <TouchableOpacity 
          style={styles.modeSwitchButton}
          onPress={async () => {
            const newMode = messageMode === 'sms' ? 'email' : 'sms';
            if (newMode === 'email' && !hasEmail) {
              // Before showing prompt, try to load email from API one more time
              try {
                const res = await api.get(`/messages/conversation/${actualConversationId || id}/info`);
                const loadedEmail = res.data?.contact_email;
                if (loadedEmail) {
                  setSavedContactEmail(loadedEmail);
                  setMessageMode('email');
                  AsyncStorage.setItem('message_mode', 'email');
                  return;
                }
              } catch {}
              setShowEmailPrompt(true);
              return;
            }
            setMessageMode(newMode);
            AsyncStorage.setItem('message_mode', newMode);
          }}
        >
          <Text style={styles.modeSwitchText}>
            Switch to {messageMode === 'sms' ? 'Email' : 'SMS'}
          </Text>
          <Ionicons 
            name={messageMode === 'sms' ? 'mail-outline' : 'chatbubble-outline'} 
            size={14} 
            color={colors.textSecondary} 
          />
        </TouchableOpacity>
      </View>
      
      {/* Inline Email Prompt */}
      {showEmailPrompt && (
        <View style={styles.emailPromptBanner} data-testid="email-prompt-banner">
          <Ionicons name="mail-outline" size={20} color="#C9A962" />
          <TextInput
            style={styles.emailPromptInput}
            placeholder="Enter customer's email address"
            placeholderTextColor={colors.textSecondary}
            value={promptEmail}
            onChangeText={setPromptEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoFocus
            data-testid="email-prompt-input"
          />
          <TouchableOpacity
            style={[styles.emailPromptSave, !promptEmail.includes('@') && { opacity: 0.4 }]}
            disabled={!promptEmail.includes('@')}
            onPress={async () => {
              if (!promptEmail.includes('@') || !user) return;
              try {
                // Use the correct conversation info endpoint
                const convId = actualConversationId || id;
                const convRes = await api.get(`/messages/conversation/${convId}/info`);
                const contactId = convRes.data?.contact_id || convRes.data?._id;
                if (contactId) {
                  await api.put(`/contacts/${user._id}/${contactId}`, { email: promptEmail.trim().toLowerCase() });
                }
                setSavedContactEmail(promptEmail.trim().toLowerCase());
                setShowEmailPrompt(false);
                setPromptEmail('');
                setMessageMode('email');
                AsyncStorage.setItem('message_mode', 'email');
              } catch (e) {
                console.error('Failed to save email:', e);
                showAlert('Error', 'Failed to save email address. Please try again.');
              }
            }}
            data-testid="email-prompt-save-btn"
          >
            <Text style={styles.emailPromptSaveText}>Save</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: colors.surface, borderRadius: 8 }}
            onPress={() => { setShowEmailPrompt(false); setPromptEmail(''); setMessageMode('sms'); AsyncStorage.setItem('message_mode', 'sms'); }} 
            data-testid="email-prompt-close"
          >
            <Ionicons name="chatbubble-outline" size={14} color="#007AFF" />
            <Text style={{ color: '#007AFF', fontSize: 15, fontWeight: '600' }}>SMS</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Relationship Intel Bar */}
      <Pressable
        style={({ pressed }) => [styles.intelBar, showIntel && styles.intelBarExpanded, pressed && { opacity: 0.7 }, { cursor: 'pointer' } as any]}
        onPress={() => {
          if (!intelData && !intelGenerating) {
            generateIntel();
          } else {
            setShowIntel(!showIntel);
          }
        }}
        role="button"
        data-testid="thread-intel-bar"
      >
        <View style={styles.intelBarLeft}>
          <Ionicons name="sparkles" size={16} color="#C9A962" />
          <Text style={styles.intelBarTitle}>Relationship Intel</Text>
          {intelData?.generated_at && !showIntel && (
            <Text style={styles.intelBarMeta}> · Updated {new Date(intelData.generated_at).toLocaleDateString()}</Text>
          )}
        </View>
        <Ionicons name={showIntel ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textTertiary} />
      </Pressable>

      {showIntel && (
        <ScrollView style={[styles.intelContent, { flex: 1 }]} nestedScrollEnabled data-testid="thread-intel-content">
          {intelGenerating ? (
            <View style={styles.intelLoadingRow}>
              <ActivityIndicator size="small" color="#C9A962" />
              <Text style={styles.intelLoadingText}>Analyzing relationship...</Text>
            </View>
          ) : intelData?.summary ? (
            <>
              <Text style={styles.intelSummaryText}>{intelData.summary}</Text>
              <View style={styles.intelMetaRow}>
                <Text style={styles.intelMetaText}>
                  {intelData.data_points?.messages || 0} messages · {intelData.data_points?.events || 0} events
                </Text>
                <Pressable
                  style={[styles.intelRefreshBtn, { cursor: 'pointer' } as any]}
                  onPress={generateIntel}
                  role="button"
                  data-testid="thread-intel-refresh"
                >
                  <Ionicons name="refresh" size={14} color="#007AFF" />
                  <Text style={styles.intelRefreshText}>Refresh</Text>
                </Pressable>
              </View>
            </>
          ) : (
            <Text style={styles.intelEmptyText}>Tap to generate an AI briefing about this contact</Text>
          )}
        </ScrollView>
      )}

      
      {/* Messages - hidden when intel is expanded */}
      {!showIntel && (loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
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
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="chatbubble-outline" size={48} color={colors.textSecondary} />
              <Text style={[styles.emptyText, { color: colors.textPrimary }]}>No messages yet</Text>
              <Text style={[styles.emptySubtext, { color: colors.textSecondary }]}>Start the conversation!</Text>
            </View>
          )}
          onContentSizeChange={() => {
            if (messages.length > 0) {
              flatListRef.current?.scrollToEnd({ animated: false });
            }
          }}
        />
      ))}
      
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
        <View style={[styles.composerContainer, { backgroundColor: colors.background }]}>
          {/* Main composer box */}
          <View style={[styles.composerBox, { backgroundColor: colors.surface }]}>
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
                <Text style={[styles.mediaPreviewText, { color: colors.textSecondary }]}>Photo attached - tap send to send MMS</Text>
              </View>
            )}
            
            {/* Text input area */}
            <TextInput
              style={[styles.composerInput, { color: colors.textPrimary, height: Math.max(36, Math.min(inputHeight, 150)) }]}
              placeholder={selectedMedia ? "Add a caption (optional)..." : "Type your message..."}
              placeholderTextColor={colors.textSecondary}
              value={message}
              onChangeText={setMessage}
              multiline
              numberOfLines={1}
              maxLength={1000}
              onContentSizeChange={(e) => {
                const h = e.nativeEvent.contentSize.height;
                if (message.trim()) {
                  setInputHeight(h);
                } else {
                  setInputHeight(36);
                }
              }}
              scrollEnabled={inputHeight > 150}
            />
            
            {/* Bottom toolbar inside the box */}
            <View style={[styles.composerToolbar, { borderTopColor: colors.border }]}>
              {/* Left side tools */}
              <View style={styles.composerTools}>
                <WebToolButton
                  onPress={handleAttachPhoto}
                  testID="attach-photo-btn"
                >
                  <Ionicons name="image-outline" size={22} color={colors.textSecondary} />
                </WebToolButton>
                
                <WebToolButton
                  onPress={() => setShowTemplates(true)}
                  testID="templates-btn"
                >
                  <Ionicons name="document-text-outline" size={22} color={colors.textSecondary} />
                </WebToolButton>
                
                <WebToolButton
                  onPress={() => setShowReviewLinks(true)}
                  testID="review-links-btn"
                >
                  <Ionicons name="star-outline" size={22} color={colors.textSecondary} />
                </WebToolButton>
                
                <WebToolButton
                  onPress={openBusinessCardPicker}
                  testID="business-card-btn"
                >
                  <Ionicons name="card-outline" size={22} color={colors.textSecondary} />
                </WebToolButton>
                
                <PersonalizeButton
                  colors={colors}
                  compact
                  onInsert={(tag) => setMessage(prev => prev + tag)}
                />
                
                <WebToolButton
                  onPress={handleVoiceToText}
                  disabled={transcribing}
                  isRecording={isRecording}
                  testID="voice-to-text-btn"
                >
                  {transcribing ? (
                    <ActivityIndicator size="small" color={colors.accent} />
                  ) : (
                    <Ionicons
                      name={isRecording ? 'stop-circle' : 'mic-outline'}
                      size={22}
                      color={isRecording ? '#FF3B30' : colors.textSecondary}
                    />
                  )}
                </WebToolButton>
                
                <WebToolButton
                  onPress={loadAISuggestion}
                  disabled={loadingAI || aiMode === 'off'}
                  testID="ai-suggestion-btn"
                >
                  <Ionicons
                    name="sparkles"
                    size={20}
                    color={aiMode === 'off' ? colors.elevated : '#34C759'}
                  />
                </WebToolButton>
              </View>
              
              {/* Send button */}
              {IS_WEB ? (
                <button
                  type="button"
                  onClick={() => selectedMedia ? sendMMS() : handleSend()}
                  disabled={(!message.trim() && !selectedMedia) || sending || sendingMedia}
                  data-testid="send-message-btn"
                  title={messageMode === 'sms' && !(user as any)?.mvpline_number ? 'Copy & open your messaging app' : 'Send message'}
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 18,
                    backgroundColor: (message.trim() || selectedMedia) && !sending && !sendingMedia 
                      ? (messageMode === 'sms' 
                          ? ((user as any)?.mvpline_number ? '#007AFF' : '#FF9500') 
                          : '#34C759') 
                      : colors.borderLight,
                    border: 'none',
                    cursor: (!message.trim() && !selectedMedia) || sending || sendingMedia ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {sending || sendingMedia ? (
                    <ActivityIndicator size="small" color={colors.text} />
                  ) : (
                    <Ionicons
                      name={messageMode === 'sms' 
                        ? ((user as any)?.mvpline_number ? 'send' : 'open-outline') 
                        : 'mail'}
                      size={18}
                      color={(message.trim() || selectedMedia) ? '#FFF' : '#6E6E73'}
                    />
                  )}
                </button>
              ) : (
                <TouchableOpacity
                  style={[
                    styles.composerSendButton, 
                    { backgroundColor: messageMode === 'sms' 
                        ? ((user as any)?.mvpline_number ? '#007AFF' : '#FF9500') 
                        : '#34C759' },
                    ((!message.trim() && !selectedMedia) || sending || sendingMedia) && styles.composerSendButtonDisabled
                  ]}
                  onPress={() => selectedMedia ? sendMMS() : handleSend()}
                  disabled={(!message.trim() && !selectedMedia) || sending || sendingMedia}
                >
                  {sending || sendingMedia ? (
                    <ActivityIndicator size="small" color={colors.text} />
                  ) : (
                    <Ionicons
                      name={messageMode === 'sms' 
                        ? ((user as any)?.mvpline_number ? 'send' : 'open-outline') 
                        : 'mail'}
                      size={18}
                      color={(message.trim() || selectedMedia) ? '#FFF' : '#6E6E73'}
                    />
                  )}
                </TouchableOpacity>
              )}
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
      
      {/* Review Links Action Sheet */}
      <Modal visible={showReviewLinks} animationType="slide" transparent={true}>
        <TouchableOpacity style={styles.actionSheetOverlay} activeOpacity={1} onPress={() => setShowReviewLinks(false)}>
          <View style={styles.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={styles.actionSheetGroup}>
              {storeSlug && (
                <>
                  <TouchableOpacity
                    style={styles.actionSheetButton}
                    data-testid="review-link-imos"
                    onPress={() => {
                      const firstName = (contact_name as string || '').split(' ')[0] || 'there';
                      const reviewUrl = `https://app.imonsocial.com/review/${storeSlug}?sp=${user?._id}`;
                      const reviewMsg = `Hey ${firstName}! We'd love your feedback. Leave us a review here: ${reviewUrl}`;
                      setShowReviewLinks(false);
                      setShowAttachMenu(false);
                      setMessage(reviewMsg);
                    }}
                  >
                    <Ionicons name="star" size={22} color="#FFD60A" />
                    <Text style={styles.actionSheetButtonText}>Send Review Request</Text>
                  </TouchableOpacity>
                  <View style={styles.actionSheetDivider} />
                </>
              )}
              {Object.entries(reviewLinks).filter(([_, url]) => url).map(([platformId, url], index, arr) => {
                const platformNames: Record<string, {name: string; icon: string; color: string}> = {
                  google: { name: 'Google Reviews', icon: 'logo-google', color: '#4285F4' },
                  facebook: { name: 'Facebook', icon: 'logo-facebook', color: '#1877F2' },
                  yelp: { name: 'Yelp', icon: 'star', color: '#D32323' },
                  trustpilot: { name: 'Trustpilot', icon: 'shield-checkmark', color: '#00B67A' },
                  dealerrater: { name: 'DealerRater', icon: 'car-sport', color: '#ED8B00' },
                  cars_com: { name: 'Cars.com', icon: 'car', color: '#5C2D91' },
                  custom: { name: customLinkName || 'Custom Link', icon: 'link', color: colors.textSecondary },
                };
                const platform = platformNames[platformId] || platformNames.custom;
                return (
                  <React.Fragment key={platformId}>
                    <TouchableOpacity style={styles.actionSheetButton} onPress={() => insertReviewLink(platformId, url, platform.name)}>
                      <Ionicons name={platform.icon as any} size={22} color={platform.color} />
                      <Text style={styles.actionSheetButtonText}>{platform.name}</Text>
                    </TouchableOpacity>
                    {index < arr.length - 1 && <View style={styles.actionSheetDivider} />}
                  </React.Fragment>
                );
              })}
              {!storeSlug && Object.keys(reviewLinks).length === 0 && (
                <TouchableOpacity style={styles.actionSheetButton} onPress={() => { setShowReviewLinks(false); router.push('/settings/review-links' as any); }}>
                  <Ionicons name="settings-outline" size={22} color="#007AFF" />
                  <Text style={styles.actionSheetButtonText}>Set Up Review Links</Text>
                </TouchableOpacity>
              )}
              {(storeSlug || Object.keys(reviewLinks).length > 0) && (
                <>
                  <View style={styles.actionSheetDivider} />
                  <TouchableOpacity style={styles.actionSheetButton} onPress={() => { setShowReviewLinks(false); router.push('/settings/review-links' as any); }}>
                    <Ionicons name="settings-outline" size={22} color={colors.textSecondary} />
                    <Text style={[styles.actionSheetButtonText, { color: colors.textSecondary, fontSize: 18 }]}>Manage Review Links</Text>
                  </TouchableOpacity>
                </>
              )}
            </View>
            <TouchableOpacity style={styles.actionSheetCancel} onPress={() => setShowReviewLinks(false)}>
              <Text style={styles.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
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
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
              ListEmptyComponent={() => (
                <View style={styles.emptyTemplates}>
                  <Ionicons name="document-text-outline" size={48} color={colors.textSecondary} />
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
            </View>
            
            <View style={styles.cardModalContent}>
              <View style={styles.cardPreview}>
                <Ionicons name="share-social" size={48} color="#007AFF" />
                <Text style={styles.cardPreviewTitle}>Share Your Stuff</Text>
                <Text style={styles.cardPreviewDesc}>
                  Choose what you'd like to send
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
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
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
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.shareOptionCard}
                  onPress={sendShowcaseLink}
                  data-testid="share-showcase-btn"
                >
                  <View style={styles.shareOptionIcon}>
                    <Ionicons name="images-outline" size={28} color="#FF9500" />
                  </View>
                  <View style={styles.shareOptionContent}>
                    <Text style={styles.shareOptionTitle}>Share Showcase</Text>
                    <Text style={styles.shareOptionDesc}>
                      Show off your happy customers & featured work
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.shareOptionCard}
                  onPress={sendLinkPageLink}
                  data-testid="share-linkpage-btn"
                >
                  <View style={styles.shareOptionIcon}>
                    <Ionicons name="link-outline" size={28} color="#AF52DE" />
                  </View>
                  <View style={styles.shareOptionContent}>
                    <Text style={styles.shareOptionTitle}>Share Link Page</Text>
                    <Text style={styles.shareOptionDesc}>
                      Send all your social links in one place
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
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
                    <Ionicons name="paper-plane" size={20} color={colors.text} />
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
      
      {/* Photo & Card Action Sheet (Web/PWA) */}
      <Modal
        visible={showPhotoOptionsModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowPhotoOptionsModal(false)}
      >
        <TouchableOpacity 
          style={styles.actionSheetOverlay}
          activeOpacity={1}
          onPress={() => setShowPhotoOptionsModal(false)}
        >
          <View style={styles.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={styles.actionSheetGroup}>
              <TouchableOpacity style={styles.actionSheetButton} onPress={() => { setShowPhotoOptionsModal(false); pickImage(); }} data-testid="photo-option-add">
                <Ionicons name="image-outline" size={22} color="#007AFF" />
                <Text style={styles.actionSheetButtonText}>Add a Photo</Text>
              </TouchableOpacity>
              <View style={styles.actionSheetDivider} />
              <View style={{ paddingVertical: 12, paddingHorizontal: 16 }}>
                <Text style={{ fontSize: 15, color: colors.textSecondary, fontWeight: '600', marginBottom: 10, textAlign: 'center' }}>CREATE A CARD</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingHorizontal: 4 }}>
                  {[
                    { type: 'congrats', label: 'Congrats', color: '#C9A962', icon: 'trophy' },
                    { type: 'birthday', label: 'Birthday', color: '#FF2D55', icon: 'gift' },
                    { type: 'holiday', label: 'Holiday', color: '#5AC8FA', icon: 'snow' },
                    { type: 'thankyou', label: 'Thank You', color: '#34C759', icon: 'thumbs-up' },
                    { type: 'anniversary', label: 'Anniversary', color: '#FF6B6B', icon: 'heart' },
                    { type: 'welcome', label: 'Welcome', color: '#007AFF', icon: 'hand-left' },
                  ].map(item => (
                    <TouchableOpacity
                      key={item.type}
                      style={{ alignItems: 'center', backgroundColor: `${item.color}15`, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 14, minWidth: 80 }}
                      onPress={() => {
                        setShowPhotoOptionsModal(false);
                        const params = new URLSearchParams();
                        params.set('type', item.type);
                        if (contactName && contactName !== 'Contact') params.set('prefillName', contactName);
                        if (contactPhone) params.set('prefillPhone', contactPhone);
                        const email = savedContactEmail || (contact_email as string) || '';
                        if (email) params.set('prefillEmail', email);
                        params.set('returnToThread', id as string);
                        router.push(`/settings/create-card?${params.toString()}` as any);
                      }}
                      data-testid={`card-template-${item.type}`}
                    >
                      <Ionicons name={item.icon as any} size={24} color={item.color} />
                      <Text style={{ fontSize: 14, fontWeight: '600', color: item.color, marginTop: 6 }}>{item.label}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            </View>
            <TouchableOpacity style={styles.actionSheetCancel} onPress={() => setShowPhotoOptionsModal(false)} data-testid="photo-option-cancel">
              <Text style={styles.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
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
                <Text style={styles.modalTitle}>Create {(CARD_TYPES.find(ct => ct.key === selectedCardType) || CARD_TYPES[0]).label} Card</Text>
              </View>
              
              <ScrollView 
                style={styles.congratsModalContent}
                contentContainerStyle={styles.congratsModalScrollContent}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
              >
                {/* Card Type Selector */}
                <Text style={styles.congratsLabel}>Card Type</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {CARD_TYPES.map(ct => (
                      <TouchableOpacity
                        key={ct.key}
                        style={[
                          styles.cardTypeChip,
                          selectedCardType === ct.key && { backgroundColor: ct.color, borderColor: ct.color },
                        ]}
                        onPress={() => setSelectedCardType(ct.key)}
                        data-testid={`card-type-${ct.key}`}
                      >
                        <Ionicons name={ct.icon as any} size={14} color={selectedCardType === ct.key ? '#FFF' : ct.color} />
                        <Text style={[styles.cardTypeChipText, selectedCardType === ct.key && { color: '#FFF' }]}>{ct.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>

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
                      <Ionicons name="camera" size={40} color={colors.textSecondary} />
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
                  <Ionicons name={(CARD_TYPES.find(ct => ct.key === selectedCardType) || CARD_TYPES[0]).icon as any} size={24} color={(CARD_TYPES.find(ct => ct.key === selectedCardType) || CARD_TYPES[0]).color} />
                  <Text style={styles.congratsPreviewText}>
                    Your customer will receive a beautiful branded {(CARD_TYPES.find(ct => ct.key === selectedCardType) || CARD_TYPES[0]).label.toLowerCase()} card they can download and share on social media!
                  </Text>
                </View>

                {/* Tag & Campaign Picker */}
                <Text style={styles.congratsLabel}>Apply Tags & Start Campaigns</Text>
                <View style={styles.congratsTagSection}>
                  {availableTags.length === 0 ? (
                    <Text style={styles.congratsTagEmpty}>No tags created yet</Text>
                  ) : (
                    <View style={styles.congratsTagGrid}>
                      {availableTags.map((tag) => {
                        const isSelected = congratsSelectedTags.includes(tag.name);
                        const linkedCampaign = getCampaignForTag(tag.name);
                        return (
                          <TouchableOpacity
                            key={tag._id}
                            style={[
                              styles.congratsTagChip,
                              isSelected && { backgroundColor: `${tag.color || '#C9A962'}25`, borderColor: tag.color || '#C9A962' },
                            ]}
                            onPress={() => toggleCongratsTag(tag.name)}
                            data-testid={`congrats-tag-${tag.name.toLowerCase().replace(/\s+/g, '-')}`}
                          >
                            <Ionicons
                              name={isSelected ? 'checkmark-circle' : 'ellipse-outline'}
                              size={16}
                              color={isSelected ? (tag.color || '#C9A962') : '#6E6E73'}
                            />
                            <Text style={[
                              styles.congratsTagText,
                              isSelected && { color: tag.color || '#C9A962' },
                            ]}>{tag.name}</Text>
                            {linkedCampaign && (
                              <View style={styles.congratsCampaignBadge}>
                                <Ionicons name="flash" size={10} color="#FF9500" />
                              </View>
                            )}
                          </TouchableOpacity>
                        );
                      })}
                    </View>
                  )}
                  {congratsSelectedTags.some(t => getCampaignForTag(t)) && (
                    <View style={styles.congratsCampaignNote}>
                      <Ionicons name="flash" size={16} color="#FF9500" />
                      <Text style={styles.congratsCampaignNoteText}>
                        Will auto-start: {congratsSelectedTags
                          .map(t => getCampaignForTag(t))
                          .filter(Boolean)
                          .map(c => c!.name)
                          .join(', ')}
                      </Text>
                    </View>
                  )}
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
                    <ActivityIndicator size="small" color={colors.text} />
                  ) : (
                    <>
                      <Ionicons name="sparkles" size={20} color={colors.text} />
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
                <Ionicons name="document-text" size={20} color={colors.textSecondary} />
              </View>
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Drafts Only</Text>
                <Text style={styles.modeDesc}>AI creates drafts but doesn't send</Text>
              </View>
              {aiMode === 'draft_only' && (
                <Ionicons name="checkmark-circle" size={24} color={colors.textSecondary} />
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
                  color={conversationStatus === 'closed' ? '#34C759' : colors.textSecondary} 
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
      <ChannelPicker
        message={channelPicker.message}
        phone={channelPicker.phone}
        email={channelPicker.email}
        link={channelPicker.link}
        onSent={channelPicker.onSent}
        visible={channelPicker.visible}
        onClose={channelPicker.close}
      />
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 0,
    backgroundColor: colors.background,
  },
  backButton: {
    padding: 4,
  },
  headerAvatar: {
    width: 36,
    height: 36,
    borderRadius: 10,
    marginLeft: 4,
  },
  headerAvatarPlaceholder: {
    width: 36,
    height: 36,
    borderRadius: 10,
    marginLeft: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerAvatarText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  headerInfo: {
    flex: 1,
    marginLeft: 8,
  },
  headerName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  headerPhone: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  settingsButton: {
    padding: 8,
  },
  modeBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    gap: 8,
    marginHorizontal: 12,
    marginTop: 4,
    borderRadius: 10,
    borderWidth: 1,
  },
  modeBannerText: {
    color: colors.textSecondary,
    fontSize: 15,
    fontWeight: '600',
    flex: 1,
  },
  modeSwitchButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  modeSwitchText: {
    color: colors.textSecondary,
    fontSize: 14,
    fontWeight: '600',
  },
  // Relationship Intel bar
  intelBar: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    justifyContent: 'space-between' as const,
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  intelBarExpanded: {
    borderBottomWidth: 0,
  },
  intelBarLeft: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: 8,
  },
  intelBarTitle: {
    fontSize: 15,
    fontWeight: '600' as const,
    color: '#C9A962',
  },
  intelBarMeta: {
    fontSize: 13,
    color: colors.textTertiary,
  },
  intelContent: {
    backgroundColor: colors.surface,
    paddingHorizontal: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  intelLoadingRow: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: 8,
    paddingVertical: 8,
  },
  intelLoadingText: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  intelSummaryText: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: 8,
  },
  intelMetaRow: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    justifyContent: 'space-between' as const,
  },
  intelMetaText: {
    fontSize: 13,
    color: colors.textTertiary,
  },
  intelRefreshBtn: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: 4,
  },
  intelRefreshText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '600' as const,
  },
  intelEmptyText: {
    fontSize: 15,
    color: colors.textTertiary,
    paddingVertical: 4,
  },
  emailPromptBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1A1A2E',
    paddingVertical: 10,
    paddingHorizontal: 14,
    gap: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A3E',
  },
  emailPromptInput: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 17,
    backgroundColor: colors.surface,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  emailPromptSave: {
    backgroundColor: '#C9A962',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  emailPromptSaveText: {
    color: colors.textPrimary,
    fontWeight: '700',
    fontSize: 16,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  messagesList: {
    padding: 12,
    flexGrow: 1,
    gap: 4,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 4,
  },
  messageContainer: {
    marginBottom: 4,
    paddingHorizontal: 4,
  },
  userMessageContainer: {
    alignItems: 'flex-end',
  },
  contactMessageContainer: {
    alignItems: 'flex-start',
  },
  senderLabel: {
    fontSize: 13,
    color: '#6E6E73',
    fontWeight: '500',
    marginBottom: 4,
    letterSpacing: 0.1,
  },
  senderLabelRight: {
    textAlign: 'right',
    paddingRight: 4,
  },
  senderLabelLeft: {
    textAlign: 'left',
    paddingLeft: 4,
  },
  messageBubble: {
    maxWidth: '80%',
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  userMessageBubble: {
    backgroundColor: colors.userBubbleBg,
    borderColor: colors.userBubbleBorder,
  },
  contactMessageBubble: {
    backgroundColor: colors.contactBubbleBg,
    borderColor: colors.contactBubbleBorder,
  },
  richMessageBubble: {
    borderLeftWidth: 3,
    backgroundColor: colors.contactBubbleBg,
    borderColor: colors.contactBubbleBorder,
  },
  richContentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  richContentIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  richContentLabel: {
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  aiIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 6,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#34C75920',
  },
  aiIndicatorText: {
    fontSize: 13,
    color: '#34C759',
    fontWeight: '600',
  },
  messageText: {
    fontSize: 17,
    color: colors.text,
    lineHeight: 21,
  },
  userMessageText: {
    color: colors.textPrimary,
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
    fontSize: 13,
    color: '#FF9500',
    fontWeight: '600',
  },
  personalSmsBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 6,
    alignSelf: 'flex-end',
  },
  personalSmsText: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  personalSmsHint: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: '#FF950010',
    borderTopWidth: 1,
    borderTopColor: '#FF950030',
  },
  personalSmsHintText: {
    fontSize: 14,
    color: '#FF9500',
    fontWeight: '500',
  },
  messageTime: {
    fontSize: 13,
    marginTop: 4,
  },
  userMessageTime: {
    color: colors.textPrimary,
    opacity: 0.7,
  },
  contactMessageTime: {
    color: colors.textSecondary,
  },
  aiLoadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 8,
    gap: 8,
  },
  aiLoadingText: {
    fontSize: 15,
    color: '#34C759',
    fontWeight: '500',
  },
  attachMenu: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 24,
    justifyContent: 'center',
  },
  attachOption: {
    alignItems: 'center',
    gap: 4,
  },
  attachOptionText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  attachButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inputWrapper: {
    flexDirection: 'row',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
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
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingLeft: 16,
    paddingRight: 8,
    paddingVertical: 8,
    minHeight: 40,
    maxHeight: 120,
  },
  inputField: {
    flex: 1,
    fontSize: 18,
    color: colors.textPrimary,
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
    borderTopColor: colors.border,
    alignItems: 'flex-end',
    gap: 8,
  },
  suggestButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 18,
    color: colors.textPrimary,
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
    backgroundColor: colors.surface,
  },
  
  // New Composer Box Styles
  composerContainer: {
    padding: 12,
    paddingBottom: 20,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  composerBox: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  mediaPreview: {
    padding: 12,
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
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
    fontSize: 14,
    color: colors.textSecondary,
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
    backgroundColor: colors.surface,
  },
  mediaImage: {
    width: 200,
    height: 200,
    borderRadius: 12,
    backgroundColor: colors.elevated,
  },
  mediaImageError: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  mediaErrorText: {
    color: colors.textSecondary,
    fontSize: 14,
    marginTop: 4,
  },
  mediaOnlyIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 4,
  },
  mediaOnlyText: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  composerInput: {
    fontSize: 18,
    color: colors.textPrimary,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
    textAlignVertical: 'top',
  },
  composerToolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
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
    backgroundColor: colors.elevated,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-start',
    paddingTop: 20,
  },
  templatesModal: {
    backgroundColor: colors.surface,
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
    borderBottomColor: colors.border,
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
    fontSize: 21,
    fontWeight: '700',
    color: colors.textPrimary,
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
    borderTopColor: colors.border,
  },
  modalCloseButton: {
    backgroundColor: colors.elevated,
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  modalCloseButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FF3B30',
  },
  emptyTemplates: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyTemplatesText: {
    fontSize: 18,
    color: colors.textSecondary,
    marginTop: 12,
  },
  modalSectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  modeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.elevated,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  modeOptionActive: {
    backgroundColor: colors.border,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  modeDesc: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  statusOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.elevated,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  // Settings Modal specific
  modalContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  templateItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.elevated,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  templatePreview: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  emptyReviews: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  emptyReviewsText: {
    fontSize: 18,
    color: colors.textSecondary,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  // Business Card Modal Styles
  cardModalContent: {
    padding: 20,
  },
  cardPreview: {
    alignItems: 'center',
    backgroundColor: colors.elevated,
    borderRadius: 16,
    padding: 24,
    marginBottom: 20,
  },
  cardPreviewTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: 12,
  },
  cardPreviewDesc: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  campaignPickerLabel: {
    fontSize: 17,
    fontWeight: '500',
    color: colors.textPrimary,
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
    backgroundColor: colors.elevated,
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
    fontSize: 16,
    color: colors.textSecondary,
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
    fontSize: 17,
    color: colors.textSecondary,
  },
  noCampaignsSubtext: {
    fontSize: 15,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  // Share Options Styles
  shareOptionsContainer: {
    marginTop: 20,
    gap: 12,
  },
  shareOptionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.elevated,
    borderRadius: 14,
    padding: 16,
  },
  shareOptionIcon: {
    width: 50,
    height: 50,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  shareOptionContent: {
    flex: 1,
  },
  shareOptionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  shareOptionDesc: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  landingPageOptions: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  landingPageOptionsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    gap: 12,
  },
  landingPageOptionsTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  // Photo Options Modal Styles (for Web)
  // Photo Options (native action sheet style for PWA)
  actionSheetOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  actionSheetContainer: { paddingHorizontal: 8, paddingBottom: 8 },
  actionSheetGroup: {
    backgroundColor: colors.surface, borderRadius: 14, overflow: 'hidden', marginBottom: 8,
  },
  actionSheetButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 18, gap: 10,
  },
  actionSheetButtonText: { fontSize: 21, color: '#007AFF', fontWeight: '400' },
  actionSheetDivider: { height: 1, backgroundColor: colors.border },
  actionSheetCancel: {
    backgroundColor: colors.surface, borderRadius: 14, paddingVertical: 18, alignItems: 'center',
  },
  actionSheetCancelText: { fontSize: 21, fontWeight: '600', color: '#007AFF' },
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
    backgroundColor: colors.surface,
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
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
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
    backgroundColor: colors.elevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  congratsPhotoText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 10,
  },
  congratsLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 8,
    marginTop: 8,
  },
  cardTypeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: colors.elevated,
    backgroundColor: colors.elevated,
  },
  cardTypeChipText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  congratsInput: {
    backgroundColor: colors.elevated,
    borderRadius: 12,
    padding: 14,
    fontSize: 18,
    color: colors.textPrimary,
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
    fontSize: 15,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  // Congrats Tag Picker Styles
  congratsTagSection: {
    marginBottom: 12,
  },
  congratsTagEmpty: {
    color: '#6E6E73',
    fontSize: 15,
    textAlign: 'center',
    paddingVertical: 12,
  },
  congratsTagGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  congratsTagChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.elevated,
    borderWidth: 1,
    borderColor: colors.border,
  },
  congratsTagText: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  congratsCampaignBadge: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#FF950020',
    alignItems: 'center',
    justifyContent: 'center',
  },
  congratsCampaignNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#FF950015',
    borderRadius: 10,
    padding: 10,
    marginTop: 10,
  },
  congratsCampaignNoteText: {
    fontSize: 14,
    color: '#FF9500',
    flex: 1,
  },
  // Quick Contact Panel Styles
  quickContactPanel: {
    backgroundColor: colors.surface,
    marginHorizontal: 12,
    marginTop: 12,
    borderRadius: 12,
    padding: 12,
  },
  quickContactHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  quickContactTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  quickContactClose: {
    padding: 4,
  },
  quickContactContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  quickContactPhotoContainer: {
    position: 'relative',
  },
  quickContactPhoto: {
    width: 60,
    height: 60,
    borderRadius: 30,
  },
  quickContactPhotoPlaceholder: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.elevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickContactPhotoBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.border,
  },
  quickContactFields: {
    flex: 1,
    gap: 8,
  },
  quickContactInput: {
    backgroundColor: colors.elevated,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 17,
    color: colors.textPrimary,
  },
  quickContactTagsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
    gap: 8,
  },
  quickContactTagsLabel: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  quickContactTagsScroll: {
    flex: 1,
  },
  quickContactTag: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    marginRight: 8,
    gap: 4,
  },
  quickContactTagText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  quickContactAddTag: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    backgroundColor: colors.elevated,
    gap: 4,
  },
  quickContactAddTagText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '500',
  },
  quickContactActions: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  quickContactActionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.elevated,
    borderRadius: 8,
    paddingVertical: 10,
    gap: 6,
  },
  quickContactSaveBtn: {
    backgroundColor: '#007AFF',
  },
  quickContactActionText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  quickContactHint: {
    fontSize: 13,
    color: '#6E6E73',
    textAlign: 'center',
    marginTop: 10,
    fontStyle: 'italic',
  },
  quickContactCollapsed: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    marginHorizontal: 12,
    marginTop: 8,
    paddingVertical: 10,
    borderRadius: 8,
    gap: 8,
  },
  quickContactCollapsedText: {
    fontSize: 15,
    color: '#007AFF',
    fontWeight: '500',
  },
  // Tag Picker Modal Styles
  tagPickerOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  tagPickerContainer: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: '60%',
  },
  tagPickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tagPickerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  tagPickerList: {
    padding: 8,
  },
  tagPickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 8,
    marginBottom: 4,
  },
  tagPickerItemSelected: {
    backgroundColor: '#007AFF20',
  },
  tagPickerDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 12,
  },
  tagPickerItemText: {
    flex: 1,
    fontSize: 17,
    color: colors.textPrimary,
  },
  tagPickerEmpty: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    padding: 20,
  },
  tagPickerDone: {
    backgroundColor: '#007AFF',
    margin: 16,
    padding: 14,
    borderRadius: 10,
    alignItems: 'center',
  },
  tagPickerDoneText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  // Create User Section Styles (Admin Only)
  createUserSection: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  createUserToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  createUserToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  createUserCheckbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  createUserCheckboxActive: {
    backgroundColor: '#34C759',
    borderColor: '#34C759',
  },
  createUserToggleText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  createUserToggleHint: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 1,
  },
  createUserFields: {
    marginTop: 12,
    gap: 10,
  },
  createUserInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.elevated,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  createUserInput: {
    flex: 1,
    fontSize: 17,
    color: colors.textPrimary,
  },
  createUserRoleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  createUserRoleLabel: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  createUserRoleOptions: {
    flex: 1,
    flexDirection: 'row',
    gap: 8,
  },
  createUserRoleBtn: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: colors.elevated,
    alignItems: 'center',
  },
  createUserRoleBtnActive: {
    backgroundColor: '#007AFF',
  },
  createUserRoleBtnText: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  createUserRoleBtnTextActive: {
    color: colors.textPrimary,
  },
});
