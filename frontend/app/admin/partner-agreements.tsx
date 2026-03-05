import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { WebModal } from '../../components/WebModal';

import { useThemeStore } from '../../store/themeStore';
interface Template {
  id: string;
  name: string;
  type: string;
  commission_tiers: { name: string; percentage: number; description?: string }[];
  payment_required: boolean;
  payment_amount?: number;
}

interface Agreement {
  id: string;
  template_name: string;
  type: string;
  partner_name?: string;
  partner_email?: string;
  commission_tier?: { name: string; percentage: number };
  custom_commission_notes?: string;
  is_white_label?: boolean;
  payment_required: boolean;
  payment_amount?: number;
  status: string;
  created_at: string;
  signed_at?: string;
}

export default function PartnerAgreementsScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  
  // New agreement form
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [selectedTier, setSelectedTier] = useState<{ name: string; percentage: number } | null>(null);
  const [partnerEmail, setPartnerEmail] = useState('');
  const [partnerName, setPartnerName] = useState('');
  const [paymentRequired, setPaymentRequired] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [customCommissionNotes, setCustomCommissionNotes] = useState('');
  const [isWhiteLabel, setIsWhiteLabel] = useState(false);
  const [createdLink, setCreatedLink] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [templatesRes, agreementsRes] = await Promise.all([
        api.get('/partners/templates'),
        api.get('/partners/agreements'),
      ]);
      setTemplates(templatesRes.data);
      setAgreements(agreementsRes.data);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const createAgreement = async () => {
    if (!selectedTemplate || !selectedTier) {
      showSimpleAlert('Required', 'Please select a template and commission tier');
      return;
    }
    
    setCreating(true);
    try {
      const response = await api.post('/partners/agreements', {
        template_id: selectedTemplate.id,
        commission_tier: selectedTier,
        custom_commission_notes: customCommissionNotes || null,
        is_white_label: isWhiteLabel,
        partner_email: partnerEmail || null,
        partner_name: partnerName || null,
        payment_required: paymentRequired,
        payment_amount: paymentRequired && paymentAmount ? parseFloat(paymentAmount) : null,
        created_by: user?._id,
      });
      
      // Update to sent status
      await api.put(`/partners/agreements/${response.data.id}`, { status: 'sent' });
      
      const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
      const link = `${baseUrl}/partner/agreement/${response.data.id}`;
      setCreatedLink(link);
      
      // Refresh agreements list
      loadData();
    } catch (error) {
      showSimpleAlert('Error', 'Failed to create agreement');
    } finally {
      setCreating(false);
    }
  };

  const copyLink = async (agreementId: string) => {
    const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
    const link = `${baseUrl}/partner/agreement/${agreementId}`;
    await Clipboard.setStringAsync(link);
    showSimpleAlert('Copied', 'Agreement link copied to clipboard');
  };

  const resetModal = () => {
    setShowCreateModal(false);
    setSelectedTemplate(null);
    setSelectedTier(null);
    setPartnerEmail('');
    setPartnerName('');
    setPaymentRequired(false);
    setPaymentAmount('');
    setCustomCommissionNotes('');
    setIsWhiteLabel(false);
    setCreatedLink(null);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'signed': return '#34C759';
      case 'pending_payment': return '#FF9500';
      case 'viewed': return '#007AFF';
      case 'sent': return colors.textSecondary;
      default: return '#6E6E73';
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  // Check if user is super admin
  if (user?.role !== 'super_admin') {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Partner Agreements</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.accessDenied}>
          <Ionicons name="lock-closed" size={64} color={colors.textSecondary} />
          <Text style={styles.accessDeniedText}>Super Admin Access Required</Text>
          <Text style={styles.accessDeniedSubtext}>This feature is only available to super administrators</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Partner Agreements</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => setShowCreateModal(true)}
        >
          <Ionicons name="add" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content}>
        {/* Stats */}
        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>{agreements.length}</Text>
            <Text style={styles.statLabel}>Total</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={[styles.statNumber, { color: '#34C759' }]}>
              {agreements.filter(a => a.status === 'signed').length}
            </Text>
            <Text style={styles.statLabel}>Signed</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={[styles.statNumber, { color: '#FF9500' }]}>
              {agreements.filter(a => a.status === 'pending_payment').length}
            </Text>
            <Text style={styles.statLabel}>Pending</Text>
          </View>
        </View>

        {/* Agreements List */}
        <Text style={styles.sectionTitle}>Recent Agreements</Text>
        
        {agreements.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="document-text-outline" size={48} color={colors.textSecondary} />
            <Text style={styles.emptyText}>No agreements yet</Text>
            <Text style={styles.emptySubtext}>Create your first partner agreement</Text>
          </View>
        ) : (
          agreements.map((agreement) => (
            <TouchableOpacity
              key={agreement.id}
              style={styles.agreementCard}
              onPress={() => router.push(`/admin/partner-agreement/${agreement.id}`)}
              data-testid={`agreement-${agreement.id}`}
            >
              <View style={styles.agreementHeader}>
                <View>
                  <Text style={styles.agreementType}>{agreement.template_name}</Text>
                  <Text style={styles.agreementPartner}>
                    {agreement.partner_name || agreement.partner_email || 'Not yet signed'}
                  </Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: getStatusColor(agreement.status) + '20' }]}>
                  <Text style={[styles.statusText, { color: getStatusColor(agreement.status) }]}>
                    {agreement.status.replace('_', ' ')}
                  </Text>
                </View>
              </View>
              
              {agreement.commission_tier && (
                <Text style={styles.agreementTier}>
                  {agreement.commission_tier.name} - {agreement.commission_tier.percentage}% commission
                </Text>
              )}
              
              {agreement.custom_commission_notes && (
                <Text style={styles.agreementCustomCommission} numberOfLines={2}>
                  {agreement.custom_commission_notes}
                </Text>
              )}
              
              {agreement.is_white_label && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, backgroundColor: '#C9A96215', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, alignSelf: 'flex-start' }}>
                  <Ionicons name="layers" size={14} color="#C9A962" />
                  <Text style={{ fontSize: 12, fontWeight: '700', color: '#C9A962' }}>White Label</Text>
                </View>
              )}
              
              <View style={styles.agreementFooter}>
                <Text style={styles.agreementDate}>
                  Created {new Date(agreement.created_at).toLocaleDateString()}
                  {agreement.signed_at && ` • Signed ${new Date(agreement.signed_at).toLocaleDateString()}`}
                </Text>
                <TouchableOpacity onPress={() => copyLink(agreement.id)}>
                  <Ionicons name="link" size={20} color="#007AFF" />
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          ))
        )}
      </ScrollView>

      {/* Create Agreement Modal */}
      <WebModal visible={showCreateModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {createdLink ? 'Agreement Created!' : 'New Partner Agreement'}
              </Text>
              <TouchableOpacity onPress={resetModal}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            
            {createdLink ? (
              <View style={styles.successContent}>
                <Ionicons name="checkmark-circle" size={64} color="#34C759" />
                <Text style={styles.successTitle}>Agreement Ready to Share</Text>
                <Text style={styles.successSubtitle}>Send this link to your partner:</Text>
                
                <View style={styles.linkBox}>
                  <Text style={styles.linkText} numberOfLines={2}>{createdLink}</Text>
                  <TouchableOpacity 
                    onPress={async () => {
                      await Clipboard.setStringAsync(createdLink);
                      showSimpleAlert('Copied!', 'Link copied to clipboard');
                    }}
                  >
                    <Ionicons name="copy" size={24} color="#007AFF" />
                  </TouchableOpacity>
                </View>
                
                <TouchableOpacity style={styles.doneButton} onPress={resetModal}>
                  <Text style={styles.doneButtonText}>Done</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <ScrollView style={styles.modalScroll}>
                {/* Template Selection */}
                <Text style={styles.formLabel}>Agreement Type</Text>
                <View style={styles.templateOptions}>
                  {templates.map((template) => (
                    <TouchableOpacity
                      key={template.id}
                      style={[
                        styles.templateOption,
                        selectedTemplate?.id === template.id && styles.templateOptionSelected
                      ]}
                      onPress={() => {
                        setSelectedTemplate(template);
                        setSelectedTier(null);
                      }}
                    >
                      <Ionicons 
                        name={template.type === 'reseller' ? 'storefront' : 'people'} 
                        size={24} 
                        color={selectedTemplate?.id === template.id ? '#007AFF' : colors.textSecondary} 
                      />
                      <Text style={[
                        styles.templateOptionText,
                        selectedTemplate?.id === template.id && styles.templateOptionTextSelected
                      ]}>
                        {template.name}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Commission Tier Selection */}
                {selectedTemplate && (
                  <>
                    <Text style={styles.formLabel}>Commission Tier</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tierScroll}>
                      {selectedTemplate.commission_tiers.map((tier, index) => (
                        <TouchableOpacity
                          key={index}
                          style={[
                            styles.tierOption,
                            selectedTier?.name === tier.name && styles.tierOptionSelected
                          ]}
                          onPress={() => setSelectedTier(tier)}
                        >
                          <Text style={[
                            styles.tierName,
                            selectedTier?.name === tier.name && styles.tierNameSelected
                          ]}>
                            {tier.name}
                          </Text>
                          <Text style={[
                            styles.tierPercentage,
                            selectedTier?.name === tier.name && styles.tierPercentageSelected
                          ]}>
                            {tier.percentage}%
                          </Text>
                          {tier.description && (
                            <Text style={styles.tierDesc}>{tier.description}</Text>
                          )}
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </>
                )}

                {/* Custom Commission Structure */}
                {selectedTemplate && (
                  <>
                    <Text style={styles.formLabel}>Custom Commission Structure</Text>
                    <TextInput
                      style={[styles.input, { minHeight: 80, textAlignVertical: 'top' }]}
                      value={customCommissionNotes}
                      onChangeText={setCustomCommissionNotes}
                      placeholder="e.g., 15% of MRR for first 12 months, then 10% ongoing. $50 flat per account + 5% of add-ons."
                      placeholderTextColor={colors.textSecondary}
                      multiline
                      data-testid="custom-commission-notes"
                    />
                    <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: -8, marginBottom: 4 }}>
                      Describe the full commission deal. This overrides or supplements the tier above.
                    </Text>
                  </>
                )}

                {/* Partner Info (Optional) */}
                <Text style={styles.formLabel}>Partner Info (Optional)</Text>
                <TextInput
                  style={styles.input}
                  value={partnerName}
                  onChangeText={setPartnerName}
                  placeholder="Partner name"
                  placeholderTextColor={colors.textSecondary}
                />
                <TextInput
                  style={styles.input}
                  value={partnerEmail}
                  onChangeText={setPartnerEmail}
                  placeholder="Partner email"
                  placeholderTextColor={colors.textSecondary}
                  keyboardType="email-address"
                  autoCapitalize="none"
                />

                {/* Payment Requirement */}
                <TouchableOpacity
                  style={styles.paymentToggle}
                  onPress={() => setPaymentRequired(!paymentRequired)}
                >
                  <View style={[styles.checkbox, paymentRequired && styles.checkboxChecked]}>
                    {paymentRequired && <Ionicons name="checkmark" size={16} color={colors.text} />}
                  </View>
                  <Text style={styles.paymentToggleText}>Require one-time payment</Text>
                </TouchableOpacity>

                {paymentRequired && (
                  <View style={styles.paymentAmountRow}>
                    <Text style={styles.currencySymbol}>$</Text>
                    <TextInput
                      style={[styles.input, styles.paymentInput]}
                      value={paymentAmount}
                      onChangeText={setPaymentAmount}
                      placeholder="0.00"
                      placeholderTextColor={colors.textSecondary}
                      keyboardType="decimal-pad"
                    />
                  </View>
                )}

                {/* White Label Toggle */}
                <TouchableOpacity
                  style={styles.paymentToggle}
                  onPress={() => setIsWhiteLabel(!isWhiteLabel)}
                  data-testid="white-label-toggle"
                >
                  <View style={[styles.checkbox, isWhiteLabel && { backgroundColor: '#C9A962', borderColor: '#C9A962' }]}>
                    {isWhiteLabel && <Ionicons name="checkmark" size={16} color="#000" />}
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.paymentToggleText}>White Label Partner</Text>
                    <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 2 }}>Partner will have branded sub-orgs, accounts & users</Text>
                  </View>
                </TouchableOpacity>

                {/* Create Button */}
                <TouchableOpacity
                  style={[styles.createButton, (!selectedTemplate || !selectedTier) && styles.createButtonDisabled]}
                  onPress={createAgreement}
                  disabled={!selectedTemplate || !selectedTier || creating}
                >
                  {creating ? (
                    <ActivityIndicator color={colors.text} />
                  ) : (
                    <>
                      <Ionicons name="document-text" size={20} color={colors.text} />
                      <Text style={styles.createButtonText}>Create Agreement Link</Text>
                    </>
                  )}
                </TouchableOpacity>
              </ScrollView>
            )}
          </View>
        </View>
      </WebModal>
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
    backgroundColor: colors.bg,
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
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  addButton: {
    padding: 4,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  accessDenied: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  accessDeniedText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  accessDeniedSubtext: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: 'center',
  },
  statsRow: {
    flexDirection: 'row',
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginRight: 8,
    alignItems: 'center',
  },
  statNumber: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
  },
  statLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 12,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 16,
    color: colors.text,
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  agreementCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  agreementHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  agreementType: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  agreementPartner: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  agreementTier: {
    fontSize: 13,
    color: '#007AFF',
    marginTop: 12,
  },
  agreementCustomCommission: {
    fontSize: 13,
    color: '#C9A962',
    marginTop: 6,
    fontStyle: 'italic',
  },
  agreementFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
  },
  agreementDate: {
    fontSize: 12,
    color: '#6E6E73',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
  },
  modalScroll: {
    padding: 20,
    maxHeight: 500,
  },
  formLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    marginTop: 16,
  },
  templateOptions: {
    flexDirection: 'row',
    gap: 12,
  },
  templateOption: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  templateOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF20',
  },
  templateOptionText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: 'center',
  },
  templateOptionTextSelected: {
    color: '#007AFF',
    fontWeight: '600',
  },
  tierScroll: {
    marginBottom: 8,
  },
  tierOption: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginRight: 12,
    minWidth: 120,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  tierOptionSelected: {
    borderColor: '#34C759',
    backgroundColor: '#34C75920',
  },
  tierName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  tierNameSelected: {
    color: '#34C759',
  },
  tierPercentage: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textSecondary,
    marginTop: 4,
  },
  tierPercentageSelected: {
    color: '#34C759',
  },
  tierDesc: {
    fontSize: 11,
    color: '#6E6E73',
    marginTop: 4,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: colors.text,
    marginBottom: 12,
  },
  paymentToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.textSecondary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  checkboxChecked: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  paymentToggleText: {
    fontSize: 16,
    color: colors.text,
  },
  paymentAmountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
  },
  currencySymbol: {
    fontSize: 20,
    color: colors.textSecondary,
    marginRight: 8,
  },
  paymentInput: {
    flex: 1,
    marginBottom: 0,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    marginTop: 24,
    marginBottom: 20,
    gap: 8,
  },
  createButtonDisabled: {
    backgroundColor: '#3C3C3E',
  },
  createButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  successContent: {
    alignItems: 'center',
    padding: 24,
  },
  successTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  successSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
  },
  linkBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 16,
    marginTop: 20,
    width: '100%',
  },
  linkText: {
    flex: 1,
    fontSize: 14,
    color: '#34C759',
    marginRight: 12,
  },
  doneButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    width: '100%',
    alignItems: 'center',
    marginTop: 24,
  },
  doneButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
});
