import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Modal, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { GOLD, tid, type Script } from '../../components/scripts/shared';

type Feature = { id: string; name: string; audience: string; summary: string };

export default function TrainingScripts() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [scripts, setScripts] = useState<Script[]>([]);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);
  const [sheet, setSheet] = useState(false);
  const [featureId, setFeatureId] = useState<string | null>(null);
  const [format, setFormat] = useState<'short' | 'long'>('short');
  const [extra, setExtra] = useState('');
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    try { const res = await api.get('/scripts/training'); setScripts(res.data.scripts || []); setFeatures(res.data.features || []); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); if (e?.response?.status === 403) router.back(); }
    finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const generate = async () => {
    if (!featureId) { showToast('Pick a feature', 'error'); return; }
    setGenerating(true);
    try {
      const res = await api.post('/scripts/training/generate', { feature_id: featureId, format, extra: extra.trim() }, { timeout: 120000 });
      setSheet(false); setExtra(''); router.push(`/scripts/${res.data.id}` as any);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Jessi could not write that right now', 'error'); }
    finally { setGenerating(false); }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Training video scripts" subtitle="Voice-over and shot list, ready to record" testID="training-header" right={<HeaderIconButton icon="add-circle" onPress={() => setSheet(true)} testID="training-new" />} />
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Pick a feature, Jessi writes a 60 to 90 second (or 3 to 5 minute) screen-recording script: hook, scenes with what to show and exactly what to say, closing line. Print it or edit any line.</Text>
          {scripts.length === 0 && (
            <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 20, alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.border }} {...tid('training-empty')}>
              <Ionicons name="videocam-outline" size={36} color={GOLD} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>No video scripts yet</Text>
              <TouchableOpacity onPress={() => setSheet(true)} style={{ marginTop: 4, height: 42, paddingHorizontal: 18, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('training-empty-new')}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Write the first one</Text>
              </TouchableOpacity>
            </View>
          )}
          {scripts.map(s => (
            <TouchableOpacity key={s.id} onPress={() => router.push(`/scripts/${s.id}` as any)} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid(`training-card-${s.id}`)}>
              <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="videocam" size={18} color={GOLD} /></View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1}>{s.title}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary }}>{s.format === 'long' ? 'Long' : 'Short'} · {s.runtime} · {s.training?.scenes?.length || 0} scenes</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      <Modal visible={sheet} animationType="slide" transparent onRequestClose={() => setSheet(false)}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '90%' }} {...tid('training-sheet')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
              <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>Write a video script</Text>
              <TouchableOpacity onPress={() => setSheet(false)} {...tid('training-sheet-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 30, gap: 14 }} keyboardShouldPersistTaps="handled">
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {(['short', 'long'] as const).map(f => (
                  <TouchableOpacity key={f} onPress={() => setFormat(f)} style={{ flex: 1, height: 44, borderRadius: 12, backgroundColor: format === f ? GOLD : colors.card, borderWidth: 1, borderColor: format === f ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`training-format-${f}`)}>
                    <Text style={{ fontSize: 13, fontWeight: '800', color: format === f ? '#111' : colors.text }}>{f === 'short' ? 'Short · 60 to 90s' : 'Long · 3 to 5 min'}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <View style={{ gap: 8 }}>
                {features.map(f => (
                  <TouchableOpacity key={f.id} onPress={() => setFeatureId(f.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: featureId === f.id ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: featureId === f.id ? GOLD : colors.border }} {...tid(`training-feature-${f.id}`)}>
                    <Ionicons name={featureId === f.id ? 'radio-button-on' : 'radio-button-off'} size={18} color={featureId === f.id ? GOLD : colors.textSecondary} />
                    <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{f.name}</Text><Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }} numberOfLines={2}>{f.summary}</Text></View>
                  </TouchableOpacity>
                ))}
              </View>
              <TextInput value={extra} onChangeText={setExtra} placeholder="Extra direction (optional): tone, what to emphasize, who is narrating" placeholderTextColor={colors.textSecondary} multiline
                style={{ minHeight: 70, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 12, color: colors.text, fontSize: 14, textAlignVertical: 'top' }} {...tid('training-extra')} />
              <TouchableOpacity onPress={generate} disabled={generating} style={{ height: 52, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('training-generate')}>
                {generating ? <><ActivityIndicator color="#111" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Jessi is writing…</Text></> : <><Ionicons name="sparkles" size={18} color="#111" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Write it</Text></>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
