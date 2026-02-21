import React, { useCallback, useRef } from 'react';
import {
  TouchableOpacity,
  Pressable,
  Text,
  StyleSheet,
  Platform,
  View,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
} from 'react-native';

interface WebSafeButtonProps {
  onPress: () => void;
  title?: string;
  children?: React.ReactNode;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
  size?: 'small' | 'medium' | 'large';
  style?: ViewStyle;
  textStyle?: TextStyle;
  testID?: string;
  fullWidth?: boolean;
}

/**
 * WebSafeButton - A cross-platform button that works reliably on:
 * - iOS Safari (static Expo web build)
 * - Android Chrome
 * - Desktop browsers
 * - Native iOS/Android apps
 * 
 * Key fixes for mobile Safari:
 * - Uses native <button> element on web
 * - Multiple event handlers (onClick, onTouchEnd, onPointerUp)
 * - Prevents event bubbling and default behavior
 * - CSS touch-action and tap-highlight fixes
 * - Immediate visual feedback
 */
export const WebSafeButton: React.FC<WebSafeButtonProps> = ({
  onPress,
  title,
  children,
  disabled = false,
  loading = false,
  variant = 'primary',
  size = 'medium',
  style,
  textStyle,
  testID,
  fullWidth = false,
}) => {
  const pressedRef = useRef(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Debounced press handler to prevent double-fires
  const handlePress = useCallback(() => {
    if (disabled || loading || pressedRef.current) return;
    
    pressedRef.current = true;
    
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Execute the press handler
    try {
      onPress();
    } catch (e) {
      console.error('Button press error:', e);
    }
    
    // Reset after a short delay to prevent rapid re-presses
    timeoutRef.current = setTimeout(() => {
      pressedRef.current = false;
    }, 300);
  }, [onPress, disabled, loading]);

  // Get variant colors
  const getVariantStyles = () => {
    switch (variant) {
      case 'primary':
        return {
          bg: '#34C759',
          text: '#FFFFFF',
          border: 'transparent',
        };
      case 'secondary':
        return {
          bg: '#1C1C1E',
          text: '#FFFFFF',
          border: '#3A3A3C',
        };
      case 'danger':
        return {
          bg: '#FF3B30',
          text: '#FFFFFF',
          border: 'transparent',
        };
      case 'outline':
        return {
          bg: 'transparent',
          text: '#34C759',
          border: '#34C759',
        };
      case 'ghost':
        return {
          bg: 'transparent',
          text: '#34C759',
          border: 'transparent',
        };
      default:
        return {
          bg: '#34C759',
          text: '#FFFFFF',
          border: 'transparent',
        };
    }
  };

  // Get size styles
  const getSizeStyles = () => {
    switch (size) {
      case 'small':
        return { padding: 10, fontSize: 14 };
      case 'large':
        return { padding: 18, fontSize: 18 };
      default:
        return { padding: 16, fontSize: 16 };
    }
  };

  const variantStyles = getVariantStyles();
  const sizeStyles = getSizeStyles();
  const isDisabled = disabled || loading;

  // Web-specific implementation using native button
  if (Platform.OS === 'web') {
    return (
      <button
        type="button"
        data-testid={testID}
        disabled={isDisabled}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          handlePress();
        }}
        onTouchEnd={(e) => {
          e.preventDefault();
          e.stopPropagation();
          handlePress();
        }}
        onPointerUp={(e) => {
          e.preventDefault();
          e.stopPropagation();
          handlePress();
        }}
        onMouseDown={(e) => {
          // Prevent focus issues on some browsers
          e.preventDefault();
        }}
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          backgroundColor: variantStyles.bg,
          color: variantStyles.text,
          border: variantStyles.border !== 'transparent' ? `2px solid ${variantStyles.border}` : 'none',
          borderRadius: 12,
          padding: sizeStyles.padding,
          fontSize: sizeStyles.fontSize,
          fontWeight: 600,
          cursor: isDisabled ? 'not-allowed' : 'pointer',
          opacity: isDisabled ? 0.5 : 1,
          width: fullWidth ? '100%' : 'auto',
          minHeight: 48, // Minimum touch target size
          // iOS Safari fixes
          WebkitAppearance: 'none',
          WebkitTapHighlightColor: 'transparent',
          touchAction: 'manipulation',
          userSelect: 'none',
          // Prevent text selection on long press
          WebkitUserSelect: 'none',
          MozUserSelect: 'none',
          msUserSelect: 'none',
          // Smooth transitions
          transition: 'opacity 0.15s ease, transform 0.1s ease',
          ...(style as any),
        }}
        onTouchStart={(e) => {
          // Visual feedback on touch start
          (e.currentTarget as HTMLButtonElement).style.opacity = '0.8';
          (e.currentTarget as HTMLButtonElement).style.transform = 'scale(0.98)';
        }}
        onTouchCancel={(e) => {
          // Reset on touch cancel
          (e.currentTarget as HTMLButtonElement).style.opacity = isDisabled ? '0.5' : '1';
          (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1)';
        }}
        onMouseUp={(e) => {
          // Reset after mouse up
          (e.currentTarget as HTMLButtonElement).style.opacity = isDisabled ? '0.5' : '1';
          (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1)';
        }}
      >
        {loading ? (
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="spinner" style={{
              width: 16,
              height: 16,
              border: '2px solid transparent',
              borderTopColor: variantStyles.text,
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
            Loading...
          </span>
        ) : (
          children || <span>{title}</span>
        )}
      </button>
    );
  }

  // Native implementation using Pressable
  return (
    <Pressable
      onPress={handlePress}
      disabled={isDisabled}
      testID={testID}
      style={({ pressed }) => [
        {
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          backgroundColor: variantStyles.bg,
          borderRadius: 12,
          padding: sizeStyles.padding,
          borderWidth: variantStyles.border !== 'transparent' ? 2 : 0,
          borderColor: variantStyles.border,
          opacity: isDisabled ? 0.5 : pressed ? 0.8 : 1,
          transform: pressed ? [{ scale: 0.98 }] : [{ scale: 1 }],
          width: fullWidth ? '100%' : undefined,
          minHeight: 48,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={variantStyles.text} />
      ) : (
        children || (
          <Text
            style={[
              {
                color: variantStyles.text,
                fontSize: sizeStyles.fontSize,
                fontWeight: '600',
              },
              textStyle,
            ]}
          >
            {title}
          </Text>
        )
      )}
    </Pressable>
  );
};

export default WebSafeButton;
