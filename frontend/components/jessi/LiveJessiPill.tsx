import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Animated, Easing, Platform, PanResponder } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { GOLD, GREEN, RED, tid } from '../scripts/shared';
import type { LiveJessi, OpenTarget } from '../../hooks/useLiveJessi';
import { statusText } from './LiveJessiSheet';
import { useHomeFabSpot } from '../common/HomeFab';

type Props = { live: LiveJessi; target: OpenTarget | null; who?: string; onExpand: () => void; onEnd: () => void };

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
const BESIDE_HOME = 18 + 56 + 10;   // Home pill right inset + its width + gap
const SWIPE_DOWN = 28;

// Jessi shrunk to a floating bar while the app shows what she opened. Tap it to bring the full sheet back; swipe it down to a gold dot.
export const LiveJessiPill = ({ live, target, who = 'Jessi', onExpand, onEnd }: Props) => {
  const insets = useSafeAreaInsets();
  const fab = useHomeFabSpot();
  const pulse = useRef(new Animated.Value(1)).current;
  const rise = useRef(new Animated.Value(0)).current;
  const drag = useRef(new Animated.Value(0)).current;
  const [mini, setMini] = useState(false);
  const draggedAt = useRef(0);   // web fires a click after a short drag that sprang back: ignore it
  const last = live.rows[live.rows.length - 1];
  const isLive = live.state === 'live';
  const warning = isLive && live.quiet.level === 'warning';

  useEffect(() => {
    Animated.timing(rise, { toValue: 1, duration: 260, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
  }, [rise]);
  useEffect(() => {
    if (!isLive) { pulse.stopAnimation(); pulse.setValue(1); return; }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1.15, duration: 800, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 1, duration: 800, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [isLive, pulse]);
  // The bar comes back by itself when she is about to close for silence or the session stops.
  useEffect(() => { if (warning || live.state === 'error' || live.state === 'ended') setMini(false); }, [warning, live.state]);

  const pan = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponderCapture: (_, g) => g.dy > 8 && Math.abs(g.dy) > Math.abs(g.dx),
    onPanResponderMove: (_, g) => drag.setValue(Math.max(0, g.dy)),
    onPanResponderRelease: (_, g) => {
      draggedAt.current = Date.now();
      if (g.dy > SWIPE_DOWN) { setMini(true); drag.setValue(0); }
      else Animated.spring(drag, { toValue: 0, useNativeDriver: true }).start();
    },
    onPanResponderTerminate: () => { draggedAt.current = Date.now(); Animated.spring(drag, { toValue: 0, useNativeDriver: true }).start(); },
  }), [drag]);
  const tap = () => { if (Date.now() - draggedAt.current > 350) onExpand(); };

  const where = target?.kind === 'contact' || target?.kind === 'thread' ? (target.first || target.name || '') : target?.kind === 'task' ? 'Reminder' : target?.kind === 'tasks' ? 'Tasks' : target?.kind === 'inbox' ? 'Inbox' : target?.kind === 'home' ? 'Home' : target?.kind === 'duplicates' ? 'Duplicates' : target?.kind === 'mentions' ? 'Who mentioned' : '';
  const line = live.working || (warning ? `Still there? Closing in ${live.quiet.closeIn} s, tap to keep going` : '') || (last ? `${last.role === 'rep' ? 'You' : who}: ${last.text}` : statusText(live, who));
  // Beside the Home pill (same row, just above the composer) when it is showing; otherwise above the bottom bar.
  const bottom = fab ? fab.bottom : (insets.bottom || (Platform.OS === 'web' ? 12 : 0)) + 84;

  if (mini) {
    return (
      <View pointerEvents="box-none" style={{ position: 'absolute', bottom: bottom + 6, right: fab ? BESIDE_HOME : 18, zIndex: 9999, elevation: 30 }}>
        <Animated.View pointerEvents="none" style={{ position: 'absolute', width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: GOLD,
          opacity: pulse.interpolate({ inputRange: [1, 1.15], outputRange: [isLive ? 0.7 : 0, 0] }), transform: [{ scale: pulse.interpolate({ inputRange: [1, 1.15], outputRange: [1, 1.6] }) }] }} />
        <TouchableOpacity onPress={() => setMini(false)} activeOpacity={0.85} accessibilityRole="button" accessibilityLabel={`Show ${who}`}
          style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: isLive ? GOLD : '#2C2C2E', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#0B0B0D',
            shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 10, shadowOffset: { width: 0, height: 4 } }} {...tid('live-jessi-dot')}>
          <Ionicons name="mic" size={20} color={isLive ? '#0B0B0D' : GOLD} />
        </TouchableOpacity>
      </View>
    );
  }

  const spot = fab ? { right: BESIDE_HOME, alignItems: 'flex-end' as const } : { right: 12, alignItems: 'center' as const };
  return (
    <Animated.View pointerEvents="box-none" {...pan.panHandlers} style={{ position: 'absolute', left: 12, bottom, ...spot, zIndex: 9999, elevation: 30, opacity: rise,
      transform: [{ translateY: Animated.add(rise.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }), drag) }] }}>
      <TouchableOpacity onPress={tap} activeOpacity={0.9} style={{ width: '100%', maxWidth: 420, minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#0B0B0D', borderRadius: 28, paddingVertical: 7, paddingLeft: 8, paddingRight: 10, borderWidth: 1.5, borderColor: isLive ? `${GOLD}AA` : '#3A3A3C', shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } }} {...tid('live-jessi-pill')}>
        <View pointerEvents="none" style={{ position: 'absolute', top: 4, left: '50%', marginLeft: -14, width: 28, height: 3, borderRadius: 2, backgroundColor: '#3A3A3C' }} {...tid('live-jessi-pill-grabber')} />
        <Animated.View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: isLive ? GOLD : '#1C1C1E', alignItems: 'center', justifyContent: 'center', transform: [{ scale: pulse }] }}>
          <Ionicons name="mic" size={19} color={isLive ? '#0B0B0D' : GOLD} />
        </Animated.View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Text style={{ color: '#fff', fontSize: 13, fontWeight: '800' }}>{who}</Text>
            {isLive && <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: GREEN }} />}
            <Text style={{ color: isLive ? GREEN : '#8E8E93', fontSize: 11, fontWeight: '700', fontVariant: ['tabular-nums'] }} {...tid('live-jessi-pill-timer')}>{fmt(live.seconds)}</Text>
            {!!where && <Text style={{ color: GOLD, fontSize: 11, fontWeight: '700' }} numberOfLines={1} {...tid('live-jessi-pill-where')}>· {where}</Text>}
          </View>
          <Text style={{ color: '#B9B9BF', fontSize: 12, marginTop: 1 }} numberOfLines={1} {...tid('live-jessi-pill-line')}>{line}</Text>
        </View>
        <Ionicons name="chevron-up" size={18} color="#8E8E93" />
        <TouchableOpacity onPress={onEnd} hitSlop={8} style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: isLive ? RED : '#2C2C2E', alignItems: 'center', justifyContent: 'center' }} {...tid('live-jessi-pill-end')}>
          <Ionicons name={isLive ? 'call' : 'close'} size={17} color="#fff" style={isLive ? { transform: [{ rotate: '135deg' }] } : undefined} />
        </TouchableOpacity>
      </TouchableOpacity>
    </Animated.View>
  );
};
