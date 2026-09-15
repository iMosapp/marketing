import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Label, GOLD, tid } from './shared';

type Card = { name: string; org: string; phone_number: string; url: string; vcf_url: string };

// What reps see when they save the shop number ("Mystery Shop" today, "Practice Call" tomorrow), plus the paste-anywhere link.
export const ContactCardSettings = ({ colors }: { colors: any }) => {
  const { showToast } = useToast();
  const [card, setCard] = useState<Card | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get('/shop-clients/number/contact-card').then(r => { setCard(r.data); setName(r.data.name); }).catch(() => {}); }, []);
  if (!card) return null;
  const save = async () => {
    setBusy(true);
    try { const r = await api.put('/shop-clients/number/contact-card', { name: name.trim(), org: card.org }); setCard(r.data); setName(r.data.name); showToast(`Reps will save it as "${r.data.name}"`, 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };
  const copy = async () => { await Clipboard.setStringAsync(card.url); showToast('Contact link copied', 'success'); };
  const dirty = name.trim() && name.trim() !== card.name;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid('contact-card-settings')}>
      <Label t="HOW IT SAVES IN A REP'S PHONE" colors={colors} />
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        <TextInput value={name} onChangeText={setName} placeholder="Mystery Shop" placeholderTextColor={colors.textSecondary} maxLength={40}
          style={{ flex: 1, height: 40, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, color: colors.text, fontSize: 15, fontWeight: '700', backgroundColor: colors.background }} {...tid('contact-card-name')} />
        {!!dirty && <TouchableOpacity onPress={save} disabled={busy} style={{ height: 40, paddingHorizontal: 14, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('contact-card-name-save')}>{busy ? <ActivityIndicator color="#111" size="small" /> : <Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>Save</Text>}</TouchableOpacity>}
      </View>
      <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Company shows as {card.org}. Rename it any time (Practice Call, for example); every link below picks up the new name.</Text>
      <TouchableOpacity onPress={copy} style={{ height: 36, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('contact-card-platform-copy')}>
        <Ionicons name="link" size={14} color={colors.text} /><Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Copy the contact link for this number</Text>
      </TouchableOpacity>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Paste it into any text from your own phone. Each client also has its own link and a "Text everyone" button on its People tab.</Text>
    </View>
  );
};
