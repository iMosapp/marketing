import React, { useState, useRef, useCallback, useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';

export interface SwipeAction {
  key: string;
  icon: string;
  label: string;
  color: string;
  bgColor: string;
  onPress: () => void;
}

interface Props {
  children: React.ReactNode;
  leftActions?: SwipeAction[];
  rightActions?: SwipeAction[];
}

const BUTTON_WIDTH = 72;
const SWIPE_THRESHOLD = 40;

// Track if user swiped (shared ref accessible by child handlers)
let _lastSwipeTime = 0;
export function wasRecentSwipe(): boolean {
  return Date.now() - _lastSwipeTime < 300;
}

export const WebSwipeableItem: React.FC<Props> = ({
  children,
  leftActions = [],
  rightActions = [],
}) => {
  const { colors } = useThemeStore();
  const [translateX, setTranslateX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const startX = useRef(0);
  const startY = useRef(0);
  const startTranslate = useRef(0);
  const isHorizontal = useRef<boolean | null>(null);

  const leftMax = leftActions.length * BUTTON_WIDTH;
  const rightMax = rightActions.length * BUTTON_WIDTH;

  const handlePointerDown = useCallback((e: any) => {
    startX.current = e.clientX || e.nativeEvent?.pageX || 0;
    startY.current = e.clientY || e.nativeEvent?.pageY || 0;
    startTranslate.current = translateX;
    isHorizontal.current = null;
  }, [translateX]);

  const handlePointerMove = useCallback((e: any) => {
    const currentX = e.clientX || e.nativeEvent?.pageX || 0;
    const currentY = e.clientY || e.nativeEvent?.pageY || 0;
    const dx = currentX - startX.current;
    const dy = currentY - startY.current;

    if (!isDragging) {
      // Only commit to horizontal if dx is clearly dominant (2x) AND exceeds minimum
      if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 2) {
        isHorizontal.current = true;
        setIsDragging(true);
      } else if (Math.abs(dy) > 8) {
        // Clearly vertical — lock out horizontal for this gesture
        isHorizontal.current = false;
      }
      return;
    }
    if (!isHorizontal.current) return;

    let newX = startTranslate.current + dx;
    newX = Math.max(-rightMax, Math.min(leftMax, newX));
    setTranslateX(newX);
  }, [isDragging, leftMax, rightMax]);

  const handlePointerUp = useCallback(() => {
    if (isDragging) {
      _lastSwipeTime = Date.now();
    }
    setIsDragging(false);
    isHorizontal.current = null;

    if (translateX > SWIPE_THRESHOLD && leftActions.length > 0) {
      setTranslateX(leftMax);
    } else if (translateX < -SWIPE_THRESHOLD && rightActions.length > 0) {
      setTranslateX(-rightMax);
    } else {
      setTranslateX(0);
    }
  }, [isDragging, translateX, leftMax, rightMax, leftActions.length, rightActions.length]);

  const handleActionPress = useCallback((action: SwipeAction) => {
    setTranslateX(0);
    setTimeout(() => action.onPress(), 150);
  }, []);

  const styles = useMemo(() => getStyles(colors), [colors]);

  return (
    <View
      style={styles.container}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      data-testid="web-swipeable-item"
    >
      {/* Left actions */}
      {leftActions.length > 0 && (
        <View style={[styles.actionsLayer, styles.actionsLeft, { width: leftMax }]}>
          {leftActions.map((action) => (
            <TouchableOpacity
              key={action.key}
              style={[styles.actionBtn, { backgroundColor: action.bgColor }]}
              onPress={() => handleActionPress(action)}
              activeOpacity={0.7}
              data-testid={`swipe-action-${action.key}`}
            >
              <Ionicons name={action.icon as any} size={20} color={action.color} />
              <Text style={[styles.actionLabel, { color: action.color }]}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Right actions */}
      {rightActions.length > 0 && (
        <View style={[styles.actionsLayer, styles.actionsRight, { width: rightMax }]}>
          {rightActions.map((action) => (
            <TouchableOpacity
              key={action.key}
              style={[styles.actionBtn, { backgroundColor: action.bgColor }]}
              onPress={() => handleActionPress(action)}
              activeOpacity={0.7}
              data-testid={`swipe-action-${action.key}`}
            >
              <Ionicons name={action.icon as any} size={20} color={action.color} />
              <Text style={[styles.actionLabel, { color: action.color }]}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Content layer */}
      <View
        style={[
          styles.content,
          {
            transform: [{ translateX }],
            transition: isDragging ? 'none' : 'transform 0.25s ease-out',
          } as any,
        ]}
      >
        {children}
      </View>
    </View>
  );
};

export default WebSwipeableItem;

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    position: 'relative',
    overflow: 'hidden',
    cursor: 'grab',
    userSelect: 'none',
    touchAction: 'pan-y',
  } as any,
  content: {
    position: 'relative',
    zIndex: 2,
    backgroundColor: colors.surface || '#1C1C1E',
  },
  actionsLayer: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    flexDirection: 'row',
    zIndex: 1,
  },
  actionsLeft: {
    left: 0,
  },
  actionsRight: {
    right: 0,
  },
  actionBtn: {
    width: 72,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 4,
  },
  actionLabel: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
});
