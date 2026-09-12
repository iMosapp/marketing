import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { GOLD, RED, tid, fmtDate, openScriptPdf, type Script, type Assignment } from '../../components/scripts/shared';
import { ScriptBody, SuccessPoints, PersonaCard, TrainingBody } from '../../components/scripts/ScriptParts';

export default function ScriptDetail() {
  const router = useRouter();
  const { id, assignment: assignmentId } = useLocalSearchParams<{ id: string; assignment?: string }>();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [script, setScript] = useState<Script | null>(null);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [canEdit, setCanEdit] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [showTemplate, setShowTemplate] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, lib] = await Promise.all([api.get(`/scripts/${id}`), api.get('/scripts')]);
      setScript(s.data); setCanEdit(!!lib.data.can_edit);
      if (assignmentId) setAssignment((lib.data.my_assignments || []).find((a: Assignment) => a.id === assignmentId) || null);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load script', 'error'); router.back(); }
    finally { setLoading(false); }
  }, [id, assignmentId]);
  useFocusEffect(useCallback(() => { if (user?._id && id) load(); }, [user?._id, id, load]));

  const pdf = async () => {
    if (!script) return;
    setPdfBusy(true);
    const r = await openScriptPdf(script);
    setPdfBusy(false);
    if (r === 'failed') showToast('Could not open the PDF', 'error');
  };
  const removeCopy = () => script && showConfirm('Remove your store\'s version', script.kind === 'training' ? 'Delete this training script?' : 'Your edits go away and the default script comes back for your team.', async () => {
    try { await api.delete(`/scripts/${script.id}`); showToast(script.kind === 'training' ? 'Deleted' : 'Back to the default script', 'success'); router.back(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, 'Remove');

  const isTraining = script?.kind === 'training';
  const H = ({ t }: { t: string }) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 8 }}>{t}</Text>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={script?.title || 'Script'} subtitle={script ? [script.kind === 'phone' ? (script.direction === 'inbound' ? 'Customer calls in' : 'You call them') : '', script.category, script.runtime].filter(Boolean).join(' · ') : undefined} testID="script-detail-header"
        right={script && (isTraining || canEdit) ? <HeaderIconButton icon="create-outline" onPress={() => router.push(`/scripts/editor?id=${script.id}` as any)} testID="script-edit" /> : undefined} />
      {loading || !script ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <>
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 130, gap: 18 }}>
            {assignment && (
              <View style={{ backgroundColor: GOLD + '1A', borderRadius: 14, borderWidth: 1, borderColor: GOLD, padding: 12, gap: 4 }} {...tid('script-assignment-banner')}>
                <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>ASSIGNED BY {(assignment.created_by_name || 'YOUR MANAGER').toUpperCase()}{assignment.due_by ? ` · DUE ${fmtDate(assignment.due_by).toUpperCase()}` : ''}</Text>
                {!!assignment.note && <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }}>{assignment.note}</Text>}
                {assignment.curveballs.length > 0 && <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Heads up: the customer has {assignment.curveballs.length} curveball{assignment.curveballs.length === 1 ? '' : 's'} ready for you.</Text>}
              </View>
            )}
            {!!script.purpose && <Text style={{ fontSize: 15, color: colors.textSecondary, lineHeight: 22, fontStyle: 'italic' }} {...tid('script-purpose')}>{script.purpose}</Text>}
            {script.customized && <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Your store's version{script.created_by_name ? ` · edited by ${script.created_by_name}` : ''}</Text>}

            {isTraining && script.training ? <TrainingBody training={script.training} colors={colors} /> : (
              <>
                <View style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10 }}>
                    <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>THE SCRIPT</Text>
                    {script.preview && (
                      <TouchableOpacity onPress={() => setShowTemplate(v => !v)} {...tid('script-toggle-fields')}>
                        <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{showTemplate ? 'Show with my name' : 'Show blanks'}</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                  <ScriptBody text={showTemplate || !script.preview ? script.body : script.preview} colors={colors} testID="script-body" />
                </View>
                {script.success_points.length > 0 && (
                  <View><H t="WHAT A GREAT CALL HITS" /><SuccessPoints points={script.success_points} colors={colors} /></View>
                )}
                {script.persona && <View><H t="PRACTICE PARTNER" /><PersonaCard persona={script.persona} colors={colors} /></View>}
              </>
            )}

            {(script.customized || isTraining) && (
              <TouchableOpacity onPress={removeCopy} style={{ alignSelf: 'center', paddingVertical: 8, paddingHorizontal: 14 }} {...tid('script-remove-copy')}>
                <Text style={{ fontSize: 13, fontWeight: '700', color: RED }}>{isTraining ? 'Delete this script' : 'Remove our version, use the default'}</Text>
              </TouchableOpacity>
            )}
          </ScrollView>

          <View style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: 16, paddingBottom: 28, backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.border, flexDirection: 'row', gap: 10 }}>
            <TouchableOpacity onPress={pdf} disabled={pdfBusy} style={{ height: 52, paddingHorizontal: 18, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('script-pdf-btn')}>
              {pdfBusy ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="print-outline" size={20} color={colors.text} />}
              <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Print / PDF</Text>
            </TouchableOpacity>
            {!isTraining && (
              <TouchableOpacity onPress={() => router.push(`/scripts/practice?script=${script.id}${assignmentId ? `&assignment=${assignmentId}` : ''}` as any)}
                style={{ flex: 1, height: 52, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('script-practice-btn')}>
                <Ionicons name="call" size={20} color="#111" />
                <Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>Practice this call</Text>
              </TouchableOpacity>
            )}
          </View>
        </>
      )}
    </SafeAreaView>
  );
}
