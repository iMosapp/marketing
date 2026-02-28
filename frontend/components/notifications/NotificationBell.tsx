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

function getNotifIcon(type: string): string {
  switch (type) {
    case 'new_lead': case 'lead_assigned': return 'person-add';
    case 'jump_ball': return 'flash';
    case 'task_overdue': return 'alert-circle';
    case 'task_due_soon': return 'time';
    case 'unread_message': return 'chatbubble';
    case 'flagged': return 'flag';
    case 'link_click': return 'open';
    case 'review_submitted': return 'star';
    case 'new_contact': return 'person-add';
    case 'digital_card_sent': return 'card';
    case 'review_request_sent': return 'star-half';
    case 'congrats_card_sent': return 'gift';
    case 'email_sent': return 'mail';
    case 'sms_sent': return 'chatbox';
    case 'badge_earned': return 'trophy';
    case 'campaign_send': return 'megaphone';
    default: return 'notifications';
  }
}

function getNotifColor(type: string): string {
  switch (type) {
    case 'new_lead': case 'lead_assigned': return '#007AFF';
    case 'jump_ball': return '#FF9500';
    case 'task_overdue': return '#FF3B30';
    case 'task_due_soon': return '#FF9500';
    case 'unread_message': return '#007AFF';
    case 'flagged': return '#FF9500';
    case 'link_click': return '#5856D6';
    case 'review_submitted': return '#FFD60A';
    case 'email_sent': return '#30D158';
    case 'sms_sent': return '#34C759';
    case 'badge_earned': return '#FFD60A';
    case 'campaign_send': return '#FF9500';
    default: return '#8E8E93';
  }
}

function getCategoryLabel(cat: string): string {
  switch (cat) {
    case 'leads': return 'Leads';
    case 'tasks': return 'Tasks';
    case 'messages': return 'Messages';
    case 'flags': return 'Flags';
    case 'campaigns': return 'Campaigns';
    case 'activity': return 'Activity';
    default: return 'All';
  }
}

function getCategoryIcon(cat: string): string {
  switch (cat) {
    case 'leads': return 'person-add';
    case 'tasks': return 'checkbox';
    case 'messages': return 'chatbubble';
    case 'flags': return 'flag';
    case 'campaigns': return 'megaphone';
    case 'activity': return 'pulse';
    default: return 'apps';
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
    if (diff < 172800000) return 'Yesterday';
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
    categoryFilter,
    setCategoryFilter,
    categoryCounts,
  } = useNotifications();
  const [open, setOpen] = useState(false);

  const handlePress = () => {
    if (!open) refreshNotifications();
    setOpen(!open);
  };

  const handleNotificationPress = (n: any) => {
    markAsRead(n.id);
    setOpen(false);
    if (n.link) {
      router.push(n.link as any);
    }
  };

  const categories = ['all', 'leads', 'tasks', 'messages', 'campaigns', 'flags', 'activity'];

  return (
    <View style={styles.wrapper}>
      <TouchableOpacity
        style={styles.button}
        onPress={handlePress}
        data-testid="notification-bell-btn"
      >
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
            {/* Header */}
            <View style={styles.dropdownHeader}>
              <Text style={styles.dropdownTitle}>Notifications</Text>
              <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
                {unreadCount > 0 && (
                  <TouchableOpacity onPress={markAllRead} data-testid="mark-all-read-btn">
                    <Text style={styles.markAll}>Mark all read</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity
                  onPress={() => { setOpen(false); router.push('/notifications' as any); }}
                  data-testid="view-all-notifications-btn"
                >
                  <Text style={[styles.markAll, { color: '#8E8E93' }]}>View All</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Category Filters */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.categoryBar}>
              {categories.map(cat => {
                const isActive = categoryFilter === cat;
                const count = cat === 'all'
                  ? Object.values(categoryCounts).reduce((s: number, v: any) => s + v, 0)
                  : (categoryCounts[cat] || 0);
                return (
                  <TouchableOpacity
                    key={cat}
                    style={[styles.categoryChip, isActive && styles.categoryChipActive]}
                    onPress={() => setCategoryFilter(cat)}
                    data-testid={`notif-filter-${cat}`}
                  >
                    <Ionicons
                      name={getCategoryIcon(cat) as any}
                      size={13}
                      color={isActive ? '#FFF' : '#8E8E93'}
                    />
                    <Text style={[styles.categoryChipText, isActive && styles.categoryChipTextActive]}>
                      {getCategoryLabel(cat)}{count > 0 ? ` (${count})` : ''}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            {/* Notification List */}
            <ScrollView style={styles.list} contentContainerStyle={{ paddingBottom: 8 }}>
              {notifications.length === 0 ? (
                <View style={styles.emptyContainer}>
                  <Ionicons name="checkmark-circle" size={32} color="#3A3A3C" />
                  <Text style={styles.empty}>All caught up!</Text>
                </View>
              ) : (
                notifications.slice(0, 25).map((n: any) => (
                  <TouchableOpacity
                    key={n.id}
                    style={[styles.item, !n.read && styles.itemUnread]}
                    onPress={() => handleNotificationPress(n)}
                    data-testid={`notification-item-${n.id}`}
                  >
                    <View style={[styles.iconCircle, { backgroundColor: getNotifColor(n.type) + '20' }]}>
                      <Ionicons name={getNotifIcon(n.type) as any} size={16} color={getNotifColor(n.type)} />
                    </View>
                    <View style={styles.itemContent}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                        <Text style={styles.itemTitle} numberOfLines={1}>{n.title}</Text>
                        {!n.read && <View style={styles.dot} />}
                      </View>
                      {(n.body || n.contact_name) && (
                        <Text style={styles.itemBody} numberOfLines={2}>
                          {n.body || n.contact_name}
                        </Text>
                      )}
                      <Text style={styles.itemTime}>{formatTime(n.timestamp || n.created_at)}</Text>
                    </View>
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
    top: IS_WEB ? 60 : 48,
    right: IS_WEB ? 16 : 0,
    width: 380,
    maxHeight: 520,
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
  categoryBar: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
    maxHeight: 44,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 16,
    backgroundColor: '#2C2C2E',
    marginRight: 6,
  },
  categoryChipActive: {
    backgroundColor: '#007AFF',
  },
  categoryChipText: {
    fontSize: 12,
    color: '#8E8E93',
    fontWeight: '500',
  },
  categoryChipTextActive: {
    color: '#FFF',
  },
  list: {
    maxHeight: 400,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 40,
    gap: 8,
  },
  empty: {
    textAlign: 'center',
    color: '#6E6E73',
    fontSize: 14,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
    gap: 10,
  },
  itemUnread: {
    backgroundColor: '#007AFF08',
  },
  iconCircle: {
    width: 32,
    height: 32,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  dot: {
    width: 7,
    height: 7,
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
    flex: 1,
  },
  itemBody: {
    fontSize: 13,
    color: '#8E8E93',
    lineHeight: 18,
    marginTop: 1,
  },
  itemTime: {
    fontSize: 11,
    color: '#6E6E73',
    marginTop: 3,
  },
});
