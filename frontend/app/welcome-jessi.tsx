/**
 * First login after Jessi onboarded someone by text: no product tour, just "here's what I built for you" and one first win.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, Image, ActivityIndicator, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { resolvePhotoUrl } from '../utils/photoUrl';
import { PrimaryButton } from '../components/ui/PrimaryButton';
import { GOLD, RADIUS, SPACE, TYPE, tid, tint } from '../components/ui/tokens';

type Win = { key: string; title: string; body: string; route: string; icon: string };
type Me = { first_name: string; name: string; title: string; photo_url?: string | null; bio: string; tone: string; specialties: string[]; what_i_sell: string; hometown: string; jessi_number: string; first_win: Win; other_wins: Win[]; welcome_pending: boolean };

export default function WelcomeJessi() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const updateUser = useAuthStore(s => s.updateUser);
  const [me, setMe] = useState<Me | null>(null);
  const [busy, setBusy] = useState('');

  useEffect(() => { api.get('/onboarding-jessi/me').then(r => setMe(r.data)).catch(() => router.replace('/(tabs)/home' as any)); }, []);

  const go = async (which: string, route: string) => {
    setBusy(which);
    try { await api.post('/onboarding-jessi/me/first-success', { which }); } catch {}
    updateUser({ jessi_welcome_pending: false, onboarding_complete: true } as any);
    router.replace(route as any);
  };

  if (!me) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}><ActivityIndicator color={GOLD} style={{ marginTop: 80 }} /></SafeAreaView>;
  const photo = resolvePhotoUrl(me.photo_url || null);
  const chips = [me.title, me.hometown ? `From ${me.hometown}` : '', me.tone ? `${me.tone} tone` : '', ...(me.specialties || []).slice(0, 3)].filter(Boolean);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} {...tid('welcome-jessi-page')}>
      <ScrollView contentContainerStyle={{ padding: SPACE.xl, paddingBottom: 60, gap: SPACE.lg }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="sparkles" size={18} color={GOLD} />
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>JESSI BUILT THIS FOR YOU</Text>
        </View>
        <Text style={{ fontSize: 30, fontWeight: '800', color: colors.text, lineHeight: 36 }} {...tid('welcome-jessi-title')}>Welcome in, {me.first_name}.</Text>
        <Text style={{ fontSize: TYPE.body, color: colors.textSecondary, lineHeight: 22 }}>
          Everything from our call is already in here: your card, your profile and the assistant that texts the way you do. Nothing to fill out.
        </Text>

        <View style={{ backgroundColor: colors.card, borderRadius: RADIUS.xl, borderWidth: 1, borderColor: colors.border, padding: SPACE.xl, alignItems: 'center', gap: SPACE.md }} {...tid('welcome-jessi-card')}>
          {photo ? <Image source={{ uri: photo }} style={{ width: 104, height: 104, borderRadius: 52, borderWidth: 3, borderColor: GOLD }} {...tid('welcome-jessi-photo')} /> : (
            <View style={{ width: 104, height: 104, borderRadius: 52, backgroundColor: tint(GOLD, 0.16), alignItems: 'center', justifyContent: 'center' }}><Ionicons name="person" size={44} color={GOLD} /></View>
          )}
          <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }} {...tid('welcome-jessi-name')}>{me.name}</Text>
          {chips.length > 0 && (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 6 }}>
              {chips.map((c, i) => <View key={i} style={{ paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12, backgroundColor: tint(GOLD, 0.14) }}><Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{c}</Text></View>)}
            </View>
          )}
          {!!me.bio && <Text style={{ fontSize: TYPE.body, color: colors.text, lineHeight: 22, textAlign: 'center' }} {...tid('welcome-jessi-bio')}>{me.bio}</Text>}
          <TouchableOpacity onPress={() => go('profile', '/my-profile')} {...tid('welcome-jessi-edit')}><Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: GOLD }}>Fix something →</Text></TouchableOpacity>
        </View>

        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1.4, marginTop: SPACE.sm }}>YOUR FIRST WIN</Text>
        <View style={{ backgroundColor: tint(GOLD, 0.1), borderRadius: RADIUS.xl, borderWidth: 1, borderColor: tint(GOLD, 0.4), padding: SPACE.xl, gap: SPACE.sm }} {...tid('welcome-jessi-first-win')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Ionicons name={me.first_win.icon as any} size={22} color={GOLD} />
            <Text style={{ fontSize: TYPE.section, fontWeight: '800', color: colors.text }}>{me.first_win.title}</Text>
          </View>
          <Text style={{ fontSize: TYPE.body, color: colors.textSecondary, lineHeight: 21 }}>{me.first_win.body}</Text>
          <PrimaryButton size="lg" full icon="arrow-forward" label={me.first_win.title} loading={busy === me.first_win.key} onPress={() => go(me.first_win.key, me.first_win.route)} testID="welcome-jessi-first-win-btn" style={{ marginTop: 6 }} />
        </View>
        {(me.other_wins || []).map(w => (
          <TouchableOpacity key={w.key} onPress={() => go(w.key, w.route)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: SPACE.lg, borderRadius: RADIUS.lg, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid(`welcome-jessi-win-${w.key}`)}>
            <Ionicons name={w.icon as any} size={20} color={GOLD} />
            <View style={{ flex: 1 }}><Text style={{ fontSize: TYPE.body, fontWeight: '700', color: colors.text }}>{w.title}</Text><Text style={{ fontSize: TYPE.caption, color: colors.textSecondary }}>{w.body}</Text></View>
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </TouchableOpacity>
        ))}
        <TouchableOpacity onPress={() => go('home', '/(tabs)/home')} style={{ alignItems: 'center', paddingVertical: SPACE.md }} {...tid('welcome-jessi-skip')}>
          <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: colors.textSecondary }}>Just take me to Home</Text>
        </TouchableOpacity>
        {!!me.jessi_number && <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary, textAlign: 'center' }}>Stuck? Text Jessi any time at {me.jessi_number.replace(/^\+1(\d{3})(\d{3})(\d{4})$/, '($1) $2-$3')}.</Text>}
      </ScrollView>
    </SafeAreaView>
  );
}
