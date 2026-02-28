import React, { useRef, useState, useCallback, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

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
  const [translateX, setTranslateX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const startX = useRef(0);
  const startY = useRef(0);
  const currentX = useRef(0);
  const isHorizontal = useRef<boolean | null>(null);
  const hasMoved = useRef(false);
  const containerRef = useRef<View>(null);

  const ACTION_WIDTH = 72;
  const leftMax = leftActions.length * ACTION_WIDTH;
  const rightMax = rightActions.length * ACTION_WIDTH;

  const handlePointerDown = useCallback((e: any) => {
    const clientX = e.nativeEvent?.pageX ?? e.pageX ?? 0;
    const clientY = e.nativeEvent?.pageY ?? e.pageY ?? 0;
    startX.current = clientX;
    startY.current = clientY;
    currentX.current = translateX;
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

    if (isHorizontal.current === null && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
      isHorizontal.current = Math.abs(dx) > Math.abs(dy);
    }
    if (!isHorizontal.current) return;
    hasMoved.current = true;

    let next = currentX.current + dx;
    if (next > 0) next = Math.min(next, leftMax);
    if (next < 0) next = Math.max(next, -rightMax);
    if (next > 0 && leftActions.length === 0) next = next * 0.2;
    if (next < 0 && rightActions.length === 0) next = next * 0.2;

    setTranslateX(next);
  }, [isDragging, leftMax, rightMax, leftActions.length, rightActions.length]);

  const handlePointerUp = useCallback(() => {
    if (!isDragging) return;
    setIsDragging(false);

    const threshold = ACTION_WIDTH * 0.4;
    if (translateX > threshold && leftActions.length > 0) {
      setTranslateX(leftMax);
    } else if (translateX < -threshold && rightActions.length > 0) {
      setTranslateX(-rightMax);
    } else {
      setTranslateX(0);
    }
  }, [isDragging, translateX, leftMax, rightMax, leftActions.length, rightActions.length]);

  const close = useCallback(() => {
    setTranslateX(0);
  }, []);

  const handleActionPress = useCallback((action: SwipeAction) => {
    close();
    setTimeout(() => action.onPress(), 150);
  }, [close]);

  const isOpen = translateX !== 0;

  // Web-specific: close on click outside by listening to document clicks
  useEffect(() => {
    if (!isOpen || Platform.OS !== 'web') return;

    const handleDocumentClick = (e: MouseEvent) => {
      if (containerRef.current) {
        const node = containerRef.current as any;
        if (node && typeof node.contains === 'function' && !node.contains(e.target as Node)) {
          close();
        }
      }
    };

    document.addEventListener('click', handleDocumentClick, true);
    return () => document.removeEventListener('click', handleDocumentClick, true);
  }, [isOpen, close]);

  return (
    <View
      ref={containerRef}
      style={styles.container}
      data-testid="web-swipeable-item"
    >
      {/* Left actions (revealed when swiping right) */}
      {leftActions.length > 0 && (
        <View style={[styles.actionsLeft, { width: leftMax }]}>
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
        <View style={[styles.actionsRight, { width: rightMax }]}>
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
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {children}
      </View>

      {/* Tap-to-close overlay when open — uses a real div on web for reliable hit testing */}
      {isOpen && !isDragging && Platform.OS === 'web' && (
        <div
          onClick={(e) => { e.stopPropagation(); close(); }}
          data-testid="swipe-close-overlay"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 10,
            cursor: 'pointer',
            backgroundColor: 'transparent',
          }}
        />
      )}
      {isOpen && !isDragging && Platform.OS !== 'web' && (
        <TouchableOpacity
          style={styles.closeOverlay}
          onPress={close}
          activeOpacity={1}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'relative',
    overflow: 'hidden',
    borderRadius: 12,
  },
  content: {
    position: 'relative',
    zIndex: 2,
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
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  closeOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 10,
    backgroundColor: 'transparent',
  },
});
