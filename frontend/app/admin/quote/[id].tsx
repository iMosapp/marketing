import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TextInput,
  Modal,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../../services/alert';

import { useThemeStore } from '../../../store/themeStore';
interface Quote {
  _id: string;
  quote_number: string;
  status: string;
  plan_type: string;
  plan_name: string;
  customer: {
    name?: string;
    email?: string;
    phone?: string;
  };
  business_info?: {
    company_name?: string;
    address?: string;
  };
  pricing: {
    base_price: number;
    final_price: number;
    discount_percent: number;
    interval: string;
    num_users?: number;
  };
  valid_until: string;
  created_at: string;
  notes?: string;
}

export default function QuoteDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editedNotes, setEditedNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    loadQuote();
  }, [id]);

  const loadQuote = async () => {
    try {
      const response = await api.get(`/subscriptions/quotes/${id}`);
      setQuote(response.data);
      setEditedNotes(response.data.notes || '');
    } catch (error) {
      console.error('Error loading quote:', error);
      showSimpleAlert('Error', 'Failed to load quote');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveNotes = async () => {
    if (!quote) return;
    
    setSaving(true);
    try {
      await api.patch(`/subscriptions/quotes/${quote._id}`, {
        notes: editedNotes
      });
      setQuote({ ...quote, notes: editedNotes });
      setShowEditModal(false);
      showSimpleAlert('Success', 'Quote updated');
    } catch (error) {
      showSimpleAlert('Error', 'Failed to update quote');
    } finally {
      setSaving(false);
    }
  };

  const handleResend = async () => {
    if (!quote) return;
    
    showConfirm(
      'Resend Quote',
      `Send quote ${quote.quote_number} to ${quote.customer?.email || 'customer'}?`,
      async () => {
        setSending(true);
        try {
          await api.post(`/subscriptions/quotes/${quote._id}/send`);
          showSimpleAlert('Success', 'Quote resent successfully');
          loadQuote();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to resend quote');
        } finally {
          setSending(false);
        }
      },
      undefined,
      'Resend',
      'Cancel'
    );
  };

  const handleDelete = async () => {
    if (!quote) return;
    
    showConfirm(
      'Delete Quote',
      `Are you sure you want to delete quote ${quote.quote_number}? This cannot be undone.`,
      async () => {
        try {
          await api.delete(`/subscriptions/quotes/${quote._id}`);
          showSimpleAlert('Success', 'Quote deleted');
          router.back();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to delete quote');
        }
      },
      undefined,
      'Delete',
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
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
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

  if (!quote) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Quote Not Found</Text>
          <View style={{ width: 28 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={64} color="#FF3B30" />
          <Text style={styles.errorText}>Quote not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Quote Details</Text>
        <TouchableOpacity onPress={() => setShowEditModal(true)} style={styles.editButton}>
          <Ionicons name="create-outline" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content}>
        {/* Quote Number & Status */}
        <View style={styles.section}>
          <View style={styles.quoteHeader}>
            <Text style={styles.quoteNumber}>{quote.quote_number}</Text>
            <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(quote.status)}20` }]}>
              <Text style={[styles.statusText, { color: getStatusColor(quote.status) }]}>
                {quote.status.toUpperCase()}
              </Text>
            </View>
          </View>
          <Text style={styles.dateText}>Created {formatDate(quote.created_at)}</Text>
          <Text style={styles.validText}>Valid until {formatDate(quote.valid_until)}</Text>
        </View>

        {/* Customer Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Customer</Text>
          <View style={styles.infoCard}>
            {quote.business_info?.company_name && (
              <View style={styles.infoRow}>
                <Ionicons name="business" size={18} color={colors.textSecondary} />
                <Text style={styles.infoText}>{quote.business_info.company_name}</Text>
              </View>
            )}
            {quote.customer?.name && (
              <View style={styles.infoRow}>
                <Ionicons name="person" size={18} color={colors.textSecondary} />
                <Text style={styles.infoText}>{quote.customer.name}</Text>
              </View>
            )}
            {quote.customer?.email && (
              <View style={styles.infoRow}>
                <Ionicons name="mail" size={18} color={colors.textSecondary} />
                <Text style={styles.infoText}>{quote.customer.email}</Text>
              </View>
            )}
            {quote.customer?.phone && (
              <View style={styles.infoRow}>
                <Ionicons name="call" size={18} color={colors.textSecondary} />
                <Text style={styles.infoText}>{quote.customer.phone}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Pricing */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Pricing</Text>
          <View style={styles.pricingCard}>
            <View style={styles.pricingRow}>
              <Text style={styles.pricingLabel}>Plan</Text>
              <Text style={styles.pricingValue}>{quote.plan_name}</Text>
            </View>
            <View style={styles.pricingRow}>
              <Text style={styles.pricingLabel}>Base Price</Text>
              <Text style={styles.pricingValue}>${quote.pricing.base_price.toFixed(2)}/{quote.pricing.interval}</Text>
            </View>
            {quote.pricing.discount_percent > 0 && (
              <View style={styles.pricingRow}>
                <Text style={styles.pricingLabel}>Discount</Text>
                <Text style={[styles.pricingValue, { color: '#34C759' }]}>-{quote.pricing.discount_percent}%</Text>
              </View>
            )}
            {quote.pricing.num_users && (
              <View style={styles.pricingRow}>
                <Text style={styles.pricingLabel}>Users</Text>
                <Text style={styles.pricingValue}>{quote.pricing.num_users}</Text>
              </View>
            )}
            <View style={[styles.pricingRow, styles.totalRow]}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalValue}>${quote.pricing.final_price.toFixed(2)}/{quote.pricing.interval}</Text>
            </View>
          </View>
        </View>

        {/* Notes */}
        {quote.notes && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Notes</Text>
            <View style={styles.notesCard}>
              <Text style={styles.notesText}>{quote.notes}</Text>
            </View>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionSection}>
          {quote.status !== 'accepted' && quote.status !== 'archived' && (
            <TouchableOpacity 
              style={styles.resendButton}
              onPress={handleResend}
              disabled={sending}
            >
              {sending ? (
                <ActivityIndicator size="small" color={colors.text} />
              ) : (
                <>
                  <Ionicons name="send" size={20} color={colors.text} />
                  <Text style={styles.resendButtonText}>Resend Quote</Text>
                </>
              )}
            </TouchableOpacity>
          )}
          
          {quote.status === 'draft' && (
            <TouchableOpacity 
              style={styles.deleteButton}
              onPress={handleDelete}
            >
              <Ionicons name="trash" size={20} color="#FF3B30" />
              <Text style={styles.deleteButtonText}>Delete Quote</Text>
            </TouchableOpacity>
          )}
        </View>
      </ScrollView>

      {/* Edit Modal */}
      <Modal
        visible={showEditModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowEditModal(false)}
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowEditModal(false)}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Edit Quote</Text>
            <TouchableOpacity onPress={handleSaveNotes} disabled={saving}>
              {saving ? (
                <ActivityIndicator size="small" color="#007AFF" />
              ) : (
                <Text style={styles.modalSave}>Save</Text>
              )}
            </TouchableOpacity>
          </View>
          
          <ScrollView style={styles.modalContent}>
            <Text style={styles.inputLabel}>Notes</Text>
            <TextInput
              style={styles.notesInput}
              value={editedNotes}
              onChangeText={setEditedNotes}
              placeholder="Add notes about this quote..."
              placeholderTextColor={colors.textSecondary}
              multiline
              numberOfLines={6}
            />
          </ScrollView>
        </View>
      </Modal>
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
  },
  errorText: {
    fontSize: 18,
    color: colors.textSecondary,
    marginTop: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  editButton: {
    padding: 4,
  },
  content: {
    flex: 1,
  },
  section: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  quoteHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  quoteNumber: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 14,
    fontWeight: '600',
  },
  dateText: {
    fontSize: 16,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  validText: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  infoCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  infoText: {
    fontSize: 18,
    color: colors.text,
    marginLeft: 12,
  },
  pricingCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  pricingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  pricingLabel: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  pricingValue: {
    fontSize: 16,
    color: colors.text,
    fontWeight: '500',
  },
  totalRow: {
    borderTopWidth: 1,
    borderTopColor: colors.surface,
    paddingTop: 12,
    marginTop: 4,
    marginBottom: 0,
  },
  totalLabel: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  totalValue: {
    fontSize: 19,
    fontWeight: '700',
    color: '#007AFF',
  },
  notesCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  notesText: {
    fontSize: 16,
    color: colors.text,
    lineHeight: 20,
  },
  actionSection: {
    padding: 16,
    gap: 12,
  },
  resendButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    padding: 16,
    borderRadius: 12,
    gap: 8,
  },
  resendButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  deleteButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
    padding: 16,
    borderRadius: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: '#FF3B30',
  },
  deleteButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FF3B30',
  },
  
  // Modal
  modalContainer: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  modalCancel: {
    fontSize: 18,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  modalSave: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
  modalContent: {
    padding: 16,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  notesInput: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    color: colors.text,
    fontSize: 18,
    minHeight: 150,
    textAlignVertical: 'top',
  },
});
