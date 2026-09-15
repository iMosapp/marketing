import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import * as FS from 'expo-file-system/legacy';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, loadLocales, locales, GOLD, GREEN, RED, AMBER, tid, type Locale } from './shared';

type Result = { dry_run: boolean; total_rows: number; created: number; skipped: number; errors: number; created_items: { row: number; name: string; city: string; locale: string; per_month: Record<string, number>; price: number }[]; skipped_items: { row: number; name: string; reason: string }[]; error_items: { row: number; reason: string }[] };

const readText = async (uri: string) => (Platform.OS === 'web' ? (await fetch(uri)).text() : FS.readAsStringAsync(uri));

// Bulk onboarding: paste or pick a CSV of dealers (Dutch list, semicolons welcome), preview what would happen, then create them all.
export const ImportSheet = ({ visible, onClose, colors, onDone }: { visible: boolean; onClose: () => void; colors: any; onDone: (created: number) => void }) => {
  const { showToast } = useToast();
  const [csv, setCsv] = useState('');
  const [fileName, setFileName] = useState('');
  const [locale, setLocale] = useState('nl-NL');
  const [locs, setLocs] = useState<Locale[]>(locales());
  const [template, setTemplate] = useState<{ columns: string[]; example: string; notes: string } | null>(null);
  const [preview, setPreview] = useState<Result | null>(null);
  const [busy, setBusy] = useState<'preview' | 'import' | null>(null);

  useEffect(() => {
    if (!visible) return;
    setPreview(null);
    loadLocales().then(setLocs).catch(() => {});
    api.get('/shop-clients/import/template').then(r => setTemplate(r.data)).catch(() => {});
  }, [visible]);

  const pick = async () => {
    try {
      const r = await DocumentPicker.getDocumentAsync({ type: ['text/csv', 'text/comma-separated-values', 'application/csv', 'text/plain', '*/*'], copyToCacheDirectory: true });
      if (r.canceled || !r.assets?.[0]?.uri) return;
      setCsv(await readText(r.assets[0].uri)); setFileName(r.assets[0].name || 'file.csv'); setPreview(null);
    } catch (e: any) { showToast('Could not read that file', 'error'); }
  };
  const run = async (dry: boolean) => {
    setBusy(dry ? 'preview' : 'import');
    try {
      const r = await api.post('/shop-clients/import', { csv, locale, dry_run: dry }, { timeout: 120000 });
      setPreview(r.data);
      if (!dry) { showToast(`${r.data.created} client${r.data.created === 1 ? '' : 's'} created`, 'success'); onDone(r.data.created); }
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Import failed', 'error'); }
    finally { setBusy(null); }
  };
  const rows = csv.trim() ? csv.trim().split(/\r?\n/).length - 1 : 0;
  const canRun = rows > 0 && !busy;
  const loc = locs.find(l => l.code === locale);

  return (
    <Sheet visible={visible} onClose={onClose} title="Import dealers from CSV" colors={colors} testID="import-sheet"
      footer={preview && preview.dry_run && preview.created > 0
        ? <GoldButton label={`Create ${preview.created} client${preview.created === 1 ? '' : 's'}`} onPress={() => run(false)} busy={busy === 'import'} testID="import-run" icon="cloud-upload-outline" />
        : preview && !preview.dry_run ? <GoldButton label="Done" onPress={onClose} testID="import-close" icon="checkmark" />
        : <GoldButton label={rows ? `Preview ${rows} row${rows === 1 ? '' : 's'}` : 'Paste or pick a CSV first'} onPress={() => run(true)} disabled={!canRun} busy={busy === 'preview'} testID="import-preview" icon="eye-outline" />}>
      <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>One line per dealer. Column names on the first line; comma or semicolon both work. Only <Text style={{ fontWeight: '800', color: colors.text }}>name</Text> is required. Nothing is billed or called until you send each client a proposal.</Text>
      <View style={{ gap: 6 }}>
        <Label t="COUNTRY & LANGUAGE FOR ROWS WITHOUT ONE" colors={colors} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{locs.map(l => <Chip key={l.code} label={`${l.label} · ${l.language_label}`} small active={locale === l.code} onPress={() => setLocale(l.code)} colors={colors} testID={`import-locale-${l.code}`} />)}</View>
        {!!loc && <Text style={{ fontSize: 12, color: colors.textSecondary }}>{loc.symbol} prices, {loc.timezone} hours, phone numbers read as {loc.country} mobiles ({loc.country === 'NL' ? '06 12345678' : loc.country === 'GB' ? '07123 456789' : 'local format'}).</Text>}
      </View>
      {!!template && (
        <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 10, borderWidth: 1, borderColor: colors.border, gap: 4 }} {...tid('import-template')}>
          <Label t="COLUMNS" colors={colors} />
          <Text style={{ fontSize: 12, color: colors.text, lineHeight: 17 }} selectable>{template.columns.join(', ')}</Text>
          <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }}>{template.notes}</Text>
          <Text style={{ fontSize: 11.5, color: colors.textSecondary, fontStyle: 'italic' }} selectable numberOfLines={2}>e.g. {template.example}</Text>
        </View>
      )}
      <TouchableOpacity onPress={pick} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, height: 44, borderRadius: 12, borderWidth: 1.5, borderColor: GOLD, paddingHorizontal: 12 }} {...tid('import-pick-file')}>
        <Ionicons name="document-attach-outline" size={18} color={GOLD} />
        <Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: GOLD }}>{fileName ? `${fileName} · ${rows} rows` : 'Pick a .csv file'}</Text>
      </TouchableOpacity>
      <Field label="OR PASTE THE CSV" value={csv} onChange={(v: string) => { setCsv(v); setPreview(null); setFileName(''); }} colors={colors} multiline placeholder={'name;city;contact_name;contact_email;contact_phone;sales;service;price\nAutobedrijf Jansen;Utrecht;Pieter Jansen;pieter@jansen.nl;06 12345678;4;2;450'} testID="import-csv" autoCapitalize="none" />
      {preview && (
        <View style={{ gap: 8 }} {...tid('import-result')}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {[[preview.dry_run ? 'Will create' : 'Created', preview.created, GREEN], ['Skipped', preview.skipped, AMBER], ['Errors', preview.errors, RED]].map(([l, n, c]) => (
              <View key={String(l)} style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 10, borderWidth: 1, borderColor: colors.border }} {...tid(`import-stat-${String(l).toLowerCase().replace(/\s/g, '-')}`)}>
                <Text style={{ fontSize: 20, fontWeight: '800', color: c as string }}>{n as number}</Text><Text style={{ fontSize: 10.5, fontWeight: '700', color: colors.textSecondary }}>{String(l).toUpperCase()}</Text>
              </View>
            ))}
          </View>
          {preview.error_items.map(e => <Text key={`e${e.row}`} style={{ fontSize: 12.5, color: RED }} {...tid(`import-error-${e.row}`)}>Row {e.row}: {e.reason}</Text>)}
          {preview.skipped_items.map(s => <Text key={`s${s.row}`} style={{ fontSize: 12.5, color: AMBER }}>Row {s.row} · {s.name}: {s.reason}</Text>)}
          {preview.created_items.slice(0, 30).map(c => (
            <View key={`c${c.row}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 10, padding: 8, borderWidth: 1, borderColor: colors.border }} {...tid(`import-row-${c.row}`)}>
              <Ionicons name="storefront-outline" size={14} color={GOLD} />
              <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: colors.text }} numberOfLines={1}>{c.name}{c.city ? ` · ${c.city}` : ''}</Text>
              <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{c.locale} · {Object.values(c.per_month).reduce((a, b) => a + b, 0)} shops · {locs.find(l => l.code === c.locale)?.symbol || ''}{c.price}</Text>
            </View>
          ))}
          {preview.created_items.length > 30 && <Text style={{ fontSize: 12, color: colors.textSecondary }}>…and {preview.created_items.length - 30} more</Text>}
        </View>
      )}
    </Sheet>
  );
};
