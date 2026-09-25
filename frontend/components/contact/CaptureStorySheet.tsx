import React from 'react';
import { Modal, View, Text, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';
import { PrimaryButton } from '../ui/PrimaryButton';

export type CaptureMode = 'sold' | 'memo';

export const capturePrompts = (mode: CaptureMode) => [
  { icon: 'heart-outline', text: 'Spouse, kids, pets' },
  { icon: 'briefcase-outline', text: 'What they do for work' },
  { icon: 'golf-outline', text: 'Hobbies, teams, weekends' },
  ...(mode === 'sold'
    ? [{ icon: 'car-sport-outline', text: 'What they bought and traded' }, { icon: 'flag-outline', text: 'Why they bought, what mattered most' }]
    : [{ icon: 'chatbubble-ellipses-outline', text: 'What you talked about' }]),
  { icon: 'checkmark-done-outline', text: 'Anything you promised them' },
];

// Explains the voice memo before the recorder starts (push tap / Home "Voice memo" land here).
export const CaptureStorySheet = ({ visible, mode, firstName, vehicle, onStart, onClose }: {
  visible: boolean; mode: CaptureMode; firstName: string; vehicle?: string; onStart: () => void; onClose: () => void;
}) => {
  const { colors } = useThemeStore();
  const first = firstName || 'them';
  const lead = mode === 'sold'
    ? `You just sold ${first}${vehicle ? ` a ${vehicle}` : ''}. Talk for about 60 seconds like you're telling a coworker about them.`
    : `A quick voice memo about ${first}. Talk like you're telling a coworker what you learned.`;
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={{ flex: 1, backgroundColor: '#00000099', justifyContent: 'flex-end' }} activeOpacity={1} onPress={onClose}>
        <TouchableOpacity activeOpacity={1} style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: SPACE.xl, paddingBottom: Platform.OS === 'ios' ? 36 : SPACE.xl, gap: SPACE.lg }} {...tid('capture-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: SPACE.md }}>
            <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="mic" size={26} color="#0B0B0D" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text }} {...tid('capture-sheet-title')}>Tell me about {first}</Text>
              <Text style={{ fontSize: TYPE.caption, color: GOLD, fontWeight: '700', marginTop: 2 }}>Jessi · voice memo · about a minute</Text>
            </View>
            <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('capture-sheet-close')}><Ionicons name="close" size={24} color={colors.textSecondary} /></TouchableOpacity>
          </View>

          <Text style={{ fontSize: TYPE.body, color: colors.text, lineHeight: 22 }} {...tid('capture-sheet-lead')}>
            {lead} I'll transcribe it, pull out the details and save them to {first}'s profile so you never have to remember them.
          </Text>

          <View style={{ backgroundColor: colors.card, borderRadius: RADIUS.lg, borderWidth: 1, borderColor: tint(GOLD, 0.35), padding: SPACE.lg, gap: SPACE.sm }} {...tid('capture-sheet-prompts')}>
            <Text style={{ fontSize: TYPE.label, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>MENTION WHAT YOU CAN</Text>
            {capturePrompts(mode).map(p => (
              <View key={p.text} style={{ flexDirection: 'row', alignItems: 'center', gap: SPACE.md, paddingVertical: 3 }}>
                <Ionicons name={p.icon as any} size={17} color={GOLD} />
                <Text style={{ fontSize: TYPE.body, color: colors.text }}>{p.text}</Text>
              </View>
            ))}
          </View>

          <PrimaryButton label="Start recording" icon="mic" size="lg" full onPress={onStart} testID="capture-sheet-start" />
          <TouchableOpacity onPress={onClose} style={{ alignItems: 'center', paddingVertical: SPACE.sm }} {...tid('capture-sheet-later')}>
            <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: colors.textSecondary }}>Not now</Text>
          </TouchableOpacity>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
};
