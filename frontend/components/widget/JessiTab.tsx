import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid, errText, timeAgo } from '../inbox/ownership';
import { Section, Label, Hint, inputStyle } from '../inbox/InboxEditorParts';
import { Field, ToggleRow } from './parts';
import { SiteCrawlCard } from './SiteCrawlCard';

type Fact = { id: string; text: string; added_by_name?: string };
type Chat = { id: string; status: string; name: string; turns: number; reason: string; host: string; at: string | null; last: string; mode?: string; agent?: string; booked?: boolean; live?: boolean };
type Props = { widgetId: string; form: any; set: (section: string, patch: any) => void; colors: any; facts: Fact[]; setFacts: (f: Fact[]) => void; storeName: string | null; showToast: (m: string, t?: any, d?: number) => void; canManage: boolean; recentChats: Chat[]; chatOn: boolean; onTurnOnChat: () => void; siteUrl: string; onKbSaved: (kb: any) => void };

const CHAT_STATUS: Record<string, { label: string; color: string }> = { open: { label: 'Chatting', color: GOLD }, handed_off: { label: 'Handed to the team', color: '#34C759' }, closed: { label: 'Ended', color: '#8E8E93' } };

const Pill = ({ text, onRemove, colors, testId }: { text: string; onRemove?: () => void; colors: any; testId: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 12, paddingRight: onRemove ? 6 : 12, height: 34, borderRadius: 17, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, maxWidth: '100%' }} {...tid(testId)}>
    <Text style={{ fontSize: 13, color: colors.text, flexShrink: 1 }} numberOfLines={1}>{text}</Text>
    {onRemove ? <TouchableOpacity onPress={onRemove} hitSlop={6} {...tid(`${testId}-remove`)}><Ionicons name="close-circle" size={18} color={colors.textSecondary} /></TouchableOpacity> : null}
  </View>
);

const AddRow = ({ placeholder, onAdd, colors, testId, busy }: { placeholder: string; onAdd: (v: string) => void | Promise<void>; colors: any; testId: string; busy?: boolean }) => {
  const [v, setV] = useState('');
  const go = async () => { const t = v.trim(); if (!t) return; await onAdd(t); setV(''); };
  return (
    <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
      <TextInput value={v} onChangeText={setV} placeholder={placeholder} placeholderTextColor={colors.textSecondary} onSubmitEditing={go} style={[inputStyle(colors), { flex: 1 }]} {...tid(`${testId}-input`)} />
      <TouchableOpacity onPress={go} disabled={busy || !v.trim()} style={{ width: 46, height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: busy || !v.trim() ? 0.5 : 1 }} {...tid(`${testId}-add`)}>
        {busy ? <ActivityIndicator color="#111" /> : <Ionicons name="add" size={22} color="#111" />}
      </TouchableOpacity>
    </View>
  );
};

export const JessiTab = ({ widgetId, form, set, colors, facts, setFacts, storeName, showToast, canManage, recentChats, chatOn, onTurnOnChat, siteUrl, onKbSaved }: Props) => {
  const router = useRouter();
  const kb = form.kb || {};
  const setKb = (p: any) => set('kb', p);
  const [factBusy, setFactBusy] = useState(false);
  const [q, setQ] = useState('');
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<any>(null);

  const addFact = async (text: string) => {
    setFactBusy(true);
    try { const r = await api.post(`/widgets/${widgetId}/facts`, { text }); setFacts([...facts, r.data.fact]); }
    catch (e: any) { showToast(errText(e, 'Could not save the fact'), 'error'); }
    finally { setFactBusy(false); }
  };
  const removeFact = async (id: string) => {
    try { await api.delete(`/widgets/${widgetId}/facts/${id}`); setFacts(facts.filter(f => f.id !== id)); }
    catch (e: any) { showToast(errText(e, 'Could not remove the fact'), 'error'); }
  };
  const ask = async () => {
    if (!q.trim()) return;
    setAsking(true); setAnswer(null);
    try { setAnswer((await api.post(`/widgets/${widgetId}/ask`, { question: q.trim() })).data); }
    catch (e: any) { showToast(errText(e, 'Jessi could not answer'), 'error'); }
    finally { setAsking(false); }
  };
  const specials: any[] = kb.specials || [];
  const patchSpecial = (i: number, p: any) => setKb({ specials: specials.map((s, j) => (j === i ? { ...s, ...p } : s)) });
  const business = kb.mode === 'business';

  return (
    <>
      {!chatOn ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: '#FF950022', borderWidth: 1, borderColor: '#FF950055' }} {...tid('widget-chat-off-banner')}>
          <Ionicons name="chatbubble-ellipses-outline" size={20} color="#FF9500" />
          <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }}>The Chat now door is off, so visitors cannot talk to Jessi yet. Everything you set here is kept.</Text>
          {canManage ? <TouchableOpacity onPress={onTurnOnChat} style={{ paddingHorizontal: 12, height: 34, borderRadius: 17, backgroundColor: GOLD, justifyContent: 'center' }} {...tid('widget-chat-turn-on')}><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Turn on</Text></TouchableOpacity> : null}
        </View>
      ) : null}
      <Section colors={colors} testId="widget-section-mode">
        <Label colors={colors}>What kind of site is this?</Label>
        <Hint colors={colors}>{business ? 'Jessi is the product expert: she answers what it does, features, plans and pricing straight from your website, and books demos. Only "talk to a person" hands off.' : 'Jessi answers hours, inventory and store questions, books test drives and service, and hands prices, payments and trade values to a person.'}</Hint>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {[{ v: 'dealership', l: 'Dealership', icon: 'car-sport-outline' }, { v: 'business', l: 'Business or software', icon: 'briefcase-outline' }].map(o => {
            const on = (kb.mode || 'dealership') === o.v;
            return (
              <TouchableOpacity key={o.v} onPress={() => setKb({ mode: o.v })} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 44, borderRadius: 12, backgroundColor: on ? GOLD : colors.surface, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`widget-kb-mode-${o.v}`)}>
                <Ionicons name={o.icon as any} size={17} color={on ? '#111' : colors.textSecondary} />
                <Text style={{ fontSize: 13.5, fontWeight: '800', color: on ? '#111' : colors.text }}>{o.l}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </Section>
      <Section colors={colors} testId="widget-section-test">
        <Label colors={colors}>Test Jessi</Label>
        <Hint colors={colors}>Ask what a visitor would ask. Unsaved changes on this tab are not used until you Save.</Hint>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TextInput value={q} onChangeText={setQ} placeholder={business ? 'How much does it cost per month?' : 'Do you have any trucks under 40k?'} placeholderTextColor={colors.textSecondary} onSubmitEditing={ask} style={[inputStyle(colors), { flex: 1 }]} {...tid('widget-ask-input')} />
          <TouchableOpacity onPress={ask} disabled={asking || !q.trim()} style={{ height: 46, paddingHorizontal: 14, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: asking || !q.trim() ? 0.5 : 1 }} {...tid('widget-ask-btn')}>
            {asking ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Ask</Text>}
          </TouchableOpacity>
        </View>
        {answer ? (
          <View style={{ marginTop: 10, padding: 12, borderRadius: 12, backgroundColor: colors.surface, gap: 6 }} {...tid('widget-ask-answer')}>
            <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }}>{answer.reply}</Text>
            <Text style={{ fontSize: 11, color: answer.handoff ? '#FF9500' : colors.textSecondary }}>
              {answer.handoff ? `Hands off to the team (${answer.reason})` : 'Answered herself'} · used {answer.used?.facts || 0} facts, {answer.used?.specials || 0} {answer.used?.mode === 'business' ? 'offers' : 'specials'}{answer.used?.mode === 'business' ? `, ${answer.used?.site_pages || 0} website pages` : `, ${answer.used?.inventory_matches || 0} of ${answer.used?.inventory_total || 0} vehicles${answer.used?.hours ? ', store hours' : ', no hours on file'}`}
            </Text>
          </View>
        ) : null}
      </Section>

      <Section colors={colors} testId="widget-section-welcome">
        <Field label="First thing Jessi says" hint={business ? "Blank = a friendly default that invites questions about what you do, how it works and pricing." : "Blank = a friendly default that mentions hours, inventory and 'want a person, just say so'."} value={kb.welcome || ''} onChange={v => setKb({ welcome: v })} multiline colors={colors} testId="widget-kb-welcome" maxLength={300} top={false} />
        {!business ? <ToggleRow label="Let Jessi state listed prices" hint="Off = she never mentions a price, even the sticker in your feed. Payments, discounts and trade values always go to a person." value={!!kb.share_listed_prices} onChange={v => setKb({ share_listed_prices: v })} colors={colors} testId="widget-kb-share-prices" /> : null}
      </Section>

      <Section colors={colors} testId="widget-section-starters">
        <Label colors={colors}>Starter questions</Label>
        <Hint colors={colors}>Up to three tap-to-ask chips under Jessi's greeting so visitors see what she can answer. Blank = {business ? '"What does it cost?", "How does it work?", "Book a demo"' : '"What are your hours?", "Is it still available?", "Book a test drive"'}. Anything with book, schedule, demo or test drive opens the booking form.</Hint>
        {[0, 1, 2].map(i => (
          <TextInput key={i} value={(kb.starters || [])[i] || ''} onChangeText={v => { const next = [...(kb.starters || ['', '', ''])]; while (next.length < 3) next.push(''); next[i] = v; setKb({ starters: next }); }}
            placeholder={(business ? ['What does it cost?', 'How does it work?', 'Book a demo'] : ['What are your hours?', 'Is it still available?', 'Book a test drive'])[i]} placeholderTextColor={colors.textSecondary} maxLength={60}
            style={[inputStyle(colors), { marginBottom: 8 }]} {...tid(`widget-kb-starter-${i}`)} />
        ))}
      </Section>

      <Section colors={colors} testId="widget-section-facts">
        <Label colors={colors}>{business ? 'Company facts' : 'Store facts'}</Label>
        <Hint colors={colors}>{business ? 'One plain sentence each: "Setup takes about 20 minutes", "Works with any CRM through Zapier". Anything the website does not say clearly.' : 'Shared with Jessi\'s texts (My VA → store facts). One plain sentence each: "Service is open Saturdays until 4", "We deliver within 100 miles". Hours and address come from the Store Profile automatically.'}</Hint>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {facts.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('widget-facts-empty')}>No facts yet{storeName ? ` for ${storeName}` : ''}.</Text> : null}
          {facts.map(f => <Pill key={f.id} text={f.text} onRemove={canManage ? () => removeFact(f.id) : undefined} colors={colors} testId={`widget-fact-${f.id}`} />)}
        </View>
        {canManage ? <AddRow placeholder="Add a fact Jessi can use" onAdd={addFact} colors={colors} testId="widget-fact" busy={factBusy} /> : null}
      </Section>

      <SiteCrawlCard widgetId={widgetId} siteUrl={siteUrl} colors={colors} canManage={canManage} showToast={showToast} business={business} onApplied={r => { setFacts(r.facts); onKbSaved(r.kb); }} />

      <Section colors={colors} testId="widget-section-specials">
        <Label colors={colors}>{business ? 'Current offers' : 'Specials'}</Label>
        <Hint colors={colors}>Jessi repeats these word for word and never adds numbers of her own. Expired ones stop being used on their own.</Hint>
        {specials.map((s, i) => (
          <View key={s.id || i} style={{ padding: 10, borderRadius: 12, backgroundColor: colors.surface, marginBottom: 8, gap: 6 }} {...tid(`widget-special-${i}`)}>
            <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
              <TextInput value={s.title} onChangeText={v => patchSpecial(i, { title: v })} placeholder="Title, like $39 oil change" placeholderTextColor={colors.textSecondary} style={[inputStyle(colors), { flex: 1 }]} {...tid(`widget-special-${i}-title`)} />
              <TouchableOpacity onPress={() => setKb({ specials: specials.filter((_, j) => j !== i) })} hitSlop={8} {...tid(`widget-special-${i}-remove`)}><Ionicons name="trash-outline" size={20} color="#FF3B30" /></TouchableOpacity>
            </View>
            <TextInput value={s.details || ''} onChangeText={v => patchSpecial(i, { details: v })} placeholder="Details or fine print (optional)" placeholderTextColor={colors.textSecondary} style={inputStyle(colors)} {...tid(`widget-special-${i}-details`)} />
            <TextInput value={s.ends || ''} onChangeText={v => patchSpecial(i, { ends: v })} placeholder="Ends on (YYYY-MM-DD, optional)" placeholderTextColor={colors.textSecondary} autoCapitalize="none" style={[inputStyle(colors), { width: 220 }]} {...tid(`widget-special-${i}-ends`)} />
          </View>
        ))}
        <TouchableOpacity onPress={() => setKb({ specials: [...specials, { id: `n${Date.now()}`, title: '', details: '', ends: '' }] })} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8 }} {...tid('widget-special-add')}>
          <Ionicons name="add-circle-outline" size={20} color={GOLD} />
          <Text style={{ fontSize: 14, fontWeight: '700', color: GOLD }}>Add a special</Text>
        </TouchableOpacity>
      </Section>

      <Section colors={colors} testId="widget-section-never">
        <Label colors={colors}>Always hand these to a person</Label>
        <Hint colors={colors}>{business ? 'Jessi answers pricing and plans herself from your site. Add anything she should leave to the team: custom quotes, contracts, refunds, complaints, jobs.' : 'Prices, payments, financing, trade values and discounts are already on the list. Add anything else: warranty claims, complaints, employment.'}</Hint>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {(business ? ['Asked for a person'] : ['Prices & payments', 'Financing terms', 'Trade-in values', 'Discounts & offers']).map(t => <Pill key={t} text={t} colors={colors} testId={`widget-never-builtin-${t.split(' ')[0].toLowerCase()}`} />)}
          {(kb.never || []).map((n: string, i: number) => <Pill key={n + i} text={n} onRemove={() => setKb({ never: kb.never.filter((_: string, j: number) => j !== i) })} colors={colors} testId={`widget-never-${i}`} />)}
        </View>
        <AddRow placeholder="Topic Jessi must not answer" onAdd={t => setKb({ never: [...(kb.never || []), t] })} colors={colors} testId="widget-never" />
      </Section>

      <Section colors={colors} testId="widget-section-notes">
        <Field label="Anything else Jessi should know" hint="Free text: departments, what makes you different, directions, amenities. Up to 2000 characters." value={kb.notes || ''} onChange={v => setKb({ notes: v })} multiline colors={colors} testId="widget-kb-notes" maxLength={2000} top={false} />
      </Section>

      <Section colors={colors} testId="widget-section-recent-chats">
        <Label colors={colors}>Recent chats</Label>
        <Hint colors={colors}>What visitors asked Jessi on your site. Handed-off chats land in the Inbox as leads.</Hint>
        {recentChats.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('widget-recent-chats-empty')}>No chats yet. Once the code is on your site, every conversation shows up here.</Text> : null}
        {recentChats.map(c => {
          const s = c.live ? { label: c.mode === 'human' ? `${c.agent || 'A rep'} is chatting` : 'Live now · Jessi answering', color: '#34C759' } : CHAT_STATUS[c.status] || { label: c.status, color: colors.textSecondary };
          return (
            <TouchableOpacity key={c.id} onPress={() => router.push(`/webchat/${c.id}` as any)} style={{ paddingVertical: 8, borderTopWidth: 0.5, borderTopColor: colors.border, gap: 2 }} {...tid(`widget-recent-chat-${c.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>{c.name}{c.booked ? ' · booked' : ''} <Text style={{ fontWeight: '400', color: colors.textSecondary }}>· {c.turns} {c.turns === 1 ? 'question' : 'questions'}{c.host ? ` · ${c.host}` : ''}</Text></Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{timeAgo(c.at)}</Text>
                <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
              </View>
              {c.last ? <Text style={{ fontSize: 13, color: colors.textSecondary }} numberOfLines={2}>"{c.last}"</Text> : null}
              <Text style={{ fontSize: 12, fontWeight: '700', color: s.color }}>{s.label}{c.reason && !c.live ? ` · ${c.reason}` : ''}</Text>
            </TouchableOpacity>
          );
        })}
      </Section>
    </>
  );
};
