import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated, Platform, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastProps {
  message: string;
  type?: ToastType;
  duration?: number;
  visible: boolean;
  onHide: () => void;
}

const getToastColors = (type: ToastType) => {
  switch (type) {
    case 'success':
      return { bg: '#34C759', icon: 'checkmark-circle' as const };
    case 'error':
      return { bg: '#FF3B30', icon: 'close-circle' as const };
    case 'warning':
      return { bg: '#FF9500', icon: 'warning' as const };
    case 'info':
    default:
      return { bg: '#007AFF', icon: 'information-circle' as const };
  }
};

export const Toast: React.FC<ToastProps> = ({
  message,
  type = 'success',
  duration = 3000,
  visible,
  onHide,
}) => {
  const [fadeAnim] = useState(new Animated.Value(0));
  const colors = getToastColors(type);

  useEffect(() => {
    if (visible) {
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }).start();

      const timer = setTimeout(() => {
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }).start(() => onHide());
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [visible, duration, fadeAnim, onHide]);

  if (!visible) return null;

  return (
    <Animated.View
      style={[
        styles.container,
        { opacity: fadeAnim, backgroundColor: '#000000' },
      ]}
    >
      <Pressable style={styles.content} onPress={onHide}>
        <Ionicons name={colors.icon} size={24} color={'#FFFFFF'} />
        <Text style={styles.message}>{message}</Text>
        <Ionicons name="close" size={20} color="rgba(255,255,255,0.7)" />
      </Pressable>
    </Animated.View>
  );
};

// Toast context for global usage
interface ToastContextType {
  showToast: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = React.createContext<ToastContextType | null>(null);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toast, setToast] = useState<{
    message: string;
    type: ToastType;
    duration: number;
    visible: boolean;
  }>({
    message: '',
    type: 'success',
    duration: 3000,
    visible: false,
  });

  const showToast = (message: string, type: ToastType = 'success', duration: number = 3000) => {
    setToast({ message, type, duration, visible: true });
  };

  const hideToast = () => {
    setToast((prev) => ({ ...prev, visible: false }));
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <Toast
        message={toast.message}
        type={toast.type}
        duration={toast.duration}
        visible={toast.visible}
        onHide={hideToast}
      />
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: Platform.OS === 'web' ? 20 : 60,
    left: 20,
    right: 20,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
    zIndex: 9999,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    gap: 12,
  },
  message: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '500',
  },
});

export default Toast;
