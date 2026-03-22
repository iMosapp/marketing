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
import { showSimpleAlert, showConfirm } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
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
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
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

  const handleDeleteQuote = async (quoteId: string, status: string) => {
    if (status !== 'draft') {
      showSimpleAlert('Cannot Delete', 'Only draft quotes can be deleted');
      return;
    }
    
    showConfirm(
      'Delete Quote',
      'Are you sure you want to delete this quote? This action cannot be undone.',
      async () => {
        try {
          await api.delete(`/subscriptions/quotes/${quoteId}`);
          loadQuotes();
        } catch (error) {
          console.error('Error deleting quote:', error);
          showSimpleAlert('Error', 'Failed to delete quote');
        }
      },
      undefined,
      'Delete',
      'Cancel'
    );
  };

  const handleArchiveQuote = async (quoteId: string) => {
    showConfirm(
      'Archive Quote',
      'Are you sure you want to archive this quote?',
      async () => {
        try {
          await api.put(`/subscriptions/quotes/${quoteId}/archive`);
          loadQuotes();
        } catch (error) {
          console.error('Error archiving quote:', error);
          showSimpleAlert('Error', 'Failed to archive quote');
        }
      },
      undefined,
      'Archive',
      'Cancel'
    );
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft': return colors.textSecondary;
      case 'sent': return '#007AFF';
      case 'viewed': return '#FF9500';
      case 'accepted': return '#34C759';
      case 'expired': return '#FF3B30';
      case 'cancelled': return '#FF3B30';
      case 'archived': return colors.textTertiary;
      default: return colors.textSecondary;
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const isExpired = (validUntil: string) => {
    return new Date(validUntil) < new Date();
  };

  const filters = ['all', 'draft', 'sent', 'accepted', 'expired', 'archived'];

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
            <Ionicons name="document-text-outline" size={64} color={colors.surface} />
            <Text style={styles.emptyText}>No quotes found</Text>
            <Text style={styles.emptySubtext}>Create your first quote to get started</Text>
            <TouchableOpacity
              style={styles.createButton}
              onPress={() => router.push('/admin/create-quote')}
            >
              <Ionicons name="add" size={20} color={colors.text} />
              <Text style={styles.createButtonText}>Create Quote</Text>
            </TouchableOpacity>
          </View>
        ) : (
          quotes.map((quote) => (
            <TouchableOpacity
              key={quote._id}
              style={styles.quoteCard}
              onPress={() => router.push(`/admin/quote/${quote._id}`)}
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
                <Ionicons name={quote.plan_type === 'store' ? 'storefront' : 'person'} size={16} color={colors.textSecondary} />
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
                <View style={styles.actionButtons}>
                  {quote.status === 'draft' && (
                    <TouchableOpacity
                      style={styles.deleteButton}
                      onPress={(e) => {
                        e.stopPropagation();
                        handleDeleteQuote(quote._id, quote.status);
                      }}
                      data-testid={`delete-quote-${quote.quote_number}`}
                    >
                      <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                    </TouchableOpacity>
                  )}
                  {quote.status !== 'archived' && (
                    <TouchableOpacity
                      style={styles.archiveButton}
                      onPress={(e) => {
                        e.stopPropagation();
                        handleArchiveQuote(quote._id);
                      }}
                      data-testid={`archive-quote-${quote.quote_number}`}
                    >
                      <Ionicons name="archive-outline" size={18} color={colors.textSecondary} />
                    </TouchableOpacity>
                  )}
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </View>
              </View>
            </TouchableOpacity>
          ))
        )}

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
    width: 40,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  filterContainer: {
    maxHeight: 50,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
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
    backgroundColor: colors.card,
    marginRight: 8,
  },
  filterPillActive: {
    backgroundColor: '#007AFF',
  },
  filterText: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  filterTextActive: {
    color: colors.text,
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
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 16,
    color: colors.textSecondary,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  quoteCard: {
    backgroundColor: colors.card,
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
    fontSize: 19,
    fontWeight: '700',
    color: colors.text,
    fontFamily: 'monospace',
  },
  quoteDate: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '700',
  },
  customerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  customerName: {
    fontSize: 17,
    color: colors.text,
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
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  detailValue: {
    fontSize: 17,
    color: colors.text,
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
    fontSize: 15,
    color: '#007AFF',
    fontWeight: '500',
  },
  quoteFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
  },
  actionButtons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  deleteButton: {
    padding: 4,
  },
  archiveButton: {
    padding: 4,
  },
  validUntil: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  validUntilExpired: {
    color: '#FF3B30',
  },
});
