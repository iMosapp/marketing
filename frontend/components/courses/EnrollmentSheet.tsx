import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { openUrl } from '../mystery-shops/ReportView';
import { Sheet, Label, GoldButton, fmtWhen, scoreColor, GOLD, GREEN, RED, PURPLE, tid } from '../mystery-shops/shared';
import { CourseProgress, ChallengeStatusRow, type Enrollment, type CourseChallenge } from './shared';

type Attempt = { session_id: string; script_id: string; script_title: string; score_pct: number | null; status: string; mode?: string; kind?: string; fail_reason?: string | null; evaluation_id?: string | null; at?: string | null };

// One person's journey through a course: per-challenge status, every attempt, certificate, and (for shop people) call now.
export const EnrollmentSheet = ({ id, onClose, colors, canManage, onChanged }: { id: string | null; onClose: () => void; colors: any; canManage: boolean; onChanged: () => void }) => {
  const router = useRouter();
  const { showToast } = useToast();
  const [d, setD] = useState<{ enrollment: Enrollment; challenges: CourseChallenge[]; attempts: Attempt[]; course: any } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => { if (id) api.get(`/courses/enrollments/${id}`).then(r => setD(r.data)).catch(() => setD(null)); };
  useEffect(() => { setD(null); load(); }, [id]);

  const remove = () => d && showConfirm('Remove from the course?', `${d.enrollment.name} loses their progress here. Scheduled course calls are cancelled.`, async () => {
    try { await api.delete(`/courses/enrollments/${d.enrollment.id}`); onChanged(); onClose(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, 'Remove');
  const callNow = async () => {
    if (!d) return;
    setBusy(true);
    try { await api.post(`/courses/enrollments/${d.enrollment.id}/shop-now`); showToast(`Calling ${d.enrollment.name.split(' ')[0]} now`, 'success'); load(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not call', 'error'); }
    finally { setBusy(false); }
  };
  const e = d?.enrollment;
  return (
    <Sheet visible={!!id} onClose={onClose} title={e ? e.name : 'Enrollment'} colors={colors} testID="enrollment-sheet"
      footer={e && canManage ? (
        <View style={{ flexDirection: 'row', gap: 10 }}>
          {e.kind === 'target' && e.status !== 'certified' && <View style={{ flex: 1 }}><GoldButton label="Call them now" onPress={callNow} busy={busy} testID="enrollment-call-now" icon="call" /></View>}
          <View style={{ flex: 1 }}><GoldButton label="Remove" onPress={remove} outline color={RED} testID="enrollment-remove" icon="trash-outline" /></View>
        </View>
      ) : undefined}>
      {!d || !e ? <ActivityIndicator color={GOLD} /> : (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={{ paddingHorizontal: 10, height: 26, borderRadius: 13, backgroundColor: (e.kind === 'target' ? PURPLE : GOLD) + '22', justifyContent: 'center' }}><Text style={{ fontSize: 11.5, fontWeight: '800', color: e.kind === 'target' ? PURPLE : GOLD }}>{e.kind === 'target' ? 'MYSTERY-SHOP PERSON' : 'REP'}</Text></View>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Enrolled {fmtWhen(e.assigned_at)}{e.assigned_by_name ? ` by ${e.assigned_by_name}` : ''}</Text>
          </View>
          <CourseProgress e={e} colors={colors} />
          {e.status === 'certified' && (
            <View style={{ backgroundColor: GREEN + '14', borderRadius: 14, padding: 12, borderWidth: 1, borderColor: GREEN + '66', gap: 8 }} {...tid('enrollment-certified')}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Ionicons name="ribbon" size={18} color={GREEN} /><Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }}>{d.course?.badge_label || 'Certified'} · {fmtWhen(e.certified_at)}</Text></View>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity onPress={async () => { await Clipboard.setStringAsync(e.certificate_url || ''); showToast('Certificate link copied', 'success'); }} style={{ flex: 1, height: 36, borderRadius: 12, backgroundColor: GREEN, alignItems: 'center', justifyContent: 'center' }} {...tid('enrollment-cert-copy')}><Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>Copy certificate link</Text></TouchableOpacity>
                <TouchableOpacity onPress={() => openUrl(e.certificate_url || '')} style={{ width: 36, height: 36, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('enrollment-cert-open')}><Ionicons name="open-outline" size={16} color={colors.text} /></TouchableOpacity>
              </View>
            </View>
          )}
          <View style={{ gap: 8 }}>
            <Label t="CHALLENGES" colors={colors} />
            {d.challenges.map((c, i) => <ChallengeStatusRow key={c.id} c={c} p={e.progress[c.id]} passPct={d.course?.pass_pct || 80} colors={colors} index={i} />)}
          </View>
          {d.attempts.length > 0 && (
            <View style={{ gap: 6 }}>
              <Label t={`ATTEMPTS · ${d.attempts.length}`} colors={colors} />
              {d.attempts.map(a => (
                <TouchableOpacity key={a.session_id} disabled={!a.evaluation_id} onPress={() => router.push((a.kind === 'mystery_shop' ? `/admin/mystery-shops/${e.client_id}?tab=calls` : `/scripts/result?session=${a.session_id}`) as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} {...tid(`attempt-${a.session_id}`)}>
                  <Text style={{ width: 46, fontSize: 15, fontWeight: '800', color: a.score_pct != null ? scoreColor(a.score_pct) : colors.textSecondary }}>{a.score_pct != null ? `${a.score_pct}%` : '–'}</Text>
                  <View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }} numberOfLines={1}>{a.script_title}</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>{fmtWhen(a.at)} · {a.status}{a.mode ? ` · ${a.mode}` : ''}{a.fail_reason && a.status !== 'completed' ? ` · ${a.fail_reason}` : ''}</Text></View>
                  {!!a.evaluation_id && <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />}
                </TouchableOpacity>
              ))}
            </View>
          )}
        </>
      )}
    </Sheet>
  );
};
