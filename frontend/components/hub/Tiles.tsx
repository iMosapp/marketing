import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Animated, { useSharedValue, useAnimatedStyle, withRepeat, withSequence, withTiming, withDelay, cancelAnimation } from 'react-native-reanimated';
import type { HubApp } from './layout';

export const TILE_RADIUS = 18;
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const Badge = ({ n }: { n?: number }) => !n ? null : (
  <View style={styles.badge} {...tid('tile-badge')}>
    <Text style={styles.badgeText}>{n > 99 ? '99+' : n}</Text>
  </View>
);

export const Jiggle = ({ on, children, seed = 0 }: { on: boolean; children: React.ReactNode; seed?: number }) => {
  const rot = useSharedValue(0);
  useEffect(() => {
    if (on) {
      rot.value = withDelay((seed * 37) % 160, withRepeat(withSequence(withTiming(-1.6, { duration: 130 }), withTiming(1.6, { duration: 130 })), -1, true));
    } else {
      cancelAnimation(rot);
      rot.value = withTiming(0, { duration: 120 });
    }
  }, [on]);
  const style = useAnimatedStyle(() => ({ transform: [{ rotate: `${rot.value}deg` }] }));
  return <Animated.View style={style}>{children}</Animated.View>;
};

/** Gold flash that fades out: marks where a dragged-out app just landed. */
export const Landing = ({ on, children }: { on: boolean; children: React.ReactNode }) => {
  const glow = useSharedValue(0);
  useEffect(() => {
    if (on) glow.value = withSequence(withTiming(1, { duration: 120 }), withTiming(1, { duration: 900 }), withTiming(0, { duration: 600 }));
  }, [on]);
  const style = useAnimatedStyle(() => ({
    borderRadius: TILE_RADIUS + 4,
    shadowColor: '#C9A962', shadowOpacity: glow.value * 0.9, shadowRadius: 14, shadowOffset: { width: 0, height: 0 },
    transform: [{ scale: 1 + glow.value * 0.06 }],
  }));
  return <Animated.View style={style}>{children}</Animated.View>;
};

export const AppTile = ({ app, size, colors, editing, dimLabel, hovered }: { app: HubApp; size: number; colors: any; editing?: boolean; dimLabel?: boolean; hovered?: boolean }) => (
  <View style={{ width: size, alignItems: 'center', transform: [{ scale: hovered ? 1.08 : 1 }] }} {...tid(`app-tile-${app.id}`)}>
    <View style={[styles.tile, { width: size, height: size, backgroundColor: colors.card, borderColor: hovered ? '#C9A962' : `${app.color}55`, borderWidth: hovered ? 2 : 1 }]}>
      <View style={[StyleSheet.absoluteFill, { borderRadius: TILE_RADIUS, backgroundColor: `${app.color}1A` }]} />
      <View style={styles.gloss} />
      <Ionicons name={app.icon as any} size={Math.round(size * 0.42)} color={app.color} />
      <Badge n={app.badge} />
      {!!app.statusDot && <View style={[styles.dot, { backgroundColor: app.statusDot === 'green' ? '#34C759' : app.statusDot === 'red' ? '#FF3B30' : '#8E8E93' }]} />}
      {editing && <View style={styles.editRing} />}
    </View>
    <Text style={[styles.label, { color: dimLabel ? colors.textSecondary : colors.text }]} numberOfLines={2}>{app.title}</Text>
  </View>
);

export const FolderTile = ({ title, apps, size, colors, editing, badge, hovered }: { title: string; apps: HubApp[]; size: number; colors: any; editing?: boolean; badge?: number; hovered?: boolean }) => {
  const mini = Math.floor((size - 22) / 3);
  return (
    <View style={{ width: size, alignItems: 'center', transform: [{ scale: hovered ? 1.1 : 1 }] }} {...tid(`folder-tile-${title}`)}>
      <View style={[styles.tile, { width: size, height: size, backgroundColor: hovered ? 'rgba(201,169,98,0.18)' : (colors.surface || colors.card), borderColor: hovered ? '#C9A962' : 'rgba(255,255,255,0.10)', borderWidth: hovered ? 2 : 1, padding: 8 }]}>
        <View style={styles.gloss} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 3, width: mini * 3 + 6 }}>
          {apps.slice(0, 9).map(a => (
            <View key={a.id} style={{ width: mini, height: mini, borderRadius: Math.max(4, mini * 0.3), backgroundColor: `${a.color}33`, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={a.icon as any} size={Math.max(9, Math.round(mini * 0.6))} color={a.color} />
            </View>
          ))}
        </View>
        <Badge n={badge} />
        {editing && <View style={styles.editRing} />}
      </View>
      <Text style={[styles.label, { color: colors.text }]} numberOfLines={2}>{title}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  tile: { borderRadius: TILE_RADIUS, borderWidth: 1, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  gloss: { position: 'absolute', top: 0, left: 0, right: 0, height: 1, backgroundColor: 'rgba(255,255,255,0.18)' },
  label: { fontSize: 11, fontWeight: '600', textAlign: 'center', marginTop: 6, lineHeight: 13, letterSpacing: 0.1 },
  badge: { position: 'absolute', top: -2, right: -2, minWidth: 20, height: 20, borderRadius: 10, paddingHorizontal: 5, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#0B0B0D' },
  badgeText: { fontSize: 11, fontWeight: '800', color: '#FFF' },
  dot: { position: 'absolute', bottom: 6, right: 6, width: 8, height: 8, borderRadius: 4 },
  editRing: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: TILE_RADIUS, borderWidth: 1.5, borderColor: '#C9A96299' },
});
