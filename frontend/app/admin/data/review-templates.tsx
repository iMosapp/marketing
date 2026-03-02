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

import { useThemeStore } from '../../../store/themeStore';
interface TemplateSent {
  _id: string;
  template_name?: string;
  user_name?: string;
  contact_name?: string;
  contact_phone?: string;
  status?: string;
  created_at: string;
}

export default function ReviewTemplatesDataScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const [templates, setTemplates] = useState<TemplateSent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadTemplates = async () => {
    try {
      const response = await api.get('/admin/data/review-templates');
      setTemplates(response.data || []);
    } catch (error) {
      console.error('Failed to load review templates:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadTemplates();
  }, []);

  const renderTemplate = ({ item }: { item: TemplateSent }) => (
    <View style={styles.templateItem}>
      <View style={styles.templateIcon}>
        <Ionicons name="star" size={18} color="#FFD60A" />
      </View>
      <View style={styles.templateContent}>
        <View style={styles.templateHeader}>
          <Text style={styles.contactName}>{item.contact_name || item.contact_phone || 'Unknown'}</Text>
          <Text style={styles.date}>{format(new Date(item.created_at), 'MMM d, h:mm a')}</Text>
        </View>
        <Text style={styles.userName}>Sent by: {item.user_name || 'System'}</Text>
        {item.template_name && (
          <Text style={styles.templateName}>Template: {item.template_name}</Text>
        )}
        {item.status && (
          <View style={[styles.statusBadge, { backgroundColor: item.status === 'sent' ? '#34C75920' : '#FF950020' }]}>
            <Text style={[styles.statusText, { color: item.status === 'sent' ? '#34C759' : '#FF9500' }]}>{item.status}</Text>
          </View>
        )}
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#FFD60A" />
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
        <Text style={styles.title}>Review Templates Sent</Text>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{templates.length}</Text>
        </View>
      </View>

      <FlatList
        data={templates}
        renderItem={renderTemplate}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FFD60A" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="star-outline" size={64} color={colors.surface} />
            <Text style={styles.emptyText}>No review templates sent yet</Text>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
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
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  countBadge: {
    backgroundColor: '#FFD60A20',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countText: {
    color: '#FFD60A',
    fontSize: 13,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  templateItem: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  templateIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#FFD60A20',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  templateContent: {
    flex: 1,
  },
  templateHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  contactName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  date: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  userName: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  templateName: {
    fontSize: 13,
    color: '#AEAEB2',
    marginTop: 4,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginTop: 6,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 100,
  },
  emptyText: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 12,
  },
});
