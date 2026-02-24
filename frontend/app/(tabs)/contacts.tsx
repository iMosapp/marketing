import React, { useState, useEffect } from 'react';
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
  const [newContactPhone, setNewContactPhone] = useState('');
  
  // Check if running on web platform
  const isWeb = Platform.OS === 'web';
  
  // Check if user has restricted access
  const isPending = user?.status === 'pending';
  
  useEffect(() => {
    if (!isPending) {
      loadContacts();
      loadTags();
    }
  }, [user, isPending]);
  
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
  
  const loadContacts = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      const data = await contactsAPI.getAll(user._id, search || undefined);
      setContacts(data);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await Promise.all([loadContacts(), loadTags()]);
    setRefreshing(false);
  };
  
  const handleSearch = async (text: string) => {
    setSearch(text);
    if (text.length > 2 || text.length === 0) {
      try {
        const data = await contactsAPI.getAll(user?._id || '', text || undefined);
        setContacts(data);
      } catch (error) {
        console.error('Search failed:', error);
      }
    }
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
  
  // Handle adding a new contact - navigate to thread with Quick Contact Panel
  const handleAddNewContact = () => {
    if (!newContactPhone.trim()) {
      showSimpleAlert('Phone Required', 'Please enter a phone number');
      return;
    }
    
    // Format phone number
    let phone = newContactPhone.trim();
    if (!phone.startsWith('+')) {
      phone = '+1' + phone.replace(/\D/g, '');
    }
    
    setShowAddContactModal(false);
    setNewContactPhone('');
    
    // Navigate to thread with the phone number - Quick Contact Panel will show
    router.push({
      pathname: `/thread/${phone}`,
      params: {
        contact_name: phone,
        contact_phone: phone,
      }
    });
  };
  
  // Filter contacts by selected tag
  const filteredContacts = selectedTag 
    ? contacts.filter(c => c.tags && c.tags.includes(selectedTag))
    : contacts;

  const handleTagFilter = (tagName: string | null) => {
    setSelectedTag(tagName === selectedTag ? null : tagName);
  };
  
  const renderContact = ({ item }: { item: any }) => {
    // Find tag colors for this contact's tags
    const contactTags = item.tags?.map((tagName: string) => {
      const tagInfo = tags.find(t => t.name === tagName);
      return tagInfo ? { name: tagName, color: tagInfo.color } : { name: tagName, color: '#8E8E93' };
    }) || [];

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
  };
  
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
            data-testid="add-contact-btn"
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
          keyExtractor={(item) => item._id || item.id}
          contentContainerStyle={styles.listContent}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
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
        onRequestClose={() => setShowAddContactModal(false)}
      >
        <View style={styles.addContactModalOverlay}>
          <View style={styles.addContactModalContent}>
            <View style={styles.addContactModalHeader}>
              <Text style={styles.addContactModalTitle}>Add New Contact</Text>
              <TouchableOpacity onPress={() => setShowAddContactModal(false)}>
                <Ionicons name="close" size={24} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            
            <Text style={styles.addContactModalSubtitle}>
              Enter the phone number to start
            </Text>
            
            <View style={styles.addContactInputContainer}>
              <Ionicons name="call-outline" size={20} color="#8E8E93" />
              <TextInput
                style={styles.addContactInput}
                placeholder="Phone number"
                placeholderTextColor="#6E6E73"
                value={newContactPhone}
                onChangeText={setNewContactPhone}
                keyboardType="phone-pad"
                autoFocus
                data-testid="new-contact-phone-input"
              />
            </View>
            
            <Text style={styles.addContactHint}>
              You'll be able to add name, photo, tags, and send a message in the next step
            </Text>
            
            <View style={styles.addContactModalActions}>
              <TouchableOpacity 
                style={styles.addContactCancelBtn}
                onPress={() => {
                  setShowAddContactModal(false);
                  setNewContactPhone('');
                }}
              >
                <Text style={styles.addContactCancelText}>Cancel</Text>
              </TouchableOpacity>
              
              <TouchableOpacity 
                style={[
                  styles.addContactContinueBtn,
                  !newContactPhone.trim() && styles.addContactContinueBtnDisabled
                ]}
                onPress={handleAddNewContact}
                disabled={!newContactPhone.trim()}
                data-testid="new-contact-continue-btn"
              >
                <Text style={styles.addContactContinueText}>Continue</Text>
                <Ionicons name="arrow-forward" size={18} color="#FFF" />
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
});