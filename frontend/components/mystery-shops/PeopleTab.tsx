import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { openUrl } from './ReportView';
import { Sheet, Field, Label, Chip, GoldButton, deptLabel, deptsOfClient, fmtPhone, fmtWhen, GOLD, GREEN, RED, tid, type Person, type Client } from './shared';
import { ClientNumberCard } from './ClientNumberCard';
import { ContactCardPanel } from './ContactCardPanel';

type Props = { client: Client; people: Person[]; colors: any; onChanged: () => void; onShopStarted: () => void; kickoffUrl?: string; kickoff?: { submitted_at?: string; submissions?: number } };

export const PeopleTab = ({ client, people, colors, onChanged, onShopStarted, kickoffUrl, kickoff }: Props) => {
  const { showToast } = useToast();
  const depts = deptsOfClient(client);
  const firstDept = depts[0]?.key || 'sales';
  const [sheet, setSheet] = useState<null | { person?: Person }>(null);
  const [f, setF] = useState({ name: '', phone: '', department: firstDept, title: '', notes: '' });
  const [busy, setBusy] = useState(false);
  const [calling, setCalling] = useState<string | null>(null);
  const [texting, setTexting] = useState<string | null>(null);
  const [sendingCard, setSendingCard] = useState<string | null>(null);
  const [cardKey, setCardKey] = useState(0);
  const copyKickoff = async () => { if (!kickoffUrl) return; await Clipboard.setStringAsync(kickoffUrl); showToast('Setup link copied', 'success'); };

  const open = (person?: Person) => { setF(person ? { name: person.name, phone: person.phone, department: person.department, title: person.title, notes: person.notes } : { name: '', phone: '', department: firstDept, title: '', notes: '' }); setSheet({ person }); };
  const save = async () => {
    setBusy(true);
    try {
      if (sheet?.person) await api.put(`/shop-clients/people/${sheet.person.id}`, f); else await api.post(`/shop-clients/${client.id}/people`, f);
      setSheet(null); onChanged(); showToast(sheet?.person ? 'Saved' : 'Added', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };
  const remove = (p: Person) => showConfirm(`Remove ${p.name}?`, 'Scheduled shops for them are canceled. Completed shops stay on the report.', async () => {
    try { await api.delete(`/shop-clients/people/${p.id}`); onChanged(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, 'Remove');
  const shopNow = (p: Person) => showConfirm(`Shop ${p.name.split(' ')[0]} right now?`, `The AI ${client.customer_noun || 'shopper'} calls ${fmtPhone(p.phone)} in a few seconds with a ${deptLabel(p.department, depts).toLowerCase()} challenge they have not had yet. Business hours don't apply; if they don't pick up or press 2, the shop waits for you to tap Try again.`, async () => {
    setCalling(p.id);
    try { await api.post(`/shop-clients/${client.id}/calls/shop-now`, { target_id: p.id }); showToast(`Calling ${p.name.split(' ')[0]} now`, 'success'); onShopStarted(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not place the call', 'error'); }
    finally { setCalling(null); }
  }, undefined, 'Call now');
  const textShop = (p: Person) => showConfirm(`Text shop ${p.name.split(' ')[0]} right now?`, `The AI ${client.customer_noun || 'shopper'} texts ${fmtPhone(p.phone)} from the shop number like a real lead and keeps the thread going as they reply. They have 4 hours to answer each text; the shop is graded on reply speed and quality when the shopper wraps up, or when you tap End & grade under Shops. No reply at all scores 0%.`, async () => {
    setTexting(p.id);
    try { await api.post(`/shop-clients/${client.id}/calls/shop-now`, { target_id: p.id, channel: 'text' }); showToast(`Texting ${p.name.split(' ')[0]} now`, 'success'); onShopStarted(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not send the text', 'error'); }
    finally { setTexting(null); }
  }, undefined, 'Text now');
  const sendCard = (p: Person) => showConfirm(`Text the contact card to ${p.name.split(' ')[0]}?`, `${fmtPhone(p.phone)} gets a text from the shop number with a link to save it as a contact${p.contact_card_ok ? ' (they already got one)' : ''}.`, async () => {
    setSendingCard(p.id);
    try { const r = await api.post(`/shop-clients/${client.id}/contact-card/send`, { target_ids: [p.id] }); showToast(r.data.sent ? `Contact card sent to ${p.name.split(' ')[0]}` : r.data.failed[0]?.error || 'Could not send', r.data.sent ? 'success' : 'error'); onChanged(); setCardKey(k => k + 1); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not send', 'error'); }
    finally { setSendingCard(null); }
  }, undefined, 'Send');

  const known = new Set(depts.map(d => d.key));
  const groups = [...depts, ...[...new Set(people.map(p => p.department).filter(k => !known.has(k)))].map(k => ({ key: k, label: deptLabel(k) }))].map(d => ({ ...d, rows: people.filter(p => p.department === d.key) }));
  return (
    <View style={{ gap: 16 }}>
      <TouchableOpacity onPress={() => open()} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: GOLD + '1A', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('people-add')}>
        <Ionicons name="person-add" size={20} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Add someone to shop</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Name, cell and department. Shops reach them by call or by text, always from the shop number.</Text></View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {people.length === 0 && <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20 }} {...tid('people-empty')}>Nobody to shop yet. Add the {depts.map(d => d.label.toLowerCase()).join(' and ')} people the {client.industry && client.industry !== 'automotive' ? 'account' : 'store'} wants evaluated.</Text>}
      {!!kickoffUrl && (
        <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }} {...tid('kickoff-card')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Ionicons name="clipboard-outline" size={18} color={GOLD} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Let the store fill this in</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('kickoff-status')}>{kickoff?.submitted_at ? `Filled in ${fmtWhen(kickoff.submitted_at)}${(kickoff.submissions || 0) > 1 ? ` · ${kickoff.submissions} times` : ''}` : 'No-login form: people, hours, vehicles. Saves straight into this client.'}</Text>
            </View>
          </View>
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }} numberOfLines={1} {...tid('kickoff-url')}>{kickoffUrl}</Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TouchableOpacity onPress={copyKickoff} style={{ flex: 1, height: 36, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('kickoff-copy')}><Ionicons name="link" size={14} color="#111" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Copy setup link</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => openUrl(kickoffUrl)} style={{ width: 36, height: 36, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('kickoff-open')}><Ionicons name="open-outline" size={16} color={colors.text} /></TouchableOpacity>
          </View>
        </View>
      )}
      {!client.demo && <ClientNumberCard client={client} colors={colors} onChanged={onChanged} />}
      {!client.demo && <ContactCardPanel client={client} colors={colors} refreshKey={cardKey} onSent={onChanged} />}
      {groups.filter(g => g.rows.length).map(g => (
        <View key={g.key} style={{ gap: 8 }}>
          <Label t={`${g.label.toUpperCase()} · ${g.rows.length}`} colors={colors} />
          {g.rows.map(p => (
            <View key={p.id} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }} {...tid(`person-${p.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontWeight: '800', color: GOLD }}>{p.name.split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase()}</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{p.name}</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{[p.title, fmtPhone(p.phone)].filter(Boolean).join(' · ')}{p.challenge_history?.length ? ` · ${p.challenge_history.length} challenge${p.challenge_history.length === 1 ? '' : 's'} used` : ''}</Text>
                </View>
                <TouchableOpacity onPress={() => sendCard(p)} disabled={sendingCard === p.id} hitSlop={8} {...tid(`person-send-card-${p.id}`)}><Ionicons name={p.contact_card_ok ? 'person-circle' : 'person-circle-outline'} size={21} color={p.contact_card_ok ? GREEN : p.contact_card_error ? RED : colors.textSecondary} /></TouchableOpacity>
                <TouchableOpacity onPress={() => open(p)} hitSlop={8} {...tid(`person-edit-${p.id}`)}><Ionicons name="create-outline" size={20} color={colors.textSecondary} /></TouchableOpacity>
                <TouchableOpacity onPress={() => remove(p)} hitSlop={8} {...tid(`person-remove-${p.id}`)}><Ionicons name="trash-outline" size={19} color={RED} /></TouchableOpacity>
              </View>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity onPress={() => shopNow(p)} disabled={calling === p.id} style={{ flex: 1.3, height: 38, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: calling === p.id ? 0.6 : 1 }} {...tid(`person-shop-now-${p.id}`)}>
                  <Ionicons name="call" size={15} color="#111" /><Text style={{ fontSize: 13.5, fontWeight: '800', color: '#111' }}>{calling === p.id ? 'Placing the call…' : 'Shop now'}</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => textShop(p)} disabled={texting === p.id} style={{ flex: 1, height: 38, borderRadius: 12, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: texting === p.id ? 0.6 : 1 }} {...tid(`person-text-shop-${p.id}`)}>
                  <Ionicons name="chatbubbles" size={15} color={GOLD} /><Text style={{ fontSize: 13.5, fontWeight: '800', color: GOLD }}>{texting === p.id ? 'Sending…' : 'Text shop'}</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      ))}

      <Sheet visible={!!sheet} onClose={() => setSheet(null)} title={sheet?.person ? 'Edit person' : 'Add someone to shop'} colors={colors} testID="person-sheet" footer={<GoldButton label={sheet?.person ? 'Save' : 'Add'} onPress={save} busy={busy} disabled={!f.name.trim() || f.phone.replace(/\D/g, '').length < 10} testID="person-save" />}>
        <Field label="NAME" value={f.name} onChange={(v: string) => setF({ ...f, name: v })} colors={colors} placeholder="Sam Seller" testID="person-name" />
        <Field label="CELL NUMBER (THIS IS THE PHONE WE CALL)" value={f.phone} onChange={(v: string) => setF({ ...f, phone: v })} colors={colors} placeholder="(801) 555-0100" keyboardType="phone-pad" testID="person-phone" />
        <View style={{ gap: 8 }}>
          <Label t="DEPARTMENT" colors={colors} />
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{depts.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => setF({ ...f, department: d.key })} colors={colors} testID={`person-dept-${d.key}`} />)}</View>
        </View>
        <Field label="TITLE (OPTIONAL)" value={f.title} onChange={(v: string) => setF({ ...f, title: v })} colors={colors} placeholder={(depts.find(d => d.key === f.department)?.rep || 'Sales consultant').replace(/^(a|an) /, '').replace(/^\w/, c => c.toUpperCase())} testID="person-title" />
        <Field label="NOTES" value={f.notes} onChange={(v: string) => setF({ ...f, notes: v })} colors={colors} multiline placeholder="New hire, started in May" testID="person-notes" />
      </Sheet>
    </View>
  );
};
