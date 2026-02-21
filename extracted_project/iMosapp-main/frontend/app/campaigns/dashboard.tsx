import React, { useState, useEffect, useCallback } from 'react';
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
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [upcomingCount, setUpcomingCount] = useState(0);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  
  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [user])
  );
  
  const loadData = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      
      // Load pending count
      const pendingData = await campaignsAPI.getPendingCount();
      setPendingCount(pendingData.pending);
      setUpcomingCount(pendingData.upcoming);
      
      // Load all campaigns and their enrollments
      const campaignsData = await campaignsAPI.getAll(user._id);
      setCampaigns(campaignsData);
      
      // Gather all enrollments
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
      
      // Sort by next_send_at (closest first), then by status
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
          'Messages Sent!',
          `Sent ${result.sent} message${result.sent !== 1 ? 's' : ''}${result.completed > 0 ? `\n${result.completed} campaign${result.completed !== 1 ? 's' : ''} completed` : ''}`,
          [{ text: 'OK', onPress: () => loadData() }]
        );
      } else {
        showSimpleAlert('No Messages', 'No pending messages to send right now.');
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
      case 'active': return '#007AFF';
      case 'completed': return '#34C759';
      case 'cancelled': return '#FF3B30';
      case 'paused': return '#FF9500';
      default: return '#8E8E93';
    }
  };
  
  const renderEnrollment = ({ item }: { item: Enrollment }) => (
    <TouchableOpacity 
      style={styles.enrollmentCard}
      onPress={() => router.push(`/contact/${item.contact_id}`)}
    >
      <View style={styles.enrollmentHeader}>
        <View style={styles.contactInfo}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {item.contact_name.split(' ').map(n => n[0]).join('').slice(0, 2)}
            </Text>
          </View>
          <View>
            <Text style={styles.contactName}>{item.contact_name}</Text>
            <Text style={styles.contactPhone}>{item.contact_phone}</Text>
          </View>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(item.status)}20` }]}>
          <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>
            {item.status}
          </Text>
        </View>
      </View>
      
      <View style={styles.campaignInfo}>
        <Ionicons name="calendar" size={16} color="#8E8E93" />
        <Text style={styles.campaignName}>{item.campaign_name}</Text>
      </View>
      
      <View style={styles.progressSection}>
        <View style={styles.progressBar}>
          <View 
            style={[
              styles.progressFill, 
              { 
                width: `${((item.current_step - 1) / item.total_steps) * 100}%`,
                backgroundColor: item.status === 'completed' ? '#34C759' : '#007AFF'
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
          <Ionicons name="paper-plane" size={14} color="#8E8E93" />
          <Text style={styles.statText}>{item.messages_sent?.length || 0} sent</Text>
        </View>
        {item.status === 'active' && item.next_send_at && (
          <View style={styles.stat}>
            <Ionicons name="time" size={14} color="#8E8E93" />
            <Text style={styles.statText}>Next: {formatNextSend(item.next_send_at)}</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
  
  const activeEnrollments = enrollments.filter(e => e.status === 'active');
  const completedEnrollments = enrollments.filter(e => e.status === 'completed');
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.title}>Campaign Dashboard</Text>
        
        <TouchableOpacity
          onPress={() => router.push('/campaigns')}
          style={styles.settingsButton}
        >
          <Ionicons name="settings-outline" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>
      
      {/* Stats Banner */}
      <View style={styles.statsBanner}>
        <TouchableOpacity 
          style={[styles.pendingCard, pendingCount > 0 && styles.pendingCardActive]}
          onPress={processScheduler}
          disabled={processing || pendingCount === 0}
        >
          {processing ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <>
              <Ionicons 
                name="send" 
                size={24} 
                color={pendingCount > 0 ? '#FFF' : '#8E8E93'} 
              />
              <Text style={[styles.pendingCount, pendingCount > 0 && styles.pendingCountActive]}>
                {pendingCount}
              </Text>
              <Text style={[styles.pendingLabel, pendingCount > 0 && styles.pendingLabelActive]}>
                Ready to Send
              </Text>
              {pendingCount > 0 && (
                <Text style={styles.tapToSend}>Tap to send</Text>
              )}
            </>
          )}
        </TouchableOpacity>
        
        <View style={styles.statsGrid}>
          <View style={styles.statCard}>
            <Text style={styles.statCardValue}>{activeEnrollments.length}</Text>
            <Text style={styles.statCardLabel}>Active</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statCardValue}>{upcomingCount}</Text>
            <Text style={styles.statCardLabel}>Upcoming</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statCardValue}>{completedEnrollments.length}</Text>
            <Text style={styles.statCardLabel}>Completed</Text>
          </View>
        </View>
      </View>
      
      {/* Enrollments List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
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
              tintColor="#007AFF"
            />
          }
          ListHeaderComponent={() => (
            enrollments.length > 0 ? (
              <Text style={styles.sectionHeader}>All Enrollments</Text>
            ) : null
          )}
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="people-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No enrollments yet</Text>
              <Text style={styles.emptySubtext}>
                Enroll contacts in campaigns from their profile page
              </Text>
              <TouchableOpacity 
                style={styles.createButton}
                onPress={() => router.push('/campaigns/new')}
              >
                <Text style={styles.createButtonText}>Create Campaign</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
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
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
  },
  settingsButton: {
    padding: 4,
  },
  statsBanner: {
    padding: 16,
    gap: 12,
  },
  pendingCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  pendingCardActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  pendingCount: {
    fontSize: 36,
    fontWeight: 'bold',
    color: '#8E8E93',
    marginTop: 8,
  },
  pendingCountActive: {
    color: '#FFF',
  },
  pendingLabel: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 4,
  },
  pendingLabelActive: {
    color: '#FFF',
  },
  tapToSend: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 8,
    fontWeight: '500',
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 8,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  statCardValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
  },
  statCardLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    padding: 16,
  },
  sectionHeader: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  enrollmentCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  enrollmentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  contactInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
  contactName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  contactPhone: {
    fontSize: 13,
    color: '#8E8E93',
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  campaignInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  campaignName: {
    fontSize: 14,
    color: '#8E8E93',
  },
  progressSection: {
    marginBottom: 12,
  },
  progressBar: {
    height: 4,
    backgroundColor: '#2C2C2E',
    borderRadius: 2,
    marginBottom: 6,
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
  progressText: {
    fontSize: 12,
    color: '#8E8E93',
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
    fontSize: 13,
    color: '#8E8E93',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 48,
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
    marginBottom: 24,
  },
  createButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  createButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
});
