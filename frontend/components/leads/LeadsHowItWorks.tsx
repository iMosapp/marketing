import React from 'react';
import { View, Text, Modal, ScrollView, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const ACCENT = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const ROWS: { icon: any; color: string; title: string; body: string }[] = [
  { icon: 'hourglass', color: '#FF3B30', title: '"1 waiting" on the tile and the red strip',
    body: 'A lead still needs a human. Either nobody has claimed it yet (it is in the shared queue under Inbox > Leads) or it is yours and the customer\'s last text has not been answered. The strip at the top names them; tap it to claim or reply. The badge clears the moment a real person texts back.' },
  { icon: 'flash', color: '#34C759', title: '"Replied in 4m"',
    body: 'Speed to lead: how long from the lead arriving to the first human text (Jessi\'s auto reply does not count). Green under 5 minutes, orange under an hour, red after that.' },
  { icon: 'refresh', color: '#FF9F0A', title: 'Why "Replied in" can disappear',
    body: 'If the same customer sends another lead (or a test lead is re-sent), the thread is treated as a brand new lead: the clock restarts, the old reply time is hidden and the lead shows as WAITING again until someone texts back.' },
  { icon: 'paper-plane', color: '#007AFF', title: 'QUEUED / SENT / FAILED',
    body: 'Status of the automatic first text to the customer. QUEUED is waiting for store hours (after-hours leads), SENT went out, FAILED could not be delivered (bad number or opt-out).' },
  { icon: 'people', color: ACCENT, title: '"on you" vs a name',
    body: 'WAITING · on you means you claimed it and owe the reply. WAITING · Jake means Jake claimed it and his customer is waiting. Managers see everyone; reps only see their own and the unclaimed queue.' },
];

export const LeadsHowItWorks = ({ visible, onClose, colors }: { visible: boolean; onClose: () => void; colors: any }) => (
  <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
    <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
      <TouchableOpacity style={{ flex: 1 }} onPress={onClose} activeOpacity={1} />
      <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '85%' }} {...tid('leads-help-sheet')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
          <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>How Internet Leads work</Text>
          <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('leads-help-close')}><Ionicons name="close" size={26} color={colors.text} /></TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40, gap: 10 }}>
          {ROWS.map(r => (
            <View key={r.title} style={{ flexDirection: 'row', gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 14 }}>
              <View style={{ width: 34, height: 34, borderRadius: 10, backgroundColor: `${r.color}22`, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name={r.icon} size={17} color={r.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{r.title}</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19, marginTop: 4 }}>{r.body}</Text>
              </View>
            </View>
          ))}
        </ScrollView>
      </View>
    </View>
  </Modal>
);
