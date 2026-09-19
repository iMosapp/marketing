/** Store page: pre-flight (likelihood the packet passes Twilio / TCR) + the team's review sign-off. */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const pill = { height: 40, borderRadius: 12, paddingHorizontal: 14, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 } as const;
const VERDICT_COLOR: Record<string, string> = { likely: '#34C759', needs_work: '#FF9500', reject: '#FF3B30' };
const LEVEL = { block: { color: '#FF3B30', icon: 'close-circle', word: 'Blocker' }, warn: { color: '#FF9500', icon: 'alert-circle', word: 'Warning' }, pass: { color: '#34C759', icon: 'checkmark-circle', word: 'OK' } } as const;

type Props = { storeId: string; preflight: any; review: any; missing: string[]; isSuper: boolean; locked: boolean; colors: any; s: any; onChanged: () => Promise<void> };

export const PreflightCard = ({ storeId, preflight, review, missing, isSuper, locked, colors, s, onChanged }: Props) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [showPass, setShowPass] = useState(false);
  const [notes, setNotes] = useState('');
  const pf = preflight || {};
  const reviewed = review?.status === 'reviewed';

  const run = async () => {
    setBusy('run');
    try { await api.post(`/admin/compliance/${storeId}/preflight`); await onChanged(); }
    catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Pre-flight failed.'); }
    finally { setBusy(null); }
  };
  const setReview = async (status: 'reviewed' | 'needs_client' | 'reopen') => {
    setBusy(status);
    try { await api.post(`/admin/compliance/${storeId}/review`, { status, notes }); setNotes(''); await onChanged(); }
    catch (e: any) { showSimpleAlert('Not done', e?.response?.data?.detail || 'Something went wrong.'); }
    finally { setBusy(null); }
  };

  const checks: any[] = pf.checks || [];
  const shown = checks.filter(c => c.level !== 'pass' || showPass);
  const color = VERDICT_COLOR[pf.verdict] || colors.textTertiary;

  return (
    <View style={s.card} {...tid('preflight-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>2 · Pre-flight and review</Text>
        {pf.at && (
          <View style={{ alignItems: 'flex-end' }} {...tid('preflight-score')}>
            <Text style={{ fontSize: 22, fontWeight: '800', color }}>{pf.score}<Text style={{ fontSize: 12, color: colors.textTertiary }}>/100</Text></Text>
          </View>
        )}
      </View>
      <Text style={s.hint}>Checks the packet the way the carrier reviewers do: EIN and legal name, website, privacy and terms pages and their wording, samples, opt-in flow, contact email domain.</Text>
      {pf.at ? (
        <View style={{ marginTop: 10, flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <View style={{ paddingHorizontal: 10, height: 26, borderRadius: 13, backgroundColor: `${color}20`, justifyContent: 'center' }} {...tid('preflight-verdict')}>
            <Text style={{ fontSize: 12.5, fontWeight: '800', color }}>{pf.verdict_label}{pf.stale ? ' · form changed since, run again' : ''}</Text>
          </View>
          <Text style={{ fontSize: 12, color: colors.textTertiary }} {...tid('preflight-counts')}>{pf.blockers} blocker{pf.blockers === 1 ? '' : 's'} · {pf.warnings} warning{pf.warnings === 1 ? '' : 's'} · {new Date(pf.at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</Text>
        </View>
      ) : missing.length > 0 ? (
        <Text style={{ marginTop: 8, fontSize: 12.5, color: '#FF9500' }} {...tid('preflight-missing')}>Form still incomplete: {missing.map(m => m.replace('.', ' → ').replace(/_/g, ' ')).join(', ')}. You can run pre-flight anyway to see everything at once.</Text>
      ) : null}

      {!locked && (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <TouchableOpacity onPress={run} disabled={!!busy} style={[pill, { backgroundColor: GOLD }]} {...tid('preflight-run-btn')}>
            {busy === 'run' ? <ActivityIndicator color="#000" /> : <Text style={s.btnText}>{pf.at ? 'Run pre-flight again' : 'Run pre-flight'}</Text>}
          </TouchableOpacity>
          {pf.at && !reviewed && (
            <TouchableOpacity onPress={() => setReview('reviewed')} disabled={!!busy || (!!pf.blockers && !isSuper) || !!pf.stale} style={[pill, { backgroundColor: colors.bg, borderWidth: 1, borderColor: '#34C759', opacity: (!!pf.blockers && !isSuper) || pf.stale ? 0.4 : 1 }]} {...tid('review-mark-btn')}>
              {busy === 'reviewed' ? <ActivityIndicator color={colors.text} /> : <Text style={[s.btnText, { color: '#34C759' }]}>Mark reviewed</Text>}
            </TouchableOpacity>
          )}
          {reviewed && (
            <TouchableOpacity onPress={() => setReview('reopen')} disabled={!!busy} style={[pill, { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }]} {...tid('review-reopen-btn')}>
              <Text style={[s.btnText, { color: colors.text }]}>Reopen review</Text>
            </TouchableOpacity>
          )}
          {pf.at && (
            <TouchableOpacity onPress={() => setReview('needs_client')} disabled={!!busy} style={[pill, { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }]} {...tid('review-needs-client-btn')}>
              {busy === 'needs_client' ? <ActivityIndicator color={colors.text} /> : <Text style={[s.btnText, { color: colors.text }]}>Send fixes to client</Text>}
            </TouchableOpacity>
          )}
        </View>
      )}
      {reviewed && (
        <Text style={{ marginTop: 8, fontSize: 12.5, color: '#34C759', fontWeight: '700' }} {...tid('review-status')}>Reviewed by {review.reviewed_by} · {new Date(review.reviewed_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}{review.notes ? ` · ${review.notes}` : ''}</Text>
      )}
      {pf.at && !locked && (
        <TextInput value={notes} onChangeText={setNotes} placeholder="Note for the client or the team (goes into the message / history)" placeholderTextColor={colors.textTertiary} style={[s.input, { marginTop: 10 }]} {...tid('review-notes')} />
      )}

      {pf.at && (
        <View style={{ marginTop: 12 }} {...tid('preflight-checks')}>
          {shown.map((c: any) => {
            const L = LEVEL[c.level as keyof typeof LEVEL];
            const open = openKey === c.key;
            return (
              <TouchableOpacity key={c.key} onPress={() => setOpenKey(open ? null : c.key)} activeOpacity={0.8} style={{ flexDirection: 'row', gap: 10, paddingVertical: 7, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`preflight-check-${c.key}`)}>
                <Ionicons name={L.icon as any} size={18} color={L.color} style={{ marginTop: 1 }} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{c.label} <Text style={{ fontSize: 12, color: L.color }}>· {L.word}</Text></Text>
                  {!!c.detail && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{c.detail}</Text>}
                  {open && !!c.fix && <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 18, marginTop: 4, backgroundColor: colors.bg, borderRadius: 8, padding: 8 }} {...tid(`preflight-fix-${c.key}`)}>{c.fix}</Text>}
                </View>
                {!!c.fix && <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textTertiary} />}
              </TouchableOpacity>
            );
          })}
          {checks.some(c => c.level === 'pass') && (
            <TouchableOpacity onPress={() => setShowPass(v => !v)} style={{ paddingTop: 8 }} {...tid('preflight-toggle-pass')}>
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: GOLD }}>{showPass ? 'Hide' : 'Show'} the {checks.filter(c => c.level === 'pass').length} checks that pass</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
    </View>
  );
};
