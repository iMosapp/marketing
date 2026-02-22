import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';

const { width } = Dimensions.get('window');

export default function MessagingReportScreen() {
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
      const response = await api.get(`/reports/messaging?days=${period}`);
      setData(response.data);
    } catch (err) {
      console.error('Failed to load messaging report:', err);
    } finally {
      setLoading(false);
    }
  };

  const maxMessages = Math.max(...(data?.daily_breakdown?.map((d: any) => d.total) || [1]));

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Messaging Analytics</Text>
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
          <View style={styles.totalsRow}>
            <View style={[styles.totalCard, { borderLeftColor: '#34C759' }]}>
              <Text style={styles.totalValue}>{data?.totals?.sms || 0}</Text>
              <Text style={styles.totalLabel}>SMS</Text>
            </View>
            <View style={[styles.totalCard, { borderLeftColor: '#007AFF' }]}>
              <Text style={styles.totalValue}>{data?.totals?.email || 0}</Text>
              <Text style={styles.totalLabel}>Email</Text>
            </View>
            <View style={[styles.totalCard, { borderLeftColor: '#AF52DE' }]}>
              <Text style={styles.totalValue}>{data?.totals?.ai_handled || 0}</Text>
              <Text style={styles.totalLabel}>AI</Text>
            </View>
          </View>

          {/* Chart */}
          <Text style={styles.sectionTitle}>Daily Activity</Text>
          <View style={styles.chartContainer}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.chart}>
                {data?.daily_breakdown?.slice(-14).map((day: any, index: number) => (
                  <View key={day.date} style={styles.chartBar}>
                    <View style={styles.barContainer}>
                      <View
                        style={[
                          styles.bar,
                          styles.barSms,
                          { height: Math.max((day.sms / maxMessages) * 100, 2) },
                        ]}
                      />
                      <View
                        style={[
                          styles.bar,
                          styles.barEmail,
                          { height: Math.max((day.email / maxMessages) * 100, 2) },
                        ]}
                      />
                    </View>
                    <Text style={styles.barLabel}>
                      {new Date(day.date).getDate()}
                    </Text>
                  </View>
                ))}
              </View>
            </ScrollView>
            <View style={styles.chartLegend}>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: '#34C759' }]} />
                <Text style={styles.legendText}>SMS</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: '#007AFF' }]} />
                <Text style={styles.legendText}>Email</Text>
              </View>
            </View>
          </View>

          {/* Daily Breakdown Table */}
          <Text style={styles.sectionTitle}>Breakdown</Text>
          <View style={styles.tableContainer}>
            <View style={styles.tableHeader}>
              <Text style={[styles.tableHeaderText, { flex: 1 }]}>Date</Text>
              <Text style={[styles.tableHeaderText, { width: 60 }]}>SMS</Text>
              <Text style={[styles.tableHeaderText, { width: 60 }]}>Email</Text>
              <Text style={[styles.tableHeaderText, { width: 60 }]}>AI</Text>
            </View>
            {data?.daily_breakdown?.slice(-14).reverse().map((day: any) => (
              <View key={day.date} style={styles.tableRow}>
                <Text style={[styles.tableCell, { flex: 1 }]}>
                  {new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </Text>
                <Text style={[styles.tableCell, { width: 60, color: '#34C759' }]}>{day.sms}</Text>
                <Text style={[styles.tableCell, { width: 60, color: '#007AFF' }]}>{day.email}</Text>
                <Text style={[styles.tableCell, { width: 60, color: '#AF52DE' }]}>{day.ai_handled}</Text>
              </View>
            ))}
          </View>

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
  totalsRow: { flexDirection: 'row', gap: 10, marginBottom: 24 },
  totalCard: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    borderLeftWidth: 3,
    alignItems: 'center',
  },
  totalValue: { fontSize: 24, fontWeight: '700', color: '#FFF' },
  totalLabel: { fontSize: 12, color: '#8E8E93', marginTop: 4 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#FFF', marginBottom: 12 },
  chartContainer: { backgroundColor: '#1C1C1E', borderRadius: 12, padding: 16, marginBottom: 24 },
  chart: { flexDirection: 'row', alignItems: 'flex-end', height: 120, gap: 8 },
  chartBar: { alignItems: 'center', width: 24 },
  barContainer: { height: 100, justifyContent: 'flex-end' },
  bar: { width: 20, borderRadius: 4, marginBottom: 2 },
  barSms: { backgroundColor: '#34C759' },
  barEmail: { backgroundColor: '#007AFF' },
  barLabel: { fontSize: 10, color: '#8E8E93', marginTop: 4 },
  chartLegend: { flexDirection: 'row', justifyContent: 'center', gap: 20, marginTop: 12 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: 12, color: '#8E8E93' },
  tableContainer: { backgroundColor: '#1C1C1E', borderRadius: 12, overflow: 'hidden' },
  tableHeader: {
    flexDirection: 'row',
    padding: 12,
    backgroundColor: '#2C2C2E',
  },
  tableHeaderText: { fontSize: 12, fontWeight: '600', color: '#8E8E93', textAlign: 'center' },
  tableRow: {
    flexDirection: 'row',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  tableCell: { fontSize: 14, color: '#FFF', textAlign: 'center' },
});
