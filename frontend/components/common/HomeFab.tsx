import React, { useEffect, useState } from 'react';
import { Keyboard, Platform, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router, usePathname, useSegments } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const GOLD = '#C9A962';
// Screens that already have a bottom bar / composer / their own navigation, or where a stray tap would hurt.
const HIDE_FIRST_SEGMENT = new Set(['(tabs)', 'thread', 'call-screen', 'dialer', 'interview', 'join', 'nda', 'port-out', 'notifications', 'touchpoints', 'quick-send', 'scripts', 'welcome-jessi', 'a2p-onboarding']);
const HIDE_PATHS = [/^campaigns\/[^/]+$/, /^contact\/sold-wizard$/];

export const goHome = () => {
  try { if (router.canDismiss()) router.dismissAll(); } catch {}
  router.replace('/(tabs)/home' as any);
};

// Same look as the home screen "+" button: a gold 56pt circle bottom-right, but it jumps straight back to Home
// from any deep screen instead of backing out one step at a time.
export const HomeFab = () => {
  const segments = useSegments() as string[];
  const pathname = (usePathname() || '').replace(/^\//, '');
  const insets = useSafeAreaInsets();
  const [keyboardUp, setKeyboardUp] = useState(false);
  useEffect(() => {
    if (Platform.OS === 'web') return;
    const s = Keyboard.addListener(Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow', () => setKeyboardUp(true));
    const h = Keyboard.addListener(Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide', () => setKeyboardUp(false));
    return () => { s.remove(); h.remove(); };
  }, []);
  if (!segments.length || HIDE_FIRST_SEGMENT.has(segments[0]) || HIDE_PATHS.some(rx => rx.test(pathname)) || keyboardUp) return null;
  return (
    <TouchableOpacity
      onPress={goHome}
      accessibilityRole="button"
      accessibilityLabel="Go to Home"
      hitSlop={6}
      activeOpacity={0.85}
      style={{ position: 'absolute', bottom: Math.max(insets.bottom, 12) + 10, right: 18, width: 56, height: 56, borderRadius: 28, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center',
        shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 10, shadowOffset: { width: 0, height: 4 }, elevation: 8, zIndex: 50 }}
      testID="home-fab-jump"
      dataSet={{ testid: 'home-fab-jump' } as any}
    >
      <Ionicons name="home" size={26} color="#000" />
    </TouchableOpacity>
  );
};
