import React, { useCallback, useMemo, useRef, useState } from 'react';
import { View, Pressable, Platform } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { useSharedValue, useAnimatedStyle, withSpring, withTiming, runOnJS, LinearTransition } from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

export type GridItem = { key: string };
type Props = {
  items: GridItem[];
  columns: number;
  cellW: number;
  cellH: number;
  gap: number;
  editing: boolean;
  renderItem: (key: string, dragging: boolean) => React.ReactNode;
  onPress: (key: string) => void;
  onLongPress: (key: string) => void;
  onReorder: (keys: string[]) => void;
  onDragging?: (active: boolean) => void;
  testID?: string;
};

const haptic = (style: 'light' | 'medium') => {
  if (Platform.OS === 'web') return;
  Haptics.impactAsync(style === 'light' ? Haptics.ImpactFeedbackStyle.Light : Haptics.ImpactFeedbackStyle.Medium).catch(() => { /* noop */ });
};

/** iOS-style grid: tap to open, hold to enter edit mode, drag to reorder while editing. */
export const SortableGrid = ({ items, columns, cellW, cellH, gap, editing, renderItem, onPress, onLongPress, onReorder, onDragging, testID }: Props) => {
  const [dragKey, setDragKey] = useState<string | null>(null);
  const dragX = useSharedValue(0);
  const dragY = useSharedValue(0);
  const dragScale = useSharedValue(1);
  const orderRef = useRef(items.map(i => i.key));
  orderRef.current = items.map(i => i.key);
  const currentIndex = useRef(0);
  const rows = Math.max(1, Math.ceil(items.length / columns));
  const stepX = cellW + gap;
  const stepY = cellH + gap;

  const slot = useCallback((i: number) => ({ x: (i % columns) * stepX, y: Math.floor(i / columns) * stepY }), [columns, stepX, stepY]);

  const begin = useCallback((key: string) => {
    const idx = orderRef.current.indexOf(key);
    currentIndex.current = idx;
    const p = slot(idx);
    dragX.value = p.x; dragY.value = p.y;
    dragScale.value = withSpring(1.12);
    setDragKey(key);
    onDragging && onDragging(true);
    haptic('medium');
  }, [slot, onDragging]);

  const moveTo = useCallback((target: number) => {
    const from = currentIndex.current;
    if (target === from || target < 0 || target >= orderRef.current.length) return;
    const next = [...orderRef.current];
    const [k] = next.splice(from, 1);
    next.splice(target, 0, k);
    currentIndex.current = target;
    orderRef.current = next;
    haptic('light');
    onReorder(next);
  }, [onReorder]);

  const finish = useCallback(() => {
    const p = slot(currentIndex.current);
    dragX.value = withSpring(p.x, { damping: 22, stiffness: 240 });
    dragY.value = withSpring(p.y, { damping: 22, stiffness: 240 });
    dragScale.value = withTiming(1, { duration: 160 });
    onDragging && onDragging(false);
    setTimeout(() => setDragKey(null), 220);
  }, [slot, onDragging]);

  const startX = useSharedValue(0);
  const startY = useSharedValue(0);

  const makePan = useCallback((key: string) => Gesture.Pan()
    .enabled(editing)
    .minDistance(4)
    .onBegin(() => {
      'worklet';
      runOnJS(begin)(key);
    })
    .onStart(() => {
      'worklet';
      startX.value = dragX.value; startY.value = dragY.value;
    })
    .onUpdate(e => {
      'worklet';
      dragX.value = startX.value + e.translationX;
      dragY.value = startY.value + e.translationY;
      const cx = dragX.value + cellW / 2;
      const cy = dragY.value + cellH / 2;
      const col = Math.min(columns - 1, Math.max(0, Math.floor(cx / stepX)));
      const row = Math.min(rows - 1, Math.max(0, Math.floor(cy / stepY)));
      runOnJS(moveTo)(row * columns + col);
    })
    .onFinalize(() => { 'worklet'; runOnJS(finish)(); }), [editing, cellW, cellH, columns, rows, stepX, stepY, begin, moveTo, finish]);

  const pans = useMemo(() => Object.fromEntries(items.map(i => [i.key, makePan(i.key)])), [items, makePan]);

  const overlayStyle = useAnimatedStyle(() => ({
    position: 'absolute', left: 0, top: 0, width: cellW, zIndex: 50,
    transform: [{ translateX: dragX.value }, { translateY: dragY.value }, { scale: dragScale.value }],
  }));

  return (
    <View style={{ width: columns * stepX - gap, height: rows * stepY - gap, position: 'relative' }} testID={testID} dataSet={testID ? ({ testid: testID } as any) : undefined}>
      {items.map((it, i) => {
        const p = slot(i);
        const hidden = dragKey === it.key;
        return (
          <Animated.View key={it.key} layout={LinearTransition.springify().damping(20).stiffness(220)} style={{ position: 'absolute', left: p.x, top: p.y, width: cellW, height: cellH, opacity: hidden ? 0 : 1 }}>
            <GestureDetector gesture={pans[it.key]}>
              <Animated.View>
                <Pressable
                  onPress={() => onPress(it.key)}
                  onLongPress={() => { if (!editing) { haptic('medium'); onLongPress(it.key); } }}
                  delayLongPress={320}
                  style={({ pressed }) => ({ opacity: pressed && !editing ? 0.7 : 1, transform: [{ scale: pressed && !editing ? 0.96 : 1 }] })}
                  testID={`grid-cell-${it.key}`}
                  dataSet={{ testid: `grid-cell-${it.key}` } as any}
                >
                  {renderItem(it.key, false)}
                </Pressable>
              </Animated.View>
            </GestureDetector>
          </Animated.View>
        );
      })}
      {dragKey && (
        <Animated.View style={overlayStyle} pointerEvents="none">
          {renderItem(dragKey, true)}
        </Animated.View>
      )}
    </View>
  );
};
