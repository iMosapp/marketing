import React, { useState, useCallback, useEffect } from 'react';
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
  const styles = getStyles(colors);
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
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q) || (c.phone || '').includes(q) || (c.email || '').toLowerCase().includes(q) || `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase().includes(q);
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
                  <Ionicons name="person-add" size={18} color={colors.text} />
                  <Text style={{ color: colors.text, fontSize: 14, fontWeight: '700' }}>Create New Contact</Text>
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
              /* Empty state  - show add options */
              <View style={{ flex: 1 }}>
                <TouchableOpacity style={[styles.manualAddBtn, { backgroundColor: colors.accent, marginTop: 8 }]} onPress={() => { onClose(); router.push('/contact/new' as any); }} data-testid="manual-add-contact-main">
                  <Ionicons name="add-circle" size={20} color={colors.text} />
                  <Text style={{ color: colors.text, fontSize: 15, fontWeight: '700' }}>New Contact</Text>
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
          /* ─── KEYPAD: iOS-native style dial pad + contact matching ─── */
          <View style={{ flex: 1, backgroundColor: colors.bg }}>
            {/* Number Display */}
            <View style={{ alignItems: 'center', paddingHorizontal: 24, paddingVertical: 8, minHeight: 52 }}>
              {dialNumber ? (
                <Text style={{ fontSize: dialNumber.length > 10 ? 30 : 38, fontWeight: '200', color: colors.text, letterSpacing: 1.5, fontVariant: ['tabular-nums'] as any }} numberOfLines={1} adjustsFontSizeToFit>
                  {(() => { const d = dialNumber.replace(/\D/g, ''); if (d.length <= 3) return d; if (d.length <= 6) return `${d.slice(0,3)}-${d.slice(3)}`; if (d.length <= 10) return `(${d.slice(0,3)}) ${d.slice(3,6)}-${d.slice(6)}`; return `+${d.slice(0,d.length-10)} (${d.slice(-10,-7)}) ${d.slice(-7,-4)}-${d.slice(-4)}`; })()}
                </Text>
              ) : (
                <Text style={{ fontSize: 38, fontWeight: '200', color: colors.text, opacity: 0 }}>{'\u00A0'}</Text>
              )}
            </View>

            {/* Contact Matches — fixed height slot so keypad never moves */}
            <View style={{ height: 84, marginHorizontal: 24, justifyContent: 'flex-start' }}>
              {dialNumber.length >= 3 && (() => {
                const digits = dialNumber.replace(/\D/g, '');
                const matches = contacts.filter(c => (c.phone || '').replace(/\D/g, '').includes(digits)).slice(0, 2);
                if (matches.length === 0) return null;
                const fmtPhone = (p: string) => { const d = (p||'').replace(/\D/g,''); if (d.length===11&&d[0]==='1') return `(${d.slice(1,4)}) ${d.slice(4,7)}-${d.slice(7)}`; if (d.length===10) return `(${d.slice(0,3)}) ${d.slice(3,6)}-${d.slice(6)}`; return p; };
                return (
                  <View style={{ backgroundColor: colors.card, borderRadius: 10, overflow: 'hidden' }}>
                    {matches.map((item: any, i: number) => (
                      <TouchableOpacity key={item._id} style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, height: 40, borderTopWidth: i > 0 ? 0.5 : 0, borderTopColor: colors.border }} onPress={() => logAndDial(item.phone, item)}>
                        <Ionicons name="person-circle" size={18} color={colors.textSecondary} style={{ marginRight: 8 }} />
                        <Text style={{ fontSize: 14, fontWeight: '400', color: colors.text, marginRight: 6 }} numberOfLines={1}>
                          {`${item.first_name || ''} ${item.last_name || ''}`.trim().length > 14 ? `${item.first_name || ''} ${item.last_name || ''}`.trim().slice(0,12)+'...' : `${item.first_name || ''} ${item.last_name || ''}`.trim()}
                        </Text>
                        <Text style={{ fontSize: 14, color: colors.textSecondary, flex: 1 }} numberOfLines={1}>{fmtPhone(item.phone)}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                );
              })()}
            </View>

            {/* Dial Pad — always in the same position */}
            <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: 24 }}>
              {[['1','','2','ABC','3','DEF'],['4','GHI','5','JKL','6','MNO'],['7','PQRS','8','TUV','9','WXYZ'],['*','',  '0','+','#','']].map((row, ri) => (
                <View key={ri} style={{ flexDirection: 'row', justifyContent: 'space-around', marginBottom: 14 }}>
                  {[0, 2, 4].map(ci => (
                    <TouchableOpacity key={row[ci]} style={{ width: 76, height: 76, borderRadius: 38, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' }} onPress={() => setDialNumber(d => d + row[ci])}>
                      <Text style={{ fontSize: 30, fontWeight: '400', color: colors.text, lineHeight: 34 }}>{row[ci]}</Text>
                      {row[ci+1] ? <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 1.5, marginTop: -1 }}>{row[ci+1]}</Text> : null}
                    </TouchableOpacity>
                  ))}
                </View>
              ))}

              {/* Bottom Row: [empty] | Call | Backspace */}
              <View style={{ flexDirection: 'row', justifyContent: 'space-around', alignItems: 'center', marginTop: 2 }}>
                <View style={{ width: 76, height: 76 }} />
                <TouchableOpacity style={{ width: 76, height: 76, borderRadius: 38, backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center', opacity: dialNumber ? 1 : 0.4 }} onPress={() => logAndDial(dialNumber)} disabled={!dialNumber}>
                  <Ionicons name="call" size={32} color="#FFF" />
                </TouchableOpacity>
                {dialNumber ? (
                  <TouchableOpacity style={{ width: 76, height: 76, borderRadius: 38, alignItems: 'center', justifyContent: 'center' }} onPress={() => setDialNumber(d => d.slice(0, -1))} onLongPress={() => setDialNumber('')}>
                    <Ionicons name="backspace-outline" size={26} color={colors.text} />
                  </TouchableOpacity>
                ) : (
                  <View style={{ width: 76, height: 76 }} />
                )}
              </View>
            </View>
            <View style={{ height: 8 }} />
          </View>
        )}
      </SafeAreaView>
    </Modal>
  );
}

// ─── Main Home Screen ─────────────────────────────────────────────
export default function HomeScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [pendingTasks, setPendingTasks] = useState<any[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [taskSummary, setTaskSummary] = useState<any>(null);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);
  const [seoScore, setSeoScore] = useState<any>(null);

  // Modals
  const [showContactAction, setShowContactAction] = useState(false);
  const [contactActionMode, setContactActionMode] = useState<'search' | 'keypad'>('search');
  const [showSendCard, setShowSendCard] = useState(false);
  const [sendCardStep, setSendCardStep] = useState<'type' | 'contact'>('type');
  const [selectedCardType, setSelectedCardType] = useState('');
  const [cardContacts, setCardContacts] = useState<any[]>([]);
  const [cardSearch, setCardSearch] = useState('');
  const [cardContactsLoading, setCardContactsLoading] = useState(false);

  // Contact picker for quick actions (share card, review, showcase → contact record)
  const [showActionPicker, setShowActionPicker] = useState(false);
  const [pendingAction, setPendingAction] = useState('');
  const [actionPickerTitle, setActionPickerTitle] = useState('');
  const [actionContacts, setActionContacts] = useState<any[]>([]);
  const [actionSearch, setActionSearch] = useState('');
  const [actionContactsLoading, setActionContactsLoading] = useState(false);

  // Universal share modals
  const [shareConfig, setShareConfig] = useState<{ visible: boolean; title: string; subtitle: string; url: string; text?: string; showPreview: boolean; previewUrl?: string; showQR: boolean; eventType: string }>({
    visible: false, title: '', subtitle: '', url: '', showPreview: true, showQR: false, eventType: '',
  });

  useFocusEffect(
    useCallback(() => {
      if (user?._id) { loadRecentActivity(); loadPendingTasks(); loadTaskSummary(); loadStoreSlug(); loadSeoScore(); }
    }, [user?._id])
  );

  // Auto-refresh activity feed and tasks every 30 seconds
  useEffect(() => {
    if (!user?._id) return;
    const interval = setInterval(() => { loadRecentActivity(); loadPendingTasks(); loadTaskSummary(); }, 30000);
    return () => clearInterval(interval);
  }, [user?._id]);

  const loadStoreSlug = async () => {
    if (user?.store_slug) { setStoreSlug(user.store_slug); return; }
    if (user?.store_id) {
      try {
        const res = await api.get(`/admin/stores/${user.store_id}`, { headers: { 'X-User-ID': user._id } });
        setStoreSlug(res.data?.slug || res.data?.name?.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
      } catch {}
    }
  };

  // Relative time helper + auto-refresh
  const getRelativeTime = useCallback((timestamp: string) => {
    const now = Date.now();
    const then = new Date(timestamp).getTime();
    const diffMs = now - then;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay}d ago`;
    return new Date(timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' });
  }, []);

  // Auto-refresh activity timestamps every 60 seconds
  const [, setTickRefresh] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTickRefresh(t => t + 1), 60000);
    return () => clearInterval(timer);
  }, []);

  const loadRecentActivity = async () => {
    if (!user?._id) return;
    try { setLoadingActivity(true); const res = await api.get(`/activity/${user._id}?limit=10`); setRecentActivity(res.data.activities || []); } catch {} finally { setLoadingActivity(false); }
  };

  const loadPendingTasks = async () => {
    if (!user?._id) return;
    try {
      setLoadingTasks(true);
      const res = await api.get(`/tasks/${user._id}?filter=today`);
      const tasks = Array.isArray(res.data) ? res.data : [];
      // Sort by priority_order ascending, then due_date
      const sorted = tasks.sort((a: any, b: any) => (a.priority_order || 3) - (b.priority_order || 3) || new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
      setPendingTasks(sorted);
    } catch {} finally { setLoadingTasks(false); }
  };

  const loadTaskSummary = async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/tasks/${user._id}/summary`);
      setTaskSummary(res.data);
    } catch {}
  };

  const loadSeoScore = async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/seo/health-score/${user._id}`);
      setSeoScore(res.data);
    } catch {}
  };

  const completeTask = async (taskId: string) => {
    if (!user?._id) return;
    try {
      await api.put(`/tasks/${user._id}/${taskId}`, { completed: true });
      setPendingTasks(prev => prev.filter(t => (t._id || t.id) !== taskId));
    } catch {}
  };

  const getTaskIcon = (task: any) => {
    if (task.channel === 'email') return { icon: 'mail', color: '#AF52DE' };
    if (task.channel === 'sms') return { icon: 'chatbubble', color: '#007AFF' };
    if (task.type === 'callback' || task.type === 'call') return { icon: 'call', color: '#32ADE6' };
    if (task.type === 'follow_up') return { icon: 'arrow-redo', color: '#FF9500' };
    if (task.type === 'appointment') return { icon: 'calendar', color: '#34C759' };
    if (task.type === 'date_trigger') return { icon: 'gift', color: '#C9A962' };
    if (task.source === 'campaign') return { icon: 'rocket', color: '#AF52DE' };
    return { icon: 'checkmark-circle', color: '#FF9500' };
  };

  // Send a Card  - contact search helpers
  const loadCardContacts = async () => {
    if (!user?._id) return;
    setCardContactsLoading(true);
    try { const data = await contactsAPI.getAll(user._id); setCardContacts(data || []); } catch {}
    setCardContactsLoading(false);
  };

  // Action picker — load contacts for quick actions
  const loadActionContacts = async () => {
    if (!user?._id) return;
    setActionContactsLoading(true);
    try { const data = await contactsAPI.getAll(user._id); setActionContacts(data || []); } catch {}
    setActionContactsLoading(false);
  };

  const openActionPicker = (actionKey: string, title: string) => {
    setPendingAction(actionKey);
    setActionPickerTitle(title);
    setActionSearch('');
    setShowActionPicker(true);
    loadActionContacts();
  };

  const handleActionContactSelect = (contact: any) => {
    setShowActionPicker(false);
    const contactId = contact._id || contact.id;
    router.push(`/contact/${contactId}?action=${pendingAction}` as any);
  };

  const filteredActionContacts = actionContacts.filter(c => {
    const q = actionSearch.toLowerCase();
    if (!q) return true;
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q) || (c.phone || '').includes(q) || (c.email || '').toLowerCase().includes(q) || `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase().includes(q);
  });

  const filteredCardContacts = cardContacts.filter(c => {
    const q = cardSearch.toLowerCase();
    if (!q) return true;
    return (c.first_name || '').toLowerCase().includes(q) || (c.last_name || '').toLowerCase().includes(q) || (c.phone || '').includes(q) || (c.email || '').toLowerCase().includes(q) || `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase().includes(q);
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
    const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';

    switch (tile) {
      case 'share-card':
        setShareConfig({
          visible: true,
          title: 'Share My Card',
          subtitle: 'Choose how to share your digital card',
          url: `${baseUrl}/card/${userId}`,
          text: `Check out my digital business card: ${baseUrl}/card/${userId}`,
          showPreview: true,
          previewUrl: `${baseUrl}/card/${userId}`,
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
      digital_card_sent: { icon: 'card', color: '#C9A962' },
      review_invite_sent: { icon: 'star', color: '#FFD60A' },
      review_request_sent: { icon: 'star', color: '#FFD60A' },
      congrats_card: { icon: 'gift', color: '#C9A962' },
      congrats_card_sent: { icon: 'gift', color: '#C9A962' },
      birthday_card_sent: { icon: 'gift', color: '#FF9500' },
      thank_you_card_sent: { icon: 'thumbs-up', color: '#34C759' },
      thankyou_card_sent: { icon: 'thumbs-up', color: '#34C759' },
      holiday_card_sent: { icon: 'snow', color: '#5AC8FA' },
      welcome_card_sent: { icon: 'hand-left', color: '#007AFF' },
      anniversary_card_sent: { icon: 'heart', color: '#FF2D55' },
      showroom_shared: { icon: 'storefront', color: '#34C759' },
      showcase_shared: { icon: 'storefront', color: '#34C759' },
      vcard_sent: { icon: 'person-circle', color: '#007AFF' },
      note_updated: { icon: 'document-text', color: '#FF9F0A' },
      link_page_shared: { icon: 'link', color: '#32ADE6' },
    };
    return map[type] || { icon: 'ellipse', color: colors.textSecondary };
  };

  const TILES = [
    { key: 'share-card', icon: 'card-outline', label: 'Share My Card', color: '#007AFF', onPress: () => router.push('/quick-send/digitalcard' as any) },
    { key: 'share-review', icon: 'star-outline', label: 'Review Link', color: '#FFD60A', onPress: () => router.push('/quick-send/review' as any) },
    { key: 'send-card', icon: 'gift-outline', label: 'Send a Card', color: '#C9A962', onPress: () => router.push('/quick-send/congrats' as any) },
    { key: 'showroom', icon: 'storefront-outline', label: 'My Showcase', color: '#34C759', onPress: () => router.push('/quick-send/showcase' as any) },
    { key: 'keypad', icon: 'keypad-outline', label: 'Keypad', color: '#32ADE6', onPress: () => { setContactActionMode('keypad'); setShowContactAction(true); } },
    { key: 'add-contact', icon: 'person-add-outline', label: 'Add Contact', color: '#AF52DE', onPress: () => router.push('/contact/new' as any) },
  ];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <View style={{ width: 32 }} />
        <Text style={[styles.userName, { color: colors.text }]}>Home</Text>
        <NotificationBell />
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.tilesGrid} data-testid="home-tiles-grid">
          {TILES.map((tile) => (
            <TouchableOpacity key={tile.key} style={[styles.tile, { backgroundColor: colors.card, borderColor: colors.border }]} onPress={tile.onPress} activeOpacity={0.7} data-testid={`home-tile-${tile.key}`}>
              <View style={[styles.tileIconWrap, { backgroundColor: `${tile.color}18` }]}>
                <Ionicons name={tile.icon as any} size={24} color={tile.color} />
              </View>
              <Text style={[styles.tileLabel, { color: colors.text }]}>{tile.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* ===== YOUR DAY SECTION ===== */}
        <View style={styles.activitySection} data-testid="your-day-section">
          <View style={styles.activityHeader}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Your Day</Text>
          </View>

          {/* Today's Touchpoints Tile */}
          <TouchableOpacity
            onPress={() => router.push('/(tabs)/touchpoints?period=today' as any)}
            activeOpacity={0.85}
            style={{ backgroundColor: colors.card, borderRadius: 14, padding: 18, borderWidth: 1, borderColor: colors.border, marginBottom: 12 }}
            data-testid="touchpoints-tile"
          >
            {/* Title row */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(201,169,98,0.12)', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="checkbox-outline" size={22} color={colors.accent} />
                </View>
                <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Today's Touchpoints</Text>
              </View>
              <View style={{ backgroundColor: 'rgba(201,169,98,0.12)', paddingVertical: 4, paddingHorizontal: 10, borderRadius: 8 }}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: colors.accent }}>{taskSummary?.pending_today || pendingTasks.length} pending</Text>
              </View>
            </View>

            {/* Mini Scoreboard */}
            <View style={{ flexDirection: 'row', gap: 6, marginBottom: 14 }}>
              {[
                { label: 'CALLS', color: '#007AFF', val: taskSummary?.activity?.calls || 0 },
                { label: 'TEXTS', color: '#34C759', val: taskSummary?.activity?.texts || 0 },
                { label: 'EMAILS', color: '#5AC8FA', val: taskSummary?.activity?.emails || 0 },
                { label: 'CARDS', color: '#C9A962', val: taskSummary?.activity?.cards || 0 },
                { label: 'CLICKS', color: '#FF375F', val: taskSummary?.activity?.clicks || 0 },
                { label: 'LEADS', color: '#32ADE6', val: taskSummary?.activity?.new_leads || 0 },
              ].map(s => (
                <View key={s.label} style={{ flex: 1, alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 2 }}>
                  <Text style={{ fontSize: 20, fontWeight: '700', color: s.color }}>{s.val}</Text>
                  <Text style={{ fontSize: 9, color: colors.textSecondary, fontWeight: '600', letterSpacing: 0.5, marginTop: 1 }}>{s.label}</Text>
                </View>
              ))}
            </View>

            {/* Progress */}
            <View style={{ backgroundColor: colors.border, borderRadius: 5, height: 6, overflow: 'hidden', marginBottom: 6 }}>
              <View style={{ height: '100%', backgroundColor: colors.accent, borderRadius: 5, width: `${taskSummary?.progress_pct || 0}%` }} />
            </View>
            <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginBottom: 12 }}>
              {taskSummary?.completed_today || 0} of {taskSummary?.total_today || 0} touchpoints completed
            </Text>

            {/* Top 3 task previews */}
            {pendingTasks.slice(0, 3).map((task, idx) => {
              const ti = getTaskIcon(task);
              const dueDate = task.due_date ? new Date(task.due_date) : null;
              const isOverdue = dueDate && dueDate.getTime() < Date.now() && new Date().setHours(0,0,0,0) > dueDate.getTime();
              const badgeLabel = isOverdue ? 'High' : task.source === 'campaign' ? 'Campaign' : task.type === 'birthday' ? 'Birthday' : task.type === 'anniversary' ? 'Anniversary' : task.priority === 'high' ? 'High' : '';
              const badgeColor = isOverdue ? '#FF3B30' : task.source === 'campaign' ? '#AF52DE' : task.type === 'birthday' ? '#34C759' : task.priority === 'high' ? '#FF9500' : '#8E8E93';
              return (
                <View key={task._id || idx} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }}>
                  <View style={{ width: 28, height: 28, borderRadius: 8, backgroundColor: `${ti.color}18`, alignItems: 'center', justifyContent: 'center' }}>
                    <Ionicons name={ti.icon as any} size={14} color={ti.color} />
                  </View>
                  <Text style={{ fontSize: 13, color: '#ccc', flex: 1 }} numberOfLines={1}>{task.title}</Text>
                  {badgeLabel ? (
                    <View style={{ backgroundColor: `${badgeColor}18`, paddingVertical: 2, paddingHorizontal: 6, borderRadius: 4 }}>
                      <Text style={{ fontSize: 10, fontWeight: '600', color: badgeColor }}>{badgeLabel}</Text>
                    </View>
                  ) : null}
                </View>
              );
            })}
            {pendingTasks.length === 0 && !loadingTasks && (
              <Text style={{ fontSize: 13, color: colors.textTertiary, textAlign: 'center', paddingVertical: 8 }}>No touchpoints for today</Text>
            )}
            {loadingTasks && pendingTasks.length === 0 && (
              <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 4 }} />
            )}
          </TouchableOpacity>

          {/* Activity Feed tile — demoted to smaller card */}

          {/* ===== SEO HEALTH WIDGET ===== */}
          {seoScore && (
            <TouchableOpacity
              onPress={() => router.push('/seo-health')}
              activeOpacity={0.85}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: colors.card, borderRadius: 14, padding: 14, paddingHorizontal: 18, borderWidth: 1, borderColor: colors.border, marginBottom: 12 }}
              data-testid="seo-health-widget"
            >
              <View style={{ width: 48, height: 48, borderRadius: 24, borderWidth: 3, borderColor: seoScore.grade_color, alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ fontSize: 16, fontWeight: '900', color: seoScore.grade_color }}>{seoScore.total_score}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>SEO Health</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{seoScore.grade}{seoScore.tips?.length > 0 ? ` \u00B7 ${seoScore.tips.length} tips to improve` : ''}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#48484A" />
            </TouchableOpacity>
          )}

          {/* Activity Feed tile */}
        </View>
      </ScrollView>

      {/* Universal Share Modal  - used by Share My Card, Review Link, Showcase */}
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

      {/* Action Picker — Pick a contact then navigate to their record to complete the action */}
      <Modal visible={showActionPicker} animationType="slide" transparent={false}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
            <TouchableOpacity onPress={() => setShowActionPicker(false)} style={{ padding: 4 }} data-testid="action-picker-back-btn">
              <Ionicons name="chevron-back" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' }}>
              {actionPickerTitle}
            </Text>
            <View style={{ width: 32 }} />
          </View>

          <Text style={{ color: colors.textSecondary, fontSize: 13, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 }}>Select a contact to send to</Text>
          <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
            <TextInput
              style={{ backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15, color: colors.text }}
              placeholder="Search contacts..."
              placeholderTextColor={colors.textTertiary}
              value={actionSearch}
              onChangeText={setActionSearch}
              data-testid="action-picker-search"
            />
          </View>

          {actionContactsLoading ? (
            <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 20 }} />
          ) : (
            <FlatList
              data={filteredActionContacts}
              keyExtractor={(item) => item._id}
              style={{ flex: 1, paddingHorizontal: 16 }}
              renderItem={({ item }) => {
                const name = `${item.first_name || ''} ${item.last_name || ''}`.trim() || item.phone || 'Unknown';
                const initials = `${(item.first_name || '?')[0]}${(item.last_name || '')[0] || ''}`.toUpperCase();
                return (
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 0.5, borderBottomColor: colors.border, gap: 10 }}
                    onPress={() => handleActionContactSelect(item)}
                    data-testid={`action-contact-${item._id}`}
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
                  {actionSearch ? 'No contacts found' : 'No contacts yet'}
                </Text>
              }
            />
          )}
        </SafeAreaView>
      </Modal>

      {/* Send a Card  - Step 1: Template Picker, Step 2: Contact Search */}
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
                <Text style={{ color: colors.accent, fontSize: 14, fontWeight: '600' }}>Skip  - create without selecting a contact</Text>
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

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, zIndex: 10000, position: 'relative' },
  userName: { fontSize: 18, fontWeight: '700' },
  scroll: { flex: 1, zIndex: 1 },
  scrollContent: { padding: 16, paddingBottom: 0 },
  tilesGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  tile: { width: '48%', flexBasis: '47%', flexGrow: 1, borderRadius: 14, padding: 14, alignItems: 'center', justifyContent: 'center', borderWidth: 1, minHeight: 88 },
  tileIconWrap: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
  tileLabel: { fontSize: 12, fontWeight: '700', textAlign: 'center' },
  activitySection: { marginTop: 16 },
  activityHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '700' },
  viewAll: { fontSize: 13, fontWeight: '600' },
  emptyActivity: { borderRadius: 14, padding: 24, alignItems: 'center', borderWidth: 1 },
  emptyText: { fontSize: 13, marginTop: 10, textAlign: 'center', lineHeight: 20 },
  activityItem: { flexDirection: 'row', alignItems: 'center', padding: 18, borderRadius: 14, marginBottom: 10, borderWidth: 1 },
  activityIconWrap: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 14 },
  activityContent: { flex: 1 },
  activityMsg: { fontSize: 15, fontWeight: '600', lineHeight: 20 },
  activityTime: { fontSize: 13, marginTop: 3 },
  taskItem: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 14, marginBottom: 8, borderWidth: 1 },
  taskDoneBtn: { padding: 4, marginLeft: 8 },
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
