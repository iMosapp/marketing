import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useToast } from '../common/Toast';
import { openUrl } from './ReportView';
import { Sheet, Field, Label, GoldButton, money, fmtWhen, GOLD, RED, GREEN, BLUE, PURPLE, tid, type Client, type Proposal } from './shared';

const PSTATUS: Record<string, { label: string; color: string }> = { draft: { label: 'Draft', color: '#8E8E93' }, sent: { label: 'Sent', color: BLUE }, viewed: { label: 'Opened', color: PURPLE }, signed: { label: 'Signed · invoice sent', color: GOLD }, paid: { label: 'Paid', color: GREEN } };

// Proposal (e-signed on a public page) -> Stripe invoice emailed by Stripe -> paid status.
export const BillingTab = ({ client, colors, onChanged }: { client: Client; colors: any; onChanged: () => void }) => {
  const { showToast } = useToast();
  const [rows, setRows] = useState<Proposal[] | null>(null);
  const [sheet, setSheet] = useState(false);
  const [f, setF] = useState({ sales: String(client.plan.sales_per_month || 20), service: String(client.plan.service_per_month || 20), price: String(client.plan.price_monthly || 400), term: '3', notes: '', contact_name: client.contact_name, contact_email: client.contact_email });
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState<string | null>(null);

  const load = async () => { try { const r = await api.get(`/shop-clients/${client.id}/proposals`); setRows(r.data.proposals); } catch { setRows([]); } };
  useEffect(() => { load(); }, [client.id]);

  const create = async () => {
    setBusy(true);
    try {
      await api.post(`/shop-clients/${client.id}/proposals`, { sales_per_month: Number(f.sales) || 0, service_per_month: Number(f.service) || 0, price_monthly: Number(f.price) || 0, term_months: Number(f.term) || 3, notes: f.notes, contact_name: f.contact_name, contact_email: f.contact_email });
      setSheet(false); load(); onChanged(); showToast('Proposal ready. Send it or copy the link.', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not create', 'error'); }
    finally { setBusy(false); }
  };
  const send = async (p: Proposal) => {
    setSending(p.id);
    try { await api.post(`/shop-clients/proposals/${p.id}/send`); showToast(`Emailed to ${p.contact_email}`, 'success'); load(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not send', 'error'); }
    finally { setSending(null); }
  };
  const copy = async (url?: string) => { if (!url) return; await Clipboard.setStringAsync(url); showToast('Link copied', 'success'); };
  const remove = (p: Proposal) => showConfirm('Delete this proposal?', 'The link stops working.', async () => { try { await api.delete(`/shop-clients/proposals/${p.id}`); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not delete', 'error'); } }, undefined, 'Delete');

  return (
    <View style={{ gap: 16 }}>
      <TouchableOpacity onPress={() => setSheet(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: GOLD + '1A', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('proposal-new')}>
        <Ionicons name="document-text" size={20} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>New proposal</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>They sign on a web page, Stripe emails the first invoice automatically.</Text></View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {client.billing?.status && <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Billing status: <Text style={{ fontWeight: '800', color: client.billing.status === 'paid' ? GREEN : GOLD }}>{client.billing.status}</Text></Text>}
      {rows === null ? <ActivityIndicator color={GOLD} /> : rows.length === 0 ? <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', paddingVertical: 16 }} {...tid('proposals-empty')}>No proposals yet.</Text> : rows.map(p => {
        const st = PSTATUS[p.status] || PSTATUS.draft;
        return (
          <View key={p.id} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }} {...tid(`proposal-${p.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{money(p.terms.price_monthly)}/mo · {p.terms.sales_per_month} sales + {p.terms.service_per_month} service</Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{p.terms.term_months} month term · to {p.contact_name || p.contact_email || 'no contact'}{p.sent_at ? ` · sent ${fmtWhen(p.sent_at)}` : ''}{p.viewed_at ? ` · opened ${fmtWhen(p.viewed_at)}` : ''}</Text>
              </View>
              <View style={{ paddingHorizontal: 8, height: 24, borderRadius: 12, backgroundColor: st.color + '22', justifyContent: 'center' }} {...tid(`proposal-status-${p.id}`)}><Text style={{ fontSize: 11, fontWeight: '800', color: st.color }}>{st.label}</Text></View>
            </View>
            {p.signer?.name && <Text style={{ fontSize: 12.5, color: colors.text }}>Signed by {p.signer.name}{p.signer.title ? `, ${p.signer.title}` : ''} · {fmtWhen(p.signed_at)}</Text>}
            {p.invoice?.hosted_invoice_url && <TouchableOpacity onPress={() => openUrl(p.invoice!.hosted_invoice_url!)} {...tid(`proposal-invoice-${p.id}`)}><Text style={{ fontSize: 12.5, fontWeight: '800', color: p.invoice.status === 'paid' ? GREEN : GOLD }}>Stripe invoice {money(p.invoice.amount)} · {p.invoice.status}{p.invoice.paid_at ? ` ${fmtWhen(p.invoice.paid_at)}` : ''} · open</Text></TouchableOpacity>}
            {p.invoice?.error && <Text style={{ fontSize: 12.5, color: RED }}>Invoice failed: {p.invoice.error}</Text>}
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {!['signed', 'paid'].includes(p.status) && <TouchableOpacity onPress={() => send(p)} disabled={sending === p.id} style={{ flex: 1, height: 38, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`proposal-send-${p.id}`)}><Ionicons name="mail" size={14} color="#111" /><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>{sending === p.id ? 'Sending…' : p.sent_at ? 'Send again' : 'Email it'}</Text></TouchableOpacity>}
              <TouchableOpacity onPress={() => copy(p.url)} style={{ flex: 1, height: 38, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`proposal-copy-${p.id}`)}><Ionicons name="link" size={14} color={colors.text} /><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Copy link</Text></TouchableOpacity>
              <TouchableOpacity onPress={() => openUrl(p.url || '')} style={{ width: 38, height: 38, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`proposal-open-${p.id}`)}><Ionicons name="open-outline" size={16} color={colors.text} /></TouchableOpacity>
              {!['signed', 'paid'].includes(p.status) && <TouchableOpacity onPress={() => remove(p)} style={{ width: 38, height: 38, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`proposal-delete-${p.id}`)}><Ionicons name="trash-outline" size={16} color={RED} /></TouchableOpacity>}
            </View>
          </View>
        );
      })}

      <Sheet visible={sheet} onClose={() => setSheet(false)} title="Proposal terms" colors={colors} testID="proposal-sheet" footer={<GoldButton label="Create proposal" onPress={create} busy={busy} disabled={!(Number(f.price) > 0)} testID="proposal-create" />}>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1 }}><Field label="SALES / MO" value={f.sales} onChange={(v: string) => setF({ ...f, sales: v.replace(/\D/g, '') })} colors={colors} keyboardType="number-pad" testID="proposal-sales" /></View>
          <View style={{ flex: 1 }}><Field label="SERVICE / MO" value={f.service} onChange={(v: string) => setF({ ...f, service: v.replace(/\D/g, '') })} colors={colors} keyboardType="number-pad" testID="proposal-service" /></View>
          <View style={{ flex: 1 }}><Field label="$ / MONTH" value={f.price} onChange={(v: string) => setF({ ...f, price: v.replace(/[^\d.]/g, '') })} colors={colors} keyboardType="decimal-pad" testID="proposal-price" /></View>
          <View style={{ flex: 1 }}><Field label="TERM (MO)" value={f.term} onChange={(v: string) => setF({ ...f, term: v.replace(/\D/g, '') })} colors={colors} keyboardType="number-pad" testID="proposal-term" /></View>
        </View>
        <Field label="SIGNER NAME" value={f.contact_name} onChange={(v: string) => setF({ ...f, contact_name: v })} colors={colors} placeholder="Pat Manager" testID="proposal-contact-name" />
        <Field label="SIGNER EMAIL (GETS THE PROPOSAL + INVOICE)" value={f.contact_email} onChange={(v: string) => setF({ ...f, contact_email: v })} colors={colors} placeholder="gm@dealer.com" keyboardType="email-address" autoCapitalize="none" testID="proposal-contact-email" />
        <Field label="EXTRA NOTES ON THE PROPOSAL (OPTIONAL)" value={f.notes} onChange={(v: string) => setF({ ...f, notes: v })} colors={colors} multiline placeholder="Kickoff call included. First report on the 1st." testID="proposal-notes" />
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Creating the proposal also sets this client's plan to these numbers. When they sign, Stripe emails a {money(Number(f.price) || 0)} invoice due in 7 days.</Text>
      </Sheet>
    </View>
  );
};
