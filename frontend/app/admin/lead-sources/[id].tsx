import React, { useState, useEffect } from 'react';
import { copyToClipboard as copyTextNative } from '../../../utils/clipboard';
import { showAlert } from '../../../services/alert';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Pressable,
  TextInput,
  ScrollView,
  ActivityIndicator,
  Alert,
  Platform,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../../store/authStore';
import api from '../../../services/api';
import { useToast } from '../../../components/common/Toast';

import { useThemeStore } from '../../../store/themeStore';
import { ContactModeToggle, LeadCallLadder, WebsiteFormRouting, type CallAttempt } from '../../../components/admin/LeadWorkflowControls';
import { AfterHoursRule, TestLeadCard, QueueTimers, type StoreHours } from '../../../components/admin/LeadTimingControls';
const IS_WEB = Platform.OS === 'web';

interface LeadSource {
  id: string;
  name: string;
  description: string;
  team_id: string;
  assignment_method: 'jump_ball' | 'round_robin' | 'weighted_round_robin';
  webhook_url: string;
  adf_url?: string;
  email_inbound_url?: string;
  monthly_cost?: number | null;
  api_key: string;
  is_active: boolean;
  lead_count: number;
  created_at: string;
  updated_at: string;
}

interface Stats {
  total_leads: number;
  by_status: Record<string, number>;
  member_lead_counts: Record<string, number>;
  assignment_method: string;
}

interface Team {
  id: string;
  name: string;
}

// Web-safe button component
const WebButton: React.FC<{
  onPress: () => void;
  style?: any;
  children: React.ReactNode;
  disabled?: boolean;
  testID?: string;
}> = ({ onPress, style, children, disabled, testID }) => {
  if (IS_WEB) {
    return (
      <button
        type="button"
        onClick={onPress}
        disabled={disabled}
        data-testid={testID}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          ...style,
        }}
      >
        {children}
      </button>
    );
  }
  return (
    <TouchableOpacity onPress={onPress} style={style} disabled={disabled} data-testid={testID}>
      {children}
    </TouchableOpacity>
  );
};

export default function LeadSourceDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuthStore();
  const { showToast } = useToast();
  
  const [source, setSource] = useState<LeadSource | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // ── Workflow automation state ──────────────────────────────────────────────
  const [workflow, setWorkflow] = useState({
    intake_text: '',
    intake_delay_seconds: 0,
    va_enabled: true,
    va_profile_id: '',
    va_prompt_override: '',
    workflow_user_ids: [] as string[],
    auto_call_on_claim: false,
    claim_timeout_minutes: 5,
    notify_all_on_intake: true,
    contact_mode: 'text_only' as 'text_only' | 'text_and_call',
    call_attempts: [] as CallAttempt[],
    website_default: false,
    website_pages: [] as string[],
    after_hours_mode: 'text_and_ai' as 'text_and_ai' | 'ring_anyway',
    text_window_start: '09:00',
    text_window_end: '20:00',
    timer_green_minutes: 5,
    timer_amber_minutes: 15,
    returning_alert_minutes: 10,
    returning_release_minutes: 30,
    digest_hour: 18,
  });
  const [storeHours, setStoreHours] = useState<StoreHours | null>(null);
  const [websitePages, setWebsitePages] = useState<{ pages: string[]; routed: Record<string, { id: string; name: string }> }>({ pages: [], routed: {} });
  const [workflowUsers, setWorkflowUsers] = useState<any[]>([]);  // All reps to choose from
  const [vaProfiles, setVaProfiles] = useState<any[]>([]);
  const [savingWorkflow, setSavingWorkflow] = useState(false);
  const [showWorkflow, setShowWorkflow] = useState(false);

  const MERGE_FIELDS = [
    { label: '{{first_name}}', desc: "Customer's first name" },
    { label: '{{full_name}}',  desc: 'Full name' },
    { label: '{{vehicle}}',    desc: 'Vehicle of interest' },
    { label: '{{make}}',       desc: 'Vehicle make' },
    { label: '{{model}}',      desc: 'Vehicle model' },
    { label: '{{year}}',       desc: 'Model year' },
    { label: '{{lead_source}}',desc: 'Source name' },
  ];

  const saveWorkflow = async () => {
    setSavingWorkflow(true);
    try {
      await api.put(`/lead-sources/${id}/workflow`, workflow);
      showToast('Workflow saved', 'success');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Failed to save workflow', 'error');
    } finally {
      setSavingWorkflow(false);
    }
  };

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    team_id: '',
    assignment_method: 'jump_ball' as 'jump_ball' | 'round_robin' | 'weighted_round_robin',
    is_active: true,
    monthly_cost: '',
  });

  useEffect(() => {
    // Wait for auth to hydrate: several requests need user._id (direct URL loads used to 404)
    if (id && user?._id) {
      fetchData();
    }
  }, [id, user?._id]);

  const fetchData = async () => {
    try {
      const [sourceRes, statsRes, teamsRes, workflowRes, usersRes, vaRes, pagesRes] = await Promise.all([
        api.get(`/lead-sources/${id}`),
        api.get(`/lead-sources/stats/${id}`),
        api.get(`/admin/team/shared-inboxes?user_id=${user?._id}`),
        api.get(`/lead-sources/${id}/workflow`).catch(() => ({ data: {} })),
        api.get(`/admin/team/users?user_id=${user?._id}`, { headers: { 'X-User-ID': user?._id } }).catch(() => ({ data: [] })),
        api.get('/va-profiles', { headers: { 'X-User-ID': user?._id } }).catch(() => ({ data: { profiles: [] } })),
        api.get('/lead-sources/website-pages').catch(() => ({ data: { pages: [], routed: {} } })),
      ]);
      if (pagesRes.data?.pages) setWebsitePages(pagesRes.data);
      
      if (sourceRes.data.success) {
        const sourceData = sourceRes.data.lead_source;
        setSource(sourceData);
        setFormData({
          name: sourceData.name,
          description: sourceData.description || '',
          team_id: sourceData.team_id,
          assignment_method: sourceData.assignment_method,
          is_active: sourceData.is_active,
          monthly_cost: sourceData.monthly_cost != null ? String(sourceData.monthly_cost) : '',
        });
      }
      
      if (statsRes.data.success) {
        setStats(statsRes.data.stats);
      }

      // Load workflow config
      if (workflowRes.data && Object.keys(workflowRes.data).length > 0) {
        const { store_hours, ...cfg } = workflowRes.data;
        setWorkflow(prev => ({ ...prev, ...cfg }));
        if (store_hours) setStoreHours(store_hours);
      }

      // Load all reps for workflow assignment (scoped to same account)
      const usersArr = Array.isArray(usersRes.data) ? usersRes.data : (usersRes.data?.users || []);
      // Normalize id field — /admin/team/users returns {id} not {_id}
      setWorkflowUsers(usersArr.map((u: any) => ({ ...u, _id: u._id || u.id })));
      
      // Load VA profiles
      setVaProfiles(vaRes.data?.profiles || []);
      
      // Teams data is an array directly
      const teamsData = Array.isArray(teamsRes.data) ? teamsRes.data : [];
      setTeams(teamsData.map((t: any) => ({ id: t._id || t.id, name: t.name })));
    } catch (error) {
      console.error('Error fetching lead source:', error);
      showAlert('Error', 'Failed to load lead source');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      if (IS_WEB) {
        showToast('Name is required', 'error');
      } else {
        showAlert('Error', 'Name is required');
      }
      return;
    }

    setSaving(true);
    try {
      const response = await api.patch(`/lead-sources/${id}`, {
        ...formData,
        monthly_cost: formData.monthly_cost !== '' ? parseFloat(formData.monthly_cost) || 0 : undefined,
      });
      if (response.data.success) {
        setSource(response.data.lead_source);
        setEditing(false);
        if (IS_WEB) {
          showToast('Lead source updated successfully', 'success');
        } else {
          showToast('Lead source updated');
        }
      }
    } catch (error) {
      console.error('Error updating lead source:', error);
      if (IS_WEB) {
        showToast('Failed to update lead source', 'error');
      } else {
        showAlert('Error', 'Failed to update lead source');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    if (IS_WEB) {
      setShowDeleteModal(true);
    } else {
      showAlert(
        'Delete Lead Source',
        `Are you sure you want to delete "${source?.name}"? This action cannot be undone.`,
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Delete',
            style: 'destructive',
            onPress: confirmDelete,
          },
        ]
      );
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/lead-sources/${id}`);
      if (IS_WEB) {
        showToast('Lead source deleted', 'success');
        setShowDeleteModal(false);
        setTimeout(() => router.back(), 500);
      } else {
        showAlert('Deleted', 'Lead source has been deleted');
        router.back();
      }
    } catch (error) {
      console.error('Error deleting lead source:', error);
      if (IS_WEB) {
        showToast('Failed to delete lead source', 'error');
        setShowDeleteModal(false);
      } else {
        showAlert('Error', 'Failed to delete lead source');
      }
    } finally {
      setDeleting(false);
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    const ok = await copyTextNative(text);
    if (ok) {
      showToast(`${label} copied to clipboard`, 'success');
    } else if (IS_WEB) {
      showToast('Could not copy to clipboard', 'error');
    } else {
      showAlert('Error', 'Could not copy to clipboard');
    }
  };

  const getAssignmentLabel = (method: string) => {
    switch (method) {
      case 'jump_ball': return 'Jump Ball';
      case 'round_robin': return 'Round Robin';
      case 'weighted_round_robin': return 'Weighted Round Robin';
      default: return method;
    }
  };

  const getAssignmentColor = (method: string) => {
    switch (method) {
      case 'jump_ball': return '#FF9500';
      case 'round_robin': return '#007AFF';
      case 'weighted_round_robin': return '#34C759';
      default: return colors.textSecondary;
    }
  };

  const assignmentMethods = [
    { id: 'jump_ball', name: 'Jump Ball', icon: 'flash', color: '#FF9500' },
    { id: 'round_robin', name: 'Round Robin', icon: 'sync', color: '#007AFF' },
    { id: 'weighted_round_robin', name: 'Weighted', icon: 'scale', color: '#34C759' },
  ];

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  if (!source) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#FF3B30" />
          <Text style={styles.errorText}>Lead source not found</Text>
          <TouchableOpacity onPress={() => router.back()} style={styles.backLink}>
            <Text style={styles.backLinkText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <WebButton onPress={() => router.back()} style={styles.backButton} testID="back-btn">
          <View style={styles.backButtonInner}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </View>
        </WebButton>
        <Text style={styles.title} numberOfLines={1}>{editing ? 'Edit Source' : source.name}</Text>
        {editing ? (
          <WebButton onPress={handleSave} disabled={saving} testID="save-btn">
            <View style={styles.saveButtonInner}>
              {saving ? (
                <ActivityIndicator size="small" color="#007AFF" />
              ) : (
                <Text style={styles.saveButtonText}>Save</Text>
              )}
            </View>
          </WebButton>
        ) : (
          <WebButton onPress={() => setEditing(true)} testID="edit-btn">
            <View style={styles.editButtonInner}>
              <Text style={styles.editButtonText}>Edit</Text>
            </View>
          </WebButton>
        )}
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentContainer}>
        {/* Status Badge */}
        <View style={styles.statusContainer}>
          <View style={[styles.statusBadge, { backgroundColor: source.is_active ? '#34C75920' : '#FF3B3020' }]}>
            <View style={[styles.statusDot, { backgroundColor: source.is_active ? '#34C759' : '#FF3B30' }]} />
            <Text style={[styles.statusText, { color: source.is_active ? '#34C759' : '#FF3B30' }]}>
              {source.is_active ? 'Active' : 'Inactive'}
            </Text>
          </View>
          <View style={[styles.methodBadge, { backgroundColor: getAssignmentColor(source.assignment_method) + '20' }]}>
            <Text style={[styles.methodText, { color: getAssignmentColor(source.assignment_method) }]}>
              {getAssignmentLabel(source.assignment_method)}
            </Text>
          </View>
        </View>

        {editing ? (
          // Edit Form
          <>
            <View style={styles.section}>
              <Text style={styles.label}>SOURCE NAME</Text>
              <TextInput
                style={styles.input}
                value={formData.name}
                onChangeText={(text) => setFormData({ ...formData, name: text })}
                placeholder="Lead source name"
                placeholderTextColor="#6E6E73"
              />
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>DESCRIPTION</Text>
              <TextInput
                style={[styles.input, styles.textArea]}
                value={formData.description}
                onChangeText={(text) => setFormData({ ...formData, description: text })}
                placeholder="Optional description..."
                placeholderTextColor="#6E6E73"
                multiline
                numberOfLines={3}
              />
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>MONTHLY COST ($)</Text>
              <TextInput
                style={styles.input}
                value={formData.monthly_cost}
                onChangeText={(text) => setFormData({ ...formData, monthly_cost: text.replace(/[^0-9.]/g, '') })}
                placeholder="e.g. 1200 — powers cost-per-sale in Source ROI"
                placeholderTextColor="#6E6E73"
                keyboardType="decimal-pad"
                testID="monthly-cost-input" dataSet={{ testid: 'monthly-cost-input' } as any}
              />
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>TEAM</Text>
              <View style={styles.teamsContainer}>
                {teams.map((team) => (
                  <TouchableOpacity
                    key={team.id}
                    style={[styles.teamOption, formData.team_id === team.id && styles.teamOptionSelected]}
                    onPress={() => setFormData({ ...formData, team_id: team.id })}
                  >
                    <Ionicons
                      name={formData.team_id === team.id ? 'radio-button-on' : 'radio-button-off'}
                      size={20}
                      color={formData.team_id === team.id ? '#007AFF' : colors.textSecondary}
                    />
                    <Text style={[styles.teamOptionText, formData.team_id === team.id && styles.teamOptionTextSelected]}>
                      {team.name}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>ASSIGNMENT METHOD</Text>
              <View style={styles.methodsRow}>
                {assignmentMethods.map((method) => (
                  <TouchableOpacity
                    key={method.id}
                    style={[
                      styles.methodOption,
                      formData.assignment_method === method.id && styles.methodOptionSelected,
                      formData.assignment_method === method.id && { borderColor: method.color },
                    ]}
                    onPress={() => setFormData({ ...formData, assignment_method: method.id as any })}
                  >
                    <Ionicons name={method.icon as any} size={20} color={method.color} />
                    <Text style={[styles.methodOptionText, { color: formData.assignment_method === method.id ? method.color : colors.textSecondary }]}>
                      {method.name}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <View style={styles.section}>
              <View style={styles.toggleRow}>
                <Text style={styles.toggleLabel}>Active</Text>
                <TouchableOpacity
                  style={[styles.toggle, formData.is_active && styles.toggleActive]}
                  onPress={() => setFormData({ ...formData, is_active: !formData.is_active })}
                >
                  <View style={[styles.toggleKnob, formData.is_active && styles.toggleKnobActive]} />
                </TouchableOpacity>
              </View>
            </View>

            <TouchableOpacity style={styles.cancelButton} onPress={() => setEditing(false)}>
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
          </>
        ) : (
          // View Mode
          <>
            {/* Stats */}
            <View style={styles.statsGrid}>
              <View style={styles.statCard}>
                <Ionicons name="people" size={24} color="#007AFF" />
                <Text style={styles.statValue}>{stats?.total_leads || source.lead_count}</Text>
                <Text style={styles.statLabel}>Total Leads</Text>
              </View>
              <View style={styles.statCard}>
                <Ionicons name="checkmark-circle" size={24} color="#34C759" />
                <Text style={styles.statValue}>{stats?.by_status?.new || 0}</Text>
                <Text style={styles.statLabel}>New</Text>
              </View>
              <View style={styles.statCard}>
                <Ionicons name="chatbubble" size={24} color="#FF9500" />
                <Text style={styles.statValue}>{stats?.by_status?.contacted || 0}</Text>
                <Text style={styles.statLabel}>Contacted</Text>
              </View>
            </View>

            {/* Webhook URL */}
            <View style={styles.credentialSection}>
              <View style={styles.credentialHeader}>
                <Ionicons name="link" size={20} color="#007AFF" />
                <Text style={styles.credentialTitle}>Webhook URL</Text>
              </View>
              <TouchableOpacity
                style={styles.credentialBox}
                onPress={() => copyToClipboard(source.webhook_url, 'Webhook URL')}
              >
                <Text style={styles.credentialValue} numberOfLines={2}>{source.webhook_url}</Text>
                <Ionicons name="copy-outline" size={18} color="#007AFF" />
              </TouchableOpacity>
              <Text style={styles.credentialHint}>POST leads to this URL</Text>
            </View>

            {/* ADF / XML URL */}
            {source.adf_url && (
              <View style={styles.credentialSection}>
                <View style={styles.credentialHeader}>
                  <Ionicons name="code-slash" size={20} color="#34C759" />
                  <Text style={styles.credentialTitle}>ADF / XML URL</Text>
                </View>
                <TouchableOpacity
                  style={styles.credentialBox}
                  onPress={() => copyToClipboard(source.adf_url!, 'ADF URL')}
                  testID="adf-url-copy" dataSet={{ testid: 'adf-url-copy' } as any}
                >
                  <Text style={styles.credentialValue} numberOfLines={2}>{source.adf_url}</Text>
                  <Ionicons name="copy-outline" size={18} color="#007AFF" />
                </TouchableOpacity>
                <Text style={styles.credentialHint}>
                  For Cars.com, AutoTrader, CarGurus & OEM portals that POST ADF XML directly
                </Text>
              </View>
            )}

            {/* Email Intake URL */}
            {source.email_inbound_url && (
              <View style={styles.credentialSection}>
                <View style={styles.credentialHeader}>
                  <Ionicons name="mail" size={20} color="#AF52DE" />
                  <Text style={styles.credentialTitle}>Email Lead Intake</Text>
                </View>
                <TouchableOpacity
                  style={styles.credentialBox}
                  onPress={() => copyToClipboard(source.email_inbound_url!, 'Email Intake URL')}
                  testID="email-intake-url-copy" dataSet={{ testid: 'email-intake-url-copy' } as any}
                >
                  <Text style={styles.credentialValue} numberOfLines={2}>{source.email_inbound_url}</Text>
                  <Ionicons name="copy-outline" size={18} color="#007AFF" />
                </TouchableOpacity>
                <Text style={styles.credentialHint}>
                  For providers that deliver leads by EMAIL: create a free inbound address on
                  CloudMailin or SendGrid Inbound Parse, point it at this URL, then give that
                  email address to your lead provider. ADF XML is auto-extracted from the email
                  body or attachments.
                </Text>
              </View>
            )}

            {/* API Key */}
            <View style={styles.credentialSection}>
              <View style={styles.credentialHeader}>
                <Ionicons name="key" size={20} color="#FF9500" />
                <Text style={styles.credentialTitle}>API Key</Text>
              </View>
              <View style={styles.apiKeyRow}>
                <TouchableOpacity
                  style={[styles.credentialBox, { flex: 1 }]}
                  onPress={() => copyToClipboard(source.api_key, 'API Key')}
                >
                  <Text style={styles.credentialValue} numberOfLines={1}>
                    {showApiKey ? source.api_key : '••••••••••••••••••••••••••••••••'}
                  </Text>
                  <Ionicons name="copy-outline" size={18} color="#007AFF" />
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.eyeButton}
                  onPress={() => setShowApiKey(!showApiKey)}
                >
                  <Ionicons name={showApiKey ? 'eye-off' : 'eye'} size={20} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
              <Text style={styles.credentialHint}>Include as X-API-Key header</Text>
            </View>

            {/* Example Request */}
            <View style={styles.exampleSection}>
              <Text style={styles.sectionTitle}>Example Request</Text>
              <View style={styles.codeBlock}>
                <Text style={styles.codeText}>
{`curl -X POST "${source.webhook_url}" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -d '{
    "name": "John Doe",
    "phone": "+15551234567",
    "email": "john@example.com",
    "notes": "Interested in SUV"
  }'`}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.copyExampleButton}
                onPress={() => copyToClipboard(
                  `curl -X POST "${source.webhook_url}" -H "Content-Type: application/json" -H "X-API-Key: ${source.api_key}" -d '{"name": "John Doe", "phone": "+15551234567", "email": "john@example.com", "notes": "Interested in SUV"}'`,
                  'Example'
                )}
              >
                <Ionicons name="clipboard-outline" size={16} color="#007AFF" />
                <Text style={styles.copyExampleText}>Copy Example</Text>
              </TouchableOpacity>
            </View>

            {/* Description */}
            {source.description && (
              <View style={styles.descriptionSection}>
                <Text style={styles.sectionTitle}>Description</Text>
                <Text style={styles.descriptionText}>{source.description}</Text>
              </View>
            )}

            {/* Delete Button */}
            <WebButton onPress={handleDelete} testID="delete-btn">
              <View style={styles.deleteButton}>
                <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                <Text style={styles.deleteButtonText}>Delete Lead Source</Text>
              </View>
            </WebButton>
          </>
        )}

        {/* ── WORKFLOW AUTOMATION SECTION ────────────────────────────────── */}
        <View style={[styles.section, { marginTop: 8 }]}>
          <TouchableOpacity
            onPress={() => setShowWorkflow(v => !v)}
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}
            testID="workflow-toggle" dataSet={{ testid: 'workflow-toggle' } as any}
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="flash" size={18} color="#C9A962" />
              </View>
              <View>
                <Text style={[styles.sectionTitle, { marginBottom: 0 }]}>Response Workflow</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                  {workflow.intake_text ? '✓ Intake text set' : 'No intake text'} · {workflow.workflow_user_ids.length} reps · {workflow.contact_mode === 'text_and_call' ? `Text + Call (${workflow.call_attempts.length} attempts)` : 'Text only'}{workflow.website_default ? ' · Website catch-all' : workflow.website_pages.length ? ` · ${workflow.website_pages.length} web pages` : ''}{workflow.after_hours_mode === 'text_and_ai' ? ' · After hours: Jessi' : ''}
                </Text>
              </View>
            </View>
            <Ionicons name={showWorkflow ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
          </TouchableOpacity>

          {showWorkflow && (
            <View style={{ marginTop: 16, gap: 20 }}>

              {/* ── Instant Intake Text ───────────────────────────── */}
              <View>
                <Text style={styles.label}>Instant Intake Text</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 8 }}>
                  Sent the moment a lead arrives. Tap a field below to insert it.
                </Text>
                {/* Merge field chips */}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                  {MERGE_FIELDS.map(f => (
                    <TouchableOpacity
                      key={f.label}
                      onPress={() => setWorkflow(prev => ({ ...prev, intake_text: (prev.intake_text || '') + f.label }))}
                      style={{ backgroundColor: colors.surface, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1, borderColor: colors.border }}
                    >
                      <Text style={{ fontSize: 11, fontWeight: '700', color: '#C9A962', fontFamily: 'monospace' }}>{f.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <TextInput
                  style={[styles.input, { height: 100, textAlignVertical: 'top' }]}
                  value={workflow.intake_text}
                  onChangeText={v => setWorkflow(prev => ({ ...prev, intake_text: v }))}
                  multiline
                  placeholder={`Hey {{first_name}}! I saw you were interested in the {{vehicle}}. This is {{rep_name}} from the dealership — what questions do you have?`}
                  placeholderTextColor={colors.textSecondary}
                  testID="intake-text-input" dataSet={{ testid: 'intake-text-input' } as any}
                />
              </View>

              {/* ── Workflow Reps ─────────────────────────────────── */}
              <View>
                <Text style={styles.label}>Notify These Reps (first to reply claims the lead)</Text>
                {workflowUsers.filter((u: any) => u.role !== 'super_admin' || u._id === user?._id).map((u: any) => {
                  const uid = u._id || u.id;
                  const isSelected = workflow.workflow_user_ids.includes(uid);
                  return (
                    <TouchableOpacity
                      key={uid}
                      onPress={() => setWorkflow(prev => ({
                        ...prev,
                        workflow_user_ids: isSelected
                          ? prev.workflow_user_ids.filter(id => id !== uid)
                          : [...prev.workflow_user_ids, uid],
                      }))}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }}
                    >
                      <View style={{ width: 22, height: 22, borderRadius: 6, backgroundColor: isSelected ? '#34C759' : colors.surface, borderWidth: 1.5, borderColor: isSelected ? '#34C759' : colors.border, alignItems: 'center', justifyContent: 'center' }}>
                        {isSelected && <Ionicons name="checkmark" size={14} color="#fff" />}
                      </View>
                      <Text style={{ color: colors.text, fontSize: 15, flex: 1 }}>{u.name || u.email}</Text>
                      <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{u.role}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {/* ── Customer contact mode + call ladder ───────────── */}
              <ContactModeToggle
                value={workflow.contact_mode}
                onChange={v => setWorkflow(prev => ({
                  ...prev,
                  contact_mode: v,
                  call_attempts: v === 'text_and_call' && prev.call_attempts.length === 0
                    ? [{ user_ids: [...prev.workflow_user_ids], delay_seconds: 60 }]
                    : prev.call_attempts,
                }))}
                colors={colors}
              />
              {workflow.contact_mode === 'text_and_call' && (
                <LeadCallLadder
                  attempts={workflow.call_attempts}
                  reps={workflowUsers.filter((u: any) => u.role !== 'super_admin' || u._id === user?._id)}
                  onChange={a => setWorkflow(prev => ({ ...prev, call_attempts: a }))}
                  colors={colors}
                />
              )}

              {/* ── After-hours rule + TCPA texting window ────────── */}
              <AfterHoursRule
                mode={workflow.after_hours_mode}
                windowStart={workflow.text_window_start}
                windowEnd={workflow.text_window_end}
                storeHours={storeHours}
                onChange={patch => setWorkflow(prev => ({ ...prev, ...patch }))}
                onEditHours={() => router.push('/settings/store-profile' as any)}
                colors={colors}
              />

              {/* ── Shared queue timers + returning-customer safety net + digest ── */}
              <QueueTimers
                values={workflow}
                onChange={patch => setWorkflow(prev => ({ ...prev, ...patch }))}
                colors={colors}
              />

              {/* ── Website form routing ──────────────────────────── */}
              <WebsiteFormRouting
                isDefault={workflow.website_default}
                pages={workflow.website_pages}
                allPages={websitePages.pages}
                routed={websitePages.routed}
                sourceId={String(id)}
                onChange={patch => setWorkflow(prev => ({ ...prev, ...patch }))}
                colors={colors}
              />

              {/* ── Auto-Call Toggle ──────────────────────────────── */}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 4 }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.label}>Auto-Call on Claim</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                    When a rep claims this lead, Twilio immediately bridges them to the customer
                  </Text>
                </View>
                <TouchableOpacity
                  onPress={() => setWorkflow(prev => ({ ...prev, auto_call_on_claim: !prev.auto_call_on_claim }))}
                  style={{ width: 50, height: 28, borderRadius: 14, backgroundColor: workflow.auto_call_on_claim ? '#34C759' : colors.surface, borderWidth: 1, borderColor: workflow.auto_call_on_claim ? '#34C759' : colors.border, justifyContent: 'center', paddingHorizontal: 3 }}
                  testID="auto-call-toggle" dataSet={{ testid: 'auto-call-toggle' } as any}
                >
                  <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: '#fff', transform: [{ translateX: workflow.auto_call_on_claim ? 22 : 0 }] }} />
                </TouchableOpacity>
              </View>

              {/* ── VA Toggle ─────────────────────────────────────── */}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 4 }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.label}>Enable AI Auto-Reply (Jessi)</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                    AI handles the conversation after intake text fires
                  </Text>
                </View>
                <TouchableOpacity
                  onPress={() => setWorkflow(prev => ({ ...prev, va_enabled: !prev.va_enabled }))}
                  style={{ width: 50, height: 28, borderRadius: 14, backgroundColor: workflow.va_enabled ? '#007AFF' : colors.surface, borderWidth: 1, borderColor: workflow.va_enabled ? '#007AFF' : colors.border, justifyContent: 'center', paddingHorizontal: 3 }}
                  testID="va-enabled-toggle" dataSet={{ testid: 'va-enabled-toggle' } as any}
                >
                  <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: '#fff', transform: [{ translateX: workflow.va_enabled ? 22 : 0 }] }} />
                </TouchableOpacity>
              </View>

              {/* ── Custom VA Prompt for this Source ──────────────── */}
              {workflow.va_enabled && (
                <View>
                  <Text style={styles.label}>VA Profile for this Source</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 8 }}>
                    Pick a VA persona to handle leads from this source.
                  </Text>

                  {vaProfiles.length === 0 ? (
                    <TouchableOpacity
                      onPress={() => router.push('/admin/va-library')}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.surface, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border, marginBottom: 10 }}
                    >
                      <Ionicons name="person-circle-outline" size={18} color={colors.accent} />
                      <Text style={{ color: colors.accent, fontWeight: '600', fontSize: 14 }}>Create a VA in VA Library first →</Text>
                    </TouchableOpacity>
                  ) : (
                    <View style={{ gap: 8, marginBottom: 12 }}>
                      {/* "No VA" option */}
                      <TouchableOpacity
                        onPress={() => setWorkflow(prev => ({ ...prev, va_profile_id: '' }))}
                        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 10, backgroundColor: !workflow.va_profile_id ? colors.accent + '20' : colors.surface, borderWidth: 1, borderColor: !workflow.va_profile_id ? colors.accent : colors.border }}
                        testID="va-none-option" dataSet={{ testid: 'va-none-option' } as any}
                      >
                        <Ionicons name="close-circle-outline" size={18} color={!workflow.va_profile_id ? colors.accent : colors.textSecondary} />
                        <Text style={{ color: !workflow.va_profile_id ? colors.accent : colors.text, fontWeight: '600' }}>No VA (use default Jessi)</Text>
                      </TouchableOpacity>

                      {vaProfiles.map((va: any) => (
                        <TouchableOpacity
                          key={va._id}
                          onPress={() => setWorkflow(prev => ({ ...prev, va_profile_id: va._id }))}
                          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 10, backgroundColor: workflow.va_profile_id === va._id ? (va.avatar_color || colors.accent) + '20' : colors.surface, borderWidth: 1, borderColor: workflow.va_profile_id === va._id ? (va.avatar_color || colors.accent) : colors.border }}
                          testID={`va-option-${va._id}`} dataSet={{ testid: `va-option-${va._id}` } as any}
                        >
                          <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: (va.avatar_color || '#C9A962') + '30', alignItems: 'center', justifyContent: 'center' }}>
                            <Text style={{ color: va.avatar_color || '#C9A962', fontWeight: '800', fontSize: 14 }}>{(va.name || 'V').charAt(0)}</Text>
                          </View>
                          <View style={{ flex: 1 }}>
                            <Text style={{ color: colors.text, fontWeight: '600' }}>{va.name}</Text>
                            {va.tagline ? <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{va.tagline}</Text> : null}
                          </View>
                          {workflow.va_profile_id === va._id && <Ionicons name="checkmark-circle" size={20} color={va.avatar_color || colors.accent} />}
                        </TouchableOpacity>
                      ))}

                      <TouchableOpacity
                        onPress={() => router.push('/admin/va-library')}
                        style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingTop: 4 }}
                      >
                        <Ionicons name="add-circle-outline" size={15} color={colors.textSecondary} />
                        <Text style={{ color: colors.textSecondary, fontSize: 13 }}>Manage VA Library</Text>
                      </TouchableOpacity>
                    </View>
                  )}

                  <Text style={[styles.label, { fontSize: 13, marginTop: 0 }]}>Custom Instructions (optional)</Text>
                  <TextInput
                    style={[styles.input, { height: 80, textAlignVertical: 'top' }]}
                    value={workflow.va_prompt_override || ''}
                    onChangeText={v => setWorkflow(prev => ({ ...prev, va_prompt_override: v }))}
                    multiline
                    placeholder="Optional: extra context specific to this lead source (e.g. 'These are trade-in leads — focus on current vehicle and timeline')."
                    placeholderTextColor={colors.textSecondary}
                  />
                </View>
              )}

              {/* ── Save Button ───────────────────────────────────── */}
              <WebButton
                onPress={saveWorkflow}
                disabled={savingWorkflow}
                style={{ backgroundColor: '#C9A962', borderRadius: 12, padding: 14, alignItems: 'center' }}
                testID="save-workflow-btn"
              >
                {savingWorkflow
                  ? <ActivityIndicator size="small" color="#000" />
                  : <Text style={{ color: '#000', fontWeight: '700', fontSize: 15 }}>Save Workflow</Text>
                }
              </WebButton>

              {/* ── Send a test lead through this workflow ────────── */}
              <TestLeadCard
                sourceId={String(id)}
                defaultPhone={(user as any)?.phone || ''}
                contactMode={workflow.contact_mode}
                hasIntakeText={!!workflow.intake_text?.trim()}
                colors={colors}
                onOpenThread={convId => router.push(`/thread/${convId}` as any)}
              />

            </View>
          )}
        </View>

      </ScrollView>

      {/* Delete Confirmation Modal (for web) */}
      {IS_WEB && (
        <Modal
          visible={showDeleteModal}
          transparent
          animationType="fade"
          onRequestClose={() => setShowDeleteModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalIconContainer}>
                <Ionicons name="warning" size={48} color="#FF3B30" />
              </View>
              <Text style={styles.modalTitle}>Delete Lead Source?</Text>
              <Text style={styles.modalMessage}>
                Are you sure you want to delete "{source?.name}"? This action cannot be undone.
              </Text>
              <View style={styles.modalButtons}>
                {IS_WEB ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setShowDeleteModal(false)}
                      disabled={deleting}
                      style={{
                        flex: 1,
                        backgroundColor: colors.surface,
                        borderRadius: 10,
                        padding: 14,
                        border: 'none',
                        cursor: deleting ? 'not-allowed' : 'pointer',
                        opacity: deleting ? 0.5 : 1,
                      }}
                    >
                      <Text style={styles.modalCancelText}>Cancel</Text>
                    </button>
                    <button
                      type="button"
                      onClick={confirmDelete}
                      disabled={deleting}
                      data-testid="confirm-delete-btn"
                      style={{
                        flex: 1,
                        backgroundColor: '#FF3B30',
                        borderRadius: 10,
                        padding: 14,
                        border: 'none',
                        cursor: deleting ? 'not-allowed' : 'pointer',
                        opacity: deleting ? 0.5 : 1,
                      }}
                    >
                      {deleting ? (
                        <ActivityIndicator size="small" color={colors.text} />
                      ) : (
                        <Text style={styles.modalDeleteText}>Delete</Text>
                      )}
                    </button>
                  </>
                ) : (
                  <>
                    <Pressable
                      style={styles.modalCancelButton}
                      onPress={() => setShowDeleteModal(false)}
                      disabled={deleting}
                    >
                      <Text style={styles.modalCancelText}>Cancel</Text>
                    </Pressable>
                    <Pressable
                      style={styles.modalDeleteButton}
                      onPress={confirmDelete}
                      disabled={deleting}
                    >
                      {deleting ? (
                        <ActivityIndicator size="small" color={colors.text} />
                      ) : (
                        <Text style={styles.modalDeleteText}>Delete</Text>
                      )}
                    </Pressable>
                  </>
                )}
              </View>
            </View>
          </View>
        </Modal>
      )}
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
    padding: 32,
  },
  errorText: {
    fontSize: 19,
    color: colors.text,
    marginTop: 16,
    marginBottom: 24,
  },
  backLink: {
    padding: 12,
  },
  backLinkText: {
    color: '#007AFF',
    fontSize: 18,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  backButtonInner: {
    padding: 4,
  },
  title: {
    flex: 1,
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
    textAlign: 'center',
    marginHorizontal: 8,
  },
  saveButtonInner: {
    padding: 4,
  },
  saveButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
  editButtonInner: {
    padding: 4,
  },
  editButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#007AFF',
  },
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 40,
  },
  statusContainer: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 20,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 15,
    fontWeight: '600',
  },
  methodBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  methodText: {
    fontSize: 15,
    fontWeight: '600',
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    gap: 8,
  },
  statValue: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
  },
  statLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  credentialSection: {
    marginBottom: 20,
  },
  credentialHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  credentialTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  credentialBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    gap: 12,
  },
  credentialValue: {
    flex: 1,
    fontSize: 15,
    color: colors.text,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  credentialHint: {
    fontSize: 14,
    color: '#6E6E73',
    marginTop: 6,
    marginLeft: 4,
  },
  apiKeyRow: {
    flexDirection: 'row',
    gap: 8,
  },
  eyeButton: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    justifyContent: 'center',
  },
  exampleSection: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 12,
  },
  codeBlock: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
  },
  codeText: {
    fontSize: 14,
    color: '#34C759',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    lineHeight: 18,
  },
  copyExampleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 8,
    padding: 8,
  },
  copyExampleText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
  descriptionSection: {
    marginBottom: 20,
  },
  descriptionText: {
    fontSize: 17,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  deleteButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF3B3015',
    borderRadius: 12,
    padding: 16,
    gap: 8,
    marginTop: 20,
  },
  deleteButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FF3B30',
  },
  // Edit form styles
  section: {
    marginBottom: 24,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    letterSpacing: 0.5,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
  teamsContainer: {
    gap: 8,
  },
  teamOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    gap: 12,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  teamOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF10',
  },
  teamOptionText: {
    fontSize: 18,
    color: colors.text,
  },
  teamOptionTextSelected: {
    color: '#007AFF',
  },
  methodsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  methodOption: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    gap: 6,
    borderWidth: 2,
    borderColor: colors.surface,
  },
  methodOptionSelected: {
    backgroundColor: colors.card,
  },
  methodOptionText: {
    fontSize: 13,
    fontWeight: '600',
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
  },
  toggleLabel: {
    fontSize: 18,
    color: colors.text,
  },
  toggle: {
    width: 51,
    height: 31,
    borderRadius: 16,
    backgroundColor: colors.borderLight,
    padding: 2,
  },
  toggleActive: {
    backgroundColor: '#34C759',
  },
  toggleKnob: {
    width: 27,
    height: 27,
    borderRadius: 14,
    backgroundColor: colors.card,
  },
  toggleKnobActive: {
    transform: [{ translateX: 20 }],
  },
  cancelButton: {
    alignItems: 'center',
    padding: 16,
    marginTop: 8,
  },
  cancelButtonText: {
    fontSize: 18,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 24,
    width: '100%',
    maxWidth: 400,
    alignItems: 'center',
  },
  modalIconContainer: {
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 21,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
    textAlign: 'center',
  },
  modalMessage: {
    fontSize: 17,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    width: '100%',
  },
  modalCancelButton: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  modalDeleteButton: {
    flex: 1,
    backgroundColor: '#FF3B30',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  modalDeleteText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
});
