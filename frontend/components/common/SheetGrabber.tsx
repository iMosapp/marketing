import React, { useRef } from 'react';
import { Animated, PanResponder, View, ViewStyle, StyleProp } from 'react-native';

type Props = { onClose: () => void; color: string; width?: number; height?: number; style?: StyleProp<ViewStyle>; testID?: string };

// The little bar at the top of every bottom sheet. Drag it (or the strip around it) down to close the sheet.
export const SheetGrabber = ({ onClose, color, width = 40, height = 4, style, testID = 'sheet-grabber' }: Props) => {
  const y = useRef(new Animated.Value(0)).current;
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const pan = useRef(PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: (_, g) => g.dy > 3 && Math.abs(g.dy) > Math.abs(g.dx),
    onPanResponderMove: (_, g) => y.setValue(Math.max(0, g.dy) * 0.35),
    onPanResponderRelease: (_, g) => {
      Animated.spring(y, { toValue: 0, useNativeDriver: true, speed: 30, bounciness: 4 }).start();
      if (g.dy > 45 || g.vy > 0.5) closeRef.current();
    },
    onPanResponderTerminate: () => Animated.spring(y, { toValue: 0, useNativeDriver: true }).start(),
  })).current;
  return (
    <View {...pan.panHandlers} hitSlop={{ top: 14, bottom: 14, left: 80, right: 80 }} style={[{ alignSelf: 'stretch', alignItems: 'center', paddingVertical: 6 }, style]} testID={testID} dataSet={{ testid: testID } as any}>
      <Animated.View style={{ width, height, borderRadius: height / 2, backgroundColor: color, transform: [{ translateY: y }] }} />
    </View>
  );
};
