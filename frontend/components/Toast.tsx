import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

let showToastFn: ((message: string, type?: 'success' | 'error' | 'info') => void) | null = null;

export const showToast = (message: string, type: 'success' | 'error' | 'info' = 'success') => {
  if (showToastFn) showToastFn(message, type);
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toast, setToast] = useState<{ message: string; type: string } | null>(null);
  const opacity = useState(new Animated.Value(0))[0];

  useEffect(() => {
    showToastFn = (message, type = 'success') => {
      setToast({ message, type });
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.delay(1500),
        Animated.timing(opacity, { toValue: 0, duration: 300, useNativeDriver: true }),
      ]).start(() => setToast(null));
    };
    return () => { showToastFn = null; };
  }, []);

  return (
    <View style={{ flex: 1 }}>
      {children}
      {toast && (
        <Animated.View style={[styles.toast, { opacity }]}>
          <View style={[styles.iconCircle, { backgroundColor: toast.type === 'error' ? '#FF3B30' : toast.type === 'info' ? '#007AFF' : '#34C759' }]}>
            <Ionicons
              name={toast.type === 'error' ? 'close' : toast.type === 'info' ? 'information' : 'checkmark'}
              size={20}
              color="#FFF"
            />
          </View>
          <Text style={styles.toastText}>{toast.message}</Text>
        </Animated.View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  toast: {
    ...(Platform.OS === 'web' ? { position: 'fixed' as any } : { position: 'absolute' }),
    top: 60,
    alignSelf: 'center',
    left: '10%' as any,
    right: '10%' as any,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    paddingHorizontal: 16,
    zIndex: 999999,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 10,
  },
  iconCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  toastText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '500',
    flex: 1,
  },
});
