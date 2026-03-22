import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Platform,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { permissionTemplatesAPI } from '../services/api';
import { adminAPI } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { WebModal } from '../components/WebModal';

const ROLE_OPTIONS = [
  { value: 'user', label: 'Sales Rep', color: '#007AFF', icon: 'person' },
  { value: 'store_manager', label: 'Store Manager', color: '#34C759', icon: 'shield-checkmark' },
  { value: 'org_admin', label: 'Org Admin', color: '#AF52DE', icon: 'business' },
];

const ICON_OPTIONS = ['person', 'people', 'star', 'shield-checkmark', 'business', 'rocket', 'trophy', 'flash'];
const COLOR_OPTIONS = ['#007AFF', '#34C759', '#FF9500', '#FF3B30', '#AF52DE', '#C9A962', '#5AC8FA', '#FF2D55'];

const PERMISSION_SECTIONS = [
  {
    key: 'my_tools',
    label: 'My Tools',
    icon: 'construct',
    items: [
      { key: 'touchpoints', label: 'Touchpoints' },
      { key: 'ask_jessi', label: 'Ask Jessi AI' },
      { key: 'training_hub', label: 'Training Hub' },
      { key: 'team_chat', label: 'Team Chat' },
    ],
  },
  {
    key: 'campaigns',
    label: 'Campaigns',
    icon: 'rocket',
    items: [
      { key: 'campaign_builder', label: 'Campaign Builder' },
      { key: 'campaign_dashboard', label: 'Campaign Dashboard' },
      { key: 'broadcast', label: 'Broadcast' },
      { key: 'date_triggers', label: 'Date Triggers' },
    ],
  },
  {
    key: 'content',
    label: 'Content',
    icon: 'document-text',
    items: [
      { key: 'sms_templates', label: 'SMS Templates' },
      { key: 'email_templates', label: 'Email Templates' },
      { key: 'card_templates', label: 'Card Templates' },
      { key: 'manage_showcase', label: 'Manage Showcase' },
    ],
  },
  {
    key: 'insights',
    label: 'Insights',
    icon: 'analytics',
    items: [
      { key: 'my_performance', label: 'My Performance' },
      { key: 'activity_reports', label: 'Activity Reports' },
      { key: 'email_analytics', label: 'Email Analytics' },
      { key: 'leaderboard', label: 'Leaderboard' },
      { key: 'lead_attribution', label: 'Lead Attribution' },
    ],
  },
];

const DEFAULT_PERMISSIONS: Record<string, Record<string, boolean>> = {
  my_tools: { _enabled: true, touchpoints: true, ask_jessi: true, training_hub: true, team_chat: true },
  campaigns: { _enabled: true, campaign_builder: true, campaign_dashboard: true, broadcast: false, date_triggers: false },
  content: { _enabled: true, sms_templates: true, email_templates: true, card_templates: false, manage_showcase: false },
  insights: { _enabled: true, my_performance: true, activity_reports: false, email_analytics: false, leaderboard: false, lead_attribution: false },
};

type Template = {
  id: string;
  _id?: string;
  name: string;
  description: string;
  role: string;
  icon: string;
  color: string;
  is_prebuilt: boolean;
  permissions: Record<string, Record<string, boolean>>;
};

type UserItem = {
  _id: string;
  name: string;
  email: string;
  role: string;
  permission_template?: string;
  store_name?: string;
};

export default function PermissionTemplatesPage() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();

  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [showEditor, setShowEditor] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [saving, setSaving] = useState(false);

  // Editor form state
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formRole, setFormRole] = useState('user');
  const [formIcon, setFormIcon] = useState('person');
  const [formColor, setFormColor] = useState('#007AFF');
  const [formPerms, setFormPerms] = useState<Record<string, Record<string, boolean>>>(JSON.parse(JSON.stringify(DEFAULT_PERMISSIONS)));

  // Apply modal
  const [showApply, setShowApply] = useState(false);
  const [applyTemplate, setApplyTemplate] = useState<Template | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [userSearch, setUserSearch] = useState('');
  const [applying, setApplying] = useState<string | null>(null);

  // Detail view
  const [viewTemplate, setViewTemplate] = useState<Template | null>(null);

  // Audit log
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [showAuditLog, setShowAuditLog] = useState(false);

  const loadTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const data = await permissionTemplatesAPI.list(user?.store_id, user?.organization_id);
      setTemplates(data.templates || []);
    } catch (err) {
      console.error('Failed to load templates:', err);
    } finally {
      setLoading(false);
    }
  }, [user?.store_id, user?.organization_id]);

  useEffect(() => {
    if (user?._id) loadTemplates();
  }, [user?._id, loadTemplates]);

  const loadUsers = async () => {
    if (!user?.organization_id) return;
    try {
      setLoadingUsers(true);
      const data = await adminAPI.listOrgUsers(user.organization_id);
      setUsers(Array.isArray(data) ? data : data.users || []);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadAuditLog = async () => {
    try {
      setLoadingAudit(true);
      const data = await permissionTemplatesAPI.getAuditLog(50);
      setAuditLog(data.entries || []);
    } catch (err) {
      console.error('Failed to load audit log:', err);
    } finally {
      setLoadingAudit(false);
    }
  };

  const openEditor = (template?: Template) => {
    if (template) {
      setEditingTemplate(template);
      setFormName(template.name);
      setFormDesc(template.description || '');
      setFormRole(template.role);
      setFormIcon(template.icon || 'person');
      setFormColor(template.color || '#007AFF');
      setFormPerms(JSON.parse(JSON.stringify(template.permissions || DEFAULT_PERMISSIONS)));
    } else {
      setEditingTemplate(null);
      setFormName('');
      setFormDesc('');
      setFormRole('user');
      setFormIcon('person');
      setFormColor('#007AFF');
      setFormPerms(JSON.parse(JSON.stringify(DEFAULT_PERMISSIONS)));
    }
    setShowEditor(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) {
      window.alert('Please enter a template name');
      return;
    }
    try {
      setSaving(true);
      const payload = {
        name: formName.trim(),
        description: formDesc.trim(),
        role: formRole,
        icon: formIcon,
        color: formColor,
        permissions: formPerms,
      };
      if (editingTemplate && !editingTemplate.is_prebuilt) {
        await permissionTemplatesAPI.update(editingTemplate.id || editingTemplate._id!, payload, user!._id);
      } else {
        await permissionTemplatesAPI.create(payload, user!._id);
      }
      setShowEditor(false);
      loadTemplates();
    } catch (err: any) {
      window.alert(err?.response?.data?.detail || 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (template: Template) => {
    if (template.is_prebuilt) {
      window.alert('Prebuilt templates cannot be deleted');
      return;
    }
    if (window.confirm(`Delete "${template.name}"? This cannot be undone.`)) {
      try {
        await permissionTemplatesAPI.delete(template.id || template._id!, user!._id);
        loadTemplates();
        if (viewTemplate?.id === template.id) setViewTemplate(null);
      } catch (err: any) {
        window.alert(err?.response?.data?.detail || 'Failed to delete');
      }
    }
  };

  const openApply = (template: Template) => {
    setApplyTemplate(template);
    setShowApply(true);
    setUserSearch('');
    loadUsers();
  };

  const handleApply = async (targetUser: UserItem) => {
    if (!applyTemplate) return;
    const templateId = applyTemplate.id || applyTemplate._id!;
    if (!window.confirm(`Apply "${applyTemplate.name}" to ${targetUser.name}?\n\nThis will change their role to ${ROLE_OPTIONS.find(r => r.value === applyTemplate.role)?.label || applyTemplate.role} and update all their feature permissions.`)) return;
    try {
      setApplying(targetUser._id);
      await permissionTemplatesAPI.apply(templateId, targetUser._id, user!._id);
      setShowApply(false);
      window.alert(`Template "${applyTemplate.name}" applied to ${targetUser.name}`);
    } catch (err: any) {
      window.alert(err?.response?.data?.detail || 'Failed to apply template');
    } finally {
      setApplying(null);
    }
  };

  const togglePerm = (section: string, item: string) => {
    setFormPerms(prev => {
      const next = { ...prev };
      next[section] = { ...next[section] };
      next[section][item] = !next[section][item];
      return next;
    });
  };

  const toggleSectionEnabled = (section: string) => {
    setFormPerms(prev => {
      const next = { ...prev };
      next[section] = { ...next[section] };
      next[section]['_enabled'] = !next[section]['_enabled'];
      return next;
    });
  };

  const filteredUsers = users.filter(u =>
    !userSearch || u.name?.toLowerCase().includes(userSearch.toLowerCase()) || u.email?.toLowerCase().includes(userSearch.toLowerCase())
  );

  const getRoleInfo = (role: string) => ROLE_OPTIONS.find(r => r.value === role) || { label: role, color: '#8E8E93', icon: 'person' };

  // ─── Template Detail View ───
  const renderDetailView = () => {
    if (!viewTemplate) return null;
    const roleInfo = getRoleInfo(viewTemplate.role);
    return (
      <WebModal visible={!!viewTemplate} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modal}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setViewTemplate(null)} data-testid="detail-close-btn">
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={s.modalTitle}>{viewTemplate.name}</Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {!viewTemplate.is_prebuilt && (
                <TouchableOpacity onPress={() => { setViewTemplate(null); openEditor(viewTemplate); }} data-testid="detail-edit-btn">
                  <Ionicons name="create-outline" size={22} color="#007AFF" />
                </TouchableOpacity>
              )}
              <TouchableOpacity onPress={() => { setViewTemplate(null); openApply(viewTemplate); }} data-testid="detail-apply-btn">
                <Ionicons name="person-add-outline" size={22} color="#34C759" />
              </TouchableOpacity>
            </View>
          </View>
          <ScrollView style={s.modalBody}>
            <View style={[s.detailBanner, { backgroundColor: viewTemplate.color + '18' }]}>
              <View style={[s.detailIcon, { backgroundColor: viewTemplate.color }]}>
                <Ionicons name={(viewTemplate.icon || 'person') as any} size={28} color="#FFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.detailName}>{viewTemplate.name}</Text>
                {viewTemplate.description ? <Text style={s.detailDesc}>{viewTemplate.description}</Text> : null}
                <View style={[s.roleBadge, { backgroundColor: roleInfo.color + '20' }]}>
                  <Text style={[s.roleBadgeText, { color: roleInfo.color }]}>{roleInfo.label}</Text>
                </View>
              </View>
            </View>
            {viewTemplate.is_prebuilt && (
              <View style={s.prebuiltNotice}>
                <Ionicons name="lock-closed" size={14} color={colors.textSecondary} />
                <Text style={s.prebuiltText}>This is a prebuilt template and cannot be edited.</Text>
              </View>
            )}
            {PERMISSION_SECTIONS.map(section => {
              const sectionPerms = viewTemplate.permissions?.[section.key] || {};
              const enabled = sectionPerms._enabled !== false;
              return (
                <View key={section.key} style={s.permSection}>
                  <View style={s.permSectionHeader}>
                    <Ionicons name={section.icon as any} size={18} color={enabled ? colors.text : colors.textSecondary} />
                    <Text style={[s.permSectionTitle, !enabled && { color: colors.textSecondary }]}>{section.label}</Text>
                    <View style={[s.statusDot, { backgroundColor: enabled ? '#34C759' : '#FF3B30' }]} />
                  </View>
                  {enabled && section.items.map(item => (
                    <View key={item.key} style={s.permItem}>
                      <Text style={s.permItemLabel}>{item.label}</Text>
                      <Ionicons
                        name={sectionPerms[item.key] ? 'checkmark-circle' : 'close-circle'}
                        size={20}
                        color={sectionPerms[item.key] ? '#34C759' : '#FF3B30'}
                      />
                    </View>
                  ))}
                </View>
              );
            })}
            <View style={{ height: 40 }} />
          </ScrollView>
        </SafeAreaView>
      </WebModal>
    );
  };

  // ─── Editor Modal ───
  const renderEditor = () => (
    <WebModal visible={showEditor} animationType="slide" presentationStyle="pageSheet">
      <SafeAreaView style={s.modal}>
        <View style={s.modalHeader}>
          <TouchableOpacity onPress={() => setShowEditor(false)} data-testid="editor-cancel-btn">
            <Text style={s.cancelText}>Cancel</Text>
          </TouchableOpacity>
          <Text style={s.modalTitle}>{editingTemplate ? 'Edit Template' : 'New Template'}</Text>
          <TouchableOpacity onPress={handleSave} disabled={saving} data-testid="editor-save-btn">
            {saving ? <ActivityIndicator size="small" color="#007AFF" /> : <Text style={s.saveText}>Save</Text>}
          </TouchableOpacity>
        </View>
        <ScrollView style={s.modalBody} keyboardShouldPersistTaps="handled">
          <Text style={s.fieldLabel}>Template Name</Text>
          <TextInput
            style={s.input}
            value={formName}
            onChangeText={setFormName}
            placeholder="e.g., Sales Rep"
            placeholderTextColor={colors.textSecondary}
            data-testid="template-name-input"
          />

          <Text style={s.fieldLabel}>Description</Text>
          <TextInput
            style={[s.input, { height: 70 }]}
            value={formDesc}
            onChangeText={setFormDesc}
            placeholder="What this template is for..."
            placeholderTextColor={colors.textSecondary}
            multiline
            data-testid="template-desc-input"
          />

          <Text style={s.fieldLabel}>Assigned Role</Text>
          <View style={s.roleRow}>
            {ROLE_OPTIONS.map(opt => (
              <TouchableOpacity
                key={opt.value}
                style={[s.roleChip, formRole === opt.value && { backgroundColor: opt.color, borderColor: opt.color }]}
                onPress={() => setFormRole(opt.value)}
                data-testid={`role-option-${opt.value}`}
              >
                <Ionicons name={opt.icon as any} size={16} color={formRole === opt.value ? '#FFF' : opt.color} />
                <Text style={[s.roleChipText, formRole === opt.value && { color: '#FFF' }]}>{opt.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={s.fieldLabel}>Icon & Color</Text>
          <View style={s.iconColorRow}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                {ICON_OPTIONS.map(ic => (
                  <TouchableOpacity
                    key={ic}
                    style={[s.iconPick, formIcon === ic && { backgroundColor: formColor, borderColor: formColor }]}
                    onPress={() => setFormIcon(ic)}
                  >
                    <Ionicons name={ic as any} size={18} color={formIcon === ic ? '#FFF' : colors.textSecondary} />
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
          </View>
          <View style={s.colorRow}>
            {COLOR_OPTIONS.map(c => (
              <TouchableOpacity
                key={c}
                style={[s.colorPick, { backgroundColor: c }, formColor === c && s.colorPickActive]}
                onPress={() => setFormColor(c)}
              />
            ))}
          </View>

          <Text style={[s.fieldLabel, { marginTop: 20 }]}>Feature Permissions</Text>
          {PERMISSION_SECTIONS.map(section => {
            const sectionPerms = formPerms[section.key] || {};
            const enabled = sectionPerms._enabled !== false;
            return (
              <View key={section.key} style={s.editorPermSection}>
                <TouchableOpacity style={s.editorPermHeader} onPress={() => toggleSectionEnabled(section.key)}>
                  <Ionicons name={section.icon as any} size={18} color={enabled ? colors.text : colors.textSecondary} />
                  <Text style={[s.editorPermTitle, !enabled && { color: colors.textSecondary }]}>{section.label}</Text>
                  <Switch
                    value={enabled}
                    onValueChange={() => toggleSectionEnabled(section.key)}
                    trackColor={{ false: colors.surface, true: '#34C759' }}
                  />
                </TouchableOpacity>
                {enabled && section.items.map(item => (
                  <TouchableOpacity key={item.key} style={s.editorPermItem} onPress={() => togglePerm(section.key, item.key)}>
                    <Text style={s.editorPermItemLabel}>{item.label}</Text>
                    <Switch
                      value={!!sectionPerms[item.key]}
                      onValueChange={() => togglePerm(section.key, item.key)}
                      trackColor={{ false: colors.surface, true: '#007AFF' }}
                    />
                  </TouchableOpacity>
                ))}
              </View>
            );
          })}
          <View style={{ height: 60 }} />
        </ScrollView>
      </SafeAreaView>
    </WebModal>
  );

  // ─── Apply to User Modal ───
  const renderApplyModal = () => (
    <WebModal visible={showApply} animationType="slide" presentationStyle="pageSheet">
      <SafeAreaView style={s.modal}>
        <View style={s.modalHeader}>
          <TouchableOpacity onPress={() => setShowApply(false)} data-testid="apply-close-btn">
            <Ionicons name="close" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={s.modalTitle}>Apply to User</Text>
          <View style={{ width: 24 }} />
        </View>
        {applyTemplate && (
          <View style={[s.applyBanner, { backgroundColor: applyTemplate.color + '18' }]}>
            <Ionicons name={(applyTemplate.icon || 'person') as any} size={20} color={applyTemplate.color} />
            <Text style={[s.applyBannerText, { color: applyTemplate.color }]}>{applyTemplate.name}</Text>
          </View>
        )}
        <View style={s.searchRow}>
          <Ionicons name="search" size={18} color={colors.textSecondary} />
          <TextInput
            style={s.searchInput}
            value={userSearch}
            onChangeText={setUserSearch}
            placeholder="Search users..."
            placeholderTextColor={colors.textSecondary}
            data-testid="user-search-input"
          />
        </View>
        {loadingUsers ? (
          <View style={s.centerLoader}><ActivityIndicator size="large" color="#007AFF" /></View>
        ) : (
          <ScrollView style={s.modalBody}>
            {filteredUsers.length === 0 ? (
              <Text style={s.emptyText}>No users found</Text>
            ) : (
              filteredUsers.map(u => {
                const roleInfo = getRoleInfo(u.role);
                return (
                  <TouchableOpacity
                    key={u._id}
                    style={s.userRow}
                    onPress={() => handleApply(u)}
                    disabled={applying === u._id}
                    data-testid={`apply-user-${u._id}`}
                  >
                    <View style={[s.userAvatar, { backgroundColor: roleInfo.color + '20' }]}>
                      <Ionicons name={roleInfo.icon as any} size={18} color={roleInfo.color} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.userName}>{u.name}</Text>
                      <Text style={s.userEmail}>{u.email}</Text>
                      {u.permission_template && (
                        <Text style={s.userCurrentTemplate}>Current: {u.permission_template}</Text>
                      )}
                    </View>
                    {applying === u._id ? (
                      <ActivityIndicator size="small" color="#007AFF" />
                    ) : (
                      <Ionicons name="arrow-forward-circle" size={24} color="#007AFF" />
                    )}
                  </TouchableOpacity>
                );
              })
            )}
            <View style={{ height: 40 }} />
          </ScrollView>
        )}
      </SafeAreaView>
    </WebModal>
  );

  // ─── Audit Log Modal ───
  const getActionIcon = (action: string): { icon: string; color: string } => {
    switch (action) {
      case 'applied': return { icon: 'person-add', color: '#34C759' };
      case 'created': return { icon: 'add-circle', color: '#007AFF' };
      case 'edited': return { icon: 'create', color: '#FF9500' };
      case 'deleted': return { icon: 'trash', color: '#FF3B30' };
      default: return { icon: 'ellipse', color: '#8E8E93' };
    }
  };

  const formatTimeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(ts).toLocaleDateString();
  };

  const getActionDescription = (entry: any): string => {
    const { action, actor_name, template_name, details } = entry;
    const actor = actor_name || 'Someone';
    switch (action) {
      case 'applied':
        return `${actor} applied "${template_name}" to ${details?.target_user_name || 'a user'}${details?.previous_role && details?.new_role ? ` (${details.previous_role} → ${details.new_role})` : ''}`;
      case 'created':
        return `${actor} created template "${template_name}"`;
      case 'edited':
        return `${actor} edited "${template_name}"${details?.fields_changed?.length ? ` (${details.fields_changed.join(', ')})` : ''}`;
      case 'deleted':
        return `${actor} deleted template "${template_name}"`;
      default:
        return `${actor} performed ${action} on "${template_name}"`;
    }
  };

  const renderAuditLog = () => (
    <WebModal visible={showAuditLog} animationType="slide" presentationStyle="pageSheet">
      <SafeAreaView style={s.modal}>
        <View style={s.modalHeader}>
          <TouchableOpacity onPress={() => setShowAuditLog(false)} data-testid="audit-close-btn">
            <Ionicons name="close" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={s.modalTitle}>Activity Log</Text>
          <View style={{ width: 24 }} />
        </View>
        {loadingAudit ? (
          <View style={s.centerLoader}><ActivityIndicator size="large" color="#C9A962" /></View>
        ) : auditLog.length === 0 ? (
          <View style={s.centerLoader}>
            <Ionicons name="document-text-outline" size={48} color={colors.textSecondary} />
            <Text style={[s.emptyText, { marginTop: 12 }]}>No activity yet</Text>
            <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginTop: 4, paddingHorizontal: 40 }}>
              Activity will appear here when templates are created, edited, deleted, or applied to users.
            </Text>
          </View>
        ) : (
          <ScrollView style={s.modalBody}>
            {auditLog.map((entry, idx) => {
              const ai = getActionIcon(entry.action);
              return (
                <View key={idx} style={s.auditEntry} data-testid={`audit-entry-${idx}`}>
                  <View style={[s.auditIconWrap, { backgroundColor: ai.color + '18' }]}>
                    <Ionicons name={ai.icon as any} size={16} color={ai.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.auditDesc}>{getActionDescription(entry)}</Text>
                    <Text style={s.auditTime}>{formatTimeAgo(entry.timestamp)}</Text>
                  </View>
                  <View style={[s.auditActionBadge, { backgroundColor: ai.color + '18' }]}>
                    <Text style={[s.auditActionText, { color: ai.color }]}>{entry.action}</Text>
                  </View>
                </View>
              );
            })}
            <View style={{ height: 40 }} />
          </ScrollView>
        )}
      </SafeAreaView>
    </WebModal>
  );

  // ─── Main List ───
  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.centerLoader}><ActivityIndicator size="large" color="#007AFF" /></View>
      </SafeAreaView>
    );
  }

  const prebuilt = templates.filter(t => t.is_prebuilt);
  const custom = templates.filter(t => !t.is_prebuilt);

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="back-btn">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Permission Templates</Text>
        <TouchableOpacity onPress={() => openEditor()} style={s.addBtn} data-testid="create-template-btn">
          <Ionicons name="add-circle" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={s.list}>
        {/* Prebuilt */}
        <Text style={s.sectionLabel}>Prebuilt Templates</Text>
        {prebuilt.map(t => {
          const roleInfo = getRoleInfo(t.role);
          return (
            <TouchableOpacity
              key={t.id}
              style={s.card}
              onPress={() => setViewTemplate(t)}
              data-testid={`template-card-${t.id}`}
            >
              <View style={[s.cardIcon, { backgroundColor: t.color }]}>
                <Ionicons name={(t.icon || 'person') as any} size={20} color="#FFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.cardName}>{t.name}</Text>
                <Text style={s.cardDesc} numberOfLines={1}>{t.description}</Text>
              </View>
              <View style={[s.roleBadge, { backgroundColor: roleInfo.color + '20' }]}>
                <Text style={[s.roleBadgeText, { color: roleInfo.color }]}>{roleInfo.label}</Text>
              </View>
              <TouchableOpacity
                style={s.applyBtn}
                onPress={(e) => { e.stopPropagation(); openApply(t); }}
                data-testid={`apply-btn-${t.id}`}
              >
                <Ionicons name="person-add" size={18} color="#007AFF" />
              </TouchableOpacity>
            </TouchableOpacity>
          );
        })}

        {/* Custom */}
        <Text style={[s.sectionLabel, { marginTop: 24 }]}>Custom Templates</Text>
        {custom.length === 0 ? (
          <View style={s.emptyCard}>
            <Ionicons name="documents-outline" size={40} color={colors.textSecondary} />
            <Text style={s.emptyCardText}>No custom templates yet</Text>
            <TouchableOpacity style={s.emptyCardBtn} onPress={() => openEditor()} data-testid="create-first-btn">
              <Ionicons name="add" size={18} color="#FFF" />
              <Text style={s.emptyCardBtnText}>Create One</Text>
            </TouchableOpacity>
          </View>
        ) : (
          custom.map(t => {
            const roleInfo = getRoleInfo(t.role);
            return (
              <TouchableOpacity
                key={t.id}
                style={s.card}
                onPress={() => setViewTemplate(t)}
                data-testid={`template-card-${t.id}`}
              >
                <View style={[s.cardIcon, { backgroundColor: t.color }]}>
                  <Ionicons name={(t.icon || 'people') as any} size={20} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.cardName}>{t.name}</Text>
                  <Text style={s.cardDesc} numberOfLines={1}>{t.description}</Text>
                </View>
                <View style={[s.roleBadge, { backgroundColor: roleInfo.color + '20' }]}>
                  <Text style={[s.roleBadgeText, { color: roleInfo.color }]}>{roleInfo.label}</Text>
                </View>
                <TouchableOpacity
                  style={s.applyBtn}
                  onPress={(e) => { e.stopPropagation(); openApply(t); }}
                  data-testid={`apply-btn-custom-${t.id}`}
                >
                  <Ionicons name="person-add" size={18} color="#007AFF" />
                </TouchableOpacity>
                <TouchableOpacity
                  style={s.deleteBtn}
                  onPress={(e) => { e.stopPropagation(); handleDelete(t); }}
                  data-testid={`delete-btn-${t.id}`}
                >
                  <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                </TouchableOpacity>
              </TouchableOpacity>
            );
          })
        )}

        {/* Activity Log Button */}
        <TouchableOpacity
          style={s.auditLogBtn}
          onPress={() => { setShowAuditLog(true); loadAuditLog(); }}
          data-testid="audit-log-btn"
        >
          <Ionicons name="time-outline" size={20} color="#C9A962" />
          <Text style={s.auditLogBtnText}>Activity Log</Text>
          <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>

      {renderEditor()}
      {renderDetailView()}
      {renderApplyModal()}
      {renderAuditLog()}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  centerLoader: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: colors.surface,
  },
  backBtn: { padding: 4 },
  addBtn: { padding: 4 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  list: { padding: 16, paddingBottom: 40 },
  sectionLabel: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 },
  card: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 12, padding: 14, marginBottom: 10, gap: 12,
  },
  cardIcon: { width: 40, height: 40, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  cardName: { fontSize: 17, fontWeight: '600', color: colors.text },
  cardDesc: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  roleBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  roleBadgeText: { fontSize: 13, fontWeight: '600' },
  applyBtn: { padding: 6 },
  deleteBtn: { padding: 6 },
  emptyCard: {
    alignItems: 'center', paddingVertical: 40, backgroundColor: colors.card,
    borderRadius: 12, borderWidth: 1, borderColor: colors.surface, borderStyle: 'dashed',
  },
  emptyCardText: { fontSize: 17, color: colors.textSecondary, marginTop: 12 },
  emptyCardBtn: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#007AFF',
    paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, marginTop: 16, gap: 6,
  },
  emptyCardBtnText: { color: '#FFF', fontWeight: '600', fontSize: 16 },

  // Modal shared
  modal: { flex: 1, backgroundColor: colors.bg },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: colors.surface,
  },
  modalTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  modalBody: { flex: 1, padding: 16 },
  cancelText: { fontSize: 18, color: colors.textSecondary },
  saveText: { fontSize: 18, fontWeight: '600', color: '#007AFF' },

  // Detail
  detailBanner: { flexDirection: 'row', alignItems: 'center', padding: 16, borderRadius: 12, gap: 16, marginBottom: 20 },
  detailIcon: { width: 56, height: 56, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  detailName: { fontSize: 21, fontWeight: '700', color: colors.text },
  detailDesc: { fontSize: 16, color: colors.textSecondary, marginTop: 4 },
  prebuiltNotice: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 16 },
  prebuiltText: { fontSize: 14, color: colors.textSecondary, fontStyle: 'italic' },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  permSection: { backgroundColor: colors.card, borderRadius: 12, padding: 14, marginBottom: 12 },
  permSectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  permSectionTitle: { flex: 1, fontSize: 17, fontWeight: '600', color: colors.text },
  permItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 6, paddingLeft: 26 },
  permItemLabel: { fontSize: 16, color: colors.text },

  // Editor
  fieldLabel: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, marginBottom: 8, marginTop: 16 },
  input: {
    backgroundColor: colors.card, borderRadius: 10, padding: 14, fontSize: 18,
    color: colors.text, borderWidth: 1, borderColor: colors.surface,
  },
  roleRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  roleChip: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1.5, borderColor: colors.surface, gap: 6, backgroundColor: colors.card,
  },
  roleChipText: { fontSize: 15, fontWeight: '600', color: colors.text },
  iconColorRow: { flexDirection: 'row', gap: 6, marginBottom: 8 },
  iconPick: {
    width: 36, height: 36, borderRadius: 8, borderWidth: 1.5, borderColor: colors.surface,
    justifyContent: 'center', alignItems: 'center', backgroundColor: colors.card,
  },
  colorRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  colorPick: { width: 30, height: 30, borderRadius: 15 },
  colorPickActive: { borderWidth: 3, borderColor: colors.text },
  editorPermSection: { backgroundColor: colors.card, borderRadius: 12, padding: 12, marginBottom: 10 },
  editorPermHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  editorPermTitle: { flex: 1, fontSize: 17, fontWeight: '600', color: colors.text },
  editorPermItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 6, paddingLeft: 26 },
  editorPermItemLabel: { fontSize: 16, color: colors.text },

  // Apply modal
  applyBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 10, marginHorizontal: 16, marginTop: 8, borderRadius: 10 },
  applyBannerText: { fontSize: 17, fontWeight: '600' },
  searchRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 10, marginHorizontal: 16, marginVertical: 12, paddingHorizontal: 12, paddingVertical: 8, gap: 8,
  },
  searchInput: { flex: 1, fontSize: 17, color: colors.text, padding: 4 },
  userRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 12, padding: 14, marginBottom: 8, gap: 12,
  },
  userAvatar: { width: 40, height: 40, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  userName: { fontSize: 17, fontWeight: '600', color: colors.text },
  userEmail: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  userCurrentTemplate: { fontSize: 13, color: '#C9A962', marginTop: 2, fontStyle: 'italic' },
  emptyText: { textAlign: 'center', color: colors.textSecondary, marginTop: 40, fontSize: 17 },

  // Audit log button
  auditLogBtn: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 12, padding: 14, marginTop: 24, gap: 10,
    borderWidth: 1, borderColor: 'rgba(201,169,98,0.2)',
  },
  auditLogBtnText: { flex: 1, fontSize: 17, fontWeight: '600', color: colors.text },

  // Audit log entries
  auditEntry: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 12, padding: 12, marginBottom: 8, gap: 10,
  },
  auditIconWrap: { width: 34, height: 34, borderRadius: 9, justifyContent: 'center', alignItems: 'center' },
  auditDesc: { fontSize: 15, color: colors.text, lineHeight: 18 },
  auditTime: { fontSize: 13, color: colors.textSecondary, marginTop: 3 },
  auditActionBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  auditActionText: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
});
