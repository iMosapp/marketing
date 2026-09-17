import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { Label, GoldButton, scoreColor, fmtWhen, GOLD, RED, tid, type Client } from '../shared';
import { CHANNELS, LEAD_STATUS, isOpen, untilText, minsText, firstMinutes, channelTone, processText, type LeadSetup, type LeadShop } from './shared';
import { LeadSetupSheet } from './LeadSetupSheet';
import { NewLeadShopSheet } from './NewLeadShopSheet';
import { LeadShopDetailSheet } from './LeadShopDetailSheet';

type Props = { client: Client; colors: any };

const Row = ({ s, colors, onPress }: { s: LeadShop; colors: any; onPress: () => void }) => {
  const st = LEAD_STATUS[s.status];
  return (
    <TouchableOpacity onPress={onPress} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }} {...tid(`lead-shop-${s.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{s.persona.name} <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· {s.source_name} · {s.department}</Text></Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={1}>{s.persona.offering ? `Asking about ${s.persona.offering}` : s.script_title}</Text>
        </View>
        {s.status === 'completed' && s.score ? <Text style={{ fontSize: 20, fontWeight: '800', color: scoreColor(s.score.overall) }} {...tid(`lead-shop-score-${s.id}`)}>{s.score.overall}%</Text> : (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, height: 24, borderRadius: 12, backgroundColor: st.color + '22' }} {...tid(`lead-shop-status-${s.id}`)}><Ionicons name={st.icon} size={12} color={st.color} /><Text style={{ fontSize: 11, fontWeight: '800', color: st.color }}>{st.label}{s.status === 'live' ? ` · ${untilText(s.expires_at)}` : ''}</Text></View>
        )}
      </View>
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        {CHANNELS.filter(c => s.process.channels.includes(c.key)).map(c => { const m = firstMinutes(s, c.key); const tone = channelTone(s, c.key); return (
          <View key={c.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, height: 22, borderRadius: 11, backgroundColor: tone + '1E' }} {...tid(`lead-shop-${s.id}-${c.key}`)}>
            <Ionicons name={c.icon} size={11} color={tone} /><Text style={{ fontSize: 11, fontWeight: '800', color: tone }}>{m == null ? (s.status === 'completed' ? 'never' : 'waiting') : minsText(m)}</Text>
          </View>
        ); })}
        <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginLeft: 'auto' }}>{s.status === 'pending_delivery' ? 'form not submitted yet' : s.started_at ? `landed ${fmtWhen(s.started_at)}` : ''}</Text>
      </View>
    </TouchableOpacity>
  );
};

// Covert shops: the store gets a brand new internet lead, the AI persona is fully reachable, and the store's whole response is graded.
export const LeadShopsTab = ({ client, colors }: Props) => {
  const [setup, setSetup] = useState<LeadSetup | null>(null);
  const [shops, setShops] = useState<LeadShop[] | null>(null);
  const [editSetup, setEditSetup] = useState(false);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { const [a, b] = await Promise.all([api.get(`/lead-shops/setup/${client.id}`), api.get('/lead-shops', { params: { client_id: client.id } })]); setSetup(a.data); setShops(b.data.shops); }
    catch { setShops([]); }
  }, [client.id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!(shops || []).some(isOpen)) return; const t = setInterval(load, 30000); return () => clearInterval(t); }, [shops, load]);

  const live = (shops || []).filter(isOpen);
  const done = (shops || []).filter(s => s.status === 'completed');
  const ready = !!setup?.email_ready;
  return (
    <View style={{ gap: 16 }}>
      <TouchableOpacity onPress={() => setCreating(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: GOLD + '1A', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('lead-new')}>
        <Ionicons name="paper-plane" size={20} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Send a lead</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>A brand new internet lead lands at the store with a real cell and email. Nobody there knows it is a shop. Every call, text and email they send is answered in persona and timed.</Text></View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {setup && !ready && <Text style={{ fontSize: 12.5, color: RED, lineHeight: 17 }} {...tid('lead-not-ready')}>Email receiving is not set up on the server yet (INBOUND_EMAIL_DOMAIN), so the shopper cannot have an email address. Lead shops are off until it is.</Text>}
      <TouchableOpacity onPress={() => setEditSetup(true)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: setup?.lead_email ? colors.border : RED + '66', padding: 12, gap: 6 }} {...tid('lead-setup-card')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Ionicons name="settings-outline" size={18} color={GOLD} />
          <Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: colors.text }}>Lead shop setup</Text>
          <Ionicons name="create-outline" size={18} color={colors.textSecondary} />
        </View>
        {setup ? (
          <>
            <Text style={{ fontSize: 12.5, color: setup.lead_email ? colors.textSecondary : RED }} {...tid('lead-setup-email-line')}>{setup.lead_email ? `CRM leads go to ${setup.lead_email}` : "No CRM lead email yet: add it, or use the web form option"}</Text>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('lead-setup-process-line')}>Promised: {processText(setup.lead_process)}</Text>
          </>
        ) : <ActivityIndicator color={GOLD} />}
      </TouchableOpacity>
      {shops === null ? <ActivityIndicator color={GOLD} /> : shops.length === 0 ? <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20 }} {...tid('lead-empty')}>No lead shops yet. Send one and watch what the store does with it.</Text> : (
        <>
          {live.length > 0 && <View style={{ gap: 8 }}><Label t={`RUNNING · ${live.length}`} colors={colors} />{live.map(s => <Row key={s.id} s={s} colors={colors} onPress={() => setOpen(s.id)} />)}</View>}
          {done.length > 0 && <View style={{ gap: 8 }}><Label t={`COMPLETED · ${done.length}`} colors={colors} />{done.map(s => <Row key={s.id} s={s} colors={colors} onPress={() => setOpen(s.id)} />)}</View>}
        </>
      )}
      {!!setup?.pool && <Text style={{ fontSize: 11.5, color: colors.textSecondary, textAlign: 'center' }} {...tid('lead-pool-line')}>Shopper numbers: {setup.pool.in_use} in use · {setup.pool.available} ready · {setup.pool.total} of {setup.pool.cap} owned</Text>}
      <LeadSetupSheet visible={editSetup} onClose={() => setEditSetup(false)} colors={colors} clientId={client.id} setup={setup} onSaved={setSetup} />
      <NewLeadShopSheet visible={creating} onClose={() => setCreating(false)} colors={colors} client={client} setup={setup} onCreated={(s) => { load(); setTimeout(() => setOpen(s.id), 450); }} />
      <LeadShopDetailSheet id={open} onClose={() => setOpen(null)} colors={colors} onChanged={load} />
    </View>
  );
};
