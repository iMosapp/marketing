import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
  ActivityIndicator, RefreshControl, Image, Linking, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';

export default function TrainingReportsScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState('viewers');
  const [overview, setOverview] = useState(null);
  const [senders, setSenders] = useState([]);
  const [videos, setVideos] = useState([]);
  const [viewers, setViewers] = useState<{ by_user: any[]; by_lesson: any[]; total_views: number } | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [ovRes, sndRes, vidRes, viewRes] = await Promise.all([
        api.get('/admin/training-reports/overview'),
        api.get('/admin/training-reports/by-sender'),
        api.get('/admin/training-reports/by-video'),
        api.get('/admin/training-reports/viewers'),
      ]);
      setOverview(ovRes.data);
      setSenders(sndRes.data?.senders || []);
      setVideos(vidRes.data?.videos || []);
      setViewers(viewRes.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  const onRefresh = async () => { setRefreshing(true); await loadData(); setRefreshing(false); };

  const openYT = (url) => {
    if (Platform.OS === 'web') window.open(url, '_blank');
    else Linking.openURL(url);
  };

  const s = getS(colors);
  const ov = overview || {};

  const TABS = [
    { key: 'viewers', label: 'Who Watched', icon: 'eye-outline' },
    { key: 'overview', label: 'Overview', icon: 'analytics-outline' },
    { key: 'senders', label: 'By Sender', icon: 'people-outline' },
    { key: 'videos', label: 'By Video', icon: 'play-circle-outline' },
  ];

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="back-button">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={s.headerTitle}>Training Report</Text>
          <Text style={s.headerSub}>Video engagement analytics</Text>
        </View>
        <View style={{ width: 44 }} />
      </View>

      <View style={s.tabBar}>
        {TABS.map(t => (
          <TouchableOpacity
            key={t.key}
            style={[s.tab, tab === t.key && s.tabActive]}
            onPress={() => setTab(t.key)}
            data-testid={`tab-${t.key}`}
          >
            <Ionicons name={t.icon} size={16} color={tab === t.key ? '#C9A962' : colors.textSecondary} />
            <Text style={[s.tabText, tab === t.key && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        contentContainerStyle={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
      >
        {loading ? (
          <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 40 }} />
        ) : (
          <>
            {/* ===== OVERVIEW ===== */}
            {tab === 'overview' && (
              <>
                {/* Stats cards */}
                <View style={s.statsRow} data-testid="overview-stats">
                  <View style={s.statCard}>
                    <Ionicons name="play-circle" size={28} color="#AF52DE" />
                    <Text style={s.statNum}>{ov.total_videos_tracked || 0}</Text>
                    <Text style={s.statLabel}>Links Tracked</Text>
                  </View>
                  <View style={s.statCard}>
                    <Ionicons name="hand-left" size={28} color="#34C759" />
                    <Text style={s.statNum}>{ov.total_clicks || 0}</Text>
                    <Text style={s.statLabel}>Total Clicks</Text>
                  </View>
                </View>

                {/* Top Videos */}
                <View style={s.section} data-testid="top-videos-section">
                  <View style={s.sectionHeader}>
                    <Ionicons name="trending-up" size={18} color="#FF9500" />
                    <Text style={s.sectionTitle}>Top Videos</Text>
                  </View>
                  {(ov.videos || []).length === 0 ? (
                    <View style={s.emptyBlock}>
                      <Ionicons name="videocam-off-outline" size={36} color={colors.textSecondary} />
                      <Text style={s.emptyText}>No video activity yet</Text>
                      <Text style={s.emptySubtext}>Send training videos to contacts via templates to start tracking</Text>
                    </View>
                  ) : (
                    (ov.videos || []).map((v, i) => (
                      <TouchableOpacity
                        key={v.youtube_url || i}
                        style={s.videoRow}
                        onPress={() => openYT(v.youtube_url)}
                        data-testid={`video-${i}`}
                      >
                        <View style={s.rankBadge}>
                          <Text style={s.rankText}>#{i + 1}</Text>
                        </View>
                        {v.thumbnail ? (
                          <Image source={{ uri: v.thumbnail }} style={s.thumb} />
                        ) : (
                          <View style={[s.thumb, { backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }]}>
                            <Ionicons name="play" size={20} color={colors.textSecondary} />
                          </View>
                        )}
                        <View style={{ flex: 1 }}>
                          <Text style={s.videoTitle} numberOfLines={1}>{v.title}</Text>
                          <Text style={s.videoMeta}>{v.total_clicks} click{v.total_clicks !== 1 ? 's' : ''} | {v.unique_senders} sender{v.unique_senders !== 1 ? 's' : ''}</Text>
                        </View>
                        <Ionicons name="open-outline" size={16} color={colors.textSecondary} />
                      </TouchableOpacity>
                    ))
                  )}
                </View>

                {/* Recent Activity */}
                {(ov.recent_activity || []).length > 0 && (
                  <View style={s.section} data-testid="recent-activity-section">
                    <View style={s.sectionHeader}>
                      <Ionicons name="time-outline" size={18} color="#007AFF" />
                      <Text style={s.sectionTitle}>Recent Activity</Text>
                    </View>
                    {(ov.recent_activity || []).slice(0, 15).map((a, i) => (
                      <View key={i} style={s.activityRow}>
                        <Ionicons name="play-circle" size={18} color="#AF52DE" />
                        <View style={{ flex: 1, marginLeft: 8 }}>
                          <Text style={s.activityTitle}>{a.video_title}</Text>
                          <Text style={s.activityMeta}>
                            {a.timestamp ? new Date(a.timestamp).toLocaleString() : 'Unknown time'}
                          </Text>
                        </View>
                      </View>
                    ))}
                  </View>
                )}
              </>
            )}

            {/* ===== BY SENDER ===== */}
            {tab === 'senders' && (
              <View style={s.section} data-testid="senders-section">
                <View style={s.sectionHeader}>
                  <Ionicons name="people" size={18} color="#007AFF" />
                  <Text style={s.sectionTitle}>Senders Ranked by Engagement</Text>
                </View>
                {senders.length === 0 ? (
                  <View style={s.emptyBlock}>
                    <Ionicons name="people-outline" size={36} color={colors.textSecondary} />
                    <Text style={s.emptyText}>No sender data yet</Text>
                  </View>
                ) : (
                  senders.map((sender, i) => (
                    <View key={sender.user_id || i} style={s.senderRow} data-testid={`sender-${i}`}>
                      <View style={s.rankBadge}>
                        <Text style={s.rankText}>#{i + 1}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.senderName}>{sender.name}</Text>
                        <Text style={s.senderMeta}>
                          {sender.videos_sent} video{sender.videos_sent !== 1 ? 's' : ''} sent | {sender.total_clicks} click{sender.total_clicks !== 1 ? 's' : ''}
                        </Text>
                        {(sender.top_videos || []).slice(0, 3).map((v, j) => (
                          <View key={j} style={s.senderVideoRow}>
                            <Ionicons name="play-circle-outline" size={14} color="#AF52DE" />
                            <Text style={s.senderVideoText} numberOfLines={1}>{v.title} ({v.clicks} click{v.clicks !== 1 ? 's' : ''})</Text>
                          </View>
                        ))}
                      </View>
                    </View>
                  ))
                )}
              </View>
            )}

            {/* ===== BY VIDEO ===== */}
            {tab === 'videos' && (
              <View style={s.section} data-testid="videos-section">
                <View style={s.sectionHeader}>
                  <Ionicons name="play-circle" size={18} color="#AF52DE" />
                  <Text style={s.sectionTitle}>All Videos</Text>
                </View>
                {videos.length === 0 ? (
                  <View style={s.emptyBlock}>
                    <Ionicons name="videocam-off-outline" size={36} color={colors.textSecondary} />
                    <Text style={s.emptyText}>No videos tracked yet</Text>
                  </View>
                ) : (
                  videos.map((v, i) => (
                    <TouchableOpacity
                      key={v.youtube_url || i}
                      style={s.videoDetailRow}
                      onPress={() => openYT(v.youtube_url)}
                      data-testid={`video-detail-${i}`}
                    >
                      {v.thumbnail ? (
                        <Image source={{ uri: v.thumbnail }} style={s.thumbLg} />
                      ) : (
                        <View style={[s.thumbLg, { backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }]}>
                          <Ionicons name="play" size={24} color={colors.textSecondary} />
                        </View>
                      )}
                      <View style={{ flex: 1, marginLeft: 12 }}>
                        <Text style={s.videoTitle}>{v.title}</Text>
                        <View style={s.videoStatsRow}>
                          <View style={s.videoStatItem}>
                            <Ionicons name="hand-left-outline" size={14} color="#34C759" />
                            <Text style={s.videoStatText}>{v.total_clicks} clicks</Text>
                          </View>
                          <View style={s.videoStatItem}>
                            <Ionicons name="send-outline" size={14} color="#007AFF" />
                            <Text style={s.videoStatText}>{v.times_sent}x sent</Text>
                          </View>
                          <View style={s.videoStatItem}>
                            <Ionicons name="person-outline" size={14} color="#FF9500" />
                            <Text style={s.videoStatText}>{v.unique_senders} senders</Text>
                          </View>
                        </View>
                      </View>
                      <Ionicons name="open-outline" size={16} color={colors.textSecondary} />
                    </TouchableOpacity>
                  ))
                )}
              </View>
            )}

            {/* ===== WHO WATCHED ===== */}
            {tab === 'viewers' && (
              <View style={s.section} data-testid="viewers-section">
                {/* Summary stats */}
                <View style={s.statsRow}>
                  <View style={s.statCard}>
                    <Ionicons name="eye" size={28} color="#C9A962" />
                    <Text style={s.statNum}>{viewers?.total_views || 0}</Text>
                    <Text style={s.statLabel}>Total Views</Text>
                  </View>
                  <View style={s.statCard}>
                    <Ionicons name="people" size={28} color="#007AFF" />
                    <Text style={s.statNum}>{viewers?.by_user?.length || 0}</Text>
                    <Text style={s.statLabel}>Unique Viewers</Text>
                  </View>
                  <View style={s.statCard}>
                    <Ionicons name="book" size={28} color="#34C759" />
                    <Text style={s.statNum}>{viewers?.by_lesson?.length || 0}</Text>
                    <Text style={s.statLabel}>Lessons Viewed</Text>
                  </View>
                </View>

                {/* Per-user table */}
                <View style={s.sectionHeader}>
                  <Ionicons name="people-outline" size={18} color="#007AFF" />
                  <Text style={s.sectionTitle}>By Team Member</Text>
                </View>
                {(viewers?.by_user?.length || 0) === 0 ? (
                  <View style={s.emptyBlock}>
                    <Ionicons name="eye-off-outline" size={36} color={colors.textSecondary} />
                    <Text style={s.emptyText}>No video views tracked yet</Text>
                    <Text style={[s.emptyText, { fontSize: 13, marginTop: 4 }]}>Views are recorded when team members open lesson videos</Text>
                  </View>
                ) : (
                  (viewers?.by_user || []).map((u: any, i: number) => (
                    <View key={u.user_id || i} style={s.senderRow} data-testid={`viewer-row-${i}`}>
                      <View style={[s.senderAvatar, { backgroundColor: '#007AFF20' }]}>
                        <Text style={[s.senderInitials, { color: '#007AFF' }]}>
                          {(u.name || '?').split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()}
                        </Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.senderName}>{u.name || 'Unknown'}</Text>
                        <Text style={s.senderSub}>{u.email}</Text>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={{ fontSize: 18, fontWeight: '800', color: '#C9A962' }}>{u.lessons_viewed}</Text>
                        <Text style={{ fontSize: 12, color: colors.textSecondary }}>lessons watched</Text>
                      </View>
                    </View>
                  ))
                )}

                {/* Per-lesson table */}
                {(viewers?.by_lesson?.length || 0) > 0 && (
                  <>
                    <View style={[s.sectionHeader, { marginTop: 24 }]}>
                      <Ionicons name="play-circle-outline" size={18} color="#AF52DE" />
                      <Text style={s.sectionTitle}>By Lesson</Text>
                    </View>
                    {(viewers?.by_lesson || []).map((l: any, i: number) => (
                      <View key={l.lesson_id || i} style={[s.senderRow, { alignItems: 'flex-start' }]} data-testid={`lesson-row-${i}`}>
                        <View style={[s.senderAvatar, { backgroundColor: '#AF52DE20' }]}>
                          <Ionicons name="play" size={16} color="#AF52DE" />
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={s.senderName}>{l.lesson_title}</Text>
                          <Text style={s.senderSub} numberOfLines={2}>{(l.viewer_names || []).join(', ') || 'No views yet'}</Text>
                        </View>
                        <View style={{ alignItems: 'flex-end' }}>
                          <Text style={{ fontSize: 18, fontWeight: '800', color: '#AF52DE' }}>{l.unique_viewers}</Text>
                          <Text style={{ fontSize: 12, color: colors.textSecondary }}>viewers</Text>
                        </View>
                      </View>
                    ))}
                  </>
                )}
              </View>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getS = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card },
  backBtn: { padding: 4, minWidth: 44 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  headerSub: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },

  tabBar: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: colors.surface, paddingHorizontal: 8 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 10 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#C9A962' },
  tabText: { fontSize: 13, color: colors.textSecondary, fontWeight: '500' },
  tabTextActive: { color: '#C9A962', fontWeight: '600' },

  scroll: { padding: 16 },

  statsRow: { flexDirection: 'row', gap: 12, marginBottom: 16 },
  statCard: { flex: 1, backgroundColor: colors.card, borderRadius: 14, padding: 16, alignItems: 'center', borderWidth: 1, borderColor: colors.surface },
  statNum: { fontSize: 28, fontWeight: '800', color: colors.text, marginTop: 6 },
  statLabel: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },

  section: { backgroundColor: colors.card, borderRadius: 14, marginBottom: 16, borderWidth: 1, borderColor: colors.surface, overflow: 'hidden' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 14, borderBottomWidth: 1, borderBottomColor: colors.surface },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: colors.text, flex: 1 },

  emptyBlock: { padding: 30, alignItems: 'center', gap: 8 },
  emptyText: { fontSize: 16, color: colors.textSecondary, fontWeight: '600' },
  emptySubtext: { fontSize: 14, color: colors.textSecondary, textAlign: 'center' },

  videoRow: { flexDirection: 'row', alignItems: 'center', padding: 12, gap: 10, borderBottomWidth: 1, borderBottomColor: colors.surface },
  rankBadge: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center' },
  rankText: { fontSize: 12, fontWeight: '700', color: '#C9A962' },
  thumb: { width: 56, height: 42, borderRadius: 6, backgroundColor: colors.surface },
  videoTitle: { fontSize: 15, fontWeight: '600', color: colors.text },
  videoMeta: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },

  activityRow: { flexDirection: 'row', alignItems: 'center', padding: 10, borderBottomWidth: 1, borderBottomColor: colors.surface },
  activityTitle: { fontSize: 15, fontWeight: '500', color: colors.text },
  activityMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },

  senderRow: { flexDirection: 'row', alignItems: 'flex-start', padding: 12, gap: 10, borderBottomWidth: 1, borderBottomColor: colors.surface },
  senderName: { fontSize: 16, fontWeight: '700', color: colors.text },
  senderMeta: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  senderVideoRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  senderVideoText: { fontSize: 13, color: colors.textSecondary },

  videoDetailRow: { flexDirection: 'row', alignItems: 'center', padding: 12, borderBottomWidth: 1, borderBottomColor: colors.surface },
  thumbLg: { width: 72, height: 54, borderRadius: 8, backgroundColor: colors.surface },
  videoStatsRow: { flexDirection: 'row', gap: 12, marginTop: 6 },
  videoStatItem: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  videoStatText: { fontSize: 12, color: colors.textSecondary },
});
