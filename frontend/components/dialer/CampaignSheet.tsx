import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, GOLD, GREEN, AMBER, RED, tid, type Campaign } from './shared';

type Person = { id: string; name: string; role: string; has_number: boolean };
type Draft = Partial<Campaign> & { name: string };

const DEFAULT: Draft = { name: '', audience: 'b2b', lines: 2, connect_mode: 'instant', voicemail: 'skip', recording: 'off', hours: { start: '09:00', end: '20:00' }, max_attempts: 3, retry_hours: 24, max_per_day: 2, allow_registry_b2b: false, script: '', rep_ids: [], caller_id: '', seller_name: '' };

const Row = ({ label, hint, children, colors, testID }: { label: string; hint?: string; children: React.ReactNode; colors: any; testID?: string }) => (
  <View style={{ gap: 6 }} {...(testID ? tid(testID) : {})}>
    <Label t={label} colors={colors} />
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{children}</View>
    {!!hint && <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }}>{hint}</Text>}
  </View>
);

// Create or edit a campaign: the compliance-relevant knobs live here, each with a plain-words hint.
export const CampaignSheet = ({ visible, onClose, colors, campaign, storeId, onSaved }: { visible: boolean; onClose: () => void; colors: any; campaign?: Campaign | null; storeId?: string | null; onSaved: (c: Campaign) => void }) => {
  const { showToast } = useToast();
  const [d, setD] = useState<Draft>(DEFAULT);
  const [people, setPeople] = useState<Person[]>([]);
  const [pipelines, setPipelines] = useState<{ id: string; name: string; stages: { id: string; name: string }[] }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const set = (patch: Partial<Draft>) => setD(x => ({ ...x, ...patch }));
  const setGhl = (patch: Partial<Campaign['ghl']>) => set({ ghl: { tag: '', push: true, pipeline_id: '', stage_id: '', ...(d.ghl || {}), ...patch } });

  useEffect(() => {
    if (!visible) return;
    setD(campaign ? { ...DEFAULT, ...campaign, hours: { ...(campaign.hours || DEFAULT.hours!) } } : DEFAULT);
    setAdvanced(false);
    api.get('/inboxes/members/options', { params: storeId ? { store_id: storeId } : {} }).then(r => setPeople((r.data.users || []).filter((u: any) => u.on_team !== false))).catch(() => setPeople([]));
    api.get('/ghl/pipelines').then(r => setPipelines(r.data.pipelines || [])).catch(() => setPipelines(null));
  }, [visible, campaign?.id]);

  const save = async () => {
    if (!d.name.trim()) { showToast('Give the campaign a name', 'error'); return; }
    setBusy(true);
    try {
      const body: any = { ...d, ghl: d.ghl || undefined };
      delete body.counts; delete body.stats; delete body.queue; delete body.reps; delete body.id; delete body.created_by; delete body.created_at; delete body.status; delete body.store_id;
      const r = campaign ? await api.patch(`/dialer/campaigns/${campaign.id}`, body) : await api.post('/dialer/campaigns', { ...body, store_id: storeId || undefined });
      onSaved(r.data); showToast(campaign ? 'Campaign updated' : 'Campaign created', 'success'); onClose();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };
  const toggleRep = (id: string) => set({ rep_ids: (d.rep_ids || []).includes(id) ? (d.rep_ids || []).filter(x => x !== id) : [...(d.rep_ids || []), id] });
  const b2c = d.audience === 'b2c';

  return (
    <Sheet visible={visible} onClose={onClose} title={campaign ? 'Campaign settings' : 'New dialer campaign'} colors={colors} testID="campaign-sheet"
      footer={<GoldButton label={campaign ? 'Save settings' : 'Create campaign'} onPress={save} busy={busy} testID="campaign-save" icon="checkmark" />}>
      <Field label="CAMPAIGN NAME" value={d.name} onChange={(v: string) => set({ name: v })} colors={colors} placeholder="Utah dealers, June list" testID="campaign-name" />
      <Row label="WHO IS ON THE LIST" colors={colors} hint={b2c ? 'Consumers: National Do Not Call Registry hits are always skipped, hours and caps follow every state rule. Load the registry under Do Not Call.' : 'Businesses (owners, GMs, managers at work numbers). Most TSR do-not-call rules do not apply to business calls; legal hours and your Do Not Call list still do.'}>
        <Chip label="Businesses (B2B)" active={!b2c} onPress={() => set({ audience: 'b2b' })} colors={colors} testID="campaign-audience-b2b" />
        <Chip label="Consumers (B2C)" active={b2c} onPress={() => set({ audience: 'b2c' })} colors={colors} testID="campaign-audience-b2c" />
      </Row>
      <Row label="LINES AT ONCE" colors={colors} hint="How many leads ring per press. The first live answer is on your phone; the rest are cancelled. Two people answering at once = one abandoned call, and the campaign drops to 1 line when abandons near the legal 3%.">
        {[1, 2, 3].map(n => <Chip key={n} label={n === 1 ? '1 line (safest)' : `${n} lines`} active={d.lines === n} onPress={() => set({ lines: n })} colors={colors} testID={`campaign-lines-${n}`} />)}
      </Row>
      <Row label="WHEN SOMEONE ANSWERS" colors={colors} hint={d.connect_mode === 'press1' ? 'Your phone says the name, you press 1 to talk. The lead hears a few seconds of silence first and is treated as abandoned if you do not press in 5 seconds.' : 'They are on your phone instantly, no dead air (recommended). You launched the calls, so every dial still starts with a human.'}>
        <Chip label="Connect instantly" active={d.connect_mode !== 'press1'} onPress={() => set({ connect_mode: 'instant' })} colors={colors} testID="campaign-mode-instant" />
        <Chip label="Press 1 to accept" active={d.connect_mode === 'press1'} onPress={() => set({ connect_mode: 'press1' })} colors={colors} testID="campaign-mode-press1" />
      </Row>
      <Row label="VOICEMAIL" colors={colors} hint="We detect answering machines. Skip = hang up and retry later (never leaves a recorded message; that needs prior consent). Let me decide = you hear the greeting and can leave a live message.">
        <Chip label="Skip voicemails" active={d.voicemail !== 'rep'} onPress={() => set({ voicemail: 'skip' })} colors={colors} testID="campaign-vm-skip" />
        <Chip label="Let me decide" active={d.voicemail === 'rep'} onPress={() => set({ voicemail: 'rep' })} colors={colors} testID="campaign-vm-rep" />
      </Row>
      <Row label="CALLING HOURS (LEAD'S LOCAL TIME)" colors={colors} hint="Always inside the law for the lead's state (8am-9pm federal, 8pm in FL/OK/WA/MA and more, no Sundays in some states). You can only make it narrower.">
        <View style={{ flex: 1 }}><Field value={d.hours?.start} onChange={(v: string) => set({ hours: { ...(d.hours || DEFAULT.hours!), start: v } })} colors={colors} placeholder="09:00" testID="campaign-hours-start" /></View>
        <Text style={{ alignSelf: 'center', color: colors.textSecondary }}>to</Text>
        <View style={{ flex: 1 }}><Field value={d.hours?.end} onChange={(v: string) => set({ hours: { ...(d.hours || DEFAULT.hours!), end: v } })} colors={colors} placeholder="20:00" testID="campaign-hours-end" /></View>
      </Row>
      <TouchableOpacity onPress={() => setAdvanced(a => !a)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('campaign-advanced-toggle')}>
        <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>{advanced ? 'Fewer settings' : 'Attempts, recording, caller ID, script'}</Text>
        <Ionicons name={advanced ? 'chevron-up' : 'chevron-down'} size={14} color={GOLD} />
      </TouchableOpacity>
      {advanced && (
        <>
          <Row label="TRIES PER LEAD" colors={colors}>{[1, 2, 3, 4, 5].map(n => <Chip key={n} label={`${n}`} small active={d.max_attempts === n} onPress={() => set({ max_attempts: n })} colors={colors} testID={`campaign-attempts-${n}`} />)}</Row>
          <Row label="WAIT BETWEEN TRIES" colors={colors}>{[4, 24, 48, 72].map(n => <Chip key={n} label={n < 24 ? `${n} h` : `${n / 24} day${n > 24 ? 's' : ''}`} small active={d.retry_hours === n} onPress={() => set({ retry_hours: n })} colors={colors} testID={`campaign-retry-${n}`} />)}</Row>
          <Row label="MAX CALLS PER LEAD PER 24H" colors={colors} hint="Florida, Oklahoma and Maryland cap this at 3; the platform never goes above 3 anywhere.">{[1, 2, 3].map(n => <Chip key={n} label={`${n}`} small active={d.max_per_day === n} onPress={() => set({ max_per_day: n })} colors={colors} testID={`campaign-perday-${n}`} />)}</Row>
          <Row label="RECORD CALLS" colors={colors} hint="On = records except into all-party-consent states (CA, FL, WA, PA, IL, MA, MD, MI, MT, NV, NH, OR, CT, DE), where the call is simply not recorded.">
            <Chip label="Off" active={d.recording !== 'on'} onPress={() => set({ recording: 'off' })} colors={colors} testID="campaign-rec-off" />
            <Chip label="On where legal" active={d.recording === 'on'} onPress={() => set({ recording: 'on' })} colors={colors} testID="campaign-rec-on" />
          </Row>
          {!b2c && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: `${AMBER}12`, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: `${AMBER}40` }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Call National Registry numbers on this B2B list</Text>
                <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16, marginTop: 2 }}>Business-to-business calls are exempt from the federal registry, but some listed numbers are personal cells. Off = skip them anyway (safest).</Text>
              </View>
              <Switch value={!!d.allow_registry_b2b} onValueChange={v => set({ allow_registry_b2b: v })} trackColor={{ true: AMBER, false: colors.border }} thumbColor="#fff" {...tid('campaign-registry-b2b')} />
            </View>
          )}
          <Field label="BUSINESS NAME SPOKEN ON THE ABANDON MESSAGE" value={d.seller_name} onChange={(v: string) => set({ seller_name: v })} colors={colors} placeholder="Your store name" testID="campaign-seller" />
          <Field label="CALLER ID (OPTIONAL, FALLS BACK TO THE REP'S WORK NUMBER)" value={d.caller_id} onChange={(v: string) => set({ caller_id: v })} colors={colors} placeholder="+1 435 220 3414" keyboardType="phone-pad" testID="campaign-caller-id" />
          <Field label="SCRIPT / TALKING POINTS SHOWN TO THE REP" value={d.script} onChange={(v: string) => set({ script: v })} colors={colors} multiline placeholder="Hi {first name}, this is ... from ..." testID="campaign-script" />
          {pipelines !== null && (
            <View style={{ gap: 8 }} {...tid('campaign-ghl')}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Push outcomes to GoHighLevel</Text>
                  <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16, marginTop: 2 }}>Every marked call adds a note + tags on the GHL contact (created if missing).</Text>
                </View>
                <Switch value={d.ghl?.push !== false} onValueChange={v => setGhl({ push: v })} trackColor={{ true: GREEN, false: colors.border }} thumbColor="#fff" {...tid('campaign-ghl-push')} />
              </View>
              {d.ghl?.push !== false && pipelines.length > 0 && (
                <Row label="OPEN AN OPPORTUNITY FOR INTERESTED / CALL BACK" colors={colors}>
                  <Chip label="No pipeline" small active={!d.ghl?.pipeline_id} onPress={() => setGhl({ pipeline_id: '', stage_id: '' })} colors={colors} testID="campaign-ghl-pipeline-none" />
                  {pipelines.map(p => <Chip key={p.id} label={p.name} small active={d.ghl?.pipeline_id === p.id} onPress={() => setGhl({ pipeline_id: p.id, stage_id: p.stages[0]?.id || '' })} colors={colors} testID={`campaign-ghl-pipeline-${p.id}`} />)}
                </Row>
              )}
              {d.ghl?.push !== false && !!d.ghl?.pipeline_id && (
                <Row label="STAGE" colors={colors}>
                  {(pipelines.find(p => p.id === d.ghl?.pipeline_id)?.stages || []).map(s => <Chip key={s.id} label={s.name} small active={d.ghl?.stage_id === s.id} onPress={() => setGhl({ stage_id: s.id })} colors={colors} testID={`campaign-ghl-stage-${s.id}`} />)}
                </Row>
              )}
            </View>
          )}
        </>
      )}
      <Row label={`REPS WHO CAN DIAL THIS LIST · ${(d.rep_ids || []).length}`} colors={colors} hint="Managers can always dial their own campaigns.">
        {people.length === 0 && <Text style={{ fontSize: 12, color: colors.textSecondary }}>No teammates found for this store yet.</Text>}
        {people.map(p => {
          const on = (d.rep_ids || []).includes(p.id);
          return (
            <TouchableOpacity key={p.id} onPress={() => toggleRep(p.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, height: 32, borderRadius: 16, backgroundColor: on ? GREEN : colors.card, borderWidth: 1, borderColor: on ? GREEN : colors.border }} {...tid(`campaign-rep-${p.id}`)}>
              <Ionicons name={on ? 'checkmark-circle' : 'person-outline'} size={14} color={on ? '#111' : colors.textSecondary} />
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? '#111' : colors.text }}>{p.name}</Text>
              {!p.has_number && <Ionicons name="alert-circle" size={13} color={on ? '#111' : RED} />}
            </TouchableOpacity>
          );
        })}
      </Row>
    </Sheet>
  );
};
