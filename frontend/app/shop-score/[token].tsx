import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { CallRecordingPlayer } from '../../components/CallRecordingPlayer';
import { ScoreRing } from '../../components/scorecards/ScoreRing';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { Label, deptLabel, fmtWhen, LIGHT, GOLD, GREEN, RED, tid } from '../../components/mystery-shops/shared';

const Card = ({ children, testID }: { children: React.ReactNode; testID: string }) => (
  <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18, gap: 12 }} {...tid(testID)}>{children}</View>
);

// The scorecard texted to whoever got mystery shopped. No login, light palette, one call only.
export default function PublicShopScore() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => { if (token) api.get(`/public/shop-score/${token}`).then(r => setD(r.data)).catch(() => setError('This scorecard link is not valid.')); }, [token]);

  const wide = width > 800;
  const passed = (d?.results || []).filter((r: any) => r.passed);
  const missed = (d?.results || []).filter((r: any) => !r.passed);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: LIGHT.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 32 : 16, paddingBottom: 60, alignItems: 'center' }}>
        <View style={{ width: '100%', maxWidth: 680, gap: 16 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>I'M ON SOCIAL · MYSTERY SHOP SCORECARD</Text>
          {error ? <Text style={{ fontSize: 15, color: LIGHT.textSecondary }} {...tid('score-error')}>{error}</Text> : !d ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <Card testID="score-hero">
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 18 }}>
                  <ScoreRing pct={d.score_pct} size={104} stroke={9} colors={LIGHT} label="score" testID="score-ring" />
                  <View style={{ flex: 1, gap: 4 }}>
                    <Text style={{ fontSize: wide ? 26 : 22, fontWeight: '800', color: LIGHT.text }} {...tid('score-title')}>{d.first_name ? `${d.first_name}, here's how that call went` : 'Your mystery shop'}</Text>
                    <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary, lineHeight: 19 }} {...tid('score-meta')}>{deptLabel(d.department)} · {d.challenge_title}{d.persona_name ? ` · the shopper was ${d.persona_name.split(' ')[0]}` : ''}{d.ended_at ? ` · ${fmtWhen(d.ended_at)}` : ''}{d.store_name ? ` · ${d.store_name}` : ''}</Text>
                  </View>
                </View>
                {!!d.summary && <Text style={{ fontSize: 15, color: LIGHT.text, lineHeight: 23 }} {...tid('score-summary')}>{d.summary}</Text>}
              </Card>
              {!!d.recording_url && (
                <Card testID="score-recording">
                  <Label t="LISTEN BACK" colors={LIGHT} />
                  <CallRecordingPlayer url={resolvePhotoUrl(d.recording_url) || d.recording_url} tint={GOLD} textColor={LIGHT.text} subColor={LIGHT.textSecondary} trackColor={LIGHT.border} />
                </Card>
              )}
              <View style={{ flexDirection: wide ? 'row' : 'column', gap: 16 }}>
                <View style={{ flex: 1 }}>
                  <Card testID="score-wins">
                    <Label t="WHAT YOU NAILED" colors={{ textSecondary: GREEN }} />
                    {passed.map((r: any, i: number) => <View key={i} style={{ flexDirection: 'row', gap: 8 }}><Ionicons name="checkmark-circle" size={18} color={GREEN} /><Text style={{ flex: 1, fontSize: 14.5, color: LIGHT.text, lineHeight: 20 }}>{r.text}</Text></View>)}
                    {(d.wins || []).map((t: string, i: number) => <Text key={`w${i}`} style={{ fontSize: 13.5, color: LIGHT.textSecondary, lineHeight: 19 }}>{t}</Text>)}
                    {passed.length === 0 && !(d.wins || []).length && <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary }}>Tough one. The next call is a clean slate.</Text>}
                  </Card>
                </View>
                <View style={{ flex: 1 }}>
                  <Card testID="score-fixes">
                    <Label t="WORK ON NEXT" colors={{ textSecondary: RED }} />
                    {missed.map((r: any, i: number) => <View key={i} style={{ flexDirection: 'row', gap: 8 }}><Ionicons name={r.critical ? 'alert-circle' : 'ellipse-outline'} size={18} color={r.critical ? RED : LIGHT.textSecondary} /><View style={{ flex: 1 }}><Text style={{ fontSize: 14.5, color: LIGHT.text, lineHeight: 20 }}>{r.text}{r.critical ? '  · must-have' : ''}</Text>{!!r.evidence && <Text style={{ fontSize: 12.5, color: LIGHT.textSecondary, fontStyle: 'italic' }}>"{r.evidence}"</Text>}</View></View>)}
                    {missed.length === 0 && <Text style={{ fontSize: 13.5, color: LIGHT.textSecondary }}>Nothing missed on the scorecard. Seriously well done.</Text>}
                  </Card>
                </View>
              </View>
              {(d.coaching || []).length > 0 && (
                <Card testID="score-coaching">
                  <Label t="COACHING" colors={LIGHT} />
                  {d.coaching.map((t: string, i: number) => <View key={i} style={{ flexDirection: 'row', gap: 8 }}><Text style={{ fontSize: 14.5, fontWeight: '800', color: GOLD }}>{i + 1}.</Text><Text style={{ flex: 1, fontSize: 14.5, color: LIGHT.text, lineHeight: 21 }}>{t}</Text></View>)}
                </Card>
              )}
              <Text style={{ fontSize: 12.5, color: LIGHT.textSecondary, textAlign: 'center', lineHeight: 18 }}>Graded with the {d.scorecard_name || 'phone'} scorecard by I'm On Social. Want to practice this exact call any time? Ask your manager about I'm On Social training.</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
