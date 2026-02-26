import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  Pressable,
  StyleSheet,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useNotifications } from '../../hooks/useNotifications';

const IS_WEB = Platform.OS === 'web';

function getNotifIcon(type: string) {
  switch (type) {
    case 'new_lead': case 'lead_assigned': return 'person-add';
    case 'jump_ball': return 'flash';
    case 'team_mention': return 'at';
    case 'team_broadcast': return 'megaphone';
    case 'team_chat': return 'chatbox';
    case 'new_message': return 'chatbubble';
    default: return 'notifications';
  }
}

function getNotifColor(type: string) {
  switch (type) {
    case 'new_lead': return '#007AFF';
    case 'jump_ball': return '#FF9500';
    case 'team_mention': return '#C9A962';
    case 'team_broadcast': return '#5856D6';
    case 'team_chat': return '#34C759';
    case 'new_message': return '#007AFF';
    default: return '#8E8E93';
  }
}

function formatTime(isoString: string) {
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  } catch { return ''; }
}

export function NotificationBell() {
  const router = useRouter();
  const {
    notifications,
    unreadCount,
    refreshNotifications,
    markAsRead,
    markAllRead,
  } = useNotifications();
  const [open, setOpen] = useState(false);

  const handlePress = () => {
    if (!open) refreshNotifications();
    setOpen(!open);
  };

  const handleNotificationPress = (n: any) => {
    markAsRead(n.id);
    setOpen(false);
    if (n.conversation_id) {
      router.push(`/inbox/${n.conversation_id}`);
    } else if (n.channel_id) {
      router.push('/team' as any);
    }
  };

  return (
    <View style={styles.wrapper}>
      <TouchableOpacity style={styles.button} onPress={handlePress}>
        <Ionicons name="notifications-outline" size={22} color="#FFF" />
        {unreadCount > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{unreadCount > 99 ? '99+' : unreadCount}</Text>
          </View>
        )}
      </TouchableOpacity>

      {open && (
        <Pressable style={styles.overlay} onPress={() => setOpen(false)}>
          <Pressable style={styles.dropdown} onPress={(e) => e.stopPropagation()}>
            <View style={styles.dropdownHeader}>
              <Text style={styles.dropdownTitle}>Notifications</Text>
              {unreadCount > 0 && (
                <TouchableOpacity onPress={markAllRead}>
                  <Text style={styles.markAll}>Mark all read</Text>
                </TouchableOpacity>
              )}
            </View>
            <ScrollView style={styles.list} contentContainerStyle={{ paddingBottom: 8 }}>
              {notifications.length === 0 ? (
                <Text style={styles.empty}>No notifications yet</Text>
              ) : (
                notifications.slice(0, 20).map((n: any) => (
                  <TouchableOpacity
                    key={n.id}
                    style={[styles.item, !n.read && styles.itemUnread]}
                    onPress={() => handleNotificationPress(n)}
                  >
                    <View style={styles.itemDot}>
                      {!n.read && <View style={styles.dot} />}
                    </View>
                    <View style={styles.itemContent}>
                      <Text style={styles.itemTitle} numberOfLines={1}>{n.title}</Text>
                      <Text style={styles.itemBody} numberOfLines={2}>{n.message || n.body || ''}</Text>
                      <Text style={styles.itemTime}>{formatTime(n.created_at)}</Text>
                    </View>
                    <Ionicons name={getNotifIcon(n.type) as any} size={18} color={getNotifColor(n.type)} />
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    position: 'relative',
    zIndex: 9999,
  },
  button: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  badge: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: '#FF3B30',
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
    borderWidth: 2,
    borderColor: '#000',
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FFF',
  },
  overlay: {
    ...(IS_WEB ? {
      position: 'fixed' as any,
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
    } : {
      position: 'absolute',
      top: 0,
      left: -300,
      width: 400,
      height: 500,
    }),
    zIndex: 99998,
  },
  dropdown: {
    position: 'absolute',
    top: IS_WEB ? 'auto' : 48,
    right: IS_WEB ? 16 : 0,
    ...(IS_WEB ? { top: 60, right: 16 } : {}),
    width: 340,
    maxHeight: 440,
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#2C2C2E',
    overflow: 'hidden',
    zIndex: 99999,
    ...(IS_WEB ? {
      boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
    } : {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.6,
      shadowRadius: 16,
      elevation: 20,
    }),
  },
  dropdownHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  dropdownTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFF',
  },
  markAll: {
    fontSize: 13,
    color: '#007AFF',
    fontWeight: '500',
  },
  list: {
    maxHeight: 380,
  },
  empty: {
    textAlign: 'center',
    color: '#6E6E73',
    fontSize: 14,
    paddingVertical: 40,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
    gap: 10,
  },
  itemUnread: {
    backgroundColor: '#007AFF10',
  },
  itemDot: {
    width: 8,
    paddingTop: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#007AFF',
  },
  itemContent: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  itemBody: {
    fontSize: 13,
    color: '#8E8E93',
    lineHeight: 18,
  },
  itemTime: {
    fontSize: 11,
    color: '#6E6E73',
    marginTop: 4,
  },
});
