import React, { useEffect, useRef, useState } from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { EmailPreview } from './EmailPreview';
import { Sheet, Field, Label, GoldButton, GOLD, tid, type Proposal } from './shared';

type Preview = { subject: string; html: string; to: string; from: string; reply_to: string; default_note: string };
type Props = { proposal: Proposal | null; colors: any; onClose: () => void; onSent: () => void };

// "Email it" opens this: pick the To address, write a personal note, watch the real email update, then send.
export const SendProposalSheet = ({ proposal, colors, onClose, onSent }: Props) => {
  const { showToast } = useToast();
  const [to, setTo] = useState('');
  const [note, setNote] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const timer = useRef<any>(null);

  const fetchPreview = async (pid: string, n?: string) => {
    const r = await api.get(`/shop-clients/proposals/${pid}/email-preview`, { params: n === undefined ? {} : { note: n } });
    return r.data as Preview;
  };

  useEffect(() => {
    if (!proposal) return;
    setPreview(null); setNote(''); setTo(proposal.contact_email || '');
    fetchPreview(proposal.id).then(p => { setPreview(p); setNote(p.default_note || ''); setTo(p.to || proposal.contact_email || ''); }).catch(() => showToast('Could not load the preview', 'error'));
  }, [proposal?.id]);

  const onNote = (v: string) => {
    setNote(v);
    if (!proposal) return;
    if (timer.current) clearTimeout(timer.current);
    setRefreshing(true);
    timer.current = setTimeout(async () => {
      try { const p = await fetchPreview(proposal.id, v); setPreview(p); } catch {} finally { setRefreshing(false); }
    }, 600);
  };

  const send = async () => {
    if (!proposal) return;
    setBusy(true);
    try { const r = await api.post(`/shop-clients/proposals/${proposal.id}/send`, { note, to: to.trim() }); showToast(`Emailed to ${r.data.to}`, 'success'); onSent(); onClose(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not send', 'error'); }
    finally { setBusy(false); }
  };

  const validTo = /.+@.+\..+/.test(to.trim());
  return (
    <Sheet visible={!!proposal} onClose={onClose} title="Send the proposal" colors={colors} testID="send-sheet"
      footer={<GoldButton label={validTo ? `Send to ${to.trim()}` : 'Enter an email address'} onPress={send} busy={busy} disabled={!validTo || !preview} testID="send-submit" icon="mail" />}>
      <Field label="TO" value={to} onChange={setTo} colors={colors} placeholder="gm@dealer.com" keyboardType="email-address" autoCapitalize="none" testID="send-to" />
      <Field label="PERSONAL NOTE (LANDS RIGHT UNDER THE GREETING, OPTIONAL)" value={note} onChange={onNote} colors={colors} multiline placeholder={'Great meeting you this morning. Here is everything we talked about, in writing.'} testID="send-note" />
      <View style={{ gap: 6 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Label t="EXACTLY WHAT THEY RECEIVE" colors={colors} />
          {refreshing && <ActivityIndicator size="small" color={GOLD} />}
        </View>
        {preview ? (
          <>
            <Text style={{ fontSize: 13, color: colors.text }} {...tid('send-subject')}><Text style={{ fontWeight: '800' }}>Subject:</Text> {preview.subject}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('send-from')}>From {preview.from} · replies go to {preview.reply_to}</Text>
            <EmailPreview html={preview.html} colors={colors} />
          </>
        ) : <ActivityIndicator color={GOLD} style={{ marginVertical: 30 }} />}
      </View>
      <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Your note is remembered as the starting point for the next proposal you send.</Text>
    </Sheet>
  );
};
