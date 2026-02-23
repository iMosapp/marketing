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

interface AIMessage {
  _id: string;
  contact_name?: string;
  user_name?: string;
  prompt?: string;
  response?: string;
  ai_type?: string;
  created_at: string;
}

export default function AIMessagesDataScreen() {
  const router = useRouter();
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadMessages = async () => {
    try {
      const response = await api.get('/admin/data/ai-messages');
      setMessages(response.data || []);
    } catch (error) {
      console.error('Failed to load AI messages:', error);
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

  const renderMessage = ({ item }: { item: AIMessage }) => (
    <View style={styles.messageItem}>
      <View style={styles.aiIcon}>
        <Ionicons name="sparkles" size={18} color="#AF52DE" />
      </View>
      <View style={styles.messageContent}>
        <View style={styles.messageHeader}>
          <Text style={styles.contactName}>{item.contact_name || 'AI Interaction'}</Text>
          <Text style={styles.date}>{format(new Date(item.created_at), 'MMM d, h:mm a')}</Text>
        </View>
        <Text style={styles.userName}>via {item.user_name || 'System'}</Text>
        {item.ai_type && (
          <View style={styles.typeBadge}>
            <Text style={styles.typeText}>{item.ai_type}</Text>
          </View>
        )}
        {item.prompt && (
          <Text style={styles.promptText} numberOfLines={2}>Prompt: {item.prompt}</Text>
        )}
        {item.response && (
          <Text style={styles.responseText} numberOfLines={2}>Response: {item.response}</Text>
        )}
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#AF52DE" />
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
        <Text style={styles.title}>AI Messages</Text>
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
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#AF52DE" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="sparkles-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No AI messages yet</Text>
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
    backgroundColor: '#AF52DE20',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#AF52DE',
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
  aiIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#AF52DE20',
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
  typeBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#AF52DE30',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginTop: 6,
  },
  typeText: {
    fontSize: 11,
    color: '#AF52DE',
    fontWeight: '500',
  },
  promptText: {
    fontSize: 13,
    color: '#AEAEB2',
    marginTop: 6,
  },
  responseText: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 4,
    fontStyle: 'italic',
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
