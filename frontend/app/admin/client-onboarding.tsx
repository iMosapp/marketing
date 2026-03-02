import React, { useState, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Platform, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';

// ─── Step definitions ───
const STEP_DEFS = [
  { id: 'quote', title: 'Send Quote', icon: 'document-text-outline', color: '#007AFF' },
  { id: 'agreement', title: 'Get Agreement Signed', icon: 'create-outline', color: '#5856D6' },
  { id: 'payment', title: 'Collect Payment', icon: 'card-outline', color: '#34C759' },
  { id: 'configure', title: 'Configure Account', icon: 'settings-outline', color: '#C9A962' },
  { id: 'team', title: 'Add Team Members', icon: 'people-outline', color: '#FF9500' },
  { id: 'live', title: 'Go Live', icon: 'rocket-outline', color: '#FF2D55' },
];

const PLANS = [
  { id: 'starter', name: 'Starter', price: 49, users: '1-5 users' },
  { id: 'pro', name: 'Professional', price: 99, users: '6-15 users' },
  { id: 'enterprise', name: 'Enterprise', price: 199, users: '16+ users' },
];

const INDUSTRIES = [
  'Automotive / Dealership', 'Real Estate', 'Restaurant / Hospitality',
  'Salon / Barbershop', 'Health & Wellness', 'Insurance',
  'Financial Services', 'Home Services', 'Retail', 'Other',
];

const COLORS = ['#C9A962','#007AFF','#34C759','#FF3B30','#FF9500','#AF52DE','#5856D6','#FF2D55','#00C7BE','#30D158'];

interface Client {
  _id: string;
  client_name: string;
  contact_email: string;
  contact_phone: string;
  industry: string;
  notes: string;
  completed_step_ids: string[];
  step_data: Record<string, any>;
  status: string;
  created_at: string;
}

export default function ClientOnboardingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [clients, setClients] = useState<Client[]>([]);
  const [expandedClientId, setExpandedClientId] = useState<string | null>(null);
  const [activeStepId, setActiveStepId] = useState<string | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [saving, setSaving] = useState(false);

  // New client form
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPhone, setNewPhone] = useState('');

  // Step-specific form state (reset when switching clients/steps)
  const [formData, setFormData] = useState<Record<string, any>>({});

  // Team members for step 5
  const [teamRows, setTeamRows] = useState<Array<{ name: string; email: string; phone: string; role: string }>>([]);
  const [inviteResults, setInviteResults] = useState<any[]>([]);

  useFocusEffect(useCallback(() => { loadClients(); }, []));

  const loadClients = async () => {
    try {
      const res = await api.get('/setup-wizard/clients');
      setClients(res.data || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const createClient = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      const res = await api.post('/setup-wizard/clients', {
        client_name: newName.trim(),
        contact_email: newEmail.trim(),
        contact_phone: newPhone.trim(),
      });
      const newClient = res.data;
      setClients([newClient, ...clients]);
      setShowNewForm(false);
      setExpandedClientId(newClient._id);
      setActiveStepId('quote');
      loadFormDataForClient(newClient);
      setNewName(''); setNewEmail(''); setNewPhone('');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Error creating client');
    } finally { setSaving(false); }
  };

  const loadFormDataForClient = (client: Client) => {
    setFormData(client.step_data || {});
    setTeamRows([]);
    setInviteResults([]);
  };

  const expandClient = (client: Client) => {
    if (expandedClientId === client._id) {
      setExpandedClientId(null);
      setActiveStepId(null);
      return;
    }
    setExpandedClientId(client._id);
    loadFormDataForClient(client);
    // Open the first incomplete step
    const next = STEP_DEFS.find(s => !(client.completed_step_ids || []).includes(s.id));
    setActiveStepId(next?.id || null);
  };

  const toggleStep = (stepId: string) => {
    setActiveStepId(activeStepId === stepId ? null : stepId);
  };

  const updateField = (stepId: string, field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [stepId]: { ...(prev[stepId] || {}), [field]: value },
    }));
  };

  const saveStepAndMarkDone = async (clientId: string, stepId: string) => {
    setSaving(true);
    try {
      const client = clients.find(c => c._id === clientId);
      if (!client) return;
      const completedIds = [...new Set([...(client.completed_step_ids || []), stepId])];
      const allDone = completedIds.length === STEP_DEFS.length;

      await api.put(`/setup-wizard/clients/${clientId}`, {
        completed_step_ids: completedIds,
        step_data: formData,
        status: allDone ? 'completed' : 'active',
      });

      setClients(clients.map(c => c._id === clientId
        ? { ...c, completed_step_ids: completedIds, step_data: formData, status: allDone ? 'completed' : 'active' }
        : c
      ));

      // Auto-advance to next step
      const nextIdx = STEP_DEFS.findIndex(s => s.id === stepId) + 1;
      if (nextIdx < STEP_DEFS.length && !completedIds.includes(STEP_DEFS[nextIdx].id)) {
        setActiveStepId(STEP_DEFS[nextIdx].id);
      } else {
        setActiveStepId(null);
      }
    } catch (e) {
      alert('Error saving');
    } finally { setSaving(false); }
  };

  const unmarkStep = async (clientId: string, stepId: string) => {
    const client = clients.find(c => c._id === clientId);
    if (!client) return;
    const completedIds = (client.completed_step_ids || []).filter(s => s !== stepId);
    setClients(clients.map(c => c._id === clientId ? { ...c, completed_step_ids: completedIds, status: 'active' } : c));
    try {
      await api.put(`/setup-wizard/clients/${clientId}`, { completed_step_ids: completedIds, status: 'active' });
    } catch (e) { console.error(e); }
  };

  const sendTeamInvites = async (clientId: string) => {
    const valid = teamRows.filter(m => m.name.trim() && m.email.trim());
    if (valid.length === 0) return;
    setSaving(true);
    try {
      // Use the client's store_id if configured, otherwise use the default store
      const stepCfg = formData.configure || {};
      const storeId = stepCfg.store_id || '';

      if (!storeId) {
        // Try to get default store
        const storesRes = await api.get('/admin/stores');
        const stores = Array.isArray(storesRes.data) ? storesRes.data : [];
        if (stores.length > 0) {
          const res = await api.post('/setup-wizard/bulk-invite', { store_id: stores[0]._id, members: valid });
          setInviteResults(res.data.results || []);
        } else {
          alert('No store found. Please complete "Configure Account" first.');
          setSaving(false);
          return;
        }
      } else {
        const res = await api.post('/setup-wizard/bulk-invite', { store_id: storeId, members: valid });
        setInviteResults(res.data.results || []);
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Error creating accounts');
    } finally { setSaving(false); }
  };

  const archiveClient = async (clientId: string) => {
    setClients(clients.map(c => c._id === clientId ? { ...c, status: 'archived' } : c));
    if (expandedClientId === clientId) { setExpandedClientId(null); setActiveStepId(null); }
    try { await api.put(`/setup-wizard/clients/${clientId}`, { status: 'archived' }); } catch (e) { console.error(e); }
  };

  // ─── Inline Step Forms ───

  const ActionLink = ({ icon, label, onPress, testId }: { icon: string; label: string; onPress: () => void; testId: string }) => (
    <TouchableOpacity style={st.actionLink} onPress={onPress} data-testid={testId}>
      <View style={st.actionLinkIcon}><Ionicons name={icon as any} size={18} color="#C9A962" /></View>
      <Text style={st.actionLinkText}>{label}</Text>
      <Ionicons name="arrow-forward" size={16} color="#C9A962" />
    </TouchableOpacity>
  );

  const WhatYouNeed = ({ items }: { items: string[] }) => (
    <View style={st.wynBox}>
      <Text style={st.wynTitle}>What You Need</Text>
      {items.map((item, i) => (
        <View key={i} style={st.wynRow}>
          <View style={st.wynBullet} />
          <Text style={st.wynText}>{item}</Text>
        </View>
      ))}
    </View>
  );

  const renderStepQuote = (client: Client) => {
    const d = formData.quote || {};
    return (
      <View style={st.form}>
        <WhatYouNeed items={[
          "Ask the client: How many users will need access?",
          "Get their email address to send the quote",
          "Decide on a plan or custom pricing",
        ]} />

        <Text style={st.sectionHead}>1. Create the Quote</Text>
        <ActionLink icon="document-text-outline" label="Open Quote Builder" onPress={() => router.push('/admin/create-quote' as any)} testId="action-create-quote" />

        <Text style={st.sectionHead}>2. Select Plan Here for Reference</Text>
        <View style={st.planGrid}>
          {PLANS.map(plan => (
            <TouchableOpacity key={plan.id} style={[st.planCard, d.plan === plan.id && st.planCardActive]} onPress={() => updateField('quote', 'plan', plan.id)} data-testid={`plan-${plan.id}`}>
              <Text style={[st.planPrice, d.plan === plan.id && st.planPriceActive]}>${plan.price}</Text>
              <Text style={[st.planName, d.plan === plan.id && st.planNameActive]}>{plan.name}</Text>
              <Text style={st.planUsers}>{plan.users}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={st.label}>Custom Price (optional)</Text>
        <TextInput style={st.input} value={d.custom_price || ''} onChangeText={v => updateField('quote', 'custom_price', v)} placeholder="$0.00" placeholderTextColor="#555" keyboardType="numeric" data-testid="quote-custom-price" />
        <Text style={st.label}>Send Quote To</Text>
        <TextInput style={st.input} value={d.send_to || client.contact_email || ''} onChangeText={v => updateField('quote', 'send_to', v)} placeholder="client@email.com" placeholderTextColor="#555" keyboardType="email-address" autoCapitalize="none" data-testid="quote-send-to" />
        <Text style={st.label}>Notes</Text>
        <TextInput style={[st.input, { height: 60, textAlignVertical: 'top' }]} value={d.notes || ''} onChangeText={v => updateField('quote', 'notes', v)} placeholder="Special terms, discount codes, etc." placeholderTextColor="#555" multiline data-testid="quote-notes" />
        <TouchableOpacity style={st.saveBtn} onPress={() => saveStepAndMarkDone(client._id, 'quote')} disabled={saving} data-testid="save-quote">
          {saving ? <ActivityIndicator color="#000" /> : <Text style={st.saveBtnText}>Save & Mark Complete</Text>}
        </TouchableOpacity>
      </View>
    );
  };

  const renderStepAgreement = (client: Client) => {
    const d = formData.agreement || {};
    return (
      <View style={st.form}>
        <WhatYouNeed items={[
          "Client's email to send the agreement to",
          "Any custom terms or special conditions",
          "Wait for their digital signature",
        ]} />

        <Text style={st.sectionHead}>1. Create & Send Agreement</Text>
        <ActionLink icon="create-outline" label="Open Agreement Builder" onPress={() => router.push('/admin/nda/create' as any)} testId="action-create-agreement" />
        <ActionLink icon="list-outline" label="View All Agreements" onPress={() => router.push('/admin/nda' as any)} testId="action-view-agreements" />

        <Text style={st.sectionHead}>2. Track Status</Text>
        <View style={st.statusRow}>
          {['not_sent', 'sent', 'viewed', 'signed'].map(s => (
            <TouchableOpacity key={s} style={[st.statusChip, d.status === s && st.statusChipActive]} onPress={() => updateField('agreement', 'status', s)} data-testid={`agreement-status-${s}`}>
              <Text style={[st.statusChipText, d.status === s && st.statusChipTextActive]}>{s === 'not_sent' ? 'Not Sent' : s.charAt(0).toUpperCase() + s.slice(1)}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={st.label}>Sent To</Text>
        <TextInput style={st.input} value={d.send_to || client.contact_email || ''} onChangeText={v => updateField('agreement', 'send_to', v)} placeholder="client@email.com" placeholderTextColor="#555" keyboardType="email-address" autoCapitalize="none" data-testid="agreement-email" />
        <Text style={st.label}>Signed Date</Text>
        <TextInput style={st.input} value={d.signed_date || ''} onChangeText={v => updateField('agreement', 'signed_date', v)} placeholder="MM/DD/YYYY" placeholderTextColor="#555" data-testid="agreement-signed-date" />
        <Text style={st.label}>Notes</Text>
        <TextInput style={[st.input, { height: 60, textAlignVertical: 'top' }]} value={d.notes || ''} onChangeText={v => updateField('agreement', 'notes', v)} placeholder="Custom terms, expiration, etc." placeholderTextColor="#555" multiline data-testid="agreement-notes" />
        <TouchableOpacity style={st.saveBtn} onPress={() => saveStepAndMarkDone(client._id, 'agreement')} disabled={saving} data-testid="save-agreement">
          {saving ? <ActivityIndicator color="#000" /> : <Text style={st.saveBtnText}>Save & Mark Complete</Text>}
        </TouchableOpacity>
      </View>
    );
  };

  const renderStepPayment = (client: Client) => {
    const d = formData.payment || {};
    return (
      <View style={st.form}>
        <WhatYouNeed items={[
          "Payment method (credit card, check, wire, etc.)",
          "Payment amount and any confirmation number",
          "Billing cycle or next due date",
        ]} />

        <Text style={st.sectionHead}>1. Process Payment</Text>
        <ActionLink icon="card-outline" label="Open Billing / Invoices" onPress={() => router.push('/admin/billing' as any)} testId="action-billing" />

        <Text style={st.sectionHead}>2. Record Payment Details</Text>
        <Text style={st.label}>Payment Method</Text>
        <View style={st.statusRow}>
          {['stripe', 'check', 'wire', 'cash', 'other'].map(m => (
            <TouchableOpacity key={m} style={[st.statusChip, d.method === m && st.statusChipActive]} onPress={() => updateField('payment', 'method', m)} data-testid={`payment-method-${m}`}>
              <Text style={[st.statusChipText, d.method === m && st.statusChipTextActive]}>{m.charAt(0).toUpperCase() + m.slice(1)}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={st.label}>Amount</Text>
        <TextInput style={st.input} value={d.amount || ''} onChangeText={v => updateField('payment', 'amount', v)} placeholder="$0.00" placeholderTextColor="#555" keyboardType="numeric" data-testid="payment-amount" />
        <Text style={st.label}>Reference / Confirmation #</Text>
        <TextInput style={st.input} value={d.reference || ''} onChangeText={v => updateField('payment', 'reference', v)} placeholder="Transaction ID, check #, etc." placeholderTextColor="#555" data-testid="payment-reference" />
        <Text style={st.label}>Payment Date</Text>
        <TextInput style={st.input} value={d.date || ''} onChangeText={v => updateField('payment', 'date', v)} placeholder="MM/DD/YYYY" placeholderTextColor="#555" data-testid="payment-date" />
        <Text style={st.label}>Notes</Text>
        <TextInput style={[st.input, { height: 60, textAlignVertical: 'top' }]} value={d.notes || ''} onChangeText={v => updateField('payment', 'notes', v)} placeholder="Billing cycle, next due date, etc." placeholderTextColor="#555" multiline data-testid="payment-notes" />
        <TouchableOpacity style={st.saveBtn} onPress={() => saveStepAndMarkDone(client._id, 'payment')} disabled={saving} data-testid="save-payment">
          {saving ? <ActivityIndicator color="#000" /> : <Text style={st.saveBtnText}>Save & Mark Complete</Text>}
        </TouchableOpacity>
      </View>
    );
  };

  const renderStepConfigure = (client: Client) => {
    const d = formData.configure || {};
    return (
      <View style={st.form}>
        <WhatYouNeed items={[
          "Company name, phone number, and address",
          "Logo file (PNG or JPG, 512x512 recommended)",
          "Their brand color preference",
          "Google, Facebook, and/or Yelp review page URLs",
        ]} />

        <Text style={st.sectionHead}>1. Use the Setup Wizard for Full Config</Text>
        <ActionLink icon="settings-outline" label="Open Full Setup Wizard" onPress={() => router.push('/admin/setup-wizard' as any)} testId="action-setup-wizard" />

        <Text style={st.sectionHead}>2. Or Quick-Enter Details Here</Text>

        <Text style={st.label}>Company Name</Text>
        <TextInput style={st.input} value={d.company_name || client.client_name || ''} onChangeText={v => updateField('configure', 'company_name', v)} placeholder="Company Name" placeholderTextColor="#555" data-testid="config-company" />
        <Text style={st.label}>Phone</Text>
        <TextInput style={st.input} value={d.phone || client.contact_phone || ''} onChangeText={v => updateField('configure', 'phone', v)} placeholder="(555) 123-4567" placeholderTextColor="#555" keyboardType="phone-pad" data-testid="config-phone" />
        <Text style={st.label}>Address</Text>
        <TextInput style={st.input} value={d.address || ''} onChangeText={v => updateField('configure', 'address', v)} placeholder="123 Main St" placeholderTextColor="#555" data-testid="config-address" />
        <View style={st.row}>
          <TextInput style={[st.input, { flex: 1, marginRight: 8 }]} value={d.city || ''} onChangeText={v => updateField('configure', 'city', v)} placeholder="City" placeholderTextColor="#555" data-testid="config-city" />
          <TextInput style={[st.input, { width: 70 }]} value={d.state || ''} onChangeText={v => updateField('configure', 'state', v)} placeholder="State" placeholderTextColor="#555" data-testid="config-state" />
        </View>
        <Text style={st.label}>Website</Text>
        <TextInput style={st.input} value={d.website || ''} onChangeText={v => updateField('configure', 'website', v)} placeholder="https://example.com" placeholderTextColor="#555" data-testid="config-website" />

        <Text style={st.label}>Industry</Text>
        <View style={st.chipWrap}>
          {INDUSTRIES.map(ind => (
            <TouchableOpacity key={ind} style={[st.chip, d.industry === ind && st.chipActive]} onPress={() => updateField('configure', 'industry', ind)} data-testid={`config-industry-${ind}`}>
              <Text style={[st.chipText, d.industry === ind && st.chipTextActive]}>{ind}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={st.label}>Brand Color</Text>
        <View style={st.colorRow}>
          {COLORS.map(c => (
            <TouchableOpacity key={c} style={[st.colorDot, { backgroundColor: c }, d.primary_color === c && st.colorDotActive]} onPress={() => updateField('configure', 'primary_color', c)} data-testid={`config-color-${c}`} />
          ))}
        </View>

        <Text style={st.label}>Google Review Link</Text>
        <TextInput style={st.input} value={d.google_review || ''} onChangeText={v => updateField('configure', 'google_review', v)} placeholder="https://g.page/your-business/review" placeholderTextColor="#555" data-testid="config-google" />
        <Text style={st.label}>Facebook Review Link</Text>
        <TextInput style={st.input} value={d.facebook_review || ''} onChangeText={v => updateField('configure', 'facebook_review', v)} placeholder="https://facebook.com/your-page/reviews" placeholderTextColor="#555" data-testid="config-facebook" />
        <Text style={st.label}>Yelp Review Link</Text>
        <TextInput style={st.input} value={d.yelp_review || ''} onChangeText={v => updateField('configure', 'yelp_review', v)} placeholder="https://yelp.com/biz/your-business" placeholderTextColor="#555" data-testid="config-yelp" />

        <TouchableOpacity style={st.saveBtn} onPress={() => saveStepAndMarkDone(client._id, 'configure')} disabled={saving} data-testid="save-config">
          {saving ? <ActivityIndicator color="#000" /> : <Text style={st.saveBtnText}>Save & Mark Complete</Text>}
        </TouchableOpacity>
      </View>
    );
  };

  const renderStepTeam = (client: Client) => {
    return (
      <View style={st.form}>
        <Text style={st.formDesc}>Add team members for {client.client_name}. They'll get login credentials automatically.</Text>

        {teamRows.map((member, idx) => (
          <View key={idx} style={st.teamCard}>
            <View style={st.teamCardHead}>
              <Text style={st.teamNum}>Member {idx + 1}</Text>
              <TouchableOpacity onPress={() => setTeamRows(teamRows.filter((_, i) => i !== idx))} data-testid={`remove-team-${idx}`}>
                <Ionicons name="close-circle" size={20} color="#FF3B30" />
              </TouchableOpacity>
            </View>
            <TextInput style={st.input} value={member.name} onChangeText={v => { const u = [...teamRows]; u[idx].name = v; setTeamRows(u); }} placeholder="Full Name" placeholderTextColor="#555" data-testid={`team-name-${idx}`} />
            <TextInput style={st.input} value={member.email} onChangeText={v => { const u = [...teamRows]; u[idx].email = v; setTeamRows(u); }} placeholder="Email" placeholderTextColor="#555" keyboardType="email-address" autoCapitalize="none" data-testid={`team-email-${idx}`} />
            <TextInput style={st.input} value={member.phone} onChangeText={v => { const u = [...teamRows]; u[idx].phone = v; setTeamRows(u); }} placeholder="Phone (optional)" placeholderTextColor="#555" keyboardType="phone-pad" data-testid={`team-phone-${idx}`} />
            <View style={st.roleWrap}>
              {[{id:'user',label:'Sales Rep'},{id:'store_manager',label:'Manager'}].map(r => (
                <TouchableOpacity key={r.id} style={[st.roleBtn, member.role === r.id && st.roleBtnActive]} onPress={() => { const u = [...teamRows]; u[idx].role = r.id; setTeamRows(u); }} data-testid={`team-role-${idx}-${r.id}`}>
                  <Text style={[st.roleBtnText, member.role === r.id && st.roleBtnTextActive]}>{r.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        ))}

        <TouchableOpacity style={st.addRow} onPress={() => setTeamRows([...teamRows, { name: '', email: '', phone: '', role: 'user' }])} data-testid="add-team-member">
          <Ionicons name="add-circle-outline" size={20} color="#C9A962" />
          <Text style={st.addRowText}>Add Team Member</Text>
        </TouchableOpacity>

        {inviteResults.length > 0 && (
          <View style={st.resultsCard}>
            <Text style={st.resultsTitle}>Accounts Created</Text>
            {inviteResults.filter(r => r.status === 'created').map((r, i) => (
              <View key={i} style={st.resultRow}>
                <Text style={st.resultName}>{r.name} — {r.email}</Text>
                <Text style={st.resultPw}>Password: {r.temp_password}</Text>
              </View>
            ))}
          </View>
        )}

        <View style={st.btnRow}>
          {teamRows.length > 0 && (
            <TouchableOpacity style={[st.saveBtn, { flex: 1, backgroundColor: '#FF9500' }]} onPress={() => sendTeamInvites(client._id)} disabled={saving} data-testid="create-accounts">
              {saving ? <ActivityIndicator color="#000" /> : <Text style={st.saveBtnText}>Create Accounts</Text>}
            </TouchableOpacity>
          )}
          <TouchableOpacity style={[st.saveBtn, { flex: 1 }]} onPress={() => saveStepAndMarkDone(client._id, 'team')} disabled={saving} data-testid="save-team">
            <Text style={st.saveBtnText}>Mark Complete</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const renderStepLive = (client: Client) => {
    const doneCount = (client.completed_step_ids || []).length;
    const allPrevDone = doneCount >= 5; // all 5 previous steps done
    return (
      <View style={st.form}>
        {allPrevDone ? (
          <View style={st.liveReady}>
            <Ionicons name="checkmark-circle" size={48} color="#34C759" />
            <Text style={st.liveTitle}>Ready to Go Live!</Text>
            <Text style={st.liveDesc}>{client.client_name} is fully configured. Hit the button to activate this account.</Text>
            <TouchableOpacity style={[st.saveBtn, { backgroundColor: '#34C759' }]} onPress={() => saveStepAndMarkDone(client._id, 'live')} disabled={saving} data-testid="go-live">
              {saving ? <ActivityIndicator color="#000" /> : <Text style={st.saveBtnText}>Activate Account</Text>}
            </TouchableOpacity>
          </View>
        ) : (
          <View style={st.liveReady}>
            <Ionicons name="alert-circle-outline" size={48} color="#FF9500" />
            <Text style={st.liveTitle}>Not Ready Yet</Text>
            <Text style={st.liveDesc}>Complete the previous steps first. {doneCount}/5 steps done.</Text>
          </View>
        )}
      </View>
    );
  };

  const renderStepContent = (stepId: string, client: Client) => {
    switch (stepId) {
      case 'quote': return renderStepQuote(client);
      case 'agreement': return renderStepAgreement(client);
      case 'payment': return renderStepPayment(client);
      case 'configure': return renderStepConfigure(client);
      case 'team': return renderStepTeam(client);
      case 'live': return renderStepLive(client);
      default: return null;
    }
  };

  const activeClients = clients.filter(c => c.status !== 'archived');
  const archivedClients = clients.filter(c => c.status === 'archived');

  if (loading) return <SafeAreaView style={st.safe}><View style={st.center}><ActivityIndicator size="large" color="#C9A962" /></View></SafeAreaView>;

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.header}>
        <TouchableOpacity onPress={() => router.back()} style={st.headerBtn} data-testid="onboarding-back">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <Text style={st.headerTitle}>Client Onboarding</Text>
        <TouchableOpacity onPress={() => setShowNewForm(true)} style={st.headerBtn} data-testid="onboarding-add">
          <Ionicons name="add" size={26} color="#C9A962" />
        </TouchableOpacity>
      </View>

      <ScrollView style={st.scroll} contentContainerStyle={st.scrollContent} keyboardShouldPersistTaps="handled">
        {/* New Client */}
        {!showNewForm ? (
          <TouchableOpacity style={st.newBtn} onPress={() => setShowNewForm(true)} data-testid="new-client-btn">
            <Ionicons name="add-circle" size={20} color="#C9A962" />
            <Text style={st.newBtnText}>New Client</Text>
          </TouchableOpacity>
        ) : (
          <View style={st.newForm}>
            <View style={st.newFormHead}><Text style={st.newFormTitle}>New Client</Text><TouchableOpacity onPress={() => setShowNewForm(false)}><Ionicons name="close" size={20} color="#8E8E93" /></TouchableOpacity></View>
            <TextInput style={st.input} value={newName} onChangeText={setNewName} placeholder="Client / Company Name *" placeholderTextColor="#555" data-testid="new-name" />
            <TextInput style={st.input} value={newEmail} onChangeText={setNewEmail} placeholder="Contact Email" placeholderTextColor="#555" keyboardType="email-address" autoCapitalize="none" data-testid="new-email" />
            <TextInput style={st.input} value={newPhone} onChangeText={setNewPhone} placeholder="Contact Phone" placeholderTextColor="#555" keyboardType="phone-pad" data-testid="new-phone" />
            <TouchableOpacity style={st.createBtn} onPress={createClient} disabled={saving || !newName.trim()} data-testid="create-client">
              {saving ? <ActivityIndicator color="#000" /> : <><Ionicons name="add-circle" size={18} color="#000" /><Text style={st.createBtnText}>Start Onboarding</Text></>}
            </TouchableOpacity>
          </View>
        )}

        {/* Empty */}
        {activeClients.length === 0 && !showNewForm && (
          <View style={st.empty}><Ionicons name="people-outline" size={48} color="#2C2C2E" /><Text style={st.emptyText}>No clients yet</Text></View>
        )}

        {/* Client cards */}
        {activeClients.map(client => {
          const isExpanded = expandedClientId === client._id;
          const doneCount = (client.completed_step_ids || []).length;
          const pct = Math.round((doneCount / STEP_DEFS.length) * 100);

          return (
            <View key={client._id} style={st.clientCard}>
              <TouchableOpacity style={st.clientHead} onPress={() => expandClient(client)} data-testid={`client-${client._id}`}>
                <View style={[st.avatar, pct === 100 && st.avatarDone]}>
                  {pct === 100 ? <Ionicons name="checkmark" size={16} color="#000" /> : <Text style={st.avatarText}>{client.client_name.charAt(0).toUpperCase()}</Text>}
                </View>
                <View style={st.clientInfo}>
                  <Text style={st.clientName}>{client.client_name}</Text>
                  <Text style={st.clientMeta}>{doneCount}/{STEP_DEFS.length} steps{pct === 100 ? ' — Live' : ''}</Text>
                </View>
                <View style={st.miniBar}><View style={[st.miniBarFill, { width: `${pct}%` as any }]} /></View>
                <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color="#555" style={{ marginLeft: 8 }} />
              </TouchableOpacity>

              {isExpanded && (
                <View style={st.stepsWrap}>
                  {STEP_DEFS.map(step => {
                    const isDone = (client.completed_step_ids || []).includes(step.id);
                    const isOpen = activeStepId === step.id;
                    return (
                      <View key={step.id}>
                        <TouchableOpacity style={st.stepRow} onPress={() => toggleStep(step.id)} data-testid={`step-${client._id}-${step.id}`}>
                          <TouchableOpacity onPress={() => isDone ? unmarkStep(client._id, step.id) : null} data-testid={`check-${client._id}-${step.id}`}>
                            <Ionicons name={isDone ? 'checkmark-circle' : 'ellipse-outline'} size={24} color={isDone ? '#34C759' : '#2C2C2E'} />
                          </TouchableOpacity>
                          <View style={[st.stepIconBox, { backgroundColor: step.color + '20' }]}>
                            <Ionicons name={step.icon as any} size={18} color={step.color} />
                          </View>
                          <Text style={[st.stepTitle, isDone && st.stepTitleDone]}>{step.title}</Text>
                          <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={16} color="#555" />
                        </TouchableOpacity>
                        {isOpen && renderStepContent(step.id, client)}
                      </View>
                    );
                  })}
                  <TouchableOpacity style={st.archiveBtn} onPress={() => archiveClient(client._id)} data-testid={`archive-${client._id}`}>
                    <Ionicons name="archive-outline" size={15} color="#FF3B30" /><Text style={st.archiveText}>Archive Client</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          );
        })}

        {archivedClients.length > 0 && (
          <View style={st.archived}>
            <Text style={st.archivedLabel}>Archived ({archivedClients.length})</Text>
            {archivedClients.map(c => (
              <View key={c._id} style={st.archivedRow}><Text style={st.archivedName}>{c.client_name}</Text><Text style={st.archivedMeta}>{(c.completed_step_ids||[]).length}/{STEP_DEFS.length}</Text></View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#000' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  headerBtn: { width: 36, height: 36, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 50 },

  newBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A96215', borderWidth: 1, borderColor: '#C9A96240', borderStyle: 'dashed' as any, borderRadius: 14, padding: 14, marginBottom: 14 },
  newBtnText: { fontSize: 15, fontWeight: '700', color: '#C9A962' },
  newForm: { backgroundColor: '#0D0D0D', borderRadius: 14, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: '#C9A96240' },
  newFormHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  newFormTitle: { fontSize: 17, fontWeight: '800', color: '#FFF' },
  createBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 14, borderRadius: 50, marginTop: 4 },
  createBtnText: { fontSize: 15, fontWeight: '800', color: '#000' },
  empty: { alignItems: 'center', paddingVertical: 60, gap: 8 },
  emptyText: { fontSize: 16, color: '#3A3A3C' },

  // Client
  clientCard: { backgroundColor: '#0D0D0D', borderRadius: 14, marginBottom: 10, borderWidth: 1, borderColor: '#1C1C1E', overflow: 'hidden' },
  clientHead: { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 10 },
  avatar: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' },
  avatarDone: { backgroundColor: '#34C759' },
  avatarText: { fontSize: 15, fontWeight: '800', color: '#C9A962' },
  clientInfo: { flex: 1 },
  clientName: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  clientMeta: { fontSize: 11, color: '#8E8E93', marginTop: 1 },
  miniBar: { width: 36, height: 4, borderRadius: 2, backgroundColor: '#1C1C1E', overflow: 'hidden' },
  miniBarFill: { height: '100%' as any, backgroundColor: '#C9A962', borderRadius: 2 },

  // Steps
  stepsWrap: { borderTopWidth: 1, borderTopColor: '#1C1C1E' },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, paddingHorizontal: 14, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  stepIconBox: { width: 30, height: 30, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  stepTitle: { flex: 1, fontSize: 14, fontWeight: '600', color: '#FFF' },
  stepTitleDone: { textDecorationLine: 'line-through', color: '#8E8E93' },

  // Forms
  form: { padding: 14, paddingTop: 8, backgroundColor: '#080808' },
  formDesc: { fontSize: 13, color: '#8E8E93', marginBottom: 14, lineHeight: 18 },
  label: { fontSize: 11, fontWeight: '700', color: '#555', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6, marginTop: 12 },
  sectionHead: { fontSize: 13, fontWeight: '700', color: '#C9A962', marginTop: 18, marginBottom: 8 },
  input: { backgroundColor: '#1C1C1E', borderRadius: 10, padding: 12, fontSize: 14, color: '#FFF', borderWidth: 1, borderColor: '#2C2C2E', marginBottom: 6 },
  row: { flexDirection: 'row', marginBottom: 6 },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#C9A962', paddingVertical: 14, borderRadius: 50, marginTop: 16 },
  saveBtnText: { fontSize: 15, fontWeight: '800', color: '#000' },
  btnRow: { flexDirection: 'row', gap: 8 },

  // Plans
  planGrid: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  planCard: { flex: 1, backgroundColor: '#1C1C1E', borderRadius: 12, padding: 14, alignItems: 'center', borderWidth: 2, borderColor: '#2C2C2E' },
  planCardActive: { borderColor: '#C9A962', backgroundColor: '#C9A96215' },
  planPrice: { fontSize: 22, fontWeight: '900', color: '#FFF', marginBottom: 2 },
  planPriceActive: { color: '#C9A962' },
  planName: { fontSize: 13, fontWeight: '700', color: '#FFF', marginBottom: 2 },
  planNameActive: { color: '#C9A962' },
  planUsers: { fontSize: 10, color: '#555' },

  // Status chips
  statusRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  statusChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, backgroundColor: '#1C1C1E', borderWidth: 1, borderColor: '#2C2C2E' },
  statusChipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  statusChipText: { fontSize: 12, fontWeight: '600', color: '#8E8E93' },
  statusChipTextActive: { color: '#000' },

  // Industry chips
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: '#1C1C1E', borderWidth: 1, borderColor: '#2C2C2E' },
  chipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  chipText: { fontSize: 12, color: '#AAA' },
  chipTextActive: { color: '#000', fontWeight: '700' },

  // Colors
  colorRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  colorDot: { width: 32, height: 32, borderRadius: 16, borderWidth: 3, borderColor: 'transparent' },
  colorDotActive: { borderColor: '#FFF' },

  // Review links
  reviewRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  reviewBadge: { width: 26, height: 26, borderRadius: 7, alignItems: 'center', justifyContent: 'center' },
  reviewBadgeText: { fontSize: 14, fontWeight: '800', color: '#FFF' },

  // Team
  teamCard: { backgroundColor: '#111', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#1C1C1E' },
  teamCardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  teamNum: { fontSize: 12, fontWeight: '700', color: '#C9A962' },
  roleWrap: { flexDirection: 'row', gap: 6, marginTop: 4 },
  roleBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, backgroundColor: '#1C1C1E', alignItems: 'center', borderWidth: 1, borderColor: '#2C2C2E' },
  roleBtnActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  roleBtnText: { fontSize: 12, fontWeight: '600', color: '#8E8E93' },
  roleBtnTextActive: { color: '#000' },
  addRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 10, borderWidth: 1, borderColor: '#2C2C2E', borderStyle: 'dashed' as any, marginBottom: 8 },
  addRowText: { fontSize: 13, fontWeight: '600', color: '#C9A962' },
  resultsCard: { backgroundColor: '#1A1500', borderRadius: 12, padding: 12, marginTop: 10, borderWidth: 1, borderColor: '#C9A96233' },
  resultsTitle: { fontSize: 13, fontWeight: '700', color: '#C9A962', marginBottom: 8 },
  resultRow: { backgroundColor: '#0D0D0D', borderRadius: 8, padding: 10, marginBottom: 6 },
  resultName: { fontSize: 13, fontWeight: '600', color: '#FFF' },
  resultPw: { fontSize: 12, color: '#C9A962', fontFamily: Platform.OS === 'web' ? 'monospace' : undefined, marginTop: 2 },

  // Go Live
  liveReady: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  liveTitle: { fontSize: 20, fontWeight: '900', color: '#FFF' },
  liveDesc: { fontSize: 13, color: '#8E8E93', textAlign: 'center', lineHeight: 18, marginBottom: 8 },

  // Archive
  archiveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderTopWidth: 1, borderTopColor: '#1C1C1E' },
  archiveText: { fontSize: 12, color: '#FF3B30', fontWeight: '600' },

  archived: { marginTop: 20 },
  archivedLabel: { fontSize: 12, fontWeight: '700', color: '#555', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 },
  archivedRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  archivedName: { fontSize: 13, color: '#555' },
  archivedMeta: { fontSize: 12, color: '#3A3A3C' },
});
