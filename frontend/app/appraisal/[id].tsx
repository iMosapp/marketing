import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderTextButton } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { showConfirm } from '../../services/alert';
import { useAppraisalMedia } from '../../hooks/useAppraisalMedia';
import { StepDots } from '../../components/appraisal/shared';
import { ModeStep } from '../../components/appraisal/ModeStep';
import { IdentityStep } from '../../components/appraisal/IdentityStep';
import { MileageStep } from '../../components/appraisal/MileageStep';
import { InspectionStep } from '../../components/appraisal/InspectionStep';
import { MarketStep } from '../../components/appraisal/MarketStep';
import { ExpectationStep } from '../../components/appraisal/ExpectationStep';
import { ReviewStep } from '../../components/appraisal/ReviewStep';

// One appraisal, one step at a time. The server keeps `step`, so a rep can close the app on the lot and pick up where they were.
export default function AppraisalScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [appraisal, setAppraisal] = useState<any | null>(null);
  const [step, setStep] = useState<string>('mode');
  const media = useAppraisalMedia(id, (m) => showToast(m, 'error', 4000));

  const load = useCallback(async () => {
    try { const d = (await api.get(`/appraisals/${id}`)).data; setAppraisal(d); setStep(d.step || 'mode'); }
    catch (e) { showToast(errText(e, 'Could not open that appraisal'), 'error'); router.back(); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const merge = (a: any) => { setAppraisal((prev: any) => ({ ...(prev || {}), ...a })); setStep(a.step || step); load(); };
  const setMode = async (mode: 'vehicle_here' | 'customer_sent') => {
    try { merge((await api.post(`/appraisals/${id}/mode`, { mode })).data.appraisal); }
    catch (e) { showToast(errText(e, 'Could not save'), 'error'); }
  };
  const discard = () => showConfirm('Discard this draft?', 'This draft is removed. The vehicle stays on the customer only if another appraisal refers to it.', async () => {
    try { await api.delete(`/appraisals/${id}`); router.replace('/appraisals' as any); } catch (e) { showToast(errText(e, 'Could not delete'), 'error'); }
  });

  if (!appraisal) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Trade Appraisal" /><ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /></SafeAreaView>;
  const sub = `${appraisal.contact_name}${appraisal.vehicle_label ? ` · ${appraisal.vehicle_label}` : ''}`;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('appraisal-screen')}>
      <ScreenHeader title={appraisal.is_reappraisal ? 'Reappraisal' : 'Trade Appraisal'} subtitle={sub} onBack={() => router.replace('/appraisals' as any)}
        right={['draft', 'ready'].includes(appraisal.status) ? <HeaderTextButton label="Discard" onPress={discard} testID="appraisal-discard" color="#FF3B30" /> : undefined} />
      <StepDots step={step} colors={colors} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 48 }} keyboardShouldPersistTaps="handled">
          {step === 'mode' && <ModeStep colors={colors} mode={appraisal.mode} onPick={setMode} />}
          {step === 'identity' && <IdentityStep colors={colors} appraisal={appraisal} media={media} onConfirmed={merge} showToast={showToast} />}
          {step === 'mileage' && <MileageStep colors={colors} appraisal={appraisal} media={media} onSaved={merge} showToast={showToast} />}
          {step === 'inspection' && <InspectionStep colors={colors} appraisal={appraisal} media={media} onSaved={merge} showToast={showToast} />}
          {step === 'market' && <MarketStep colors={colors} appraisal={appraisal} onSaved={merge} showToast={showToast} />}
          {step === 'expectation' && <ExpectationStep colors={colors} appraisal={appraisal} onSaved={merge} showToast={showToast} />}
          {step === 'review' && <ReviewStep colors={colors} appraisal={appraisal} onEdit={(s) => setStep(s)} />}
          {step !== 'review' && appraisal.step === 'review' ? (
            <Text onPress={() => setStep('review')} style={{ marginTop: 18, textAlign: 'center', fontSize: 13, fontWeight: '700', color: GOLD }} {...tid('back-to-review')}>Back to the summary</Text>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
