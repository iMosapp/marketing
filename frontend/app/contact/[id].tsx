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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
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
import api from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import { useToast } from '../../components/common/Toast';
import VoiceInput from '../../components/VoiceInput';
import CampaignJourney from '../../components/CampaignJourney';
import { SoldWorkflowModal } from '../../components/SoldWorkflowModal';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { getS } from '../../components/contact/contactStyles';
import {
  getTimeInSystem, getTimeInSystemLabel, formatEventTime, formatDateUTC,
  QUICK_ACTIONS, EVENT_CATEGORY_ICON, IntelRenderer,
} from '../../utils/contactHelpers';
import { EVENT_TYPE_LABELS, getEventLabel } from '../../utils/eventTypes';
import PersonalIntelSection from '../../components/PersonalIntelSection';
import ChannelPicker, { useChannelPicker } from '../../components/ChannelPicker';

const IS_WEB = Platform.OS === 'web';

function getEventTitle(evt: { title?: string; event_type: string; metadata?: any }): string {
  // card_headline in metadata wins — set for custom cards since slug v timestamp 
  if (evt.metadata?.card_headline) return `Viewed '${evt.metadata.card_headline}' Card`;
  if (evt.title) return evt.title;
  return getEventLabel(evt.event_type);
}

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


export default function ContactDetailScreen() {
  const { colors } = useThemeStore();
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
  const { id, prefill, channel, action, taskId, taskTitle, event_type: urlEventType, event_title: urlEventTitle } = useLocalSearchParams();
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
  const [voiceNotesLoading, setVoiceNotesLoading] = useState(false);
  const [uploadingVoiceNote, setUploadingVoiceNote] = useState(false);
  const [playingNoteId, setPlayingNoteId] = useState<string | null>(null);
  const [showAllNotes, setShowAllNotes] = useState(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const recordingTimerRef = React.useRef<any>(null);
  const scrollRef = React.useRef<ScrollView>(null);
  const MAX_RECORDING_SECONDS = 300;

  // AI Relationship Intel
  const [intelData, setIntelData] = useState<any>(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [intelGenerating, setIntelGenerating] = useState(false);
  const [showIntel, setShowIntel] = useState(false);

  // Events & stats
  const [events, setEvents] = useState<ContactEvent[]>([]);
  const [stats, setStats] = useState<ContactStats>({
    total_touchpoints: 0, messages_sent: 0, campaigns: 0,
    cards_sent: 0, broadcasts: 0, custom_events: 0, link_clicks: 0, referral_count: 0, created_at: null,
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
  const [composerInputHeight, setComposerInputHeight] = useState(36);
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
    showAlert('Add Photo', undefined, [
      { text: 'Add a Photo', onPress: async () => {
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
      setAllContacts(data.filter((c: any) => c._id !== id));
    } catch (e) { console.error(e); }
  };

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
        setShowReviewLinks(true);
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
      // Upload photo if attached
      let photoUrl = '';
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
          photoUrl = uploadRes.data?.original_url || uploadRes.data?.url || uploadRes.data?.file_url || '';
        } catch (uploadErr) {
          console.warn('Photo upload failed, sending text only:', uploadErr);
        }
      }

      // Make photo URL absolute so it's a clickable link in SMS
      let absolutePhotoUrl = photoUrl;
      if (photoUrl && photoUrl.startsWith('/')) {
        const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
        absolutePhotoUrl = `${baseUrl}${photoUrl}`;
      }
      const messageContent = absolutePhotoUrl ? `${content || ''}\n${absolutePhotoUrl}`.trim() : (content || '');
      
      // Create or get existing conversation for this contact
      const conv = await messagesAPI.createConversation(user._id, {
        contact_id: id as string,
        contact_phone: contact.phone || undefined,
      });
      const conversationId = conv._id || conv.id;
      
      if (composerMode === 'sms') {
        // For SMS: Log the message server-side, then open messaging channel
        const sendPayload: any = {
          conversation_id: conversationId,
          content: messageContent,
          channel: 'sms_personal',
        };
        if (composerEventType) sendPayload.event_type = composerEventType;
        if (composerEventTitle) sendPayload.event_title = composerEventTitle;
        await messagesAPI.send(user._id, sendPayload);
        
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
            if (Platform.OS === 'web' && typeof navigator !== 'undefined' && navigator.clipboard) {
              navigator.clipboard.writeText(messageContent);
            }
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
      setShowIntel(true);
      // Scroll to top after intel loads
      requestAnimationFrame(() => {
        // Native approach
        scrollRef.current?.scrollTo({ y: 0, animated: true });
        // Web fallback: find the actual scrollable div (RNW renders ScrollView as nested divs)
        if (Platform.OS === 'web') {
          try {
            const el = (scrollRef.current as any)?._nativeRef?.current
              || (scrollRef.current as any)?.getScrollableNode?.()
              || (scrollRef.current as any)?.getInnerViewNode?.();
            if (el) { el.scrollTop = 0; }
            // Brute force: walk up from any known element to find the scrollable parent
            const hero = document.querySelector('[data-testid="contact-hero"]');
            if (hero) {
              let parent = hero.parentElement;
              while (parent) {
                if (parent.scrollHeight > parent.clientHeight && parent.scrollTop > 0) {
                  parent.scrollTop = 0;
                  break;
                }
                parent = parent.parentElement;
              }
            }
          } catch (_) {}
        }
      });
    } catch (e) {
      console.error('Failed to generate intel:', e);
      showSimpleAlert('Error', 'Failed to generate AI summary. Please try again.');
    } finally {
      setIntelGenerating(false);
    }
  };

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

  // ===== RENDER (existing contact) =====
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
          <View style={[s.heroSection, { backgroundColor: colors.bg }]} data-testid="contact-hero">
            <View style={s.heroRow}>
              {/* Left: Avatar */}
              <View style={s.heroAvatarContainer}>
                <TouchableOpacity onPress={isEditing ? pickImage : viewFullPhoto} activeOpacity={isEditing ? 0.7 : 0.8}>
                  {contact.photo ? (
                    <Image source={{ uri: resolvePhotoUrl(contact.photo) }} style={s.heroAvatar} />
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
                  {(contact.occupation || contact.employer || contact.organization_name) ? (
                    <View style={s.heroMetaItem}>
                      <Ionicons name="briefcase-outline" size={11} color={colors.textTertiary} />
                      <Text style={s.heroMetaText}>{[contact.occupation, contact.employer || contact.organization_name].filter(Boolean).join(' at ')}</Text>
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

              {/* Quick Record Button */}
              {!isEditing && !isNewContact && (
                <TouchableOpacity
                  onPress={isRecording ? stopRecording : startRecording}
                  activeOpacity={0.7}
                  style={{
                    width: 44, height: 44, borderRadius: 22,
                    backgroundColor: isRecording ? '#FF3B30' : '#34C759',
                    alignItems: 'center', justifyContent: 'center',
                    shadowColor: isRecording ? '#FF3B30' : '#34C759',
                    shadowOffset: { width: 0, height: 2 },
                    shadowOpacity: 0.4, shadowRadius: 6, elevation: 4,
                    marginLeft: 8,
                  }}
                  data-testid="hero-record-btn"
                >
                  <Ionicons name={isRecording ? 'stop' : 'mic'} size={22} color="#FFF" />
                </TouchableOpacity>
              )}
            </View>

            {/* Compact stats line */}
            {!isNewContact && (
              <View style={s.heroStatsLine} data-testid="contact-stats-row">
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.total_touchpoints}</Text>
                  <Text style={s.heroStatLbl}>tchs</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.messages_sent}</Text>
                  <Text style={s.heroStatLbl}>msgs</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.link_clicks}</Text>
                  <Text style={s.heroStatLbl}>clks</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.campaigns}</Text>
                  <Text style={s.heroStatLbl}>cmpn</Text>
                </View>
                <Text style={s.heroStatDot}>·</Text>
                <View style={s.heroStatChip}>
                  <Text style={s.heroStatVal}>{stats.referral_count ?? contact.referral_count}</Text>
                  <Text style={s.heroStatLbl}>refs</Text>
                </View>
              </View>
            )}

            {/* Linked App Account Card */}
            {!isNewContact && !isEditing && contact.linked_user_id && (
              <View
                style={{
                  flexDirection: 'row', alignItems: 'center',
                  backgroundColor: '#007AFF15', borderRadius: 10,
                  paddingHorizontal: 12, paddingVertical: 8, marginTop: 8,
                  borderWidth: 1, borderColor: '#007AFF30',
                }}
                data-testid="linked-account-card"
              >
                <Ionicons name="shield-checkmark" size={18} color="#007AFF" />
                <View style={{ marginLeft: 8, flex: 1 }}>
                  <Text style={{ color: '#007AFF', fontWeight: '600', fontSize: 13 }}>
                    {contact.linked_role ? (contact.linked_role === 'super_admin' ? 'Super Admin' : contact.linked_role === 'org_admin' ? 'Admin' : contact.linked_role === 'store_manager' ? 'Manager' : 'User') : 'User'} Account
                  </Text>
                  {(contact.linked_store_name || contact.linked_org_name) && (
                    <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 1 }}>
                      {[contact.linked_store_name, contact.linked_org_name].filter(Boolean).join(' · ')}
                    </Text>
                  )}
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
                    const displayTag = tag === 'imos_user' ? 'User' : tag === 'imos_super_admin' ? 'Super Admin' : tag === 'imos_org_admin' ? 'Admin' : tag === 'imos_store_manager' ? 'Manager' : tag;
                    return (
                      <View key={`tag-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10` }]}>
                        <Ionicons name={(info?.icon || 'pricetag') as any} size={13} color={chipColor} />
                        <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{displayTag}</Text>
                      </View>
                    );
                  })}
                  {contact.birthday && (() => {
                    const isPaused = contact.disabled_automations.includes('birthday');
                    return (
                    <TouchableOpacity
                      style={[s.heroTagChip, {
                        borderColor: isPaused ? '#FF950040' : '#FF2D5540',
                        backgroundColor: isPaused ? '#FF950008' : '#FF2D5510',
                        borderStyle: 'dashed',
                      }]}
                      onPress={() => handleAutomationChipPress('birthday', 'Birthday', '#FF2D55', contact.birthday)}
                      activeOpacity={0.7}
                      data-testid="auto-birthday"
                    >
                      {isPaused && <Ionicons name="pause-circle" size={14} color="#FF9500" style={{ marginRight: 1 }} />}
                      <Ionicons name="gift" size={13} color={isPaused ? '#999' : '#FF2D55'} />
                      <Text style={[s.heroTagChipText, { color: isPaused ? '#999' : '#FF2D55', textDecorationLine: isPaused ? 'line-through' : 'none' }]} numberOfLines={1}>{formatDateUTC(contact.birthday)}</Text>
                    </TouchableOpacity>
                    );
                  })()}
                  {contact.anniversary && (() => {
                    const isPaused = contact.disabled_automations.includes('anniversary');
                    return (
                    <TouchableOpacity
                      style={[s.heroTagChip, {
                        borderColor: isPaused ? '#FF950040' : '#FF6B6B40',
                        backgroundColor: isPaused ? '#FF950008' : '#FF6B6B10',
                        borderStyle: 'dashed',
                      }]}
                      onPress={() => handleAutomationChipPress('anniversary', 'Anniversary', '#FF6B6B', contact.anniversary)}
                      activeOpacity={0.7}
                      data-testid="auto-anniversary"
                    >
                      {isPaused && <Ionicons name="pause-circle" size={14} color="#FF9500" style={{ marginRight: 1 }} />}
                      <Ionicons name="heart" size={13} color={isPaused ? '#999' : '#FF6B6B'} />
                      <Text style={[s.heroTagChipText, { color: isPaused ? '#999' : '#FF6B6B', textDecorationLine: isPaused ? 'line-through' : 'none' }]} numberOfLines={1}>{formatDateUTC(contact.anniversary)}</Text>
                    </TouchableOpacity>
                    );
                  })()}
                  {contact.date_sold && (() => {
                    const isPaused = contact.disabled_automations.includes('sold_date');
                    return (
                    <TouchableOpacity
                      style={[s.heroTagChip, {
                        borderColor: isPaused ? '#FF950040' : '#34C75940',
                        backgroundColor: isPaused ? '#FF950008' : '#34C75910',
                        borderStyle: 'dashed',
                      }]}
                      onPress={() => handleAutomationChipPress('sold_date', 'Sold Date', '#34C759', contact.date_sold)}
                      activeOpacity={0.7}
                      data-testid="auto-sold"
                    >
                      {isPaused && <Ionicons name="pause-circle" size={14} color="#FF9500" style={{ marginRight: 1 }} />}
                      <Ionicons name="car-sport" size={13} color={isPaused ? '#999' : '#34C759'} />
                      <Text style={[s.heroTagChipText, { color: isPaused ? '#999' : '#34C759', textDecorationLine: isPaused ? 'line-through' : 'none' }]} numberOfLines={1}>{formatDateUTC(contact.date_sold)}</Text>
                    </TouchableOpacity>
                    );
                  })()}
                  {contactEnrollments.map((e, i) => {
                    const chipColor = e.status === 'completed' ? '#34C759' : '#007AFF';
                    return (
                      <View key={`camp-${i}`} style={[s.heroTagChip, { borderColor: `${chipColor}40`, backgroundColor: `${chipColor}10`, borderStyle: 'dashed' }]} data-testid={`campaign-chip-${i}`}>
                        <Ionicons name={e.status === 'completed' ? 'checkmark-circle' : 'play-circle'} size={13} color={chipColor} />
                        <Text style={[s.heroTagChipText, { color: chipColor }]} numberOfLines={1}>{e.campaign_name}</Text>
                        {e.status !== 'completed' && (
                          <Text style={{ fontSize: 12, color: chipColor, fontWeight: '600' }}>{e.current_step}/{e.total_steps}</Text>
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
              {/* Quick Add - Essential Fields */}
              <View style={s.section}>
                {isNewContact && <Text style={[s.sectionHeader, { fontSize: 19, marginBottom: 12 }]}>Quick Add</Text>}
                {!isNewContact && <Text style={s.sectionHeader}>Basic Info</Text>}
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>First Name *</Text>
                  <TextInput style={s.input} placeholder="First name" placeholderTextColor={colors.textTertiary}
                    value={contact.first_name} onChangeText={t => setContact({ ...contact, first_name: t })} autoFocus={isNewContact} data-testid="input-first-name" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Last Name</Text>
                  <TextInput style={s.input} placeholder="Last name" placeholderTextColor={colors.textTertiary}
                    value={contact.last_name} onChangeText={t => setContact({ ...contact, last_name: t })} data-testid="input-last-name" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Phone</Text>
                  <TextInput style={s.input} placeholder="+1 (555) 123-4567" placeholderTextColor={colors.textTertiary}
                    value={contact.phone} onChangeText={t => setContact({ ...contact, phone: t })} keyboardType="phone-pad" data-testid="input-phone" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Email</Text>
                  <TextInput style={s.input} placeholder="email@example.com" placeholderTextColor={colors.textTertiary}
                    value={contact.email} onChangeText={t => setContact({ ...contact, email: t })} keyboardType="email-address" autoCapitalize="none" data-testid="input-email" />
                </View>
              </View>

              {/* Collapsible More Details - Vehicle, Address, Tags, Dates */}
              {isNewContact && !showMoreDetails && (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, marginHorizontal: 16, marginBottom: 8, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}
                  onPress={() => setShowMoreDetails(true)}
                  data-testid="show-more-details-btn"
                >
                  <Ionicons name="add-circle-outline" size={20} color="#007AFF" style={{ marginRight: 8 }} />
                  <Text style={{ fontSize: 17, fontWeight: '600', color: '#007AFF' }}>More Details (optional)</Text>
                </TouchableOpacity>
              )}

              {(!isNewContact || showMoreDetails) && (
                <>
                  {isNewContact && (
                    <TouchableOpacity
                      style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 10, marginHorizontal: 16, marginBottom: 4 }}
                      onPress={() => setShowMoreDetails(false)}
                      data-testid="hide-more-details-btn"
                    >
                      <Ionicons name="chevron-up" size={18} color={colors.textSecondary} style={{ marginRight: 6 }} />
                      <Text style={{ fontSize: 16, color: colors.textSecondary }}>Hide Details</Text>
                    </TouchableOpacity>
                  )}

                  <View style={s.section}>
                    {!isNewContact && <View />}
                    <View style={s.inputGroup}>
                      <Text style={s.inputLabel}>Vehicle</Text>
                      <TextInput style={s.input} placeholder="e.g., 2023 Toyota RAV4" placeholderTextColor={colors.textTertiary}
                        value={contact.vehicle} onChangeText={t => setContact({ ...contact, vehicle: t })} data-testid="input-vehicle" />
                    </View>
                  </View>

                  {/* Employment Section */}
                  <View style={s.section}>
                    <Text style={s.sectionHeader}>Employment</Text>
                    <View style={s.inputGroup}>
                      <Text style={s.inputLabel}>Organization Name</Text>
                      <TextInput style={s.input} placeholder="e.g., Hertz, Goldman Sachs" placeholderTextColor={colors.textTertiary}
                        value={contact.organization_name} onChangeText={t => setContact({ ...contact, organization_name: t })} data-testid="input-organization-name" />
                    </View>
                    <View style={s.inputGroup}>
                      <Text style={s.inputLabel}>Job Title / Occupation</Text>
                      <TextInput style={s.input} placeholder="e.g., Senior Manager" placeholderTextColor={colors.textTertiary}
                        value={contact.occupation} onChangeText={t => setContact({ ...contact, occupation: t })} data-testid="input-occupation" />
                    </View>
                    <View style={s.inputGroup}>
                      <Text style={s.inputLabel}>Employer / Company</Text>
                      <TextInput style={s.input} placeholder="e.g., Goldman Sachs" placeholderTextColor={colors.textTertiary}
                        value={contact.employer} onChangeText={t => setContact({ ...contact, employer: t })} data-testid="input-employer" />
                    </View>
                  </View>

                  {/* Additional Phone Numbers */}
                  {contact.phones.length > 0 && (
                    <View style={s.section}>
                      <Text style={s.sectionHeader}>Additional Phone Numbers</Text>
                      {contact.phones.map((p, idx) => (
                        <View key={`phone-${idx}`} style={s.inputGroup}>
                          <Text style={s.inputLabel}>{p.label || 'Phone'}</Text>
                          <TextInput style={s.input} value={p.value} keyboardType="phone-pad"
                            onChangeText={t => {
                              const updated = [...contact.phones];
                              updated[idx] = { ...updated[idx], value: t };
                              setContact({ ...contact, phones: updated });
                            }}
                            data-testid={`input-phone-${idx}`} />
                        </View>
                      ))}
                    </View>
                  )}

                  {/* Additional Email Addresses */}
                  {contact.emails.length > 0 && (
                    <View style={s.section}>
                      <Text style={s.sectionHeader}>Additional Email Addresses</Text>
                      {contact.emails.map((e, idx) => (
                        <View key={`email-${idx}`} style={s.inputGroup}>
                          <Text style={s.inputLabel}>{e.label || 'Email'}</Text>
                          <TextInput style={s.input} value={e.value} keyboardType="email-address" autoCapitalize="none"
                            onChangeText={t => {
                              const updated = [...contact.emails];
                              updated[idx] = { ...updated[idx], value: t };
                              setContact({ ...contact, emails: updated });
                            }}
                            data-testid={`input-email-${idx}`} />
                        </View>
                      ))}
                    </View>
                  )}

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
                </>
              )}

              {/* Tags (edit mode  - at top) */}
              {(!isNewContact || showMoreDetails) && (
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
              )}

              {/* Important Dates (edit mode  - at top) */}
              {(!isNewContact || showMoreDetails) && (
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
              )}
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
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <TouchableOpacity
                      onPress={(e) => {
                        e.stopPropagation?.();
                        generateIntel();
                      }}
                      style={s.intelUpdateBtn}
                      data-testid="intel-update-btn"
                    >
                      <Ionicons name="refresh" size={13} color="#C9A962" />
                      <Text style={s.intelUpdateBtnText}>Update</Text>
                    </TouchableOpacity>
                    <Ionicons name={showIntel ? 'chevron-up' : 'chevron-forward'} size={18} color={colors.textTertiary} />
                  </View>
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

              {/* Task Context Banner — shows when navigating from a task notification */}
              {taskTitle ? (
                <View style={s.taskBanner} data-testid="task-context-banner">
                  <View style={s.taskBannerIcon}>
                    <Ionicons name="alert-circle" size={20} color="#FF9500" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.taskBannerLabel}>Pending Task</Text>
                    <Text style={s.taskBannerTitle}>{decodeURIComponent(taskTitle as string)}</Text>
                    {prefill ? <Text style={s.taskBannerDesc} numberOfLines={2}>{decodeURIComponent(prefill as string)}</Text> : null}
                  </View>
                  <TouchableOpacity
                    onPress={() => router.setParams({ taskTitle: '', taskId: '', prefill: '' })}
                    style={s.taskBannerClose}
                    data-testid="task-banner-dismiss"
                  >
                    <Ionicons name="close" size={16} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>
              ) : null}

              {/* Sold Workflow Status */}
              {!isNewContact && contact.sold_workflow_status && contact.sold_workflow_status !== 'not_applicable' && (
                <View style={{ marginHorizontal: 16, marginBottom: 12, backgroundColor: colors.card, borderRadius: 12, padding: 14 }} data-testid="sold-workflow-status">
                  <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Ionicons 
                        name={
                          contact.sold_workflow_status === 'delivery_success' ? 'checkmark-circle' :
                          contact.sold_workflow_status === 'delivery_pending' ? 'time' :
                          contact.sold_workflow_status === 'validation_failed' ? 'alert-circle' :
                          contact.sold_workflow_status === 'delivery_failed' ? 'close-circle' : 'help-circle'
                        }
                        size={20}
                        color={
                          contact.sold_workflow_status === 'delivery_success' ? '#34C759' :
                          contact.sold_workflow_status === 'delivery_pending' ? '#FF9500' :
                          contact.sold_workflow_status === 'validation_failed' ? '#FF9500' :
                          '#FF3B30'
                        }
                      />
                      <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>
                        Sold Workflow: {contact.sold_workflow_status.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                      </Text>
                    </View>
                    {(contact.sold_workflow_status === 'validation_failed' || contact.sold_workflow_status === 'delivery_failed') && (
                      <TouchableOpacity
                        onPress={() => {
                          if (contact.sold_workflow_status === 'validation_failed') {
                            setSoldWorkflowResult({
                              status: 'validation_failed',
                              event_id: contact.sold_workflow_event_id,
                              missing_fields: contact.sold_validation_missing_fields || [],
                            });
                            setShowSoldModal(true);
                          } else {
                            // Manual retry for delivery_failed
                            api.post(`/sold-workflow/retry/${contact.sold_workflow_event_id}`, {}, { headers: { 'X-User-ID': user?._id } })
                              .then(() => { showToast('Delivery retry initiated'); loadContact(); })
                              .catch(() => showSimpleAlert('Error', 'Retry failed'));
                          }
                        }}
                        style={{ backgroundColor: '#FF950020', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 }}
                        data-testid="sold-workflow-retry-btn"
                      >
                        <Text style={{ fontSize: 14, fontWeight: '600', color: '#FF9500' }}>
                          {contact.sold_workflow_status === 'validation_failed' ? 'Fix & Complete' : 'Retry'}
                        </Text>
                      </TouchableOpacity>
                    )}
                  </View>
                  {contact.sold_workflow_last_error && (
                    <Text style={{ fontSize: 14, color: '#FF3B30', marginTop: 6 }}>
                      {contact.sold_workflow_last_error}
                    </Text>
                  )}
                </View>
              )}

              {/* Campaign Journey — upcoming campaign activities */}
              {!isNewContact && user && (
                <CampaignJourney
                  userId={user._id}
                  contactId={id as string}
                  onEnrollmentRemoved={loadCampaignsAndEnrollments}
                  onPrePopulateComposer={(msg) => {
                    setComposerMessage(msg);
                    setComposerMode('sms');
                  }}
                />
              )}

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
                        <Image source={{ uri: replyPhoto }} style={s.bubblePhotoThumb} contentFit="cover" />
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
                    {(() => {
                      const ENGAGEMENT_SET = new Set(['digital_card_viewed', 'showcase_viewed', 'link_page_viewed', 'link_clicked', 'review_link_clicked', 'congrats_card_viewed', 'review_page_viewed', 'training_video_clicked']);
                      const MILESTONE_SET = new Set(['new_contact_added', 'campaign_enrolled', 'review_submitted', 'referral_made']);
                      const PHOTO_SET = new Set(['congrats_card_sent', 'birthday_card_sent', 'anniversary_card_sent', 'holiday_card_sent', 'thank_you_card_sent', 'thankyou_card_sent', 'welcome_card_sent', 'delivery_photo']);
                      const ENG_LABELS: Record<string, string> = {
                        digital_card_viewed: 'Customer viewed your digital card',
                        showcase_viewed: 'Customer viewed your showcase',
                        link_page_viewed: 'Customer visited your link page',
                        link_clicked: 'Customer clicked your link',
                        review_link_clicked: 'Customer clicked your review link',
                        congrats_card_viewed: 'Customer opened your congrats card',
                        review_page_viewed: 'Customer viewed your review page',
                        training_video_clicked: 'Customer watched a training video',
                      };
                      const MILE_META: Record<string, { icon: string; color: string; label: string }> = {
                        new_contact_added: { icon: 'person-add', color: '#007AFF', label: 'Relationship Started' },
                        campaign_enrolled: { icon: 'rocket', color: '#AF52DE', label: 'Campaign Launched' },
                        review_submitted: { icon: 'star', color: '#FFD60A', label: 'Review Received' },
                        referral_made: { icon: 'people', color: '#34C759', label: 'Referral Connection' },
                      };
                      let runningCount = 0;
                      return eventDateGroups.map((group, gi) => {
                      const isCollapsed = collapsedDateGroups[group.label] === true;
                      let groupEvents: typeof group.events;
                      if (showAllEvents) {
                        groupEvents = group.events;
                      } else {
                        const remaining = INITIAL_EVENT_COUNT - runningCount;
                        if (remaining <= 0) return null;
                        groupEvents = group.events.slice(0, remaining);
                      }
                      runningCount += groupEvents.length;
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
                      const evtKey = `${group.label}-${i}`;
                      const isExpanded = expandedEvents[evtKey] === true;
                      const isInbound = evt.direction === 'inbound' || evt.event_type === 'customer_reply';
                      const et = evt.event_type;
                      const catStyle = EVENT_CATEGORY_ICON[evt.category] || EVENT_CATEGORY_ICON.custom;
                      const isCustomerAction = ENGAGEMENT_SET.has(et) || isInbound || evt.category === 'customer_activity';
                      const actorColor = isCustomerAction ? '#34C759' : '#007AFF'; // green = customer, blue = salesperson

                      // ── Milestone Card ──
                      if (MILESTONE_SET.has(et)) {
                        const meta = MILE_META[et] || { icon: 'flag', color: '#C9A962', label: getEventTitle(evt) };
                        return (
                          <View key={evtKey} style={{ marginHorizontal: 4, marginBottom: 10, borderRadius: 16, borderWidth: 1, borderColor: meta.color + '30', backgroundColor: meta.color + '08', flexDirection: 'row', alignItems: 'center', padding: 14, borderStyle: 'dashed' }} data-testid={`feed-event-${evtKey}`}>
                            <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: meta.color + '18', alignItems: 'center', justifyContent: 'center', marginRight: 12 }}>
                              <Ionicons name={meta.icon as any} size={20} color={meta.color} />
                            </View>
                            <View style={{ flex: 1 }}>
                              <Text style={{ fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5, color: meta.color }}>{meta.label}</Text>
                              {evt.description ? <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 2 }} numberOfLines={2}>{evt.description}</Text> : null}
                            </View>
                            <Text style={{ fontSize: 12, color: colors.textTertiary }}>{formatEventTime(evt.timestamp)}</Text>
                          </View>
                        );
                      }

                      // ── Engagement Card (customer action = green) ──
                      if (ENGAGEMENT_SET.has(et)) {
                        const engLabel = ENG_LABELS[et] || getEventTitle(evt);
                        return (
                          <View key={evtKey} style={{ marginHorizontal: 4, marginBottom: 6, borderRadius: 14, overflow: 'hidden', flexDirection: 'row', backgroundColor: colors.card }} data-testid={`feed-event-${evtKey}`}>
                            <View style={{ width: 3, backgroundColor: '#34C759' }} />
                            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', padding: 12 }}>
                              <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#34C75915', alignItems: 'center', justifyContent: 'center', marginRight: 12 }}>
                                <Ionicons name={(evt.icon || catStyle.icon) as any} size={16} color="#34C759" />
                              </View>
                              <View style={{ flex: 1 }}>
                                <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{engLabel}</Text>
                                <Text style={{ fontSize: 12, color: colors.textTertiary, marginTop: 2 }}>{formatEventTime(evt.timestamp)}</Text>
                              </View>
                              <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                            </View>
                          </View>
                        );
                      }

                      // ── Sent Card (salesperson action = blue) ──
                      if (PHOTO_SET.has(et)) {
                        const sentLabel = 'You sent ' + (getEventTitle(evt) || '').toLowerCase();
                        return (
                          <View key={evtKey} style={{ marginHorizontal: 4, marginBottom: 6, borderRadius: 14, overflow: 'hidden', flexDirection: 'row', backgroundColor: colors.card }} data-testid={`feed-event-${evtKey}`}>
                            <View style={{ width: 3, backgroundColor: '#007AFF' }} />
                            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', padding: 12 }}>
                              <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#007AFF15', alignItems: 'center', justifyContent: 'center', marginRight: 12 }}>
                                <Ionicons name={(evt.icon || 'camera') as any} size={16} color="#007AFF" />
                              </View>
                              <View style={{ flex: 1 }}>
                                <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{sentLabel}</Text>
                                {evt.description ? <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 1 }} numberOfLines={1}>{evt.description}</Text> : null}
                                <Text style={{ fontSize: 12, color: colors.textTertiary, marginTop: 2 }}>{formatEventTime(evt.timestamp)}</Text>
                              </View>
                            </View>
                          </View>
                        );
                      }

                      // ── Inbound / Message Card ──
                      if (isInbound) {
                        return (
                          <TouchableOpacity key={evtKey} activeOpacity={0.7} onPress={() => setExpandedEvents(prev => ({ ...prev, [evtKey]: !prev[evtKey] }))} style={{ marginHorizontal: 4, marginBottom: 6, borderRadius: 14, padding: 12, backgroundColor: colors.card, flexDirection: 'row', alignItems: 'flex-start', borderLeftWidth: 3, borderLeftColor: '#30D158' }} data-testid={`feed-event-${evtKey}`}>
                            <View style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: '#30D15818', alignItems: 'center', justifyContent: 'center', marginRight: 12 }}>
                              <Ionicons name="arrow-down" size={16} color="#30D158" />
                            </View>
                            <View style={{ flex: 1 }}>
                              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                                <Text style={{ fontSize: 14, fontWeight: '700', color: '#30D158' }}>Customer Reply</Text>
                                <View style={{ backgroundColor: '#30D15820', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 }}><Text style={{ fontSize: 9, fontWeight: '700', color: '#30D158' }}>INBOUND</Text></View>
                              </View>
                              <Text style={{ fontSize: 14, color: '#30D158', fontStyle: 'italic', marginTop: 3 }} numberOfLines={isExpanded ? 10 : 1}>"{evt.description || evt.full_content}"</Text>
                              {isExpanded && evt.full_content && evt.full_content !== evt.description && (
                                <View style={{ marginTop: 6, padding: 10, borderRadius: 10, backgroundColor: '#30D15810' }}>
                                  <Text style={{ fontSize: 14, color: '#30D158' }}>"{evt.full_content}"</Text>
                                </View>
                              )}
                              {evt.has_photo && (
                                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
                                  <Ionicons name="image" size={13} color="#30D158" />
                                  <Text style={{ fontSize: 12, color: '#30D158' }}>Photo attached</Text>
                                </View>
                              )}
                              <Text style={{ fontSize: 12, color: colors.textTertiary, marginTop: 4 }}>{formatEventTime(evt.timestamp)}</Text>
                            </View>
                          </TouchableOpacity>
                        );
                      }

                      // ── Default Text Event Card (color-coded by actor) ──
                      const channelLabel = evt.channel === 'email' ? 'Email' : evt.channel === 'sms_personal' ? 'SMS' : evt.channel === 'sms' ? 'SMS' : evt.channel === 'whatsapp' ? 'WhatsApp' : '';
                      const isCustomerEvt = evt.category === 'customer_activity';
                      const actorPrefix = isCustomerEvt ? 'Customer: ' : 'You: ';
                      return (
                        <TouchableOpacity key={evtKey} activeOpacity={0.7} onPress={() => setExpandedEvents(prev => ({ ...prev, [evtKey]: !prev[evtKey] }))} style={{ marginHorizontal: 4, marginBottom: 4, borderRadius: 14, padding: 12, backgroundColor: colors.card, flexDirection: 'row', alignItems: 'flex-start', borderLeftWidth: 3, borderLeftColor: actorColor }} data-testid={`feed-event-${evtKey}`}>
                          <View style={{ position: 'relative', marginRight: 12 }}>
                            <View style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: actorColor + '15', alignItems: 'center', justifyContent: 'center' }}>
                              <Ionicons name={(evt.icon || catStyle.icon) as any} size={16} color={actorColor} />
                            </View>
                            {channelLabel ? (
                              <View style={{ position: 'absolute', bottom: -3, right: -3, backgroundColor: actorColor, borderRadius: 6, paddingHorizontal: 3, paddingVertical: 1 }}>
                                <Text style={{ fontSize: 7, fontWeight: '700', color: '#FFF' }}>{channelLabel}</Text>
                              </View>
                            ) : null}
                          </View>
                          <View style={{ flex: 1 }}>
                            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{actorPrefix}{getEventTitle(evt)}</Text>
                              <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textTertiary} />
                            </View>
                            {!isExpanded && evt.description ? (
                              <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{evt.description}</Text>
                            ) : null}
                            {isExpanded && (
                              <View style={{ marginTop: 6 }}>
                                {evt.subject ? <Text style={{ fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 4 }}>{evt.subject}</Text> : null}
                                <View style={{ padding: 10, borderRadius: 10, backgroundColor: colors.surface }}>
                                  <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20 }}>{evt.full_content || evt.description || ''}</Text>
                                </View>
                                {evt.has_photo && (
                                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6 }}>
                                    <Ionicons name="image" size={13} color="#30D158" />
                                    <Text style={{ fontSize: 12, color: '#30D158' }}>Photo attached</Text>
                                  </View>
                                )}
                                {evt.link && (
                                  <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6 }} onPress={(e) => { e.stopPropagation?.(); router.push(evt.link as any); }} data-testid={`feed-view-link-${evtKey}`}>
                                    <Ionicons name="open-outline" size={14} color="#007AFF" />
                                    <Text style={{ fontSize: 13, fontWeight: '600', color: '#007AFF' }}>View Card</Text>
                                  </TouchableOpacity>
                                )}
                              </View>
                            )}
                            <Text style={{ fontSize: 12, color: colors.textTertiary, marginTop: 4 }}>{formatEventTime(evt.timestamp)}</Text>
                          </View>
                        </TouchableOpacity>
                      );
                    })}
                        </View>
                      );
                    });
                    })()}
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
                onPress={async () => {
                  // Get the actual conversation ID (not contact ID) so thread loads messages correctly
                  try {
                    const conv = await messagesAPI.createConversation(user._id, {
                      contact_id: id as string,
                      contact_phone: contact?.phone || undefined,
                    });
                    const conversationId = conv._id || conv.id;
                    router.push({
                      pathname: `/thread/${conversationId}`,
                      params: {
                        contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
                        contact_phone: contact.phone || '',
                        contact_email: contact.email || contact.email_work || '',
                      }
                    });
                  } catch {
                    // Fallback to contact ID
                    router.push({
                      pathname: `/thread/${id}`,
                      params: {
                        contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
                        contact_phone: contact.phone || '',
                        contact_email: contact.email || contact.email_work || '',
                      }
                    });
                  }
                }}
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
                              <TouchableOpacity
                                onPress={(e) => {
                                  e.stopPropagation?.();
                                  deleteVoiceNote(note.id);
                                }}
                                style={{ padding: 12, margin: -8, zIndex: 10 }}
                                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                                data-testid={`delete-voice-note-${i}`}
                              >
                                <Ionicons name="trash-outline" size={18} color="#FF3B30" />
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
                                <Text style={{ color: '#007AFF', fontSize: 14, marginTop: 4 }}>
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

              {/* Personal Intelligence (from voice memo extraction) */}
              <PersonalIntelSection contactId={id as string} userId={user?._id || ''} colors={colors} />

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

              {/* Convert to User (super_admin only) */}
              {!isNewContact && user?.role === 'super_admin' && (
                <TouchableOpacity
                  onPress={() => {
                    const fullName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
                    showConfirm(
                      'Convert to User',
                      `Create a user account for ${fullName}? This will let them log into i'M On Social.`,
                      () => {
                        router.push({
                          pathname: '/admin/users' as any,
                          params: {
                            importName: fullName,
                            importEmail: contact.email || '',
                            importPhone: contact.phone || '',
                            importContactId: id as string,
                          },
                        });
                      }
                    );
                  }}
                  style={[s.deleteBtn, { borderColor: '#007AFF40', marginBottom: 8 }]}
                  data-testid="convert-to-user-btn"
                >
                  <Ionicons name="person-add-outline" size={18} color="#007AFF" />
                  <Text style={[s.deleteBtnText, { color: '#007AFF' }]}>Convert to User Account</Text>
                </TouchableOpacity>
              )}

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
              {/* Photo attachment preview */}
              {selectedMedia?.uri && (
                <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingTop: 10, gap: 8 }} data-testid="composer-photo-preview">
                  <Image source={{ uri: selectedMedia.uri }} style={{ width: 60, height: 60, borderRadius: 8 }} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>Photo attached</Text>
                    <Text style={{ fontSize: 13, color: colors.textTertiary }}>Will be sent with your message</Text>
                  </View>
                  <TouchableOpacity onPress={() => setSelectedMedia(null)} style={{ padding: 4 }} data-testid="remove-photo-btn">
                    <Ionicons name="close-circle" size={22} color="#FF3B30" />
                  </TouchableOpacity>
                </View>
              )}
              <TextInput
                style={[s.composerInput, { color: colors.text, height: Math.max(36, Math.min(composerInputHeight, 150)) }]}
                placeholder="Type your message..."
                placeholderTextColor={colors.textTertiary}
                value={composerMessage}
                onChangeText={setComposerMessage}
                multiline
                numberOfLines={1}
                maxLength={1000}
                onContentSizeChange={(e) => {
                  const h = e.nativeEvent.contentSize.height;
                  // Only grow when user has content; reset to min when empty
                  if (composerMessage.trim()) {
                    setComposerInputHeight(h);
                  } else {
                    setComposerInputHeight(36);
                  }
                }}
                scrollEnabled={composerInputHeight > 150}
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
                    disabled={(!composerMessage.trim() && !selectedMedia) || composerSending}
                    data-testid="composer-send-btn"
                    style={{
                      width: 36, height: 36, borderRadius: 18,
                      backgroundColor: (composerMessage.trim() || selectedMedia) && !composerSending
                        ? (composerMode === 'sms' ? '#34C759' : '#AF52DE')
                        : colors.borderLight,
                      border: 'none',
                      cursor: (!composerMessage.trim() && !selectedMedia) || composerSending ? 'not-allowed' : 'pointer',
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
                    onPress={async () => {
                      const firstName = contact.first_name || 'there';
                      const reviewUrl = `https://app.imonsocial.com/review/${storeSlug}?sp=${user?._id}`;
                      setShowReviewLinks(false);
                      try {
                        const shortRes = await api.post('/s/create', {
                          original_url: reviewUrl,
                          link_type: 'review_request',
                          user_id: user?._id,
                          reference_id: id as string,
                          metadata: { contact_id: id as string, platform: 'imos' },
                        });
                        const trackableUrl = shortRes.data?.short_url || reviewUrl;
                        setComposerMessage(`Hey ${firstName}! We'd love your feedback. Leave us a review here: ${trackableUrl}`);
                      } catch (e) {
                        setComposerMessage(`Hey ${firstName}! We'd love your feedback. Leave us a review here: ${reviewUrl}`);
                      }
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
                  dealerrater: { name: 'DealerRater', icon: 'car-sport', color: '#ED8B00' },
                  cars_com: { name: 'Cars.com', icon: 'car', color: '#5C2D91' },
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
                    <Text style={[s.actionSheetButtonText, { color: colors.textSecondary, fontSize: 18 }]}>Manage Review Links</Text>
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
          <View style={[s.toolbarModal, { marginBottom: 40 }]} onStartShouldSetResponder={() => true}>
            <View style={s.toolbarModalHeader}>
              <View style={s.toolbarModalHandle} />
            </View>
            <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 16 }} bounces={false}>
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
                    <Ionicons name="card-outline" size={28} color="#007AFF" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Digital Card</Text>
                    <Text style={s.shareOptionDesc}>Send your sleek digital business card</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendLandingPageLink} data-testid="share-landingpage-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="globe-outline" size={28} color="#5856D6" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Landing Page</Text>
                    <Text style={s.shareOptionDesc}>Send your full profile with bio, socials & more</Text>
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

                {/* CRM Timeline Link */}
                <View style={[s.shareOptionCard, { borderTopWidth: 1, borderTopColor: colors.surface, marginTop: 8, paddingTop: 16 }]}>
                  <View style={[s.shareOptionIcon, { backgroundColor: '#C9A96220' }]}>
                    <Ionicons name="open-outline" size={28} color="#C9A962" />
                  </View>
                  <View style={[s.shareOptionContent, { flex: 1 }]}>
                    <Text style={s.shareOptionTitle}>CRM Timeline Link</Text>
                    <Text style={s.shareOptionDesc}>Copy a live activity link for your CRM</Text>
                  </View>
                  <TouchableOpacity
                    style={{ backgroundColor: '#C9A962', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 }}
                    onPress={async () => {
                      try {
                        const res = await api.post(`/crm/timeline-token/${user._id}/${id}`);
                        const link = `${api.defaults.baseURL?.replace('/api', '')}/timeline/${res.data.token}`;
                        api.post(`/crm/mark-copied/${user._id}/${id}`).catch(() => {});

                        // Use native Share Sheet on mobile (most reliable on iOS)
                        if (typeof navigator !== 'undefined' && navigator.share) {
                          try {
                            await navigator.share({
                              title: `${contact.first_name || ''} ${contact.last_name || ''} — Activity Timeline`.trim(),
                              url: link,
                            });
                            return;
                          } catch (shareErr: any) {
                            // User cancelled share — still show the link
                            if (shareErr?.name === 'AbortError') return;
                          }
                        }

                        // Desktop fallback: clipboard
                        try {
                          await Clipboard.setStringAsync(link);
                          showSimpleAlert('CRM Link Copied!', 'Paste this into your CRM. It stays up-to-date automatically.');
                        } catch {
                          // Last resort: show the link so user can manually copy
                          showSimpleAlert('CRM Timeline Link', link);
                        }
                      } catch (e: any) {
                        console.error('CRM link error:', e?.response?.data || e?.message || e);
                        showSimpleAlert('Error', e?.response?.data?.detail || 'Could not generate CRM link');
                      }
                    }}
                    data-testid="copy-crm-link-btn"
                  >
                    <Text style={{ color: '#000', fontWeight: '700', fontSize: 15 }}>Copy</Text>
                  </TouchableOpacity>
                </View>
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
            </ScrollView>
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
              <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowPhotoOptionsModal(false); pickComposerPhoto(); }} data-testid="photo-option-add">
                <Ionicons name="image-outline" size={22} color="#007AFF" />
                <Text style={s.actionSheetButtonText}>Add a Photo</Text>
              </TouchableOpacity>
              <View style={s.actionSheetDivider} />
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
                    ...customCardTypes,
                  ].map(item => (
                    <TouchableOpacity
                      key={item.type}
                      style={{ alignItems: 'center', backgroundColor: `${item.color}15`, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 14, minWidth: 80 }}
                      onPress={() => { setShowPhotoOptionsModal(false); handleCardTemplateSelect(item.type); }}
                      data-testid={`card-template-${item.type}`}
                    >
                      <Ionicons name={item.icon as any} size={24} color={item.color} />
                      <Text style={{ fontSize: 14, fontWeight: '600', color: item.color, marginTop: 6 }}>{item.label}</Text>
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

      {/* Web Action Sheet for Automation Chips */}
      <Modal visible={webActionSheet.visible} animationType="slide" transparent={true} onRequestClose={() => setWebActionSheet(prev => ({ ...prev, visible: false }))}>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setWebActionSheet(prev => ({ ...prev, visible: false }))}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={s.actionSheetGroup}>
              <View style={{ paddingVertical: 14, alignItems: 'center', borderBottomWidth: 1, borderBottomColor: colors.border }}>
                <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary }}>{webActionSheet.title}</Text>
              </View>
              {webActionSheet.options.map((option, idx) => (
                <React.Fragment key={idx}>
                  <TouchableOpacity 
                    style={s.actionSheetButton} 
                    onPress={() => { setWebActionSheet(prev => ({ ...prev, visible: false })); option.onPress(); }}
                    data-testid={`action-sheet-${option.label.toLowerCase().replace(/\s+/g, '-')}`}
                  >
                    <Ionicons name={option.icon as any} size={22} color={option.color} />
                    <Text style={[s.actionSheetButtonText, { color: option.color }]}>{option.label}</Text>
                  </TouchableOpacity>
                  {idx < webActionSheet.options.length - 1 && <View style={s.actionSheetDivider} />}
                </React.Fragment>
              ))}
            </View>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setWebActionSheet(prev => ({ ...prev, visible: false }))} data-testid="action-sheet-cancel">
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
              ...customCardTypes,
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
                    fontSize: 18, marginBottom: 12, marginTop: 8,
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
                  <Text style={{ fontSize: 18, fontWeight: '600', color: '#FF3B30' }}>Clear Date</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.labelBtn, { backgroundColor: editingAutomation.color || '#007AFF' }]}
                  onPress={() => handleUpdateAutomationDate(editingAutomation.field, automationPickerDate)}
                  data-testid="automation-save-btn"
                >
                  <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>Save Date</Text>
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
                  <Text style={{ fontSize: 18, color: '#FF3B30' }}>Cancel</Text>
                </TouchableOpacity>
                <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>{activeDateLabel}</Text>
                <TouchableOpacity onPress={confirmDateSelection}>
                  <Text style={{ fontSize: 18, fontWeight: '600', color: '#007AFF' }}>Done</Text>
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
                      {Array.from({ length: 126 }, (_, i) => 1920 + i).map(y => (
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
                    <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>
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
                <Text style={{ fontSize: 18, fontWeight: '600', color: '#FF3B30' }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: '#007AFF' }]} onPress={confirmCustomDateWithLabel}>
                <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>Save</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* Photo Gallery — Modern reel */}
      <Modal visible={showPhotoViewer} animationType="slide" transparent={false} onRequestClose={() => { setShowPhotoViewer(false); setFullPhoto(null); setAllPhotos([]); setSelectedPhotoIndex(-1); }}>
        <SafeAreaView style={{ flex: 1, backgroundColor: '#000' }} edges={['top']}>
        <View style={s.galleryRoot}>
          {/* Header */}
          <View style={s.galleryTopBar}>
            <TouchableOpacity
              style={s.galleryCloseBtn}
              onPress={() => { setShowPhotoViewer(false); setFullPhoto(null); setAllPhotos([]); setSelectedPhotoIndex(-1); }}
              data-testid="close-photo-viewer"
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Ionicons name="close" size={22} color="#FFF" />
            </TouchableOpacity>
            <Text style={s.galleryTopTitle}>
              {selectedPhotoIndex >= 0 ? `${selectedPhotoIndex + 1} of ${allPhotos.length}` : 'Photos'}
            </Text>
            <TouchableOpacity
              style={s.galleryUploadBtn}
              onPress={() => { setShowPhotoViewer(false); setFullPhoto(null); setAllPhotos([]); setSelectedPhotoIndex(-1); pickImage(); }}
              data-testid="gallery-upload-btn"
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Ionicons name="camera" size={22} color="#C9A962" />
            </TouchableOpacity>
          </View>

          {fullPhotoLoading ? (
            /* === SHIMMER SKELETON GRID === */
            <View style={{ flex: 1, padding: 0 }}>
              <View
                style={s.galleryGrid}
                onLayout={(e) => setGalleryWidth(e.nativeEvent.layout.width)}
              >
                {[0,1,2,3,4,5].map(i => {
                  const sz = galleryWidth > 0 ? Math.floor((galleryWidth - 2) / 3) : 120;
                  return (
                    <View key={i} style={{ width: sz, height: sz, backgroundColor: '#1a1a1a' }} data-testid={`shimmer-${i}`} />
                  );
                })}
              </View>
            </View>
          ) : selectedPhotoIndex >= 0 && allPhotos.length > 0 ? (
            /* === FULL-SCREEN VIEWER === */
            <View style={{ flex: 1 }}>
              <ScrollView
                ref={photoReelRef}
                horizontal
                pagingEnabled
                showsHorizontalScrollIndicator={false}
                scrollEventThrottle={16}
                onLayout={() => {
                  // Scroll to the tapped photo after layout — more reliable than FlatList initialScrollIndex on web
                  if (selectedPhotoIndex > 0 && photoReelRef.current) {
                    setTimeout(() => {
                      photoReelRef.current?.scrollTo({ x: selectedPhotoIndex * screenWidth, animated: false });
                    }, 50);
                  }
                }}
                onScroll={(e) => {
                  const idx = Math.round(e.nativeEvent.contentOffset.x / screenWidth);
                  if (idx >= 0 && idx < allPhotos.length && idx !== selectedPhotoIndex) {
                    setSelectedPhotoIndex(idx);
                    setFullPhoto(allPhotos[idx]?.url || null);
                  }
                }}
                style={{ flex: 1 }}
                data-testid="photo-reel"
              >
                {allPhotos.map((item, i) => {
                  const screenH = Dimensions.get('window').height;
                  const imgH = screenH - 200;
                  return (
                    <View key={`reel-${i}`} style={{ width: screenWidth, height: imgH, justifyContent: 'center', alignItems: 'center' }}>
                      <Image
                        source={{ uri: item.url }}
                        style={{ width: screenWidth, height: imgH }}
                        contentFit="contain"
                        transition={200}
                        cachePolicy="memory-disk"
                      />
                    </View>
                  );
                })}
              </ScrollView>
              {/* Bottom action bar */}
              <View style={s.viewerBottomBar}>
                <View style={{ flex: 1 }}>
                  <Text style={s.viewerLabel} numberOfLines={1}>
                    {allPhotos[selectedPhotoIndex]?.type === 'profile' ? 'Profile Photo' : (allPhotos[selectedPhotoIndex]?.label || 'Photo')}
                  </Text>
                  {allPhotos[selectedPhotoIndex]?.date && (
                    <Text style={s.viewerDate}>{new Date(allPhotos[selectedPhotoIndex].date).toLocaleDateString()}</Text>
                  )}
                </View>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TouchableOpacity
                    style={s.viewerActionBtn}
                    onPress={() => { setSelectedPhotoIndex(-1); setFullPhoto(null); }}
                    data-testid="back-to-gallery-grid"
                  >
                    <Ionicons name="grid-outline" size={18} color="#FFF" />
                  </TouchableOpacity>
                  {/* Delete photo button */}
                  <TouchableOpacity
                    style={[s.viewerActionBtn, { backgroundColor: '#FF3B30' }]}
                    onPress={() => {
                      const photo = allPhotos[selectedPhotoIndex];
                      if (!photo) return;
                      const isProfile = photo.type === 'profile';
                      showConfirm(
                        isProfile ? 'Remove Profile Photo' : 'Delete Photo',
                        isProfile
                          ? 'This will remove the profile photo. The next photo in history will become the new profile photo.'
                          : 'Are you sure you want to delete this photo? This cannot be undone.',
                        async () => {
                          try {
                            await api.delete(`/contacts/${user?._id}/${id}/photos`, { data: { photo_url: photo.url, photo_type: photo.type } });
                            if (isProfile) {
                              setContact((prev: any) => ({ ...prev, photo: null, photo_url: null, photo_thumbnail: null, photo_path: null }));
                            }
                            showToast('Photo deleted', 'success');
                            setSelectedPhotoIndex(-1); setFullPhoto(null);
                            preloadGalleryPhotos();
                          } catch { showSimpleAlert('Error', 'Failed to delete photo'); }
                        }
                      );
                    }}
                    data-testid="delete-photo-btn"
                  >
                    <Ionicons name="trash" size={18} color="#FFF" />
                  </TouchableOpacity>
                  {allPhotos[selectedPhotoIndex]?.type !== 'profile' && (
                    <TouchableOpacity
                      style={[s.viewerActionBtn, { backgroundColor: '#C9A962' }]}
                      onPress={async () => {
                        const photoUrl = allPhotos[selectedPhotoIndex]?.url;
                        if (!photoUrl) return;
                        try {
                          await api.patch(`/contacts/${user._id}/${id}/profile-photo`, { photo_url: photoUrl });
                          setContact((prev: any) => ({ ...prev, photo: photoUrl, photo_url: photoUrl, photo_thumbnail: photoUrl }));
                          showToast('Profile photo updated!', 'success');
                          // Refresh gallery and go back to grid
                          setSelectedPhotoIndex(-1); setFullPhoto(null);
                          preloadGalleryPhotos();
                        } catch { showSimpleAlert('Error', 'Failed to update profile photo'); }
                      }}
                      data-testid="set-as-profile-btn"
                    >
                      <Ionicons name="person-circle" size={18} color="#000" />
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            </View>
          ) : allPhotos.length > 0 ? (
            /* === INSTAGRAM-STYLE 3-COLUMN GRID === */
            <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }}>
              <View
                style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 1 }}
                onLayout={(e) => setGalleryWidth(e.nativeEvent.layout.width)}
              >
                {galleryWidth > 0 && allPhotos.map((photo: any, idx: number) => {
                  const isProfile = photo.type === 'profile';
                  const tileSize = Math.floor((galleryWidth - 2) / 3);
                  return (
                    <TouchableOpacity
                      key={`${photo.type}-${idx}`}
                      activeOpacity={0.85}
                      onPress={() => { setSelectedPhotoIndex(idx); setFullPhoto(photo.url); }}
                      data-testid={`gallery-tile-${idx}`}
                      style={{ width: tileSize, height: tileSize, overflow: 'hidden', position: 'relative', backgroundColor: '#111' }}
                    >
                      <Image
                        source={{ uri: photo.thumbnail_url || photo.url }}
                        style={{ width: tileSize, height: tileSize }}
                        contentFit="cover"
                        transition={250}
                        cachePolicy="memory-disk"
                      />
                      {isProfile && (
                        <View style={s.profileBadge} data-testid="profile-badge">
                          <Ionicons name="person-circle" size={14} color="#C9A962" />
                        </View>
                      )}
                      {!isProfile && (
                        <TouchableOpacity
                          style={s.setProfileOverlay}
                          onPress={async (e) => {
                            e.stopPropagation?.();
                            try {
                              await api.patch(`/contacts/${user._id}/${id}/profile-photo`, { photo_url: photo.url });
                              setContact((prev: any) => ({ ...prev, photo: photo.url, photo_url: photo.url, photo_thumbnail: photo.url }));
                              showToast('Profile photo updated!', 'success');
                              // Refresh gallery to get correct deduped state
                              preloadGalleryPhotos();
                            } catch { showSimpleAlert('Error', 'Failed to update'); }
                          }}
                          data-testid={`set-profile-${idx}`}
                          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                        >
                          <Ionicons name="person-circle-outline" size={16} color="#FFF" />
                        </TouchableOpacity>
                      )}
                    </TouchableOpacity>
                  );
                })}
              </View>
            </ScrollView>
          ) : (
            /* === EMPTY STATE === */
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 40 }}>
              <Ionicons name="images-outline" size={48} color="rgba(255,255,255,0.15)" />
              <Text style={{ color: 'rgba(255,255,255,0.4)', fontSize: 18, marginTop: 12, textAlign: 'center' }}>No photos yet</Text>
              <TouchableOpacity
                style={{ marginTop: 20, backgroundColor: '#C9A962', borderRadius: 20, paddingHorizontal: 24, paddingVertical: 10 }}
                onPress={() => { setShowPhotoViewer(false); pickImage(); }}
                data-testid="gallery-empty-upload"
              >
                <Text style={{ color: '#000', fontWeight: '700', fontSize: 16 }}>Add Photo</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
        </SafeAreaView>
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
  );
}

