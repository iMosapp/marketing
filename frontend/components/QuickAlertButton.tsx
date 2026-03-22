import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  TextInput,
  ActivityIndicator,
  FlatList,
  Platform,
  Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import { useRouter } from 'expo-router';
import api from '../services/api';

import { useThemeStore } from '../store/themeStore';
const COLORS = {
  background: '#000',
  card: '#1C1C1E',
  accent: '#007AFF',
  alert: '#FF3B30',
  warning: '#FF9500',
  success: '#34C759',
  textPrimary: '#FFF',
  textSecondary: '#8E8E93',
};

// Preset quick alert messages
const PRESET_ALERTS = [
  { id: '1', icon: 'person', text: 'Customer waiting at front', color: '#FF9500' },
  { id: '2', icon: 'hand-left', text: 'Need backup on sales floor', color: '#FF3B30' },
  { id: '3', icon: 'megaphone', text: 'Manager to register please', color: '#5856D6' },
  { id: '4', icon: 'people', text: 'Team huddle in 5 minutes', color: '#007AFF' },
  { id: '5', icon: 'call', text: 'Phone call holding - who can take?', color: '#34C759' },
  { id: '6', icon: 'car', text: 'Customer arrived for pickup', color: '#FF9500' },
];

interface Message {
  id: string;
  sender_id: string;
  sender_name: string;
  sender_photo?: string;
  content: string;
  is_broadcast: boolean;
  created_at: string;
  channel_name?: string;
}

interface QuickAlertButtonProps {
  visible?: boolean;
}

export default function QuickAlertButton({ visible = true }: QuickAlertButtonProps) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const { user } = useAuthStore();
  const router = useRouter();
  const [showModal, setShowModal] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [unreadMessages, setUnreadMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'messages' | 'send'>('messages');
  const [customMessage, setCustomMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sentAlert, setSentAlert] = useState<string | null>(null);

  // Fetch unread count periodically
  const fetchUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    
    try {
      const response = await api.get(`/team-chat/channels?user_id=${user._id}`);
      if (response.data.success) {
        const total = response.data.channels.reduce((sum: number, ch: any) => sum + (ch.unread_count || 0), 0);
        setUnreadCount(total);
      }
    } catch (error) {
      console.error('Error fetching unread count:', error);
    }
  }, [user?._id]);

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 10000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Fetch unread messages when modal opens
  const fetchUnreadMessages = async () => {
    if (!user?._id) return;
    
    setLoading(true);
    try {
      const channelsRes = await api.get(`/team-chat/channels?user_id=${user._id}`);
      if (channelsRes.data.success) {
        const allMessages: Message[] = [];
        
        for (const channel of channelsRes.data.channels) {
          if (channel.unread_count > 0 || channel.last_message) {
            try {
              const msgsRes = await api.get(`/team-chat/messages/${channel.id}?user_id=${user._id}&limit=5`);
              if (msgsRes.data.success) {
                const msgs = msgsRes.data.messages.map((m: any) => ({
                  ...m,
                  channel_name: channel.name
                }));
                allMessages.push(...msgs);
              }
            } catch (e) {}
          }
        }
        
        allMessages.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setUnreadMessages(allMessages.slice(0, 20));
      }
    } catch (error) {
      console.error('Error fetching messages:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setShowModal(true);
    setActiveTab('messages');
    fetchUnreadMessages();
  };

  const sendAlert = async (message: string) => {
    if (!user?._id || sending) return;

    setSending(true);
    try {
      const channelsRes = await api.get(`/team-chat/channels?user_id=${user._id}`);
      
      let targetChannel = null;
      if (channelsRes.data.success && channelsRes.data.channels.length > 0) {
        targetChannel = channelsRes.data.channels.find((c: any) => c.channel_type === 'store') ||
                       channelsRes.data.channels.find((c: any) => c.channel_type === 'org') ||
                       channelsRes.data.channels[0];
      }

      if (!targetChannel) {
        const createRes = await api.post('/team-chat/channels', {
          name: 'Quick Alerts',
          channel_type: user.organization_id ? 'org' : 'custom',
          organization_id: user.organization_id,
          store_id: user.store_id,
          member_ids: user.organization_id ? undefined : [user._id],
          created_by: user._id,
        });
        
        if (createRes.data.success) {
          targetChannel = { id: createRes.data.channel_id };
        }
      }

      if (targetChannel) {
        await api.post('/team-chat/messages', {
          channel_id: targetChannel.id,
          sender_id: user._id,
          content: `🚨 QUICK ALERT: ${message}`,
          mentions: [],
          is_broadcast: true,
        });

        setSentAlert(message);
        setTimeout(() => {
          setSentAlert(null);
          setActiveTab('messages');
          setCustomMessage('');
          fetchUnreadMessages();
        }, 1500);
      }
    } catch (error) {
      console.error('Error sending quick alert:', error);
    } finally {
      setSending(false);
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    if (diff < 60000) return 'now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
    if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const goToTeamChat = () => {
    setShowModal(false);
    router.push('/team');
  };

  if (!visible || !user) return null;

  return (
    <>
      {/* Top Right Notification Badge */}
      <View style={styles.badgeContainer}>
        <TouchableOpacity
          style={styles.badgeButton}
          onPress={handleOpen}
          activeOpacity={0.7}
        >
          <Ionicons name="chatbox-ellipses" size={22} color={COLORS.textPrimary} />
          {unreadCount > 0 && (
            <View style={styles.countBadge}>
              <Text style={styles.countText}>
                {unreadCount > 99 ? '99+' : unreadCount}
              </Text>
            </View>
          )}
        </TouchableOpacity>
      </View>

      {/* Messages Modal */}
      <Modal
        visible={showModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowModal(false)}
      >
        <TouchableOpacity 
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowModal(false)}
        >
          <View style={styles.modalContent} onStartShouldSetResponder={() => true}>
            {/* Header */}
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Team Messages</Text>
              <TouchableOpacity onPress={() => setShowModal(false)}>
                <Ionicons name="close" size={24} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>

            {/* Tabs */}
            <View style={styles.tabContainer}>
              <TouchableOpacity
                style={[styles.tab, activeTab === 'messages' && styles.tabActive]}
                onPress={() => setActiveTab('messages')}
              >
                <Ionicons 
                  name="mail" 
                  size={18} 
                  color={activeTab === 'messages' ? COLORS.accent : COLORS.textSecondary} 
                />
                <Text style={[styles.tabText, activeTab === 'messages' && styles.tabTextActive]}>
                  Messages
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.tab, activeTab === 'send' && styles.tabActive]}
                onPress={() => setActiveTab('send')}
              >
                <Ionicons 
                  name="flash" 
                  size={18} 
                  color={activeTab === 'send' ? COLORS.alert : COLORS.textSecondary} 
                />
                <Text style={[styles.tabText, activeTab === 'send' && styles.tabTextActive]}>
                  Quick Alert
                </Text>
              </TouchableOpacity>
            </View>

            {/* Messages Tab */}
            {activeTab === 'messages' && (
              <View style={styles.messagesContainer}>
                {loading ? (
                  <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={COLORS.accent} />
                  </View>
                ) : unreadMessages.length === 0 ? (
                  <View style={styles.emptyContainer}>
                    <Ionicons name="checkmark-circle" size={48} color={COLORS.success} />
                    <Text style={styles.emptyText}>All caught up!</Text>
                    <Text style={styles.emptySubtext}>No new team messages</Text>
                  </View>
                ) : (
                  <FlatList
                    data={unreadMessages}
                    keyExtractor={(item) => item.id}
                    renderItem={({ item }) => (
                      <View style={[styles.messageItem, item.is_broadcast && styles.broadcastItem]}>
                        <View style={styles.messageHeader}>
                          {item.sender_photo ? (
                            <Image source={{ uri: item.sender_photo }} style={styles.senderAvatar} />
                          ) : (
                            <View style={styles.senderAvatarPlaceholder}>
                              <Text style={styles.senderInitials}>
                                {item.sender_name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                              </Text>
                            </View>
                          )}
                          <View style={styles.messageInfo}>
                            <Text style={styles.senderName}>{item.sender_name}</Text>
                            <Text style={styles.channelName}>{item.channel_name}</Text>
                          </View>
                          <Text style={styles.messageTime}>{formatTime(item.created_at)}</Text>
                        </View>
                        <Text style={styles.messageContent} numberOfLines={2}>{item.content}</Text>
                      </View>
                    )}
                    style={styles.messagesList}
                  />
                )}
                
                <TouchableOpacity style={styles.openChatButton} onPress={goToTeamChat}>
                  <Text style={styles.openChatText}>Open Team Chat</Text>
                  <Ionicons name="arrow-forward" size={18} color={COLORS.accent} />
                </TouchableOpacity>
              </View>
            )}

            {/* Send Alert Tab */}
            {activeTab === 'send' && (
              <View style={styles.sendContainer}>
                {sentAlert ? (
                  <View style={styles.successContainer}>
                    <Ionicons name="checkmark-circle" size={64} color={COLORS.success} />
                    <Text style={styles.successText}>Alert Sent!</Text>
                    <Text style={styles.successSubtext}>{sentAlert}</Text>
                  </View>
                ) : (
                  <>
                    <Text style={styles.sendLabel}>Tap to send to your team:</Text>
                    <View style={styles.presetGrid}>
                      {PRESET_ALERTS.map((alert) => (
                        <TouchableOpacity
                          key={alert.id}
                          style={styles.presetButton}
                          onPress={() => sendAlert(alert.text)}
                          disabled={sending}
                        >
                          <View style={[styles.presetIcon, { backgroundColor: alert.color }]}>
                            <Ionicons name={alert.icon as any} size={18} color={colors.text} />
                          </View>
                          <Text style={styles.presetText} numberOfLines={2}>{alert.text}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>

                    <View style={styles.customContainer}>
                      <Text style={styles.customLabel}>Custom message:</Text>
                      <View style={styles.customInputRow}>
                        <TextInput
                          style={styles.customInput}
                          value={customMessage}
                          onChangeText={setCustomMessage}
                          placeholder="Type alert..."
                          placeholderTextColor={COLORS.textSecondary}
                          maxLength={100}
                        />
                        <TouchableOpacity
                          style={[styles.customSendButton, (!customMessage.trim() || sending) && styles.customSendDisabled]}
                          onPress={() => sendAlert(customMessage.trim())}
                          disabled={!customMessage.trim() || sending}
                        >
                          {sending ? (
                            <ActivityIndicator size="small" color={colors.text} />
                          ) : (
                            <Ionicons name="send" size={16} color={colors.text} />
                          )}
                        </TouchableOpacity>
                      </View>
                    </View>
                  </>
                )}
              </View>
            )}
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  badgeContainer: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 50 : 10,
    right: 16,
    zIndex: 1000,
    ...Platform.select({
      web: {
        position: 'fixed' as any,
        top: 12,
      },
    }),
  },
  badgeButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.card,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.surface,
  },
  countBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: COLORS.alert,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  countText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.text,
  },
  
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'flex-start',
    alignItems: 'flex-end',
    paddingTop: Platform.OS === 'ios' ? 100 : 60,
    paddingRight: 16,
  },
  modalContent: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    width: 340,
    maxWidth: '90%',
    maxHeight: '70%',
    overflow: 'hidden',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  modalTitle: {
    fontSize: 19,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },

  tabContainer: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    gap: 6,
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: COLORS.accent,
  },
  tabText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  tabTextActive: {
    color: COLORS.textPrimary,
  },

  messagesContainer: {
    flex: 1,
  },
  loadingContainer: {
    padding: 32,
    alignItems: 'center',
  },
  emptyContainer: {
    padding: 32,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 15,
    color: COLORS.textSecondary,
    marginTop: 4,
  },
  messagesList: {
    maxHeight: 300,
  },
  messageItem: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  broadcastItem: {
    backgroundColor: 'rgba(255, 59, 48, 0.1)',
  },
  messageHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  senderAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    marginRight: 8,
  },
  senderAvatarPlaceholder: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  senderInitials: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  messageInfo: {
    flex: 1,
  },
  senderName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  channelName: {
    fontSize: 13,
    color: COLORS.textSecondary,
  },
  messageTime: {
    fontSize: 13,
    color: COLORS.textSecondary,
  },
  messageContent: {
    fontSize: 15,
    color: COLORS.textSecondary,
    lineHeight: 18,
  },
  openChatButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
    gap: 6,
  },
  openChatText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.accent,
  },

  sendContainer: {
    padding: 12,
  },
  sendLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 12,
  },
  presetGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  presetButton: {
    width: '48%',
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    backgroundColor: colors.surface,
    borderRadius: 10,
    gap: 8,
  },
  presetIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  presetText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
    color: COLORS.textPrimary,
  },
  customContainer: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
  },
  customLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 8,
  },
  customInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  customInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    color: COLORS.textPrimary,
    fontSize: 16,
  },
  customSendButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: COLORS.alert,
    justifyContent: 'center',
    alignItems: 'center',
  },
  customSendDisabled: {
    opacity: 0.5,
  },

  successContainer: {
    padding: 24,
    alignItems: 'center',
  },
  successText: {
    fontSize: 19,
    fontWeight: '700',
    color: COLORS.success,
    marginTop: 12,
  },
  successSubtext: {
    fontSize: 15,
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginTop: 4,
  },
});
