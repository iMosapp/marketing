import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import * as FS from 'expo-file-system/legacy';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GoldButton, Field, GOLD, GREEN, RED, AMBER, tid, fmtWhen, type Registry } from '../../components/dialer/shared';

type Entry = { phone: string; source: string; note?: string; added_at: string | null };
const SOURCE: Record<string, string> = { press9: 'Pressed 9 on a call', stop: 'Texted STOP', rep: 'Rep marked on a call', manual: 'Added by a manager', import: 'Imported' };
const CHUNK = 4_000_000;
const readText = async (uri: string) => (Platform.OS === 'web' ? (await fetch(uri)).text() : FS.readAsStringAsync(uri));

// The internal Do Not Call list (kept forever) + the National Registry download. Both are checked at import time and again right before every dial.
export default function DoNotCall() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [q, setQ] = useState('');
  const [phone, setPhone] = useState('');
  const [note, setNote] = useState('');
  const [check, setCheck] = useState<any>(null);
  const [busy, setBusy] = useState<'add' | 'import' | 'check' | null>(null);
  const [progress, setProgress] = useState('');

  const load = useCallback(async () => {
    try { const r = await api.get('/dialer/dnc', { params: { q: q || undefined, limit: 200 } }); setEntries(r.data.entries); setTotal(r.data.total); setRegistry(r.data.registry); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); setEntries([]); }
  }, [q]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const add = async () => {
    setBusy('add');
    try { const r = await api.post('/dialer/dnc', { phone, note }); showToast(r.data.added ? `${r.data.phone} will never be dialed` : 'Already on the list', 'success'); setPhone(''); setNote(''); load(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not add', 'error'); }
    finally { setBusy(null); }
  };
  const lookup = async () => {
    setBusy('check');
    try { const r = await api.get(`/dialer/dnc/check/${encodeURIComponent(phone)}`); setCheck(r.data); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not check', 'error'); }
    finally { setBusy(null); }
  };
  const importRegistry = async () => {
    try {
      const r = await DocumentPicker.getDocumentAsync({ type: ['text/plain', 'text/csv', '*/*'], copyToCacheDirectory: true });
      if (r.canceled || !r.assets?.[0]?.uri) return;
      setBusy('import');
      const text = await readText(r.assets[0].uri);
      let added = 0, lines = 0;
      for (let i = 0; i < text.length; i += CHUNK) {
        let end = Math.min(text.length, i + CHUNK);
        if (end < text.length) { const nl = text.lastIndexOf('\n', end); if (nl > i) end = nl; }
        setProgress(`Loading… ${Math.round((end / text.length) * 100)}%`);
        const res = await api.post('/dialer/dnc/registry', { text: text.slice(i, end) }, { timeout: 300000 });
        added += res.data.added; lines += res.data.lines; i = end - CHUNK;
      }
      showToast(`${added.toLocaleString()} new numbers loaded (${lines.toLocaleString()} in the file)`, 'success'); load();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Import failed', 'error'); }
    finally { setBusy(null); setProgress(''); }
  };
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border } as const;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Do Not Call" subtitle="Checked when a list is imported and again right before every dial" testID="dnc-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }}>
        <View style={{ ...card, gap: 8 }} {...tid('dnc-registry-card')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Ionicons name="flag" size={18} color={registry?.numbers ? GREEN : AMBER} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>National Do Not Call Registry</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} {...tid('dnc-registry-stats')}>{registry?.numbers ? `${registry.numbers.toLocaleString()} numbers · ${registry.areas.length} area code${registry.areas.length === 1 ? '' : 's'} · loaded ${fmtWhen(registry.last_import_at)}${registry.stale ? ' · OLDER THAN 31 DAYS' : ''}` : 'Not loaded. Consumer lists cannot be legally dialed without it.'}</Text>
            </View>
          </View>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }}>Get your Subscription Account Number at telemarketing.donotcall.gov (first 5 area codes are free), download the area codes you call as text files, and load them here. Re-load at least every 31 days (the law) and re-check your campaigns afterwards.</Text>
          <GoldButton label={busy === 'import' ? (progress || 'Loading…') : 'Load a registry file'} onPress={importRegistry} busy={busy === 'import'} outline testID="dnc-registry-import" icon="cloud-upload-outline" />
          {!!registry?.areas.length && <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Area codes: {registry.areas.join(', ')}</Text>}
        </View>

        <View style={{ ...card, gap: 10 }} {...tid('dnc-add-card')}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Add a number / check a number</Text>
          <Field value={phone} onChange={setPhone} colors={colors} placeholder="(801) 555-0100" keyboardType="phone-pad" testID="dnc-phone" />
          <Field value={note} onChange={setNote} colors={colors} placeholder="Why (optional)" testID="dnc-note" />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View style={{ flex: 1 }}><GoldButton label="Check" onPress={lookup} outline busy={busy === 'check'} disabled={!phone.trim()} testID="dnc-check" icon="search" /></View>
            <View style={{ flex: 1 }}><GoldButton label="Never call" onPress={add} busy={busy === 'add'} disabled={!phone.trim()} testID="dnc-add" icon="ban" color={RED} /></View>
          </View>
          {check && (
            <Text style={{ fontSize: 12.5, color: check.blocked ? RED : GREEN, fontWeight: '700' }} {...tid('dnc-check-result')}>
              {check.phone}: {check.status === 'internal' ? 'on your Do Not Call list' : check.status === 'registry' ? 'on the National Registry' : check.status === 'unscrubbed' ? 'not on your list (registry not loaded)' : 'clear'}{check.state ? ` · ${check.state}` : ''}{check.tz ? ` · ${check.tz}` : ''}
            </Text>
          )}
        </View>

        <View style={card}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Your list · {total}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, marginBottom: 8 }}>Press 9 on the abandon message, STOP texts and rep marks land here automatically and stay forever.</Text>
          <TextInput value={q} onChangeText={setQ} placeholder="Search by number" placeholderTextColor={colors.textSecondary} keyboardType="phone-pad" style={{ backgroundColor: colors.bg, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, color: colors.text, fontSize: 14, borderWidth: 1, borderColor: colors.border, marginBottom: 6 }} {...tid('dnc-search')} />
          {entries === null ? <ActivityIndicator color={GOLD} style={{ marginVertical: 20 }} /> : entries.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20 }} {...tid('dnc-empty')}>Nothing here yet.</Text>
            : entries.map(e => (
              <View key={e.phone} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`dnc-entry-${e.phone.replace('+', '')}`)}>
                <Ionicons name="ban" size={16} color={RED} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{e.phone}</Text>
                  <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{SOURCE[e.source] || e.source} · {fmtWhen(e.added_at)}{e.note ? ` · ${e.note}` : ''}</Text>
                </View>
              </View>
            ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
