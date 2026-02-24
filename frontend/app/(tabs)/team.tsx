import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Modal,
  Alert,
  Platform,
  KeyboardAvoidingView,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import VoiceInput from '../../components/VoiceInput';

// Colors matching the app theme
const COLORS = {
  background: '#000',
  card: '#1C1C1E',
  cardHover: '#2C2C2E',
  accent: '#007AFF',
  success: '#34C759',
  warning: '#FF9500',
  error: '#FF3B30',
  textPrimary: '#FFF',
  textSecondary: '#8E8E93',
  border: '#2C2C2E',
};

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
  const router = useRouter();
  const { user } = useAuthStore();
  
  // State
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
  const [newChannelType, setNewChannelType] = useState<'org' | 'store' | 'custom'>('store');
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
  const [availableMembers, setAvailableMembers] = useState<Member[]>([]);
  const [memberSearchQuery, setMemberSearchQuery] = useState('');
  
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
      Alert.alert('Error', 'Failed to send message');
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
        Alert.alert('Success', 'Channel created!');
      }
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to create channel');
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
      <TouchableOpacity
        style={[styles.channelItem, item.unread_count > 0 && styles.channelUnread]}
        onPress={() => {
          setSelectedChannel(item);
          loadMembers();
        }}
        activeOpacity={0.7}
      >
        <View style={styles.channelIcon}>
          {item.avatar ? (
            <Image source={{ uri: item.avatar }} style={styles.channelAvatar} />
          ) : (
            <Ionicons name={getChannelIcon()} size={24} color={COLORS.accent} />
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
              <Ionicons name="megaphone" size={12} color="#FFF" />
              <Text style={styles.broadcastLabel}>Broadcast</Text>
            </View>
          )}
          <Text style={styles.messageText}>{item.content}</Text>
          <Text style={styles.messageTime}>{formatTime(item.created_at)}</Text>
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
      <SafeAreaView style={styles.container} edges={['top']}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Team Chat</Text>
          <TouchableOpacity
            style={styles.createButton}
            onPress={() => {
              loadMembers();
              setShowCreateModal(true);
            }}
          >
            <Ionicons name="add-circle" size={28} color={COLORS.accent} />
          </TouchableOpacity>
        </View>

        {/* Channel List */}
        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={COLORS.accent} />
          </View>
        ) : (
          <FlatList
            data={channels}
            keyExtractor={(item) => item.id}
            renderItem={renderChannel}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={() => {
                  setRefreshing(true);
                  loadChannels();
                }}
                tintColor={COLORS.accent}
              />
            }
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Ionicons name="chatbox-ellipses-outline" size={64} color={COLORS.textSecondary} />
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

        {/* Create Channel Modal */}
        <Modal
          visible={showCreateModal}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={() => setShowCreateModal(false)}
        >
          <View style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <TouchableOpacity onPress={() => setShowCreateModal(false)}>
                <Text style={styles.modalCancel}>Cancel</Text>
              </TouchableOpacity>
              <Text style={styles.modalTitle}>New Channel</Text>
              <TouchableOpacity onPress={createChannel}>
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
                  placeholderTextColor={COLORS.textSecondary}
                />
              </View>

              {/* Channel Type */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Channel Type</Text>
                <View style={styles.typeButtons}>
                  {[
                    { type: 'store' as const, label: 'Store', icon: 'business-outline' },
                    { type: 'org' as const, label: 'Organization', icon: 'globe-outline' },
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
                        color={newChannelType === option.type ? '#FFF' : COLORS.textSecondary}
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
                    placeholderTextColor={COLORS.textSecondary}
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
                            <Ionicons name="close" size={14} color="#FFF" />
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
                        <Ionicons name="add-circle-outline" size={24} color={COLORS.accent} />
                      </TouchableOpacity>
                    )}
                    style={styles.memberList}
                  />
                </View>
              )}
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    );
  }

  // Chat view (when channel is selected)
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Chat Header */}
      <View style={styles.chatHeader}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => {
            setSelectedChannel(null);
            loadChannels();
          }}
        >
          <Ionicons name="chevron-back" size={28} color={COLORS.accent} />
        </TouchableOpacity>
        
        <View style={styles.chatHeaderInfo}>
          <Text style={styles.chatHeaderName}>{selectedChannel.name}</Text>
          <Text style={styles.chatHeaderMembers}>
            {selectedChannel.member_count} member{selectedChannel.member_count !== 1 ? 's' : ''}
          </Text>
        </View>
        
        <TouchableOpacity style={styles.chatHeaderAction}>
          <Ionicons name="information-circle-outline" size={26} color={COLORS.accent} />
        </TouchableOpacity>
      </View>

      {/* Messages */}
      <KeyboardAvoidingView
        style={styles.chatContent}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {messagesLoading && messages.length === 0 ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={COLORS.accent} />
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
                <Ionicons name="chatbubble-outline" size={48} color={COLORS.textSecondary} />
                <Text style={styles.emptyMessagesText}>No messages yet</Text>
                <Text style={styles.emptyMessagesSubtext}>Start the conversation!</Text>
              </View>
            }
            onContentSizeChange={() => {
              flatListRef.current?.scrollToEnd({ animated: false });
            }}
          />
        )}

        {/* Message Input */}
        <View style={styles.inputContainer}>
          <TouchableOpacity style={styles.voiceButton}>
            <Ionicons name="mic" size={24} color={COLORS.accent} />
          </TouchableOpacity>
          
          <TextInput
            ref={messageInputRef}
            style={styles.messageInput}
            value={messageText}
            onChangeText={setMessageText}
            placeholder="Type a message... (use @ to mention)"
            placeholderTextColor={COLORS.textSecondary}
            multiline
            maxLength={2000}
          />
          
          <TouchableOpacity
            style={[styles.sendButton, (!messageText.trim() || sending) && styles.sendButtonDisabled]}
            onPress={sendMessage}
            disabled={!messageText.trim() || sending}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <Ionicons name="send" size={20} color="#FFF" />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  
  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  createButton: {
    padding: 4,
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
    borderBottomColor: COLORS.border,
  },
  channelUnread: {
    backgroundColor: 'rgba(0, 122, 255, 0.1)',
  },
  channelIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: COLORS.card,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  channelAvatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
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
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
    flex: 1,
  },
  channelTime: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginLeft: 8,
  },
  channelPreview: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  senderName: {
    fontWeight: '500',
  },
  unreadBadge: {
    backgroundColor: COLORS.accent,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
    marginLeft: 8,
  },
  unreadText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFF',
  },
  
  // Empty State
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyList: {
    flex: 1,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginTop: 8,
  },
  emptyButton: {
    backgroundColor: COLORS.accent,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 20,
    marginTop: 24,
  },
  emptyButtonText: {
    color: '#FFF',
    fontWeight: '600',
  },
  
  // Create Modal
  modalContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  modalCancel: {
    fontSize: 16,
    color: COLORS.accent,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  modalCreate: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.accent,
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
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: COLORS.card,
    borderRadius: 12,
    padding: 16,
    color: COLORS.textPrimary,
    fontSize: 16,
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
    backgroundColor: COLORS.card,
    borderRadius: 12,
    gap: 4,
  },
  typeButtonActive: {
    backgroundColor: COLORS.accent,
  },
  typeButtonText: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  typeButtonTextActive: {
    color: '#FFF',
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
    backgroundColor: COLORS.accent,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 4,
  },
  selectedMemberName: {
    color: '#FFF',
    fontSize: 14,
  },
  memberList: {
    maxHeight: 200,
    marginTop: 12,
  },
  memberItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: COLORS.card,
    borderRadius: 8,
    marginBottom: 8,
  },
  memberAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    marginRight: 12,
  },
  memberAvatarPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: COLORS.cardHover,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  memberInitials: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    fontSize: 16,
    fontWeight: '500',
    color: COLORS.textPrimary,
  },
  memberRole: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  
  // Chat View
  chatHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  backButton: {
    padding: 4,
  },
  chatHeaderInfo: {
    flex: 1,
    marginLeft: 8,
  },
  chatHeaderName: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  chatHeaderMembers: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  chatHeaderAction: {
    padding: 4,
  },
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
    borderRadius: 12,
    marginRight: 6,
  },
  senderAvatarPlaceholder: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.card,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 6,
  },
  senderInitials: {
    fontSize: 10,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  senderNameText: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  messageBubble: {
    padding: 12,
    borderRadius: 16,
  },
  ownBubble: {
    backgroundColor: COLORS.accent,
    borderBottomRightRadius: 4,
  },
  otherBubble: {
    backgroundColor: COLORS.card,
    borderBottomLeftRadius: 4,
  },
  broadcastBubble: {
    backgroundColor: COLORS.warning,
  },
  broadcastBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 8,
  },
  broadcastLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: '#FFF',
  },
  messageText: {
    fontSize: 16,
    color: '#FFF',
    lineHeight: 22,
  },
  messageTime: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.6)',
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
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 12,
  },
  emptyMessagesSubtext: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 4,
  },
  
  // Input
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    backgroundColor: COLORS.background,
  },
  voiceButton: {
    padding: 8,
    marginRight: 8,
  },
  messageInput: {
    flex: 1,
    backgroundColor: COLORS.card,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: COLORS.textPrimary,
    fontSize: 16,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: COLORS.accent,
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
});
