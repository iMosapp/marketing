import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { campaignsAPI } from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { FS, EYEBROW } from '../../constants/typography';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

interface Enrollment {
  _id: string;
  campaign_id: string;
  campaign_name: string;
  contact_id: string;
  contact_name: string;
  contact_phone: string;
  current_step: number;
  total_steps: number;
  status: string;
  next_send_at: string | null;
  messages_sent: any[];
  enrolled_at: string;
}

export default function CampaignDashboardScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [upcomingCount, setUpcomingCount] = useState(0);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  
  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [user])
  );
  
  const loadData = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      
      const pendingData = await campaignsAPI.getPendingCount();
      setPendingCount(pendingData.pending);
      setUpcomingCount(pendingData.upcoming);
      
      const campaignsData = await campaignsAPI.getAll(user._id);
      
      const allEnrollments: Enrollment[] = [];
      for (const campaign of campaignsData) {
        const campEnrollments = await campaignsAPI.getEnrollments(user._id, campaign._id);
        campEnrollments.forEach((e: any) => {
          allEnrollments.push({
            ...e,
            campaign_name: campaign.name,
            total_steps: campaign.sequences?.length || 0,
          });
        });
      }
      
      allEnrollments.sort((a, b) => {
        if (a.status === 'active' && b.status !== 'active') return -1;
        if (a.status !== 'active' && b.status === 'active') return 1;
        if (a.next_send_at && b.next_send_at) {
          return new Date(a.next_send_at).getTime() - new Date(b.next_send_at).getTime();
        }
        return 0;
      });
      
      setEnrollments(allEnrollments);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };
  
  const processScheduler = async () => {
    setProcessing(true);
    try {
      const result = await campaignsAPI.processScheduler();
      
      if (result.sent > 0) {
        showAlert(
          'Messages sent',
          `Sent ${result.sent} message${result.sent !== 1 ? 's' : ''}${result.completed > 0 ? `\n${result.completed} campaign${result.completed !== 1 ? 's' : ''} completed` : ''}`,
          [{ text: 'OK', onPress: () => loadData() }]
        );
      } else {
        showSimpleAlert('No messages', 'No pending messages to send right now.');
      }
    } catch (error) {
      console.error('Failed to process scheduler:', error);
      showSimpleAlert('Error', 'Failed to process pending messages');
    } finally {
      setProcessing(false);
    }
  };
  
  const formatNextSend = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffMs < 0) return 'Ready to send';
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Tomorrow';
    if (diffDays < 7) return `${diffDays} days`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) !== 1 ? 's' : ''}`;
    return `${Math.floor(diffDays / 30)} month${Math.floor(diffDays / 30) !== 1 ? 's' : ''}`;
  };
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return colors.accent;
      case 'completed': return '#34C759';
      case 'cancelled': return '#FF3B30';
      case 'paused': return '#FF9500';
      default: return colors.textSecondary;
    }
  };
  
  const renderEnrollment = ({ item }: { item: Enrollment }) => (
    <TouchableOpacity 
      style={styles.enrollmentCard}
      onPress={() => router.push(`/contact/${item.contact_id}`)}
      {...tid(`enrollment-${item._id}`)}
    >
      <View style={styles.enrollmentHeader}>
        <View style={styles.contactInfo}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {(item.contact_name || '?').split(' ').map(n => n[0]).join('').slice(0, 2)}
            </Text>
          </View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={styles.contactName} numberOfLines={1}>{item.contact_name}</Text>
            <Text style={styles.contactPhone} numberOfLines={1}>{item.contact_phone}</Text>
          </View>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(item.status)}20` }]}>
          <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>
            {item.status}
          </Text>
        </View>
      </View>
      
      <View style={styles.campaignInfo}>
        <Ionicons name="calendar" size={16} color={colors.textSecondary} />
        <Text style={styles.campaignName} numberOfLines={1}>{item.campaign_name}</Text>
      </View>
      
      <View style={styles.progressSection}>
        <View style={styles.progressBar}>
          <View 
            style={[
              styles.progressFill, 
              { 
                width: `${item.total_steps ? Math.min(100, ((item.current_step - 1) / item.total_steps) * 100) : 0}%`,
                backgroundColor: item.status === 'completed' ? '#34C759' : colors.accent
              }
            ]} 
          />
        </View>
        <Text style={styles.progressText}>
          {item.status === 'completed' 
            ? 'Complete'
            : `Step ${item.current_step} of ${item.total_steps}`}
        </Text>
      </View>
      
      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Ionicons name="paper-plane" size={14} color={colors.textSecondary} />
          <Text style={styles.statText}>{item.messages_sent?.length || 0} sent</Text>
        </View>
        {item.status === 'active' && item.next_send_at && (
          <View style={styles.stat}>
            <Ionicons name="time" size={14} color={colors.textSecondary} />
            <Text style={styles.statText}>Next: {formatNextSend(item.next_send_at)}</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
  
  const activeEnrollments = enrollments.filter(e => e.status === 'active');
  const completedEnrollments = enrollments.filter(e => e.status === 'completed');
  const hasPending = pendingCount > 0;
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScreenHeader
        title="Campaign Dashboard"
        testID="campaign-dashboard-header"
        right={<HeaderIconButton icon="settings-outline" onPress={() => router.push('/campaigns')} testID="campaign-dashboard-settings" />}
      />
      
      <View style={styles.statsBanner}>
        <TouchableOpacity 
          style={[styles.pendingCard, hasPending && styles.pendingCardActive]}
          onPress={processScheduler}
          disabled={processing || !hasPending}
          {...tid('pending-send-card')}
        >
          {processing ? (
            <ActivityIndicator color={hasPending ? '#000' : colors.text} />
          ) : (
            <>
              <Ionicons 
                name="send" 
                size={24} 
                color={hasPending ? '#000' : colors.textSecondary} 
              />
              <Text style={[styles.pendingCount, hasPending && styles.pendingCountActive]}>
                {pendingCount}
              </Text>
              <Text style={[styles.pendingLabel, hasPending && styles.pendingLabelActive]}>
                Ready to send
              </Text>
              {hasPending && (
                <Text style={styles.tapToSend}>Tap to send now</Text>
              )}
            </>
          )}
        </TouchableOpacity>
        
        <View style={styles.statsGrid}>
          <View style={styles.statCard} {...tid('stat-active')}>
            <Text style={styles.statCardValue}>{activeEnrollments.length}</Text>
            <Text style={styles.statCardLabel}>Active</Text>
          </View>
          <View style={styles.statCard} {...tid('stat-upcoming')}>
            <Text style={styles.statCardValue}>{upcomingCount}</Text>
            <Text style={styles.statCardLabel}>Upcoming</Text>
          </View>
          <View style={styles.statCard} {...tid('stat-completed')}>
            <Text style={styles.statCardValue}>{completedEnrollments.length}</Text>
            <Text style={styles.statCardLabel}>Completed</Text>
          </View>
        </View>
      </View>
      
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlatList
          data={enrollments}
          renderItem={renderEnrollment}
          keyExtractor={(item) => item._id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent}
            />
          }
          ListHeaderComponent={() => (
            enrollments.length > 0 ? (
              <Text style={styles.sectionHeader}>All enrollments</Text>
            ) : null
          )}
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer} {...tid('dashboard-empty')}>
              <Ionicons name="people-outline" size={52} color={colors.textTertiary} />
              <Text style={styles.emptyText}>No enrollments yet</Text>
              <Text style={styles.emptySubtext}>
                Enroll contacts in a campaign from their profile page.
              </Text>
              <TouchableOpacity 
                style={styles.createButton}
                onPress={() => router.push('/campaigns/new')}
                {...tid('create-campaign-btn')}
              >
                <Text style={styles.createButtonText}>Create campaign</Text>
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
    backgroundColor: colors.bg,
  },
  statsBanner: {
    padding: 16,
    gap: 12,
  },
  pendingCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  pendingCardActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  pendingCount: {
    fontSize: 36,
    fontWeight: '800',
    color: colors.textSecondary,
    marginTop: 8,
  },
  pendingCountActive: {
    color: '#000',
  },
  pendingLabel: {
    fontSize: FS.heading,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: 4,
  },
  pendingLabelActive: {
    color: '#000',
  },
  tapToSend: {
    fontSize: FS.secondary,
    color: 'rgba(0,0,0,0.65)',
    marginTop: 8,
    fontWeight: '600',
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 8,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  statCardValue: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.text,
  },
  statCardLabel: {
    fontSize: FS.secondary,
    color: colors.textSecondary,
    marginTop: 4,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    padding: 16,
    paddingBottom: 40,
  },
  sectionHeader: {
    ...EYEBROW,
    color: colors.textSecondary,
    marginBottom: 10,
  },
  enrollmentCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  enrollmentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    gap: 8,
  },
  contactInfo: {
    flex: 1,
    minWidth: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.accent,
  },
  contactName: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
    flexShrink: 1,
  },
  contactPhone: {
    fontSize: FS.secondary,
    color: colors.textSecondary,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    flexShrink: 0,
  },
  statusText: {
    fontSize: FS.micro,
    fontWeight: '800',
    textTransform: 'capitalize',
  },
  campaignInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  campaignName: {
    fontSize: FS.body,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  progressSection: {
    marginBottom: 12,
  },
  progressBar: {
    height: 4,
    backgroundColor: colors.surface,
    borderRadius: 2,
    marginBottom: 6,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
  progressText: {
    fontSize: FS.secondary,
    color: colors.textSecondary,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 16,
  },
  stat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: FS.secondary,
    color: colors.textSecondary,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  emptyText: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: colors.text,
    marginTop: 16,
    marginBottom: 6,
  },
  emptySubtext: {
    fontSize: FS.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 20,
  },
  createButton: {
    backgroundColor: colors.accent,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 14,
  },
  createButtonText: {
    fontSize: FS.heading,
    fontWeight: '700',
    color: '#000',
  },
});
