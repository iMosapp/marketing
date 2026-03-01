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
  const vcfInputRef = React.useRef<HTMLInputElement>(null);

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
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q);
  });

  // VCF file upload handler
  const handleVcfUpload = () => {
    if (IS_WEB && vcfInputRef.current) {
      vcfInputRef.current.click();
    } else {
      goToImportFromPhone();
    }
  };

  const parseVcf = (text: string) => {
    const cards: any[] = [];
    const vcards = text.split('BEGIN:VCARD');
    for (const vc of vcards) {
      if (!vc.trim()) continue;
      const lines = vc.split('\n').map(l => l.trim());
      const contact: any = {};
      for (const line of lines) {
        if (line.startsWith('FN:')) contact.name = line.substring(3);
        if (line.startsWith('N:')) {
          const parts = line.substring(2).split(';');
          contact.last_name = parts[0] || '';
          contact.first_name = parts[1] || '';
        }
        if (line.startsWith('TEL') && line.includes(':')) contact.phone = line.split(':').pop() || '';
        if (line.startsWith('EMAIL') && line.includes(':')) contact.email = line.split(':').pop() || '';
      }
      if (contact.first_name || contact.name || contact.phone) {
        if (!contact.first_name && contact.name) {
          const parts = contact.name.split(' ');
          contact.first_name = parts[0] || '';
          contact.last_name = parts.slice(1).join(' ') || '';
        }
        cards.push(contact);
      }
    }
    return cards;
  };

  const onVcfSelected = async (e: any) => {
    const file = e.target?.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = parseVcf(text);
      if (parsed.length === 0) {
        showSimpleAlert('No Contacts', 'Could not find any contacts in this file.');
        return;
      }
      // Import each contact
      let imported = 0;
      for (const c of parsed) {
        try {
          await api.post(`/contacts/${userId}`, {
            first_name: c.first_name || '',
            last_name: c.last_name || '',
            phone: c.phone || '',
            email: c.email || '',
            source: 'vcf_import',
          });
          imported++;
        } catch {}
      }
      showSimpleAlert('Imported!', `${imported} contact${imported !== 1 ? 's' : ''} imported successfully.`);
      loadContacts();
    } catch {
      showSimpleAlert('Error', 'Could not read the contact file.');
    }
    if (vcfInputRef.current) vcfInputRef.current.value = '';
  };

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
    <Modal visible={visible} animationType="slide" transparent={false}>
      <SafeAreaView style={[{ flex: 1, backgroundColor: colors.bg }]} edges={['top']}>
        {/* Clean header */}
        <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
          <TouchableOpacity onPress={onClose} style={{ padding: 4 }} data-testid="close-action-modal">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' }}>{initialMode === 'keypad' ? 'Keypad' : 'Add Contact'}</Text>
          <View style={{ width: 32 }} />
        </View>

        {initialMode === 'search' ? (
          /* ─── ADD CONTACT: Search first, then act ─── */
          <View style={{ flex: 1, paddingHorizontal: 16, paddingTop: 12 }}>
            {/* Search bar + Add buttons always visible */}
            <TextInput style={[styles.searchInput, { backgroundColor: colors.searchBg, color: colors.text, borderColor: colors.border }]} placeholder="Search name or phone..." placeholderTextColor={colors.textTertiary} value={search} onChangeText={setSearch} autoFocus data-testid="contact-search-input" />

            {search.trim().length > 0 && filtered.length === 0 && (
              <View style={{ gap: 8, marginBottom: 8 }}>
                <TouchableOpacity style={[styles.manualAddBtn, { backgroundColor: colors.accent }]} onPress={() => { onClose(); router.push('/contact/new' as any); }} data-testid="manual-add-contact">
                  <Ionicons name="person-add" size={18} color="#000" />
                  <Text style={{ color: '#000', fontSize: 14, fontWeight: '700' }}>Create New Contact</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.importPhoneBtn, { borderColor: colors.border }]} onPress={handleVcfUpload} data-testid="import-vcf">
                  <Ionicons name="document-outline" size={18} color={colors.accent} />
                  <Text style={{ color: colors.accent, fontSize: 14, fontWeight: '600' }}>Upload Contact File (.vcf)</Text>
                </TouchableOpacity>
              </View>
            )}

            {loading ? <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} /> : search.trim().length > 0 ? (
              /* Scrollable search results */
              <FlatList data={filtered.slice(0, 20)} keyExtractor={(item) => item._id} style={{ flex: 1 }}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={[styles.contactRow, { borderBottomColor: colors.border }]}
                    onPress={() => { onClose(); router.push(`/contact/${item._id}` as any); }}
                    data-testid={`contact-row-${item._id}`}
                  >
                    <View style={[styles.contactAvatar, { backgroundColor: `${colors.accent}20` }]}>
                      <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 16 }}>{(item.first_name || '?')[0].toUpperCase()}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.contactName, { color: colors.text }]}>{item.first_name} {item.last_name || ''}</Text>
                      <Text style={{ color: colors.textTertiary, fontSize: 12 }}>{item.phone || item.email || ''}</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
                  </TouchableOpacity>
                )}
                ListEmptyComponent={
                  <View style={{ alignItems: 'center', marginTop: 30 }}>
                    <Ionicons name="person-outline" size={40} color={colors.textTertiary} style={{ marginBottom: 8 }} />
                    <Text style={{ color: colors.textSecondary, fontSize: 15, fontWeight: '600', marginBottom: 4 }}>No matches found</Text>
                    <Text style={{ color: colors.textTertiary, fontSize: 13 }}>Create a new contact or import from a file</Text>
                  </View>
                }
              />
            ) : (
              /* Empty state — show add options */
              <View style={{ flex: 1 }}>
                <TouchableOpacity style={[styles.manualAddBtn, { backgroundColor: colors.accent, marginTop: 8 }]} onPress={() => { onClose(); router.push('/contact/new' as any); }} data-testid="manual-add-contact-main">
                  <Ionicons name="add-circle" size={20} color="#000" />
                  <Text style={{ color: '#000', fontSize: 15, fontWeight: '700' }}>New Contact</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.importPhoneBtn, { borderColor: colors.border, marginTop: 8 }]} onPress={handleVcfUpload} data-testid="import-vcf-main">
                  <Ionicons name="document-outline" size={18} color={colors.accent} />
                  <Text style={{ color: colors.accent, fontSize: 14, fontWeight: '600' }}>Upload Contact File (.vcf)</Text>
                </TouchableOpacity>

                {/* Recent contacts */}
                <Text style={{ color: colors.textTertiary, fontSize: 11, fontWeight: '600', letterSpacing: 1, marginTop: 20, marginBottom: 8 }}>RECENT CONTACTS</Text>
                <FlatList data={contacts.slice(0, 10)} keyExtractor={(item) => item._id} style={{ flex: 1 }}
                  renderItem={({ item }) => (
                    <TouchableOpacity
                      style={[styles.contactRow, { borderBottomColor: colors.border }]}
                      onPress={() => { onClose(); router.push(`/contact/${item._id}` as any); }}
                    >
                      <View style={[styles.contactAvatar, { backgroundColor: `${colors.accent}20` }]}>
                        <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 16 }}>{(item.first_name || '?')[0].toUpperCase()}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.contactName, { color: colors.text }]}>{item.first_name} {item.last_name || ''}</Text>
                        <Text style={{ color: colors.textTertiary, fontSize: 12 }}>{item.phone || item.email || ''}</Text>
                      </View>
                      <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
                    </TouchableOpacity>
                  )}
                />
              </View>
            )}

            {/* Hidden file input for vcf */}
            {IS_WEB && <input ref={vcfInputRef as any} type="file" accept=".vcf,text/vcard" style={{ display: 'none' }} onChange={onVcfSelected as any} />}
          </View>
        ) : (
          /* ─── KEYPAD: Dial pad + contact matching ─── */
          <View style={{ flex: 1 }}>
            <View style={[styles.dialDisplay, { borderColor: colors.border }]}>
              <Text style={[styles.dialNumber, { color: dialNumber ? colors.text : colors.textTertiary }]}>{dialNumber || '\u00A0'}</Text>
              {dialNumber.length > 0 && <TouchableOpacity onPress={() => setDialNumber(d => d.slice(0, -1))}><Ionicons name="backspace-outline" size={22} color={colors.textSecondary} /></TouchableOpacity>}
            </View>

            {/* Matching contacts — scrollable, fixed height area above keypad */}
            <View style={{ height: 130, paddingHorizontal: 16 }}>
              {dialNumber.length >= 2 && (() => {
                const matches = contacts.filter(c => (c.phone || '').replace(/\D/g, '').includes(dialNumber.replace(/\D/g, '')));
                if (matches.length === 0) return null;
                return (
                  <FlatList
                    data={matches.slice(0, 5)}
                    keyExtractor={(item) => item._id}
                    style={{ flex: 1 }}
                    renderItem={({ item }) => (
                      <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 8, gap: 10 }} onPress={() => logAndDial(item.phone, item)}>
                        <View style={[styles.contactAvatar, { backgroundColor: `${colors.accent}20`, width: 34, height: 34 }]}>
                          <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 14 }}>{(item.first_name || '?')[0].toUpperCase()}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ color: colors.text, fontSize: 14, fontWeight: '600' }}>{item.first_name} {item.last_name || ''}</Text>
                          <Text style={{ color: colors.textTertiary, fontSize: 11 }}>{item.phone}</Text>
                        </View>
                        <Ionicons name="call" size={18} color="#34C759" />
                      </TouchableOpacity>
                    )}
                  />
                );
              })()}
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
          </View>
        )}
      </SafeAreaView>
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
  const [showContactAction, setShowContactAction] = useState(false);
  const [contactActionMode, setContactActionMode] = useState<'search' | 'keypad'>('search');
  const [showSendCard, setShowSendCard] = useState(false);
  const [sendCardStep, setSendCardStep] = useState<'type' | 'contact'>('type');
  const [selectedCardType, setSelectedCardType] = useState('');
  const [cardContacts, setCardContacts] = useState<any[]>([]);
  const [cardSearch, setCardSearch] = useState('');
  const [cardContactsLoading, setCardContactsLoading] = useState(false);

  // Universal share modals
  const [shareConfig, setShareConfig] = useState<{ visible: boolean; title: string; subtitle: string; url: string; text?: string; showPreview: boolean; previewUrl?: string; showQR: boolean; eventType: string }>({
    visible: false, title: '', subtitle: '', url: '', showPreview: true, showQR: false, eventType: '',
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

  // Send a Card — contact search helpers
  const loadCardContacts = async () => {
    if (!user?._id) return;
    setCardContactsLoading(true);
    try { const data = await contactsAPI.getAll(user._id); setCardContacts(data || []); } catch {}
    setCardContactsLoading(false);
  };

  const filteredCardContacts = cardContacts.filter(c => {
    const q = cardSearch.toLowerCase();
    if (!q) return true;
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q);
  });

  const handleCardTypeSelect = (cardKey: string) => {
    setSelectedCardType(cardKey);
    setSendCardStep('contact');
    setCardSearch('');
    loadCardContacts();
  };

  const handleCardContactSelect = (contact: any) => {
    setShowSendCard(false);
    setSendCardStep('type');
    const name = `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
    const params = new URLSearchParams();
    params.set('type', selectedCardType);
    if (name) params.set('prefillName', name);
    if (contact.phone) params.set('prefillPhone', contact.phone);
    if (contact.email) params.set('prefillEmail', contact.email);
    router.push(`/settings/create-card?${params.toString()}` as any);
  };

  const handleCardSkipContact = () => {
    setShowSendCard(false);
    setSendCardStep('type');
    router.push(`/settings/create-card?type=${selectedCardType}` as any);
  };

  // Open share modal for a tile
  const openShareModal = (tile: string) => {
    const userId = user?._id || '';
    const baseUrl = typeof window !== 'undefined' ? window.location.origin : 'https://app.imosapp.com';

    switch (tile) {
      case 'share-card':
        setShareConfig({
          visible: true,
          title: 'Share My Card',
          subtitle: 'Choose how to share your digital card',
          url: `${baseUrl}/p/${userId}`,
          text: `Check out my digital business card: ${baseUrl}/p/${userId}`,
          showPreview: true,
          previewUrl: `${baseUrl}/p/${userId}`,
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
          showPreview: true,
          previewUrl: `${baseUrl}/review/${storeSlug}?sp=${userId}`,
          showQR: true,
          eventType: 'review_invite_sent',
        });
        break;
      case 'showroom':
        setShareConfig({
          visible: true,
          title: 'Share My Showcase',
          subtitle: 'Show off your happy customers',
          url: `${baseUrl}/showcase/${userId}`,
          text: `Check out my showcase of happy customers: ${baseUrl}/showcase/${userId}`,
          showPreview: true,
          previewUrl: `${baseUrl}/showcase/${userId}`,
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
    { key: 'send-card', icon: 'gift-outline', label: 'Send a Card', color: '#C9A962', onPress: () => { setSendCardStep('type'); setShowSendCard(true); } },
    { key: 'showroom', icon: 'storefront-outline', label: 'My Showcase', color: '#34C759', onPress: () => openShareModal('showroom') },
    { key: 'keypad', icon: 'keypad-outline', label: 'Keypad', color: '#32ADE6', onPress: () => { setContactActionMode('keypad'); setShowContactAction(true); } },
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

      {/* Universal Share Modal — used by Share My Card, Review Link, Showcase */}
      <UniversalShareModal
        visible={shareConfig.visible}
        onClose={() => setShareConfig(c => ({ ...c, visible: false }))}
        title={shareConfig.title}
        subtitle={shareConfig.subtitle}
        shareUrl={shareConfig.url}
        shareText={shareConfig.text}
        showPreview={shareConfig.showPreview}
        previewUrl={shareConfig.previewUrl}
        showQR={shareConfig.showQR}
        vCardUserId={user?._id}
        userId={user?._id}
        eventType={shareConfig.eventType}
      />

      <ContactActionModal visible={showContactAction} onClose={() => setShowContactAction(false)} colors={colors} userId={user?._id || ''} initialMode={contactActionMode} />

      {/* Send a Card — Step 1: Template Picker, Step 2: Contact Search */}
      <Modal visible={showSendCard} animationType="slide" transparent={false}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
            <TouchableOpacity onPress={() => { if (sendCardStep === 'contact') { setSendCardStep('type'); } else { setShowSendCard(false); } }} style={{ padding: 4 }} data-testid="send-card-back-btn">
              <Ionicons name="chevron-back" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' }}>
              {sendCardStep === 'type' ? 'Send a Card' : 'Select Contact'}
            </Text>
            <View style={{ width: 32 }} />
          </View>

          {sendCardStep === 'type' ? (
            <>
              <Text style={{ color: colors.textSecondary, fontSize: 13, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 }}>Choose a card type to create and send</Text>
              <ScrollView style={{ flex: 1, paddingHorizontal: 16 }}>
                {[
                  { key: 'congrats', label: 'Congrats Card', icon: 'gift', color: '#C9A962' },
                  { key: 'birthday', label: 'Birthday Card', icon: 'balloon', color: '#FF2D55' },
                  { key: 'anniversary', label: 'Anniversary Card', icon: 'heart', color: '#FF6B6B' },
                  { key: 'thankyou', label: 'Thank You Card', icon: 'thumbs-up', color: '#34C759' },
                  { key: 'welcome', label: 'Welcome Card', icon: 'hand-left', color: '#007AFF' },
                  { key: 'holiday', label: 'Holiday Card', icon: 'snow', color: '#5AC8FA' },
                ].map((card) => (
                  <TouchableOpacity
                    key={card.key}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 14, borderBottomWidth: 0.5, borderBottomColor: colors.border }}
                    onPress={() => handleCardTypeSelect(card.key)}
                    data-testid={`card-type-${card.key}`}
                  >
                    <View style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: `${card.color}18`, alignItems: 'center', justifyContent: 'center' }}>
                      <Ionicons name={card.icon as any} size={24} color={card.color} />
                    </View>
                    <Text style={{ flex: 1, fontSize: 16, fontWeight: '600', color: colors.text }}>{card.label}</Text>
                    <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </>
          ) : (
            <>
              <View style={{ paddingHorizontal: 16, paddingTop: 12 }}>
                <TextInput
                  style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, fontSize: 15, color: colors.text, borderWidth: 1, borderColor: colors.border }}
                  placeholder="Search by name, phone, or email..."
                  placeholderTextColor={colors.textTertiary}
                  value={cardSearch}
                  onChangeText={setCardSearch}
                  autoFocus
                  data-testid="send-card-contact-search"
                />
              </View>
              <TouchableOpacity
                style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 12 }}
                onPress={handleCardSkipContact}
                data-testid="send-card-skip-contact"
              >
                <Ionicons name="arrow-forward-circle-outline" size={20} color={colors.accent} />
                <Text style={{ color: colors.accent, fontSize: 14, fontWeight: '600' }}>Skip — create without selecting a contact</Text>
              </TouchableOpacity>
              {cardContactsLoading ? (
                <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} />
              ) : (
                <FlatList
                  data={filteredCardContacts}
                  keyExtractor={(item) => item._id}
                  style={{ flex: 1, paddingHorizontal: 16 }}
                  renderItem={({ item }) => {
                    const name = `${item.first_name || ''} ${item.last_name || ''}`.trim() || item.phone || 'Unknown';
                    const initials = `${(item.first_name || '?')[0]}${(item.last_name || '')[0] || ''}`.toUpperCase();
                    return (
                      <TouchableOpacity
                        style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 0.5, borderBottomColor: colors.border, gap: 10 }}
                        onPress={() => handleCardContactSelect(item)}
                        data-testid={`card-contact-${item._id}`}
                      >
                        <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: `${colors.accent}20`, alignItems: 'center', justifyContent: 'center' }}>
                          <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 14 }}>{initials}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{name}</Text>
                          {item.phone ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>{item.phone}</Text> : null}
                        </View>
                        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                      </TouchableOpacity>
                    );
                  }}
                  ListEmptyComponent={
                    <Text style={{ textAlign: 'center', color: colors.textSecondary, marginTop: 24, fontSize: 14 }}>
                      {cardSearch ? 'No contacts found' : 'No contacts yet'}
                    </Text>
                  }
                />
              )}
            </>
          )}
        </SafeAreaView>
      </Modal>
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
  importPhoneBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 12, paddingHorizontal: 14, marginBottom: 8, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed' },
  contactRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 0.5, gap: 10 },
  contactAvatar: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  contactName: { fontSize: 14, fontWeight: '600' },
  actionBtns: { flexDirection: 'row', gap: 6 },
  actionBtn: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  manualAddBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, marginTop: 12 },
  // Keypad
  dialDisplay: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, marginBottom: 4 },
  dialNumber: { fontSize: 30, fontWeight: '300', letterSpacing: 2 },
  keypadGrid: { paddingHorizontal: 12, marginBottom: 12, flex: 1, justifyContent: 'center' },
  keypadRow: { flexDirection: 'row', justifyContent: 'center', gap: 16, marginBottom: 12 },
  keypadKey: { width: 88, height: 60, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  keypadKeyText: { fontSize: 28, fontWeight: '500' },
  dialBtn: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', alignSelf: 'center' },
});
