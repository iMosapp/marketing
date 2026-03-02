import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../services/api';

interface OnboardingStep {
  id: string;
  num: number;
  title: string;
  subtitle: string;
  icon: string;
  color: string;
  route: string;
  status: 'not_started' | 'in_progress' | 'complete';
  detail?: string;
}

const STEP_DEFINITIONS = [
  {
    id: 'quote',
    title: 'Send Quote',
    subtitle: 'Create and send a pricing quote to the new client',
    icon: 'document-text-outline',
    color: '#007AFF',
    route: '/admin/create-quote',
  },
  {
    id: 'agreement',
    title: 'Get Agreement Signed',
    subtitle: 'Client reviews and e-signs the service agreement',
    icon: 'create-outline',
    color: '#5856D6',
    route: '/admin/nda',
  },
  {
    id: 'payment',
    title: 'Collect Payment',
    subtitle: 'Process first payment or set up billing',
    icon: 'card-outline',
    color: '#34C759',
    route: '/admin/billing',
  },
  {
    id: 'configure',
    title: 'Configure Account',
    subtitle: 'Company info, branding, logo, review links',
    icon: 'settings-outline',
    color: '#C9A962',
    route: '/admin/setup-wizard',
  },
  {
    id: 'team',
    title: 'Add Team Members',
    subtitle: 'Invite the team and assign roles',
    icon: 'people-outline',
    color: '#FF9500',
    route: '/admin/manage-team',
  },
  {
    id: 'live',
    title: 'Account Live',
    subtitle: 'Everything is set — account is active and ready',
    icon: 'rocket-outline',
    color: '#FF2D55',
    route: '',
  },
];

export default function ClientOnboardingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [steps, setSteps] = useState<OnboardingStep[]>([]);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [orgs, setOrgs] = useState<any[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>('');
  const [saving, setSaving] = useState(false);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [])
  );

  const loadData = async () => {
    try {
      const userStr = await AsyncStorage.getItem('user');
      const user = userStr ? JSON.parse(userStr) : null;
      setCurrentUser(user);

      // Load orgs
      const orgsRes = await api.get('/admin/organizations').catch(() => ({ data: [] }));
      const orgList = Array.isArray(orgsRes.data) ? orgsRes.data : [];
      setOrgs(orgList);

      // Try to load saved progress
      const savedOrgId = await AsyncStorage.getItem('onboarding_selected_org');
      if (savedOrgId) {
        setSelectedOrgId(savedOrgId);
        await loadProgress(savedOrgId);
      } else if (orgList.length > 0) {
        const orgId = orgList[0]._id;
        setSelectedOrgId(orgId);
        await loadProgress(orgId);
      } else {
        // No orgs, set default steps
        initDefaultSteps();
      }
    } catch (e) {
      console.error('Error loading onboarding data:', e);
      initDefaultSteps();
    } finally {
      setLoading(false);
    }
  };

  const initDefaultSteps = () => {
    setSteps(STEP_DEFINITIONS.map((d, i) => ({
      ...d,
      num: i + 1,
      status: 'not_started',
    })));
  };

  const loadProgress = async (orgId: string) => {
    try {
      const res = await api.get(`/setup-wizard/progress/${orgId}`);
      const completedSteps: string[] = res.data.completed_step_ids || [];
      setSteps(STEP_DEFINITIONS.map((d, i) => ({
        ...d,
        num: i + 1,
        status: completedSteps.includes(d.id) ? 'complete' : 'not_started',
      })));
    } catch {
      initDefaultSteps();
    }
  };

  const selectOrg = async (orgId: string) => {
    setSelectedOrgId(orgId);
    await AsyncStorage.setItem('onboarding_selected_org', orgId);
    setLoading(true);
    await loadProgress(orgId);
    setLoading(false);
  };

  const toggleStepComplete = async (stepId: string) => {
    const updated = steps.map(s => {
      if (s.id === stepId) {
        return { ...s, status: s.status === 'complete' ? 'not_started' as const : 'complete' as const };
      }
      return s;
    });
    setSteps(updated);

    // Save progress
    if (selectedOrgId) {
      const completedIds = updated.filter(s => s.status === 'complete').map(s => s.id);
      try {
        await api.post(`/setup-wizard/progress/${selectedOrgId}`, {
          completed_step_ids: completedIds,
          completed_steps: updated.filter(s => s.status === 'complete').map(s => s.num),
          current_step: updated.findIndex(s => s.status !== 'complete') + 1 || updated.length,
          completed: completedIds.length === updated.length,
        });
      } catch (e) {
        console.error('Error saving progress:', e);
      }
    }
  };

  const goToStep = (step: OnboardingStep) => {
    if (step.route) {
      router.push(step.route as any);
    }
  };

  const completedCount = steps.filter(s => s.status === 'complete').length;
  const progressPct = steps.length > 0 ? (completedCount / steps.length) * 100 : 0;

  // Find the next incomplete step
  const nextStep = steps.find(s => s.status !== 'complete');

  if (loading) {
    return (
      <SafeAreaView style={st.safe}>
        <View style={st.loadingWrap}><ActivityIndicator size="large" color="#C9A962" /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.safe}>
      {/* Header */}
      <View style={st.header}>
        <TouchableOpacity onPress={() => router.back()} style={st.headerBack} data-testid="onboarding-back">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <Text style={st.headerTitle}>Client Onboarding</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView style={st.body} contentContainerStyle={st.bodyContent}>
        {/* Org selector (if multiple) */}
        {orgs.length > 1 && (
          <View style={st.orgSelector}>
            <Text style={st.orgSelectorLabel}>Organization</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={st.orgChips}>
              {orgs.map((org: any) => (
                <TouchableOpacity
                  key={org._id}
                  style={[st.orgChip, selectedOrgId === org._id && st.orgChipActive]}
                  onPress={() => selectOrg(org._id)}
                  data-testid={`onboarding-org-${org._id}`}
                >
                  <Text style={[st.orgChipText, selectedOrgId === org._id && st.orgChipTextActive]}>{org.name}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Progress overview */}
        <View style={st.progressCard}>
          <View style={st.progressHeader}>
            <Text style={st.progressTitle}>Setup Progress</Text>
            <Text style={st.progressCount}>{completedCount} of {steps.length}</Text>
          </View>
          <View style={st.progressBarBg}>
            <View style={[st.progressBarFill, { width: `${progressPct}%` as any }]} />
          </View>
          {progressPct === 100 ? (
            <Text style={st.progressHint}>All steps complete! This account is live.</Text>
          ) : nextStep ? (
            <Text style={st.progressHint}>Next up: {nextStep.title}</Text>
          ) : null}
        </View>

        {/* Steps */}
        <View style={st.stepsContainer}>
          {steps.map((step, idx) => {
            const isComplete = step.status === 'complete';
            const isNext = step.id === nextStep?.id;
            const isLast = idx === steps.length - 1;

            return (
              <View key={step.id} style={st.stepWrapper}>
                {/* Timeline connector */}
                <View style={st.timeline}>
                  <View style={[
                    st.timelineDot,
                    isComplete && st.timelineDotComplete,
                    isNext && st.timelineDotNext,
                  ]}>
                    {isComplete ? (
                      <Ionicons name="checkmark" size={16} color="#000" />
                    ) : (
                      <Text style={[st.timelineNum, isNext && st.timelineNumNext]}>{step.num}</Text>
                    )}
                  </View>
                  {!isLast && (
                    <View style={[st.timelineLine, isComplete && st.timelineLineComplete]} />
                  )}
                </View>

                {/* Step card */}
                <View style={[st.stepCard, isNext && st.stepCardNext, isComplete && st.stepCardComplete]}>
                  <View style={st.stepCardTop}>
                    <View style={[st.stepIcon, { backgroundColor: step.color + '20' }]}>
                      <Ionicons name={step.icon as any} size={22} color={step.color} />
                    </View>
                    <View style={st.stepInfo}>
                      <Text style={[st.stepTitle, isComplete && st.stepTitleComplete]}>{step.title}</Text>
                      <Text style={st.stepSubtitle}>{step.subtitle}</Text>
                    </View>
                  </View>

                  <View style={st.stepActions}>
                    {/* Mark complete toggle */}
                    <TouchableOpacity
                      style={[st.checkBtn, isComplete && st.checkBtnComplete]}
                      onPress={() => toggleStepComplete(step.id)}
                      data-testid={`onboarding-check-${step.id}`}
                    >
                      <Ionicons
                        name={isComplete ? 'checkmark-circle' : 'ellipse-outline'}
                        size={20}
                        color={isComplete ? '#000' : '#555'}
                      />
                      <Text style={[st.checkBtnText, isComplete && st.checkBtnTextComplete]}>
                        {isComplete ? 'Done' : 'Mark Done'}
                      </Text>
                    </TouchableOpacity>

                    {/* Go to action button */}
                    {step.route ? (
                      <TouchableOpacity
                        style={[st.goBtn, isNext && st.goBtnNext]}
                        onPress={() => goToStep(step)}
                        data-testid={`onboarding-go-${step.id}`}
                      >
                        <Text style={[st.goBtnText, isNext && st.goBtnTextNext]}>
                          {isNext ? 'Do This Now' : 'Open'}
                        </Text>
                        <Ionicons name="arrow-forward" size={16} color={isNext ? '#000' : '#C9A962'} />
                      </TouchableOpacity>
                    ) : null}
                  </View>
                </View>
              </View>
            );
          })}
        </View>

        {/* Quick reference */}
        <View style={st.refCard}>
          <Text style={st.refTitle}>Quick Reference</Text>
          <View style={st.refRow}>
            <Ionicons name="time-outline" size={16} color="#8E8E93" />
            <Text style={st.refText}>Average setup time: 15-30 minutes</Text>
          </View>
          <View style={st.refRow}>
            <Ionicons name="information-circle-outline" size={16} color="#8E8E93" />
            <Text style={st.refText}>You can complete steps in any order</Text>
          </View>
          <View style={st.refRow}>
            <Ionicons name="save-outline" size={16} color="#8E8E93" />
            <Text style={st.refText}>Progress saves automatically — pick up where you left off</Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#000' },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  headerBack: { width: 32, height: 32, justifyContent: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#FFF' },

  body: { flex: 1 },
  bodyContent: { padding: 16, paddingBottom: 40 },

  // Org selector
  orgSelector: { marginBottom: 16 },
  orgSelectorLabel: { fontSize: 12, color: '#8E8E93', fontWeight: '600', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 },
  orgChips: { flexDirection: 'row' },
  orgChip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: '#1C1C1E', marginRight: 8, borderWidth: 1, borderColor: '#2C2C2E' },
  orgChipActive: { backgroundColor: '#C9A962', borderColor: '#C9A962' },
  orgChipText: { fontSize: 13, fontWeight: '600', color: '#8E8E93' },
  orgChipTextActive: { color: '#000' },

  // Progress card
  progressCard: { backgroundColor: '#0D0D0D', borderRadius: 16, padding: 18, marginBottom: 20, borderWidth: 1, borderColor: '#1C1C1E' },
  progressHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  progressTitle: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  progressCount: { fontSize: 14, fontWeight: '700', color: '#C9A962' },
  progressBarBg: { height: 6, borderRadius: 3, backgroundColor: '#1C1C1E', overflow: 'hidden', marginBottom: 10 },
  progressBarFill: { height: '100%' as any, borderRadius: 3, backgroundColor: '#C9A962' },
  progressHint: { fontSize: 13, color: '#8E8E93' },

  // Steps
  stepsContainer: { marginBottom: 20 },
  stepWrapper: { flexDirection: 'row', marginBottom: 0 },

  // Timeline
  timeline: { width: 36, alignItems: 'center' },
  timelineDot: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#2C2C2E', zIndex: 1 },
  timelineDotComplete: { backgroundColor: '#34C759', borderColor: '#34C759' },
  timelineDotNext: { borderColor: '#C9A962' },
  timelineNum: { fontSize: 13, fontWeight: '700', color: '#555' },
  timelineNumNext: { color: '#C9A962' },
  timelineLine: { width: 2, flex: 1, backgroundColor: '#1C1C1E', marginVertical: -2 },
  timelineLineComplete: { backgroundColor: '#34C759' },

  // Step card
  stepCard: { flex: 1, marginLeft: 12, marginBottom: 12, backgroundColor: '#0D0D0D', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#1C1C1E' },
  stepCardNext: { borderColor: '#C9A96266' },
  stepCardComplete: { borderColor: '#34C75933', opacity: 0.85 },
  stepCardTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  stepIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  stepInfo: { flex: 1 },
  stepTitle: { fontSize: 15, fontWeight: '700', color: '#FFF', marginBottom: 2 },
  stepTitleComplete: { textDecorationLine: 'line-through', color: '#8E8E93' },
  stepSubtitle: { fontSize: 12, color: '#8E8E93', lineHeight: 16 },

  stepActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  checkBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: '#1C1C1E' },
  checkBtnComplete: { backgroundColor: '#34C759' },
  checkBtnText: { fontSize: 12, fontWeight: '600', color: '#8E8E93' },
  checkBtnTextComplete: { color: '#000' },
  goBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: '#1C1C1E', marginLeft: 'auto' as any },
  goBtnNext: { backgroundColor: '#C9A962' },
  goBtnText: { fontSize: 12, fontWeight: '700', color: '#C9A962' },
  goBtnTextNext: { color: '#000' },

  // Reference card
  refCard: { backgroundColor: '#0D0D0D', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#1C1C1E' },
  refTitle: { fontSize: 14, fontWeight: '700', color: '#FFF', marginBottom: 12 },
  refRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  refText: { fontSize: 13, color: '#8E8E93', flex: 1 },
});
