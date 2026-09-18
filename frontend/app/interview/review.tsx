import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, GREEN, RED, tid, fmtDate } from '../../components/scripts/shared';
import { voiceLabel, type InterviewSession, type InterviewStatus } from '../../components/profile/InterviewCard';

const ORDER = ['bio', 'professional_identity', 'years_experience', 'specialties', 'ideal_customer', 'hometown', 'family_info', 'hobbies', 'vehicles', 'personal_motto', 'fun_facts', 'tone', 'humor_level', 'response_length', 'emoji_usage', 'greeting_style', 'signature', 'custom_phrases', 'never_say', 'interests'];
const show = (v: any) => Array.isArray(v) ? v.join(', ') : String(v ?? '');

export default function InterviewReview() {
  const router = useRouter();
  const { session } = useLocalSearchParams<{ session?: string }>();
  const { colors } = useThemeStore();
  const user = useAuthStore((s: any) => s.user);
  const setUser = useAuthStore((s: any) => s.setUser);
  const [s, setS] = useState<InterviewSession | null>(null);
  const [voice, setVoice] = useState<InterviewStatus['voice'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      if (session) {
        const [r, st] = await Promise.all([api.get(`/interview/sessions/${session}`), api.get('/interview/status')]);
        setS(r.data); setVoice(st.data.voice);
      } else {
        const st = await api.get('/interview/status');
        setS(st.data.session); setVoice(st.data.voice);
      }
    } catch { setError('Could not load the interview'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [session]);

  const rebuild = async () => {
    if (!s) return;
    setRebuilding(true); setError('');
    try { const r = await api.post(`/interview/sessions/${s.id}/rebuild`, {}, { timeout: 150000 }); setS(r.data); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Rebuild failed, try again'); }
    finally { setRebuilding(false); }
  };
  const applyNow = async () => {
    if (!s) return;
    setApplying(true); setError('');
    try {
      const r = await api.post(`/interview/sessions/${s.id}/apply`);
      setS(r.data);
      api.get('/auth/me').then(m => { if (m.data?.user) setUser({ ...user, ...m.data.user }); }).catch(() => {});
    } catch (e: any) { setError(e?.response?.data?.detail || 'Could not save, try again'); }
    finally { setApplying(false); }
  };

  const first = (user?.name || 'you').split(' ')[0];
  const rows = s?.extracted ? ORDER.filter(k => { const v = (s.extracted as any)[k]; return Array.isArray(v) ? v.length : !!v; }) : [];
  const preview = !!s && s.dry_run && !s.applied;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="What Jessi learned" subtitle={s?.ended_at ? `Interview · ${fmtDate(s.ended_at)}` : undefined} testID="interview-review-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
        {loading ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : !s ? (
          <Text style={{ color: colors.textSecondary, textAlign: 'center', marginTop: 40 }} {...tid('interview-review-empty')}>No interview yet. Start one from My Profile.</Text>
        ) : (
          <>
            {s.status === 'completed' ? (
              <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: `${GOLD}55` }} {...tid('interview-review-summary')}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <Ionicons name={preview ? 'flask' : 'sparkles'} size={20} color={GOLD} />
                  <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text, flex: 1 }}>{preview ? `Test run: here is what Jessi would save for ${first}` : `Your VA, bio and card now sound like ${first}`}</Text>
                </View>
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 6, lineHeight: 17 }}>{preview
                  ? `${rows.length} details written from a ${Math.max(1, Math.round(s.elapsed_s / 60))} minute call. NOTHING has been saved to your profile. Read it over, then save it or run the interview again.`
                  : `${s.applied_fields.length} details saved from a ${Math.max(1, Math.round(s.elapsed_s / 60))} minute call. Anything off? Tap Edit and fix it in seconds.`}</Text>
                {s.live_transport === 'gpt-live' && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10 }} {...tid('interview-review-live')}>
                    <Ionicons name="radio" size={14} color={GREEN} />
                    <Text style={{ fontSize: 12, fontWeight: '700', color: GREEN }}>Interviewed on GPT-Live{s.live_voice ? ` · ${s.live_voice}` : ''}</Text>
                  </View>
                )}
                {preview && (
                  <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: GOLD, borderRadius: 12, paddingVertical: 12, marginTop: 12 }} onPress={applyNow} disabled={applying} {...tid('interview-apply-btn')}>
                    {applying ? <ActivityIndicator size="small" color="#000" /> : <><Ionicons name="save-outline" size={16} color="#000" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#000' }}>Save this to my profile</Text></>}
                  </TouchableOpacity>
                )}
                {s.dry_run && s.applied && <Text style={{ fontSize: 12, color: GREEN, fontWeight: '700', marginTop: 8 }} {...tid('interview-applied-note')}>Saved to your profile.</Text>}
                {voice && voiceLabel(voice) ? (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10 }} {...tid('interview-review-voice')}>
                    <Ionicons name={voice.enrolled ? 'shield-checkmark' : 'shield-outline'} size={14} color={voice.enrolled ? GREEN : colors.textSecondary} />
                    <Text style={{ fontSize: 12, fontWeight: '700', color: voice.enrolled ? GREEN : colors.textSecondary }}>{voiceLabel(voice)}{voice.enrolled ? ' · we recognize you on recorded calls' : ''}</Text>
                  </View>
                ) : null}
              </View>
            ) : (
              <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: `${RED}55` }} {...tid('interview-review-failed')}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{s.status === 'building' ? 'Jessi is still writing…' : 'Not built yet'}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 4 }}>{s.fail_reason || `Status: ${s.status}`}</Text>
                {s.rep_turns >= 3 && s.status !== 'building' && (
                  <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: GOLD, borderRadius: 12, paddingVertical: 12, marginTop: 12 }} onPress={rebuild} disabled={rebuilding} {...tid('interview-rebuild-btn')}>
                    {rebuilding ? <ActivityIndicator size="small" color="#000" /> : <><Ionicons name="refresh" size={16} color="#000" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#000' }}>Rebuild from the call</Text></>}
                  </TouchableOpacity>
                )}
              </View>
            )}
            {!!error && <Text style={{ color: RED, marginTop: 10, fontSize: 12 }} {...tid('interview-review-error')}>{error}</Text>}

            {s.highlights.length > 0 && (
              <View style={{ marginTop: 18 }}>
                <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 8 }}>HIGHLIGHTS</Text>
                {s.highlights.map((h, i) => (
                  <View key={i} style={{ flexDirection: 'row', gap: 8, marginBottom: 6 }} {...tid(`interview-highlight-${i}`)}>
                    <Ionicons name="checkmark-circle" size={16} color={GREEN} style={{ marginTop: 1 }} />
                    <Text style={{ flex: 1, fontSize: 14, color: colors.text, lineHeight: 20 }}>{h}</Text>
                  </View>
                ))}
              </View>
            )}

            {rows.length > 0 && (
              <View style={{ marginTop: 18 }}>
                <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 8 }}>{preview ? 'WHAT WOULD BE SAVED' : 'SAVED TO YOUR VA'}</Text>
                {rows.map(k => (
                  <View key={k} style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: GOLD }} {...tid(`interview-field-${k}`)}>
                    <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 3 }}>{s.labels[k] || k}</Text>
                    <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }}>{show((s.extracted as any)[k])}</Text>
                  </View>
                ))}
              </View>
            )}

            {s.status === 'completed' && !preview && (
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 18 }}>
                <TouchableOpacity style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: GOLD, borderRadius: 12, paddingVertical: 13 }} onPress={() => router.push('/settings/persona' as any)} {...tid('interview-edit-btn')}>
                  <Ionicons name="create-outline" size={16} color="#000" />
                  <Text style={{ fontSize: 14, fontWeight: '800', color: '#000' }}>Edit details</Text>
                </TouchableOpacity>
                <TouchableOpacity style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 12, paddingVertical: 13, borderWidth: 1, borderColor: `${GOLD}66` }} onPress={() => router.push('/settings/virtual-assistant' as any)} {...tid('interview-open-va-btn')}>
                  <Ionicons name="chatbubbles-outline" size={16} color={GOLD} />
                  <Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>Hear your VA</Text>
                </TouchableOpacity>
              </View>
            )}

            {s.turns && s.turns.length > 0 && (
              <View style={{ marginTop: 22 }}>
                <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 8 }}>THE CALL</Text>
                {s.turns.map((t: any, i: number) => (
                  <View key={i} style={{ alignSelf: t.role === 'rep' ? 'flex-end' : 'flex-start', maxWidth: '88%', backgroundColor: t.role === 'rep' ? `${GOLD}22` : colors.card, borderRadius: 14, padding: 10, marginBottom: 6 }} {...tid(`interview-turn-${i}`)}>
                    <Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, marginBottom: 2 }}>{t.role === 'rep' ? first.toUpperCase() : 'JESSI'}</Text>
                    <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{t.text}</Text>
                  </View>
                ))}
              </View>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
