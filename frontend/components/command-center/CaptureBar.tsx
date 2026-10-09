import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import VoiceTextInput from '../VoiceTextInput';
import { GOLD, detail, tid } from './shared';

type Props = { colors: any; onCaptured?: () => void; sticky?: boolean };

// Capture an idea in one action: type or speak, save, stay where you are. Ideas land in the vault as "captured", never as work.
export const CaptureBar = ({ colors, onCaptured, sticky }: Props) => {
  const { showToast } = useToast();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const save = async () => {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    try {
      await api.post('/command-center/ideas', { title: t.length > 120 ? t.slice(0, 117) + '...' : t, description: t.length > 120 ? t : '', source: 'text' });
      setText(''); showToast('Saved to the Idea Vault'); onCaptured && onCaptured();
    } catch (e: any) { showToast(detail(e, 'Could not save the idea'), 'error'); }
    finally { setBusy(false); }
  };
  return (
    <View style={[{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: GOLD + '66', padding: 12, gap: 8 }, sticky && { position: 'absolute', left: 12, right: 12, bottom: Platform.OS === 'web' ? 12 : 24, shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 6 }]} {...tid('cc-capture')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="bulb" size={16} color={GOLD} />
        <Text style={{ fontSize: 11.5, fontWeight: '800', letterSpacing: 1.2, color: colors.textSecondary }}>CAPTURE AN IDEA</Text>
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
        <View style={{ flex: 1 }}>
          <VoiceTextInput value={text} onChangeText={setText} placeholder="Type it or tap the mic. One sentence is enough." showVoice voiceAppend multiline onSubmitEditing={save} blurOnSubmit testID="cc-capture-input" />
        </View>
        <TouchableOpacity onPress={save} disabled={!text.trim() || busy} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('cc-capture-save')}>
          <Ionicons name="arrow-up" size={20} color={text.trim() ? '#1C1C1E' : colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
};
