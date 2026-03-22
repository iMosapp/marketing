import React, { useRef, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useThemeStore } from '../store/themeStore';
interface SwipeAction {
  key: string;
  icon: string;
  label: string;
  color: string;
  bgColor: string;
  onPress: () => void;
}

interface WebSwipeableItemProps {
  children: React.ReactNode;
  leftActions?: SwipeAction[];
  rightActions?: SwipeAction[];
}

export default function WebSwipeableItem({
  children,
  leftActions = [],
  rightActions = [],
}: WebSwipeableItemProps) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const [translateX, setTranslateX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [swipeJustEnded, setSwipeJustEnded] = useState(false);
  const startX = useRef(0);
  const startY = useRef(0);
  const startTranslate = useRef(0);
  const isHorizontal = useRef<boolean | null>(null);
  const hasMoved = useRef(false);
  // Track if we should block the next click (after a swipe gesture)
  const blockNextClick = useRef(false);

  const ACTION_WIDTH = 72;
  const leftMax = leftActions.length * ACTION_WIDTH;
  const rightMax = rightActions.length * ACTION_WIDTH;

  const handlePointerDown = useCallback((e: any) => {
    const clientX = e.nativeEvent?.pageX ?? e.pageX ?? 0;
    const clientY = e.nativeEvent?.pageY ?? e.pageY ?? 0;
    startX.current = clientX;
    startY.current = clientY;
    startTranslate.current = translateX;
    isHorizontal.current = null;
    hasMoved.current = false;
    setIsDragging(true);
  }, [translateX]);

  const handlePointerMove = useCallback((e: any) => {
    if (!isDragging) return;
    const clientX = e.nativeEvent?.pageX ?? e.pageX ?? 0;
    const clientY = e.nativeEvent?.pageY ?? e.pageY ?? 0;
    const dx = clientX - startX.current;
    const dy = clientY - startY.current;

    // Determine direction lock
    if (isHorizontal.current === null && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
      isHorizontal.current = Math.abs(dx) > Math.abs(dy);
    }
    if (!isHorizontal.current) return;
    hasMoved.current = true;

    let next = startTranslate.current + dx;
    // Clamp with rubber-band on edges
    if (next > 0 && leftActions.length > 0) next = Math.min(next, leftMax + 20);
    else if (next > 0) next = next * 0.15;
    if (next < 0 && rightActions.length > 0) next = Math.max(next, -(rightMax + 20));
    else if (next < 0) next = next * 0.15;

    setTranslateX(next);
  }, [isDragging, leftMax, rightMax, leftActions.length, rightActions.length]);

  const handlePointerUp = useCallback((e: any) => {
    if (!isDragging) return;
    
    // Set the block flag BEFORE setting isDragging to false
    // This ensures the flag is set before any click events can fire
    if (hasMoved.current) {
      blockNextClick.current = true;
    }
    
    setIsDragging(false);

    // If user barely moved, treat it as a tap → close if open
    if (!hasMoved.current && translateX !== 0) {
      setTranslateX(0);
      return;
    }

    // If user swiped (moved), prevent the click from propagating to children
    if (hasMoved.current) {
      e?.stopPropagation?.();
      e?.preventDefault?.();
      setSwipeJustEnded(true);
      // Reset the flags after a short delay
      setTimeout(() => { 
        blockNextClick.current = false; 
        setSwipeJustEnded(false);
      }, 300);
    }

    const snapThreshold = ACTION_WIDTH * 0.4;
    const velocity = translateX - startTranslate.current; // direction of this gesture

    // Snap logic: consider both position and swipe direction
    if (translateX > snapThreshold && leftActions.length > 0 && velocity > 0) {
      setTranslateX(leftMax);
    } else if (translateX < -snapThreshold && rightActions.length > 0 && velocity < 0) {
      setTranslateX(-rightMax);
    } else {
      // Snap closed — either didn't reach threshold or swiped back
      setTranslateX(0);
    }
  }, [isDragging, translateX, leftMax, rightMax, leftActions.length, rightActions.length]);

  const handleActionPress = useCallback((action: SwipeAction) => {
    setTranslateX(0);
    setTimeout(() => action.onPress(), 200);
  }, []);

  // Prevent click events on content when swiped or just finished swiping
  const handleContentClick = useCallback((e: any) => {
    // If swiped open, clicking content should close it, not navigate
    if (translateX !== 0) {
      e?.stopPropagation?.();
      e?.preventDefault?.();
      setTranslateX(0);
      return;
    }
    // If we just finished a swipe gesture, prevent the click
    if (blockNextClick.current) {
      e?.stopPropagation?.();
      e?.preventDefault?.();
      blockNextClick.current = false;
    }
  }, [translateX]);

  // When swiped open, action layers must be above content
  const isOpen = translateX !== 0 && !isDragging;

  return (
    <View
      style={styles.container}
      data-testid="web-swipeable-item"
    >
      {/* Left actions (revealed when swiping right) */}
      {leftActions.length > 0 && (
        <View style={[styles.actionsLeft, { width: leftMax }, isOpen && { zIndex: 3 }]}>
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

      {/* Right actions (revealed when swiping left) */}
      {rightActions.length > 0 && (
        <View style={[styles.actionsRight, { width: rightMax }, isOpen && { zIndex: 3 }]}>
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

      {/* Content layer — handles all swiping */}
      <View
        style={[
          styles.content,
          {
            transform: [{ translateX }],
            transition: isDragging ? 'none' : 'transform 0.3s cubic-bezier(.25,.8,.25,1)',
            // When swiped open, lower z-index so action buttons can be clicked
            zIndex: isOpen ? 1 : 2,
          } as any,
        ]}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onClick={handleContentClick}
      >
        {/* Children wrapper - disable pointer events when swiped open or during swipe */}
        <View style={{ pointerEvents: (isOpen || isDragging || swipeJustEnded) ? 'none' : 'auto' } as any}>
          {children}
        </View>
        {/* Transparent overlay to capture clicks when swiped open - prevents navigation */}
        {isOpen && (
          <View
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 10,
              backgroundColor: 'transparent',
            } as any}
            onTouchEnd={(e: any) => {
              e?.stopPropagation?.();
              setTranslateX(0);
            }}
            onClick={(e: any) => {
              e?.stopPropagation?.();
              e?.preventDefault?.();
              setTranslateX(0);
            }}
          />
        )}
      </View>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    position: 'relative',
    overflow: 'hidden',
    borderRadius: 12,
  },
  content: {
    position: 'relative',
    zIndex: 2,
    backgroundColor: colors.background || '#fff',
  },
  actionsLeft: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    flexDirection: 'row',
    zIndex: 1,
  },
  actionsRight: {
    position: 'absolute',
    right: 0,
    top: 0,
    bottom: 0,
    flexDirection: 'row',
    zIndex: 1,
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
