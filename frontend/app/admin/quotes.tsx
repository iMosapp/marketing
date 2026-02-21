import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

interface Quote {
  _id: string;
  quote_number: string;
  plan_type: string;
  plan_name: string;
  customer: {
    email: string;
    name: string;
    phone: string;
  };
  business_info?: {
    company_name: string;
  };
  pricing: {
    final_price: number;
    discount_percent: number;
    interval: string;
    num_users: number;
  };
  status: string;
  valid_until: string;
  created_at: string;
}

export default function QuotesListPage() {
  const router = useRouter();
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    loadQuotes();
  }, [filter]);

  const loadQuotes = async () => {
    try {
      const params = filter !== 'all' ? `?status=${filter}` : '';
      const response = await api.get(`/subscriptions/quotes${params}`);
      setQuotes(response.data);
    } catch (error) {
      console.error('Error loading quotes:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadQuotes();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft': return '#8E8E93';
      case 'sent': return '#007AFF';
      case 'viewed': return '#FF9500';
      case 'accepted': return '#34C759';
      case 'expired': return '#FF3B30';
      case 'cancelled': return '#FF3B30';
      default: return '#8E8E93';
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const isExpired = (validUntil: string) => {
    return new Date(validUntil) < new Date();
  };

  const filters = ['all', 'draft', 'sent', 'accepted', 'expired'];

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Quotes</Text>
        <TouchableOpacity onPress={() => router.push('/admin/create-quote')}>
          <Ionicons name="add" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Filter Pills */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filterContainer}
        contentContainerStyle={styles.filterContent}
      >
        {filters.map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterPill, filter === f && styles.filterPillActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {loading ? (
          <ActivityIndicator color="#007AFF" style={{ marginTop: 40 }} />
        ) : quotes.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="document-text-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No quotes found</Text>
            <Text style={styles.emptySubtext}>Create your first quote to get started</Text>
            <TouchableOpacity
              style={styles.createButton}
              onPress={() => router.push('/admin/create-quote')}
            >
              <Ionicons name="add" size={20} color="#FFF" />
              <Text style={styles.createButtonText}>Create Quote</Text>
            </TouchableOpacity>
          </View>
        ) : (
          quotes.map((quote) => (
            <TouchableOpacity
              key={quote._id}
              style={styles.quoteCard}
              onPress={() => {/* Could navigate to quote detail */}}
              data-testid={`quote-${quote.quote_number}`}
            >
              <View style={styles.quoteHeader}>
                <View>
                  <Text style={styles.quoteNumber}>{quote.quote_number}</Text>
                  <Text style={styles.quoteDate}>Created {formatDate(quote.created_at)}</Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(quote.status)}20` }]}>
                  <Text style={[styles.statusText, { color: getStatusColor(quote.status) }]}>
                    {quote.status.toUpperCase()}
                  </Text>
                </View>
              </View>

              <View style={styles.customerInfo}>
                <Ionicons name={quote.plan_type === 'store' ? 'storefront' : 'person'} size={16} color="#8E8E93" />
                <Text style={styles.customerName}>
                  {quote.business_info?.company_name || quote.customer?.name || quote.customer?.email || 'N/A'}
                </Text>
              </View>

              <View style={styles.quoteDetails}>
                <View style={styles.detailItem}>
                  <Text style={styles.detailLabel}>Plan</Text>
                  <Text style={styles.detailValue}>{quote.plan_name}</Text>
                </View>
                <View style={styles.detailItem}>
                  <Text style={styles.detailLabel}>Price</Text>
                  <Text style={styles.detailValue}>${quote.pricing.final_price.toFixed(2)}/{quote.pricing.interval}</Text>
                </View>
                {quote.pricing.discount_percent > 0 && (
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Discount</Text>
                    <Text style={[styles.detailValue, { color: '#34C759' }]}>{quote.pricing.discount_percent}% OFF</Text>
                  </View>
                )}
              </View>

              {quote.plan_type === 'store' && (
                <View style={styles.userCountBadge}>
                  <Ionicons name="people" size={14} color="#007AFF" />
                  <Text style={styles.userCountText}>{quote.pricing.num_users} users</Text>
                </View>
              )}

              <View style={styles.quoteFooter}>
                <Text style={[
                  styles.validUntil,
                  isExpired(quote.valid_until) && styles.validUntilExpired
                ]}>
                  {isExpired(quote.valid_until) ? 'Expired' : `Valid until ${formatDate(quote.valid_until)}`}
                </Text>
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </View>
            </TouchableOpacity>
          ))
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
    width: 40,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  filterContainer: {
    maxHeight: 50,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  filterContent: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
    flexDirection: 'row',
  },
  filterPill: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
    marginRight: 8,
  },
  filterPillActive: {
    backgroundColor: '#007AFF',
  },
  filterText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#8E8E93',
  },
  filterTextActive: {
    color: '#FFF',
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    marginTop: 24,
    gap: 8,
  },
  createButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  quoteCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  quoteHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  quoteNumber: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
    fontFamily: 'monospace',
  },
  quoteDate: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '700',
  },
  customerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  customerName: {
    fontSize: 15,
    color: '#FFF',
    fontWeight: '500',
  },
  quoteDetails: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
    marginBottom: 12,
  },
  detailItem: {},
  detailLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 2,
  },
  detailValue: {
    fontSize: 15,
    color: '#FFF',
    fontWeight: '500',
  },
  userCountBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#007AFF20',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    alignSelf: 'flex-start',
    marginBottom: 12,
  },
  userCountText: {
    fontSize: 13,
    color: '#007AFF',
    fontWeight: '500',
  },
  quoteFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  validUntil: {
    fontSize: 13,
    color: '#8E8E93',
  },
  validUntilExpired: {
    color: '#FF3B30',
  },
});
