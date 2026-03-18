import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
  ActivityIndicator, RefreshControl, Modal, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';

const BILLING_MODELS = [
  { value: 'per_org', label: 'Per Organization' },
  { value: 'per_store', label: 'Per Store/Account' },
  { value: 'per_seat', label: 'Per Seat (User)' },
  { value: 'custom', label: 'Custom' },
];

export default function PartnerBillingScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const { id: partnerId, name: partnerName } = useLocalSearchParams<{ id: string; name: string }>();
  const isSuperAdmin = user?.role === 'super_admin';

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Layer 1: Platform billing config
  const [platformBilling, setPlatformBilling] = useState<any>({});
  const [editingPlatform, setEditingPlatform] = useState(false);
  const [platformForm, setPlatformForm] = useState({ model: 'per_store', rate: '', notes: '', includes_carrier: false, carrier_addon_rate: '' });
  const [savingPlatform, setSavingPlatform] = useState(false);

  // Layer 2: Client billing records
  const [clientRecords, setClientRecords] = useState<any[]>([]);
  const [showAddRecord, setShowAddRecord] = useState(false);
  const [recordForm, setRecordForm] = useState({ client_name: '', client_type: 'store', billing_model: 'per_store', rate: '', billing_contact: '', notes: '' });
  const [savingRecord, setSavingRecord] = useState(false);

  // Summary
  const [summary, setSummary] = useState<any>(null);

  const loadData = useCallback(async () => {
    if (!partnerId) return;
    try {
      const [billingRes, recordsRes] = await Promise.all([
        isSuperAdmin ? api.get(`/admin/partner-billing/platform/${partnerId}`) : Promise.resolve({ data: {} }),
        api.get('/admin/partner-billing/client-records'),
      ]);
      setPlatformBilling(billingRes.data || {});
      setClientRecords((recordsRes.data || []).filter((r: any) => r.partner_id === partnerId));

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

  const handleAddClientRecord = async () => {
    if (!recordForm.client_name) { showSimpleAlert('Error', 'Client name is required'); return; }
    setSavingRecord(true);
    try {
      await api.post('/admin/partner-billing/client-records', {
        partner_id: partnerId,
        client_name: recordForm.client_name,
        client_type: recordForm.client_type,
        billing_model: recordForm.billing_model,
        rate: recordForm.rate ? parseFloat(recordForm.rate) : null,
        billing_contact: recordForm.billing_contact,
        notes: recordForm.notes,
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

  const modelLabel = (m: string) => BILLING_MODELS.find(b => b.value === m)?.label || m;

  const s = getS(colors);

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

      <ScrollView
        contentContainerStyle={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
      >
        {loading ? (
          <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 40 }} />
        ) : (
          <>
            {/* Summary Card */}
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
                    <Text style={s.summaryNum}>{summary.seat_count || '-'}</Text>
                    <Text style={s.summaryLabel}>Seats</Text>
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

            {/* Layer 1: Platform Billing (super_admin only) */}
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
                        <TouchableOpacity
                          key={m.value}
                          style={[s.modelOption, platformForm.model === m.value && s.modelOptionActive]}
                          onPress={() => setPlatformForm({ ...platformForm, model: m.value })}
                        >
                          <Text style={[s.modelText, platformForm.model === m.value && s.modelTextActive]}>{m.label}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    <Text style={s.inputLabel}>Rate ($)</Text>
                    <TextInput
                      style={s.input}
                      placeholder="e.g., 150"
                      placeholderTextColor={colors.textSecondary}
                      value={platformForm.rate}
                      onChangeText={t => setPlatformForm({ ...platformForm, rate: t })}
                      keyboardType="numeric"
                      data-testid="platform-rate-input"
                    />
                    <TouchableOpacity
                      style={s.toggleRow}
                      onPress={() => setPlatformForm({ ...platformForm, includes_carrier: !platformForm.includes_carrier })}
                    >
                      <Ionicons name={platformForm.includes_carrier ? 'checkbox' : 'square-outline'} size={22} color="#C9A962" />
                      <Text style={s.toggleLabel}>Includes carrier services (Twilio/Telnet)</Text>
                    </TouchableOpacity>
                    {platformForm.includes_carrier && (
                      <>
                        <Text style={s.inputLabel}>Carrier Add-on Rate ($)</Text>
                        <TextInput
                          style={s.input}
                          placeholder="Additional per-unit carrier cost"
                          placeholderTextColor={colors.textSecondary}
                          value={platformForm.carrier_addon_rate}
                          onChangeText={t => setPlatformForm({ ...platformForm, carrier_addon_rate: t })}
                          keyboardType="numeric"
                        />
                      </>
                    )}
                    <Text style={s.inputLabel}>Notes</Text>
                    <TextInput
                      style={[s.input, { minHeight: 60 }]}
                      placeholder="Billing terms, negotiated details..."
                      placeholderTextColor={colors.textSecondary}
                      value={platformForm.notes}
                      onChangeText={t => setPlatformForm({ ...platformForm, notes: t })}
                      multiline
                      data-testid="platform-notes-input"
                    />
                    {Platform.OS === 'web' ? (
                      <button
                        type="button"
                        onClick={() => handleSavePlatformBilling()}
                        disabled={savingPlatform}
                        style={{ backgroundColor: '#C9A962', borderRadius: 10, padding: 12, border: 'none', cursor: 'pointer', marginTop: 8, width: '100%' }}
                        data-testid="save-platform-billing-btn"
                      >
                        {savingPlatform ? <ActivityIndicator size="small" color="#000" /> : <Text style={{ color: '#000', fontWeight: '600', fontSize: 15, textAlign: 'center' }}>Save Billing Config</Text>}
                      </button>
                    ) : (
                      <TouchableOpacity style={s.saveBtn} onPress={handleSavePlatformBilling} disabled={savingPlatform}>
                        {savingPlatform ? <ActivityIndicator size="small" color="#000" /> : <Text style={s.saveBtnText}>Save Billing Config</Text>}
                      </TouchableOpacity>
                    )}
                  </View>
                ) : (
                  <View style={s.infoBlock}>
                    {platformBilling.model ? (
                      <>
                        <View style={s.infoRow}>
                          <Text style={s.infoLabel}>Model</Text>
                          <Text style={s.infoValue}>{modelLabel(platformBilling.model)}</Text>
                        </View>
                        <View style={s.infoRow}>
                          <Text style={s.infoLabel}>Rate</Text>
                          <Text style={s.infoValue}>{platformBilling.rate != null ? `$${platformBilling.rate}` : 'Not set'}</Text>
                        </View>
                        {platformBilling.includes_carrier && (
                          <View style={s.infoRow}>
                            <Text style={s.infoLabel}>Carrier</Text>
                            <Text style={[s.infoValue, { color: '#34C759' }]}>Included{platformBilling.carrier_addon_rate ? ` (+$${platformBilling.carrier_addon_rate})` : ''}</Text>
                          </View>
                        )}
                        {platformBilling.notes ? (
                          <Text style={s.notesText}>{platformBilling.notes}</Text>
                        ) : null}
                      </>
                    ) : (
                      <Text style={s.emptyText}>No billing configured yet. Tap edit to set up.</Text>
                    )}
                  </View>
                )}
              </View>
            )}

            {/* Layer 2: Client Billing Records */}
            <View style={s.section} data-testid="client-billing-section">
              <View style={s.sectionHeader}>
                <Ionicons name="receipt-outline" size={18} color="#007AFF" />
                <Text style={s.sectionTitle}>{isSuperAdmin ? "Partner's Client Billing" : 'Client Billing Records'}</Text>
              </View>

              {clientRecords.length === 0 ? (
                <View style={s.infoBlock}>
                  <Text style={s.emptyText}>No billing records yet</Text>
                  <Text style={[s.emptyText, { fontSize: 12, marginTop: 4 }]}>
                    Add billing when onboarding new orgs or stores
                  </Text>
                </View>
              ) : (
                clientRecords.map(r => (
                  <View key={r._id} style={s.recordCard} data-testid={`record-${r._id}`}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                      <View style={{ flex: 1 }}>
                        <Text style={s.recordName}>{r.client_name}</Text>
                        <Text style={s.recordMeta}>
                          {r.client_type === 'org' ? 'Organization' : 'Store'} | {modelLabel(r.billing_model)} | {r.rate != null ? `$${r.rate}` : 'TBD'}
                        </Text>
                        {r.billing_contact ? <Text style={s.recordContact}>{r.billing_contact}</Text> : null}
                        {r.notes ? <Text style={s.recordNotes}>{r.notes}</Text> : null}
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
      </ScrollView>

      {/* Add Client Record Modal */}
      <Modal visible={showAddRecord} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowAddRecord(false)} data-testid="modal-cancel">
              <Text style={{ fontSize: 17, color: '#007AFF' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>New Billing Record</Text>
            {Platform.OS === 'web' ? (
              <button
                type="button"
                onClick={() => handleAddClientRecord()}
                disabled={savingRecord}
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                data-testid="modal-save"
              >
                {savingRecord ? <ActivityIndicator size="small" color="#C9A962" /> : <Text style={{ fontSize: 17, fontWeight: '600', color: '#C9A962' }}>Save</Text>}
              </button>
            ) : (
              <TouchableOpacity onPress={handleAddClientRecord} disabled={savingRecord} data-testid="modal-save">
                {savingRecord ? <ActivityIndicator size="small" color="#C9A962" /> : <Text style={{ fontSize: 17, fontWeight: '600', color: '#C9A962' }}>Save</Text>}
              </TouchableOpacity>
            )}
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
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  headerBtn: { padding: 4, minWidth: 44 },
  headerTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
  headerSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  scroll: { padding: 16 },

  summaryCard: { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.surface },
  summaryGrid: { flexDirection: 'row', gap: 16, marginTop: 12 },
  summaryItem: { alignItems: 'center', flex: 1 },
  summaryNum: { fontSize: 24, fontWeight: '700', color: colors.text },
  summaryLabel: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },

  section: { backgroundColor: colors.card, borderRadius: 14, marginBottom: 16, borderWidth: 1, borderColor: colors.surface, overflow: 'hidden' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 14, borderBottomWidth: 1, borderBottomColor: colors.surface },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 },

  formBlock: { padding: 14 },
  infoBlock: { padding: 14 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  infoLabel: { fontSize: 14, color: colors.textSecondary },
  infoValue: { fontSize: 14, fontWeight: '600', color: colors.text },
  notesText: { fontSize: 13, color: colors.textSecondary, fontStyle: 'italic', marginTop: 8 },
  emptyText: { fontSize: 14, color: colors.textSecondary, textAlign: 'center' },

  inputLabel: { fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 12 },
  input: { backgroundColor: colors.surface, borderRadius: 10, padding: 12, fontSize: 15, color: colors.text, borderWidth: 1, borderColor: colors.borderLight || colors.surface },

  modelPicker: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  modelOption: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.surface },
  modelOptionActive: { backgroundColor: '#C9A96220', borderColor: '#C9A962' },
  modelText: { fontSize: 13, color: colors.textSecondary },
  modelTextActive: { color: '#C9A962', fontWeight: '600' },

  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12 },
  toggleLabel: { fontSize: 14, color: colors.text },

  saveBtn: { backgroundColor: '#C9A962', borderRadius: 10, padding: 12, alignItems: 'center', marginTop: 8 },
  saveBtnText: { color: '#000', fontWeight: '600', fontSize: 15 },

  recordCard: { padding: 14, borderBottomWidth: 1, borderBottomColor: colors.surface },
  recordName: { fontSize: 15, fontWeight: '600', color: colors.text },
  recordMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 3 },
  recordContact: { fontSize: 12, color: '#007AFF', marginTop: 2 },
  recordNotes: { fontSize: 12, color: colors.textSecondary, fontStyle: 'italic', marginTop: 2 },

  modalContainer: { flex: 1, backgroundColor: colors.bg },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.surface },
  modalTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
});
