import React, { useCallback, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, TextInput, Switch, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import { showConfirm } from '../../services/alert';
import api from '../../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const MONO = Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' });

type Feed = {
  id: string; label: string; provider: string; provider_label: string; transport: 'url' | 'sftp'; enabled: boolean;
  feed_url?: string; sftp_host?: string; sftp_port?: number; sftp_username?: string; remote_path?: string; file_pattern?: string;
  mark_missing_sold: boolean; last_status?: string | null; last_error?: string | null; last_run_at?: string | null; last_success_at?: string | null;
  last_counts?: { units_seen: number; added: number; updated: number; marked_sold: number; skipped: number };
  last_file?: { name: string; modified?: string }; live_units: number; consecutive_failures?: number;
  runs: { id: string; status: string; started_at: string; units_seen: number; added: number; updated: number; marked_sold: number; error?: string | null; triggered_by: string }[];
};

const PROVIDERS = [
  { id: 'homenet', label: 'HomeNet' }, { id: 'vauto', label: 'vAuto' }, { id: 'dealer_com', label: 'Dealer.com' },
  { id: 'dealeron', label: 'DealerOn / DI' }, { id: 'sheet', label: 'Google Sheet' }, { id: 'other', label: 'Other' },
];

const EMPTY = { transport: 'url' as 'url' | 'sftp', provider: 'homenet', label: '', feed_url: '', sftp_host: '', sftp_port: '22', sftp_username: '', sftp_password: '', remote_path: '/', file_pattern: '*.csv', mark_missing_sold: true };

const ago = (iso?: string | null) => {
  if (!iso) return 'never';
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 60 ? 'just now' : s < 3600 ? `${Math.round(s / 60)}m ago` : s < 86400 ? `${Math.round(s / 3600)}h ago` : `${Math.round(s / 86400)}d ago`;
};

const Guide = ({ title, icon, color, steps, colors, id }: { title: string; icon: any; color: string; steps: string[]; colors: any; id: string }) => {
  const [open, setOpen] = useState(false);
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden' }}>
      <TouchableOpacity onPress={() => setOpen(o => !o)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16 }} {...tid(id)}>
        <View style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: `${color}22`, alignItems: 'center', justifyContent: 'center' }}><Ionicons name={icon} size={16} color={color} /></View>
        <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 }}>{title}</Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {open && (
        <View style={{ paddingHorizontal: 16, paddingBottom: 16, gap: 8 }}>
          {steps.map((s, i) => (
            <View key={i} style={{ flexDirection: 'row', gap: 10 }}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD, width: 18 }}>{i + 1}.</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19, flex: 1 }} selectable>{s}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
};

export default function InventoryFeedScreen() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const s = useMemo(() => getStyles(colors), [colors]);
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY });
  const [test, setTest] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try {
      const r = await api.get(`/inventory-feeds/${user._id}`);
      setFeeds(r.data.feeds || []);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load feeds', 'error'); }
    finally { setLoading(false); }
  }, [user?._id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const set = (k: string, v: any) => setForm(f => ({ ...f, [k]: v }));
  const payload = () => ({ ...form, sftp_port: Number(form.sftp_port) || 22, feed_id: editId || undefined });

  const runTest = async () => {
    if (!user?._id) return;
    setTesting(true); setTest(null);
    try {
      const r = await api.post(`/inventory-feeds/${user._id}/test`, payload());
      setTest(r.data);
    } catch (e: any) { setTest({ ok: false, error: e?.response?.data?.detail || 'Test failed' }); }
    finally { setTesting(false); }
  };

  const save = async () => {
    if (!user?._id) return;
    setSaving(true);
    try {
      if (editId) {
        await api.put(`/inventory-feeds/${user._id}/${editId}`, payload());
        showToast('Feed updated', 'success');
      } else {
        const r = await api.post(`/inventory-feeds/${user._id}`, { ...payload(), run_now: true });
        const run = r.data.run;
        showToast(run?.status === 'ok' ? `Connected: ${run.units_seen} vehicles imported` : `Saved, first pull failed: ${run?.error || 'unknown'}`, run?.status === 'ok' ? 'success' : 'error');
      }
      setAdding(false); setEditId(null); setForm({ ...EMPTY }); setTest(null);
      load();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save feed', 'error'); }
    finally { setSaving(false); }
  };

  const pullNow = async (f: Feed) => {
    if (!user?._id) return;
    setBusy(f.id);
    try {
      const r = await api.post(`/inventory-feeds/${user._id}/${f.id}/run`);
      const run = r.data.run;
      showToast(run.status === 'ok' ? `${run.units_seen} vehicles · ${run.added} new · ${run.updated} updated · ${run.marked_sold} sold` : (run.error || 'Pull failed'), run.status === 'ok' ? 'success' : 'error');
      load();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Pull failed', 'error'); }
    finally { setBusy(null); }
  };

  const toggle = async (f: Feed) => {
    if (!user?._id) return;
    try { await api.put(`/inventory-feeds/${user._id}/${f.id}`, { enabled: !f.enabled }); load(); } catch { showToast('Could not update', 'error'); }
  };

  const remove = (f: Feed) => {
    showConfirm('Remove this feed?', 'Vehicles already imported stay in Inventory. Automatic pulls stop.', async () => {
      try { await api.delete(`/inventory-feeds/${user?._id}/${f.id}`); showToast('Feed removed', 'success'); load(); } catch { showToast('Could not remove', 'error'); }
    }, undefined, 'Remove');
  };

  const startEdit = (f: Feed) => {
    setEditId(f.id); setAdding(true); setTest(null);
    setForm({ transport: f.transport, provider: f.provider, label: f.label, feed_url: f.feed_url || '', sftp_host: f.sftp_host || '', sftp_port: String(f.sftp_port || 22),
      sftp_username: f.sftp_username || '', sftp_password: '', remote_path: f.remote_path || '/', file_pattern: f.file_pattern || '*.csv', mark_missing_sold: f.mark_missing_sold !== false });
  };

  const statusPill = (f: Feed) => {
    if (!f.enabled) return { label: 'Paused', color: '#8E8E93', icon: 'pause-circle' };
    if (f.last_status === 'error') return { label: 'Needs attention', color: '#FF3B30', icon: 'alert-circle' };
    if (!f.last_status) return { label: 'Waiting for first pull', color: '#FF9500', icon: 'time' };
    return { label: 'Healthy', color: '#34C759', icon: 'checkmark-circle' };
  };

  const renderForm = () => (
    <View style={s.card} {...tid('feed-form')}>
      <Text style={s.cardTitle}>{editId ? 'Edit feed' : 'Connect a feed'}</Text>
      <Text style={s.label}>HOW DOES THE FILE ARRIVE?</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {(['url', 'sftp'] as const).map(t => (
          <TouchableOpacity key={t} onPress={() => { set('transport', t); setTest(null); }} style={[s.chip, form.transport === t && s.chipOn, { flex: 1 }]} {...tid(`feed-transport-${t}`)}>
            <Text style={[s.chipText, form.transport === t && { color: '#000' }]}>{t === 'url' ? 'Feed link (free)' : 'SFTP drop'}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={s.hint}>
        {form.transport === 'url'
          ? 'A public CSV or XML link the dealer already has: their Facebook / Google vehicle catalog feed, or a Google Sheet published as CSV. We check it every hour.'
          : "The dealer's inventory tool drops a CSV on an SFTP folder you own. We pull the newest file every hour and only re-import when it changed."}
      </Text>

      <Text style={s.label}>WHO PUBLISHES IT?</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {PROVIDERS.map(p => (
          <TouchableOpacity key={p.id} onPress={() => set('provider', p.id)} style={[s.chip, form.provider === p.id && s.chipOn]} {...tid(`feed-provider-${p.id}`)}>
            <Text style={[s.chipText, form.provider === p.id && { color: '#000' }]}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={s.label}>NAME (OPTIONAL)</Text>
      <TextInput style={s.input} value={form.label} onChangeText={v => set('label', v)} placeholder="e.g. Used inventory" placeholderTextColor={colors.textTertiary} {...tid('feed-label-input')} />

      {form.transport === 'url' ? (
        <>
          <Text style={s.label}>FEED LINK</Text>
          <TextInput style={[s.input, { fontFamily: MONO, fontSize: 13 }]} value={form.feed_url} onChangeText={v => set('feed_url', v)} placeholder="https://..." autoCapitalize="none" autoCorrect={false} keyboardType="url" placeholderTextColor={colors.textTertiary} {...tid('feed-url-input')} />
        </>
      ) : (
        <>
          <Text style={s.label}>SFTP HOST</Text>
          <TextInput style={[s.input, { fontFamily: MONO, fontSize: 13 }]} value={form.sftp_host} onChangeText={v => set('sftp_host', v)} placeholder="feeds.yourdomain.com" autoCapitalize="none" autoCorrect={false} placeholderTextColor={colors.textTertiary} {...tid('feed-sftp-host')} />
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <View style={{ flex: 2 }}>
              <Text style={s.label}>USERNAME</Text>
              <TextInput style={[s.input, { fontFamily: MONO, fontSize: 13 }]} value={form.sftp_username} onChangeText={v => set('sftp_username', v)} autoCapitalize="none" autoCorrect={false} placeholderTextColor={colors.textTertiary} {...tid('feed-sftp-user')} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.label}>PORT</Text>
              <TextInput style={[s.input, { fontFamily: MONO, fontSize: 13 }]} value={form.sftp_port} onChangeText={v => set('sftp_port', v)} keyboardType="number-pad" placeholderTextColor={colors.textTertiary} {...tid('feed-sftp-port')} />
            </View>
          </View>
          <Text style={s.label}>PASSWORD{editId ? ' (LEAVE BLANK TO KEEP)' : ''}</Text>
          <TextInput style={[s.input, { fontFamily: MONO, fontSize: 13 }]} value={form.sftp_password} onChangeText={v => set('sftp_password', v)} secureTextEntry autoCapitalize="none" placeholderTextColor={colors.textTertiary} {...tid('feed-sftp-pass')} />
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <View style={{ flex: 1 }}>
              <Text style={s.label}>FOLDER</Text>
              <TextInput style={[s.input, { fontFamily: MONO, fontSize: 13 }]} value={form.remote_path} onChangeText={v => set('remote_path', v)} autoCapitalize="none" autoCorrect={false} placeholderTextColor={colors.textTertiary} {...tid('feed-sftp-path')} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.label}>FILE PATTERN</Text>
              <TextInput style={[s.input, { fontFamily: MONO, fontSize: 13 }]} value={form.file_pattern} onChangeText={v => set('file_pattern', v)} autoCapitalize="none" autoCorrect={false} placeholderTextColor={colors.textTertiary} {...tid('feed-sftp-pattern')} />
            </View>
          </View>
        </>
      )}

      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 6 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>Mark missing vehicles as sold</Text>
          <Text style={s.hint}>A unit that disappears from the file is marked sold so Jessi stops offering it.</Text>
        </View>
        <Switch value={form.mark_missing_sold} onValueChange={v => set('mark_missing_sold', v)} trackColor={{ true: GOLD }} {...tid('feed-mark-sold')} />
      </View>

      {test && (
        <View style={[s.testBox, { borderColor: test.ok ? '#34C759' : '#FF3B30' }]} {...tid('feed-test-result')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Ionicons name={test.ok ? 'checkmark-circle' : 'close-circle'} size={18} color={test.ok ? '#34C759' : '#FF3B30'} />
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text, flex: 1 }}>
              {test.ok ? `Found ${test.vehicles} vehicle${test.vehicles === 1 ? '' : 's'}${test.file_count > 1 ? ` in ${test.files?.[0]?.name}` : ''}` : test.error}
            </Text>
          </View>
          {test.ok && test.fields?.length ? <Text style={s.hint}>Columns: {test.fields.join(', ')}</Text> : null}
          {test.ok && test.warning ? <Text style={[s.hint, { color: '#FF9500' }]}>{test.warning}</Text> : null}
          {test.ok && test.sample?.map((v: any, i: number) => (
            <Text key={i} style={{ fontSize: 13, color: colors.text }}>• {v.name}{v.price ? ` · $${Math.round(v.price).toLocaleString()}` : ''}{v.photos ? ` · ${v.photos} photo${v.photos === 1 ? '' : 's'}` : ' · no photos'}</Text>
          ))}
          {test.ok && test.files?.length > 1 ? <Text style={s.hint}>{test.file_count} files match; the newest one is used.</Text> : null}
        </View>
      )}

      <View style={{ flexDirection: 'row', gap: 10, marginTop: 4 }}>
        <TouchableOpacity onPress={runTest} disabled={testing} style={[s.btn, s.btnOutline, { flex: 1 }]} {...tid('feed-test-btn')}>
          {testing ? <ActivityIndicator size="small" color={GOLD} /> : <><Ionicons name="flask-outline" size={16} color={GOLD} /><Text style={[s.btnText, { color: GOLD }]}>Test</Text></>}
        </TouchableOpacity>
        <TouchableOpacity onPress={save} disabled={saving} style={[s.btn, { flex: 1, backgroundColor: GOLD }]} {...tid('feed-save-btn')}>
          {saving ? <ActivityIndicator size="small" color="#000" /> : <><Ionicons name="cloud-download-outline" size={16} color="#000" /><Text style={[s.btnText, { color: '#000' }]}>{editId ? 'Save' : 'Connect and import'}</Text></>}
        </TouchableOpacity>
      </View>
      <TouchableOpacity onPress={() => { setAdding(false); setEditId(null); setForm({ ...EMPTY }); setTest(null); }} style={{ alignSelf: 'center', paddingVertical: 6 }} {...tid('feed-cancel-btn')}>
        <Text style={{ fontSize: 13, color: colors.textSecondary }}>Cancel</Text>
      </TouchableOpacity>
    </View>
  );

  const renderFeed = (f: Feed) => {
    const pill = statusPill(f);
    const c = f.last_counts;
    return (
      <View key={f.id} style={s.card} {...tid(`feed-card-${f.id}`)}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: `${pill.color}22`, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={f.transport === 'sftp' ? 'server-outline' : 'link-outline'} size={18} color={pill.color} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{f.label}</Text>
            <Text style={s.hint}>{f.provider_label} · {f.transport === 'sftp' ? `${f.sftp_username}@${f.sftp_host}${f.remote_path}` : (f.feed_url || '').replace(/^https?:\/\//, '').slice(0, 44)}</Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, paddingVertical: 4, borderRadius: 10, backgroundColor: `${pill.color}22` }} {...tid(`feed-status-${f.id}`)}>
            <Ionicons name={pill.icon as any} size={13} color={pill.color} />
            <Text style={{ fontSize: 12, fontWeight: '700', color: pill.color }}>{pill.label}</Text>
          </View>
        </View>

        <View style={{ flexDirection: 'row', gap: 8 }}>
          <View style={s.pill}><Text style={s.pillLabel}>LIVE UNITS</Text><Text style={s.pillValue} {...tid(`feed-live-${f.id}`)}>{f.live_units}</Text></View>
          <View style={s.pill}><Text style={s.pillLabel}>LAST PULL</Text><Text style={s.pillValue}>{ago(f.last_run_at)}</Text></View>
          <View style={s.pill}><Text style={s.pillLabel}>LAST CHANGE</Text><Text style={s.pillValue}>{c ? `+${c.added} / ~${c.updated} / -${c.marked_sold}` : '-'}</Text></View>
        </View>
        {f.last_status === 'error' && f.last_error ? (
          <View style={{ flexDirection: 'row', gap: 8, backgroundColor: '#FF3B3015', borderRadius: 10, padding: 10 }}>
            <Ionicons name="warning" size={16} color="#FF3B30" />
            <Text style={{ fontSize: 13, color: '#FF3B30', flex: 1 }} {...tid(`feed-error-${f.id}`)}>{f.last_error}</Text>
          </View>
        ) : null}
        {f.last_file?.name ? <Text style={s.hint}>File: {f.last_file.name}{f.last_success_at ? ` · last successful import ${ago(f.last_success_at)}` : ''}</Text> : null}

        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          <TouchableOpacity onPress={() => pullNow(f)} disabled={busy === f.id} style={[s.btn, { backgroundColor: GOLD, paddingHorizontal: 12 }]} {...tid(`feed-pull-${f.id}`)}>
            {busy === f.id ? <ActivityIndicator size="small" color="#000" /> : <><Ionicons name="refresh" size={15} color="#000" /><Text style={[s.btnText, { color: '#000' }]}>Pull now</Text></>}
          </TouchableOpacity>
          <TouchableOpacity onPress={() => startEdit(f)} style={[s.btn, s.btnOutline, { paddingHorizontal: 12 }]} {...tid(`feed-edit-${f.id}`)}><Ionicons name="create-outline" size={15} color={GOLD} /><Text style={[s.btnText, { color: GOLD }]}>Edit</Text></TouchableOpacity>
          <TouchableOpacity onPress={() => toggle(f)} style={[s.btn, s.btnOutline, { paddingHorizontal: 12 }]} {...tid(`feed-toggle-${f.id}`)}><Ionicons name={f.enabled ? 'pause' : 'play'} size={15} color={GOLD} /><Text style={[s.btnText, { color: GOLD }]}>{f.enabled ? 'Pause' : 'Resume'}</Text></TouchableOpacity>
          <TouchableOpacity onPress={() => remove(f)} style={[s.btn, s.btnOutline, { paddingHorizontal: 10, borderColor: '#FF3B3055' }]} {...tid(`feed-delete-${f.id}`)}><Ionicons name="trash-outline" size={15} color="#FF3B30" /></TouchableOpacity>
        </View>

        {f.runs?.length ? (
          <View style={{ gap: 6 }}>
            <Text style={s.label}>RECENT PULLS</Text>
            {f.runs.slice(0, 5).map(r => (
              <View key={r.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name={r.status === 'ok' ? 'checkmark-circle' : r.status === 'no_change' ? 'remove-circle-outline' : 'close-circle'} size={14} color={r.status === 'ok' ? '#34C759' : r.status === 'no_change' ? colors.textTertiary : '#FF3B30'} />
                <Text style={{ fontSize: 12, color: colors.textSecondary, flex: 1 }} numberOfLines={1}>
                  {ago(r.started_at)} · {r.status === 'ok' ? `${r.units_seen} units, +${r.added} ~${r.updated} -${r.marked_sold}` : r.status === 'no_change' ? 'no change' : (r.error || 'error')}
                  {r.triggered_by?.startsWith('user') ? ' · manual' : ''}
                </Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.back} {...tid('inventory-feed-back')}><Ionicons name="chevron-back" size={28} color={GOLD} /></TouchableOpacity>
        <Text style={s.title}>Inventory Feed</Text>
        <View style={s.back} />
      </View>
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, gap: 14, paddingBottom: 60 }}>
          <View style={[s.card, { flexDirection: 'row', gap: 12, alignItems: 'center' }]}>
            <Ionicons name="sparkles" size={20} color={GOLD} />
            <Text style={[s.hint, { flex: 1 }]}>Connect the dealer's inventory once. Every hour we pull the latest file, update prices and photos, and mark sold units so Jessi only offers what is on the lot.</Text>
          </View>

          {feeds.map(renderFeed)}

          {adding ? renderForm() : (
            <TouchableOpacity onPress={() => { setAdding(true); setEditId(null); setForm({ ...EMPTY }); }} style={[s.btn, { backgroundColor: GOLD, alignSelf: 'stretch', paddingVertical: 14 }]} {...tid('feed-add-btn')}>
              <Ionicons name="add" size={18} color="#000" />
              <Text style={[s.btnText, { color: '#000', fontSize: 15 }]}>{feeds.length ? 'Add another feed' : 'Connect a feed'}</Text>
            </TouchableOpacity>
          )}

          <Text style={[s.label, { marginTop: 8 }]}>DEALER CHECKLISTS (SEND THESE)</Text>
          <Guide id="guide-url" title="Get a feed link (free, no vendor form)" icon="link" color="#34C759" colors={colors} steps={[
            'Ask the dealer: "Do you run Facebook Marketplace / Automotive Inventory Ads or Google Vehicle Listing Ads?" If yes, they already have a catalog feed link.',
            'HomeNet: Inventory Online > Exports (or their HomeNet rep) > copy the Facebook / Google catalog feed URL.',
            'Dealer.com / DealerOn / Dealer Inspire: the website provider support desk can send the store\'s Facebook or Google vehicle feed URL in a day.',
            'Small independents: keep a Google Sheet (VIN, Stock, Year, Make, Model, Trim, Price, Mileage, Color, Body, Photo URLs) and use File > Share > Publish to web > CSV. Paste that link here.',
            'Paste the link above, tap Test, confirm the vehicle count and photos, then Connect and import.',
          ]} />
          <Guide id="guide-homenet" title="HomeNet SFTP export (when a link is not available)" icon="server" color="#FF9500" colors={colors} steps={[
            'Create a folder and login for this dealer on your SFTP box (see the owner guide below).',
            'Dealer\'s Internet Director opens homenetauto.com/vfsr (HomeNet Export Request Form).',
            'Destination: "i\'M On Social". Format: CSV with photos (ImageList). Frequency: nightly.',
            'They paste your SFTP host, port 22, the dealer\'s username and password, folder /, and a fixed file name (e.g. inventory.csv).',
            'HomeNet enables the export in 1 to 3 business days. Add the same SFTP details here with pattern *.csv and tap Test.',
          ]} />
          <Guide id="guide-vauto" title="vAuto SFTP export" icon="server" color="#FF9500" colors={colors} steps={[
            'Same folder + login on your SFTP box.',
            'Dealer asks their vAuto rep for a "third-party inventory export" to i\'M On Social, nightly CSV with photo URLs.',
            'They hand the rep your SFTP host, port 22, username, password and folder.',
            'Once the first file lands, add the SFTP details here and tap Test.',
          ]} />
          <Guide id="guide-owner" title="Owner setup: your own SFTP box for $4/mo" icon="construct" color={GOLD} colors={colors} steps={[
            'Create a Hetzner (or DigitalOcean) Ubuntu 24.04 server, smallest size. Point a DNS name at it, e.g. feeds.imonsocial.com.',
            'Install SFTPGo (open source) from its apt repo: curl -sS https://download.sftpgo.com/apt/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/sftpgo-archive-keyring.gpg; echo "deb [signed-by=/usr/share/keyrings/sftpgo-archive-keyring.gpg] https://download.sftpgo.com/apt $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/sftpgo.list; sudo apt update && sudo apt install sftpgo',
            'SFTPGo listens for SFTP on port 2022 and its web admin on 8080. Vendor forms usually assume port 22: move your own SSH to 2222 (Port 2222 in /etc/ssh/sshd_config, restart ssh), then set SFTPGo to 22 (sudo sed -i \'s/"port": 2022/"port": 22/\' /etc/sftpgo/sftpgo.json; sudo systemctl restart sftpgo). Open ports 22, 2222 and 8080 in the firewall.',
            'Open http://feeds.imonsocial.com:8080/web/admin and finish the setup wizard (create the admin login).',
            'For each dealer: Users > Add. Username = dealer slug (e.g. mountain-toyota), a strong password, home directory /srv/sftpgo/data/mountain-toyota, permissions: list, upload, download, overwrite, delete.',
            'Give the dealer (or their vendor form) the host, port 22, that username and password, folder /. Enter the same details in this screen with pattern *.csv.',
            'One box serves every dealer, no per-user fees. Later you can move to SFTP To Go ($18/mo) or Files.com without changing anything in the app.',
          ]} />
          <Guide id="guide-columns" title="Columns we understand" icon="list" color="#5856D6" colors={colors} steps={[
            'Required for matching: VIN or Stock number. Everything else is optional.',
            'Vehicle: Year, Make, Model, Trim, Body / Body Style, Type or Condition (New / Used / Certified), Exterior Color, Mileage, Drivetrain, Fuel, Transmission, Engine.',
            'Pricing: Internet Price wins over Selling Price, Price, MSRP when several exist.',
            'Photos: ImageList / Photo URLs / Images, separated by | or , (up to 12). Facebook and Google XML catalog feeds work as-is.',
            'Google Sheet edit links are converted to CSV automatically.',
          ]} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  back: { width: 40 },
  title: { fontSize: 17, fontWeight: '700', color: colors.text },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 16, gap: 12 },
  cardTitle: { fontSize: 17, fontWeight: '800', color: colors.text },
  label: { fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.8 },
  hint: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  input: { backgroundColor: colors.bg, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border },
  chip: { paddingHorizontal: 14, height: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg, justifyContent: 'center', alignItems: 'center' },
  chipOn: { backgroundColor: GOLD, borderColor: GOLD },
  chipText: { fontSize: 13, fontWeight: '700', color: colors.text },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 10, paddingHorizontal: 10, borderRadius: 12 },
  btnOutline: { borderWidth: 1, borderColor: GOLD, backgroundColor: 'transparent' },
  btnText: { fontSize: 13, fontWeight: '700' },
  pill: { flex: 1, backgroundColor: colors.bg, borderRadius: 10, padding: 10, borderWidth: 1, borderColor: colors.border },
  pillLabel: { fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6 },
  pillValue: { fontSize: 15, fontWeight: '800', color: colors.text, marginTop: 2 },
  testBox: { borderWidth: 1, borderRadius: 12, padding: 12, gap: 6, backgroundColor: colors.bg },
});
