import React, { useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, Animated, Easing, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, usePathname } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { GOLD, RED, tid } from '../scripts/shared';
import { useRecordingStore, fmtClock, MAX_SECONDS } from '../../store/recordingStore';
import { useHomeFabStore } from '../../store/homeFabStore';
import { useLiveJessiLauncher } from '../jessi/LiveJessiProvider';

const WARN_AT = MAX_SECONDS - 120;

const PulsingDot = () => {
  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 0.25, duration: 700, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 1, duration: 700, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  return <Animated.View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: '#fff', opacity: pulse }} />;
};

// Floating red bar that follows the rep to every screen while a conversation is being recorded (and while it uploads):
// who it is with, how long, and the only button that matters. Tapping the bar opens that contact.
export const RecordingBar = () => {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const pathname = usePathname() || '';
  const fabOffset = useHomeFabStore(s => s.offset);
  const jessiActive = useLiveJessiLauncher().active;
  const session = useRecordingStore(s => s.session);
  const recording = useRecordingStore(s => s.recording);
  const seconds = useRecordingStore(s => s.seconds);
  const saving = useRecordingStore(s => s.saving);
  const failed = useRecordingStore(s => s.failed);
  const stop = useRecordingStore(s => s.stop);
  const retry = useRecordingStore(s => s.retry);
  const discard = useRecordingStore(s => s.discard);
  const rise = useRef(new Animated.Value(0)).current;
  const visible = recording || !!saving || !!failed;

  useEffect(() => {
    if (!visible) { rise.setValue(0); return; }
    Animated.timing(rise, { toValue: 1, duration: 260, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
  }, [visible, rise]);

  if (!visible) return null;
  const who = session?.contactFirst || failed?.session.contactFirst || 'the customer';
  const onContact = !!session && pathname.startsWith(`/contact/${session.contactId}`);
  const fabBottom = fabOffset > 0 ? fabOffset + 10 : Math.max(insets.bottom, Platform.OS === 'web' ? 12 : 0) + 10;
  const bottom = fabBottom + 56 + 10 + (jessiActive ? 70 : 0);
  const left = seconds >= WARN_AT ? `Stops automatically in ${fmtClock(MAX_SECONDS - seconds)}` : onContact ? 'Tap Stop & save when you are done' : `Tap to open ${who}`;
  const goThere = () => { if (session && !onContact) router.push(`/contact/${session.contactId}` as any); };
  const title = recording ? `Recording · ${who}` : failed ? `Couldn't save ${who}'s conversation` : `Saving ${who}'s conversation`;
  const line = recording ? left : failed ? `${failed.reason} · ${fmtClock(failed.duration)} kept on this phone` : saving;

  return (
    <Animated.View pointerEvents="box-none" style={{ position: 'absolute', left: 12, right: 12, bottom, zIndex: 9998, elevation: 29, opacity: rise, transform: [{ translateY: rise.interpolate({ inputRange: [0, 1], outputRange: [30, 0] }) }] }}>
      <TouchableOpacity onPress={goThere} activeOpacity={0.9} disabled={onContact || !recording}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: recording ? RED : '#0B0B0D', borderRadius: 24, paddingVertical: 9, paddingLeft: 14, paddingRight: 9, borderWidth: 1.5, borderColor: recording ? '#FF7B72' : failed ? `${RED}AA` : `${GOLD}AA`, shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } }}
        {...tid('recording-bar')}>
        {recording ? <PulsingDot /> : failed ? <Ionicons name="cloud-offline-outline" size={18} color={RED} /> : <ActivityIndicator size="small" color={GOLD} />}
        <View style={{ flex: 1, minWidth: 0 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Text style={{ color: '#fff', fontSize: 13, fontWeight: '800' }} numberOfLines={1} {...tid('recording-bar-title')}>{title}</Text>
            {recording && <Text style={{ color: '#fff', fontSize: 13, fontWeight: '800', fontVariant: ['tabular-nums'] }} {...tid('recording-bar-timer')}>{fmtClock(seconds)}</Text>}
          </View>
          <Text style={{ color: recording ? '#FFE1DE' : '#B9B9BF', fontSize: 12, marginTop: 1 }} numberOfLines={1} {...tid('recording-bar-line')}>{line}</Text>
        </View>
        {recording && (
          <TouchableOpacity onPress={stop} hitSlop={8} activeOpacity={0.85}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#fff', borderRadius: 17, height: 34, paddingHorizontal: 12 }} {...tid('recording-bar-stop')}>
            <Ionicons name="stop" size={14} color={RED} />
            <Text style={{ color: RED, fontWeight: '800', fontSize: 12 }}>Stop & save</Text>
          </TouchableOpacity>
        )}
        {!!failed && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <TouchableOpacity onPress={retry} hitSlop={8} activeOpacity={0.85}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: GOLD, borderRadius: 17, height: 34, paddingHorizontal: 12 }} {...tid('recording-bar-retry')}>
              <Ionicons name="refresh" size={14} color="#0B0B0D" />
              <Text style={{ color: '#0B0B0D', fontWeight: '800', fontSize: 12 }}>Retry</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={discard} hitSlop={8} activeOpacity={0.85} style={{ width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFFFFF14' }} {...tid('recording-bar-discard')}>
              <Ionicons name="trash-outline" size={16} color="#fff" />
            </TouchableOpacity>
          </View>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
};
