import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, RefreshControl, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';

const IS_WEB = Platform.OS === 'web';

function getYouTubeEmbedUrl(url: string): string | null {
  const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  return match ? `https://www.youtube.com/embed/${match[1]}?rel=0&modestbranding=1` : null;
}

interface Track {
  id: string; slug: string; title: string; description: string;
  icon: string; color: string; roles: string[];
  lesson_count: number; completed_count: number;
}

interface Lesson {
  id: string; slug: string; title: string; description: string;
  icon: string; duration: string; order: number;
  content: string; video_url: string; steps: string[];
}

export default function TrainingHubScreen() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<{ id: string; title: string; color: string; lessons: Lesson[] } | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<Lesson | null>(null);
  const [progress, setProgress] = useState<Record<string, boolean>>({});
  const user = useAuthStore((state) => state.user);
  const [saving, setSaving] = useState(false);

  useEffect(() => { loadData(); }, [user?._id]);

  const loadData = async () => {
    try {
      const userRole = user?.role || 'user';
      const [tracksRes, progressRes] = await Promise.all([
        api.get(`/training/tracks?role=${userRole}`),
        user?._id ? api.get(`/training/progress/${user._id}`).catch(() => ({ data: [] })) : Promise.resolve({ data: [] }),
      ]);
      setTracks(Array.isArray(tracksRes.data) ? tracksRes.data : []);
      const pm: Record<string, boolean> = {};
      if (Array.isArray(progressRes.data)) {
        progressRes.data.forEach((p: any) => { if (p.completed) pm[p.lesson_id] = true; });
      }
      setProgress(pm);
    } catch (e) { console.error(e); }
    finally { setLoading(false); setRefreshing(false); }
  };

  const openTrack = async (track: Track) => {
    try {
      const res = await api.get(`/training/tracks/${track.id}`);
      setSelectedTrack({ id: track.id, title: res.data.title, color: track.color, lessons: res.data.lessons || [] });
      setSelectedLesson(null);
    } catch (e) { console.error(e); }
  };

  const toggleComplete = async (lessonId: string, trackId: string) => {
    if (!user?._id) return;
    const current = progress[lessonId] || false;
    setSaving(true);
    try {
      await api.post('/training/progress', { user_id: user._id, lesson_id: lessonId, track_id: trackId, completed: !current });
      setProgress(prev => ({ ...prev, [lessonId]: !current }));
      // Update track counts
      setTracks(prev => prev.map(t => t.id === trackId ? { ...t, completed_count: t.completed_count + (current ? -1 : 1) } : t));
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  // Track video views — fires once per lesson open (deduped server-side per hour)
  const trackedLessons = React.useRef<Set<string>>(new Set());
  const trackVideoView = React.useCallback((lesson: Lesson, trackId: string) => {
    if (!lesson.video_url || !user?._id) return;
    const key = `${user._id}:${lesson.id}`;
    if (trackedLessons.current.has(key)) return;
    trackedLessons.current.add(key);
    api.post('/training/track-video-view', {
      user_id: user._id,
      lesson_id: lesson.id,
      track_id: trackId,
      lesson_title: lesson.title,
    }).catch(() => {});
  }, [user?._id]);

  const renderMarkdown = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <View key={i} style={{ height: 8 }} />;
      if (trimmed.startsWith('## ')) return <Text key={i} style={s.mdH2}>{trimmed.replace('## ', '')}</Text>;
      if (trimmed.startsWith('### ')) return <Text key={i} style={s.mdH3}>{trimmed.replace('### ', '')}</Text>;
      if (trimmed.startsWith('> ')) return <View key={i} style={s.mdQuote}><Text style={s.mdQuoteText}>{trimmed.replace('> ', '')}</Text></View>;
      if (trimmed.startsWith('- ')) return (
        <View key={i} style={s.mdListItem}>
          <Text style={s.mdBullet}>{'\u2022'}</Text>
          <Text style={s.mdListText}>{renderInline(trimmed.replace('- ', ''))}</Text>
        </View>
      );
      if (/^\d+\.\s/.test(trimmed)) return (
        <View key={i} style={s.mdListItem}>
          <Text style={s.mdBullet}>{trimmed.match(/^(\d+)\./)?.[1]}.</Text>
          <Text style={s.mdListText}>{renderInline(trimmed.replace(/^\d+\.\s/, ''))}</Text>
        </View>
      );
      if (trimmed.startsWith('*') && trimmed.endsWith('*') && !trimmed.startsWith('**')) return <Text key={i} style={s.mdItalic}>{trimmed.replace(/\*/g, '')}</Text>;
      return <Text key={i} style={s.mdParagraph}>{renderInline(trimmed)}</Text>;
    });
  };

  const renderInline = (text: string): string => {
    return text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1');
  };

  // ---- TRACK LIST VIEW ----
  const renderTrackList = () => (
    <View>
      <View style={s.heroSection}>
        <View style={s.heroIcon}><Ionicons name="school" size={32} color="#C9A962" /></View>
        <Text style={s.heroTitle}>Training Hub</Text>
        <Text style={s.heroDesc}>Role-based learning paths to get you up and running. Complete at your own pace — you can always come back.</Text>
      </View>

      {/* Overall Progress */}
      {tracks.length > 0 && (() => {
        const totalLessons = tracks.reduce((a, t) => a + t.lesson_count, 0);
        const totalDone = tracks.reduce((a, t) => a + t.completed_count, 0);
        const pct = totalLessons > 0 ? Math.round((totalDone / totalLessons) * 100) : 0;
        return (
          <View style={s.overallProgress}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary }}>Overall Progress</Text>
              <Text style={{ fontSize: 15, fontWeight: '700', color: '#C9A962' }}>{totalDone}/{totalLessons} lessons ({pct}%)</Text>
            </View>
            <View style={s.progressBar}><View style={[s.progressFill, { width: `${pct}%` }]} /></View>
          </View>
        );
      })()}

      {tracks.map(track => {
        const pct = track.lesson_count > 0 ? Math.round((track.completed_count / track.lesson_count) * 100) : 0;
        const allDone = track.completed_count === track.lesson_count && track.lesson_count > 0;
        return (
          <TouchableOpacity key={track.id} style={s.trackCard} onPress={() => openTrack(track)} activeOpacity={0.7} data-testid={`track-${track.slug}`}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
              <View style={[s.trackIconBox, { backgroundColor: track.color + '18' }]}>
                <Ionicons name={track.icon as any} size={24} color={track.color} />
              </View>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={s.trackTitle}>{track.title}</Text>
                  {allDone && <Ionicons name="checkmark-circle" size={18} color="#34C759" />}
                </View>
                <Text style={s.trackDesc} numberOfLines={2}>{track.description}</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8 }}>
                  <Text style={{ fontSize: 14, color: colors.textTertiary }}>{track.lesson_count} lessons</Text>
                  <View style={[s.progressBar, { flex: 1, height: 4 }]}><View style={[s.progressFill, { width: `${pct}%`, backgroundColor: track.color }]} /></View>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: track.color }}>{pct}%</Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.textTertiary} />
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  // ---- LESSON LIST VIEW ----
  const renderLessonList = () => {
    if (!selectedTrack) return null;
    const completedCount = selectedTrack.lessons.filter(l => progress[l.id]).length;
    return (
      <View>
        <TouchableOpacity onPress={() => setSelectedTrack(null)} style={s.breadcrumb}>
          <Ionicons name="arrow-back" size={18} color="#C9A962" />
          <Text style={{ fontSize: 16, color: '#C9A962', fontWeight: '600' }}>All Tracks</Text>
        </TouchableOpacity>
        <Text style={s.sectionTitle}>{selectedTrack.title}</Text>
        <Text style={{ fontSize: 15, color: colors.textSecondary, marginBottom: 16 }}>{completedCount}/{selectedTrack.lessons.length} lessons completed</Text>
        {selectedTrack.lessons.map((lesson, idx) => {
          const done = progress[lesson.id] || false;
          return (
            <TouchableOpacity key={lesson.id} style={[s.lessonCard, done && { borderLeftWidth: 3, borderLeftColor: '#34C759' }]}
              onPress={() => setSelectedLesson(lesson)} activeOpacity={0.7} data-testid={`lesson-${lesson.slug}`}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={[s.lessonNum, done && { backgroundColor: '#34C759', borderColor: '#34C759' }]}>
                  {done ? <Ionicons name="checkmark" size={14} color="#FFF" /> : <Text style={{ fontSize: 15, fontWeight: '700', color: colors.textTertiary }}>{idx + 1}</Text>}
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[s.lessonTitle, done && { color: colors.textSecondary }]}>{lesson.title}</Text>
                  <Text style={s.lessonMeta}>{lesson.description}</Text>
                </View>
                <View style={{ alignItems: 'flex-end', gap: 4 }}>
                  <Text style={{ fontSize: 13, color: colors.textTertiary }}>{lesson.duration}</Text>
                  <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                </View>
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    );
  };

  // ---- LESSON DETAIL VIEW ----
  const renderLessonDetail = () => {
    if (!selectedLesson || !selectedTrack) return null;
    const done = progress[selectedLesson.id] || false;
    const currIdx = selectedTrack.lessons.findIndex(l => l.id === selectedLesson.id);
    const nextLesson = currIdx < selectedTrack.lessons.length - 1 ? selectedTrack.lessons[currIdx + 1] : null;

    // Track video view when lesson renders (covers embedded YouTube — plays inline, never clicks a link)
    if (selectedLesson.video_url) {
      trackVideoView(selectedLesson, selectedTrack.id);
    }

    return (
      <View>
        <TouchableOpacity onPress={() => setSelectedLesson(null)} style={s.breadcrumb}>
          <Ionicons name="arrow-back" size={18} color="#C9A962" />
          <Text style={{ fontSize: 16, color: '#C9A962', fontWeight: '600' }}>{selectedTrack.title}</Text>
        </TouchableOpacity>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <View style={[s.lessonNum, { width: 32, height: 32, borderRadius: 8, backgroundColor: selectedTrack.color + '18', borderColor: selectedTrack.color }]}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: selectedTrack.color }}>{currIdx + 1}</Text>
          </View>
          <Text style={s.lessonDetailTitle}>{selectedLesson.title}</Text>
        </View>
        <Text style={{ fontSize: 14, color: colors.textTertiary, marginBottom: 20 }}>{selectedLesson.duration} read</Text>

        {/* Content */}
        <View style={s.contentCard}>
          {renderMarkdown(selectedLesson.content)}
        </View>

        {/* Video */}
        {selectedLesson.video_url ? (
          <View style={[s.contentCard, { marginTop: 12 }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Ionicons name="play-circle" size={20} color={selectedTrack.color} />
              <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Watch the Video</Text>
            </View>
            {IS_WEB && getYouTubeEmbedUrl(selectedLesson.video_url) ? (
              <View style={{ borderRadius: 12, overflow: 'hidden', aspectRatio: 16/9, width: '100%', backgroundColor: '#000' }}>
                <iframe
                  src={getYouTubeEmbedUrl(selectedLesson.video_url)!}
                  style={{ width: '100%', height: '100%', border: 'none' } as any}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              </View>
            ) : (
              <TouchableOpacity
                style={s.videoPlaceholder}
                onPress={() => {
                  trackVideoView(selectedLesson, selectedTrack.id);
                  Linking.openURL(selectedLesson.video_url);
                }}
                data-testid="open-video-btn"
              >
                <Ionicons name="play" size={32} color="#FFF" />
                <Text style={{ color: '#FFF', fontSize: 15, marginTop: 4 }}>Open Video</Text>
              </TouchableOpacity>
            )}
          </View>
        ) : null}

        {/* Action Steps */}
        {selectedLesson.steps && selectedLesson.steps.length > 0 && (
          <View style={[s.contentCard, { marginTop: 12, borderColor: selectedTrack.color, borderWidth: 1 }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Ionicons name="list" size={18} color={selectedTrack.color} />
              <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Action Steps</Text>
            </View>
            {selectedLesson.steps.map((step, i) => (
              <View key={i} style={{ flexDirection: 'row', gap: 10, paddingVertical: 6 }}>
                <View style={[s.stepCheck, { borderColor: selectedTrack.color }]}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: selectedTrack.color }}>{i + 1}</Text>
                </View>
                <Text style={{ flex: 1, fontSize: 16, color: colors.text, lineHeight: 20 }}>{step}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Mark Complete + Next */}
        <View style={{ marginTop: 20, gap: 10 }}>
          <TouchableOpacity style={[s.markBtn, done && s.markBtnDone]}
            onPress={() => toggleComplete(selectedLesson.id, selectedTrack.id)}
            disabled={saving} data-testid="mark-complete-btn">
            <Ionicons name={done ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={done ? '#FFF' : selectedTrack.color} />
            <Text style={[s.markBtnText, done && { color: '#FFF' }]}>{done ? 'Completed!' : 'Mark as Complete'}</Text>
          </TouchableOpacity>
          {nextLesson && (
            <TouchableOpacity style={s.nextBtn} onPress={() => { setSelectedLesson(nextLesson); scrollRef?.current?.scrollTo({ y: 0, animated: true }); }}>
              <Text style={{ fontSize: 17, fontWeight: '600', color: colors.textSecondary }}>Next: {nextLesson.title}</Text>
              <Ionicons name="arrow-forward" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
      </View>
    );
  };

  const scrollRef = React.useRef<ScrollView>(null);

  if (loading) return (
    <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}>
      <ActivityIndicator size="large" color="#C9A962" />
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => {
          if (selectedLesson) setSelectedLesson(null);
          else if (selectedTrack) setSelectedTrack(null);
          else router.back();
        }} style={s.headerBackBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>{selectedLesson ? selectedLesson.title : selectedTrack ? selectedTrack.title : 'Training Hub'}</Text>
        <View style={{ width: 36 }} />
      </View>
      <ScrollView ref={scrollRef} contentContainerStyle={s.content}
        refreshControl={!selectedTrack ? <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadData(); }} tintColor="#C9A962" /> : undefined}
        showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
        {selectedLesson ? renderLessonDetail() : selectedTrack ? renderLessonList() : renderTrackList()}
      </ScrollView>
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerBackBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: colors.text, flex: 1, textAlign: 'center' },
  content: { padding: 20, paddingBottom: 60, maxWidth: 700, alignSelf: 'center', width: '100%' },
  heroSection: { alignItems: 'center', paddingVertical: 24 },
  heroIcon: { width: 64, height: 64, borderRadius: 20, backgroundColor: '#C9A96218', alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  heroTitle: { fontSize: 26, fontWeight: '800', color: colors.text, marginBottom: 8 },
  heroDesc: { fontSize: 16, color: colors.textSecondary, textAlign: 'center', lineHeight: 20, maxWidth: 400 },
  overallProgress: { backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: colors.border },
  progressBar: { height: 6, backgroundColor: colors.border, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: '#C9A962', borderRadius: 3 },
  trackCard: { backgroundColor: colors.card, borderRadius: 14, padding: 18, marginBottom: 12, borderWidth: 1, borderColor: colors.border },
  trackIconBox: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  trackTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  trackDesc: { fontSize: 15, color: colors.textSecondary, marginTop: 2 },
  breadcrumb: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 16, paddingVertical: 4 },
  sectionTitle: { fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 4 },
  lessonCard: { backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  lessonNum: { width: 28, height: 28, borderRadius: 14, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  lessonTitle: { fontSize: 17, fontWeight: '600', color: colors.text },
  lessonMeta: { fontSize: 14, color: colors.textTertiary, marginTop: 2 },
  lessonDetailTitle: { fontSize: 22, fontWeight: '800', color: colors.text, flex: 1 },
  contentCard: { backgroundColor: colors.card, borderRadius: 14, padding: 20, borderWidth: 1, borderColor: colors.border },
  mdH2: { fontSize: 21, fontWeight: '800', color: colors.text, marginTop: 16, marginBottom: 8 },
  mdH3: { fontSize: 18, fontWeight: '700', color: colors.text, marginTop: 12, marginBottom: 6 },
  mdParagraph: { fontSize: 17, color: colors.text, lineHeight: 22, marginBottom: 4 },
  mdQuote: { borderLeftWidth: 3, borderLeftColor: '#C9A962', paddingLeft: 14, paddingVertical: 8, marginVertical: 8, backgroundColor: '#C9A96210', borderRadius: 4 },
  mdQuoteText: { fontSize: 17, color: colors.text, fontStyle: 'italic', lineHeight: 22 },
  mdListItem: { flexDirection: 'row', gap: 8, paddingVertical: 2, paddingLeft: 4 },
  mdBullet: { fontSize: 17, color: '#C9A962', fontWeight: '700', width: 16 },
  mdListText: { flex: 1, fontSize: 17, color: colors.text, lineHeight: 22 },
  mdItalic: { fontSize: 16, color: colors.textSecondary, fontStyle: 'italic', marginVertical: 4 },
  videoPlaceholder: { height: 120, borderRadius: 10, backgroundColor: '#333', alignItems: 'center', justifyContent: 'center' },
  stepCheck: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: 'center', justifyContent: 'center', marginTop: 1 },
  markBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, paddingVertical: 16, borderRadius: 14, borderWidth: 2, borderColor: '#C9A962' },
  markBtnDone: { backgroundColor: '#34C759', borderColor: '#34C759' },
  markBtnText: { fontSize: 18, fontWeight: '700', color: '#C9A962' },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
});
