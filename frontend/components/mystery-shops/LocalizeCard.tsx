import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { Bar, GOLD, GREEN, AMBER, PURPLE, tid } from './shared';

export type ReviewSummary = { language: string; language_label: string; total: number; pending: number; approved: number; source_total: number; by_department: Record<string, { total: number; pending: number }>; job: { status?: string; made?: number; total?: number; error?: string | null }; pending_items: { id: string; title: string; department: string; persona: string }[] };

// The Dutch (or any non-English) content pack for one industry: have Jessi adapt the English library, watch progress, approve everything at once.
export const LocalizeCard = ({ language, industry, industryLabel, review, colors, onChanged }: { language: string; industry: string; industryLabel: string; review: ReviewSummary | null; colors: any; onChanged: () => void }) => {
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);
  const running = review?.job?.status === 'running';
  const missing = Math.max(0, (review?.source_total || 0) - (review?.total || 0));

  // poll while Jessi writes so the counts move without a refresh
  useEffect(() => { if (!running) return; const t = setInterval(onChanged, 5000); return () => clearInterval(t); }, [running, onChanged]);

  const start = async () => {
    setBusy(true);
    try { const r = await api.post('/shop-clients/challenges/localize', { language, industry }); showToast(r.data.started ? `Jessi is writing the ${review?.language_label || language} versions, a few minutes` : 'Already running', 'success'); onChanged(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not start', 'error'); }
    finally { setBusy(false); }
  };
  const approveAll = () => showConfirm(`Approve all ${review?.pending} pending?`, 'Only do this after a native speaker has read them. Approved challenges go live for every client in this language.', async () => {
    try { const r = await api.post('/shop-clients/challenges/review/approve-all', { language }); showToast(`${r.data.approved} approved`, 'success'); onChanged(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not approve', 'error'); }
  }, undefined, 'Approve all');

  if (!review) return <ActivityIndicator color={GOLD} />;
  const tone = review.pending ? AMBER : review.total ? GREEN : PURPLE;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: tone + '66', padding: 14, gap: 10 }} {...tid('localize-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: tone + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={review.pending ? 'eye-outline' : review.total ? 'checkmark-done' : 'language'} size={20} color={tone} /></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} {...tid('localize-title')}>{review.language_label} {industryLabel.toLowerCase()} pack</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('localize-status')}>
            {running ? `Jessi is writing… ${review.job.made || 0} of ${review.job.total || 0} done` : review.total === 0 ? `Nothing yet. ${review.source_total} English challenges can be adapted.` : `${review.approved} approved · ${review.pending} waiting for a native reader${missing ? ` · ${missing} English not adapted yet` : ''}`}
          </Text>
        </View>
      </View>
      {running && <Bar pct={review.job.total ? (100 * (review.job.made || 0)) / review.job.total : 5} color={PURPLE} colors={colors} />}
      {review.job?.status === 'error' && <Text style={{ fontSize: 12, color: AMBER }} {...tid('localize-error')}>Last run stopped: {review.job.error}. Tap again to finish the rest.</Text>}
      <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Jessi adapts every English challenge (persona, curveballs, graded points) the way a local trainer would write it. Each one lands as NEEDS REVIEW; your native-speaking teammate opens it, fixes anything that sounds off, and approves. Clients in this language only get approved ones; until then their caller improvises from the English scripts.</Text>
      <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
        {(missing > 0 || review.total === 0) && (
          <TouchableOpacity onPress={start} disabled={busy || running} style={{ flex: 1, minWidth: 180, height: 40, borderRadius: 12, backgroundColor: PURPLE, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: busy || running ? 0.6 : 1 }} {...tid('localize-start')}>
            {busy || running ? <ActivityIndicator color="#fff" size="small" /> : <Ionicons name="color-wand-outline" size={16} color="#fff" />}<Text style={{ fontSize: 13, fontWeight: '800', color: '#fff' }}>{review.total ? `Write the ${missing} missing` : `Have Jessi write the ${review.language_label.split(' ')[0]} versions`}</Text>
          </TouchableOpacity>
        )}
        {review.pending > 0 && (
          <TouchableOpacity onPress={approveAll} style={{ flex: 1, minWidth: 150, height: 40, borderRadius: 12, borderWidth: 1.5, borderColor: GREEN, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('localize-approve-all')}>
            <Ionicons name="checkmark-done" size={16} color={GREEN} /><Text style={{ fontSize: 13, fontWeight: '800', color: GREEN }}>Approve all {review.pending}</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};
