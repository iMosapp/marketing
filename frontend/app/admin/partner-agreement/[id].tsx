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
interface Agreement {
  id: string;
  template_name: string;
  type: string;
  content?: string;
  partner_name?: string;
  partner_email?: string;
  partner_phone?: string;
  commission_tier?: { name: string; percentage: number };
  custom_commission_notes?: string;
  custom_terms?: string;
  commission_duration?: string;
  is_white_label?: boolean;
  commission_tiers?: { name: string; percentage: number; description?: string }[];
  payment_required: boolean;
  payment_amount?: number;
  status: string;
  w9_status?: string;
  w9_file_url?: string;
  w9_uploaded_at?: string;
  signed_partner?: {
    name: string;
    email: string;
    company?: string;
    phone?: string;
    address?: string;
    city?: string;
    state?: string;
    zip_code?: string;
    signed_at?: string;
    ip_address?: string;
    user_agent?: string;
    document_hash?: string;
    signature?: string;
  };
  signed_at?: string;
  created_at?: string;
  sent_at?: string;
}

export default function PartnerAgreementDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const { id } = useLocalSearchParams();
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editedPartnerName, setEditedPartnerName] = useState('');
  const [editedPartnerEmail, setEditedPartnerEmail] = useState('');
  const [editedPartnerPhone, setEditedPartnerPhone] = useState('');
  const [editedCommissionTier, setEditedCommissionTier] = useState('');
  const [editedCustomNotes, setEditedCustomNotes] = useState('');
  const [editedNotes, setEditedNotes] = useState('');
  const [editedContent, setEditedContent] = useState('');
  const [showContentEditor, setShowContentEditor] = useState(false);
  const [showFullScreenEditor, setShowFullScreenEditor] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendingText, setSendingText] = useState(false);

  useEffect(() => {
    loadAgreement();
  }, [id]);

  const loadAgreement = async () => {
    try {
      const response = await api.get(`/partners/agreements/${id}`);
      setAgreement(response.data);
      setEditedPartnerName(response.data.partner_name || '');
      setEditedPartnerEmail(response.data.partner_email || '');
      setEditedPartnerPhone(response.data.partner_phone || response.data.signed_partner?.phone || '');
      setEditedCommissionTier(response.data.commission_tier || '');
      setEditedCustomNotes(response.data.custom_commission_notes || '');
      setEditedNotes(response.data.notes || '');
      setEditedContent(response.data.content || '');
    } catch (error) {
      console.error('Error loading agreement:', error);
      showSimpleAlert('Error', 'Failed to load agreement');
    } finally {
      setLoading(false);
    }
  };

  const [showFullAgreement, setShowFullAgreement] = useState(false);

  const handleSave = async () => {
    if (!agreement) return;
    
    setSaving(true);
    try {
      await api.put(`/partners/agreements/${agreement.id}`, {
        partner_name: editedPartnerName,
        partner_email: editedPartnerEmail,
        partner_phone: editedPartnerPhone,
        commission_tier: editedCommissionTier || undefined,
        custom_commission_notes: editedCustomNotes || undefined,
        notes: editedNotes,
        content: editedContent || undefined,
      });
      setAgreement({
        ...agreement,
        partner_name: editedPartnerName,
        partner_email: editedPartnerEmail,
        partner_phone: editedPartnerPhone,
        commission_tier: editedCommissionTier,
        custom_commission_notes: editedCustomNotes,
        notes: editedNotes,
        content: editedContent,
      } as any);
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
      ? (process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com')
      : 'https://app.imonsocial.com';
    const link = `${baseUrl}/partner/agreement/${agreement.id}`;
    await Clipboard.setStringAsync(link);
    showSimpleAlert('Copied', 'Agreement link copied to clipboard');
  };

  const handleSendViaText = async () => {
    if (!agreement || !user?._id) return;
    const phone = agreement.signed_partner?.phone || (agreement as any).partner_phone || '';
    if (!phone) {
      showSimpleAlert('No Phone Number', 'This agreement has no partner phone number. Add one in the edit screen first.');
      return;
    }
    setSendingText(true);
    try {
      const res = await api.post(`/partners/agreements/${agreement.id}/add-contact`, {
        user_id: user._id,
      });
      const { sms_body, created, name } = res.data;
      const digits = phone.replace(/\D/g, '');
      const smsUrl = Platform.OS === 'ios'
        ? `sms:${digits}&body=${encodeURIComponent(sms_body)}`
        : `sms:${digits}?body=${encodeURIComponent(sms_body)}`;
      const canOpen = await Linking.canOpenURL(smsUrl);
      if (canOpen) {
        await Linking.openURL(smsUrl);
      } else if (typeof window !== 'undefined') {
        await Clipboard.setStringAsync(sms_body);
        showSimpleAlert('Copied to Clipboard', `No SMS app detected. Message copied:\n\n${sms_body}`);
        return;
      }
      if (created) {
        showSimpleAlert('Contact Added', `${name || 'Partner'} has been added to your contacts and your SMS is ready to send.`);
      }
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to prepare text message.');
    } finally {
      setSendingText(false);
    }
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
          {agreement.is_white_label && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, backgroundColor: '#C9A96218', paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, alignSelf: 'flex-start' }}>
              <Ionicons name="layers" size={16} color="#C9A962" />
              <Text style={{ fontSize: 15, fontWeight: '700', color: '#C9A962' }}>White Label Partner</Text>
            </View>
          )}
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

        {/* Commission — show custom override if set, otherwise state "per Exhibit A" */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Commission</Text>
          {agreement.custom_commission_notes ? (
            <View style={[styles.commissionCard, { borderLeftWidth: 3, borderLeftColor: '#C9A962' }]}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: '#C9A962', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Custom Commission Terms (in Exhibit A)</Text>
              <Text style={{ fontSize: 16, color: colors.text, lineHeight: 22 }}>{agreement.custom_commission_notes}</Text>
            </View>
          ) : (
            <View style={styles.commissionCard}>
              <Text style={styles.commissionTier}>{agreement.template_name}</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 4 }}>Commission tiers defined in Exhibit A</Text>
            </View>
          )}
          {agreement.custom_terms ? (
            <View style={[styles.commissionCard, { marginTop: 10, borderLeftWidth: 3, borderLeftColor: '#007AFF' }]}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: '#007AFF', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Exhibit A — Special Terms</Text>
              <Text style={{ fontSize: 15, color: colors.text, lineHeight: 22 }}>{agreement.custom_terms}</Text>
            </View>
          ) : null}
          {agreement.commission_duration ? (
            <View style={{ flexDirection: 'row', marginTop: 8, gap: 8 }}>
              <Text style={{ fontSize: 13, color: colors.textSecondary }}>Duration:</Text>
              <Text style={{ fontSize: 13, color: colors.text, fontWeight: '600', flex: 1 }}>{agreement.commission_duration}</Text>
            </View>
          ) : null}
        </View>

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

        {/* ── Legal Signature Record (shown after signing) ── */}
        {agreement.status === 'signed' && agreement.signed_partner && (
          <View style={[styles.section, { borderLeftWidth: 3, borderLeftColor: '#34C759' }]}>
            <Text style={styles.sectionTitle}>Legal Signature Record</Text>
            {[
              { label: 'Signed By',     value: agreement.signed_partner.name },
              { label: 'Email',         value: agreement.signed_partner.email },
              { label: 'Company',       value: agreement.signed_partner.company },
              { label: 'Phone',         value: agreement.signed_partner.phone },
              { label: 'Signed At',     value: agreement.signed_partner.signed_at ? new Date(agreement.signed_partner.signed_at).toLocaleString() : undefined },
              { label: 'IP Address',    value: agreement.signed_partner.ip_address },
              { label: 'User Agent',    value: agreement.signed_partner.user_agent, mono: true, truncate: true },
              { label: 'Doc Hash',      value: agreement.signed_partner.document_hash ? agreement.signed_partner.document_hash.slice(0, 16) + '…' : undefined, mono: true },
              { label: 'Signature',     value: agreement.signed_partner.signature ? `"${agreement.signed_partner.signature}"` : undefined },
            ].filter(r => r.value).map((row, i) => (
              <View key={i} style={{ flexDirection: 'row', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 12 }}>
                <Text style={{ fontSize: 13, color: colors.textSecondary, width: 90, flexShrink: 0 }}>{row.label}</Text>
                <Text style={{ fontSize: 13, color: colors.text, flex: 1, fontFamily: (row as any).mono ? 'monospace' : undefined }} numberOfLines={(row as any).truncate ? 1 : undefined}>{row.value}</Text>
              </View>
            ))}
          </View>
        )}

        {/* ── W-9 Panel ── */}
        {agreement.status === 'signed' && (
          <View style={[styles.section, {
            borderLeftWidth: 3,
            borderLeftColor: agreement.w9_status === 'verified' ? '#34C759' : agreement.w9_status === 'uploaded' ? '#FF9500' : '#FF3B30',
          }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <Text style={styles.sectionTitle}>W-9 Form</Text>
              <View style={{
                flexDirection: 'row', alignItems: 'center', gap: 6,
                backgroundColor: agreement.w9_status === 'verified' ? '#34C75920' : agreement.w9_status === 'uploaded' ? '#FF950020' : '#FF3B3015',
                borderRadius: 10, paddingHorizontal: 10, paddingVertical: 4,
              }}>
                <Ionicons
                  name={agreement.w9_status === 'verified' ? 'checkmark-circle' : agreement.w9_status === 'uploaded' ? 'cloud-upload' : 'alert-circle'}
                  size={14}
                  color={agreement.w9_status === 'verified' ? '#34C759' : agreement.w9_status === 'uploaded' ? '#FF9500' : '#FF3B30'}
                />
                <Text style={{ fontSize: 13, fontWeight: '700', color: agreement.w9_status === 'verified' ? '#34C759' : agreement.w9_status === 'uploaded' ? '#FF9500' : '#FF3B30' }}>
                  {agreement.w9_status === 'verified' ? 'Verified' : agreement.w9_status === 'uploaded' ? 'Awaiting Review' : 'Not Submitted'}
                </Text>
              </View>
            </View>

            {agreement.w9_uploaded_at && (
              <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 10 }}>
                Uploaded: {new Date(agreement.w9_uploaded_at).toLocaleString()}
              </Text>
            )}

            <View style={{ gap: 10 }}>
              {agreement.w9_file_url && (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: colors.border }}
                  onPress={() => {
                    const url = agreement.w9_file_url?.startsWith('/api/') ? `${process.env.EXPO_PUBLIC_API_URL || ''}${agreement.w9_file_url}` : agreement.w9_file_url;
                    if (typeof window !== 'undefined' && url) window.open(url, '_blank');
                  }}
                >
                  <Ionicons name="document-text" size={20} color="#007AFF" />
                  <Text style={{ fontSize: 15, fontWeight: '600', color: '#007AFF', flex: 1 }}>View / Download W-9</Text>
                  <Ionicons name="open-outline" size={16} color="#007AFF" />
                </TouchableOpacity>
              )}

              {agreement.w9_status === 'uploaded' && (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#34C75918', borderRadius: 10, padding: 14, borderWidth: 1, borderColor: '#34C759' }}
                  onPress={async () => {
                    try {
                      await api.post(`/partners/agreements/${agreement.id}/w9/verify`);
                      setAgreement((prev: any) => ({ ...prev, w9_status: 'verified' }));
                      showSimpleAlert('Verified', 'W-9 marked as verified. Partner is now fully onboarded.');
                    } catch { showSimpleAlert('Error', 'Failed to verify W-9.'); }
                  }}
                >
                  <Ionicons name="checkmark-circle" size={20} color="#34C759" />
                  <Text style={{ fontSize: 15, fontWeight: '700', color: '#34C759' }}>Mark W-9 as Verified</Text>
                </TouchableOpacity>
              )}

              {(!agreement.w9_status || agreement.w9_status === 'pending') && (
                <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20, textAlign: 'center', paddingVertical: 8 }}>
                  W-9 has not been submitted yet.{'\n'}Partner can upload it from their agreement signing page.
                </Text>
              )}
            </View>
          </View>
        )}

        {/* View Full Agreement */}
        {agreement.content && (
          <View style={styles.section}>
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 4 }}
              onPress={() => setShowFullAgreement(v => !v)}
            >
              <Text style={styles.sectionTitle}>Full Agreement Text</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={{ fontSize: 13, color: '#007AFF', fontWeight: '600' }}>{showFullAgreement ? 'Collapse' : 'View'}</Text>
                <Ionicons name={showFullAgreement ? 'chevron-up' : 'chevron-down'} size={18} color="#007AFF" />
              </View>
            </TouchableOpacity>
            {showFullAgreement && (
              <ScrollView
                style={{ maxHeight: 480, marginTop: 12, backgroundColor: colors.bg, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: colors.border }}
                nestedScrollEnabled
              >
                {agreement.content.split('\n').map((line: string, i: number) => {
                  if (line.startsWith('# ')) return <Text key={i} style={{ fontSize: 18, fontWeight: '800', color: colors.text, marginTop: 16, marginBottom: 6 }}>{line.substring(2)}</Text>;
                  if (line.startsWith('## ')) return <Text key={i} style={{ fontSize: 15, fontWeight: '700', color: colors.text, marginTop: 14, marginBottom: 4 }}>{line.substring(3)}</Text>;
                  if (line.startsWith('### ')) return <Text key={i} style={{ fontSize: 14, fontWeight: '700', color: colors.textSecondary, marginTop: 10, marginBottom: 3 }}>{line.substring(4)}</Text>;
                  if (line.startsWith('- ')) return <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 20, paddingLeft: 10 }}>{'• '}{line.substring(2)}</Text>;
                  if (line.startsWith('| ')) return <Text key={i} style={{ fontSize: 12, color: colors.text, fontFamily: 'monospace', lineHeight: 18 }}>{line}</Text>;
                  if (line.startsWith('---')) return <View key={i} style={{ height: 1, backgroundColor: colors.border, marginVertical: 8 }} />;
                  if (!line.trim()) return <View key={i} style={{ height: 6 }} />;
                  const boldParts = line.split(/\*\*(.*?)\*\*/);
                  if (boldParts.length > 1) return (
                    <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 20, marginBottom: 2 }}>
                      {boldParts.map((p, pi) => pi % 2 === 1
                        ? <Text key={pi} style={{ fontWeight: '700' }}>{p}</Text>
                        : p)}
                    </Text>
                  );
                  return <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 20, marginBottom: 2 }}>{line}</Text>;
                })}
              </ScrollView>
            )}
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionSection}>
          {agreement.status === 'signed' && (
            <TouchableOpacity
              style={[styles.copyLinkButton, { borderColor: '#34C759', backgroundColor: '#34C75910' }]}
              onPress={async () => {
                try {
                  const resp = await api.get(`/partners/agreements/${agreement.id}/pdf`, {
                    responseType: 'blob',
                  });
                  const blob = new Blob([resp.data], { type: 'application/pdf' });
                  const href = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  const partnerName = (agreement.signed_partner?.name || agreement.partner_name || 'agreement')
                    .replace(/[^a-zA-Z0-9_-]/g, '_');
                  a.href = href;
                  a.download = `signed_agreement_${partnerName}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  URL.revokeObjectURL(href);
                } catch (e) {
                  showSimpleAlert('Error', 'Failed to download PDF. Please try again.');
                }
              }}
              data-testid="download-pdf-button"
            >
              <Ionicons name="document-text" size={20} color="#34C759" />
              <Text style={[styles.copyLinkButtonText, { color: '#34C759' }]}>Download Signed Agreement (PDF)</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity 
            style={styles.copyLinkButton}
            onPress={copyLink}
            data-testid="copy-link-button"
          >
            <Ionicons name="link" size={20} color="#007AFF" />
            <Text style={styles.copyLinkButtonText}>Copy Agreement Link</Text>
          </TouchableOpacity>

          {/* Send via Text */}
          {agreement.status !== 'signed' && (
            <TouchableOpacity
              style={[styles.copyLinkButton, { borderColor: '#34C759', backgroundColor: '#34C75910' }]}
              onPress={handleSendViaText}
              disabled={sendingText}
              data-testid="send-text-btn"
            >
              {sendingText ? (
                <ActivityIndicator size="small" color="#34C759" />
              ) : (
                <>
                  <Ionicons name="chatbubble" size={20} color="#34C759" />
                  <Text style={[styles.copyLinkButtonText, { color: '#34C759' }]}>Send Link via Text</Text>
                </>
              )}
            </TouchableOpacity>
          )}
          
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
        <SafeAreaView style={[styles.modalContainer, { flex: 1 }]}>
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
          
          <ScrollView style={styles.modalContent} keyboardShouldPersistTaps="handled">

            {/* ── Partner Info ──────────────────────────────── */}
            <Text style={[styles.inputLabel, { color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11, marginBottom: 12 }]}>Partner Info</Text>

            <Text style={styles.inputLabel}>Partner Name</Text>
            <TextInput
              style={styles.textInput}
              value={editedPartnerName}
              onChangeText={setEditedPartnerName}
              placeholder="Enter partner name"
              placeholderTextColor={colors.textSecondary}
              autoCapitalize="words"
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

            <Text style={styles.inputLabel}>Partner Phone</Text>
            <TextInput
              style={styles.textInput}
              value={editedPartnerPhone}
              onChangeText={setEditedPartnerPhone}
              placeholder="Enter partner phone number"
              placeholderTextColor={colors.textSecondary}
              keyboardType="phone-pad"
            />

            {/* ── Commission ────────────────────────────────── */}
            <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 20 }} />
            <Text style={[styles.inputLabel, { color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11, marginBottom: 12 }]}>Commission Terms</Text>

            <Text style={styles.inputLabel}>Commission Tier</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
              {[
                { value: 'referral_standard', label: 'Referral\n10/15%' },
                { value: 'reseller_standard', label: 'Reseller\n20/30/40%' },
                { value: 'custom', label: 'Custom' },
              ].map(opt => (
                <TouchableOpacity
                  key={opt.value}
                  onPress={() => setEditedCommissionTier(opt.value)}
                  style={{ flex: 1, padding: 12, borderRadius: 12, borderWidth: 1.5, alignItems: 'center',
                    borderColor: editedCommissionTier === opt.value ? '#C9A962' : colors.border,
                    backgroundColor: editedCommissionTier === opt.value ? '#C9A96218' : colors.card,
                  }}
                >
                  <Text style={{ fontSize: 13, fontWeight: '600', color: editedCommissionTier === opt.value ? '#C9A962' : colors.text, textAlign: 'center' }}>
                    {opt.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.inputLabel}>Custom Commission Notes (replaces Exhibit A tiers)</Text>            <TextInput
              style={[styles.textInput, { minHeight: 90, textAlignVertical: 'top' }]}
              value={editedCustomNotes}
              onChangeText={setEditedCustomNotes}
              placeholder="e.g. 25% flat commission on all MRR for the first 12 months, then standard tiers apply."
              placeholderTextColor={colors.textSecondary}
              multiline
              numberOfLines={4}
            />
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 16, marginTop: -8 }}>
              Leave blank to use standard commission table for the selected tier.
            </Text>

            {/* ── Internal Notes ────────────────────────────── */}
            <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 20 }} />
            <Text style={[styles.inputLabel, { color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11, marginBottom: 12 }]}>Internal Notes</Text>

            <Text style={styles.inputLabel}>Notes (not shown to partner)</Text>
            <TextInput
              style={[styles.textInput, { minHeight: 80, textAlignVertical: 'top' }]}
              value={editedNotes}
              onChangeText={setEditedNotes}
              placeholder="Internal notes about this agreement..."
              placeholderTextColor={colors.textSecondary}
              multiline
              numberOfLines={4}
            />

            {/* ── Agreement Content ─────────────────────────── */}
            <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 20 }} />
            <Text style={[styles.inputLabel, { color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11, marginBottom: 4 }]}>Agreement Text</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 12 }}>
              Edit the full agreement text (MPA + Exhibit A). Changes are saved but not retroactively applied to already-signed agreements.
            </Text>

            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
                backgroundColor: '#C9A96215', borderRadius: 12, padding: 16, marginBottom: 12,
                borderWidth: 1.5, borderColor: '#C9A96240' }}
              onPress={() => setShowFullScreenEditor(true)}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Ionicons name="document-text" size={20} color="#C9A962" />
                <View>
                  <Text style={{ fontSize: 15, fontWeight: '700', color: '#C9A962' }}>Open Full Editor</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                    {editedContent ? `${editedContent.length.toLocaleString()} characters` : 'No content yet'}
                  </Text>
                </View>
              </View>
              <Ionicons name="expand" size={18} color="#C9A962" />
            </TouchableOpacity>

            {/* removed inline collapsed editor — now full-screen via showFullScreenEditor */}

            <View style={{ height: 40 }} />
          </ScrollView>
        </SafeAreaView>
      </Modal>
      {/* ── Full-Screen Agreement Text Editor ── */}
      <Modal visible={showFullScreenEditor} animationType="slide" presentationStyle="fullScreen" onRequestClose={() => setShowFullScreenEditor(false)}>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
          {/* Header */}
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <TouchableOpacity onPress={() => setShowFullScreenEditor(false)}>
              <Text style={{ fontSize: 17, color: '#FF3B30' }}>Discard</Text>
            </TouchableOpacity>
            <View style={{ alignItems: 'center' }}>
              <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Agreement Text</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{editedContent.length.toLocaleString()} chars</Text>
            </View>
            <TouchableOpacity onPress={() => setShowFullScreenEditor(false)}>
              <Text style={{ fontSize: 17, fontWeight: '700', color: '#C9A962' }}>Done</Text>
            </TouchableOpacity>
          </View>

          {/* Toolbar hint */}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 8, backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <Ionicons name="information-circle-outline" size={15} color={colors.textSecondary} />
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>
              Markdown supported: **bold**, # Heading, - list, --- divider
            </Text>
          </View>

          {/* Editor */}
          <TextInput
            style={{
              flex: 1,
              padding: 16,
              fontSize: 15,
              lineHeight: 24,
              color: colors.text,
              backgroundColor: colors.bg,
              fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
              textAlignVertical: 'top',
            }}
            value={editedContent}
            onChangeText={setEditedContent}
            placeholder="Paste or type the full MPA + Exhibit A in Markdown..."
            placeholderTextColor={colors.textSecondary}
            multiline
            scrollEnabled
            autoCorrect={false}
            autoCapitalize="none"
            data-testid="agreement-content-editor"
          />

          {/* Bottom bar */}
          <View style={{ paddingHorizontal: 16, paddingVertical: 12, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.card }}>
            <TouchableOpacity
              style={{ backgroundColor: '#C9A962', borderRadius: 12, padding: 16, alignItems: 'center' }}
              onPress={() => setShowFullScreenEditor(false)}
            >
              <Text style={{ fontSize: 17, fontWeight: '800', color: '#000' }}>Save & Close Editor</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
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
    fontSize: 14,
    fontWeight: '600',
  },
  typeText: {
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
    fontSize: 14,
    color: '#34C759',
    fontWeight: '600',
  },
  notSignedText: {
    fontSize: 16,
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
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  commissionPercentage: {
    fontSize: 28,
    fontWeight: '700',
    color: '#34C759',
  },
  commissionLabel: {
    fontSize: 14,
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
    fontSize: 16,
    color: colors.textSecondary,
  },
  paymentAmount: {
    fontSize: 21,
    fontWeight: '700',
    color: '#FF9500',
  },
  paymentNote: {
    fontSize: 14,
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
    fontSize: 16,
    color: colors.textSecondary,
  },
  timelineValue: {
    fontSize: 16,
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
    marginTop: 16,
  },
  textInput: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    color: colors.text,
    fontSize: 18,
  },
});
