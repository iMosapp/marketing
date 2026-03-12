import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';

const STEPS = [
  {
    num: 1,
    title: 'Organization & Store',
    icon: 'business',
    color: '#007AFF',
    desc: 'Create or select an organization, then add a store location.',
    fields: ['Organization Name', 'Store Name', 'Industry', 'Phone', 'Website', 'City/State'],
    tip: 'If the organization already exists, select it from the list and you can add a new store under it.',
  },
  {
    num: 2,
    title: 'Branding',
    icon: 'color-palette',
    color: '#AF52DE',
    desc: 'Upload a logo, pick brand color, and set an email footer.',
    fields: ['Logo Upload', 'Brand Color', 'Email Footer'],
    tip: 'This can be done later under Settings > Brand Kit. Feel free to skip.',
  },
  {
    num: 3,
    title: 'Team Roster',
    icon: 'people',
    color: '#FF9500',
    desc: 'Add team members and assign their roles. Each user gets a temporary password shown on screen.',
    fields: ['First Name', 'Last Name', 'Email', 'Phone', 'Role (Sales / Manager / Admin)'],
    tip: 'Write down the temporary passwords! The new user will be forced to change it on their first login.',
  },
  {
    num: 4,
    title: 'Review Links',
    icon: 'star',
    color: '#FFCC00',
    desc: 'Add review platform URLs so the team can send review requests to customers.',
    fields: ['Google Reviews', 'Facebook', 'Yelp', 'DealerRater', 'Custom Link'],
    tip: 'Google Reviews is the most important one. Get the direct link from your Google Business Profile.',
  },
  {
    num: 5,
    title: 'Message Templates',
    icon: 'chatbubbles',
    color: '#34C759',
    desc: 'Pre-loaded templates are enabled by default. Toggle off any that don\'t apply.',
    fields: ['Welcome', 'Follow Up', 'Review Request', 'Referral Ask', 'Birthday', 'Anniversary'],
    tip: 'Templates can always be customized later. The defaults work well for most dealerships.',
  },
  {
    num: 6,
    title: 'Tags',
    icon: 'pricetags',
    color: '#5856D6',
    desc: 'Create tags for organizing contacts (e.g., "VIP", "Service Customer", "New Lead").',
    fields: ['Custom tag names'],
    tip: 'Start with 3-5 tags. More can always be added later from Settings > Tags.',
  },
  {
    num: 7,
    title: 'Handoff',
    icon: 'checkmark-circle',
    color: '#34C759',
    desc: 'Review what was configured and see what\'s still needed. Click Finish to complete.',
    fields: ['Configuration summary', 'Remaining items checklist'],
    tip: 'Screenshot this page to track what still needs to be set up for the account.',
  },
];

const AFTER_STEPS = [
  {
    icon: 'key',
    color: '#FF9500',
    title: 'New user logs in with temp password',
    desc: 'They\'ll be prompted to set a new password immediately.',
  },
  {
    icon: 'school',
    color: '#007AFF',
    title: 'Onboarding slides auto-play',
    desc: '13 slides walk them through the app features.',
  },
  {
    icon: 'home',
    color: '#34C759',
    title: 'User lands on their Home screen',
    desc: 'They\'re ready to start adding contacts and sending messages.',
  },
];

export default function OnboardingGuide() {
  const router = useRouter();
  const colors = useThemeStore((s) => s.colors);

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={[styles.title, { color: colors.text }]}>Account Onboarding Guide</Text>
            <Text style={[styles.subtitle, { color: colors.textSecondary }]}>Step-by-step process for setting up a new account</Text>
          </View>
        </View>

        {/* CTA Button */}
        <TouchableOpacity
          style={styles.ctaBtn}
          onPress={() => router.push('/admin/setup-wizard' as any)}
        >
          <Ionicons name="rocket" size={20} color="#FFF" />
          <Text style={styles.ctaText}>Start New Account Setup</Text>
          <Ionicons name="arrow-forward" size={18} color="#FFF" />
        </TouchableOpacity>

        {/* Steps */}
        <Text style={[styles.sectionTitle, { color: colors.text }]}>The 7-Step Setup Wizard</Text>

        {STEPS.map((step) => (
          <View key={step.num} style={[styles.stepCard, { backgroundColor: colors.card, borderColor: colors.surface }]}>
            <View style={styles.stepHeader}>
              <View style={[styles.stepNum, { backgroundColor: `${step.color}20` }]}>
                <Text style={[styles.stepNumText, { color: step.color }]}>{step.num}</Text>
              </View>
              <Ionicons name={step.icon as any} size={20} color={step.color} />
              <Text style={[styles.stepTitle, { color: colors.text }]}>{step.title}</Text>
            </View>
            <Text style={[styles.stepDesc, { color: colors.textSecondary }]}>{step.desc}</Text>

            {/* Fields */}
            <View style={styles.fieldsRow}>
              {step.fields.map((f) => (
                <View key={f} style={[styles.fieldPill, { backgroundColor: `${step.color}12`, borderColor: `${step.color}30` }]}>
                  <Text style={[styles.fieldText, { color: step.color }]}>{f}</Text>
                </View>
              ))}
            </View>

            {/* Tip */}
            <View style={[styles.tipRow, { backgroundColor: colors.surface }]}>
              <Ionicons name="bulb" size={14} color="#FF9500" />
              <Text style={[styles.tipText, { color: colors.textSecondary }]}>{step.tip}</Text>
            </View>
          </View>
        ))}

        {/* After Setup */}
        <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 24 }]}>What Happens After Setup</Text>
        <View style={[styles.afterCard, { backgroundColor: colors.card, borderColor: colors.surface }]}>
          {AFTER_STEPS.map((a, i) => (
            <View key={i} style={[styles.afterRow, i < AFTER_STEPS.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.surface }]}>
              <View style={[styles.afterIcon, { backgroundColor: `${a.color}15` }]}>
                <Ionicons name={a.icon as any} size={18} color={a.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.afterTitle, { color: colors.text }]}>{a.title}</Text>
                <Text style={[styles.afterDesc, { color: colors.textSecondary }]}>{a.desc}</Text>
              </View>
              {i < AFTER_STEPS.length - 1 && (
                <Ionicons name="arrow-down" size={16} color={colors.textSecondary} style={{ position: 'absolute', right: -8, bottom: -12 }} />
              )}
            </View>
          ))}
        </View>

        {/* Bottom CTA */}
        <TouchableOpacity
          style={[styles.ctaBtn, { marginTop: 20 }]}
          onPress={() => router.push('/admin/setup-wizard' as any)}
        >
          <Ionicons name="add-circle" size={20} color="#FFF" />
          <Text style={styles.ctaText}>Start New Account Setup</Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, maxWidth: 700, alignSelf: 'center' as any, width: '100%' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 20 },
  backBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: '700' },
  subtitle: { fontSize: 13, marginTop: 2 },
  ctaBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    backgroundColor: '#FF2D55', borderRadius: 14, paddingVertical: 14, paddingHorizontal: 20,
    marginBottom: 24,
  },
  ctaText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
  sectionTitle: { fontSize: 17, fontWeight: '700', marginBottom: 12 },
  stepCard: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 12 },
  stepHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  stepNum: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  stepNumText: { fontSize: 14, fontWeight: '800' },
  stepTitle: { fontSize: 16, fontWeight: '700', flex: 1 },
  stepDesc: { fontSize: 13, lineHeight: 19, marginBottom: 10 },
  fieldsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 },
  fieldPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, borderWidth: 1 },
  fieldText: { fontSize: 11, fontWeight: '600' },
  tipRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, borderRadius: 10, padding: 10 },
  tipText: { fontSize: 12, lineHeight: 17, flex: 1 },
  afterCard: { borderRadius: 14, borderWidth: 1, overflow: 'hidden' },
  afterRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, position: 'relative' as any },
  afterIcon: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  afterTitle: { fontSize: 14, fontWeight: '600' },
  afterDesc: { fontSize: 12, marginTop: 2 },
});
