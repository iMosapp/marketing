import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { format } from 'date-fns';
import api from '../../services/api';

interface Contact {
  _id: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  email?: string;
  user_name?: string;
  store_name?: string;
  status?: string;
  created_at: string;
}

export default function AdminContactsScreen() {
  const router = useRouter();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const loadContacts = async () => {
    try {
      const response = await api.get('/admin/contacts');
      setContacts(response.data || []);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadContacts();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadContacts();
  }, []);

  const filteredContacts = contacts.filter((contact) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const fullName = `${contact.first_name || ''} ${contact.last_name || ''}`.toLowerCase();
    return (
      fullName.includes(query) ||
      contact.phone?.includes(query) ||
      contact.email?.toLowerCase().includes(query)
    );
  });

  const renderContact = ({ item }: { item: Contact }) => (
    <TouchableOpacity 
      style={styles.contactItem}
      onPress={() => router.push(`/contact/${item._id}` as any)}
    >
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>
          {(item.first_name?.[0] || '') + (item.last_name?.[0] || '') || '?'}
        </Text>
      </View>
      <View style={styles.contactContent}>
        <View style={styles.contactHeader}>
          <Text style={styles.contactName}>
            {item.first_name || ''} {item.last_name || 'Unknown'}
          </Text>
          {item.status && (
            <View style={[styles.statusBadge, { 
              backgroundColor: item.status === 'sold' ? '#34C75920' : 
                             item.status === 'active' ? '#007AFF20' : '#8E8E9320' 
            }]}>
              <Text style={[styles.statusText, { 
                color: item.status === 'sold' ? '#34C759' : 
                       item.status === 'active' ? '#007AFF' : '#8E8E93' 
              }]}>{item.status}</Text>
            </View>
          )}
        </View>
        {item.phone && <Text style={styles.contactPhone}>{item.phone}</Text>}
        {item.email && <Text style={styles.contactEmail}>{item.email}</Text>}
        <View style={styles.contactFooter}>
          <Text style={styles.assignedTo}>{item.user_name || 'Unassigned'}</Text>
          {item.store_name && <Text style={styles.storeName}> • {item.store_name}</Text>}
        </View>
      </View>
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#FF9500" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>All Contacts</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{filteredContacts.length}</Text>
        </View>
      </View>

      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={18} color="#8E8E93" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search contacts..."
            placeholderTextColor="#8E8E93"
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={18} color="#8E8E93" />
            </TouchableOpacity>
          )}
        </View>
      </View>

      <FlatList
        data={filteredContacts}
        renderItem={renderContact}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FF9500" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="people-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>
              {searchQuery ? 'No contacts found' : 'No contacts yet'}
            </Text>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  countBadge: {
    backgroundColor: '#FF950020',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#FF9500',
    fontSize: 13,
    fontWeight: '600',
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    color: '#FFF',
  },
  listContent: {
    padding: 16,
  },
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FF950030',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  avatarText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF9500',
  },
  contactContent: {
    flex: 1,
  },
  contactHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  contactName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    flex: 1,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  contactPhone: {
    fontSize: 13,
    color: '#AEAEB2',
    marginTop: 2,
  },
  contactEmail: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 1,
  },
  contactFooter: {
    flexDirection: 'row',
    marginTop: 4,
  },
  assignedTo: {
    fontSize: 12,
    color: '#6E6E73',
  },
  storeName: {
    fontSize: 12,
    color: '#6E6E73',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 100,
  },
  emptyText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 12,
  },
});
