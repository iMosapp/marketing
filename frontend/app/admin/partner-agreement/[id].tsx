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
import * as Clipboard from 'expo-clipboard';
import api from '../../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../../services/alert';

import { useThemeStore } from '../../../store/themeStore';
interface Agreement {
  id: string;
  template_name: string;
  type: string;
  content?: string;
  partner_name?: string;
  partner_email?: string;
  commission_tier?: { name: string; percentage: number };
  commission_tiers?: { name: string; percentage: number; description?: string }[];
  payment_required: boolean;
  payment_amount?: number;
  status: string;
  signed_partner?: {
    name: string;
    email: string;
    company?: string;
    phone?: string;
    signed_at?: string;
  };
  signed_at?: string;
  created_at?: string;
  sent_at?: string;
}

export default function PartnerAgreementDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editedPartnerName, setEditedPartnerName] = useState('');
  const [editedPartnerEmail, setEditedPartnerEmail] = useState('');
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    loadAgreement();
  }, [id]);

  const loadAgreement = async () => {
    try {
      const response = await api.get(`/partners/agreements/${id}`);
      setAgreement(response.data);
      setEditedPartnerName(response.data.partner_name || '');
      setEditedPartnerEmail(response.data.partner_email || '');
    } catch (error) {
      console.error('Error loading agreement:', error);
      showSimpleAlert('Error', 'Failed to load agreement');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!agreement) return;
    
    setSaving(true);
    try {
      await api.put(`/partners/agreements/${agreement.id}`, {
        partner_name: editedPartnerName,
        partner_email: editedPartnerEmail
      });
      setAgreement({ 
        ...agreement, 
        partner_name: editedPartnerName,
        partner_email: editedPartnerEmail 
      });
      setShowEditModal(false);
      showSimpleAlert('Success', 'Agreement updated');
    } catch (error) {
      showSimpleAlert('Error', 'Failed to update agreement');
    } finally {
      setSaving(false);
    }
  };

  const handleResend = async () => {
    if (!agreement) return;
    
    if (!agreement.partner_email) {
      showSimpleAlert('Error', 'Please add a partner email first');
      return;
    }
    
    showConfirm(
      'Resend Agreement',
      `Send agreement link to ${agreement.partner_email}?`,
      async () => {
        setSending(true);
        try {
          await api.post(`/partners/agreements/${agreement.id}/send`);
          showSimpleAlert('Success', 'Agreement link sent successfully');
          loadAgreement();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to send agreement');
        } finally {
          setSending(false);
        }
      },
      undefined,
      'Send',
      'Cancel'
    );
  };

  const handleDelete = async () => {
    if (!agreement) return;
    
    if (agreement.status === 'signed') {
      showSimpleAlert('Error', 'Cannot delete a signed agreement');
      return;
    }
    
    showConfirm(
      'Delete Agreement',
      `Are you sure you want to delete this agreement? This cannot be undone.`,
      async () => {
        try {
          await api.delete(`/partners/agreements/${agreement.id}`);
          showSimpleAlert('Success', 'Agreement deleted');
          router.back();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to delete agreement');
        }
      },
      undefined,
      'Delete',
      'Cancel'
    );
  };

  const copyLink = async () => {
    if (!agreement) return;
    const baseUrl = Platform.OS === 'web' 
      ? window.location.origin 
      : 'https://app.imosapp.com';
    const link = `${baseUrl}/partner/agreement/${agreement.id}`;
    await Clipboard.setStringAsync(link);
    showSimpleAlert('Copied', 'Agreement link copied to clipboard');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'signed': return '#34C759';
      case 'pending_payment': return '#FF9500';
      case 'viewed': return '#007AFF';
      case 'sent': return colors.textSecondary;
      case 'draft': return '#6E6E73';
      default: return colors.textSecondary;
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
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

  if (!agreement) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Agreement Not Found</Text>
          <View style={{ width: 28 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={64} color="#FF3B30" />
          <Text style={styles.errorText}>Agreement not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} data-testid="back-button">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Agreement Details</Text>
        <TouchableOpacity onPress={() => setShowEditModal(true)} style={styles.editButton} data-testid="edit-button">
          <Ionicons name="create-outline" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content}>
        {/* Agreement Type & Status */}
        <View style={styles.section}>
          <View style={styles.agreementHeader}>
            <Text style={styles.agreementType}>{agreement.template_name}</Text>
            <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(agreement.status)}20` }]}>
              <Text style={[styles.statusText, { color: getStatusColor(agreement.status) }]}>
                {agreement.status.replace('_', ' ').toUpperCase()}
              </Text>
            </View>
          </View>
          <Text style={styles.typeText}>{agreement.type === 'reseller' ? 'Reseller Agreement' : 'Referral Partner Agreement'}</Text>
        </View>

        {/* Partner Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Partner</Text>
          <View style={styles.infoCard}>
            {agreement.signed_partner ? (
              <>
                <View style={styles.infoRow}>
                  <Ionicons name="person" size={18} color="#34C759" />
                  <Text style={styles.infoText}>{agreement.signed_partner.name}</Text>
                  <View style={styles.signedBadge}>
                    <Ionicons name="checkmark-circle" size={14} color="#34C759" />
                    <Text style={styles.signedBadgeText}>Signed</Text>
                  </View>
                </View>
                {agreement.signed_partner.email && (
                  <View style={styles.infoRow}>
                    <Ionicons name="mail" size={18} color={colors.textSecondary} />
                    <Text style={styles.infoText}>{agreement.signed_partner.email}</Text>
                  </View>
                )}
                {agreement.signed_partner.company && (
                  <View style={styles.infoRow}>
                    <Ionicons name="business" size={18} color={colors.textSecondary} />
                    <Text style={styles.infoText}>{agreement.signed_partner.company}</Text>
                  </View>
                )}
                {agreement.signed_partner.phone && (
                  <View style={styles.infoRow}>
                    <Ionicons name="call" size={18} color={colors.textSecondary} />
                    <Text style={styles.infoText}>{agreement.signed_partner.phone}</Text>
                  </View>
                )}
              </>
            ) : (
              <>
                {agreement.partner_name ? (
                  <View style={styles.infoRow}>
                    <Ionicons name="person" size={18} color={colors.textSecondary} />
                    <Text style={styles.infoText}>{agreement.partner_name}</Text>
                  </View>
                ) : null}
                {agreement.partner_email ? (
                  <View style={styles.infoRow}>
                    <Ionicons name="mail" size={18} color={colors.textSecondary} />
                    <Text style={styles.infoText}>{agreement.partner_email}</Text>
                  </View>
                ) : null}
                {!agreement.partner_name && !agreement.partner_email && (
                  <Text style={styles.notSignedText}>Not yet assigned to a partner</Text>
                )}
              </>
            )}
          </View>
        </View>

        {/* Commission Tier */}
        {agreement.commission_tier && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Commission</Text>
            <View style={styles.commissionCard}>
              <View style={styles.commissionHeader}>
                <Text style={styles.commissionTier}>{agreement.commission_tier.name}</Text>
                <Text style={styles.commissionPercentage}>{agreement.commission_tier.percentage}%</Text>
              </View>
              <Text style={styles.commissionLabel}>Commission Rate</Text>
            </View>
          </View>
        )}

        {/* Payment Info */}
        {agreement.payment_required && agreement.payment_amount && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Payment</Text>
            <View style={styles.paymentCard}>
              <View style={styles.paymentRow}>
                <Text style={styles.paymentLabel}>One-time Payment</Text>
                <Text style={styles.paymentAmount}>${agreement.payment_amount.toFixed(2)}</Text>
              </View>
              <Text style={styles.paymentNote}>Required before activation</Text>
            </View>
          </View>
        )}

        {/* Timeline */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Timeline</Text>
          <View style={styles.timelineCard}>
            <View style={styles.timelineRow}>
              <Text style={styles.timelineLabel}>Created</Text>
              <Text style={styles.timelineValue}>{formatDate(agreement.created_at)}</Text>
            </View>
            {agreement.sent_at && (
              <View style={styles.timelineRow}>
                <Text style={styles.timelineLabel}>Sent</Text>
                <Text style={styles.timelineValue}>{formatDate(agreement.sent_at)}</Text>
              </View>
            )}
            {agreement.signed_at && (
              <View style={styles.timelineRow}>
                <Text style={styles.timelineLabel}>Signed</Text>
                <Text style={[styles.timelineValue, { color: '#34C759' }]}>{formatDate(agreement.signed_at)}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Action Buttons */}
        <View style={styles.actionSection}>
          {/* Copy Link Button */}
          <TouchableOpacity 
            style={styles.copyLinkButton}
            onPress={copyLink}
            data-testid="copy-link-button"
          >
            <Ionicons name="link" size={20} color="#007AFF" />
            <Text style={styles.copyLinkButtonText}>Copy Agreement Link</Text>
          </TouchableOpacity>
          
          {/* Resend Button */}
          {agreement.status !== 'signed' && (
            <TouchableOpacity 
              style={styles.resendButton}
              onPress={handleResend}
              disabled={sending}
              data-testid="resend-button"
            >
              {sending ? (
                <ActivityIndicator size="small" color={colors.text} />
              ) : (
                <>
                  <Ionicons name="send" size={20} color={colors.text} />
                  <Text style={styles.resendButtonText}>Send to Partner</Text>
                </>
              )}
            </TouchableOpacity>
          )}
          
          {/* Delete Button - only for non-signed agreements */}
          {agreement.status !== 'signed' && (
            <TouchableOpacity 
              style={styles.deleteButton}
              onPress={handleDelete}
              data-testid="delete-button"
            >
              <Ionicons name="trash" size={20} color="#FF3B30" />
              <Text style={styles.deleteButtonText}>Delete Agreement</Text>
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
            <Text style={styles.modalTitle}>Edit Agreement</Text>
            <TouchableOpacity onPress={handleSave} disabled={saving}>
              {saving ? (
                <ActivityIndicator size="small" color="#007AFF" />
              ) : (
                <Text style={styles.modalSave}>Save</Text>
              )}
            </TouchableOpacity>
          </View>
          
          <ScrollView style={styles.modalContent}>
            <Text style={styles.inputLabel}>Partner Name</Text>
            <TextInput
              style={styles.textInput}
              value={editedPartnerName}
              onChangeText={setEditedPartnerName}
              placeholder="Enter partner name"
              placeholderTextColor={colors.textSecondary}
            />
            
            <Text style={styles.inputLabel}>Partner Email</Text>
            <TextInput
              style={styles.textInput}
              value={editedPartnerEmail}
              onChangeText={setEditedPartnerEmail}
              placeholder="Enter partner email"
              placeholderTextColor={colors.textSecondary}
              keyboardType="email-address"
              autoCapitalize="none"
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
    fontSize: 16,
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
    fontSize: 18,
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
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  agreementHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  agreementType: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  typeText: {
    fontSize: 14,
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
    fontSize: 16,
    color: colors.text,
    marginLeft: 12,
    flex: 1,
  },
  signedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#34C75920',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
  },
  signedBadgeText: {
    fontSize: 12,
    color: '#34C759',
    fontWeight: '600',
  },
  notSignedText: {
    fontSize: 14,
    color: colors.textSecondary,
    fontStyle: 'italic',
  },
  commissionCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  commissionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  commissionTier: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  commissionPercentage: {
    fontSize: 28,
    fontWeight: '700',
    color: '#34C759',
  },
  commissionLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  paymentCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  paymentRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  paymentLabel: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  paymentAmount: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FF9500',
  },
  paymentNote: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 8,
  },
  timelineCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  timelineRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  timelineLabel: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  timelineValue: {
    fontSize: 14,
    color: colors.text,
  },
  actionSection: {
    padding: 16,
    gap: 12,
  },
  copyLinkButton: {
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
  copyLinkButtonText: {
    fontSize: 16,
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
    fontSize: 16,
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
    fontSize: 16,
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
    fontSize: 16,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  modalSave: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  modalContent: {
    padding: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    marginTop: 16,
  },
  textInput: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    color: colors.text,
    fontSize: 16,
  },
});
