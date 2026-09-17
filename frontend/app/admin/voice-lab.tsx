import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, GREEN, RED, tid } from '../../components/scripts/shared';
import { VoicePicker, LevelRow, Voice } from '../../components/jessi/VoiceLabControls';
import { SessionsList } from '../../components/jessi/SessionsList';
import { useLiveJessiLauncher } from '../../components/jessi/LiveJessiProvider';
import { liveSupported } from '../../hooks/useLiveJessi';

type Cfg = { voice: string; energy: number; pacing: number; playful: number; brevity: number; daily_cap_min: number; idle_close_s: number; greeting: string; contact_greeting: string; notes: string; updated_at?: string | null; updated_by?: string | null };
type Meta = { voices: Voice[]; labels: Record<string, Record<string, string>>; configured: boolean; reason?: string | null; price_per_min: number; model: string; lab_live: boolean };
const LEVELS: { key: keyof Cfg; label: string }[] = [{ key: 'energy', label: 'Energy' }, { key: 'pacing', label: 'Pacing' }, { key: 'playful', label: 'Playfulness' }, { key: 'brevity', label: 'Brevity' }];

export default function VoiceLab() {
  const { colors } = useThemeStore();
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [saved, setSaved] = useState<Cfg | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState('');
  const jessi = useLiveJessiLauncher();
  const [refreshKey, setRefreshKey] = useState(0);
  const audition = () => cfg && jessi.open({ options: { mode: 'lab', overrides: cfg }, title: `Audition · ${cfg.voice}`, onClose: () => setRefreshKey(k => k + 1) });

  useEffect(() => {
    api.get('/live-voice/admin/config').then(r => { setCfg(r.data.config); setSaved(r.data.config); setMeta(r.data); })
      .catch(e => setError(e?.response?.data?.detail || 'Could not load the Voice Lab'));
  }, []);
  useEffect(() => {
    if (!cfg) return;
    const t = setTimeout(() => {
      api.get('/live-voice/admin/preview', { params: { voice: cfg.voice, energy: cfg.energy, pacing: cfg.pacing, playful: cfg.playful, brevity: cfg.brevity, notes: cfg.notes } })
        .then(r => setPreview(r.data.personality)).catch(() => {});
    }, 350);
    return () => clearTimeout(t);
  }, [cfg?.voice, cfg?.energy, cfg?.pacing, cfg?.playful, cfg?.brevity, cfg?.notes]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(() => JSON.stringify(cfg) !== JSON.stringify(saved), [cfg, saved]);
  const set = (patch: Partial<Cfg>) => setCfg(c => (c ? { ...c, ...patch } : c));
  const save = async () => {
    if (!cfg) return;
    setSaving(true); setError('');
    try { const r = await api.put('/live-voice/admin/config', cfg); setCfg(r.data.config); setSaved(r.data.config); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not save'); }
    finally { setSaving(false); }
  };
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border, marginBottom: 14 } as const;
  const h = { fontSize: 11, fontWeight: '800' as const, color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 10 };
  const input = { backgroundColor: colors.bg, borderRadius: 10, borderWidth: 1, borderColor: colors.border, color: colors.text, padding: 10, fontSize: 14 } as const;
  const NumPill = ({ label, value, opts, onPick, testID }: { label: string; value: number; opts: number[]; onPick: (n: number) => void; testID: string }) => (
    <View style={{ flex: 1 }} {...tid(testID)}>
      <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text, marginBottom: 6 }}>{label}</Text>
      <View style={{ flexDirection: 'row', gap: 6 }}>
        {opts.map(n => (
          <TouchableOpacity key={n} onPress={() => onPick(n)} style={{ flex: 1, paddingVertical: 8, borderRadius: 9, alignItems: 'center', backgroundColor: n === value ? GOLD : colors.bg, borderWidth: 1, borderColor: n === value ? GOLD : colors.border }} {...tid(`${testID}-${n}`)}>
            <Text style={{ fontSize: 12, fontWeight: '800', color: n === value ? '#0B0B0D' : colors.textSecondary }}>{n}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Jessi Voice Lab" subtitle="Pick her voice, set the energy, hear her before reps do" testID="voice-lab-header" />
      {!cfg || !meta ? (error ? <Text style={{ color: RED, padding: 20 }} {...tid('voice-lab-error')}>{error}</Text> : <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} />) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }} keyboardShouldPersistTaps="handled">
          {!meta.configured && (
            <View style={{ flexDirection: 'row', gap: 10, backgroundColor: `${RED}14`, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: `${RED}55`, marginBottom: 14 }} {...tid('voice-lab-needs-key')}>
              <Ionicons name="key" size={18} color={RED} />
              <Text style={{ flex: 1, fontSize: 12.5, color: colors.text, lineHeight: 18 }}>{meta.reason}</Text>
            </View>
          )}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: `${GOLD}14`, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: `${GOLD}40`, marginBottom: 14 }} {...tid('voice-lab-intro')}>
            <Ionicons name="radio" size={18} color={GOLD} />
            <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>{meta.model}, full duplex, about ${meta.price_per_min.toFixed(2)} a minute. Audition uses the settings on this screen even before you save. Reps hear the saved config{meta.lab_live ? '' : ' once you release Talk to Jessi in the Test Lab'}.</Text>
          </View>

          <View style={card}>
            <Text style={h}>HER VOICE</Text>
            <VoicePicker voices={meta.voices} value={cfg.voice} onChange={v => set({ voice: v })} />
          </View>

          <View style={card}>
            <Text style={h}>HOW SHE COMES ACROSS</Text>
            {LEVELS.map(l => <LevelRow key={l.key} label={l.label} value={cfg[l.key] as number} onChange={n => set({ [l.key]: n } as any)} hint={meta.labels[l.key]?.[String(cfg[l.key])] || ''} testID={`level-${l.key}`} />)}
            <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text, marginBottom: 6 }}>Anything else about her (optional)</Text>
            <TextInput value={cfg.notes} onChangeText={t => set({ notes: t })} placeholder="e.g. Loves a quick car joke. Never says 'absolutely'." placeholderTextColor={colors.textSecondary} multiline style={[input, { minHeight: 60 }]} maxLength={600} {...tid('voice-notes')} />
            {!!preview && (
              <View style={{ marginTop: 12, backgroundColor: colors.bg, borderRadius: 10, padding: 10, borderWidth: 1, borderColor: colors.border }} {...tid('voice-preview')}>
                <Text style={{ fontSize: 10, fontWeight: '800', color: GOLD, letterSpacing: 0.6, marginBottom: 4 }}>WHAT GPT-LIVE IS TOLD</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>{preview}</Text>
              </View>
            )}
          </View>

          <View style={card}>
            <Text style={h}>OPENING LINE</Text>
            <TextInput value={cfg.greeting} onChangeText={t => set({ greeting: t })} style={input} maxLength={220} {...tid('voice-greeting')} />
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6 }}>{'{first}'} becomes the rep's first name. She paraphrases a little; that is the point.</Text>
            <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text, marginTop: 14, marginBottom: 6 }}>When opened from a contact (the Ask button)</Text>
            <TextInput value={cfg.contact_greeting} onChangeText={t => set({ contact_greeting: t })} style={input} maxLength={220} {...tid('voice-contact-greeting')} />
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6 }}>{'{contact}'} becomes that customer's first name. She already knows who they are, so "text him" or "what did he buy" just works.</Text>
          </View>

          <View style={card}>
            <Text style={h}>LIMITS</Text>
            <View style={{ flexDirection: 'row', gap: 12 }}>
              <NumPill label="Minutes per rep per day" value={cfg.daily_cap_min} opts={[5, 10, 15, 30, 60]} onPick={n => set({ daily_cap_min: n })} testID="voice-cap" />
            </View>
            <View style={{ flexDirection: 'row', gap: 12, marginTop: 12 }}>
              <NumPill label="Hang up after quiet seconds" value={cfg.idle_close_s} opts={[15, 25, 40, 60, 90]} onPick={n => set({ idle_close_s: n })} testID="voice-idle" />
            </View>
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 8 }}>Cap: {cfg.daily_cap_min} min is about ${(cfg.daily_cap_min * meta.price_per_min).toFixed(2)} a day per rep at most.</Text>
          </View>

          {!!error && <Text style={{ color: RED, marginBottom: 10 }} {...tid('voice-lab-error')}>{error}</Text>}
          <View style={{ flexDirection: 'row', gap: 10, marginBottom: 20 }}>
            <TouchableOpacity onPress={audition} disabled={!meta.configured || !liveSupported()} style={{ flex: 1, borderRadius: 14, paddingVertical: 14, alignItems: 'center', backgroundColor: GOLD, opacity: !meta.configured || !liveSupported() ? 0.5 : 1, flexDirection: 'row', justifyContent: 'center', gap: 8 }} {...tid('voice-audition')}>
              <Ionicons name="mic" size={18} color="#0B0B0D" />
              <Text style={{ color: '#0B0B0D', fontWeight: '800', fontSize: 15 }}>Audition{dirty ? ' (unsaved)' : ''}</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={save} disabled={!dirty || saving} style={{ flex: 1, borderRadius: 14, paddingVertical: 14, alignItems: 'center', borderWidth: 1.5, borderColor: dirty ? GREEN : colors.border, opacity: !dirty || saving ? 0.6 : 1 }} {...tid('voice-save')}>
              {saving ? <ActivityIndicator color={GREEN} /> : <Text style={{ color: dirty ? GREEN : colors.textSecondary, fontWeight: '800', fontSize: 15 }}>{dirty ? 'Save for everyone' : 'Saved'}</Text>}
            </TouchableOpacity>
          </View>
          {!liveSupported() && <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginBottom: 16 }} {...tid('voice-web-only')}>{Platform.OS === 'web' ? 'This browser has no microphone access.' : 'Update the app from the App Store to audition her here.'}</Text>}
          {saved?.updated_at && <Text style={{ fontSize: 11, color: colors.textSecondary, textAlign: 'center', marginBottom: 16 }} {...tid('voice-saved-at')}>Saved {new Date(saved.updated_at).toLocaleString()}{saved.updated_by ? ` by ${saved.updated_by}` : ''}</Text>}

          <View style={card}>
            <Text style={h}>RECENT CONVERSATIONS</Text>
            <SessionsList refreshKey={refreshKey} />
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
