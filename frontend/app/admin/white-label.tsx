import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
export default function WhiteLabelPartnersScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const [partners, setPartners] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', slug: '', primary_color: '#E87722', secondary_color: '#008B8B',
    accent_color: '#1B2A4A', powered_by_text: "i'M On Social",
    company_name: '', company_address: '', company_phone: '', company_email: '', company_website: '',
    commission_notes: '',
  });

  useEffect(() => { loadPartners(); }, []);

  const loadPartners = async () => {
    try {
      const res = await api.get('/admin/partners');
      setPartners(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleSave = async () => {
    if (!form.name || !form.slug) return;
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/admin/partners/${editing._id}`, form);
      } else {
        await api.post('/admin/partners', form);
      }
      setShowForm(false); setEditing(null);
      setForm({ name: '', slug: '', primary_color: '#E87722', secondary_color: '#008B8B', accent_color: '#1B2A4A', powered_by_text: "i'M On Social", company_name: '', company_address: '', company_phone: '', company_email: '', company_website: '', commission_notes: '' });
      loadPartners();
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const handleEdit = async (id: string) => {
    try {
      const res = await api.get(`/admin/partners/${id}`);
      const p = res.data;
      setForm({
        name: p.name, slug: p.slug, primary_color: p.primary_color, secondary_color: p.secondary_color,
        accent_color: p.accent_color, powered_by_text: p.powered_by_text,
        company_name: p.company_name || '', company_address: p.company_address || '',
        company_phone: p.company_phone || '', company_email: p.company_email || '',
        company_website: p.company_website || '', commission_notes: p.commission_notes || '',
        sold_workflow_enabled: p.sold_workflow_enabled || false,
        sold_required_fields: p.sold_required_fields || [],
        external_account_id_required: p.external_account_id_required || false,
        event_delivery: p.event_delivery || { enabled: false, endpoint_url: '', auth_type: 'none', auth_value_encrypted: '' },
      } as any);
      setEditing(p); setShowForm(true);
    } catch (e) { console.error(e); }
  };

  const handleDelete = async (id: string) => {
    try { await api.delete(`/admin/partners/${id}`); loadPartners(); } catch (e) { console.error(e); }
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.headerBtn}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>White Label Partners</Text>
        <TouchableOpacity onPress={() => { setEditing(null); setShowForm(!showForm); }} style={s.headerBtn}>
          <Ionicons name={showForm ? 'close' : 'add'} size={24} color="#C9A962" />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={s.scroll}>
        {showForm && (
          <View style={s.formCard} data-testid="partner-form">
            <Text style={s.formTitle}>{editing ? 'Edit Partner' : 'New White Label Partner'}</Text>
            {[
              { key: 'name', label: 'Partner Name', placeholder: 'Calendar Systems' },
              { key: 'slug', label: 'URL Slug', placeholder: 'calendar-systems' },
              { key: 'company_name', label: 'Legal Name', placeholder: 'Calendar Systems Inc.' },
              { key: 'company_phone', label: 'Phone', placeholder: '1.801.479.7097' },
              { key: 'company_email', label: 'Email', placeholder: 'info@calendarsystems.info' },
              { key: 'company_website', label: 'Website', placeholder: 'https://calendarsystems.info' },
              { key: 'company_address', label: 'Address', placeholder: '1480 E Ridgeline Drive...' },
              { key: 'powered_by_text', label: 'Powered By Text', placeholder: "i'M On Social" },
            ].map(f => (
              <View key={f.key} style={s.inputGroup}>
                <Text style={s.inputLabel}>{f.label}</Text>
                <TextInput style={s.input} placeholder={f.placeholder} placeholderTextColor={colors.textTertiary}
                  value={(form as any)[f.key]} onChangeText={t => setForm({ ...form, [f.key]: t })} />
              </View>
            ))}
            <View style={s.inputGroup}>
              <Text style={s.inputLabel}>Commission Structure</Text>
              <TextInput style={[s.input, { minHeight: 72, textAlignVertical: 'top' }]}
                placeholder="e.g., 15% of MRR for first 12 months, then 10% ongoing"
                placeholderTextColor={colors.textTertiary}
                value={form.commission_notes}
                onChangeText={t => setForm({ ...form, commission_notes: t })}
                multiline
                data-testid="commission-notes-input"
              />
            </View>

            {/* Sold Workflow Config Section */}
            <View style={{ borderTopWidth: 1, borderTopColor: colors.surface, paddingTop: 16, marginTop: 8, marginBottom: 12 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Ionicons name="pricetag" size={18} color="#FF9500" />
                <Text style={[s.inputLabel, { marginBottom: 0, fontSize: 15, fontWeight: '700' }]}>Sold Workflow</Text>
              </View>
              <TouchableOpacity
                onPress={() => setForm({ ...form, sold_workflow_enabled: !form.sold_workflow_enabled } as any)}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12, padding: 10, backgroundColor: (form as any).sold_workflow_enabled ? '#34C75915' : colors.surface, borderRadius: 8 }}
                data-testid="sold-workflow-toggle"
              >
                <Ionicons name={(form as any).sold_workflow_enabled ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={(form as any).sold_workflow_enabled ? '#34C759' : colors.textSecondary} />
                <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>Enable Sold Workflow</Text>
              </TouchableOpacity>
              {(form as any).sold_workflow_enabled && (
                <>
                  <Text style={[s.inputLabel, { fontSize: 12, color: colors.textSecondary }]}>Required Fields</Text>
                  {[
                    { id: 'customer_name', label: 'Customer Name' },
                    { id: 'phone_number', label: 'Phone Number' },
                    { id: 'full_size_image', label: 'Full-Size Image' },
                    { id: 'deal_or_stock_number', label: 'Deal or Stock Number' },
                  ].map(f => {
                    const isOn = ((form as any).sold_required_fields || []).includes(f.id);
                    return (
                      <TouchableOpacity key={f.id}
                        onPress={() => {
                          const current = (form as any).sold_required_fields || [];
                          const next = isOn ? current.filter((x: string) => x !== f.id) : [...current, f.id];
                          setForm({ ...form, sold_required_fields: next } as any);
                        }}
                        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, paddingHorizontal: 10 }}
                      >
                        <Ionicons name={isOn ? 'checkbox' : 'square-outline'} size={20} color={isOn ? '#34C759' : colors.textSecondary} />
                        <Text style={{ fontSize: 13, color: colors.text }}>{f.label}</Text>
                      </TouchableOpacity>
                    );
                  })}
                  <TouchableOpacity
                    onPress={() => setForm({ ...form, external_account_id_required: !(form as any).external_account_id_required } as any)}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, paddingHorizontal: 10, marginBottom: 12 }}
                  >
                    <Ionicons name={(form as any).external_account_id_required ? 'checkbox' : 'square-outline'} size={20} color={(form as any).external_account_id_required ? '#34C759' : colors.textSecondary} />
                    <Text style={{ fontSize: 13, color: colors.text }}>Require External Account ID</Text>
                  </TouchableOpacity>

                  <View style={{ borderTopWidth: 1, borderTopColor: colors.surface, paddingTop: 12, marginBottom: 8 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <Ionicons name="send" size={16} color="#007AFF" />
                      <Text style={[s.inputLabel, { marginBottom: 0, fontSize: 13, fontWeight: '600' }]}>External Endpoint</Text>
                    </View>
                    <TouchableOpacity
                      onPress={() => {
                        const ed = (form as any).event_delivery || { enabled: false, endpoint_url: '', auth_type: 'none', auth_value_encrypted: '' };
                        setForm({ ...form, event_delivery: { ...ed, enabled: !ed.enabled } } as any);
                      }}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8, padding: 8 }}
                    >
                      <Ionicons name={((form as any).event_delivery?.enabled) ? 'checkmark-circle' : 'ellipse-outline'} size={20} color={((form as any).event_delivery?.enabled) ? '#34C759' : colors.textSecondary} />
                      <Text style={{ fontSize: 13, color: colors.text }}>Enable Endpoint Delivery</Text>
                    </TouchableOpacity>
                    {((form as any).event_delivery?.enabled) && (
                      <>
                        <View style={s.inputGroup}>
                          <Text style={[s.inputLabel, { fontSize: 12 }]}>Endpoint URL</Text>
                          <TextInput style={s.input} placeholder="https://api.partner.com/sold-events"
                            placeholderTextColor={colors.textTertiary}
                            value={(form as any).event_delivery?.endpoint_url || ''}
                            onChangeText={t => setForm({ ...form, event_delivery: { ...(form as any).event_delivery, endpoint_url: t } } as any)}
                            autoCapitalize="none" keyboardType="url"
                          />
                        </View>
                      </>
                    )}
                  </View>
                </>
              )}
            </View>
            <Text style={s.inputLabel}>Brand Colors</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
              {[
                { key: 'primary_color', label: 'Primary' },
                { key: 'secondary_color', label: 'Secondary' },
                { key: 'accent_color', label: 'Accent' },
              ].map(c => (
                <View key={c.key} style={{ flex: 1 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <View style={{ width: 16, height: 16, borderRadius: 4, backgroundColor: (form as any)[c.key] }} />
                    <Text style={{ fontSize: 11, color: colors.textSecondary }}>{c.label}</Text>
                  </View>
                  <TextInput style={[s.input, { fontSize: 13, padding: 10 }]} placeholder="#000000" placeholderTextColor={colors.textTertiary}
                    value={(form as any)[c.key]} onChangeText={t => setForm({ ...form, [c.key]: t })} />
                </View>
              ))}
            </View>
            <TouchableOpacity style={s.saveBtn} onPress={handleSave} disabled={saving}>
              {saving ? <ActivityIndicator color={colors.text} /> : <Text style={s.saveBtnText}>{editing ? 'Update Partner' : 'Create Partner'}</Text>}
            </TouchableOpacity>
          </View>
        )}

        {loading ? (
          <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 40 }} />
        ) : partners.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="business-outline" size={48} color={colors.surface} />
            <Text style={s.emptyText}>No white-label partners yet</Text>
            <Text style={s.emptySub}>Create your first partner to start white-labeling</Text>
          </View>
        ) : (
          partners.map(p => (
            <View key={p._id} style={s.partnerCard} data-testid={`partner-card-${p.slug}`}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 }}>
                <View style={[s.partnerIcon, { backgroundColor: (p.primary_color || '#C9A962') + '20' }]}>
                  <Text style={[s.partnerIconText, { color: p.primary_color || '#C9A962' }]}>
                    {p.name?.split(' ').map((w: string) => w[0]).join('').slice(0, 2)}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.partnerName}>{p.name}</Text>
                  <Text style={s.partnerSlug}>/{p.slug}</Text>
                  {p.commission_notes && (
                    <Text style={{ fontSize: 12, color: '#C9A962', marginTop: 3, fontStyle: 'italic' }} numberOfLines={1}>{p.commission_notes}</Text>
                  )}
                  {p.sold_workflow_enabled && (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
                      <Ionicons name="pricetag" size={12} color="#34C759" />
                      <Text style={{ fontSize: 11, color: '#34C759', fontWeight: '600' }}>Sold Workflow Active</Text>
                      {p.event_delivery?.enabled && (
                        <>
                          <Ionicons name="send" size={10} color="#007AFF" style={{ marginLeft: 6 }} />
                          <Text style={{ fontSize: 11, color: '#007AFF' }}>Endpoint On</Text>
                        </>
                      )}
                    </View>
                  )}
                </View>
                <View style={[s.statusBadge, p.is_active && s.statusActive]}>
                  <Text style={s.statusText}>{p.is_active ? 'Active' : 'Inactive'}</Text>
                </View>
              </View>
              <View style={s.partnerActions}>
                <TouchableOpacity style={s.actionBtn} onPress={() => handleEdit(p._id)}>
                  <Ionicons name="create-outline" size={18} color="#007AFF" />
                  <Text style={[s.actionText, { color: '#007AFF' }]}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.actionBtn} onPress={() => router.push(`/admin/partner-orgs?id=${p._id}&name=${p.name}`)}>
                  <Ionicons name="business-outline" size={18} color="#C9A962" />
                  <Text style={[s.actionText, { color: '#C9A962' }]}>Orgs</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.actionBtn} onPress={() => handleDelete(p._id)}>
                  <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                  <Text style={[s.actionText, { color: '#FF3B30' }]}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  headerBtn: { padding: 4, minWidth: 50 },
  headerTitle: { fontSize: 17, fontWeight: '600', color: colors.text, flex: 1, textAlign: 'center' },
  scroll: { padding: 16 },
  formCard: { backgroundColor: colors.card, borderRadius: 14, padding: 20, marginBottom: 20, borderWidth: 1, borderColor: colors.surface },
  formTitle: { fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 16 },
  inputGroup: { marginBottom: 12 },
  inputLabel: { fontSize: 12, fontWeight: '500', color: '#8E8E93', marginBottom: 4, marginLeft: 2 },
  input: { backgroundColor: colors.surface, borderRadius: 10, padding: 14, fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.borderLight },
  saveBtn: { backgroundColor: '#C9A962', borderRadius: 12, padding: 16, alignItems: 'center', marginTop: 8 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: colors.text },
  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { fontSize: 18, color: '#8E8E93', marginTop: 12 },
  emptySub: { fontSize: 14, color: colors.textSecondary, marginTop: 4 },
  partnerCard: { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.surface },
  partnerIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  partnerIconText: { fontSize: 16, fontWeight: '800' },
  partnerName: { fontSize: 16, fontWeight: '600', color: colors.text },
  partnerSlug: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, backgroundColor: colors.surface },
  statusActive: { backgroundColor: '#34C75920' },
  statusText: { fontSize: 11, fontWeight: '600', color: '#8E8E93' },
  partnerActions: { flexDirection: 'row', gap: 16, marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.surface },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  actionText: { fontSize: 13, fontWeight: '600' },
});
