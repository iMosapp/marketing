import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Platform, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import * as Sharing from 'expo-sharing';
import { File as ExpoFile, Paths } from 'expo-file-system';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Sheet } from '../../mystery-shops/shared';
import { GOLD, detail, tid, type Roundtable } from '../shared';

const slug = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48) || 'roundtable';

const Option = ({ icon, title, sub, onPress, busy, colors, testID }: { icon: any; title: string; sub: string; onPress: () => void; busy: boolean; colors: any; testID: string }) => (
  <TouchableOpacity onPress={onPress} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid(testID)}>
    <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}>{busy ? <ActivityIndicator color={GOLD} size="small" /> : <Ionicons name={icon} size={20} color={GOLD} />}</View>
    <View style={{ flex: 1 }}><Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }}>{title}</Text><Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{sub}</Text></View>
    <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
  </TouchableOpacity>
);

// EXPORT: the roundtable record (question, room, brief, dissent register, every assessment and challenge) as PDF or Markdown. Rendered server-side from the stored document.
export const ExportRoundtable = ({ rt, colors }: { rt: Roundtable; colors: any }) => {
  const { showToast } = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const name = `roundtable-${slug(rt.title)}-${rt.id.slice(-6)}`;
  const path = (ext: string) => `/command-center/team/roundtables/${rt.id}/export.${ext}`;
  const download = async (ext: 'pdf' | 'md') => {
    setBusy(ext);
    try {
      const res = await api.get(path(ext), { responseType: Platform.OS === 'web' ? 'blob' : ext === 'pdf' ? 'arraybuffer' : 'text' });
      if (Platform.OS === 'web') {
        const url = URL.createObjectURL(res.data);
        const a = document.createElement('a'); a.href = url; a.download = `${name}.${ext}`; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
        showToast(ext === 'pdf' ? 'PDF downloaded' : 'Markdown downloaded', 'success');
      } else {
        const file = new ExpoFile(Paths.cache, `${name}.${ext}`);
        if (ext === 'pdf') file.write(new Uint8Array(res.data)); else file.write(String(res.data));
        if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(file.uri, { mimeType: ext === 'pdf' ? 'application/pdf' : 'text/markdown', dialogTitle: 'Share the brief' });
      }
      setOpen(false);
    } catch (e: any) { showToast(detail(e, 'Could not build the export'), 'error'); } finally { setBusy(null); }
  };
  const copy = async () => {
    setBusy('copy');
    try { const res = await api.get(path('md'), { responseType: 'text' }); await Clipboard.setStringAsync(String(res.data)); showToast('Markdown copied', 'success'); setOpen(false); }
    catch (e: any) { showToast(detail(e, 'Could not copy'), 'error'); } finally { setBusy(null); }
  };
  return (
    <>
      <TouchableOpacity onPress={() => setOpen(true)} style={{ padding: 6 }} {...tid('cc-rt-export')}><Ionicons name="share-outline" size={21} color={colors.text} /></TouchableOpacity>
      <Sheet visible={open} onClose={() => setOpen(false)} title="Export the brief" colors={colors} testID="cc-rt-export-sheet">
        <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>The full record: the question, the room, the executive brief, the dissent register, every assessment and the challenge round. Exactly as it stands; nothing is rewritten.</Text>
        <Option icon="document-text" title="Download PDF" sub="Clean brief to share with a partner, investor or your own team" onPress={() => download('pdf')} busy={busy === 'pdf'} colors={colors} testID="cc-rt-export-pdf" />
        <Option icon="logo-markdown" title="Download Markdown" sub={`${name}.md, for Notion, Obsidian or a repo`} onPress={() => download('md')} busy={busy === 'md'} colors={colors} testID="cc-rt-export-md" />
        <Option icon="copy" title="Copy as Markdown" sub="Paste it anywhere" onPress={copy} busy={busy === 'copy'} colors={colors} testID="cc-rt-export-copy" />
      </Sheet>
    </>
  );
};
