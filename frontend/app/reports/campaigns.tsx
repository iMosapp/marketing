import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';

export default function CampaignsReportScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, [period]);

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/reports/campaigns?days=${period}`);
      setData(response.data);
    } catch (err) {
      console.error('Failed to load campaigns report:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'sent': return '#34C759';
      case 'scheduled': return '#FF9500';
      case 'draft': return '#8E8E93';
      default: return '#007AFF';
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Campaign Performance</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Period Selector */}
      <View style={styles.periodSelector}>
        {[7, 30, 90].map((days) => (
          <TouchableOpacity
            key={days}
            style={[styles.periodButton, period === days && styles.periodButtonActive]}
            onPress={() => setPeriod(days)}
          >
            <Text style={[styles.periodText, period === days && styles.periodTextActive]}>
              {days}D
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Totals */}
          <View style={styles.totalsGrid}>
            <View style={styles.totalCard}>
              <Text style={styles.totalValue}>{data?.totals?.total_campaigns || 0}</Text>
              <Text style={styles.totalLabel}>Campaigns</Text>
            </View>
            <View style={styles.totalCard}>
              <Text style={styles.totalValue}>{data?.totals?.total_recipients || 0}</Text>
              <Text style={styles.totalLabel}>Recipients</Text>
            </View>
            <View style={styles.totalCard}>
              <Text style={[styles.totalValue, { color: '#34C759' }]}>
                {data?.totals?.avg_delivery_rate || 0}%
              </Text>
              <Text style={styles.totalLabel}>Delivery Rate</Text>
            </View>
            <View style={styles.totalCard}>
              <Text style={[styles.totalValue, { color: '#007AFF' }]}>
                {data?.totals?.avg_open_rate || 0}%
              </Text>
              <Text style={styles.totalLabel}>Open Rate</Text>
            </View>
          </View>

          {/* Campaign List */}
          <Text style={styles.sectionTitle}>Recent Campaigns</Text>
          
          {data?.campaigns?.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="megaphone-outline" size={48} color="#2C2C2E" />
              <Text style={styles.emptyText}>No campaigns in this period</Text>
            </View>
          ) : (
            data?.campaigns?.map((campaign: any) => (
              <View key={campaign._id} style={styles.campaignCard}>
                <View style={styles.campaignHeader}>
                  <View style={styles.campaignInfo}>
                    <Text style={styles.campaignName}>{campaign.name}</Text>
                    <Text style={styles.campaignDate}>
                      {new Date(campaign.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                  <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(campaign.status)}20` }]}>
                    <Text style={[styles.statusText, { color: getStatusColor(campaign.status) }]}>
                      {campaign.status.toUpperCase()}
                    </Text>
                  </View>
                </View>
                
                <View style={styles.campaignStats}>
                  <View style={styles.statItem}>
                    <Text style={styles.statValue}>{campaign.recipient_count}</Text>
                    <Text style={styles.statLabel}>Sent</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Text style={styles.statValue}>{campaign.delivered_count}</Text>
                    <Text style={styles.statLabel}>Delivered</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Text style={styles.statValue}>{campaign.opened_count}</Text>
                    <Text style={styles.statLabel}>Opened</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Text style={[styles.statValue, { color: '#34C759' }]}>
                      {campaign.delivery_rate}%
                    </Text>
                    <Text style={styles.statLabel}>Rate</Text>
                  </View>
                </View>
              </View>
            ))
          )}

          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: { padding: 4 },
  title: { fontSize: 18, fontWeight: 'bold', color: '#FFF' },
  periodSelector: { flexDirection: 'row', padding: 16, gap: 8 },
  periodButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
  },
  periodButtonActive: { backgroundColor: '#007AFF' },
  periodText: { color: '#8E8E93', fontWeight: '600' },
  periodTextActive: { color: '#FFF' },
  scrollContent: { padding: 16 },
  totalsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 24,
  },
  totalCard: {
    width: '48%',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  totalValue: { fontSize: 28, fontWeight: '700', color: '#FFF' },
  totalLabel: { fontSize: 12, color: '#8E8E93', marginTop: 4 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#FFF', marginBottom: 12 },
  emptyState: { alignItems: 'center', paddingVertical: 48 },
  emptyText: { color: '#8E8E93', marginTop: 12 },
  campaignCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
  },
  campaignHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 14,
  },
  campaignInfo: { flex: 1 },
  campaignName: { fontSize: 16, fontWeight: '600', color: '#FFF' },
  campaignDate: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusText: { fontSize: 11, fontWeight: '600' },
  campaignStats: { flexDirection: 'row', justifyContent: 'space-between' },
  statItem: { alignItems: 'center' },
  statValue: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  statLabel: { fontSize: 11, color: '#8E8E93', marginTop: 2 },
});
