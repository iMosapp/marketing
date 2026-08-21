import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Switch,
  Modal,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';

const RULE_COLORS = ['#007AFF', '#FF9500', '#34C759', '#AF52DE', '#FF2D55', '#5856D6', '#00C7BE', '#FFD60A'];

const timeAgo = (iso: string) => {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

export default function KeywordRulesScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const isManager = ['super_admin', 'org_admin', 'store_manager', 'admin'].includes((user as any)?.role || '');

  const [loading, setLoading] = useState(true);
  const [rules, setRules] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editRule, setEditRule] = useState<any>(null);
  const [formTag, setFormTag] = useState('');
  const [formKeywords, setFormKeywords] = useState('');
  const [formColor, setFormColor] = useState(RULE_COLORS[0]);
  const [formAlert, setFormAlert] = useState(false);
  const [formScope, setFormScope] = useState<'personal' | 'team'>('personal');
  const [saving, setSaving] = useState(false);
  const [scanningId, setScanningId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const [rulesRes, eventsRes] = await Promise.all([
        api.get(`/keyword-rules/${user._id}`),
        api.get(`/keyword-rules/${user._id}/events?limit=30`),
      ]);
      setRules(rulesRes.data || []);
      setEvents(eventsRes.data || []);
    } catch (e) {
      console.error('Failed to load keyword rules:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id]);

  useEffect(() => { load(); }, [load]);

  const openAdd = () => {
    setEditRule(null);
    setFormTag('');
    setFormKeywords('');
    setFormColor(RULE_COLORS[rules.length % RULE_COLORS.length]);
    setFormAlert(false);
    setFormScope('personal');
    setModalOpen(true);
  };

  const openEdit = (rule: any) => {
    setEditRule(rule);
    setFormTag(rule.tag);
    setFormKeywords((rule.keywords || []).join(', '));
    setFormColor(rule.color || RULE_COLORS[0]);
    setFormAlert(!!rule.alert_enabled);
    setFormScope(rule.scope === 'team' ? 'team' : 'personal');
    setModalOpen(true);
  };

  const saveRule = async () => {
    const tag = formTag.trim();
    const keywords = formKeywords.split(',').map(k => k.trim()).filter(Boolean);
    if (!tag) { showSimpleAlert('Missing Tag', 'Enter the tag to apply.'); return; }
    if (keywords.length === 0) { showSimpleAlert('Missing Keywords', 'Enter at least one keyword (comma-separated).'); return; }
    setSaving(true);
    try {
      if (editRule) {
        await api.put(`/keyword-rules/${user?._id}/${editRule._id}`, { tag, keywords, color: formColor, alert_enabled: formAlert });
      } else {
        await api.post(`/keyword-rules/${user?._id}`, { tag, keywords, color: formColor, enabled: true, alert_enabled: formAlert, scope: formScope });
      }
      setModalOpen(false);
      load();
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to save rule');
    } finally {
      setSaving(false);
    }
  };

  const toggleRule = async (rule: any) => {
    setRules(prev => prev.map(r => r._id === rule._id ? { ...r, enabled: !r.enabled } : r));
    try {
      await api.put(`/keyword-rules/${user?._id}/${rule._id}`, { enabled: !rule.enabled });
    } catch {
      setRules(prev => prev.map(r => r._id === rule._id ? { ...r, enabled: rule.enabled } : r));
    }
  };

  const toggleAlert = async (rule: any) => {
    setRules(prev => prev.map(r => r._id === rule._id ? { ...r, alert_enabled: !r.alert_enabled } : r));
    try {
      await api.put(`/keyword-rules/${user?._id}/${rule._id}`, { alert_enabled: !rule.alert_enabled });
    } catch {
      setRules(prev => prev.map(r => r._id === rule._id ? { ...r, alert_enabled: rule.alert_enabled } : r));
    }
  };

  const scanRule = async (rule: any) => {
    const doScan = async () => {
      setScanningId(rule._id);
      try {
        const res = await api.post(`/keyword-rules/${user?._id}/${rule._id}/scan`);
        const d = res.data || {};
        showSimpleAlert(
          'Scan Complete',
          `${d.messages_matched || 0} message(s) + ${d.calls_matched || 0} call(s) matched — ${d.contacts_tagged || 0} contact(s) tagged "${rule.tag}".`
        );
        load();
      } catch {
        showSimpleAlert('Error', 'History scan failed');
      } finally {
        setScanningId(null);
      }
    };
    if (Platform.OS === 'web') {
      if (window.confirm(`Scan all past texts & calls for "${rule.tag}" keywords and tag matching contacts?`)) doScan();
    } else {
      const { Alert } = require('react-native');
      Alert.alert('Scan History', `Scan all past texts & calls for "${rule.tag}" keywords and tag matching contacts?`, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Scan', onPress: doScan },
      ]);
    }
  };

  const deleteRule = async (rule: any) => {
    const doDelete = async () => {
      try {
        await api.delete(`/keyword-rules/${user?._id}/${rule._id}`);
        setRules(prev => prev.filter(r => r._id !== rule._id));
      } catch {
        showSimpleAlert('Error', 'Failed to delete rule');
      }
    };
    if (Platform.OS === 'web') {
      if (window.confirm(`Delete the "${rule.tag}" rule?`)) doDelete();
    } else {
      const { Alert } = require('react-native');
      Alert.alert('Delete Rule', `Delete the "${rule.tag}" rule?`, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: doDelete },
      ]);
    }
  };

  const openEvent = (ev: any) => {
    if (ev.conversation_id && ev.message_id) {
      router.push(`/thread/${ev.conversation_id}?jumpToMsg=${ev.message_id}&q=${encodeURIComponent(ev.keyword || '')}` as any);
    } else if (ev.contact_id) {
      router.push(`/contact/${ev.contact_id}` as any);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="keyword-rules-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.accent} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Keyword Auto-Tags</Text>
        <TouchableOpacity onPress={openAdd} style={styles.addBtn} data-testid="keyword-rules-add-btn">
          <Ionicons name="add" size={22} color="#fff" />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.loadingWrap}><ActivityIndicator size="large" color={colors.accent} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 60 }}>
          {/* Explainer */}
          <View style={styles.explainer}>
            <Ionicons name="pricetags" size={16} color="#5856D6" />
            <Text style={styles.explainerText}>
              When a keyword shows up in a text or a call transcript, the tag is applied to the contact automatically — and you can see exactly which message triggered it.{'\n\n'}
              <Ionicons name="notifications" size={11} color="#FF9500" /> bell = instant push alert when a customer says it · <Ionicons name="time-outline" size={11} color="#32ADE6" /> clock = scan past conversations
            </Text>
          </View>

          {/* Rules */}
          <Text style={styles.sectionTitle}>RULES</Text>
          {rules.length === 0 && (
            <Text style={styles.emptyText}>No rules yet — tap + to create one.</Text>
          )}
          {rules.map(rule => (
            <View key={rule._id} style={styles.ruleCard} data-testid={`keyword-rule-${rule.tag.toLowerCase().replace(/\s+/g, '-')}`}>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <View style={[styles.tagChip, { backgroundColor: `${rule.color || '#5856D6'}22` }]}>
                    <Ionicons name="pricetag" size={11} color={rule.color || '#5856D6'} />
                    <Text style={[styles.tagChipText, { color: rule.color || '#5856D6' }]}>{rule.tag}</Text>
                  </View>
                  {rule.scope === 'team' && (
                    <View style={[styles.tagChip, { backgroundColor: '#32ADE622' }]} data-testid={`keyword-rule-team-badge-${rule._id}`}>
                      <Ionicons name="people" size={10} color="#32ADE6" />
                      <Text style={[styles.tagChipText, { color: '#32ADE6' }]}>Team</Text>
                    </View>
                  )}
                  {rule.hit_count > 0 && (
                    <Text style={styles.hitCount}>{rule.hit_count} hit{rule.hit_count === 1 ? '' : 's'}</Text>
                  )}
                </View>
                <Text style={styles.keywordsText} numberOfLines={2}>
                  {(rule.keywords || []).join(' · ')}
                </Text>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 2 }}>
                {rule.editable !== false && (
                  <TouchableOpacity onPress={() => toggleAlert(rule)} style={styles.iconBtn} data-testid={`keyword-rule-alert-${rule._id}`}>
                    <Ionicons name={rule.alert_enabled ? 'notifications' : 'notifications-off-outline'} size={16} color={rule.alert_enabled ? '#FF9500' : colors.textTertiary} />
                  </TouchableOpacity>
                )}
                <TouchableOpacity onPress={() => scanRule(rule)} style={styles.iconBtn} disabled={scanningId === rule._id} data-testid={`keyword-rule-scan-${rule._id}`}>
                  {scanningId === rule._id
                    ? <ActivityIndicator size="small" color="#32ADE6" />
                    : <Ionicons name="time-outline" size={16} color="#32ADE6" />}
                </TouchableOpacity>
                {rule.editable !== false && (
                  <>
                    <TouchableOpacity onPress={() => openEdit(rule)} style={styles.iconBtn} data-testid={`keyword-rule-edit-${rule._id}`}>
                      <Ionicons name="pencil" size={16} color={colors.textSecondary} />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => deleteRule(rule)} style={styles.iconBtn} data-testid={`keyword-rule-delete-${rule._id}`}>
                      <Ionicons name="trash-outline" size={16} color="#FF3B30" />
                    </TouchableOpacity>
                    <Switch
                      value={rule.enabled}
                      onValueChange={() => toggleRule(rule)}
                      trackColor={{ false: colors.surface, true: '#34C759' }}
                      thumbColor="#fff"
                      data-testid={`keyword-rule-toggle-${rule._id}`}
                    />
                  </>
                )}
              </View>
            </View>
          ))}

          {/* Recent activity */}
          <Text style={[styles.sectionTitle, { marginTop: 24 }]}>RECENT AUTO-TAGS</Text>
          {events.length === 0 && (
            <Text style={styles.emptyText}>Nothing tagged yet — new texts and calls are scanned automatically.</Text>
          )}
          {events.map(ev => (
            <TouchableOpacity key={ev._id} style={styles.eventRow} onPress={() => openEvent(ev)} activeOpacity={0.7} data-testid={`keyword-event-${ev._id}`}>
              <View style={styles.eventIcon}>
                <Ionicons name={ev.source_type === 'call' ? 'call' : 'chatbubble'} size={14} color={ev.source_type === 'call' ? '#30D158' : '#007AFF'} />
              </View>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <Text style={styles.eventName}>{ev.contact_name || 'Unknown'}</Text>
                  <View style={[styles.tagChip, { backgroundColor: '#5856D622' }]}>
                    <Text style={[styles.tagChipText, { color: '#5856D6' }]}>{ev.tag}</Text>
                  </View>
                  <Text style={styles.eventTime}>{timeAgo(ev.created_at)}</Text>
                </View>
                {!!ev.snippet && <Text style={styles.eventSnippet} numberOfLines={2}>"{ev.snippet}"</Text>}
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* Add/Edit modal */}
      <Modal visible={modalOpen} transparent animationType="slide" onRequestClose={() => setModalOpen(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <Text style={styles.modalTitle}>{editRule ? 'Edit Rule' : 'New Keyword Rule'}</Text>
              <TouchableOpacity onPress={() => setModalOpen(false)} data-testid="keyword-rule-modal-close">
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <Text style={styles.fieldLabel}>Tag to apply</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Appointment, Jeep Gladiator"
              placeholderTextColor={colors.textTertiary}
              value={formTag}
              onChangeText={setFormTag}
              data-testid="keyword-rule-tag-input"
            />

            {isManager && !editRule && (
              <>
                <Text style={styles.fieldLabel}>Who does this rule apply to?</Text>
                <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
                  <TouchableOpacity
                    onPress={() => setFormScope('personal')}
                    style={[styles.scopePill, formScope === 'personal' && { backgroundColor: '#5856D6', borderColor: '#5856D6' }]}
                    data-testid="keyword-rule-scope-personal"
                  >
                    <Ionicons name="person" size={13} color={formScope === 'personal' ? '#fff' : colors.textSecondary} />
                    <Text style={[styles.scopePillText, { color: formScope === 'personal' ? '#fff' : colors.textSecondary }]}>Just me</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => setFormScope('team')}
                    style={[styles.scopePill, formScope === 'team' && { backgroundColor: '#32ADE6', borderColor: '#32ADE6' }]}
                    data-testid="keyword-rule-scope-team"
                  >
                    <Ionicons name="people" size={13} color={formScope === 'team' ? '#fff' : colors.textSecondary} />
                    <Text style={[styles.scopePillText, { color: formScope === 'team' ? '#fff' : colors.textSecondary }]}>Whole team</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
            {editRule?.scope === 'team' && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 16 }}>
                <Ionicons name="people" size={13} color="#32ADE6" />
                <Text style={{ fontSize: 12, color: '#32ADE6', fontWeight: '600' }}>Team rule — applies to every rep's conversations</Text>
              </View>
            )}

            <Text style={styles.fieldLabel}>Keywords (comma-separated)</Text>
            <TextInput
              style={[styles.input, { minHeight: 60 }]}
              placeholder="e.g. appointment, appt, come in"
              placeholderTextColor={colors.textTertiary}
              value={formKeywords}
              onChangeText={setFormKeywords}
              multiline
              data-testid="keyword-rule-keywords-input"
            />

            <Text style={styles.fieldLabel}>Color</Text>
            <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
              {RULE_COLORS.map(c => (
                <TouchableOpacity
                  key={c}
                  onPress={() => setFormColor(c)}
                  style={[styles.colorDot, { backgroundColor: c }, formColor === c && styles.colorDotSelected]}
                  data-testid={`keyword-rule-color-${c.replace('#', '')}`}
                />
              ))}
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <View style={{ flex: 1, marginRight: 12 }}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Instant alert</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>Push notification the moment a customer says or texts this</Text>
              </View>
              <Switch
                value={formAlert}
                onValueChange={setFormAlert}
                trackColor={{ false: colors.surface, true: '#FF9500' }}
                thumbColor="#fff"
                data-testid="keyword-rule-alert-switch"
              />
            </View>

            <TouchableOpacity
              style={[styles.saveBtn, saving && { opacity: 0.6 }]}
              onPress={saveRule}
              disabled={saving}
              data-testid="keyword-rule-save-btn"
            >
              {saving ? <ActivityIndicator size="small" color="#fff" /> : (
                <Text style={styles.saveBtnText}>{editRule ? 'Save Changes' : 'Create Rule'}</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn: { padding: 4 },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: colors.text, marginLeft: 6 },
  addBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#5856D6', alignItems: 'center', justifyContent: 'center' },
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  explainer: { flexDirection: 'row', gap: 10, backgroundColor: '#5856D615', borderRadius: 12, padding: 12, margin: 16, alignItems: 'flex-start' },
  explainerText: { flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  sectionTitle: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6, marginHorizontal: 16, marginBottom: 8 },
  emptyText: { fontSize: 13, color: colors.textTertiary, marginHorizontal: 16, marginBottom: 12 },
  ruleCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 14, padding: 14, marginHorizontal: 16, marginBottom: 10, borderWidth: 1, borderColor: colors.border, gap: 8 },
  tagChip: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  tagChipText: { fontSize: 12, fontWeight: '700' },
  hitCount: { fontSize: 11, color: colors.textTertiary, fontWeight: '600' },
  keywordsText: { fontSize: 12, color: colors.textSecondary, marginTop: 6 },
  iconBtn: { padding: 6 },
  eventRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 12, marginHorizontal: 16, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  eventIcon: { width: 30, height: 30, borderRadius: 15, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  eventName: { fontSize: 14, fontWeight: '600', color: colors.text },
  eventTime: { fontSize: 11, color: colors.textTertiary },
  eventSnippet: { fontSize: 12, color: colors.textSecondary, marginTop: 3, fontStyle: 'italic' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalCard: { backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 36 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, marginBottom: 6, letterSpacing: 0.4 },
  input: { backgroundColor: colors.surface, borderRadius: 10, padding: 12, fontSize: 15, color: colors.text, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  colorDot: { width: 30, height: 30, borderRadius: 15 },
  colorDotSelected: { borderWidth: 3, borderColor: colors.text },
  scopePill: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 9, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
  scopePillText: { fontSize: 13, fontWeight: '700' },
  saveBtn: { backgroundColor: '#5856D6', borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  saveBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
