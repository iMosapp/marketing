import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
  ActivityIndicator,
  Linking,
  TextInput,
  Modal,
  FlatList,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { contactsAPI } from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { NotificationBell } from '../../components/notifications/NotificationBell';

const IS_WEB = Platform.OS === 'web';

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const colors = useThemeStore((s) => s.colors);
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);

  // Quick Dial state
  const [showDialer, setShowDialer] = useState(false);
  const [dialContacts, setDialContacts] = useState<any[]>([]);
  const [dialSearch, setDialSearch] = useState('');
  const [dialLoading, setDialLoading] = useState(false);

  useFocusEffect(
    useCallback(() => {
      if (user?._id) {
        loadRecentActivity();
        loadStoreSlug();
      }
    }, [user?._id])
  );

  const loadStoreSlug = async () => {
    if (user?.store_slug) {
      setStoreSlug(user.store_slug);
    } else if (user?.store_id) {
      try {
        const res = await api.get(`/admin/stores/${user.store_id}`, {
          headers: { 'X-User-ID': user._id }
        });
        setStoreSlug(res.data?.slug || res.data?.name?.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
      } catch {}
    }
  };

  const loadRecentActivity = async () => {
    if (!user?._id) return;
    try {
      setLoadingActivity(true);
      const res = await api.get(`/activity/${user._id}?limit=5`);
      setRecentActivity(res.data.activities || []);
    } catch {
    } finally {
      setLoadingActivity(false);
    }
  };

  // === ACTION HANDLERS ===

  const handleShareCard = () => {
    router.push(`/card/${user?._id}` as any);
  };

  const handleShareReview = () => {
    if (!storeSlug) {
      showSimpleAlert('Setup Needed', 'Please set up your store profile first.');
      return;
    }
    const spParam = user?._id ? `?sp=${user._id}` : '';
    const url = `https://app.imosapp.com/review/${storeSlug}${spParam}`;
    if (IS_WEB && navigator.clipboard) {
      navigator.clipboard.writeText(url);
      showSimpleAlert('Link Copied!', 'Your review link has been copied to clipboard.');
    } else {
      Linking.openURL(url);
    }
  };

  const handleCreateCard = () => {
    router.push('/settings/congrats-template' as any);
  };

  const handleShowroom = () => {
    router.push(`/showcase/${user?._id}` as any);
  };

  const handleAddContact = () => {
    router.push('/contact/new' as any);
  };

  // Quick Dial
  const handleQuickDial = async () => {
    setShowDialer(true);
    setDialSearch('');
    setDialLoading(true);
    try {
      const data = await contactsAPI.getAll(user?._id || '');
      setDialContacts(data || []);
    } catch {}
    setDialLoading(false);
  };

  const placeCall = async (contact: any) => {
    const phone = contact.phone;
    if (!phone) {
      showSimpleAlert('No Phone', 'This contact has no phone number.');
      return;
    }
    // Log the call activity
    try {
      await api.post(`/calls/${user?._id}`, {
        contact_id: contact._id,
        type: 'outbound',
        duration: 0,
      });
    } catch {}
    // Also log as contact event
    try {
      await contactsAPI.logEvent(user?._id || '', contact._id, {
        event_type: 'call_placed',
        title: 'Outbound Call',
        description: `Called ${contact.first_name} ${contact.last_name || ''}`.trim(),
        channel: 'call',
        category: 'message',
        icon: 'call',
        color: '#32ADE6',
      });
    } catch {}

    // Open native dialer
    const telUrl = `tel:${phone}`;
    if (IS_WEB) {
      window.location.href = telUrl;
    } else {
      Linking.openURL(telUrl);
    }
    setShowDialer(false);
    showSimpleAlert('Call Logged', `Call to ${contact.first_name} has been logged.`);
    loadRecentActivity();
  };

  const filteredDialContacts = dialContacts.filter(c => {
    const q = dialSearch.toLowerCase();
    if (!q) return true;
    return (
      (c.first_name || '').toLowerCase().includes(q) ||
      (c.last_name || '').toLowerCase().includes(q) ||
      (c.phone || '').includes(q)
    );
  });

  // Activity icon map
  const getActivityIcon = (type: string) => {
    const map: Record<string, { icon: string; color: string }> = {
      contact_added: { icon: 'person-add', color: '#34C759' },
      message_sent: { icon: 'chatbubble', color: '#007AFF' },
      task_created: { icon: 'checkmark-circle', color: '#FF9500' },
      campaign_enrollment: { icon: 'rocket', color: '#AF52DE' },
      call_placed: { icon: 'call', color: '#32ADE6' },
      card_shared: { icon: 'card', color: '#C9A962' },
      review_invite_sent: { icon: 'star', color: '#FFD60A' },
    };
    return map[type] || { icon: 'ellipse', color: '#8E8E93' };
  };

  const TILES = [
    {
      key: 'share-card',
      icon: 'card-outline',
      label: 'Share My Card',
      color: '#007AFF',
      onPress: handleShareCard,
    },
    {
      key: 'share-review',
      icon: 'star-outline',
      label: 'Review Link',
      color: '#FFD60A',
      onPress: handleShareReview,
    },
    {
      key: 'create-card',
      icon: 'gift-outline',
      label: 'Create Card',
      color: '#C9A962',
      onPress: handleCreateCard,
    },
    {
      key: 'showroom',
      icon: 'storefront-outline',
      label: 'My Showroom',
      color: '#34C759',
      onPress: handleShowroom,
    },
    {
      key: 'quick-dial',
      icon: 'call-outline',
      label: 'Quick Dial',
      color: '#32ADE6',
      onPress: handleQuickDial,
    },
    {
      key: 'add-contact',
      icon: 'person-add-outline',
      label: 'Add Contact',
      color: '#AF52DE',
      onPress: handleAddContact,
    },
  ];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <View>
          <Text style={[styles.greeting, { color: colors.textSecondary }]}>Welcome back,</Text>
          <Text style={[styles.userName, { color: colors.text }]}>{user?.name?.split(' ')[0] || 'there'}</Text>
        </View>
        <NotificationBell />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Action Tiles Grid */}
        <View style={styles.tilesGrid} data-testid="home-tiles-grid">
          {TILES.map((tile) => (
            <TouchableOpacity
              key={tile.key}
              style={[styles.tile, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={tile.onPress}
              activeOpacity={0.7}
              data-testid={`home-tile-${tile.key}`}
            >
              <View style={[styles.tileIconWrap, { backgroundColor: `${tile.color}18` }]}>
                <Ionicons name={tile.icon as any} size={28} color={tile.color} />
              </View>
              <Text style={[styles.tileLabel, { color: colors.text }]}>{tile.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Recent Activity */}
        <View style={styles.activitySection}>
          <View style={styles.activityHeader}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Recent Activity</Text>
            <TouchableOpacity
              onPress={() => router.push('/admin/activity-feed' as any)}
              data-testid="view-all-activity"
            >
              <Text style={[styles.viewAll, { color: colors.accent }]}>View All</Text>
            </TouchableOpacity>
          </View>

          {loadingActivity ? (
            <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} />
          ) : recentActivity.length === 0 ? (
            <View style={[styles.emptyActivity, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Ionicons name="pulse-outline" size={32} color={colors.textTertiary} />
              <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                No recent activity yet. Start by sharing your card or adding a contact!
              </Text>
            </View>
          ) : (
            recentActivity.map((item, idx) => {
              const ai = getActivityIcon(item.type);
              return (
                <View
                  key={idx}
                  style={[styles.activityItem, { backgroundColor: colors.card, borderColor: colors.border }]}
                  data-testid={`activity-item-${idx}`}
                >
                  <View style={[styles.activityIconWrap, { backgroundColor: `${ai.color}18` }]}>
                    <Ionicons name={ai.icon as any} size={18} color={ai.color} />
                  </View>
                  <View style={styles.activityContent}>
                    <Text style={[styles.activityMsg, { color: colors.text }]} numberOfLines={1}>
                      {item.message}
                    </Text>
                    <Text style={[styles.activityTime, { color: colors.textTertiary }]}>
                      {item.timestamp ? new Date(item.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}
                    </Text>
                  </View>
                </View>
              );
            })
          )}
        </View>
      </ScrollView>

      {/* Quick Dial Modal */}
      <Modal visible={showDialer} animationType="slide" transparent data-testid="quick-dial-modal">
        <View style={[styles.modalOverlay, { backgroundColor: colors.overlay }]}>
          <View style={[styles.modalContent, { backgroundColor: colors.modalBg }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Quick Dial</Text>
              <TouchableOpacity onPress={() => setShowDialer(false)} data-testid="close-dial-modal">
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <TextInput
              style={[styles.searchInput, { backgroundColor: colors.searchBg, color: colors.text, borderColor: colors.border }]}
              placeholder="Search contacts..."
              placeholderTextColor={colors.textTertiary}
              value={dialSearch}
              onChangeText={setDialSearch}
              data-testid="dial-search-input"
            />

            {dialLoading ? (
              <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} />
            ) : (
              <FlatList
                data={filteredDialContacts.slice(0, 50)}
                keyExtractor={(item) => item._id}
                style={{ maxHeight: 400 }}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={[styles.dialContactItem, { borderBottomColor: colors.border }]}
                    onPress={() => placeCall(item)}
                    data-testid={`dial-contact-${item._id}`}
                  >
                    <View style={[styles.dialAvatar, { backgroundColor: `${colors.accent}20` }]}>
                      <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 16 }}>
                        {(item.first_name || '?')[0].toUpperCase()}
                      </Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.dialName, { color: colors.text }]}>
                        {item.first_name} {item.last_name || ''}
                      </Text>
                      <Text style={[styles.dialPhone, { color: colors.textSecondary }]}>{item.phone}</Text>
                    </View>
                    <Ionicons name="call" size={20} color="#32ADE6" />
                  </TouchableOpacity>
                )}
                ListEmptyComponent={
                  <Text style={[styles.emptyText, { color: colors.textSecondary, textAlign: 'center', marginTop: 30 }]}>
                    No contacts found
                  </Text>
                }
              />
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 0.5,
  },
  greeting: { fontSize: 13, fontWeight: '500' },
  userName: { fontSize: 24, fontWeight: '800', marginTop: 2 },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 40 },

  // Tiles
  tilesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  tile: {
    width: '48%',
    flexBasis: '47%',
    flexGrow: 1,
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    minHeight: 120,
  },
  tileIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  tileLabel: { fontSize: 14, fontWeight: '700', textAlign: 'center' },

  // Activity
  activitySection: { marginTop: 28 },
  activityHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: { fontSize: 18, fontWeight: '700' },
  viewAll: { fontSize: 13, fontWeight: '600' },
  emptyActivity: {
    borderRadius: 14,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
  },
  emptyText: { fontSize: 13, marginTop: 10, textAlign: 'center', lineHeight: 20 },
  activityItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
  },
  activityIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  activityContent: { flex: 1 },
  activityMsg: { fontSize: 13, fontWeight: '600' },
  activityTime: { fontSize: 11, marginTop: 2 },

  // Modal
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '80%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: { fontSize: 20, fontWeight: '700' },
  searchInput: {
    borderRadius: 12,
    padding: 12,
    fontSize: 15,
    marginBottom: 12,
    borderWidth: 1,
  },
  dialContactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 0.5,
    gap: 12,
  },
  dialAvatar: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialName: { fontSize: 15, fontWeight: '600' },
  dialPhone: { fontSize: 13, marginTop: 2 },
});
