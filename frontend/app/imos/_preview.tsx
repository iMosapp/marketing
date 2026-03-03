import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter } from './_components';

type MockupRow = { icon: string; label: string; sub?: string; badge?: string; badgeColor?: string };
type MockupStat = { value: string; label: string; color?: string };
type MockupCard = { icon: string; title: string; sub: string; color: string };

export type PreviewConfig = {
  title: string;
  subtitle: string;
  description: string;
  icon: string;
  iconColor: string;
  bullets: string[];
  mockup: 
    | { type: 'list'; rows: MockupRow[] }
    | { type: 'stats'; stats: MockupStat[] }
    | { type: 'chat'; messages: { from: string; text: string; time: string }[] }
    | { type: 'cards'; cards: MockupCard[] }
    | { type: 'form'; fields: { label: string; value: string }[] };
};

function MockupPhone({ config, isDesktop }: { config: PreviewConfig['mockup']; isDesktop: boolean }) {
  const w = isDesktop ? 380 : '100%';
  return (
    <View style={[mp.phone, { width: w as any, maxWidth: 400 }]}>
      {/* Status bar */}
      <View style={mp.statusBar}>
        <View style={mp.notch} />
      </View>
      {/* App header */}
      <View style={mp.appHeader}>
        <Text style={mp.appTitle}>{config.type === 'list' ? 'Items' : config.type === 'chat' ? 'Messages' : config.type === 'stats' ? 'Dashboard' : config.type === 'cards' ? 'Templates' : 'Settings'}</Text>
      </View>
      {/* Content */}
      <View style={mp.content}>
        {config.type === 'list' && config.rows.map((r, i) => (
          <View key={i} style={mp.listRow}>
            <View style={[mp.listIcon, { backgroundColor: 'rgba(201,169,98,0.12)' }]}>
              <Ionicons name={r.icon as any} size={16} color="#007AFF" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={mp.listLabel}>{r.label}</Text>
              {r.sub && <Text style={mp.listSub}>{r.sub}</Text>}
            </View>
            {r.badge && (
              <View style={[mp.badge, { backgroundColor: (r.badgeColor || '#007AFF') + '20' }]}>
                <Text style={[mp.badgeText, { color: r.badgeColor || '#007AFF' }]}>{r.badge}</Text>
              </View>
            )}
          </View>
        ))}
        {config.type === 'stats' && (
          <View style={mp.statsGrid}>
            {config.stats.map((s, i) => (
              <View key={i} style={mp.statCard}>
                <Text style={[mp.statValue, { color: s.color || '#007AFF' }]}>{s.value}</Text>
                <Text style={mp.statLabel}>{s.label}</Text>
              </View>
            ))}
          </View>
        )}
        {config.type === 'chat' && config.messages.map((m, i) => (
          <View key={i} style={[mp.chatBubble, m.from === 'me' ? mp.chatMe : mp.chatThem]}>
            <Text style={mp.chatText}>{m.text}</Text>
            <Text style={mp.chatTime}>{m.time}</Text>
          </View>
        ))}
        {config.type === 'cards' && (
          <View style={mp.cardsGrid}>
            {config.cards.map((c, i) => (
              <View key={i} style={mp.card}>
                <View style={[mp.cardIcon, { backgroundColor: c.color + '15' }]}>
                  <Ionicons name={c.icon as any} size={18} color={c.color} />
                </View>
                <Text style={mp.cardTitle}>{c.title}</Text>
                <Text style={mp.cardSub}>{c.sub}</Text>
              </View>
            ))}
          </View>
        )}
        {config.type === 'form' && config.fields.map((f, i) => (
          <View key={i} style={mp.formField}>
            <Text style={mp.formLabel}>{f.label}</Text>
            <View style={mp.formInput}><Text style={mp.formValue}>{f.value}</Text></View>
          </View>
        ))}
      </View>
    </View>
  );
}

export function PreviewPage({ config }: { config: PreviewConfig }) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 960 : undefined;

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

          {/* Hero */}
          <View style={s.hero}>
            <View style={[s.iconWrap, { backgroundColor: config.iconColor + '15' }]}>
              <Ionicons name={config.icon as any} size={40} color={config.iconColor} />
            </View>
            <Text style={s.label}>{config.subtitle.toUpperCase()}</Text>
            <Text style={[s.title, isDesktop && { fontSize: 40 }]}>{config.title}</Text>
            <Text style={s.desc}>{config.description}</Text>
          </View>

          {/* Main content area */}
          <View style={[s.mainContent, isDesktop && { flexDirection: 'row', gap: 40 }]}>
            {/* Mockup */}
            <View style={[s.mockupWrap, isDesktop && { flex: 1 }]}>
              <MockupPhone config={config.mockup} isDesktop={isDesktop} />
            </View>

            {/* Bullets + CTA */}
            <View style={[s.infoSide, isDesktop && { flex: 1 }]}>
              <Text style={s.whatTitle}>What you get</Text>
              {config.bullets.map((b, i) => (
                <View key={i} style={s.bulletRow}>
                  <Ionicons name="checkmark-circle" size={20} color={config.iconColor} />
                  <Text style={s.bulletText}>{b}</Text>
                </View>
              ))}

              <View style={s.ctaBox}>
                <Text style={s.ctaTitle}>Ready to use {config.title}?</Text>
                <Text style={s.ctaSub}>Start your 14-day free trial. No commitment.</Text>
                <TouchableOpacity style={s.ctaBtn} onPress={() => router.push('/auth/signup' as any)} data-testid="preview-signup-btn">
                  <Ionicons name="arrow-forward-circle" size={20} color="#000" />
                  <Text style={s.ctaBtnText}>Start 14-Day Free Trial</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.ctaSecondary} onPress={() => router.push('/imos/demo' as any)}>
                  <Text style={s.ctaSecondaryText}>Schedule a Demo Instead</Text>
                  <Ionicons name="arrow-forward" size={14} color="#007AFF" />
                </TouchableOpacity>
              </View>
            </View>
          </View>

        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingBottom: 0 },
  hero: { alignItems: 'center', paddingTop: 40, paddingBottom: 32, paddingHorizontal: 20 },
  iconWrap: { width: 72, height: 72, borderRadius: 20, alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  label: { fontSize: 11, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 10 },
  title: { fontSize: 30, fontWeight: '800', color: '#1D1D1F', textAlign: 'center', marginBottom: 12, lineHeight: 38 },
  desc: { fontSize: 15, color: '#6E6E73', textAlign: 'center', lineHeight: 22, maxWidth: 460 },
  mainContent: { paddingHorizontal: 20, paddingBottom: 40 },
  mockupWrap: { alignItems: 'center', marginBottom: 32 },
  infoSide: {},
  whatTitle: { fontSize: 18, fontWeight: '700', color: '#1D1D1F', marginBottom: 16 },
  bulletRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 12 },
  bulletText: { fontSize: 15, color: '#3A3A3C', lineHeight: 22, flex: 1 },
  ctaBox: { marginTop: 28, backgroundColor: 'rgba(201,169,98,0.06)', borderRadius: 16, padding: 24, borderWidth: 1, borderColor: 'rgba(201,169,98,0.12)' },
  ctaTitle: { fontSize: 18, fontWeight: '700', color: '#1D1D1F', marginBottom: 6 },
  ctaSub: { fontSize: 14, color: '#86868B', marginBottom: 20 },
  ctaBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#007AFF', paddingVertical: 14, borderRadius: 24 },
  ctaBtnText: { fontSize: 16, fontWeight: '700', color: '#000' },
  ctaSecondary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 14 },
  ctaSecondaryText: { fontSize: 14, color: '#007AFF', fontWeight: '500' },
});

const mp = StyleSheet.create({
  phone: {
    backgroundColor: '#F5F5F7',
    borderRadius: 24,
    borderWidth: 1,
    borderColor: '#222',
    overflow: 'hidden',
    ...(Platform.OS === 'web' ? { boxShadow: '0 8px 32px rgba(0,0,0,0.5)' } as any : {}),
  },
  statusBar: { height: 28, backgroundColor: '#FAFAFA', alignItems: 'center', justifyContent: 'flex-end', paddingBottom: 4 },
  notch: { width: 80, height: 4, borderRadius: 2, backgroundColor: '#222' },
  appHeader: { paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1A1A1A' },
  appTitle: { fontSize: 17, fontWeight: '600', color: '#1D1D1F' },
  content: { padding: 12, minHeight: 260 },
  listRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1A1A1A' },
  listIcon: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginRight: 10 },
  listLabel: { fontSize: 14, fontWeight: '500', color: '#1D1D1F' },
  listSub: { fontSize: 11, color: '#666', marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  badgeText: { fontSize: 10, fontWeight: '600' },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  statCard: { width: '47%', backgroundColor: '#1A1A1A', borderRadius: 12, padding: 14, alignItems: 'center' },
  statValue: { fontSize: 28, fontWeight: '800' },
  statLabel: { fontSize: 10, color: '#666', marginTop: 4, textAlign: 'center' },
  chatBubble: { maxWidth: '80%', borderRadius: 16, padding: 10, marginBottom: 8 },
  chatMe: { backgroundColor: '#007AFF', alignSelf: 'flex-end', borderBottomRightRadius: 4 },
  chatThem: { backgroundColor: '#1A1A1A', alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
  chatText: { fontSize: 13, color: '#1D1D1F' },
  chatTime: { fontSize: 9, color: '#AEAEB2', marginTop: 4, textAlign: 'right' },
  cardsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  card: { width: '47%', backgroundColor: '#1A1A1A', borderRadius: 12, padding: 12 },
  cardIcon: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  cardTitle: { fontSize: 12, fontWeight: '600', color: '#1D1D1F' },
  cardSub: { fontSize: 10, color: '#666', marginTop: 2 },
  formField: { marginBottom: 12 },
  formLabel: { fontSize: 11, color: '#666', marginBottom: 4 },
  formInput: { backgroundColor: '#1A1A1A', borderRadius: 8, padding: 10, borderWidth: 1, borderColor: '#222' },
  formValue: { fontSize: 13, color: '#999' },
});
