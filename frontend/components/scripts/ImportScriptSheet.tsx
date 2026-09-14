import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, Platform, ActivityIndicator, TextInput, KeyboardAvoidingView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import api from '../../services/api';
import { GOLD, tid, type Persona } from './shared';

export type ImportedScript = { title: string; category: string; direction?: 'inbound' | 'outbound'; runtime: string; purpose: string; body: string; success_points: string[]; persona: Persona };
type PanelProps = { colors: any; onImported: (draft: ImportedScript) => void; onCancel?: () => void; autoFocus?: boolean; onFocusInput?: (node: any) => void; industry?: string; department?: string };
type Props = { visible: boolean; colors: any; onClose: () => void; onImported: (draft: ImportedScript) => void };

// Paste a script you already use (Word, email, notes): Jessi shapes it into the editor fields, nothing is saved until you tap Save.
// The panel is plain content so it can live INSIDE another sheet (stacking two iOS modals freezes the app); the Sheet wraps it for full screens.
export const ImportScriptPanel = ({ colors, onImported, onCancel, autoFocus = true, onFocusInput, industry, department }: PanelProps) => {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ready = text.trim().length >= 40;
  const inputRef = React.useRef<TextInput>(null);

  const run = async () => {
    if (!ready || busy) return;
    setBusy(true); setError('');
    try {
      const res = await api.post('/scripts/import', { text: text.trim(), industry, department }, { timeout: 120000 });
      onImported(res.data); setText('');
    } catch (e: any) { setError(e?.response?.data?.detail || 'Jessi could not format that, try again'); }
    finally { setBusy(false); }
  };

  // Attach a PDF / Word / text file: the server pulls the text out, then Jessi formats it the same way as a paste.
  const [fileName, setFileName] = useState('');
  const attach = async () => {
    if (busy) return;
    setError('');
    let picked: DocumentPicker.DocumentPickerAsset | null = null;
    try {
      const r = await DocumentPicker.getDocumentAsync({ type: ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', '*/*'], copyToCacheDirectory: true, multiple: false });
      if (r.canceled || !r.assets?.[0]?.uri) return;
      picked = r.assets[0];
    } catch { setError('Could not open the file picker'); return; }
    setBusy(true); setFileName(picked.name || 'file');
    try {
      const form = new FormData();
      const name = picked.name || 'script.pdf';
      if (Platform.OS === 'web') { const blob = await (await fetch(picked.uri)).blob(); form.append('file', blob, name); }
      else form.append('file', { uri: picked.uri, name, type: picked.mimeType || 'application/octet-stream' } as any);
      const res = await api.post('/scripts/import-file', form, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 180000, params: { industry, department } });
      onImported(res.data); setText(''); setFileName('');
    } catch (e: any) { setError(e?.response?.data?.detail || 'Jessi could not read that file, try pasting the text'); }
    finally { setBusy(false); }
  };

  return (
    <View style={{ gap: 12 }} {...tid('script-import-sheet')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Ionicons name="clipboard-outline" size={22} color={GOLD} />
        <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }}>Paste an existing script</Text>
        {onCancel && <TouchableOpacity onPress={onCancel} disabled={busy} hitSlop={10} {...tid('script-import-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>}
      </View>
      <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Copy it from Word, an email, a PDF or your notes and paste it here. Jessi keeps your words, adds merge fields like {'{first_name}'}, pulls out what a great call hits and builds a practice customer. You review everything before it saves.</Text>
      <TextInput ref={inputRef} value={text} onChangeText={setText} multiline editable={!busy} placeholder="Paste the whole script here…" placeholderTextColor={colors.textSecondary} autoFocus={autoFocus}
        onFocus={() => onFocusInput?.(inputRef.current)}
        style={{ minHeight: 160, maxHeight: 300, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, color: colors.text, fontSize: 15, lineHeight: 21, textAlignVertical: 'top' }} {...tid('script-import-text')} />
      {!!error && <Text style={{ fontSize: 13, color: '#FF453A', fontWeight: '600' }} {...tid('script-import-error')}>{error}</Text>}
      <TouchableOpacity onPress={run} disabled={!ready || busy} style={{ height: 48, borderRadius: 14, backgroundColor: ready ? GOLD : colors.card, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('script-import-run')}>
        {busy ? <><ActivityIndicator size="small" color="#111" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Jessi is formatting it…</Text></>
          : <><Ionicons name="sparkles" size={16} color={ready ? '#111' : colors.textSecondary} /><Text style={{ fontSize: 15, fontWeight: '800', color: ready ? '#111' : colors.textSecondary }}>{ready ? 'Let Jessi format it' : 'Paste at least a few lines first'}</Text></>}
      </TouchableOpacity>
      <TouchableOpacity onPress={attach} disabled={busy} style={{ height: 44, borderRadius: 14, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: busy ? 0.6 : 1 }} {...tid('script-import-file')}>
        <Ionicons name="document-attach-outline" size={16} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>{busy && fileName ? `Reading ${fileName}…` : 'Or attach a PDF, Word or text file'}</Text>
      </TouchableOpacity>
      {busy && <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center' }}>Usually 10 to 20 seconds</Text>}
    </View>
  );
};

export const ImportScriptSheet = ({ visible, colors, onClose, onImported }: Props) => (
  <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={onClose} />
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, paddingBottom: Platform.OS === 'ios' ? 30 : 18 }}>
          <ImportScriptPanel colors={colors} onImported={onImported} onCancel={onClose} />
        </View>
      </View>
    </KeyboardAvoidingView>
  </Modal>
);
