import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { showConfirm } from '../../services/alert';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GoldButton, Field, Chip, Label, GOLD, GREEN, RED, AMBER, BLUE, tid, fmtWhen } from '../../components/dialer/shared';

type Conn = { connected: boolean; id?: string; location_id?: string; location_name?: string; token_hint?: string; lead_source_id?: string | null; connected_by_name?: string; connected_at?: string | null; last_test_at?: string | null; ok?: boolean; error?: string | null; webhook_url?: string; last_sync?: string | null; pushed?: number; store_id?: string | null; lead_sources: { id: string; name: string; active: boolean }[] };

// One GoHighLevel sub-account per store, connected with a Private Integration Token. Feeds dialer imports, outcome sync and (via a GHL workflow webhook) speed to lead.
export default function GoHighLevel() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [conn, setConn] = useState<Conn | null>(null);
  const [locationId, setLocationId] = useState('');
  const [token, setToken] = useState('');
  const [source, setSource] = useState<string | null>(null);
  const [busy, setBusy] = useState<'save' | 'test' | null>(null);
  const [tags, setTags] = useState<string[] | null>(null);
  const [pipelines, setPipelines] = useState<any[] | null>(null);

  const load = useCallback(async () => {
    try { const r = await api.get('/ghl/connection'); setConn(r.data); setLocationId(r.data.location_id || ''); setSource(r.data.lead_source_id || null); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); setConn({ connected: false, lead_sources: [] }); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!conn?.connected) { setTags(null); setPipelines(null); return; }
    api.get('/ghl/tags').then(r => setTags(r.data.tags)).catch(() => setTags([]));
    api.get('/ghl/pipelines').then(r => setPipelines(r.data.pipelines)).catch(() => setPipelines([]));
  }, [conn?.connected, conn?.location_id]);

  const save = async () => {
    setBusy('save');
    try { const r = await api.put('/ghl/connection', { location_id: locationId.trim(), token: token.trim() || undefined, lead_source_id: source ?? '' }); setConn(c => ({ ...(c as Conn), ...r.data })); setToken(''); showToast(`Connected to ${r.data.location_name || 'GoHighLevel'}`, 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not connect', 'error'); }
    finally { setBusy(null); }
  };
  const test = async () => {
    setBusy('test');
    try { const r = await api.post('/ghl/connection/test'); showToast(r.data.ok ? `Token works: ${r.data.location?.name}` : r.data.error, r.data.ok ? 'success' : 'error'); load(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Test failed', 'error'); }
    finally { setBusy(null); }
  };
  const disconnect = () => showConfirm('Disconnect GoHighLevel?', 'Imports and outcome sync stop. Nothing is deleted on either side.', async () => {
    try { await api.delete('/ghl/connection'); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not disconnect', 'error'); }
  }, undefined, 'Disconnect');
  const copy = async (v: string) => { await Clipboard.setStringAsync(v); showToast('Copied', 'success'); };

  if (!conn) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="GoHighLevel" testID="ghl-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 10 } as const;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="GoHighLevel" subtitle={conn.connected ? `${conn.location_name || conn.location_id} · connected` : 'Connect your sub-account'} testID="ghl-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }}>
        <View style={{ ...card, flexDirection: 'row', alignItems: 'center', borderColor: conn.connected ? (conn.ok === false ? `${RED}66` : `${GREEN}66`) : colors.border }} {...tid('ghl-status')}>
          <Ionicons name={conn.connected ? (conn.ok === false ? 'alert-circle' : 'checkmark-circle') : 'link-outline'} size={22} color={conn.connected ? (conn.ok === false ? RED : GREEN) : colors.textSecondary} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{conn.connected ? (conn.ok === false ? 'Connected, but the token is failing' : `Connected to ${conn.location_name || 'your location'}`) : 'Not connected'}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{conn.connected ? `Token ${conn.token_hint} · by ${conn.connected_by_name || 'a manager'} ${fmtWhen(conn.connected_at)}${conn.pushed ? ` · ${conn.pushed} outcomes pushed` : ''}${conn.error ? ` · ${conn.error}` : ''}` : 'Dialer imports by tag, call outcomes as notes + tags + pipeline opportunities, and GHL workflow webhooks into your lead sources.'}</Text>
          </View>
        </View>

        <View style={card} {...tid('ghl-connect-card')}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{conn.connected ? 'Update the connection' : 'Connect'}</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }}>In GoHighLevel: Settings → Business Profile copies the <Text style={{ fontWeight: '800', color: colors.text }}>Location ID</Text>. Settings → Private Integrations → Create: scopes contacts (read + write), locations (read), opportunities (read + write), locations/tags (read). Paste the token once; we only show its last 4 digits after that.</Text>
          <Field label="LOCATION ID" value={locationId} onChange={setLocationId} colors={colors} placeholder="ve9EPM428h8vShlRW1KT" testID="ghl-location-id" autoCapitalize="none" />
          <Field label={conn.connected ? `PRIVATE INTEGRATION TOKEN (LEAVE EMPTY TO KEEP ${conn.token_hint})` : 'PRIVATE INTEGRATION TOKEN'} value={token} onChange={setToken} colors={colors} placeholder="pit-…" testID="ghl-token" autoCapitalize="none" />
          <View style={{ gap: 6 }}>
            <Label t="NEW GHL CONTACTS LAND IN THIS LEAD SOURCE (SPEED TO LEAD)" colors={colors} />
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              <Chip label="None" small active={!source} onPress={() => setSource(null)} colors={colors} testID="ghl-source-none" />
              {conn.lead_sources.map(s => <Chip key={s.id} label={s.name} small active={source === s.id} onPress={() => setSource(s.id)} colors={colors} testID={`ghl-source-${s.id}`} />)}
            </View>
            {conn.lead_sources.length === 0 && <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>No lead sources on this store yet (Tools → Lead Source Config).</Text>}
          </View>
          <GoldButton label={conn.connected ? 'Save' : 'Connect'} onPress={save} busy={busy === 'save'} disabled={!locationId.trim() || (!conn.connected && !token.trim())} testID="ghl-save" icon="link" />
          {conn.connected && (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1 }}><GoldButton label="Test token" onPress={test} outline busy={busy === 'test'} testID="ghl-test" icon="pulse" /></View>
              <View style={{ flex: 1 }}><GoldButton label="Disconnect" onPress={disconnect} outline color={RED} testID="ghl-disconnect" icon="unlink" /></View>
            </View>
          )}
        </View>

        {conn.connected && (
          <>
            <View style={card} {...tid('ghl-webhook-card')}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Send new GHL leads to the team</Text>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }}>In a GoHighLevel workflow add the action <Text style={{ fontWeight: '800', color: colors.text }}>Webhook</Text> (POST) with this URL. The contact runs through the lead source picked above: first text, call ladder, Jessi, everything.</Text>
              <TouchableOpacity onPress={() => copy(conn.webhook_url || '')} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.bg, borderRadius: 10, padding: 10, borderWidth: 1, borderColor: colors.border }} {...tid('ghl-webhook-copy')}>
                <Text style={{ flex: 1, fontSize: 11.5, color: colors.text }} numberOfLines={2}>{conn.webhook_url}</Text><Ionicons name="copy-outline" size={16} color={GOLD} />
              </TouchableOpacity>
              {!source && <Text style={{ fontSize: 12, color: AMBER }} {...tid('ghl-webhook-warning')}>Pick a lead source above first or the webhook answers with an error.</Text>}
            </View>
            <View style={card} {...tid('ghl-data-card')}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>What we see in your location</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>TAGS · {tags === null ? 'loading…' : `${tags.length}`}</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{(tags || []).slice(0, 30).map(t => <View key={t} style={{ backgroundColor: `${BLUE}18`, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 }}><Text style={{ fontSize: 11.5, color: BLUE, fontWeight: '700' }}>{t}</Text></View>)}</View>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 4 }}>PIPELINES · {pipelines === null ? 'loading…' : `${pipelines.length}`}</Text>
              {(pipelines || []).map(p => <Text key={p.id} style={{ fontSize: 12.5, color: colors.text }}>{p.name} <Text style={{ color: colors.textSecondary }}>· {p.stages.map((s: any) => s.name).join(' → ')}</Text></Text>)}
              <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }}>Pick a pipeline + stage on a dialer campaign (Settings → GoHighLevel) to open an opportunity when a lead is marked Interested or Call back.</Text>
            </View>
            <GoldButton label="Open the Power Dialer" onPress={() => router.push('/dialer' as any)} outline testID="ghl-open-dialer" icon="call" />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
