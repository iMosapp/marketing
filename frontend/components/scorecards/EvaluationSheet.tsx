import React, { useEffect, useState } from 'react';
import { View, Text, Modal, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../common/Toast';
import { CallRecordingPlayer } from '../CallRecordingPlayer';
import { ScoreRing } from './ScoreRing';
import { CriteriaChecklist } from './CriteriaChecklist';
import { GOLD, GREEN, RED, tid, fmtDur, fmtWhen, passedCount, type Evaluation, type Scorecard } from './shared';

type Props = {
  visible: boolean; onClose: () => void;
  evaluationId?: string | null; callSid?: string | null; hasRecording?: boolean;
  onChanged?: (ev: Evaluation) => void;
};

const REASONS: Record<string, string> = {
  no_transcript: 'This call has no transcript yet, so there is nothing to grade.',
  too_short: 'Calls under 30 seconds are not graded.',
  voicemail: 'Voicemails and no-answers are not graded.',
  no_scorecard: 'No scorecard applies to this rep yet. A manager can pick one below.',
};

// Full evaluation: score ring, summary, checklist (manager corrections), wins, coaching, recording, re-score.
export const EvaluationSheet = ({ visible, onClose, evaluationId, callSid, hasRecording, onChanged }: Props) => {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const router = useRouter();
  const [ev, setEv] = useState<Evaluation | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [cards, setCards] = useState<Scorecard[] | null>(null);
  const [showCards, setShowCards] = useState(false);

  useEffect(() => {
    if (!visible) return;
    setEv(null); setReason(null); setShowCards(false);
    const url = evaluationId ? `/scorecards/evaluations/${evaluationId}` : callSid ? `/scorecards/evaluations/call/${callSid}` : null;
    if (!url) return;
    setLoading(true);
    api.get(url).then(res => { setEv(res.data.evaluation); setReason(res.data.reason || null); setCanManage(!!res.data.can_manage); })
      .catch((e: any) => showToast(e?.response?.data?.detail || 'Could not load the scorecard', 'error'))
      .finally(() => setLoading(false));
  }, [visible, evaluationId, callSid]);

  const override = async (criterionId: string, passed: boolean | null) => {
    if (!ev) return;
    setBusy(criterionId);
    try {
      const res = await api.put(`/scorecards/evaluations/${ev.id}/override`, { criterion_id: criterionId, passed });
      setEv(res.data); onChanged?.(res.data);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(null); }
  };

  const openCards = async () => {
    if (!cards) { try { const res = await api.get('/scorecards'); setCards(res.data.scorecards || []); } catch { setCards([]); } }
    setShowCards(true);
  };
  const rescore = async (scorecardId: string | null) => {
    const sid = ev?.call_sid || callSid;
    if (!sid) return;
    setBusy('rescore'); setShowCards(false);
    try {
      const res = await api.post(`/scorecards/evaluations/rescore/${sid}`, { scorecard_id: scorecardId });
      setEv(res.data.evaluation); setReason(null); onChanged?.(res.data.evaluation); showToast('Call re-scored', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not re-score', 'error'); }
    finally { setBusy(null); }
  };

  const sid = ev?.call_sid || callSid;
  const counts = ev ? passedCount(ev) : null;
  const sentiment = ev?.customer_sentiment === 'positive' ? { c: GREEN, l: 'Customer upbeat' } : ev?.customer_sentiment === 'negative' ? { c: RED, l: 'Customer frustrated' } : { c: '#8E8E93', l: 'Customer neutral' };
  const H = ({ t }: { t: string }) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 8 }}>{t}</Text>;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <TouchableOpacity style={{ flex: 1 }} onPress={onClose} activeOpacity={1} />
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%' }} {...tid('evaluation-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 14, paddingBottom: 8, gap: 12 }}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid('eval-title')}>{ev ? ev.contact_name || 'Call' : 'Call scorecard'}</Text>
              {ev && <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{ev.direction === 'inbound' ? 'Inbound' : 'Outbound'} · {fmtDur(ev.duration_s)} · {fmtWhen(ev.call_at)} · {ev.scorecard_name}{ev.rep_name ? ` · ${ev.rep_name.split(' ')[0]}` : ''}</Text>}
            </View>
            <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('eval-close')}><Ionicons name="close" size={26} color={colors.text} /></TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40, gap: 16 }}>
            {loading && <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} />}
            {!loading && !ev && (
              <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 18, alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.border }} {...tid('eval-empty')}>
                <Ionicons name="clipboard-outline" size={34} color={GOLD} />
                <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Not scored</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 }}>{REASONS[reason || ''] || 'This call has not been scored.'}</Text>
                {canManage && sid && reason !== 'no_transcript' && reason !== 'too_short' && (
                  <TouchableOpacity onPress={openCards} disabled={busy === 'rescore'} style={{ marginTop: 6, height: 42, paddingHorizontal: 18, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('eval-score-now')}>
                    <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>{busy === 'rescore' ? 'Scoring…' : 'Score this call'}</Text>
                  </TouchableOpacity>
                )}
              </View>
            )}

            {ev && (
              <>
                <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 16 }}>
                  <ScoreRing pct={ev.score_pct} size={84} stroke={8} colors={colors} testID="eval-score-ring" />
                  <View style={{ flex: 1, gap: 6 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} {...tid('eval-passed-count')}>{counts!.passed} of {counts!.graded} criteria hit</Text>
                    {ev.critical_misses.length > 0 ? (
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}><Ionicons name="alert-circle" size={15} color={RED} /><Text style={{ fontSize: 13, fontWeight: '700', color: RED }} {...tid('eval-critical-count')}>{ev.critical_misses.length} critical miss{ev.critical_misses.length === 1 ? '' : 'es'}</Text></View>
                    ) : (
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}><Ionicons name="shield-checkmark" size={15} color={GREEN} /><Text style={{ fontSize: 13, fontWeight: '700', color: GREEN }}>All critical items covered</Text></View>
                    )}
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                      <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: sentiment.c + '22' }}><Text style={{ fontSize: 11, fontWeight: '700', color: sentiment.c }}>{sentiment.l}</Text></View>
                      <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: colors.surface }}><Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary }}>{ev.graded_by === 'manager' ? 'Manager corrected' : 'AI graded'}</Text></View>
                    </View>
                  </View>
                </View>

                {!!ev.summary && (
                  <View><H t="WHAT HAPPENED" /><Text style={{ fontSize: 14, color: colors.text, lineHeight: 21 }} {...tid('eval-summary')}>{ev.summary}</Text></View>
                )}

                <View>
                  <H t={`CHECKLIST${canManage ? ' · TAP A ROW TO CORRECT' : ' · TAP FOR EVIDENCE'}`} />
                  <CriteriaChecklist results={ev.results} colors={colors} canManage={canManage} onOverride={override} busyId={busy} />
                </View>

                {ev.wins.length > 0 && (
                  <View style={{ backgroundColor: GREEN + '12', borderRadius: 14, padding: 14, borderLeftWidth: 3, borderLeftColor: GREEN }}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: GREEN, letterSpacing: 1, marginBottom: 6 }}>WHAT WENT WELL</Text>
                    {ev.wins.map((w, i) => <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 19, marginBottom: 4 }}>• {w}</Text>)}
                  </View>
                )}
                {ev.coaching.length > 0 && (
                  <View style={{ backgroundColor: GOLD + '14', borderRadius: 14, padding: 14, borderLeftWidth: 3, borderLeftColor: GOLD }} {...tid('eval-coaching')}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1, marginBottom: 6 }}>COACH ON THIS</Text>
                    {ev.coaching.map((t, i) => <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 19, marginBottom: 4 }}>{i + 1}. {t}</Text>)}
                  </View>
                )}

                {hasRecording && sid && (
                  <View><H t="RECORDING" /><View style={{ backgroundColor: colors.surface, borderRadius: 12, padding: 10 }}>
                    <CallRecordingPlayer url={`${api.defaults.baseURL}/calls/recording/${sid}`} tint={GOLD} textColor={colors.text} subColor={colors.textSecondary} trackColor={colors.border} />
                  </View></View>
                )}

                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {ev.conversation_id && (
                    <TouchableOpacity onPress={() => { onClose(); router.push(`/thread/${ev.conversation_id}` as any); }} style={{ flex: 1, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('eval-open-thread')}>
                      <Ionicons name="chatbubble-outline" size={16} color={colors.text} /><Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Open thread</Text>
                    </TouchableOpacity>
                  )}
                  {canManage && (
                    <TouchableOpacity onPress={openCards} disabled={busy === 'rescore'} style={{ flex: 1, height: 44, borderRadius: 12, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('eval-rescore')}>
                      {busy === 'rescore' ? <ActivityIndicator color={GOLD} /> : <><Ionicons name="refresh" size={16} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>Re-score</Text></>}
                    </TouchableOpacity>
                  )}
                </View>
              </>
            )}

            {showCards && (
              <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: GOLD, gap: 8 }} {...tid('eval-card-picker')}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Grade with which scorecard?</Text>
                {ev && <TouchableOpacity onPress={() => rescore(ev.scorecard_id)} style={{ padding: 12, borderRadius: 10, backgroundColor: GOLD + '22' }} {...tid('eval-card-same')}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Same card: {ev.scorecard_name}</Text></TouchableOpacity>}
                {(cards || []).filter(c => c.id !== ev?.scorecard_id).map(c => (
                  <TouchableOpacity key={c.id} onPress={() => rescore(c.id)} style={{ padding: 12, borderRadius: 10, backgroundColor: colors.surface }} {...tid(`eval-card-${c.id}`)}>
                    <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{c.name}</Text><Text style={{ fontSize: 11, color: colors.textSecondary }}>{c.department || 'No department'} · {c.criteria.length} criteria</Text>
                  </TouchableOpacity>
                ))}
                {cards && cards.length === 0 && <Text style={{ fontSize: 12, color: colors.textSecondary }}>No scorecards yet. Create one under Hub, Manage, Scorecards.</Text>}
                <TouchableOpacity onPress={() => setShowCards(false)} style={{ alignItems: 'center', padding: 8 }} {...tid('eval-card-picker-cancel')}><Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary }}>Cancel</Text></TouchableOpacity>
              </View>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};
