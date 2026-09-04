import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, Platform, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import * as Sharing from 'expo-sharing';
import { File as ExpoFile, Paths } from 'expo-file-system';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../services/api';
import { useToast } from '../common/Toast';

const GOLD = '#C9A962';
const DISMISS_KEY = 'proof_cost_prompt_dismissed_until';
const fmtSecs = (s: number | null | undefined) => s == null ? '--' : s < 60 ? `${s}s` : s < 3600 ? `${Math.round(s / 60)}m` : s < 86400 ? `${Math.round(s / 3600)}h` : `${Math.round(s / 86400)}d`;
const money = (n: number | null | undefined) => n == null ? '--' : `$${Math.round(n).toLocaleString()}`;

type Source = { source_id?: string | null; source_name: string; leads: number; sold: number; close_rate: number | null; reply_rate: number | null; first_touch_avg_seconds: number | null; touched_pct: number | null; avg_touches: number | null; avg_days_to_sold: number | null; monthly_cost: number | null; period_cost: number | null; cost_per_lead: number | null; cost_per_sale: number | null };

type Bucket = { label: string; leads: number; sold: number; close_rate: number | null; reply_rate: number | null };
type Proof = {
  days: number; leads: number; sold: number; close_rate: number | null; small_sample: boolean;
  reply: { replied: { leads: number; sold: number; close_rate: number | null }; silent: { leads: number; sold: number; close_rate: number | null }; lift: number | null };
  speed_human_text: Bucket[]; speed_first_touch: Bucket[]; touchpoints: Bucket[]; conversation_depth: Bucket[]; headlines: string[];
  time_to_sold?: { count: number; avg_days: number | null; median_days: number | null; fastest_days: number | null };
  sources?: Source[]; benchmark?: string; unpriced_sources?: { source_id: string; source_name: string; leads: number }[];
};

const SourceCostPrompt = ({ items, colors, onSaved }: { items: { source_id: string; source_name: string; leads: number }[]; colors: any; onSaved: () => void }) => {
  const { showToast } = useToast();
  const [hidden, setHidden] = useState(true);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  useEffect(() => {
    AsyncStorage.getItem(DISMISS_KEY).then(v => setHidden(!!v && Number(v) > Date.now())).catch(() => setHidden(false));
  }, []);
  if (hidden || !items.length) return null;
  const dismiss = async () => {
    await AsyncStorage.setItem(DISMISS_KEY, String(Date.now() + 30 * 86400000));
    setHidden(true);
  };
  const save = async (id: string) => {
    const n = Number(String(vals[id] || '').replace(/[^0-9.]/g, ''));
    if (!n) return;
    setSaving(id);
    try {
      await api.patch(`/lead-sources/${id}`, { monthly_cost: n });
      showToast('Monthly spend saved', 'success');
      onSaved();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not save', 'error');
    } finally {
      setSaving(null);
    }
  };
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, gap: 10, borderWidth: 1, borderColor: `${GOLD}44` }} testID="source-cost-prompt" dataSet={{ testid: 'source-cost-prompt' } as any}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="cash-outline" size={16} color={GOLD} />
        <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 }}>Optional: what do these sources cost per month?</Text>
        <TouchableOpacity onPress={dismiss} testID="source-cost-dismiss" dataSet={{ testid: 'source-cost-dismiss' } as any}><Text style={{ fontSize: 13, fontWeight: '600', color: colors.textSecondary }}>Skip</Text></TouchableOpacity>
      </View>
      <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Add a number and cost per sale fills in automatically. Leave it blank and everything else still works.</Text>
      {items.map(it => (
        <View key={it.source_id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} testID={`source-cost-row-${it.source_id}`} dataSet={{ testid: `source-cost-row-${it.source_id}` } as any}>
          <Text style={{ flex: 1, fontSize: 15, color: colors.text }} numberOfLines={1}>{it.source_name} <Text style={{ color: colors.textSecondary, fontSize: 12 }}>· {it.leads} leads</Text></Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.bg, borderRadius: 8, paddingHorizontal: 8, height: 34, width: 110 }}>
            <Text style={{ color: colors.textSecondary, fontSize: 15 }}>$</Text>
            <TextInput value={vals[it.source_id] || ''} onChangeText={t => setVals(v => ({ ...v, [it.source_id]: t }))} keyboardType="numeric" placeholder="per mo" placeholderTextColor={colors.textSecondary}
              style={{ flex: 1, color: colors.text, fontSize: 15, paddingVertical: 0 }} testID={`source-cost-input-${it.source_id}`} dataSet={{ testid: `source-cost-input-${it.source_id}` } as any} />
          </View>
          <TouchableOpacity onPress={() => save(it.source_id)} disabled={saving === it.source_id} style={{ backgroundColor: GOLD, borderRadius: 8, paddingHorizontal: 12, height: 34, justifyContent: 'center' }} testID={`source-cost-save-${it.source_id}`} dataSet={{ testid: `source-cost-save-${it.source_id}` } as any}>
            {saving === it.source_id ? <ActivityIndicator size="small" color="#000" /> : <Text style={{ fontSize: 13, fontWeight: '700', color: '#000' }}>Save</Text>}
          </TouchableOpacity>
        </View>
      ))}
    </View>
  );
};

const Card = ({ title, children, colors, testid, right }: any) => (
  <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, gap: 10 }} testID={testid} dataSet={{ testid } as any}>
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text, letterSpacing: 0.8, flex: 1 }}>{title}</Text>
      {right}
    </View>
    {children}
  </View>
);

const BucketBars = ({ rows, colors }: { rows: Bucket[]; colors: any }) => {
  const max = Math.max(1, ...rows.map(r => r.close_rate || 0));
  return (
    <View style={{ gap: 8 }}>
      {rows.map(r => (
        <View key={r.label} style={{ gap: 3 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ fontSize: 13, color: r.leads ? colors.text : colors.textSecondary }}>{r.label}</Text>
            <Text style={{ fontSize: 13, fontWeight: '700', color: r.leads ? colors.text : colors.textSecondary }}>
              {r.leads ? `${r.close_rate}% closed · ${r.sold} of ${r.leads}` : 'no leads'}
            </Text>
          </View>
          <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.bg, overflow: 'hidden' }}>
            <View style={{ width: `${r.leads ? Math.max(3, Math.round(100 * (r.close_rate || 0) / max)) : 0}%`, height: 6, backgroundColor: r.leads ? GOLD : 'transparent', borderRadius: 3 }} />
          </View>
        </View>
      ))}
    </View>
  );
};

const SourceRow = ({ s, colors }: { s: Source; colors: any }) => (
  <View style={{ gap: 6, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.border }} testID={`proof-source-${s.source_name}`} dataSet={{ testid: `proof-source-${s.source_name}` } as any}>
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 }} numberOfLines={1}>{s.source_name}</Text>
      <Text style={{ fontSize: 15, fontWeight: '800', color: s.cost_per_sale != null ? GOLD : colors.textSecondary }}>{s.cost_per_sale != null ? `${money(s.cost_per_sale)} / sale` : s.period_cost ? 'no sales yet' : 'no cost set'}</Text>
    </View>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
      {[
        `${s.leads} leads`, `${s.sold} sold${s.close_rate != null ? ` (${s.close_rate}%)` : ''}`,
        s.first_touch_avg_seconds != null ? `first touch ${fmtSecs(s.first_touch_avg_seconds)}` : 'never touched',
        s.reply_rate != null ? `${s.reply_rate}% replied` : null,
        s.avg_touches != null ? `${s.avg_touches} touches avg` : null,
        s.avg_days_to_sold != null ? `${s.avg_days_to_sold} days to sold` : null,
        s.period_cost != null ? `spent ${money(s.period_cost)}` : null,
        s.cost_per_lead != null ? `${money(s.cost_per_lead)} / lead` : null,
      ].filter(Boolean).map((chip, i) => (
        <View key={i} style={{ backgroundColor: colors.bg, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 }}>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>{chip}</Text>
        </View>
      ))}
    </View>
  </View>
);

export const ProofPanel = ({ data, colors, isManager, storeParam = '', days = 90, onRefresh }: { data: Proof | null; colors: any; isManager?: boolean; storeParam?: string; days?: number; onRefresh?: () => void }) => {
  const { showToast } = useToast();
  const [sharing, setSharing] = useState(false);
  if (!data) return null;
  const rp = data.reply.replied, sl = data.reply.silent;
  const tts = data.time_to_sold;
  const shareImage = async () => {
    setSharing(true);
    try {
      const res = await api.get(`/leads/analytics/proof-card.png?${storeParam}days=${days}`, { responseType: Platform.OS === 'web' ? 'blob' : 'arraybuffer' });
      if (Platform.OS === 'web') {
        const url = URL.createObjectURL(res.data);
        const a = document.createElement('a'); a.href = url; a.download = 'imos-proof.png'; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
        showToast('Proof image downloaded', 'success');
      } else {
        const file = new ExpoFile(Paths.cache, 'imos-proof.png');
        file.write(new Uint8Array(res.data));
        if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(file.uri, { mimeType: 'image/png', dialogTitle: 'Share proof' });
      }
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not build the image', 'error');
    } finally {
      setSharing(false);
    }
  };
  const copy = async () => {
    const src = (data.sources || []).filter(s => s.leads).map(s => `• ${s.source_name}: ${s.leads} leads, ${s.sold} sold${s.close_rate != null ? ` (${s.close_rate}%)` : ''}${s.cost_per_sale != null ? `, ${money(s.cost_per_sale)} per sale` : ''}${s.first_touch_avg_seconds != null ? `, first touch ${fmtSecs(s.first_touch_avg_seconds)}` : ''}`);
    const lines = [`iMOS internet lead proof (last ${data.days} days, ${data.leads} leads, ${data.close_rate ?? 0}% closed)`, ...data.headlines.map(h => `• ${h}`), ...(src.length ? ['', 'By source:', ...src] : [])];
    await Clipboard.setStringAsync(lines.join('\n'));
    showToast('Proof summary copied', 'success');
  };
  return (
    <View style={{ gap: 10 }} testID="proof-panel" dataSet={{ testid: 'proof-panel' } as any}>
      <Card title="DOES ENGAGEMENT CLOSE DEALS?" colors={colors} testid="proof-summary"
        right={<View style={{ flexDirection: 'row', gap: 14 }}>
          <TouchableOpacity onPress={shareImage} disabled={sharing} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} testID="proof-share-image" dataSet={{ testid: 'proof-share-image' } as any}>
            {sharing ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="image-outline" size={14} color={GOLD} />}<Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Share image</Text></TouchableOpacity>
          <TouchableOpacity onPress={copy} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} testID="proof-copy" dataSet={{ testid: 'proof-copy' } as any}>
            <Ionicons name="copy-outline" size={14} color={GOLD} /><Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Copy</Text></TouchableOpacity>
        </View>}>
        <Text style={{ fontSize: 15, color: colors.text }}>{`${data.leads} internet leads · ${data.sold} sold · ${data.close_rate ?? 0}% close rate`}</Text>
        {data.small_sample && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="information-circle-outline" size={14} color="#FF9500" />
            <Text style={{ fontSize: 12, color: colors.textSecondary, flex: 1 }}>Under 30 leads in this window. Numbers firm up as more leads and sold photos come in.</Text>
          </View>
        )}
        {data.headlines.length ? data.headlines.map((h, i) => (
          <View key={i} style={{ flexDirection: 'row', gap: 8 }} testID={`proof-headline-${i}`} dataSet={{ testid: `proof-headline-${i}` } as any}>
            <Ionicons name="checkmark-circle" size={16} color="#34C759" style={{ marginTop: 1 }} />
            <Text style={{ flex: 1, fontSize: 15, fontWeight: '600', color: colors.text, lineHeight: 21 }}>{h}</Text>
          </View>
        )) : (
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Headlines appear once there are sold leads in both groups being compared. Keep snapping sold photos.</Text>
        )}
      </Card>

      <Card title="TEXTED BACK VS SILENT" colors={colors} testid="proof-reply">
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {[{ l: 'REPLIED', g: rp, c: '#34C759' }, { l: 'SILENT', g: sl, c: '#FF9500' }].map(x => (
            <View key={x.l} style={{ flex: 1, backgroundColor: colors.bg, borderRadius: 10, padding: 12, alignItems: 'center', gap: 2 }}>
              <Text style={{ fontSize: 28, fontWeight: '800', color: x.g.leads ? x.c : colors.textSecondary }}>{x.g.leads ? `${x.g.close_rate}%` : '--'}</Text>
              <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }}>{x.l} CLOSED</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{`${x.g.sold} of ${x.g.leads} leads`}</Text>
            </View>
          ))}
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>
          {data.reply.lift ? `A lead that texts back is ${data.reply.lift}x more likely to buy. ` : ''}Only leads that received a text are counted.
        </Text>
      </Card>

      <Card title="SPEED OF FIRST TOUCH (CALL, TEXT OR AI)" colors={colors} testid="proof-first-touch"><BucketBars rows={data.speed_first_touch} colors={colors} /></Card>

      <Card title="TRUE COST PER SALE BY SOURCE" colors={colors} testid="proof-sources">
        {isManager && !!data.unpriced_sources?.length && <SourceCostPrompt items={data.unpriced_sources} colors={colors} onSaved={() => onRefresh && onRefresh()} />}
        {tts?.avg_days != null && (
          <View style={{ flexDirection: 'row', gap: 8 }} testID="proof-time-to-sold" dataSet={{ testid: 'proof-time-to-sold' } as any}>
            {[{ l: 'AVG DAYS', v: tts.avg_days }, { l: 'MEDIAN DAYS', v: tts.median_days }, { l: 'FASTEST', v: tts.fastest_days }].map(x => (
              <View key={x.l} style={{ flex: 1, backgroundColor: colors.bg, borderRadius: 10, paddingVertical: 10, alignItems: 'center' }}>
                <Text style={{ fontSize: 20, fontWeight: '800', color: GOLD }}>{x.v}</Text>
                <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }} numberOfLines={1}>{x.l}</Text>
              </View>
            ))}
          </View>
        )}
        {(data.sources || []).length ? (data.sources || []).map(s => <SourceRow key={s.source_name} s={s} colors={colors} />) : (
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>No sources in this window.</Text>
        )}
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Spend comes from the monthly cost on each source in Lead Source Config, prorated to this window. Sold is any lead whose contact got a sold photo.</Text>
      </Card>

      <Card title="SPEED OF FIRST HUMAN TEXT" colors={colors} testid="proof-human-speed"><BucketBars rows={data.speed_human_text} colors={colors} /></Card>
      <Card title="TOUCHPOINTS PER LEAD (TEXTS + CALLS)" colors={colors} testid="proof-touchpoints"><BucketBars rows={data.touchpoints} colors={colors} /></Card>
      <Card title="HOW MANY TIMES THEY REPLIED" colors={colors} testid="proof-depth"><BucketBars rows={data.conversation_depth} colors={colors} /></Card>
      {!!data.benchmark && (
        <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 4 }}>
          <Ionicons name="school-outline" size={14} color={colors.textSecondary} style={{ marginTop: 2 }} />
          <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>{`Industry benchmark. ${data.benchmark}`}</Text>
        </View>
      )}
    </View>
  );
};
