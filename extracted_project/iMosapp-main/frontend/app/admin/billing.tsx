import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { format } from 'date-fns';
import api from '../../services/api';

const TIME_FILTERS = [
  { label: '7D', value: '7d' },
  { label: '30D', value: '30d' },
  { label: '90D', value: '90d' },
  { label: '12M', value: '12m' },
  { label: 'All', value: 'all' },
];

export default function BillingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState<any>(null);
  const [mrr, setMrr] = useState<any>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [timeRange, setTimeRange] = useState('30d');
  const [activeTab, setActiveTab] = useState<'overview' | 'transactions'>('overview');

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [timeRange])
  );

  const loadData = async () => {
    try {
      setLoading(true);
      const [summaryRes, mrrRes, transactionsRes] = await Promise.all([
        api.get(`/admin/billing/summary?time_range=${timeRange}`),
        api.get('/admin/billing/mrr'),
        api.get('/admin/billing/transactions?limit=20'),
      ]);
      setSummary(summaryRes.data);
      setMrr(mrrRes.data);
      setTransactions(transactionsRes.data.transactions);
    } catch (error) {
      console.error('Failed to load billing data:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value || 0);
  };

  const StatCard = ({ label, value, color, icon, subtext }: any) => (
    <View style={styles.statCard}>
      <View style={styles.statHeader}>
        <Ionicons name={icon} size={20} color={color} />
        <Text style={styles.statLabel}>{label}</Text>
      </View>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      {subtext && <Text style={styles.statSubtext}>{subtext}</Text>}
    </View>
  );

  const renderTransaction = ({ item }: any) => (
    <View style={styles.transactionRow}>
      <View style={styles.transactionInfo}>
        <Text style={styles.transactionName}>{item.user_name}</Text>
        <Text style={styles.transactionEmail}>{item.user_email}</Text>
        <Text style={styles.transactionPlan}>{item.plan_id} plan</Text>
      </View>
      <View style={styles.transactionMeta}>
        <Text style={styles.transactionAmount}>{formatCurrency(item.amount)}</Text>
        <Text style={styles.transactionDate}>
          {item.created_at ? format(new Date(item.created_at), 'MMM d, yyyy') : '-'}
        </Text>
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#34C759" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Billing & Revenue</Text>
        <View style={{ width: 28 }} />
      </View>

      {/* Time Filter */}
      <View style={styles.filterContainer}>
        {TIME_FILTERS.map((filter) => (
          <TouchableOpacity
            key={filter.value}
            style={[styles.filterPill, timeRange === filter.value && styles.filterPillActive]}
            onPress={() => setTimeRange(filter.value)}
          >
            <Text style={[styles.filterText, timeRange === filter.value && styles.filterTextActive]}>
              {filter.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Tab Navigation */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'overview' && styles.tabActive]}
          onPress={() => setActiveTab('overview')}
        >
          <Text style={[styles.tabText, activeTab === 'overview' && styles.tabTextActive]}>
            Overview
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'transactions' && styles.tabActive]}
          onPress={() => setActiveTab('transactions')}
        >
          <Text style={[styles.tabText, activeTab === 'transactions' && styles.tabTextActive]}>
            Transactions
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#34C759" />
        }
      >
        {activeTab === 'overview' && (
          <>
            {/* MRR Highlight */}
            <View style={styles.mrrBox}>
              <Text style={styles.mrrLabel}>Monthly Recurring Revenue</Text>
              <Text style={styles.mrrValue}>{formatCurrency(mrr?.mrr || 0)}</Text>
              <View style={styles.mrrDetails}>
                <View style={styles.mrrDetail}>
                  <Text style={styles.mrrDetailLabel}>ARR</Text>
                  <Text style={styles.mrrDetailValue}>{formatCurrency(mrr?.arr || 0)}</Text>
                </View>
                <View style={styles.mrrDetail}>
                  <Text style={styles.mrrDetailLabel}>Subscribers</Text>
                  <Text style={styles.mrrDetailValue}>{mrr?.subscriber_count || 0}</Text>
                </View>
                <View style={styles.mrrDetail}>
                  <Text style={styles.mrrDetailLabel}>ARPU</Text>
                  <Text style={styles.mrrDetailValue}>{formatCurrency(mrr?.arpu || 0)}</Text>
                </View>
              </View>
            </View>

            {/* Revenue Stats */}
            <Text style={styles.sectionTitle}>REVENUE BREAKDOWN</Text>
            <View style={styles.statsGrid}>
              <StatCard
                label="Gross Revenue"
                value={formatCurrency(summary?.total_revenue)}
                color="#34C759"
                icon="cash"
                subtext={`${summary?.transaction_count || 0} transactions`}
              />
              <StatCard
                label="Commissions"
                value={formatCurrency(summary?.total_commissions)}
                color="#FF9500"
                icon="people"
                subtext={`${(summary?.commission_rate || 0) * 100}% rate`}
              />
              <StatCard
                label="Net Revenue"
                value={formatCurrency(summary?.net_revenue)}
                color="#007AFF"
                icon="trending-up"
              />
              <StatCard
                label="Bonus Pool"
                value={formatCurrency(summary?.bonus_pool)}
                color="#AF52DE"
                icon="gift"
                subtext={`${(summary?.bonus_pool_rate || 0) * 100}% of net`}
              />
            </View>

            {/* Company Retained */}
            <View style={styles.retainedBox}>
              <Ionicons name="business" size={24} color="#007AFF" />
              <View style={styles.retainedInfo}>
                <Text style={styles.retainedLabel}>Company Retained</Text>
                <Text style={styles.retainedSubtext}>After commissions & bonus pool</Text>
              </View>
              <Text style={styles.retainedValue}>{formatCurrency(summary?.company_retained)}</Text>
            </View>

            {/* Plan Breakdown */}
            {summary?.plan_breakdown && Object.keys(summary.plan_breakdown).length > 0 && (
              <>
                <Text style={styles.sectionTitle}>BY PLAN TYPE</Text>
                <View style={styles.planList}>
                  {Object.entries(summary.plan_breakdown).map(([plan, data]: [string, any]) => (
                    <View key={plan} style={styles.planRow}>
                      <View style={styles.planInfo}>
                        <Text style={styles.planName}>{plan.charAt(0).toUpperCase() + plan.slice(1)}</Text>
                        <Text style={styles.planCount}>{data.count} subscriptions</Text>
                      </View>
                      <Text style={styles.planRevenue}>{formatCurrency(data.revenue)}</Text>
                    </View>
                  ))}
                </View>
              </>
            )}

            {/* Monthly Chart (simplified) */}
            {summary?.monthly_revenue && summary.monthly_revenue.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>MONTHLY TREND</Text>
                <View style={styles.chartContainer}>
                  {summary.monthly_revenue.map((m: any, i: number) => {
                    const maxRevenue = Math.max(...summary.monthly_revenue.map((x: any) => x.revenue || 1));
                    const height = ((m.revenue || 0) / maxRevenue) * 100;
                    return (
                      <View key={i} style={styles.chartBar}>
                        <View style={[styles.chartBarFill, { height: `${Math.max(height, 5)}%` }]} />
                        <Text style={styles.chartLabel}>{m.month}</Text>
                      </View>
                    );
                  })}
                </View>
              </>
            )}
          </>
        )}

        {activeTab === 'transactions' && (
          <>
            <Text style={styles.sectionTitle}>RECENT TRANSACTIONS</Text>
            {transactions.length > 0 ? (
              transactions.map((t, i) => (
                <View key={t._id || i}>
                  {renderTransaction({ item: t })}
                </View>
              ))
            ) : (
              <View style={styles.emptyContainer}>
                <Ionicons name="receipt-outline" size={48} color="#8E8E93" />
                <Text style={styles.emptyText}>No transactions yet</Text>
                <Text style={styles.emptySubtext}>Payments will appear here</Text>
              </View>
            )}
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
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
  filterContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
  },
  filterPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: '#1C1C1E',
  },
  filterPillActive: {
    backgroundColor: '#34C759',
  },
  filterText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
  },
  filterTextActive: {
    color: '#FFF',
  },
  tabContainer: {
    flexDirection: 'row',
    marginHorizontal: 16,
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 4,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 8,
  },
  tabActive: {
    backgroundColor: '#2C2C2E',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#8E8E93',
  },
  tabTextActive: {
    color: '#FFF',
  },
  content: {
    padding: 16,
  },
  mrrBox: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#34C759',
  },
  mrrLabel: {
    fontSize: 13,
    color: '#8E8E93',
  },
  mrrValue: {
    fontSize: 40,
    fontWeight: '700',
    color: '#34C759',
    marginTop: 4,
  },
  mrrDetails: {
    flexDirection: 'row',
    marginTop: 16,
    gap: 24,
  },
  mrrDetail: {
    alignItems: 'center',
  },
  mrrDetailLabel: {
    fontSize: 11,
    color: '#8E8E93',
  },
  mrrDetailValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    letterSpacing: 0.5,
    marginBottom: 12,
    marginTop: 8,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
  },
  statHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  statLabel: {
    fontSize: 11,
    color: '#8E8E93',
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  statSubtext: {
    fontSize: 10,
    color: '#8E8E93',
    marginTop: 4,
  },
  retainedBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  retainedInfo: {
    flex: 1,
    marginLeft: 12,
  },
  retainedLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  retainedSubtext: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  retainedValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#007AFF',
  },
  planList: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 20,
  },
  planRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  planInfo: {
    flex: 1,
  },
  planName: {
    fontSize: 15,
    fontWeight: '500',
    color: '#FFF',
  },
  planCount: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  planRevenue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#34C759',
  },
  chartContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 120,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    gap: 4,
    marginBottom: 20,
  },
  chartBar: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'flex-end',
    height: '100%',
  },
  chartBarFill: {
    width: '80%',
    backgroundColor: '#34C759',
    borderRadius: 4,
    minHeight: 4,
  },
  chartLabel: {
    fontSize: 9,
    color: '#8E8E93',
    marginTop: 4,
  },
  transactionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  transactionInfo: {
    flex: 1,
  },
  transactionName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  transactionEmail: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  transactionPlan: {
    fontSize: 11,
    color: '#34C759',
    marginTop: 2,
  },
  transactionMeta: {
    alignItems: 'flex-end',
  },
  transactionAmount: {
    fontSize: 16,
    fontWeight: '700',
    color: '#34C759',
  },
  transactionDate: {
    fontSize: 11,
    color: '#8E8E93',
    marginTop: 2,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
  },
});
