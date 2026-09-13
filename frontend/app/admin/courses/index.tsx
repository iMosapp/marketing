import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { CourseSheet } from '../../../components/courses/CourseSheet';
import { deptColor, type Course } from '../../../components/courses/shared';
import { deptLabel, GOLD, GREEN, tid } from '../../../components/mystery-shops/shared';

// Courses & certification: iMOS admins build them, managers enroll their reps.
export default function CoursesAdmin() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [sheet, setSheet] = useState(false);
  const load = useCallback(async () => { try { const r = await api.get('/courses'); setCourses(r.data.courses); setCanManage(!!r.data.can_manage); } catch { setCourses([]); } }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Courses & Certification" subtitle={courses ? `${courses.length} course${courses.length === 1 ? '' : 's'}` : undefined} testID="courses-header" right={canManage ? <HeaderIconButton icon="add-circle" onPress={() => setSheet(true)} testID="courses-add" /> : undefined} />
      {courses === null ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{canManage ? 'Bundle challenges from the library into a course with a pass mark. Enroll reps (they practice with Jessi) or mystery-shop people (we call them). Pass every challenge, get certified.' : 'Enroll your reps in a course. They practice each challenge by phone with Jessi and get certified when every one is passed at the pass mark.'}</Text>
          {courses.length === 0 && (
            <TouchableOpacity disabled={!canManage} onPress={() => setSheet(true)} style={{ alignItems: 'center', padding: 30, gap: 10, backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border }} {...tid('courses-empty')}>
              <Ionicons name="school" size={36} color={GOLD} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{canManage ? 'Build your first course' : 'No courses yet'}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>{canManage ? 'Name it, set the pass mark, then add challenges.' : 'iMOS is putting courses together.'}</Text>
            </TouchableOpacity>
          )}
          {courses.map(c => (
            <TouchableOpacity key={c.id} onPress={() => router.push(`/admin/courses/${c.id}` as any)} activeOpacity={0.85} style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 8 }} {...tid(`course-${c.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: deptColor(c.department) + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="school" size={20} color={deptColor(c.department)} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{c.title}</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{c.department === 'mixed' ? 'Mixed' : deptLabel(c.department)} · {c.challenge_count} challenge{c.challenge_count === 1 ? '' : 's'} · pass at {c.pass_pct}%</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
              </View>
              <View style={{ flexDirection: 'row', gap: 14 }}>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }}><Text style={{ fontWeight: '800', color: colors.text }}>{c.enrolled}</Text> enrolled</Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }}><Text style={{ fontWeight: '800', color: GREEN }}>{c.certified}</Text> certified</Text>
              </View>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
      <CourseSheet visible={sheet} onClose={() => setSheet(false)} colors={colors} onSaved={(c) => router.push(`/admin/courses/${c.id}` as any)} />
    </SafeAreaView>
  );
}
