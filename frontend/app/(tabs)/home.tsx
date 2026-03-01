import React, { useState, useCallback } from 'react';
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
import { UniversalShareModal } from '../../components/UniversalShareModal';

const IS_WEB = Platform.OS === 'web';

// ─── Contact Action Sheet ─────────────────────────────────────────
function ContactActionModal({
  visible, onClose, colors, userId, initialMode,
}: {
  visible: boolean; onClose: () => void; colors: any; userId: string; initialMode: 'search' | 'keypad';
}) {
  const router = useRouter();
  const [mode, setMode] = useState<'search' | 'keypad'>(initialMode);
  const [contacts, setContacts] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [dialNumber, setDialNumber] = useState('');

  React.useEffect(() => {
    if (visible) { setMode(initialMode); setSearch(''); setDialNumber(''); loadContacts(); }
  }, [visible, initialMode]);

  const loadContacts = async () => {
    setLoading(true);
    try { const data = await contactsAPI.getAll(userId); setContacts(data || []); } catch {}
    setLoading(false);
  };

  const filtered = contacts.filter(c => {
    const q = search.toLowerCase();
    if (!q) return true;
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q) || (c.phone || '').includes(q) || (c.email || '').toLowerCase().includes(q);
  });

  const logAndDial = async (phone: string, contact?: any) => {
    if (!phone) { showSimpleAlert('No Number', 'No phone number to dial.'); return; }
    try {
      if (contact?._id) {
        await api.post(`/calls/${userId}`, { contact_id: contact._id, type: 'outbound', duration: 0 });
        await contactsAPI.logEvent(userId, contact._id, { event_type: 'call_placed', title: 'Outbound Call', description: `Called ${contact.first_name || ''} ${contact.last_name || ''}`.trim(), channel: 'call', category: 'message', icon: 'call', color: '#32ADE6' });
      }
    } catch {}
    const telUrl = `tel:${phone.replace(/[^\d+]/g, '')}`;
    IS_WEB ? (window.location.href = telUrl) : Linking.openURL(telUrl);
    onClose();
    showSimpleAlert('Call Logged', 'Call has been logged.');
  };

  const logAndText = async (phone: string, contact?: any) => {
    if (!phone) return;
    try {
      if (contact?._id) {
        await contactsAPI.logEvent(userId, contact._id, { event_type: 'sms_sent', title: 'SMS Sent', description: `Texted ${contact.first_name || ''}`.trim(), channel: 'sms_personal', category: 'message', icon: 'chatbubble', color: '#007AFF' });
      }
    } catch {}
    const smsUrl = `sms:${phone.replace(/[^\d+]/g, '')}`;
    IS_WEB ? (window.location.href = smsUrl) : Linking.openURL(smsUrl);
    onClose();
  };

  const logAndEmail = async (email: string, contact?: any) => {
    if (!email) return;
    try {
      if (contact?._id) {
        await contactsAPI.logEvent(userId, contact._id, { event_type: 'email_sent', title: 'Email Sent', description: `Emailed ${contact.first_name || ''}`.trim(), channel: 'email', category: 'message', icon: 'mail', color: '#AF52DE' });
      }
    } catch {}
    Linking.openURL(`mailto:${email}`);
    onClose();
  };

  const goToImportFromPhone = () => { onClose(); router.push('/contacts/import' as any); };

  const KEYS = [['1','2','3'],['4','5','6'],['7','8','9'],['*','0','#']];

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={[styles.modalOverlay, { backgroundColor: colors.overlay }]}>
        <View style={[styles.modalContent, { backgroundColor: colors.modalBg }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>{initialMode === 'keypad' ? 'Quick Dial' : 'Add Contact'}</Text>
            <TouchableOpacity onPress={onClose} data-testid="close-action-modal"><Ionicons name="close" size={24} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <View style={[styles.modeTabs, { borderColor: colors.border }]}>
            <TouchableOpacity style={[styles.modeTab, mode === 'search' && { backgroundColor: colors.accent + '20' }]} onPress={() => setMode('search')} data-testid="mode-search">
              <Ionicons name="search" size={16} color={mode === 'search' ? colors.accent : colors.textSecondary} />
              <Text style={{ color: mode === 'search' ? colors.accent : colors.textSecondary, fontSize: 13, fontWeight: '600' }}>Contacts</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.modeTab, mode === 'keypad' && { backgroundColor: colors.accent + '20' }]} onPress={() => setMode('keypad')} data-testid="mode-keypad">
              <Ionicons name="keypad" size={16} color={mode === 'keypad' ? colors.accent : colors.textSecondary} />
              <Text style={{ color: mode === 'keypad' ? colors.accent : colors.textSecondary, fontSize: 13, fontWeight: '600' }}>Keypad</Text>
            </TouchableOpacity>
          </View>

          {mode === 'search' ? (
            <>
              <TextInput style={[styles.searchInput, { backgroundColor: colors.searchBg, color: colors.text, borderColor: colors.border }]} placeholder="Search name, phone, or email..." placeholderTextColor={colors.textTertiary} value={search} onChangeText={setSearch} data-testid="contact-search-input" />
              <TouchableOpacity style={[styles.importPhoneBtn, { borderColor: colors.border }]} onPress={goToImportFromPhone} data-testid="import-from-phone">
                <Ionicons name="phone-portrait-outline" size={18} color={colors.accent} />
                <Text style={{ color: colors.accent, fontSize: 14, fontWeight: '600' }}>Import from Phone Contacts</Text>
              </TouchableOpacity>
              {loading ? <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} /> : (
                <FlatList data={filtered.slice(0, 50)} keyExtractor={(item) => item._id} style={{ maxHeight: 320 }}
                  renderItem={({ item }) => (
                    <View style={[styles.contactRow, { borderBottomColor: colors.border }]}>
                      <View style={[styles.contactAvatar, { backgroundColor: `${colors.accent}20` }]}>
                        <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 16 }}>{(item.first_name || '?')[0].toUpperCase()}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.contactName, { color: colors.text }]}>{item.first_name} {item.last_name || ''}</Text>
                        <Text style={{ color: colors.textTertiary, fontSize: 12 }}>{item.phone || item.email || ''}</Text>
                      </View>
                      <View style={styles.actionBtns}>
                        {item.phone ? <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#32ADE620' }]} onPress={() => logAndDial(item.phone, item)}><Ionicons name="call" size={16} color="#32ADE6" /></TouchableOpacity> : null}
                        {item.phone ? <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#34C75920' }]} onPress={() => logAndText(item.phone, item)}><Ionicons name="chatbubble" size={16} color="#34C759" /></TouchableOpacity> : null}
                        {item.email ? <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#AF52DE20' }]} onPress={() => logAndEmail(item.email, item)}><Ionicons name="mail" size={16} color="#AF52DE" /></TouchableOpacity> : null}
                      </View>
                    </View>
                  )}
                  ListEmptyComponent={<Text style={{ color: colors.textSecondary, textAlign: 'center', marginTop: 30, fontSize: 14 }}>{search ? 'No contacts match your search' : 'No contacts yet'}</Text>}
                />
              )}
              <TouchableOpacity style={[styles.manualAddBtn, { backgroundColor: colors.accent }]} onPress={() => { onClose(); router.push('/contact/new' as any); }} data-testid="manual-add-contact">
                <Ionicons name="person-add" size={18} color="#000" />
                <Text style={{ color: '#000', fontSize: 14, fontWeight: '700' }}>Enter Manually</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <View style={[styles.dialDisplay, { borderColor: colors.border }]}>
                <Text style={[styles.dialNumber, { color: colors.text }]}>{dialNumber || 'Enter number'}</Text>
                {dialNumber.length > 0 && <TouchableOpacity onPress={() => setDialNumber(d => d.slice(0, -1))}><Ionicons name="backspace-outline" size={22} color={colors.textSecondary} /></TouchableOpacity>}
              </View>
              <View style={styles.keypadGrid}>
                {KEYS.map((row, ri) => (
                  <View key={ri} style={styles.keypadRow}>
                    {row.map((key) => (
                      <TouchableOpacity key={key} style={[styles.keypadKey, { backgroundColor: colors.card }]} onPress={() => setDialNumber(d => d + key)}>
                        <Text style={[styles.keypadKeyText, { color: colors.text }]}>{key}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                ))}
              </View>
              <TouchableOpacity style={[styles.dialBtn, { backgroundColor: '#34C759' }]} onPress={() => logAndDial(dialNumber)}>
                <Ionicons name="call" size={22} color="#FFF" />
              </TouchableOpacity>
              <View style={{ height: 20 }} />
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

// ─── Send a Card Template Picker ──────────────────────────────────
function SendCardModal({ visible, onClose, colors }: { visible: boolean; onClose: () => void; colors: any; }) {
  const router = useRouter();
  const CARD_TYPES = [
    { key: 'congrats', label: 'Congrats Card', icon: 'gift', color: '#C9A962', route: '/settings/create-congrats' },
    { key: 'birthday', label: 'Birthday Card', icon: 'balloon', color: '#FF2D55', route: '/settings/create-birthday-card' },
    { key: 'anniversary', label: 'Anniversary Card', icon: 'heart', color: '#FF6B6B', route: '/settings/create-congrats' },
    { key: 'thankyou', label: 'Thank You Card', icon: 'thumbs-up', color: '#34C759', route: '/settings/create-congrats' },
    { key: 'welcome', label: 'Welcome Card', icon: 'hand-left', color: '#007AFF', route: '/settings/create-congrats' },
    { key: 'holiday', label: 'Holiday Card', icon: 'snow', color: '#5AC8FA', route: '/settings/create-congrats' },
  ];

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={[styles.modalOverlay, { backgroundColor: colors.overlay }]}>
        <View style={[styles.modalContent, { backgroundColor: colors.modalBg }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Send a Card</Text>
            <TouchableOpacity onPress={onClose} data-testid="close-card-modal"><Ionicons name="close" size={24} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <Text style={{ color: colors.textSecondary, fontSize: 13, marginBottom: 16 }}>Choose a card type to send to a customer</Text>
          <ScrollView style={{ maxHeight: 400 }}>
            {CARD_TYPES.map((card) => (
              <TouchableOpacity key={card.key} style={[styles.cardTypeRow, { borderColor: colors.border }]} onPress={() => { onClose(); router.push(card.route as any); }} data-testid={`card-type-${card.key}`}>
                <View style={[styles.cardTypeIcon, { backgroundColor: `${card.color}18` }]}><Ionicons name={card.icon as any} size={24} color={card.color} /></View>
                <Text style={[styles.cardTypeLabel, { color: colors.text }]}>{card.label}</Text>
                <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

// ─── Main Home Screen ─────────────────────────────────────────────
export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const colors = useThemeStore((s) => s.colors);
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);

  // Modals
  const [showSendCard, setShowSendCard] = useState(false);
  const [showContactAction, setShowContactAction] = useState(false);
  const [contactActionMode, setContactActionMode] = useState<'search' | 'keypad'>('search');

  // Universal share modals
  const [shareConfig, setShareConfig] = useState<{ visible: boolean; title: string; subtitle: string; url: string; text?: string; showVCard: boolean; showQR: boolean; eventType: string }>({
    visible: false, title: '', subtitle: '', url: '', showVCard: false, showQR: false, eventType: '',
  });

  useFocusEffect(
    useCallback(() => {
      if (user?._id) { loadRecentActivity(); loadStoreSlug(); }
    }, [user?._id])
  );

  const loadStoreSlug = async () => {
    if (user?.store_slug) { setStoreSlug(user.store_slug); return; }
    if (user?.store_id) {
      try {
        const res = await api.get(`/admin/stores/${user.store_id}`, { headers: { 'X-User-ID': user._id } });
        setStoreSlug(res.data?.slug || res.data?.name?.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
      } catch {}
    }
  };

  const loadRecentActivity = async () => {
    if (!user?._id) return;
    try { setLoadingActivity(true); const res = await api.get(`/activity/${user._id}?limit=5`); setRecentActivity(res.data.activities || []); } catch {} finally { setLoadingActivity(false); }
  };

  // Open share modal for a tile
  const openShareModal = (tile: string) => {
    const userId = user?._id || '';
    const baseUrl = 'https://app.imosapp.com';

    switch (tile) {
      case 'share-card':
        setShareConfig({
          visible: true,
          title: 'Share My Card',
          subtitle: 'Choose how to share your digital card',
          url: `${baseUrl}/p/${userId}`,
          text: `Check out my digital business card: ${baseUrl}/p/${userId}`,
          showVCard: true,
          showQR: true,
          eventType: 'digital_card_shared',
        });
        break;
      case 'share-review':
        if (!storeSlug) {
          showSimpleAlert('Setup Needed', 'Please configure your store profile first to generate a review link.');
          return;
        }
        setShareConfig({
          visible: true,
          title: 'Share Review Link',
          subtitle: 'Ask your customer to leave a review',
          url: `${baseUrl}/review/${storeSlug}?sp=${userId}`,
          text: `I'd really appreciate it if you could leave me a review: ${baseUrl}/review/${storeSlug}?sp=${userId}`,
          showVCard: false,
          showQR: true,
          eventType: 'review_invite_sent',
        });
        break;
      case 'showroom':
        setShareConfig({
          visible: true,
          title: 'Share My Showroom',
          subtitle: 'Show off your happy customers',
          url: `${baseUrl}/showcase/${userId}`,
          text: `Check out my showroom of happy customers: ${baseUrl}/showcase/${userId}`,
          showVCard: false,
          showQR: true,
          eventType: 'showroom_shared',
        });
        break;
    }
  };

  const getActivityIcon = (type: string) => {
    const map: Record<string, { icon: string; color: string }> = {
      contact_added: { icon: 'person-add', color: '#34C759' },
      message_sent: { icon: 'chatbubble', color: '#007AFF' },
      sms_sent: { icon: 'chatbubble', color: '#007AFF' },
      email_sent: { icon: 'mail', color: '#AF52DE' },
      task_created: { icon: 'checkmark-circle', color: '#FF9500' },
      campaign_enrollment: { icon: 'rocket', color: '#AF52DE' },
      call_placed: { icon: 'call', color: '#32ADE6' },
      card_shared: { icon: 'card', color: '#C9A962' },
      digital_card_shared: { icon: 'card', color: '#C9A962' },
      review_invite_sent: { icon: 'star', color: '#FFD60A' },
      congrats_card: { icon: 'gift', color: '#C9A962' },
      showroom_shared: { icon: 'storefront', color: '#34C759' },
    };
    return map[type] || { icon: 'ellipse', color: '#8E8E93' };
  };

  const TILES = [
    { key: 'share-card', icon: 'card-outline', label: 'Share My Card', color: '#007AFF', onPress: () => openShareModal('share-card') },
    { key: 'share-review', icon: 'star-outline', label: 'Review Link', color: '#FFD60A', onPress: () => openShareModal('share-review') },
    { key: 'send-card', icon: 'gift-outline', label: 'Send a Card', color: '#C9A962', onPress: () => setShowSendCard(true) },
    { key: 'showroom', icon: 'storefront-outline', label: 'My Showroom', color: '#34C759', onPress: () => openShareModal('showroom') },
    { key: 'quick-dial', icon: 'call-outline', label: 'Quick Dial', color: '#32ADE6', onPress: () => { setContactActionMode('keypad'); setShowContactAction(true); } },
    { key: 'add-contact', icon: 'person-add-outline', label: 'Add Contact', color: '#AF52DE', onPress: () => { setContactActionMode('search'); setShowContactAction(true); } },
  ];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4 }} data-testid="home-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.userName, { color: colors.text }]}>Home</Text>
        <NotificationBell />
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.tilesGrid} data-testid="home-tiles-grid">
          {TILES.map((tile) => (
            <TouchableOpacity key={tile.key} style={[styles.tile, { backgroundColor: colors.card, borderColor: colors.border }]} onPress={tile.onPress} activeOpacity={0.7} data-testid={`home-tile-${tile.key}`}>
              <View style={[styles.tileIconWrap, { backgroundColor: `${tile.color}18` }]}>
                <Ionicons name={tile.icon as any} size={28} color={tile.color} />
              </View>
              <Text style={[styles.tileLabel, { color: colors.text }]}>{tile.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.activitySection}>
          <View style={styles.activityHeader}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Recent Activity</Text>
            <TouchableOpacity onPress={() => router.push('/admin/activity-feed' as any)} data-testid="view-all-activity">
              <Text style={[styles.viewAll, { color: colors.accent }]}>View All</Text>
            </TouchableOpacity>
          </View>
          {loadingActivity ? (
            <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} />
          ) : recentActivity.length === 0 ? (
            <View style={[styles.emptyActivity, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Ionicons name="pulse-outline" size={32} color={colors.textTertiary} />
              <Text style={[styles.emptyText, { color: colors.textSecondary }]}>No recent activity yet. Start by sharing your card or adding a contact!</Text>
            </View>
          ) : (
            recentActivity.map((item, idx) => {
              const ai = getActivityIcon(item.type);
              return (
                <View key={idx} style={[styles.activityItem, { backgroundColor: colors.card, borderColor: colors.border }]} data-testid={`activity-item-${idx}`}>
                  <View style={[styles.activityIconWrap, { backgroundColor: `${ai.color}18` }]}><Ionicons name={ai.icon as any} size={18} color={ai.color} /></View>
                  <View style={styles.activityContent}>
                    <Text style={[styles.activityMsg, { color: colors.text }]} numberOfLines={1}>{item.message}</Text>
                    <Text style={[styles.activityTime, { color: colors.textTertiary }]}>{item.timestamp ? new Date(item.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}</Text>
                  </View>
                </View>
              );
            })
          )}
        </View>
      </ScrollView>

      {/* Universal Share Modal — used by Share My Card, Review Link, Showroom */}
      <UniversalShareModal
        visible={shareConfig.visible}
        onClose={() => setShareConfig(c => ({ ...c, visible: false }))}
        title={shareConfig.title}
        subtitle={shareConfig.subtitle}
        shareUrl={shareConfig.url}
        shareText={shareConfig.text}
        showVCard={shareConfig.showVCard}
        showQR={shareConfig.showQR}
        vCardUserId={user?._id}
        userId={user?._id}
        eventType={shareConfig.eventType}
      />

      <SendCardModal visible={showSendCard} onClose={() => setShowSendCard(false)} colors={colors} />
      <ContactActionModal visible={showContactAction} onClose={() => setShowContactAction(false)} colors={colors} userId={user?._id || ''} initialMode={contactActionMode} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5 },
  userName: { fontSize: 18, fontWeight: '700' },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 40 },
  tilesGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  tile: { width: '48%', flexBasis: '47%', flexGrow: 1, borderRadius: 16, padding: 20, alignItems: 'center', justifyContent: 'center', borderWidth: 1, minHeight: 120 },
  tileIconWrap: { width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  tileLabel: { fontSize: 14, fontWeight: '700', textAlign: 'center' },
  activitySection: { marginTop: 28 },
  activityHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '700' },
  viewAll: { fontSize: 13, fontWeight: '600' },
  emptyActivity: { borderRadius: 14, padding: 24, alignItems: 'center', borderWidth: 1 },
  emptyText: { fontSize: 13, marginTop: 10, textAlign: 'center', lineHeight: 20 },
  activityItem: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 12, marginBottom: 8, borderWidth: 1 },
  activityIconWrap: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  activityContent: { flex: 1 },
  activityMsg: { fontSize: 13, fontWeight: '600' },
  activityTime: { fontSize: 11, marginTop: 2 },
  // Modal shared
  modalOverlay: { flex: 1, justifyContent: 'flex-end' },
  modalContent: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 34, maxHeight: '75%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 20, fontWeight: '700' },
  searchInput: { borderRadius: 12, padding: 12, fontSize: 15, marginBottom: 8, borderWidth: 1 },
  modeTabs: { flexDirection: 'row', borderWidth: 1, borderRadius: 10, marginBottom: 12, overflow: 'hidden' },
  modeTab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10 },
  importPhoneBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 12, paddingHorizontal: 14, marginBottom: 8, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed' },
  contactRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 0.5, gap: 10 },
  contactAvatar: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  contactName: { fontSize: 14, fontWeight: '600' },
  actionBtns: { flexDirection: 'row', gap: 6 },
  actionBtn: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  manualAddBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, marginTop: 12 },
  dialDisplay: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, marginBottom: 4 },
  dialNumber: { fontSize: 24, fontWeight: '300', letterSpacing: 2 },
  keypadGrid: { paddingHorizontal: 16, marginBottom: 8 },
  keypadRow: { flexDirection: 'row', justifyContent: 'center', gap: 14, marginBottom: 8 },
  keypadKey: { width: 64, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  keypadKeyText: { fontSize: 22, fontWeight: '500' },
  dialBtn: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', alignSelf: 'center' },
  // Send Card
  cardTypeRow: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 14, borderBottomWidth: 0.5 },
  cardTypeIcon: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardTypeLabel: { flex: 1, fontSize: 16, fontWeight: '600' },
});
