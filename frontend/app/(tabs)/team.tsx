import React, {
  useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import VoiceInput from '../../components/VoiceInput';
import { useToast } from '../../components/common/Toast';
import { showAlert } from '../../services/alert';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { FS } from '../../constants/typography';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

interface Channel {
  id: string;
  name: string;
  description?: string;
  channel_type: 'org' | 'store' | 'custom' | 'dm';
  member_count: number;
  avatar?: string;
  last_message?: {
    content: string;
    sender_name: string;
    created_at: string;
  };
  unread_count: number;
  last_message_at?: string;
}

interface Message {
  id: string;
  sender_id: string;
  sender_name: string;
  sender_photo?: string;
  content: string;
  mentions: string[];
  is_broadcast: boolean;
  created_at: string;
}

interface Member {
  id: string;
  name: string;
  email?: string;
  role: string;
  photo_url?: string;
}

export default function TeamChatScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  
  // State
  const { showToast } = useToast();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<Channel | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  
  // Create channel modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [newChannelType, setNewChannelType] = useState<'org' | 'store' | 'custom'>('org');
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
  const [availableMembers, setAvailableMembers] = useState<Member[]>([]);
  const [memberSearchQuery, setMemberSearchQuery] = useState('');
  
  // Web-compatible menus
  const [channelMenuId, setChannelMenuId] = useState<string | null>(null);
  const [showChatMenu, setShowChatMenu] = useState(false);
  const [menuPosition, setMenuPosition] = useState({top: 80, right: 16});
  const [channelSearch, setChannelSearch] = useState('');
  
  // Filtered channels based on search
  const filteredChannels = useMemo(() => {
    if (!channelSearch.trim()) return channels;
    const q = channelSearch.toLowerCase();
    return channels.filter(ch => ch.name.toLowerCase().includes(q));
  }, [channels, channelSearch]);
  
  // Refs
  const flatListRef = useRef<FlatList>(null);
  const messageInputRef = useRef<TextInput>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Load channels
  const loadChannels = useCallback(async () => {
    if (!user?._id) return;
    
    try {
      const response = await api.get(`/team-chat/channels?user_id=${user._id}`);
      if (response.data.success) {
        setChannels(response.data.channels);
      }
    } catch (error) {
      console.error('Error loading channels:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id]);

  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  // Load messages for selected channel
  const loadMessages = useCallback(async (channelId: string) => {
    if (!user?._id) return;
    
    setMessagesLoading(true);
    try {
      const response = await api.get(`/team-chat/messages/${channelId}?user_id=${user._id}`);
      if (response.data.success) {
        setMessages(response.data.messages);
      }
    } catch (error) {
      console.error('Error loading messages:', error);
    } finally {
      setMessagesLoading(false);
    }
  }, [user?._id]);

  // Poll for new messages when channel is selected
  useEffect(() => {
    if (selectedChannel) {
      loadMessages(selectedChannel.id);
      
      // Poll every 3 seconds for new messages
      pollIntervalRef.current = setInterval(() => {
        loadMessages(selectedChannel.id);
      }, 3000);
      
      return () => {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
        }
      };
    }
  }, [selectedChannel, loadMessages]);

  // Send message
  const sendMessage = async () => {
    if (!messageText.trim() || !selectedChannel || !user?._id || sending) return;
    
    setSending(true);
    try {
      // Extract mentions from message (@username)
      const mentionMatches = messageText.match(/@(\w+)/g);
      const mentions: string[] = [];
      
      if (mentionMatches) {
        // Find user IDs for mentioned names
        for (const mention of mentionMatches) {
          const name = mention.slice(1).toLowerCase();
          const member = availableMembers.find(m => 
            m.name.toLowerCase().includes(name)
          );
          if (member) {
            mentions.push(member.id);
          }
        }
      }
      
      const response = await api.post('/team-chat/messages', {
        channel_id: selectedChannel.id,
        sender_id: user._id,
        content: messageText.trim(),
        mentions,
        is_broadcast: false
      });
      
      if (response.data.success) {
        setMessageText('');
        loadMessages(selectedChannel.id);
        // Scroll to bottom
        setTimeout(() => {
          flatListRef.current?.scrollToEnd({ animated: true });
        }, 100);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      showAlert('Error', 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  // Load available members for creating channels
  const loadMembers = async (query: string = '') => {
    if (!user?._id) return;
    
    try {
      const response = await api.get(`/team-chat/members/search?user_id=${user._id}&query=${query}`);
      if (response.data.success) {
        setAvailableMembers(response.data.members);
      }
    } catch (error) {
      console.error('Error loading members:', error);
    }
  };

  // Create channel
  const createChannel = async () => {
    if (!newChannelName.trim() || !user?._id) return;
    
    try {
      const payload: any = {
        name: newChannelName.trim(),
        channel_type: newChannelType,
        created_by: user._id,
      };
      
      if (newChannelType === 'org') {
        payload.organization_id = user.organization_id;
      } else if (newChannelType === 'store') {
        payload.store_id = user.store_id;
      } else if (newChannelType === 'custom') {
        payload.member_ids = [...selectedMembers, user._id];
      }
      
      const response = await api.post('/team-chat/channels', payload);
      
      if (response.data.success) {
        setShowCreateModal(false);
        setNewChannelName('');
        setSelectedMembers([]);
        loadChannels();
        showToast('Channel created!');
      }
    } catch (error: any) {
      showAlert('Error', error.response?.data?.detail || 'Failed to create channel');
    }
  };

  // Start DM with a member
  const startDM = async (memberId: string, memberName: string) => {
    if (!user?._id) return;
    
    try {
      const response = await api.post('/team-chat/channels', {
        name: `DM: ${memberName}`,
        channel_type: 'dm',
        member_ids: [user._id, memberId],
        created_by: user._id
      });
      
      if (response.data.success) {
        loadChannels();
        // Open the DM
        const newChannel: Channel = {
          id: response.data.channel_id,
          name: memberName,
          channel_type: 'dm',
          member_count: 2,
          unread_count: 0
        };
        setSelectedChannel(newChannel);
      }
    } catch (error) {
      console.error('Error starting DM:', error);
    }
  };

  // Delete channel
  const deleteChannel = async (channel: Channel) => {
    if (!user?._id) return;
    const confirmed = Platform.OS === 'web'
      ? window.confirm(`Delete "${channel.name}" and all its messages? This cannot be undone.`)
      : true;
    if (!confirmed) return;
    try {
      const response = await api.delete(`/team-chat/channels/${channel.id}?user_id=${user._id}`);
      if (response.data.success) {
        if (selectedChannel?.id === channel.id) setSelectedChannel(null);
        loadChannels();
      }
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Failed to delete channel';
      Platform.OS === 'web' ? window.alert(msg) : showAlert('Error', msg);
    }
  };

  // Clear chat history
  const clearHistory = async (channel: Channel) => {
    if (!user?._id) return;
    const confirmed = Platform.OS === 'web'
      ? window.confirm(`Clear all messages in "${channel.name}"? This cannot be undone.`)
      : true;
    if (!confirmed) return;
    try {
      const response = await api.delete(`/team-chat/channels/${channel.id}/messages?user_id=${user._id}`);
      if (response.data.success && selectedChannel?.id === channel.id) {
        setMessages([]);
      }
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Failed to clear history';
      Platform.OS === 'web' ? window.alert(msg) : showAlert('Error', msg);
    }
  };

  // Show channel actions menu (web-compatible)
  const showChannelActions = (channel: Channel, pageY?: number) => {
    if (Platform.OS === 'web') {
      if (channelMenuId === channel.id) {
        setChannelMenuId(null);
      } else {
        const top = pageY ? Math.min(pageY + 10, window.innerHeight - 200) : 80;
        setMenuPosition({ top, right: 16 });
        setChannelMenuId(channel.id);
      }
    } else {
      showAlert(
        channel.name,
        undefined,
        [
          { text: 'Open Chat', onPress: () => { setSelectedChannel(channel); loadMembers(); } },
          { text: 'Clear History', style: 'destructive', onPress: () => clearHistory(channel) },
          { text: 'Delete Channel', style: 'destructive', onPress: () => deleteChannel(channel) },
          { text: 'Cancel', style: 'cancel' },
        ]
      );
    }
  };

  // Render channel list item
  const renderChannel = ({ item }: { item: Channel }) => {
    const getChannelIcon = () => {
      switch (item.channel_type) {
        case 'org': return 'globe-outline';
        case 'store': return 'business-outline';
        case 'custom': return 'people-outline';
        case 'dm': return 'person-outline';
        default: return 'chatbox-outline';
      }
    };

    return (
      <View
        style={[styles.channelItem, { backgroundColor: colors.card, borderBottomColor: colors.border }, item.unread_count > 0 && styles.channelUnread]}
        {...tid(`channel-${item.id}`)}
      >
        <TouchableOpacity
          style={styles.channelTapArea}
          onPress={() => {
            setSelectedChannel(item);
            loadMembers();
          }}
          onLongPress={() => showChannelActions(item)}
          activeOpacity={0.7}
        >
        <View style={styles.channelIcon}>
          {item.avatar ? (
            <Image source={{ uri: item.avatar }} style={styles.channelAvatar} />
          ) : (
            <Ionicons name={getChannelIcon()} size={24} color={colors.accent} />
          )}
        </View>
        
        <View style={styles.channelInfo}>
          <View style={styles.channelHeader}>
            <Text style={styles.channelName} numberOfLines={1}>
              {item.name}
            </Text>
            {item.last_message?.created_at && (
              <Text style={styles.channelTime}>
                {formatTime(item.last_message.created_at)}
              </Text>
            )}
          </View>
          
          {item.last_message && (
            <Text style={styles.channelPreview} numberOfLines={1}>
              <Text style={styles.senderName}>{item.last_message.sender_name}: </Text>
              {item.last_message.content}
            </Text>
          )}
          
          {!item.last_message && (
            <Text style={styles.channelPreview}>
              {item.member_count} member{item.member_count !== 1 ? 's' : ''}
            </Text>
          )}
        </View>
        
        {item.unread_count > 0 && (
          <View style={styles.unreadBadge}>
            <Text style={styles.unreadText}>{item.unread_count}</Text>
          </View>
        )}
        </TouchableOpacity>
        
        {/* 3-dot menu button  - outside the tap area */}
        <TouchableOpacity
          style={styles.channelMenuBtn}
          onPress={(e: any) => {
            const pageY = e?.nativeEvent?.pageY;
            showChannelActions(item, pageY);
          }}
          accessibilityRole="button"
          accessibilityLabel="Channel menu"
        >
          <Ionicons name="ellipsis-vertical" size={18} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
    );
  };

  // Render message
  const renderMessage = ({ item }: { item: Message }) => {
    const isOwnMessage = item.sender_id === user?._id;
    
    return (
      <View style={[
        styles.messageContainer,
        isOwnMessage ? styles.ownMessage : styles.otherMessage
      ]}>
        {!isOwnMessage && (
          <View style={styles.messageSender}>
            {item.sender_photo ? (
              <Image source={{ uri: item.sender_photo }} style={styles.senderAvatar} />
            ) : (
              <View style={styles.senderAvatarPlaceholder}>
                <Text style={styles.senderInitials}>
                  {item.sender_name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                </Text>
              </View>
            )}
            <Text style={styles.senderNameText}>{item.sender_name}</Text>
          </View>
        )}
        
        <View style={[
          styles.messageBubble,
          isOwnMessage ? styles.ownBubble : styles.otherBubble,
          item.is_broadcast && styles.broadcastBubble
        ]}>
          {item.is_broadcast && (
            <View style={styles.broadcastBadge}>
              <Ionicons name="megaphone" size={12} color="#000" />
              <Text style={[styles.broadcastLabel, { color: '#000' }]}>Broadcast</Text>
            </View>
          )}
          <Text style={[styles.messageText, (isOwnMessage || item.is_broadcast) && { color: '#000' }]}>{item.content}</Text>
          <Text style={[styles.messageTime, (isOwnMessage || item.is_broadcast) ? { color: 'rgba(0,0,0,0.6)' } : { color: colors.textTertiary }]}>{formatTime(item.created_at)}</Text>
        </View>
      </View>
    );
  };

  // Format time
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    if (diff < 60000) return 'now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
    if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  // Channel list view
  if (!selectedChannel) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
        <ScreenHeader
          title="Team Chat"
          testID="team-chat-header"
          right={<HeaderIconButton icon="add-circle" onPress={() => { loadMembers(); setShowCreateModal(true); }} testID="create-channel-btn" />}
        />

        {/* Channel Search Bar */}
        <View style={[styles.channelSearchBar, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
          <Ionicons name="search" size={18} color={colors.textSecondary} />
          <TextInput
            style={[styles.channelSearchInput, { color: colors.text }]}
            value={channelSearch}
            onChangeText={setChannelSearch}
            placeholder="Search channels..."
            placeholderTextColor={colors.textSecondary}
            {...tid('channel-search-input')}
          />
          {channelSearch.length > 0 && (
            <TouchableOpacity onPress={() => setChannelSearch('')}>
              <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>

        {/* Channel List */}
        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.accent} />
          </View>
        ) : (
          <FlatList
            data={filteredChannels}
            keyExtractor={(item) => item.id}
            renderItem={renderChannel}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={() => {
                  setRefreshing(true);
                  loadChannels();
                }}
                tintColor={colors.accent}
              />
            }
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Ionicons name="chatbox-ellipses-outline" size={64} color={colors.textSecondary} />
                <Text style={styles.emptyText}>No channels yet</Text>
                <Text style={styles.emptySubtext}>Create a channel to start messaging your team</Text>
                <TouchableOpacity
                  style={styles.emptyButton}
                  onPress={() => {
                    loadMembers();
                    setShowCreateModal(true);
                  }}
                >
                  <Text style={styles.emptyButtonText}>Create Channel</Text>
                </TouchableOpacity>
              </View>
            }
            contentContainerStyle={channels.length === 0 ? styles.emptyList : undefined}
          />
        )}

        {/* Web channel action dropdown: backdrop + menu as siblings */}
        {Platform.OS === 'web' && channelMenuId && (
          <>
            <View 
              style={{
                position: 'fixed' as any,
                top: 0, left: 0, right: 0, bottom: 0,
                zIndex: 9998,
                backgroundColor: 'transparent',
              }}
              onStartShouldSetResponder={() => true}
              onResponderRelease={() => setChannelMenuId(null)}
            />
            <View 
              style={{
                position: 'fixed' as any,
                top: menuPosition.top,
                right: menuPosition.right,
                backgroundColor: colors.surface,
                borderRadius: 12,
                overflow: 'hidden' as any,
                minWidth: 200,
                zIndex: 99999,
                // @ts-ignore
                boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              }}
            >
              <TouchableOpacity 
                style={styles.channelDropdownItem}
                onPress={() => {
                  const ch = channels.find(c => c.id === channelMenuId);
                  setChannelMenuId(null);
                  if (ch) { setSelectedChannel(ch); loadMembers(); }
                }}
              >
                <Ionicons name="chatbubble-outline" size={16} color={colors.text} />
                <Text style={styles.channelDropdownText}>Open Chat</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.channelDropdownItem}
                onPress={() => {
                  const ch = channels.find(c => c.id === channelMenuId);
                  setChannelMenuId(null);
                  if (ch) clearHistory(ch);
                }}
              >
                <Ionicons name="trash-outline" size={16} color="#FF9500" />
                <Text style={[styles.channelDropdownText, { color: '#FF9500' }]}>Clear History</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.channelDropdownItem}
                onPress={() => {
                  const ch = channels.find(c => c.id === channelMenuId);
                  setChannelMenuId(null);
                  if (ch) deleteChannel(ch);
                }}
              >
                <Ionicons name="close-circle-outline" size={16} color="#FF3B30" />
                <Text style={[styles.channelDropdownText, { color: '#FF3B30' }]}>Delete Channel</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {/* Create Channel Panel (web-compatible, replaces Modal) */}
        {showCreateModal && (
          <View style={styles.createPanel}>
            <View style={styles.createPanelHeader}>
              <TouchableOpacity onPress={() => setShowCreateModal(false)} hitSlop={8} {...tid('create-channel-cancel')}>
                <Text style={styles.modalCancel}>Cancel</Text>
              </TouchableOpacity>
              <Text style={styles.modalTitle}>New Channel</Text>
              <TouchableOpacity onPress={createChannel} hitSlop={8} {...tid('create-channel-submit')}>
                <Text style={[styles.modalCreate, !newChannelName.trim() && styles.modalCreateDisabled]}>
                  Create
                </Text>
              </TouchableOpacity>
            </View>

            <View style={styles.modalContent}>
              {/* Channel Name */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Channel Name</Text>
                <TextInput
                  style={styles.textInput}
                  value={newChannelName}
                  onChangeText={setNewChannelName}
                  placeholder="e.g., Sales Floor, All Managers"
                  placeholderTextColor={colors.textSecondary}
                  {...tid('channel-name-input')}
                />
              </View>

              {/* Channel Type */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Channel Type</Text>
                <View style={styles.typeButtons}>
                  {[
                    { type: 'org' as const, label: 'Organization', icon: 'globe-outline' },
                    { type: 'store' as const, label: 'Store', icon: 'business-outline' },
                    { type: 'custom' as const, label: 'Custom Group', icon: 'people-outline' },
                  ].map((option) => (
                    <TouchableOpacity
                      key={option.type}
                      style={[
                        styles.typeButton,
                        newChannelType === option.type && styles.typeButtonActive
                      ]}
                      onPress={() => setNewChannelType(option.type)}
                    >
                      <Ionicons
                        name={option.icon as any}
                        size={20}
                        color={newChannelType === option.type ? '#000' : colors.textSecondary}
                      />
                      <Text style={[
                        styles.typeButtonText,
                        newChannelType === option.type && styles.typeButtonTextActive
                      ]}>
                        {option.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Member Selection (for custom groups) */}
              {newChannelType === 'custom' && (
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Select Members</Text>
                  <TextInput
                    style={styles.textInput}
                    value={memberSearchQuery}
                    onChangeText={(text) => {
                      setMemberSearchQuery(text);
                      loadMembers(text);
                    }}
                    placeholder="Search members..."
                    placeholderTextColor={colors.textSecondary}
                  />
                  
                  {/* Selected members */}
                  {selectedMembers.length > 0 && (
                    <View style={styles.selectedMembers}>
                      {selectedMembers.map((memberId) => {
                        const member = availableMembers.find(m => m.id === memberId);
                        return member ? (
                          <TouchableOpacity
                            key={memberId}
                            style={styles.selectedMemberChip}
                            onPress={() => setSelectedMembers(prev => prev.filter(id => id !== memberId))}
                          >
                            <Text style={styles.selectedMemberName}>{member.name}</Text>
                            <Ionicons name="close" size={14} color="#000" />
                          </TouchableOpacity>
                        ) : null;
                      })}
                    </View>
                  )}
                  
                  {/* Available members */}
                  <FlatList
                    data={availableMembers.filter(m => !selectedMembers.includes(m.id) && m.id !== user?._id)}
                    keyExtractor={(item) => item.id}
                    renderItem={({ item }) => (
                      <TouchableOpacity
                        style={styles.memberItem}
                        onPress={() => setSelectedMembers(prev => [...prev, item.id])}
                      >
                        {item.photo_url ? (
                          <Image source={{ uri: item.photo_url }} style={styles.memberAvatar} />
                        ) : (
                          <View style={styles.memberAvatarPlaceholder}>
                            <Text style={styles.memberInitials}>
                              {item.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                            </Text>
                          </View>
                        )}
                        <View style={styles.memberInfo}>
                          <Text style={styles.memberName}>{item.name}</Text>
                          <Text style={styles.memberRole}>{item.role}</Text>
                        </View>
                        <Ionicons name="add-circle-outline" size={24} color={colors.accent} />
                      </TouchableOpacity>
                    )}
                    style={styles.memberList}
                  />
                </View>
              )}
            </View>
          </View>
        )}
      </SafeAreaView>
    );
  }

  // Chat view (when channel is selected)
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScreenHeader
        title={selectedChannel.name}
        subtitle={`${selectedChannel.member_count} member${selectedChannel.member_count !== 1 ? 's' : ''}`}
        testID="chat-header"
        onBack={() => {
          setSelectedChannel(null);
          loadChannels();
        }}
        right={(
          <HeaderIconButton
            icon="ellipsis-vertical"
            testID="chat-options-btn"
            onPress={() => {
              if (Platform.OS === 'web') {
                setShowChatMenu(!showChatMenu);
              } else {
                showAlert(
                  selectedChannel.name,
                  `${selectedChannel.member_count} member${selectedChannel.member_count !== 1 ? 's' : ''}`,
                  [
                    { text: 'Clear History', style: 'destructive', onPress: () => clearHistory(selectedChannel) },
                    { text: 'Delete Channel', style: 'destructive', onPress: () => deleteChannel(selectedChannel) },
                    { text: 'Cancel', style: 'cancel' },
                  ]
                );
              }
            }}
          />
        )}
      />

      {/* Chat header dropdown: backdrop + menu as siblings (web) */}
      {Platform.OS === 'web' && showChatMenu && selectedChannel && (
        <>
          <View 
            style={{
              position: 'fixed' as any,
              top: 0, left: 0, right: 0, bottom: 0,
              zIndex: 9998,
              backgroundColor: 'transparent',
            }}
            onStartShouldSetResponder={() => true}
            onResponderRelease={() => setShowChatMenu(false)}
          />
          <View 
            style={{
              position: 'fixed' as any,
              top: 56,
              right: 8,
              backgroundColor: colors.surface,
              borderRadius: 12,
              overflow: 'hidden' as any,
              minWidth: 180,
              zIndex: 99999,
              // @ts-ignore
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
            }}
          >
            <TouchableOpacity 
              style={styles.channelDropdownItem}
              onPress={() => { setShowChatMenu(false); clearHistory(selectedChannel); }}
            >
              <Ionicons name="trash-outline" size={16} color="#FF9500" />
              <Text style={[styles.channelDropdownText, { color: '#FF9500' }]}>Clear History</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.channelDropdownItem}
              onPress={() => { setShowChatMenu(false); deleteChannel(selectedChannel); }}
            >
              <Ionicons name="close-circle-outline" size={16} color="#FF3B30" />
              <Text style={[styles.channelDropdownText, { color: '#FF3B30' }]}>Delete Channel</Text>
            </TouchableOpacity>
          </View>
        </>
      )}

      {/* Messages */}
      <KeyboardAvoidingView
        style={styles.chatContent}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {messagesLoading && messages.length === 0 ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.accent} />
          </View>
        ) : (
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={(item) => item.id}
            renderItem={renderMessage}
            contentContainerStyle={styles.messagesList}
            ListEmptyComponent={
              <View style={styles.emptyMessages}>
                <Ionicons name="chatbubble-outline" size={48} color={colors.textSecondary} />
                <Text style={styles.emptyMessagesText}>No messages yet</Text>
                <Text style={styles.emptyMessagesSubtext}>Say hello to get the conversation going.</Text>
              </View>
            }
            onContentSizeChange={() => {
              flatListRef.current?.scrollToEnd({ animated: false });
            }}
          />
        )}

        {/* Message Input */}
        <View style={styles.inputContainer}>
          <VoiceInput 
            onTranscription={(text) => {
              setMessageText(prev => prev ? `${prev} ${text}` : text);
            }}
            size={24}
            color={colors.accent}
          />
          
          <TextInput
            ref={messageInputRef}
            style={styles.messageInput}
            value={messageText}
            onChangeText={setMessageText}
            placeholder="Type a message... (use @ to mention)"
            placeholderTextColor={colors.textSecondary}
            multiline
            maxLength={2000}
            {...tid('chat-message-input')}
          />
          
          <TouchableOpacity
            style={[styles.sendButton, (!messageText.trim() || sending) && styles.sendButtonDisabled]}
            onPress={sendMessage}
            disabled={!messageText.trim() || sending}
            {...tid('chat-send-btn')}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#000" />
            ) : (
              <Ionicons name="send" size={20} color="#000" />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  
  // Loading
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  
  // Channel List
  channelItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    position: 'relative' as any,
  },
  channelTapArea: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  channelUnread: {
    backgroundColor: 'rgba(201, 169, 98, 0.10)',
  },
  channelIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  channelAvatar: {
    width: 48,
    height: 48,
    borderRadius: 12,
  },
  channelInfo: {
    flex: 1,
  },
  channelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  channelName: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
    flex: 1,
    flexShrink: 1,
  },
  channelTime: {
    fontSize: FS.caption,
    color: colors.textSecondary,
    marginLeft: 8,
  },
  channelPreview: {
    fontSize: FS.secondary,
    color: colors.textSecondary,
  },
  senderName: {
    fontWeight: '500',
  },
  unreadBadge: {
    backgroundColor: colors.accent,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
    marginLeft: 8,
  },
  unreadText: {
    fontSize: FS.caption,
    fontWeight: '800',
    color: '#000',
  },
  
  // Empty State
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },

  // Channel Search
  channelSearchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 10,
    marginHorizontal: 16,
    marginBottom: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
  },
  channelSearchInput: {
    flex: 1,
    fontSize: 17,
    color: colors.text,
    padding: 0,
  },
  emptyList: {
    flex: 1,
  },
  emptyText: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: FS.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
  },
  emptyButton: {
    backgroundColor: colors.accent,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 14,
    marginTop: 24,
  },
  emptyButtonText: {
    color: '#000',
    fontWeight: '700',
    fontSize: FS.heading,
  },
  
  // Create Modal
  modalCancel: {
    fontSize: FS.heading,
    color: colors.textSecondary,
  },
  modalTitle: {
    fontSize: FS.nav,
    fontWeight: '700',
    color: colors.text,
  },
  modalCreate: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.accent,
  },
  modalCreateDisabled: {
    opacity: 0.5,
  },
  modalContent: {
    padding: 16,
  },
  inputGroup: {
    marginBottom: 24,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    color: colors.text,
    fontSize: FS.body,
    borderWidth: 1,
    borderColor: colors.border,
  },
  typeButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  typeButton: {
    flex: 1,
    flexDirection: 'column',
    alignItems: 'center',
    padding: 12,
    backgroundColor: colors.card,
    borderRadius: 12,
    gap: 4,
  },
  typeButtonActive: {
    backgroundColor: colors.accent,
  },
  typeButtonText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  typeButtonTextActive: {
    color: '#000',
  },
  
  // Member Selection
  selectedMembers: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  selectedMemberChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.accent,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 4,
  },
  selectedMemberName: {
    color: '#000',
    fontSize: FS.secondary,
    fontWeight: '600',
  },
  memberList: {
    maxHeight: 200,
    marginTop: 12,
  },
  memberItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: colors.card,
    borderRadius: 8,
    marginBottom: 8,
  },
  memberAvatar: {
    width: 40,
    height: 40,
    borderRadius: 10,
    marginRight: 12,
  },
  memberAvatarPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  memberInitials: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    fontSize: FS.body,
    fontWeight: '600',
    color: colors.text,
  },
  memberRole: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  
  // Chat View
  chatContent: {
    flex: 1,
  },
  messagesList: {
    padding: 16,
    flexGrow: 1,
  },
  
  // Messages
  messageContainer: {
    marginBottom: 16,
    maxWidth: '80%',
  },
  ownMessage: {
    alignSelf: 'flex-end',
  },
  otherMessage: {
    alignSelf: 'flex-start',
  },
  messageSender: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  senderAvatar: {
    width: 24,
    height: 24,
    borderRadius: 7,
    marginRight: 6,
  },
  senderAvatarPlaceholder: {
    width: 24,
    height: 24,
    borderRadius: 7,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 6,
  },
  senderInitials: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.text,
  },
  senderNameText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  messageBubble: {
    padding: 12,
    borderRadius: 16,
  },
  ownBubble: {
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  otherBubble: {
    backgroundColor: colors.card,
    borderBottomLeftRadius: 4,
  },
  broadcastBubble: {
    backgroundColor: colors.warning,
  },
  broadcastBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 8,
  },
  broadcastLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.text,
  },
  messageText: {
    fontSize: FS.body,
    color: colors.text,
    lineHeight: 21,
  },
  messageTime: {
    fontSize: FS.micro,
    marginTop: 4,
    alignSelf: 'flex-end',
  },
  
  // Empty Messages
  emptyMessages: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyMessagesText: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
    marginTop: 12,
  },
  emptyMessagesSubtext: {
    fontSize: FS.body,
    color: colors.textSecondary,
    marginTop: 4,
  },
  
  // Input
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bg,
  },
  voiceButton: {
    padding: 8,
    marginRight: 8,
  },
  messageInput: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: colors.text,
    fontSize: FS.body,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: colors.accent,
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
  sendButtonDisabled: {
    opacity: 0.5,
  },
  // Channel row 3-dot menu button
  channelMenuBtn: {
    padding: 12,
    marginLeft: 4,
    zIndex: 1,
  },
  // Channel dropdown menu items
  channelDropdownItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    gap: 10,
  },
  channelDropdownText: {
    fontSize: 16,
    color: colors.text,
    fontWeight: '500',
  },
  // Create channel panel (replaces Modal)
  createPanel: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.bg,
    zIndex: 9999,
  },
  createPanelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
});
