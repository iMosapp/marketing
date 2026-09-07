import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { FS } from '../../constants/typography';
import { showAlert } from '../../services/alert';
import api from '../../services/api';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const TONE_OPTIONS = [
  { value: 'friendly',     label: 'Friendly' },
  { value: 'professional', label: 'Professional' },
  { value: 'casual',       label: 'Casual' },
  { value: 'energetic',    label: 'Energetic' },
];

const AVATAR_COLORS = ['#C9A962','#34C759','#FF9500','#AF52DE','#FF3B30','#007AFF','#5856D6','#FF2D55'];

const EMPTY_PROFILE = {
  name: '', tagline: '', bio: '', specialties: '',
  tone: 'friendly', never_say: '', custom_prompt: '', avatar_color: '#C9A962',
};

export default function VALibraryScreen() {
  const router    = useRouter();
  const colors    = useThemeStore(s => s.colors);
  const { user }  = useAuthStore();
  const { showToast } = useToast();
  const s = getS(colors);

  const [profiles,  setProfiles]  = useState<any[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing,   setEditing]   = useState<any | null>(null);
  const [form,      setForm]      = useState<any>({ ...EMPTY_PROFILE });
  const [saving,    setSaving]    = useState(false);
  const [preview,   setPreview]   = useState<{ id: string; text: string; loading: boolean } | null>(null);

  const headers = { headers: { 'X-User-ID': user?._id } };

  useFocusEffect(useCallback(() => { load(); }, []));

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get('/va-profiles', headers);
      setProfiles(res.data.profiles || []);
    } catch { setProfiles([]); }
    setLoading(false);
  };

  const openCreate = () => { setEditing(null); setForm({ ...EMPTY_PROFILE }); setShowModal(true); };
  const openEdit   = (p: any) => { setEditing(p); setForm({ ...p }); setShowModal(true); };

  const save = async () => {
    if (!form.name.trim()) { showToast('Name is required', 'error'); return; }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/va-profiles/${editing._id}`, form, headers);
        showToast('VA profile updated', 'success');
      } else {
        await api.post('/va-profiles', form, headers);
        showToast('VA profile created', 'success');
      }
      setShowModal(false);
      await load();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Save failed', 'error');
    }
    setSaving(false);
  };

  const remove = (id: string, name: string) => {
    showAlert('Delete VA', `Delete "${name}"? Lead sources using it fall back to the default VA.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try {
          await api.delete(`/va-profiles/${id}`, headers);
          setProfiles(prev => prev.filter(p => p._id !== id));
          showToast('Deleted', 'success');
        } catch { showToast('Delete failed', 'error'); }
      } },
    ]);
  };

  const generatePreview = async (profileId: string) => {
    setPreview({ id: profileId, text: '', loading: true });
    try {
      const res = await api.get(`/va-profiles/${profileId}/preview`, headers);
      setPreview({ id: profileId, text: res.data.sample_reply || '', loading: false });
    } catch {
      setPreview({ id: profileId, text: 'Preview failed', loading: false });
    }
  };

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <ScreenHeader
        title="VA Library"
        testID="va-library-header"
        right={<HeaderIconButton icon="add-circle" onPress={openCreate} testID="create-va-btn" />}
      />

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
        <Text style={[s.hint, { color: colors.textSecondary }]}>
          Create named VA personas (for example "Ford Truck Specialist") and assign them to Lead Sources so each channel has its own personality.
        </Text>

        {loading ? (
          <View style={s.center}><ActivityIndicator size="large" color={colors.accent} /></View>
        ) : profiles.length === 0 ? (
          <View style={s.center} {...tid('va-library-empty')}>
            <Ionicons name="person-circle-outline" size={52} color={colors.textTertiary} />
            <Text style={[s.emptyTitle, { color: colors.text }]}>No VAs yet</Text>
            <Text style={[s.emptySub, { color: colors.textSecondary }]}>Create your first VA persona to assign to lead sources.</Text>
            <TouchableOpacity style={[s.addBtn, { marginTop: 20, backgroundColor: colors.accent, paddingHorizontal: 24 }]} onPress={openCreate} {...tid('create-first-va-btn')}>
              <Ionicons name="add" size={16} color="#000" />
              <Text style={{ fontWeight: '700', color: '#000', fontSize: FS.heading }}>Create first VA</Text>
            </TouchableOpacity>
          </View>
        ) : (
          profiles.map(p => (
            <View key={p._id} style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]} {...tid(`va-card-${p._id}`)}>
              {/* Card header */}
              <View style={s.cardHeader}>
                <View style={[s.avatar, { backgroundColor: p.avatar_color + '30', borderColor: p.avatar_color }]}>
                  <Text style={[s.avatarText, { color: p.avatar_color }]}>{p.name.charAt(0).toUpperCase()}</Text>
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text style={[s.cardName, { color: colors.text }]} numberOfLines={1}>{p.name}</Text>
                  {p.tagline ? <Text style={[s.cardTag, { color: colors.textSecondary }]} numberOfLines={2}>{p.tagline}</Text> : null}
                </View>
                <View style={[s.tonePill, { backgroundColor: colors.surface }]}>
                  <Text style={{ fontSize: FS.micro, color: colors.textSecondary, fontWeight: '800' }}>{p.tone}</Text>
                </View>
              </View>

              {/* Bio preview */}
              {p.bio ? (
                <Text style={[s.bio, { color: colors.textSecondary }]} numberOfLines={2}>{p.bio}</Text>
              ) : null}
              {p.specialties ? (
                <View style={[s.specChip, { backgroundColor: colors.surface }]}>
                  <Ionicons name="star-outline" size={12} color={colors.accent} />
                  <Text style={{ fontSize: 11, color: colors.accent }}>{p.specialties}</Text>
                </View>
              ) : null}

              {/* AI preview */}
              {preview && preview.id === p._id && (
                <View style={[s.previewBox, { backgroundColor: colors.surface, borderColor: colors.border }]}>
                  <Text style={[s.previewLabel, { color: colors.textSecondary }]}>SAMPLE REPLY</Text>
                  {preview.loading
                    ? <ActivityIndicator size="small" color={colors.accent} />
                    : <Text style={{ color: colors.text, fontSize: 13, lineHeight: 18 }}>{preview.text}</Text>
                  }
                </View>
              )}

              {/* Actions */}
              <View style={s.cardActions}>
                <TouchableOpacity onPress={() => generatePreview(p._id)} style={s.actionBtn} activeOpacity={0.7} {...tid(`va-preview-${p._id}`)}>
                  <Ionicons name="play-circle-outline" size={16} color={colors.accent} />
                  <Text style={{ fontSize: FS.secondary, color: colors.accent, fontWeight: '700' }}>Preview</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => openEdit(p)} style={s.actionBtn} activeOpacity={0.7} {...tid(`va-edit-${p._id}`)}>
                  <Ionicons name="create-outline" size={16} color={colors.accent} />
                  <Text style={{ fontSize: FS.secondary, color: colors.accent, fontWeight: '700' }}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => remove(p._id, p.name)} style={s.actionBtn} activeOpacity={0.7} {...tid(`va-delete-${p._id}`)}>
                  <Ionicons name="trash-outline" size={16} color="#FF3B30" />
                  <Text style={{ fontSize: FS.secondary, color: '#FF3B30', fontWeight: '700' }}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      {/* Create / Edit Modal */}
      <Modal visible={showModal} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
          {/* Modal header */}
          <View style={[s.modalHeader, { borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => setShowModal(false)} hitSlop={8} {...tid('va-modal-cancel')}>
              <Text style={{ color: colors.textSecondary, fontSize: FS.heading, fontWeight: '600' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={[s.modalTitle, { color: colors.text }]}>{editing ? 'Edit VA' : 'New VA'}</Text>
            <TouchableOpacity onPress={save} disabled={saving} hitSlop={8} {...tid('save-va-btn')}>
              {saving ? <ActivityIndicator size="small" color={colors.accent} /> : <Text style={{ color: colors.accent, fontSize: FS.heading, fontWeight: '700' }}>Save</Text>}
            </TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={{ padding: 20, gap: 18, paddingBottom: 60 }}>
            {/* Name */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>VA Name *</Text>
              <TextInput style={[s.input, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]} value={form.name} onChangeText={v => setForm((p: any) => ({ ...p, name: v }))} placeholder="e.g. Ford Truck Specialist" placeholderTextColor={colors.textSecondary} {...tid('va-name-input')} />
            </View>

            {/* Tagline */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>Tagline</Text>
              <TextInput style={[s.input, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]} value={form.tagline} onChangeText={v => setForm((p: any) => ({ ...p, tagline: v }))} placeholder="Short description, e.g. 'Truck & off-road specialist'" placeholderTextColor={colors.textSecondary} />
            </View>

            {/* Avatar color */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>Avatar Color</Text>
              <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap', marginTop: 6 }}>
                {AVATAR_COLORS.map(c => (
                  <TouchableOpacity key={c} onPress={() => setForm((p: any) => ({ ...p, avatar_color: c }))} style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: c, borderWidth: form.avatar_color === c ? 3 : 0, borderColor: colors.text }} {...tid(`va-color-${c.replace('#', '')}`)} />
                ))}
              </View>
            </View>

            {/* Tone */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>Tone</Text>
              <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
                {TONE_OPTIONS.map(t => (
                  <TouchableOpacity key={t.value} onPress={() => setForm((p: any) => ({ ...p, tone: t.value }))} style={{ borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, backgroundColor: form.tone === t.value ? colors.accent : colors.card, borderWidth: 1, borderColor: form.tone === t.value ? colors.accent : colors.border }}>
                    <Text style={{ fontSize: 13, fontWeight: '600', color: form.tone === t.value ? '#000' : colors.text }}>{t.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Bio */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>Bio / Background</Text>
              <Text style={{ fontSize: FS.caption, color: colors.textSecondary, marginBottom: 6 }}>Who this VA is: their experience, personality, why customers love them.</Text>
              <TextInput style={[s.input, { height: 90, textAlignVertical: 'top', color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]} value={form.bio} onChangeText={v => setForm((p: any) => ({ ...p, bio: v }))} multiline placeholder="e.g. 10 years selling trucks in Utah. Knows every tow rating and lift kit. Loves off-roading on weekends." placeholderTextColor={colors.textSecondary} />
            </View>

            {/* Specialties */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>Specialties</Text>
              <TextInput style={[s.input, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]} value={form.specialties} onChangeText={v => setForm((p: any) => ({ ...p, specialties: v }))} placeholder="e.g. Trucks, trade-ins, towing, off-road builds" placeholderTextColor={colors.textSecondary} />
            </View>

            {/* Never say */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>Never Say</Text>
              <TextInput style={[s.input, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]} value={form.never_say} onChangeText={v => setForm((p: any) => ({ ...p, never_say: v }))} placeholder="e.g. Sorry for the delay, I apologize, as an AI" placeholderTextColor={colors.textSecondary} />
            </View>

            {/* Custom prompt (advanced) */}
            <View>
              <Text style={[s.label, { color: colors.textSecondary }]}>Custom Prompt (Advanced, overrides everything above)</Text>
              <TextInput style={[s.input, { height: 120, textAlignVertical: 'top', color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]} value={form.custom_prompt} onChangeText={v => setForm((p: any) => ({ ...p, custom_prompt: v }))} multiline placeholder="Paste a full system prompt here if you want complete control. Leave blank to use the fields above." placeholderTextColor={colors.textSecondary} />
            </View>
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const getS = (c: any) => StyleSheet.create({
  container:   { flex: 1 },
  addBtn:      { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 10 },
  hint:        { fontSize: FS.secondary, lineHeight: 19, marginBottom: 16 },
  center:      { alignItems: 'center', paddingTop: 60, paddingBottom: 20 },
  emptyTitle:  { fontSize: FS.heading, fontWeight: '700', marginTop: 12 },
  emptySub:    { fontSize: FS.body, marginTop: 6, textAlign: 'center', paddingHorizontal: 20 },
  card:        { borderRadius: 16, borderWidth: 1, padding: 14, marginBottom: 12 },
  cardHeader:  { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 8 },
  avatar:      { width: 44, height: 44, borderRadius: 22, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  avatarText:  { fontSize: 18, fontWeight: '800' },
  cardName:    { fontSize: FS.heading, fontWeight: '700' },
  cardTag:     { fontSize: FS.secondary, marginTop: 2 },
  tonePill:    { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 4 },
  bio:         { fontSize: FS.secondary, lineHeight: 18, marginBottom: 6 },
  specChip:    { flexDirection: 'row', alignItems: 'center', gap: 5, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4, alignSelf: 'flex-start', marginBottom: 8 },
  previewBox:  { borderRadius: 10, padding: 12, marginTop: 8, borderWidth: 1, marginBottom: 4 },
  previewLabel:{ fontSize: FS.micro, fontWeight: '800', letterSpacing: 0.5, marginBottom: 6 },
  cardActions: { flexDirection: 'row', gap: 0, marginTop: 10, borderTopWidth: 1, borderTopColor: c.border, paddingTop: 10 },
  actionBtn:   { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, minHeight: 32 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 16, borderBottomWidth: 1 },
  modalTitle:  { fontSize: FS.nav, fontWeight: '700' },
  label:       { fontSize: FS.caption, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 },
  input:       { borderRadius: 12, borderWidth: 1, padding: 12, fontSize: FS.body, marginTop: 2 },
});
