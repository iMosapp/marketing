import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Sheet, Field, GoldButton, GOLD, RED, tid } from '../shared';
import { type Campaign } from './shared';

type Props = { campaign: Campaign | null; visible: boolean; onClose: () => void; colors: any; onArmed: (c: Campaign) => void };

// The one gate before anything reaches the store: a named admin confirms they are authorized to test it.
export const ArmSheet = ({ campaign, visible, onClose, colors, onArmed }: Props) => {
  const { showToast } = useToast();
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { if (visible) { setUrl(''); setNote(''); setConfirm(false); setErr(''); } }, [visible]);
  if (!campaign) return null;
  const n = campaign.counts.draft;
  const go = async () => {
    setBusy(true); setErr('');
    try { const r = await api.post(`/journeys/${campaign.id}/arm`, { confirm, website_url: url.trim(), note: note.trim() }); showToast(campaign.method === 'adf' ? `${n} lead${n === 1 ? '' : 's'} sent to the CRM` : `${n} identit${n === 1 ? 'y' : 'ies'} armed, submit their forms`, 'success'); onClose(); onArmed(r.data); }
    catch (e: any) { setErr(e?.response?.data?.detail || 'Could not arm the campaign'); }
    finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="Arm the campaign" colors={colors} testID="arm-sheet" error={err}
      footer={<GoldButton label={campaign.method === 'adf' ? `Send ${n} lead${n === 1 ? '' : 's'} to the CRM` : `Reserve ${n} number${n === 1 ? '' : 's'} and arm`} onPress={go} busy={busy} disabled={!confirm || !n} icon="shield-checkmark" testID="arm-submit" />}>
      <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }} {...tid('arm-what')}>{n} identit{n === 1 ? 'y' : 'ies'} each get a shopper number from the pool. {campaign.method === 'adf' ? `The leads go to the CRM intake address right away and every clock starts.` : `You then type each identity into ${campaign.store_name}'s website form and tap "I submitted the form" on it to start its clock.`} From that moment every call, text and email the store sends is timed and graded for {campaign.window_label}.</Text>
      <Field label="STORE WEBSITE OR FORM URL (OPTIONAL)" value={url} onChange={setUrl} colors={colors} placeholder="https://www.store.com/contact" autoCapitalize="none" testID="arm-url" />
      <Field label="AUTHORIZATION NOTE" value={note} onChange={setNote} colors={colors} multiline placeholder="Approved by the GM on the kickoff call, May 3" testID="arm-note" />
      <TouchableOpacity onPress={() => setConfirm(v => !v)} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: confirm ? GOLD : colors.border, padding: 12 }} {...tid('arm-confirm')}>
        <Ionicons name={confirm ? 'checkbox' : 'square-outline'} size={22} color={confirm ? GOLD : colors.textSecondary} />
        <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }}>I confirm {campaign.store_name} has authorized this mystery shop and I am allowed to submit inquiries on its website and contact its staff. The record keeps my name and the time.</Text>
      </TouchableOpacity>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}><Ionicons name="hand-left" size={16} color={RED} style={{ marginTop: 1 }} /><Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>An emergency stop on the campaign screen closes every identity at once and returns the numbers to the pool.</Text></View>
    </Sheet>
  );
};
