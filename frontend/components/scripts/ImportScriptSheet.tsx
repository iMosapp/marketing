import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, Platform, ActivityIndicator, TextInput, KeyboardAvoidingView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, type Persona } from './shared';

export type ImportedScript = { title: string; category: string; direction?: 'inbound' | 'outbound'; runtime: string; purpose: string; body: string; success_points: string[]; persona: Persona };
type Props = { visible: boolean; colors: any; onClose: () => void; onImported: (draft: ImportedScript) => void };

// Paste a script you already use (Word, email, notes): Jessi shapes it into the editor fields, nothing is saved until you tap Save.
export const ImportScriptSheet = ({ visible, colors, onClose, onImported }: Props) => {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ready = text.trim().length >= 40;

  const run = async () => {
    if (!ready || busy) return;
    setBusy(true); setError('');
    try {
      const res = await api.post('/scripts/import', { text: text.trim() }, { timeout: 120000 });
      onImported(res.data); setText('');
    } catch (e: any) { setError(e?.response?.data?.detail || 'Jessi could not format that, try again'); }
    finally { setBusy(false); }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={busy ? undefined : onClose} />
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, paddingBottom: Platform.OS === 'ios' ? 30 : 18, gap: 12 }} {...tid('script-import-sheet')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Ionicons name="clipboard-outline" size={22} color={GOLD} />
              <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }}>Paste an existing script</Text>
              <TouchableOpacity onPress={onClose} disabled={busy} hitSlop={10} {...tid('script-import-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
            </View>
            <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Copy it from Word, an email or your notes and paste it here. Jessi keeps your words, adds merge fields like {'{first_name}'}, pulls out what a great call hits and builds a practice customer. You review everything before it saves.</Text>
            <TextInput value={text} onChangeText={setText} multiline editable={!busy} placeholder="Paste the whole script here…" placeholderTextColor={colors.textSecondary} autoFocus
              style={{ minHeight: 200, maxHeight: 340, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, color: colors.text, fontSize: 15, lineHeight: 21, textAlignVertical: 'top' }} {...tid('script-import-text')} />
            {!!error && <Text style={{ fontSize: 13, color: '#FF453A', fontWeight: '600' }} {...tid('script-import-error')}>{error}</Text>}
            <TouchableOpacity onPress={run} disabled={!ready || busy} style={{ height: 48, borderRadius: 14, backgroundColor: ready ? GOLD : colors.card, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('script-import-run')}>
              {busy ? <><ActivityIndicator size="small" color="#111" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Jessi is formatting it…</Text></>
                : <><Ionicons name="sparkles" size={16} color={ready ? '#111' : colors.textSecondary} /><Text style={{ fontSize: 15, fontWeight: '800', color: ready ? '#111' : colors.textSecondary }}>Let Jessi format it</Text></>}
            </TouchableOpacity>
            {busy && <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center' }}>Usually 10 to 20 seconds</Text>}
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
