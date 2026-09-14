import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../../components/common/Toast';
import { CourseSheet } from '../../../components/courses/CourseSheet';
import { ChallengePickerSheet, AssignSheet } from '../../../components/courses/CourseSheets';
import { EnrollmentSheet } from '../../../components/courses/EnrollmentSheet';
import { CourseProgress, ChallengeStatusRow, deptColor, type Course, type CourseChallenge, type Enrollment } from '../../../components/courses/shared';
import { Label, GoldButton, deptLabel, loadIndustries, fmtWhen, GOLD, GREEN, RED, PURPLE, tid } from '../../../components/mystery-shops/shared';

export default function CourseAdminDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [course, setCourse] = useState<Course | null>(null);
  const [challenges, setChallenges] = useState<CourseChallenge[]>([]);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [canManage, setCanManage] = useState(false);
  const [canAssign, setCanAssign] = useState(false);
  const [edit, setEdit] = useState(false);
  const [picker, setPicker] = useState(false);
  const [assign, setAssign] = useState(false);
  const [openE, setOpenE] = useState<string | null>(null);

  const load = useCallback(async () => {
    loadIndustries();
    try { const r = await api.get(`/courses/${id}`); setCourse(r.data.course); setChallenges(r.data.challenges); setEnrollments(r.data.enrollments); setCanManage(!!r.data.can_manage); setCanAssign(!!r.data.can_assign); }
    catch { showToast('Course not found', 'error'); router.back(); }
  }, [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const saveIds = async (ids: string[]) => { const r = await api.put(`/courses/${id}`, { challenge_ids: ids }); setCourse(r.data); load(); };
  const move = (i: number, dir: -1 | 1) => { const ids = challenges.map(c => c.id); const j = i + dir; if (j < 0 || j >= ids.length) return; [ids[i], ids[j]] = [ids[j], ids[i]]; saveIds(ids); };
  const removeChallenge = (c: CourseChallenge) => showConfirm('Remove from the course?', `${c.title} will no longer count toward certification.`, () => saveIds(challenges.filter(x => x.id !== c.id).map(x => x.id)), undefined, 'Remove');
  const retire = () => showConfirm('Retire this course?', 'It disappears for everyone. Certificates already earned stay valid.', async () => { await api.delete(`/courses/${id}`); router.replace('/admin/courses' as any); }, undefined, 'Retire');

  if (!course) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}><ActivityIndicator style={{ marginTop: 80 }} color={GOLD} /></SafeAreaView>;
  const certified = enrollments.filter(e => e.status === 'certified');
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={course.title} subtitle={`${course.department === 'mixed' ? 'Mixed' : deptLabel(course.department)} · pass at ${course.pass_pct}%`} testID="course-header" right={canManage ? <HeaderIconButton icon="create-outline" onPress={() => setEdit(true)} testID="course-edit" /> : undefined} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 18 }}>
        {!!course.description && <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20 }} {...tid('course-description-text')}>{course.description}</Text>}
        <View style={{ flexDirection: 'row', gap: 10 }}>
          {[['Challenges', challenges.length, GOLD], ['Enrolled', enrollments.length, colors.text], ['Certified', certified.length, GREEN]].map(([l, v, c]) => (
            <View key={String(l)} style={{ flex: 1, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid(`course-stat-${String(l).toLowerCase()}`)}>
              <Text style={{ fontSize: 22, fontWeight: '800', color: c as string }}>{v}</Text><Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary }}>{String(l).toUpperCase()}</Text>
            </View>
          ))}
        </View>
        <View style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <View style={{ flex: 1 }}><Label t="CHALLENGES, IN ORDER" colors={colors} /></View>
            {canManage && <TouchableOpacity onPress={() => setPicker(true)} {...tid('course-add-challenges')}><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>+ Add from library</Text></TouchableOpacity>}
          </View>
          {challenges.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }}>No challenges yet. Add some from the library, then enroll people.</Text>}
          {challenges.map((c, i) => (
            <ChallengeStatusRow key={c.id} c={c} passPct={course.pass_pct} colors={colors} index={i} right={canManage ? (
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <TouchableOpacity onPress={() => move(i, -1)} disabled={i === 0} hitSlop={6} {...tid(`course-challenge-up-${c.id}`)}><Ionicons name="chevron-up" size={18} color={i === 0 ? colors.border : colors.textSecondary} /></TouchableOpacity>
                <TouchableOpacity onPress={() => move(i, 1)} disabled={i === challenges.length - 1} hitSlop={6} {...tid(`course-challenge-down-${c.id}`)}><Ionicons name="chevron-down" size={18} color={i === challenges.length - 1 ? colors.border : colors.textSecondary} /></TouchableOpacity>
                <TouchableOpacity onPress={() => removeChallenge(c)} hitSlop={6} {...tid(`course-challenge-remove-${c.id}`)}><Ionicons name="close-circle-outline" size={18} color={RED} /></TouchableOpacity>
              </View>
            ) : undefined} />
          ))}
        </View>
        <View style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <View style={{ flex: 1 }}><Label t={`PEOPLE · ${enrollments.length}`} colors={colors} /></View>
            {canAssign && challenges.length > 0 && <TouchableOpacity onPress={() => setAssign(true)} {...tid('course-enroll')}><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>+ Enroll people</Text></TouchableOpacity>}
          </View>
          {enrollments.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }}>Nobody enrolled yet.</Text>}
          {enrollments.map(e => (
            <TouchableOpacity key={e.id} onPress={() => setOpenE(e.id)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: e.status === 'certified' ? GREEN + '66' : colors.border, padding: 12, gap: 8 }} {...tid(`enrollment-${e.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Ionicons name={e.kind === 'target' ? 'storefront' : 'person'} size={16} color={e.kind === 'target' ? PURPLE : GOLD} />
                <Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }}>{e.name}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary }}>{e.status === 'certified' ? `Certified ${fmtWhen(e.certified_at)}` : e.last_activity_at ? `Last try ${fmtWhen(e.last_activity_at)}` : `Enrolled ${fmtWhen(e.assigned_at)}`}</Text>
              </View>
              <CourseProgress e={e} colors={colors} compact />
            </TouchableOpacity>
          ))}
        </View>
        {canManage && <GoldButton label="Retire this course" onPress={retire} outline color={RED} testID="course-retire" icon="archive-outline" />}
      </ScrollView>
      <CourseSheet visible={edit} onClose={() => setEdit(false)} colors={colors} course={course} onSaved={(c) => { setCourse(c); load(); }} />
      <ChallengePickerSheet visible={picker} onClose={() => setPicker(false)} colors={colors} already={challenges.map(c => c.id)} defaultDept={course.department} onAdd={(ids) => saveIds([...challenges.map(c => c.id), ...ids])} />
      <AssignSheet visible={assign} onClose={() => setAssign(false)} colors={colors} courseId={course.id} onDone={load} />
      <EnrollmentSheet id={openE} onClose={() => setOpenE(null)} colors={colors} canManage={canAssign} onChanged={load} />
    </SafeAreaView>
  );
}
