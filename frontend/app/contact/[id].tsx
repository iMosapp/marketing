import React, { useState, useEffect, useCallback } from 'react';
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
import { useRouter, useLocalSearchParams } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Swipeable } from 'react-native-gesture-handler';
import { format, formatDistanceToNow, differenceInDays, differenceInMonths, differenceInYears } from 'date-fns';
import { useAuthStore } from '../../store/authStore';
import { contactsAPI, campaignsAPI, tagsAPI } from '../../services/api';
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
}

interface ContactStats {
  total_touchpoints: number;
  messages_sent: number;
  campaigns: number;
  cards_sent: number;
  broadcasts: number;
  custom_events: number;
  created_at: string | null;
}

// ===== HELPER: Time in System =====
function getTimeInSystem(createdAt: string | null): string {
  if (!createdAt) return '0d';
  const created = new Date(createdAt);
  const now = new Date();
  const years = differenceInYears(now, created);
  if (years >= 1) return `${years}y`;
  const months = differenceInMonths(now, created);
  if (months >= 1) return `${months}mo`;
  const days = differenceInDays(now, created);
  return `${Math.max(days, 0)}d`;
}

function getTimeInSystemLabel(createdAt: string | null): string {
  if (!createdAt) return 'New';
  const created = new Date(createdAt);
  const now = new Date();
  const years = differenceInYears(now, created);
  if (years >= 1) return years === 1 ? 'year' : 'years';
  const months = differenceInMonths(now, created);
  if (months >= 1) return months === 1 ? 'month' : 'months';
  const days = differenceInDays(now, created);
  if (days === 1) return 'day';
  return 'days';
}

function formatEventTime(timestamp: string): string {
  if (!timestamp) return '';
  try {
    return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
  } catch {
    return '';
  }
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
  custom: { icon: 'flag', color: '#8E8E93' },
};

export default function ContactDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
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
  });
  const [loading, setLoading] = useState(!isNewContact);
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(isNewContact);

  // Events & stats
  const [events, setEvents] = useState<ContactEvent[]>([]);
  const [stats, setStats] = useState<ContactStats>({
    total_touchpoints: 0, messages_sent: 0, campaigns: 0,
    cards_sent: 0, broadcasts: 0, custom_events: 0, created_at: null,
  });
  const [eventsLoading, setEventsLoading] = useState(false);

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

  // ===== DATA LOADING =====
  useEffect(() => {
    if (!isNewContact && user) {
      loadContact();
      loadEvents();
      loadReferrals();
      loadCampaignsAndEnrollments();
      loadTags();
    }
  }, [id, user]);

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
      });
    } catch (e) {
      console.error('Failed to load contact:', e);
    } finally {
      setLoading(false);
    }
  };

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
    if (!contact.email && key === 'email') {
      showSimpleAlert('Missing Info', 'No email address available');
      return;
    }
    switch (key) {
      case 'sms':
        if (IS_WEB) {
          Linking.openURL(`sms:${contact.phone}`);
        } else {
          // Navigate to thread/inbox for this contact
          router.push(`/thread/${id}`);
        }
        break;
      case 'call':
        Linking.openURL(`tel:${contact.phone}`);
        break;
      case 'email':
        Linking.openURL(`mailto:${contact.email}`);
        break;
      case 'review':
        showToast('Review invite feature');
        break;
      case 'card':
        if (user) router.push(`/card/${user._id}`);
        break;
      case 'gift':
        router.push(`/congrats/${id}`);
        break;
    }
  };

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
      <SafeAreaView style={s.container} edges={['top']}>
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
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* HEADER */}
        <View style={s.header} data-testid="contact-detail-header">
          <TouchableOpacity onPress={() => router.back()} style={s.headerBtn} data-testid="contact-back-button">
            <Ionicons name="chevron-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.headerTitle} numberOfLines={1}>{isNewContact ? 'New Contact' : fullName}</Text>
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

        <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
          {/* ===== PROFILE HERO ===== */}
          <View style={s.heroSection} data-testid="contact-hero">
            <View style={s.heroAvatarContainer}>
              <TouchableOpacity onPress={isEditing ? pickImage : undefined} activeOpacity={isEditing ? 0.7 : 1}>
                {contact.photo ? (
                  <Image source={{ uri: contact.photo }} style={s.heroAvatar} />
                ) : (
                  <View style={s.heroAvatarPlaceholder}>
                    <Text style={s.heroInitials}>{initials}</Text>
                  </View>
                )}
                {isEditing && (
                  <View style={s.heroCameraBadge}>
                    <Ionicons name="camera" size={14} color="#FFF" />
                  </View>
                )}
              </TouchableOpacity>
              {/* Touch point badge */}
              {!isNewContact && stats.total_touchpoints > 0 && (
                <View style={s.touchpointBadge} data-testid="touchpoint-badge">
                  <Text style={s.touchpointBadgeText}>{stats.total_touchpoints}</Text>
                </View>
              )}
            </View>

            <Text style={s.heroName} data-testid="contact-name">{fullName}</Text>
            {contact.vehicle ? <Text style={s.heroVehicle}>{contact.vehicle}</Text> : null}

            {/* Contact chips */}
            <View style={s.heroChips}>
              {contact.phone ? (
                <TouchableOpacity style={s.heroChip} onPress={() => Linking.openURL(`tel:${contact.phone}`)}>
                  <Ionicons name="call" size={14} color="#34C759" />
                  <Text style={s.heroChipText}>{contact.phone}</Text>
                </TouchableOpacity>
              ) : null}
              {contact.email ? (
                <TouchableOpacity style={s.heroChip} onPress={() => Linking.openURL(`mailto:${contact.email}`)}>
                  <Ionicons name="mail" size={14} color="#AF52DE" />
                  <Text style={s.heroChipText} numberOfLines={1}>{contact.email}</Text>
                </TouchableOpacity>
              ) : null}
            </View>

            {/* Time in system counter */}
            {!isNewContact && (
              <View style={s.timeCounter} data-testid="time-in-system">
                <View style={s.timeCounterInner}>
                  <Text style={s.timeValue}>{timeValue}</Text>
                  <Text style={s.timeLabel}>{timeLabel}</Text>
                </View>
                <Text style={s.timeSubLabel}>in system</Text>
              </View>
            )}
          </View>

          {/* ===== QUICK STATS BAR ===== */}
          {!isNewContact && (
            <View style={s.statsRow} data-testid="contact-stats-row">
              <View style={s.statItem}>
                <Text style={s.statValue}>{stats.total_touchpoints}</Text>
                <Text style={s.statLabel}>Touchpoints</Text>
              </View>
              <View style={s.statDivider} />
              <View style={s.statItem}>
                <Text style={s.statValue}>{stats.messages_sent}</Text>
                <Text style={s.statLabel}>Messages</Text>
              </View>
              <View style={s.statDivider} />
              <View style={s.statItem}>
                <Text style={s.statValue}>{stats.campaigns}</Text>
                <Text style={s.statLabel}>Campaigns</Text>
              </View>
              <View style={s.statDivider} />
              <View style={s.statItem}>
                <Text style={s.statValue}>{contact.referral_count}</Text>
                <Text style={s.statLabel}>Referrals</Text>
              </View>
            </View>
          )}

          {/* ===== QUICK ACTIONS ===== */}
          {!isNewContact && (
            <View style={s.quickActions} data-testid="quick-actions">
              {QUICK_ACTIONS.map(a => (
                <TouchableOpacity
                  key={a.key}
                  style={s.quickActionBtn}
                  onPress={() => handleQuickAction(a.key)}
                  data-testid={`quick-action-${a.key}`}
                >
                  <View style={[s.quickActionIcon, { backgroundColor: `${a.color}20` }]}>
                    <Ionicons name={a.icon as any} size={20} color={a.color} />
                  </View>
                  <Text style={s.quickActionLabel}>{a.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          {/* ===== TAGS (always visible) ===== */}
          {(contact.tags.length > 0 || isEditing) && (
            <View style={s.section}>
              <Text style={s.sectionHeader}>Tags</Text>
              <View style={s.tagsWrap}>
                {contact.tags.map((tag, i) => {
                  const info = availableTags.find(t => t.name === tag);
                  return (
                    <View key={i} style={[s.tagPill, info?.color && { borderColor: info.color }]}>
                      {info?.icon && <Ionicons name={info.icon as any} size={13} color={info.color || '#8E8E93'} />}
                      <Text style={[s.tagPillText, info?.color && { color: info.color }]}>{tag}</Text>
                      {isEditing && (
                        <TouchableOpacity onPress={() => removeTag(tag)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                          <Ionicons name="close-circle" size={15} color="#8E8E93" />
                        </TouchableOpacity>
                      )}
                    </View>
                  );
                })}
                {isEditing && (
                  <TouchableOpacity style={s.addTagChip} onPress={() => { loadTags(); setShowTagPicker(true); }} data-testid="add-tag-button">
                    <Ionicons name="add" size={16} color="#007AFF" />
                    <Text style={s.addTagChipText}>Add</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          )}

          {/* ===== ACTIVITY FEED ===== */}
          {!isNewContact && (
            <View style={s.section} data-testid="activity-feed">
              <View style={s.sectionHeaderRow}>
                <Text style={s.sectionHeader}>Activity Feed</Text>
                <Text style={s.sectionHeaderCount}>{events.length} events</Text>
              </View>

              {eventsLoading ? (
                <ActivityIndicator size="small" color="#C9A962" style={{ marginTop: 16 }} />
              ) : events.length === 0 ? (
                <View style={s.emptyFeed}>
                  <Ionicons name="time-outline" size={36} color="#2C2C2E" />
                  <Text style={s.emptyFeedText}>No activity yet</Text>
                  <Text style={s.emptyFeedSub}>Send a message or enroll in a campaign to get started</Text>
                </View>
              ) : (
                <View style={s.feedTimeline}>
                  {events.map((evt, i) => {
                    const catStyle = EVENT_CATEGORY_ICON[evt.category] || EVENT_CATEGORY_ICON.custom;
                    return (
                      <View key={i} style={s.feedItem} data-testid={`feed-event-${i}`}>
                        {/* Timeline line */}
                        {i < events.length - 1 && <View style={s.feedLine} />}
                        {/* Icon */}
                        <View style={[s.feedIcon, { backgroundColor: `${evt.color || catStyle.color}20` }]}>
                          <Ionicons name={(evt.icon || catStyle.icon) as any} size={16} color={evt.color || catStyle.color} />
                        </View>
                        {/* Content */}
                        <View style={s.feedContent}>
                          <Text style={s.feedTitle}>{evt.title}</Text>
                          {evt.description ? <Text style={s.feedDesc} numberOfLines={2}>{evt.description}</Text> : null}
                          <Text style={s.feedTime}>{formatEventTime(evt.timestamp)}</Text>
                        </View>
                      </View>
                    );
                  })}
                </View>
              )}
            </View>
          )}

          {/* ===== CONVERSATIONS LINK ===== */}
          {!isNewContact && (
            <TouchableOpacity
              style={s.conversationLink}
              onPress={() => router.push(`/thread/${id}`)}
              data-testid="go-to-conversation"
            >
              <View style={[s.quickActionIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="chatbubbles" size={20} color="#007AFF" />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={s.conversationLinkTitle}>View Conversation</Text>
                <Text style={s.conversationLinkSub}>Open full message thread</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#8E8E93" />
            </TouchableOpacity>
          )}

          {/* ===== EDITABLE DETAILS (shown when editing or new) ===== */}
          {isEditing && (
            <>
              {/* Basic Info */}
              <View style={s.section}>
                <Text style={s.sectionHeader}>Basic Info</Text>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>First Name *</Text>
                  <TextInput style={s.input} placeholder="First name" placeholderTextColor="#636366"
                    value={contact.first_name} onChangeText={t => setContact({ ...contact, first_name: t })} data-testid="input-first-name" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Last Name</Text>
                  <TextInput style={s.input} placeholder="Last name" placeholderTextColor="#636366"
                    value={contact.last_name} onChangeText={t => setContact({ ...contact, last_name: t })} data-testid="input-last-name" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Phone *</Text>
                  <TextInput style={s.input} placeholder="+1 (555) 123-4567" placeholderTextColor="#636366"
                    value={contact.phone} onChangeText={t => setContact({ ...contact, phone: t })} keyboardType="phone-pad" data-testid="input-phone" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Email</Text>
                  <TextInput style={s.input} placeholder="email@example.com" placeholderTextColor="#636366"
                    value={contact.email} onChangeText={t => setContact({ ...contact, email: t })} keyboardType="email-address" autoCapitalize="none" data-testid="input-email" />
                </View>
                <View style={s.inputGroup}>
                  <Text style={s.inputLabel}>Vehicle</Text>
                  <TextInput style={s.input} placeholder="e.g., 2023 Toyota RAV4" placeholderTextColor="#636366"
                    value={contact.vehicle} onChangeText={t => setContact({ ...contact, vehicle: t })} data-testid="input-vehicle" />
                </View>
              </View>

              {/* Important Dates */}
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
                      <Text style={[s.dateRowValue, !(contact as any)[d.field] && { color: '#636366' }]}>
                        {formatDateDisplay((contact as any)[d.field])}
                      </Text>
                    </View>
                    {(contact as any)[d.field] && (
                      <TouchableOpacity onPress={() => clearDate(d.field)} style={{ padding: 4, marginRight: 8 }}>
                        <Ionicons name="close-circle" size={20} color="#8E8E93" />
                      </TouchableOpacity>
                    )}
                    <Ionicons name="calendar" size={20} color="#8E8E93" />
                  </TouchableOpacity>
                ))}
                {contact.custom_dates.map((cd, i) => (
                  <TouchableOpacity key={i} style={s.dateRow} onPress={() => openDatePicker(`custom_${i}`, cd.date)}>
                    <View style={[s.dateRowIcon, { backgroundColor: '#007AFF20' }]}>
                      <Ionicons name="calendar-outline" size={18} color="#007AFF" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.dateRowLabel}>{cd.name}</Text>
                      <Text style={[s.dateRowValue, !cd.date && { color: '#636366' }]}>{formatDateDisplay(cd.date)}</Text>
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

              {/* Referral */}
              <View style={s.section}>
                <Text style={s.sectionHeader}>Referral</Text>
                <TouchableOpacity style={s.dateRow} onPress={() => { loadAllContacts(); setShowReferralPicker(true); }}>
                  <View style={[s.dateRowIcon, { backgroundColor: '#34C75920' }]}>
                    <Ionicons name="people" size={18} color="#34C759" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.dateRowLabel}>Referred By</Text>
                    <Text style={[s.dateRowValue, !contact.referred_by_name && { color: '#636366' }]}>
                      {contact.referred_by_name || 'Select referrer'}
                    </Text>
                  </View>
                  {contact.referred_by ? (
                    <TouchableOpacity onPress={clearReferrer} style={{ padding: 4 }}>
                      <Ionicons name="close-circle" size={20} color="#8E8E93" />
                    </TouchableOpacity>
                  ) : (
                    <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                  )}
                </TouchableOpacity>
                {contact.referred_by && (
                  <View style={s.inputGroup}>
                    <Text style={s.inputLabel}>Referral Notes</Text>
                    <TextInput style={s.input} placeholder="How did they refer?" placeholderTextColor="#636366"
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
                    size="small" color="#8E8E93"
                  />
                </View>
                <TextInput style={[s.input, { minHeight: 100, textAlignVertical: 'top', marginTop: 8 }]}
                  placeholder="Add notes..." placeholderTextColor="#636366" value={contact.notes}
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

          {/* ===== VIEW-ONLY DETAILS (when not editing) ===== */}
          {!isEditing && !isNewContact && (
            <>
              {/* Notes (view) */}
              {contact.notes ? (
                <View style={s.section}>
                  <Text style={s.sectionHeader}>Notes</Text>
                  <Text style={s.viewText}>{contact.notes}</Text>
                </View>
              ) : null}

              {/* Important Dates (view) */}
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

              {/* Referrals (view) */}
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
                      <Ionicons name="chevron-forward" size={16} color="#8E8E93" />
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              {/* Campaigns (view) */}
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

          <View style={{ height: 50 }} />
        </ScrollView>
      </KeyboardAvoidingView>

      {/* ===== MODALS ===== */}

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
            <Ionicons name="search" size={18} color="#8E8E93" />
            <TextInput style={s.modalSearchInput} placeholder="Search contacts" placeholderTextColor="#8E8E93"
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
            <TouchableOpacity onPress={() => router.push('/settings/tags')}>
              <Text style={s.modalAction}>Manage</Text>
            </TouchableOpacity>
          </View>
          <View style={s.modalSearch}>
            <Ionicons name="search" size={18} color="#8E8E93" />
            <TextInput style={s.modalSearchInput} placeholder="Search tags..." placeholderTextColor="#8E8E93"
              value={tagSearch} onChangeText={setTagSearch} autoCapitalize="none" />
          </View>
          <ScrollView style={{ flex: 1 }}>
            {filteredAvailableTags.length > 0 ? filteredAvailableTags.map(tag => (
              <TouchableOpacity key={tag._id} style={s.pickerItem} onPress={() => addTag(tag.name)} data-testid={`tag-option-${tag.name}`}>
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
                <Text style={{ fontSize: 17, fontWeight: '600', color: '#FFF' }}>{activeDateLabel}</Text>
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
                    <Text style={{ fontSize: 17, fontWeight: '600', color: '#FFF' }}>
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
            <TextInput style={s.labelInput} placeholder='e.g., "Lease Expiration"' placeholderTextColor="#8E8E93"
              value={newCustomDateName} onChangeText={setNewCustomDateName} returnKeyType="done" onSubmitEditing={confirmCustomDateWithLabel} />
            <View style={{ flexDirection: 'row', gap: 12 }}>
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: '#2C2C2E' }]} onPress={() => setShowCustomDateLabel(false)}>
                <Text style={{ fontSize: 16, fontWeight: '600', color: '#FF3B30' }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: '#007AFF' }]} onPress={confirmCustomDateWithLabel}>
                <Text style={{ fontSize: 16, fontWeight: '600', color: '#FFF' }}>Save</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}

// ===== STYLES =====
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 12, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#1C1C1E',
  },
  headerBtn: { padding: 4, minWidth: 50 },
  headerTitle: { fontSize: 17, fontWeight: '600', color: '#FFF', flex: 1, textAlign: 'center' },
  headerAction: { fontSize: 17, fontWeight: '600', color: '#C9A962' },
  scroll: { paddingBottom: 32 },

  // Hero
  heroSection: { alignItems: 'center', paddingTop: 24, paddingBottom: 20, paddingHorizontal: 16 },
  heroAvatarContainer: { position: 'relative', marginBottom: 14 },
  heroAvatar: { width: 96, height: 96, borderRadius: 48, borderWidth: 3, borderColor: '#C9A962' },
  heroAvatarPlaceholder: {
    width: 96, height: 96, borderRadius: 48,
    backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center',
    borderWidth: 3, borderColor: '#2C2C2E',
  },
  heroInitials: { fontSize: 32, fontWeight: '700', color: '#C9A962' },
  heroCameraBadge: {
    position: 'absolute', bottom: 0, right: 0,
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: '#000',
  },
  touchpointBadge: {
    position: 'absolute', top: -4, right: -4,
    backgroundColor: '#C9A962', borderRadius: 12,
    minWidth: 24, height: 24, alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: 6, borderWidth: 2, borderColor: '#000',
  },
  touchpointBadgeText: { fontSize: 11, fontWeight: '800', color: '#000' },
  heroName: { fontSize: 24, fontWeight: '700', color: '#FFF', marginBottom: 4 },
  heroVehicle: { fontSize: 14, color: '#C9A962', fontWeight: '600', letterSpacing: 0.5, marginBottom: 8 },
  heroChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginBottom: 16 },
  heroChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#1C1C1E', borderRadius: 20, paddingVertical: 6, paddingHorizontal: 12,
  },
  heroChipText: { fontSize: 13, color: '#8E8E93' },

  // Time counter
  timeCounter: { alignItems: 'center', marginTop: 4 },
  timeCounterInner: { flexDirection: 'row', alignItems: 'baseline', gap: 4 },
  timeValue: { fontSize: 28, fontWeight: '800', color: '#C9A962' },
  timeLabel: { fontSize: 14, fontWeight: '600', color: '#8E8E93' },
  timeSubLabel: { fontSize: 11, color: '#636366', marginTop: 2, textTransform: 'uppercase', letterSpacing: 1 },

  // Stats row
  statsRow: {
    flexDirection: 'row', marginHorizontal: 16, marginBottom: 16,
    backgroundColor: '#1C1C1E', borderRadius: 14, padding: 16,
    alignItems: 'center',
  },
  statItem: { flex: 1, alignItems: 'center' },
  statValue: { fontSize: 20, fontWeight: '700', color: '#FFF', marginBottom: 2 },
  statLabel: { fontSize: 11, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5 },
  statDivider: { width: 1, height: 28, backgroundColor: '#2C2C2E' },

  // Quick actions
  quickActions: {
    flexDirection: 'row', marginHorizontal: 16, marginBottom: 16,
    justifyContent: 'space-between',
  },
  quickActionBtn: { alignItems: 'center', gap: 6, flex: 1 },
  quickActionIcon: {
    width: 44, height: 44, borderRadius: 22,
    alignItems: 'center', justifyContent: 'center',
  },
  quickActionLabel: { fontSize: 11, color: '#8E8E93', fontWeight: '500' },

  // Section
  section: { marginHorizontal: 16, marginBottom: 16 },
  sectionHeader: {
    fontSize: 13, fontWeight: '600', color: '#8E8E93',
    textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10,
  },
  sectionHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  sectionHeaderCount: { fontSize: 12, color: '#636366' },

  // Tags
  tagsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tagPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: '#1C1C1E', borderRadius: 16,
    paddingVertical: 6, paddingHorizontal: 12,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  tagPillText: { fontSize: 13, fontWeight: '500', color: '#FFF' },
  addTagChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#007AFF15', borderRadius: 16,
    paddingVertical: 6, paddingHorizontal: 12,
    borderWidth: 1, borderColor: '#007AFF30', borderStyle: 'dashed',
  },
  addTagChipText: { fontSize: 13, fontWeight: '600', color: '#007AFF' },

  // Activity feed
  emptyFeed: { alignItems: 'center', paddingVertical: 32 },
  emptyFeedText: { fontSize: 16, color: '#8E8E93', marginTop: 8 },
  emptyFeedSub: { fontSize: 13, color: '#636366', marginTop: 4, textAlign: 'center' },
  feedTimeline: { gap: 0 },
  feedItem: {
    flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 10,
    position: 'relative',
  },
  feedLine: {
    position: 'absolute', left: 17, top: 42, bottom: -10,
    width: 2, backgroundColor: '#1C1C1E',
  },
  feedIcon: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
    marginRight: 12,
  },
  feedContent: { flex: 1 },
  feedTitle: { fontSize: 14, fontWeight: '600', color: '#FFF', marginBottom: 2 },
  feedDesc: { fontSize: 13, color: '#8E8E93', marginBottom: 4 },
  feedTime: { fontSize: 12, color: '#636366' },

  // Conversation link
  conversationLink: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, marginBottom: 16,
    backgroundColor: '#1C1C1E', borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  conversationLinkTitle: { fontSize: 15, fontWeight: '600', color: '#FFF' },
  conversationLinkSub: { fontSize: 12, color: '#8E8E93', marginTop: 1 },

  // Input group
  inputGroup: { marginBottom: 12 },
  inputLabel: { fontSize: 12, fontWeight: '500', color: '#8E8E93', marginBottom: 4, marginLeft: 2 },
  input: {
    backgroundColor: '#1C1C1E', borderRadius: 10, padding: 14,
    fontSize: 16, color: '#FFF', borderWidth: 1, borderColor: '#2C2C2E',
  },

  // Date row
  dateRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#1C1C1E', borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  dateRowIcon: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  dateRowLabel: { fontSize: 12, color: '#8E8E93', marginBottom: 1 },
  dateRowValue: { fontSize: 15, fontWeight: '600', color: '#FFF' },

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
    backgroundColor: '#1C1C1E', borderWidth: 1, borderColor: '#FF3B3040',
  },
  deleteBtnText: { fontSize: 16, fontWeight: '600', color: '#FF3B30' },

  // View-only rows
  viewText: { fontSize: 15, color: '#D1D1D6', lineHeight: 22 },
  viewRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1C1C1E',
  },
  viewRowLabel: { fontSize: 14, color: '#8E8E93', flex: 1 },
  viewRowValue: { fontSize: 14, fontWeight: '600', color: '#FFF' },

  // Referral items
  referralItem: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1C1C1E',
  },
  referralAvatar: {
    width: 32, height: 32, borderRadius: 16, backgroundColor: '#2C2C2E',
    alignItems: 'center', justifyContent: 'center',
  },
  referralAvatarText: { fontSize: 12, fontWeight: '600', color: '#FFF' },
  referralName: { flex: 1, fontSize: 14, fontWeight: '500', color: '#FFF' },

  // Campaign cards
  campaignCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#1C1C1E', borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  campaignName: { fontSize: 15, fontWeight: '600', color: '#FFF' },
  campaignSub: { fontSize: 13, color: '#8E8E93', marginTop: 1 },

  // Modals
  modalContainer: { flex: 1, backgroundColor: '#000' },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16, borderBottomWidth: 1, borderBottomColor: '#2C2C2E',
  },
  modalCancel: { fontSize: 17, color: '#007AFF' },
  modalTitle: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  modalAction: { fontSize: 17, color: '#007AFF' },
  modalSearch: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#1C1C1E', borderRadius: 10, margin: 16, paddingHorizontal: 12, gap: 8,
  },
  modalSearchInput: { flex: 1, padding: 12, fontSize: 16, color: '#FFF' },
  pickerItem: {
    flexDirection: 'row', alignItems: 'center', padding: 14,
    borderBottomWidth: 1, borderBottomColor: '#1C1C1E',
  },
  pickerAvatar: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: '#2C2C2E',
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  pickerAvatarText: { fontSize: 15, fontWeight: '600', color: '#FFF' },
  pickerName: { fontSize: 16, fontWeight: '500', color: '#FFF' },
  pickerSub: { fontSize: 14, color: '#8E8E93', marginTop: 1 },
  emptyPicker: { padding: 32, alignItems: 'center' },
  emptyPickerText: { fontSize: 16, color: '#8E8E93' },

  // Date picker modal
  dateOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  dateModal: { backgroundColor: '#1C1C1E', borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingBottom: 20 },
  dateModalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16, borderBottomWidth: 1, borderBottomColor: '#2C2C2E',
  },
  dateConfirmBtn: { backgroundColor: '#007AFF', borderRadius: 12, padding: 16, alignItems: 'center' },

  // Web picker
  webPickerLabel: { fontSize: 12, fontWeight: '600', color: '#8E8E93', marginBottom: 8, textTransform: 'uppercase' },
  webPickerScroll: { maxHeight: 200, width: '100%', backgroundColor: '#2C2C2E', borderRadius: 8 },
  webPickerItem: { paddingVertical: 10, paddingHorizontal: 12, alignItems: 'center' },
  webPickerItemSel: { backgroundColor: '#007AFF', borderRadius: 6, marginHorizontal: 4 },
  webPickerText: { fontSize: 16, color: '#8E8E93' },
  webPickerTextSel: { color: '#FFF', fontWeight: '600' },

  // Label modal
  labelOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-start', paddingTop: 150 },
  labelModal: { backgroundColor: '#1C1C1E', borderRadius: 16, marginHorizontal: 20, padding: 24 },
  labelTitle: { fontSize: 20, fontWeight: '700', color: '#FFF', textAlign: 'center', marginBottom: 8 },
  labelSub: { fontSize: 15, color: '#007AFF', textAlign: 'center', marginBottom: 20, fontWeight: '600' },
  labelInput: { backgroundColor: '#2C2C2E', borderRadius: 12, padding: 16, fontSize: 16, color: '#FFF', marginBottom: 24 },
  labelBtn: { flex: 1, borderRadius: 12, padding: 16, alignItems: 'center' },
});
