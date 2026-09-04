import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { useToast } from '../../components/common/Toast';
import { copyToClipboard } from '../../utils/clipboard';
import api from '../../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const MONO = Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' });

type Source = { id: string; name: string; is_active: boolean };
type Connect = {
  source: { id: string; name: string; is_active: boolean; api_key?: string | null; lead_count: number };
  webhook_url: string; header_name: string; sample_payload: Record<string, any>;
  fields: { key: string; label: string; aliases: string[] }[];
  last_lead: { id: string; name: string; phone_last4?: string | null; seconds_ago?: number | null; is_test: boolean; status?: string; conversation_id?: string | null; vehicle?: string | null } | null;
  received_24h: number;
};

const ago = (s?: number | null) => s == null ? '' : s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : s < 86400 ? `${Math.round(s / 3600)}h ago` : `${Math.round(s / 86400)}d ago`;

const CopyRow = ({ label, value, id, colors, onCopy, mono = true }: { label: string; value: string; id: string; colors: any; onCopy: (v: string, l: string) => void; mono?: boolean }) => (
  <View style={{ gap: 4 }}>
    <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6 }}>{label.toUpperCase()}</Text>
    <TouchableOpacity onPress={() => onCopy(value, label)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.bg, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: colors.border }} {...tid(id)}>
      <Text style={{ flex: 1, fontSize: 13, color: colors.text, fontFamily: mono ? MONO : undefined }} numberOfLines={2} selectable>{value}</Text>
      <Ionicons name="copy-outline" size={18} color={GOLD} />
    </TouchableOpacity>
  </View>
);

const Step = ({ n, title, children, colors }: { n: number; title: string; children: React.ReactNode; colors: any }) => (
  <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 16, gap: 12 }} {...tid(`connect-step-${n}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>
        <Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>{n}</Text>
      </View>
      <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, flex: 1 }}>{title}</Text>
    </View>
    {children}
  </View>
);

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
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19, flex: 1 }}>{s}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
};

export default function LeadConnectScreen() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const s = useMemo(() => getStyles(colors), [colors]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [info, setInfo] = useState<Connect | null>(null);
  const [loading, setLoading] = useState(true);
  const [showKey, setShowKey] = useState(false);
  const [baseline, setBaseline] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    const storeId = user?.store_id || user?._id;
    if (!storeId) return;
    api.get(`/lead-sources?store_id=${storeId}`).then(r => {
      const list: Source[] = r.data.lead_sources || r.data || [];
      setSources(list);
      setSelected(prev => prev || list.find(x => x.is_active)?.id || list[0]?.id || null);
    }).catch(() => showToast('Could not load lead sources', 'error')).finally(() => setLoading(false));
  }, [user?._id, user?.store_id]);

  const refresh = useCallback(async () => {
    if (!selected) return;
    try {
      const r = await api.get(`/leads/connect/${selected}`);
      setInfo(r.data);
      setBaseline(b => (b === undefined ? (r.data.last_lead?.id ?? null) : b));
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load connection details', 'error'); }
  }, [selected]);

  useEffect(() => { setInfo(null); setBaseline(undefined); refresh(); }, [selected]);
  useFocusEffect(useCallback(() => { const t = setInterval(refresh, 5000); return () => clearInterval(t); }, [refresh]));

  const copy = async (v: string, label: string) => { showToast((await copyToClipboard(v)) ? `${label} copied` : 'Could not copy', 'success'); };
  const fresh = !!info?.last_lead && baseline !== undefined && info.last_lead.id !== baseline;
  const sample = info ? JSON.stringify(info.sample_payload, null, 2) : '';
  const key = info?.source.api_key || '';

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.back} {...tid('lead-connect-back')}><Ionicons name="chevron-back" size={28} color={colors.accent} /></TouchableOpacity>
        <Text style={s.title}>Connect Zapier / Make</Text>
        <View style={s.back} />
      </View>
      {loading ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} {...tid('lead-connect-scroll')}>
          <View style={[s.card, { borderWidth: 1, borderColor: `${GOLD}55` }]}>
            <Text style={s.cardSub}>{"Point any app at iMOS. Zapier, Make, a website form, a Facebook lead ad. Every lead that lands here gets the full treatment: instant text from the rep's number, the call ladder, speed clocks and a spot in Proof."}</Text>
          </View>

          <Step n={1} title="Pick the lead source it feeds" colors={colors}>
            {sources.length === 0 ? (
              <TouchableOpacity onPress={() => router.push('/admin/lead-sources')} style={s.linkBtn} {...tid('connect-create-source')}>
                <Ionicons name="add-circle" size={16} color={GOLD} /><Text style={s.linkText}>Create your first lead source</Text>
              </TouchableOpacity>
            ) : (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                {sources.map(src => (
                  <TouchableOpacity key={src.id} onPress={() => setSelected(src.id)} style={[s.chip, selected === src.id && s.chipOn]} {...tid(`connect-source-${src.id}`)}>
                    <Text style={[s.chipText, selected === src.id && { color: '#000' }]}>{src.name}</Text>
                  </TouchableOpacity>
                ))}
                <TouchableOpacity onPress={() => router.push('/admin/lead-sources')} style={[s.chip, { borderStyle: 'dashed' }]} {...tid('connect-new-source')}>
                  <Text style={s.chipText}>+ New</Text>
                </TouchableOpacity>
              </View>
            )}
            <Text style={s.cardSub}>One source per feed keeps Proof honest: you will see cost per sale for each one.</Text>
          </Step>

          {info && (
            <>
              <Step n={2} title="Paste these into your Zap" colors={colors}>
                <CopyRow label="Webhook URL" value={info.webhook_url} id="connect-copy-url" colors={colors} onCopy={copy} />
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <View style={s.pill}><Text style={s.pillLabel}>METHOD</Text><Text style={s.pillValue}>POST</Text></View>
                  <View style={s.pill}><Text style={s.pillLabel}>PAYLOAD TYPE</Text><Text style={s.pillValue}>JSON</Text></View>
                </View>
                {key ? (
                  <View style={{ gap: 6 }}>
                    <CopyRow label={`Header: ${info.header_name}`} value={showKey ? key : `${key.slice(0, 6)}${'•'.repeat(Math.max(4, key.length - 10))}${key.slice(-4)}`} id="connect-copy-key" colors={colors} onCopy={(_, l) => copy(key, l)} />
                    <TouchableOpacity onPress={() => setShowKey(v => !v)} style={{ alignSelf: 'flex-start' }} {...tid('connect-toggle-key')}>
                      <Text style={s.linkText}>{showKey ? 'Hide key' : 'Show key'}</Text>
                    </TouchableOpacity>
                    <Text style={s.cardSub}>Zapier: open the Headers section on the POST step and add {info.header_name} with this value. No header option in your tool? Add ?api_key= plus the key to the end of the URL instead.</Text>
                  </View>
                ) : (
                  <Text style={s.cardSub}>This source has no API key, so no header is needed.</Text>
                )}
              </Step>

              <Step n={3} title="Map your fields" colors={colors}>
                <Text style={s.cardSub}>Phone is the only must-have. Use these names as the Data keys in Zapier (or copy the sample and swap in your fields). Capitalization does not matter.</Text>
                <TouchableOpacity onPress={() => copy(sample, 'Sample payload')} style={[s.codeBox]} {...tid('connect-copy-sample')}>
                  <Text style={s.code} selectable>{sample}</Text>
                  <View style={{ position: 'absolute', top: 10, right: 10, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                    <Ionicons name="copy-outline" size={14} color={GOLD} /><Text style={{ fontSize: 12, color: GOLD, fontWeight: '700' }}>Copy</Text>
                  </View>
                </TouchableOpacity>
                <View style={{ gap: 6 }}>
                  {info.fields.map(f => (
                    <View key={f.key} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
                      <Text style={[s.code, { color: f.key === 'phone' ? GOLD : colors.text, width: 118 }]}>{f.aliases[0]}</Text>
                      <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>{f.label}{f.aliases.length > 1 ? `  (also ${f.aliases.slice(1).join(', ')})` : ''}</Text>
                    </View>
                  ))}
                </View>
              </Step>

              <Step n={4} title="Send a test and watch it land" colors={colors}>
                <Text style={s.cardSub}>Use your own cell as the phone and keep is_test set to true. The real pipeline runs, so you will get the intake text, but the lead stays out of Proof. Delete is_test once the Zap is live.</Text>
                <View style={[s.statusBox, fresh && { borderColor: '#34C759', backgroundColor: '#34C75914' }]} {...tid('connect-test-status')}>
                  {fresh ? (
                    <>
                      <Ionicons name="checkmark-circle" size={22} color="#34C759" />
                      <View style={{ flex: 1 }}>
                        <Text style={[s.statusTitle, { color: '#34C759' }]}>It landed</Text>
                        <Text style={s.cardSub}>{info.last_lead!.name}{info.last_lead!.phone_last4 ? ` · ***${info.last_lead!.phone_last4}` : ''}{info.last_lead!.vehicle ? ` · ${info.last_lead!.vehicle}` : ''} · {ago(info.last_lead!.seconds_ago)}{info.last_lead!.is_test ? ' · test lead' : ''}</Text>
                      </View>
                    </>
                  ) : (
                    <>
                      <ActivityIndicator size="small" color={GOLD} />
                      <View style={{ flex: 1 }}>
                        <Text style={s.statusTitle}>Listening for your test...</Text>
                        <Text style={s.cardSub}>{info.last_lead ? `Last lead on ${info.source.name}: ${info.last_lead.name}, ${ago(info.last_lead.seconds_ago)}.` : `No leads on ${info.source.name} yet.`} {info.received_24h} in the last 24h.</Text>
                      </View>
                    </>
                  )}
                </View>
                {info.last_lead?.conversation_id && (
                  <TouchableOpacity onPress={() => router.push(`/thread/${info.last_lead!.conversation_id}` as any)} style={s.linkBtn} {...tid('connect-open-thread')}>
                    <Ionicons name="chatbubble-ellipses" size={16} color={GOLD} /><Text style={s.linkText}>{"Open the latest lead's thread"}</Text>
                  </TouchableOpacity>
                )}
                {!info.source.is_active && <Text style={[s.cardSub, { color: '#FF3B30' }]}>This source is paused. Turn it on in Lead Source Config or posts will be rejected.</Text>}
              </Step>

              <Guide id="connect-guide-zapier" title="Step by step in Zapier" icon="flash" color="#FF4A00" colors={colors} steps={[
                'Pick your trigger (Facebook Lead Ads, Google Forms, Typeform, Gmail, a Sheet row, anything).',
                'Add an action: search for "Webhooks by Zapier" and choose the POST event.',
                'URL: paste the Webhook URL from step 2. Payload Type: json.',
                'Data: add a row per field. Left side is the name from step 3 (phone, first_name...). Right side is the matching field from your trigger.',
                key ? `Headers: add ${info.header_name} with the key from step 2.` : 'Headers: none needed for this source.',
                'Turn on Wrap Request In Array: No. Unflatten: yes.',
                'Hit Test step. Watch step 4 above turn green, then publish the Zap.',
              ]} />
              <Guide id="connect-guide-make" title="Step by step in Make" icon="git-network" color="#6C63FF" colors={colors} steps={[
                'Add your trigger module, then an HTTP module: "Make a request".',
                'URL: the Webhook URL from step 2. Method: POST. Body type: Raw. Content type: JSON (application/json).',
                'Request content: paste the sample from step 3 and replace the values with mapped fields from your trigger.',
                key ? `Headers: add ${info.header_name} with the key from step 2.` : 'Headers: none needed for this source.',
                'Run once. Step 4 above confirms the lead landed. Then schedule the scenario.',
              ]} />
              <Guide id="connect-guide-other" title="Website form, Facebook or anything else" icon="globe" color="#34C759" colors={colors} steps={[
                'Any tool that can POST JSON or a standard form to a URL works: Gravity Forms, WordPress, Webflow, HubSpot workflows, Facebook Lead Ads via Zapier.',
                'ADF/XML providers (Cars.com, AutoTrader, CarGurus, dealer websites) can post XML to this same URL. The ADF email address is in Lead Source Config.',
                'Every post is logged in Lead Source Queue with its status, so you can always see what came in and why it did or did not text.',
              ]} />
            </>
          )}
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
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 16 },
  cardSub: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  chip: { paddingHorizontal: 14, height: 34, borderRadius: 17, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg, justifyContent: 'center' },
  chipOn: { backgroundColor: GOLD, borderColor: GOLD },
  chipText: { fontSize: 13, fontWeight: '700', color: colors.text },
  pill: { flex: 1, backgroundColor: colors.bg, borderRadius: 10, padding: 10, borderWidth: 1, borderColor: colors.border },
  pillLabel: { fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6 },
  pillValue: { fontSize: 15, fontWeight: '800', color: colors.text, marginTop: 2 },
  codeBox: { backgroundColor: colors.bg, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border },
  code: { fontSize: 12, color: colors.text, fontFamily: MONO, lineHeight: 18 },
  statusBox: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.bg, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.border },
  statusTitle: { fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 2 },
  linkBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start' },
  linkText: { fontSize: 13, fontWeight: '700', color: GOLD },
});
