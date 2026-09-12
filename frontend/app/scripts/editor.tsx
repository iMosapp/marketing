import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, RED, tid, VOICES, type Script, type Persona, type Training } from '../../components/scripts/shared';
import { ImportScriptSheet, type ImportedScript } from '../../components/scripts/ImportScriptSheet';

const CATS = ['Sales calls', 'Appointments', 'Follow-up', 'Objections', 'Service', 'Custom'];
const emptyPersona: Persona = { name: '', voice: 'female', summary: '', goals: '', objections: [], opening_line: '' };

const Field = ({ label, value, onChange, colors, multiline, placeholder, testID }: any) => (
  <View style={{ gap: 6 }}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{label}</Text>
    <TextInput value={value} onChangeText={onChange} multiline={multiline} placeholder={placeholder} placeholderTextColor={colors.textSecondary}
      style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: 10, color: colors.text, fontSize: 15, minHeight: multiline ? 110 : 44, textAlignVertical: 'top', lineHeight: multiline ? 22 : undefined }} {...tid(testID)} />
  </View>
);

const ListField = ({ label, items, onChange, colors, placeholder, testID, max = 12 }: any) => (
  <View style={{ gap: 6 }}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{label}</Text>
    {items.map((it: string, i: number) => (
      <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <TextInput value={it} onChangeText={v => onChange(items.map((x: string, j: number) => (j === i ? v : x)))} placeholder={placeholder} placeholderTextColor={colors.textSecondary}
          style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, height: 44, color: colors.text, fontSize: 15 }} {...tid(`${testID}-${i}`)} />
        <TouchableOpacity onPress={() => onChange(items.filter((_: string, j: number) => j !== i))} hitSlop={8} {...tid(`${testID}-remove-${i}`)}><Ionicons name="close-circle" size={22} color={colors.textSecondary} /></TouchableOpacity>
      </View>
    ))}
    {items.length < max && (
      <TouchableOpacity onPress={() => onChange([...items, ''])} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6 }} {...tid(`${testID}-add`)}>
        <Ionicons name="add-circle-outline" size={18} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Add</Text>
      </TouchableOpacity>
    )}
  </View>
);

export default function ScriptEditor() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [loading, setLoading] = useState(!!id);
  const [saving, setSaving] = useState(false);
  const [kind, setKind] = useState<'phone' | 'training'>('phone');
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('Sales calls');
  const [runtime, setRuntime] = useState('');
  const [purpose, setPurpose] = useState('');
  const [body, setBody] = useState('');
  const [points, setPoints] = useState<string[]>([]);
  const [persona, setPersona] = useState<Persona>(emptyPersona);
  const [training, setTraining] = useState<Training | null>(null);
  const [cards, setCards] = useState<{ id: string; name: string }[]>([]);
  const [scorecardId, setScorecardId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [imported, setImported] = useState(false);

  const applyImport = (d: ImportedScript) => {
    setTitle(d.title || ''); setCategory(d.category || 'Custom'); setRuntime(d.runtime || ''); setPurpose(d.purpose || ''); setBody(d.body || '');
    setPoints(d.success_points || []); setPersona({ ...emptyPersona, ...(d.persona || {}) });
    setImportOpen(false); setImported(true);
  };

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([id ? api.get(`/scripts/${id}`) : Promise.resolve(null), api.get('/scorecards').catch(() => ({ data: { scorecards: [] } }))]);
      setCards((c?.data?.scorecards || []).map((x: any) => ({ id: x.id, name: x.name })));
      if (s) {
        const sc: Script = s.data;
        setKind(sc.kind); setTitle(sc.title); setCategory(sc.category || 'Custom'); setRuntime(sc.runtime || ''); setPurpose(sc.purpose || ''); setBody(sc.body || '');
        setPoints(sc.success_points || []); setPersona({ ...emptyPersona, ...(sc.persona || {}) }); setScorecardId(sc.scorecard_id || null); setTraining(sc.training || null);
      }
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); router.back(); }
    finally { setLoading(false); }
  }, [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const save = async () => {
    if (!title.trim()) { showToast('Give it a title', 'error'); return; }
    if (kind === 'phone' && !body.trim()) { showToast('The script text is empty', 'error'); return; }
    setSaving(true);
    try {
      const payload: any = kind === 'training' ? { title: title.trim(), purpose, training } : {
        title: title.trim(), category, runtime, purpose, body, success_points: points.filter(p => p.trim()), scorecard_id: scorecardId,
        persona: persona.name.trim() ? { ...persona, objections: (persona.objections || []).filter(o => o.trim()) } : null,
      };
      const res = id ? await api.put(`/scripts/${id}`, payload) : await api.post('/scripts', payload);
      showToast(id ? (res.data.customized ? 'Saved your store\'s version' : 'Saved') : 'Script added', 'success');
      router.replace(`/scripts/${res.data.id}` as any);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setSaving(false); }
  };

  const setScene = (i: number, k: 'on_screen' | 'voice_over', v: string) => training && setTraining({ ...training, scenes: training.scenes.map((s, j) => (j === i ? { ...s, [k]: v } : s)) });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={id ? 'Edit script' : 'New script'} subtitle={id && kind === 'phone' ? 'Saves as your store\'s version' : undefined} testID="script-editor-header"
        right={<TouchableOpacity onPress={save} disabled={saving} style={{ paddingHorizontal: 14, height: 34, borderRadius: 17, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('script-editor-save')}>{saving ? <ActivityIndicator size="small" color="#111" /> : <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Save</Text>}</TouchableOpacity>} />
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80, gap: 18 }} keyboardShouldPersistTaps="handled">
            {!id && kind === 'phone' && (
              <TouchableOpacity onPress={() => setImportOpen(true)} activeOpacity={0.85} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: imported ? colors.card : GOLD + '1A', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: imported ? colors.border : GOLD + '66' }} {...tid('script-editor-import')}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={imported ? 'checkmark-circle' : 'clipboard-outline'} size={20} color={GOLD} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{imported ? 'Pasted script filled in below' : 'Already have this script written?'}</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{imported ? 'Check the wording, points and practice partner, then Save. Tap to paste a different one.' : 'Paste it and Jessi fills in everything below for you to review.'}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
            <Field label="TITLE" value={title} onChange={setTitle} colors={colors} placeholder="Inbound sales call" testID="script-editor-title" />
            {kind === 'training' && training ? (
              <>
                <Field label="HOOK (FIRST 5 SECONDS)" value={training.hook} onChange={(v: string) => setTraining({ ...training, hook: v })} colors={colors} multiline testID="script-editor-hook" />
                {training.scenes.map((s, i) => (
                  <View key={i} style={{ gap: 8, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border }}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>SCENE {i + 1} · {s.seconds}s</Text>
                    <Field label="ON SCREEN" value={s.on_screen} onChange={(v: string) => setScene(i, 'on_screen', v)} colors={colors} multiline testID={`script-editor-scene-${i}-screen`} />
                    <Field label="VOICE-OVER" value={s.voice_over} onChange={(v: string) => setScene(i, 'voice_over', v)} colors={colors} multiline testID={`script-editor-scene-${i}-vo`} />
                  </View>
                ))}
                <Field label="CLOSING LINE" value={training.cta} onChange={(v: string) => setTraining({ ...training, cta: v })} colors={colors} testID="script-editor-cta" />
              </>
            ) : (
              <>
                <View style={{ gap: 6 }}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>CATEGORY</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                    {Array.from(new Set([...CATS, category])).map(c => (
                      <TouchableOpacity key={c} onPress={() => setCategory(c)} style={{ paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: category === c ? GOLD : colors.card, borderWidth: 1, borderColor: category === c ? GOLD : colors.border, justifyContent: 'center' }} {...tid(`script-editor-cat-${c.toLowerCase().replace(/\s+/g, '-')}`)}>
                        <Text style={{ fontSize: 12.5, fontWeight: '800', color: category === c ? '#111' : colors.text }}>{c}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
                <Field label="RUNTIME" value={runtime} onChange={setRuntime} colors={colors} placeholder="2 to 4 min" testID="script-editor-runtime" />
                <Field label="PURPOSE (ONE LINE)" value={purpose} onChange={setPurpose} colors={colors} multiline placeholder="When to use it and what a win looks like" testID="script-editor-purpose" />
                <Field label="SCRIPT TEXT" value={body} onChange={setBody} colors={colors} multiline placeholder={'Use [brackets] for stage directions and {first_name} {vehicle} {store} {rep_name} {appointment_time} {trade} for merge fields.'} testID="script-editor-body" />
                <ListField label="WHAT A GREAT CALL HITS (GRADED)" items={points} onChange={setPoints} colors={colors} placeholder="Offers two appointment times" testID="script-editor-point" />

                <View style={{ gap: 12, backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: GOLD + '55' }}>
                  <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Practice partner <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· who Jessi plays on the phone</Text></Text>
                  <Field label="NAME" value={persona.name} onChange={(v: string) => setPersona({ ...persona, name: v })} colors={colors} placeholder="Maria Lopez" testID="script-editor-persona-name" />
                  <View style={{ gap: 6 }}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>VOICE</Text>
                    <View style={{ flexDirection: 'row', gap: 8 }}>
                      {VOICES.map(v => (
                        <TouchableOpacity key={v.key} onPress={() => setPersona({ ...persona, voice: v.key })} style={{ flex: 1, height: 34, borderRadius: 17, backgroundColor: persona.voice === v.key ? GOLD : colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid(`script-editor-voice-${v.key}`)}>
                          <Text style={{ fontSize: 12, fontWeight: '800', color: persona.voice === v.key ? '#111' : colors.text }}>{v.label}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                  <Field label="WHO THEY ARE" value={persona.summary} onChange={(v: string) => setPersona({ ...persona, summary: v })} colors={colors} multiline placeholder="38, busy nurse, saw a Tahoe online, wants the payment before driving over" testID="script-editor-persona-summary" />
                  <Field label="WHAT THEY WANT" value={persona.goals || ''} onChange={(v: string) => setPersona({ ...persona, goals: v })} colors={colors} placeholder="Find out if it's available and what it costs" testID="script-editor-persona-goals" />
                  <Field label="OPENING LINE" value={persona.opening_line || ''} onChange={(v: string) => setPersona({ ...persona, opening_line: v })} colors={colors} placeholder="Hi, I'm calling about the Tahoe you have online" testID="script-editor-persona-opening" />
                  <ListField label="OBJECTIONS THEY THROW" items={persona.objections || []} onChange={(o: string[]) => setPersona({ ...persona, objections: o })} colors={colors} placeholder="Can you just tell me the payment?" testID="script-editor-objection" max={6} />
                </View>

                {cards.length > 0 && (
                  <View style={{ gap: 6 }}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>GRADE PRACTICE WITH</Text>
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                      {[{ id: null as string | null, name: 'Store default' }, ...cards].map(c => (
                        <TouchableOpacity key={c.id || 'default'} onPress={() => setScorecardId(c.id)} style={{ paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: scorecardId === c.id ? GOLD : colors.card, borderWidth: 1, borderColor: scorecardId === c.id ? GOLD : colors.border, justifyContent: 'center' }} {...tid(`script-editor-card-${c.id || 'default'}`)}>
                          <Text style={{ fontSize: 12.5, fontWeight: '800', color: scorecardId === c.id ? '#111' : colors.text }}>{c.name}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                )}
              </>
            )}
            {!!id && kind === 'phone' && <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Saving makes this your store's version. Other stores keep the default. You can remove your version any time to go back.</Text>}
          </ScrollView>
        </KeyboardAvoidingView>
      )}
      <ImportScriptSheet visible={importOpen} colors={colors} onClose={() => setImportOpen(false)} onImported={applyImport} />
    </SafeAreaView>
  );
}
