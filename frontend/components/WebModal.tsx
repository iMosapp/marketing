import React from 'react';
import { View, StyleSheet, Platform, Pressable } from 'react-native';

interface WebModalProps {
  visible: boolean;
  onRequestClose?: () => void;
  transparent?: boolean;
  animationType?: string;
  presentationStyle?: string;
  children: React.ReactNode;
}

export const WebModal: React.FC<WebModalProps> = ({ visible, onRequestClose, transparent, children }) => {
  if (!visible) return null;

  return (
    <View style={styles.overlay}>
      <Pressable style={styles.backdrop} onPress={onRequestClose} />
      <View style={[styles.content, transparent && styles.transparentContent]}>
        {children}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  overlay: {
    ...(Platform.OS === 'web' ? { position: 'fixed' as any } : { position: 'absolute' }),
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 99999,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  backdrop: {
    ...(Platform.OS === 'web' ? { position: 'fixed' as any } : { position: 'absolute' }),
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  content: {
    zIndex: 100000,
    width: '90%',
    maxWidth: 500,
    maxHeight: '90%',
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    overflow: 'hidden',
  },
  transparentContent: {
    backgroundColor: 'transparent',
  },
});

export default WebModal;
