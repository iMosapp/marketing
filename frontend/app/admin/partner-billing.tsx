import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
  ActivityIndicator, RefreshControl, Modal, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';

const BILLING_MODELS = [
  { value: 'per_org', label: 'Per Organization' },
  { value: 'per_store', label: 'Per Store/Account' },
  { value: 'per_seat', label: 'Per Seat (User)' },
  { value: 'custom', label: 'Custom' },
];

const STATUS_COLORS = {
  draft: '#8E8E93',
  sent: '#007AFF',
  paid: '#34C759',
  overdue: '#FF3B30',
  cancelled: '#8E8E93',
};

type TabKey = 'overview' | 'invoices' | 'waivers' | 'rates';

export default function PartnerBillingScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const { id: partnerId, name: partnerName } = useLocalSearchParams<{ id: string; name: string }>();
  const isSuperAdmin = user?.role === 'super_admin';

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  // Platform billing config
  const [platformBilling, setPlatformBilling] = useState<any>({});
  const [editingPlatform, setEditingPlatform] = useState(false);
  const [platformForm, setPlatformForm] = useState({ model: 'per_store', rate: '', notes: '', includes_carrier: false, carrier_addon_rate: '' });
  const [savingPlatform, setSavingPlatform] = useState(false);

  // Client billing records
  const [clientRecords, setClientRecords] = useState<any[]>([]);
  const [showAddRecord, setShowAddRecord] = useState(false);
  const [recordForm, setRecordForm] = useState({ client_name: '', client_type: 'store', billing_model: 'per_store', rate: '', billing_contact: '', notes: '' });
  const [savingRecord, setSavingRecord] = useState(false);

  // Summary
  const [summary, setSummary] = useState<any>(null);

  // Invoices
  const [invoices, setInvoices] = useState<any[]>([]);
  const [generatingInvoice, setGeneratingInvoice] = useState(false);
  const [invoicePeriod, setInvoicePeriod] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });

  // Waivers
  const [waivers, setWaivers] = useState<any[]>([]);
  const [showAddWaiver, setShowAddWaiver] = useState(false);
  const [waiverForm, setWaiverForm] = useState({ store_id: '', store_name: '', waived_until: '', reason: '' });
  const [savingWaiver, setSavingWaiver] = useState(false);

  // Store rates
  const [storeRates, setStoreRates] = useState<any[]>([]);
  const [editingRate, setEditingRate] = useState<string | null>(null);
  const [rateForm, setRateForm] = useState({ billing_rate: '', billing_package: '' });

  // Partner stores for waiver picker
  const [partnerStores, setPartnerStores] = useState<any[]>([]);

  const loadData = useCallback(async () => {
    if (!partnerId) return;
    try {
      const promises: Promise<any>[] = [
        isSuperAdmin ? api.get(`/admin/partner-billing/platform/${partnerId}`) : Promise.resolve({ data: {} }),
        api.get('/admin/partner-billing/client-records'),
        api.get(`/admin/partner-invoices/list/${partnerId}`),
        api.get(`/admin/partner-invoices/waivers/${partnerId}`),
        api.get(`/admin/partner-invoices/store-rates/${partnerId}`),
      ];
      const [billingRes, recordsRes, invoicesRes, waiversRes, ratesRes] = await Promise.all(promises);

      setPlatformBilling(billingRes.data || {});
      setClientRecords((recordsRes.data || []).filter((r: any) => r.partner_id === partnerId));
      setInvoices(invoicesRes.data || []);
      setWaivers(waiversRes.data || []);
      setStoreRates(ratesRes.data || []);
      setPartnerStores(ratesRes.data || []);

      if (isSuperAdmin) {
        const summaryRes = await api.get('/admin/partner-billing/platform-summary');
        const s = (summaryRes.data || []).find((p: any) => p._id === partnerId);
        setSummary(s || null);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [partnerId, isSuperAdmin]);

  useEffect(() => { loadData(); }, [loadData]);
  const onRefresh = async () => { setRefreshing(true); await loadData(); setRefreshing(false); };

  // Platform billing handlers
  const handleSavePlatformBilling = async () => {
    setSavingPlatform(true);
    try {
      await api.put(`/admin/partner-billing/platform/${partnerId}`, {
        model: platformForm.model,
        rate: platformForm.rate ? parseFloat(platformForm.rate) : null,
        notes: platformForm.notes,
        includes_carrier: platformForm.includes_carrier,
        carrier_addon_rate: platformForm.carrier_addon_rate ? parseFloat(platformForm.carrier_addon_rate) : null,
      });
      showSimpleAlert('Saved', 'Platform billing updated');
      setEditingPlatform(false);
      loadData();
    } catch (e) { showSimpleAlert('Error', 'Failed to save'); }
    setSavingPlatform(false);
  };

  // Client record handlers
  const handleAddClientRecord = async () => {
    if (!recordForm.client_name) { showSimpleAlert('Error', 'Client name is required'); return; }
    setSavingRecord(true);
    try {
      await api.post('/admin/partner-billing/client-records', {
        partner_id: partnerId,
        ...recordForm,
        rate: recordForm.rate ? parseFloat(recordForm.rate) : null,
      });
      showSimpleAlert('Added', 'Billing record created');
      setShowAddRecord(false);
      setRecordForm({ client_name: '', client_type: 'store', billing_model: 'per_store', rate: '', billing_contact: '', notes: '' });
      loadData();
    } catch (e) { showSimpleAlert('Error', 'Failed to create record'); }
    setSavingRecord(false);
  };

  const handleDeleteRecord = async (id: string) => {
    try {
      await api.delete(`/admin/partner-billing/client-records/${id}`);
      loadData();
    } catch (e) { showSimpleAlert('Error', 'Failed to delete'); }
  };

  // Invoice handlers
  const handleGenerateInvoice = async () => {
    setGeneratingInvoice(true);
    try {
      const res = await api.post(`/admin/partner-invoices/generate/${partnerId}`, { period: invoicePeriod });
      showSimpleAlert('Invoice Generated', `Invoice ${res.data.invoice_number} created for $${res.data.total.toFixed(2)}`);
      loadData();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to generate invoice';
      showSimpleAlert('Error', msg);
    }
    setGeneratingInvoice(false);
  };

  const handleInvoiceStatus = async (invoiceId: string, status: string) => {
    try {
      await api.patch(`/admin/partner-invoices/status/${invoiceId}`, { status });
      showSimpleAlert('Updated', `Invoice marked as ${status}`);
      loadData();
    } catch (e) { showSimpleAlert('Error', 'Failed to update status'); }
  };

  const handleSendInvoice = async (invoiceId: string) => {
    try {
      const res = await api.post(`/admin/partner-invoices/send/${invoiceId}`);
      showSimpleAlert('Sent', `Invoice emailed to ${res.data.sent_to}`);
      loadData();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to send';
      showSimpleAlert('Error', msg);
    }
  };

  const handleDownloadPdf = async (invoiceId: string) => {
    const baseUrl = api.defaults.baseURL || process.env.REACT_APP_BACKEND_URL || '';
    const url = `${baseUrl}/admin/partner-invoices/pdf/${invoiceId}`;
    if (Platform.OS === 'web') {
      window.open(url, '_blank');
    } else {
      Linking.openURL(url);
    }
  };

  // Waiver handlers
  const handleAddWaiver = async () => {
    if (!waiverForm.store_id) { showSimpleAlert('Error', 'Select a store'); return; }
    setSavingWaiver(true);
    try {
      await api.post('/admin/partner-invoices/waivers', {
        partner_id: partnerId,
        store_id: waiverForm.store_id,
        store_name: waiverForm.store_name,
        waived_until: waiverForm.waived_until || null,
        reason: waiverForm.reason,
      });
      showSimpleAlert('Waiver Created', 'Store will show $0 on future invoices');
      setShowAddWaiver(false);
      setWaiverForm({ store_id: '', store_name: '', waived_until: '', reason: '' });
      loadData();
    } catch (e) { showSimpleAlert('Error', 'Failed to create waiver'); }
    setSavingWaiver(false);
  };

  const handleDeleteWaiver = async (waiverId: string) => {
    showConfirm('Remove Waiver', 'This store will be charged on the next invoice.', async () => {
      try {
        await api.delete(`/admin/partner-invoices/waivers/${waiverId}`);
        loadData();
      } catch (e) { showSimpleAlert('Error', 'Failed to remove waiver'); }
    });
  };

  // Store rate handler
  const handleSaveRate = async (storeId: string) => {
    try {
      await api.put(`/admin/partner-invoices/store-rate/${storeId}`, {
        billing_rate: rateForm.billing_rate ? parseFloat(rateForm.billing_rate) : null,
        billing_package: rateForm.billing_package,
      });
      showSimpleAlert('Saved', 'Store rate updated');
      setEditingRate(null);
      loadData();
    } catch (e) { showSimpleAlert('Error', 'Failed to update rate'); }
  };

  const modelLabel = (m: string) => BILLING_MODELS.find(b => b.value === m)?.label || m;
  const s = getS(colors);

  const TABS: { key: TabKey; label: string; icon: string }[] = [
    { key: 'overview', label: 'Overview', icon: 'analytics-outline' },
    { key: 'invoices', label: 'Invoices', icon: 'receipt-outline' },
    { key: 'waivers', label: 'Waivers', icon: 'shield-outline' },
    { key: 'rates', label: 'Rates', icon: 'pricetags-outline' },
  ];

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.headerBtn} data-testid="back-button">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={s.headerTitle}>{partnerName || 'Partner'}</Text>
          <Text style={s.headerSub}>Billing Management</Text>
        </View>
        <TouchableOpacity onPress={() => setShowAddRecord(true)} style={s.headerBtn} data-testid="add-record-btn">
          <Ionicons name="add-circle" size={24} color="#34C759" />
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={s.tabBar}>
        {TABS.map(tab => (
          <TouchableOpacity
            key={tab.key}
            style={[s.tab, activeTab === tab.key && s.tabActive]}
            onPress={() => setActiveTab(tab.key)}
            data-testid={`tab-${tab.key}`}
          >
            <Ionicons name={tab.icon as any} size={16} color={activeTab === tab.key ? '#C9A962' : colors.textSecondary} />
            <Text style={[s.tabText, activeTab === tab.key && s.tabTextActive]}>{tab.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        contentContainerStyle={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
      >
        {loading ? (
          <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 40 }} />
        ) : (
          <>
            {/* ===== OVERVIEW TAB ===== */}
            {activeTab === 'overview' && (
              <>
                {summary && (
                  <View style={s.summaryCard} data-testid="billing-summary">
                    <Text style={s.sectionTitle}>Partner Summary</Text>
                    <View style={s.summaryGrid}>
                      <View style={s.summaryItem}>
                        <Text style={s.summaryNum}>{summary.org_count}</Text>
                        <Text style={s.summaryLabel}>Orgs</Text>
                      </View>
                      <View style={s.summaryItem}>
                        <Text style={s.summaryNum}>{summary.store_count}</Text>
                        <Text style={s.summaryLabel}>Stores</Text>
                      </View>
                      <View style={s.summaryItem}>
                        <Text style={s.summaryNum}>{waivers.filter(w => !w.expired).length}</Text>
                        <Text style={s.summaryLabel}>Waived</Text>
                      </View>
                      {summary.estimated_monthly != null && (
                        <View style={s.summaryItem}>
                          <Text style={[s.summaryNum, { color: '#34C759' }]}>${summary.estimated_monthly}</Text>
                          <Text style={s.summaryLabel}>Est/mo</Text>
                        </View>
                      )}
                    </View>
                  </View>
                )}

                {/* Platform Billing Config */}
                {isSuperAdmin && (
                  <View style={s.section} data-testid="platform-billing-section">
                    <View style={s.sectionHeader}>
                      <Ionicons name="cash-outline" size={18} color="#C9A962" />
                      <Text style={s.sectionTitle}>Your Billing to Partner</Text>
                      <TouchableOpacity onPress={() => {
                        setPlatformForm({
                          model: platformBilling.model || 'per_store',
                          rate: platformBilling.rate?.toString() || '',
                          notes: platformBilling.notes || '',
                          includes_carrier: platformBilling.includes_carrier || false,
                          carrier_addon_rate: platformBilling.carrier_addon_rate?.toString() || '',
                        });
                        setEditingPlatform(!editingPlatform);
                      }} data-testid="edit-platform-billing-btn">
                        <Ionicons name={editingPlatform ? 'close' : 'create-outline'} size={20} color="#007AFF" />
                      </TouchableOpacity>
                    </View>

                    {editingPlatform ? (
                      <View style={s.formBlock}>
                        <Text style={s.inputLabel}>Billing Model</Text>
                        <View style={s.modelPicker}>
                          {BILLING_MODELS.map(m => (
                            <TouchableOpacity key={m.value} style={[s.modelOption, platformForm.model === m.value && s.modelOptionActive]}
                              onPress={() => setPlatformForm({ ...platformForm, model: m.value })}>
                              <Text style={[s.modelText, platformForm.model === m.value && s.modelTextActive]}>{m.label}</Text>
                            </TouchableOpacity>
                          ))}
                        </View>
                        <Text style={s.inputLabel}>Rate ($)</Text>
                        <TextInput style={s.input} placeholder="e.g., 150" placeholderTextColor={colors.textSecondary}
                          value={platformForm.rate} onChangeText={t => setPlatformForm({ ...platformForm, rate: t })} keyboardType="numeric" data-testid="platform-rate-input" />
                        <TouchableOpacity style={s.toggleRow} onPress={() => setPlatformForm({ ...platformForm, includes_carrier: !platformForm.includes_carrier })}>
                          <Ionicons name={platformForm.includes_carrier ? 'checkbox' : 'square-outline'} size={22} color="#C9A962" />
                          <Text style={s.toggleLabel}>Includes carrier services</Text>
                        </TouchableOpacity>
                        {platformForm.includes_carrier && (
                          <>
                            <Text style={s.inputLabel}>Carrier Add-on Rate ($)</Text>
                            <TextInput style={s.input} placeholder="Additional per-unit carrier cost" placeholderTextColor={colors.textSecondary}
                              value={platformForm.carrier_addon_rate} onChangeText={t => setPlatformForm({ ...platformForm, carrier_addon_rate: t })} keyboardType="numeric" />
                          </>
                        )}
                        <Text style={s.inputLabel}>Notes</Text>
                        <TextInput style={[s.input, { minHeight: 60 }]} placeholder="Billing terms..." placeholderTextColor={colors.textSecondary}
                          value={platformForm.notes} onChangeText={t => setPlatformForm({ ...platformForm, notes: t })} multiline data-testid="platform-notes-input" />
                        <TouchableOpacity style={s.saveBtn} onPress={handleSavePlatformBilling} disabled={savingPlatform} data-testid="save-platform-billing-btn">
                          {savingPlatform ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.saveBtnText}>Save Billing Config</Text>}
                        </TouchableOpacity>
                      </View>
                    ) : (
                      <View style={s.infoBlock}>
                        {platformBilling.model ? (
                          <>
                            <View style={s.infoRow}><Text style={s.infoLabel}>Model</Text><Text style={s.infoValue}>{modelLabel(platformBilling.model)}</Text></View>
                            <View style={s.infoRow}><Text style={s.infoLabel}>Rate</Text><Text style={s.infoValue}>{platformBilling.rate != null ? `$${platformBilling.rate}` : 'Not set'}</Text></View>
                            {platformBilling.includes_carrier && (
                              <View style={s.infoRow}><Text style={s.infoLabel}>Carrier</Text><Text style={[s.infoValue, { color: '#34C759' }]}>Included{platformBilling.carrier_addon_rate ? ` (+$${platformBilling.carrier_addon_rate})` : ''}</Text></View>
                            )}
                            {platformBilling.notes ? <Text style={s.notesText}>{platformBilling.notes}</Text> : null}
                          </>
                        ) : (
                          <Text style={s.emptyText}>No billing configured yet. Tap edit to set up.</Text>
                        )}
                      </View>
                    )}
                  </View>
                )}

                {/* Client Records */}
                <View style={s.section} data-testid="client-billing-section">
                  <View style={s.sectionHeader}>
                    <Ionicons name="receipt-outline" size={18} color="#007AFF" />
                    <Text style={s.sectionTitle}>{isSuperAdmin ? "Partner's Client Billing" : 'Client Billing Records'}</Text>
                  </View>
                  {clientRecords.length === 0 ? (
                    <View style={s.infoBlock}>
                      <Text style={s.emptyText}>No billing records yet</Text>
                    </View>
                  ) : (
                    clientRecords.map(r => (
                      <View key={r._id} style={s.recordCard} data-testid={`record-${r._id}`}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                          <View style={{ flex: 1 }}>
                            <Text style={s.recordName}>{r.client_name}</Text>
                            <Text style={s.recordMeta}>{r.client_type === 'org' ? 'Organization' : 'Store'} | {modelLabel(r.billing_model)} | {r.rate != null ? `$${r.rate}` : 'TBD'}</Text>
                          </View>
                          <TouchableOpacity onPress={() => handleDeleteRecord(r._id)} data-testid={`delete-record-${r._id}`}>
                            <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                          </TouchableOpacity>
                        </View>
                      </View>
                    ))
                  )}
                </View>
              </>
            )}

            {/* ===== INVOICES TAB ===== */}
            {activeTab === 'invoices' && (
              <>
                {/* Generate Invoice */}
                <View style={s.section} data-testid="generate-invoice-section">
                  <View style={s.sectionHeader}>
                    <Ionicons name="add-circle-outline" size={18} color="#34C759" />
                    <Text style={s.sectionTitle}>Generate Invoice</Text>
                  </View>
                  <View style={s.formBlock}>
                    <Text style={s.inputLabel}>Billing Period (YYYY-MM)</Text>
                    <TextInput style={s.input} value={invoicePeriod}
                      onChangeText={setInvoicePeriod} placeholder="2026-03" placeholderTextColor={colors.textSecondary} data-testid="invoice-period-input" />
                    <TouchableOpacity style={[s.saveBtn, { marginTop: 12 }]} onPress={handleGenerateInvoice} disabled={generatingInvoice} data-testid="generate-invoice-btn">
                      {generatingInvoice ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.saveBtnText}>Generate Invoice</Text>}
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Invoice History */}
                <View style={s.section} data-testid="invoice-history-section">
                  <View style={s.sectionHeader}>
                    <Ionicons name="document-text-outline" size={18} color="#C9A962" />
                    <Text style={s.sectionTitle}>Invoice History</Text>
                  </View>
                  {invoices.length === 0 ? (
                    <View style={s.infoBlock}><Text style={s.emptyText}>No invoices generated yet</Text></View>
                  ) : (
                    invoices.map(inv => (
                      <View key={inv._id} style={s.invoiceCard} data-testid={`invoice-${inv._id}`}>
                        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                          <View style={{ flex: 1 }}>
                            <Text style={s.invoiceNumber}>{inv.invoice_number}</Text>
                            <Text style={s.invoiceMeta}>Period: {inv.period} | {inv.line_item_count} account{inv.line_item_count !== 1 ? 's' : ''}</Text>
                          </View>
                          <View style={{ alignItems: 'flex-end' }}>
                            <Text style={s.invoiceTotal}>${inv.total?.toFixed(2)}</Text>
                            <View style={[s.statusBadge, { backgroundColor: (STATUS_COLORS[inv.status] || '#8E8E93') + '20' }]}>
                              <Text style={[s.statusText, { color: STATUS_COLORS[inv.status] || '#8E8E93' }]}>{inv.status?.toUpperCase()}</Text>
                            </View>
                          </View>
                        </View>
                        {/* Action buttons */}
                        <View style={s.invoiceActions}>
                          <TouchableOpacity style={s.actionBtn} onPress={() => handleDownloadPdf(inv._id)} data-testid={`pdf-${inv._id}`}>
                            <Ionicons name="download-outline" size={16} color="#007AFF" />
                            <Text style={[s.actionText, { color: '#007AFF' }]}>PDF</Text>
                          </TouchableOpacity>
                          {inv.status === 'draft' && (
                            <TouchableOpacity style={s.actionBtn} onPress={() => handleSendInvoice(inv._id)} data-testid={`send-${inv._id}`}>
                              <Ionicons name="send-outline" size={16} color="#C9A962" />
                              <Text style={[s.actionText, { color: '#C9A962' }]}>Send</Text>
                            </TouchableOpacity>
                          )}
                          {(inv.status === 'sent' || inv.status === 'overdue') && (
                            <TouchableOpacity style={s.actionBtn} onPress={() => handleInvoiceStatus(inv._id, 'paid')} data-testid={`mark-paid-${inv._id}`}>
                              <Ionicons name="checkmark-circle-outline" size={16} color="#34C759" />
                              <Text style={[s.actionText, { color: '#34C759' }]}>Paid</Text>
                            </TouchableOpacity>
                          )}
                          {inv.status === 'sent' && (
                            <TouchableOpacity style={s.actionBtn} onPress={() => handleInvoiceStatus(inv._id, 'overdue')} data-testid={`mark-overdue-${inv._id}`}>
                              <Ionicons name="alert-circle-outline" size={16} color="#FF3B30" />
                              <Text style={[s.actionText, { color: '#FF3B30' }]}>Overdue</Text>
                            </TouchableOpacity>
                          )}
                          {inv.status !== 'cancelled' && inv.status !== 'paid' && (
                            <TouchableOpacity style={s.actionBtn} onPress={() => handleInvoiceStatus(inv._id, 'cancelled')} data-testid={`cancel-${inv._id}`}>
                              <Ionicons name="close-circle-outline" size={16} color="#8E8E93" />
                              <Text style={[s.actionText, { color: '#8E8E93' }]}>Cancel</Text>
                            </TouchableOpacity>
                          )}
                        </View>
                      </View>
                    ))
                  )}
                </View>
              </>
            )}

            {/* ===== WAIVERS TAB ===== */}
            {activeTab === 'waivers' && (
              <>
                <View style={s.section} data-testid="waivers-section">
                  <View style={s.sectionHeader}>
                    <Ionicons name="shield-outline" size={18} color="#AF52DE" />
                    <Text style={s.sectionTitle}>Active Waivers</Text>
                    <TouchableOpacity onPress={() => setShowAddWaiver(true)} data-testid="add-waiver-btn">
                      <Ionicons name="add-circle" size={22} color="#34C759" />
                    </TouchableOpacity>
                  </View>
                  {waivers.length === 0 ? (
                    <View style={s.infoBlock}><Text style={s.emptyText}>No waivers — all stores will be billed at rate</Text></View>
                  ) : (
                    waivers.map(w => (
                      <View key={w._id} style={[s.recordCard, w.expired && { opacity: 0.5 }]} data-testid={`waiver-${w._id}`}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                          <View style={{ flex: 1 }}>
                            <Text style={s.recordName}>{w.store_name || 'Unknown Store'}</Text>
                            <Text style={s.recordMeta}>
                              {w.waived_until ? `Until ${w.waived_until.slice(0, 10)}` : 'Indefinite'}
                              {w.expired ? ' (EXPIRED)' : ''}
                            </Text>
                            {w.reason ? <Text style={s.recordNotes}>{w.reason}</Text> : null}
                          </View>
                          <TouchableOpacity onPress={() => handleDeleteWaiver(w._id)} data-testid={`delete-waiver-${w._id}`}>
                            <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                          </TouchableOpacity>
                        </View>
                      </View>
                    ))
                  )}
                </View>
              </>
            )}

            {/* ===== RATES TAB ===== */}
            {activeTab === 'rates' && (
              <>
                <View style={s.section} data-testid="store-rates-section">
                  <View style={s.sectionHeader}>
                    <Ionicons name="pricetags-outline" size={18} color="#FF9500" />
                    <Text style={s.sectionTitle}>Per-Store Rates</Text>
                  </View>
                  <View style={s.infoBlock}>
                    <Text style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 8 }}>
                      Default rate: {platformBilling.rate != null ? `$${platformBilling.rate}/store` : 'Not set'}. Override individual stores below.
                    </Text>
                  </View>
                  {storeRates.length === 0 ? (
                    <View style={s.infoBlock}><Text style={s.emptyText}>No stores found for this partner</Text></View>
                  ) : (
                    storeRates.map(store => (
                      <View key={store._id} style={s.recordCard} data-testid={`store-rate-${store._id}`}>
                        {editingRate === store._id ? (
                          <View>
                            <Text style={s.recordName}>{store.name}</Text>
                            <Text style={[s.inputLabel, { marginTop: 8 }]}>Rate ($)</Text>
                            <TextInput style={s.input} value={rateForm.billing_rate}
                              onChangeText={t => setRateForm({ ...rateForm, billing_rate: t })}
                              placeholder={`Default: $${platformBilling.rate || '0'}`} placeholderTextColor={colors.textSecondary} keyboardType="numeric" />
                            <Text style={s.inputLabel}>Package Name</Text>
                            <TextInput style={s.input} value={rateForm.billing_package}
                              onChangeText={t => setRateForm({ ...rateForm, billing_package: t })}
                              placeholder="e.g., Gold, Silver, Enterprise" placeholderTextColor={colors.textSecondary} />
                            <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                              <TouchableOpacity style={[s.saveBtn, { flex: 1 }]} onPress={() => handleSaveRate(store._id)}>
                                <Text style={s.saveBtnText}>Save</Text>
                              </TouchableOpacity>
                              <TouchableOpacity style={[s.saveBtn, { flex: 1, backgroundColor: colors.surface }]} onPress={() => setEditingRate(null)}>
                                <Text style={[s.saveBtnText, { color: colors.text }]}>Cancel</Text>
                              </TouchableOpacity>
                            </View>
                          </View>
                        ) : (
                          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                            <View style={{ flex: 1 }}>
                              <Text style={s.recordName}>{store.name}</Text>
                              <Text style={s.recordMeta}>
                                Rate: {store.billing_rate != null ? `$${store.billing_rate}` : `$${platformBilling.rate || 0} (default)`}
                                {store.billing_package ? ` | ${store.billing_package}` : ''}
                              </Text>
                            </View>
                            <TouchableOpacity onPress={() => {
                              setEditingRate(store._id);
                              setRateForm({
                                billing_rate: store.billing_rate?.toString() || '',
                                billing_package: store.billing_package || '',
                              });
                            }} data-testid={`edit-rate-${store._id}`}>
                              <Ionicons name="create-outline" size={20} color="#007AFF" />
                            </TouchableOpacity>
                          </View>
                        )}
                      </View>
                    ))
                  )}
                </View>
              </>
            )}
          </>
        )}
      </ScrollView>

      {/* Add Client Record Modal */}
      <Modal visible={showAddRecord} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowAddRecord(false)} data-testid="modal-cancel">
              <Text style={{ fontSize: 18, color: '#007AFF' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>New Billing Record</Text>
            <TouchableOpacity onPress={handleAddClientRecord} disabled={savingRecord} data-testid="modal-save">
              {savingRecord ? <ActivityIndicator size="small" color="#C9A962" /> : <Text style={{ fontSize: 18, fontWeight: '600', color: '#C9A962' }}>Save</Text>}
            </TouchableOpacity>
          </View>
          <ScrollView style={{ padding: 16 }}>
            <Text style={s.inputLabel}>Client Name *</Text>
            <TextInput style={s.input} placeholder="e.g., Ken Garff Honda" placeholderTextColor={colors.textSecondary}
              value={recordForm.client_name} onChangeText={t => setRecordForm({ ...recordForm, client_name: t })} data-testid="record-name-input" />
            <Text style={s.inputLabel}>Client Type</Text>
            <View style={s.modelPicker}>
              {[{ value: 'org', label: 'Organization' }, { value: 'store', label: 'Store' }].map(t => (
                <TouchableOpacity key={t.value} style={[s.modelOption, recordForm.client_type === t.value && s.modelOptionActive]}
                  onPress={() => setRecordForm({ ...recordForm, client_type: t.value })}>
                  <Text style={[s.modelText, recordForm.client_type === t.value && s.modelTextActive]}>{t.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.inputLabel}>Billing Model</Text>
            <View style={s.modelPicker}>
              {BILLING_MODELS.map(m => (
                <TouchableOpacity key={m.value} style={[s.modelOption, recordForm.billing_model === m.value && s.modelOptionActive]}
                  onPress={() => setRecordForm({ ...recordForm, billing_model: m.value })}>
                  <Text style={[s.modelText, recordForm.billing_model === m.value && s.modelTextActive]}>{m.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.inputLabel}>Rate ($)</Text>
            <TextInput style={s.input} placeholder="Amount" placeholderTextColor={colors.textSecondary}
              value={recordForm.rate} onChangeText={t => setRecordForm({ ...recordForm, rate: t })} keyboardType="numeric" data-testid="record-rate-input" />
            <Text style={s.inputLabel}>Billing Contact</Text>
            <TextInput style={s.input} placeholder="Name or email for billing" placeholderTextColor={colors.textSecondary}
              value={recordForm.billing_contact} onChangeText={t => setRecordForm({ ...recordForm, billing_contact: t })} data-testid="record-contact-input" />
            <Text style={s.inputLabel}>Notes</Text>
            <TextInput style={[s.input, { minHeight: 60 }]} placeholder="Additional billing details..." placeholderTextColor={colors.textSecondary}
              value={recordForm.notes} onChangeText={t => setRecordForm({ ...recordForm, notes: t })} multiline data-testid="record-notes-input" />
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Add Waiver Modal */}
      <Modal visible={showAddWaiver} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowAddWaiver(false)} data-testid="waiver-modal-cancel">
              <Text style={{ fontSize: 18, color: '#007AFF' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>Add Waiver</Text>
            <TouchableOpacity onPress={handleAddWaiver} disabled={savingWaiver} data-testid="waiver-modal-save">
              {savingWaiver ? <ActivityIndicator size="small" color="#C9A962" /> : <Text style={{ fontSize: 18, fontWeight: '600', color: '#C9A962' }}>Save</Text>}
            </TouchableOpacity>
          </View>
          <ScrollView style={{ padding: 16 }}>
            <Text style={s.inputLabel}>Select Store *</Text>
            <View style={{ gap: 6 }}>
              {partnerStores.map(store => (
                <TouchableOpacity
                  key={store._id}
                  style={[s.modelOption, { paddingVertical: 12 }, waiverForm.store_id === store._id && s.modelOptionActive]}
                  onPress={() => setWaiverForm({ ...waiverForm, store_id: store._id, store_name: store.name })}
                  data-testid={`waiver-store-${store._id}`}
                >
                  <Text style={[s.modelText, waiverForm.store_id === store._id && s.modelTextActive]}>{store.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.inputLabel}>Waived Until (optional — leave blank for indefinite)</Text>
            <TextInput style={s.input} value={waiverForm.waived_until}
              onChangeText={t => setWaiverForm({ ...waiverForm, waived_until: t })}
              placeholder="YYYY-MM-DD (e.g., 2026-06-01)" placeholderTextColor={colors.textSecondary} data-testid="waiver-until-input" />
            <Text style={s.inputLabel}>Reason</Text>
            <TextInput style={[s.input, { minHeight: 60 }]} value={waiverForm.reason}
              onChangeText={t => setWaiverForm({ ...waiverForm, reason: t })}
              placeholder="e.g., Early adopter, promotional period" placeholderTextColor={colors.textSecondary} multiline data-testid="waiver-reason-input" />
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  headerBtn: { padding: 4, minWidth: 44 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  headerSub: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },

  tabBar: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: colors.surface, paddingHorizontal: 8 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 10 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#C9A962' },
  tabText: { fontSize: 13, color: colors.textSecondary, fontWeight: '500' },
  tabTextActive: { color: '#C9A962', fontWeight: '600' },

  scroll: { padding: 16 },

  summaryCard: { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.surface },
  summaryGrid: { flexDirection: 'row', gap: 16, marginTop: 12 },
  summaryItem: { alignItems: 'center', flex: 1 },
  summaryNum: { fontSize: 24, fontWeight: '700', color: colors.text },
  summaryLabel: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },

  section: { backgroundColor: colors.card, borderRadius: 14, marginBottom: 16, borderWidth: 1, borderColor: colors.surface, overflow: 'hidden' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 14, borderBottomWidth: 1, borderBottomColor: colors.surface },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: colors.text, flex: 1 },

  formBlock: { padding: 14 },
  infoBlock: { padding: 14 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  infoLabel: { fontSize: 16, color: colors.textSecondary },
  infoValue: { fontSize: 16, fontWeight: '600', color: colors.text },
  notesText: { fontSize: 15, color: colors.textSecondary, fontStyle: 'italic', marginTop: 8 },
  emptyText: { fontSize: 16, color: colors.textSecondary, textAlign: 'center' },

  inputLabel: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 12 },
  input: { backgroundColor: colors.surface, borderRadius: 10, padding: 12, fontSize: 17, color: colors.text, borderWidth: 1, borderColor: colors.borderLight || colors.surface },

  modelPicker: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  modelOption: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.surface },
  modelOptionActive: { backgroundColor: '#C9A96220', borderColor: '#C9A962' },
  modelText: { fontSize: 15, color: colors.textSecondary },
  modelTextActive: { color: '#C9A962', fontWeight: '600' },

  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12 },
  toggleLabel: { fontSize: 16, color: colors.text },

  saveBtn: { backgroundColor: '#C9A962', borderRadius: 10, padding: 12, alignItems: 'center', marginTop: 8 },
  saveBtnText: { color: '#000', fontWeight: '600', fontSize: 17 },

  recordCard: { padding: 14, borderBottomWidth: 1, borderBottomColor: colors.surface },
  recordName: { fontSize: 17, fontWeight: '600', color: colors.text },
  recordMeta: { fontSize: 14, color: colors.textSecondary, marginTop: 3 },
  recordNotes: { fontSize: 14, color: colors.textSecondary, fontStyle: 'italic', marginTop: 2 },

  invoiceCard: { padding: 14, borderBottomWidth: 1, borderBottomColor: colors.surface },
  invoiceNumber: { fontSize: 16, fontWeight: '700', color: colors.text },
  invoiceMeta: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  invoiceTotal: { fontSize: 18, fontWeight: '700', color: '#34C759' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, marginTop: 4 },
  statusText: { fontSize: 11, fontWeight: '700' },
  invoiceActions: { flexDirection: 'row', gap: 16, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.surface },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  actionText: { fontSize: 14, fontWeight: '600' },

  modalContainer: { flex: 1, backgroundColor: colors.bg },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.surface },
  modalTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
});
