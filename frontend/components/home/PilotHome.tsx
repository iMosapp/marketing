import React, { useCallback, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { AvatarButton } from '../account/AvatarButton';
import { NotificationBell } from '../notifications/NotificationBell';
import { UniversalShareModal } from '../UniversalShareModal';
import { PilotChecklist, PilotChecklistData, PilotStep } from './PilotChecklist';
import { GOLD, RADIUS, SPACE, tid, tint } from '../ui/tokens';

type Tile = { key: string; title: string; sub: string; icon: any; color: string; route: string };

const HERO: Tile = { key: 'card', title: 'Digital Card', sub: 'Your photo, title and bio. This is what customers see.', icon: 'id-card', color: GOLD, route: '/my-account' };
const TILES: Tile[] = [
  { key: 'contacts', title: 'Contacts', sub: 'Everyone you have met', icon: 'people', color: '#007AFF', route: '/(tabs)/contacts' },
  { key: 'share', title: 'Share', sub: 'Text your card or show the QR', icon: 'share-social', color: '#34C759', route: 'share' },
  { key: 'memo', title: 'Voice Memo', sub: 'Say what you learned, we remember it', icon: 'mic', color: '#FF9500', route: '/voice-memos?record=1' },
  { key: 'messages', title: 'Messages', sub: 'Texts with your customers', icon: 'chatbubbles', color: '#5856D6', route: '/(tabs)/inbox' },
];

const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; };

/** Stage 3: the pilot customer's Home. Five things to do every day plus the setup checklist; nothing else. */
export function PilotHome() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const [checklist, setChecklist] = useState<PilotChecklistData | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [share, setShare] = useState<{ visible: boolean; qr: boolean }>({ visible: false, qr: false });

  const load = useCallback(async () => {
    try {
      const res = await api.get('/pilot/checklist');
      setChecklist(res.data);
    } catch { /* legacy or not-yet-pilot accounts simply show no checklist */ }
    finally { setLoaded(true); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const refresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const baseUrl = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';
  const cardUrl = `${baseUrl}/card/${user?._id || ''}`;
  const go = (route: string) => {
    if (route === 'share') { setShare({ visible: true, qr: false }); return; }
    router.push(route as any);
  };
  const onStep = (s: PilotStep) => go(s.route);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('home-pilot')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: SPACE.lg, paddingTop: 8, paddingBottom: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
        <View style={{ marginRight: 12 }}><AvatarButton size={38} /></View>
        <View style={{ flex: 1 }}>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>
            {greeting()}{(user as any)?.first_name ? `, ${(user as any).first_name}` : ''}
          </Text>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 28, fontWeight: '800', color: colors.text }}>Home</Text>
        </View>
        <TouchableOpacity onPress={() => setShare({ visible: true, qr: true })} activeOpacity={0.7} style={{ padding: 6 }} {...tid('pilot-header-qr')}>
          <Ionicons name="qr-code-outline" size={20} color={colors.textSecondary} />
        </TouchableOpacity>
        <NotificationBell />
      </View>

      <ScrollView
        contentContainerStyle={{ paddingTop: SPACE.lg, paddingBottom: 120 }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={GOLD} colors={[GOLD]} />}
      >
        {!loaded ? (
          <View style={{ paddingVertical: 24, alignItems: 'center' }}><ActivityIndicator color={GOLD} /></View>
        ) : checklist ? (
          <PilotChecklist data={checklist} colors={colors} onStep={onStep} />
        ) : null}

        {(() => {
          const pp = (user as any)?.pilot_program;
          const owner = !!(user as any)?.pilot_owner;
          if (!owner || !pp || !(pp.state === 'completed' || (pp.state === 'active' && typeof pp.days_left === 'number' && pp.days_left <= 14))) return null;
          const over = pp.state === 'completed';
          return (
            <TouchableOpacity onPress={() => router.push('/settings/billing' as any)} activeOpacity={0.85} {...tid('pilot-banner')}
              style={{ marginHorizontal: SPACE.lg, marginBottom: SPACE.lg, padding: SPACE.md, borderRadius: RADIUS.md, borderWidth: 1, borderColor: tint(GOLD, 0.45), backgroundColor: tint(GOLD, 0.1), flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Ionicons name="time-outline" size={18} color={GOLD} />
              <Text style={{ flex: 1, fontSize: 13.5, color: colors.text, lineHeight: 18 }}>
                {over ? 'Your complimentary pilot has ended. Nothing was charged.' : `Your complimentary pilot ends in ${pp.days_left} day${pp.days_left === 1 ? '' : 's'}.`}
                <Text style={{ fontWeight: '700', color: GOLD }}> Continue →</Text>
              </Text>
            </TouchableOpacity>
          );
        })()}

        <Text style={{ fontSize: 11, fontWeight: '800', letterSpacing: 1.4, color: colors.textSecondary, marginHorizontal: SPACE.lg, marginBottom: SPACE.sm }}>EVERY DAY</Text>

        <TouchableOpacity
          onPress={() => go(HERO.route)}
          activeOpacity={0.85}
          style={{ marginHorizontal: SPACE.lg, marginBottom: SPACE.md, padding: SPACE.xl, borderRadius: RADIUS.xl, backgroundColor: tint(GOLD, 0.12), borderWidth: 1.5, borderColor: tint(GOLD, 0.45), flexDirection: 'row', alignItems: 'center', gap: 16 }}
          {...tid(`pilot-tile-${HERO.key}`)}
        >
          <View style={{ width: 56, height: 56, borderRadius: 16, backgroundColor: tint(GOLD, 0.2), alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={HERO.icon} size={28} color={GOLD} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>{HERO.title}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 3, lineHeight: 18 }}>{HERO.sub}</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={GOLD} />
        </TouchableOpacity>

        <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: SPACE.lg - 6 }}>
          {TILES.map((t) => (
            <View key={t.key} style={{ width: '50%', padding: 6 }}>
              <TouchableOpacity
                onPress={() => go(t.route)}
                activeOpacity={0.85}
                style={{ minHeight: 132, padding: SPACE.lg, borderRadius: RADIUS.lg, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, justifyContent: 'space-between' }}
                {...tid(`pilot-tile-${t.key}`)}
              >
                <View style={{ width: 44, height: 44, borderRadius: 13, backgroundColor: tint(t.color, 0.16), alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={t.icon} size={23} color={t.color} />
                </View>
                <View>
                  <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{t.title}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }} numberOfLines={2}>{t.sub}</Text>
                </View>
              </TouchableOpacity>
            </View>
          ))}
        </View>

        <TouchableOpacity
          onPress={() => router.push('/report-bug?from=home' as any)}
          activeOpacity={0.7}
          style={{ marginHorizontal: SPACE.lg, marginTop: SPACE.xl, flexDirection: 'row', alignItems: 'center', gap: 10, padding: SPACE.md, borderRadius: RADIUS.md, borderWidth: 1, borderColor: colors.border, borderStyle: 'dashed' }}
          {...tid('pilot-feedback-link')}
        >
          <Ionicons name="chatbox-ellipses-outline" size={18} color={colors.textSecondary} />
          <Text style={{ flex: 1, fontSize: 13.5, color: colors.textSecondary }}>Have a question or hit a snag? <Text style={{ fontWeight: '700', color: GOLD }}>Send feedback</Text></Text>
        </TouchableOpacity>
      </ScrollView>

      <UniversalShareModal
        visible={share.visible}
        onClose={() => { setShare({ visible: false, qr: false }); load(); }}
        title={share.qr ? 'Your Card QR' : 'Share My Card'}
        subtitle={share.qr ? 'Have them scan it. Your card opens instantly' : 'Choose how to share your digital card'}
        shareUrl={cardUrl}
        shareText={`Check out my digital business card: ${cardUrl}`}
        showPreview={!share.qr}
        previewUrl={cardUrl}
        showQR
        startWithQR={share.qr}
        vCardUserId={user?._id}
        userId={user?._id}
        eventType={share.qr ? 'card_qr_shown' : 'digital_card_shared'}
        showScanStats={share.qr}
      />
    </SafeAreaView>
  );
}
