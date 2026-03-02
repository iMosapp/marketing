import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
const ICONS: Record<string, string> = {
  congrats: 'gift', birthday: 'balloon', anniversary: 'heart',
  thankyou: 'thumbs-up', welcome: 'hand-left', holiday: 'snow',
};

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
    if (user?.store_id) fetchTemplates();
  }, [user?.store_id]);

  const fetchTemplates = async () => {
    try {
      const res = await api.get(`/congrats/templates/all/${user?.store_id}`);
      setTemplates(res.data);
    } catch { showSimpleAlert('Error', 'Failed to load templates'); }
    finally { setLoading(false); }
  };

  const saveTemplate = async () => {
    if (!editing || !user?.store_id) return;
    setSaving(true);
    try {
      await api.post(`/congrats/template/${user.store_id}`, {
        card_type: editing.card_type,
        headline: editing.headline,
        message: editing.message,
        accent_color: editing.accent_color,
        footer_text: editing.footer_text,
      });
      showSimpleAlert('Saved', `${editing.card_type} template updated`);
      setEditing(null);
      fetchTemplates();
    } catch { showSimpleAlert('Error', 'Failed to save template'); }
    finally { setSaving(false); }
  };

  if (loading) {
    return <View style={s.loading}><ActivityIndicator size="large" color="#C9A962" /></View>;
  }

  if (editing) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => setEditing(null)} data-testid="template-edit-back"><Ionicons name="chevron-back" size={24} color={colors.text} /></TouchableOpacity>
          <Text style={s.headerTitle}>Edit {editing.card_type.charAt(0).toUpperCase() + editing.card_type.slice(1)} Template</Text>
          <View style={{ width: 24 }} />
        </View>
        <ScrollView style={s.content}>
          <Text style={s.label}>HEADLINE</Text>
          <TextInput style={s.input} value={editing.headline} onChangeText={v => setEditing({ ...editing, headline: v })} placeholderTextColor={colors.textSecondary} data-testid="template-headline" />
          <Text style={s.label}>MESSAGE</Text>
          <Text style={s.hint}>Use {'{customer_name}'} or {'{name}'} as placeholders</Text>
          <TextInput style={[s.input, { height: 100, textAlignVertical: 'top' }]} value={editing.message} onChangeText={v => setEditing({ ...editing, message: v })} multiline placeholderTextColor={colors.textSecondary} data-testid="template-message" />
          <Text style={s.label}>ACCENT COLOR</Text>
          <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
            {['#C9A962', '#FF2D55', '#FF6B6B', '#34C759', '#007AFF', '#5AC8FA', '#AF52DE', '#FF9500'].map(c => (
              <TouchableOpacity key={c} onPress={() => setEditing({ ...editing, accent_color: c })}
                style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: c, borderWidth: editing.accent_color === c ? 3 : 0, borderColor: colors.border }} />
            ))}
          </View>
          <Text style={s.label}>FOOTER TEXT (OPTIONAL)</Text>
          <TextInput style={s.input} value={editing.footer_text} onChangeText={v => setEditing({ ...editing, footer_text: v })} placeholder="e.g. Your satisfaction is our priority" placeholderTextColor={colors.textSecondary} />

          {/* Preview */}
          <View style={[s.previewBox, { borderColor: editing.accent_color }]}>
            <Text style={[s.previewHL, { color: editing.accent_color }]}>{editing.headline}</Text>
            <Text style={s.previewMsg}>{editing.message.replace('{customer_name}', 'John').replace('{name}', 'John')}</Text>
            {editing.footer_text ? <Text style={s.previewFooter}>{editing.footer_text}</Text> : null}
          </View>

          <TouchableOpacity style={[s.saveBtn, { backgroundColor: editing.accent_color }, saving && { opacity: 0.5 }]} onPress={saveTemplate} disabled={saving} data-testid="template-save">
            {saving ? <ActivityIndicator size="small" color={colors.text} /> : <><Ionicons name="checkmark" size={20} color={colors.text} /><Text style={s.saveBtnText}>Save Template</Text></>}
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="template-list-back"><Ionicons name="chevron-back" size={24} color={colors.text} /></TouchableOpacity>
        <Text style={s.headerTitle}>Card Templates</Text>
        <TouchableOpacity onPress={() => {
          // Create a new template by pre-filling with defaults and opening the editor
          setEditing({
            card_type: 'custom',
            customized: false,
            headline: 'New Card',
            message: 'Hey {customer_name}, just wanted to reach out!',
            accent_color: '#C9A962',
            background_color: '#1A1A1A',
            text_color: colors.text,
            footer_text: '',
          });
        }} data-testid="create-card-template-btn">
          <Ionicons name="add-circle" size={26} color="#007AFF" />
        </TouchableOpacity>
      </View>
      <ScrollView style={s.content}>
        <Text style={s.sectionNote}>Customize the look and message for each card type. These settings apply to all users in your store.</Text>
        {templates.map(t => (
          <TouchableOpacity key={t.card_type} style={s.card} onPress={() => setEditing(t)} data-testid={`template-${t.card_type}`}>
            <View style={[s.cardIcon, { backgroundColor: t.accent_color + '20' }]}>
              <Ionicons name={(ICONS[t.card_type] || 'gift') as any} size={24} color={t.accent_color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.cardTitle}>{t.headline}</Text>
              <Text style={s.cardSub}>{t.card_type.charAt(0).toUpperCase() + t.card_type.slice(1)} Card{t.customized ? ' (Customized)' : ''}</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  loading: { flex: 1, backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  headerTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
  content: { flex: 1, padding: 16 },
  sectionNote: { fontSize: 13, color: '#8E8E93', marginBottom: 20, lineHeight: 18 },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 12, gap: 14 },
  cardIcon: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  cardSub: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  label: { fontSize: 10, fontWeight: '700', color: '#6E6E73', marginTop: 16, marginBottom: 6, letterSpacing: 1 },
  hint: { fontSize: 11, color: '#8E8E93', marginBottom: 6 },
  input: { backgroundColor: colors.card, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 12, fontSize: 14, color: colors.text, borderWidth: 1.5, borderColor: colors.borderLight },
  previewBox: { backgroundColor: '#1A1A1A', borderRadius: 16, padding: 24, marginTop: 20, borderWidth: 1, alignItems: 'center' },
  previewHL: { fontSize: 24, fontWeight: '800', marginBottom: 12, textAlign: 'center' },
  previewMsg: { fontSize: 14, color: '#FFFFFFCC', textAlign: 'center', lineHeight: 20 },
  previewFooter: { fontSize: 11, color: '#8E8E93', marginTop: 12 },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 12, marginTop: 24, marginBottom: 40 },
  saveBtnText: { fontSize: 17, fontWeight: '700', color: colors.text },
});
