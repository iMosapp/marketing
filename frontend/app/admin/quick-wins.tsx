// Quick wins to demo live with a prospect or a brand-new user: pick one, do it on their phone, under two minutes each.
import React from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const WINS = [
  { id: 'card', icon: 'id-card', color: GOLD, title: 'Text them your Digital Card', feel: 'They tap once and your photo, number and socials are saved in their phone. Then show them theirs.', route: '/quick-send/digitalcard', cta: 'Send my card now' },
  { id: 'review', icon: 'star', color: '#FFD60A', title: 'Send a review link in one tap', feel: 'The link lands as a text, the review posts to Google. Managers see this as instant five-star reviews.', route: '/quick-send/review', cta: 'Send a review link' },
  { id: 'jessi', icon: 'sparkles', color: '#AF52DE', title: 'Ask Jessi about a customer', feel: '"Who did I talk to last week that has not bought?" Jessi answers in a sentence. Nobody expects it.', route: '/jessie', cta: 'Open Ask Jessi' },
  { id: 'memo', icon: 'mic', color: '#34C759', title: 'Voice memo becomes the follow-up text', feel: 'Talk for 20 seconds after a test drive, Jessi writes the follow-up. The lazy way to never drop a lead.', route: '/voice-memos', cta: 'Record a memo' },
];

export default function QuickWinsScreen() {
  const router = useRouter();
  const { colors } = useThemeStore();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Quick wins" subtitle="Show them, do not tell them" testID="quick-wins-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 12 }} {...tid('quick-wins')}>
        <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20, marginBottom: 4 }}>
          Pick one. Do it with them on their phone. Each takes under two minutes and they feel it immediately.
        </Text>
        {WINS.map((w, i) => (
          <View key={w.id} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10 }} {...tid(`quick-win-${w.id}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: `${w.color}22`, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name={w.icon as any} size={20} color={w.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, fontWeight: '700', color: GOLD, letterSpacing: 1 }}>WIN {i + 1}</Text>
                <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{w.title}</Text>
              </View>
            </View>
            <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20 }}>{w.feel}</Text>
            <TouchableOpacity onPress={() => router.push(w.route as any)} activeOpacity={0.85}
              style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: GOLD, borderRadius: 999, paddingVertical: 9, paddingHorizontal: 16 }}
              {...tid(`quick-win-${w.id}-go`)}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: '#000' }}>{w.cta}</Text>
              <Ionicons name="arrow-forward" size={14} color="#000" />
            </TouchableOpacity>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
