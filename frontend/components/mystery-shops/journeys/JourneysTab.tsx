import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../../services/api';
import { Label, scoreColor, fmtWhen, GOLD, RED, tid, afterModal, type Client } from '../shared';
import { CAMPAIGN_STATUS, isRunning, modesText, type Campaign, type JourneyOptions } from './shared';
import { NewCampaignSheet } from './NewCampaignSheet';

type Props = { client: Client; colors: any };

const Row = ({ c, colors, onPress }: { c: Campaign; colors: any; onPress: () => void }) => {
  const st = CAMPAIGN_STATUS[c.status];
  const n = c.counts;
  return (
    <TouchableOpacity onPress={onPress} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }} {...tid(`journey-${c.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{c.name}</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={1}>{c.department} · {c.window_label} · {c.method === 'adf' ? 'ADF to CRM' : 'web form'}{c.scenario?.offering ? ` · ${c.scenario.offering}` : ''}</Text>
        </View>
        {c.avg_score != null ? <Text style={{ fontSize: 20, fontWeight: '800', color: scoreColor(c.avg_score) }} {...tid(`journey-score-${c.id}`)}>{c.avg_score}%</Text> : null}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, height: 24, borderRadius: 12, backgroundColor: st.color + '22' }} {...tid(`journey-status-${c.id}`)}><Ionicons name={st.icon} size={12} color={st.color} /><Text style={{ fontSize: 11, fontWeight: '800', color: st.color }}>{st.label}</Text></View>
      </View>
      <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid(`journey-counts-${c.id}`)}>{n.total} identit{n.total === 1 ? 'y' : 'ies'}{n.draft ? ` · ${n.draft} draft` : ''}{n.open ? ` · ${n.open} in play` : ''}{n.completed ? ` · ${n.completed} graded` : ''} · {modesText(c.modes)}</Text>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{c.status === 'draft' ? `created ${fmtWhen(c.created_at)}` : c.armed_at ? `armed ${fmtWhen(c.armed_at)}` : ''}{c.closed_at ? ` · closed ${fmtWhen(c.closed_at)}` : c.stopped_at ? ` · stopped ${fmtWhen(c.stopped_at)}` : ''}</Text>
    </TouchableOpacity>
  );
};

// One campaign = up to 10 virtual customers landing at the store as internet leads, every follow-up timed and graded across call, text and email.
export const JourneysTab = ({ client, colors }: Props) => {
  const router = useRouter();
  const [rows, setRows] = useState<Campaign[] | null>(null);
  const [opts, setOpts] = useState<JourneyOptions | null>(null);
  const [creating, setCreating] = useState(false);
  const load = useCallback(async () => {
    try { const [a, b] = await Promise.all([api.get('/journeys', { params: { client_id: client.id } }), api.get('/journeys/options')]); setRows(a.data.campaigns); setOpts(b.data); }
    catch { setRows([]); }
  }, [client.id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!(rows || []).some(isRunning)) return; const t = setInterval(load, 30000); return () => clearInterval(t); }, [rows, load]);
  const open = (id: string) => router.push(`/admin/journeys/${id}` as any);
  const running = (rows || []).filter(c => c.status === 'draft' || isRunning(c));
  const done = (rows || []).filter(c => c.status === 'closed' || c.status === 'stopped');
  return (
    <View style={{ gap: 16 }}>
      <TouchableOpacity onPress={() => setCreating(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: GOLD + '1A', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('journey-new')}>
        <Ionicons name="people" size={20} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>New journey campaign</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Up to 10 virtual customers, each with a real cell, email, timeline and questions. You review every identity before anything reaches the store, then every call, text and email they get is timed and graded for up to 30 days.</Text></View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {opts && !opts.email_ready && <Text style={{ fontSize: 12.5, color: RED, lineHeight: 17 }} {...tid('journey-not-ready')}>Email receiving is not set up on the server yet (INBOUND_EMAIL_DOMAIN), so identities cannot have an email address. Campaigns are off until it is.</Text>}
      {rows === null ? <ActivityIndicator color={GOLD} /> : rows.length === 0 ? <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20 }} {...tid('journey-empty')}>No campaigns yet. Build one and watch how the store treats ten different customers.</Text> : (
        <>
          {running.length > 0 && <View style={{ gap: 8 }}><Label t={`IN PROGRESS · ${running.length}`} colors={colors} />{running.map(c => <Row key={c.id} c={c} colors={colors} onPress={() => open(c.id)} />)}</View>}
          {done.length > 0 && <View style={{ gap: 8 }}><Label t={`FINISHED · ${done.length}`} colors={colors} />{done.map(c => <Row key={c.id} c={c} colors={colors} onPress={() => open(c.id)} />)}</View>}
        </>
      )}
      {!!opts?.pool && <Text style={{ fontSize: 11.5, color: colors.textSecondary, textAlign: 'center' }} {...tid('journey-pool-line')}>Shopper numbers: {opts.pool.in_use} in use · {opts.pool.available} ready · {opts.pool.total} of {opts.pool.cap} owned</Text>}
      <NewCampaignSheet visible={creating} onClose={() => setCreating(false)} colors={colors} client={client} opts={opts} onCreated={(c) => { load(); afterModal(() => open(c.id)); }} />
    </View>
  );
};
