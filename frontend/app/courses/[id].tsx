import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { useToast } from '../../components/common/Toast';
import { openUrl } from '../../components/mystery-shops/ReportView';
import { ScoreRing } from '../../components/scorecards/ScoreRing';
import { CourseProgress, ChallengeStatusRow, type Course, type CourseChallenge, type Enrollment } from '../../components/courses/shared';
import { Sheet, Label, GoldButton, deptLabel, loadIndustries, fmtWhen, GOLD, GREEN, tid } from '../../components/mystery-shops/shared';

// A rep's view of a course they are enrolled in: what is passed, what is next, practice any challenge, grab the certificate.
export default function MyCourse() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [course, setCourse] = useState<Course | null>(null);
  const [challenges, setChallenges] = useState<CourseChallenge[]>([]);
  const [me, setMe] = useState<Enrollment | null>(null);
  const [open, setOpen] = useState<CourseChallenge | null>(null);
  const load = useCallback(async () => {
    loadIndustries();
    try { const r = await api.get(`/courses/${id}`); setCourse(r.data.course); setChallenges(r.data.challenges); setMe(r.data.my_enrollment); }
    catch { showToast('Course not found', 'error'); router.back(); }
  }, [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (!course) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}><ActivityIndicator style={{ marginTop: 80 }} color={GOLD} /></SafeAreaView>;
  const pct = me && me.total ? Math.round((100 * me.passed) / me.total) : 0;
  const next = challenges.find(c => c.id === me?.next_challenge_id);
  const practice = (c: CourseChallenge) => { setOpen(null); router.push(`/scripts/practice?script=${c.id}&enrollment=${me?.id || ''}&course=${course.id}` as any); };
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={course.title} subtitle={`${course.department === 'mixed' ? 'Mixed' : deptLabel(course.department)} · pass every challenge at ${course.pass_pct}%`} testID="my-course-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 18 }}>
        {!me ? <Text style={{ fontSize: 14, color: colors.textSecondary }} {...tid('my-course-not-enrolled')}>You are not enrolled in this course. Ask your manager to add you.</Text> : (
          <>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, backgroundColor: colors.card, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: me.status === 'certified' ? GREEN + '88' : colors.border }} {...tid('my-course-hero')}>
              <ScoreRing pct={pct} size={84} stroke={8} colors={colors} label={me.status === 'certified' ? 'done' : 'passed'} />
              <View style={{ flex: 1, gap: 6 }}>
                <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>{me.status === 'certified' ? course.badge_label : `${me.passed} of ${me.total} passed`}</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{me.status === 'certified' ? `Certified ${fmtWhen(me.certified_at)}. Nice work.` : next ? `Up next: ${next.title}` : 'Pick any challenge below to practice.'}</Text>
                {me.status !== 'certified' && next && <GoldButton label="Practice the next one" onPress={() => practice(next)} testID="my-course-next" icon="call" />}
              </View>
            </View>
            {me.status === 'certified' && (
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <View style={{ flex: 1 }}><GoldButton label="Share my certificate" onPress={async () => { await Clipboard.setStringAsync(me.certificate_url || ''); showToast('Certificate link copied', 'success'); }} testID="my-course-cert-copy" icon="share-social" color={GREEN} /></View>
                <TouchableOpacity onPress={() => openUrl(me.certificate_url || '')} style={{ width: 48, height: 48, borderRadius: 14, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('my-course-cert-open')}><Ionicons name="open-outline" size={18} color={colors.text} /></TouchableOpacity>
              </View>
            )}
            {!!course.description && <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }}>{course.description}</Text>}
            <View style={{ gap: 8 }}>
              <Label t="CHALLENGES" colors={colors} />
              {challenges.map((c, i) => <TouchableOpacity key={c.id} onPress={() => setOpen(c)} activeOpacity={0.85} {...tid(`my-challenge-${c.id}`)}><ChallengeStatusRow c={c} p={me.progress[c.id]} passPct={course.pass_pct} colors={colors} index={i} onPress={() => setOpen(c)} /></TouchableOpacity>)}
            </View>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Best attempt counts and you can retry as often as you like. Jessi plays the customer on a real phone call, then you get the same scorecard your manager sees.</Text>
          </>
        )}
      </ScrollView>
      <Sheet visible={!!open} onClose={() => setOpen(null)} title={open?.title || ''} colors={colors} testID="my-challenge-sheet" footer={open ? <GoldButton label="Practice this by phone" onPress={() => practice(open)} testID="my-challenge-practice" icon="call" /> : undefined}>
        {open && me && (
          <>
            <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{deptLabel(open.department).toUpperCase()}{open.runtime ? ` · ${open.runtime}` : ''}</Text>
            {!!open.purpose && <Text style={{ fontSize: 14.5, color: colors.text, lineHeight: 21 }}>{open.purpose}</Text>}
            {open.persona_name && <Text style={{ fontSize: 13, color: colors.textSecondary }}>The caller will be {open.persona_name}. You answer the phone like it is a real customer.</Text>}
            {me.progress[open.id]?.attempts ? <Text style={{ fontSize: 13, color: colors.textSecondary }}>Best so far {me.progress[open.id].best_pct}% over {me.progress[open.id].attempts} {me.progress[open.id].attempts === 1 ? 'try' : 'tries'}. Need {course.pass_pct}%.</Text> : <Text style={{ fontSize: 13, color: colors.textSecondary }}>Not tried yet. Need {course.pass_pct}% to pass.</Text>}
            <TouchableOpacity onPress={() => { setOpen(null); router.push(`/scripts/${open.id}` as any); }} {...tid('my-challenge-read')}><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Read the full script first</Text></TouchableOpacity>
          </>
        )}
      </Sheet>
    </SafeAreaView>
  );
}
