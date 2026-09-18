import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, DAYS, GOLD, AMBER, tid, industries, industryOf, deptsFor, loadIndustries, locales, localeOf, loadLocales, isTollFree, TOLL_FREE_WARNING, DIFFICULTIES, type Client } from './shared';

type Grading = Record<string, Record<string, { name?: string | null; custom_id?: string | null; built_in?: string | null }>>;
type Props = { visible: boolean; onClose: () => void; colors: any; client?: Client | null; onSaved: (c: Client) => void; defaultFrom?: string; grading?: Grading | null; scorecardOptions?: { id: string; name: string; department?: string }[] };

const blank = { name: '', industry: 'automotive', locale: 'en-US', vat_id: '', brand: '', city: '', state: '', contact_name: '', contact_email: '', contact_phone: '', contact_title: '', per: { sales: '20', service: '20' } as Record<string, string>, textPer: {} as Record<string, string>, price: '400', start: '09:00', end: '18:00', days: [0, 1, 2, 3, 4, 5], vehicles: '', from_number: '', record: true, notes: '', timezone: 'America/Denver',
  difficulty: 'medium', direction_mix: 'mixed', tries: 3, spacing: 'next_day', reissue: true, scorecards: {} as Record<string, string | null> };
const SPACING = [['same_day', 'Later the same day'], ['next_day', 'Next open day'], ['two_days', 'Two open days later']] as const;
const MIX = [['mixed', 'Both, alternating', 'Each person gets inbound and outbound shops turn about'], ['inbound', 'Inbound only', 'The shopper always calls the store'], ['outbound', 'Outbound only', 'The shopper always leaves a lead and the rep calls back']] as const;

// Create / edit a client account: industry, who they are, the plan they bought (shops per department), when we may call, what the caller can mention.
export const ClientSheet = ({ visible, onClose, colors, client, onSaved, defaultFrom, grading, scorecardOptions }: Props) => {
  const { showToast } = useToast();
  const [f, setF] = useState<any>(blank);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));
  const [, setTick] = useState(0);
  const ind = industryOf(f.industry);
  const depts = deptsFor(f.industry);
  const loc = localeOf(f.locale);

  useEffect(() => {
    if (!visible) return;
    Promise.all([loadIndustries(), loadLocales()]).then(() => setTick(t => t + 1));
    if (client) setF({ name: client.name, industry: client.industry || 'automotive', locale: client.locale || 'en-US', vat_id: client.vat_id || '', brand: client.brand, city: client.city, state: client.state, contact_name: client.contact_name, contact_email: client.contact_email, contact_phone: client.contact_phone, contact_title: client.contact_title,
      per: Object.fromEntries(Object.entries(client.plan.per_month || {}).map(([k, v]) => [k, String(v)])), textPer: Object.fromEntries(Object.entries(client.plan.text_per_month || {}).map(([k, v]) => [k, String(v)])), price: String(client.plan.price_monthly), start: client.hours.start, end: client.hours.end, days: client.hours.days, vehicles: (client.offerings || client.vehicles || []).join('\n'),
      from_number: client.from_number || '', record: client.record_calls, notes: client.notes || '', timezone: client.timezone, text_scorecards: !!client.text_scorecards, live_calls: (client as any).live_calls ?? null,
      difficulty: client.difficulty || 'medium', direction_mix: client.direction_mix || 'mixed', tries: client.retry?.tries ?? 3, spacing: client.retry?.spacing || 'next_day', reissue: client.reissue_unreachable !== false, scorecards: { ...(client.scorecards || {}) } });
    else setF(blank);
  }, [visible, client?.id]);
  // switching country also moves the timezone to that country's default unless the admin typed their own
  const pickLocale = (code: string) => setF((x: any) => { const prev = localeOf(x.locale); const next = localeOf(code); return { ...x, locale: code, timezone: (!x.timezone || x.timezone === prev.timezone) ? next.timezone : x.timezone }; });
  const pickIndustry = (key: string) => setF((x: any) => ({ ...x, industry: key, per: Object.fromEntries(deptsFor(key).map(d => [d.key, x.per?.[d.key] ?? (deptsFor(key)[0].key === d.key ? '20' : '10')])) }));
  // Built-in card for one direction; an older per-department pick (both directions) moves to the other direction so it is not lost.
  const pickBuiltIn = (dept: string, dir: 'inbound' | 'outbound') => setF((x: any) => {
    const sc = { ...(x.scorecards || {}), [`${dept}:${dir}`]: null };
    const legacy = x.scorecards?.[dept];
    if (legacy) { sc[dept] = null; const other = `${dept}:${dir === 'inbound' ? 'outbound' : 'inbound'}`; if (!sc[other]) sc[other] = legacy; }
    return { ...x, scorecards: sc };
  });

  const save = async () => {
    if (!f.name.trim()) { showToast('Give the client a name', 'error'); return; }
    setBusy(true);
    try {
      const per_month = Object.fromEntries(depts.map(d => [d.key, Number(f.per?.[d.key]) || 0]));
      const text_per_month = Object.fromEntries(depts.map(d => [d.key, Number(f.textPer?.[d.key]) || 0]));
      const payload = { name: f.name, industry: f.industry, locale: f.locale, vat_id: f.vat_id || '', brand: f.brand, city: f.city, state: f.state, timezone: f.timezone, contact_name: f.contact_name, contact_email: f.contact_email.trim(), contact_phone: f.contact_phone, contact_title: f.contact_title,
        plan: { per_month, text_per_month, price_monthly: Number(f.price) || 0 }, hours: { start: f.start, end: f.end, days: f.days },
        vehicles: f.vehicles.split('\n').map((v: string) => v.trim()).filter(Boolean), from_number: f.from_number || '', record_calls: f.record, notes: f.notes, text_scorecards: !!f.text_scorecards, live_calls: f.live_calls === undefined ? null : f.live_calls,
        difficulty: f.difficulty, direction_mix: f.direction_mix, retry: { tries: f.tries, spacing: f.spacing }, reissue_unreachable: !!f.reissue, ...(grading ? { scorecards: f.scorecards } : {}) };
      const res = client ? await api.put(`/shop-clients/${client.id}`, payload) : await api.post('/shop-clients', payload);
      onSaved(res.data); onClose(); showToast(client ? 'Saved' : 'Client added', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };

  return (
    <Sheet visible={visible} onClose={onClose} title={client ? 'Edit client' : 'New mystery shop client'} colors={colors} testID="client-sheet" footer={<GoldButton label={client ? 'Save changes' : 'Add client'} onPress={save} busy={busy} testID="client-save" />}>
      <View style={{ gap: 8 }}>
        <Label t="INDUSTRY" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{industries().map(i => <Chip key={i.key} label={i.label} small active={f.industry === i.key} onPress={() => (client ? null : pickIndustry(i.key))} colors={colors} testID={`client-industry-${i.key}`} />)}</View>
        {!!client && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Industry is set when the account is created.</Text>}
      </View>
      <View style={{ gap: 8 }}>
        <Label t="COUNTRY & LANGUAGE (VOICES, CURRENCY, WHAT THE CALLER SPEAKS)" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{locales().map(l => <Chip key={l.code} label={`${l.label} · ${l.language_label}`} small active={f.locale === l.code} onPress={() => pickLocale(l.code)} colors={colors} testID={`client-locale-${l.code}`} />)}</View>
        <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('client-locale-note')}>{loc.language === 'nl' ? `Jessi shops, texts and coaches in Dutch. Prices in ${loc.symbol}. Times in ${loc.timezone}.` : `Calls, texts and reports in ${loc.language_label}. Prices in ${loc.symbol}. Times in ${loc.timezone}.`}</Text>
      </View>
      <Field label={`${ind.business.toUpperCase()} NAME`} value={f.name} onChange={(v: string) => set('name', v)} colors={colors} placeholder={f.industry === 'automotive' ? 'LHM Jeep Sandy' : `Their ${ind.business} name`} testID="client-name" />
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 2 }}><Field label={f.industry === 'automotive' ? 'BRANDS' : 'WHAT THEY DO (SHORT)'} value={f.brand} onChange={(v: string) => set('brand', v)} colors={colors} placeholder={f.industry === 'automotive' ? 'Jeep, Ram, Chrysler' : 'Residential HVAC, plumbing'} testID="client-brand" /></View>
        <View style={{ flex: 1.3 }}><Field label="CITY" value={f.city} onChange={(v: string) => set('city', v)} colors={colors} placeholder="Sandy" testID="client-city" /></View>
        <View style={{ flex: 0.7 }}><Field label="ST" value={f.state} onChange={(v: string) => set('state', v.toUpperCase().slice(0, 2))} colors={colors} placeholder="UT" autoCapitalize="characters" testID="client-state" /></View>
      </View>
      <View style={{ gap: 8 }}>
        <Label t="CONTACT (GETS THE PROPOSAL, INVOICE AND REPORT)" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1.4 }}><Field value={f.contact_name} onChange={(v: string) => set('contact_name', v)} colors={colors} placeholder="Name" testID="client-contact-name" /></View>
          <View style={{ flex: 1 }}><Field value={f.contact_title} onChange={(v: string) => set('contact_title', v)} colors={colors} placeholder="GM" testID="client-contact-title" /></View>
        </View>
        <Field value={f.contact_email} onChange={(v: string) => set('contact_email', v)} colors={colors} placeholder="owner@example.com" keyboardType="email-address" autoCapitalize="none" testID="client-contact-email" />
        <Field value={f.contact_phone} onChange={(v: string) => set('contact_phone', v)} colors={colors} placeholder="Contact phone (optional)" keyboardType="phone-pad" testID="client-contact-phone" />
        {loc.currency !== 'usd' && <Field value={f.vat_id} onChange={(v: string) => set('vat_id', v.toUpperCase())} colors={colors} placeholder={loc.country === 'NL' ? 'Btw-nummer, e.g. NL123456789B01 (invoice shows btw verlegd)' : 'VAT number (invoice shows reverse charge)'} autoCapitalize="characters" testID="client-vat-id" />}
      </View>
      <View style={{ gap: 8 }}>
        <Label t="PLAN PER MONTH (SHOPS PER DEPARTMENT)" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
          {depts.map(d => <View key={d.key} style={{ flex: 1, minWidth: 110 }}><Field label={d.label.toUpperCase()} value={f.per?.[d.key] ?? ''} onChange={(v: string) => set('per', { ...(f.per || {}), [d.key]: v.replace(/\D/g, '') })} colors={colors} keyboardType="number-pad" testID={`client-plan-${d.key}`} /></View>)}
          <View style={{ flex: 1, minWidth: 110 }}><Field label={`PRICE (${loc.symbol}/MO)`} value={f.price} onChange={(v: string) => set('price', v.replace(/[^\d.]/g, ''))} colors={colors} keyboardType="decimal-pad" testID="client-plan-price" /></View>
        </View>
        <Label t="TEXT SHOPS PER MONTH (THE SHOPPER TEXTS LIKE A LEAD, OPTIONAL)" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
          {depts.map(d => <View key={d.key} style={{ flex: 1, minWidth: 110 }}><Field label={`${d.label.toUpperCase()} TEXTS`} value={f.textPer?.[d.key] ?? ''} onChange={(v: string) => set('textPer', { ...(f.textPer || {}), [d.key]: v.replace(/\D/g, '') })} colors={colors} keyboardType="number-pad" placeholder="0" testID={`client-plan-text-${d.key}`} /></View>)}
        </View>
      </View>
      <View style={{ gap: 8 }}>
        <Label t="WHEN WE MAY CALL (THEIR LOCAL TIME)" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          <View style={{ flex: 1 }}><Field value={f.start} onChange={(v: string) => set('start', v)} colors={colors} placeholder="09:00" testID="client-hours-start" /></View>
          <Text style={{ color: colors.textSecondary }}>to</Text>
          <View style={{ flex: 1 }}><Field value={f.end} onChange={(v: string) => set('end', v)} colors={colors} placeholder="18:00" testID="client-hours-end" /></View>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {DAYS.map((d, i) => <Chip key={d} label={d} small active={f.days.includes(i)} onPress={() => set('days', f.days.includes(i) ? f.days.filter((x: number) => x !== i) : [...f.days, i].sort())} colors={colors} testID={`client-day-${i}`} />)}
        </View>
        <Field value={f.timezone} onChange={(v: string) => set('timezone', v)} colors={colors} placeholder="America/Denver" autoCapitalize="none" testID="client-timezone" />
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} {...tid('client-night-guard')}>Never before 8 AM or after 8 PM in the person's own time, whatever is set here. Each person can have their own hours and timezone under People.</Text>
      </View>
      <View style={{ gap: 8 }}>
        <Label t="HOW TOUGH THE SHOPPER IS" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
          {DIFFICULTIES.map(d => <Chip key={d.key} label={d.label} small active={f.difficulty === d.key} onPress={() => set('difficulty', d.key)} colors={colors} testID={`client-difficulty-${d.key}`} />)}
          <Chip label="Mix it up" small active={f.difficulty === 'mixed'} onPress={() => set('difficulty', 'mixed')} colors={colors} testID="client-difficulty-mixed" />
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} {...tid('client-difficulty-hint')}>{f.difficulty === 'mixed' ? 'Mostly medium, some easy, a few hard, drawn at random per shop.' : DIFFICULTIES.find(d => d.key === f.difficulty)?.hint} Every concern comes up once; a reasonable answer settles it. The scorecard is the same at every level. Set per person under People.</Text>
      </View>
      <View style={{ gap: 8 }}>
        <Label t="PHONE SHOPS: WHO CALLS WHOM" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{MIX.map(([k, label]) => <Chip key={k} label={label} small active={f.direction_mix === k} onPress={() => set('direction_mix', k)} colors={colors} testID={`client-mix-${k}`} />)}</View>
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} {...tid('client-mix-hint')}>{MIX.find(m => m[0] === f.direction_mix)?.[2]}. Outbound shops are graded with the department's follow-up card (open with name, store and reason).</Text>
      </View>
      <View style={{ gap: 8 }}>
        <Label t="IF NOBODY PICKS UP" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <Text style={{ fontSize: 13, color: colors.text }}>Try</Text>
          {[1, 2, 3, 4, 5].map(n => <Chip key={n} label={String(n)} small active={f.tries === n} onPress={() => set('tries', n)} colors={colors} testID={`client-tries-${n}`} />)}
          <Text style={{ fontSize: 13, color: colors.text }}>{f.tries === 1 ? 'time, then park it' : 'times, then park it'}</Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{SPACING.map(([k, label]) => <Chip key={k} label={label} small active={f.spacing === k} onPress={() => set('spacing', k)} colors={colors} testID={`client-spacing-${k}`} />)}</View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }}>
          <Ionicons name="refresh" size={18} color={GOLD} />
          <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Re-issue unreachable shops</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>When a shop is parked after all tries, the planner books a fresh one on a new date (once per shop) so everyone still gets their monthly number.</Text></View>
          <Switch value={!!f.reissue} onValueChange={(v) => set('reissue', v)} {...tid('client-reissue-toggle')} />
        </View>
      </View>
      {!!client && !!grading && (
        <View style={{ gap: 8 }} {...tid('client-grading')}>
          <Label t="HOW EACH DEPARTMENT IS GRADED" colors={colors} />
          {depts.map(d => (
            <View key={d.key} style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid(`client-grading-${d.key}`)}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{d.label}</Text>
              {(['inbound', 'outbound'] as const).map(dir => {
                const key = `${d.key}:${dir}`;
                const picked = f.scorecards?.[key] ?? f.scorecards?.[d.key] ?? null;
                const builtIn = grading[d.key]?.[dir]?.built_in || 'Built-in card';
                return (
                  <View key={dir} style={{ gap: 6 }}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>{dir === 'inbound' ? 'INBOUND (THEY CALL THE STORE)' : 'OUTBOUND (REP CALLS THEM BACK)'}</Text>
                    <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
                      <Chip label={builtIn} small active={!picked} onPress={() => pickBuiltIn(d.key, dir)} colors={colors} testID={`client-card-${d.key}-${dir}-builtin`} />
                      {(scorecardOptions || []).map(o => <Chip key={o.id} label={o.name} small active={picked === o.id} onPress={() => set('scorecards', { ...f.scorecards, [key]: o.id })} colors={colors} testID={`client-card-${d.key}-${dir}-${o.id}`} />)}
                    </View>
                  </View>
                );
              })}
            </View>
          ))}
        </View>
      )}
      <Field label={`${ind.offering.field.toUpperCase()} (ONE PER LINE)`} value={f.vehicles} onChange={(v: string) => set('vehicles', v)} colors={colors} multiline placeholder={ind.offering.hint} testID="client-vehicles" />
      <Field label="CALL FROM NUMBER (OPTIONAL)" value={f.from_number} onChange={(v: string) => set('from_number', v)} colors={colors} placeholder={defaultFrom ? `Default ${defaultFrom}` : 'Twilio number the caller calls from'} keyboardType="phone-pad" testID="client-from-number" />
      {isTollFree(f.from_number) && <Text style={{ fontSize: 12, color: AMBER, lineHeight: 16, marginTop: -4 }} {...tid('client-from-number-tollfree')}>{TOLL_FREE_WARNING}</Text>}      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }}>
        <Ionicons name="recording" size={18} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Record shop calls</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Recordings go on the client report. Consent is covered in the proposal.</Text></View>
        <Switch value={f.record} onValueChange={(v) => set('record', v)} {...tid('client-record-toggle')} />
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }}>
        <Ionicons name="chatbubble-ellipses" size={18} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Text people their scorecard</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Right after each shop is graded, the person gets a text with their score, top win, top fix and a link to the full scorecard and recording.</Text></View>
        <Switch value={!!f.text_scorecards} onValueChange={(v) => set('text_scorecards', v)} {...tid('client-text-scorecards-toggle')} />
      </View>
      {(f.locale || 'en-US').startsWith('en') && (
        <View style={{ gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('client-live-calls')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <Ionicons name="radio" size={18} color={GOLD} />
            <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>GPT-Live shopper</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>{f.live_calls === null || f.live_calls === undefined ? 'Follows the Test Lab switch. Pick On to try the full-duplex shopper on this client only.' : f.live_calls ? 'Phone shops for this client run on GPT-Live, whatever the Test Lab says.' : 'Phone shops for this client stay on the classic relay, whatever the Test Lab says.'}</Text></View>
          </View>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            <Chip label="Follow Test Lab" small active={f.live_calls === null || f.live_calls === undefined} onPress={() => set('live_calls', null)} colors={colors} testID="client-live-calls-lab" />
            <Chip label="On" small active={f.live_calls === true} onPress={() => set('live_calls', true)} colors={colors} testID="client-live-calls-on" />
            <Chip label="Off" small active={f.live_calls === false} onPress={() => set('live_calls', false)} colors={colors} testID="client-live-calls-off" />
          </View>
        </View>
      )}
      <Field label="NOTES" value={f.notes} onChange={(v: string) => set('notes', v)} colors={colors} multiline placeholder={`Anything the ${ind.customer} should know about this ${ind.business}`} testID="client-notes" />
    </Sheet>
  );
};
