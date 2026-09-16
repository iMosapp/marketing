import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { CallRecordingPlayer } from '../../components/CallRecordingPlayer';
import { ScoreRing } from '../../components/scorecards/ScoreRing';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { Label, deptLabel, replyDur, LIGHT, GOLD, GREEN, RED, tid } from '../../components/mystery-shops/shared';
import { makeT, langOf, fmtWhenL } from '../../components/mystery-shops/i18n';

const Card = ({ children, testID }: { children: React.ReactNode; testID: string }) => (
  <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18, gap: 12 }} {...tid(testID)}>{children}</View>
);

// The scorecard texted to whoever got mystery shopped. No login, light palette, one call only, in the client's language.
export default function PublicShopScore() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => { if (token) api.get(`/public/shop-score/${token}`).then(r => setD(r.data)).catch(() => setError('invalid')); }, [token]);

  const lang = langOf(d?.language);
  const tr = makeT(lang);
  const wide = width > 800;
  const passed = (d?.results || []).filter((r: any) => r.passed);
  const missed = (d?.results || []).filter((r: any) => !r.passed);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: LIGHT.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 32 : 16, paddingBottom: 60, alignItems: 'center' }}>
        <View style={{ width: '100%', maxWidth: 680, gap: 16 }} {...tid(`score-page-${lang}`)}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>{tr('sc.kicker')}</Text>
          {error ? <Text style={{ fontSize: 15, color: LIGHT.textSecondary }} {...tid('score-error')}>{tr('sc.invalid')}</Text> : !d ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <Card testID="score-hero">
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 18 }}>
                  <ScoreRing pct={d.score_pct} size={104} stroke={9} colors={LIGHT} label={tr('sc.score')} testID="score-ring" />
                  <View style={{ flex: 1, gap: 4 }}>
                    <Text style={{ fontSize: wide ? 26 : 22, fontWeight: '800', color: LIGHT.text }} {...tid('score-title')}>{d.first_name ? tr('sc.title', { name: d.first_name }) : tr('sc.title_generic')}</Text>
                    <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary, lineHeight: 19 }} {...tid('score-meta')}>{d.department_label || deptLabel(d.department)} · {d.challenge_title}{d.persona_name ? ` · ${tr('sc.was', { customer: d.customer_noun || 'shopper', name: d.persona_name.split(' ')[0] })}` : ''}{d.ended_at ? ` · ${fmtWhenL(d.ended_at, lang)}` : ''}{d.store_name ? ` · ${d.store_name}` : ''}</Text>
                  </View>
                </View>
                {d.channel === 'text' && d.text && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('score-text-speed')}>
                    <Ionicons name="chatbubbles" size={16} color={GOLD} />
                    <Text style={{ fontSize: 13.5, fontWeight: '700', color: d.text.first_reply_s == null ? RED : d.text.first_reply_s <= 300 ? GREEN : GOLD }}>{tr('sc.text_speed')}: {d.text.first_reply_s == null ? tr('tx.noreply') : `${tr('tx.first', { d: replyDur(d.text.first_reply_s, lang) })}${d.text.replies > 1 ? ` · ${tr('tx.slowest', { d: replyDur(d.text.max_reply_s, lang) })}` : ''} · ${tr('tx.replies', { n: d.text.replies })}`}</Text>
                  </View>
                )}
                {!!d.summary && <Text style={{ fontSize: 15, color: LIGHT.text, lineHeight: 23 }} {...tid('score-summary')}>{d.summary}</Text>}
              </Card>
              {d.channel === 'text' && (d.transcript_turns || []).length > 0 && (
                <Card testID="score-thread">
                  <Label t={tr('sc.thread')} colors={LIGHT} />
                  {d.transcript_turns.map((t: any, i: number) => (
                    <View key={i} style={{ flexDirection: 'row', justifyContent: t.role === 'rep' ? 'flex-end' : 'flex-start' }}>
                      <View style={{ maxWidth: '86%', backgroundColor: t.role === 'rep' ? GOLD : LIGHT.bg, borderRadius: 14, padding: 10, borderWidth: t.role === 'rep' ? 0 : 1, borderColor: LIGHT.border }}>
                        <Text style={{ fontSize: 14, lineHeight: 19, color: t.role === 'rep' ? '#111' : LIGHT.text }}>{t.text}</Text>
                        {t.role === 'rep' && t.delay_s != null && <Text style={{ fontSize: 10.5, color: '#11111199', marginTop: 3, textAlign: 'right' }}>{t.delay_s < 60 ? tr('tx.within') : tr('tx.after', { d: replyDur(t.delay_s, lang) })}</Text>}
                      </View>
                    </View>
                  ))}
                </Card>
              )}
              {!!d.recording_url && (
                <Card testID="score-recording">
                  <Label t={tr('sc.listen')} colors={LIGHT} />
                  <CallRecordingPlayer url={resolvePhotoUrl(d.recording_url) || d.recording_url} tint={GOLD} textColor={LIGHT.text} subColor={LIGHT.textSecondary} trackColor={LIGHT.border} />
                </Card>
              )}
              <View style={{ flexDirection: wide ? 'row' : 'column', gap: 16 }}>
                <View style={{ flex: 1 }}>
                  <Card testID="score-wins">
                    <Label t={tr('sc.nailed')} colors={{ textSecondary: GREEN }} />
                    {passed.map((r: any, i: number) => <View key={i} style={{ flexDirection: 'row', gap: 8 }}><Ionicons name="checkmark-circle" size={18} color={GREEN} /><Text style={{ flex: 1, fontSize: 14.5, color: LIGHT.text, lineHeight: 20 }}>{r.text}</Text></View>)}
                    {(d.wins || []).map((t: string, i: number) => <Text key={`w${i}`} style={{ fontSize: 13.5, color: LIGHT.textSecondary, lineHeight: 19 }}>{t}</Text>)}
                    {passed.length === 0 && !(d.wins || []).length && <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary }}>{tr('sc.tough')}</Text>}
                  </Card>
                </View>
                <View style={{ flex: 1 }}>
                  <Card testID="score-fixes">
                    <Label t={tr('sc.next')} colors={{ textSecondary: RED }} />
                    {missed.map((r: any, i: number) => <View key={i} style={{ flexDirection: 'row', gap: 8 }}><Ionicons name={r.critical ? 'alert-circle' : 'ellipse-outline'} size={18} color={r.critical ? RED : LIGHT.textSecondary} /><View style={{ flex: 1 }}><Text style={{ fontSize: 14.5, color: LIGHT.text, lineHeight: 20 }}>{r.text}{r.critical ? tr('sc.must') : ''}</Text>{!!r.evidence && <Text style={{ fontSize: 12.5, color: LIGHT.textSecondary, fontStyle: 'italic' }}>"{r.evidence}"</Text>}</View></View>)}
                    {missed.length === 0 && <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary }}>{tr('sc.nothing_missed')}</Text>}
                  </Card>
                </View>
              </View>
              {(d.coaching || []).length > 0 && (
                <Card testID="score-coaching">
                  <Label t={tr('sc.coaching')} colors={LIGHT} />
                  {d.coaching.map((t: string, i: number) => <View key={i} style={{ flexDirection: 'row', gap: 8 }}><Text style={{ fontSize: 14.5, fontWeight: '800', color: GOLD }}>{i + 1}.</Text><Text style={{ flex: 1, fontSize: 14.5, color: LIGHT.text, lineHeight: 21 }}>{t}</Text></View>)}
                </Card>
              )}
              <Text style={{ fontSize: 12.5, color: LIGHT.textSecondary, textAlign: 'center', lineHeight: 18 }}>{tr('sc.footer', { scorecard: d.scorecard_name || tr('sc.phone') })}</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
