import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, KeyboardAvoidingView, Platform, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { showConfirm } from '../../../services/alert';
import { ScreenHeader, HeaderTextButton } from '../../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../../components/inbox/ownership';
import { WidgetPreview } from '../../../components/widget/WidgetPreview';
import { LookTab } from '../../../components/widget/LookTab';
import { DoorsTab } from '../../../components/widget/DoorsTab';
import { JessiTab } from '../../../components/widget/JessiTab';
import { RoutingTab } from '../../../components/widget/RoutingTab';
import { InstallCard } from '../../../components/widget/InstallCard';
import { StatsCard } from '../../../components/widget/StatsCard';
import { Swatch } from '../../../components/widget/parts';

type Tab = 'look' | 'doors' | 'jessi' | 'routing' | 'install';
const TABS: [Tab, string][] = [['look', 'Look'], ['doors', 'Doors'], ['jessi', 'Jessi'], ['routing', 'Routing'], ['install', 'Install']];
const pick = (w: any) => ({ name: w.name, appearance: w.appearance, doors: w.doors, kb: w.kb, copy: w.copy, routing: w.routing, hours: w.hours });

export default function WidgetEditor() {
  const router = useRouter();
  const { id, tab: tabParam } = useLocalSearchParams<{ id: string; tab?: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const { width } = useWindowDimensions();
  const [detail, setDetail] = useState<any>(null);
  const [form, setForm] = useState<any>(null);
  const [facts, setFacts] = useState<any[]>([]);
  const [domains, setDomains] = useState('');
  const [tab, setTab] = useState<Tab>((tabParam as Tab) || 'look');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [swatches, setSwatches] = useState<Swatch[]>([]);
  const [siteUrl, setSiteUrl] = useState('');
  const [matching, setMatching] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [previewPath, setPreviewPath] = useState('');

  const load = useCallback(async () => {
    try {
      const d = (await api.get(`/widgets/${id}`)).data;
      setDetail(d); setForm(pick(d.widget)); setDomains((d.widget.domains || []).join(', ')); setFacts(d.facts || []);
      if (!siteUrl) setSiteUrl(d.store_website || d.widget.last_seen_host || '');
    } catch (e: any) { showToast(errText(e, 'Could not load the widget'), 'error'); if (e?.response?.status === 404) router.back(); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const set = (section: string, patch: any) => { setForm((f: any) => ({ ...f, [section]: { ...f[section], ...patch } })); setDirty(true); };

  const save = async () => {
    setSaving(true);
    try {
      const body = { ...form, domains: domains.split(',').map(s => s.trim()).filter(Boolean) };
      const res = await api.put(`/widgets/${id}`, body);
      setDetail((d: any) => ({ ...d, widget: res.data.widget })); setForm(pick(res.data.widget)); setDirty(false);
      showToast('Widget saved. Your site picks it up within two minutes.', 'success');
    } catch (e: any) { showToast(errText(e, 'Could not save'), 'error', 3500); }
    finally { setSaving(false); }
  };

  const matchSite = async () => {
    setMatching(true);
    try {
      const res = await api.post('/widgets/palette', { url: siteUrl.trim() });
      const sw: Swatch[] = res.data.swatches || [];
      setSwatches(sw);
      if (sw[0]) { set('appearance', { bubble_color: sw[0].hex, text_color: sw[0].text }); showToast(`Found ${sw.length} colors. Bubble set to the strongest one, tap another to switch.`, 'success', 3500); }
      else showToast('No brand colors stood out on that page. Paste the hex from your style guide instead.', 'error', 3500);
    } catch (e: any) { showToast(errText(e, "Couldn't read that site"), 'error', 3500); }
    finally { setMatching(false); }
  };

  const rotate = () => showConfirm('New install code?', 'The line currently on your website stops working the moment you confirm. Copy and paste the new one right after.', async () => {
    try { const res = await api.post(`/widgets/${id}/rotate-key`); setDetail((d: any) => ({ ...d, widget: res.data.widget })); showToast('New code ready. Copy it below.', 'success'); }
    catch (e: any) { showToast(errText(e), 'error'); }
  }, undefined, 'Get new code');

  const disable = () => showConfirm('Turn the widget off?', 'The bubble disappears from your website. Leads already in the Inbox stay put.', async () => {
    try { await api.delete(`/widgets/${id}`); showToast('Widget turned off', 'success'); router.replace('/admin/website-widget' as any); }
    catch (e: any) { showToast(errText(e), 'error'); }
  }, undefined, 'Turn off');

  if (!form || !detail) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Website Widget" testID="widget-editor-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const w = detail.widget;
  const wide = width >= 900;
  const canManage = detail.can_manage !== false;
  const canPreview = tab === 'look' || tab === 'doors' || tab === 'jessi';
  const preview = <WidgetPreview widgetKey={w.key} config={{ appearance: form.appearance, doors: form.doors, copy: form.copy, kb: form.kb, path: tab === 'look' ? previewPath : '', door: tab === 'jessi' && form.doors?.chat?.on ? 'chat' : '' }} colors={colors} height={wide ? 620 : 380} />;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={w.store_name || w.name || 'Website Widget'} subtitle={w.installed ? `Live on ${w.last_seen_host}` : 'Not installed yet'} testID="widget-editor-header"
        right={canManage ? <HeaderTextButton label={saving ? 'Saving…' : 'Save'} onPress={save} disabled={saving || !dirty} testID="widget-save" color={dirty ? GOLD : colors.textSecondary} /> : undefined} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={{ flex: 1, flexDirection: wide ? 'row' : 'column' }}>
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 90, gap: 14 }} keyboardShouldPersistTaps="handled">
            <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
              {TABS.map(([k, l]) => (
                <TouchableOpacity key={k} onPress={() => setTab(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center', backgroundColor: tab === k ? GOLD : 'transparent' }} {...tid(`widget-tab-${k}`)}>
                  <Text style={{ fontSize: 12.5, fontWeight: '800', color: tab === k ? '#111' : colors.textSecondary }} numberOfLines={1}>{l}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {!wide && canPreview ? (
              <View>
                <TouchableOpacity onPress={() => setShowPreview(v => !v)} style={{ alignSelf: 'flex-end', paddingVertical: 4 }} {...tid('widget-preview-toggle')}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{showPreview ? 'Hide preview' : 'Show preview'}</Text>
                </TouchableOpacity>
                {showPreview ? preview : null}
              </View>
            ) : null}
            {tab === 'look' && <LookTab form={form} set={set} colors={colors} swatches={swatches} siteUrl={siteUrl} setSiteUrl={setSiteUrl} onMatchSite={matchSite} matching={matching} previewPath={previewPath} setPreviewPath={setPreviewPath} />}
            {tab === 'doors' && <DoorsTab form={form} set={set} colors={colors} />}
            {tab === 'jessi' && <JessiTab widgetId={String(id)} form={form} set={set} colors={colors} facts={facts} setFacts={setFacts} storeName={detail.store_name} showToast={showToast} canManage={canManage} recentChats={detail.recent_chats || []} chatOn={!!form.doors?.chat?.on} onTurnOnChat={() => set('doors', { chat: { ...(form.doors?.chat || {}), on: true } })} />}
            {tab === 'routing' && <RoutingTab form={form} set={set} colors={colors} reps={detail.reps || []} inboxes={detail.inboxes || []} storeName={detail.store_name} storeHours={detail.store_hours} />}
            {tab === 'install' && (
              <>
                <InstallCard widget={w} colors={colors} domains={domains} setDomains={v => { setDomains(v); setDirty(true); }} onRotate={rotate} onDisable={disable} showToast={showToast} />
                <StatsCard stats={detail.stats || {}} recent={detail.recent_calls || []} colors={colors} />
              </>
            )}
          </ScrollView>
          {wide ? <View style={{ width: 460, padding: 16, paddingLeft: 0 }}>{preview}</View> : null}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
