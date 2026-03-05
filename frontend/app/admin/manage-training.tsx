import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, TextInput, Alert, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';

interface Track {
  id: string; slug: string; title: string; description: string;
  icon: string; color: string; roles: string[]; order: number; lesson_count: number;
}

interface Lesson {
  id: string; slug: string; title: string; description: string;
  icon: string; duration: string; order: number;
  content: string; video_url: string; steps: string[];
}

const ALL_ROLES = [
  { key: 'user', label: 'Sales / Internal Hires' },
  { key: 'manager', label: 'Managers' },
  { key: 'admin', label: 'Admins' },
  { key: 'store_manager', label: 'Store Managers' },
  { key: 'partner', label: 'Partners' },
  { key: 'reseller', label: 'Resellers' },
  { key: 'super_admin', label: 'Super Admins' },
];

export default function ManageTrainingPage() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();

  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Track editing
  const [editingTrack, setEditingTrack] = useState<Track | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editColor, setEditColor] = useState('');
  const [editRoles, setEditRoles] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // Lesson management
  const [expandedTrack, setExpandedTrack] = useState<string | null>(null);
  const [trackLessons, setTrackLessons] = useState<Record<string, Lesson[]>>({});
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const [lessonForm, setLessonForm] = useState({ title: '', description: '', content: '', duration: '', video_url: '', steps: '' });

  // New track form
  const [showNewTrack, setShowNewTrack] = useState(false);
  const [newTrackTitle, setNewTrackTitle] = useState('');
  const [newTrackDesc, setNewTrackDesc] = useState('');
  const [newTrackColor, setNewTrackColor] = useState('#007AFF');
  const [newTrackRoles, setNewTrackRoles] = useState<string[]>([]);

  // New lesson form
  const [addingLessonTo, setAddingLessonTo] = useState<string | null>(null);
  const [newLessonTitle, setNewLessonTitle] = useState('');
  const [newLessonDesc, setNewLessonDesc] = useState('');

  useEffect(() => { loadTracks(); }, []);

  const loadTracks = async () => {
    try {
      const res = await api.get('/training/admin/tracks');
      setTracks(Array.isArray(res.data) ? res.data : []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); setRefreshing(false); }
  };

  const loadLessons = async (trackId: string) => {
    try {
      const res = await api.get(`/training/admin/tracks/${trackId}/lessons`);
      setTrackLessons(prev => ({ ...prev, [trackId]: res.data || [] }));
    } catch (e) { console.error(e); }
  };

  const toggleExpand = (trackId: string) => {
    if (expandedTrack === trackId) {
      setExpandedTrack(null);
      return;
    }
    setExpandedTrack(trackId);
    if (!trackLessons[trackId]) loadLessons(trackId);
  };

  const startEditTrack = (t: Track) => {
    setEditingTrack(t);
    setEditTitle(t.title);
    setEditDesc(t.description);
    setEditColor(t.color || '#007AFF');
    setEditRoles(t.roles || []);
  };

  const saveTrack = async () => {
    if (!editingTrack) return;
    setSaving(true);
    try {
      await api.put(`/training/admin/tracks/${editingTrack.id}`, {
        title: editTitle, description: editDesc, color: editColor, roles: editRoles,
      });
      setEditingTrack(null);
      loadTracks();
    } catch (e) { console.error(e); Alert.alert('Error', 'Failed to save track'); }
    finally { setSaving(false); }
  };

  const createTrack = async () => {
    if (!newTrackTitle.trim()) return;
    setSaving(true);
    try {
      await api.post('/training/admin/tracks', {
        title: newTrackTitle, description: newTrackDesc, color: newTrackColor, roles: newTrackRoles,
      });
      setShowNewTrack(false);
      setNewTrackTitle(''); setNewTrackDesc(''); setNewTrackRoles([]);
      loadTracks();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const deleteTrack = (trackId: string, title: string) => {
    Alert.alert('Delete Track', `Delete "${title}" and all its lessons?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        await api.delete(`/training/admin/tracks/${trackId}`);
        loadTracks();
      }},
    ]);
  };

  const startEditLesson = (l: Lesson) => {
    setEditingLesson(l);
    setLessonForm({
      title: l.title, description: l.description, content: l.content,
      duration: l.duration, video_url: l.video_url || '',
      steps: (l.steps || []).join('\n'),
    });
  };

  const saveLesson = async () => {
    if (!editingLesson) return;
    setSaving(true);
    try {
      await api.put(`/training/lessons/${editingLesson.id}`, {
        title: lessonForm.title, description: lessonForm.description,
        content: lessonForm.content, duration: lessonForm.duration,
        video_url: lessonForm.video_url,
        steps: lessonForm.steps.split('\n').filter(s => s.trim()),
      });
      setEditingLesson(null);
      if (expandedTrack) loadLessons(expandedTrack);
    } catch (e) { console.error(e); Alert.alert('Error', 'Failed to save lesson'); }
    finally { setSaving(false); }
  };

  const createLesson = async (trackId: string) => {
    if (!newLessonTitle.trim()) return;
    setSaving(true);
    try {
      const existing = trackLessons[trackId]?.length || 0;
      await api.post(`/training/admin/tracks/${trackId}/lessons`, {
        title: newLessonTitle, description: newLessonDesc, order: existing + 1,
      });
      setAddingLessonTo(null);
      setNewLessonTitle(''); setNewLessonDesc('');
      loadLessons(trackId);
      loadTracks();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const deleteLesson = (lessonId: string, title: string, trackId: string) => {
    Alert.alert('Delete Lesson', `Delete "${title}"?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        await api.delete(`/training/admin/lessons/${lessonId}`);
        loadLessons(trackId);
        loadTracks();
      }},
    ]);
  };

  const toggleRole = (role: string, currentRoles: string[], setter: (r: string[]) => void) => {
    setter(currentRoles.includes(role) ? currentRoles.filter(r => r !== role) : [...currentRoles, role]);
  };

  // ---- LESSON EDITOR MODAL ----
  if (editingLesson) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => setEditingLesson(null)} style={s.backBtn}>
            <Ionicons name="close" size={22} color={colors.text} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Edit Lesson</Text>
          <TouchableOpacity onPress={saveLesson} disabled={saving} style={s.saveBtn} data-testid="save-lesson-btn">
            <Text style={s.saveBtnText}>{saving ? 'Saving...' : 'Save'}</Text>
          </TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={s.formContent} keyboardShouldPersistTaps="handled">
          <Text style={s.label}>Title</Text>
          <TextInput style={s.input} value={lessonForm.title} onChangeText={v => setLessonForm(p => ({ ...p, title: v }))} placeholder="Lesson title" placeholderTextColor={colors.textTertiary} data-testid="lesson-title-input" />

          <Text style={s.label}>Description</Text>
          <TextInput style={s.input} value={lessonForm.description} onChangeText={v => setLessonForm(p => ({ ...p, description: v }))} placeholder="Short description" placeholderTextColor={colors.textTertiary} data-testid="lesson-desc-input" />

          <Text style={s.label}>Duration</Text>
          <TextInput style={s.input} value={lessonForm.duration} onChangeText={v => setLessonForm(p => ({ ...p, duration: v }))} placeholder="e.g. 5 min" placeholderTextColor={colors.textTertiary} data-testid="lesson-duration-input" />

          <Text style={s.label}>Video URL (optional)</Text>
          <TextInput style={s.input} value={lessonForm.video_url} onChangeText={v => setLessonForm(p => ({ ...p, video_url: v }))} placeholder="https://..." placeholderTextColor={colors.textTertiary} data-testid="lesson-video-input" />

          <Text style={s.label}>Content (Markdown)</Text>
          <TextInput style={[s.input, s.textArea]} value={lessonForm.content} onChangeText={v => setLessonForm(p => ({ ...p, content: v }))} placeholder="Lesson content in Markdown..." placeholderTextColor={colors.textTertiary} multiline numberOfLines={12} textAlignVertical="top" data-testid="lesson-content-input" />

          <Text style={s.label}>Action Steps (one per line)</Text>
          <TextInput style={[s.input, s.textArea, { minHeight: 100 }]} value={lessonForm.steps} onChangeText={v => setLessonForm(p => ({ ...p, steps: v }))} placeholder="Step 1&#10;Step 2&#10;Step 3" placeholderTextColor={colors.textTertiary} multiline numberOfLines={5} textAlignVertical="top" data-testid="lesson-steps-input" />
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ---- TRACK EDITOR MODAL ----
  if (editingTrack) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => setEditingTrack(null)} style={s.backBtn}>
            <Ionicons name="close" size={22} color={colors.text} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Edit Track</Text>
          <TouchableOpacity onPress={saveTrack} disabled={saving} style={s.saveBtn} data-testid="save-track-btn">
            <Text style={s.saveBtnText}>{saving ? 'Saving...' : 'Save'}</Text>
          </TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={s.formContent} keyboardShouldPersistTaps="handled">
          <Text style={s.label}>Title</Text>
          <TextInput style={s.input} value={editTitle} onChangeText={setEditTitle} placeholderTextColor={colors.textTertiary} data-testid="track-title-input" />

          <Text style={s.label}>Description</Text>
          <TextInput style={[s.input, { minHeight: 80 }]} value={editDesc} onChangeText={setEditDesc} multiline placeholderTextColor={colors.textTertiary} data-testid="track-desc-input" />

          <Text style={s.label}>Color</Text>
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {['#007AFF', '#C9A962', '#34C759', '#AF52DE', '#FF3B30', '#FF9500', '#5AC8FA', '#FF2D55'].map(c => (
              <TouchableOpacity key={c} onPress={() => setEditColor(c)}
                style={[s.colorDot, { backgroundColor: c, borderWidth: editColor === c ? 3 : 0, borderColor: '#FFF' }]} />
            ))}
          </View>

          <Text style={s.label}>Visible to Roles</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
            {ALL_ROLES.map(r => (
              <TouchableOpacity key={r.key} onPress={() => toggleRole(r.key, editRoles, setEditRoles)}
                style={[s.roleChip, editRoles.includes(r.key) && { backgroundColor: editColor || '#C9A962', borderColor: editColor || '#C9A962' }]}>
                <Text style={[s.roleChipText, editRoles.includes(r.key) && { color: '#FFF' }]}>{r.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ---- NEW TRACK FORM ----
  if (showNewTrack) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => setShowNewTrack(false)} style={s.backBtn}>
            <Ionicons name="close" size={22} color={colors.text} />
          </TouchableOpacity>
          <Text style={s.headerTitle}>New Track</Text>
          <TouchableOpacity onPress={createTrack} disabled={saving || !newTrackTitle.trim()} style={s.saveBtn} data-testid="create-track-btn">
            <Text style={s.saveBtnText}>{saving ? 'Creating...' : 'Create'}</Text>
          </TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={s.formContent} keyboardShouldPersistTaps="handled">
          <Text style={s.label}>Track Title</Text>
          <TextInput style={s.input} value={newTrackTitle} onChangeText={setNewTrackTitle} placeholder="e.g. Service Advisor Training" placeholderTextColor={colors.textTertiary} data-testid="new-track-title-input" />

          <Text style={s.label}>Description</Text>
          <TextInput style={[s.input, { minHeight: 80 }]} value={newTrackDesc} onChangeText={setNewTrackDesc} placeholder="What this track covers..." multiline placeholderTextColor={colors.textTertiary} data-testid="new-track-desc-input" />

          <Text style={s.label}>Color</Text>
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {['#007AFF', '#C9A962', '#34C759', '#AF52DE', '#FF3B30', '#FF9500', '#5AC8FA', '#FF2D55'].map(c => (
              <TouchableOpacity key={c} onPress={() => setNewTrackColor(c)}
                style={[s.colorDot, { backgroundColor: c, borderWidth: newTrackColor === c ? 3 : 0, borderColor: '#FFF' }]} />
            ))}
          </View>

          <Text style={s.label}>Visible to Roles</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {ALL_ROLES.map(r => (
              <TouchableOpacity key={r.key} onPress={() => toggleRole(r.key, newTrackRoles, setNewTrackRoles)}
                style={[s.roleChip, newTrackRoles.includes(r.key) && { backgroundColor: newTrackColor, borderColor: newTrackColor }]}>
                <Text style={[s.roleChipText, newTrackRoles.includes(r.key) && { color: '#FFF' }]}>{r.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  if (loading) return (
    <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}>
      <ActivityIndicator size="large" color="#C9A962" />
    </SafeAreaView>
  );

  // ---- MAIN TRACK LIST ----
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Manage Training</Text>
        <TouchableOpacity onPress={() => setShowNewTrack(true)} style={s.addBtn} data-testid="add-track-btn">
          <Ionicons name="add" size={22} color="#C9A962" />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadTracks(); }} tintColor="#C9A962" />}>

        <View style={s.infoBanner}>
          <Ionicons name="information-circle" size={20} color="#C9A962" />
          <Text style={s.infoText}>Manage your LMS tracks and lessons. Each track is shown to users based on their role. Tap a track to manage its lessons.</Text>
        </View>

        {tracks.map(track => {
          const isExpanded = expandedTrack === track.id;
          const lessons = trackLessons[track.id] || [];
          return (
            <View key={track.id} style={s.trackCard} data-testid={`admin-track-${track.slug}`}>
              <TouchableOpacity onPress={() => toggleExpand(track.id)} activeOpacity={0.7} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={[s.trackDot, { backgroundColor: track.color || '#007AFF' }]} />
                <View style={{ flex: 1 }}>
                  <Text style={s.trackTitle}>{track.title}</Text>
                  <Text style={s.trackMeta}>{track.lesson_count} lessons · {(track.roles || []).length} roles</Text>
                </View>
                <TouchableOpacity onPress={() => startEditTrack(track)} style={s.iconBtn} data-testid={`edit-track-${track.slug}`}>
                  <Ionicons name="pencil" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity onPress={() => deleteTrack(track.id, track.title)} style={s.iconBtn} data-testid={`delete-track-${track.slug}`}>
                  <Ionicons name="trash" size={16} color="#FF3B30" />
                </TouchableOpacity>
                <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textTertiary} />
              </TouchableOpacity>

              {/* Role pills */}
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                {(track.roles || []).map(r => (
                  <View key={r} style={[s.rolePill, { backgroundColor: (track.color || '#007AFF') + '20' }]}>
                    <Text style={[s.rolePillText, { color: track.color || '#007AFF' }]}>{ALL_ROLES.find(ar => ar.key === r)?.label || r}</Text>
                  </View>
                ))}
              </View>

              {/* Expanded lessons */}
              {isExpanded && (
                <View style={s.lessonsContainer}>
                  {lessons.length === 0 && (
                    <Text style={{ color: colors.textTertiary, fontSize: 13, textAlign: 'center', paddingVertical: 12 }}>No lessons yet. Add one below.</Text>
                  )}
                  {lessons.map((lesson, idx) => (
                    <View key={lesson.id} style={s.lessonRow}>
                      <View style={s.lessonNumBadge}><Text style={s.lessonNumText}>{idx + 1}</Text></View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.lessonTitle}>{lesson.title}</Text>
                        <Text style={s.lessonDesc}>{lesson.description || 'No description'}</Text>
                      </View>
                      <Text style={{ fontSize: 11, color: colors.textTertiary, marginRight: 8 }}>{lesson.duration}</Text>
                      <TouchableOpacity onPress={() => startEditLesson(lesson)} style={s.iconBtn} data-testid={`edit-lesson-${lesson.slug}`}>
                        <Ionicons name="pencil" size={14} color={colors.textSecondary} />
                      </TouchableOpacity>
                      <TouchableOpacity onPress={() => deleteLesson(lesson.id, lesson.title, track.id)} style={s.iconBtn} data-testid={`delete-lesson-${lesson.slug}`}>
                        <Ionicons name="trash" size={14} color="#FF3B30" />
                      </TouchableOpacity>
                    </View>
                  ))}

                  {/* Add Lesson */}
                  {addingLessonTo === track.id ? (
                    <View style={s.addLessonForm}>
                      <TextInput style={s.input} value={newLessonTitle} onChangeText={setNewLessonTitle} placeholder="Lesson title" placeholderTextColor={colors.textTertiary} data-testid="new-lesson-title-input" />
                      <TextInput style={s.input} value={newLessonDesc} onChangeText={setNewLessonDesc} placeholder="Short description" placeholderTextColor={colors.textTertiary} data-testid="new-lesson-desc-input" />
                      <View style={{ flexDirection: 'row', gap: 8 }}>
                        <TouchableOpacity onPress={() => { setAddingLessonTo(null); setNewLessonTitle(''); setNewLessonDesc(''); }} style={[s.actionBtn, { backgroundColor: colors.card }]}>
                          <Text style={{ color: colors.textSecondary, fontWeight: '600' }}>Cancel</Text>
                        </TouchableOpacity>
                        <TouchableOpacity onPress={() => createLesson(track.id)} disabled={saving || !newLessonTitle.trim()} style={[s.actionBtn, { backgroundColor: track.color || '#C9A962' }]} data-testid="confirm-add-lesson-btn">
                          <Text style={{ color: '#FFF', fontWeight: '600' }}>{saving ? 'Adding...' : 'Add Lesson'}</Text>
                        </TouchableOpacity>
                      </View>
                    </View>
                  ) : (
                    <TouchableOpacity onPress={() => setAddingLessonTo(track.id)} style={s.addLessonBtn} data-testid={`add-lesson-to-${track.slug}`}>
                      <Ionicons name="add-circle" size={18} color={track.color || '#C9A962'} />
                      <Text style={{ color: track.color || '#C9A962', fontWeight: '600', fontSize: 14 }}>Add Lesson</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}
            </View>
          );
        })}

        {tracks.length === 0 && (
          <View style={s.emptyState}>
            <Ionicons name="school-outline" size={48} color={colors.textTertiary} />
            <Text style={{ color: colors.textSecondary, fontSize: 16, marginTop: 12 }}>No training tracks yet</Text>
            <Text style={{ color: colors.textTertiary, fontSize: 13, marginTop: 4 }}>Tap + to create your first track</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' },
  backBtn: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  addBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#C9A96218', alignItems: 'center', justifyContent: 'center' },
  saveBtn: { paddingHorizontal: 16, paddingVertical: 8, backgroundColor: '#C9A962', borderRadius: 8 },
  saveBtnText: { color: '#000', fontWeight: '700', fontSize: 14 },
  content: { padding: 16, paddingBottom: 60 },
  formContent: { padding: 20, paddingBottom: 60 },
  infoBanner: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', backgroundColor: '#C9A96210', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#C9A96230' },
  infoText: { flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 19 },
  trackCard: { backgroundColor: colors.card, borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.border },
  trackDot: { width: 12, height: 12, borderRadius: 6 },
  trackTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  trackMeta: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
  iconBtn: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  rolePill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  rolePillText: { fontSize: 11, fontWeight: '600' },
  lessonsContainer: { marginTop: 14, paddingTop: 14, borderTopWidth: 1, borderTopColor: colors.border },
  lessonRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  lessonNumBadge: { width: 24, height: 24, borderRadius: 12, backgroundColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  lessonNumText: { fontSize: 11, fontWeight: '700', color: colors.textSecondary },
  lessonTitle: { fontSize: 14, fontWeight: '600', color: colors.text },
  lessonDesc: { fontSize: 12, color: colors.textTertiary, marginTop: 1 },
  addLessonBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, marginTop: 4 },
  addLessonForm: { marginTop: 10, gap: 10, padding: 12, backgroundColor: colors.bg, borderRadius: 10 },
  actionBtn: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 8 },
  label: { fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 12 },
  input: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: colors.text },
  textArea: { minHeight: 200, textAlignVertical: 'top' },
  colorDot: { width: 32, height: 32, borderRadius: 16 },
  roleChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card },
  roleChipText: { fontSize: 13, fontWeight: '600', color: colors.text },
  emptyState: { alignItems: 'center', paddingVertical: 60 },
});
