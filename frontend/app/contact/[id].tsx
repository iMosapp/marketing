import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
  FlatList,
  Linking,
  Dimensions,
  useWindowDimensions,
  Switch,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import * as Clipboard from 'expo-clipboard';
import * as DeviceContacts from 'expo-contacts';
import { Audio } from 'expo-av';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Swipeable } from 'react-native-gesture-handler';
import { format, differenceInDays, differenceInMonths, differenceInYears } from 'date-fns';
import { Image } from 'expo-image';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { contactsAPI, campaignsAPI, tagsAPI, messagesAPI } from '../../services/api';
import { useContactSearch } from '../../hooks/useContactSearch';
import api from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import { useToast } from '../../components/common/Toast';
import VoiceInput from '../../components/VoiceInput';
import { CallTranscript } from '../../components/CallTranscript';
import CampaignJourney from '../../components/CampaignJourney';
import { SoldWorkflowModal } from '../../components/SoldWorkflowModal';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { getS } from '../../components/contact/contactStyles';
import {
  getTimeInSystem, getTimeInSystemLabel, formatEventTime, formatDateUTC,
  QUICK_ACTIONS, EVENT_CATEGORY_ICON, getEventTitle,
} from '../../utils/contactHelpers';
import { EVENT_TYPE_LABELS, getEventLabel } from '../../utils/eventTypes';
import PersonalIntelSection from '../../components/PersonalIntelSection';
import PurchaseHistorySection from '../../components/contact/PurchaseHistorySection';
import ChannelPicker, { useChannelPicker } from '../../components/ChannelPicker';
import { ContactProvider } from '../../components/contact/ContactContext';
import { ScreenErrorBoundary } from '../../components/ScreenErrorBoundary';
import HeroSection from '../../components/contact/HeroSection';
import EditFormTop from '../../components/contact/EditFormTop';
import EditFormBottom from '../../components/contact/EditFormBottom';
import FeedTab from '../../components/contact/FeedTab';
import DetailsTab from '../../components/contact/DetailsTab';
import CallsTab from '../../components/contact/CallsTab';
import ComposerBar from '../../components/contact/ComposerBar';
import ShareModals from '../../components/contact/ShareModals';
import PickerModals from '../../components/contact/PickerModals';
import DateModals from '../../components/contact/DateModals';
import AddTaskModal from '../../components/contact/AddTaskModal';
import GalleryModal from '../../components/contact/GalleryModal';
import IntelBriefingCard from '../../components/contact/IntelBriefingCard';
import QuickActionsRow from '../../components/contact/QuickActionsRow';

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
  referral_count: number;
  created_at: string | null;
}


function ContactDetailScreen() {
  const { colors, mode } = useThemeStore();
  const insets = useSafeAreaInsets();
  const s = getS(colors);
  const { width: screenWidth } = useWindowDimensions();
  const ncs = {
    card: {
      backgroundColor: colors.card,
      borderRadius: 12,
      marginHorizontal: 16,
      marginBottom: 12,
      borderWidth: 1,
      borderColor: colors.border,
      overflow: 'hidden' as const,
    },
    cardInput: {
      fontSize: 18,
      color: colors.text,
      paddingVertical: 14,
      paddingHorizontal: 16,
    },
    cardDivider: {
      height: 1,
      backgroundColor: colors.border,
      marginLeft: 16,
    },
    cardRow: {
      flexDirection: 'row' as const,
      alignItems: 'center' as const,
      paddingVertical: 12,
      paddingHorizontal: 16,
    },
    cardRowIcon: {
      width: 28,
      marginRight: 10,
    },
  };
  const router = useRouter();
  const { id, prefill, channel, action, taskId, taskTitle, capture, event_type: urlEventType, event_title: urlEventTitle } = useLocalSearchParams();
  const user = useAuthStore((state) => state.user);
  const isNewContact = id === 'new';
  const { showToast } = useToast();

  // Core state
  const [contact, setContact] = useState({
    first_name: '', last_name: '', phone: '', email: '',
    photo: null as string | null, photo_thumbnail: null as string | null,
    notes: '', vehicle: '', tags: [] as string[],
    occupation: '', employer: '', organization_name: '',
    phones: [] as { label: string; value: string }[],
    emails: [] as { label: string; value: string }[],
    referred_by: null as string | null, referred_by_name: null as string | null,
    referral_notes: '', referral_count: 0,
    birthday: null as Date | null, anniversary: null as Date | null,
    date_sold: null as Date | null, custom_dates: [] as CustomDateField[],
    address_street: '', address_city: '', address_state: '', address_zip: '', address_country: '',
    disabled_automations: [] as string[],
    ownership_type: 'org' as string,
    linked_user_id: null as string | null,
    linked_store_name: null as string | null,
    linked_store_id: null as string | null,
    linked_org_name: null as string | null,
    linked_role: null as string | null,
  });
  const [loading, setLoading] = useState(!isNewContact);
  const [saving, setSaving] = useState(false);
  const [originalNotes, setOriginalNotes] = useState('');
  // Full photo viewer & gallery
  const [showPhotoViewer, setShowPhotoViewer] = useState(false);
  const [galleryWidth, setGalleryWidth] = useState(0);
  const [fullPhoto, setFullPhoto] = useState<string | null>(null);
  const [fullPhotoLoading, setFullPhotoLoading] = useState(false);
  const [allPhotos, setAllPhotos] = useState<any[]>([]);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);
  const photoReelRef = useRef<ScrollView>(null);
  const [isEditing, setIsEditing] = useState(isNewContact);
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  // Voice notes
  const [voiceNotes, setVoiceNotes] = useState<any[]>([]);

  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [nativeRecording, setNativeRecording] = useState<any>(null);
  const [voiceNotesLoading, setVoiceNotesLoading] = useState(false);
  const [uploadingVoiceNote, setUploadingVoiceNote] = useState(false);
  const [playingNoteId, setPlayingNoteId] = useState<string | null>(null);
  const [showAllNotes, setShowAllNotes] = useState(true);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const recordingTimerRef = React.useRef<any>(null);
  const scrollRef = React.useRef<ScrollView>(null);
  const MAX_RECORDING_SECONDS = 300;

  // AI Relationship Intel (auto-updating)
  const [intelData, setIntelData] = useState<any>(null);
  const [intelRefreshing, setIntelRefreshing] = useState(false);
  const intelBusyRef = useRef(false);
  const composerInputRef = useRef<TextInput>(null);

  // Events & stats
  const [events, setEvents] = useState<ContactEvent[]>([]);
  const [stats, setStats] = useState<ContactStats>({
    total_touchpoints: 0, messages_sent: 0, campaigns: 0,
    cards_sent: 0, broadcasts: 0, custom_events: 0, link_clicks: 0, referral_count: 0, created_at: null,
  });
  const [eventsLoading, setEventsLoading] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState<Record<number, boolean>>({});
  const [feedSearch, setFeedSearch] = useState('');
  const [hasMoreEvents, setHasMoreEvents] = useState(false);
  const [loadingMoreEvents, setLoadingMoreEvents] = useState(false);
  const EVENT_PAGE_SIZE = 100;

  // Tab state for Feed vs Details
  const [contactTab, setContactTab] = useState<'feed' | 'details' | 'calls'>('feed');
  const [callLogs, setCallLogs] = useState<any[]>([]);
  const [callLogsLoading, setCallLogsLoading] = useState(false);

  // Suggested actions & log reply
  const [suggestedActions, setSuggestedActions] = useState<any[]>([]);

  // Toolbar modals (mirroring inbox)
  const [showTemplates, setShowTemplates] = useState(false);
  const [showReviewLinks, setShowReviewLinks] = useState(false);
  const [showReviewCardOptions, setShowReviewCardOptions] = useState(false);
  const [sendingReviewCard, setSendingReviewCard] = useState(false);
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

  // Sold workflow modal
  const [showSoldModal, setShowSoldModal] = useState(false);
  const [soldWorkflowResult, setSoldWorkflowResult] = useState<any>(null);

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

  // New contact: duplicate detection
  const [duplicateMatches, setDuplicateMatches] = useState<any[]>([]);
  const dupCheckTimer = useRef<any>(null);

  // New contact: voice recorder for notes
  const [ncVoiceRecording, setNcVoiceRecording] = useState(false);
  const [ncVoiceTranscribing, setNcVoiceTranscribing] = useState(false);
  const ncVoiceRef = useRef<any>(null);
  const ncVoiceAudioBlob = useRef<Blob | null>(null); // Store audio for post-save upload

  // Ref for ScrollView in new contact form
  const ncScrollRef = useRef<ScrollView>(null);
  const referredByRef = useRef<View>(null);

  // Device contacts picker state
  const [showDeviceContacts, setShowDeviceContacts] = useState(false);
  const [deviceContacts, setDeviceContacts] = useState<DeviceContacts.Contact[]>([]);
  const [deviceContactSearch, setDeviceContactSearch] = useState('');
  const [loadingDeviceContacts, setLoadingDeviceContacts] = useState(false);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<Set<string>>(new Set());
  const [bulkImporting, setBulkImporting] = useState(false);

  const loadDeviceContacts = useCallback(async () => {
    try {
      setLoadingDeviceContacts(true);
      const { status } = await DeviceContacts.requestPermissionsAsync();
      if (status !== 'granted') {
        showSimpleAlert('Permission Needed', 'Please allow access to your contacts in your device Settings to use this feature.');
        return;
      }
      const { data } = await DeviceContacts.getContactsAsync({
        fields: [
          DeviceContacts.Fields.FirstName,
          DeviceContacts.Fields.LastName,
          DeviceContacts.Fields.PhoneNumbers,
          DeviceContacts.Fields.Emails,
          DeviceContacts.Fields.Image,
          DeviceContacts.Fields.Birthday,
          DeviceContacts.Fields.Company,
          DeviceContacts.Fields.JobTitle,
          DeviceContacts.Fields.Addresses,
        ],
      });
      setDeviceContacts(data || []);
      setSelectedDeviceIds(new Set());
      setShowDeviceContacts(true);
    } catch (e) {
      showSimpleAlert('Error', 'Could not load phone contacts. Please check your permissions in Settings.');
    } finally {
      setLoadingDeviceContacts(false);
    }
  }, []);

  const selectDeviceContact = useCallback((dc: DeviceContacts.Contact) => {
    // Single-select mode: fill the current form
    const phone = dc.phoneNumbers?.[0]?.number || '';
    const email = dc.emails?.[0]?.email || '';
    const addr = dc.addresses?.[0];
    const bday = dc.birthday;
    
    setContact(prev => ({
      ...prev,
      first_name: dc.firstName || prev.first_name,
      last_name: dc.lastName || prev.last_name,
      phone: phone || prev.phone,
      email: email || prev.email,
      address: addr?.street || prev.address,
      city: addr?.city || prev.city,
      state: addr?.region || prev.state,
      zip_code: addr?.postalCode || prev.zip_code,
      birthday: bday ? `${bday.year || new Date().getFullYear()}-${String(bday.month! + 1).padStart(2, '0')}-${String(bday.day).padStart(2, '0')}` : prev.birthday,
      photo: dc.image?.uri || prev.photo,
      ownership_type: 'personal',
    }));
    setShowDeviceContacts(false);
    setDeviceContactSearch('');
    setSelectedDeviceIds(new Set());
  }, []);

  const toggleDeviceContact = useCallback((dcId: string) => {
    setSelectedDeviceIds(prev => {
      const next = new Set(prev);
      if (next.has(dcId)) next.delete(dcId);
      else next.add(dcId);
      return next;
    });
  }, []);

  const filteredDeviceContactsList = useMemo(() => {
    const list = deviceContactSearch.trim()
      ? deviceContacts.filter(dc => {
          const name = `${dc.firstName || ''} ${dc.lastName || ''}`.toLowerCase();
          const phone = dc.phoneNumbers?.[0]?.number || '';
          return name.includes(deviceContactSearch.toLowerCase()) || phone.includes(deviceContactSearch);
        })
      : deviceContacts;
    return list.slice(0, 100);
  }, [deviceContacts, deviceContactSearch]);

  const toggleSelectAllVisible = useCallback(() => {
    setSelectedDeviceIds(prev => {
      const visibleIds = filteredDeviceContactsList.map(dc => dc.id!).filter(Boolean);
      const allSelected = visibleIds.length > 0 && visibleIds.every(id => prev.has(id));
      if (allSelected) return new Set();
      return new Set(visibleIds);
    });
  }, [filteredDeviceContactsList]);

  const handleBulkImport = useCallback(async () => {
    if (selectedDeviceIds.size === 0) return;
    const selected = deviceContacts.filter(dc => dc.id && selectedDeviceIds.has(dc.id));
    const payload = selected.map(dc => {
      const phone = dc.phoneNumbers?.[0]?.number || '';
      const email = dc.emails?.[0]?.email || '';
      const addr = dc.addresses?.[0];
      const bday = dc.birthday;
      return {
        first_name: dc.firstName || '',
        last_name: dc.lastName || '',
        phone,
        email,
        address: addr?.street || '',
        city: addr?.city || '',
        state: addr?.region || '',
        zip_code: addr?.postalCode || '',
        birthday: bday ? `${bday.year || new Date().getFullYear()}-${String(bday.month! + 1).padStart(2, '0')}-${String(bday.day).padStart(2, '0')}` : '',
      };
    }).filter(c => c.first_name || c.last_name || c.phone);

    if (payload.length === 0) {
      showSimpleAlert('No valid contacts to import', 'error');
      return;
    }

    try {
      setBulkImporting(true);
      const res = await api.post(`/contacts/${user._id}/import?source=phone_import`, payload);
      const count = res.data?.imported || payload.length;
      showSimpleAlert(`Imported ${count} contact${count !== 1 ? 's' : ''}!`, 'success');
      setShowDeviceContacts(false);
      setSelectedDeviceIds(new Set());
      setDeviceContactSearch('');
      router.back();
    } catch (e: any) {
      showSimpleAlert(e?.response?.data?.detail || 'Import failed', 'error');
    } finally {
      setBulkImporting(false);
    }
  }, [selectedDeviceIds, deviceContacts, user, router]);

  // Composer state (inline inbox)
  const [composerMessage, setComposerMessage] = useState('');
  const [composerInputHeight, setComposerInputHeight] = useState(44);
  const [composerMode, setComposerMode] = useState<'sms' | 'email'>('sms');
  const [composerSending, setComposerSending] = useState(false);
  const [composerEventType, setComposerEventType] = useState<string | null>(null);
  const [composerEventTitle, setComposerEventTitle] = useState<string | null>(null);
  const channelPicker = useChannelPicker();

  // Populate composer from query param (e.g. returning from create-card or task action item)
  useEffect(() => {
    if (prefill && typeof prefill === 'string') {
      setComposerMessage(prefill);
      // If arriving from a task, auto-open the composer
      if (taskId) {
        const ch = typeof channel === 'string' ? channel : 'sms';
        setComposerMode(ch === 'email' ? 'email' : 'sms');
      }
    }
    if (channel && typeof channel === 'string' && !taskId) {
      if (channel === 'email') setComposerMode('email');
      else setComposerMode('sms');
    }
    // Set composer event type from URL param (e.g. returning from card creation)
    if (urlEventType && typeof urlEventType === 'string') {
      setComposerEventType(urlEventType);
    }
    if (urlEventTitle && typeof urlEventTitle === 'string') {
      setComposerEventTitle(decodeURIComponent(urlEventTitle as string));
    }
  }, [prefill, channel, taskId, urlEventType, urlEventTitle]);

  // Auto-trigger action from query param (e.g. /contact/123?action=digitalcard)
  useEffect(() => {
    if (action && typeof action === 'string' && !isNewContact && !loading && contact.first_name) {
      setTimeout(() => handleQuickAction(action), 300);
    }
  }, [action, loading, contact.first_name]);
  const [aiSuggestion, setAiSuggestion] = useState('');
  const [loadingAI, setLoadingAI] = useState(false);
  const [showAISuggestion, setShowAISuggestion] = useState(false);
  const [showLogReply, setShowLogReply] = useState(false);
  const [showAddTask, setShowAddTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskNotes, setNewTaskNotes] = useState('');
  const [newTaskDue, setNewTaskDue] = useState<'today' | 'tomorrow' | 'thisweek' | 'custom'>('today');
  const [newTaskPriority, setNewTaskPriority] = useState<'low' | 'medium' | 'high'>('medium');
  const [newTaskDate, setNewTaskDate] = useState<Date>(new Date());
  const [newTaskTime, setNewTaskTime] = useState<string | null>(null);
  const [newTaskApptType, setNewTaskApptType] = useState<string | null>(null);
  const [savingTask, setSavingTask] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [replyPhoto, setReplyPhoto] = useState<string | null>(null);
  const [submittingReply, setSubmittingReply] = useState(false);
  const [collapsedDateGroups, setCollapsedDateGroups] = useState<Record<string, boolean>>({});
  const [editingAutomation, setEditingAutomation] = useState<{ field: string; label: string; color: string; value: string } | null>(null);
  const [webActionSheet, setWebActionSheet] = useState<{ visible: boolean; title: string; options: { label: string; icon: string; color: string; onPress: () => void }[] }>({ visible: false, title: '', options: [] });

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

  // Auto-open voice recorder when deep-linked with ?capture=true (from post-sale notification)
  useEffect(() => {
    if (capture === 'true' && !isNewContact) {
      setContactTab('details');
      // Small delay so the tab renders before we start recording
      setTimeout(() => {
        startRecording();
      }, 800);
    }
  }, [capture, isNewContact]);

  // Periodic polling DISABLED — causes scroll jumps. Events refresh on focus and after user actions.
  // useEffect(() => {
  //   if (isNewContact || !user) return;
  //   const interval = setInterval(() => { loadEvents(); }, 15000);
  //   return () => clearInterval(interval);
  // }, [id, user, isNewContact]);

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
        occupation: data.occupation || '', employer: data.employer || '',
        organization_name: data.organization_name || '',
        phones: data.phones || [],
        emails: data.emails || [],
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
        disabled_automations: data.disabled_automations || [],
        linked_user_id: data.linked_user_id || null,
        linked_store_name: data.linked_store_name || null,
        linked_store_id: data.linked_store_id || null,
        linked_org_name: data.linked_org_name || null,
        linked_role: data.linked_role || null,
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
        contactsAPI.getEvents(user._id, id as string, EVENT_PAGE_SIZE),
        contactsAPI.getStats(user._id, id as string),
      ]);
      const loaded = evtsResp.events || [];
      setEvents(loaded);
      setHasMoreEvents(loaded.length === EVENT_PAGE_SIZE);
      setStats(statsResp);
    } catch (e) {
      console.error('Failed to load events:', e);
    } finally {
      setEventsLoading(false);
    }
  };

  const loadMoreEvents = async () => {
    if (!user || loadingMoreEvents) return;
    setLoadingMoreEvents(true);
    try {
      const resp = await contactsAPI.getEvents(user._id, id as string, EVENT_PAGE_SIZE, events.length);
      const more = resp.events || [];
      setEvents(prev => [...prev, ...more]);
      setHasMoreEvents(more.length === EVENT_PAGE_SIZE);
    } catch (e) {
      console.error('Failed to load more events:', e);
    } finally {
      setLoadingMoreEvents(false);
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


  const handleSaveTask = async () => {
    if (!newTaskTitle.trim() || !user?._id) return;
    setSavingTask(true);
    try {
      const now = new Date();
      let dueDate: Date;
      if (newTaskDue === 'today') {
        dueDate = new Date(now); dueDate.setHours(23, 59, 0, 0);
      } else if (newTaskDue === 'tomorrow') {
        dueDate = new Date(now); dueDate.setDate(dueDate.getDate() + 1); dueDate.setHours(9, 0, 0, 0);
      } else if (newTaskDue === 'custom') {
        dueDate = new Date(newTaskDate);
        if (newTaskTime) {
          const [h, m] = newTaskTime.split(':').map(Number);
          dueDate.setHours(h, m, 0, 0);
        } else {
          dueDate.setHours(9, 0, 0, 0);
        }
      } else {
        // this week = next Monday
        dueDate = new Date(now);
        const daysUntilMon = (8 - dueDate.getDay()) % 7 || 7;
        dueDate.setDate(dueDate.getDate() + daysUntilMon); dueDate.setHours(9, 0, 0, 0);
      }
      await api.post(`/tasks/${user._id}`, {
        title: newTaskTitle.trim(),
        description: newTaskNotes.trim(),
        contact_id: id as string,
        contact_name: contact ? `${contact.first_name || ''} ${contact.last_name || ''}`.trim() : '',
        contact_phone: contact?.phone || '',
        due_date: dueDate.toISOString(),
        has_time: newTaskDue === 'custom' && !!newTaskTime,
        appointment_type: newTaskApptType,
        priority: newTaskPriority,
        type: newTaskApptType ? 'appointment' : 'manual',
        source: 'manual',
        action_type: 'manual',
      });
      setShowAddTask(false);
      setNewTaskTitle('');
      setNewTaskNotes('');
      setNewTaskDue('today');
      setNewTaskPriority('medium');
      setNewTaskDate(new Date());
      setNewTaskTime(null);
      setNewTaskApptType(null);
      showSimpleAlert('Task Added', `"${newTaskTitle.trim()}" added to your touchpoints.`);
    } catch { showSimpleAlert('Error', 'Could not save task. Try again.'); }
    finally { setSavingTask(false); }
  };


  const handleLogReply = async () => {
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
      // Load templates
      const templatesRes = await api.get(`/templates/${user._id}`).catch(() => ({ data: [] }));
      setTemplates(Array.isArray(templatesRes.data) ? templatesRes.data : []);

      // Load review links from user-level first
      let userReviewLinks: Record<string, string> = {};
      let userCustomName = '';
      try {
        const reviewRes = await api.get(`/users/${user._id}/review-links`);
        userReviewLinks = reviewRes.data?.review_links || {};
        userCustomName = reviewRes.data?.custom_link_name || '';
      } catch { }

      // Load store data (slug + store-level review links)
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
            // Set store slug
            const slug = storeData.slug;
            if (slug) {
              setStoreSlug(slug);
            } else if (storeData.name) {
              setStoreSlug(storeData.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
            }
            // Merge store-level review links with user-level (user overrides store)
            const storeLinks = storeData.review_links || {};
            const mergedLinks: Record<string, string> = {};
            for (const [key, val] of Object.entries(storeLinks)) {
              if (key === 'custom' && Array.isArray(val)) {
                // Handle custom links array - use first one with a name
                for (const item of val as any[]) {
                  if (item?.url) {
                    mergedLinks['custom'] = item.url;
                    if (item.name && !userCustomName) {
                      setCustomLinkName(item.name);
                    }
                    break;
                  }
                }
              } else if (typeof val === 'string' && val) {
                mergedLinks[key] = val;
              }
            }
            // User-level links override store-level
            for (const [key, val] of Object.entries(userReviewLinks)) {
              if (typeof val === 'string' && val) mergedLinks[key] = val;
            }
            setReviewLinks(mergedLinks);
            setCustomLinkName(userCustomName || storeData.custom_link_name || '');
          }
        } else {
          // No store — just use user-level links
          setReviewLinks(userReviewLinks);
          setCustomLinkName(userCustomName);
        }
      } catch {
        setReviewLinks(userReviewLinks);
        setCustomLinkName(userCustomName);
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
    showAlert('Attach', undefined, [
      { text: 'Photo from Library', onPress: async () => {
        const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: true, quality: 0.7 });
        if (!result.canceled && result.assets[0]?.uri) setSelectedMedia(result.assets[0]);
      }},
      { text: 'Create Card', onPress: () => setShowCardTemplatePicker(true) },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  // Pick a photo to attach to the composer message
  const pickComposerPhoto = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        quality: 0.7,
      });
      if (!result.canceled && result.assets && result.assets.length > 0) {
        setSelectedMedia(result.assets[0]);
      }
    } catch (e) {
      console.error('pickComposerPhoto error:', e);
      showToast('Failed to pick photo. Please try again.', 'error');
    }
  };

  const insertReviewLink = async (platformId: string, url: string, platformName: string) => {
    const firstName = contact.first_name || 'there';
    setShowReviewLinks(false);
    setComposerEventType('review_request_sent');
    try {
      // Create a trackable short URL with contact_id in metadata
      const shortRes = await api.post('/s/create', {
        original_url: url,
        link_type: 'review_request',
        user_id: user?._id,
        reference_id: id as string,
        metadata: { contact_id: id as string, platform: platformId },
      });
      const trackableUrl = shortRes.data?.short_url || url;
      setComposerMessage(`Hey ${firstName}! We'd love your feedback. Leave us a review here: ${trackableUrl}`);
    } catch (e) {
      // Fallback to raw URL if short URL creation fails
      setComposerMessage(`Hey ${firstName}! We'd love your feedback. Leave us a review here: ${url}`);
    }
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

  const sendBusinessCardLink = async () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imonsocial.com';
    let cardUrl = `${baseUrl}/card/${user._id}`;
    const params: string[] = [];
    if (selectedCampaign) params.push(`campaign=${selectedCampaign}`);
    if (id) params.push(`contact=${id}`);
    if (params.length > 0) cardUrl += `?${params.join('&')}`;
    const firstName = contact.first_name || 'there';
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    setSelectedCampaign(null);
    try {
      const shortRes = await api.post('/s/create', {
        original_url: cardUrl, link_type: 'business_card', user_id: user._id,
        reference_id: id as string, metadata: { contact_id: id as string },
      });
      setComposerMessage(`Hey ${firstName}! Here's my digital business card: ${shortRes.data?.short_url || cardUrl}`);
      setComposerEventType('digital_card_sent');
    } catch { setComposerMessage(`Hey ${firstName}! Here's my digital business card: ${cardUrl}`); setComposerEventType('digital_card_sent'); }
  };

  const sendVCardLink = () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imonsocial.com';
    const vcardUrl = `${baseUrl}/api/card/vcard/${user._id}`;
    const firstName = contact.first_name || 'there';
    const cardMessage = `Hey ${firstName}! Tap here to save my contact info directly to your phone: ${vcardUrl}`;
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    setSelectedCampaign(null);
    setComposerMessage(cardMessage);
    setComposerEventType('vcard_sent');
  };

  const sendShowcaseLink = async () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imonsocial.com';
    const showcaseUrl = `${baseUrl}/showcase/${user._id}`;
    const firstName = contact.first_name || 'there';
    setShowBusinessCard(false);
    try {
      const shortRes = await api.post('/s/create', {
        original_url: showcaseUrl, link_type: 'showcase', user_id: user._id,
        reference_id: id as string, metadata: { contact_id: id as string },
      });
      setComposerMessage(`Hey ${firstName}! Check out some of our happy customers: ${shortRes.data?.short_url || showcaseUrl}`);
      setComposerEventType('showcase_shared');
    } catch { setComposerMessage(`Hey ${firstName}! Check out some of our happy customers: ${showcaseUrl}`); setComposerEventType('showcase_shared'); }
  };


  const sendLandingPageLink = async () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imonsocial.com';
    const landingUrl = `${baseUrl}/p/${user._id}`;
    const firstName = contact.first_name || 'there';
    setShowBusinessCard(false);
    setShowLandingPageOptions(false);
    try {
      const shortRes = await api.post('/s/create', {
        original_url: landingUrl, link_type: 'landing_page', user_id: user._id,
        reference_id: id as string, metadata: { contact_id: id as string },
      });
      setComposerMessage(`Hey ${firstName}! Check out my page: ${shortRes.data?.short_url || landingUrl}`);
      setComposerEventType('landing_page_shared');
    } catch { setComposerMessage(`Hey ${firstName}! Check out my page: ${landingUrl}`); setComposerEventType('landing_page_shared'); }
  };

  const sendLinkPageLink = async () => {
    if (!user?._id) return;
    const baseUrl = 'https://app.imonsocial.com';
    const firstName = contact.first_name || 'there';
    try {
      const resp = await api.get(`/linkpage/user/${user._id}`);
      const username = resp.data?.username;
      if (username) {
        const url = `${baseUrl}/l/${username}`;
        try {
          const shortRes = await api.post('/s/create', {
            original_url: url, link_type: 'link_page', user_id: user._id,
            reference_id: id as string, metadata: { contact_id: id as string },
          });
          setShowBusinessCard(false);
          setComposerMessage(`Hey ${firstName}! Here are all my links: ${shortRes.data?.short_url || url}`);
          setComposerEventType('link_page_shared');
        } catch { setShowBusinessCard(false); setComposerMessage(`Hey ${firstName}! Here are all my links: ${url}`); setComposerEventType('link_page_shared'); }
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
          import('expo-linking').then(L => L.openSettings?.()).catch(() => {});
          showSimpleAlert('Microphone Blocked', 'Enable microphone in Settings → Im On Social → Microphone, then try again.');
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

  const handleSuggestedAction = async (action: any) => {
    if (!contact.phone && (action.action === 'sms' || action.action === 'call')) {
      const recovered = await resolveContactPhone();
      if (!recovered) {
        showSimpleAlert('Missing Info', 'No phone number saved for this contact.');
        return;
      }
    }
    
    switch (action.action) {
      case 'sms':
        setComposerMode('sms');
        setComposerMessage(action.suggested_message || '');
        break;
      case 'congrats':
        setShowCardTemplatePicker(true);
        break;
      case 'email':
        setComposerMode('email');
        setComposerMessage(action.suggested_message || '');
        break;
      default:
        setComposerMode('sms');
        setComposerMessage(action.suggested_message || '');
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
      const contactArr = Array.isArray(data) ? data : (data?.contacts || []);
      setAllContacts(contactArr.filter((c: any) => c._id !== id));
    } catch (e) { console.error(e); }
  };

  useContactSearch(user?._id, contactSearch, (arr) => setAllContacts(arr.filter((c: any) => c._id !== id)));

  // ===== NEW CONTACT: DUPLICATE CHECK =====
  const checkDuplicate = useCallback(async (phone: string, email: string) => {
    if (!user) return;
    const params = new URLSearchParams();
    if (phone && phone.replace(/\D/g, '').length >= 7) params.set('phone', phone);
    if (email && email.length >= 3 && email.includes('@')) params.set('email', email);
    if (!params.toString()) { setDuplicateMatches([]); return; }
    try {
      const res = await api.get(`/contacts/${user._id}/check-duplicate?${params.toString()}`);
      setDuplicateMatches(res.data.matches || []);
    } catch (e) { setDuplicateMatches([]); }
  }, [user]);

  const onPhoneOrEmailChange = useCallback((field: 'phone' | 'email', value: string) => {
    setContact(prev => ({ ...prev, [field]: value }));
    if (isNewContact) {
      clearTimeout(dupCheckTimer.current);
      dupCheckTimer.current = setTimeout(() => {
        const p = field === 'phone' ? value : contact.phone;
        const e = field === 'email' ? value : contact.email;
        checkDuplicate(p, e);
      }, 500);
    }
  }, [isNewContact, contact.phone, contact.email, checkDuplicate]);

  // ===== NEW CONTACT: VOICE-TO-TEXT =====
  const handleNewContactVoice = async () => {
    try {
      if (ncVoiceRecording) {
        setNcVoiceRecording(false);
        if (ncVoiceRef.current) {
          setNcVoiceTranscribing(true);
          await ncVoiceRef.current.stopAndUnloadAsync();
          const uri = ncVoiceRef.current.getURI();
          ncVoiceRef.current = null;
          if (uri) {
            const formData = new FormData();
            if (IS_WEB) {
              const resp = await fetch(uri);
              const blob = await resp.blob();
              ncVoiceAudioBlob.current = blob; // Save for post-creation upload
              formData.append('file', blob, 'recording.webm');
            } else {
              // On native, store the URI for later upload
              ncVoiceAudioBlob.current = { uri, type: 'audio/m4a', name: 'recording.m4a' } as any;
              formData.append('file', { uri, type: 'audio/m4a', name: 'recording.m4a' } as any);
            }
            try {
              const response = await api.post('/voice/transcribe', formData, {
                
              });
              if (response.data.success && response.data.text) {
                setContact(prev => ({
                  ...prev,
                  notes: prev.notes ? `${prev.notes}\n${response.data.text}` : response.data.text
                }));
              }
            } catch (err) { console.error('Transcription error:', err); }
          }
          setNcVoiceTranscribing(false);
        }
      } else {
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          import('expo-linking').then(L => L.openSettings?.()).catch(() => {});
          showSimpleAlert('Microphone Blocked', 'Enable microphone in Settings → Im On Social → Microphone, then try again.');
          return;
        }
        await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
        const recordingOptions = IS_WEB
          ? { ...Audio.RecordingOptionsPresets.HIGH_QUALITY, isMeteringEnabled: false, web: { mimeType: 'audio/webm;codecs=opus', bitsPerSecond: 128000 } }
          : Audio.RecordingOptionsPresets.HIGH_QUALITY;
        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync(recordingOptions);
        await recording.startAsync();
        ncVoiceRef.current = recording;
        ncVoiceAudioBlob.current = null; // Clear previous
        setNcVoiceRecording(true);
      }
    } catch (err) {
      console.error('Voice recording error:', err);
      setNcVoiceRecording(false);
      setNcVoiceTranscribing(false);
    }
  };

  // ===== SAVE / DELETE =====
  const handleSave = async () => {
    if (!contact.first_name) {
      showSimpleAlert('Error', 'First name is required');
      return;
    }
    if (!contact.phone && !contact.email) {
      showSimpleAlert('Error', 'Please provide a phone number or email');
      return;
    }
    if (!user) return;
    try {
      setSaving(true);
      let result: any = null;
      if (isNewContact) {
        result = await contactsAPI.create(user._id, contact);
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
      showToast('Contact saved!', 'success');
      if (isNewContact) {
        // Navigate to the new contact's page so user can record voice notes, etc.
        const newId = result?._id || result?.id;
        
        // Upload the voice recording as a proper voice note (triggers AI intelligence extraction)
        if (newId && ncVoiceAudioBlob.current) {
          try {
            const voiceFormData = new FormData();
            if (IS_WEB && ncVoiceAudioBlob.current instanceof Blob) {
              voiceFormData.append('audio', ncVoiceAudioBlob.current, 'recording.webm');
            } else {
              voiceFormData.append('audio', ncVoiceAudioBlob.current as any);
            }
            voiceFormData.append('duration', '0');
            await api.post(`/voice-notes/${user._id}/${newId}`, voiceFormData, {
              
            });
            ncVoiceAudioBlob.current = null;
          } catch (voiceErr) {
            console.error('Failed to save voice note after contact creation:', voiceErr);
            // Non-critical — contact was still saved, notes text is preserved
          }
        }
        
        if (newId) {
          router.replace(`/contact/${newId}` as any);
        } else {
          router.back();
        }
      } else {
        setIsEditing(false);
        // Reload contact data so the profile picture and all fields reflect the saved state
        loadContact();
        // Scroll to top so user sees the updated profile
        requestAnimationFrame(() => {
          scrollRef.current?.scrollTo({ y: 0, animated: true });
          if (Platform.OS === 'web') {
            try {
              const hero = document.querySelector('[data-testid="contact-hero"]');
              if (hero) {
                let parent = hero.parentElement;
                while (parent) {
                  if (parent.scrollHeight > parent.clientHeight) { parent.scrollTop = 0; break; }
                  parent = parent.parentElement;
                }
              }
            } catch (_) {}
          }
        });
      }
    } catch (e: any) {
      console.error('handleSave error:', e);
      showSimpleAlert('Error', e?.response?.data?.detail || e?.message || 'Failed to save contact. Please try again.');
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

  // ── Look up phone from conversation history if contact.phone is missing ──
  const resolveContactPhone = async (): Promise<string | null> => {
    if (contact.phone) return contact.phone;
    // Try to find phone from their most recent conversation
    try {
      const res = await api.get(`/messages/conversations/${user?._id}`);
      const convs = res.data?.conversations || res.data || [];
      const match = convs.find((c: any) => c.contact_id === id && c.contact_phone);
      if (match?.contact_phone) {
        // Auto-save it back to the contact record so it's there next time
        await api.patch(`/contacts/${user?._id}/${id}`, { phone: match.contact_phone }).catch(() => {});
        setContact((prev: any) => ({ ...prev, phone: match.contact_phone }));
        return match.contact_phone;
      }
    } catch {}
    return null;
  };

  // ===== QUICK ACTIONS =====

  const sendReviewCard = async () => {
    if (!user?._id || !id) return;
    setSendingReviewCard(true);
    setShowReviewCardOptions(false);
    try {
      const res = await api.post(`/congrats/review-card/${user._id}/${id}`);
      const { image_url, sms_text, contact_phone } = res.data;
      const phone = contact_phone?.replace(/\D/g, '') || '';
      if (!phone) {
        showSimpleAlert('No Phone', 'This contact has no phone number.');
        return;
      }
      // Build MMS SMS URL — includes image URL in the body so it shows as rich card
      const body = image_url ? `${image_url}\n\n${sms_text}` : sms_text;
      const smsUrl = Platform.OS === 'ios'
        ? `sms:${phone}&body=${encodeURIComponent(body)}`
        : `sms:${phone}?body=${encodeURIComponent(body)}`;
      const canOpen = await Linking.canOpenURL(smsUrl);
      if (canOpen) {
        await Linking.openURL(smsUrl);
      } else if (typeof window !== 'undefined') {
        await Clipboard.setStringAsync(body);
        showSimpleAlert('Copied', 'Review card message copied to clipboard.');
      }
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Could not generate review card.');
    } finally {
      setSendingReviewCard(false);
    }
  };


  const handleQuickAction = async (key: string) => {
    if (!contact.phone && (key === 'sms' || key === 'call')) {
      // Try to recover the phone from conversation history first
      const recovered = await resolveContactPhone();
      if (!recovered) {
        showAlert('No Phone Number', 'This contact has no phone number saved. Would you like to add one?', [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Add Number', onPress: () => {
            setIsEditing(true);
            // Scroll to phone field
            setTimeout(() => showSimpleAlert('Edit contact', 'Scroll to the Phone field and add their number, then save.'), 300);
          }},
        ]);
        return;
      }
    }
    const contactEmail = contact.email || contact.email_work || '';
    if (!contactEmail && key === 'email') {
      showSimpleAlert('Missing Info', 'No email address available');
      return;
    }
    
    switch (key) {
      case 'sms':
        setComposerMode('sms');
        break;
      case 'call': {
        router.push(`/call-screen?contact_id=${id}&contact_name=${encodeURIComponent((contact.first_name || '') + ' ' + (contact.last_name || ''))}&phone=${encodeURIComponent(contact.phone)}`);
        break;
      }
      case 'email':
        setComposerMode('email');
        break;
      case 'review':
        // Show options: plain review link OR branded review card
        setShowReviewCardOptions(true);
        break;
      case 'card':
        openBusinessCardPicker();
        break;
      case 'gift':
      case 'congrats':
        setShowCardTemplatePicker(true);
        break;
      case 'digitalcard':
        openBusinessCardPicker();
        break;
      case 'linkpage':
        sendLinkPageLink();
        break;
      case 'showcase':
        sendShowcaseLink();
        break;
    }
  };

  // ===== COMPOSER: Send message directly from contact page =====
  const handleComposerSend = async (textOverride?: string) => {
    let content = textOverride || composerMessage.trim();
    if (!content && !selectedMedia) return;
    if (!user) return;
    
    // Resolve personalization merge tags
    const firstName = contact.first_name || '';
    const lastName = contact.last_name || '';
    content = content
      .replace(/\{first_name\}/g, firstName)
      .replace(/\{last_name\}/g, lastName)
      .replace(/\{full_name\}/g, `${firstName} ${lastName}`.trim())
      .replace(/\{phone\}/g, contact.phone || '')
      .replace(/\{email\}/g, contact.email || '')
      .replace(/\{my_name\}/g, (user as any).name || '')
      .replace(/\{my_phone\}/g, (user as any).phone || '')
      .replace(/\{company\}/g, (user as any).organization_name || '')
      .replace(/\{date_sold\}/g, '')
      .replace(/\{name\}/g, firstName);
    
    const contactEmail = contact.email || '';
    if (composerMode === 'email' && !contactEmail) {
      showSimpleAlert('Missing Info', 'No email address available for this contact');
      return;
    }
    if (composerMode === 'sms' && !contact.phone) {
      // Try to recover from conversation history before failing
      const recovered = await resolveContactPhone();
      if (!recovered) {
        showSimpleAlert('Missing Info', 'No phone number saved for this contact. Open the edit form and add their number.');
        return;
      }
    }
    
    setComposerSending(true);
    try {
      // Upload photo if attached — send as MMS media_urls, NOT as a URL in the text body
      let mediaUrls: string[] = [];
      if (selectedMedia?.uri) {
        try {
          const formData = new FormData();
          if (IS_WEB) {
            const response = await fetch(selectedMedia.uri);
            const blob = await response.blob();
            formData.append('file', blob, 'photo.jpg');
          } else {
            formData.append('file', { uri: selectedMedia.uri, type: 'image/jpeg', name: 'photo.jpg' } as any);
          }
          const uploadRes = await api.post('/images/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
          let photoUrl = uploadRes.data?.original_url || uploadRes.data?.url || uploadRes.data?.file_url || '';
          // Make absolute URL + force JPEG so Twilio can deliver as MMS (WebP not universally supported)
          if (photoUrl && photoUrl.startsWith('/')) {
            const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
            photoUrl = `${baseUrl}${photoUrl}`;
          }
          if (photoUrl) mediaUrls = [`${photoUrl}?format=jpeg`];
        } catch (uploadErr) {
          console.warn('Photo upload failed, sending text only:', uploadErr);
        }
      }

      const messageContent = content || '';
      if (!messageContent && mediaUrls.length === 0) return;
      
      // Create or get existing conversation for this contact
      const conv = await messagesAPI.createConversation(user._id, {
        contact_id: id as string,
        contact_phone: contact.phone || undefined,
      });
      const conversationId = conv._id || conv.id;
      
      if (composerMode === 'sms') {
        // For SMS: Log the message server-side (non-blocking), then ALWAYS open messaging channel.
        // Logging failure must NOT prevent the customer from receiving the message.
        const sendPayload: any = {
          conversation_id: conversationId,
          content: messageContent,
          channel: 'sms_personal',
        };
        if (composerEventType) sendPayload.event_type = composerEventType;
        if (composerEventTitle) sendPayload.event_title = composerEventTitle;

        // Check if user has a dedicated Twilio number
        const twilioNumber = (user as any).twilio_number || (user as any).mvpline_number;

        if (twilioNumber && contact.phone) {
          // Twilio path: send silently from dedicated business number
          try {
            const { smartSendSMS } = await import('../../services/api');
            const result = await smartSendSMS({
              to:          contact.phone,
              body:        messageContent,
              userId:      user._id,
              twilioNumber,
              contactId:   id as string,
              eventType:   composerEventType || (mediaUrls.length > 0 ? 'mms_sent' : 'personal_sms'),
              platform:    Platform.OS,
              mediaUrls,   // ← native photo, not a URL in text
            });
            if (result.usedTwilio) {
              showToast(`Sent from ${twilioNumber}`, 'success');
              setComposerMessage('');
              setSelectedMedia(null);
              return;
            }
          } catch (twilioErr) {
            console.warn('[Composer] Twilio send failed, falling back to native:', twilioErr);
          }
        }

        // No Twilio number (or fallback): fire-and-forget logging then open native SMS
        messagesAPI.send(user._id, sendPayload).catch((logErr: any) => {
          console.warn('[Send] Backend logging failed (non-fatal):', logErr?.message);
        });
        
        // Fetch user's enabled channels
        let userChannels: any[] = [];
        try {
          const chRes = await api.get(`/messaging-channels/user/${user._id}`);
          userChannels = chRes.data.channels || [];
        } catch {
          userChannels = [{ id: 'sms', url_scheme: 'sms:{phone}?body={message}', requires_phone: true }];
        }

        if (userChannels.length === 1) {
          // Single channel — open directly from this click handler (user gesture context)
          const ch = userChannels[0];
          const phone_clean = (contact.phone || '').replace(/\D/g, '');
          let url = ch.url_scheme
            .replace('{phone}', encodeURIComponent(contact.phone || ''))
            .replace('{phone_clean}', phone_clean)
            .replace('{message}', encodeURIComponent(messageContent))
            .replace('{email}', encodeURIComponent(contact.email || ''));
          // iOS SMS uses & separator
          if (url.startsWith('sms:') && Platform.OS === 'web' && typeof window !== 'undefined') {
            const ua = window.navigator.userAgent.toLowerCase();
            if (/iphone|ipad|ipod/.test(ua)) {
              url = url.replace('?body=', '&body=');
            }
          }
          // Copy to clipboard for easy pasting
          try {
            Clipboard.setStringAsync(messageContent).catch(() => {});
          } catch {}
          // Open in user gesture context (not blocked by popup blocker)
          if (Platform.OS === 'web' && typeof window !== 'undefined') {
            window.location.href = url;
          } else {
            Linking.openURL(url).catch(() => {});
          }
          showToast(`Message logged & opening ${ch.name || 'SMS'}...`, 'success');
          api.patch(`/contacts/${user._id}/${id}/events/latest-channel`, { channel: ch.id }).catch(() => {});
        } else {
          // Multiple channels — show the picker modal
          channelPicker.open({
            message: messageContent,
            phone: contact.phone || '',
            email: contact.email || '',
            onSent: (ch) => {
              showToast(`Message logged & opened in ${ch === 'clipboard' ? 'clipboard' : ch}!`);
              api.patch(`/contacts/${user._id}/${id}/events/latest-channel`, { channel: ch }).catch(() => {});
            },
          });
        }
      } else {
        // Email: send directly via Resend
        const emailPayload: any = {
          conversation_id: conversationId,
          content: messageContent,
          channel: 'email',
        };
        if (composerEventType) emailPayload.event_type = composerEventType;
        await messagesAPI.send(user._id, emailPayload);
        showToast('Email sent!');
      }
      
      setComposerMessage('');
      setComposerInputHeight(36);
      setComposerEventType(null);
      setSelectedMedia(null);
      setShowAISuggestion(false);
      setAiSuggestion('');
      // Refresh events to show the new message in the feed
      loadEvents();
      
      // Auto-complete the task if this send came from a Touchpoints task card
      if (taskId && typeof taskId === 'string' && user?._id) {
        try {
          await api.patch(`/tasks/${user._id}/${taskId}`, { action: 'complete' });
        } catch {}
      }
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

  // Drop a gallery photo straight into a new card (birthday/congrats/etc.)
  const usePhotoForCard = (photoUrl: string) => {
    if (!photoUrl) return;
    const contactName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
    const params = new URLSearchParams({
      type: 'congrats',
      prefillName: contactName,
      prefillPhone: contact.phone || '',
      prefillEmail: contact.email || '',
      prefillPhoto: photoUrl,
      for_contact: id as string,
      return_to_contact: 'true',
    });
    setShowPhotoViewer(false);
    setSelectedPhotoIndex(-1);
    setFullPhoto(null);
    router.push(`/settings/create-card?${params.toString()}`);
  };

  // Handle card template selection → navigate to card creation and return
  const handleCardTemplateSelect = (cardType: string) => {    setShowCardTemplatePicker(false);
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
  const [customCardTypes, setCustomCardTypes] = useState<any[]>([]);

  // Fetch custom card types for the composer
  useEffect(() => {
    const fetchCustomCardTypes = async () => {
      try {
        const storeId = user?.store_id;
        if (!storeId) return;
        const res = await api.get(`/congrats/templates/all/${storeId}`);
        const all = res.data || [];
        const defaults = ['congrats', 'birthday', 'holiday', 'thankyou', 'anniversary', 'welcome'];
        const custom = all
          .filter((t: any) => !defaults.includes(t.card_type))
          .map((t: any) => ({
            type: t.card_type,
            label: t.headline || t.card_type,
            sub: t.message?.substring(0, 40) || 'Custom card template',
            color: t.accent_color || '#C9A962',
            icon: 'create-outline',
          }));
        setCustomCardTypes(custom);
      } catch (e) { /* ignore */ }
    };
    fetchCustomCardTypes();
  }, [user?.store_id]);

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
    setShowTagPicker(false);
    setTagSearch('');
    
    // Confirmation dialog
    showConfirm(
      'Add Tag',
      `Add "${name}" to ${contact.first_name || 'this contact'}?`,
      async () => {
        const updatedTags = [...contact.tags, name];
        setContact((prev: any) => ({ ...prev, tags: updatedTags }));
        try {
          const res = await api.patch(`/contacts/${user._id}/${id}/tags`, { tags: updatedTags });
          showToast(`Tag "${name}" added`);
          
          // Check for sold workflow response
          if (res.data?.sold_workflow) {
            const sw = res.data.sold_workflow;
            if (sw.status === 'validation_failed' && sw.missing_fields?.length > 0) {
              setSoldWorkflowResult(sw);
              setShowSoldModal(true);
            } else if (sw.status === 'queued') {
              showToast('Sold workflow completed');
            }
          }
        } catch (e: any) {
          setContact((prev: any) => ({ ...prev, tags: prev.tags.filter((t: string) => t !== name) }));
          showSimpleAlert('Error', 'Could not add tag');
        }
      }
    );
  };

  // Toggle birthday/anniversary send opt-in (adds/removes the manual tag; never fires a send)
  const toggleDateOptin = async (occasion: 'birthday' | 'anniversary', enable: boolean) => {
    if (!user?._id || !id) return;
    const tag = occasion === 'birthday' ? 'Birthday' : 'Anniversary';
    setContact((prev: any) => ({
      ...prev,
      tags: enable
        ? [...(prev.tags || []).filter((t: string) => t.toLowerCase() !== tag.toLowerCase()), tag]
        : (prev.tags || []).filter((t: string) => t.toLowerCase() !== tag.toLowerCase()),
    }));
    try {
      await api.post(`/contacts/${user._id}/date-optins/bulk`, {
        contact_ids: [String(id)],
        occasion,
        enable,
      });
      showToast(enable ? `${tag} sends ON` : `${tag} sends OFF`);
    } catch (e) {
      setContact((prev: any) => ({
        ...prev,
        tags: enable
          ? (prev.tags || []).filter((t: string) => t.toLowerCase() !== tag.toLowerCase())
          : [...(prev.tags || []), tag],
      }));
      showSimpleAlert('Error', 'Could not update. Try again.');
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
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true, aspect: [1, 1], quality: 0.5, base64: true,
      });
      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        let photoData: string | null = null;
        if (asset.base64) {
          photoData = `data:image/jpeg;base64,${asset.base64}`;
        } else if (asset.uri) {
          // On web, base64 may not be returned — use the blob URI directly
          photoData = asset.uri;
        }
        if (photoData) {
          setContact({ ...contact, photo: photoData });
          showToast('Photo selected! Tap Save to apply.', 'info');
        } else {
          showToast('Could not load the selected photo. Please try again.', 'warning');
        }
      }
    } catch (e) {
      console.error('pickImage error:', e);
      showToast('Failed to pick photo. Please try again.', 'error');
    }
  };

  // iOS cannot present the image picker/camera while the photo-viewer Modal is
  // still dismissing (it opens then instantly closes). Defer the launch until the
  // modal has fully closed: use the Modal's onDismiss (iOS) with a timeout fallback.
  const pendingActionRef = useRef<null | 'library' | 'camera'>(null);
  const requestAddPhotoFromGallery = () => {
    // Web has no native camera picker — go straight to the file picker.
    if (Platform.OS === 'web') { startDeferredPick('library'); return; }
    showAlert('Add Photo', undefined, [
      { text: 'Take Photo', onPress: () => startDeferredPick('camera') },
      { text: 'Choose from Library', onPress: () => startDeferredPick('library') },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };
  const startDeferredPick = (action: 'library' | 'camera') => {
    pendingActionRef.current = action;
    setShowPhotoViewer(false);
    setFullPhoto(null);
    setAllPhotos([]);
    setSelectedPhotoIndex(-1);
    if (Platform.OS !== 'ios') {
      // Android/web don't reliably fire Modal.onDismiss — use a short delay
      setTimeout(runPendingPick, 350);
    }
  };
  const runPendingPick = () => {
    const action = pendingActionRef.current;
    pendingActionRef.current = null;
    if (action === 'camera') captureGalleryPhoto();
    else if (action === 'library') uploadGalleryPhoto();
  };

  // Upload a picked/captured asset to the contact + gallery immediately (no Save step).
  const persistPickedPhoto = async (asset: any) => {
    const photoData = asset?.base64
      ? `data:image/jpeg;base64,${asset.base64}`
      : asset?.uri || null;
    if (!photoData) {
      showToast('Could not load the selected photo. Please try again.', 'warning');
      return;
    }
    showToast('Uploading photo...', 'info');
    const resp = await api.post(`/contacts/${user._id}/${id}/photo`, { photo: photoData });
    const newUrl = resp.data?.photo_url;
    setContact((prev: any) => ({
      ...prev,
      photo: newUrl ? resolvePhotoUrl(newUrl) : photoData,
      photo_url: newUrl || prev?.photo_url,
      photo_thumbnail: newUrl || prev?.photo_thumbnail,
    }));
    await preloadGalleryPhotos();
    showToast('Photo added!', 'success');
  };

  // Choose an existing photo from the library.
  const uploadGalleryPhoto = async () => {
    if (!user?._id || !id) return;
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true, aspect: [1, 1], quality: 0.5, base64: true,
      });
      if (result.canceled || !result.assets || result.assets.length === 0) return;
      await persistPickedPhoto(result.assets[0]);
    } catch (e) {
      console.error('uploadGalleryPhoto error:', e);
      showToast('Failed to add photo. Please try again.', 'error');
    }
  };

  // Snap a brand-new photo with the camera.
  const captureGalleryPhoto = async () => {
    if (!user?._id || !id) return;
    try {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (perm.status !== 'granted') {
        showSimpleAlert('Camera Permission', 'Camera access is required to take a photo.');
        return;
      }
      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true, aspect: [1, 1], quality: 0.5, base64: true,
      });
      if (result.canceled || !result.assets || result.assets.length === 0) return;
      await persistPickedPhoto(result.assets[0]);
    } catch (e) {
      console.error('captureGalleryPhoto error:', e);
      showToast('Failed to take photo. Please try again.', 'error');
    }
  };

  // Preload gallery photos when contact loads (so gallery opens instantly)
  const preloadGalleryPhotos = React.useCallback(async () => {
    if (!user || isNewContact) return;
    try {
      const galleryRes = await api.get(`/contacts/${user._id}/${id}/photos/all`);
      const rawPhotos = galleryRes.data?.photos || [];
      const photos = rawPhotos.map((p: any) => ({
        ...p,
        url: resolvePhotoUrl(p.url),
        thumbnail_url: resolvePhotoUrl(p.thumbnail_url || p.url),
      }));
      setAllPhotos(photos);
    } catch { /* silent — gallery will show empty */ }
  }, [user, id, isNewContact]);

  React.useEffect(() => {
    if (!isNewContact && user) preloadGalleryPhotos();
  }, [isNewContact, user]);

  const viewFullPhoto = () => {
    if (!user || isNewContact) return;
    setShowPhotoViewer(true);
    setSelectedPhotoIndex(-1);
    setFullPhoto(null);
    // If photos already preloaded, show grid instantly
    if (allPhotos.length > 0) {
      setFullPhotoLoading(false);
      if (allPhotos.length === 1) {
        setSelectedPhotoIndex(0);
        setFullPhoto(allPhotos[0]?.url || resolvePhotoUrl(contact.photo));
      }
      return;
    }
    // Fallback: load now (first visit or preload didn't run)
    setFullPhotoLoading(true);
    api.get(`/contacts/${user._id}/${id}/photos/all`).then(res => {
      const photos = (res.data?.photos || []).map((p: any) => ({
        ...p, url: resolvePhotoUrl(p.url), thumbnail_url: resolvePhotoUrl(p.thumbnail_url || p.url),
      }));
      setAllPhotos(photos);
      if (photos.length <= 1) {
        setSelectedPhotoIndex(0);
        setFullPhoto(photos[0]?.url || resolvePhotoUrl(contact.photo));
      }
    }).catch(() => {
      setAllPhotos([]);
      if (contact.photo) {
        setSelectedPhotoIndex(0);
        setFullPhoto(resolvePhotoUrl(contact.photo));
      }
    }).finally(() => setFullPhotoLoading(false));
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
    // ── Native (iOS/Android) — use expo-av ───────────────────────────────────
    if (Platform.OS !== 'web') {
      try {
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          import('expo-linking').then(L => L.openSettings?.()).catch(() => {});
          showSimpleAlert('Microphone Blocked', 'Enable microphone in Settings → Im On Social → Microphone, then try again.');
          return;
        }
        // Reset audio session before recording — fixes iOS audio session conflicts
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
          staysActiveInBackground: false,
        });
        // Small delay to let audio session settle
        await new Promise(r => setTimeout(r, 100));
        let recordingInstance: Audio.Recording | null = null;
        try {
          const { recording } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
          recordingInstance = recording;
        } catch {
          // Retry once after resetting the session
          await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
          await new Promise(r => setTimeout(r, 200));
          await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
          const { recording } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
          recordingInstance = recording;
        }
        setNativeRecording(recordingInstance);
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
      } catch (e: any) {
        console.error('Native recording failed:', e);
        showSimpleAlert('Recording Error', 'Could not start recording. Please check that Im On Social has microphone access in your iPhone Settings.');
      }
      return;
    }
    // ── Web — use MediaRecorder API ──────────────────────────────────────────
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

  const stopRecording = async () => {
    setIsRecording(false);
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    // Native path
    if (Platform.OS !== 'web' && nativeRecording) {
      try {
        await nativeRecording.stopAndUnloadAsync();
        const uri = nativeRecording.getURI();
        setNativeRecording(null);
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
        if (uri && user) {
          setUploadingVoiceNote(true);
          try {
            // React Native FormData: pass URI object directly — RN handles the file read
            const fd = new FormData();
            fd.append('audio', { uri, type: 'audio/m4a', name: 'voice_note.m4a' } as any);
            fd.append('duration', String(recordingTime));
            // Use the correct endpoint: /voice-notes/{userId}/{contactId}
            const res = await api.post(
              `/voice-notes/${user._id}/${id}`,
              fd,
              { headers: { 'Content-Type': 'multipart/form-data' } }
            );
            if (res.data) await loadVoiceNotes();
          } catch (uploadErr: any) {
            console.error('[VoiceNote] Upload error:', uploadErr?.response?.data || uploadErr?.message);
            showSimpleAlert('Error', 'Failed to save voice note. Please try again.');
          } finally {
            setUploadingVoiceNote(false);
          }
        }
      } catch (e) {
        console.error('Native stop recording failed:', e);
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false }).catch(() => {});
        showSimpleAlert('Error', 'Recording stopped unexpectedly. Please try again.');
      }
      setRecordingTime(0);
      return;
    }
    // Web path
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
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

  const nativeSoundRef = React.useRef<any>(null);

  const playVoiceNote = async (noteId: string, audioUrl: string) => {
    // Stop any current playback
    if (nativeSoundRef.current) {
      try { await nativeSoundRef.current.unloadAsync(); } catch {}
      nativeSoundRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (playingNoteId === noteId) {
      setPlayingNoteId(null);
      return;
    }

    // Resolve to absolute URL for native
    const { resolvePhotoUrl } = await import('../../utils/photoUrl');
    const resolvedUrl = audioUrl.startsWith('http') ? audioUrl : resolvePhotoUrl(audioUrl) || audioUrl;

    if (Platform.OS !== 'web') {
      // Native: use expo-av Sound
      try {
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
        const { sound } = await Audio.Sound.createAsync(
          { uri: resolvedUrl },
          { shouldPlay: true },
          (status: any) => {
            if (status.didJustFinish || !status.isLoaded) {
              setPlayingNoteId(null);
              nativeSoundRef.current = null;
            }
          }
        );
        nativeSoundRef.current = sound;
        setPlayingNoteId(noteId);
      } catch (e) {
        console.error('[VoiceNote] Playback error:', e);
        showSimpleAlert('Error', 'Failed to play audio. Please try again.');
      }
      return;
    }

    // Web: use HTML5 Audio
    const audio = new Audio(resolvedUrl);
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

  // ===== AI RELATIONSHIP INTEL (auto-updating) =====
  const refreshIntel = async () => {
    if (!user || isNewContact || intelBusyRef.current) return;
    intelBusyRef.current = true;
    setIntelRefreshing(true);
    try {
      const data = await contactsAPI.generateContactIntel(user._id, id as string);
      setIntelData({ ...data, stale: false });
    } catch (e) {
      console.error('Failed to refresh intel:', e);
    } finally {
      intelBusyRef.current = false;
      setIntelRefreshing(false);
    }
  };

  const loadCachedIntel = async () => {
    if (!user || isNewContact) return;
    try {
      const data = await contactsAPI.getContactIntel(user._id, id as string);
      if (data.summary) setIntelData(data);
      if (data.stale) refreshIntel();
    } catch (e) {
      // No cached intel  - that's fine
    }
  };

  React.useEffect(() => {
    if (!isNewContact && user) loadCachedIntel();
  }, [id, user, isNewContact]);

  // Toggle automation on/off for a specific date field
  const toggleAutomation = async (field: string) => {
    if (!user) return;
    try {
      const res = await api.patch(`/contacts/${user._id}/${id}/toggle-automation`, { field });
      setContact(prev => ({ ...prev, disabled_automations: res.data.disabled_automations || [] }));
    } catch (e) {
      console.error('Failed to toggle automation:', e);
    }
  };

  // Show action sheet for automation chip (edit date vs toggle auto-card)
  const handleAutomationChipPress = (field: string, label: string, color: string, value: Date | null) => {
    const disabled = contact.disabled_automations.includes(field);
    const toggleLabel = disabled ? `Resume Auto-Card` : `Pause Auto-Card`;

    if (Platform.OS === 'web') {
      setWebActionSheet({
        visible: true,
        title: `${label} Automation`,
        options: [
          { label: 'Edit Date', icon: 'calendar', color: '#007AFF', onPress: () => {
            setAutomationPickerDate(value || new Date());
            setEditingAutomation({ field, label, color, value });
          }},
          { label: toggleLabel, icon: disabled ? 'play-circle' : 'pause-circle', color: disabled ? '#34C759' : '#FF9500', onPress: () => {
            toggleAutomation(field);
          }},
        ],
      });
    } else {
      showAlert(
        `${label} Automation`,
        undefined,
        [
          { text: 'Edit Date', onPress: () => {
            setAutomationPickerDate(value || new Date());
            setEditingAutomation({ field, label, color, value });
          }},
          { text: toggleLabel, onPress: () => toggleAutomation(field) },
          { text: 'Cancel', style: 'cancel' },
        ]
      );
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
  const selectReferrer = async (ref: any) => {
    // "New Referral" means: the CURRENT contact referred the PICKED contact
    // So we update the PICKED contact's referred_by = current contact ID
    setShowReferralPicker(false);
    if (!user?._id) return;
    try {
      await contactsAPI.update(user._id, ref._id, { referred_by: id as string });
      // Increment current contact's referral count locally for instant UI update
      setContact(prev => ({ ...prev, referral_count: (prev.referral_count || 0) + 1 }));
      // Reload referrals list to show the new entry
      loadReferrals();
      showToast(`Added ${ref.first_name || 'contact'} as a referral`);
    } catch (e) {
      showSimpleAlert('Error', 'Failed to add referral');
    }
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

  // ===== RENDER (existing contact) =====
  // Build context value — components extracted in future phases consume this
  const contextValue = {
    contact, setContact, contactId: id as string, userId: user?._id || '',
    isEditing, setIsEditing, loading, saving, colors,
    events, setEvents, stats, eventsLoading,
    expandedEvents, setExpandedEvents,
    feedSearch, setFeedSearch, collapsedDateGroups, setCollapsedDateGroups,
    allPhotos, setAllPhotos, showPhotoViewer, setShowPhotoViewer,
    selectedPhotoIndex, setSelectedPhotoIndex,
    addTagFromHero: (tag: string) => setContact({ ...contact, tags: [...(contact.tags || []), tag] }),
    removeTag: (tag: string) => setContact({ ...contact, tags: (contact.tags || []).filter((t: string) => t !== tag) }),
    loadingCampaigns, selectedCampaign, setSelectedCampaign,
    composerMessage, setComposerMessage, composerMode, setComposerMode,
    reloadEvents: loadEvents,
  };

  return (
    <ContactProvider value={contextValue as any}>
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
        keyboardVerticalOffset={0}
      >
        {/* HEADER */}
        <View style={[s.header, { borderBottomColor: colors.border }]} data-testid="contact-detail-header">
          <TouchableOpacity onPress={() => router.back()} style={s.headerBtn} data-testid="contact-back-button">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={[s.headerTitle, { color: colors.text }]} numberOfLines={1}>{isNewContact ? 'New Contact' : fullName}</Text>
          {isEditing ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              {!isNewContact && (
                <TouchableOpacity onPress={() => { setIsEditing(false); loadContact(); }} style={s.headerBtn} data-testid="contact-cancel-button">
                  <Text style={[s.headerAction, { color: colors.textSecondary }]}>Cancel</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity onPress={handleSave} style={[s.headerBtn, { backgroundColor: '#C9A962', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 6 }]} disabled={saving} data-testid="contact-save-button">
                {saving ? <ActivityIndicator size="small" color="#000" /> : <Text style={[s.headerAction, { color: '#000', fontWeight: '700' }]}>Save</Text>}
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity onPress={() => setIsEditing(true)} style={s.headerBtn} data-testid="contact-edit-button">
              <Text style={s.headerAction}>Edit</Text>
            </TouchableOpacity>
          )}
        </View>

        <ScrollView ref={scrollRef} contentContainerStyle={[s.scroll, { paddingBottom: 80 }]} showsVerticalScrollIndicator={false} data-testid="contact-scroll">
          {/* ===== TASK BANNER (when arriving from Home action item) ===== */}
          {taskTitle && typeof taskTitle === 'string' && (
            <View style={{ backgroundColor: '#007AFF12', borderBottomWidth: 1, borderBottomColor: '#007AFF30', paddingHorizontal: 16, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }} data-testid="task-banner">
              <View style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: '#007AFF20', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="checkbox-outline" size={18} color="#007AFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '600', color: '#007AFF', textTransform: 'uppercase', letterSpacing: 0.5 }}>Task</Text>
                <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 1 }}>{taskTitle}</Text>
              </View>
              <Text style={{ fontSize: 13, color: colors.textTertiary }}>Send below</Text>
              <Ionicons name="arrow-down" size={14} color={colors.textTertiary} />
            </View>
          )}
          {/* ===== COMPACT PROFILE HERO ===== */}
          <HeroSection
            s={s}
            colors={colors}
            contact={contact}
            stats={stats}
            isEditing={isEditing}
            isNewContact={isNewContact}
            fullName={fullName}
            initials={initials}
            availableTags={availableTags}
            contactEnrollments={contactEnrollments}
            pickImage={pickImage}
            viewFullPhoto={viewFullPhoto}
            handleAutomationChipPress={handleAutomationChipPress}
            onAddTag={() => { loadTags(); setShowTagPicker(true); }}
          />

          {/* ===== QUICK ACTIONS ROW ===== */}
          {!isNewContact && !isEditing && (
            <QuickActionsRow
              colors={colors}
              isRecording={isRecording}
              onText={() => { setComposerMode('sms'); composerInputRef.current?.focus(); }}
              onCall={() => {
                if (contact.phone) {
                  router.push({ pathname: '/call-screen', params: { phone: contact.phone, contact_name: fullName, contact_id: id as string } } as any);
                } else {
                  showSimpleAlert('No Phone', 'This contact has no phone number saved.');
                }
              }}
              onEmail={() => { setComposerMode('email'); composerInputRef.current?.focus(); }}
              onNote={() => (isRecording ? stopRecording() : startRecording())}
              onTask={() => setShowAddTask(true)}
            />
          )}

          {/* ===== RELATIONSHIP INTEL BRIEFING (auto-updating) ===== */}
          {!isNewContact && !isEditing && (
            <IntelBriefingCard
              colors={colors}
              intelData={intelData}
              refreshing={intelRefreshing}
              onRefresh={refreshIntel}
            />
          )}

          {/* ===== SOLD WIZARD BUTTON ===== */}
          {!isNewContact && !isEditing && !contact.tags.includes('Sold') && (
            <TouchableOpacity
              style={{
                flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
                marginHorizontal: 16, marginBottom: 10, marginTop: 4,
                backgroundColor: '#C9A962', borderRadius: 14, paddingVertical: 16,
              }}
              onPress={() => {
                // Route to create-card (congrats) — same flow as home screen SOLD tile.
                // Pre-fills the contact's name + phone so "Via Text" fires
                // VCF → card (2 min) → review (5 min) → Sold tag automatically.
                const params = new URLSearchParams();
                params.set('type', 'congrats');
                const contactName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
                if (contactName) params.set('prefillName', contactName);
                if (contact.phone) params.set('prefillPhone', contact.phone);
                if (contact.email) params.set('prefillEmail', contact.email);
                // Pass contact_id so Sold tag gets applied to THIS existing contact
                params.set('for_contact', id as string);
                params.set('return_to_contact', 'true');
                params.set('sold_flow', 'true');
                router.push(`/settings/create-card?${params.toString()}` as any);
              }}
              data-testid="sold-wizard-btn"
            >
              <Ionicons name="checkmark-circle" size={22} color="#000" />
              <Text style={{ fontSize: 18, fontWeight: '800', color: '#000', letterSpacing: 0.3 }}>SOLD!</Text>
            </TouchableOpacity>
          )}

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

          {/* ===== FEED / DETAILS / CALLS TAB BAR ===== */}
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
              <TouchableOpacity
                style={[s.tabBtn, contactTab === 'calls' && s.tabBtnActive]}
                onPress={async () => {
                  setContactTab('calls');
                  if (callLogs.length === 0 && !callLogsLoading) {
                    setCallLogsLoading(true);
                    try {
                      const res = await api.get(`/calls/${user?._id}/contact/${id}`);
                      const all = [...(res.data.recordings || []), ...(res.data.calls || [])];
                      all.sort((a: any, b: any) => { try { return new Date(b.timestamp||b.created_at||0).getTime() - new Date(a.timestamp||a.created_at||0).getTime(); } catch { return 0; } });
                      setCallLogs(all);
                    } catch {}
                    setCallLogsLoading(false);
                  }
                }}
                data-testid="tab-calls"
              >
                <Text style={[s.tabBtnText, contactTab === 'calls' && s.tabBtnTextActive]}>Calls</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* ===== EDIT-MODE: Basic Info + Tags + Important Dates at top ===== */}
          {isEditing && (
            <EditFormTop
              s={s}
              colors={colors}
              contact={contact}
              setContact={setContact}
              isNewContact={isNewContact}
              showMoreDetails={showMoreDetails}
              setShowMoreDetails={setShowMoreDetails}
              availableTags={availableTags}
              removeTag={removeTag}
              onAddTag={() => { loadTags(); setShowTagPicker(true); }}
              openDatePicker={openDatePicker}
              formatDateDisplay={formatDateDisplay}
              clearDate={clearDate}
              removeCustomDateField={removeCustomDateField}
              onAddCustomDate={() => {
                setTempDate(new Date()); setActiveDateField('pending_custom');
                setActiveDateLabel('Select Date'); setShowDatePicker(true);
              }}
            />
          )}

          {/* ===== FEED TAB ===== */}
          {!isNewContact && !isEditing && contactTab === 'feed' && (
            <FeedTab
              s={s}
              colors={colors}
              contact={contact}
              user={user}
              contactId={id as string}
              isNewContact={isNewContact}
              suggestedActions={suggestedActions}
              handleSuggestedAction={handleSuggestedAction}
              taskTitle={taskTitle}
              prefill={prefill}
              setSoldWorkflowResult={setSoldWorkflowResult}
              setShowSoldModal={setShowSoldModal}
              loadContact={loadContact}
              showToast={showToast}
              loadCampaignsAndEnrollments={loadCampaignsAndEnrollments}
              setComposerMessage={setComposerMessage}
              setComposerMode={setComposerMode}
              events={events}
              feedSearch={feedSearch}
              setFeedSearch={setFeedSearch}
              feedQuery={feedQuery}
              filteredEvents={filteredEvents}
              eventDateGroups={eventDateGroups}
              eventsLoading={eventsLoading}
              expandedEvents={expandedEvents}
              setExpandedEvents={setExpandedEvents}
              collapsedDateGroups={collapsedDateGroups}
              setCollapsedDateGroups={setCollapsedDateGroups}
              hasMoreEvents={hasMoreEvents}
              loadMoreEvents={loadMoreEvents}
              loadingMoreEvents={loadingMoreEvents}
              showLogReply={showLogReply}
              setShowLogReply={setShowLogReply}
              replyText={replyText}
              setReplyText={setReplyText}
              replyPhoto={replyPhoto}
              setReplyPhoto={setReplyPhoto}
              submittingReply={submittingReply}
              handleLogReply={handleLogReply}
              pickReplyPhoto={pickReplyPhoto}
              setShowAddTask={setShowAddTask}
            />
          )}

          {/* ===== DETAILS TAB ===== */}
          {!isNewContact && !isEditing && contactTab === 'details' && (
            <DetailsTab
              s={s}
              colors={colors}
              contact={contact}
              reloadContact={loadContact}
              contactId={id as string}
              userId={user?._id || ''}
              isNewContact={isNewContact}
              voiceNotes={voiceNotes}
              voiceNotesLoading={voiceNotesLoading}
              isRecording={isRecording}
              recordingTime={recordingTime}
              uploadingVoiceNote={uploadingVoiceNote}
              playingNoteId={playingNoteId}
              showAllNotes={showAllNotes}
              startRecording={startRecording}
              stopRecording={stopRecording}
              playVoiceNote={playVoiceNote}
              deleteVoiceNote={deleteVoiceNote}
              formatRecordingTime={formatRecordingTime}
              maxRecordingSeconds={MAX_RECORDING_SECONDS}
              referrals={referrals}
              contactEnrollments={contactEnrollments}
              toggleDateOptin={toggleDateOptin}
            />
          )}

          {/* ===== REMAINING EDIT FIELDS ===== */}
          {isEditing && (
            <EditFormBottom
              s={s}
              colors={colors}
              contact={contact}
              setContact={setContact}
              isNewContact={isNewContact}
              user={user}
              contactId={id as string}
              onPickReferrer={() => { loadAllContacts(); setShowReferralPicker(true); }}
              clearReferrer={clearReferrer}
              handleDelete={handleDelete}
            />
          )}

          {/* ===== CALLS TAB ===== */}
          {!isNewContact && !isEditing && contactTab === 'calls' && (
            <CallsTab
              colors={colors}
              callLogs={callLogs}
              callLogsLoading={callLogsLoading}
              onRefresh={async () => {
                setCallLogsLoading(true);
                try {
                  const res = await api.get(`/calls/${user?._id}/contact/${id}`);
                  const all = [...(res.data.recordings || []), ...(res.data.calls || [])];
                  all.sort((a: any, b: any) => { try { return new Date(b.timestamp||b.created_at||0).getTime() - new Date(a.timestamp||a.created_at||0).getTime(); } catch { return 0; } });
                  setCallLogs(all);
                } catch {}
                setCallLogsLoading(false);
              }}
            />
          )}

          <View style={{ height: 140 }} />
        </ScrollView>

        {/* ===== INLINE COMPOSER (Inbox-Style) ===== */}
        {!isNewContact && !isEditing && (
          <ComposerBar
            s={s}
            colors={colors}
            contact={contact}
            contactId={id as string}
            composerMode={composerMode}
            setComposerMode={setComposerMode}
            composerMessage={composerMessage}
            setComposerMessage={setComposerMessage}
            composerSending={composerSending}
            inputRef={composerInputRef}
            selectedMedia={selectedMedia}
            setSelectedMedia={setSelectedMedia}
            showAISuggestion={showAISuggestion}
            setShowAISuggestion={setShowAISuggestion}
            aiSuggestion={aiSuggestion}
            setAiSuggestion={setAiSuggestion}
            loadingAI={loadingAI}
            loadAISuggestionForComposer={loadAISuggestionForComposer}
            handleComposerSend={handleComposerSend}
            handleAttachPhoto={handleAttachPhoto}
            onOpenTemplates={() => setShowTemplates(true)}
            onOpenReviewLinks={() => setShowReviewLinks(true)}
            openBusinessCardPicker={openBusinessCardPicker}
            handleVoiceToText={handleVoiceToText}
            isVoiceRecording={isVoiceRecording}
            voiceTranscribing={voiceTranscribing}
          />
        )}
      </KeyboardAvoidingView>

      {/* ===== MODALS ===== */}
      <ShareModals
        s={s}
        colors={colors}
        contact={contact}
        user={user}
        contactId={id as string}
        showReviewCardOptions={showReviewCardOptions}
        setShowReviewCardOptions={setShowReviewCardOptions}
        sendReviewCard={sendReviewCard}
        sendingReviewCard={sendingReviewCard}
        showReviewLinks={showReviewLinks}
        setShowReviewLinks={setShowReviewLinks}
        storeSlug={storeSlug}
        reviewLinks={reviewLinks}
        customLinkName={customLinkName}
        insertReviewLink={insertReviewLink}
        setComposerMessage={setComposerMessage}
        showTemplates={showTemplates}
        setShowTemplates={setShowTemplates}
        templates={templates}
        selectTemplate={selectTemplate}
        showBusinessCard={showBusinessCard}
        setShowBusinessCard={setShowBusinessCard}
        sendVCardLink={sendVCardLink}
        sendBusinessCardLink={sendBusinessCardLink}
        sendLandingPageLink={sendLandingPageLink}
        sendShowcaseLink={sendShowcaseLink}
        sendLinkPageLink={sendLinkPageLink}
        showLandingPageOptions={showLandingPageOptions}
        setShowLandingPageOptions={setShowLandingPageOptions}
        loadingCampaigns={loadingCampaigns}
        campaigns={campaigns}
        selectedCampaign={selectedCampaign}
        setSelectedCampaign={setSelectedCampaign}
        showPhotoOptionsModal={showPhotoOptionsModal}
        setShowPhotoOptionsModal={setShowPhotoOptionsModal}
        pickComposerPhoto={pickComposerPhoto}
        showCardTemplatePicker={showCardTemplatePicker}
        setShowCardTemplatePicker={setShowCardTemplatePicker}
        handleCardTemplateSelect={handleCardTemplateSelect}
        customCardTypes={customCardTypes}
        webActionSheet={webActionSheet}
        setWebActionSheet={setWebActionSheet}
      />

      <AddTaskModal
        colors={colors}
        visible={showAddTask}
        onClose={() => setShowAddTask(false)}
        contact={contact}
        newTaskTitle={newTaskTitle}
        setNewTaskTitle={setNewTaskTitle}
        newTaskNotes={newTaskNotes}
        setNewTaskNotes={setNewTaskNotes}
        newTaskDue={newTaskDue}
        setNewTaskDue={setNewTaskDue}
        newTaskDate={newTaskDate}
        setNewTaskDate={setNewTaskDate}
        newTaskTime={newTaskTime}
        setNewTaskTime={setNewTaskTime}
        newTaskApptType={newTaskApptType}
        setNewTaskApptType={setNewTaskApptType}
        newTaskPriority={newTaskPriority}
        setNewTaskPriority={setNewTaskPriority}
        savingTask={savingTask}
        handleSaveTask={handleSaveTask}
      />


      <PickerModals
        s={s}
        colors={colors}
        isEditing={isEditing}
        showReferralPicker={showReferralPicker}
        setShowReferralPicker={setShowReferralPicker}
        contactSearch={contactSearch}
        setContactSearch={setContactSearch}
        filteredContacts={filteredContacts}
        selectReferrer={selectReferrer}
        showTagPicker={showTagPicker}
        setShowTagPicker={setShowTagPicker}
        tagSearch={tagSearch}
        setTagSearch={setTagSearch}
        filteredAvailableTags={filteredAvailableTags}
        addTag={addTag}
        addTagFromHero={addTagFromHero}
        showCampaignPicker={showCampaignPicker}
        setShowCampaignPicker={setShowCampaignPicker}
        availableCampaigns={availableCampaigns}
        enrollInCampaign={enrollInCampaign}
      />

      <DateModals
        s={s}
        colors={colors}
        mode={mode}
        editingAutomation={editingAutomation}
        setEditingAutomation={setEditingAutomation}
        automationPickerDate={automationPickerDate}
        setAutomationPickerDate={setAutomationPickerDate}
        handleClearAutomation={handleClearAutomation}
        handleUpdateAutomationDate={handleUpdateAutomationDate}
        showDatePicker={showDatePicker}
        setShowDatePicker={setShowDatePicker}
        activeDateLabel={activeDateLabel}
        tempDate={tempDate}
        handleDateChange={handleDateChange}
        confirmDateSelection={confirmDateSelection}
        webMonth={webMonth}
        setWebMonth={setWebMonth}
        webDay={webDay}
        setWebDay={setWebDay}
        webYear={webYear}
        setWebYear={setWebYear}
        showCustomDateLabel={showCustomDateLabel}
        setShowCustomDateLabel={setShowCustomDateLabel}
        pendingCustomDate={pendingCustomDate}
        newCustomDateName={newCustomDateName}
        setNewCustomDateName={setNewCustomDateName}
        confirmCustomDateWithLabel={confirmCustomDateWithLabel}
      />

      {/* Photo Gallery — Modern reel */}
      <GalleryModal
        s={s}
        insets={insets}
        screenWidth={screenWidth}
        user={user}
        contactId={id as string}
        setContact={setContact}
        showPhotoViewer={showPhotoViewer}
        setShowPhotoViewer={setShowPhotoViewer}
        fullPhotoLoading={fullPhotoLoading}
        allPhotos={allPhotos}
        setAllPhotos={setAllPhotos}
        selectedPhotoIndex={selectedPhotoIndex}
        setSelectedPhotoIndex={setSelectedPhotoIndex}
        setFullPhoto={setFullPhoto}
        galleryWidth={galleryWidth}
        setGalleryWidth={setGalleryWidth}
        photoReelRef={photoReelRef}
        runPendingPick={runPendingPick}
        requestAddPhotoFromGallery={requestAddPhotoFromGallery}
        preloadGalleryPhotos={preloadGalleryPhotos}
        usePhotoForCard={usePhotoForCard}
        showToast={showToast}
      />
      <ChannelPicker
        message={channelPicker.message}
        phone={channelPicker.phone}
        email={channelPicker.email}
        link={channelPicker.link}
        onSent={channelPicker.onSent}
        visible={channelPicker.visible}
        onClose={channelPicker.close}
      />
      <SoldWorkflowModal
        visible={showSoldModal}
        onClose={() => setShowSoldModal(false)}
        onComplete={() => {
          setShowSoldModal(false);
          showToast('Sold workflow completed');
          loadContact();
        }}
        contactId={id as string}
        workflowResult={soldWorkflowResult}
      />
    </SafeAreaView>
    </ContactProvider>
  );
}


export default function ContactDetailScreenWithBoundary(props: any) {
  return <ScreenErrorBoundary screenName="Contact Detail"><ContactDetailScreen {...props} /></ScreenErrorBoundary>;
}
