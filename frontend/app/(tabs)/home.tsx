import { ScreenErrorBoundary } from '../../components/ScreenErrorBoundary';
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
import { useContactSearch } from '../../hooks/useContactSearch';
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
  const [phoneMatches, setPhoneMatches] = useState<any[]>([]);
  const phoneSearchTimer = React.useRef<any>(null);
  const vcfInputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (visible) { setMode(initialMode); setSearch(''); setDialNumber(''); setPhoneMatches([]); loadContacts(); }
  }, [visible, initialMode]);

  // Live phone search — queries backend for ALL contacts, not just the local 50
  React.useEffect(() => {
    const digits = dialNumber.replace(/\D/g, '');
    if (digits.length < 4) { setPhoneMatches([]); return; }
    clearTimeout(phoneSearchTimer.current);
    phoneSearchTimer.current = setTimeout(async () => {
      try {
        // Use the main contacts search which supports partial phone number matching
        const res = await api.get(`/contacts/${userId}`, { params: { search: digits, limit: 3 } });
        const results = Array.isArray(res.data) ? res.data : (res.data?.contacts || []);
        // Filter to only contacts that have a phone matching the typed digits
        const phoneOnly = results.filter((c: any) => (c.phone || '').replace(/\D/g, '').includes(digits));
        setPhoneMatches(phoneOnly.slice(0, 3));
      } catch { setPhoneMatches([]); }
    }, 300);
  }, [dialNumber, userId]);

  const loadContacts = async () => {
    setLoading(true);
    try { const data = await contactsAPI.getAll(userId); setContacts(Array.isArray(data) ? data : (data?.contacts || [])); } catch {}
    setLoading(false);
  };

  useContactSearch(userId, search, setContacts, visible);

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
          <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' }}>{initialMode === 'keypad' ? 'Keypad' : 'Add Contact'}</Text>
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
                  <Text style={{ color: colors.text, fontSize: 16, fontWeight: '700' }}>Create New Contact</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.importPhoneBtn, { borderColor: colors.border }]} onPress={handleVcfUpload} data-testid="import-vcf">
                  <Ionicons name="document-outline" size={18} color={colors.accent} />
                  <Text style={{ color: colors.accent, fontSize: 16, fontWeight: '600' }}>Upload Contact File (.vcf)</Text>
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
                      <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 18 }}>{(item.first_name || '?')[0].toUpperCase()}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.contactName, { color: colors.text }]}>{item.first_name} {item.last_name || ''}</Text>
                      <Text style={{ color: colors.textTertiary, fontSize: 14 }}>{item.phone || item.email || ''}</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
                  </TouchableOpacity>
                )}
                ListEmptyComponent={
                  <View style={{ alignItems: 'center', marginTop: 30 }}>
                    <Ionicons name="person-outline" size={40} color={colors.textTertiary} style={{ marginBottom: 8 }} />
                    <Text style={{ color: colors.textSecondary, fontSize: 17, fontWeight: '600', marginBottom: 4 }}>No matches found</Text>
                    <Text style={{ color: colors.textTertiary, fontSize: 15 }}>Create a new contact or import from a file</Text>
                  </View>
                }
              />
            ) : (
              /* Empty state  - show add options */
              <View style={{ flex: 1 }}>
                <TouchableOpacity style={[styles.manualAddBtn, { backgroundColor: colors.accent, marginTop: 8 }]} onPress={() => { onClose(); router.push('/contact/new' as any); }} data-testid="manual-add-contact-main">
                  <Ionicons name="add-circle" size={20} color={colors.text} />
                  <Text style={{ color: colors.text, fontSize: 17, fontWeight: '700' }}>New Contact</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.importPhoneBtn, { borderColor: colors.border, marginTop: 8 }]} onPress={handleVcfUpload} data-testid="import-vcf-main">
                  <Ionicons name="document-outline" size={18} color={colors.accent} />
                  <Text style={{ color: colors.accent, fontSize: 16, fontWeight: '600' }}>Upload Contact File (.vcf)</Text>
                </TouchableOpacity>

                {/* Recent contacts */}
                <Text style={{ color: colors.textTertiary, fontSize: 13, fontWeight: '600', letterSpacing: 1, marginTop: 20, marginBottom: 8 }}>RECENT CONTACTS</Text>
                <FlatList data={contacts.slice(0, 10)} keyExtractor={(item) => item._id} style={{ flex: 1 }}
                  renderItem={({ item }) => (
                    <TouchableOpacity
                      style={[styles.contactRow, { borderBottomColor: colors.border }]}
                      onPress={() => { onClose(); router.push(`/contact/${item._id}` as any); }}
                    >
                      <View style={[styles.contactAvatar, { backgroundColor: `${colors.accent}20` }]}>
                        <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 18 }}>{(item.first_name || '?')[0].toUpperCase()}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.contactName, { color: colors.text }]}>{item.first_name} {item.last_name || ''}</Text>
                        <Text style={{ color: colors.textTertiary, fontSize: 14 }}>{item.phone || item.email || ''}</Text>
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

            {/* Contact Matches — live backend search across ALL contacts */}
            <View style={{ height: 84, marginHorizontal: 24, justifyContent: 'flex-start' }}>
              {dialNumber.length >= 4 && phoneMatches.length > 0 && (() => {
                const fmtPhone = (p: string) => { const d = (p||'').replace(/\D/g,''); if (d.length===11&&d[0]==='1') return `(${d.slice(1,4)}) ${d.slice(4,7)}-${d.slice(7)}`; if (d.length===10) return `(${d.slice(0,3)}) ${d.slice(3,6)}-${d.slice(6)}`; return p; };
                return (
                  <View style={{ backgroundColor: colors.card, borderRadius: 10, overflow: 'hidden' }}>
                    {phoneMatches.map((item: any, i: number) => (
                      <TouchableOpacity key={item._id || item.id} style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, height: 40, borderTopWidth: i > 0 ? 0.5 : 0, borderTopColor: colors.border }} onPress={() => logAndDial(item.phone, item)}>
                        <Ionicons name="person-circle" size={18} color={colors.textSecondary} style={{ marginRight: 8 }} />
                        <Text style={{ fontSize: 16, fontWeight: '400', color: colors.text, marginRight: 6 }} numberOfLines={1}>
                          {`${item.first_name || ''} ${item.last_name || ''}`.trim().slice(0, 16) || 'Contact'}
                        </Text>
                        <Text style={{ fontSize: 16, color: colors.textSecondary, flex: 1 }} numberOfLines={1}>{fmtPhone(item.phone)}</Text>
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
                      {row[ci+1] ? <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 1.5, marginTop: -1 }}>{row[ci+1]}</Text> : null}
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
function HomeScreen() {
  const { colors, themeMode, toggle: toggleTheme } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [pendingTasks, setPendingTasks] = useState<any[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [taskSummary, setTaskSummary] = useState<any>(null);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);
  const [seoScore, setSeoScore] = useState<any>(null);
  const [initialLoaded, setInitialLoaded] = useState(false);

  // New: home intelligence data
  const [streak, setStreak] = useState<any>(null);
  const [my3, setMy3] = useState<any[]>([]);
  const [winsFeed, setWinsFeed] = useState<any[]>([]);
  const [completedToday, setCompletedToday] = useState<Set<string>>(new Set());
  const [loadingMy3, setLoadingMy3] = useState(false);
  const [soldPerf, setSoldPerf] = useState<any>(null);
  const [hotOpps, setHotOpps] = useState<any[]>([]);

  // Modals
  const [showSharePicker, setShowSharePicker] = useState(false);

  // ── AI master switch (pauses all AI auto-replies) ──
  const [aiPaused, setAiPaused] = useState<boolean>(!!(user as any)?.ai_master_paused);
  useEffect(() => { setAiPaused(!!(user as any)?.ai_master_paused); }, [(user as any)?.ai_master_paused]);
  const toggleAiMaster = async () => {
    if (!user?._id) return;
    const next = !aiPaused;
    setAiPaused(next);
    try {
      await api.patch(`/users/${user._id}`, { ai_master_paused: next });
      useAuthStore.getState().updateUser({ ai_master_paused: next } as any);
    } catch {
      setAiPaused(!next);
      showSimpleAlert('Error', 'Could not update AI setting. Try again.');
    }
  };

  // ── Instant Card QR (header button + Card tile long-press) ──
  const openCardQR = () => {
    const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
    const cardUrl = `${baseUrl}/card/${user?._id}`;
    setShareConfig({ visible: true, title: 'Your Card QR', subtitle: 'Have them scan it — your card opens instantly', url: cardUrl, text: `My digital card: ${cardUrl}`, showPreview: false, showQR: true, startQR: true, eventType: 'card_qr_shown' });
  };

  // ── Add card QR to Apple/Google Wallet ──
  const handleAddToWallet = async () => {
    setShowSharePicker(false);
    if (!user?._id) return;
    try {
      const st = await api.get(`/wallet/${user._id}/status`);
      if (Platform.OS === 'android') {
        if (!st.data?.google) {
          showSimpleAlert('Almost Ready', 'Google Wallet passes need a one-time setup (wallet credentials). Ask us to finish the setup and this will light up.');
          return;
        }
        const r = await api.get(`/wallet/${user._id}/google-save-url`);
        if (r.data?.save_url) Linking.openURL(r.data.save_url);
        return;
      }
      if (!st.data?.apple) {
        showSimpleAlert('Almost Ready', 'Apple Wallet passes need a one-time certificate setup. Ask us to finish the setup and this will light up.');
        return;
      }
      const t = await api.post(`/wallet/${user._id}/download-token`);
      const url = `${api.defaults.baseURL}/wallet/download/${t.data.token}.pkpass`;
      if (IS_WEB && typeof window !== 'undefined') window.open(url, '_blank');
      else Linking.openURL(url);
    } catch {
      showSimpleAlert('Error', 'Could not create your wallet pass. Try again.');
    }
  };
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
  const [shareConfig, setShareConfig] = useState<{ visible: boolean; title: string; subtitle: string; url: string; text?: string; showPreview: boolean; previewUrl?: string; showQR: boolean; startQR?: boolean; eventType: string }>({
    visible: false, title: '', subtitle: '', url: '', showPreview: true, showQR: false, eventType: '',
  });

  useFocusEffect(
    useCallback(() => {
      if (user?._id) {
        loadAllData();
        // Stagger home intelligence 1s to avoid simultaneous OOM on server
        const t = setTimeout(() => loadHomeIntelligence(), 1000);
        // Always refresh sold performance when returning to home (e.g. after SOLD wizard)
        api.get(`/users/${user._id}/sold-performance`).then(r => setSoldPerf(r.data)).catch(() => {});
        return () => clearTimeout(t);
      }
    }, [user?._id])
  );

  // Auto-refresh every 60 seconds (was 30s) — halves server polling load
  useEffect(() => {
    if (!user?._id) return;
    const interval = setInterval(() => { loadAllData(true); loadHomeIntelligence(true); }, 60000);
    return () => clearInterval(interval);
  }, [user?._id]);

  const loadHomeIntelligence = async (silent = false) => {
    if (!user?._id) return;
    if (!silent) setLoadingMy3(true);
    try {
      const res = await api.get(`/home/${user._id}`);
      setStreak(res.data.streak);
      setMy3(res.data.my_3 || []);
      // Load sold performance stats
      api.get(`/users/${user._id}/sold-performance`).then(r => setSoldPerf(r.data)).catch(() => {});
      setWinsFeed(res.data.wins_feed || []);
      // Load hot opportunities (conversations with detected buying intent)
      api.get(`/messages/conversations/${user._id}?hot_only=true`)
        .then(r => {
          const all = Array.isArray(r.data) ? r.data : (r.data?.conversations || []);
          setHotOpps(all.filter((c: any) => c.hot_opportunity === true).slice(0, 5));
        }).catch(() => {});
    } catch { /* silent fail — not critical */ }
    finally { if (!silent) setLoadingMy3(false); }
  };

  const loadAllData = async (silent = false) => {
    if (!user?._id) return;
    if (!silent) setLoadingTasks(true);
    try {
      // Load sequentially in priority order — prevents simultaneous OOM on server
      // Activity + tasks first (most visible), then SEO score (least critical)
      const [actRes, taskRes, summRes] = await Promise.all([
        api.get(`/activity/${user._id}?limit=10`).catch(() => ({ data: { activities: [] } })),
        api.get(`/tasks/${user._id}?filter=today`).catch(() => ({ data: [] })),
        api.get(`/tasks/${user._id}/summary`).catch(() => ({ data: null })),
      ]);
      setRecentActivity(actRes.data.activities || []);
      const tasks = Array.isArray(taskRes.data) ? taskRes.data : [];
      setPendingTasks(tasks.sort((a: any, b: any) => (a.priority_order || 3) - (b.priority_order || 3) || new Date(a.due_date).getTime() - new Date(b.due_date).getTime()));
      setTaskSummary(summRes.data);

      // Stagger SEO score load by 2s — low priority, prevents request avalanche
      setTimeout(async () => {
        try {
          const seoRes = await api.get(`/seo/health-score/${user._id}`).catch(() => ({ data: null }));
          setSeoScore(seoRes.data);
        } catch {}
      }, 2000);

      // Load store slug (sync, not parallel — depends on user data)
      if (!storeSlug) {
        if (user?.store_slug) { setStoreSlug(user.store_slug); }
        else if (user?.store_id) {
          try {
            const sRes = await api.get(`/admin/stores/${user.store_id}`, { headers: { 'X-User-ID': user._id } });
            setStoreSlug(sRes.data?.slug || sRes.data?.name?.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
          } catch {}
        }
      }
    } finally {
      if (!silent) setLoadingTasks(false);
      setInitialLoaded(true);
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
    try { const data = await contactsAPI.getAll(user._id); setCardContacts(Array.isArray(data) ? data : (data?.contacts || [])); } catch {}
    setCardContactsLoading(false);
  };

  // Action picker — load contacts for quick actions
  const loadActionContacts = async () => {
    if (!user?._id) return;
    setActionContactsLoading(true);
    try { const data = await contactsAPI.getAll(user._id); setActionContacts(Array.isArray(data) ? data : (data?.contacts || [])); } catch {}
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
    if (pendingAction === 'voice') {
      // capture=true auto-starts the voice recorder on the contact page
      router.push(`/contact/${contactId}?capture=true` as any);
      return;
    }
    router.push(`/contact/${contactId}?action=${pendingAction}` as any);
  };

  useContactSearch(user?._id, actionSearch, setActionContacts, showActionPicker);
  useContactSearch(user?._id, cardSearch, setCardContacts, showSendCard);

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
    setShowSendCard(false);
    setSendCardStep('type');
    // Go straight to the card creator — no contact picker step
    // Recipient is optional on the create-card page (leave blank to just get a link)
    router.push(`/settings/create-card?type=${cardKey}&generic=true` as any);
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
    router.push(`/settings/create-card?type=${selectedCardType}&generic=true` as any);
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
    { key: 'sold',        icon: 'trophy',     label: 'SOLD!',       sublabel: 'Snap the moment & start campaign', color: '#C9A962', onPress: () => router.push('/sold-quick' as any) },
    { key: 'send-photo',  icon: 'camera',     label: 'Send Photo',  sublabel: 'Snap & text a photo — no sale needed', color: '#32ADE6', onPress: () => router.push('/quick-send/photo' as any) },
    { key: 'review',      icon: 'star',       label: 'Review',      sublabel: 'Ask for a 5-star review',          color: '#FF9500', onPress: () => router.push('/quick-send/review' as any) },
    { key: 'card',        icon: 'card',       label: 'Card',        sublabel: 'Send your digital card',           color: '#007AFF', onPress: () => setShowSharePicker(true), onLongPress: openCardQR },
    { key: 'voice-note',  icon: 'mic',        label: 'Voice Note',  sublabel: 'Record notes on a customer',       color: '#34C759', onPress: () => openActionPicker('voice', 'Voice Note — pick a person') },
    { key: 'new-contact', icon: 'person-add', label: 'New Contact', sublabel: 'Add someone new',                  color: '#AF52DE', onPress: () => router.push('/contact/new' as any) },
  ];

  // ── ONE clear next action, picked by priority ──
  const nextMove = (() => {
    if (hotOpps.length > 0) {
      const c: any = hotOpps[0];
      return {
        icon: 'flame', color: '#FF3B30',
        label: `Reply to ${c.contact_name || c.contact_phone || 'a hot lead'}`,
        sub: c.intent_signals?.[0] || 'High buying intent — strike while it\'s hot',
        btn: 'Open Chat',
        onPress: () => router.push(`/thread/${c._id}` as any),
      };
    }
    if ((taskSummary?.overdue || 0) > 0) {
      return {
        icon: 'alert-circle', color: '#FF9500',
        label: `Clear ${taskSummary.overdue} overdue touchpoint${taskSummary.overdue === 1 ? '' : 's'}`,
        sub: 'A quick text keeps them from going cold',
        btn: "Let's Go",
        onPress: () => router.push('/(tabs)/touchpoints?period=today' as any),
      };
    }
    const next3: any = my3.find((m: any) => !completedToday.has(m.contact_id));
    if (next3) {
      return {
        icon: next3.icon || 'chatbubble', color: next3.color || '#C9A962',
        label: `${next3.action_label || 'Text'} ${next3.first_name || ''}`.trim(),
        sub: next3.reason_label || '30 seconds, big impact',
        btn: 'Do It',
        onPress: () => {
          setCompletedToday(p => new Set([...p, next3.contact_id]));
          router.push(`/contact/${next3.contact_id}` as any);
        },
      };
    }
    if (pendingTasks.length > 0) {
      return {
        icon: 'checkbox', color: '#C9A962',
        label: 'Knock out today\'s touchpoints',
        sub: `${taskSummary?.pending_today || pendingTasks.length} waiting for you`,
        btn: 'Start',
        onPress: () => router.push('/(tabs)/touchpoints?period=today' as any),
      };
    }
    return {
      icon: 'star', color: '#C9A962',
      label: 'All caught up!',
      sub: 'Perfect time to ask a happy customer for a review',
      btn: 'Get Reviews',
      onPress: () => router.push('/quick-send/review' as any),
    };
  })();

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <View style={{ width: 32 }} />
        <Text style={[styles.userName, { color: colors.text }]}>Home</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          <TouchableOpacity
            onPress={openCardQR}
            activeOpacity={0.7}
            style={{ padding: 6 }}
            data-testid="header-qr-btn"
          >
            <Ionicons name="qr-code-outline" size={19} color={colors.textSecondary} />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={toggleAiMaster}
            activeOpacity={0.7}
            style={{
              flexDirection: 'row', alignItems: 'center', gap: 4,
              paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14,
              backgroundColor: aiPaused ? 'rgba(142,142,147,0.12)' : 'rgba(201,169,98,0.15)',
              borderWidth: 1, borderColor: aiPaused ? 'rgba(142,142,147,0.35)' : 'rgba(201,169,98,0.5)',
            }}
            data-testid="ai-master-toggle"
          >
            <Ionicons name="sparkles" size={13} color={aiPaused ? '#8E8E93' : '#C9A962'} />
            <Text style={{ fontSize: 11, fontWeight: '800', letterSpacing: 0.5, color: aiPaused ? '#8E8E93' : '#C9A962' }}>
              {aiPaused ? 'AI OFF' : 'AI ON'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={toggleTheme}
            style={{ padding: 6 }}
            testID="theme-toggle-home"
          >
            <Ionicons
              name={themeMode === 'dark' ? 'moon' : 'sunny'}
              size={20}
              color={themeMode === 'dark' ? '#5856D6' : '#FF9500'}
            />
          </TouchableOpacity>
          <NotificationBell />
        </View>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {!initialLoaded && loadingTasks ? (
          <View style={{ flex: 1, paddingTop: 60, alignItems: 'center' }}>
            <ActivityIndicator size="large" color={colors.accent} />
          </View>
        ) : (
        <>

        {/* ── DO THIS NEXT — one clear action ─── */}
        <TouchableOpacity
          onPress={nextMove.onPress}
          activeOpacity={0.85}
          style={{
            marginHorizontal: 16, marginBottom: 16, borderRadius: 20, padding: 18,
            backgroundColor: nextMove.color + '12',
            borderWidth: 2, borderColor: nextMove.color + '55',
          }}
          data-testid="next-move-card"
        >
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Ionicons name="arrow-forward-circle" size={14} color={nextMove.color} />
            <Text style={{ fontSize: 11, fontWeight: '900', color: nextMove.color, letterSpacing: 1.2 }}>DO THIS NEXT</Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <View style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: nextMove.color + '22', alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={nextMove.icon as any} size={24} color={nextMove.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, lineHeight: 21 }} numberOfLines={2}>{nextMove.label}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{nextMove.sub}</Text>
            </View>
            <View style={{ backgroundColor: nextMove.color, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 9 }}>
              <Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>{nextMove.btn}</Text>
            </View>
          </View>
        </TouchableOpacity>

        {/* ── QUICK ACTIONS — 2×2 grid ─── */}
        <View style={{ paddingHorizontal: 16, marginBottom: 16 }}>
          {[[TILES[0], TILES[1]], [TILES[2], TILES[3]], [TILES[4], TILES[5]]].map((row, rowIdx) => (
            <View key={rowIdx} style={{ flexDirection: 'row', gap: 10, marginBottom: rowIdx < 2 ? 10 : 0 }}>
              {row.map(tile => (
                <TouchableOpacity
                  key={tile.key}
                  onPress={tile.onPress}
                  onLongPress={(tile as any).onLongPress}
                  delayLongPress={350}
                  activeOpacity={0.75}
                  style={{
                    flex: 1,
                    backgroundColor: tile.color + '14',
                    borderWidth: 1.5,
                    borderColor: tile.color + '45',
                    borderRadius: 18,
                    padding: 16,
                    minHeight: 108,
                  }}
                  data-testid={`quick-action-${tile.key}`}
                >
                  <View style={{
                    width: 44, height: 44, borderRadius: 12,
                    backgroundColor: tile.color + '22',
                    alignItems: 'center', justifyContent: 'center',
                    marginBottom: 10,
                  }}>
                    <Ionicons name={tile.icon as any} size={24} color={tile.color} />
                  </View>
                  <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, marginBottom: 3 }}>
                    {tile.label}
                  </Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} numberOfLines={2}>
                    {tile.sublabel}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          ))}
        </View>
        {/* ── MAKE A CALL BAR ── */}
        <TouchableOpacity
          onPress={() => router.push('/(tabs)/dialer' as any)}
          style={{ marginHorizontal: 16, marginBottom: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 14, paddingVertical: 13, borderWidth: 1, borderColor: colors.surface }}
          data-testid="make-a-call-btn"
        >
          <Ionicons name="call-outline" size={20} color="#34C759" />
          <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Make a Call</Text>
        </TouchableOpacity>

        {streak && (
          <TouchableOpacity
            onPress={() => router.push('/touchpoints')}
            style={{ marginHorizontal: 16, marginBottom: 14, borderRadius: 16,
              backgroundColor: streak.streak >= 3 ? '#FF950018' : streak.at_risk ? '#FF3B3012' : colors.card,
              borderWidth: 1.5, borderColor: streak.streak >= 3 ? '#FF9500' : streak.at_risk ? '#FF3B30' : colors.border,
              flexDirection: 'row', alignItems: 'center', padding: 14, gap: 10 }}
          >
            <Text style={{ fontSize: 26 }}>{streak.emoji}</Text>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '700', color: streak.streak >= 3 ? '#FF9500' : streak.at_risk ? '#FF3B30' : colors.text }}>
                {streak.label}
              </Text>
              {streak.at_risk && <Text style={{ fontSize: 12, color: '#FF3B30', marginTop: 1 }}>Reach out to someone to keep it going</Text>}
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
          </TouchableOpacity>
        )}

        {/* ── MY MONTH SALES WIDGET ── */}
        {soldPerf && (
          <View style={{ marginHorizontal: 16, marginBottom: 16, backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: '#C9A96230' }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 6 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name="trophy" size={17} color="#C9A962" />
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>
                  {new Date().toLocaleString('default', { month: 'long' })} Sales
                </Text>
              </View>
              {soldPerf.mom_change !== 0 && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: soldPerf.mom_change > 0 ? '#34C75918' : '#FF3B3018', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 }}>
                  <Ionicons name={soldPerf.mom_change > 0 ? 'trending-up' : 'trending-down'} size={12} color={soldPerf.mom_change > 0 ? '#34C759' : '#FF3B30'} />
                  <Text style={{ fontSize: 12, fontWeight: '700', color: soldPerf.mom_change > 0 ? '#34C759' : '#FF3B30' }} numberOfLines={1}>
                    {soldPerf.mom_change > 0 ? '+' : ''}{soldPerf.mom_change} vs prev
                  </Text>
                </View>
              )}
            </View>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {[
                { label: 'Sold', value: soldPerf.current_month?.total || 0, color: '#C9A962', icon: 'checkmark-circle',
                  onPress: () => router.push('/sales-list?type=sold' as any) },
                { label: 'Referrals', value: soldPerf.current_month?.referrals || 0, color: '#007AFF', icon: 'people',
                  onPress: () => router.push('/sales-list?type=referrals' as any) },
                { label: 'Repeats', value: soldPerf.current_month?.repeats || 0, color: '#AF52DE', icon: 'repeat',
                  onPress: () => router.push('/sales-list?type=repeats' as any) },
              ].map((stat, i) => (
                <TouchableOpacity
                  key={i}
                  style={{ flex: 1, backgroundColor: stat.color + '12', borderRadius: 12, padding: 12, alignItems: 'center', gap: 4 }}
                  onPress={stat.onPress}
                  data-testid={`sold-stat-${stat.label.toLowerCase()}`}
                >
                  <Ionicons name={stat.icon as any} size={20} color={stat.color} />
                  <Text style={{ fontSize: 22, fontWeight: '800', color: stat.color }}>{stat.value}</Text>
                  <Text style={{ fontSize: 11, fontWeight: '600', color: colors.textSecondary, textAlign: 'center' }} numberOfLines={1} adjustsFontSizeToFit>{stat.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {soldPerf.all_time_sold > 0 && (
              <Text style={{ fontSize: 12, color: colors.textTertiary, textAlign: 'center', marginTop: 10 }}>
                {soldPerf.all_time_sold} total sold · {soldPerf.all_time_referrals} referrals all-time
              </Text>
            )}
          </View>
        )}

        {/* ── MY 3 FOR TODAY ────────────────────────────── */}
        <View style={{ marginHorizontal: 16, marginBottom: 20 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <View style={{ flex: 1, marginRight: 10 }}>
              <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>Your 3 for Today</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
                {my3.length > 0 ? '30 seconds each. Keep the streak alive.' : 'Analysing your relationships...'}
              </Text>
            </View>
            {my3.length > 0 && (
              <View style={{ backgroundColor: '#C9A96220', borderRadius: 20, paddingHorizontal: 12, paddingVertical: 4, flexShrink: 0 }}>
                <Text style={{ fontSize: 13, fontWeight: '700', color: '#C9A962' }}>{my3.length - completedToday.size}/{my3.length}</Text>
              </View>
            )}
          </View>
          {loadingMy3 && my3.length === 0 ? (
            <View style={{ padding: 28, alignItems: 'center' }}>
              <ActivityIndicator color="#C9A962" />
              <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 10 }}>Finding your best contacts for today...</Text>
            </View>
          ) : my3.length === 0 ? (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 24, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
              <Ionicons name="checkmark-circle" size={40} color="#34C759" />
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, marginTop: 10 }}>You're all caught up!</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 4, textAlign: 'center' }}>No one needs your attention right now.</Text>
            </View>
          ) : (
            my3.map((item, idx) => {
              const done = completedToday.has(item.contact_id);
              return (
                <TouchableOpacity key={item.contact_id + idx} onPress={() => router.push(`/contact/${item.contact_id}`)}
                  style={{ backgroundColor: colors.card, borderRadius: 16, marginBottom: 10, borderWidth: 1, borderColor: done ? '#34C75930' : colors.border, opacity: done ? 0.5 : 1, overflow: 'hidden' }}
                  data-testid={`my3-card-${idx}`}
                >
                  <View style={{ height: 3, backgroundColor: done ? '#34C759' : item.color }} />
                  <View style={{ flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12 }}>
                    <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: item.color + '20', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <Ionicons name={item.icon as any} size={20} color={item.color} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 16, fontWeight: '700', color: done ? colors.textSecondary : colors.text }} numberOfLines={1}>{item.first_name} {item.last_name}</Text>
                      <Text style={{ fontSize: 13, color: item.color, marginTop: 2, fontWeight: '500' }}>{item.reason_label}</Text>
                    </View>
                    {!done ? (
                      <TouchableOpacity onPress={(e) => { e.stopPropagation?.(); setCompletedToday(p => new Set([...p, item.contact_id])); router.push(`/contact/${item.contact_id}`); }}
                        style={{ backgroundColor: item.color, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 }}>
                        <Text style={{ fontSize: 13, fontWeight: '700', color: '#fff' }}>{item.action_label}</Text>
                      </TouchableOpacity>
                    ) : (
                      <View style={{ backgroundColor: '#34C75920', borderRadius: 20, padding: 8 }}>
                        <Ionicons name="checkmark" size={16} color="#34C759" />
                      </View>
                    )}
                  </View>
                </TouchableOpacity>
              );
            })
          )}
        </View>

        {/* ── HOT OPPORTUNITIES ─────────────────────────────── */}
        {hotOpps.length > 0 && (
          <View style={{ marginHorizontal: 16, marginBottom: 16, backgroundColor: '#FF3B300D', borderRadius: 16, padding: 16, borderWidth: 1.5, borderColor: '#FF3B3030' }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Ionicons name="flame" size={18} color="#FF3B30" />
              <Text style={{ fontSize: 16, fontWeight: '800', color: '#FF3B30', flex: 1 }}>
                Hot Opportunities ({hotOpps.length})
              </Text>
              <TouchableOpacity onPress={() => router.push('/(tabs)/inbox?tab=hot' as any)}>
                <Text style={{ fontSize: 13, fontWeight: '600', color: '#FF3B30' }}>View All →</Text>
              </TouchableOpacity>
            </View>
            {hotOpps.map((conv: any, i: number) => (
              <TouchableOpacity
                key={conv._id}
                onPress={() => router.push(`/thread/${conv._id}` as any)}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderTopWidth: i > 0 ? 0.5 : 0, borderTopColor: '#FF3B3020' }}
              >
                <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#FF3B3020', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Ionicons name="flame" size={16} color="#FF3B30" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }} numberOfLines={1}>
                    {conv.contact_name || conv.contact_phone || 'Customer'}
                  </Text>
                  <Text style={{ fontSize: 12, color: '#FF3B30', fontWeight: '500', marginTop: 1 }} numberOfLines={1}>
                    {conv.intent_signals?.slice(0, 2).join(' · ') || 'High buying intent detected'}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color="#FF3B30" />
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* ── WINS FEED ─────────────────────────────────── */}
        {winsFeed.length > 0 && (
          <View style={{ marginHorizontal: 16, marginBottom: 16, backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border }}>
            <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, marginBottom: 12 }}>Recent Wins 🎯</Text>
            {winsFeed.slice(0, 5).map((win: any, i: number) => (
              <TouchableOpacity key={i} onPress={() => win.contact_id && router.push(`/contact/${win.contact_id}`)}
                style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 9, gap: 10, borderBottomWidth: i < Math.min(winsFeed.length, 5) - 1 ? 0.5 : 0, borderBottomColor: colors.border }}>
                <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: win.color + '20', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Ionicons name={win.icon as any} size={14} color={win.color} />
                </View>
                <Text style={{ flex: 1, fontSize: 14, color: colors.text, fontWeight: '500', lineHeight: 19 }} numberOfLines={2}>{win.message}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, flexShrink: 0, marginLeft: 4 }}>{getRelativeTime(win.timestamp)}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <View style={{ height: 1, backgroundColor: colors.border, marginHorizontal: 16, marginBottom: 16 }} />

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
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 14 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 }}>
                <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(201,169,98,0.12)', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="checkbox-outline" size={22} color={colors.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>Today's Touchpoints</Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 3 }}>
                    <View style={{ backgroundColor: 'rgba(201,169,98,0.12)', paddingVertical: 2, paddingHorizontal: 8, borderRadius: 6 }}>
                      <Text style={{ fontSize: 13, fontWeight: '700', color: colors.accent }}>{taskSummary?.pending_today || pendingTasks.length} pending</Text>
                    </View>
                  </View>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
            </View>

            {/* Mini Scoreboard — 2 rows of 3 so labels never wrap */}
            <View style={{ gap: 6, marginBottom: 14 }}>
              {(() => {
                const stats = [
                  { label: 'CALLS', color: '#007AFF', val: taskSummary?.activity?.calls || 0 },
                  { label: 'TEXTS', color: '#34C759', val: taskSummary?.activity?.texts || 0 },
                  { label: 'EMAILS', color: '#5AC8FA', val: taskSummary?.activity?.emails || 0 },
                  { label: 'CARDS', color: '#C9A962', val: taskSummary?.activity?.cards || 0 },
                  { label: 'CLICKS', color: '#FF375F', val: taskSummary?.activity?.clicks || 0 },
                  { label: 'LEADS', color: '#32ADE6', val: taskSummary?.activity?.new_leads || 0 },
                ];
                return [0, 1].map(row => (
                  <View key={row} style={{ flexDirection: 'row', gap: 6 }}>
                    {stats.slice(row * 3, row * 3 + 3).map(s => (
                      <View key={s.label} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7, backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 10, paddingVertical: 10, paddingHorizontal: 4 }}>
                        <Text style={{ fontSize: 20, fontWeight: '700', color: s.color }} maxFontSizeMultiplier={1.2} numberOfLines={1}>{s.val}</Text>
                        <Text style={{ fontSize: 11, color: colors.textSecondary, fontWeight: '600', letterSpacing: 0.5 }} maxFontSizeMultiplier={1.1} numberOfLines={1}>{s.label}</Text>
                      </View>
                    ))}
                  </View>
                ));
              })()}
            </View>

            {/* Progress */}
            <View style={{ backgroundColor: colors.border, borderRadius: 5, height: 6, overflow: 'hidden', marginBottom: 6 }}>
              <View style={{ height: '100%', backgroundColor: colors.accent, borderRadius: 5, width: `${taskSummary?.progress_pct || 0}%` }} />
            </View>
            <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginBottom: 4 }}>
              {taskSummary?.completed_today || 0} of {taskSummary?.total_today || 0} today's touchpoints
            </Text>
            {(taskSummary?.overdue || 0) > 0 && (
              <Text style={{ fontSize: 13, color: '#FF9500', textAlign: 'center', marginBottom: 12, fontWeight: '600' }}>
                + {taskSummary.overdue} overdue from past days
              </Text>
            )}
            {(taskSummary?.overdue || 0) === 0 && <View style={{ marginBottom: 12 }} />}

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
                  <Text style={{ fontSize: 15, color: '#ccc', flex: 1 }} numberOfLines={1}>{task.title}</Text>
                  {badgeLabel ? (
                    <View style={{ backgroundColor: `${badgeColor}18`, paddingVertical: 2, paddingHorizontal: 6, borderRadius: 4 }}>
                      <Text style={{ fontSize: 12, fontWeight: '600', color: badgeColor }}>{badgeLabel}</Text>
                    </View>
                  ) : null}
                </View>
              );
            })}
            {pendingTasks.length === 0 && !loadingTasks && (
              <Text style={{ fontSize: 15, color: colors.textTertiary, textAlign: 'center', paddingVertical: 8 }}>No touchpoints for today</Text>
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
                <Text style={{ fontSize: 18, fontWeight: '900', color: seoScore.grade_color }}>{seoScore.total_score}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>SEO Health</Text>
                <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 1 }}>{seoScore.grade}{seoScore.tips?.length > 0 ? ` \u00B7 ${seoScore.tips.length} tips to improve` : ''}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#48484A" />
            </TouchableOpacity>
          )}

          {/* Activity Feed tile */}
        </View>
        </>
        )}
      </ScrollView>

      {/* Asset Share Picker — tapping Card tile on home screen */}
      <Modal visible={showSharePicker} transparent animationType="slide" onRequestClose={() => setShowSharePicker(false)}>
        <TouchableOpacity
          style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }}
          activeOpacity={1}
          onPress={() => setShowSharePicker(false)}
        >
          <View
            style={{ backgroundColor: colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingBottom: 36 }}
            onStartShouldSetResponder={() => true}
          >
            {/* Handle */}
            <View style={{ alignItems: 'center', paddingTop: 12, paddingBottom: 8 }}>
              <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border }} />
            </View>

            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text, textAlign: 'center', marginBottom: 4 }}>
              What do you want to share?
            </Text>
            <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginBottom: 20 }}>
              Choose an asset to send to your customer
            </Text>

            {[
              {
                key: 'digital-card',
                icon: 'card',
                color: '#007AFF',
                label: 'Digital Card',
                sublabel: 'Your interactive business card',
                isDefault: true,
                onPress: () => { setShowSharePicker(false); router.push('/quick-send/digitalcard' as any); },
              },
              {
                key: 'card-qr',
                icon: 'qr-code',
                color: '#C9A962',
                label: 'Card QR Code',
                sublabel: 'Let them scan it right off your screen',
                isDefault: false,
                onPress: () => {
                  setShowSharePicker(false);
                  const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
                  const cardUrl = `${baseUrl}/card/${user?._id}`;
                  setShareConfig({ visible: true, title: 'Your Card QR', subtitle: 'Have them scan it — your card opens instantly', url: cardUrl, text: `My digital card: ${cardUrl}`, showPreview: false, showQR: true, startQR: true, eventType: 'card_qr_shown' });
                },
              },
              {
                key: 'wallet',
                icon: 'wallet',
                color: '#34C759',
                label: 'Add to Wallet',
                sublabel: 'Your card QR in Apple or Google Wallet',
                isDefault: false,
                onPress: handleAddToWallet,
              },
              {
                key: 'vcf',
                icon: 'person-circle',
                color: '#34C759',
                label: 'Contact Card (VCF)',
                sublabel: 'Save your number to their contacts',
                isDefault: false,
                onPress: () => {
                  setShowSharePicker(false);
                  const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
                  const vcfUrl = `${baseUrl}/api/profile/${user?._id}/vcard.vcf`;
                  setShareConfig({ visible: true, title: 'Share Contact Card', subtitle: 'Customer taps to save your number', url: vcfUrl, text: `Tap to save my contact: ${vcfUrl}`, showPreview: false, showQR: false, eventType: 'vcf_shared' });
                },
              },
              {
                key: 'landing',
                icon: 'globe-outline',
                color: '#AF52DE',
                label: 'Landing Page',
                sublabel: 'Your full personal page',
                isDefault: false,
                onPress: () => {
                  setShowSharePicker(false);
                  const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
                  setShareConfig({ visible: true, title: 'Share Landing Page', subtitle: 'Your full personal page', url: `${baseUrl}/p/${user?._id}`, text: `Check out my page: ${baseUrl}/p/${user?._id}`, showPreview: true, previewUrl: `${baseUrl}/p/${user?._id}`, showQR: true, eventType: 'landing_page_shared' });
                },
              },
              {
                key: 'showcase',
                icon: 'images-outline',
                color: '#FF9500',
                label: 'Showcase',
                sublabel: 'Your customer photo gallery',
                isDefault: false,
                onPress: () => { setShowSharePicker(false); openShareModal('showroom'); },
              },
              {
                key: 'linkpage',
                icon: 'link',
                color: '#FF2D55',
                label: 'Link Page',
                sublabel: 'All your links in one spot',
                isDefault: false,
                onPress: () => {
                  setShowSharePicker(false);
                  const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
                  setShareConfig({ visible: true, title: 'Share Link Page', subtitle: 'All your links in one place', url: `${baseUrl}/l/${user?._id}`, text: `All my links: ${baseUrl}/l/${user?._id}`, showPreview: true, previewUrl: `${baseUrl}/l/${user?._id}`, showQR: true, eventType: 'link_page_shared' });
                },
              },
            ].map((item, i, arr) => (
              <TouchableOpacity
                key={item.key}
                onPress={item.onPress}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  paddingHorizontal: 20,
                  paddingVertical: 14,
                  borderBottomWidth: i < arr.length - 1 ? 1 : 0,
                  borderBottomColor: colors.border,
                  backgroundColor: item.isDefault ? item.color + '0D' : 'transparent',
                }}
                data-testid={`share-picker-${item.key}`}
              >
                <View style={{
                  width: 44, height: 44, borderRadius: 12,
                  backgroundColor: item.color + '20',
                  alignItems: 'center', justifyContent: 'center',
                  marginRight: 14,
                }}>
                  <Ionicons name={item.icon as any} size={22} color={item.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{item.label}</Text>
                    {item.isDefault && (
                      <View style={{ backgroundColor: item.color, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 }}>
                        <Text style={{ fontSize: 10, fontWeight: '800', color: '#fff', letterSpacing: 0.3 }}>DEFAULT</Text>
                      </View>
                    )}
                  </View>
                  <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 1 }}>{item.sublabel}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>

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
        startWithQR={!!shareConfig.startQR}
        vCardUserId={user?._id}
        userId={user?._id}
        eventType={shareConfig.eventType}
        showScanStats={shareConfig.eventType === 'card_qr_shown'}
      />

      <ContactActionModal visible={showContactAction} onClose={() => setShowContactAction(false)} colors={colors} userId={user?._id || ''} initialMode={contactActionMode} />

      {/* Action Picker — Pick a contact then navigate to their record to complete the action */}
      <Modal visible={showActionPicker} animationType="slide" transparent={false}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
            <TouchableOpacity onPress={() => setShowActionPicker(false)} style={{ padding: 4 }} data-testid="action-picker-back-btn">
              <Ionicons name="chevron-back" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' }}>
              {actionPickerTitle}
            </Text>
            <View style={{ width: 32 }} />
          </View>

          <Text style={{ color: colors.textSecondary, fontSize: 15, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 }}>Select a contact to send to</Text>
          <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
            <TextInput
              style={{ backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, fontSize: 17, color: colors.text }}
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
                      <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 16 }}>{initials}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{name}</Text>
                      {item.phone ? <Text style={{ fontSize: 14, color: colors.textSecondary }}>{item.phone}</Text> : null}
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                );
              }}
              ListEmptyComponent={
                <Text style={{ textAlign: 'center', color: colors.textSecondary, marginTop: 24, fontSize: 16 }}>
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
            <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' }}>
              {sendCardStep === 'type' ? 'Send a Card' : "Who's it for?"}
            </Text>
            <View style={{ width: 32 }} />
          </View>

          {sendCardStep === 'type' ? (
            <>
              <Text style={{ color: colors.textSecondary, fontSize: 15, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 }}>Choose a card type to create and send</Text>
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
                    <Text style={{ flex: 1, fontSize: 18, fontWeight: '600', color: colors.text }}>{card.label}</Text>
                    <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </>
          ) : (
            <>
              {/* Skip button FIRST — most visible, before keyboard opens */}
              <TouchableOpacity
                style={{ flexDirection: 'row', alignItems: 'center', gap: 12, margin: 16, marginBottom: 8, padding: 16, backgroundColor: colors.accent + '20', borderRadius: 14, borderWidth: 1.5, borderColor: colors.accent }}
                onPress={handleCardSkipContact}
                data-testid="send-card-skip-contact"
              >
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="share-outline" size={20} color="#000" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: colors.accent, fontSize: 17, fontWeight: '800' }}>No Contact — Just Get a Link</Text>
                  <Text style={{ color: colors.textSecondary, fontSize: 13, marginTop: 2 }}>Create the card and share the link anywhere</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color={colors.accent} />
              </TouchableOpacity>

              <Text style={{ color: colors.textTertiary, fontSize: 13, fontWeight: '600', paddingHorizontal: 16, paddingBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>— or send to a specific contact —</Text>
              <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
                <TextInput
                  style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, fontSize: 17, color: colors.text, borderWidth: 1, borderColor: colors.border }}
                  placeholder="Search by name, phone, or email..."
                  placeholderTextColor={colors.textTertiary}
                  value={cardSearch}
                  onChangeText={setCardSearch}
                  data-testid="send-card-contact-search"
                />
              </View>
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
                          <Text style={{ color: colors.accent, fontWeight: '700', fontSize: 16 }}>{initials}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{name}</Text>
                          {item.phone ? <Text style={{ fontSize: 14, color: colors.textSecondary }}>{item.phone}</Text> : null}
                        </View>
                        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                      </TouchableOpacity>
                    );
                  }}
                  ListEmptyComponent={
                    <Text style={{ textAlign: 'center', color: colors.textSecondary, marginTop: 24, fontSize: 16 }}>
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
  userName: { fontSize: 19, fontWeight: '700' },
  scroll: { flex: 1, zIndex: 1 },
  scrollContent: { padding: 16, paddingBottom: 0 },
  tilesGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  tile: { width: '48%', flexBasis: '47%', flexGrow: 1, borderRadius: 14, padding: 14, alignItems: 'center', justifyContent: 'center', borderWidth: 1, minHeight: 88 },
  tileIconWrap: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
  tileLabel: { fontSize: 14, fontWeight: '700', textAlign: 'center' },
  activitySection: { marginTop: 16 },
  activityHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 19, fontWeight: '700' },
  viewAll: { fontSize: 15, fontWeight: '600' },
  emptyActivity: { borderRadius: 14, padding: 24, alignItems: 'center', borderWidth: 1 },
  emptyText: { fontSize: 15, marginTop: 10, textAlign: 'center', lineHeight: 20 },
  activityItem: { flexDirection: 'row', alignItems: 'center', padding: 18, borderRadius: 14, marginBottom: 10, borderWidth: 1 },
  activityIconWrap: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 14 },
  activityContent: { flex: 1 },
  activityMsg: { fontSize: 17, fontWeight: '600', lineHeight: 20 },
  activityTime: { fontSize: 15, marginTop: 3 },
  taskItem: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 14, marginBottom: 8, borderWidth: 1 },
  taskDoneBtn: { padding: 4, marginLeft: 8 },
  // Modal shared
  modalOverlay: { flex: 1, justifyContent: 'flex-end' },
  modalContent: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 34, maxHeight: '75%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 21, fontWeight: '700' },
  searchInput: { borderRadius: 12, padding: 12, fontSize: 17, marginBottom: 8, borderWidth: 1 },
  importPhoneBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 12, paddingHorizontal: 14, marginBottom: 8, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed' },
  contactRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 0.5, gap: 10 },
  contactAvatar: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  contactName: { fontSize: 16, fontWeight: '600' },
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

export default function HomeScreenWithBoundary(props: any) {
  return <ScreenErrorBoundary screenName="Home"><HomeScreen {...props} /></ScreenErrorBoundary>;
}
