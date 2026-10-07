import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../../inbox/ownership';
import { SectionCard, SwitchRow, NumField, ChipRow, TextField } from './fields';

type P = { colors: any; rules: any; set: (patch: any) => void; options: any };
const Row = ({ children }: { children: React.ReactNode }) => <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>{children}</View>;

export const TargetGrossSection = ({ colors, rules, set }: P) => {
  const tg = rules.target_gross;
  const up = (p: any) => set({ target_gross: { ...tg, ...p } });
  return (
    <SectionCard colors={colors} title="Target front-end gross" hint="Taken off a retail starting value. Fixed dollars or a percent of the starting value." enabled={tg.enabled} onToggle={v => up({ enabled: v })} testId="rules-target-gross">
      <ChipRow colors={colors} options={[{ key: 'fixed', label: 'Fixed amount' }, { key: 'percent', label: 'Percent of retail' }]} value={tg.method} onChange={m => up({ method: m })} testId="target-gross-method" />
      <Row>
        {tg.method === 'percent' ? <NumField colors={colors} label="Percent" value={tg.percent} onChange={v => up({ percent: v ?? 0 })} prefix="" suffix="%" testId="target-gross-percent" />
          : <NumField colors={colors} label="Amount" value={tg.amount} onChange={v => up({ amount: v ?? 0 })} testId="target-gross-amount" />}
      </Row>
      <SwitchRow colors={colors} label="Also take it off wholesale book values" hint="Off = MMR / Black Book wholesale numbers already sit below retail" value={tg.apply_to_wholesale} onChange={v => up({ apply_to_wholesale: v })} testId="target-gross-wholesale" />
    </SectionCard>
  );
};

export const ReconSection = ({ colors, rules, set, options }: P) => {
  const rc = rules.recon;
  const up = (p: any) => set({ recon: { ...rc, ...p } });
  const byc = rc.by_condition || {};
  return (
    <SectionCard colors={colors} title="Reconditioning by condition" hint="Deducted by the confirmed overall condition from the inspection. Leave Poor empty to force a manager's estimate." enabled={rc.enabled} onToggle={v => up({ enabled: v })} testId="rules-recon">
      <Row>
        {Object.entries(options.conditions || {}).map(([k, label]: any) => (
          <NumField key={k} colors={colors} label={label} value={byc[k]} onChange={v => up({ by_condition: { ...byc, [k]: v } })} allowEmpty emptyLabel="Manager" testId={`recon-${k}`} />
        ))}
      </Row>
      <Row>
        <NumField colors={colors} label="Not graded yet" value={rc.unknown_amount} onChange={v => up({ unknown_amount: v })} allowEmpty emptyLabel="No deduction" testId="recon-unknown" />
      </Row>
      <SwitchRow colors={colors} label="Poor condition needs a manager" value={rc.poor_requires_review} onChange={v => up({ poor_requires_review: v })} testId="recon-poor-review" />
      <SwitchRow colors={colors} label="No confirmed condition needs a manager" value={rc.unknown_requires_review} onChange={v => up({ unknown_requires_review: v })} testId="recon-unknown-review" />
    </SectionCard>
  );
};

export const MileageSection = ({ colors, rules, set }: P) => {
  const mi = rules.mileage;
  const up = (p: any) => set({ mileage: { ...mi, ...p } });
  return (
    <SectionCard colors={colors} title="Mileage adjustment" hint="Per 1,000 miles above or below what is expected for the age. Market predictions usually already reflect mileage, so this is off by default." enabled={mi.enabled} onToggle={v => up({ enabled: v })} testId="rules-mileage">
      <Row>
        <NumField colors={colors} label="Expected miles per year" value={mi.expected_per_year} onChange={v => up({ expected_per_year: v ?? 12000 })} prefix="" testId="mileage-expected" />
        <NumField colors={colors} label="Cap" value={mi.cap} onChange={v => up({ cap: v ?? 0 })} testId="mileage-cap" />
      </Row>
      <Row>
        <NumField colors={colors} label="Per 1,000 over (negative)" value={mi.per_1000_over} onChange={v => up({ per_1000_over: v ?? 0 })} negative testId="mileage-over" />
        <NumField colors={colors} label="Per 1,000 under (bonus)" value={mi.per_1000_under} onChange={v => up({ per_1000_under: v ?? 0 })} negative testId="mileage-under" />
      </Row>
    </SectionCard>
  );
};

export const AgeSection = ({ colors, rules, set }: P) => {
  const ag = rules.age;
  const up = (p: any) => set({ age: { ...ag, ...p } });
  const bands: any[] = ag.bands || [];
  const setBand = (i: number, p: any) => up({ bands: bands.map((b, j) => (j === i ? { ...b, ...p } : b)) });
  return (
    <SectionCard colors={colors} title="Age adjustment" hint="Bands by model-year age. Empty amount + review = older units need a manager. Off by default: market data already prices the model year." enabled={ag.enabled} onToggle={v => up({ enabled: v })} testId="rules-age">
      {bands.map((b, i) => (
        <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }} {...tid(`age-band-${i}`)}>
          <NumField colors={colors} label="From yr" value={b.min_years} onChange={v => setBand(i, { min_years: v ?? 0 })} prefix="" testId={`age-min-${i}`} />
          <NumField colors={colors} label="To yr" value={b.max_years} onChange={v => setBand(i, { max_years: v })} prefix="" allowEmpty emptyLabel="and up" testId={`age-max-${i}`} />
          <NumField colors={colors} label="Amount" value={b.amount} onChange={v => setBand(i, { amount: v, requires_review: v == null ? true : b.requires_review })} negative allowEmpty emptyLabel="Review" testId={`age-amount-${i}`} />
          <TouchableOpacity onPress={() => up({ bands: bands.filter((_, j) => j !== i) })} style={{ height: 42, justifyContent: 'center' }} {...tid(`age-remove-${i}`)}><Ionicons name="close-circle" size={20} color="#FF3B30" /></TouchableOpacity>
        </View>
      ))}
      <TouchableOpacity onPress={() => up({ bands: [...bands, { min_years: (bands[bands.length - 1]?.max_years ?? -1) + 1, max_years: null, amount: null, requires_review: true }] })} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start' }} {...tid('age-add')}>
        <Ionicons name="add-circle" size={18} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Add a band</Text>
      </TouchableOpacity>
    </SectionCard>
  );
};

export const ReserveSection = ({ colors, rules, set }: P) => {
  const rs = rules.reserve;
  return (
    <SectionCard colors={colors} title="Inventory / risk reserve" hint="A flat hold-back on every unit." enabled={rs.enabled} onToggle={v => set({ reserve: { ...rs, enabled: v } })} testId="rules-reserve">
      <Row><NumField colors={colors} label="Amount" value={rs.amount} onChange={v => set({ reserve: { ...rs, amount: v ?? 0 } })} testId="reserve-amount" /></Row>
    </SectionCard>
  );
};

export const ReviewSection = ({ colors, rules, set }: P) => {
  const rv = rules.review;
  const up = (p: any) => set({ review: { ...rv, ...p } });
  return (
    <SectionCard colors={colors} title="When a manager must look" hint="These flag the appraisal 'Needs your eyes' on the desk. Every appraisal still goes through the desk." testId="rules-review">
      <SwitchRow colors={colors} label="Market confidence is low" value={rv.low_confidence} onChange={v => up({ low_confidence: v })} testId="review-low-confidence" />
      <SwitchRow colors={colors} label="Condition is Poor" value={rv.poor_condition} onChange={v => up({ poor_condition: v })} testId="review-poor" />
      <Row><NumField colors={colors} label="Customer wants more than suggested by" value={rv.customer_gap_over} onChange={v => up({ customer_gap_over: v })} allowEmpty emptyLabel="Never flag" testId="review-gap" /></Row>
    </SectionCard>
  );
};

export const RangeSection = ({ colors, rules, set, options }: P) => {
  const rg = rules.range;
  const up = (p: any) => set({ range: { ...rg, ...p } });
  return (
    <SectionCard colors={colors} title="Trade range and rounding" hint="The range shown around the suggested ACV, and how numbers round." testId="rules-range">
      <ChipRow colors={colors} options={[{ key: 'fixed', label: 'Fixed below / above' }, { key: 'percent', label: 'Percent' }]} value={rg.method} onChange={m => up({ method: m })} testId="range-method" />
      <Row>
        {rg.method === 'percent' ? <NumField colors={colors} label="Spread" value={rg.percent} onChange={v => up({ percent: v ?? 0 })} prefix="" suffix="%" testId="range-percent" /> : (
          <>
            <NumField colors={colors} label="Below" value={rg.below} onChange={v => up({ below: v ?? 0 })} testId="range-below" />
            <NumField colors={colors} label="Above" value={rg.above} onChange={v => up({ above: v ?? 0 })} testId="range-above" />
          </>
        )}
      </Row>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>ROUND TO</Text>
      <ChipRow colors={colors} options={(options.roundings || [1, 5, 10, 25, 50, 100]).map((r: number) => ({ key: String(r), label: `$${r}` }))} value={String(rules.rounding)} onChange={k => set({ rounding: parseInt(k, 10) })} testId="rounding" />
    </SectionCard>
  );
};

export const FollowUpSection = ({ colors, rules, set, options }: P) => {
  const fu = rules.follow_up;
  const up = (p: any) => set({ follow_up: { ...fu, ...p } });
  return (
    <SectionCard colors={colors} title="After the customer answers" hint="When on, each outcome adds a contact tag so your existing tag workflows (campaigns, tasks, Jessi) take it from there. Nothing is enrolled otherwise." enabled={fu.tag_on_outcome} onToggle={v => up({ tag_on_outcome: v })} testId="rules-follow-up">
      {Object.entries(options.outcomes || {}).map(([k, label]: any) => (
        <TextField key={k} colors={colors} label={`${label} → tag`} value={fu.tags?.[k] || ''} onChange={v => up({ tags: { ...fu.tags, [k]: v } })} placeholder="leave empty for no tag" testId={`follow-up-tag-${k}`} />
      ))}
    </SectionCard>
  );
};
