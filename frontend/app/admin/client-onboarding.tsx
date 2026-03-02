import React, { useState, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';

const STEP_DEFS = [
  { id: 'quote', title: 'Send Quote', subtitle: 'Create and send a pricing quote', icon: 'document-text-outline', color: '#007AFF', route: '/admin/create-quote' },
  { id: 'agreement', title: 'Get Agreement Signed', subtitle: 'Client reviews and e-signs', icon: 'create-outline', color: '#5856D6', route: '/admin/nda' },
  { id: 'payment', title: 'Collect Payment', subtitle: 'Process first payment or billing', icon: 'card-outline', color: '#34C759', route: '/admin/billing' },
  { id: 'configure', title: 'Configure Account', subtitle: 'Company info, branding, review links', icon: 'settings-outline', color: '#C9A962', route: '/admin/setup-wizard' },
  { id: 'team', title: 'Add Team Members', subtitle: 'Invite the team and assign roles', icon: 'people-outline', color: '#FF9500', route: '/admin/manage-team' },
  { id: 'live', title: 'Account Live', subtitle: 'Account is active and ready', icon: 'rocket-outline', color: '#FF2D55', route: '' },
];

interface Client {
  _id: string;
  client_name: string;
  contact_email: string;
  contact_phone: string;
  industry: string;
  notes: string;
  completed_step_ids: string[];
  created_at: string;
  status: string; // active, completed, archived
}

export default function ClientOnboardingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [clients, setClients] = useState<Client[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [saving, setSaving] = useState(false);

  // New client form
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPhone, setNewPhone] = useState('');
  const [newIndustry, setNewIndustry] = useState('');
  const [newNotes, setNewNotes] = useState('');

  useFocusEffect(useCallback(() => { loadClients(); }, []));

  const loadClients = async () => {
    try {
      const res = await api.get('/setup-wizard/clients');
      setClients(res.data || []);
    } catch (e) {
      console.error('Error loading clients:', e);
    } finally {
      setLoading(false);
    }
  };

  const createClient = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      const res = await api.post('/setup-wizard/clients', {
        client_name: newName.trim(),
        contact_email: newEmail.trim(),
        contact_phone: newPhone.trim(),
        industry: newIndustry.trim(),
        notes: newNotes.trim(),
      });
      setClients([res.data, ...clients]);
      setShowNewForm(false);
      setExpandedId(res.data._id);
      setNewName(''); setNewEmail(''); setNewPhone(''); setNewIndustry(''); setNewNotes('');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Error creating client');
    } finally {
      setSaving(false);
    }
  };

  const toggleStep = async (clientId: string, stepId: string) => {
    const client = clients.find(c => c._id === clientId);
    if (!client) return;

    const ids = client.completed_step_ids || [];
    const updated = ids.includes(stepId) ? ids.filter(s => s !== stepId) : [...ids, stepId];
    const allDone = updated.length === STEP_DEFS.length;

    // Optimistic update
    setClients(clients.map(c => c._id === clientId ? { ...c, completed_step_ids: updated, status: allDone ? 'completed' : 'active' } : c));

    try {
      await api.put(`/setup-wizard/clients/${clientId}`, {
        completed_step_ids: updated,
        status: allDone ? 'completed' : 'active',
      });
    } catch (e) {
      console.error('Error saving step:', e);
    }
  };

  const archiveClient = async (clientId: string) => {
    setClients(clients.map(c => c._id === clientId ? { ...c, status: 'archived' } : c));
    try {
      await api.put(`/setup-wizard/clients/${clientId}`, { status: 'archived' });
    } catch (e) {
      console.error('Error archiving:', e);
    }
  };

  const activeClients = clients.filter(c => c.status !== 'archived');
  const archivedClients = clients.filter(c => c.status === 'archived');

  if (loading) {
    return (
      <SafeAreaView style={st.safe}>
        <View style={st.center}><ActivityIndicator size="large" color="#C9A962" /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.safe}>
      {/* Header */}
      <View style={st.header}>
        <TouchableOpacity onPress={() => router.back()} style={st.headerBtn} data-testid="onboarding-back">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <Text style={st.headerTitle}>Client Onboarding</Text>
        <TouchableOpacity onPress={() => setShowNewForm(true)} style={st.headerBtn} data-testid="onboarding-new-client">
          <Ionicons name="add" size={26} color="#C9A962" />
        </TouchableOpacity>
      </View>

      <ScrollView style={st.body} contentContainerStyle={st.bodyContent}>
        {/* New Client Button */}
        {!showNewForm && (
          <TouchableOpacity style={st.newClientBtn} onPress={() => setShowNewForm(true)} data-testid="onboarding-new-client-btn">
            <Ionicons name="add-circle" size={22} color="#C9A962" />
            <Text style={st.newClientBtnText}>New Client</Text>
          </TouchableOpacity>
        )}

        {/* New Client Form */}
        {showNewForm && (
          <View style={st.formCard}>
            <View style={st.formHeader}>
              <Text style={st.formTitle}>New Client</Text>
              <TouchableOpacity onPress={() => setShowNewForm(false)} data-testid="onboarding-cancel-new">
                <Ionicons name="close" size={22} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            <TextInput style={st.input} value={newName} onChangeText={setNewName} placeholder="Company / Client Name *" placeholderTextColor="#555" data-testid="new-client-name" />
            <TextInput style={st.input} value={newEmail} onChangeText={setNewEmail} placeholder="Contact Email" placeholderTextColor="#555" keyboardType="email-address" autoCapitalize="none" data-testid="new-client-email" />
            <TextInput style={st.input} value={newPhone} onChangeText={setNewPhone} placeholder="Contact Phone" placeholderTextColor="#555" keyboardType="phone-pad" data-testid="new-client-phone" />
            <TextInput style={st.input} value={newIndustry} onChangeText={setNewIndustry} placeholder="Industry (e.g. Automotive)" placeholderTextColor="#555" data-testid="new-client-industry" />
            <TextInput style={[st.input, { height: 70, textAlignVertical: 'top' }]} value={newNotes} onChangeText={setNewNotes} placeholder="Notes (optional)" placeholderTextColor="#555" multiline data-testid="new-client-notes" />
            <TouchableOpacity style={st.createBtn} onPress={createClient} disabled={saving || !newName.trim()} data-testid="new-client-create">
              {saving ? <ActivityIndicator color="#000" /> : (
                <>
                  <Ionicons name="add-circle" size={18} color="#000" />
                  <Text style={st.createBtnText}>Create & Start Onboarding</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}

        {/* Active Clients */}
        {activeClients.length === 0 && !showNewForm && (
          <View style={st.emptyState}>
            <Ionicons name="people-outline" size={48} color="#2C2C2E" />
            <Text style={st.emptyTitle}>No clients yet</Text>
            <Text style={st.emptySubtitle}>Tap "New Client" to start onboarding</Text>
          </View>
        )}

        {activeClients.map(client => {
          const isExpanded = expandedId === client._id;
          const doneCount = (client.completed_step_ids || []).length;
          const pct = Math.round((doneCount / STEP_DEFS.length) * 100);
          const nextStep = STEP_DEFS.find(s => !(client.completed_step_ids || []).includes(s.id));

          return (
            <View key={client._id} style={st.clientCard}>
              {/* Client header — tap to expand */}
              <TouchableOpacity
                style={st.clientHeader}
                onPress={() => setExpandedId(isExpanded ? null : client._id)}
                data-testid={`client-toggle-${client._id}`}
              >
                <View style={st.clientLeft}>
                  <View style={[st.clientAvatar, pct === 100 && st.clientAvatarDone]}>
                    {pct === 100 ? (
                      <Ionicons name="checkmark" size={18} color="#000" />
                    ) : (
                      <Text style={st.clientAvatarText}>{client.client_name.charAt(0).toUpperCase()}</Text>
                    )}
                  </View>
                  <View style={st.clientInfo}>
                    <Text style={st.clientName}>{client.client_name}</Text>
                    <Text style={st.clientMeta}>
                      {pct === 100 ? 'Live' : nextStep ? `Next: ${nextStep.title}` : ''} — {doneCount}/{STEP_DEFS.length} steps
                    </Text>
                  </View>
                </View>
                <View style={st.clientRight}>
                  <View style={st.miniBar}><View style={[st.miniBarFill, { width: `${pct}%` as any }]} /></View>
                  <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color="#555" />
                </View>
              </TouchableOpacity>

              {/* Expanded checklist */}
              {isExpanded && (
                <View style={st.checklist}>
                  {client.contact_email || client.contact_phone ? (
                    <View style={st.contactRow}>
                      {client.contact_email ? <Text style={st.contactText}>{client.contact_email}</Text> : null}
                      {client.contact_phone ? <Text style={st.contactText}>{client.contact_phone}</Text> : null}
                      {client.industry ? <Text style={st.contactText}>{client.industry}</Text> : null}
                    </View>
                  ) : null}

                  {STEP_DEFS.map((step, idx) => {
                    const isDone = (client.completed_step_ids || []).includes(step.id);
                    const isNext = step.id === nextStep?.id;
                    return (
                      <View key={step.id} style={st.checkRow}>
                        <TouchableOpacity
                          style={st.checkCircle}
                          onPress={() => toggleStep(client._id, step.id)}
                          data-testid={`check-${client._id}-${step.id}`}
                        >
                          <Ionicons
                            name={isDone ? 'checkmark-circle' : 'ellipse-outline'}
                            size={24}
                            color={isDone ? '#34C759' : '#2C2C2E'}
                          />
                        </TouchableOpacity>
                        <View style={st.checkInfo}>
                          <Text style={[st.checkTitle, isDone && st.checkTitleDone]}>{step.title}</Text>
                          <Text style={st.checkSub}>{step.subtitle}</Text>
                        </View>
                        {step.route ? (
                          <TouchableOpacity
                            style={[st.goBtn, isNext && st.goBtnNext]}
                            onPress={() => router.push(step.route as any)}
                            data-testid={`go-${client._id}-${step.id}`}
                          >
                            <Text style={[st.goBtnText, isNext && st.goBtnTextNext]}>
                              {isNext ? 'Do It' : 'Open'}
                            </Text>
                          </TouchableOpacity>
                        ) : null}
                      </View>
                    );
                  })}

                  {/* Archive button */}
                  <TouchableOpacity style={st.archiveBtn} onPress={() => archiveClient(client._id)} data-testid={`archive-${client._id}`}>
                    <Ionicons name="archive-outline" size={16} color="#FF3B30" />
                    <Text style={st.archiveBtnText}>Archive</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          );
        })}

        {/* Archived section */}
        {archivedClients.length > 0 && (
          <View style={st.archivedSection}>
            <Text style={st.archivedTitle}>Archived ({archivedClients.length})</Text>
            {archivedClients.map(c => (
              <View key={c._id} style={st.archivedRow}>
                <Text style={st.archivedName}>{c.client_name}</Text>
                <Text style={st.archivedMeta}>{(c.completed_step_ids || []).length}/{STEP_DEFS.length} steps</Text>
              </View>
            ))}
          </View>
        )}

        {/* Quick ref */}
        <View style={st.refCard}>
          <Text style={st.refTitle}>Quick Reference</Text>
          <View style={st.refRow}><Ionicons name="time-outline" size={15} color="#555" /><Text style={st.refText}>Average setup: 15-30 minutes per client</Text></View>
          <View style={st.refRow}><Ionicons name="swap-horizontal-outline" size={15} color="#555" /><Text style={st.refText}>Steps can be completed in any order</Text></View>
          <View style={st.refRow}><Ionicons name="save-outline" size={15} color="#555" /><Text style={st.refText}>Progress saves automatically</Text></View>
        </View>
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

  body: { flex: 1 },
  bodyContent: { padding: 16, paddingBottom: 40 },

  // New client button
  newClientBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A96215', borderWidth: 1, borderColor: '#C9A96240', borderRadius: 14, padding: 16, marginBottom: 16, borderStyle: 'dashed' as any },
  newClientBtnText: { fontSize: 16, fontWeight: '700', color: '#C9A962' },

  // Form
  formCard: { backgroundColor: '#0D0D0D', borderRadius: 16, padding: 18, marginBottom: 16, borderWidth: 1, borderColor: '#C9A96240' },
  formHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  formTitle: { fontSize: 18, fontWeight: '800', color: '#FFF' },
  input: { backgroundColor: '#1C1C1E', borderRadius: 10, padding: 13, fontSize: 15, color: '#FFF', borderWidth: 1, borderColor: '#2C2C2E', marginBottom: 10 },
  createBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', paddingVertical: 14, borderRadius: 50, marginTop: 4 },
  createBtnText: { fontSize: 15, fontWeight: '800', color: '#000' },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 60, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: '#555' },
  emptySubtitle: { fontSize: 14, color: '#3A3A3C' },

  // Client card
  clientCard: { backgroundColor: '#0D0D0D', borderRadius: 14, marginBottom: 10, borderWidth: 1, borderColor: '#1C1C1E', overflow: 'hidden' },
  clientHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14 },
  clientLeft: { flexDirection: 'row', alignItems: 'center', flex: 1, gap: 12 },
  clientAvatar: { width: 38, height: 38, borderRadius: 10, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#2C2C2E' },
  clientAvatarDone: { backgroundColor: '#34C759', borderColor: '#34C759' },
  clientAvatarText: { fontSize: 16, fontWeight: '800', color: '#C9A962' },
  clientInfo: { flex: 1 },
  clientName: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  clientMeta: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  clientRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  miniBar: { width: 40, height: 4, borderRadius: 2, backgroundColor: '#1C1C1E', overflow: 'hidden' },
  miniBarFill: { height: '100%' as any, backgroundColor: '#C9A962', borderRadius: 2 },

  // Checklist
  checklist: { paddingHorizontal: 14, paddingBottom: 14, borderTopWidth: 1, borderTopColor: '#1C1C1E' },
  contactRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1C1C1E', marginBottom: 6 },
  contactText: { fontSize: 12, color: '#8E8E93' },
  checkRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, gap: 10 },
  checkCircle: { width: 28 },
  checkInfo: { flex: 1 },
  checkTitle: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  checkTitleDone: { textDecorationLine: 'line-through', color: '#8E8E93' },
  checkSub: { fontSize: 11, color: '#555', marginTop: 1 },
  goBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#1C1C1E' },
  goBtnNext: { backgroundColor: '#C9A962' },
  goBtnText: { fontSize: 12, fontWeight: '700', color: '#C9A962' },
  goBtnTextNext: { color: '#000' },
  archiveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, marginTop: 6, borderTopWidth: 1, borderTopColor: '#1C1C1E' },
  archiveBtnText: { fontSize: 13, color: '#FF3B30', fontWeight: '600' },

  // Archived
  archivedSection: { marginTop: 20, marginBottom: 16 },
  archivedTitle: { fontSize: 13, fontWeight: '700', color: '#555', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 },
  archivedRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  archivedName: { fontSize: 14, color: '#555' },
  archivedMeta: { fontSize: 12, color: '#3A3A3C' },

  // Reference
  refCard: { backgroundColor: '#0D0D0D', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#1C1C1E', marginTop: 8 },
  refTitle: { fontSize: 13, fontWeight: '700', color: '#FFF', marginBottom: 10 },
  refRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  refText: { fontSize: 12, color: '#555', flex: 1 },
});
