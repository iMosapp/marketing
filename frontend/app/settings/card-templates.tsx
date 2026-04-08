import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert, showAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';

// Icons for all 15 card types
const ICONS: Record<string, string> = {
  congrats:           'gift',
  birthday:           'balloon',
  anniversary:        'heart',
  thankyou:           'thumbs-up',
  welcome:            'hand-left',
  holiday:            'snow',
  nice_meeting_you:   'people',
  check_this_out:     'eye',
  look_at_this_trade: 'car-sport',
  before:             'camera-reverse',
  after:              'checkmark-circle',
  monthly_special:    'pricetag',
  you_did_it:         'trophy',
  nice_to_meet_you:   'hand-right',
  key_west:           'sunny',
};

const ACCENT_COLORS = [
  '#C9A962', '#FF2D55', '#FF6B6B', '#34C759', '#007AFF',
  '#5AC8FA', '#AF52DE', '#FF9500', '#FFD60A', '#00C7BE',
  '#FF3B30', '#8E8E93',
];

interface Template {
  card_type: string;
  customized: boolean;
  headline: string;
  message: string;
  accent_color: string;
  background_color: string;
  text_color: string;
  footer_text: string;
}

export default function ManageCardTemplatesPage() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Template | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Super admins may not have store_id — use organization store or first available store
    const storeId = user?.store_id || (user as any)?.store_ids?.[0];
    if (storeId) fetchTemplates(storeId);
    else if (user?._id) {
      // Try to find any store for this user
      api.get(`/users/${user._id}`).then(r => {
        const sid = r.data?.store_id;
        if (sid) fetchTemplates(sid);
        else setLoading(false);
      }).catch(() => setLoading(false));
    } else setLoading(false);
  }, [user?._id]);

  const fetchTemplates = async (storeId?: string) => {
    const sid = storeId || user?.store_id;
    if (!sid) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await api.get(`/congrats/templates/all/${sid}`);
      const data = Array.isArray(res.data) ? res.data : [];
      setTemplates(data.sort((a: Template, b: Template) => a.card_type.localeCompare(b.card_type)));
    } catch { showSimpleAlert('Error', 'Failed to load templates'); }
    finally { setLoading(false); }
  };

  const saveTemplate = async () => {
    const storeId = user?.store_id || (user as any)?.store_ids?.[0];
    if (!editing || !storeId) return;
    setSaving(true);
    try {
      await api.post(`/congrats/template/${storeId}`, {
        card_type:    editing.card_type,
        name:         editing.headline,
        headline:     editing.headline,
        message:      editing.message,
        accent_color: editing.accent_color,
        footer_text:  editing.footer_text,
      });
      showSimpleAlert('Saved ✓', `"${editing.headline}" template updated`);
      setEditing(null);
      fetchTemplates(storeId);
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to save template');
    } finally { setSaving(false); }
  };

  const deleteTemplate = async (template: Template) => {
    if (!user?.store_id) return;
    if (!template.card_type.startsWith('custom_')) {
      showSimpleAlert('Cannot Delete', 'Only custom card types can be deleted. You can edit the message instead.');
      return;
    }
    const doDelete = async () => {
      try {
        await api.delete(`/congrats/template/${user.store_id}/${template.card_type}`);
        fetchTemplates();
      } catch { showSimpleAlert('Error', 'Failed to delete template'); }
    };
    if (Platform.OS === 'web') {
      if (window.confirm(`Delete "${template.headline}" card template?`)) doDelete();
    } else {
      showAlert('Delete Card Template', `Delete "${template.headline}"?`, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: doDelete },
      ]);
    }
  };

  // ── Edit screen ────────────────────────────────────────────────────────────
  if (editing) {
    const previewMsg = editing.message
      .replace(/{customer_name}/g, 'Alex')
      .replace(/{name}/g, 'Alex');

    return (
      <SafeAreaView style={s.container} edges={['top']}>
        {/* Header — Save button ALWAYS visible here */}
        <View style={s.header}>
          <TouchableOpacity onPress={() => setEditing(null)} style={s.hBtn} data-testid="template-edit-back">
            <Ionicons name="close" size={24} color={colors.textSecondary} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>
            {editing.card_type.startsWith('custom_') ? 'Custom Card' : editing.headline}
          </Text>
          <TouchableOpacity
            style={[s.saveHeaderBtn, { backgroundColor: editing.accent_color }, saving && { opacity: 0.5 }]}
            onPress={saveTemplate}
            disabled={saving}
            data-testid="template-save-header"
          >
            {saving
              ? <ActivityIndicator size="small" color="#fff" />
              : <Text style={s.saveHeaderTxt}>Save</Text>
            }
          </TouchableOpacity>
        </View>

        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <ScrollView style={s.content} keyboardShouldPersistTaps="handled">

            {/* Live preview card */}
            <View style={[s.previewBox, { borderColor: editing.accent_color + '80' }]}>
              <Text style={[s.previewHL, { color: editing.accent_color }]}>{editing.headline}</Text>
              <Text style={s.previewMsg}>{previewMsg}</Text>
              {editing.footer_text ? <Text style={s.previewFooter}>{editing.footer_text}</Text> : null}
              <Text style={s.previewNote}>Preview — "Alex" replaces customer name</Text>
            </View>

            <Text style={s.label}>HEADLINE</Text>
            <TextInput
              style={s.input}
              value={editing.headline}
              onChangeText={v => setEditing({ ...editing, headline: v })}
              placeholder="e.g. Congratulations!"
              placeholderTextColor={colors.textTertiary}
              returnKeyType="next"
              data-testid="template-headline"
            />

            <Text style={s.label}>MESSAGE</Text>
            <Text style={s.hint}>Use {'{name}'} or {'{customer_name}'} for the customer's first name</Text>
            <TextInput
              style={[s.input, s.msgInput]}
              value={editing.message}
              onChangeText={v => setEditing({ ...editing, message: v })}
              multiline
              placeholder="Write your message here..."
              placeholderTextColor={colors.textTertiary}
              textAlignVertical="top"
              data-testid="template-message"
            />

            <Text style={s.label}>ACCENT COLOR</Text>
            <View style={s.colorRow}>
              {ACCENT_COLORS.map(c => (
                <TouchableOpacity
                  key={c}
                  onPress={() => setEditing({ ...editing, accent_color: c })}
                  style={[s.colorChip, { backgroundColor: c },
                    editing.accent_color === c && s.colorChipSelected,
                  ]}
                >
                  {editing.accent_color === c && <Ionicons name="checkmark" size={16} color="#fff" />}
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.label}>FOOTER (OPTIONAL)</Text>
            <TextInput
              style={s.input}
              value={editing.footer_text}
              onChangeText={v => setEditing({ ...editing, footer_text: v })}
              placeholder="e.g. Your satisfaction is our priority"
              placeholderTextColor={colors.textTertiary}
              data-testid="template-footer"
            />

            {/* Bottom save button — also here for convenience */}
            <TouchableOpacity
              style={[s.saveBtn, { backgroundColor: editing.accent_color }, saving && { opacity: 0.5 }]}
              onPress={saveTemplate}
              disabled={saving}
              data-testid="template-save"
            >
              {saving
                ? <ActivityIndicator size="small" color="#fff" />
                : <><Ionicons name="checkmark-circle" size={20} color="#fff" /><Text style={s.saveBtnText}>Save Template</Text></>
              }
            </TouchableOpacity>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  // ── Template list ──────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.hBtn} data-testid="template-list-back">
          <Ionicons name="chevron-back" size={26} color="#007AFF" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Card Templates</Text>
        <TouchableOpacity
          onPress={() => setEditing({
            card_type: 'custom_' + Date.now().toString(36),
            customized: false,
            headline: 'New Card',
            message: 'Hey {name}, just wanted to reach out!',
            accent_color: '#C9A962',
            background_color: '#1A1A1A',
            text_color: '#FFFFFF',
            footer_text: '',
          })}
          style={s.hBtn}
          data-testid="create-card-template-btn"
        >
          <Ionicons name="add-circle" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color="#C9A962" /></View>
      ) : (
        <ScrollView style={s.content}>
          <Text style={s.note}>Tap any card to edit its message, headline, or color. Changes apply to all users in your store.</Text>

          {templates.length === 0 && (
            <Text style={{ color: colors.textSecondary, textAlign: 'center', marginTop: 40 }}>
              No templates yet. Your store may need to be set up — contact support.
            </Text>
          )}

          {templates.map(t => (
            <View key={t.card_type} style={s.card}>
              <TouchableOpacity
                style={s.cardMain}
                onPress={() => setEditing({ ...t })}
                data-testid={`template-${t.card_type}`}
              >
                <View style={[s.cardIcon, { backgroundColor: t.accent_color + '20' }]}>
                  <Ionicons name={(ICONS[t.card_type] || 'gift') as any} size={22} color={t.accent_color} />
                </View>
                <View style={{ flex: 1 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Text style={s.cardTitle}>{t.headline}</Text>
                    {t.customized && (
                      <View style={{ backgroundColor: '#C9A96220', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 }}>
                        <Text style={{ fontSize: 11, color: '#C9A962', fontWeight: '700' }}>Custom</Text>
                      </View>
                    )}
                  </View>
                  <Text style={s.cardMsg} numberOfLines={1}>{t.message}</Text>
                </View>
                <Ionicons name="create-outline" size={18} color={colors.textTertiary} />
              </TouchableOpacity>

              {t.card_type.startsWith('custom_') && (
                <TouchableOpacity onPress={() => deleteTemplate(t)} style={s.deleteBtn}>
                  <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                </TouchableOpacity>
              )}
            </View>
          ))}

          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container:       { flex: 1, backgroundColor: colors.bg },
  center:          { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header:          { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  hBtn:            { padding: 4, minWidth: 40 },
  headerTitle:     { fontSize: 18, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' },
  saveHeaderBtn:   { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 10, minWidth: 60, alignItems: 'center' },
  saveHeaderTxt:   { fontSize: 15, fontWeight: '700', color: '#fff' },
  content:         { flex: 1, padding: 16 },
  note:            { fontSize: 14, color: colors.textSecondary, marginBottom: 16, lineHeight: 20 },
  // Card list
  card:            { backgroundColor: colors.card, borderRadius: 14, marginBottom: 10, overflow: 'hidden' },
  cardMain:        { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12 },
  cardIcon:        { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  cardTitle:       { fontSize: 16, fontWeight: '700', color: colors.text },
  cardMsg:         { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  deleteBtn:       { borderTopWidth: 1, borderTopColor: colors.border, padding: 12, alignItems: 'center' },
  // Edit form
  previewBox:      { backgroundColor: '#1A1A1A', borderRadius: 16, padding: 20, marginBottom: 20, borderWidth: 1.5, alignItems: 'center' },
  previewHL:       { fontSize: 22, fontWeight: '800', marginBottom: 10, textAlign: 'center' },
  previewMsg:      { fontSize: 15, color: '#FFFFFFCC', textAlign: 'center', lineHeight: 22 },
  previewFooter:   { fontSize: 12, color: '#8E8E93', marginTop: 10 },
  previewNote:     { fontSize: 11, color: '#555', marginTop: 10, fontStyle: 'italic' },
  label:           { fontSize: 12, fontWeight: '700', color: colors.textTertiary, marginTop: 20, marginBottom: 6, letterSpacing: 0.8, textTransform: 'uppercase' },
  hint:            { fontSize: 13, color: colors.textSecondary, marginBottom: 6 },
  input:           { backgroundColor: colors.card, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: colors.text, borderWidth: 1.5, borderColor: colors.border },
  msgInput:        { height: 110, textAlignVertical: 'top' },
  colorRow:        { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 4 },
  colorChip:       { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  colorChipSelected: { borderWidth: 2.5, borderColor: '#fff' },
  saveBtn:         { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 14, marginTop: 24, marginBottom: 40 },
  saveBtnText:     { fontSize: 17, fontWeight: '700', color: '#fff' },
});
