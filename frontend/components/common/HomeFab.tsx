import React, { useEffect, useState } from 'react';
import { Keyboard, Platform, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router, usePathname, useSegments } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useHomeFabStore } from '../../store/homeFabStore';

const GOLD = '#C9A962';
// Screens that already own the bottom edge (composer, chat, bottom bar) or their own navigation, or where a stray tap would hurt.
const HIDE_FIRST_SEGMENT = new Set(['(tabs)', 'thread', 'call-screen', 'dialer', 'interview', 'join', 'nda', 'port-out', 'notifications', 'touchpoints', 'quick-send', 'scripts', 'welcome-jessi', 'a2p-onboarding', 'help', 'jessie']);
const HIDE_PATHS = [/^campaigns\/[^/]+$/, /^contact\/sold-wizard$/, /^settings\/create-card$/];

export const goHome = () => {
  try { if (router.canDismiss()) router.dismissAll(); } catch {}
  router.replace('/(tabs)/home' as any);
};

// Tracks the on-screen keyboard: native events on iOS/Android, visualViewport shrink on web (Safari/PWA has no keyboard events).
const useKeyboardUp = () => {
  const [up, setUp] = useState(false);
  useEffect(() => {
    if (Platform.OS === 'web') {
      const vv = typeof window !== 'undefined' ? (window as any).visualViewport : null;
      if (!vv) return;
      const onResize = () => setUp(window.innerHeight - vv.height > 120);
      vv.addEventListener('resize', onResize);
      return () => vv.removeEventListener('resize', onResize);
    }
    const s = Keyboard.addListener(Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow', () => setUp(true));
    const h = Keyboard.addListener(Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide', () => setUp(false));
    return () => { s.remove(); h.remove(); };
  }, []);
  return up;
};

// Same look as the home screen "+" button: a gold 56pt circle bottom-right that jumps straight back to Home from any deep
// screen. Screens with their own bottom composer hide it (useHideHomeFab); fixed bottom bars push it up (useHomeFabOffset).
export const HomeFab = () => {
  const segments = useSegments() as string[];
  const pathname = (usePathname() || '').replace(/^\//, '');
  const insets = useSafeAreaInsets();
  const keyboardUp = useKeyboardUp();
  const blockers = useHomeFabStore(s => s.blockers);
  const offset = useHomeFabStore(s => s.offset);
  if (!segments.length || HIDE_FIRST_SEGMENT.has(segments[0]) || HIDE_PATHS.some(rx => rx.test(pathname)) || keyboardUp || blockers > 0) return null;
  const bottom = offset > 0 ? offset + 10 : Math.max(insets.bottom, 12) + 10;
  return (
    <TouchableOpacity
      onPress={goHome}
      accessibilityRole="button"
      accessibilityLabel="Go to Home"
      hitSlop={6}
      activeOpacity={0.85}
      style={{ position: 'absolute', bottom, right: 18, width: 56, height: 56, borderRadius: 28, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center',
        shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 10, shadowOffset: { width: 0, height: 4 }, elevation: 8, zIndex: 50 }}
      testID="home-fab-jump"
      dataSet={{ testid: 'home-fab-jump' } as any}
    >
      <Ionicons name="home" size={26} color="#000" />
    </TouchableOpacity>
  );
};
