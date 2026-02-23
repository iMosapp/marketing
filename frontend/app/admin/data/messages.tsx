import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { format } from 'date-fns';
import api from '../../../services/api';

interface Message {
  _id: string;
  contact_name?: string;
  contact_phone?: string;
  user_name?: string;
  content: string;
  direction: 'inbound' | 'outbound';
  created_at: string;
  status?: string;
}

export default function MessagesDataScreen() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadMessages = async () => {
    try {
      const response = await api.get('/admin/data/messages');
      setMessages(response.data || []);
    } catch (error) {
      console.error('Failed to load messages:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadMessages();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadMessages();
  }, []);

  const renderMessage = ({ item }: { item: Message }) => (
    <View style={styles.messageItem}>
      <View style={[styles.directionIcon, { backgroundColor: item.direction === 'inbound' ? '#34C75920' : '#007AFF20' }]}>
        <Ionicons 
          name={item.direction === 'inbound' ? 'arrow-down' : 'arrow-up'} 
          size={16} 
          color={item.direction === 'inbound' ? '#34C759' : '#007AFF'} 
        />
      </View>
      <View style={styles.messageContent}>
        <View style={styles.messageHeader}>
          <Text style={styles.contactName}>{item.contact_name || item.contact_phone || 'Unknown'}</Text>
          <Text style={styles.date}>{format(new Date(item.created_at), 'MMM d, h:mm a')}</Text>
        </View>
        <Text style={styles.userName}>via {item.user_name || 'System'}</Text>
        <Text style={styles.messageText} numberOfLines={2}>{item.content}</Text>
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
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
        <Text style={styles.title}>Messages</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{messages.length}</Text>
        </View>
      </View>

      <FlatList
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="chatbubbles-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No messages yet</Text>
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
    backgroundColor: '#007AFF20',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#007AFF',
    fontSize: 13,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  messageItem: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  directionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  messageContent: {
    flex: 1,
  },
  messageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  contactName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  date: {
    fontSize: 12,
    color: '#8E8E93',
  },
  userName: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  messageText: {
    fontSize: 14,
    color: '#AEAEB2',
    marginTop: 6,
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
