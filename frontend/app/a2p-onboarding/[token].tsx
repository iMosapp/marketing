/**
 * Public, no-login A2P 10DLC onboarding form the dealership fills in from the text / email we send at signup.
 * Saves as they go (PUT), "Send to {sender}" submits (POST) and pings the iMOS team.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { GoldButton, LIGHT, GOLD, GREEN, RED } from '../../components/mystery-shops/shared';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const inp = { backgroundColor: LIGHT.surface, borderRadius: 12, borderWidth: 1, borderColor: LIGHT.border, paddingHorizontal: 12, paddingVertical: 12, color: LIGHT.text, fontSize: 15 } as const;
const PRETTY: Record<string, string> = { 'business.ein': 'EIN', 'business.legal_name': 'legal business name', 'business.website': 'website', 'business.street': 'street', 'business.city': 'city', 'business.state': 'state', 'business.postal_code': 'ZIP', 'business.business_type': 'business type', 'business.ein_format': 'EIN (9 digits)', 'rep.first_name': 'contact first name', 'rep.last_name': 'contact last name', 'rep.email': 'contact email', 'rep.phone': 'contact phone', 'rep.title': 'contact title', 'rep.job_position': 'contact position', 'campaign.use_case': 'texting use', 'campaign.description': 'what reps text about', 'campaign.message_flow': 'how customers opt in', 'campaign.privacy_url': 'privacy policy link', 'campaign.terms_url': 'terms link', 'campaign.samples': 'two sample texts' };

const Card = ({ title, sub, children, testID }: { title: string; sub?: string; children: React.ReactNode; testID: string }) => (
  <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18, gap: 12 }} {...tid(testID)}>
    <View style={{ gap: 2 }}><Text style={{ fontSize: 18, fontWeight: '800', color: LIGHT.text }}>{title}</Text>{!!sub && <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary, lineHeight: 19 }}>{sub}</Text>}</View>
    {children}
  </View>
);
const F = ({ label, value, onChange, testID, placeholder, hint, multiline, keyboardType, flex }: any) => (
  <View style={{ gap: 5, flex }}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: LIGHT.textSecondary, letterSpacing: 0.6, textTransform: 'uppercase' }}>{label}</Text>
    <TextInput value={value ?? ''} onChangeText={onChange} placeholder={placeholder} placeholderTextColor="#9A9A9A" multiline={multiline} keyboardType={keyboardType} autoCapitalize="none"
      style={[inp, multiline && { minHeight: 84, textAlignVertical: 'top' }]} {...tid(testID)} />
    {!!hint && <Text style={{ fontSize: 12, color: LIGHT.textSecondary, lineHeight: 17 }}>{hint}</Text>}
  </View>
);
const Chips = ({ label, value, options, onChange, testID }: any) => (
  <View style={{ gap: 6 }}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: LIGHT.textSecondary, letterSpacing: 0.6, textTransform: 'uppercase' }}>{label}</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
      {options.map((o: any) => { const k = typeof o === 'string' ? o : o.key; const t = typeof o === 'string' ? o : o.label; const on = value === k; return (
        <TouchableOpacity key={k} onPress={() => onChange(k)} style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: 14, backgroundColor: on ? GOLD : LIGHT.surface, borderWidth: 1, borderColor: on ? GOLD : LIGHT.border }} {...tid(`${testID}-${k}`)}>
          <Text style={{ fontSize: 13, fontWeight: '700', color: LIGHT.text }}>{t}</Text>
        </TouchableOpacity>); })}
    </View>
  </View>
);

export default function PublicA2POnboarding() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const wide = width > 800;
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [rec, setRec] = useState<any>(null);
  const [contact, setContact] = useState<any>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState('');
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [done, setDone] = useState(false);

  const hydrate = (d: any) => { setData(d); setRec({ business: { ...d.business, ein: '' }, rep: d.rep, campaign: d.campaign, cnam: d.cnam }); setContact((c: any) => ({ name: c.name || `${d.rep?.first_name || ''} ${d.rep?.last_name || ''}`.trim(), email: c.email || d.rep?.email || '', phone: c.phone || d.rep?.phone || '' })); };
  useEffect(() => { if (token) api.get(`/public/a2p-onboarding/${token}`).then(r => hydrate(r.data)).catch(() => setError('invalid')); }, [token]);

  const set = (block: string, key: string, v: any) => setRec((r: any) => ({ ...r, [block]: { ...(r[block] || {}), [key]: v } }));
  const setSample = (i: number, v: string) => setRec((r: any) => { const samples = [...(r.campaign?.samples || [])]; samples[i] = v; return { ...r, campaign: { ...r.campaign, samples } }; });
  const body = () => ({ business: rec.business, rep: rec.rep, campaign: rec.campaign, cnam: rec.cnam, contact });

  const save = async (submit: boolean) => {
    setBusy(submit ? 'submit' : 'save'); setErr('');
    try {
      const r = submit ? await api.post(`/public/a2p-onboarding/${token}/submit`, body()) : await api.put(`/public/a2p-onboarding/${token}`, body());
      hydrate(r.data); setSavedAt(new Date()); if (submit) setDone(true);
    } catch (e: any) { setErr(e?.response?.data?.detail || 'Could not save. Try again.'); }
    finally { setBusy(null); }
  };

  const b = rec?.business || {}, rp = rec?.rep || {}, c = rec?.campaign || {}, cn = rec?.cnam || {};
  const missing: string[] = data?.missing || [];
  const name = data?.store?.name || 'your dealership';
  const locked = !!data?.submitted_to_twilio;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: LIGHT.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 32 : 16, paddingBottom: 80, alignItems: 'center' }} keyboardShouldPersistTaps="handled">
        <View style={{ width: '100%', maxWidth: 760, gap: 18 }} {...tid('a2p-page')}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>TEXTING REGISTRATION</Text>
          {error ? <Text style={{ fontSize: 15, color: LIGHT.textSecondary }} {...tid('a2p-error')}>This link is not valid any more. Reply to the text or email you received and we will send a fresh one.</Text> : !rec ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <Text style={{ fontSize: wide ? 32 : 26, fontWeight: '800', color: LIGHT.text }} {...tid('a2p-title')}>Register {name} for customer texting</Text>
              <Text style={{ fontSize: 15, color: LIGHT.text, lineHeight: 23 }}>US carriers require every business that texts customers to be registered (A2P 10DLC). Until that is done, texts from your team are throttled or blocked. This takes about 10 minutes; everything saves as you go. {data.sender_name} and the I'm On Social team review it before it goes to the carriers.</Text>

              {locked && (
                <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, padding: 18, borderWidth: 1, borderColor: GREEN + '88', flexDirection: 'row', gap: 12, alignItems: 'center' }} {...tid('a2p-locked')}>
                  <Ionicons name="lock-closed" size={26} color={GREEN} />
                  <Text style={{ flex: 1, fontSize: 15, color: LIGHT.text, lineHeight: 21 }}>This registration is already with the carriers. Reply to our email if something needs to change.</Text>
                </View>
              )}
              {(done || data.returned_at) && !locked && (
                <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, padding: 18, borderWidth: 1, borderColor: (missing.length ? GOLD : GREEN) + '88', flexDirection: 'row', gap: 12, alignItems: 'center' }} {...tid('a2p-returned')}>
                  <Ionicons name={missing.length ? 'alert-circle' : 'checkmark-circle'} size={28} color={missing.length ? GOLD : GREEN} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 17, fontWeight: '800', color: LIGHT.text }}>{missing.length ? 'Received, a few items still needed' : `Thank you, ${data.sender_name} has it`}</Text>
                    <Text style={{ fontSize: 14, color: LIGHT.textSecondary, lineHeight: 20 }}>{missing.length ? 'Still needed: ' + missing.map(m => PRETTY[m] || m).join(', ') + '. Fill them in below and press Send again.' : 'We review it, run it past the carrier checks and submit. You will hear from us if anything needs a tweak.'}</Text>
                  </View>
                </View>
              )}

              <Card title="Your business, as filed with the IRS" sub="Copy these from your IRS letter (CP-575 or 147C). Most rejections are a legal name / EIN mismatch, so the DBA on the sign is not what goes here." testID="a2p-business">
                <F label="Legal business name" value={b.legal_name} onChange={(v: string) => set('business', 'legal_name', v)} testID="a2p-legal-name" placeholder="Smith Motors LLC" />
                <F label={`EIN${b.has_ein ? ` (on file: ${b.ein_masked}, leave blank to keep)` : ''}`} value={b.ein} onChange={(v: string) => set('business', 'ein', v)} testID="a2p-ein" placeholder="12-3456789" keyboardType="numbers-and-punctuation" />
                <Chips label="Entity type" value={b.business_type} options={data.options.business_types} onChange={(v: string) => set('business', 'business_type', v)} testID="a2p-type" />
                <F label="Website" value={b.website} onChange={(v: string) => set('business', 'website', v)} testID="a2p-website" placeholder="https://www.smithmotors.com" />
                <F label="Street" value={b.street} onChange={(v: string) => set('business', 'street', v)} testID="a2p-street" />
                <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                  <F label="City" value={b.city} onChange={(v: string) => set('business', 'city', v)} testID="a2p-city" flex={2} />
                  <F label="State" value={b.state} onChange={(v: string) => set('business', 'state', v.toUpperCase().slice(0, 2))} testID="a2p-state" placeholder="UT" flex={1} />
                  <F label="ZIP" value={b.postal_code} onChange={(v: string) => set('business', 'postal_code', v)} testID="a2p-zip" flex={1} />
                </View>
              </Card>

              <Card title="Who can vouch for this registration" sub="An owner, GM or controller. The carriers may email this person; use an address at your dealership's domain, not Gmail." testID="a2p-rep">
                <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                  <F label="First name" value={rp.first_name} onChange={(v: string) => set('rep', 'first_name', v)} testID="a2p-rep-first" flex={1} />
                  <F label="Last name" value={rp.last_name} onChange={(v: string) => set('rep', 'last_name', v)} testID="a2p-rep-last" flex={1} />
                </View>
                <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                  <F label="Work email" value={rp.email} onChange={(v: string) => set('rep', 'email', v)} testID="a2p-rep-email" keyboardType="email-address" flex={1.4} />
                  <F label="Direct phone" value={rp.phone} onChange={(v: string) => set('rep', 'phone', v)} testID="a2p-rep-phone" keyboardType="phone-pad" flex={1} />
                </View>
                <F label="Title" value={rp.title} onChange={(v: string) => set('rep', 'title', v)} testID="a2p-rep-title" placeholder="General Manager" />
                <Chips label="Position" value={rp.job_position} options={data.options.job_positions} onChange={(v: string) => set('rep', 'job_position', v)} testID="a2p-rep-position" />
              </Card>

              <Card title="How customers agree to texts" sub="Carriers want to know how a customer's number ends up with a rep and that they said yes. We wrote a draft from how the app works; adjust it to match your store." testID="a2p-campaign">
                <Chips label="What your team mostly texts" value={c.use_case} options={Object.entries(data.options.use_cases || {}).map(([k, v]) => ({ key: k, label: String(v).split(' (')[0] }))} onChange={(v: string) => set('campaign', 'use_case', v)} testID="a2p-use-case" />
                <F label="What reps text customers about" value={c.description} onChange={(v: string) => set('campaign', 'description', v)} testID="a2p-description" multiline />
                <F label="How a customer opts in" value={c.message_flow} onChange={(v: string) => set('campaign', 'message_flow', v)} testID="a2p-message-flow" multiline hint="Name every moment a number is collected (in person, credit app, website form, customer texts first) and say the customer agrees to texts." />
                {[0, 1, 2].map(i => (
                  <F key={i} label={`Sample text ${i + 1}${i > 1 ? ' (optional)' : ''}`} value={c.samples?.[i] || ''} onChange={(v: string) => setSample(i, v)} testID={`a2p-sample-${i}`} multiline hint={i === 0 ? 'Realistic, names the dealership, ends with "Reply STOP to opt out". No link shorteners.' : undefined} />
                ))}
              </Card>

              <Card title="Privacy policy and terms on your website" sub="Both pages must be public and mention texting. Your privacy policy needs this sentence: 'No mobile information will be shared with third parties or affiliates for marketing or promotional purposes.' Your terms need STOP, HELP, message frequency and 'Msg & data rates may apply'." testID="a2p-links">
                <F label="Privacy policy URL" value={c.privacy_url} onChange={(v: string) => set('campaign', 'privacy_url', v)} testID="a2p-privacy-url" placeholder="https://www.smithmotors.com/privacy" />
                <F label="Terms URL" value={c.terms_url} onChange={(v: string) => set('campaign', 'terms_url', v)} testID="a2p-terms-url" placeholder="https://www.smithmotors.com/sms-terms" />
              </Card>

              <Card title="Caller ID name on outbound calls" sub="What shows on the customer's phone when a rep calls from an app number. Up to 15 letters and numbers, shown in caps." testID="a2p-cnam">
                <F label="Display name" value={cn.display_name} onChange={(v: string) => set('cnam', 'display_name', v.toUpperCase().slice(0, 15))} testID="a2p-cnam-name" placeholder="SMITH MOTORS" />
              </Card>

              <Card title="Where we reach you about this" sub="For questions and the approval notice." testID="a2p-contact">
                <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                  <F label="Name" value={contact.name} onChange={(v: string) => setContact({ ...contact, name: v })} testID="a2p-contact-name" flex={1.2} />
                  <F label="Email" value={contact.email} onChange={(v: string) => setContact({ ...contact, email: v })} testID="a2p-contact-email" keyboardType="email-address" flex={1.4} />
                  <F label="Cell" value={contact.phone} onChange={(v: string) => setContact({ ...contact, phone: v })} testID="a2p-contact-phone" keyboardType="phone-pad" flex={1} />
                </View>
              </Card>

              {!!err && <Text style={{ fontSize: 14, color: RED, fontWeight: '600' }} {...tid('a2p-err')}>{err}</Text>}
              {!!savedAt && !err && <Text style={{ fontSize: 13, color: GREEN, fontWeight: '600' }} {...tid('a2p-saved')}>Saved {savedAt.toLocaleTimeString()}</Text>}
              {!locked && (
                <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                  <View style={{ flex: 1 }}><GoldButton label="Save and finish later" onPress={() => save(false)} busy={busy === 'save'} disabled={!!busy} testID="a2p-save" icon="save-outline" outline /></View>
                  <View style={{ flex: 1 }}><GoldButton label={`Send to ${data.sender_name}`} onPress={() => save(true)} busy={busy === 'submit'} disabled={!!busy} testID="a2p-submit" icon="paper-plane" /></View>
                </View>
              )}
              <Text style={{ fontSize: 12, color: LIGHT.textSecondary, textAlign: 'center' }}>I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065 · Your EIN is used only for this registration with Twilio and The Campaign Registry and is never displayed again after saving.</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
