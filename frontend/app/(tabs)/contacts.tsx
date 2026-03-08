import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Image,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  Platform,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { contactsAPI, messagesAPI, tagsAPI } from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';

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
  
  const [search, setSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  
  // Add Contact navigation (unified with home page)
  
  // Selection & Delete state
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  
  // Check if running on web platform
  const isWeb = Platform.OS === 'web';
  
  // Check if user has restricted access
  const isPending = user?.status === 'pending';
  const userId = user?._id;
  const searchTimer = useRef<any>(null);
  const initialLoadDone = useRef(false);
  
  useEffect(() => {
    if (!isPending && userId) {
      loadContacts();
      loadTags();
      initialLoadDone.current = true;
    }
  }, [userId, isPending]);

  // Auto-refresh when tab gains focus (e.g. after adding a new contact)
  useFocusEffect(
    useCallback(() => {
      if (initialLoadDone.current && userId && !isPending) {
        loadContacts();
      }
    }, [userId, isPending])
  );

  const loadTags = async () => {
    if (!user?._id) return;
    try {
      const data = await tagsAPI.getAll(user._id);
      setTags(data);
    } catch (error) {
      console.error('Failed to load tags:', error);
    }
  };
  
  // Show restricted access screen for pending users
  if (isPending) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
        <View style={styles.restrictedContainer}>
          <View style={styles.restrictedIcon}>
            <Ionicons name="lock-closed" size={48} color="#FF9500" />
          </View>
          <Text style={[styles.restrictedTitle, { color: colors.text }]}>Access Pending</Text>
          <Text style={[styles.restrictedText, { color: colors.textSecondary }]}>
            Your account is being reviewed by an admin. You'll have full access to contacts once your account is configured.
          </Text>
          <TouchableOpacity 
            style={styles.restrictedButton}
            onPress={() => router.push('/onboarding')}
          >
            <Text style={styles.restrictedButtonText}>Complete Your Profile</Text>
            <Ionicons name="arrow-forward" size={18} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }
  
  const loadContacts = useCallback(async () => {
    if (!userId) return;
    
    try {
      if (!initialLoadDone.current) setLoading(true);
      const data = await contactsAPI.getAll(userId, search || undefined);
      setContacts(data);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      setLoading(false);
    }
  }, [userId, search]);
  
  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await Promise.all([loadContacts(), loadTags()]);
    setRefreshing(false);
  };
  
  const handleSearch = (text: string) => {
    setSearch(text);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      if (text.length > 2 || text.length === 0) {
        try {
          const data = await contactsAPI.getAll(userId || '', text || undefined);
          setContacts(data);
        } catch (error) {
          console.error('Search failed:', error);
        }
      }
    }, 300);
  };
  
  const startConversation = async (contact: any) => {
    if (!user) return;
    
    // Light haptic when starting conversation
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    try {
      // Send an initial message to create/get the conversation
      const result = await messagesAPI.send(user._id, {
        conversation_id: contact._id, // Using contact_id as conversation identifier
        content: '', // Empty message just to get conversation ID
      });
      
      // Navigate to thread
      router.push({
        pathname: `/thread/${result.conversation_id || contact._id}`,
        params: {
          contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
          contact_phone: contact.phone,
          contact_photo: contact.photo_thumbnail || contact.photo_url || '',
        }
      });
    } catch (error) {
      // If send fails, just navigate anyway - the thread will handle it
      router.push({
        pathname: `/thread/${contact._id}`,
        params: {
          contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
          contact_phone: contact.phone,
          contact_photo: contact.photo_thumbnail || contact.photo_url || '',
        }
      });
    }
  };
  
  // Handle adding a new contact - create via API then navigate to thread
  const handleAddNewContact = () => {
    router.push('/contact/new' as any);
  };

  // Toggle contact selection
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Select/deselect all
  const toggleSelectAll = () => {
    if (selectedIds.size === filteredContacts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredContacts.map(c => c._id)));
    }
  };

  // Exit select mode
  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  // Delete selected contacts
  const handleBulkDelete = () => {
    if (selectedIds.size === 0) return;
    showConfirm(
      'Delete Contacts',
      `Are you sure you want to permanently delete ${selectedIds.size} contact${selectedIds.size > 1 ? 's' : ''}? This cannot be undone.`,
      async () => {
        setDeleting(true);
        try {
          await contactsAPI.bulkDelete(userId || '', Array.from(selectedIds));
          exitSelectMode();
          loadContacts();
        } catch (err: any) {
          showSimpleAlert('Error', err?.response?.data?.detail || 'Failed to delete contacts');
        } finally {
          setDeleting(false);
        }
      }
    );
  };
  
  // Filter contacts by selected tag - memoized
  const filteredContacts = useMemo(() => 
    selectedTag 
      ? contacts.filter(c => c.tags && c.tags.includes(selectedTag))
      : contacts,
    [contacts, selectedTag]
  );

  const handleTagFilter = (tagName: string | null) => {
    setSelectedTag(tagName === selectedTag ? null : tagName);
  };

  const keyExtractor = useCallback((item: any) => item._id || item.id, []);
  const ListSeparator = useCallback(() => <View style={[styles.separator, { backgroundColor: colors.border }]} />, [colors]);
  
  // Pre-build tag lookup map for O(1) access
  const tagMap = useMemo(() => {
    const map: Record<string, string> = {};
    tags.forEach(t => { map[t.name] = t.color; });
    return map;
  }, [tags]);

  const renderContact = useCallback(({ item }: { item: any }) => {
    const contactTags = item.tags?.map((tagName: string) => ({
      name: tagName,
      color: tagMap[tagName] || colors.textSecondary,
    })) || [];
    const isSelected = selectedIds.has(item._id);

    return (
    <TouchableOpacity
      style={[styles.contactItem, { backgroundColor: colors.card, borderBottomColor: colors.border }]}
      onPress={() => {
        if (selectMode) {
          toggleSelect(item._id);
        } else {
          router.push(`/contact/${item._id}`);
        }
      }}
      onLongPress={() => {
        if (!selectMode) {
          setSelectMode(true);
          setSelectedIds(new Set([item._id]));
        }
      }}
    >
      {/* Checkbox in select mode */}
      {selectMode && (
        <View style={[styles.checkbox, isSelected && styles.checkboxSelected]}>
          {isSelected && <Ionicons name="checkmark" size={16} color={colors.text} />}
        </View>
      )}
      {(item.photo_thumbnail || item.photo_url) ? (
        <Image source={{ uri: item.photo_thumbnail || item.photo_url }} style={styles.photoAvatar} />
      ) : (
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {item.first_name?.[0] || ''}{item.last_name?.[0] || ''}
          </Text>
        </View>
      )}
      
      <View style={styles.contactInfo}>
        <Text style={[styles.contactName, { color: colors.text }]}>
          {item.first_name} {item.last_name || ''}
        </Text>
        <Text style={[styles.contactPhone, { color: colors.textSecondary }]} dataDetectorType="none">{item.phone}</Text>
        {contactTags.length > 0 && (
          <View style={styles.tags}>
            {contactTags.map((tag: { name: string; color: string }, index: number) => (
              <View key={index} style={[styles.tag, { backgroundColor: tag.color + '20' }]}>
                <Text style={[styles.tagText, { color: tag.color }]}>{tag.name}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
      
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={(e) => {
            e.stopPropagation();
            if (item.phone) {
              const phoneUrl = Platform.OS === 'web' 
                ? `tel:${item.phone}` 
                : `tel:${item.phone}`;
              Linking.canOpenURL(phoneUrl).then(supported => {
                if (supported) {
                  Linking.openURL(phoneUrl);
                } else {
                  showSimpleAlert('Call', `Calling ${item.phone}`);
                }
              });
            }
          }}
        >
          <Ionicons name="call" size={20} color="#007AFF" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={(e) => {
            e.stopPropagation();
            // Navigate to thread in SMS mode
            router.push({
              pathname: `/thread/${item._id}`,
              params: {
                contact_name: `${item.first_name} ${item.last_name || ''}`.trim(),
                contact_phone: item.phone,
                mode: 'sms'
              }
            });
          }}
        >
          <Ionicons name="chatbubble" size={20} color="#007AFF" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={(e) => {
            e.stopPropagation();
            if (item.email) {
              // Navigate to thread in email mode
              router.push({
                pathname: `/thread/${item._id}`,
                params: {
                  contact_name: `${item.first_name} ${item.last_name || ''}`.trim(),
                  contact_phone: item.phone,
                  contact_email: item.email,
                  mode: 'email'
                }
              });
            } else {
              showSimpleAlert('No Email', 'This contact does not have an email address');
            }
          }}
        >
          <Ionicons name="mail" size={20} color="#34C759" />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
    );
  }, [tagMap, router, user, selectMode, selectedIds]);
  
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Normal header or Select mode header */}
      {selectMode ? (
        <View style={[styles.selectHeader, { backgroundColor: colors.bg }]}>
          <TouchableOpacity onPress={exitSelectMode} style={styles.headerButton}>
            <Ionicons name="close" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={[styles.selectHeaderTitle, { color: colors.text }]}>{selectedIds.size} selected</Text>
          <View style={styles.headerButtons}>
            <TouchableOpacity onPress={toggleSelectAll} style={styles.headerButton}>
              <Ionicons 
                name={selectedIds.size === filteredContacts.length ? "checkbox" : "square-outline"} 
                size={24} 
                color="#007AFF" 
              />
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
          <Text style={[styles.title, { color: colors.text }]}>Contacts</Text>
          <View style={styles.headerButtons}>
            {isWeb && (
              <TouchableOpacity 
                onPress={onRefresh}
                style={styles.headerButton}
                disabled={refreshing}
              >
                <Ionicons 
                  name="refresh" 
                  size={24} 
                  color={refreshing ? "#4C4C4E" : "#007AFF"} 
                />
              </TouchableOpacity>
            )}
            <TouchableOpacity 
              onPress={() => setSelectMode(true)}
              style={styles.headerButton}
            >
              <Ionicons name="checkbox-outline" size={24} color="#007AFF" />
            </TouchableOpacity>
            <TouchableOpacity 
              onPress={() => router.push('/contacts/import')}
              style={styles.headerButton}
            >
              <Ionicons name="download-outline" size={26} color="#007AFF" />
            </TouchableOpacity>
            <TouchableOpacity 
              onPress={handleAddNewContact}
              accessibilityRole="button"
              accessibilityLabel="Add new contact"
              data-testid="add-contact-btn"
            >
              <Ionicons name="add-circle" size={32} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>
      )}
      
      <View style={[styles.searchContainer, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
        <Ionicons name="search" size={20} color={colors.textSecondary} style={styles.searchIcon} />
        <TextInput
          style={[styles.searchInput, { color: colors.text }]}
          placeholder="Search contacts"
          placeholderTextColor={colors.textSecondary}
          value={search}
          onChangeText={handleSearch}
        />
      </View>

      {/* Tag Filter Bar */}
      {tags.length > 0 && (
        <View style={styles.tagFilterContainer}>
          <ScrollView 
            horizontal 
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.tagFilterContent}
          >
            <TouchableOpacity
              style={[
                styles.tagFilterChip,
                { backgroundColor: colors.card },
                !selectedTag && styles.tagFilterChipActive,
              ]}
              onPress={() => handleTagFilter(null)}
            >
              <Text style={[
                styles.tagFilterText,
                !selectedTag && styles.tagFilterTextActive,
              ]}>All</Text>
            </TouchableOpacity>
            {tags.map((tag) => (
              <TouchableOpacity
                key={tag._id}
                style={[
                  styles.tagFilterChip,
                  { backgroundColor: colors.card },
                  selectedTag === tag.name && styles.tagFilterChipActive,
                  selectedTag === tag.name && { backgroundColor: tag.color },
                ]}
                onPress={() => handleTagFilter(tag.name)}
              >
                <Ionicons 
                  name={tag.icon as any} 
                  size={14} 
                  color={selectedTag === tag.name ? '#FFF' : tag.color} 
                  style={{ marginRight: 4 }}
                />
                <Text style={[
                  styles.tagFilterText,
                  selectedTag === tag.name && styles.tagFilterTextActive,
                  selectedTag !== tag.name && { color: tag.color },
                ]}>
                  {tag.name}
                </Text>
                {tag.contact_count > 0 && (
                  <Text style={[
                    styles.tagFilterCount,
                    selectedTag === tag.name && styles.tagFilterCountActive,
                  ]}>
                    {tag.contact_count}
                  </Text>
                )}
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      )}
      
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
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
          windowSize={5}
          removeClippedSubviews={Platform.OS !== 'web'}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#007AFF"
            />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="people-outline" size={64} color={colors.surface} />
              <Text style={[styles.emptyText, { color: colors.text }]}>No contacts yet</Text>
              <Text style={[styles.emptySubtext, { color: colors.textSecondary }]}>Tap + to add or import contacts</Text>
              <TouchableOpacity 
                style={styles.importButton}
                onPress={() => router.push('/contacts/import')}
              >
                <Ionicons name="download-outline" size={20} color="#007AFF" />
                <Text style={styles.importButtonText}>Import Contacts</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
      
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
    padding: 16,
  },
  selectHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    gap: 12,
  },
  selectHeaderTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.textSecondary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  checkboxSelected: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  headerButtons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerButton: {
    padding: 4,
  },
  title: {
    fontSize: 34,
    fontWeight: 'bold',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    marginHorizontal: 24,
    paddingHorizontal: 12,
    marginBottom: 16,
    gap: 8,
  },
  searchIcon: {
  },
  searchInput: {
    flex: 1,
    paddingVertical: 14,
    fontSize: 17,
  },
  listContent: {
    paddingBottom: 16,
  },
  contactItem: {
    flexDirection: 'row',
    padding: 16,
    alignItems: 'center',
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  photoAvatar: {
    width: 48,
    height: 48,
    borderRadius: 12,
    marginRight: 12,
    resizeMode: 'cover',
  },
  avatarText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  contactInfo: {
    flex: 1,
  },
  contactName: {
    fontSize: 17,
    fontWeight: '600',
    marginBottom: 2,
  },
  contactPhone: {
    fontSize: 14,
    marginBottom: 4,
    textDecorationLine: 'none',
  },
  tags: {
    flexDirection: 'row',
    gap: 4,
    flexWrap: 'wrap',
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  tagText: {
    fontSize: 11,
    color: '#007AFF',
    fontWeight: '600',
  },
  actions: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    padding: 8,
  },
  separator: {
    height: 1,
    marginLeft: 76,
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
  },
  emptyText: {
    fontSize: 20,
    fontWeight: '600',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 15,
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
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  tagFilterContainer: {
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  tagFilterContent: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 8,
  },
  tagFilterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  tagFilterChipActive: {
    backgroundColor: '#007AFF',
  },
  tagFilterText: {
    fontSize: 13,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  tagFilterTextActive: {
    color: colors.text,
  },
  tagFilterCount: {
    fontSize: 11,
    marginLeft: 4,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 8,
  },
  tagFilterCountActive: {
    color: colors.text,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  
  // Restricted Access
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
    fontSize: 16,
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
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  // View toggle
  viewToggle: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 8,
    padding: 2,
  },
  viewToggleBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  viewToggleBtnActive: {
    backgroundColor: '#007AFF',
  },

  // Master feed
  feedContainer: { paddingBottom: 20 },
  feedSection: { marginBottom: 8 },
  feedSectionHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 16, paddingVertical: 10,
  },
  feedSectionTitle: { fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 },
  feedSectionCount: { fontSize: 12, color: colors.textTertiary },
  feedBadge: {
    backgroundColor: '#FF9500', borderRadius: 10,
    minWidth: 20, height: 20, alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: 6,
  },
  feedBadgeText: { fontSize: 11, fontWeight: '800', color: colors.text },

  // Suggested action cards
  feedSuggestedCard: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 12, marginBottom: 6,
    backgroundColor: colors.card, borderRadius: 14, padding: 12,
    borderWidth: 1, borderColor: colors.surface,
  },
  feedSuggestedIcon: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center', marginRight: 10,
  },
  feedSuggestedTitle: { fontSize: 14, fontWeight: '700', color: colors.text },
  feedSuggestedDesc: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  feedSuggestedMsg: { fontSize: 11, color: colors.textTertiary, fontStyle: 'italic', marginTop: 4 },

  // Mini avatars
  feedMiniAvatar: { width: 22, height: 22, borderRadius: 6, borderWidth: 1, borderColor: colors.surface },
  feedMiniAvatarPlaceholder: {
    width: 22, height: 22, borderRadius: 6,
    backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center',
  },
  feedMiniAvatarText: { fontSize: 10, fontWeight: '700', color: colors.textTertiary },

  // Upcoming campaign cards
  feedUpcomingCard: {
    marginHorizontal: 12, marginBottom: 6,
    backgroundColor: colors.card, borderRadius: 14, padding: 12,
    borderWidth: 1, borderColor: '#AF52DE30',
  },
  feedUpcomingTitle: { fontSize: 14, fontWeight: '600', color: colors.text },
  feedUpcomingDesc: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  feedCampaignBadge: {
    backgroundColor: '#AF52DE20', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
  },
  feedCampaignBadgeText: { fontSize: 10, fontWeight: '600', color: '#AF52DE' },

  // Event cards
  feedEventCard: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 12, marginBottom: 4,
    backgroundColor: colors.card, borderRadius: 14, padding: 12,
  },
  feedEventAvatarGroup: { position: 'relative', marginRight: 10 },
  feedEventAvatar: { width: 44, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.surface },
  feedEventAvatarPlaceholder: {
    width: 44, height: 44, borderRadius: 12,
    backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center',
  },
  feedEventAvatarText: { fontSize: 16, fontWeight: '700', color: colors.textTertiary },
  feedEventIconBadge: {
    position: 'absolute', bottom: -3, right: -3,
    width: 20, height: 20, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: colors.card,
  },
  feedEventContent: { flex: 1 },
  feedEventName: { fontSize: 14, fontWeight: '700', color: colors.text },
  feedEventTitle: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },
  feedEventDesc: { fontSize: 12, color: colors.textTertiary, marginTop: 1 },
  feedEventTime: { fontSize: 11, color: colors.borderLight, fontWeight: '500', marginLeft: 6 },
  feedInboundBadge: { backgroundColor: '#30D15820', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  feedInboundBadgeText: { fontSize: 8, fontWeight: '700', color: '#30D158' },
  feedMiniTag: { backgroundColor: colors.surface, paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  feedMiniTagText: { fontSize: 8, fontWeight: '600', color: colors.textTertiary },

  // Feed empty state
  feedEmpty: { alignItems: 'center', paddingVertical: 40 },
  feedEmptyText: { fontSize: 16, color: colors.textSecondary, marginTop: 8 },
  feedEmptySubtext: { fontSize: 13, color: colors.textTertiary, marginTop: 4 },
});