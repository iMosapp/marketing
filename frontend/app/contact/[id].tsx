import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { Audio } from 'expo-av';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Swipeable } from 'react-native-gesture-handler';
import { format, differenceInDays, differenceInMonths, differenceInYears } from 'date-fns';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { contactsAPI, campaignsAPI, tagsAPI, messagesAPI } from '../../services/api';
import api from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import { useToast } from '../../components/common/Toast';
import VoiceInput from '../../components/VoiceInput';

const IS_WEB = Platform.OS === 'web';

interface CustomDateField {
  name: string;
  date: Date | null;
}

interface ContactEvent {
  event_type: string;
  icon: string;
  color: string;
  title: string;
  description: string;
  timestamp: string;
  category: string;
  direction?: string;
  has_photo?: boolean;
  full_content?: string;
  link?: string;
  channel?: string;
  subject?: string;
}

interface ContactStats {
  total_touchpoints: number;
  messages_sent: number;
  campaigns: number;
  cards_sent: number;
  broadcasts: number;
  custom_events: number;
  link_clicks: number;
  created_at: string | null;
}

// ===== HELPER: Time in System =====
function getTimeInSystem(createdAt: string | null): string {
  if (!createdAt) return '0';
  const created = new Date(createdAt);
  const now = new Date();
  const years = differenceInYears(now, created);
  if (years >= 1) return `${years}`;
  const months = differenceInMonths(now, created);
  if (months >= 1) return `${months}`;
  const days = differenceInDays(now, created);
  return `${Math.max(days, 0)}`;
}

function getTimeInSystemLabel(createdAt: string | null): string {
  if (!createdAt) return 'day';
  const created = new Date(createdAt);
  const now = new Date();
  const years = differenceInYears(now, created);
  if (years >= 1) return years === 1 ? 'year' : 'year';
  const months = differenceInMonths(now, created);
  if (months >= 1) return months === 1 ? 'month' : 'month';
  const days = differenceInDays(now, created);
  if (days === 1) return 'day';
  return 'day';
}

function formatEventTime(timestamp: string): string {
  if (!timestamp) return '';
  try {
    const date = new Date(timestamp);
    const now = new Date();
    // Compare by calendar date in local timezone
    const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dayDiff = Math.round((nowDay.getTime() - dateDay.getTime()) / 86400000);
    // Future dates
    if (dayDiff < 0) {
      if (dayDiff === -1) {
        return 'Tomorrow at ' + format(date, 'h:mm a');
      }
      return format(date, 'MMM d \'at\' h:mm a');
    }
    // Today: show time only
    if (dayDiff === 0) {
      return format(date, 'h:mm a');
    }
    // Yesterday
    if (dayDiff === 1) {
      return 'Yesterday at ' + format(date, 'h:mm a');
    }
    // Within this year
    if (date.getFullYear() === now.getFullYear()) {
      return format(date, 'MMM d \'at\' h:mm a');
    }
    // Older
    return format(date, 'MMM d, yyyy \'at\' h:mm a');
  } catch {
    return '';
  }
}

// Format date-only fields using UTC to prevent timezone from shifting the day
function formatDateUTC(dateStr: string, fmt: string = 'MMM d'): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    // Create local date from UTC components to avoid timezone shift
    const local = new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
    return format(local, fmt);
  } catch { return ''; }
}


// ===== EVENT TITLE FALLBACK =====
const EVENT_TYPE_LABELS: Record<string, string> = {
  email_sent: 'Email Sent',
  personal_sms: 'Personal SMS',
  digital_card_sent: 'Digital Card Shared',
  review_request_sent: 'Review Invite Sent',
  congrats_card_sent: 'Congrats Card Sent',
  birthday_card_sent: 'Birthday Card Sent',
  thank_you_card_sent: 'Thank You Card Sent',
  vcard_sent: 'vCard Shared',
  showcase_shared: 'Showcase Shared',
  link_page_shared: 'Link Page Shared',
  call_placed: 'Call Placed',
  new_contact: 'Contact Created',
  link_click: 'Link Clicked',
  link_clicked: 'Link Clicked',
  voice_note: 'Voice Note',
  note_updated: 'Note Updated',
  customer_reply: 'Customer Reply',
  congrats_card_viewed: 'Viewed Congrats Card',
  congrats_card_download: 'Downloaded Card',
  congrats_card_share: 'Shared Card',
  review_submitted: 'Left a Review',
  review_link_clicked: 'Clicked Review Link',
  digital_card_viewed: 'Viewed Digital Card',
  review_page_viewed: 'Viewed Review Page',
  showcase_viewed: 'Viewed Showcase',
  link_page_viewed: 'Viewed Link Page',
};

function getEventTitle(evt: ContactEvent): string {
  if (evt.title) return evt.title;
  return EVENT_TYPE_LABELS[evt.event_type] || evt.event_type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Activity';
}

// ===== QUICK ACTION CONFIG =====
const QUICK_ACTIONS = [
  { key: 'sms', icon: 'chatbubble', label: 'SMS', color: '#34C759' },
  { key: 'call', icon: 'call', label: 'Call', color: '#32ADE6' },
  { key: 'email', icon: 'mail', label: 'Email', color: '#AF52DE' },
  { key: 'review', icon: 'star', label: 'Review', color: '#FFD60A' },
  { key: 'card', icon: 'card', label: 'Card', color: '#007AFF' },
  { key: 'gift', icon: 'gift', label: 'Congrats', color: '#C9A962' },
];

// ===== EVENT ICON MAP =====
const EVENT_CATEGORY_ICON: Record<string, { icon: string; color: string }> = {
  message: { icon: 'chatbubble', color: '#007AFF' },
  campaign: { icon: 'rocket', color: '#AF52DE' },
  card: { icon: 'card', color: '#C9A962' },
  broadcast: { icon: 'megaphone', color: '#FF2D55' },
  review: { icon: 'star', color: '#FFD60A' },
  voice_note: { icon: 'mic', color: '#34C759' },
  note: { icon: 'document-text', color: '#FF9F0A' },
  customer_activity: { icon: 'arrow-down', color: '#30D158' },
  custom: { icon: 'flag', color: '#8E8E93' },
};

// Renders relationship intel text with bold section headers and bullet formatting
const SECTION_HEADERS = ['Quick Take', 'Key Facts', 'Communication Patterns', 'Personal Notes', 'Before Your Next Interaction'];

const IntelRenderer = ({ text }: { text: string }) => {
  const { colors } = useThemeStore();
  const lines = text.split('\n').filter(l => l.trim());
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    const trimmed = line.trim()
      .replace(/\*\*/g, '');  // strip any leftover markdown bold

    const isHeader = SECTION_HEADERS.some(h => trimmed.toLowerCase().startsWith(h.toLowerCase()));
    const isBullet = trimmed.startsWith('-') || trimmed.startsWith('•');

    if (isHeader) {
      elements.push(
        <Text key={i} style={{ color: colors.text, fontSize: 14, fontWeight: '700', marginTop: i > 0 ? 14 : 0, marginBottom: 4 }}>
          {trimmed.replace(/:$/, '')}
        </Text>
      );
    } else if (isBullet) {
      const bulletText = trimmed.replace(/^[-•]\s*/, '');
      elements.push(
        <View key={i} style={{ flexDirection: 'row', paddingLeft: 4, marginBottom: 3 }}>
          <Text style={{ color: colors.textTertiary, fontSize: 13, marginRight: 6 }}>{'\u2022'}</Text>
          <Text style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19, flex: 1 }}>{bulletText}</Text>
        </View>
      );
    } else {
      elements.push(
        <Text key={i} style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19, marginBottom: 4 }}>
          {trimmed}
        </Text>
      );
    }
  });

  return <View>{elements}</View>;
};

export default function ContactDetailScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const { id, prefill } = useLocalSearchParams();
  const user = useAuthStore((state) => state.user);
  const isNewContact = id === 'new';
  const { showToast } = useToast();

  // Core state
  const [contact, setContact] = useState({
    first_name: '', last_name: '', phone: '', email: '',
    photo: null as string | null, photo_thumbnail: null as string | null,
    notes: '', vehicle: '', tags: [] as string[],
    referred_by: null as string | null, referred_by_name: null as string | null,
    referral_notes: '', referral_count: 0,
    birthday: null as Date | null, anniversary: null as Date | null,
    date_sold: null as Date | null, custom_dates: [] as CustomDateField[],
    address_street: '', address_city: '', address_state: '', address_zip: '', address_country: '',
  });
  const [loading, setLoading] = useState(!isNewContact);
  const [saving, setSaving] = useState(false);
  const [originalNotes, setOriginalNotes] = useState('');
  // Full photo viewer & gallery
  const [showPhotoViewer, setShowPhotoViewer] = useState(false);
  const [fullPhoto, setFullPhoto] = useState<string | null>(null);
  const [fullPhotoLoading, setFullPhotoLoading] = useState(false);
  const [allPhotos, setAllPhotos] = useState<any[]>([]);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);
  const [isEditing, setIsEditing] = useState(isNewContact);

  // Voice notes
  const [voiceNotes, setVoiceNotes] = useState<any[]>([]);

  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [voiceNotesLoading, setVoiceNotesLoading] = useState(false);
  const [uploadingVoiceNote, setUploadingVoiceNote] = useState(false);
  const [playingNoteId, setPlayingNoteId] = useState<string | null>(null);
  const [showAllNotes, setShowAllNotes] = useState(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const recordingTimerRef = React.useRef<any>(null);
  const scrollRef = React.useRef<ScrollView>(null);
  const MAX_RECORDING_SECONDS = 120;

  // AI Relationship Intel
  const [intelData, setIntelData] = useState<any>(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [intelGenerating, setIntelGenerating] = useState(false);
  const [showIntel, setShowIntel] = useState(false);

  // Events & stats
  const [events, setEvents] = useState<ContactEvent[]>([]);
  const [stats, setStats] = useState<ContactStats>({
    total_touchpoints: 0, messages_sent: 0, campaigns: 0,
    cards_sent: 0, broadcasts: 0, custom_events: 0, link_clicks: 0, created_at: null,
  });
  const [eventsLoading, setEventsLoading] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState<Record<number, boolean>>({});
  const [showAllEvents, setShowAllEvents] = useState(false);
  const [feedSearch, setFeedSearch] = useState('');
  const INITIAL_EVENT_COUNT = 5;

  // Tab state for Feed vs Details
  const [contactTab, setContactTab] = useState<'feed' | 'details'>('feed');

  // Suggested actions & log reply
  const [suggestedActions, setSuggestedActions] = useState<any[]>([]);

  // Toolbar modals (mirroring inbox)
  const [showTemplates, setShowTemplates] = useState(false);
  const [showReviewLinks, setShowReviewLinks] = useState(false);
  const [showBusinessCard, setShowBusinessCard] = useState(false);
  const [showLandingPageOptions, setShowLandingPageOptions] = useState(false);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(null);
  const [showPhotoOptionsModal, setShowPhotoOptionsModal] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState<any>(null);
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  const [voiceTranscribing, setVoiceTranscribing] = useState(false);
  const voiceRecordingRef = useRef<any>(null);
  const [templates, setTemplates] = useState<any[]>([]);
  const [reviewLinks, setReviewLinks] = useState<Record<string, string>>({});
  const [storeSlug, setStoreSlug] = useState('');
  const [customLinkName, setCustomLinkName] = useState('');

  // Action progress tracker
  const [actionProgress, setActionProgress] = useState<any[]>([]);
  const [progressCompleted, setProgressCompleted] = useState(0);
  const [progressTotal, setProgressTotal] = useState(0);

  // Computed: filtered events for search (must come after state declarations)
  const feedQuery = feedSearch.toLowerCase().trim();
  const filteredEvents = feedQuery
    ? events.filter(e =>
        (e.title || '').toLowerCase().includes(feedQuery) ||
        (e.description || '').toLowerCase().includes(feedQuery) ||
        (e.event_type || '').toLowerCase().includes(feedQuery) ||
        (getEventTitle(e)).toLowerCase().includes(feedQuery)
      )
    : events;
  const visibleEvents = showAllEvents ? filteredEvents : filteredEvents.slice(0, INITIAL_EVENT_COUNT);

  // Modals
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [activeDateField, setActiveDateField] = useState<string | null>(null);
  const [activeDateLabel, setActiveDateLabel] = useState('');
  const [tempDate, setTempDate] = useState(new Date());
  const [webMonth, setWebMonth] = useState(new Date().getMonth());
  const [webDay, setWebDay] = useState(new Date().getDate());
  const [webYear, setWebYear] = useState(new Date().getFullYear());
  const [newCustomDateName, setNewCustomDateName] = useState('');
  const [pendingCustomDate, setPendingCustomDate] = useState<Date | null>(null);
  const [showCustomDateLabel, setShowCustomDateLabel] = useState(false);
  const [showReferralPicker, setShowReferralPicker] = useState(false);
  const [allContacts, setAllContacts] = useState<any[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  const [showCampaignPicker, setShowCampaignPicker] = useState(false);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [contactEnrollments, setContactEnrollments] = useState<any[]>([]);
  const [availableTags, setAvailableTags] = useState<any[]>([]);
  const [showTagPicker, setShowTagPicker] = useState(false);
  const [tagSearch, setTagSearch] = useState('');
  const [referrals, setReferrals] = useState<any[]>([]);

  // Composer state (inline inbox)
  const [composerMessage, setComposerMessage] = useState('');
  const [composerMode, setComposerMode] = useState<'sms' | 'email'>('sms');
  const [composerSending, setComposerSending] = useState(false);

  // Populate composer from query param (e.g. returning from create-card)
  useEffect(() => {
    if (prefill && typeof prefill === 'string') {
      setComposerMessage(prefill);
    }
  }, [prefill]);
  const [aiSuggestion, setAiSuggestion] = useState('');
  const [loadingAI, setLoadingAI] = useState(false);
  const [showAISuggestion, setShowAISuggestion] = useState(false);
  const [showLogReply, setShowLogReply] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [replyPhoto, setReplyPhoto] = useState<string | null>(null);
  const [submittingReply, setSubmittingReply] = useState(false);
  const [collapsedDateGroups, setCollapsedDateGroups] = useState<Record<string, boolean>>({});
  const [editingAutomation, setEditingAutomation] = useState<{ field: string; label: string; color: string; value: string } | null>(null);

  // ===== DATA LOADING =====
  useEffect(() => {
    if (!isNewContact && user) {
      loadContact();
      loadEvents();
      loadSuggestedActions();
      loadActionProgress();
      loadReferrals();
      loadCampaignsAndEnrollments();
      loadTags();
    }
  }, [id, user]);

  // Auto-refresh events when returning from call screen, inbox, etc.
  useFocusEffect(
    useCallback(() => {
      if (!isNewContact && user) {
        loadEvents();
      }
    }, [id, user])
  );

  // Periodic polling for real-time activity updates (every 15 seconds)
  useEffect(() => {
    if (isNewContact || !user) return;
    const interval = setInterval(() => {
      loadEvents();
    }, 15000);
    return () => clearInterval(interval);
  }, [id, user, isNewContact]);

  const loadContact = async () => {
    if (!user) return;
    try {
      setLoading(true);
      const data = await contactsAPI.getById(user._id, id as string);
      const parseDate = (d: any): Date | null => d ? new Date(d) : null;
      const customDates = (data.custom_dates || []).map((cd: any) => ({
        name: cd.name, date: parseDate(cd.date),
      }));
      setContact({
        first_name: data.first_name || '', last_name: data.last_name || '',
        phone: data.phone || '', email: data.email || '',
        photo: data.photo_thumbnail || data.photo_url || data.photo || null,
        photo_thumbnail: data.photo_thumbnail || null,
        notes: data.notes || '', vehicle: data.vehicle || '',
        tags: data.tags || [],
        referred_by: data.referred_by || null,
        referred_by_name: data.referred_by_name || null,
        referral_notes: data.referral_notes || '',
        referral_count: data.referral_count || 0,
        birthday: parseDate(data.birthday), anniversary: parseDate(data.anniversary),
        date_sold: parseDate(data.date_sold) || parseDate(data.purchase_date),
        custom_dates: customDates,
        address_street: data.address_street || '',
        address_city: data.address_city || '',
        address_state: data.address_state || '',
        address_zip: data.address_zip || '',
        address_country: data.address_country || '',
      });
    } catch (e) {
      console.error('Failed to load contact:', e);
    } finally {
      setLoading(false);
    }
  };

  // Track original notes for change detection
  React.useEffect(() => {
    if (contact.notes !== undefined && !loading && !isNewContact) {
      setOriginalNotes(prev => prev || contact.notes);
    }
  }, [contact.notes, loading]);

  const loadEvents = async () => {
    if (!user || isNewContact) return;
    try {
      setEventsLoading(true);
      const [evtsResp, statsResp] = await Promise.all([
        contactsAPI.getEvents(user._id, id as string),
        contactsAPI.getStats(user._id, id as string),
      ]);
      setEvents(evtsResp.events || []);
      setStats(statsResp);
    } catch (e) {
      console.error('Failed to load events:', e);
    } finally {
      setEventsLoading(false);
    }
  };

  const loadSuggestedActions = async () => {
    if (!user || isNewContact) return;
    try {
      const resp = await api.get(`/contacts/${user._id}/${id}/suggested-actions`);
      setSuggestedActions(resp.data.actions || []);
    } catch (e) {
      console.error('Failed to load suggested actions:', e);
    }
  };

  const loadActionProgress = async () => {
    if (!user || isNewContact) return;
    try {
      const resp = await api.get(`/contacts/${user._id}/${id}/action-progress`);
      setActionProgress(resp.data.progress || []);
      setProgressCompleted(resp.data.completed || 0);
      setProgressTotal(resp.data.total || 0);
    } catch (e) {
      console.error('Failed to load action progress:', e);
    }
  };

  const handleLogReply = async () => {
    if (!user || (!replyText.trim() && !replyPhoto)) return;
    try {
      setSubmittingReply(true);
      await api.post(`/contacts/${user._id}/${id}/log-reply`, {
        text: replyText.trim(),
        photo: replyPhoto,
      });
      setReplyText('');
      setReplyPhoto(null);
      setShowLogReply(false);
      showToast('Customer reply logged!');
      loadEvents();
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to log reply');
    } finally {
      setSubmittingReply(false);
    }
  };

  const pickReplyPhoto = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        quality: 0.6,
        base64: true,
      });
      if (!result.canceled && result.assets[0]?.base64) {
        const mime = result.assets[0].mimeType || 'image/jpeg';
        setReplyPhoto(`data:${mime};base64,${result.assets[0].base64}`);
      }
    } catch (e) {
      console.error('Photo pick error:', e);
    }
  };

  // === Toolbar functions (mirroring inbox) ===
  const loadToolbarData = async () => {
    if (!user) return;
    try {
      const [templatesRes, storeRes] = await Promise.all([
        api.get(`/messages/templates/${user._id}`).catch(() => ({ data: [] })),
        api.get(`/store/${user.org_id || user._id}`).catch(() => ({ data: null })),
      ]);
      setTemplates(templatesRes.data || []);
      if (storeRes.data) {
        setStoreSlug(storeRes.data.slug || '');
        setReviewLinks(storeRes.data.review_links || {});
        setCustomLinkName(storeRes.data.custom_link_name || '');
      }
    } catch (e) {
      console.error('Toolbar data load error:', e);
    }
  };

  React.useEffect(() => {
    if (user && !isNewContact) loadToolbarData();
  }, [user]);

  const handleAttachPhoto = () => {
    if (IS_WEB) {
      setShowPhotoOptionsModal(true);
      return;
    }
    Alert.alert('Add Photo', undefined, [
      { text: 'Photo Library', onPress: async () => {
        const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: true, quality: 0.7 });
        if (!result.canceled && result.assets[0]?.uri) setSelectedMedia(result.assets[0]);
      }},
      { text: 'Take Photo', onPress: async () => {
        const result = await ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.7 });
        if (!result.canceled && result.assets[0]?.uri) setSelectedMedia(result.assets[0]);
      }},
      { text: 'Create Card', onPress: () => setShowCardTemplatePicker(true) },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  const insertReviewLink = (platformId: string, url: string, platformName: string) => {
    const firstName = contact.first_name || 'there';
    const reviewMessage = `Hey ${firstName}! We'd love your feedback. Leave us a review here: ${url}`;
    setShowReviewLinks(false);
    setComposerMessage(reviewMessage);
  };

  const openBusinessCardPicker = async () => {
    if (!user?._id) return;
    setLoadingCampaigns(true);
    setShowBusinessCard(true);
    try {
      const response = await api.get(`/card/campaigns/${user._id}`);
      setCampaigns(response.data);
    } catch (error) {
      setCampaigns([]);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const sendBusinessCardLink = () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imosapp.com';
    let cardUrl = `${baseUrl}/card/${user._id}`;
    const params: string[] = [];
    if (selectedCampaign) params.push(`campaign=${selectedCampaign}`);
    if (id) params.push(`contact=${id}`);
    if (params.length > 0) cardUrl += `?${params.join('&')}`;
    const firstName = contact.first_name || 'there';
    const cardMessage = `Hey ${firstName}! Here's my digital business card: ${cardUrl}`;
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    setSelectedCampaign(null);
    setComposerMessage(cardMessage);
  };

  const sendVCardLink = () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imosapp.com';
    const vcardUrl = `${baseUrl}/api/card/vcard/${user._id}`;
    const firstName = contact.first_name || 'there';
    const cardMessage = `Hey ${firstName}! Tap here to save my contact info directly to your phone: ${vcardUrl}`;
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    setSelectedCampaign(null);
    setComposerMessage(cardMessage);
  };

  const sendShowcaseLink = () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imosapp.com';
    const showcaseUrl = `${baseUrl}/showcase/${user._id}`;
    const firstName = contact.first_name || 'there';
    const msg = `Hey ${firstName}! Check out some of our happy customers: ${showcaseUrl}`;
    setShowBusinessCard(false);
    setComposerMessage(msg);
  };

  const sendLinkPageLink = async () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imosapp.com';
    const firstName = contact.first_name || 'there';
    try {
      const resp = await api.get(`/linkpage/user/${user._id}`);
      const username = resp.data?.username;
      if (username) {
        const url = `${baseUrl}/l/${username}`;
        const msg = `Hey ${firstName}! Here are all my links: ${url}`;
        setShowBusinessCard(false);
        setComposerMessage(msg);
      } else {
        showSimpleAlert('Not Set Up', 'Set up your Link Page in Settings first');
      }
    } catch {
      showSimpleAlert('Not Set Up', 'Set up your Link Page in Settings first');
    }
  };

  const selectTemplate = (template: { _id: string; name: string; content: string; category?: string }) => {
    const firstName = contact.first_name || 'there';
    const content = template.content.replace(/{name}/g, firstName);
    setComposerMessage(content);
    setShowTemplates(false);
  };

  const handleVoiceToText = async () => {
    try {
      if (isVoiceRecording) {
        setIsVoiceRecording(false);
        if (voiceRecordingRef.current) {
          setVoiceTranscribing(true);
          await voiceRecordingRef.current.stopAndUnloadAsync();
          const uri = voiceRecordingRef.current.getURI();
          voiceRecordingRef.current = null;
          if (uri) {
            const formData = new FormData();
            if (IS_WEB) {
              const response = await fetch(uri);
              const blob = await response.blob();
              formData.append('file', blob, 'recording.webm');
            } else {
              formData.append('file', { uri, type: 'audio/m4a', name: 'recording.m4a' } as any);
            }
            try {
              const response = await api.post('/voice/transcribe', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
              });
              if (response.data.success && response.data.text) {
                setComposerMessage(prev => prev ? `${prev} ${response.data.text}` : response.data.text);
              }
            } catch (error) {
              console.error('Transcription error:', error);
            }
          }
          setVoiceTranscribing(false);
        }
      } else {
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          showSimpleAlert('Permission Denied', 'Microphone permission is required.');
          return;
        }
        await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
        const recordingOptions = IS_WEB 
          ? { ...Audio.RecordingOptionsPresets.HIGH_QUALITY, isMeteringEnabled: false, web: { mimeType: 'audio/webm;codecs=opus', bitsPerSecond: 128000 } }
          : Audio.RecordingOptionsPresets.HIGH_QUALITY;
        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync(recordingOptions);
        await recording.startAsync();
        voiceRecordingRef.current = recording;
        setIsVoiceRecording(true);
      }
    } catch (error) {
      console.error('Voice recording error:', error);
      setIsVoiceRecording(false);
      setVoiceTranscribing(false);
    }
  };

  const handleSuggestedAction = (action: any) => {
    if (!contact.phone && (action.action === 'sms' || action.action === 'call')) {
      showSimpleAlert('Missing Info', 'No phone number available');
      return;
    }
    const threadParams = `contact_name=${encodeURIComponent(contact.first_name + ' ' + (contact.last_name || ''))}&contact_phone=${encodeURIComponent(contact.phone || '')}&contact_email=${encodeURIComponent(contact.email || '')}`;
    
    switch (action.action) {
      case 'sms':
        router.push(`/thread/${id}?${threadParams}&mode=sms&prefill=${encodeURIComponent(action.suggested_message || '')}`);
        break;
      case 'congrats':
        router.push(`/thread/${id}?${threadParams}&mode=congrats`);
        break;
      case 'email':
        router.push(`/thread/${id}?${threadParams}&mode=email&prefill=${encodeURIComponent(action.suggested_message || '')}`);
        break;
      default:
        router.push(`/thread/${id}?${threadParams}&mode=sms&prefill=${encodeURIComponent(action.suggested_message || '')}`);
    }
  };

  const loadReferrals = async () => {
    if (!user || isNewContact) return;
    try {
      const data = await contactsAPI.getReferrals(user._id, id as string);
      setReferrals(data || []);
    } catch (e) { console.error(e); }
  };

  const loadCampaignsAndEnrollments = async () => {
    if (!user || isNewContact) return;
    try {
      const campaignsData = await campaignsAPI.getAll(user._id);
      setCampaigns(campaignsData.filter((c: any) => c.active));
      const allEnrollments: any[] = [];
      for (const campaign of campaignsData) {
        const enrollments = await campaignsAPI.getEnrollments(user._id, campaign._id);
        const ce = enrollments.find((e: any) => e.contact_id === id);
        if (ce) {
          allEnrollments.push({
            ...ce, campaign_name: campaign.name,
            campaign_type: campaign.type, total_steps: campaign.sequences?.length || 0,
          });
        }
      }
      setContactEnrollments(allEnrollments);
    } catch (e) { console.error(e); }
  };

  const loadTags = async () => {
    if (!user) return;
    try { setAvailableTags(await tagsAPI.getAll(user._id)); } catch (e) { console.error(e); }
  };

  const loadAllContacts = async () => {
    if (!user) return;
    try {
      const data = await contactsAPI.getAll(user._id);
      setAllContacts(data.filter((c: any) => c._id !== id));
    } catch (e) { console.error(e); }
  };

  // ===== SAVE / DELETE =====
  const handleSave = async () => {
    if (!contact.first_name || !contact.phone) {
      showSimpleAlert('Error', 'Name and phone are required');
      return;
    }
    if (!user) return;
    try {
      setSaving(true);
      if (isNewContact) {
        await contactsAPI.create(user._id, contact);
      } else {
        await contactsAPI.update(user._id, id as string, contact);
        // Log note change to activity feed
        if (contact.notes && contact.notes.trim() !== originalNotes.trim()) {
          try {
            await contactsAPI.logEvent(user._id, id as string, {
              event_type: 'note_updated',
              title: 'Note Updated',
              description: contact.notes.slice(0, 300),
              channel: 'note',
              category: 'note',
              icon: 'document-text',
              color: '#FF9F0A',
            });
            setOriginalNotes(contact.notes);
            loadEvents();
          } catch (e) { /* non-critical */ }
        }
      }
      showToast('Contact saved!');
      if (isNewContact) {
        router.back();
      } else {
        setIsEditing(false);
      }
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    if (isNewContact || !user) return;
    showConfirm('Delete Contact', `Delete "${contact.first_name}"? This cannot be undone.`, async () => {
      try {
        await contactsAPI.delete(user._id, id as string);
        showToast('Contact deleted');
        router.back();
      } catch (e: any) {
        showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to delete');
      }
    });
  };

  // ===== QUICK ACTIONS =====
  const handleQuickAction = (key: string) => {
    if (!contact.phone && (key === 'sms' || key === 'call')) {
      showSimpleAlert('Missing Info', 'No phone number available');
      return;
    }
    const contactEmail = contact.email || contact.email_work || '';
    if (!contactEmail && key === 'email') {
      showSimpleAlert('Missing Info', 'No email address available');
      return;
    }
    
    // Build thread URL with contact info  - always include both email fields
    const threadParams = `contact_name=${encodeURIComponent(contact.first_name + ' ' + (contact.last_name || ''))}&contact_phone=${encodeURIComponent(contact.phone || '')}&contact_email=${encodeURIComponent(contactEmail)}`;
    
    switch (key) {
      case 'sms':
        router.push(`/thread/${id}?${threadParams}&mode=sms`);
        break;
      case 'call':
        router.push(`/call-screen?contact_id=${id}&contact_name=${encodeURIComponent((contact.first_name || '') + ' ' + (contact.last_name || ''))}&phone=${encodeURIComponent(contact.phone)}`);
        break;
      case 'email':
        router.push(`/thread/${id}?${threadParams}&mode=email`);
        break;
      case 'review':
        router.push(`/thread/${id}?${threadParams}&mode=review`);
        break;
      case 'card':
        router.push(`/thread/${id}?${threadParams}&mode=card`);
        break;
      case 'gift':
        router.push(`/thread/${id}?${threadParams}&mode=congrats`);
        break;
    }
  };

  // ===== COMPOSER: Send message directly from contact page =====
  const handleComposerSend = async (textOverride?: string) => {
    const content = textOverride || composerMessage.trim();
    if (!content || !user) return;
    
    const contactEmail = contact.email || '';
    if (composerMode === 'email' && !contactEmail) {
      showSimpleAlert('Missing Info', 'No email address available for this contact');
      return;
    }
    if (composerMode === 'sms' && !contact.phone) {
      showSimpleAlert('Missing Info', 'No phone number available for this contact');
      return;
    }
    
    setComposerSending(true);
    try {
      // Create or get existing conversation for this contact
      const conv = await messagesAPI.createConversation(user._id, {
        contact_id: id as string,
        contact_phone: contact.phone || undefined,
      });
      const conversationId = conv._id || conv.id;
      
      if (composerMode === 'sms') {
        // For SMS: Use personal SMS flow  - log the message server-side, then open native SMS app
        await messagesAPI.send(user._id, {
          conversation_id: conversationId,
          content,
          channel: 'sms_personal',
        });
        
        // Open native SMS app with the message pre-filled
        if (IS_WEB && typeof window !== 'undefined') {
          const ua = window.navigator.userAgent.toLowerCase();
          const isIos = /iphone|ipad|ipod/.test(ua);
          const sep = isIos ? '&' : '?';
          const smsUrl = `sms:${encodeURIComponent(contact.phone || '')}${sep}body=${encodeURIComponent(content)}`;
          window.open(smsUrl, '_self');
        }
        
        showToast('Message logged & SMS app opened!');
      } else {
        // Email: send directly via Resend
        await messagesAPI.send(user._id, {
          conversation_id: conversationId,
          content,
          channel: 'email',
        });
        showToast('Email sent!');
      }
      
      setComposerMessage('');
      setShowAISuggestion(false);
      setAiSuggestion('');
      // Refresh events to show the new message in the feed
      loadEvents();
    } catch (e: any) {
      showSimpleAlert('Send Failed', e?.response?.data?.detail || 'Could not send message');
    } finally {
      setComposerSending(false);
    }
  };

  // ===== AI: Suggest a message based on relationship context =====
  const loadAISuggestionForComposer = async () => {
    if (!user || !id || id === 'new') return;
    setLoadingAI(true);
    try {
      const data = await contactsAPI.suggestMessage(user._id, id as string);
      if (data?.suggestion) {
        setAiSuggestion(data.suggestion);
        setShowAISuggestion(true);
      }
    } catch (e: any) {
      console.error('AI suggestion failed:', e);
      showToast('AI suggestion unavailable');
    } finally {
      setLoadingAI(false);
    }
  };

  // Handle card template selection → navigate to card creation and return
  const handleCardTemplateSelect = (cardType: string) => {
    setShowCardTemplatePicker(false);
    const contactName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
    const params = new URLSearchParams({
      type: cardType,
      prefillName: contactName,
      prefillPhone: contact.phone || '',
      prefillEmail: contact.email || '',
      for_contact: id as string,
      return_to_contact: 'true',
    });
    router.push(`/settings/create-card?${params.toString()}`);
  };

  // State for card template picker
  const [showCardTemplatePicker, setShowCardTemplatePicker] = useState(false);

  // Clear a date automation field
  const handleClearAutomation = async (field: string) => {
    if (!user) return;
    try {
      await contactsAPI.update(user._id, id as string, { [field]: null });
      setContact((prev: any) => ({ ...prev, [field]: null }));
      setEditingAutomation(null);
      showToast('Automation removed');
    } catch (e: any) {
      showSimpleAlert('Error', 'Could not update contact');
    }
  };

  // Update a date automation field
  const handleUpdateAutomationDate = async (field: string, date: Date) => {
    if (!user) return;
    try {
      const isoDate = date.toISOString();
      await contactsAPI.update(user._id, id as string, { [field]: isoDate });
      setContact((prev: any) => ({ ...prev, [field]: isoDate }));
      setEditingAutomation(null);
      showToast('Date updated');
    } catch (e: any) {
      showSimpleAlert('Error', 'Could not update date');
    }
  };

  // State for automation date edit picker
  const [automationPickerDate, setAutomationPickerDate] = useState(new Date());

  // Add tag from hero (immediate save)
  const addTagFromHero = async (name: string) => {
    if (!user || contact.tags.includes(name)) return;
    const updatedTags = [...contact.tags, name];
    setContact((prev: any) => ({ ...prev, tags: updatedTags }));
    setShowTagPicker(false);
    setTagSearch('');
    try {
      await contactsAPI.update(user._id, id as string, { tags: updatedTags });
      showToast(`Tag "${name}" added`);
    } catch (e: any) {
      setContact((prev: any) => ({ ...prev, tags: prev.tags.filter((t: string) => t !== name) }));
      showSimpleAlert('Error', 'Could not add tag');
    }
  };

  // Group events by date for collapsible sections
  const groupEventsByDate = (evts: ContactEvent[]) => {
    const groups: { label: string; events: ContactEvent[] }[] = [];
    const map: Record<string, ContactEvent[]> = {};
    const now = new Date();
    const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    evts.forEach(evt => {
      if (!evt.timestamp) return;
      const d = new Date(evt.timestamp);
      const evtDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
      const days = Math.round((nowDay.getTime() - evtDay.getTime()) / 86400000);
      const label = days < 0 ? 'Upcoming' : days === 0 ? 'Today' : days === 1 ? 'Yesterday' : days < 7 ? `${days} days ago` : format(d, 'MMM d, yyyy');
      if (!map[label]) { map[label] = []; groups.push({ label, events: map[label] }); }
      map[label].push(evt);
    });
    return groups;
  };

  const eventDateGroups = groupEventsByDate(filteredEvents);

  // ===== PHOTO =====
  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true, aspect: [1, 1], quality: 0.5, base64: true,
    });
    if (!result.canceled && result.assets[0].base64) {
      setContact({ ...contact, photo: `data:image/jpeg;base64,${result.assets[0].base64}` });
    }
  };

  const viewFullPhoto = async () => {
    if (!user || isNewContact) return;
    setShowPhotoViewer(true);
    setFullPhotoLoading(true);
    setSelectedPhotoIndex(-1); // -1 = show grid, >=0 = show single photo
    setFullPhoto(null);
    try {
      // Load all photos gallery
      const galleryRes = await api.get(`/contacts/${user._id}/${id}/photos/all`);
      const photos = galleryRes.data?.photos || [];
      // If profile photo exists, load high-res version for it
      if (photos.length > 0 && photos[0].type === 'profile') {
        try {
          const res = await contactsAPI.getFullPhoto(user._id, id as string);
          if (res.photo) photos[0].url = res.photo;
        } catch {}
      }
      setAllPhotos(photos);
      // If only 1 photo, go straight to full view
      if (photos.length <= 1) {
        setSelectedPhotoIndex(0);
        setFullPhoto(photos[0]?.url || contact.photo);
      }
    } catch {
      // Fallback to just the profile photo
      setAllPhotos([]);
      setSelectedPhotoIndex(0);
      setFullPhoto(contact.photo);
    } finally {
      setFullPhotoLoading(false);
    }
  };

  // ===== VOICE NOTES =====
  const loadVoiceNotes = async () => {
    if (!user || isNewContact) return;
    try {
      setVoiceNotesLoading(true);
      const notes = await contactsAPI.getVoiceNotes(user._id, id as string);
      setVoiceNotes(notes);
    } catch (e) {
      console.error('Failed to load voice notes:', e);
    } finally {
      setVoiceNotesLoading(false);
    }
  };

  React.useEffect(() => {
    if (!isNewContact && user) loadVoiceNotes();
  }, [id, user, isNewContact]);

  const startRecording = async () => {
    if (Platform.OS !== 'web') return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        await uploadVoiceNote(blob);
      };
      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setRecordingTime(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingTime(prev => {
          if (prev >= MAX_RECORDING_SECONDS - 1) {
            stopRecording();
            return MAX_RECORDING_SECONDS;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (e) {
      console.error('Mic access denied:', e);
      showSimpleAlert('Microphone Access', 'Please allow microphone access to record voice notes.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    setIsRecording(false);
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  };

  const uploadVoiceNote = async (blob: Blob) => {
    if (!user) return;
    try {
      setUploadingVoiceNote(true);
      await contactsAPI.uploadVoiceNote(user._id, id as string, blob, recordingTime);
      showToast('Voice note saved & transcribing...');
      await loadVoiceNotes();
      // Refresh events to show in activity feed
      loadEvents();
    } catch (e) {
      console.error('Upload failed:', e);
      showSimpleAlert('Error', 'Failed to save voice note');
    } finally {
      setUploadingVoiceNote(false);
      setRecordingTime(0);
    }
  };

  const playVoiceNote = (noteId: string, audioUrl: string) => {
    if (Platform.OS !== 'web') return;
    // Stop current playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (playingNoteId === noteId) {
      setPlayingNoteId(null);
      return;
    }
    const audio = new Audio(audioUrl);
    audio.onended = () => setPlayingNoteId(null);
    audio.onerror = () => { setPlayingNoteId(null); showSimpleAlert('Error', 'Failed to play audio'); };
    audio.play();
    audioRef.current = audio;
    setPlayingNoteId(noteId);
  };

  const deleteVoiceNote = async (noteId: string) => {
    if (!user) return;
    showConfirm('Delete Voice Note', 'Are you sure?', async () => {
      try {
        await contactsAPI.deleteVoiceNote(user._id, id as string, noteId);
        if (playingNoteId === noteId && audioRef.current) {
          audioRef.current.pause();
          audioRef.current = null;
          setPlayingNoteId(null);
        }
        await loadVoiceNotes();
        showToast('Voice note deleted');
      } catch (e) {
        showSimpleAlert('Error', 'Failed to delete');
      }
    });
  };

  const formatRecordingTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // ===== AI RELATIONSHIP INTEL =====
  const loadCachedIntel = async () => {
    if (!user || isNewContact) return;
    try {
      const data = await contactsAPI.getContactIntel(user._id, id as string);
      if (data.summary) setIntelData(data);
    } catch (e) {
      // No cached intel  - that's fine
    }
  };

  React.useEffect(() => {
    if (!isNewContact && user) loadCachedIntel();
  }, [id, user, isNewContact]);

  const generateIntel = async () => {
    if (!user) return;
    try {
      setIntelGenerating(true);
      setShowIntel(true);
      const data = await contactsAPI.generateContactIntel(user._id, id as string);
      setIntelData(data);
      // Scroll to top so user sees the refreshed Intel
      setTimeout(() => {
        scrollRef.current?.scrollTo({ y: 0, animated: true });
      }, 300);
    } catch (e) {
      console.error('Failed to generate intel:', e);
      showSimpleAlert('Error', 'Failed to generate AI summary. Please try again.');
    } finally {
      setIntelGenerating(false);
    }
  };

  // ===== DATE PICKER =====
  const openDatePicker = (field: string, currentDate: Date | null, label?: string) => {
    const d = currentDate || new Date();
    setActiveDateField(field); setActiveDateLabel(label || field);
    setTempDate(d); setWebMonth(d.getMonth()); setWebDay(d.getDate()); setWebYear(d.getFullYear());
    setShowDatePicker(true);
  };

  const confirmDateSelection = () => {
    let dateToUse = Platform.OS === 'web' ? new Date(webYear, webMonth, webDay) : tempDate;
    if (activeDateField === 'pending_custom') {
      setPendingCustomDate(dateToUse);
      setShowDatePicker(false);
      setTimeout(() => setShowCustomDateLabel(true), 300);
      return;
    }
    if (activeDateField?.startsWith('custom_')) {
      const idx = parseInt(activeDateField.replace('custom_', ''));
      const newDates = [...contact.custom_dates];
      newDates[idx] = { ...newDates[idx], date: dateToUse };
      setContact({ ...contact, custom_dates: newDates });
    } else if (activeDateField) {
      setContact({ ...contact, [activeDateField]: dateToUse });
    }
    setShowDatePicker(false); setActiveDateField(null);
  };

  const handleDateChange = (event: any, selectedDate?: Date) => {
    if (Platform.OS === 'android') {
      setShowDatePicker(false);
      if (event.type === 'set' && selectedDate && activeDateField) {
        if (activeDateField === 'pending_custom') {
          setPendingCustomDate(selectedDate);
          setTimeout(() => setShowCustomDateLabel(true), 300);
        } else if (activeDateField.startsWith('custom_')) {
          const idx = parseInt(activeDateField.replace('custom_', ''));
          const newDates = [...contact.custom_dates];
          newDates[idx] = { ...newDates[idx], date: selectedDate };
          setContact({ ...contact, custom_dates: newDates });
        } else {
          setContact({ ...contact, [activeDateField]: selectedDate });
        }
      }
      return;
    }
    if (selectedDate) setTempDate(selectedDate);
  };

  const confirmCustomDateWithLabel = () => {
    if (!newCustomDateName.trim() || !pendingCustomDate) return;
    setContact({ ...contact, custom_dates: [...contact.custom_dates, { name: newCustomDateName.trim(), date: pendingCustomDate }] });
    setNewCustomDateName(''); setPendingCustomDate(null); setShowCustomDateLabel(false);
  };

  const removeCustomDateField = (index: number) => {
    showConfirm('Remove Date', `Remove "${contact.custom_dates[index].name}"?`, () => {
      setContact({ ...contact, custom_dates: contact.custom_dates.filter((_, i) => i !== index) });
    });
  };

  const clearDate = (field: string) => {
    if (field.startsWith('custom_')) {
      const idx = parseInt(field.replace('custom_', ''));
      const newDates = [...contact.custom_dates];
      newDates[idx] = { ...newDates[idx], date: null };
      setContact({ ...contact, custom_dates: newDates });
    } else {
      setContact({ ...contact, [field]: null });
    }
  };

  const formatDateDisplay = (date: Date | null): string => date ? format(date, 'MMM d, yyyy') : 'Not set';

  // ===== TAGS =====
  const addTag = (name: string) => {
    if (!contact.tags.includes(name)) setContact({ ...contact, tags: [...contact.tags, name] });
    setShowTagPicker(false); setTagSearch('');
  };
  const removeTag = (tag: string) => setContact({ ...contact, tags: contact.tags.filter(t => t !== tag) });

  const filteredAvailableTags = availableTags.filter(
    t => !contact.tags.includes(t.name) && t.name.toLowerCase().includes(tagSearch.toLowerCase())
  );

  // ===== REFERRAL =====
  const selectReferrer = (ref: any) => {
    setContact({ ...contact, referred_by: ref._id, referred_by_name: `${ref.first_name} ${ref.last_name || ''}`.trim() });
    setShowReferralPicker(false);
  };
  const clearReferrer = () => setContact({ ...contact, referred_by: null, referred_by_name: null });

  // ===== CAMPAIGNS =====
  const enrollInCampaign = async (campaign: any) => {
    if (!user) return;
    setShowCampaignPicker(false);
    try {
      await campaignsAPI.enrollContact(user._id, campaign._id, id as string);
      showToast(`Enrolled in "${campaign.name}"`);
      loadCampaignsAndEnrollments();
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to enroll');
    }
  };
  const cancelEnrollment = async (enrollment: any) => {
    if (!user) return;
    try {
      await campaignsAPI.cancelEnrollment(user._id, enrollment.campaign_id, enrollment._id);
      setContactEnrollments(prev => prev.filter(e => e._id !== enrollment._id));
    } catch { showSimpleAlert('Error', 'Failed to cancel enrollment'); }
  };
  const availableCampaigns = campaigns.filter(c =>
    !contactEnrollments.some(e => e.campaign_id === c._id && e.status === 'active')
  );

  const getDaysInMonth = (m: number, y: number) => new Date(y, m + 1, 0).getDate();
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  const filteredContacts = allContacts.filter(c => {
    const name = `${c.first_name} ${c.last_name || ''}`.toLowerCase();
    return name.includes(contactSearch.toLowerCase());
  });

  // ===== LOADING =====
  if (loading) {
    return (
      <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
        <View style={s.loadingContainer}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      </SafeAreaView>
    );
  }

  const fullName = `${contact.first_name} ${contact.last_name || ''}`.trim() || 'New Contact';
  const initials = `${contact.first_name?.[0] || ''}${contact.last_name?.[0] || ''}`.toUpperCase() || '?';
  const timeValue = getTimeInSystem(stats.created_at);
  const timeLabel = getTimeInSystemLabel(stats.created_at);

  // ===== RENDER =====
  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* HEADER */}
        <View style={[s.header, { borderBottomColor: colors.border }]} data-testid="contact-detail-header">
          <TouchableOpacity onPress={() => router.back()} style={s.headerBtn} data-testid="contact-back-button">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={[s.headerTitle, { color: colors.text }]} numberOfLines={1}>{isNewContact ? 'New Contact' : fullName}</Text>
          {isEditing ? (
            <TouchableOpacity onPress={handleSave} style={s.headerBtn} disabled={saving} data-testid="contact-save-button">
              {saving ? <ActivityIndicator size="small" color="#C9A962" /> : <Text style={s.headerAction}>Save</Text>}
            </TouchableOpacity>
          ) : (
            <TouchableOpacity onPress={() => setIsEditing(true)} style={s.headerBtn} data-testid="contact-edit-button">
              <Text style={s.headerAction}>Edit</Text>
            </TouchableOpacity>
          )}
        </View>

        <ScrollView ref={scrollRef} contentContainerStyle={[s.scroll, { paddingBottom: 80 }]} showsVerticalScrollIndicator={false}>
          {/* ===== COMPACT PROFILE HERO ===== */}
          <View style={[s.heroSection, { backgroundColor: colors.bg }]} data-testid="contact-hero">
            <View style={s.heroRow}>
              {/* Left: Avatar */}
              <View style={s.heroAvatarContainer}>
                <TouchableOpacity onPress={isEditing ? pickImage : viewFullPhoto} activeOpacity={isEditing ? 0.7 : 0.8}>
                  {contact.photo ? (
                    <Image source={{ uri: contact.photo }} style={s.heroAvatar} />
                  ) : (
                    <View style={s.heroAvatarPlaceholder}>
                      <Text style={s.heroInitials}>{initials}</Text>
                    </View>
                  )}
                  {isEditing && (
                    <View style={s.heroCameraBadge}>
                      <Ionicons name="camera" size={12} color={colors.text} />
                    </View>
                  )}
                </TouchableOpacity>
                {!isNewContact && stats.total_touchpoints > 0 && (
                  <View style={s.touchpointBadge} data-testid="touchpoint-badge">
                    <Text style={s.touchpointBadgeText}>{stats.total_touchpoints}</Text>
                  </View>
                )}
              </View>

              {/* Right: Name + Info */}
              <View style={s.heroInfo}>
                <Text style={[s.heroName, { color: colors.text }]} data-testid="contact-name" numberOfLines={1}>{fullName}</Text>

                {/* Vehicle / Product / Highlight */}
                {contact.vehicle ? (
                  <View style={s.heroHighlight}>
                    <Ionicons name="pricetag" size={12} color="#C9A962" />
                    <Text style={s.heroHighlightText} numberOfLines={1}>{contact.vehicle}</Text>
                  </View>
                ) : null}

                {/* Location + Time compact */}
                <View style={s.heroMetaRow}>
                  {(contact.address_city || contact.address_state) ? (
                    <View style={s.heroMetaItem}>
                      <Ionicons name="location-outline" size={11} color={colors.textTertiary} />
                      <Text style={s.heroMetaText}>{[contact.address_city, contact.address_state].filter(Boolean).join(', ')}</Text>
                    </View>
                  ) : null}
                  {!isNewContact && (
                    <View style={s.heroMetaItem}>
                      <Ionicons name="time-outline" size={11} color={colors.textTertiary} />
                      <Text style={s.heroMetaText}>{timeValue} {timeLabel} relationship</Text>
                    </View>
                  )}
                </View>
              </View>
            </View>

            {/* Compact stats line */}
            {!isNewContact && (
              <View style={s.heroStatsLine} data-testid="contact-stats-row">
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.total_touchpoints}</Text>
                  <Text style={s.heroStatLbl}>touches</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.messages_sent}</Text>
                  <Text style={s.heroStatLbl}>msgs</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.link_clicks}</Text>
                  <Text style={s.heroStatLbl}>clicks</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.campaigns}</Text>
                  <Text style={s.heroStatLbl}>campaigns</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{contact.referral_count}</Text>
                  <Text style={s.heroStatLbl}>referrals</Text>
                </View>
              </View>
            )}

            {/* Tags + Automations Strip (merged) */}
            {!isNewContact && (
              <View style={s.heroTagsStrip} data-testid="hero-tags-strip">
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingBottom: 4, alignItems: 'center' }}>
                  {contact.tags.map((tag, i) => {
                    const info = availableTags.find(t => t.name === tag);
                    const chipColor = info?.color || colors.textSecondary;
                    return (
                      <View key={`tag-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10` }]}>
                        <Ionicons name={(info?.icon || 'pricetag') as any} size={13} color={chipColor} />
                        <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{tag}</Text>
                      </View>
                    );
                  })}
                  {contact.birthday && (
                    <TouchableOpacity
                      style={[s.heroTagChip, { borderColor: '#FF2D5540', backgroundColor: '#FF2D5510', borderStyle: 'dashed' }]}
                      onPress={() => {
                        setAutomationPickerDate(contact.birthday ? new Date(contact.birthday) : new Date());
                        setEditingAutomation({ field: 'birthday', label: 'Birthday', color: '#FF2D55', value: contact.birthday });
                      }}
                      activeOpacity={0.7}
                      data-testid="auto-birthday"
                    >
                      <Ionicons name="gift" size={13} color="#FF2D55" />
                      <Text style={[s.heroTagChipText, { color: '#FF2D55' }]} numberOfLines={1}>{formatDateUTC(contact.birthday)}</Text>
                    </TouchableOpacity>
                  )}
                  {contact.anniversary && (
                    <TouchableOpacity
                      style={[s.heroTagChip, { borderColor: '#FF6B6B40', backgroundColor: '#FF6B6B10', borderStyle: 'dashed' }]}
                      onPress={() => {
                        setAutomationPickerDate(contact.anniversary ? new Date(contact.anniversary) : new Date());
                        setEditingAutomation({ field: 'anniversary', label: 'Anniversary', color: '#FF6B6B', value: contact.anniversary });
                      }}
                      activeOpacity={0.7}
                      data-testid="auto-anniversary"
                    >
                      <Ionicons name="heart" size={13} color="#FF6B6B" />
                      <Text style={[s.heroTagChipText, { color: '#FF6B6B' }]} numberOfLines={1}>{formatDateUTC(contact.anniversary)}</Text>
                    </TouchableOpacity>
                  )}
                  {contact.date_sold && (
                    <TouchableOpacity
                      style={[s.heroTagChip, { borderColor: '#34C75940', backgroundColor: '#34C75910', borderStyle: 'dashed' }]}
                      onPress={() => {
                        setAutomationPickerDate(contact.date_sold ? new Date(contact.date_sold) : new Date());
                        setEditingAutomation({ field: 'date_sold', label: 'Sold Date', color: '#34C759', value: contact.date_sold });
                      }}
                      activeOpacity={0.7}
                      data-testid="auto-sold"
                    >
                      <Ionicons name="car-sport" size={13} color="#34C759" />
                      <Text style={[s.heroTagChipText, { color: '#34C759' }]} numberOfLines={1}>{formatDateUTC(contact.date_sold)}</Text>
                    </TouchableOpacity>
                  )}
                  {contactEnrollments.map((e, i) => {
                    const chipColor = e.status === 'completed' ? '#34C759' : '#007AFF';
                    return (
                      <View key={`camp-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10`, borderStyle: 'dashed' }]} data-testid={`campaign-chip-${i}`}>
                        <Ionicons name={e.status === 'completed' ? 'checkmark-circle' : 'play-circle'} size={13} color={chipColor} />
                        <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{e.campaign_name}</Text>
                        {e.status !== 'completed' && (
                          <Text style={{ fontSize: 10, color: chipColor, fontWeight: '600' }}>{e.current_step}/{e.total_steps}</Text>
                        )}
                      </View>
                    );
                  })}
                  <TouchableOpacity onPress={() => { loadTags(); setShowTagPicker(true); }} style={[s.heroTagChip, { borderColor: '#007AFF40', backgroundColor: '#007AFF08' }]} data-testid="hero-add-tag-btn">
                    <Ionicons name="add" size={14} color="#007AFF" />
                  </TouchableOpacity>
                </ScrollView>
              </View>
            )}
          </View>

          {/* ===== ACTION PROGRESS TRACKER (above tabs) ===== */}
          {!isNewContact && !isEditing && actionProgress.length > 0 && (
            <View style={s.progressSection} data-testid="action-progress">
              <View style={s.progressHeader}>
                <Text style={s.progressLabel}>{progressCompleted}/{progressTotal} Actions</Text>
                <View style={s.progressBarBg}>
                  <View style={[s.progressBarFill, { width: `${progressTotal > 0 ? (progressCompleted / progressTotal) * 100 : 0}%` }]} />
                </View>
              </View>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.progressRow}>
                {actionProgress.map((a: any) => (
                  <TouchableOpacity
                    key={a.key}
                    style={[s.progressItem, a.done && s.progressItemDone]}
                    onPress={() => !a.done && handleQuickAction(a.key === 'personal_sms' ? 'sms' : a.key === 'congrats_card_sent' ? 'congrats' : a.key === 'review_request_sent' ? 'review' : a.key === 'email_sent' ? 'email' : a.key === 'link_page_shared' ? 'linkpage' : a.key === 'digital_card_sent' ? 'digitalcard' : a.key)}
                    activeOpacity={a.done ? 1 : 0.7}
                    data-testid={`progress-${a.key}`}
                  >
                    <View style={[s.progressIcon, { backgroundColor: a.done ? `${a.color}25` : colors.card }]}>
                      {a.done ? (
                        <Ionicons name="checkmark-circle" size={18} color={a.color} />
                      ) : (
                        <Ionicons name={(a.icon || 'ellipse-outline') as any} size={16} color={colors.borderLight} />
                      )}
                    </View>
                    <Text style={[s.progressText, a.done && { color: a.color }]} numberOfLines={1}>{a.label}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}

          {/* ===== FEED / DETAILS TAB BAR ===== */}
          {!isNewContact && !isEditing && (
            <View style={s.tabBar} data-testid="contact-tab-bar">
              <TouchableOpacity
                style={[s.tabBtn, contactTab === 'feed' && s.tabBtnActive]}
                onPress={() => setContactTab('feed')}
                data-testid="tab-feed"
              >
                <Text style={[s.tabBtnText, contactTab === 'feed' && s.tabBtnTextActive]}>Feed</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[s.tabBtn, contactTab === 'details' && s.tabBtnActive]}
                onPress={() => setContactTab('details')}
                data-testid="tab-details"
              >
                <Text style={[s.tabBtnText, contactTab === 'details' && s.tabBtnTextActive]}>Details</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* ===== EDIT-MODE: Basic Info + Tags + Important Dates at top ===== */}
          {isEditing && (
            <>
              {/* Basic Info */}
              <View style={s.section}>
                <Text style={s.sectionHeader}>Basic Info</Text>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>First Name *</Text>
                  <TextInput style={s.input} placeholder="First name" placeholderTextColor={colors.textTertiary}
                    value={contact.first_name} onChangeText={t => setContact({ ...contact, first_name: t })} data-testid="input-first-name" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Last Name</Text>
                  <TextInput style={s.input} placeholder="Last name" placeholderTextColor={colors.textTertiary}
                    value={contact.last_name} onChangeText={t => setContact({ ...contact, last_name: t })} data-testid="input-last-name" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Phone *</Text>
                  <TextInput style={s.input} placeholder="+1 (555) 123-4567" placeholderTextColor={colors.textTertiary}
                    value={contact.phone} onChangeText={t => setContact({ ...contact, phone: t })} keyboardType="phone-pad" data-testid="input-phone" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Email</Text>
                  <TextInput style={s.input} placeholder="email@example.com" placeholderTextColor={colors.textTertiary}
                    value={contact.email} onChangeText={t => setContact({ ...contact, email: t })} keyboardType="email-address" autoCapitalize="none" data-testid="input-email" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Vehicle</Text>
                  <TextInput style={s.input} placeholder="e.g., 2023 Toyota RAV4" placeholderTextColor={colors.textTertiary}
                    value={contact.vehicle} onChangeText={t => setContact({ ...contact, vehicle: t })} data-testid="input-vehicle" />
                </View>
              </View>

              {/* Address Section */}
              <View style={s.section}>
                <Text style={s.sectionHeader}>Address</Text>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Street</Text>
                  <TextInput style={s.input} placeholder="123 Main St" placeholderTextColor={colors.textTertiary}
                    value={contact.address_street} onChangeText={t => setContact({ ...contact, address_street: t })} data-testid="input-address-street" />
                </View>
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <View style={[s.inputGroup, { flex: 1 }]}>
                    <Text style={s.inputLabel}>City</Text>
                    <TextInput style={s.input} placeholder="City" placeholderTextColor={colors.textTertiary}
                      value={contact.address_city} onChangeText={t => setContact({ ...contact, address_city: t })} data-testid="input-address-city" />
                  </View>
                  <View style={[s.inputGroup, { flex: 0.5 }]}>
                    <Text style={s.inputLabel}>State</Text>
                    <TextInput style={s.input} placeholder="ST" placeholderTextColor={colors.textTertiary}
                      value={contact.address_state} onChangeText={t => setContact({ ...contact, address_state: t })} autoCapitalize="characters" data-testid="input-address-state" />
                  </View>
                </View>
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <View style={[s.inputGroup, { flex: 1 }]}>
                    <Text style={s.inputLabel}>ZIP Code</Text>
                    <TextInput style={s.input} placeholder="12345" placeholderTextColor={colors.textTertiary}
                      value={contact.address_zip} onChangeText={t => setContact({ ...contact, address_zip: t })} keyboardType="number-pad" data-testid="input-address-zip" />
                  </View>
                  <View style={[s.inputGroup, { flex: 1 }]}>
                    <Text style={s.inputLabel}>Country</Text>
                    <TextInput style={s.input} placeholder="US" placeholderTextColor={colors.textTertiary}
                      value={contact.address_country} onChangeText={t => setContact({ ...contact, address_country: t })} data-testid="input-address-country" />
                  </View>
                </View>
              </View>

              {/* Tags (edit mode  - at top) */}
              <View style={s.section}>
                <Text style={s.sectionHeader}>Tags</Text>
                <View style={s.tagsWrap}>
                  {contact.tags.map((tag, i) => {
                    const info = availableTags.find(t => t.name === tag);
                    return (
                      <View key={i} style={[s.tagPill, info?.color && { borderColor: info.color }]}>
                        {info?.icon && <Ionicons name={info.icon as any} size={13} color={info.color || colors.textSecondary} />}
                        <Text style={[s.tagPillText, info?.color && { color: info.color }]}>{tag}</Text>
                        <TouchableOpacity onPress={() => removeTag(tag)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                          <Ionicons name="close-circle" size={15} color={colors.textSecondary} />
                        </TouchableOpacity>
                      </View>
                    );
                  })}
                  <TouchableOpacity style={s.addTagChip} onPress={() => { loadTags(); setShowTagPicker(true); }} data-testid="add-tag-button-top">
                    <Ionicons name="add" size={16} color="#007AFF" />
                    <Text style={s.addTagChipText}>Add</Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* Important Dates (edit mode  - at top) */}
              <View style={s.section}>
                <Text style={s.sectionHeader}>Important Dates</Text>
                {[
                  { field: 'birthday', label: 'Birthday', icon: 'gift', color: '#FF9500' },
                  { field: 'anniversary', label: 'Anniversary', icon: 'heart', color: '#FF2D55' },
                  { field: 'date_sold', label: 'Date Sold', icon: 'car', color: '#34C759' },
                ].map(d => (
                  <TouchableOpacity key={d.field} style={s.dateRow} onPress={() => openDatePicker(d.field, (contact as any)[d.field], d.label)}>
                    <View style={[s.dateRowIcon, { backgroundColor: `${d.color}20` }]}>
                      <Ionicons name={d.icon as any} size={18} color={d.color} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.dateRowLabel}>{d.label}</Text>
                      <Text style={[s.dateRowValue, !(contact as any)[d.field] && { color: colors.textTertiary }]}>
                        {formatDateDisplay((contact as any)[d.field])}
                      </Text>
                    </View>
                    {(contact as any)[d.field] && (
                      <TouchableOpacity onPress={() => clearDate(d.field)} style={{ padding: 4, marginRight: 8 }}>
                        <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
                      </TouchableOpacity>
                    )}
                    <Ionicons name="calendar" size={20} color={colors.textSecondary} />
                  </TouchableOpacity>
                ))}
                {contact.custom_dates.map((cd, i) => (
                  <TouchableOpacity key={i} style={s.dateRow} onPress={() => openDatePicker(`custom_${i}`, cd.date)}>
                    <View style={[s.dateRowIcon, { backgroundColor: '#007AFF20' }]}>
                      <Ionicons name="calendar-outline" size={18} color="#007AFF" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.dateRowLabel}>{cd.name}</Text>
                      <Text style={[s.dateRowValue, !cd.date && { color: colors.textTertiary }]}>{formatDateDisplay(cd.date)}</Text>
                    </View>
                    <TouchableOpacity onPress={() => removeCustomDateField(i)} style={{ padding: 4 }}>
                      <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                    </TouchableOpacity>
                  </TouchableOpacity>
                ))}
                <TouchableOpacity style={s.addBtn} onPress={() => {
                  setTempDate(new Date()); setActiveDateField('pending_custom');
                  setActiveDateLabel('Select Date'); setShowDatePicker(true);
                }}>
                  <Ionicons name="add-circle" size={20} color="#007AFF" />
                  <Text style={s.addBtnText}>Add Custom Date</Text>
                </TouchableOpacity>
              </View>
            </>
          )}

          {/* ===== FEED TAB ===== */}
          {!isNewContact && !isEditing && contactTab === 'feed' && (
            <>
              {/* Suggested Actions (inline at top of feed) */}
              {suggestedActions.length > 0 && (
                <View style={[s.section, { paddingTop: 4 }]} data-testid="suggested-actions">
                  {suggestedActions.map((action, i) => (
                    <TouchableOpacity
                      key={i}
                      style={s.suggestedCard}
                      onPress={() => handleSuggestedAction(action)}
                      activeOpacity={0.7}
                      data-testid={`suggested-action-${i}`}
                    >
                      <View style={[s.suggestedIcon, { backgroundColor: `${action.color}20` }]}>
                        <Ionicons name={action.icon as any} size={20} color={action.color} />
                      </View>
                      <View style={{ flex: 1, marginLeft: 12 }}>
                        <Text style={s.suggestedTitle}>{action.title}</Text>
                        <Text style={s.suggestedDesc}>{action.description}</Text>
                        {action.suggested_message && (
                          <View style={s.suggestedMsgPreview}>
                            <Text style={s.suggestedMsgText} numberOfLines={2}>"{action.suggested_message}"</Text>
                          </View>
                        )}
                      </View>
                      <View style={[s.suggestedArrow, { backgroundColor: `${action.color}15` }]}>
                        <Ionicons name="arrow-forward" size={16} color={action.color} />
                      </View>
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              {/* AI Intel pill (collapsed) */}
              <View style={[s.section, { paddingTop: suggestedActions.length > 0 ? 0 : 4 }]} data-testid="relationship-intel">
                <TouchableOpacity
                  style={s.intelBtn}
                  onPress={() => {
                    if (intelData && !showIntel) { setShowIntel(true); return; }
                    if (!intelData) { generateIntel(); return; }
                    setShowIntel(!showIntel);
                  }}
                  activeOpacity={0.7}
                  data-testid="intel-toggle-btn"
                >
                  <View style={s.intelBtnLeft}>
                    <View style={s.intelIcon}>
                      <Ionicons name="sparkles" size={16} color="#C9A962" />
                    </View>
                    <View>
                      <Text style={s.intelBtnTitle}>Relationship Intel</Text>
                      {intelData?.generated_at && !showIntel && (
                        <Text style={s.intelBtnSub}>
                          Updated {formatEventTime(intelData.generated_at)}
                        </Text>
                      )}
                    </View>
                  </View>
                  <Ionicons name={showIntel ? 'chevron-up' : 'chevron-forward'} size={18} color={colors.textTertiary} />
                </TouchableOpacity>

                {showIntel && (
                  <View style={s.intelCard}>
                    {intelGenerating ? (
                      <View style={s.intelLoading}>
                        <ActivityIndicator size="small" color="#C9A962" />
                        <Text style={s.intelLoadingText}>Analyzing relationship history...</Text>
                      </View>
                    ) : intelData?.summary ? (
                      <>
                        <IntelRenderer text={intelData.summary} />
                        <View style={s.intelMeta}>
                          <Text style={s.intelMetaText}>
                            Based on {intelData.data_points?.messages || 0} messages, {intelData.data_points?.events || 0} events, {intelData.data_points?.voice_notes || 0} voice notes
                          </Text>
                          <TouchableOpacity onPress={generateIntel} style={s.intelRefresh} data-testid="intel-refresh-btn">
                            <Ionicons name="refresh" size={14} color="#007AFF" />
                            <Text style={s.intelRefreshText}>Refresh</Text>
                          </TouchableOpacity>
                        </View>
                      </>
                    ) : (
                      <Text style={s.intelEmpty}>Tap to generate an AI briefing</Text>
                    )}
                  </View>
                )}
              </View>

              {/* Pinned Notes (view-only, inside feed) */}
              {contact.notes ? (
                <View style={[s.section, { paddingTop: 0 }]} data-testid="pinned-notes">
                  <View style={s.pinnedNote}>
                    <Ionicons name="document-text" size={14} color="#C9A962" style={{ marginTop: 2 }} />
                    <Text style={s.pinnedNoteText} numberOfLines={3}>{contact.notes}</Text>
                  </View>
                </View>
              ) : null}

              {/* Relationship Feed (Activity) */}
              <View style={[s.section, { paddingTop: 0 }]} data-testid="activity-feed">
                <View style={s.sectionHeaderRow}>
                  <Text style={s.sectionHeader}>Activity</Text>
                  <Text style={s.sectionHeaderCount}>{events.length} events</Text>
                </View>

                {/* Log Reply + Search Row */}
                <View style={s.feedActionRow}>
                  <TouchableOpacity
                    style={s.logReplyBtn}
                    onPress={() => setShowLogReply(true)}
                    data-testid="log-reply-btn"
                  >
                    <Ionicons name="chatbubble-ellipses" size={16} color="#30D158" />
                    <Text style={s.logReplyBtnText}>Log Customer Reply</Text>
                  </TouchableOpacity>
                  {events.length > 0 && (
                    <View style={s.feedSearchRowCompact}>
                      <Ionicons name="search" size={14} color={colors.textTertiary} />
                      <TextInput
                        style={s.feedSearchInputCompact}
                        placeholder="Search..."
                        placeholderTextColor={colors.textTertiary}
                        value={feedSearch}
                        onChangeText={setFeedSearch}
                        data-testid="feed-search-input"
                      />
                      {feedSearch.length > 0 && (
                        <TouchableOpacity onPress={() => setFeedSearch('')}>
                          <Ionicons name="close-circle" size={14} color={colors.textTertiary} />
                        </TouchableOpacity>
                      )}
                    </View>
                  )}
                </View>

                {/* Log Reply Inline Composer  - Chat Bubble Style */}
                {showLogReply && (
                  <View style={s.logReplyBubble} data-testid="log-reply-composer">
                    <View style={s.bubbleTail} />
                    <View style={s.bubbleHeader}>
                      <Ionicons name="arrow-down-circle" size={18} color="#30D158" />
                      <Text style={s.bubbleHeaderText}>Customer said...</Text>
                      <TouchableOpacity onPress={() => { setShowLogReply(false); setReplyText(''); setReplyPhoto(null); }} style={s.bubbleClose}>
                        <Ionicons name="close-circle" size={22} color={colors.textTertiary} />
                      </TouchableOpacity>
                    </View>
                    <View style={s.bubbleInputWrap}>
                      <TextInput
                        style={s.bubbleInput}
                        placeholder="Paste what they said..."
                        placeholderTextColor={colors.textTertiary}
                        value={replyText}
                        onChangeText={setReplyText}
                        multiline
                        data-testid="log-reply-input"
                      />
                    </View>
                    {replyPhoto && (
                      <View style={s.bubblePhotoPreview}>
                        <Image source={{ uri: replyPhoto }} style={s.bubblePhotoThumb} resizeMode="cover" />
                        <TouchableOpacity style={s.bubblePhotoRemove} onPress={() => setReplyPhoto(null)}>
                          <Ionicons name="close-circle" size={22} color="#FF3B30" />
                        </TouchableOpacity>
                      </View>
                    )}
                    <View style={s.bubbleFooter}>
                      <TouchableOpacity style={s.bubblePhotoBtn} onPress={pickReplyPhoto} data-testid="log-reply-photo-btn">
                        <Ionicons name="image" size={20} color={colors.textTertiary} />
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[s.bubbleSaveBtn, (!replyText.trim() && !replyPhoto) && { opacity: 0.35 }]}
                        onPress={handleLogReply}
                        disabled={(!replyText.trim() && !replyPhoto) || submittingReply}
                        data-testid="log-reply-submit"
                      >
                        {submittingReply ? (
                          <ActivityIndicator size="small" color={colors.text} />
                        ) : (
                          <>
                            <Text style={s.bubbleSaveText}>Save Reply</Text>
                            <Ionicons name="arrow-up-circle" size={22} color={colors.text} />
                          </>
                        )}
                      </TouchableOpacity>
                    </View>
                  </View>
                )}

                {eventsLoading ? (
                  <ActivityIndicator size="small" color="#C9A962" style={{ marginTop: 16 }} />
                ) : filteredEvents.length === 0 ? (
                  <View style={s.emptyFeed}>
                    <Ionicons name={feedQuery ? 'search-outline' : 'time-outline'} size={36} color={colors.surface} />
                    <Text style={s.emptyFeedText}>{feedQuery ? 'No matching events' : 'No activity yet'}</Text>
                    <Text style={s.emptyFeedSub}>{feedQuery ? 'No results for "' + feedSearch + '"' : 'Send a message or enroll in a campaign to get started'}</Text>
                  </View>
                ) : (
                  <View style={s.feedTimeline}>
                    {eventDateGroups.map((group, gi) => {
                      const isCollapsed = collapsedDateGroups[group.label] === true;
                      const groupEvents = showAllEvents ? group.events : (gi === 0 ? group.events.slice(0, INITIAL_EVENT_COUNT) : group.events);
                      if (groupEvents.length === 0) return null;
                      return (
                        <View key={group.label}>
                          <TouchableOpacity
                            style={s.feedDateHeader}
                            onPress={() => setCollapsedDateGroups(prev => ({ ...prev, [group.label]: !prev[group.label] }))}
                            activeOpacity={0.7}
                            data-testid={`feed-date-${group.label}`}
                          >
                            <View style={s.feedDateLine} />
                            <Text style={s.feedDateText}>{group.label}</Text>
                            <Text style={s.feedDateCount}>{group.events.length}</Text>
                            <Ionicons name={isCollapsed ? 'chevron-down' : 'chevron-up'} size={14} color={colors.textTertiary} />
                            <View style={s.feedDateLine} />
                          </TouchableOpacity>

                          {!isCollapsed && groupEvents.map((evt, i) => {
                      const catStyle = EVENT_CATEGORY_ICON[evt.category] || EVENT_CATEGORY_ICON.custom;
                      const evtKey = `${group.label}-${i}`;
                      const isExpanded = expandedEvents[evtKey] === true;
                      const fullContent = evt.full_content || evt.description || '';
                      const hasLink = !!evt.link;
                      const isInbound = evt.direction === 'inbound' || evt.event_type === 'customer_reply';
                      const isCustomerActivity = evt.category === 'customer_activity';
                      const channelLabel = evt.channel === 'email' ? 'Email' : evt.channel === 'sms_personal' ? 'Personal SMS' : evt.channel === 'sms' ? 'SMS' : '';
                      return (
                        <TouchableOpacity
                          key={evtKey}
                          activeOpacity={0.7}
                          onPress={() => setExpandedEvents(prev => ({ ...prev, [evtKey]: !prev[evtKey] }))}
                          style={[s.feedItem, isInbound && s.feedItemInbound]}
                          data-testid={`feed-event-${evtKey}`}
                        >
                          {i < groupEvents.length - 1 && <View style={[s.feedLine, { backgroundColor: colors.border }]} />}
                          <View style={[s.feedIcon, { backgroundColor: `${evt.color || catStyle.color}20` }]}>
                            <Ionicons name={(evt.icon || catStyle.icon) as any} size={16} color={evt.color || catStyle.color} />
                          </View>
                          <View style={s.feedContent}>
                            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flex: 1 }}>
                                <Text style={[s.feedTitle, { color: colors.text }]}>{getEventTitle(evt)}</Text>
                                {isInbound && (
                                  <View style={s.inboundBadge}>
                                    <Text style={s.inboundBadgeText}>INBOUND</Text>
                                  </View>
                                )}
                                {isCustomerActivity && !isInbound && (
                                  <View style={s.customerBadge}>
                                    <Text style={s.customerBadgeText}>CUSTOMER</Text>
                                  </View>
                                )}
                              </View>
                              <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textTertiary} />
                            </View>
                            {!isExpanded && evt.description ? (
                              <Text style={[s.feedDesc, isInbound && { color: '#30D158', fontStyle: 'italic' }]} numberOfLines={1}>
                                {isInbound ? `"${evt.description}"` : evt.description}
                              </Text>
                            ) : null}
                            {isExpanded && (
                              <View style={s.feedExpandedPreview}>
                                {channelLabel ? (
                                  <View style={[s.feedChannelBadge, { backgroundColor: `${evt.color || '#007AFF'}20` }]}>
                                    <Ionicons name={evt.channel === 'email' ? 'mail' : 'chatbubble'} size={10} color={evt.color || '#007AFF'} />
                                    <Text style={[s.feedChannelText, { color: evt.color || '#007AFF' }]}>{channelLabel}</Text>
                                  </View>
                                ) : null}
                                {evt.subject ? (
                                  <Text style={s.feedSubject}>{evt.subject}</Text>
                                ) : null}
                                <View style={[s.feedMessageBubble, isInbound && s.feedMessageBubbleInbound]}>
                                  <Text style={[s.feedMessageText, isInbound && { color: '#30D158' }]}>
                                    {isInbound ? `"${fullContent}"` : fullContent}
                                  </Text>
                                </View>
                                {evt.has_photo && (
                                  <View style={s.feedPhotoIndicator}>
                                    <Ionicons name="image" size={14} color="#30D158" />
                                    <Text style={s.feedPhotoText}>Photo attached</Text>
                                  </View>
                                )}
                                {hasLink && (
                                  <TouchableOpacity
                                    style={s.feedViewLink}
                                    onPress={(e) => {
                                      e.stopPropagation?.();
                                      router.push(evt.link as any);
                                    }}
                                    data-testid={`feed-view-link-${evtKey}`}
                                  >
                                    <Ionicons name="open-outline" size={14} color="#007AFF" />
                                    <Text style={s.feedViewLinkText}>View Card</Text>
                                  </TouchableOpacity>
                                )}
                              </View>
                            )}
                            <Text style={s.feedTime}>{formatEventTime(evt.timestamp)}</Text>
                          </View>
                        </TouchableOpacity>
                      );
                    })}
                        </View>
                      );
                    })}
                    {filteredEvents.length > INITIAL_EVENT_COUNT && (
                      <TouchableOpacity
                        style={s.showMoreBtn}
                        onPress={() => setShowAllEvents(!showAllEvents)}
                        data-testid="show-more-events-button"
                      >
                        <Text style={s.showMoreText}>
                          {showAllEvents ? 'Show Less' : `Show All ${filteredEvents.length} Events`}
                        </Text>
                        <Ionicons name={showAllEvents ? 'chevron-up' : 'chevron-down'} size={16} color="#007AFF" />
                      </TouchableOpacity>
                    )}
                  </View>
                )}
              </View>

              {/* Conversations Link */}
              <TouchableOpacity
                style={s.conversationLink}
                onPress={() => router.push({
                  pathname: `/thread/${id}`,
                  params: {
                    contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
                    contact_phone: contact.phone || '',
                    contact_email: contact.email || contact.email_work || '',
                  }
                })}
                data-testid="go-to-conversation"
              >
                <View style={[s.quickActionIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="chatbubbles" size={20} color="#007AFF" />
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={s.conversationLinkTitle}>View Conversation</Text>
                  <Text style={s.conversationLinkSub}>Open full message thread</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
              </TouchableOpacity>
            </>
          )}

          {/* ===== DETAILS TAB ===== */}
          {!isNewContact && !isEditing && contactTab === 'details' && (
            <>
              {/* Voice Notes */}
              {Platform.OS === 'web' && (
                <View style={[s.section, { paddingTop: 4 }]} data-testid="voice-notes-section">
                  <View style={s.sectionHeaderRow}>
                    <Text style={s.sectionHeader}>Voice Notes</Text>
                    <Text style={s.sectionHeaderCount}>{voiceNotes.length} {voiceNotes.length === 1 ? 'note' : 'notes'}</Text>
                  </View>

                  {isRecording ? (
                    <View style={s.vnRecording} data-testid="voice-recording-indicator">
                      <View style={s.vnRecordingDot} />
                      <Text style={s.vnRecordingTime}>{formatRecordingTime(recordingTime)}</Text>
                      <Text style={s.vnRecordingLimit}>/ {formatRecordingTime(MAX_RECORDING_SECONDS)}</Text>
                      <TouchableOpacity style={s.vnStopBtn} onPress={stopRecording} data-testid="stop-recording-btn">
                        <Ionicons name="stop" size={18} color={colors.text} />
                        <Text style={s.vnStopText}>Stop</Text>
                      </TouchableOpacity>
                    </View>
                  ) : uploadingVoiceNote ? (
                    <View style={s.vnRecording}>
                      <ActivityIndicator size="small" color="#34C759" />
                      <Text style={[s.vnRecordingTime, { marginLeft: 8 }]}>Saving & transcribing...</Text>
                    </View>
                  ) : (
                    <TouchableOpacity style={s.vnRecordBtn} onPress={startRecording} data-testid="start-recording-btn">
                      <Ionicons name="mic" size={20} color="#34C759" />
                      <Text style={s.vnRecordText}>Record a Voice Note</Text>
                    </TouchableOpacity>
                  )}

                  {voiceNotesLoading ? (
                    <ActivityIndicator size="small" color="#C9A962" style={{ marginTop: 12 }} />
                  ) : voiceNotes.length > 0 ? (
                    <View style={{ marginTop: 12 }}>
                      {(showAllNotes ? voiceNotes : voiceNotes.slice(0, 1)).map((note, i) => {
                        const isPlaying = playingNoteId === note.id;
                        return (
                          <View key={note.id} style={s.vnCard} data-testid={`voice-note-${i}`}>
                            <View style={s.vnCardHeader}>
                              <TouchableOpacity
                                style={[s.vnPlayBtn, isPlaying && s.vnPlayBtnActive]}
                                onPress={() => playVoiceNote(note.id, note.audio_url)}
                                data-testid={`play-voice-note-${i}`}
                              >
                                <Ionicons name={isPlaying ? 'pause' : 'play'} size={16} color={isPlaying ? '#000' : '#34C759'} />
                              </TouchableOpacity>
                              <View style={{ flex: 1, marginLeft: 10 }}>
                                <Text style={s.vnCardDate}>{formatEventTime(note.created_at)}</Text>
                                <Text style={s.vnCardDuration}>{formatRecordingTime(Math.round(note.duration))}</Text>
                              </View>
                              <TouchableOpacity onPress={() => deleteVoiceNote(note.id)} style={{ padding: 4 }} data-testid={`delete-voice-note-${i}`}>
                                <Ionicons name="trash-outline" size={16} color={colors.textTertiary} />
                              </TouchableOpacity>
                            </View>
                            {note.transcript ? (
                              <Text style={s.vnTranscript} numberOfLines={expandedEvents[1000 + i] ? undefined : 3}>
                                {note.transcript}
                              </Text>
                            ) : (
                              <Text style={[s.vnTranscript, { fontStyle: 'italic', color: colors.textTertiary }]}>Transcribing...</Text>
                            )}
                            {note.transcript && note.transcript.length > 120 && (
                              <TouchableOpacity onPress={() => setExpandedEvents(prev => ({ ...prev, [1000 + i]: !prev[1000 + i] }))}>
                                <Text style={{ color: '#007AFF', fontSize: 12, marginTop: 4 }}>
                                  {expandedEvents[1000 + i] ? 'Show less' : 'Read full transcript'}
                                </Text>
                              </TouchableOpacity>
                            )}
                          </View>
                        );
                      })}
                      {voiceNotes.length > 1 && (
                        <TouchableOpacity
                          style={s.showMoreBtn}
                          onPress={() => setShowAllNotes(!showAllNotes)}
                          data-testid="show-more-voice-notes"
                        >
                          <Text style={s.showMoreText}>
                            {showAllNotes ? 'Show Latest Only' : `Show All ${voiceNotes.length} Voice Notes`}
                          </Text>
                          <Ionicons name={showAllNotes ? 'chevron-up' : 'chevron-down'} size={16} color="#007AFF" />
                        </TouchableOpacity>
                      )}
                    </View>
                  ) : null}
                </View>
              )}

              {/* Notes (editable view in details) */}
              {contact.notes ? (
                <View style={s.section}>
                  <Text style={s.sectionHeader}>Notes</Text>
                  <Text style={s.viewText}>{contact.notes}</Text>
                </View>
              ) : null}

              {/* Important Dates */}
              {(contact.birthday || contact.anniversary || contact.date_sold || contact.custom_dates.length > 0) && (
                <View style={s.section}>
                  <Text style={s.sectionHeader}>Important Dates</Text>
                  {contact.birthday && (
                    <View style={s.viewRow}>
                      <Ionicons name="gift" size={16} color="#FF9500" />
                      <Text style={s.viewRowLabel}>Birthday</Text>
                      <Text style={s.viewRowValue}>{format(contact.birthday, 'MMM d, yyyy')}</Text>
                    </View>
                  )}
                  {contact.anniversary && (
                    <View style={s.viewRow}>
                      <Ionicons name="heart" size={16} color="#FF2D55" />
                      <Text style={s.viewRowLabel}>Anniversary</Text>
                      <Text style={s.viewRowValue}>{format(contact.anniversary, 'MMM d, yyyy')}</Text>
                    </View>
                  )}
                  {contact.date_sold && (
                    <View style={s.viewRow}>
                      <Ionicons name="car" size={16} color="#34C759" />
                      <Text style={s.viewRowLabel}>Date Sold</Text>
                      <Text style={s.viewRowValue}>{format(contact.date_sold, 'MMM d, yyyy')}</Text>
                    </View>
                  )}
                  {contact.custom_dates.map((cd, i) => cd.date && (
                    <View key={i} style={s.viewRow}>
                      <Ionicons name="calendar-outline" size={16} color="#007AFF" />
                      <Text style={s.viewRowLabel}>{cd.name}</Text>
                      <Text style={s.viewRowValue}>{format(cd.date, 'MMM d, yyyy')}</Text>
                    </View>
                  ))}
                </View>
              )}

              {/* Referrals */}
              {(contact.referred_by_name || referrals.length > 0) && (
                <View style={s.section}>
                  <Text style={s.sectionHeader}>Referrals</Text>
                  {contact.referred_by_name && (
                    <View style={s.viewRow}>
                      <Ionicons name="people" size={16} color="#34C759" />
                      <Text style={s.viewRowLabel}>Referred by</Text>
                      <Text style={s.viewRowValue}>{contact.referred_by_name}</Text>
                    </View>
                  )}
                  {contact.referral_count > 0 && (
                    <View style={s.viewRow}>
                      <Ionicons name="trophy" size={16} color="#FF9500" />
                      <Text style={s.viewRowLabel}>Referred</Text>
                      <Text style={s.viewRowValue}>{contact.referral_count} customer{contact.referral_count > 1 ? 's' : ''}</Text>
                    </View>
                  )}
                  {referrals.map(r => (
                    <TouchableOpacity key={r._id} style={s.referralItem} onPress={() => router.push(`/contact/${r._id}`)}>
                      <View style={s.referralAvatar}><Text style={s.referralAvatarText}>{r.first_name?.[0]}{r.last_name?.[0]}</Text></View>
                      <Text style={s.referralName}>{r.first_name} {r.last_name || ''}</Text>
                      <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              {/* Campaigns */}
              {contactEnrollments.length > 0 && (
                <View style={s.section}>
                  <Text style={s.sectionHeader}>Campaigns</Text>
                  {contactEnrollments.map((e, i) => (
                    <View key={i} style={s.campaignCard}>
                      <View style={[s.quickActionIcon, { backgroundColor: e.status === 'completed' ? '#34C75920' : '#007AFF20' }]}>
                        <Ionicons name={e.status === 'completed' ? 'checkmark-circle' : 'play-circle'} size={18}
                          color={e.status === 'completed' ? '#34C759' : '#007AFF'} />
                      </View>
                      <View style={{ flex: 1, marginLeft: 12 }}>
                        <Text style={s.campaignName}>{e.campaign_name}</Text>
                        <Text style={s.campaignSub}>
                          {e.status === 'completed' ? 'Completed' : `Step ${e.current_step} of ${e.total_steps}`}
                        </Text>
                      </View>
                    </View>
                  ))}
                </View>
              )}
            </>
          )}

          {/* ===== REMAINING EDIT FIELDS ===== */}
          {isEditing && (
            <>
              {/* Referral */}
              <View style={s.section}>
                <Text style={s.sectionHeader}>Referral</Text>
                <TouchableOpacity style={s.dateRow} onPress={() => { loadAllContacts(); setShowReferralPicker(true); }}>
                  <View style={[s.dateRowIcon, { backgroundColor: '#34C75920' }]}>
                    <Ionicons name="people" size={18} color="#34C759" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.dateRowLabel}>Referred By</Text>
                    <Text style={[s.dateRowValue, !contact.referred_by_name && { color: colors.textTertiary }]}>
                      {contact.referred_by_name || 'Select referrer'}
                    </Text>
                  </View>
                  {contact.referred_by ? (
                    <TouchableOpacity onPress={clearReferrer} style={{ padding: 4 }}>
                      <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
                    </TouchableOpacity>
                  ) : (
                    <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                  )}
                </TouchableOpacity>
                {contact.referred_by && (
                  <View style={s.inputGroup}>
                    <Text style={s.inputLabel}>Referral Notes</Text>
                    <TextInput style={s.input} placeholder="How did they refer?" placeholderTextColor={colors.textTertiary}
                      value={contact.referral_notes} onChangeText={t => setContact({ ...contact, referral_notes: t })} />
                  </View>
                )}
              </View>

              {/* Notes */}
              <View style={s.section}>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text style={[s.sectionHeader, { marginBottom: 0 }]}>Notes</Text>
                  <VoiceInput
                    onTranscription={(text: string) => setContact({ ...contact, notes: contact.notes + ' ' + text })}
                    size="small" color={colors.textSecondary}
                  />
                </View>
                <TextInput style={[s.input, { minHeight: 100, textAlignVertical: 'top', marginTop: 8 }]}
                  placeholder="Add notes..." placeholderTextColor={colors.textTertiary} value={contact.notes}
                  onChangeText={t => setContact({ ...contact, notes: t })} multiline data-testid="input-notes" />
              </View>

              {/* Delete */}
              {!isNewContact && (
                <TouchableOpacity onPress={handleDelete} style={s.deleteBtn} data-testid="delete-contact-button">
                  <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                  <Text style={s.deleteBtnText}>Delete Contact</Text>
                </TouchableOpacity>
              )}
            </>
          )}

          <View style={{ height: 140 }} />
        </ScrollView>

        {/* ===== INLINE COMPOSER (Inbox-Style) ===== */}
        {!isNewContact && !isEditing && (
          <View style={s.composerContainer} data-testid="contact-composer">
            {/* SMS/Email mode toggle */}
            <View style={s.composerModeRow}>
              <TouchableOpacity
                style={[s.composerModeBtn, composerMode === 'sms' && s.composerModeBtnActive]}
                onPress={() => setComposerMode('sms')}
                data-testid="composer-mode-sms"
              >
                <Ionicons name="chatbubble" size={14} color={composerMode === 'sms' ? '#34C759' : colors.textTertiary} />
                <Text style={[s.composerModeBtnText, composerMode === 'sms' && { color: '#34C759' }]}>SMS</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[s.composerModeBtn, composerMode === 'email' && s.composerModeBtnActive]}
                onPress={() => setComposerMode('email')}
                data-testid="composer-mode-email"
              >
                <Ionicons name="mail" size={14} color={composerMode === 'email' ? '#AF52DE' : colors.textTertiary} />
                <Text style={[s.composerModeBtnText, composerMode === 'email' && { color: '#AF52DE' }]}>Email</Text>
              </TouchableOpacity>
              <View style={{ flex: 1 }} />
              <TouchableOpacity
                style={s.composerCallBtn}
                onPress={() => {
                  if (!contact.phone) { showSimpleAlert('Missing Info', 'No phone number'); return; }
                  const contactName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
                  router.push(`/call-screen?contact_id=${id}&contact_name=${encodeURIComponent(contactName)}&phone=${encodeURIComponent(contact.phone)}`);
                }}
                data-testid="composer-call-btn"
              >
                <Ionicons name="call" size={16} color="#32ADE6" />
              </TouchableOpacity>
            </View>

            {/* AI Suggestion bubble */}
            {showAISuggestion && aiSuggestion ? (
              <View style={s.aiSuggestionBubble} data-testid="ai-suggestion-bubble">
                <View style={s.aiSuggestionHeader}>
                  <Ionicons name="sparkles" size={14} color="#34C759" />
                  <Text style={s.aiSuggestionLabel}>AI Suggestion</Text>
                  <TouchableOpacity onPress={() => { setShowAISuggestion(false); setAiSuggestion(''); }}>
                    <Ionicons name="close-circle" size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                </View>
                <Text style={s.aiSuggestionText}>{aiSuggestion}</Text>
                <View style={s.aiSuggestionActions}>
                  <TouchableOpacity
                    style={s.aiActionBtn}
                    onPress={() => { setComposerMessage(aiSuggestion); setShowAISuggestion(false); }}
                    data-testid="ai-edit-btn"
                  >
                    <Ionicons name="pencil" size={14} color="#007AFF" />
                    <Text style={s.aiActionBtnText}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[s.aiActionBtn, s.aiActionBtnSend]}
                    onPress={() => { handleComposerSend(aiSuggestion); setShowAISuggestion(false); setAiSuggestion(''); }}
                    data-testid="ai-send-btn"
                  >
                    <Ionicons name="send" size={14} color={colors.text} />
                    <Text style={[s.aiActionBtnText, { color: colors.text }]}>Send Now</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : null}

            {/* Composer box */}
            <View style={[s.composerBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <TextInput
                style={[s.composerInput, { color: colors.text }]}
                placeholder="Type your message..."
                placeholderTextColor={colors.textTertiary}
                value={composerMessage}
                onChangeText={setComposerMessage}
                multiline
                maxLength={1000}
                data-testid="composer-input"
              />
              <View style={[s.composerToolbar, { backgroundColor: colors.bg, borderTopColor: colors.border }]}>
                <View style={s.composerTools}>
                  {/* Photo */}
                  <TouchableOpacity style={s.composerToolBtn} onPress={handleAttachPhoto} data-testid="toolbar-photo-btn">
                    <Ionicons name="image-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                  {/* Templates */}
                  <TouchableOpacity style={s.composerToolBtn} onPress={() => setShowTemplates(true)} data-testid="toolbar-templates-btn">
                    <Ionicons name="document-text-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                  {/* Review Link */}
                  <TouchableOpacity style={s.composerToolBtn} onPress={() => setShowReviewLinks(true)} data-testid="toolbar-review-btn">
                    <Ionicons name="star-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                  {/* Business Card */}
                  <TouchableOpacity style={s.composerToolBtn} onPress={openBusinessCardPicker} data-testid="toolbar-card-btn">
                    <Ionicons name="card-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                  {/* Voice to Text */}
                  <TouchableOpacity
                    style={[s.composerToolBtn, isVoiceRecording && { backgroundColor: '#FF3B3020', borderRadius: 16 }]}
                    onPress={handleVoiceToText}
                    data-testid="toolbar-voice-btn"
                  >
                    {voiceTranscribing ? (
                      <ActivityIndicator size="small" color="#FF9500" />
                    ) : (
                      <Ionicons name={isVoiceRecording ? 'stop-circle' : 'mic-outline'} size={22} color={isVoiceRecording ? '#FF3B30' : colors.textSecondary} />
                    )}
                  </TouchableOpacity>
                  {/* AI Sparkle */}
                  <TouchableOpacity
                    style={[s.composerToolBtn, loadingAI && { opacity: 0.5 }]}
                    onPress={loadAISuggestionForComposer}
                    disabled={loadingAI}
                    data-testid="ai-sparkle-btn"
                  >
                    {loadingAI ? (
                      <ActivityIndicator size="small" color="#AF52DE" />
                    ) : (
                      <Ionicons name="sparkles" size={20} color="#AF52DE" />
                    )}
                  </TouchableOpacity>
                </View>
                {/* Send button */}
                {IS_WEB ? (
                  <button
                    type="button"
                    onClick={() => handleComposerSend()}
                    disabled={!composerMessage.trim() || composerSending}
                    data-testid="composer-send-btn"
                    style={{
                      width: 36, height: 36, borderRadius: 18,
                      backgroundColor: composerMessage.trim() && !composerSending
                        ? (composerMode === 'sms' ? '#34C759' : '#AF52DE')
                        : colors.borderLight,
                      border: 'none',
                      cursor: !composerMessage.trim() || composerSending ? 'not-allowed' : 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    {composerSending ? (
                      <ActivityIndicator size="small" color={colors.text} />
                    ) : (
                      <Ionicons
                        name={composerMode === 'sms' ? 'send' : 'mail'}
                        size={18}
                        color={composerMessage.trim() ? '#FFF' : '#6E6E73'}
                      />
                    )}
                  </button>
                ) : (
                  <TouchableOpacity
                    style={[s.composerSendBtn, { backgroundColor: composerMode === 'sms' ? '#34C759' : '#AF52DE' },
                      (!composerMessage.trim() || composerSending) && { backgroundColor: colors.borderLight }]}
                    onPress={() => handleComposerSend()}
                    disabled={!composerMessage.trim() || composerSending}
                    data-testid="composer-send-btn"
                  >
                    {composerSending ? (
                      <ActivityIndicator size="small" color={colors.text} />
                    ) : (
                      <Ionicons name={composerMode === 'sms' ? 'send' : 'mail'} size={18} color={composerMessage.trim() ? '#FFF' : '#6E6E73'} />
                    )}
                  </TouchableOpacity>
                )}
              </View>
            </View>
          </View>
        )}
      </KeyboardAvoidingView>

      {/* ===== MODALS ===== */}

      {/* Review Links Action Sheet */}
      <Modal visible={showReviewLinks} animationType="slide" transparent={true}>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setShowReviewLinks(false)}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={s.actionSheetGroup}>
              {storeSlug && (
                <>
                  <TouchableOpacity
                    style={s.actionSheetButton}
                    data-testid="review-link-imos"
                    onPress={() => {
                      const firstName = contact.first_name || 'there';
                      const reviewUrl = `https://app.imosapp.com/review/${storeSlug}?sp=${user?._id}`;
                      const reviewMsg = `Hey ${firstName}! We'd love your feedback. Leave us a review here: ${reviewUrl}`;
                      setShowReviewLinks(false);
                      setComposerMessage(reviewMsg);
                    }}
                  >
                    <Ionicons name="star" size={22} color="#FFD60A" />
                    <Text style={s.actionSheetButtonText}>Send Review Request</Text>
                  </TouchableOpacity>
                  <View style={s.actionSheetDivider} />
                </>
              )}
              {Object.entries(reviewLinks).filter(([_, url]) => url).map(([platformId, url], index, arr) => {
                const platformNames: Record<string, {name: string; icon: string; color: string}> = {
                  google: { name: 'Google Reviews', icon: 'logo-google', color: '#4285F4' },
                  facebook: { name: 'Facebook', icon: 'logo-facebook', color: '#1877F2' },
                  yelp: { name: 'Yelp', icon: 'star', color: '#D32323' },
                  trustpilot: { name: 'Trustpilot', icon: 'shield-checkmark', color: '#00B67A' },
                  custom: { name: customLinkName || 'Custom Link', icon: 'link', color: colors.textSecondary },
                };
                const platform = platformNames[platformId] || platformNames.custom;
                return (
                  <React.Fragment key={platformId}>
                    <TouchableOpacity style={s.actionSheetButton} onPress={() => insertReviewLink(platformId, url, platform.name)}>
                      <Ionicons name={platform.icon as any} size={22} color={platform.color} />
                      <Text style={s.actionSheetButtonText}>{platform.name}</Text>
                    </TouchableOpacity>
                    {index < arr.length - 1 && <View style={s.actionSheetDivider} />}
                  </React.Fragment>
                );
              })}
              {!storeSlug && Object.keys(reviewLinks).length === 0 && (
                <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowReviewLinks(false); router.push('/settings/review-links' as any); }}>
                  <Ionicons name="settings-outline" size={22} color="#007AFF" />
                  <Text style={s.actionSheetButtonText}>Set Up Review Links</Text>
                </TouchableOpacity>
              )}
              {(storeSlug || Object.keys(reviewLinks).length > 0) && (
                <>
                  <View style={s.actionSheetDivider} />
                  <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowReviewLinks(false); router.push('/settings/review-links' as any); }}>
                    <Ionicons name="settings-outline" size={22} color={colors.textSecondary} />
                    <Text style={[s.actionSheetButtonText, { color: colors.textSecondary, fontSize: 16 }]}>Manage Review Links</Text>
                  </TouchableOpacity>
                </>
              )}
            </View>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setShowReviewLinks(false)}>
              <Text style={s.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Templates Modal */}
      <Modal visible={showTemplates} animationType="slide" presentationStyle="pageSheet" transparent={true}>
        <TouchableOpacity style={s.toolbarModalOverlay} activeOpacity={1} onPress={() => setShowTemplates(false)}>
          <View style={s.toolbarModal} onStartShouldSetResponder={() => true}>
            <View style={s.toolbarModalHeader}>
              <View style={s.toolbarModalHandle} />
              <Text style={s.toolbarModalTitle}>Message Templates</Text>
            </View>
            <FlatList
              data={templates}
              keyExtractor={(item) => item._id}
              style={s.toolbarTemplatesList}
              contentContainerStyle={s.toolbarTemplatesListContent}
              showsVerticalScrollIndicator={true}
              renderItem={({ item: template }) => (
                <TouchableOpacity style={s.toolbarTemplateItem} onPress={() => selectTemplate(template)}>
                  <View style={s.toolbarTemplateIcon}>
                    <Ionicons name="document-text" size={20} color="#007AFF" />
                  </View>
                  <View style={s.toolbarTemplateContent}>
                    <Text style={s.toolbarTemplateName}>{template.name}</Text>
                    <Text style={s.toolbarTemplatePreview} numberOfLines={2}>{template.content}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
              ListEmptyComponent={() => (
                <View style={s.toolbarEmptyTemplates}>
                  <Ionicons name="document-text-outline" size={48} color={colors.textSecondary} />
                  <Text style={s.toolbarEmptyTemplatesText}>No templates yet</Text>
                </View>
              )}
            />
            <View style={s.toolbarModalFooter}>
              <TouchableOpacity style={s.toolbarModalCloseBtn} onPress={() => setShowTemplates(false)}>
                <Text style={s.toolbarModalCloseBtnText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Digital Business Card Modal */}
      <Modal visible={showBusinessCard} animationType="slide" presentationStyle="pageSheet" transparent={true}>
        <TouchableOpacity style={s.toolbarModalOverlay} activeOpacity={1} onPress={() => setShowBusinessCard(false)}>
          <View style={s.toolbarModal} onStartShouldSetResponder={() => true}>
            <View style={s.toolbarModalHeader}>
              <View style={s.toolbarModalHandle} />
            </View>
            <View style={s.cardModalContent}>
              <View style={s.cardPreview}>
                <Ionicons name="share-social" size={48} color="#007AFF" />
                <Text style={s.cardPreviewTitle}>Share Your Stuff</Text>
                <Text style={s.cardPreviewDesc}>Choose what you'd like to send to {contact.first_name || 'this contact'}</Text>
              </View>
              <View style={s.shareOptionsContainer}>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendVCardLink} data-testid="share-vcf-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="person-add" size={28} color="#34C759" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Contact (VCF)</Text>
                    <Text style={s.shareOptionDesc}>Send a direct link to save your contact info to their phone</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendBusinessCardLink} data-testid="share-landing-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="globe-outline" size={28} color="#007AFF" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Landing Page</Text>
                    <Text style={s.shareOptionDesc}>Send your full digital card with socials, bio & more</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendShowcaseLink} data-testid="share-showcase-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="images-outline" size={28} color="#FF9500" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Showcase</Text>
                    <Text style={s.shareOptionDesc}>Show off your happy customers & featured work</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendLinkPageLink} data-testid="share-linkpage-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="link-outline" size={28} color="#AF52DE" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Link Page</Text>
                    <Text style={s.shareOptionDesc}>Send all your social links in one place</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
              {showLandingPageOptions && (
                <View style={s.landingPageOptions}>
                  <View style={s.landingPageOptionsHeader}>
                    <TouchableOpacity onPress={() => setShowLandingPageOptions(false)}>
                      <Ionicons name="arrow-back" size={24} color="#007AFF" />
                    </TouchableOpacity>
                    <Text style={s.landingPageOptionsTitle}>Landing Page Options</Text>
                  </View>
                  <Text style={s.campaignPickerLabel}>Start them on a campaign (optional):</Text>
                  {loadingCampaigns ? (
                    <ActivityIndicator size="small" color="#007AFF" style={{ marginVertical: 20 }} />
                  ) : campaigns.length === 0 ? (
                    <View style={s.noCampaigns}>
                      <Text style={s.noCampaignsText}>No active campaigns</Text>
                      <Text style={s.noCampaignsSubtext}>Create campaigns in the Campaigns tab</Text>
                    </View>
                  ) : (
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.campaignScroller} contentContainerStyle={s.campaignScrollerContent}>
                      <TouchableOpacity style={[s.campaignChip, !selectedCampaign && s.campaignChipSelected]} onPress={() => setSelectedCampaign(null)}>
                        <Text style={[s.campaignChipText, !selectedCampaign && s.campaignChipTextSelected]}>None</Text>
                      </TouchableOpacity>
                      {campaigns.map((campaign: any) => (
                        <TouchableOpacity key={campaign.id || campaign._id} style={[s.campaignChip, selectedCampaign === (campaign.id || campaign._id) && s.campaignChipSelected]} onPress={() => setSelectedCampaign(campaign.id || campaign._id)}>
                          <Text style={[s.campaignChipText, selectedCampaign === (campaign.id || campaign._id) && s.campaignChipTextSelected]}>{campaign.name}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  )}
                  <TouchableOpacity style={s.sendCardButton} onPress={sendBusinessCardLink} data-testid="send-card-btn">
                    <Ionicons name="paper-plane" size={20} color="#FFF" />
                    <Text style={s.sendCardButtonText}>{selectedCampaign ? 'Send Card + Start Campaign' : 'Send Landing Page'}</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
            <View style={s.toolbarModalFooter}>
              <TouchableOpacity style={s.toolbarModalCloseBtn} onPress={() => { setShowBusinessCard(false); setShowLandingPageOptions(false); }}>
                <Text style={s.toolbarModalCloseBtnText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Photo & Card Action Sheet (Web/PWA) */}
      <Modal visible={showPhotoOptionsModal} animationType="slide" transparent={true} onRequestClose={() => setShowPhotoOptionsModal(false)}>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setShowPhotoOptionsModal(false)}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={s.actionSheetGroup}>
              <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowPhotoOptionsModal(false); pickImage(); }} data-testid="photo-option-library">
                <Ionicons name="images-outline" size={22} color="#007AFF" />
                <Text style={s.actionSheetButtonText}>Photo Library</Text>
              </TouchableOpacity>
              <View style={s.actionSheetDivider} />
              <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowPhotoOptionsModal(false); pickImage(); }} data-testid="photo-option-camera">
                <Ionicons name="camera-outline" size={22} color="#007AFF" />
                <Text style={s.actionSheetButtonText}>Take Photo</Text>
              </TouchableOpacity>
              <View style={s.actionSheetDivider} />
              <View style={{ paddingVertical: 12, paddingHorizontal: 16 }}>
                <Text style={{ fontSize: 13, color: colors.textSecondary, fontWeight: '600', marginBottom: 10, textAlign: 'center' }}>CREATE A CARD</Text>
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
                      onPress={() => { setShowPhotoOptionsModal(false); handleCardTemplateSelect(item.type); }}
                      data-testid={`card-template-${item.type}`}
                    >
                      <Ionicons name={item.icon as any} size={24} color={item.color} />
                      <Text style={{ fontSize: 12, fontWeight: '600', color: item.color, marginTop: 6 }}>{item.label}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            </View>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setShowPhotoOptionsModal(false)} data-testid="photo-option-cancel">
              <Text style={s.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Card Template Picker */}
      <Modal visible={showCardTemplatePicker} animationType="fade" transparent onRequestClose={() => setShowCardTemplatePicker(false)}>
        <TouchableOpacity style={s.sendPickerOverlay} activeOpacity={1} onPress={() => setShowCardTemplatePicker(false)}>
          <View style={s.sendPickerSheet} onStartShouldSetResponder={() => true}>
            <View style={s.sendPickerHandle} />
            <Text style={s.sendPickerTitle}>Choose a Card Template</Text>
            {[
              { type: 'congrats', label: 'Congratulations', sub: 'Celebrate a purchase or milestone', color: '#C9A962', icon: 'trophy' },
              { type: 'birthday', label: 'Happy Birthday', sub: 'Send birthday wishes', color: '#FF2D55', icon: 'gift' },
              { type: 'anniversary', label: 'Anniversary', sub: 'Celebrate their anniversary', color: '#FF6B6B', icon: 'heart' },
              { type: 'thankyou', label: 'Thank You', sub: 'Show your appreciation', color: '#34C759', icon: 'thumbs-up' },
              { type: 'welcome', label: 'Welcome', sub: 'Welcome a new customer', color: '#007AFF', icon: 'hand-left' },
              { type: 'holiday', label: 'Holiday', sub: 'Seasonal greetings', color: '#5AC8FA', icon: 'snow' },
            ].map(item => (
              <TouchableOpacity
                key={item.type}
                style={s.sendPickerItem}
                onPress={() => handleCardTemplateSelect(item.type)}
                activeOpacity={0.7}
                data-testid={`card-template-${item.type}`}
              >
                <View style={[s.sendPickerIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={item.icon as any} size={20} color={item.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.sendPickerLabel}>{item.label}</Text>
                  <Text style={s.sendPickerSub}>{item.sub}</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.borderLight} />
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>


      {/* Referral Picker */}
      <Modal visible={showReferralPicker} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowReferralPicker(false)}>
              <Text style={s.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>Select Referrer</Text>
            <View style={{ width: 60 }} />
          </View>
          <View style={s.modalSearch}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput style={s.modalSearchInput} placeholder="Search contacts" placeholderTextColor={colors.textSecondary}
              value={contactSearch} onChangeText={setContactSearch} />
          </View>
          <FlatList data={filteredContacts} keyExtractor={i => i._id} renderItem={({ item }) => (
            <TouchableOpacity style={s.pickerItem} onPress={() => selectReferrer(item)}>
              <View style={s.pickerAvatar}><Text style={s.pickerAvatarText}>{item.first_name?.[0]}{item.last_name?.[0] || ''}</Text></View>
              <View style={{ flex: 1 }}><Text style={s.pickerName}>{item.first_name} {item.last_name || ''}</Text><Text style={s.pickerSub}>{item.phone}</Text></View>
            </TouchableOpacity>
          )} ListEmptyComponent={<View style={s.emptyPicker}><Text style={s.emptyPickerText}>No contacts found</Text></View>} />
        </SafeAreaView>
      </Modal>

      {/* Tag Picker */}
      <Modal visible={showTagPicker} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => { setShowTagPicker(false); setTagSearch(''); }}>
              <Text style={s.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>Select Tag</Text>
            <TouchableOpacity onPress={() => { setShowTagPicker(false); setTagSearch(''); router.push('/settings/tags' as any); }}>
              <Text style={s.modalAction}>Manage</Text>
            </TouchableOpacity>
          </View>
          <View style={s.modalSearch}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput style={s.modalSearchInput} placeholder="Search tags..." placeholderTextColor={colors.textSecondary}
              value={tagSearch} onChangeText={setTagSearch} autoCapitalize="none" />
          </View>
          <ScrollView style={{ flex: 1 }}>
            {filteredAvailableTags.length > 0 ? filteredAvailableTags.map(tag => (
              <TouchableOpacity key={tag._id} style={s.pickerItem} onPress={() => isEditing ? addTag(tag.name) : addTagFromHero(tag.name)} data-testid={`tag-option-${tag.name}`}>
                <View style={[s.dateRowIcon, { backgroundColor: `${tag.color}20` }]}>
                  <Ionicons name={tag.icon || 'pricetag'} size={18} color={tag.color} />
                </View>
                <View style={{ flex: 1 }}><Text style={s.pickerName}>{tag.name}</Text></View>
                <Ionicons name="add-circle" size={24} color={tag.color} />
              </TouchableOpacity>
            )) : (
              <View style={s.emptyPicker}><Text style={s.emptyPickerText}>No tags available</Text></View>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Campaign Picker */}
      <Modal visible={showCampaignPicker} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowCampaignPicker(false)}>
              <Text style={s.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>Enroll in Campaign</Text>
            <View style={{ width: 60 }} />
          </View>
          <FlatList data={availableCampaigns} keyExtractor={i => i._id} contentContainerStyle={{ padding: 16 }}
            renderItem={({ item }) => (
              <TouchableOpacity style={s.campaignCard} onPress={() => enrollInCampaign(item)}>
                <View style={[s.quickActionIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="calendar" size={20} color="#007AFF" />
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={s.campaignName}>{item.name}</Text>
                  <Text style={s.campaignSub}>{item.sequences?.length || 0} steps</Text>
                </View>
                <Ionicons name="add-circle" size={24} color="#007AFF" />
              </TouchableOpacity>
            )} ListEmptyComponent={<View style={s.emptyPicker}><Text style={s.emptyPickerText}>No available campaigns</Text></View>} />
        </SafeAreaView>
      </Modal>

      {/* Automation Edit Modal */}
      {editingAutomation && (
        <Modal visible={!!editingAutomation} animationType="fade" transparent onRequestClose={() => setEditingAutomation(null)}>
          <TouchableOpacity style={s.labelOverlay} activeOpacity={1} onPress={() => setEditingAutomation(null)}>
            <TouchableOpacity activeOpacity={1} style={s.labelModal} onPress={() => {}}>
              <Text style={s.labelTitle}>Edit {editingAutomation.label}</Text>
              <Text style={[s.labelSub, { color: editingAutomation.color }]}>
                {editingAutomation.value ? formatDateUTC(editingAutomation.value, 'MMM d, yyyy') : 'No date set'}
              </Text>
              {IS_WEB ? (
                <input
                  type="date"
                  defaultValue={editingAutomation.value ? new Date(editingAutomation.value).toISOString().split('T')[0] : ''}
                  onChange={(e: any) => {
                    if (e.target.value) setAutomationPickerDate(new Date(e.target.value + 'T12:00:00'));
                  }}
                  style={{
                    width: '100%', padding: 12, borderRadius: 10,
                    backgroundColor: colors.surface, color: colors.text, border: '1px solid #3A3A3C',
                    fontSize: 16, marginBottom: 12, marginTop: 8,
                  }}
                  data-testid="automation-date-input"
                />
              ) : (
                <DateTimePicker
                  value={editingAutomation.value ? new Date(editingAutomation.value) : new Date()}
                  mode="date"
                  display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                  onChange={(_, d) => { if (d) setAutomationPickerDate(d); }}
                  textColor="#FFFFFF"
                  themeVariant="dark"
                  style={{ height: 150, marginVertical: 8 }}
                />
              )}
              <View style={{ flexDirection: 'row', gap: 12, marginTop: 4 }}>
                <TouchableOpacity
                  style={[s.labelBtn, { backgroundColor: colors.surface }]}
                  onPress={() => handleClearAutomation(editingAutomation.field)}
                  data-testid="automation-clear-btn"
                >
                  <Text style={{ fontSize: 16, fontWeight: '600', color: '#FF3B30' }}>Clear Date</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.labelBtn, { backgroundColor: editingAutomation.color || '#007AFF' }]}
                  onPress={() => handleUpdateAutomationDate(editingAutomation.field, automationPickerDate)}
                  data-testid="automation-save-btn"
                >
                  <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>Save Date</Text>
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          </TouchableOpacity>
        </Modal>
      )}

      {/* Date Picker */}
      {showDatePicker && (
        <Modal visible={showDatePicker} animationType={IS_WEB ? 'none' : 'slide'} transparent onRequestClose={() => setShowDatePicker(false)}>
          <View style={s.dateOverlay}>
            <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={() => setShowDatePicker(false)} />
            <View style={[s.dateModal, IS_WEB && { minHeight: 400 }]}>
              <View style={s.dateModalHeader}>
                <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                  <Text style={{ fontSize: 17, color: '#FF3B30' }}>Cancel</Text>
                </TouchableOpacity>
                <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>{activeDateLabel}</Text>
                <TouchableOpacity onPress={confirmDateSelection}>
                  <Text style={{ fontSize: 17, fontWeight: '600', color: '#007AFF' }}>Done</Text>
                </TouchableOpacity>
              </View>
              {IS_WEB ? (
                <View style={{ flexDirection: 'row', paddingHorizontal: 20, paddingVertical: 16, gap: 12 }}>
                  {/* Month */}
                  <View style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={s.webPickerLabel}>MONTH</Text>
                    <ScrollView style={s.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {months.map((m, i) => (
                        <TouchableOpacity key={m} style={[s.webPickerItem, webMonth === i && s.webPickerItemSel]}
                          onPress={() => { setWebMonth(i); const max = getDaysInMonth(i, webYear); if (webDay > max) setWebDay(max); }}>
                          <Text style={[s.webPickerText, webMonth === i && s.webPickerTextSel]}>{m}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                  {/* Day */}
                  <View style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={s.webPickerLabel}>DAY</Text>
                    <ScrollView style={s.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {Array.from({ length: getDaysInMonth(webMonth, webYear) }, (_, i) => i + 1).map(d => (
                        <TouchableOpacity key={d} style={[s.webPickerItem, webDay === d && s.webPickerItemSel]}
                          onPress={() => setWebDay(d)}>
                          <Text style={[s.webPickerText, webDay === d && s.webPickerTextSel]}>{d}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                  {/* Year */}
                  <View style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={s.webPickerLabel}>YEAR</Text>
                    <ScrollView style={s.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {Array.from({ length: 100 }, (_, i) => new Date().getFullYear() - 50 + i).map(y => (
                        <TouchableOpacity key={y} style={[s.webPickerItem, webYear === y && s.webPickerItemSel]}
                          onPress={() => { setWebYear(y); const max = getDaysInMonth(webMonth, y); if (webDay > max) setWebDay(max); }}>
                          <Text style={[s.webPickerText, webYear === y && s.webPickerTextSel]}>{y}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                </View>
              ) : (
                <DateTimePicker value={tempDate} mode="date" display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                  onChange={handleDateChange} textColor="#FFFFFF" themeVariant="dark" style={{ height: 200, marginHorizontal: 10 }}
                  maximumDate={new Date(2100, 11, 31)} minimumDate={new Date(1900, 0, 1)} />
              )}
              {(Platform.OS === 'ios' || IS_WEB) && (
                <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 16 }}>
                  <TouchableOpacity style={s.dateConfirmBtn} onPress={confirmDateSelection}>
                    <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>
                      Select {IS_WEB ? format(new Date(webYear, webMonth, webDay), 'MMM d, yyyy') : format(tempDate, 'MMM d, yyyy')}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </View>
        </Modal>
      )}

      {/* Custom Date Label Modal */}
      <Modal visible={showCustomDateLabel} animationType="fade" transparent onRequestClose={() => setShowCustomDateLabel(false)}>
        <TouchableOpacity style={s.labelOverlay} activeOpacity={1} onPress={() => setShowCustomDateLabel(false)}>
          <TouchableOpacity activeOpacity={1} style={s.labelModal} onPress={() => {}}>
            <Text style={s.labelTitle}>Name This Date</Text>
            <Text style={s.labelSub}>{pendingCustomDate ? format(pendingCustomDate, 'MMM d, yyyy') : ''}</Text>
            <TextInput style={s.labelInput} placeholder='e.g., "Lease Expiration"' placeholderTextColor={colors.textSecondary}
              value={newCustomDateName} onChangeText={setNewCustomDateName} returnKeyType="done" onSubmitEditing={confirmCustomDateWithLabel} />
            <View style={{ flexDirection: 'row', gap: 12 }}>
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: colors.surface }]} onPress={() => setShowCustomDateLabel(false)}>
                <Text style={{ fontSize: 16, fontWeight: '600', color: '#FF3B30' }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: '#007AFF' }]} onPress={confirmCustomDateWithLabel}>
                <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>Save</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* Full Photo Viewer Modal with Gallery */}
      <Modal visible={showPhotoViewer} animationType="fade" transparent onRequestClose={() => setShowPhotoViewer(false)}>
        <View style={s.photoViewerOverlay}>
          {IS_WEB ? (
            <button
              type="button"
              onClick={() => { setShowPhotoViewer(false); setFullPhoto(null); setAllPhotos([]); setSelectedPhotoIndex(-1); }}
              data-testid="close-photo-viewer"
              style={{ position: 'absolute', top: 16, right: 16, zIndex: 100, background: 'rgba(0,0,0,0.5)', border: 'none', borderRadius: 20, width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
            >
              <Ionicons name="close" size={28} color={colors.text} />
            </button>
          ) : (
            <TouchableOpacity
              style={s.photoViewerClose}
              onPress={() => { setShowPhotoViewer(false); setFullPhoto(null); setAllPhotos([]); setSelectedPhotoIndex(-1); }}
              data-testid="close-photo-viewer"
            >
              <Ionicons name="close" size={28} color={colors.text} />
            </TouchableOpacity>
          )}

          {fullPhotoLoading ? (
            <ActivityIndicator size="large" color="#C9A962" />
          ) : selectedPhotoIndex >= 0 && fullPhoto ? (
            <View style={s.photoViewerContent}>
              <Image
                source={{ uri: fullPhoto }}
                style={s.photoViewerImage}
                resizeMode="contain"
                data-testid="full-photo-image"
              />
              <Text style={s.photoViewerName}>
                {allPhotos[selectedPhotoIndex]?.label || `${contact.first_name} ${contact.last_name}`}
              </Text>
              {allPhotos[selectedPhotoIndex]?.date && (
                <Text style={s.photoViewerDate}>{new Date(allPhotos[selectedPhotoIndex].date).toLocaleDateString()}</Text>
              )}

              {/* Navigation arrows */}
              {allPhotos.length > 1 && (
                IS_WEB ? (
                  <div style={{ flexDirection: 'row', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, marginTop: 12 }}>
                    <button
                      type="button"
                      disabled={selectedPhotoIndex === 0}
                      onClick={() => { const prev = selectedPhotoIndex - 1; setSelectedPhotoIndex(prev); setFullPhoto(allPhotos[prev].url); }}
                      data-testid="photo-nav-prev"
                      style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.15)', border: 'none', cursor: selectedPhotoIndex === 0 ? 'not-allowed' : 'pointer', opacity: selectedPhotoIndex === 0 ? 0.3 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                      <Ionicons name="chevron-back" size={28} color={colors.text} />
                    </button>
                    <span style={{ color: colors.textSecondary, fontSize: 14 }}>{selectedPhotoIndex + 1} / {allPhotos.length}</span>
                    <button
                      type="button"
                      disabled={selectedPhotoIndex === allPhotos.length - 1}
                      onClick={() => { const next = selectedPhotoIndex + 1; setSelectedPhotoIndex(next); setFullPhoto(allPhotos[next].url); }}
                      data-testid="photo-nav-next"
                      style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.15)', border: 'none', cursor: selectedPhotoIndex === allPhotos.length - 1 ? 'not-allowed' : 'pointer', opacity: selectedPhotoIndex === allPhotos.length - 1 ? 0.3 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                      <Ionicons name="chevron-forward" size={28} color={colors.text} />
                    </button>
                  </div>
                ) : (
                  <View style={s.photoNavRow}>
                    <TouchableOpacity style={[s.photoNavBtn, selectedPhotoIndex === 0 && { opacity: 0.3 }]} disabled={selectedPhotoIndex === 0} onPress={() => { const prev = selectedPhotoIndex - 1; setSelectedPhotoIndex(prev); setFullPhoto(allPhotos[prev].url); }}>
                      <Ionicons name="chevron-back" size={28} color={colors.text} />
                    </TouchableOpacity>
                    <Text style={s.photoNavCount}>{selectedPhotoIndex + 1} / {allPhotos.length}</Text>
                    <TouchableOpacity style={[s.photoNavBtn, selectedPhotoIndex === allPhotos.length - 1 && { opacity: 0.3 }]} disabled={selectedPhotoIndex === allPhotos.length - 1} onPress={() => { const next = selectedPhotoIndex + 1; setSelectedPhotoIndex(next); setFullPhoto(allPhotos[next].url); }}>
                      <Ionicons name="chevron-forward" size={28} color={colors.text} />
                    </TouchableOpacity>
                  </View>
                )
              )}

              {/* Back to grid */}
              {allPhotos.length > 1 && (
                IS_WEB ? (
                  <button
                    type="button"
                    onClick={() => { setSelectedPhotoIndex(-1); setFullPhoto(null); }}
                    data-testid="back-to-gallery-grid"
                    style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: 8, padding: '8px 14px', marginTop: 8, cursor: 'pointer', color: colors.text, fontSize: 14 }}
                  >
                    <Ionicons name="grid-outline" size={18} color={colors.text} />
                    All Photos
                  </button>
                ) : (
                  <TouchableOpacity style={s.backToGridBtn} onPress={() => { setSelectedPhotoIndex(-1); setFullPhoto(null); }} data-testid="back-to-gallery-grid">
                    <Ionicons name="grid-outline" size={18} color={colors.text} />
                    <Text style={s.backToGridText}>All Photos</Text>
                  </TouchableOpacity>
                )
              )}

              {/* Set as Profile Photo */}
              {fullPhoto && allPhotos[selectedPhotoIndex]?.type !== 'profile' && (
                IS_WEB ? (
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await api.patch(`/contacts/${user._id}/${id}/profile-photo`, { photo_url: fullPhoto });
                        setContact((prev: any) => ({ ...prev, photo: fullPhoto, photo_url: fullPhoto, photo_thumbnail: fullPhoto }));
                        showToast('Profile photo updated!');
                      } catch (e: any) {
                        showSimpleAlert('Error', 'Failed to update profile photo');
                      }
                    }}
                    data-testid="set-as-profile-btn"
                    style={{
                      display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 6,
                      backgroundColor: '#C9A962', borderRadius: 10, border: 'none',
                      padding: '10px 16px', marginTop: 8, cursor: 'pointer',
                      fontSize: 14, fontWeight: 700, color: colors.text,
                    }}
                  >
                    <Ionicons name="person-circle" size={18} color={colors.text} />
                    Set as Profile Photo
                  </button>
                ) : (
                  <TouchableOpacity
                    style={s.setProfileBtn}
                    onPress={async () => {
                      try {
                        await api.patch(`/contacts/${user._id}/${id}/profile-photo`, { photo_url: fullPhoto });
                        setContact((prev: any) => ({ ...prev, photo: fullPhoto, photo_url: fullPhoto, photo_thumbnail: fullPhoto }));
                        showToast('Profile photo updated!');
                      } catch (e: any) {
                        showSimpleAlert('Error', 'Failed to update profile photo');
                      }
                    }}
                    data-testid="set-as-profile-btn"
                  >
                    <Ionicons name="person-circle" size={18} color={colors.text} />
                    <Text style={s.setProfileBtnText}>Set as Profile Photo</Text>
                  </TouchableOpacity>
                )
              )}
            </View>
          ) : allPhotos.length > 0 ? (
            /* === GALLERY GRID VIEW === */
            <View style={s.galleryGridContainer}>
              <Text style={s.galleryGridTitle}>Photos</Text>
              <Text style={s.galleryGridCount}>{allPhotos.length} photo{allPhotos.length !== 1 ? 's' : ''}</Text>
              <View style={s.galleryGrid}>
                {allPhotos.map((photo: any, idx: number) => (
                  <TouchableOpacity
                    key={`${photo.type}-${idx}`}
                    style={s.galleryTile}
                    onPress={() => {
                      setSelectedPhotoIndex(idx);
                      setFullPhoto(photo.url);
                    }}
                    data-testid={`gallery-tile-${idx}`}
                  >
                    <Image source={{ uri: photo.url }} style={s.galleryTileImg} resizeMode="cover" />
                    <View style={s.galleryTileBadge}>
                      <Text style={s.galleryTileBadgeText}>
                        {photo.type === 'profile' ? 'Profile' : photo.type === 'congrats' ? 'Congrats' : photo.type === 'birthday' ? 'Birthday' : photo.type}
                      </Text>
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ) : (
            <Text style={{ color: colors.textSecondary, fontSize: 16 }}>No photos available</Text>
          )}
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ===== STYLES =====
const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 12, paddingVertical: 12,
    borderBottomWidth: 1,
  },
  headerBtn: { padding: 4, minWidth: 50 },
  headerTitle: { fontSize: 17, fontWeight: '600', flex: 1, textAlign: 'center', color: colors.text },
  headerAction: { fontSize: 17, fontWeight: '600', color: '#C9A962' },
  scroll: { paddingBottom: 32 },

  // Hero section  - compact left-aligned
  heroSection: {
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12,
  },
  heroRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 14,
  },
  heroAvatarContainer: { position: 'relative' },
  heroAvatar: { width: 68, height: 68, borderRadius: 18, borderWidth: 2, borderColor: '#C9A962', resizeMode: 'cover' as const },
  heroAvatarPlaceholder: {
    width: 68, height: 68, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2,
  },
  heroInitials: { fontSize: 24, fontWeight: '700', color: '#C9A962' },
  heroCameraBadge: {
    position: 'absolute', bottom: -2, right: -2,
    width: 24, height: 24, borderRadius: 12,
    backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: colors.border,
  },
  touchpointBadge: {
    position: 'absolute', top: -4, right: -4,
    backgroundColor: '#C9A962', borderRadius: 10,
    minWidth: 20, height: 20, alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: 5, borderWidth: 2, borderColor: colors.border,
  },
  touchpointBadgeText: { fontSize: 10, fontWeight: '800', color: colors.text },
  heroInfo: { flex: 1, paddingTop: 2 },
  heroName: { fontSize: 20, fontWeight: '700', marginBottom: 4, color: colors.text },
  heroTagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 6 },
  heroTag: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingVertical: 2, paddingHorizontal: 7,
    borderRadius: 10, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.card,
  },
  heroTagText: { fontSize: 10, fontWeight: '600', color: colors.textSecondary },
  heroTagMore: { fontSize: 10, fontWeight: '600', color: colors.textTertiary, alignSelf: 'center' },
  heroTagAdd: {
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: '#007AFF20', borderWidth: 1, borderColor: '#007AFF40',
    alignItems: 'center', justifyContent: 'center',
    alignSelf: 'center',
  },
  heroHighlight: {
    flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 4,
  },
  heroHighlightText: { fontSize: 13, color: '#C9A962', fontWeight: '600' },
  heroMetaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  heroMetaItem: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  heroMetaText: { fontSize: 11, color: colors.textTertiary },
  // Compact stats line
  heroStatsLine: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border,
    gap: 4,
  },
  heroStatChip: { flexDirection: 'row', alignItems: 'baseline', gap: 3 },
  heroStatVal: { fontSize: 14, fontWeight: '700', color: colors.text },
  heroStatLbl: { fontSize: 11, color: colors.textTertiary },
  heroStatDot: { fontSize: 11, color: colors.textTertiary, marginHorizontal: 2 },

  // Hero tags strip
  heroTagsStrip: {
    paddingHorizontal: 16, paddingTop: 6, paddingBottom: 4,
  },
  heroTagsStripHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8,
  },
  heroTagsStripTitle: {
    fontSize: 11, fontWeight: '700', color: '#FF9500', textTransform: 'uppercase', letterSpacing: 0.5, flex: 1,
  },
  heroTagsStripAdd: {
    width: 22, height: 22, borderRadius: 11, backgroundColor: '#007AFF15',
    alignItems: 'center', justifyContent: 'center',
  },
  heroTagChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14,
    borderWidth: 1,
  },
  heroTagChipText: {
    fontSize: 12, fontWeight: '600', maxWidth: 120, color: colors.text,
  },
  heroTagsEmpty: {
    fontSize: 12, color: colors.textTertiary, fontStyle: 'italic', paddingBottom: 4,
  },

  // Hero campaigns strip
  heroCampaignsStrip: {
    paddingHorizontal: 16, paddingTop: 10, paddingBottom: 4,
    borderTopWidth: 1, borderTopColor: colors.border,
  },
  heroCampaignsHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8,
  },
  heroCampaignsTitle: {
    fontSize: 11, fontWeight: '700', color: '#AF52DE', textTransform: 'uppercase', letterSpacing: 0.5, flex: 1,
  },
  heroCampaignsAdd: {
    width: 22, height: 22, borderRadius: 11, backgroundColor: '#007AFF15',
    alignItems: 'center', justifyContent: 'center',
  },
  heroCampaignChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14,
    borderWidth: 1,
  },
  heroCampaignChipText: {
    fontSize: 12, fontWeight: '600', maxWidth: 120, color: colors.text,
  },
  heroCampaignStep: {
    fontSize: 10, fontWeight: '700', color: colors.text,
    paddingHorizontal: 4, paddingVertical: 1, borderRadius: 6,
  },
  heroCampaignDate: {
    fontSize: 10, fontWeight: '700', color: colors.text,
    paddingHorizontal: 5, paddingVertical: 1, borderRadius: 6,
  },

  // Tab bar (Feed / Details)
  tabBar: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 4,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tabBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabBtnActive: {
    borderBottomColor: '#C9A962',
  },
  tabBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textTertiary,
  },
  tabBtnTextActive: {
    color: colors.text,
  },

  // Pinned note (feed tab)
  pinnedNote: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: colors.card,
    borderRadius: 10,
    borderLeftWidth: 3,
    borderLeftColor: '#C9A962',
  },
  pinnedNoteText: {
    flex: 1,
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
  },

  // Sticky action bar → replaced by Composer
  stickyBar: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.border,
    paddingVertical: 8, paddingBottom: 12,
  },
  stickyBarInner: {
    flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12,
  },
  stickyBtn: { alignItems: 'center', gap: 4, paddingHorizontal: 8, minWidth: 50 },
  stickyBtnIcon: {
    width: 38, height: 38, borderRadius: 19,
    alignItems: 'center', justifyContent: 'center',
  },
  stickyBtnLabel: { fontSize: 9, color: colors.textSecondary, fontWeight: '600', textAlign: 'center' },

  // ===== INLINE COMPOSER =====
  composerContainer: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.border,
    paddingHorizontal: 12, paddingTop: 8, paddingBottom: 16,
  },
  composerModeRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8,
  },
  composerModeBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 5, borderRadius: 16,
    borderWidth: 1,
  },
  composerModeBtnActive: {
  },
  composerModeBtnText: {
    fontSize: 12, fontWeight: '600', color: colors.text,
  },
  composerCallBtn: {
    width: 32, height: 32, borderRadius: 16, backgroundColor: '#32ADE615',
    alignItems: 'center', justifyContent: 'center',
  },
  composerBox: {
    borderRadius: 16,
    borderWidth: 1, overflow: 'hidden',
  },
  composerInput: {
    fontSize: 16, color: colors.text,
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8,
    minHeight: 60, maxHeight: 160,
  },
  composerToolbar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 8, paddingVertical: 6,
    borderTopWidth: 1,
  },
  composerTools: {
    flexDirection: 'row', alignItems: 'center', gap: 2,
  },
  composerToolBtn: {
    width: 38, height: 34, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center',
  },
  composerSendBtn: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
  },
  // AI Suggestion bubble
  aiSuggestionBubble: {
    backgroundColor: '#1A2E1A', borderRadius: 14,
    padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#34C75930',
  },
  aiSuggestionHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8,
  },
  aiSuggestionLabel: {
    fontSize: 12, fontWeight: '700', color: '#34C759', flex: 1, textTransform: 'uppercase', letterSpacing: 0.5,
  },
  aiSuggestionText: {
    fontSize: 14, color: colors.textSecondary, lineHeight: 20, marginBottom: 10,
  },
  aiSuggestionActions: {
    flexDirection: 'row', gap: 8, justifyContent: 'flex-end',
  },
  aiActionBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  aiActionBtnSend: {
    backgroundColor: '#34C759', borderColor: '#34C759',
  },
  aiActionBtnText: {
    fontSize: 13, fontWeight: '600', color: '#007AFF',
  },
  // Toolbar Modals
  toolbarModalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-start', paddingTop: 20,
  },
  toolbarModal: {
    backgroundColor: colors.surface, borderRadius: 20, marginHorizontal: 10,
    flex: 1, marginBottom: 20,
  },
  toolbarModalHeader: {
    paddingTop: 12, paddingBottom: 16, paddingHorizontal: 20,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  toolbarModalHandle: {
    width: 36, height: 5, backgroundColor: colors.borderLight, borderRadius: 3,
    alignSelf: 'center', marginBottom: 16,
  },
  toolbarModalTitle: {
    fontSize: 20, fontWeight: '700', color: colors.text, textAlign: 'center',
  },
  toolbarTemplatesList: { flex: 1 },
  toolbarTemplatesListContent: { padding: 16, paddingBottom: 8 },
  toolbarModalFooter: {
    padding: 16, paddingBottom: 32, borderTopWidth: 1, borderTopColor: colors.border,
  },
  toolbarModalCloseBtn: {
    backgroundColor: colors.card, borderRadius: 12, padding: 16, alignItems: 'center',
  },
  toolbarModalCloseBtnText: { fontSize: 17, fontWeight: '600', color: '#FF3B30' },
  toolbarTemplateItem: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 12, padding: 14, marginBottom: 10,
  },
  toolbarTemplateIcon: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: '#007AFF20',
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  toolbarTemplateContent: { flex: 1 },
  toolbarTemplateName: { fontSize: 16, fontWeight: '600', color: colors.text },
  toolbarTemplatePreview: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  toolbarEmptyTemplates: { alignItems: 'center', paddingVertical: 40 },
  toolbarEmptyTemplatesText: { fontSize: 16, color: colors.textSecondary, marginTop: 12 },
  toolbarEmptyReviews: { alignItems: 'center', paddingVertical: 32 },
  toolbarEmptyReviewsText: { fontSize: 16, color: colors.textSecondary, marginTop: 12, marginBottom: 20 },
  toolbarSetupBtn: { backgroundColor: '#007AFF', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 20 },
  toolbarSetupBtnText: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  // Business Card Modal
  cardModalContent: { padding: 20 },
  cardPreview: {
    alignItems: 'center', backgroundColor: colors.card, borderRadius: 16, padding: 24, marginBottom: 20,
  },
  cardPreviewTitle: { fontSize: 18, fontWeight: '600', color: colors.text, marginTop: 12 },
  cardPreviewDesc: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  shareOptionsContainer: { marginTop: 20, gap: 12 },
  shareOptionCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 14, padding: 16,
  },
  shareOptionIcon: {
    width: 50, height: 50, borderRadius: 12, backgroundColor: colors.surface,
    alignItems: 'center', justifyContent: 'center', marginRight: 14,
  },
  shareOptionContent: { flex: 1 },
  shareOptionTitle: { fontSize: 16, fontWeight: '600', color: colors.text, marginBottom: 4 },
  shareOptionDesc: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  landingPageOptions: { marginTop: 16, paddingTop: 16, borderTopWidth: 1, borderTopColor: colors.border },
  landingPageOptionsHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 16, gap: 12 },
  landingPageOptionsTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
  campaignPickerLabel: { fontSize: 15, fontWeight: '500', color: colors.text, marginBottom: 12 },
  campaignScroller: { maxHeight: 50, marginBottom: 20 },
  campaignScrollerContent: { paddingRight: 20 },
  campaignChip: {
    paddingHorizontal: 16, paddingVertical: 10, backgroundColor: colors.card,
    borderRadius: 20, marginRight: 10, borderWidth: 2, borderColor: 'transparent',
  },
  campaignChipSelected: { backgroundColor: '#007AFF20', borderColor: '#007AFF' },
  campaignChipText: { fontSize: 14, color: colors.textSecondary, fontWeight: '500' },
  campaignChipTextSelected: { color: '#007AFF' },
  noCampaigns: { alignItems: 'center', paddingVertical: 20 },
  noCampaignsText: { fontSize: 15, color: colors.textSecondary },
  noCampaignsSubtext: { fontSize: 13, color: colors.textTertiary, marginTop: 4 },
  sendCardButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#007AFF', borderRadius: 12, padding: 16, gap: 8,
  },
  sendCardButtonText: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  // Photo Options (native action sheet style for PWA)
  actionSheetOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  actionSheetContainer: { paddingHorizontal: 8, paddingBottom: 8 },
  actionSheetGroup: {
    backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden', marginBottom: 8,
  },
  actionSheetButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 18, gap: 10,
  },
  actionSheetButtonText: { fontSize: 20, color: '#007AFF', fontWeight: '400' },
  actionSheetDivider: { height: 1, backgroundColor: colors.border },
  actionSheetCancel: {
    backgroundColor: colors.card, borderRadius: 14, paddingVertical: 18, alignItems: 'center',
  },
  actionSheetCancelText: { fontSize: 20, fontWeight: '600', color: '#007AFF' },
  // Send Something Picker Modal (legacy)
  sendPickerOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  sendPickerSheet: {
    backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingTop: 12, paddingBottom: 32, paddingHorizontal: 16,
  },
  sendPickerHandle: {
    width: 36, height: 4, backgroundColor: colors.borderLight, borderRadius: 2,
    alignSelf: 'center', marginBottom: 16,
  },
  sendPickerTitle: {
    fontSize: 18, fontWeight: '700', marginBottom: 16, color: colors.text,
  },
  sendPickerItem: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 14, borderBottomWidth: 1,
  },
  sendPickerIcon: {
    width: 42, height: 42, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
  },
  sendPickerLabel: {
    fontSize: 16, fontWeight: '600', color: colors.text,
  },
  sendPickerSub: {
    fontSize: 12, color: colors.textSecondary, marginTop: 2,
  },
  // Feed date group header (collapsible)
  feedDateHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 10, marginTop: 4,
  },
  feedDateLine: {
    flex: 1, height: 1, backgroundColor: colors.border,
  },
  feedDateText: {
    fontSize: 11, fontWeight: '700', color: colors.textSecondary,
    textTransform: 'uppercase', letterSpacing: 0.8,
  },
  feedDateCount: {
    fontSize: 10, fontWeight: '700', color: colors.textSecondary,
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8,
    backgroundColor: colors.surface,
  },

  // Action progress tracker
  progressSection: {
    marginHorizontal: 16, marginBottom: 12,
    borderRadius: 14, padding: 12,
  },
  progressHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10,
  },
  progressLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5 },
  progressBarBg: { flex: 1, height: 4, backgroundColor: colors.surface, borderRadius: 2, overflow: 'hidden' },
  progressBarFill: { height: 4, backgroundColor: '#C9A962', borderRadius: 2 },
  progressRow: { flexDirection: 'row', gap: 8 },
  progressItem: { alignItems: 'center', gap: 4, minWidth: 56 },
  progressItemDone: {},
  progressIcon: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: colors.border,
  },
  progressText: { fontSize: 9, fontWeight: '600', color: colors.textSecondary, textAlign: 'center' },

  // Section
  section: { marginHorizontal: 16, marginBottom: 16 },
  sectionHeader: {
    fontSize: 13, fontWeight: '600', color: colors.textSecondary,
    textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10,
  },
  sectionHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  sectionHeaderCount: { fontSize: 12, color: colors.textTertiary },

  // Tags
  tagsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tagPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderRadius: 16,
    paddingVertical: 6, paddingHorizontal: 12,
    borderWidth: 1, borderColor: colors.border,
  },
  tagPillText: { fontSize: 13, fontWeight: '500', color: colors.text },
  addTagChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#007AFF15', borderRadius: 16,
    paddingVertical: 6, paddingHorizontal: 12,
    borderWidth: 1, borderColor: '#007AFF30', borderStyle: 'dashed',
  },
  addTagChipText: { fontSize: 13, fontWeight: '600', color: '#007AFF' },

  // Activity feed
  emptyFeed: { alignItems: 'center', paddingVertical: 32 },
  emptyFeedText: { fontSize: 16, color: colors.textSecondary, marginTop: 8 },
  emptyFeedSub: { fontSize: 13, color: colors.textTertiary, marginTop: 4, textAlign: 'center' },
  feedTimeline: { gap: 0 },
  feedItem: {
    flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 10,
    position: 'relative',
  },
  feedItemInbound: {
    backgroundColor: '#30D15808', borderRadius: 12, marginVertical: 2, paddingHorizontal: 4,
  },
  feedLine: {
    position: 'absolute', left: 17, top: 42, bottom: -10,
    width: 2,
  },
  feedIcon: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
    marginRight: 12,
  },
  feedContent: { flex: 1 },
  feedTitle: { fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: 2 },
  feedDesc: { fontSize: 13, color: colors.textSecondary, marginBottom: 4 },
  feedExpandedPreview: { marginTop: 8, marginBottom: 4, gap: 6 },
  feedChannelBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  feedChannelText: { fontSize: 10, fontWeight: '600', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5 },
  feedSubject: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
  feedMessageBubble: { borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border },
  feedMessageBubbleInbound: { backgroundColor: '#30D15812', borderColor: '#30D15830' },
  feedMessageText: { fontSize: 13, lineHeight: 18, color: colors.text },
  feedViewLink: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', paddingVertical: 4 },
  feedViewLinkText: { fontSize: 13, color: '#007AFF', fontWeight: '500' },
  feedTime: { fontSize: 12, color: colors.textTertiary },
  feedPhotoIndicator: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4 },
  feedPhotoText: { fontSize: 12, color: '#30D158', fontWeight: '500' },

  // Inbound / Customer badges
  inboundBadge: { backgroundColor: '#30D15820', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  inboundBadgeText: { fontSize: 9, fontWeight: '700', color: '#30D158', letterSpacing: 0.5 },
  customerBadge: { backgroundColor: '#FFD60A20', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  customerBadgeText: { fontSize: 9, fontWeight: '700', color: '#FFD60A', letterSpacing: 0.5 },

  // Feed actions row
  feedActionRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  logReplyBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#30D15815', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12,
    borderWidth: 1, borderColor: '#30D15830',
  },
  logReplyBtnText: { fontSize: 13, fontWeight: '600', color: '#30D158' },
  feedSearchRowCompact: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 8, paddingHorizontal: 10, borderRadius: 10,
    borderWidth: 1, borderColor: colors.border,
  },
  feedSearchInputCompact: { flex: 1, fontSize: 13, padding: 0, color: colors.text },

  // Log Reply  - Chat Bubble Style
  logReplyBubble: {
    backgroundColor: '#1A2E1A', borderRadius: 20, padding: 16, marginBottom: 14,
    borderWidth: 1.5, borderColor: '#30D15850',
    position: 'relative',
  },
  bubbleTail: {
    position: 'absolute', top: -8, left: 24,
    width: 16, height: 16, backgroundColor: '#1A2E1A',
    borderTopWidth: 1.5, borderLeftWidth: 1.5, borderColor: '#30D15850',
    transform: [{ rotate: '45deg' }],
  },
  bubbleHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12,
  },
  bubbleHeaderText: { fontSize: 14, fontWeight: '700', color: '#30D158', flex: 1 },
  bubbleClose: { padding: 2 },
  bubbleInputWrap: {
    backgroundColor: '#0D1A0D', borderRadius: 16, borderWidth: 1, borderColor: '#30D15830',
    marginBottom: 10,
  },
  bubbleInput: {
    fontSize: 15, color: colors.text, padding: 14, minHeight: 80, textAlignVertical: 'top',
    lineHeight: 22,
  },
  bubblePhotoPreview: {
    position: 'relative', width: 80, height: 80, borderRadius: 12, overflow: 'hidden', marginBottom: 10,
  },
  bubblePhotoThumb: { width: 80, height: 80, borderRadius: 12 },
  bubblePhotoRemove: { position: 'absolute', top: -2, right: -2 },
  bubbleFooter: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  bubblePhotoBtn: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: '#0D1A0D',
    alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#30D15830',
  },
  bubbleSaveBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#30D158', borderRadius: 24,
    paddingVertical: 12, paddingHorizontal: 20,
  },
  bubbleSaveText: { fontSize: 15, fontWeight: '800', color: colors.text },

  // Suggested Actions
  actionBadge: { backgroundColor: '#FF9500', borderRadius: 10, minWidth: 20, height: 20, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 },
  actionBadgeText: { fontSize: 11, fontWeight: '800', color: colors.text },
  suggestedCard: {
    flexDirection: 'row', alignItems: 'center', padding: 14,
    borderRadius: 14, marginBottom: 8,
    borderWidth: 1,
  },
  suggestedIcon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  suggestedTitle: { fontSize: 15, fontWeight: '700', marginBottom: 2, color: colors.text },
  suggestedDesc: { fontSize: 13, color: colors.textSecondary },
  suggestedMsgPreview: { marginTop: 6, borderRadius: 8, padding: 8, borderWidth: 1 },
  suggestedMsgText: { fontSize: 12, fontStyle: 'italic', lineHeight: 16, color: colors.textSecondary },
  suggestedArrow: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginLeft: 8 },
  showMoreBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    marginTop: 12, paddingVertical: 10, borderRadius: 10,
    borderWidth: 1,
  },
  showMoreText: { fontSize: 14, fontWeight: '600', color: '#007AFF' },
  // Photo viewer
  photoViewerOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.95)', justifyContent: 'center', alignItems: 'center',
  },
  photoViewerClose: {
    position: 'absolute', top: 50, right: 20, zIndex: 10, width: 40, height: 40,
    borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center',
  },
  photoViewerContent: {
    width: '90%', maxHeight: '80%', justifyContent: 'center', alignItems: 'center',
  },
  photoViewerImage: {
    width: '100%', height: '100%', borderRadius: 12, maxHeight: 500,
  },
  photoViewerName: {
    color: '#000000', fontSize: 16, fontWeight: '600', marginTop: 12, textAlign: 'center' as const,
  },
  photoViewerDate: {
    color: colors.textSecondary, fontSize: 13, marginTop: 4,
  },
  photoNavRow: {
    flexDirection: 'row' as const, alignItems: 'center', justifyContent: 'center', gap: 24, marginTop: 20,
  },
  photoNavBtn: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.12)',
    justifyContent: 'center' as const, alignItems: 'center' as const,
  },
  photoNavCount: {
    color: colors.textSecondary, fontSize: 14, fontWeight: '600' as const, minWidth: 60, textAlign: 'center' as const,
  },
  backToGridBtn: {
    flexDirection: 'row' as const, alignItems: 'center', gap: 6, marginTop: 20,
    paddingVertical: 10, paddingHorizontal: 16, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.1)',
  },
  backToGridText: {
    color: colors.text, fontSize: 14, fontWeight: '500' as const,
  },
  setProfileBtn: {
    flexDirection: 'row' as const, alignItems: 'center', gap: 6,
    backgroundColor: '#C9A962', borderRadius: 10,
    paddingVertical: 10, paddingHorizontal: 16, marginTop: 8,
  },
  setProfileBtnText: { color: colors.text, fontSize: 14, fontWeight: '700' as const },
  // Gallery grid
  galleryGridContainer: {
    width: '90%', maxHeight: '80%', alignItems: 'center',
  },
  galleryGridTitle: {
    color: colors.text, fontSize: 22, fontWeight: '700', marginBottom: 4,
  },
  galleryGridCount: {
    color: colors.textSecondary, fontSize: 14, marginBottom: 20,
  },
  galleryGrid: {
    flexDirection: 'row' as const, flexWrap: 'wrap' as const, gap: 4, justifyContent: 'flex-start' as const, width: '100%',
  },
  galleryTile: {
    width: '32%', aspectRatio: 1, borderRadius: 8, overflow: 'hidden' as const, position: 'relative' as const,
  },
  galleryTileImg: {
    width: '100%', height: '100%',
  },
  galleryTileBadge: {
    position: 'absolute' as const, bottom: 0, left: 0, right: 0,
    backgroundColor: 'rgba(0,0,0,0.6)', paddingVertical: 4,
  },
  galleryTileBadgeText: {
    color: colors.text, fontSize: 10, fontWeight: '600', textAlign: 'center' as const, textTransform: 'uppercase' as const,
  },
  // Voice notes
  vnRecordBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8,
    paddingVertical: 12, paddingHorizontal: 16, borderRadius: 12,
    backgroundColor: '#1A2E1A', borderWidth: 1, borderColor: '#34C75930',
  },
  vnRecordText: { fontSize: 15, fontWeight: '600', color: '#34C759' },
  vnRecording: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8,
    paddingVertical: 12, paddingHorizontal: 16, borderRadius: 12,
    backgroundColor: '#2E1A1A', borderWidth: 1, borderColor: '#FF3B3030',
  },
  vnRecordingDot: {
    width: 10, height: 10, borderRadius: 5, backgroundColor: '#FF3B30',
  },
  vnRecordingTime: { fontSize: 20, fontWeight: '700', color: '#FF3B30', fontVariant: ['tabular-nums'] as any },
  vnRecordingLimit: { fontSize: 14, color: colors.textTertiary },
  vnStopBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4, marginLeft: 'auto',
    paddingVertical: 6, paddingHorizontal: 14, borderRadius: 8, backgroundColor: '#FF3B30',
  },
  vnStopText: { fontSize: 14, fontWeight: '600', color: colors.text },
  vnCard: {
    borderRadius: 12, padding: 12, marginBottom: 8,
    borderWidth: 1,
  },
  vnCardHeader: { flexDirection: 'row', alignItems: 'center' },
  vnPlayBtn: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: '#34C75920',
    justifyContent: 'center', alignItems: 'center',
  },
  vnPlayBtnActive: { backgroundColor: '#34C759' },
  vnCardDate: { fontSize: 13, fontWeight: '600', color: colors.text },
  vnCardDuration: { fontSize: 12, color: colors.textTertiary },
  vnTranscript: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: 8 },
  // Relationship Intel
  intelBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingVertical: 12, paddingHorizontal: 14, borderRadius: 12,
    borderWidth: 1, borderColor: '#C9A96230',
  },
  intelBtnLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  intelIcon: {
    width: 34, height: 34, borderRadius: 10, backgroundColor: '#C9A96220',
    justifyContent: 'center', alignItems: 'center',
  },
  intelBtnTitle: { fontSize: 15, fontWeight: '700', color: '#C9A962' },
  intelBtnSub: { fontSize: 11, color: colors.textTertiary, marginTop: 1 },
  intelCard: {
    marginTop: 8, padding: 14, borderRadius: 12,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  intelLoading: {
    flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 20,
    justifyContent: 'center',
  },
  intelLoadingText: { fontSize: 14, color: '#C9A962', fontStyle: 'italic' },
  intelSummary: { fontSize: 13.5, color: colors.textSecondary, lineHeight: 20 },
  intelMeta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border,
  },
  intelMetaText: { fontSize: 11, color: colors.textTertiary, flex: 1 },
  intelRefresh: { flexDirection: 'row', alignItems: 'center', gap: 4, padding: 4 },
  intelRefreshText: { fontSize: 12, fontWeight: '600', color: '#007AFF' },
  intelEmpty: { fontSize: 14, color: colors.textTertiary, textAlign: 'center', paddingVertical: 16 },

  // Conversation link
  conversationLink: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, marginBottom: 16,
    backgroundColor: colors.card, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: colors.border,
  },
  conversationLinkTitle: { fontSize: 15, fontWeight: '600', color: colors.text },
  conversationLinkSub: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },

  // Input group
  inputGroup: { marginBottom: 12 },
  inputLabel: { fontSize: 12, fontWeight: '500', color: colors.textSecondary, marginBottom: 4, marginLeft: 2 },
  input: {
    backgroundColor: colors.card, borderRadius: 10, padding: 14,
    fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border,
  },

  // Date row
  dateRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.card, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: colors.border,
  },
  dateRowIcon: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  dateRowLabel: { fontSize: 12, color: colors.textSecondary, marginBottom: 1 },
  dateRowValue: { fontSize: 15, fontWeight: '600', color: colors.text },

  // Add button
  addBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#007AFF15', borderRadius: 10, padding: 12, marginTop: 4,
    borderWidth: 1, borderColor: '#007AFF30', borderStyle: 'dashed',
  },
  addBtnText: { fontSize: 15, fontWeight: '600', color: '#007AFF' },

  // Delete
  deleteBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginHorizontal: 16, marginTop: 8, paddingVertical: 14, borderRadius: 12,
    backgroundColor: colors.card, borderWidth: 1, borderColor: '#FF3B3040',
  },
  deleteBtnText: { fontSize: 16, fontWeight: '600', color: '#FF3B30' },

  // View-only rows
  viewText: { fontSize: 15, color: colors.text, lineHeight: 22 },
  viewRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  viewRowLabel: { fontSize: 14, color: colors.textSecondary, flex: 1 },
  viewRowValue: { fontSize: 14, fontWeight: '600', color: colors.text },

  // Referral items
  referralItem: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  referralAvatar: {
    width: 32, height: 32, borderRadius: 16, backgroundColor: colors.surface,
    alignItems: 'center', justifyContent: 'center',
  },
  referralAvatarText: { fontSize: 12, fontWeight: '600', color: colors.text },
  referralName: { flex: 1, fontSize: 14, fontWeight: '500', color: colors.text },

  // Campaign cards
  campaignCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.card, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: colors.border,
  },
  campaignName: { fontSize: 15, fontWeight: '600', color: colors.text },
  campaignSub: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },

  // Modals
  modalContainer: { flex: 1, backgroundColor: colors.bg },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  modalCancel: { fontSize: 17, color: '#007AFF' },
  modalTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
  modalAction: { fontSize: 17, color: '#007AFF' },
  modalSearch: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: colors.card, borderRadius: 10, margin: 16, paddingHorizontal: 12, gap: 8,
  },
  modalSearchInput: { flex: 1, padding: 12, fontSize: 16, color: colors.text },
  pickerItem: {
    flexDirection: 'row', alignItems: 'center', padding: 14,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  pickerAvatar: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surface,
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  pickerAvatarText: { fontSize: 15, fontWeight: '600', color: colors.text },
  pickerName: { fontSize: 16, fontWeight: '500', color: colors.text },
  pickerSub: { fontSize: 14, color: colors.textSecondary, marginTop: 1 },
  emptyPicker: { padding: 32, alignItems: 'center' },
  emptyPickerText: { fontSize: 16, color: colors.textSecondary },

  // Date picker modal
  dateOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  dateModal: { backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingBottom: 20 },
  dateModalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  dateConfirmBtn: { backgroundColor: '#007AFF', borderRadius: 12, padding: 16, alignItems: 'center' },

  // Web picker
  webPickerLabel: { fontSize: 12, fontWeight: '600', color: colors.textSecondary, marginBottom: 8, textTransform: 'uppercase' },
  webPickerScroll: { maxHeight: 200, width: '100%', backgroundColor: colors.surface, borderRadius: 8 },
  webPickerItem: { paddingVertical: 10, paddingHorizontal: 12, alignItems: 'center' },
  webPickerItemSel: { backgroundColor: '#007AFF', borderRadius: 6, marginHorizontal: 4 },
  webPickerText: { fontSize: 16, color: colors.textSecondary },
  webPickerTextSel: { color: colors.text, fontWeight: '600' },

  // Label modal
  labelOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-start', paddingTop: 150 },
  labelModal: { backgroundColor: colors.card, borderRadius: 16, marginHorizontal: 20, padding: 24 },
  labelTitle: { fontSize: 20, fontWeight: '700', color: colors.text, textAlign: 'center', marginBottom: 8 },
  labelSub: { fontSize: 15, color: '#007AFF', textAlign: 'center', marginBottom: 20, fontWeight: '600' },
  labelInput: { backgroundColor: colors.surface, borderRadius: 12, padding: 16, fontSize: 16, color: colors.text, marginBottom: 24 },
  labelBtn: { flex: 1, borderRadius: 12, padding: 16, alignItems: 'center' },
});
