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
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import api from '../../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../../services/alert';
import { useAuthStore } from '../../../store/authStore';

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
    authorized_signer?: { name?: string; title?: string; email?: string };
  };
  pricing: {
    base_price: number;
    final_price: number;
    discount_percent: number;
    interval: string;
    num_users?: number;
    trial_days?: number;
  };
  valid_until: string;
  created_at: string;
  notes?: string;
  digital_signature?: {
    name?: string;
    email?: string;
    signature?: string;
    signed_at?: string;
    ip_address?: string;
    user_agent?: string;
    document_hash?: string;
  };
  accepted_at?: string;
  sent_at?: string;
}

export default function QuoteDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const { id } = useLocalSearchParams();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editedNotes, setEditedNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendingText, setSendingText] = useState(false);

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

  const copyLink = async () => {
    if (!quote) return;
    const base = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
    await Clipboard.setStringAsync(`${base}/quote/accept/${quote._id}`);
    showSimpleAlert('Copied', 'Quote signing link copied to clipboard');
  };

  const handleSendViaText = async () => {
    if (!quote || !user?._id) return;
    const phone = quote.customer?.phone;
    if (!phone) {
      showSimpleAlert('No Phone', 'This quote has no customer phone number. Add one first.');
      return;
    }
    setSendingText(true);
    try {
      const res = await api.post(`/subscriptions/quotes/${quote._id}/add-contact`, {
        user_id: user._id,
      });
      const { sms_body, created, name } = res.data;
      // Open native SMS with pre-filled message
      const digits = phone.replace(/\D/g, '');
      const smsUrl = Platform.OS === 'ios'
        ? `sms:${digits}&body=${encodeURIComponent(sms_body)}`
        : `sms:${digits}?body=${encodeURIComponent(sms_body)}`;
      const canOpen = await Linking.canOpenURL(smsUrl);
      if (canOpen) {
        await Linking.openURL(smsUrl);
      } else if (typeof window !== 'undefined') {
        // Web fallback — copy to clipboard
        await Clipboard.setStringAsync(sms_body);
        showSimpleAlert('Copied to Clipboard', `No SMS app detected. Message copied:\n\n${sms_body}`);
        return;
      }
      if (created) {
        showSimpleAlert(
          'Contact Added',
          `${name || 'Customer'} has been added to your contacts and your SMS is ready to send.`
        );
      }
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to prepare text message.');
    } finally {
      setSendingText(false);
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

        {/* Digital Signature Record */}
        {quote.status === 'accepted' && quote.digital_signature && (
          <View style={[styles.section, { borderLeftWidth: 3, borderLeftColor: '#34C759' }]}>
            <Text style={styles.sectionTitle}>Digital Signature Record</Text>
            {[
              { label: 'Signed By',     value: quote.digital_signature.name },
              { label: 'Email',         value: quote.digital_signature.email },
              { label: 'Signed At',     value: quote.digital_signature.signed_at ? new Date(quote.digital_signature.signed_at).toLocaleString() : undefined },
              { label: 'IP Address',    value: quote.digital_signature.ip_address, mono: true },
              { label: 'Signature',     value: quote.digital_signature.signature ? `"${quote.digital_signature.signature}"` : undefined },
              { label: 'User Agent',    value: quote.digital_signature.user_agent, mono: true, truncate: true },
              { label: 'Doc Hash',      value: quote.digital_signature.document_hash ? quote.digital_signature.document_hash.slice(0,16) + '…' : undefined, mono: true },
            ].filter(r => r.value).map((row, i) => (
              <View key={i} style={{ flexDirection: 'row', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 12 }}>
                <Text style={{ fontSize: 13, color: colors.textSecondary, width: 88, flexShrink: 0 }}>{row.label}</Text>
                <Text style={{ fontSize: 13, color: colors.text, flex: 1, fontFamily: (row as any).mono ? 'monospace' : undefined }} numberOfLines={(row as any).truncate ? 1 : undefined}>
                  {row.value}
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Payment Status (TODO) */}
        {quote.status === 'accepted' && (
          <View style={[styles.section, { borderLeftWidth: 3, borderLeftColor: '#FF9500' }]}>
            <Text style={styles.sectionTitle}>Payment Status</Text>
            <View style={{ backgroundColor: '#FF950015', borderRadius: 10, padding: 14 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: '#FF9500', marginBottom: 4 }}>Pending — Awaiting Payment Setup</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19 }}>
                Customer was emailed &amp; texted a payment setup link when they signed.{'\n'}
                Payment collection will auto-activate once Stripe is configured.
              </Text>
            </View>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionSection}>
          {/* Copy signing link — for unsigned quotes */}
          {quote.status !== 'accepted' && (
            <TouchableOpacity style={styles.copyButton} onPress={copyLink} data-testid="copy-link-button">
              <Ionicons name="link" size={20} color="#007AFF" />
              <Text style={styles.copyButtonText}>Copy Signing Link</Text>
            </TouchableOpacity>
          )}

          {/* Send via Text — creates contact + opens SMS pre-filled */}
          {quote.status !== 'accepted' && quote.customer?.phone && (
            <TouchableOpacity
              style={[styles.copyButton, { borderColor: '#34C759', backgroundColor: '#34C75910' }]}
              onPress={handleSendViaText}
              disabled={sendingText}
              data-testid="send-text-btn"
            >
              {sendingText ? (
                <ActivityIndicator size="small" color="#34C759" />
              ) : (
                <>
                  <Ionicons name="chatbubble" size={20} color="#34C759" />
                  <Text style={[styles.copyButtonText, { color: '#34C759' }]}>Send Link via Text</Text>
                </>
              )}
            </TouchableOpacity>
          )}
          {/* Download PDF — accepted quotes only */}
          {quote.status === 'accepted' && (
            <TouchableOpacity
              style={[styles.copyButton, { borderColor: '#34C759', backgroundColor: '#34C75910' }]}
              onPress={async () => {
                try {
                  const resp = await api.get(`/subscriptions/quotes/${quote._id}/pdf`, { responseType: 'blob' });
                  const blob = new Blob([resp.data], { type: 'application/pdf' });
                  const href = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  const safeName = (quote.business_info?.company_name || quote.customer?.name || 'quote').replace(/[^a-zA-Z0-9_-]/g,'_');
                  a.href = href; a.download = `signed_quote_${safeName}.pdf`;
                  document.body.appendChild(a); a.click();
                  document.body.removeChild(a); URL.revokeObjectURL(href);
                } catch { showSimpleAlert('Error', 'Failed to download PDF.'); }
              }}
              data-testid="download-pdf-button"
            >
              <Ionicons name="document-text" size={20} color="#34C759" />
              <Text style={[styles.copyButtonText, { color: '#34C759' }]}>Download Signed Quote (PDF)</Text>
            </TouchableOpacity>
          )}

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
  copyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
    padding: 16,
    borderRadius: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  copyButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
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
