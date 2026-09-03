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
  Platform,
  Linking,
  Modal,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, useLocalSearchParams } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { contactsAPI, messagesAPI, tagsAPI } from '../../services/api';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { SmartListBar } from '../../components/contacts/SmartListBar';
import { ContactFilterSheet } from '../../components/contacts/ContactFilterSheet';
import { ContactRow, daysUntilBirthday } from '../../components/contacts/ContactRow';
import { DraftMessageSheet } from '../../components/DraftMessageSheet';

const GOLD = '#C9A962';

interface Tag {
  _id: string;
  name: string;
  color: string;
  icon: string;
  contact_count: number;
}

export default function ContactsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const { tag: tagParam, smart: smartParam } = useLocalSearchParams<{ tag?: string; smart?: string }>();

  const [search, setSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTag, setSelectedTag] = useState<string | null>(tagParam || null);
  const [crmFilter, setCrmFilter] = useState<'all' | 'linked' | 'not_linked' | 'users'>('all');
  const [viewMode, setViewMode] = useState<'mine' | 'team'>('mine');
  const [sortMode, setSortMode] = useState<'alpha' | 'recent'>('recent');
  const [hasMore, setHasMore] = useState(false);
  const [totalContacts, setTotalContacts] = useState(0);
  const currentSkip = useRef(0);
  const PAGE_SIZE = 50;

  // Smart lists
  const [smartList, setSmartList] = useState<string | null>(smartParam || null);
  const [smartCounts, setSmartCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    if (smartParam) setSmartList(smartParam);
  }, [smartParam]);

  // Filter sheet
  const [filterOpen, setFilterOpen] = useState(false);

  // AI draft sheet
  const [draftItem, setDraftItem] = useState<any | null>(null);

  // Selection & Delete state
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const deletingRef = useRef(false);

  const isWeb = Platform.OS === 'web';
  const isManager = ['super_admin', 'org_admin', 'store_manager'].includes(user?.role || '');
  const isPending = user?.status === 'pending';
  const userId = user?._id;
  const searchTimer = useRef<any>(null);
  const initialLoadDone = useRef(false);
  const requestSeq = useRef(0);
  const lastLoadTs = useRef(0);

  const loadContacts = useCallback(async (resetPage = true) => {
    if (!userId) return;
    const seq = ++requestSeq.current;
    const skip = resetPage ? 0 : currentSkip.current;
    try {
      if (resetPage && !initialLoadDone.current) setLoading(true);
      const data = await contactsAPI.getAll(
        userId, search || undefined,
        viewMode === 'team' ? 'team' : undefined,
        sortMode, skip, PAGE_SIZE,
        smartList || undefined,
        selectedTag || undefined,
        crmFilter !== 'all' ? crmFilter : undefined,
      );
      lastLoadTs.current = Date.now();
      if (seq !== requestSeq.current) return;
      const newContacts = data.contacts ?? data;
      if (resetPage) {
        setContacts(newContacts);
        currentSkip.current = PAGE_SIZE;
      } else {
        setContacts(prev => [...prev, ...newContacts]);
        currentSkip.current = skip + PAGE_SIZE;
      }
      setHasMore(data.has_more ?? false);
      setTotalContacts(data.total ?? newContacts.length);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [userId, search, viewMode, sortMode, smartList, selectedTag, crmFilter]);

  const loadMoreContacts = useCallback(async () => {
    if (!hasMore || loadingMore || loading) return;
    setLoadingMore(true);
    await loadContacts(false);
  }, [hasMore, loadingMore, loading, loadContacts]);

  const loadTags = async () => {
    if (!user?._id) return;
    try {
      const data = await tagsAPI.getAll(user._id);
      setTags(data);
    } catch (error) {
      console.error('Failed to load tags:', error);
    }
  };

  const loadSmartCounts = useCallback(async () => {
    if (!userId) return;
    try {
      const data = await contactsAPI.getSmartLists(userId);
      setSmartCounts(data);
    } catch {}
  }, [userId]);

  useEffect(() => {
    if (!isPending && userId) {
      loadContacts();
      loadTags();
      loadSmartCounts();
      initialLoadDone.current = true;
    }
  }, [userId, isPending, viewMode, sortMode, smartList, selectedTag, crmFilter, loadContacts]);

  useFocusEffect(
    useCallback(() => {
      if (initialLoadDone.current && userId && !isPending && !deletingRef.current && Date.now() - lastLoadTs.current > 1000) {
        loadContacts();
        loadSmartCounts();
      }
    }, [userId, isPending, loadContacts, loadSmartCounts])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await Promise.all([loadContacts(true), loadTags(), loadSmartCounts()]);
    setRefreshing(false);
  };

  const handleSearch = (text: string) => {
    setSearch(text);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      if (text.length > 2 || text.length === 0) {
        currentSkip.current = 0;
        await loadContacts(true);
      }
    }, 300);
  };

  const handleAddNewContact = () => {
    router.push('/contact/new' as any);
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredContacts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredContacts.map(c => c._id)));
    }
  };

  // ── Bulk Push to CRM ──
  const [bulkPushOpen, setBulkPushOpen] = useState(false);
  const [bulkEmail, setBulkEmail] = useState('');
  const [bulkRemember, setBulkRemember] = useState(true);
  const [pushing, setPushing] = useState(false);

  const openBulkPush = async () => {
    if (selectedIds.size === 0) return;
    setBulkPushOpen(true);
    try {
      const res = await api.get(`/crm-push/${userId}/settings`);
      if (res.data.crm_email) setBulkEmail(res.data.crm_email);
    } catch {}
  };

  const doBulkPush = async () => {
    if (!bulkEmail.trim()) { showSimpleAlert('Missing address', "Enter your CRM's ADF intake email address."); return; }
    setPushing(true);
    try {
      const res = await api.post(`/crm-push/${userId}/bulk`, {
        contact_ids: Array.from(selectedIds),
        email: bulkEmail.trim(),
        save_email: bulkRemember,
      });
      setBulkPushOpen(false);
      exitSelectMode();
      const { sent, failed } = res.data;
      showSimpleAlert('Leads sent', `${sent} lead${sent === 1 ? '' : 's'} pushed to your CRM${failed ? ` (${failed} failed)` : ''}.`);
    } catch (e: any) {
      showSimpleAlert('Push failed', e?.response?.data?.detail || 'Could not send. Check the address and try again.');
    }
    setPushing(false);
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const handleBulkDelete = () => {
    if (selectedIds.size === 0) return;
    showConfirm(
      'Delete Contacts',
      `Are you sure you want to permanently delete ${selectedIds.size} contact${selectedIds.size > 1 ? 's' : ''}? This cannot be undone.`,
      async () => {
        setDeleting(true);
        deletingRef.current = true;
        const idsToDelete = new Set(selectedIds);
        try {
          setContacts(prev => prev.filter(c => !idsToDelete.has(c._id)));
          exitSelectMode();
          await contactsAPI.bulkDelete(userId || '', Array.from(idsToDelete));
        } catch (err: any) {
          showSimpleAlert('Error', err?.response?.data?.detail || 'Failed to delete contacts');
          loadContacts();
        } finally {
          setDeleting(false);
          setTimeout(() => { deletingRef.current = false; }, 1000);
        }
      }
    );
  };

  const filteredContacts = contacts;

  const activeFilterCount =
    (viewMode === 'team' ? 1 : 0) +
    (sortMode !== 'recent' ? 1 : 0) +
    (crmFilter !== 'all' ? 1 : 0) +
    (selectedTag ? 1 : 0);

  const resetFilters = () => {
    setViewMode('mine');
    setSortMode('recent');
    setCrmFilter('all');
    setSelectedTag(null);
  };

  const keyExtractor = useCallback((item: any) => item._id || item.id, []);
  const ListSeparator = useCallback(() => <View style={[styles.separator, { backgroundColor: colors.border }]} />, [colors]);

  // ── Row actions ──
  const handleText = useCallback((item: any) => {
    router.push({
      pathname: `/thread/${item._id}`,
      params: {
        contact_name: `${item.first_name} ${item.last_name || ''}`.trim(),
        contact_phone: item.phone,
        mode: 'sms',
      },
    });
  }, [router]);

  const handleCall = useCallback(async (item: any) => {
    if (!item.phone) { showSimpleAlert('No Phone', 'This contact does not have a phone number'); return; }
    if (userId && item._id) {
      try {
        await contactsAPI.logEvent(userId, item._id, {
          event_type: 'call_placed', title: 'Outbound Call',
          description: `Called ${item.first_name || ''} ${item.last_name || ''}`.trim(),
          channel: 'call', category: 'message', icon: 'call', color: '#32ADE6',
        });
      } catch {}
    }
    Linking.openURL(`tel:${item.phone}`).catch(() => {
      showSimpleAlert('Call', `Calling ${item.phone}`);
    });
  }, [userId]);

  const handleEmail = useCallback((item: any) => {
    if (item.email) {
      router.push({
        pathname: `/thread/${item._id}`,
        params: {
          contact_name: `${item.first_name} ${item.last_name || ''}`.trim(),
          contact_phone: item.phone,
          contact_email: item.email,
          mode: 'email',
        },
      });
    } else {
      showSimpleAlert('No Email', 'This contact does not have an email address');
    }
  }, [router]);

  const handleDraft = useCallback((item: any) => {
    const t: string[] = item.tags || [];
    const bd = daysUntilBirthday(item.birthday);
    const reason = (bd !== null && bd <= 30) ? 'birthday'
      : t.includes('hot') ? 'warm_lead'
      : t.includes('sold') ? 'purchase_followup'
      : 'cooling_down';
    const reasonLabel = reason === 'birthday' ? (bd === 0 ? 'Birthday today!' : `Birthday in ${bd} day${bd === 1 ? '' : 's'}`)
      : reason === 'warm_lead' ? 'Warm lead reach-out'
      : reason === 'purchase_followup' ? 'Purchase follow-up'
      : 'Quick check-in';
    setDraftItem({
      contact_id: item._id,
      first_name: item.first_name,
      last_name: item.last_name,
      phone: item.phone,
      reason_key: reason,
      reason_label: reasonLabel,
      icon: reason === 'birthday' ? 'gift' : 'sparkles',
      color: reason === 'birthday' ? '#AF52DE' : GOLD,
    });
  }, []);

  const renderContact = useCallback(({ item }: { item: any }) => {
    const isTeamView = viewMode === 'team';
    const isOwnContact = item.user_id === userId;
    return (
      <ContactRow
        item={item}
        colors={colors}
        selectMode={selectMode}
        isSelected={selectedIds.has(item._id)}
        isTeamView={isTeamView}
        isOwnContact={isOwnContact}
        onPress={() => {
          if (selectMode && !isTeamView) toggleSelect(item._id);
          else router.push(`/contact/${item._id}`);
        }}
        onLongPress={() => {
          if (!selectMode && !isTeamView) {
            setSelectMode(true);
            setSelectedIds(new Set([item._id]));
          }
        }}
        onCall={() => handleCall(item)}
        onText={() => handleText(item)}
        onEmail={() => handleEmail(item)}
        onDraft={() => handleDraft(item)}
      />
    );
  }, [colors, selectMode, selectedIds, viewMode, userId, router, handleCall, handleText, handleEmail, handleDraft]);

  const emptyLabel = smartList === 'needs_attention' ? 'Nobody needs attention right now. Nice work!'
    : smartList === 'hot' ? 'No hot leads at the moment'
    : smartList === 'new_this_week' ? 'No new contacts this week'
    : smartList === 'birthdays' ? 'No birthdays in the next 30 days'
    : smartList === 'birthdays_on' ? 'Nobody is enrolled in auto birthday texts yet'
    : smartList === 'birthdays_off' ? 'Everyone with a birthday has auto-texts turned on'
    : 'Tap + to add or import contacts';

  if (isPending) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
        <View style={styles.restrictedContainer}>
          <View style={styles.restrictedIcon}>
            <Ionicons name="lock-closed" size={48} color="#FF9500" />
          </View>
          <Text maxFontSizeMultiplier={1.0} style={[styles.restrictedTitle, { color: colors.text }]}>Access Pending</Text>
          <Text maxFontSizeMultiplier={1.0} style={[styles.restrictedText, { color: colors.textSecondary }]}>
            Your account is being reviewed by an admin. You&apos;ll have full access to contacts once your account is configured.
          </Text>
          <TouchableOpacity
            style={styles.restrictedButton}
            onPress={() => router.push('/onboarding')}
          >
            <Text maxFontSizeMultiplier={1.0} style={styles.restrictedButtonText}>Complete Your Profile</Text>
            <Ionicons name="arrow-forward" size={18} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      {selectMode ? (
        <View style={[styles.selectHeader, { backgroundColor: colors.bg }]}>
          <TouchableOpacity onPress={exitSelectMode} style={styles.headerButton}>
            <Ionicons name="close" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text maxFontSizeMultiplier={1.0} style={[styles.selectHeaderTitle, { color: colors.text }]}>{selectedIds.size} selected</Text>
          <View style={styles.headerButtons}>
            <TouchableOpacity onPress={toggleSelectAll} style={styles.headerButton}>
              <Ionicons
                name={selectedIds.size === filteredContacts.length ? "checkbox" : "square-outline"}
                size={24}
                color={GOLD}
              />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={openBulkPush}
              style={styles.headerButton}
              disabled={selectedIds.size === 0 || pushing}
              testID="bulk-crm-push-btn" dataSet={{ testid: "bulk-crm-push-btn" } as any}
            >
              <Ionicons name="cloud-upload" size={24} color={selectedIds.size > 0 ? '#AF52DE' : '#4C4C4E'} />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={handleBulkDelete}
              style={styles.headerButton}
              disabled={selectedIds.size === 0 || deleting}
            >
              {deleting ? (
                <ActivityIndicator size="small" color="#FF3B30" />
              ) : (
                <Ionicons name="trash" size={24} color={selectedIds.size > 0 ? "#FF3B30" : "#4C4C4E"} />
              )}
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <View style={[styles.header, { backgroundColor: colors.bg }]}>
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8 }}>
            <Text maxFontSizeMultiplier={1.0} style={[styles.title, { color: colors.text }]}>Contacts</Text>
            {totalContacts > 0 && (
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 14, fontWeight: '600', color: colors.textTertiary }} testID="contacts-total-count" dataSet={{ testid: "contacts-total-count" } as any}>
                {totalContacts}
              </Text>
            )}
          </View>
          <View style={styles.headerButtons}>
            {isWeb && (
              <TouchableOpacity onPress={onRefresh} style={styles.headerButton} disabled={refreshing}>
                <Ionicons name="refresh" size={18} color={refreshing ? "#4C4C4E" : colors.textSecondary} />
              </TouchableOpacity>
            )}
            <TouchableOpacity onPress={() => setSelectMode(true)} style={styles.headerButton} testID="select-mode-btn" dataSet={{ testid: "select-mode-btn" } as any}>
              <Ionicons name="checkbox-outline" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
            <TouchableOpacity onPress={() => router.push('/contacts/duplicates')} style={styles.headerButton} testID="duplicates-btn" dataSet={{ testid: "duplicates-btn" } as any}>
              <Ionicons name="copy-outline" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
            <TouchableOpacity onPress={() => router.push('/contacts/import')} style={styles.headerButton} testID="import-btn" dataSet={{ testid: "import-btn" } as any}>
              <Ionicons name="download-outline" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={handleAddNewContact}
              accessibilityRole="button"
              accessibilityLabel="Add new contact"
              testID="add-contact-btn" dataSet={{ testid: "add-contact-btn" } as any}
            >
              <Ionicons name="add-circle" size={26} color={GOLD} />
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Search + filter button */}
      <View style={[styles.searchContainer, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <TextInput
          maxFontSizeMultiplier={1.0}
          style={[styles.searchInput, { color: colors.text }]}
          placeholder="Search contacts"
          placeholderTextColor={colors.textSecondary}
          value={search}
          onChangeText={handleSearch}
          testID="contacts-search-input" dataSet={{ testid: "contacts-search-input" } as any}
        />
        <TouchableOpacity onPress={() => setFilterOpen(true)} style={{ padding: 4 }} testID="open-filter-sheet-btn" dataSet={{ testid: "open-filter-sheet-btn" } as any}>
          <View>
            <Ionicons name="options-outline" size={20} color={activeFilterCount > 0 ? GOLD : colors.textSecondary} />
            {activeFilterCount > 0 && (
              <View style={{
                position: 'absolute', top: -4, right: -6,
                backgroundColor: GOLD, borderRadius: 8, minWidth: 15, height: 15,
                alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3,
              }}>
                <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 10, fontWeight: '800', color: '#000' }}>{activeFilterCount}</Text>
              </View>
            )}
          </View>
        </TouchableOpacity>
      </View>

      {/* Smart lists (personal book of business — hidden in team view) */}
      {!selectMode && viewMode !== 'team' && (
        <SmartListBar
          counts={smartCounts}
          active={smartList?.startsWith('birthdays') ? 'birthdays' : smartList}
          onSelect={(k) => setSmartList(k)}
        />
      )}

      {/* Birthday split: everyone with a birthday vs. enrolled in auto-texts */}
      {!selectMode && viewMode !== 'team' && smartList?.startsWith('birthdays') && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingBottom: 8 }}>
          {[
            { key: 'birthdays', label: 'Upcoming' },
            { key: 'birthdays_on', label: `Auto-text ON${smartCounts.birthdays_on != null ? ` · ${smartCounts.birthdays_on}` : ''}` },
            { key: 'birthdays_off', label: `No auto-text${smartCounts.birthdays_off != null ? ` · ${smartCounts.birthdays_off}` : ''}` },
          ].map((o) => (
            <TouchableOpacity
              key={o.key}
              onPress={() => setSmartList(o.key)}
              style={{
                paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12,
                backgroundColor: smartList === o.key ? '#AF52DE' : colors.card,
              }}
              testID={`bday-sub-${o.key}`}
              dataSet={{ testid: `bday-sub-${o.key}` }}
            >
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, fontWeight: '700', color: smartList === o.key ? '#FFF' : colors.textSecondary }}>
                {o.label}
              </Text>
            </TouchableOpacity>
          ))}
          <View style={{ flex: 1 }} />
          <TouchableOpacity
            onPress={() => router.push('/settings/date-recipients')}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}
            testID="manage-birthday-texts-btn"
            dataSet={{ testid: 'manage-birthday-texts-btn' }}
          >
            <Ionicons name="settings-outline" size={12} color={GOLD} />
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Manage</Text>
          </TouchableOpacity>
        </View>
      )}

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={GOLD} />
        </View>
      ) : (
        <FlatList
          data={filteredContacts}
          renderItem={renderContact}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.listContent}
          ItemSeparatorComponent={ListSeparator}
          initialNumToRender={15}
          maxToRenderPerBatch={10}
          windowSize={7}
          removeClippedSubviews={false}
          onEndReached={loadMoreContacts}
          onEndReachedThreshold={0.3}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={GOLD} />
          }
          ListFooterComponent={() => loadingMore ? (
            <View style={{ padding: 16, alignItems: 'center' }}>
              <ActivityIndicator size="small" color={colors.textSecondary} />
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, color: colors.textSecondary, marginTop: 4 }}>Loading more...</Text>
            </View>
          ) : hasMore ? (
            <View style={{ padding: 12, alignItems: 'center' }}>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, color: colors.textSecondary }}>{contacts.length} of {totalContacts}</Text>
            </View>
          ) : contacts.length > 0 ? (
            <View style={{ padding: 12, alignItems: 'center' }}>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, color: colors.textSecondary }}>{totalContacts} contacts</Text>
            </View>
          ) : null}
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="people-outline" size={64} color={colors.surface} />
              <Text maxFontSizeMultiplier={1.0} style={[styles.emptyText, { color: colors.text }]}>
                {smartList ? 'Nothing here' : 'No contacts yet'}
              </Text>
              <Text maxFontSizeMultiplier={1.0} style={[styles.emptySubtext, { color: colors.textSecondary }]}>{emptyLabel}</Text>
              {!smartList && (
                <TouchableOpacity style={styles.importButton} onPress={() => router.push('/contacts/import')}>
                  <Ionicons name="download-outline" size={20} color="#007AFF" />
                  <Text maxFontSizeMultiplier={1.0} style={styles.importButtonText}>Import Contacts</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        />
      )}

      {/* Filter bottom sheet */}
      <ContactFilterSheet
        visible={filterOpen}
        onClose={() => setFilterOpen(false)}
        isManager={isManager}
        viewMode={viewMode}
        onViewMode={(v) => { setViewMode(v); setSelectMode(false); setSelectedIds(new Set()); }}
        sortMode={sortMode}
        onSortMode={setSortMode}
        crmFilter={crmFilter}
        onCrmFilter={setCrmFilter}
        tags={tags}
        selectedTag={selectedTag}
        onSelectTag={setSelectedTag}
        onReset={resetFilters}
      />

      {/* AI draft sheet */}
      <DraftMessageSheet
        userId={userId}
        item={draftItem}
        onClose={() => setDraftItem(null)}
      />

      {/* ── Bulk Push to CRM modal ── */}
      <Modal visible={bulkPushOpen} transparent animationType="slide" onRequestClose={() => setBulkPushOpen(false)}>
        <TouchableOpacity style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }} activeOpacity={1} onPress={() => setBulkPushOpen(false)}>
          <TouchableOpacity activeOpacity={1} onPress={() => {}}>
            <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34 }} testID="bulk-crm-sheet" dataSet={{ testid: "bulk-crm-sheet" } as any}>
              <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: 'center', marginBottom: 16 }} />
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>Push {selectedIds.size} Contact{selectedIds.size === 1 ? '' : 's'} to CRM</Text>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4, lineHeight: 18 }}>
                Each contact is sent as its own industry-standard ADF/XML lead to your CRM&apos;s intake address.
              </Text>
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, marginTop: 16, marginBottom: 6, letterSpacing: 0.4 }}>CRM INTAKE EMAIL</Text>
              <TextInput
                maxFontSizeMultiplier={1.0}
                value={bulkEmail}
                onChangeText={setBulkEmail}
                placeholder="yourstore@lead.yourcrm.com"
                placeholderTextColor={colors.textSecondary}
                autoCapitalize="none"
                keyboardType="email-address"
                style={{ backgroundColor: colors.bg, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: colors.text }}
                testID="bulk-crm-email-input" dataSet={{ testid: "bulk-crm-email-input" } as any}
              />
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
                <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 13, color: colors.textSecondary }}>Remember this address</Text>
                <Switch value={bulkRemember} onValueChange={setBulkRemember} />
              </View>
              <TouchableOpacity
                onPress={doBulkPush}
                disabled={pushing}
                style={{ backgroundColor: pushing ? colors.border : '#AF52DE', borderRadius: 16, paddingVertical: 15, alignItems: 'center', marginTop: 14, flexDirection: 'row', justifyContent: 'center', gap: 8 }}
                testID="bulk-crm-send-btn" dataSet={{ testid: "bulk-crm-send-btn" } as any}
              >
                {pushing ? <ActivityIndicator color="#fff" /> : <Ionicons name="cloud-upload" size={17} color="#fff" />}
                <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 16, fontWeight: '800', color: '#fff' }}>{pushing ? 'Sending...' : `Send ${selectedIds.size} Lead${selectedIds.size === 1 ? '' : 's'}`}</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  selectHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    gap: 12,
  },
  selectHeaderTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
  },
  headerButtons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  headerButton: {
    padding: 4,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    marginHorizontal: 16,
    paddingHorizontal: 10,
    marginBottom: 10,
    gap: 6,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 9,
    fontSize: 16,
  },
  listContent: {
    paddingBottom: 16,
  },
  separator: {
    height: 1,
    marginLeft: 74,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 64,
    paddingHorizontal: 24,
  },
  emptyText: {
    fontSize: 21,
    fontWeight: '600',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 16,
    textAlign: 'center',
  },
  importButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF20',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 20,
    marginTop: 20,
    gap: 8,
  },
  importButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
  restrictedContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  restrictedIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#FF950020',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  restrictedTitle: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 12,
  },
  restrictedText: {
    fontSize: 18,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 32,
  },
  restrictedButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF20',
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 12,
    gap: 8,
  },
  restrictedButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
});
