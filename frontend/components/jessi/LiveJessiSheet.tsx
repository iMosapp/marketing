import React, { useEffect, useRef } from 'react';
import { View, Text, Modal, TouchableOpacity, ScrollView, Animated, Easing, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, GREEN, RED, tid } from '../scripts/shared';
import type { LiveJessi } from '../../hooks/useLiveJessi';

type Props = { visible: boolean; onClose: () => void; live: LiveJessi; title?: string; who?: string; hint?: string; onRetry: () => void; onCollapse?: () => void };

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
export const REASONS: Record<string, string> = { idle: 'Closed after a quiet spell', daily_cap: "Today's minutes are used up", connection_lost: 'The connection dropped', close_requested: 'Conversation ended', expired: 'Session limit reached', content: 'Ended by the safety filter', no_start: 'did not pick up', unmounted: 'Closed' };

export const statusText = (live: LiveJessi, who = 'Jessi') =>
  live.state === 'connecting' ? `Connecting to ${who}` : live.state === 'ending' ? 'Wrapping up' : live.state === 'live' ? (live.working || 'Listening') : live.state === 'ended' ? (live.closeReason === 'no_start' ? `${who} did not pick up` : REASONS[live.closeReason] || 'Conversation ended') : 'Could not connect';

// Full-screen live conversation: gold orb, live captions, one End button. The session itself lives in LiveJessiProvider,
// so shrinking this sheet (chevron) keeps Jessi talking while the app navigates underneath.
export const LiveJessiSheet = ({ visible, onClose, live, title = 'Talk to Jessi', who = 'Jessi', hint, onRetry, onCollapse }: Props) => {
  const pulse = useRef(new Animated.Value(1)).current;
  const scroll = useRef<ScrollView>(null);

  useEffect(() => {
    if (live.state !== 'live') { pulse.stopAnimation(); pulse.setValue(1); return; }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1.12, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [live.state, pulse]);
  useEffect(() => { scroll.current?.scrollToEnd({ animated: true }); }, [live.rows]);

  const end = () => { if (live.state === 'live' || live.state === 'connecting') live.stop('close_requested'); else onClose(); };
  const busy = live.state === 'connecting' || live.state === 'ending';
  const canCollapse = !!onCollapse && (live.state === 'live' || live.state === 'connecting');

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={canCollapse ? onCollapse : end} presentationStyle="fullScreen">
      <View style={{ flex: 1, backgroundColor: '#0B0B0D' }} {...tid('live-jessi-sheet')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 18, paddingTop: 18, paddingBottom: 8, gap: 10 }}>
          {canCollapse && (
            <TouchableOpacity onPress={onCollapse} hitSlop={10} style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' }} {...tid('live-jessi-collapse')}>
              <Ionicons name="chevron-down" size={22} color="#D5D5DA" />
            </TouchableOpacity>
          )}
          <View style={{ flex: 1 }}>
            <Text style={{ color: '#fff', fontSize: 18, fontWeight: '800' }} {...tid('live-jessi-title')}>{title}</Text>
            <Text style={{ color: '#8E8E93', fontSize: 12, marginTop: 2 }} {...tid('live-jessi-status')}>{statusText(live, who)}{live.voice ? ` · ${live.voice}` : ''}</Text>
          </View>
          <View style={{ backgroundColor: live.state === 'live' ? `${GREEN}22` : '#1C1C1E', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 5, flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('live-jessi-timer')}>
            {live.state === 'live' && <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: GREEN }} />}
            <Text style={{ color: live.state === 'live' ? GREEN : '#8E8E93', fontWeight: '800', fontSize: 13, fontVariant: ['tabular-nums'] }}>{fmt(live.seconds)}</Text>
          </View>
        </View>

        <View style={{ alignItems: 'center', paddingVertical: 22 }}>
          <Animated.View style={{ width: 128, height: 128, borderRadius: 64, backgroundColor: `${GOLD}1A`, borderWidth: 2, borderColor: live.state === 'live' ? GOLD : '#2C2C2E', alignItems: 'center', justifyContent: 'center', transform: [{ scale: pulse }] }} {...tid('live-jessi-orb')}>
            <View style={{ width: 88, height: 88, borderRadius: 44, backgroundColor: live.state === 'live' ? GOLD : '#1C1C1E', alignItems: 'center', justifyContent: 'center' }}>
              {busy ? <ActivityIndicator color={GOLD} /> : <Ionicons name={live.state === 'ended' || live.state === 'error' ? 'checkmark' : 'mic'} size={38} color={live.state === 'live' ? '#0B0B0D' : GOLD} />}
            </View>
          </Animated.View>
          {live.capLeft !== null && live.state === 'live' && <Text style={{ color: '#8E8E93', fontSize: 11, marginTop: 10 }} {...tid('live-jessi-cap')}>{Math.max(0, Math.floor((live.capLeft - live.seconds) / 60))} min left today</Text>}
          {canCollapse && !hint && <Text style={{ color: '#5A5A5F', fontSize: 11, marginTop: 8 }} {...tid('live-jessi-collapse-hint')}>Say "pull up Sarah" or "open her thread" and the app follows along</Text>}
        </View>

        <ScrollView ref={scroll} style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 18, paddingBottom: 16, gap: 10 }} {...tid('live-jessi-captions')}>
          {live.rows.length === 0 && live.state === 'live' && <Text style={{ color: '#5A5A5F', fontSize: 13, textAlign: 'center', marginTop: 10 }} {...tid('live-jessi-hint')}>{hint || 'Just talk. Ask who you should reach out to today, or say a name.'}</Text>}
          {live.rows.map(r => (
            <View key={r.id} style={{ alignSelf: r.role === 'rep' ? 'flex-end' : 'flex-start', maxWidth: '86%', backgroundColor: r.role === 'rep' ? '#1F1F23' : `${GOLD}1F`, borderRadius: 14, paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: r.role === 'rep' ? '#2C2C2E' : `${GOLD}40` }} {...tid(`live-caption-${r.role}`)}>
              <Text style={{ color: r.role === 'rep' ? '#D5D5DA' : '#F3E6C4', fontSize: 14, lineHeight: 20 }}>{r.text}</Text>
            </View>
          ))}
          {!!live.error && <Text style={{ color: RED, fontSize: 13, textAlign: 'center', marginTop: 8 }} {...tid('live-jessi-error')}>{live.error}</Text>}
        </ScrollView>

        <View style={{ padding: 18, paddingBottom: 30, gap: 10 }}>
          {(live.state === 'error' || live.state === 'ended') && (
            <TouchableOpacity onPress={onRetry} style={{ borderRadius: 26, paddingVertical: 14, alignItems: 'center', borderWidth: 1, borderColor: `${GOLD}66` }} {...tid('live-jessi-retry')}>
              <Text style={{ color: GOLD, fontWeight: '800', fontSize: 15 }}>Talk again</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={end} disabled={live.state === 'ending'} style={{ borderRadius: 26, paddingVertical: 15, alignItems: 'center', backgroundColor: live.state === 'live' ? RED : '#1C1C1E', opacity: live.state === 'ending' ? 0.6 : 1 }} {...tid('live-jessi-end')}>
            <Text style={{ color: '#fff', fontWeight: '800', fontSize: 15 }}>{live.state === 'live' || live.state === 'connecting' ? 'End conversation' : 'Close'}</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};
