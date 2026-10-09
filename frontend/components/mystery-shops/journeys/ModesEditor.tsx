import React from 'react';
import { View, Text } from 'react-native';
import { Label, Chip } from '../shared';
import { MODE_LABEL, MODE_HINT, VOICE_LABEL, type Mode, type Modes, type VoiceMode } from './shared';

type Props = { modes: Modes; onChange: (m: Modes) => void; colors: any; disabled?: boolean; prefix?: string };

// How the shopper answers on each channel. Approve is the default: nothing the AI writes leaves without a human looking at it.
export const ModesEditor = ({ modes, onChange, colors, disabled, prefix = 'modes' }: Props) => {
  const set = (k: keyof Modes, v: Mode | VoiceMode) => { if (!disabled) onChange({ ...modes, [k]: v } as Modes); };
  const rowFor = (k: 'email' | 'sms', title: string) => (
    <View style={{ gap: 6 }} key={k}>
      <Label t={title} colors={colors} />
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
        {(['approve', 'auto', 'observe'] as Mode[]).map(m => <Chip key={m} small label={MODE_LABEL[m]} active={modes[k] === m} onPress={() => set(k, m)} colors={colors} testID={`${prefix}-${k}-${m}`} />)}
      </View>
      <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{MODE_HINT[modes[k]]}</Text>
    </View>
  );
  return (
    <View style={{ gap: 12 }}>
      {rowFor('email', 'WHEN THE STORE EMAILS')}
      {rowFor('sms', 'WHEN THE STORE TEXTS')}
      <View style={{ gap: 6 }}>
        <Label t="WHEN THE STORE CALLS" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
          {(['voicemail', 'live'] as VoiceMode[]).map(m => <Chip key={m} small label={VOICE_LABEL[m]} active={modes.voice === m} onPress={() => set('voice', m)} colors={colors} testID={`${prefix}-voice-${m}`} />)}
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{modes.voice === 'voicemail' ? 'Calls go to a voicemail greeting; the message is recorded, transcribed and timed. Nobody talks to a bot.' : 'The AI shopper answers the phone in persona (GPT-Live). Needs the live voice permission on the account.'}</Text>
      </View>
    </View>
  );
};
