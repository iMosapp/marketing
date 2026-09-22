import React, { useEffect, useMemo, useRef } from 'react';
import { Modal, View, Text, Animated, Easing, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { PrimaryButton } from '../ui/PrimaryButton';
import { GOLD, GREEN, RED, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';

const COLORS = [GOLD, GREEN, RED, '#0A84FF', '#FFFFFF', '#FFD60A'];
const PIECES = 46;

const Piece = ({ i, width, height }: { i: number; width: number; height: number }) => {
  const t = useRef(new Animated.Value(0)).current;
  const seed = useMemo(() => ({ x: Math.random() * width, drift: (Math.random() - 0.5) * 160, delay: Math.random() * 900, dur: 2200 + Math.random() * 1400, size: 6 + Math.random() * 8, color: COLORS[i % COLORS.length], round: Math.random() > 0.5 }), []);
  useEffect(() => {
    Animated.loop(Animated.sequence([Animated.delay(seed.delay), Animated.timing(t, { toValue: 1, duration: seed.dur, easing: Easing.in(Easing.quad), useNativeDriver: true }), Animated.timing(t, { toValue: 0, duration: 0, useNativeDriver: true })])).start();
  }, []);
  return (
    <Animated.View pointerEvents="none" style={{
      position: 'absolute', top: -20, left: seed.x, width: seed.size, height: seed.size * (seed.round ? 1 : 0.5), borderRadius: seed.round ? seed.size / 2 : 2, backgroundColor: seed.color,
      opacity: t.interpolate({ inputRange: [0, 0.1, 0.9, 1], outputRange: [0, 1, 1, 0] }),
      transform: [{ translateY: t.interpolate({ inputRange: [0, 1], outputRange: [0, height + 40] }) }, { translateX: t.interpolate({ inputRange: [0, 1], outputRange: [0, seed.drift] }) }, { rotate: t.interpolate({ inputRange: [0, 1], outputRange: ['0deg', `${540 + i * 20}deg`] }) }],
    }} />
  );
};

/** Confetti + Jessi's line the first time a Jessi-onboarded user sends their digital card. */
export const FirstWinCelebration = ({ visible, firstName, message, onClose }: { visible: boolean; firstName?: string; message?: string; onClose: () => void }) => {
  const { colors } = useThemeStore();
  const { width, height } = useWindowDimensions();
  const pop = useRef(new Animated.Value(0)).current;
  useEffect(() => { if (visible) { pop.setValue(0); Animated.spring(pop, { toValue: 1, friction: 6, tension: 80, useNativeDriver: true }).start(); } }, [visible]);
  if (!visible) return null;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.72)', alignItems: 'center', justifyContent: 'center', padding: SPACE.xl }} {...tid('first-win-celebration')}>
        {Array.from({ length: PIECES }).map((_, i) => <Piece key={i} i={i} width={width} height={height} />)}
        <Animated.View style={{ width: '100%', maxWidth: 420, backgroundColor: colors.card, borderRadius: RADIUS.xl, borderWidth: 1, borderColor: tint(GOLD, 0.6), padding: SPACE.xl, alignItems: 'center', gap: SPACE.md, transform: [{ scale: pop }] }}>
          <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: tint(GOLD, 0.18), alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="trophy" size={36} color={GOLD} />
          </View>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>FIRST WIN</Text>
          <Text style={{ fontSize: 26, fontWeight: '800', color: colors.text, textAlign: 'center' }} {...tid('first-win-title')}>Your first card is out the door{firstName ? `, ${firstName}` : ''}!</Text>
          {!!message && (
            <View style={{ alignSelf: 'stretch', backgroundColor: GOLD, borderRadius: RADIUS.md, borderBottomLeftRadius: 4, padding: SPACE.md }}>
              <Text style={{ fontSize: TYPE.body, color: '#000', lineHeight: 21 }} {...tid('first-win-message')}>{message}</Text>
              <Text style={{ fontSize: 10, color: 'rgba(0,0,0,0.6)', marginTop: 4, fontWeight: '700' }}>JESSI · also texted to you</Text>
            </View>
          )}
          <PrimaryButton full size="lg" icon="arrow-forward" label="Keep going" onPress={onClose} testID="first-win-close" />
        </Animated.View>
      </View>
    </Modal>
  );
};
