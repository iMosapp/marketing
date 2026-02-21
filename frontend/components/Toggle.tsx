import React from 'react';
import { TouchableOpacity, View, StyleSheet, ViewStyle } from 'react-native';

interface ToggleProps {
  value: boolean;
  onValueChange: (value: boolean) => void;
  disabled?: boolean;
  size?: 'small' | 'medium' | 'large';
  activeColor?: string;
  inactiveColor?: string;
  style?: ViewStyle;
  testID?: string;
}

/**
 * Standardized Toggle component for consistent UI across the app.
 * Works reliably on both web and native platforms.
 */
export default function Toggle({
  value,
  onValueChange,
  disabled = false,
  size = 'medium',
  activeColor = '#007AFF',
  inactiveColor = '#3A3A3C',
  style,
  testID,
}: ToggleProps) {
  const dimensions = {
    small: { width: 40, height: 24, knobSize: 20 },
    medium: { width: 50, height: 30, knobSize: 26 },
    large: { width: 60, height: 36, knobSize: 32 },
  }[size];

  const handlePress = () => {
    if (!disabled) {
      onValueChange(!value);
    }
  };

  return (
    <TouchableOpacity
      testID={testID}
      onPress={handlePress}
      activeOpacity={0.7}
      disabled={disabled}
      style={[
        styles.track,
        {
          width: dimensions.width,
          height: dimensions.height,
          borderRadius: dimensions.height / 2,
          backgroundColor: value ? activeColor : inactiveColor,
          opacity: disabled ? 0.5 : 1,
        },
        style,
      ]}
      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
    >
      <View
        style={[
          styles.knob,
          {
            width: dimensions.knobSize,
            height: dimensions.knobSize,
            borderRadius: dimensions.knobSize / 2,
            transform: [{ translateX: value ? dimensions.width - dimensions.knobSize - 2 : 2 }],
          },
        ]}
      />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  track: {
    justifyContent: 'center',
    padding: 2,
  },
  knob: {
    backgroundColor: '#FFFFFF',
    elevation: 2,
  },
});
