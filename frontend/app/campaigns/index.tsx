import React, { useState, useEffect } from 'react';
import { showAlert } from '../../services/alert';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { campaignsAPI } from '../../services/api';
import Toggle from '../../components/Toggle';

import { useThemeStore } from '../../store/themeStore';
export default function CampaignsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  
  useEffect(() => {
    loadCampaigns();
  }, [user]);
  
  const loadCampaigns = async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      const data = await campaignsAPI.getAll(user._id);
      setCampaigns(data);
    } catch (error) {
      console.error('Failed to load campaigns:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadCampaigns();
    setRefreshing(false);
  };
  
  const toggleCampaign = async (id: string) => {
    const campaign = campaigns.find((c) => c._id === id || c.id === id);
    if (!campaign || !user?._id) return;
    
    const newActiveState = !campaign.active;
    
    // Optimistically update UI
    setCampaigns(
      campaigns.map((c) => (c._id === id || c.id === id ? { ...c, active: newActiveState } : c))
    );
    
    // Save to backend
    try {
      await campaignsAPI.update(user._id, id, { active: newActiveState });
    } catch (error) {
      console.error('Failed to toggle campaign:', error);
      // Revert on error
      setCampaigns(
        campaigns.map((c) => (c._id === id || c.id === id ? { ...c, active: !newActiveState } : c))
      );
      showAlert('Error', 'Failed to update campaign status');
    }
  };
  
  const getCampaignIcon = (type: string) => {
    switch (type) {
      case 'birthday':
        return { icon: 'gift', color: '#FF9500' };
      case 'anniversary':
        return { icon: 'heart', color: '#FF3B30' };
      case 'check_in':
        return { icon: 'chatbubble', color: '#007AFF' };
      default:
        return { icon: 'create', color: '#34C759' };
    }
  };
  
  const formatDate = (date: Date | null) => {
    if (!date) return 'Never';
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    
    if (diffInHours < 24) return `${Math.floor(diffInHours)}h ago`;
    if (diffInHours < 168) return `${Math.floor(diffInHours / 24)}d ago`;
    return date.toLocaleDateString();
  };
  
  const renderCampaign = ({ item }: { item: typeof campaigns[0] }) => {
    const iconData = getCampaignIcon(item.type);
    
    const handleToggle = () => {
      console.log('Toggle clicked for:', item._id || item.id);
      toggleCampaign(item._id || item.id);
    };
    
    return (
      <TouchableOpacity 
        style={styles.campaignCard}
        onPress={() => router.push(`/campaigns/${item._id || item.id}`)}
        activeOpacity={0.7}
      >
        <View style={[styles.iconContainer, { backgroundColor: `${iconData.color}20` }]}>
          <Ionicons name={iconData.icon as any} size={24} color={iconData.color} />
        </View>
        
        <View style={styles.campaignContent}>
          <View style={styles.campaignHeader}>
            <Text style={styles.campaignName}>{item.name}</Text>
            <Toggle
              value={item.active}
              onValueChange={handleToggle}
              activeColor="#007AFF"
            />
          </View>
          
          <View style={styles.tagRow}>
            {(item.targetTags || []).map((tag, index) => (
              <View key={index} style={styles.miniTag}>
                <Text style={styles.miniTagText}>{tag}</Text>
              </View>
            ))}
          </View>
          
          <View style={styles.statsRow}>
            <View style={styles.stat}>
              <Ionicons name="paper-plane" size={14} color={colors.textSecondary} />
              <Text style={styles.statText}>{item.messages_sent_count || 0} sent</Text>
            </View>
            <View style={styles.stat}>
              <Ionicons name="time" size={14} color={colors.textSecondary} />
              <Text style={styles.statText}>{formatDate(item.last_sent_at ? new Date(item.last_sent_at) : null)}</Text>
            </View>
            {(item.enrollments_active > 0 || item.enrollments_total > 0) && (
              <View style={styles.stat}>
                <Ionicons name="people" size={14} color={colors.textSecondary} />
                <Text style={styles.statText}>{item.enrollments_active || 0} active</Text>
              </View>
            )}
          </View>
        </View>
      </TouchableOpacity>
    );
  };
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.title}>Campaigns</Text>
        
        <View style={styles.headerButtons}>
          <TouchableOpacity
            onPress={() => router.push('/campaigns/dashboard')}
            style={styles.dashboardButton}
          >
            <Ionicons name="speedometer-outline" size={24} color="#007AFF" />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => router.push('/campaigns/new')}
            style={styles.addButton}
          >
            <Ionicons name="add-circle" size={32} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </View>
      
      {/* Stats Banner */}
      <View style={styles.statsBanner}>
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{campaigns.filter((c) => c.active).length}</Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={styles.statValue}>
            {campaigns.reduce((sum, c) => sum + (c.messages_sent_count || 0), 0)}
          </Text>
          <Text style={styles.statLabel}>Total Sent</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{campaigns.length}</Text>
          <Text style={styles.statLabel}>Campaigns</Text>
        </View>
      </View>
      
      {/* Campaign List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          data={campaigns}
          renderItem={renderCampaign}
          keyExtractor={(item) => item._id || item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#007AFF"
            />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="calendar-outline" size={64} color={colors.surface} />
              <Text style={styles.emptyText}>No campaigns yet</Text>
              <Text style={styles.emptySubtext}>Create your first nurture campaign</Text>
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.text,
  },
  addButton: {
    padding: 4,
  },
  dashboardButton: {
    padding: 4,
    marginRight: 8,
  },
  headerButtons: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statsBanner: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    marginHorizontal: 16,
    marginVertical: 16,
    borderRadius: 12,
    padding: 20,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statDivider: {
    width: 1,
    backgroundColor: colors.surface,
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  campaignCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    alignItems: 'flex-start',
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  campaignContent: {
    flex: 1,
  },
  campaignHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  campaignName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    flex: 1,
  },
  tagRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 12,
    flexWrap: 'wrap',
  },
  miniTag: {
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  miniTagText: {
    fontSize: 13,
    color: colors.textSecondary,
    fontWeight: '600',
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
    fontSize: 15,
    color: colors.textSecondary,
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
    fontSize: 21,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 17,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});
