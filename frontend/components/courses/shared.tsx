import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Bar, deptLabel, scoreColor, industryOfDept, GOLD, GREEN, PURPLE, tid } from '../mystery-shops/shared';

export type Course = { id: string; title: string; description: string; department: string; challenge_ids: string[]; pass_pct: number; badge_label: string; active: boolean; enrolled?: number; certified?: number; challenge_count?: number; created_by_name?: string };
export type CourseChallenge = { id: string; title: string; department: string; purpose: string; runtime: string; persona_name?: string };
export type Progress = Record<string, { best_pct?: number | null; attempts?: number; passed?: boolean; last_pct?: number | null; last_session_id?: string; last_at?: string; passed_at?: string | null }>;
export type Enrollment = { id: string; course_id: string; kind: 'user' | 'target'; user_id?: string; target_id?: string; client_id?: string; name: string; status: string; assigned_at: string; assigned_by_name?: string; certified_at?: string | null; certificate_token?: string | null; certificate_url?: string | null; note?: string; progress: Progress; passed: number; total: number; next_challenge_id?: string | null; last_activity_at?: string | null; course?: Course };
const DEPT_PALETTE = [GOLD, '#0A84FF', '#FF9F0A', '#30B0C7', '#34C759'];
// Colour by the department's position inside its own industry (first department gold, second blue...), Mixed is purple.
export const deptColor = (d?: string) => { if (d === 'mixed') return PURPLE; const i = industryOfDept(d).departments.findIndex(x => x.key === d); return DEPT_PALETTE[i < 0 ? 0 : i % DEPT_PALETTE.length]; };

// "3 of 20 passed" bar with the certified ribbon when done.
export const CourseProgress = ({ e, colors, compact }: { e: Enrollment; colors: any; compact?: boolean }) => (
  <View style={{ gap: 4 }} {...tid(`course-progress-${e.id}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <Bar pct={e.total ? (100 * e.passed) / e.total : 0} color={e.status === 'certified' ? GREEN : GOLD} colors={colors} />
      <Text style={{ fontSize: compact ? 12 : 13, fontWeight: '800', color: colors.text }}>{e.passed} of {e.total}</Text>
      {e.status === 'certified' && <Ionicons name="ribbon" size={compact ? 14 : 16} color={GREEN} />}
    </View>
  </View>
);

// One row per challenge in a course: status dot, best score, attempts.
export const ChallengeStatusRow = ({ c, p, passPct, colors, index, onPress, right, showStatus = true }: { c: CourseChallenge; p?: Progress[string]; passPct: number; colors: any; index: number; onPress?: () => void; right?: React.ReactNode; showStatus?: boolean }) => {
  const passed = !!p?.passed;
  const tried = (p?.attempts || 0) > 0;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: passed ? GREEN + '66' : colors.border, padding: 12 }} {...tid(`course-challenge-${c.id}`)}>
      <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: passed ? GREEN : tried ? scoreColor(p?.best_pct) + '33' : colors.bg, alignItems: 'center', justifyContent: 'center', borderWidth: passed ? 0 : 1, borderColor: colors.border }}>
        {passed ? <Ionicons name="checkmark" size={16} color="#fff" /> : <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary }}>{index + 1}</Text>}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }} numberOfLines={1}>{c.title}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
          <Text style={{ color: deptColor(c.department), fontWeight: '700' }}>{deptLabel(c.department)}</Text>
          {!showStatus ? `${c.runtime ? ` · ${c.runtime}` : ''}${c.persona_name ? ` · ${industryOfDept(c.department).customer} ${c.persona_name.split(' ')[0]}` : ''}` : tried ? ` · best ${p?.best_pct ?? '–'}% of ${passPct}% · ${p?.attempts} ${p?.attempts === 1 ? 'try' : 'tries'}` : ` · not tried yet · need ${passPct}%`}
        </Text>
      </View>
      {right}
      {onPress && <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />}
    </View>
  );
};
