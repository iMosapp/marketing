import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

export default function AnalyticsScreen() {
  const router = useRouter();
  const [period, setPeriod] = useState<'week' | 'month' | 'year'>('week');
  
  // Mock analytics data
  const stats = {
    week: {
      conversations: 32,
      messages: 156,
      calls: 24,
      responseTime: '12m',
      aiHandled: 68,
      closedDeals: 3,
    },
    month: {
      conversations: 124,
      messages: 589,
      calls: 96,
      responseTime: '15m',
      aiHandled: 256,
      closedDeals: 12,
    },
    year: {
      conversations: 1,messages: 7102,
      calls: 1152,
      responseTime: '18m',
      aiHandled: 3084,
      closedDeals: 142,
    },
  };
  
  const currentStats = stats[period];
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        
        <Text style={styles.title}>Analytics</Text>
        
        <View style={{ width: 32 }} />
      </View>
      
      {/* Period Selector */}
      <View style={styles.periodSelector}>
        {(['week', 'month', 'year'] as const).map((p) => (
          <TouchableOpacity
            key={p}
            style={[styles.periodButton, period === p && styles.periodButtonActive]}
            onPress={() => setPeriod(p)}
          >
            <Text
              style={[styles.periodText, period === p && styles.periodTextActive]}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Main Stats Grid */}
        <View style={styles.statsGrid}>
          <View style={[styles.statCard, styles.statCardLarge]}>
            <Ionicons name="chatbubbles" size={32} color="#007AFF" />
            <Text style={styles.statValue}>{currentStats.conversations}</Text>
            <Text style={styles.statLabel}>Conversations</Text>
            <View style={styles.trendBadge}>
              <Ionicons name="trending-up" size={14} color="#34C759" />
              <Text style={styles.trendText}>+12%</Text>
            </View>
          </View>
          
          <View style={[styles.statCard, styles.statCardLarge]}>
            <Ionicons name="paper-plane" size={32} color="#34C759" />
            <Text style={styles.statValue}>{currentStats.messages}</Text>
            <Text style={styles.statLabel}>Messages Sent</Text>
            <View style={styles.trendBadge}>
              <Ionicons name="trending-up" size={14} color="#34C759" />
              <Text style={styles.trendText}>+8%</Text>
            </View>
          </View>
        </View>
        
        <View style={styles.statsGrid}>
          <View style={styles.statCard}>
            <Ionicons name="call" size={24} color="#FF9500" />
            <Text style={styles.statValue}>{currentStats.calls}</Text>
            <Text style={styles.statLabel}>Calls</Text>
          </View>
          
          <View style={styles.statCard}>
            <Ionicons name="time" size={24} color="#8E8E93" />
            <Text style={styles.statValue}>{currentStats.responseTime}</Text>
            <Text style={styles.statLabel}>Avg Response</Text>
          </View>
        </View>
        
        {/* AI Performance */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>AI Performance</Text>
          
          <View style={styles.aiCard}>
            <View style={styles.aiHeader}>
              <View style={styles.aiTitleRow}>
                <Ionicons name="sparkles" size={24} color="#34C759" />
                <Text style={styles.aiTitle}>AI Handled</Text>
              </View>
              <Text style={styles.aiValue}>{currentStats.aiHandled}</Text>
            </View>
            
            <View style={styles.progressBar}>
              <View
                style={[
                  styles.progressFill,
                  {
                    width: `${
                      (currentStats.aiHandled / currentStats.messages) * 100
                    }%`,
                  },
                ]}
              />
            </View>
            
            <Text style={styles.aiPercentage}>
              {Math.round((currentStats.aiHandled / currentStats.messages) * 100)}% of
              messages automated
            </Text>
          </View>
        </View>
        
        {/* Deal Tracking */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Pipeline</Text>
          
          <View style={styles.dealCard}>
            <View style={styles.dealHeader}>
              <Ionicons name="checkmark-circle" size={32} color="#34C759" />
              <View style={styles.dealInfo}>
                <Text style={styles.dealValue}>{currentStats.closedDeals}</Text>
                <Text style={styles.dealLabel}>Closed Deals</Text>
              </View>
            </View>
          </View>
        </View>
        
        {/* Activity Breakdown */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Activity Breakdown</Text>
          
          <View style={styles.breakdownCard}>
            <View style={styles.breakdownRow}>
              <View style={styles.breakdownLabel}>
                <Ionicons name="chatbubble" size={16} color="#007AFF" />
                <Text style={styles.breakdownText}>Direct Messages</Text>
              </View>
              <Text style={styles.breakdownValue}>
                {currentStats.messages - currentStats.aiHandled}
              </Text>
            </View>
            
            <View style={styles.breakdownRow}>
              <View style={styles.breakdownLabel}>
                <Ionicons name="sparkles" size={16} color="#34C759" />
                <Text style={styles.breakdownText}>AI Messages</Text>
              </View>
              <Text style={styles.breakdownValue}>{currentStats.aiHandled}</Text>
            </View>
            
            <View style={styles.breakdownRow}>
              <View style={styles.breakdownLabel}>
                <Ionicons name="call" size={16} color="#FF9500" />
                <Text style={styles.breakdownText}>Phone Calls</Text>
              </View>
              <Text style={styles.breakdownValue}>{currentStats.calls}</Text>
            </View>
            
            <View style={styles.breakdownRow}>
              <View style={styles.breakdownLabel}>
                <Ionicons name="checkmark-done" size={16} color="#8E8E93" />
                <Text style={styles.breakdownText}>Closed Conversations</Text>
              </View>
              <Text style={styles.breakdownValue}>
                {Math.floor(currentStats.conversations * 0.4)}
              </Text>
            </View>
          </View>
        </View>
      </ScrollView>
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
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
  },
  periodSelector: {
    flexDirection: 'row',
    padding: 16,
    gap: 8,
  },
  periodButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#1C1C1E',
    alignItems: 'center',
  },
  periodButtonActive: {
    backgroundColor: '#007AFF',
  },
  periodText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  periodTextActive: {
    color: '#FFF',
  },
  scrollContent: {
    padding: 16,
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  statCardLarge: {
    paddingVertical: 24,
  },
  statValue: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFF',
    marginTop: 12,
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 13,
    color: '#8E8E93',
    textAlign: 'center',
  },
  trendBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#34C75920',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
    marginTop: 8,
  },
  trendText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#34C759',
  },
  section: {
    marginTop: 24,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  aiCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 20,
  },
  aiHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  aiTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  aiTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  aiValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#34C759',
  },
  progressBar: {
    height: 8,
    backgroundColor: '#2C2C2E',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 12,
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#34C759',
    borderRadius: 4,
  },
  aiPercentage: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
  },
  dealCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 20,
  },
  dealHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  dealInfo: {
    flex: 1,
  },
  dealValue: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 4,
  },
  dealLabel: {
    fontSize: 15,
    color: '#8E8E93',
  },
  breakdownCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
  },
  breakdownRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  breakdownLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  breakdownText: {
    fontSize: 15,
    color: '#FFF',
  },
  breakdownValue: {
    fontSize: 17,
    fontWeight: '600',
    color: '#8E8E93',
  },
});
