import React, {
  useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Pressable,
  ScrollView,
  ActivityIndicator,
  Alert,
  Image,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { format } from 'date-fns';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { useToast } from '../../components/common/Toast';

import { useThemeStore } from '../../store/themeStore';
const IS_WEB = Platform.OS === 'web';

interface Broadcast {
  id: string;
  name: string;
  message: string;
  status: 'draft' | 'scheduled' | 'sending' | 'sent' | 'failed';
  filters: {
    tags: string[];
    exclude_tags: string[];
    purchase_month: number | null;
    purchase_year: number | null;
    days_since_purchase: number | null;
  };
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  scheduled_at: string | null;
  sent_at: string | null;
  created_at: string;
  media_urls: string[];
}

export default function BroadcastDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuthStore();
  
const { showToast } = useToast();
    const [broadcast, setBroadcast] = useState<Broadcast | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchBroadcast();
  }, [id]);

  const fetchBroadcast = async () => {
    if (!id || !user?._id) return;
    
    try {
      const res = await api.get(`/broadcast/${id}?user_id=${user._id}`);
      if (res.data.success) {
        setBroadcast(res.data.broadcast);
      }
    } catch (error) {
      console.error('Error fetching broadcast:', error);
      Alert.alert('Error', 'Failed to load broadcast');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    Alert.alert(
      'Send Broadcast',
      `Are you sure you want to send this broadcast to ${broadcast?.recipient_count} contacts?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Send Now',
          style: 'default',
          onPress: async () => {
            setSending(true);
            try {
              const res = await api.post(`/broadcast/${id}/send?user_id=${user?._id}`);
              if (res.data.success) {
                Alert.alert('Success', res.data.message);
                fetchBroadcast(); // Refresh to show updated status
              }
            } catch (error: any) {
              Alert.alert('Error', error.response?.data?.detail || 'Failed to send broadcast');
            } finally {
              setSending(false);
            }
          },
        },
      ]
    );
  };

  const handleDuplicate = async () => {
    try {
      const res = await api.post(`/broadcast/${id}/duplicate?user_id=${user?._id}`);
      if (res.data.success) {
        showToast('Broadcast duplicated');
        router.push(`/broadcast/${res.data.broadcast.id}`);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to duplicate broadcast');
    }
  };

  const handleDelete = async () => {
    Alert.alert(
      'Delete Broadcast',
      'Are you sure you want to delete this broadcast? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            setDeleting(true);
            try {
              await api.delete(`/broadcast/${id}?user_id=${user?._id}`);
              showToast('Broadcast deleted');
              router.back();
            } catch (error: any) {
              Alert.alert('Error', error.response?.data?.detail || 'Failed to delete broadcast');
            } finally {
              setDeleting(false);
            }
          },
        },
      ]
    );
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft': return colors.textSecondary;
      case 'scheduled': return '#FF9500';
      case 'sending': return '#007AFF';
      case 'sent': return '#34C759';
      case 'failed': return '#FF3B30';
      default: return colors.textSecondary;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'draft': return 'document-outline';
      case 'scheduled': return 'time-outline';
      case 'sending': return 'paper-plane-outline';
      case 'sent': return 'checkmark-circle-outline';
      case 'failed': return 'alert-circle-outline';
      default: return 'document-outline';
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  if (!broadcast) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>Broadcast not found</Text>
          <Pressable style={styles.backButtonLarge} onPress={() => router.back()} testID="go-back-btn">
            <Text style={styles.backButtonText}>Go Back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const canSend = broadcast.status === 'draft' || broadcast.status === 'scheduled';
  const canEdit = broadcast.status === 'draft' || broadcast.status === 'scheduled';
  const canDelete = broadcast.status !== 'sending' && broadcast.status !== 'sent';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton} testID="back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </Pressable>
        <Text style={styles.headerTitle}>Broadcast Details</Text>
        <Pressable onPress={handleDuplicate} style={styles.duplicateButton} testID="duplicate-btn">
          <Ionicons name="copy-outline" size={22} color="#007AFF" />
        </Pressable>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Status Banner */}
        <View style={[styles.statusBanner, { backgroundColor: `${getStatusColor(broadcast.status)}20` }]}>
          <Ionicons name={getStatusIcon(broadcast.status)} size={24} color={getStatusColor(broadcast.status)} />
          <View style={styles.statusInfo}>
            <Text style={[styles.statusLabel, { color: getStatusColor(broadcast.status) }]}>
              {broadcast.status.charAt(0).toUpperCase() + broadcast.status.slice(1)}
            </Text>
            {broadcast.scheduled_at && broadcast.status === 'scheduled' && (
              <Text style={styles.statusSubtext}>
                Scheduled for {format(new Date(broadcast.scheduled_at), 'MMM d, yyyy h:mm a')}
              </Text>
            )}
            {broadcast.sent_at && broadcast.status === 'sent' && (
              <Text style={styles.statusSubtext}>
                Sent on {format(new Date(broadcast.sent_at), 'MMM d, yyyy h:mm a')}
              </Text>
            )}
          </View>
        </View>

        {/* Broadcast Name */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Name</Text>
          <Text style={styles.broadcastName}>{broadcast.name}</Text>
        </View>

        {/* Message */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Message</Text>
          <Text style={styles.messageText}>{broadcast.message}</Text>
        </View>

        {/* Media Attachments */}
        {broadcast.media_urls?.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardLabel}>Media Attachments</Text>
            <View style={styles.mediaGrid}>
              {broadcast.media_urls.map((url, index) => (
                <Image
                  key={index}
                  source={{ uri: url }}
                  style={styles.mediaImage}
                  resizeMode="cover"
                />
              ))}
            </View>
          </View>
        )}

        {/* Stats */}
        <View style={styles.statsCard}>
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{broadcast.recipient_count}</Text>
            <Text style={styles.statLabel}>Recipients</Text>
          </View>
          {broadcast.status === 'sent' && (
            <>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Text style={[styles.statValue, { color: '#34C759' }]}>{broadcast.sent_count}</Text>
                <Text style={styles.statLabel}>Sent</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Text style={[styles.statValue, { color: '#FF3B30' }]}>{broadcast.failed_count}</Text>
                <Text style={styles.statLabel}>Failed</Text>
              </View>
            </>
          )}
        </View>

        {/* Filters Used */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Filters Applied</Text>
          <View style={styles.filtersContainer}>
            {broadcast.filters.tags?.length > 0 && (
              <View style={styles.filterRow}>
                <Ionicons name="pricetag" size={16} color="#007AFF" />
                <Text style={styles.filterText}>
                  Tags: {broadcast.filters.tags.join(', ')}
                </Text>
              </View>
            )}
            {broadcast.filters.exclude_tags?.length > 0 && (
              <View style={styles.filterRow}>
                <Ionicons name="pricetag-outline" size={16} color="#FF3B30" />
                <Text style={styles.filterText}>
                  Excluded: {broadcast.filters.exclude_tags.join(', ')}
                </Text>
              </View>
            )}
            {broadcast.filters.days_since_purchase && (
              <View style={styles.filterRow}>
                <Ionicons name="calendar" size={16} color="#FF9500" />
                <Text style={styles.filterText}>
                  Purchased {broadcast.filters.days_since_purchase}+ days ago
                </Text>
              </View>
            )}
            {broadcast.filters.purchase_month && (
              <View style={styles.filterRow}>
                <Ionicons name="calendar-outline" size={16} color="#FF9500" />
                <Text style={styles.filterText}>
                  Purchased in month {broadcast.filters.purchase_month}
                  {broadcast.filters.purchase_year && `, ${broadcast.filters.purchase_year}`}
                </Text>
              </View>
            )}
            {!broadcast.filters.tags?.length && 
             !broadcast.filters.exclude_tags?.length && 
             !broadcast.filters.days_since_purchase && 
             !broadcast.filters.purchase_month && (
              <Text style={styles.noFiltersText}>All contacts</Text>
            )}
          </View>
        </View>

        {/* Created Date */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Created</Text>
          <Text style={styles.dateText}>
            {format(new Date(broadcast.created_at), 'MMMM d, yyyy h:mm a')}
          </Text>
        </View>

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          {canSend && (
            <Pressable
              style={styles.sendButton}
              onPress={handleSend}
              disabled={sending}
              testID="send-btn"
            >
              {sending ? (
                <ActivityIndicator size="small" color={colors.text} />
              ) : (
                <>
                  <Ionicons name="send" size={20} color={colors.text} />
                  <Text style={styles.sendButtonText}>Send Now</Text>
                </>
              )}
            </Pressable>
          )}
          
          {canDelete && (
            <Pressable
              style={styles.deleteButton}
              onPress={handleDelete}
              disabled={deleting}
              testID="delete-btn"
            >
              {deleting ? (
                <ActivityIndicator size="small" color="#FF3B30" />
              ) : (
                <>
                  <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                  <Text style={styles.deleteButtonText}>Delete</Text>
                </>
              )}
            </Pressable>
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  errorText: {
    fontSize: 19,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  backButtonLarge: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  backButtonText: {
    color: colors.text,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  duplicateButton: {
    padding: 4,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  statusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 16,
    marginBottom: 16,
    gap: 12,
  },
  statusInfo: {
    flex: 1,
  },
  statusLabel: {
    fontSize: 18,
    fontWeight: '600',
  },
  statusSubtext: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  cardLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  broadcastName: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  messageText: {
    fontSize: 18,
    color: colors.text,
    lineHeight: 24,
  },
  mediaGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  mediaImage: {
    width: 100,
    height: 100,
    borderRadius: 12,
  },
  statsCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 20,
    marginBottom: 12,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 28,
    fontWeight: '700',
    color: '#007AFF',
  },
  statLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  statDivider: {
    width: 1,
    backgroundColor: colors.surface,
    marginHorizontal: 16,
  },
  filtersContainer: {
    gap: 10,
  },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  filterText: {
    fontSize: 16,
    color: colors.text,
    flex: 1,
  },
  noFiltersText: {
    fontSize: 16,
    color: colors.textSecondary,
    fontStyle: 'italic',
  },
  dateText: {
    fontSize: 17,
    color: colors.text,
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  sendButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
    backgroundColor: '#007AFF',
    borderRadius: 14,
  },
  sendButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  deleteButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
    backgroundColor: 'rgba(255, 59, 48, 0.15)',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#FF3B30',
  },
  deleteButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FF3B30',
  },
});
