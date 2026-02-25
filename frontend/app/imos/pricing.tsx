import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter } from './_components';

const INDIVIDUAL_PLANS = [
  {
    name: 'Starter',
    price: 49,
    interval: 'month',
    description: 'Perfect for individual salespeople getting started',
    features: ['Smart messaging (SMS + Email)', 'Contact management', 'Digital business card', 'Congrats cards', 'Basic campaigns', 'Mobile app access'],
  },
  {
    name: 'Professional',
    price: 99,
    interval: 'month',
    description: 'For serious sales professionals who want to grow',
    badge: 'Most Popular',
    features: ['Everything in Starter', 'AI assistant (Jessi)', 'Automated birthday campaigns', 'Anniversary & sold-date sequences', 'Holiday campaign templates', 'Advanced analytics'],
  },
  {
    name: 'Elite',
    price: null,
    interval: 'month',
    description: 'Full power for top performers',
    features: ['Everything in Professional', 'Unlimited campaigns', 'Priority AI responses', 'Custom campaign builder', 'Advanced reporting', 'Dedicated support'],
  },
];

const STORE_PLANS = [
  {
    name: 'Team',
    pricePerUser: 75,
    minUsers: 5,
    interval: 'month',
    description: 'For small to mid-size sales teams',
    features: ['Everything in Elite for each user', 'Team leaderboards', 'Activity feeds', 'Broadcast messaging', 'Manager dashboard', 'Guided onboarding'],
  },
  {
    name: 'Enterprise',
    pricePerUser: 60,
    minUsers: 20,
    interval: 'month',
    description: 'For large organizations and multi-store operations',
    badge: 'Best Value',
    features: ['Everything in Team', 'Multi-store hierarchy', 'White-label branding', 'Custom domain support', 'API access', 'Dedicated account manager'],
  },
];

export default function PricingScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 960 : undefined;
  const [tab, setTab] = useState<'individual' | 'store'>('individual');

  return (
    <View style={s.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
        <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

          <View style={s.titleSection}>
            <Text style={s.label}>PRICING</Text>
            <Text style={[s.title, isDesktop && { fontSize: 36 }]}>Simple, Transparent Pricing</Text>
            <Text style={s.subtitle}>Choose the plan that fits your team. No hidden fees. Cancel anytime.</Text>
          </View>

          {/* Tab Toggle */}
          <View style={s.tabRow}>
            <TouchableOpacity style={[s.tab, tab === 'individual' && s.tabActive]} onPress={() => setTab('individual')} data-testid="pricing-individual-tab">
              <Text style={[s.tabText, tab === 'individual' && s.tabTextActive]}>Individual</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.tab, tab === 'store' && s.tabActive]} onPress={() => setTab('store')} data-testid="pricing-store-tab">
              <Text style={[s.tabText, tab === 'store' && s.tabTextActive]}>Store / Team</Text>
            </TouchableOpacity>
          </View>

          {/* Plans */}
          <View style={[s.planGrid, isDesktop && { flexDirection: 'row', gap: 16 }]}>
            {(tab === 'individual' ? INDIVIDUAL_PLANS : STORE_PLANS).map((plan, i) => (
              <View key={i} style={[s.planCard, isDesktop && { flex: 1 }, plan.badge ? s.planCardFeatured : undefined]}>
                {plan.badge && (
                  <View style={s.planBadge}><Text style={s.planBadgeText}>{plan.badge}</Text></View>
                )}
                <Text style={s.planName}>{plan.name}</Text>
                <View style={s.priceRow}>
                  {('price' in plan && plan.price !== null) || 'pricePerUser' in plan ? (
                    <>
                      <Text style={s.priceSymbol}>$</Text>
                      <Text style={s.priceValue}>{'price' in plan ? plan.price : (plan as any).pricePerUser}</Text>
                      <Text style={s.priceUnit}>{'pricePerUser' in plan ? '/user/mo' : '/mo'}</Text>
                    </>
                  ) : (
                    <Text style={s.priceCustom}>Contact Us</Text>
                  )}
                </View>
                {'minUsers' in plan && (
                  <Text style={s.minUsers}>Min {(plan as any).minUsers} users</Text>
                )}
                <Text style={s.planDesc}>{plan.description}</Text>
                <View style={s.featureList}>
                  {plan.features.map((f, fi) => (
                    <View key={fi} style={s.featureItem}>
                      <Ionicons name="checkmark-circle" size={16} color="#34C759" />
                      <Text style={s.featureText}>{f}</Text>
                    </View>
                  ))}
                </View>
                <TouchableOpacity style={[s.planBtn, plan.badge ? s.planBtnFeatured : undefined]} onPress={() => plan.price === null ? router.push('/imos/demo' as any) : router.push('/auth/signup' as any)} data-testid={`plan-${plan.name.toLowerCase()}`}>
                  <Text style={[s.planBtnText, plan.badge ? { color: '#000' } : undefined]}>{plan.price === null ? 'Contact Sales' : 'Get Started'}</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>

          {/* FAQ teaser */}
          <View style={s.faqSection}>
            <Text style={s.faqTitle}>Questions?</Text>
            <Text style={s.faqDesc}>Contact us at forest@imosapp.com for custom pricing, demos, or anything else.</Text>
          </View>

        </View>
        <ImosFooter />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  scroll: { paddingBottom: 0 },
  titleSection: { alignItems: 'center', paddingHorizontal: 24, paddingTop: 40, paddingBottom: 24 },
  label: { fontSize: 11, fontWeight: '700', color: '#C9A962', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#FFF', marginBottom: 8, textAlign: 'center' },
  subtitle: { fontSize: 15, color: '#8E8E93', textAlign: 'center', lineHeight: 22, maxWidth: 400 },
  tabRow: { flexDirection: 'row', alignSelf: 'center', backgroundColor: '#1C1C1E', borderRadius: 12, padding: 3, marginBottom: 28 },
  tab: { paddingVertical: 10, paddingHorizontal: 24, borderRadius: 10 },
  tabActive: { backgroundColor: '#C9A962' },
  tabText: { fontSize: 14, fontWeight: '600', color: '#8E8E93' },
  tabTextActive: { color: '#000' },
  planGrid: { paddingHorizontal: 16, gap: 16, marginBottom: 32 },
  planCard: {
    backgroundColor: '#1C1C1E', borderRadius: 16, padding: 24, marginBottom: 16,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  planCardFeatured: { borderColor: '#C9A962', borderWidth: 2 },
  planBadge: { backgroundColor: '#C9A96225', alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, marginBottom: 12 },
  planBadgeText: { fontSize: 11, fontWeight: '700', color: '#C9A962' },
  planName: { fontSize: 20, fontWeight: '700', color: '#FFF', marginBottom: 8 },
  priceRow: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: 4 },
  priceSymbol: { fontSize: 20, fontWeight: '700', color: '#C9A962', marginBottom: 4 },
  priceValue: { fontSize: 44, fontWeight: '900', color: '#FFF', lineHeight: 48 },
  priceUnit: { fontSize: 14, color: '#8E8E93', marginBottom: 8, marginLeft: 4 },
  priceCustom: { fontSize: 32, fontWeight: '800', color: '#C9A962', lineHeight: 48 },
  minUsers: { fontSize: 12, color: '#FF9500', marginBottom: 8 },
  planDesc: { fontSize: 14, color: '#8E8E93', lineHeight: 20, marginBottom: 16 },
  featureList: { gap: 8, marginBottom: 20 },
  featureItem: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  featureText: { fontSize: 13, color: 'rgba(255,255,255,0.8)' },
  planBtn: {
    alignItems: 'center', paddingVertical: 14, borderRadius: 12,
    borderWidth: 1, borderColor: 'rgba(201,169,98,0.3)',
  },
  planBtnFeatured: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  planBtnText: { fontSize: 15, fontWeight: '700', color: '#C9A962' },
  faqSection: { alignItems: 'center', paddingVertical: 40, paddingHorizontal: 20 },
  faqTitle: { fontSize: 20, fontWeight: '700', color: '#FFF', marginBottom: 8 },
  faqDesc: { fontSize: 14, color: '#8E8E93', textAlign: 'center', lineHeight: 20 },
});
