import React, { useState, useEffect } from 'react';
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
const IS_WEB = Platform.OS === 'web';

interface LeadSource {
  id: string;
  name: string;
  description: string;
  team_id: string;
  assignment_method: 'jump_ball' | 'round_robin' | 'weighted_round_robin';
  webhook_url: string;
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
  
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    team_id: '',
    assignment_method: 'jump_ball' as 'jump_ball' | 'round_robin' | 'weighted_round_robin',
    is_active: true,
  });

  useEffect(() => {
    if (id) {
      fetchData();
    }
  }, [id]);

  const fetchData = async () => {
    try {
      const [sourceRes, statsRes, teamsRes] = await Promise.all([
        api.get(`/lead-sources/${id}`),
        api.get(`/lead-sources/stats/${id}`),
        api.get(`/admin/team/shared-inboxes?user_id=${user?._id}`),
      ]);
      
      if (sourceRes.data.success) {
        const sourceData = sourceRes.data.lead_source;
        setSource(sourceData);
        setFormData({
          name: sourceData.name,
          description: sourceData.description || '',
          team_id: sourceData.team_id,
          assignment_method: sourceData.assignment_method,
          is_active: sourceData.is_active,
        });
      }
      
      if (statsRes.data.success) {
        setStats(statsRes.data.stats);
      }
      
      // Teams data is an array directly
      const teamsData = Array.isArray(teamsRes.data) ? teamsRes.data : [];
      setTeams(teamsData.map((t: any) => ({ id: t._id || t.id, name: t.name })));
    } catch (error) {
      console.error('Error fetching lead source:', error);
      Alert.alert('Error', 'Failed to load lead source');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      if (IS_WEB) {
        showToast('Name is required', 'error');
      } else {
        Alert.alert('Error', 'Name is required');
      }
      return;
    }

    setSaving(true);
    try {
      const response = await api.patch(`/lead-sources/${id}`, formData);
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
        Alert.alert('Error', 'Failed to update lead source');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    if (IS_WEB) {
      setShowDeleteModal(true);
    } else {
      Alert.alert(
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
        Alert.alert('Deleted', 'Lead source has been deleted');
        router.back();
      }
    } catch (error) {
      console.error('Error deleting lead source:', error);
      if (IS_WEB) {
        showToast('Failed to delete lead source', 'error');
        setShowDeleteModal(false);
      } else {
        Alert.alert('Error', 'Failed to delete lead source');
      }
    } finally {
      setDeleting(false);
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        if (IS_WEB) {
          showToast(`${label} copied to clipboard`, 'success');
        } else {
          showToast('${label} copied to clipboard');
        }
      }
    } catch (error) {
      if (IS_WEB) {
        showToast('Could not copy to clipboard', 'error');
      } else {
        Alert.alert('Error', 'Could not copy to clipboard');
      }
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
