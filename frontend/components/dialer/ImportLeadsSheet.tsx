import React, { useEffect, useState } from 'react';
import { View, Text, Platform } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as FS from 'expo-file-system/legacy';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, GOLD, GREEN, AMBER, RED, tid } from './shared';

type Result = { added: number; duplicates: number; invalid: number; dnc: number; rows: number; pulled?: number };
type Mode = 'csv' | 'ghl' | 'contacts';
const readText = async (uri: string) => (Platform.OS === 'web' ? (await fetch(uri)).text() : FS.readAsStringAsync(uri));

// Three ways into a campaign: a purchased CSV, a GoHighLevel tag, or the team's own tagged contacts. Every number is DNC-checked on the way in.
export const ImportLeadsSheet = ({ visible, onClose, colors, campaignId, ghlConnected, onDone }: { visible: boolean; onClose: () => void; colors: any; campaignId: string; ghlConnected: boolean; onDone: (added: number) => void }) => {
  const { showToast } = useToast();
  const [mode, setMode] = useState<Mode>('csv');
  const [csv, setCsv] = useState('');
  const [fileName, setFileName] = useState('');
  const [tag, setTag] = useState('');
  const [ghlTags, setGhlTags] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => { if (visible) { setResult(null); setCsv(''); setFileName(''); setTag(''); } }, [visible]);
  useEffect(() => {
    if (visible && mode === 'ghl' && ghlConnected && ghlTags === null) api.get('/ghl/tags').then(r => setGhlTags(r.data.tags || [])).catch(() => setGhlTags([]));
  }, [visible, mode, ghlConnected]);

  const pick = async () => {
    try {
      const r = await DocumentPicker.getDocumentAsync({ type: ['text/csv', 'text/comma-separated-values', 'application/csv', 'text/plain', '*/*'], copyToCacheDirectory: true });
      if (r.canceled || !r.assets?.[0]?.uri) return;
      setCsv(await readText(r.assets[0].uri)); setFileName(r.assets[0].name || 'file.csv'); setResult(null);
    } catch { showToast('Could not read that file', 'error'); }
  };
  const run = async () => {
    setBusy(true);
    try {
      const r = mode === 'csv' ? await api.post(`/dialer/campaigns/${campaignId}/import/csv`, { csv }, { timeout: 180000 })
        : mode === 'ghl' ? await api.post(`/dialer/campaigns/${campaignId}/import/ghl`, { tag: tag || undefined }, { timeout: 180000 })
        : await api.post(`/dialer/campaigns/${campaignId}/import/contacts`, { tag }, { timeout: 120000 });
      setResult(r.data); onDone(r.data.added);
      showToast(`${r.data.added} lead${r.data.added === 1 ? '' : 's'} added`, r.data.added ? 'success' : 'info');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Import failed', 'error'); }
    finally { setBusy(false); }
  };
  const rows = csv.trim() ? Math.max(0, csv.trim().split(/\r?\n/).length - 1) : 0;
  const canRun = !busy && (mode === 'csv' ? rows > 0 : mode === 'contacts' ? !!tag.trim() : ghlConnected);

  return (
    <Sheet visible={visible} onClose={onClose} title="Add leads" colors={colors} testID="import-leads-sheet"
      footer={result ? <GoldButton label="Done" onPress={onClose} testID="import-leads-close" icon="checkmark" />
        : <GoldButton label={mode === 'csv' ? (rows ? `Import ${rows} row${rows === 1 ? '' : 's'}` : 'Pick or paste a CSV') : mode === 'ghl' ? (tag ? `Import GoHighLevel tag "${tag}"` : 'Import every GoHighLevel contact') : (tag ? `Import contacts tagged "${tag}"` : 'Type a tag')} onPress={run} disabled={!canRun} busy={busy} testID="import-leads-run" icon="cloud-download-outline" />}>
      <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
        <Chip label="CSV file" active={mode === 'csv'} onPress={() => setMode('csv')} colors={colors} testID="import-mode-csv" />
        <Chip label="GoHighLevel" active={mode === 'ghl'} onPress={() => setMode('ghl')} colors={colors} testID="import-mode-ghl" />
        <Chip label="My contacts" active={mode === 'contacts'} onPress={() => setMode('contacts')} colors={colors} testID="import-mode-contacts" />
      </View>
      {mode === 'csv' && (
        <>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>First line = column names. We look for <Text style={{ fontWeight: '800', color: colors.text }}>phone</Text> (required), first name, last name, name, company, email, state, city, title, notes. Commas, semicolons or tabs all work. Duplicates and bad numbers are skipped; Do Not Call hits are kept but never dialed.</Text>
          <GoldButton label={fileName ? `Picked ${fileName}` : 'Pick a CSV file'} onPress={pick} outline testID="import-leads-pick" icon="document-attach-outline" />
          <Field label="OR PASTE ROWS" value={csv} onChange={(v: string) => { setCsv(v); setResult(null); }} colors={colors} multiline placeholder={'First Name,Last Name,Company,Phone,State\nSam,Seller,Peak Motors,(801) 555-0100,UT'} testID="import-leads-csv" autoCapitalize="none" />
        </>
      )}
      {mode === 'ghl' && (
        <>
          {!ghlConnected ? <Text style={{ fontSize: 13, color: AMBER, lineHeight: 18 }} {...tid('import-ghl-not-connected')}>GoHighLevel is not connected for this store yet. Tools {'>'} GoHighLevel.</Text> : (
            <>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Pulls contacts from your GoHighLevel location. Pick a tag to import just that list, or leave it empty for everyone (max 5,000).</Text>
              <Label t="TAG" colors={colors} />
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                <Chip label="Everyone" active={!tag} onPress={() => setTag('')} colors={colors} testID="import-ghl-tag-all" small />
                {(ghlTags || []).slice(0, 40).map(t => <Chip key={t} label={t} small active={tag === t} onPress={() => setTag(t)} colors={colors} testID={`import-ghl-tag-${t.replace(/\W+/g, '-')}`} />)}
              </View>
              {ghlTags === null && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Loading tags…</Text>}
              <Field label="OR TYPE A TAG" value={tag} onChange={setTag} colors={colors} placeholder="june-list" testID="import-ghl-tag" autoCapitalize="none" />
            </>
          )}
        </>
      )}
      {mode === 'contacts' && (
        <>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Adds every contact in the team's book that carries this tag (contacts marked Do Not Call are left out).</Text>
          <Field label="CONTACT TAG" value={tag} onChange={setTag} colors={colors} placeholder="Orphan owners" testID="import-contacts-tag" />
        </>
      )}
      {result && (
        <View style={{ backgroundColor: `${GREEN}14`, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: `${GREEN}40`, gap: 4 }} {...tid('import-leads-result')}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{result.added} added</Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>
            {result.pulled !== undefined ? `${result.pulled} pulled from GoHighLevel · ` : `${result.rows} rows · `}{result.duplicates} already in the list · {result.invalid} bad numbers{result.dnc ? ` · ` : ''}
            {!!result.dnc && <Text style={{ color: RED, fontWeight: '700' }}>{result.dnc} on a Do Not Call list (kept, never dialed)</Text>}
          </Text>
        </View>
      )}
    </Sheet>
  );
};
