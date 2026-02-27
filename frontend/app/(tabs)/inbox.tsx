import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Modal,
  Alert,
  Platform,
  Linking,
  ScrollView,
  KeyboardAvoidingView,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BlurView } from 'expo-blur';
import * as Haptics from 'expo-haptics';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import { NotificationBell } from '../../components/notifications/NotificationBell';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { messagesAPI, contactsAPI, emailAPI } from '../../services/api';
import SwipeableConversationItem from '../../components/SwipeableConversationItem';
import AppointmentModal from '../../components/AppointmentModal';

const IS_WEB = Platform.OS === 'web';

// Web-safe icon button for header actions
const WebIconButton: React.FC<{
  onPress: () => void;
  iconName: keyof typeof Ionicons.glyphMap;
  iconSize?: number;
  iconColor: string;
  testID?: string;
  style?: any;
}> = ({ onPress, iconName, iconSize = 24, iconColor, testID, style }) => {
  if (IS_WEB) {
    return (
      <button
        type="button"
        onClick={onPress}
        data-testid={testID}
        style={{
          background: 'none',
          border: 'none',
          padding: 8,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          ...style,
        }}
      >
        <Ionicons name={iconName} size={iconSize} color={iconColor} />
      </button>
    );
  }
  return (
    <TouchableOpacity onPress={onPress} style={[{ padding: 8 }, style]} data-testid={testID}>
      <Ionicons name={iconName} size={iconSize} color={iconColor} />
    </TouchableOpacity>
  );
};

// Message Mode Types
type MessageModeType = 'sms' | 'email';

// Luxury Design System Colors - Dark Mode (SMS)
const COLORS_DARK = {
  background: '#000000',
  surface: '#1C1C1E',
  elevated: '#2C2C2E',
  accent: '#2E5CFF',
  success: '#30D158',
  warning: '#FFD60A',
  danger: '#FF453A',
  gold: '#D4AF37',
  textPrimary: '#FFFFFF',
  textSecondary: '#8E8E93',
  textTertiary: '#48484A',
  border: 'rgba(255, 255, 255, 0.08)',
  borderFocus: 'rgba(46, 92, 255, 0.5)',
};

// Light Mode Colors (Email)
const COLORS_LIGHT = {
  background: '#F2F2F7',
  surface: '#FFFFFF',
  elevated: '#E5E5EA',
  accent: '#007AFF',
  success: '#34C759',
  warning: '#FF9500',
  danger: '#FF3B30',
  gold: '#D4AF37',
  textPrimary: '#000000',
  textSecondary: '#6E6E73',
  textTertiary: '#AEAEB2',
  border: 'rgba(0, 0, 0, 0.08)',
  borderFocus: 'rgba(0, 122, 255, 0.5)',
};

// Default to dark (SMS mode)
let COLORS = COLORS_DARK;

// AI Outcome configurations with luxury colors
const AI_OUTCOME_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: string }> = {
  appointment_set: { label: 'Appt Set', color: COLORS.success, bgColor: `${COLORS.success}20`, icon: 'calendar' },
  callback_requested: { label: 'Call Back', color: COLORS.accent, bgColor: `${COLORS.accent}20`, icon: 'call' },
  needs_assistance: { label: 'Needs Help', color: COLORS.warning, bgColor: `${COLORS.warning}20`, icon: 'hand-left' },
  hot_lead: { label: 'Hot Lead', color: COLORS.danger, bgColor: `${COLORS.danger}20`, icon: 'flame' },
  question_asked: { label: 'Question', color: '#AF52DE', bgColor: '#AF52DE20', icon: 'help-circle' },
  escalated: { label: 'Help', color: '#5856D6', bgColor: '#5856D620', icon: 'alert-circle' },
};

// Haptic feedback helper
const triggerHaptic = (type: 'light' | 'medium' | 'heavy' | 'selection' = 'light') => {
  if (Platform.OS !== 'web') {
    switch (type) {
      case 'light':
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        break;
      case 'medium':
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        break;
      case 'heavy':
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
        break;
      case 'selection':
        Haptics.selectionAsync();
        break;
    }
  }
};

export default function InboxScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'unread' | 'active' | 'closed' | 'ai'>('active');
  const [conversations, setConversations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  
  // Inbox view toggle (My Inbox vs Team Inbox)
  const [inboxView, setInboxView] = useState<'my' | 'team'>('my');
  const [teamConversations, setTeamConversations] = useState<any[]>([]);
  const [loadingTeam, setLoadingTeam] = useState(false);
  
  // Message mode state (SMS vs Email)
  const [messageMode, setMessageMode] = useState<MessageModeType>('sms');
  const [toggleStyle, setToggleStyle] = useState<string>('pill');
  
  // Get current colors based on mode
  const colors = messageMode === 'email' ? COLORS_LIGHT : COLORS_DARK;
  
  // Bulk selection mode state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  
  // New message modal state
  const [showNewMessage, setShowNewMessage] = useState(false);
  const [contacts, setContacts] = useState<any[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  const [loadingContacts, setLoadingContacts] = useState(false);
  
  // Appointment modal state
  const [showAppointmentModal, setShowAppointmentModal] = useState(false);
  const [appointmentConversation, setAppointmentConversation] = useState<any>(null);
  
  // Load user preferences for toggle style and default mode
  useEffect(() => {
    loadMessagePreferences();
  }, [user?._id]);
  
  const loadMessagePreferences = async () => {
    if (!user?._id) return;
    try {
      // First check AsyncStorage for saved preference
      const savedMode = await AsyncStorage.getItem('message_mode');
      if (savedMode === 'sms' || savedMode === 'email') {
        setMessageMode(savedMode);
      }
      // Also load from API
      const prefs = await emailAPI.getPreferences(user._id);
      if (prefs.default_mode) setMessageMode(prefs.default_mode);
      if (prefs.toggle_style) setToggleStyle(prefs.toggle_style);
    } catch (error) {
      // Fallback to defaults if preferences don't exist
      console.log('Using default message preferences');
    }
  };
  
  const handleModeChange = async (mode: MessageModeType) => {
    triggerHaptic('medium');
    setMessageMode(mode);
    // Save mode preference to AsyncStorage so other screens can use it
    try {
      await AsyncStorage.setItem('message_mode', mode);
    } catch (e) {
      console.log('Error saving mode preference:', e);
    }
  };
  
  const handleInboxViewChange = async (view: 'my' | 'team') => {
    triggerHaptic('medium');
    setInboxView(view);
    if (view === 'team') {
      await loadTeamConversations();
    }
  };
  
  const loadTeamConversations = async () => {
    if (!user) return;
    setLoadingTeam(true);
    try {
      // Get user's teams/shared inboxes
      const teamsResponse = await fetch(
        `${Platform.OS === 'web' ? '' : (process.env.EXPO_PUBLIC_BACKEND_URL || '')}/api/admin/team/shared-inboxes?user_id=${user._id}`
      );
      const teamsData = await teamsResponse.json();
      
      // teamsData is an array directly (not wrapped in {inboxes: ...})
      const teams = Array.isArray(teamsData) ? teamsData : (teamsData.inboxes || []);
      
      if (teams.length > 0) {
        // Get conversations for all teams
        const allTeamConversations: any[] = [];
        for (const team of teams) {
          const teamId = team._id || team.id;
          try {
            const convResponse = await fetch(
              `${Platform.OS === 'web' ? '' : (process.env.EXPO_PUBLIC_BACKEND_URL || '')}/api/lead-sources/team-inbox/${teamId}?include_claimed=true`
            );
            const convData = await convResponse.json();
            if (convData.conversations) {
              allTeamConversations.push(...convData.conversations.map((c: any) => ({
                ...c,
                team_name: team.name,
              })));
            }
          } catch (e) {
            console.log(`No leads for team ${teamId}`);
          }
        }
        setTeamConversations(allTeamConversations);
      } else {
        setTeamConversations([]);
      }
    } catch (error) {
      console.error('Failed to load team conversations:', error);
      setTeamConversations([]);
    } finally {
      setLoadingTeam(false);
    }
  };
  
  useEffect(() => {
    loadConversations();
  }, [user]);
  
  const loadConversations = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      const data = await messagesAPI.getConversations(user._id);
      setConversations(data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    triggerHaptic('light');
    await loadConversations();
    setRefreshing(false);
  };

  // ============= BULK SELECTION FUNCTIONS =============
  
  const enterSelectionMode = (conversationId?: string) => {
    triggerHaptic('medium');
    setSelectionMode(true);
    if (conversationId) {
      setSelectedIds(new Set([conversationId]));
    }
  };

  const exitSelectionMode = () => {
    triggerHaptic('light');
    setSelectionMode(false);
    setSelectedIds(new Set());
  };

  const toggleSelection = (conversationId: string) => {
    triggerHaptic('selection');
    const newSelected = new Set(selectedIds);
    if (newSelected.has(conversationId)) {
      newSelected.delete(conversationId);
      if (newSelected.size === 0) {
        exitSelectionMode();
        return;
      }
    } else {
      newSelected.add(conversationId);
    }
    setSelectedIds(newSelected);
  };

  const selectAll = () => {
    triggerHaptic('medium');
    const allIds = filteredConversations.map(c => c._id);
    setSelectedIds(new Set(allIds));
  };

  const handleBulkAction = async (action: 'archive' | 'read' | 'unread' | 'delete') => {
    if (selectedIds.size === 0) return;
    triggerHaptic('medium');

    const ids = Array.from(selectedIds);
    
    if (action === 'delete') {
      Alert.alert(
        'Delete Conversations',
        `Are you sure you want to delete ${ids.length} conversation${ids.length > 1 ? 's' : ''}? This cannot be undone.`,
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Delete',
            style: 'destructive',
            onPress: async () => {
              setBulkActionLoading(true);
              try {
                await messagesAPI.bulkDelete(ids);
                await loadConversations();
                exitSelectionMode();
              } catch (error) {
                console.error('Bulk delete failed:', error);
                Alert.alert('Error', 'Failed to delete conversations');
              } finally {
                setBulkActionLoading(false);
              }
            },
          },
        ]
      );
      return;
    }

    setBulkActionLoading(true);
    try {
      switch (action) {
        case 'archive':
          await messagesAPI.bulkArchive(ids);
          break;
        case 'read':
          await messagesAPI.bulkMarkRead(ids);
          break;
        case 'unread':
          await messagesAPI.bulkMarkUnread(ids);
          break;
      }
      await loadConversations();
      exitSelectionMode();
    } catch (error) {
      console.error(`Bulk ${action} failed:`, error);
      Alert.alert('Error', `Failed to ${action} conversations`);
    } finally {
      setBulkActionLoading(false);
    }
  };

  // Acknowledge AI outcome
  const acknowledgeAiOutcome = async (conversationId: string, aiOutcome: string, conversation: any, e: any) => {
    e.stopPropagation();
    triggerHaptic('medium');
    if (!user) return;
    
    if (aiOutcome === 'appointment_set') {
      setAppointmentConversation(conversation);
      setShowAppointmentModal(true);
      return;
    }
    
    try {
      await messagesAPI.updateConversation(user._id, conversationId, {
        ai_outcome_acknowledged: true,
      });
      await loadConversations();
    } catch (error) {
      console.error('Failed to acknowledge AI outcome:', error);
    }
  };

  const handleAppointmentComplete = async (appointmentCreated: boolean) => {
    setShowAppointmentModal(false);
    
    if (!user || !appointmentConversation) return;
    
    try {
      await messagesAPI.updateConversation(user._id, appointmentConversation._id, {
        ai_outcome_acknowledged: true,
      });
      await loadConversations();
    } catch (error) {
      console.error('Failed to acknowledge appointment outcome:', error);
    }
    
    setAppointmentConversation(null);
  };

  const openNewMessage = async () => {
    triggerHaptic('light');
    setShowNewMessage(true);
    if (contacts.length === 0) {
      loadContacts();
    }
  };
  
  const loadContacts = async () => {
    if (!user) return;
    
    try {
      setLoadingContacts(true);
      const data = await contactsAPI.getAll(user._id);
      setContacts(data);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      setLoadingContacts(false);
    }
  };
  
  const startConversation = (contact: any) => {
    triggerHaptic('light');
    setShowNewMessage(false);
    setContactSearch('');
    router.push({
      pathname: `/thread/${contact._id}`,
      params: {
        contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
        contact_phone: contact.phone,
        contact_photo: contact.photo_thumbnail || contact.photo_url || '',
      }
    });
  };
  
  const startNewConversationWithNumber = (phoneNumber: string) => {
    triggerHaptic('light');
    setShowNewMessage(false);
    setContactSearch('');
    router.push({
      pathname: `/thread/new`,
      params: {
        contact_name: phoneNumber,
        contact_phone: phoneNumber,
        is_new: 'true',
      }
    });
  };
  
  const isPhoneNumber = /^[\d\s\-\+\(\)]+$/.test(contactSearch) && contactSearch.replace(/\D/g, '').length >= 3;
  
  const filteredContacts = contacts.filter(c => {
    const name = `${c.first_name} ${c.last_name || ''}`.toLowerCase();
    const phone = c.phone || '';
    const searchLower = contactSearch.toLowerCase();
    return name.includes(searchLower) || phone.includes(searchLower);
  });
  
  const filteredConversations = conversations
    .filter((conv) => {
      if (!conv) return false;
      const contactName = conv.contact?.name || '';
      const matchesSearch = !search || contactName.toLowerCase().includes(search.toLowerCase());
      
      if (filter === 'unread') return matchesSearch && (conv.unread || conv.needs_assistance);
      if (filter === 'ai') return matchesSearch && conv.ai_handled && conv.ai_outcome;
      if (filter === 'active') return matchesSearch && conv.status === 'active';
      if (filter === 'closed') return matchesSearch && conv.status === 'closed';
      return matchesSearch;
    })
    .sort((a, b) => {
      const aUnacked = a.ai_outcome && !a.ai_outcome_acknowledged ? 1 : 0;
      const bUnacked = b.ai_outcome && !b.ai_outcome_acknowledged ? 1 : 0;
      if (bUnacked !== aUnacked) return bUnacked - aUnacked;
      
      const aAiPriority = a.ai_outcome && !a.ai_outcome_acknowledged ? (a.ai_outcome_priority || 999) : 999;
      const bAiPriority = b.ai_outcome && !b.ai_outcome_acknowledged ? (b.ai_outcome_priority || 999) : 999;
      if (aAiPriority !== bAiPriority) return aAiPriority - bAiPriority;
      
      const aUrgent = a.unread || a.needs_assistance ? 1 : 0;
      const bUrgent = b.unread || b.needs_assistance ? 1 : 0;
      if (bUrgent !== aUrgent) return bUrgent - aUrgent;
      
      const aTime = new Date(a.last_message?.timestamp || a.last_message_at || 0).getTime();
      const bTime = new Date(b.last_message?.timestamp || b.last_message_at || 0).getTime();
      return bTime - aTime;
    });
  
  const formatTimestamp = (timestamp: string | Date | undefined) => {
    if (!timestamp) return '';
    
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    if (isNaN(date.getTime())) return '';
    
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    
    if (diffInHours < 24) {
      return format(date, 'h:mm a');
    } else if (diffInHours < 168) {
      return format(date, 'EEE');
    } else {
      return format(date, 'M/d/yy');
    }
  };

  // Quick action handlers
  const handleArchive = async (conversationId: string) => {
    try {
      const conversation = conversations.find(c => c._id === conversationId);
      if (conversation?.status === 'archived') {
        await messagesAPI.restoreConversation(conversationId);
      } else {
        await messagesAPI.archiveConversation(conversationId);
      }
      loadConversations();
    } catch (error) {
      console.error('Error archiving conversation:', error);
      Alert.alert('Error', 'Failed to archive conversation');
    }
  };

  const handleToggleRead = async (conversationId: string, isRead: boolean) => {
    try {
      if (isRead) {
        await messagesAPI.markAsUnread(conversationId);
      } else {
        await messagesAPI.markAsRead(conversationId);
      }
      loadConversations();
    } catch (error) {
      console.error('Error toggling read status:', error);
      Alert.alert('Error', 'Failed to update conversation');
    }
  };

  const handleQuickCall = async (conversationId: string) => {
    const conversation = conversations.find(c => c._id === conversationId);
    const phone = conversation?.contact?.phone;
    if (phone) {
      const phoneUrl = Platform.OS === 'ios' ? `telprompt:${phone}` : `tel:${phone}`;
      Linking.openURL(phoneUrl).catch(() => {
        Alert.alert('Error', 'Unable to make phone call');
      });
    } else {
      Alert.alert('No Phone Number', 'This contact does not have a phone number');
    }
  };

  const handleDeleteConversation = async (conversationId: string) => {
    try {
      await messagesAPI.deleteConversation(conversationId);
      loadConversations();
    } catch (error) {
      console.error('Error deleting conversation:', error);
      Alert.alert('Error', 'Failed to delete conversation');
    }
  };

  const handleFilterPress = (f: typeof filter) => {
    triggerHaptic('selection');
    setFilter(f);
  };
  
  const renderConversation = ({ item }: { item: any }) => {
    const contactName = item.contact?.name || 'Unknown';
    const contactPhoto = item.contact?.photo_thumbnail || item.contact?.photo_url || null;
    const contactInitials = contactName
      .split(' ')
      .map((n: string) => n[0] || '')
      .join('')
      .toUpperCase() || '?';
    
    const isUrgent = item.unread || item.needs_assistance;
    const aiOutcome = item.ai_outcome ? AI_OUTCOME_CONFIG[item.ai_outcome] : null;
    const hasAiOutcome = item.ai_handled && aiOutcome;
    const isAcknowledged = item.ai_outcome_acknowledged;
    const isRead = !item.unread;
    const isArchived = item.status === 'archived';
    const isSelected = selectedIds.has(item._id);

    const handlePress = () => {
      triggerHaptic('light');
      if (selectionMode) {
        toggleSelection(item._id);
      } else {
        router.push({
          pathname: `/thread/${item._id}`,
          params: {
            contact_name: contactName,
            contact_phone: item.contact?.phone || '',
          }
        });
      }
    };

    const handleLongPress = () => {
      if (!selectionMode) {
        enterSelectionMode(item._id);
      }
    };
    
    const conversationContent = (
      <TouchableOpacity
        style={[
          styles.conversationItem,
          item.status === 'closed' && styles.conversationItemClosed,
          hasAiOutcome && !isAcknowledged && styles.conversationItemAI,
          isSelected && styles.conversationItemSelected,
        ]}
        onPress={handlePress}
        onLongPress={handleLongPress}
        delayLongPress={500}
        activeOpacity={0.7}
        data-testid={`conversation-item-${item._id}`}
      >
        {/* Selection checkbox */}
        {selectionMode && (
          <View style={styles.checkboxContainer}>
            <View style={[styles.checkbox, isSelected && styles.checkboxSelected]}>
              {isSelected && (
                <Ionicons name="checkmark" size={14} color="#FFF" />
              )}
            </View>
          </View>
        )}
        
        <View style={styles.avatarContainer}>
          {hasAiOutcome && (
            <View style={[
              styles.aiRing, 
              { borderColor: aiOutcome.color },
              isAcknowledged && styles.aiRingAcknowledged,
            ]} />
          )}
          {contactPhoto ? (
            <Image 
              source={{ uri: contactPhoto }} 
              style={[
                styles.avatarPhoto,
                hasAiOutcome && styles.avatarWithRing,
              ]} 
            />
          ) : (
            <View style={[
              styles.avatar,
              hasAiOutcome && styles.avatarWithRing,
              isUrgent && !hasAiOutcome && styles.avatarUrgent,
            ]}>
              <Text style={styles.avatarText}>
                {contactInitials}
              </Text>
            </View>
          )}
          {item.status === 'closed' && (
            <View style={styles.closedBadge}>
              <Ionicons name="checkmark" size={10} color="#FFF" />
            </View>
          )}
          {hasAiOutcome && !isAcknowledged && (
            <View style={[styles.aiOutcomeBadge, { backgroundColor: aiOutcome.color }]}>
              <Ionicons name={aiOutcome.icon as any} size={10} color="#FFF" />
            </View>
          )}
          {hasAiOutcome && isAcknowledged && (
            <View style={[styles.aiOutcomeBadge, styles.aiOutcomeBadgeAcknowledged]}>
              <Ionicons name="checkmark" size={10} color={COLORS.textSecondary} />
            </View>
          )}
          {!hasAiOutcome && isUrgent && (
            <View style={styles.unreadBubble}>
              <Text style={styles.unreadBubbleText}>
                {item.unread_count > 9 ? '9+' : item.unread_count || ''}
              </Text>
            </View>
          )}
        </View>
      
        <View style={styles.conversationContent}>
          <View style={styles.conversationHeader}>
            <View style={styles.nameRow}>
              <Text
                style={[
                  styles.contactName,
                  isUrgent && styles.contactNameUnread,
                  item.status === 'closed' && styles.contactNameClosed,
                ]}
                numberOfLines={1}
              >
                {contactName}
              </Text>
              {hasAiOutcome && !isAcknowledged && (
                <View style={[styles.aiOutcomeTag, { backgroundColor: aiOutcome.bgColor }]}>
                  <Ionicons name={aiOutcome.icon as any} size={9} color={aiOutcome.color} />
                  <Text style={[styles.aiOutcomeTagText, { color: aiOutcome.color }]}>
                    {aiOutcome.label}
                  </Text>
                </View>
              )}
              {hasAiOutcome && isAcknowledged && (
                <View style={styles.aiOutcomeTagAcknowledged}>
                  <Ionicons name="checkmark-circle" size={11} color={COLORS.textSecondary} />
                </View>
              )}
              {!hasAiOutcome && item.ai_enabled && item.ai_mode !== 'draft_only' && item.status === 'active' && (
                <View style={styles.mvpBadge}>
                  <Ionicons name="sparkles" size={9} color={COLORS.success} />
                </View>
              )}
            </View>
            <Text style={[
              styles.timestamp,
              isUrgent && styles.timestampUnread,
              hasAiOutcome && !isAcknowledged && { color: aiOutcome.color },
            ]}>
              {item.last_message?.timestamp ? formatTimestamp(item.last_message.timestamp) : ''}
            </Text>
          </View>
          
          <Text
            style={[
              styles.messageText,
              isUrgent && styles.messageTextUnread,
              item.status === 'closed' && styles.messageTextClosed,
            ]}
            numberOfLines={1}
          >
            {item.last_message?.sender === 'user' ? 'You: ' : ''}
            {item.last_message?.content || 'No messages yet'}
          </Text>
        </View>
        
        {hasAiOutcome && !isAcknowledged && (
          <TouchableOpacity
            style={[styles.doneButton, { borderColor: aiOutcome.color }]}
            onPress={(e) => acknowledgeAiOutcome(item._id, item.ai_outcome, item, e)}
            activeOpacity={0.7}
            data-testid={`acknowledge-btn-${item._id}`}
          >
            <Ionicons name="checkmark" size={16} color={aiOutcome.color} />
          </TouchableOpacity>
        )}
      </TouchableOpacity>
    );

    if (Platform.OS !== 'web' && !selectionMode) {
      return (
        <SwipeableConversationItem
          conversationId={item._id}
          isRead={isRead}
          isArchived={isArchived}
          onArchive={handleArchive}
          onToggleRead={handleToggleRead}
          onCall={handleQuickCall}
          onDelete={handleDeleteConversation}
        >
          {conversationContent}
        </SwipeableConversationItem>
      );
    }

    return conversationContent;
  };

  // Render team conversation item
  const renderTeamConversation = ({ item }: { item: any }) => {
    const contactName = item.contact_name || 'Unknown';
    const contactPhoto = item.contact_photo || null;
    const contactInitials = contactName
      .split(' ')
      .map((n: string) => n[0] || '')
      .join('')
      .toUpperCase() || '?';
    
    const isClaimed = item.claimed;
    const isNew = item.status === 'new';

    const handlePress = () => {
      triggerHaptic('light');
      router.push({
        pathname: `/thread/${item.id}`,
        params: {
          contact_name: contactName,
          contact_phone: item.contact_phone || '',
        }
      });
    };

    const handleClaim = async () => {
      triggerHaptic('medium');
      if (!user) return;
      
      try {
        const response = await fetch(
          `${Platform.OS === 'web' ? '' : (process.env.EXPO_PUBLIC_BACKEND_URL || '')}/api/lead-sources/claim/${item.id}?user_id=${user._id}`,
          { method: 'POST' }
        );
        const data = await response.json();
        if (data.success) {
          Alert.alert('Claimed', 'You have claimed this lead');
          loadTeamConversations();
        } else {
          Alert.alert('Error', data.detail || 'Could not claim lead');
        }
      } catch (error) {
        console.error('Error claiming lead:', error);
        Alert.alert('Error', 'Failed to claim lead');
      }
    };
    
    return (
      <TouchableOpacity
        style={[
          styles.conversationItem,
          !isClaimed && styles.teamConversationUnclaimed,
        ]}
        onPress={handlePress}
        activeOpacity={0.7}
        data-testid={`team-conversation-${item.id}`}
      >
        <View style={styles.avatarContainer}>
          {contactPhoto ? (
            <Image 
              source={{ uri: contactPhoto }} 
              style={[
                styles.avatarPhoto,
                !isClaimed && { borderWidth: 2, borderColor: '#FF9500' },
              ]} 
            />
          ) : (
            <View style={[
              styles.avatar,
              !isClaimed && { backgroundColor: '#FF9500' },
            ]}>
              <Text style={styles.avatarText}>
                {contactInitials}
              </Text>
            </View>
          )}
          {isNew && !isClaimed && (
            <View style={styles.newLeadBadge}>
              <Ionicons name="flash" size={10} color="#FFF" />
            </View>
          )}
        </View>
      
        <View style={styles.conversationContent}>
          <View style={styles.conversationHeader}>
            <View style={styles.nameRow}>
              <Text style={[styles.contactName, { color: colors.textPrimary }]} numberOfLines={1}>
                {contactName}
              </Text>
              {item.lead_source_name && (
                <View style={styles.leadSourceTag}>
                  <Text style={styles.leadSourceTagText}>{item.lead_source_name}</Text>
                </View>
              )}
            </View>
            <Text style={[styles.timestamp, { color: colors.textSecondary }]}>
              {item.created_at ? formatTimestamp(item.created_at) : ''}
            </Text>
          </View>
          
          <View style={styles.teamConversationMeta}>
            {item.team_name && (
              <View style={styles.teamBadge}>
                <Ionicons name="people" size={10} color="#8E8E93" />
                <Text style={styles.teamBadgeText}>{item.team_name}</Text>
              </View>
            )}
            {isClaimed ? (
              <View style={styles.claimedBadge}>
                <Ionicons name="checkmark-circle" size={12} color="#34C759" />
                <Text style={styles.claimedBadgeText}>
                  Claimed{item.claimed_by === user?._id ? ' by you' : ''}
                </Text>
              </View>
            ) : (
              <View style={styles.unclaimedBadge}>
                <Ionicons name="flash" size={12} color="#FF9500" />
                <Text style={styles.unclaimedBadgeText}>Jump Ball</Text>
              </View>
            )}
          </View>
        </View>
        
        {!isClaimed && (
          <TouchableOpacity
            style={styles.claimButton}
            onPress={handleClaim}
            activeOpacity={0.7}
            data-testid={`claim-btn-${item.id}`}
          >
            <Ionicons name="hand-right" size={18} color="#FF9500" />
          </TouchableOpacity>
        )}
      </TouchableOpacity>
    );
  };

  // Render header with glassmorphism on native
  const renderHeader = () => {
    if (selectionMode) {
      return (
        <View style={[styles.selectionHeader, { backgroundColor: colors.surface }]}>
          <TouchableOpacity onPress={exitSelectionMode} style={styles.headerIconButton} data-testid="selection-cancel-btn">
            <Ionicons name="close" size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={[styles.selectionCount, { color: colors.textPrimary }]} data-testid="selection-count">
            {selectedIds.size} selected
          </Text>
          <TouchableOpacity onPress={selectAll} style={styles.selectAllButton} data-testid="select-all-btn">
            <Text style={styles.selectAllText}>Select All</Text>
          </TouchableOpacity>
        </View>
      );
    }

    const headerContent = (
      <View style={styles.headerInner}>
        <View style={styles.headerLeft}>
          <Text style={[styles.title, { color: colors.textPrimary }]}>
            {messageMode === 'sms' ? 'Inbox' : 'Email'}
          </Text>
          <View style={styles.modeBadge}>
            <Ionicons 
              name={messageMode === 'sms' ? 'chatbubbles' : 'mail'} 
              size={12} 
              color={messageMode === 'email' ? '#007AFF' : '#8E8E93'} 
            />
          </View>
        </View>
        <View style={styles.headerButtons}>
          <NotificationBell />
          <WebIconButton 
            onPress={() => { triggerHaptic('light'); router.push('/search'); }} 
            iconName="search"
            iconSize={22}
            iconColor={colors.accent}
            testID="inbox-search-btn"
            style={styles.headerIconButton}
          />
          <WebIconButton 
            onPress={openNewMessage} 
            iconName="create-outline"
            iconSize={24}
            iconColor={colors.accent}
            testID="compose-btn"
            style={styles.composeButton}
          />
        </View>
      </View>
    );

    if (Platform.OS !== 'web') {
      return (
        <BlurView intensity={80} tint={messageMode === 'email' ? 'light' : 'dark'} style={[styles.header, { backgroundColor: colors.background }]}>
          {headerContent}
        </BlurView>
      );
    }

    return <View style={[styles.header, styles.headerWeb, { backgroundColor: colors.background }]}>{headerContent}</View>;
  };
  
  // Check if user has restricted access (pending status)
  const isPending = user?.status === 'pending';
  
  // Show restricted access screen for pending users
  if (isPending) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={[styles.header, styles.headerWeb]}>
          <View style={styles.headerInner}>
            <Text style={styles.title}>Inbox</Text>
          </View>
        </View>
        <View style={styles.restrictedContainer}>
          <View style={styles.restrictedIcon}>
            <Ionicons name="lock-closed" size={48} color="#FF9500" />
          </View>
          <Text style={styles.restrictedTitle}>Access Pending</Text>
          <Text style={styles.restrictedText}>
            Your account is being reviewed by an admin. You'll have full access to messaging once your account is configured.
          </Text>
          <View style={styles.restrictedActions}>
            <TouchableOpacity 
              style={styles.restrictedButton}
              onPress={() => router.push('/onboarding')}
            >
              <Text style={styles.restrictedButtonText}>Complete Your Profile</Text>
              <Ionicons name="arrow-forward" size={18} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }
  
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      {renderHeader()}
      
      {/* Mode Indicator Banner */}
      {messageMode === 'email' && (
        <View style={styles.modeIndicatorBanner}>
          <Ionicons name="mail" size={16} color="#007AFF" />
          <Text style={styles.modeIndicatorText}>Email Mode - Sending branded HTML emails</Text>
        </View>
      )}
      
      {/* Premium Search Bar */}
      <View style={[styles.searchContainer, { backgroundColor: colors.background }]}>
        <View style={[styles.searchBar, { backgroundColor: colors.surface }]}>
          <Ionicons name="search" size={18} color={colors.textSecondary} />
          <TextInput
            style={[styles.searchInput, { color: colors.textPrimary }]}
            placeholder="Search conversations"
            placeholderTextColor={colors.textSecondary}
            value={search}
            onChangeText={setSearch}
          />
          {search.length > 0 && (
            <TouchableOpacity onPress={() => setSearch('')}>
              <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
      </View>
      
      {/* Inbox View Toggle (My/Team) */}
      <View style={[styles.inboxToggleContainer, { backgroundColor: colors.background }]}>
        <View style={[styles.inboxToggle, { backgroundColor: colors.surface }]}>
          <Pressable
            style={[
              styles.inboxToggleOption,
              inboxView === 'my' && styles.inboxToggleOptionActive,
            ]}
            onPress={() => handleInboxViewChange('my')}
            data-testid="my-inbox-toggle"
          >
            <Ionicons name="person" size={14} color={inboxView === 'my' ? '#FFF' : colors.textSecondary} />
            <Text style={[styles.inboxToggleText, inboxView === 'my' && styles.inboxToggleTextActive]}>
              My Inbox
            </Text>
          </Pressable>
          <Pressable
            style={[
              styles.inboxToggleOption,
              inboxView === 'team' && styles.inboxToggleOptionActive,
            ]}
            onPress={() => handleInboxViewChange('team')}
            data-testid="team-inbox-toggle"
          >
            <Ionicons name="people" size={14} color={inboxView === 'team' ? '#FFF' : colors.textSecondary} />
            <Text style={[styles.inboxToggleText, inboxView === 'team' && styles.inboxToggleTextActive]}>
              Team Inbox
            </Text>
          </Pressable>
        </View>
      </View>
      
      {/* Luxury Pill Filter Buttons - Scrollable */}
      <ScrollView 
        horizontal 
        showsHorizontalScrollIndicator={false}
        style={styles.filterScroll}
        contentContainerStyle={styles.filterContainer}
      >
        {(['active', 'unread', 'ai', 'closed', 'all'] as const).map((f) => (
          <TouchableOpacity
            key={f}
            style={[
              styles.filterButton,
              filter === f && styles.filterButtonActive,
              f === 'ai' && filter === f && styles.filterButtonAI,
            ]}
            onPress={() => handleFilterPress(f)}
            activeOpacity={0.7}
          >
            {f === 'ai' ? (
              <Image 
                source={require('../../assets/images/imos-logo-white-v3.png')}
                style={styles.imosLogoFilter}
                resizeMode="contain"
              />
            ) : (
              <Text
                style={[
                  styles.filterText,
                  filter === f && styles.filterTextActive,
                ]}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </Text>
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>
      
      {/* Conversation List */}
      {loading || (inboxView === 'team' && loadingTeam) ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.accent} />
        </View>
      ) : inboxView === 'team' ? (
        <FlatList
          data={teamConversations}
          renderItem={renderTeamConversation}
          keyExtractor={(item) => item.id || item._id}
          contentContainerStyle={styles.listContent}
          style={styles.listContainer}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => loadTeamConversations()}
              tintColor={COLORS.accent}
            />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIconContainer}>
                <Ionicons name="people" size={48} color={COLORS.accent} />
              </View>
              <Text style={styles.emptyTitle}>No team leads yet</Text>
              <Text style={styles.emptySubtext}>Leads from your team's lead sources will appear here</Text>
            </View>
          )}
        />
      ) : (
        <FlatList
          data={filteredConversations}
          renderItem={renderConversation}
          keyExtractor={(item) => item._id || item.id}
          contentContainerStyle={styles.listContent}
          style={styles.listContainer}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={COLORS.accent}
            />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIconContainer}>
                <Ionicons name="chatbubbles" size={48} color={COLORS.accent} />
              </View>
              <Text style={styles.emptyTitle}>No conversations yet</Text>
              <Text style={styles.emptySubtext}>Start connecting with your contacts</Text>
              <TouchableOpacity style={styles.emptyButton} onPress={openNewMessage} activeOpacity={0.8}>
                <Ionicons name="add" size={20} color="#FFF" />
                <Text style={styles.emptyButtonText}>New Message</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
      
      {/* New Message Modal */}
      <Modal
        visible={showNewMessage}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ flex: 1 }}
        >
          <SafeAreaView style={[styles.modalContainer, { backgroundColor: colors.background }]}>
            <View style={[styles.modalHeader, { borderBottomColor: colors.border }]}>
              <TouchableOpacity onPress={() => {
                setShowNewMessage(false);
                setContactSearch('');
              }}>
                <Text style={[styles.modalCancel, { color: colors.accent }]}>Cancel</Text>
              </TouchableOpacity>
              <Text style={[styles.modalTitle, { color: colors.textPrimary }]}>New Message</Text>
              <View style={{ width: 60 }} />
            </View>
            
            <View style={styles.modalSearchContainer}>
              <View style={[styles.modalSearchBar, { backgroundColor: colors.surface, borderColor: colors.border }]}>
                <Ionicons name="search" size={18} color={colors.textSecondary} />
                <TextInput
                  style={[styles.modalSearchInput, { color: colors.textPrimary }]}
                  placeholder="Search or enter phone number"
                  placeholderTextColor={colors.textSecondary}
                  value={contactSearch}
                  onChangeText={setContactSearch}
                  autoFocus
                  keyboardType="default"
                />
                {contactSearch.length > 0 && (
                  <TouchableOpacity onPress={() => setContactSearch('')}>
                    <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
                  </TouchableOpacity>
                )}
              </View>
            </View>
            
            {loadingContacts ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color={COLORS.accent} />
              </View>
            ) : (
              <FlatList
                data={filteredContacts}
                keyExtractor={(item) => item._id}
                keyboardShouldPersistTaps="handled"
                ListHeaderComponent={() => (
                  isPhoneNumber ? (
                  <TouchableOpacity 
                    style={[styles.phoneNumberOption, { backgroundColor: colors.elevated }]}
                    onPress={() => startNewConversationWithNumber(contactSearch)}
                    activeOpacity={0.7}
                  >
                    <View style={[styles.phoneNumberIcon, { backgroundColor: `${colors.success}20` }]}>
                      <Ionicons name="keypad" size={22} color={colors.success} />
                    </View>
                    <View style={styles.phoneNumberInfo}>
                      <Text style={[styles.phoneNumberLabel, { color: colors.textSecondary }]}>Send to</Text>
                      <Text style={[styles.phoneNumberValue, { color: colors.textPrimary }]}>{contactSearch}</Text>
                    </View>
                    <Ionicons name="arrow-forward-circle" size={26} color={colors.success} />
                  </TouchableOpacity>
                ) : null
              )}
              renderItem={({ item }) => (
                <TouchableOpacity 
                  style={styles.contactItem}
                  onPress={() => startConversation(item)}
                  activeOpacity={0.7}
                >
                  {(item.photo_thumbnail || item.photo_url || item.photo) ? (
                    <Image source={{ uri: item.photo_thumbnail || item.photo_url || item.photo }} style={styles.contactAvatarPhoto} />
                  ) : (
                    <View style={[styles.contactAvatar, { backgroundColor: colors.elevated }]}>
                      <Text style={[styles.contactAvatarText, { color: colors.textPrimary }]}>
                        {item.first_name?.[0]}{item.last_name?.[0] || ''}
                      </Text>
                    </View>
                  )}
                  <View style={styles.contactInfo}>
                    <Text style={[styles.contactNameModal, { color: colors.textPrimary }]}>
                      {item.first_name} {item.last_name || ''}
                    </Text>
                    <Text style={[styles.contactPhone, { color: colors.textSecondary }]}>{item.phone}</Text>
                  </View>
                  <View style={styles.contactAction}>
                    <Ionicons name="chatbubble" size={20} color={colors.accent} />
                  </View>
                </TouchableOpacity>
              )}
              ItemSeparatorComponent={() => <View style={[styles.modalSeparator, { backgroundColor: colors.border }]} />}
              ListEmptyComponent={() => (
                <View style={styles.emptyContainer}>
                  <View style={[styles.emptyIconContainerSmall, { backgroundColor: colors.elevated }]}>
                    <Ionicons name="people" size={32} color={colors.textTertiary} />
                  </View>
                  <Text style={[styles.emptyTitle, { color: colors.textPrimary }]}>
                    {contactSearch ? 'No contacts found' : 'No contacts yet'}
                  </Text>
                  <Text style={[styles.emptySubtext, { color: colors.textSecondary }]}>
                    {contactSearch ? 'Try a different search' : 'Add contacts to start messaging'}
                  </Text>
                </View>
              )}
            />
          )}
        </SafeAreaView>
      </KeyboardAvoidingView>
      </Modal>

      {/* Bulk Action Bar */}
      {selectionMode && selectedIds.size > 0 && (
        <View style={styles.bulkActionBar}>
          {bulkActionLoading ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <>
              <TouchableOpacity 
                style={styles.bulkActionButton} 
                onPress={() => handleBulkAction('archive')}
                activeOpacity={0.7}
                data-testid="bulk-archive-btn"
              >
                <View style={styles.bulkActionIcon}>
                  <Ionicons name="archive" size={20} color="#FFF" />
                </View>
                <Text style={styles.bulkActionText}>Archive</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.bulkActionButton} 
                onPress={() => handleBulkAction('read')}
                activeOpacity={0.7}
                data-testid="bulk-read-btn"
              >
                <View style={styles.bulkActionIcon}>
                  <Ionicons name="mail-open" size={20} color="#FFF" />
                </View>
                <Text style={styles.bulkActionText}>Read</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.bulkActionButton} 
                onPress={() => handleBulkAction('unread')}
                activeOpacity={0.7}
                data-testid="bulk-unread-btn"
              >
                <View style={styles.bulkActionIcon}>
                  <Ionicons name="mail-unread" size={20} color="#FFF" />
                </View>
                <Text style={styles.bulkActionText}>Unread</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.bulkActionButton} 
                onPress={() => handleBulkAction('delete')}
                activeOpacity={0.7}
                data-testid="bulk-delete-btn"
              >
                <View style={[styles.bulkActionIcon, styles.bulkActionIconDanger]}>
                  <Ionicons name="trash" size={20} color={COLORS.danger} />
                </View>
                <Text style={[styles.bulkActionText, styles.bulkActionTextDanger]}>Delete</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      )}

      {/* Appointment Modal */}
      {appointmentConversation && (
        <AppointmentModal
          visible={showAppointmentModal}
          onClose={() => {
            setShowAppointmentModal(false);
            setAppointmentConversation(null);
          }}
          onComplete={handleAppointmentComplete}
          conversationId={appointmentConversation._id}
          contactName={appointmentConversation.contact?.name || 'Unknown'}
          contactPhone={appointmentConversation.contact?.phone || ''}
          userId={user?._id || ''}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS_DARK.background,
  },
  
  // Header - Luxury Glassmorphic
  header: {
    borderBottomWidth: 1,
    borderBottomColor: COLORS_DARK.border,
  },
  headerWeb: {
    backgroundColor: 'rgba(0, 0, 0, 0.9)',
  },
  headerInner: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  modeBadge: {
    backgroundColor: 'rgba(142, 142, 147, 0.2)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
  },
  modeIndicatorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF15',
    paddingVertical: 8,
    paddingHorizontal: 16,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#007AFF30',
  },
  modeIndicatorText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#007AFF',
  },
  headerButtons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  headerIconButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 20,
  },
  composeButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 20,
    backgroundColor: `${COLORS_DARK.accent}15`,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS_DARK.textPrimary,
    letterSpacing: -0.4,
  },
  
  // Selection Header
  selectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: COLORS_DARK.surface,
    borderBottomWidth: 1,
    borderBottomColor: COLORS_DARK.border,
  },
  selectionCount: {
    fontSize: 17,
    fontWeight: '600',
    color: COLORS_DARK.textPrimary,
    letterSpacing: -0.2,
  },
  selectAllButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  selectAllText: {
    fontSize: 15,
    color: COLORS.accent,
    fontWeight: '600',
  },
  
  // Premium Search Bar
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderRadius: 10,
    paddingHorizontal: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    height: 38,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    color: COLORS.textPrimary,
    letterSpacing: -0.1,
    paddingVertical: 0,
  },
  
  // Luxury Pill Filters
  filterScroll: {
    marginBottom: 4,
    flexGrow: 0,
    flexShrink: 0,
    maxHeight: 36,
  },
  filterContainer: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    gap: 6,
    alignItems: 'center',
  },
  filterButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    backgroundColor: COLORS.surface,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
    height: 30,
  },
  filterButtonActive: {
    backgroundColor: COLORS.accent,
    borderColor: COLORS.accent,
  },
  filterButtonAI: {
    backgroundColor: COLORS.success,
    borderColor: COLORS.success,
  },
  filterText: {
    color: COLORS.textSecondary,
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  filterTextActive: {
    color: '#FFF',
  },
  imosLogoFilter: {
    width: 52,
    height: 20,
  },
  
  // List
  listContainer: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 20,
    paddingHorizontal: 12,
    paddingTop: 8,
    flexGrow: 1,
    gap: 8,
  },
  separator: {
    height: 0,
  },
  
  // Conversation Item - Card Style matching More page
  conversationItem: {
    flexDirection: 'row',
    paddingVertical: 14,
    paddingHorizontal: 14,
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  conversationItemClosed: {
    opacity: 0.5,
  },
  conversationItemAI: {
    borderColor: `${COLORS_DARK.success}30`,
    borderLeftWidth: 3,
    borderLeftColor: COLORS_DARK.success,
  },
  conversationItemSelected: {
    backgroundColor: `${COLORS_DARK.accent}15`,
    borderColor: COLORS_DARK.accent,
  },
  
  // Checkbox
  checkboxContainer: {
    marginRight: 14,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: COLORS.textSecondary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxSelected: {
    backgroundColor: COLORS.accent,
    borderColor: COLORS.accent,
  },
  
  // Avatar - Premium Style
  avatarContainer: {
    position: 'relative',
    marginRight: 12,
    width: 46,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
  },
  aiRing: {
    position: 'absolute',
    width: 46,
    height: 46,
    borderRadius: 23,
    borderWidth: 2,
    backgroundColor: 'transparent',
  },
  aiRingAcknowledged: {
    opacity: 0.25,
  },
  avatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: COLORS.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarPhoto: {
    width: 54,
    height: 54,
    borderRadius: 27,
  },
  avatarWithRing: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: 2,
    borderColor: COLORS.background,
  },
  avatarUrgent: {
    backgroundColor: COLORS.accent,
  },
  avatarText: {
    color: '#FFF',
    fontSize: 24,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  
  // Badges
  closedBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: COLORS.textSecondary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: COLORS.background,
  },
  unreadBubble: {
    position: 'absolute',
    top: -2,
    right: -2,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: COLORS.accent,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 5,
    borderWidth: 2,
    borderColor: COLORS.background,
  },
  unreadBubbleText: {
    color: '#FFF',
    fontSize: 10,
    fontWeight: '700',
  },
  aiOutcomeBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: COLORS.background,
  },
  aiOutcomeBadgeAcknowledged: {
    backgroundColor: COLORS.elevated,
  },
  
  // Conversation Content
  conversationContent: {
    flex: 1,
    minWidth: 0, // Important for text truncation
  },
  conversationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 4,
  },
  nameRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'nowrap',
    marginRight: 8,
    minWidth: 0, // Important for text truncation
  },
  contactName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
    letterSpacing: -0.2,
    flexShrink: 1,
    minWidth: 0, // Allow shrinking
  },
  contactNameUnread: {
    fontWeight: '700',
  },
  contactNameClosed: {
    color: COLORS.textSecondary,
  },
  
  // Tags
  aiOutcomeTag: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    gap: 2,
    marginLeft: 6,
    flexShrink: 0, // Don't shrink the tag
  },
  aiOutcomeTagText: {
    fontSize: 8,
    fontWeight: '700',
    letterSpacing: 0.2,
    textTransform: 'uppercase',
  },
  aiOutcomeTagAcknowledged: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mvpBadge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: `${COLORS.success}20`,
    alignItems: 'center',
    justifyContent: 'center',
  },
  
  // Timestamp & Message
  timestamp: {
    fontSize: 12,
    color: COLORS.textSecondary,
    fontWeight: '500',
    flexShrink: 0,
    marginLeft: 4,
  },
  timestampUnread: {
    color: COLORS.accent,
    fontWeight: '600',
  },
  messageText: {
    fontSize: 14,
    color: COLORS.textSecondary,
    letterSpacing: -0.1,
  },
  messageTextUnread: {
    fontWeight: '500',
    color: COLORS.textPrimary,
  },
  messageTextClosed: {
    color: COLORS.textTertiary,
  },
  
  // Done Button
  doneButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    marginLeft: 10,
  },
  
  // Bulk Action Bar - Premium Style
  bulkActionBar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  bulkActionButton: {
    alignItems: 'center',
    gap: 6,
  },
  bulkActionIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.elevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bulkActionIconDanger: {
    backgroundColor: `${COLORS.danger}20`,
  },
  bulkActionText: {
    fontSize: 11,
    color: COLORS.textSecondary,
    fontWeight: '600',
  },
  bulkActionTextDanger: {
    color: COLORS.danger,
  },
  
  // Empty State - Premium
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 40,
  },
  emptyIconContainer: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: `${COLORS.accent}15`,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  emptyIconContainerSmall: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: COLORS.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 8,
    letterSpacing: -0.3,
  },
  emptySubtext: {
    fontSize: 15,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  emptyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.accent,
    borderRadius: 25,
    paddingVertical: 14,
    paddingHorizontal: 28,
    marginTop: 28,
    gap: 8,
  },
  emptyButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    letterSpacing: -0.1,
  },
  
  // Modal - Premium Style
  modalContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  modalCancel: {
    fontSize: 17,
    color: COLORS.accent,
    fontWeight: '500',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: COLORS.textPrimary,
    letterSpacing: -0.2,
  },
  modalSearchContainer: {
    paddingHorizontal: 20,
    paddingVertical: 14,
  },
  modalSearchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    gap: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  modalSearchInput: {
    flex: 1,
    paddingVertical: 12,
    fontSize: 16,
    color: COLORS.textPrimary,
  },
  modalSeparator: {
    height: 1,
    backgroundColor: COLORS.border,
    marginLeft: 76,
  },
  
  // Contact Item
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 20,
  },
  contactAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.elevated,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  contactAvatarPhoto: {
    width: 44,
    height: 44,
    borderRadius: 22,
    marginRight: 14,
  },
  contactAvatarText: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  contactInfo: {
    flex: 1,
  },
  contactNameModal: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
    letterSpacing: -0.2,
  },
  contactPhone: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  contactAction: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: `${COLORS.accent}15`,
    alignItems: 'center',
    justifyContent: 'center',
  },
  
  // Phone Number Option
  phoneNumberOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 20,
    backgroundColor: `${COLORS.success}08`,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  phoneNumberIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: `${COLORS.success}20`,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  phoneNumberInfo: {
    flex: 1,
  },
  phoneNumberLabel: {
    fontSize: 12,
    color: COLORS.textSecondary,
    fontWeight: '500',
    letterSpacing: 0.2,
  },
  phoneNumberValue: {
    fontSize: 17,
    fontWeight: '600',
    color: COLORS.success,
    letterSpacing: -0.2,
  },
  
  // Restricted Access
  restrictedContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  restrictedIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#FF950020',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  restrictedTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 12,
  },
  restrictedText: {
    fontSize: 16,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 32,
  },
  restrictedActions: {
    width: '100%',
  },
  restrictedButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF20',
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 12,
    gap: 8,
  },
  restrictedButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  
  // Inbox Toggle (My/Team)
  inboxToggleContainer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  inboxToggle: {
    flexDirection: 'row',
    borderRadius: 10,
    padding: 4,
  },
  inboxToggleOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    gap: 6,
  },
  inboxToggleOptionActive: {
    backgroundColor: COLORS_DARK.accent,
  },
  inboxToggleText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS_DARK.textSecondary,
  },
  inboxToggleTextActive: {
    color: '#FFF',
  },
  
  // Team Conversation Styles
  teamConversationUnclaimed: {
    backgroundColor: `${COLORS_DARK.warning}08`,
  },
  newLeadBadge: {
    position: 'absolute',
    top: -2,
    right: -2,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#FF9500',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: COLORS_DARK.background,
  },
  leadSourceTag: {
    backgroundColor: '#5856D620',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: 6,
  },
  leadSourceTagText: {
    fontSize: 9,
    fontWeight: '600',
    color: '#5856D6',
    textTransform: 'uppercase',
  },
  teamConversationMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 4,
  },
  teamBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  teamBadgeText: {
    fontSize: 11,
    color: COLORS_DARK.textSecondary,
  },
  claimedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#34C75915',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  claimedBadgeText: {
    fontSize: 10,
    fontWeight: '500',
    color: '#34C759',
  },
  unclaimedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#FF950020',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  unclaimedBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#FF9500',
  },
  claimButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#FF950020',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 10,
  },
});
