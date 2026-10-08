import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { showConfirm } from '../../services/alert';
import { BigButton, StepTitle, BusyBar } from './shared';
import { InspectionCapture } from './InspectionCapture';
import { InspectionMedia } from './InspectionMedia';
import { InspectionCoverage } from './InspectionCoverage';
import { FindingCard } from './FindingCard';
import { FindingEditor } from './FindingEditor';
import { ConditionReport } from './ConditionReport';
import { EvidenceViewer } from './EvidenceViewer';
import { VoiceNotes } from './VoiceNotes';
import { MediaViewer } from './MediaViewer';
import type { useAppraisalMedia, MediaSource } from '../../hooks/useAppraisalMedia';

type Props = { colors: any; appraisal: any; media: ReturnType<typeof useAppraisalMedia>; onSaved: (appraisal: any) => void; showToast: (m: string, t?: any, d?: number) => void };
const STAGE: Record<string, string> = { queued: 'Queued…', extracting: 'Pulling the sharpest frames out of the video…', inspecting: 'Jessi is inspecting the vehicle…', scoring: 'Scoring coverage and condition…' };
const GUIDE_HERE = "Start at the driver's front corner and slowly walk around the vehicle. Keep the whole car in frame, then get the wheels, windshield, seats and dashboard. Jessi tells you what is still missing.";
const GUIDE_SENT = 'Import the walkaround video and photos the customer texted or emailed. You can add your own shots later — they all land on the same inspection.';

// Step 4: media in -> Jessi -> coverage, findings you confirm/dismiss/edit/add -> condition report -> continue.
export const InspectionStep = ({ colors, appraisal, media, onSaved, showToast }: Props) => {
  const [insp, setInsp] = useState<any | null>(null);
  const [source, setSource] = useState<MediaSource>(appraisal.mode === 'customer_sent' ? 'customer_supplied' : 'uploaded_by_rep');
  const [editor, setEditor] = useState<{ finding?: any } | null>(null);
  const [evidence, setEvidence] = useState<any | null>(null);
  const [viewer, setViewer] = useState<number | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    try { const d = (await api.get(`/appraisals/${appraisal.id}/inspection`)).data; setInsp(d); return d; }
    catch (e) { showToast(errText(e, 'Could not load the inspection'), 'error'); return null; }
  }, [appraisal.id]);
  useEffect(() => { load(); }, [load]);
  const running = !!insp && ['queued', 'processing'].includes(insp.status);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      const d = await load();
      if (d && !['queued', 'processing'].includes(d.status)) { clearInterval(t); onSaved({ status: d.appraisal_status }); showToast(d.status === 'ready' ? 'Jessi finished the inspection.' : `Inspection failed: ${d.last_error || 'unknown error'}`, d.status === 'ready' ? 'success' : 'error', 4000); }
    }, 3000);
    return () => clearInterval(t);
  }, [running, load]);

  const analyze = async () => {
    setActing(true);
    try { await api.post(`/appraisals/${appraisal.id}/inspection/run`); showToast('Jessi is on it. You can keep adding media.', 'success', 3000); await load(); }
    catch (e) { showToast(errText(e, 'Could not start the inspection'), 'error'); }
    finally { setActing(false); }
  };
  const decide = async (f: any, decision: string) => {
    setActing(true);
    try { await api.post(`/appraisals/${appraisal.id}/inspection/findings/${f.id}/decision`, { decision }); await load(); }
    catch (e) { showToast(errText(e, 'Could not save that'), 'error'); }
    finally { setActing(false); }
  };
  const remove = (m: any) => showConfirm('Remove this file?', 'Its frames come off the inspection too. Findings keep any other evidence.', async () => {
    try { await api.delete(`/appraisals/${appraisal.id}/media/${m.id}`); await load(); } catch (e) { showToast(errText(e, 'Could not remove it'), 'error'); }
  });
  const next = async () => {
    try { const r = (await api.patch(`/appraisals/${appraisal.id}`, { step: 'market' })).data; onSaved(r.appraisal); }
    catch (e) { showToast(errText(e, 'Could not continue'), 'error'); }
  };

  const mediaList: any[] = insp?.media || appraisal.media || [];
  const inspectable = mediaList.filter((m: any) => m.role !== 'vin_photo');
  const unprocessed = inspectable.filter((m: any) => !(insp?.processed_media_ids || []).includes(m.id)).length;
  const report = insp?.report;
  const busy = !!media.busy || acting || !!running;

  return (
    <View style={{ gap: 12 }} {...tid('inspection-step')}>
      <StepTitle colors={colors} title="AI Vehicle Inspection" sub={appraisal.mode === 'customer_sent' ? GUIDE_SENT : GUIDE_HERE} />
      <InspectionCapture colors={colors} mode={appraisal.mode} media={media} source={source} onSource={setSource} onDone={load} disabled={busy} />
      <BusyBar text={media.busy} colors={colors} />
      <InspectionMedia colors={colors} media={mediaList} processed={insp?.processed_media_ids || []} onDelete={remove} busy={busy} onOpen={(m) => setViewer(inspectable.findIndex((x: any) => x.id === m.id))} />
      <MediaViewer colors={colors} media={inspectable} index={viewer} onClose={() => setViewer(null)} />
      <VoiceNotes colors={colors} appraisal={appraisal} onSaved={onSaved} showToast={showToast} />
      {running ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: GOLD }} {...tid('inspect-running')}>
          <ActivityIndicator color={GOLD} />
          <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{STAGE[insp.stage] || 'Working…'}</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Usually under a minute. Findings appear here.</Text></View>
        </View>
      ) : inspectable.length ? (
        <BigButton colors={colors} icon="sparkles" label={report ? (unprocessed ? `Analyze ${unprocessed} new file${unprocessed > 1 ? 's' : ''}` : 'Re-run inspection') : 'Analyze with Jessi'} sub={report && !unprocessed ? 'Same media, fresh look. Your decisions stay.' : `${inspectable.length} file${inspectable.length > 1 ? 's' : ''} ready`} onPress={analyze} primary={!report || unprocessed > 0} disabled={busy} testId="inspect-analyze" />
      ) : null}
      {insp?.status === 'failed' ? <Text style={{ fontSize: 13, color: '#FF3B30' }} {...tid('inspect-error')}>Last run failed: {insp.last_error}. Tap analyze to retry — nothing is duplicated.</Text> : null}
      {report ? (
        <>
          <InspectionCoverage colors={colors} coverage={insp.coverage} />
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>FINDINGS · {insp.findings.length}</Text>
            <TouchableOpacity onPress={() => setEditor({})} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 6, paddingHorizontal: 10, borderRadius: 10, borderWidth: 1, borderColor: GOLD }} {...tid('inspect-add-issue')}>
              <Ionicons name="add" size={15} color={GOLD} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Add issue</Text>
            </TouchableOpacity>
          </View>
          {insp.findings.length ? insp.findings.map((f: any) => <FindingCard key={f.id} colors={colors} finding={f} onDecide={d => decide(f, d)} onEdit={() => setEditor({ finding: f })} onEvidence={setEvidence} busy={busy} />)
            : <Text style={{ fontSize: 13, color: colors.textSecondary }}>Jessi did not see any issues. Add anything you noticed in person.</Text>}
          <ConditionReport colors={colors} appraisalId={appraisal.id} report={report} grades={insp.grades} onChanged={load} showToast={showToast} />
        </>
      ) : null}
      <BigButton colors={colors} icon="arrow-forward" label={report ? 'Continue' : 'Skip inspection for now'} sub={report && insp.coverage?.missing?.length ? `Missing: ${insp.coverage.missing.slice(0, 4).join(', ')}${insp.coverage.missing.length > 4 ? '…' : ''}` : report ? 'On to what the customer wants' : 'You can come back from the summary'} onPress={next} primary={!!report} disabled={busy} testId="inspect-continue" />
      {editor ? <FindingEditor colors={colors} appraisalId={appraisal.id} meta={{ categories: insp.categories, subtypes: insp.subtypes, severities: insp.severities }} frames={insp.frames} finding={editor.finding} onClose={() => setEditor(null)} onSaved={load} showToast={showToast} /> : null}
      <EvidenceViewer colors={colors} evidence={evidence} onClose={() => setEvidence(null)} />
    </View>
  );
};
