import React, { useCallback, useMemo, useRef, useState } from 'react';
import { View, Pressable, Platform } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { useSharedValue, useAnimatedStyle, withTiming, runOnJS, LinearTransition, Easing } from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

export type GridItem = { key: string };
type Props = {
  items: GridItem[];
  columns: number;
  cellW: number;
  cellH: number;
  gap: number;
  editing: boolean;
  renderItem: (key: string, dragging: boolean, hovered: boolean) => React.ReactNode;
  onPress: (key: string) => void;
  onLongPress: (key: string) => void;
  onReorder: (keys: string[]) => void;
  onDragging?: (active: boolean) => void;
  /** iOS "hold over another icon": return true if dragKey may be dropped onto targetKey */
  canDropOn?: (dragKey: string, targetKey: string) => boolean;
  onDropOn?: (dragKey: string, targetKey: string) => void;
  /** Fires once when a dragged tile is pulled well past the grid edge (drag out of a folder) */
  onDragOutside?: (key: string) => void;
  outsideMargin?: number;
  /** 'vertical' ignores left/right pulls for onDragOutside (paged folders use the sides for page hops) */
  outsideAxis?: 'both' | 'vertical';
  /** Fires after the tile hangs off the left/right edge for edgeHoldMs (hop to the previous/next page). Ends the drag. */
  onEdgeHold?: (key: string, dir: 'left' | 'right') => void;
  edgeHoldMs?: number;
  testID?: string;
};

const DWELL_MS = 600;
const SETTLE_MS = 170;
const EASE = Easing.out(Easing.cubic);

const haptic = (style: 'light' | 'medium') => {
  if (Platform.OS === 'web') return;
  Haptics.impactAsync(style === 'light' ? Haptics.ImpactFeedbackStyle.Light : Haptics.ImpactFeedbackStyle.Medium).catch(() => { /* noop */ });
};

/** iOS-style grid: tap to open, hold to enter edit mode, drag to reorder while editing,
 *  hover over a folder/app to drop into it, pull past the edge to drag out. */
export const SortableGrid = ({ items, columns, cellW, cellH, gap, editing, renderItem, onPress, onLongPress, onReorder, onDragging, canDropOn, onDropOn, onDragOutside, outsideMargin = 56, outsideAxis = 'both', onEdgeHold, edgeHoldMs = 450, testID }: Props) => {
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const dragX = useSharedValue(0);
  const dragY = useSharedValue(0);
  const dragScale = useSharedValue(1);
  const startX = useSharedValue(0);
  const startY = useSharedValue(0);
  const orderRef = useRef(items.map(i => i.key));
  orderRef.current = items.map(i => i.key);
  const currentIndex = useRef(0);
  const dragRef = useRef<string | null>(null);
  const hover = useRef<{ key: string; armed: boolean; timer: any } | null>(null);
  const outFired = useRef(false);
  const moved = useRef(false);
  const count = items.length;
  const rows = Math.max(1, Math.ceil(count / columns));
  const stepX = cellW + gap;
  const stepY = cellH + gap;
  const gridW = columns * stepX - gap;
  const gridH = rows * stepY - gap;

  const slot = useCallback((i: number) => ({ x: (i % columns) * stepX, y: Math.floor(i / columns) * stepY }), [columns, stepX, stepY]);

  const clearHover = useCallback(() => {
    if (hover.current?.timer) clearTimeout(hover.current.timer);
    hover.current = null;
    setHoverKey(null);
  }, []);

  const begin = useCallback((key: string) => {
    const idx = orderRef.current.indexOf(key);
    currentIndex.current = idx;
    dragRef.current = key;
    outFired.current = false;
    moved.current = false;
    const p = slot(idx);
    dragX.value = p.x; dragY.value = p.y;
    dragScale.value = withTiming(1.12, { duration: 140, easing: EASE });
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

  // iOS feel: entering another tile's slot does nothing for a beat; if you are still there it either
  // shifts the tile out of the way (edge) or starts the drop hover (centre).
  const latest = useRef({ target: 0, inCenter: false });
  const pending = useRef<{ target: number; timer: any } | null>(null);
  const clearPending = useCallback(() => { if (pending.current) clearTimeout(pending.current.timer); pending.current = null; }, []);
  const edgeHold = useRef<{ dir: 'left' | 'right'; timer: any } | null>(null);
  const clearEdge = useCallback(() => { if (edgeHold.current) clearTimeout(edgeHold.current.timer); edgeHold.current = null; }, []);

  // Ends the drag without a drop animation (the tile is about to appear somewhere else).
  const cancelDrag = useCallback(() => {
    dragRef.current = null;
    clearPending();
    clearHover();
    setDragKey(null);
    dragScale.value = 1;
    onDragging && onDragging(false);
  }, [clearPending, clearHover, onDragging]);

  const decide = useCallback(() => {
    pending.current = null;
    const key = dragRef.current;
    const { target, inCenter } = latest.current;
    if (!key || target === currentIndex.current) return;
    const overKey = orderRef.current[target];
    if (inCenter && overKey && canDropOn && canDropOn(key, overKey)) {
      if (hover.current?.key !== overKey) {
        clearHover();
        const h = { key: overKey, armed: false, timer: null as any };
        h.timer = setTimeout(() => { h.armed = true; setHoverKey(overKey); haptic('light'); }, DWELL_MS - SETTLE_MS);
        hover.current = h;
      }
      return;
    }
    clearHover();
    moveTo(target);
  }, [canDropOn, moveTo, clearHover]);

  const track = useCallback((target: number, inCenter: boolean, outside: boolean, edge: 'left' | 'right' | null) => {
    const key = dragRef.current;
    if (!key) return;
    if (outside && onDragOutside && !outFired.current) {
      outFired.current = true;
      clearPending();
      clearHover();
      clearEdge();
      onDragOutside(key);
      return;
    }
    if (onEdgeHold) {
      if (!edge) clearEdge();
      else if (edgeHold.current?.dir !== edge) {
        clearEdge();
        edgeHold.current = { dir: edge, timer: setTimeout(() => {
          edgeHold.current = null;
          cancelDrag();
          onEdgeHold(key, edge);
        }, edgeHoldMs) };
      }
    }
    latest.current = { target, inCenter };
    moved.current = true;
    if (target === currentIndex.current) { clearPending(); clearHover(); return; }
    const overKey = orderRef.current[target];
    if (hover.current) {
      if (hover.current.key === overKey && inCenter) return;
      const slidOffCentre = hover.current.key === overKey && !inCenter;
      clearHover();
      if (slidOffCentre) { moveTo(target); return; }
    }
    if (pending.current?.target === target) return;
    clearPending();
    pending.current = { target, timer: setTimeout(decide, SETTLE_MS) };
  }, [onDragOutside, onEdgeHold, edgeHoldMs, clearHover, clearPending, clearEdge, cancelDrag, moveTo, decide]);

  const finish = useCallback(() => {
    const key = dragRef.current;
    if (!key) return;
    dragRef.current = null;
    const wasPending = !!pending.current;
    clearPending();
    clearEdge();
    const h = hover.current;
    clearHover();
    onDragging && onDragging(false);
    if ((wasPending || (h && !h.armed)) && latest.current.target !== currentIndex.current) moveTo(latest.current.target);
    if (h?.armed && onDropOn) {
      dragScale.value = withTiming(0.6, { duration: 140 });
      setTimeout(() => { setDragKey(null); dragScale.value = 1; }, 150);
      onDropOn(key, h.key);
      return;
    }
    const p = slot(currentIndex.current);
    dragX.value = withTiming(p.x, { duration: 200, easing: EASE });
    dragY.value = withTiming(p.y, { duration: 200, easing: EASE });
    dragScale.value = withTiming(1, { duration: 160 });
    setTimeout(() => setDragKey(null), 220);
  }, [slot, onDragging, onDropOn, clearHover, clearPending, moveTo]);

  // Gesture objects must survive re-renders and reorders, so worklets call through a stable bridge.
  const handlers = useRef({ begin, track, finish });
  handlers.current = { begin, track, finish };
  const invoke = useCallback((name: 'begin' | 'track' | 'finish', ...args: any[]) => (handlers.current[name] as any)(...args), []);

  const makePan = useCallback((key: string) => Gesture.Pan()
    .enabled(editing)
    .minDistance(4)
    .onBegin(() => { 'worklet'; runOnJS(invoke)('begin', key); })
    .onStart(() => { 'worklet'; startX.value = dragX.value; startY.value = dragY.value; })
    .onUpdate(e => {
      'worklet';
      dragX.value = startX.value + e.translationX;
      dragY.value = startY.value + e.translationY;
      const cx = dragX.value + cellW / 2;
      const cy = dragY.value + cellW / 2;
      const col = Math.min(columns - 1, Math.max(0, Math.floor(cx / stepX)));
      const row = Math.min(rows - 1, Math.max(0, Math.floor(cy / stepY)));
      const dx = cx - (col * stepX + cellW / 2);
      const dy = cy - (row * stepY + cellW / 2);
      const inCenter = Math.abs(dx) < cellW * 0.32 && Math.abs(dy) < cellW * 0.32;
      const outsideY = cy < -outsideMargin || cy > gridH + outsideMargin;
      const outsideX = cx < -outsideMargin || cx > gridW + outsideMargin;
      const outside = outsideY || (outsideAxis === 'both' && outsideX);
      const edge = dragX.value < -24 ? 'left' : dragX.value + cellW > gridW + 24 ? 'right' : null;
      runOnJS(invoke)('track', Math.min(row * columns + col, count - 1), inCenter, outside, edge);
    })
    .onFinalize(() => { 'worklet'; runOnJS(invoke)('finish'); }), [editing, cellW, columns, rows, count, stepX, stepY, gridW, gridH, outsideMargin, outsideAxis, invoke]);

  // Recreated every render on purpose: a memoised gesture stops receiving pointer events after the
  // first state change on web. Render order is stable (sorted by key) so a reorder never moves a node
  // under an active pointer.
  const pans = Object.fromEntries(items.map(i => [i.key, makePan(i.key)]));
  const stableItems = useMemo(() => [...items].sort((a, b) => a.key.localeCompare(b.key)), [items]);
  const indexOf = useMemo(() => Object.fromEntries(items.map((it, i) => [it.key, i])), [items]);

  const overlayStyle = useAnimatedStyle(() => ({
    position: 'absolute', left: 0, top: 0, width: cellW, zIndex: 50,
    transform: [{ translateX: dragX.value }, { translateY: dragY.value }, { scale: dragScale.value }],
  }));

  return (
    <View style={{ width: gridW, height: gridH, position: 'relative' }} testID={testID} dataSet={testID ? ({ testid: testID } as any) : undefined}>
      {stableItems.map(it => {
        const p = slot(indexOf[it.key] ?? 0);
        const hidden = dragKey === it.key;
        return (
          <Animated.View key={it.key} layout={LinearTransition.duration(220).easing(EASE)} style={{ position: 'absolute', left: p.x, top: p.y, width: cellW, height: cellH, opacity: hidden ? 0 : 1 }}>
            <GestureDetector gesture={pans[it.key]}>
              <Animated.View>
                <Pressable
                  onPress={() => { if (moved.current) { moved.current = false; return; } onPress(it.key); }}
                  onLongPress={() => { if (!editing) { haptic('medium'); onLongPress(it.key); } }}
                  delayLongPress={320}
                  style={({ pressed }) => ({ opacity: pressed && !editing ? 0.7 : 1, transform: [{ scale: pressed && !editing ? 0.96 : 1 }] })}
                  testID={`grid-cell-${it.key}`}
                  dataSet={{ testid: `grid-cell-${it.key}` } as any}
                >
                  {renderItem(it.key, false, hoverKey === it.key)}
                </Pressable>
              </Animated.View>
            </GestureDetector>
          </Animated.View>
        );
      })}
      {dragKey && (
        <Animated.View style={overlayStyle} pointerEvents="none">
          {renderItem(dragKey, true, false)}
        </Animated.View>
      )}
    </View>
  );
};
