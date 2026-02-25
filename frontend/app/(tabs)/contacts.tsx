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
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
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
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [search, setSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  
  // Add Contact Modal state
  const [showAddContactModal, setShowAddContactModal] = useState(false);
  const [newContactFirstName, setNewContactFirstName] = useState('');
  const [newContactLastName, setNewContactLastName] = useState('');
  const [newContactPhone, setNewContactPhone] = useState('');
  const [newContactEmail, setNewContactEmail] = useState('');
  const [savingContact, setSavingContact] = useState(false);
  
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
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.restrictedContainer}>
          <View style={styles.restrictedIcon}>
            <Ionicons name="lock-closed" size={48} color="#FF9500" />
          </View>
          <Text style={styles.restrictedTitle}>Access Pending</Text>
          <Text style={styles.restrictedText}>
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
          contact_photo: contact.photo || '',
        }
      });
    } catch (error) {
      // If send fails, just navigate anyway - the thread will handle it
      router.push({
        pathname: `/thread/${contact._id}`,
        params: {
          contact_name: `${contact.first_name} ${contact.last_name || ''}`.trim(),
          contact_phone: contact.phone,
          contact_photo: contact.photo || '',
        }
      });
    }
  };
  
  // Handle adding a new contact - create via API then navigate to thread
  const handleAddNewContact = async () => {
    if (!newContactPhone.trim()) {
      showSimpleAlert('Phone Required', 'Please enter a phone number');
      return;
    }
    
    // Format phone number
    let phone = newContactPhone.trim();
    if (!phone.startsWith('+')) {
      phone = '+1' + phone.replace(/\D/g, '');
    }
    
    const firstName = newContactFirstName.trim() || phone;
    const lastName = newContactLastName.trim();
    
    setSavingContact(true);
    try {
      await contactsAPI.create(user._id, {
        first_name: firstName,
        last_name: lastName,
        phone: phone,
        email: newContactEmail.trim().toLowerCase() || undefined,
      });
      
      setShowAddContactModal(false);
      setNewContactFirstName('');
      setNewContactLastName('');
      setNewContactPhone('');
      setNewContactEmail('');
      
      // Refresh contacts list
      loadContacts();
      
      // Navigate to thread
      router.push({
        pathname: `/thread/${phone}`,
        params: {
          contact_name: `${firstName} ${lastName}`.trim(),
          contact_phone: phone,
        }
      });
    } catch (err: any) {
      showSimpleAlert('Error', err?.response?.data?.detail || 'Failed to save contact');
    } finally {
      setSavingContact(false);
    }
  };

  const resetAddContactModal = () => {
    setShowAddContactModal(false);
    setNewContactFirstName('');
    setNewContactLastName('');
    setNewContactPhone('');
    setNewContactEmail('');
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
  const ListSeparator = useCallback(() => <View style={styles.separator} />, []);
  
  // Pre-build tag lookup map for O(1) access
  const tagMap = useMemo(() => {
    const map: Record<string, string> = {};
    tags.forEach(t => { map[t.name] = t.color; });
    return map;
  }, [tags]);

  const renderContact = useCallback(({ item }: { item: any }) => {
    const contactTags = item.tags?.map((tagName: string) => ({
      name: tagName,
      color: tagMap[tagName] || '#8E8E93',
    })) || [];

    return (
    <TouchableOpacity
      style={styles.contactItem}
      onPress={() => router.push(`/contact/${item._id}`)}
    >
      {item.photo ? (
        <Image source={{ uri: item.photo }} style={styles.photoAvatar} />
      ) : (
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {item.first_name?.[0] || ''}{item.last_name?.[0] || ''}
          </Text>
        </View>
      )}
      
      <View style={styles.contactInfo}>
        <Text style={styles.contactName}>
          {item.first_name} {item.last_name || ''}
        </Text>
        <Text style={styles.contactPhone}>{item.phone}</Text>
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
  }, [tagMap, router, user]);
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Contacts</Text>
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
            onPress={() => router.push('/contacts/import')}
            style={styles.headerButton}
          >
            <Ionicons name="download-outline" size={26} color="#007AFF" />
          </TouchableOpacity>
          <TouchableOpacity 
            onPress={() => setShowAddContactModal(true)}
            accessibilityRole="button"
            accessibilityLabel="Add new contact"
            data-testid="add-contact-button"
          >
            <Ionicons name="add-circle" size={32} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </View>
      
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#8E8E93" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search contacts"
          placeholderTextColor="#8E8E93"
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
              <Ionicons name="people-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No contacts yet</Text>
              <Text style={styles.emptySubtext}>Tap + to add or import contacts</Text>
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
      
      {/* Add Contact Modal */}
      <Modal
        visible={showAddContactModal}
        transparent
        animationType="fade"
        onRequestClose={resetAddContactModal}
      >
        <View style={styles.addContactModalOverlay}>
          <View style={styles.addContactModalContent}>
            <View style={styles.addContactModalHeader}>
              <Text style={styles.addContactModalTitle}>Add New Contact</Text>
              <TouchableOpacity onPress={resetAddContactModal}>
                <Ionicons name="close" size={24} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            
            <Text style={styles.addContactModalSubtitle}>
              Fill in their details while you're with them
            </Text>
            
            <View style={{ gap: 10 }}>
              <View style={styles.addContactNameRow}>
                <View style={[styles.addContactInputContainer, { flex: 1 }]}>
                  <Ionicons name="person-outline" size={18} color="#8E8E93" />
                  <TextInput
                    style={styles.addContactInput}
                    placeholder="First name"
                    placeholderTextColor="#6E6E73"
                    value={newContactFirstName}
                    onChangeText={setNewContactFirstName}
                    autoCapitalize="words"
                    autoFocus
                    data-testid="new-contact-first-name-input"
                  />
                </View>
                <View style={[styles.addContactInputContainer, { flex: 1 }]}>
                  <TextInput
                    style={styles.addContactInput}
                    placeholder="Last name"
                    placeholderTextColor="#6E6E73"
                    value={newContactLastName}
                    onChangeText={setNewContactLastName}
                    autoCapitalize="words"
                    data-testid="new-contact-last-name-input"
                  />
                </View>
              </View>

              <View style={styles.addContactInputContainer}>
                <Ionicons name="call-outline" size={18} color="#8E8E93" />
                <TextInput
                  style={styles.addContactInput}
                  placeholder="Phone number"
                  placeholderTextColor="#6E6E73"
                  value={newContactPhone}
                  onChangeText={setNewContactPhone}
                  keyboardType="phone-pad"
                  data-testid="new-contact-phone-input"
                />
              </View>

              <View style={styles.addContactInputContainer}>
                <Ionicons name="mail-outline" size={18} color="#8E8E93" />
                <TextInput
                  style={styles.addContactInput}
                  placeholder="Email (optional)"
                  placeholderTextColor="#6E6E73"
                  value={newContactEmail}
                  onChangeText={setNewContactEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  data-testid="new-contact-email-input"
                />
              </View>
            </View>
            
            <View style={styles.addContactModalActions}>
              <TouchableOpacity 
                style={styles.addContactCancelBtn}
                onPress={resetAddContactModal}
              >
                <Text style={styles.addContactCancelText}>Cancel</Text>
              </TouchableOpacity>
              
              <TouchableOpacity 
                style={[
                  styles.addContactContinueBtn,
                  !newContactPhone.trim() && styles.addContactContinueBtnDisabled
                ]}
                onPress={handleAddNewContact}
                disabled={!newContactPhone.trim() || savingContact}
                data-testid="new-contact-save-btn"
              >
                {savingContact ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <>
                    <Text style={styles.addContactContinueText}>Save & Message</Text>
                    <Ionicons name="chatbubble-outline" size={16} color="#FFF" />
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
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
    color: '#FFF',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
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
    color: '#FFF',
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
    borderRadius: 24,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  photoAvatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    marginRight: 12,
  },
  avatarText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
  contactInfo: {
    flex: 1,
  },
  contactName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  contactPhone: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 4,
  },
  tags: {
    flexDirection: 'row',
    gap: 4,
    flexWrap: 'wrap',
  },
  tag: {
    backgroundColor: '#1C1C1E',
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
    backgroundColor: '#2C2C2E',
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
    color: '#FFF',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 15,
    color: '#8E8E93',
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
    backgroundColor: '#1C1C1E',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  tagFilterChipActive: {
    backgroundColor: '#007AFF',
  },
  tagFilterText: {
    fontSize: 13,
    color: '#8E8E93',
    fontWeight: '500',
  },
  tagFilterTextActive: {
    color: '#FFF',
  },
  tagFilterCount: {
    fontSize: 11,
    color: '#6E6E73',
    marginLeft: 4,
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 8,
  },
  tagFilterCountActive: {
    color: '#FFF',
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
    color: '#FFF',
    marginBottom: 12,
  },
  restrictedText: {
    fontSize: 16,
    color: '#8E8E93',
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
  // Add Contact Modal Styles
  addContactModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  addContactModalContent: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    maxWidth: 400,
  },
  addContactModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  addContactModalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
  },
  addContactModalSubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 20,
  },
  addContactInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
    gap: 10,
  },
  addContactNameRow: {
    flexDirection: 'row',
    gap: 10,
  },
  addContactInput: {
    flex: 1,
    fontSize: 17,
    color: '#FFF',
  },
  addContactHint: {
    fontSize: 12,
    color: '#6E6E73',
    marginTop: 12,
    lineHeight: 18,
  },
  addContactModalActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  addContactCancelBtn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#2C2C2E',
  },
  addContactCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#8E8E93',
  },
  addContactContinueBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#007AFF',
    gap: 6,
  },
  addContactContinueBtnDisabled: {
    opacity: 0.5,
  },
  addContactContinueText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
});