import React, { useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, Animated, Easing, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { GOLD, GREEN, RED, tid } from '../scripts/shared';
import type { LiveJessi, OpenTarget } from '../../hooks/useLiveJessi';
import { statusText } from './LiveJessiSheet';

type Props = { live: LiveJessi; target: OpenTarget | null; who?: string; onExpand: () => void; onEnd: () => void };

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

// Jessi shrunk to a floating bar while the app shows what she opened. Tap it to bring the full sheet back.
export const LiveJessiPill = ({ live, target, who = 'Jessi', onExpand, onEnd }: Props) => {
  const insets = useSafeAreaInsets();
  const pulse = useRef(new Animated.Value(1)).current;
  const rise = useRef(new Animated.Value(0)).current;
  const last = live.rows[live.rows.length - 1];
  const isLive = live.state === 'live';

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

  const where = target?.kind === 'contact' || target?.kind === 'thread' ? (target.first || target.name || '') : target?.kind === 'task' ? 'Reminder' : target?.kind === 'tasks' ? 'Tasks' : target?.kind === 'inbox' ? 'Inbox' : target?.kind === 'home' ? 'Home' : target?.kind === 'duplicates' ? 'Duplicates' : '';
  const line = live.working || (last ? `${last.role === 'rep' ? 'You' : who}: ${last.text}` : statusText(live, who));

  return (
    <Animated.View pointerEvents="box-none" style={{ position: 'absolute', left: 12, right: 12, bottom: (insets.bottom || (Platform.OS === 'web' ? 12 : 0)) + 84, zIndex: 9999, elevation: 30, opacity: rise, transform: [{ translateY: rise.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }) }] }}>
      <TouchableOpacity onPress={onExpand} activeOpacity={0.9} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#0B0B0D', borderRadius: 24, paddingVertical: 8, paddingLeft: 8, paddingRight: 10, borderWidth: 1.5, borderColor: isLive ? `${GOLD}AA` : '#3A3A3C', shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } }} {...tid('live-jessi-pill')}>
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
