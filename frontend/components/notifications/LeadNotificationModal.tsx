import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  Pressable,
  Linking,
  Platform,
  ActivityIndicator,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import * as Haptics from 'expo-haptics';

import { useThemeStore } from '../../store/themeStore';
const API_URL = Platform.OS === 'web' ? '' : (process.env.EXPO_PUBLIC_BACKEND_URL || '');

interface LeadNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  conversation_id: string;
  contact_id: string;
  contact_name: string;
  contact_phone: string;
  contact_email?: string;
  lead_source_name?: string;
  created_at: string;
}

interface LeadNotificationModalProps {
  visible: boolean;
  notification: LeadNotification | null;
  onDismiss: () => void;
  onActionComplete: () => void;
}

const triggerHaptic = (type: 'light' | 'medium' | 'heavy' = 'light') => {
  if (Platform.OS !== 'web') {
    Haptics.impactAsync(
      type === 'heavy' ? Haptics.ImpactFeedbackStyle.Heavy :
      type === 'medium' ? Haptics.ImpactFeedbackStyle.Medium :
      Haptics.ImpactFeedbackStyle.Light
    );
  }
};

export const LeadNotificationModal: React.FC<LeadNotificationModalProps> = ({
  visible,
  notification,
  onDismiss,
  onActionComplete,
}) => {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const [loading, setLoading] = useState(false);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const scaleAnim = useState(new Animated.Value(0))[0];

  useEffect(() => {
    if (visible) {
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 8,
        tension: 65,
        useNativeDriver: true,
      }).start();
      triggerHaptic('heavy');
    } else {
      scaleAnim.setValue(0);
    }
  }, [visible]);

  const recordAction = async (action: string) => {
    if (!notification || !user) return;
    
    setLoading(true);
    setSelectedAction(action);
    triggerHaptic('medium');
    
    try {
      const response = await fetch(
        `${API_URL}/api/notifications/${notification.id}/action?action=${action}&user_id=${user._id}`,
        { method: 'POST' }
      );
      const data = await response.json();
      
      if (data.success) {
        // Perform the action
        if (action === 'call' && notification.contact_phone) {
          const phoneUrl = `tel:${notification.contact_phone}`;
          await Linking.openURL(phoneUrl);
        } else if (action === 'text' && notification.contact_phone) {
          // Navigate to thread with SMS mode
          router.push({
            pathname: `/thread/${notification.conversation_id}`,
            params: {
              contact_name: notification.contact_name,
              contact_phone: notification.contact_phone,
              mode: 'sms',
            }
          });
        } else if (action === 'email' && notification.contact_email) {
          const emailUrl = `mailto:${notification.contact_email}?subject=Following up on your inquiry`;
          await Linking.openURL(emailUrl);
        }
        
        onActionComplete();
      }
    } catch (error) {
      console.error('Error recording action:', error);
    } finally {
      setLoading(false);
      setSelectedAction(null);
    }
  };

  const handleDismiss = async () => {
    if (!notification || !user) {
      onDismiss();
      return;
    }
    
    triggerHaptic('light');
    
    try {
      await fetch(
        `${API_URL}/api/notifications/${notification.id}/action?action=dismissed&user_id=${user._id}`,
        { method: 'POST' }
      );
    } catch (error) {
      console.error('Error dismissing notification:', error);
    }
    
    onDismiss();
  };

  if (!notification) return null;

  const isJumpBall = notification.type === 'jump_ball';
  const hasEmail = !!notification.contact_email;
  const hasPhone = !!notification.contact_phone;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={handleDismiss}
    >
      <View style={styles.overlay}>
        <Animated.View 
          style={[
            styles.modal,
            { transform: [{ scale: scaleAnim }] }
          ]}
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={[
              styles.iconContainer,
              isJumpBall && styles.iconContainerJumpBall
            ]}>
              <Ionicons 
                name={isJumpBall ? "flash" : "person-add"} 
                size={28} 
                color={'#FFFFFF'} 
              />
            </View>
            <Text style={styles.title}>{notification.title}</Text>
            <Pressable 
              style={styles.closeButton}
              onPress={handleDismiss}
              hitSlop={8}
            >
              <Ionicons name="close" size={24} color="#8E8E93" />
            </Pressable>
          </View>

          {/* Content */}
          <View style={styles.content}>
            <Text style={styles.contactName}>{notification.contact_name}</Text>
            
            {notification.lead_source_name && (
              <View style={styles.sourceTag}>
                <Ionicons name="git-network" size={12} color="#5856D6" />
                <Text style={styles.sourceTagText}>{notification.lead_source_name}</Text>
              </View>
            )}
            
            <Text style={styles.message}>{notification.message}</Text>
            
            {isJumpBall && (
              <View style={styles.jumpBallBadge}>
                <Ionicons name="flash" size={14} color="#FF9500" />
                <Text style={styles.jumpBallText}>First to respond claims this lead!</Text>
              </View>
            )}
          </View>

          {/* Contact Info */}
          <View style={styles.contactInfo}>
            {hasPhone && (
              <View style={styles.contactRow}>
                <Ionicons name="call" size={16} color="#8E8E93" />
                <Text style={styles.contactText}>{notification.contact_phone}</Text>
              </View>
            )}
            {hasEmail && (
              <View style={styles.contactRow}>
                <Ionicons name="mail" size={16} color="#8E8E93" />
                <Text style={styles.contactText}>{notification.contact_email}</Text>
              </View>
            )}
          </View>

          {/* Action Buttons */}
          <View style={styles.actions}>
            {hasPhone && (
              <Pressable
                style={[styles.actionButton, styles.callButton]}
                onPress={() => recordAction('call')}
                disabled={loading}
              >
                {loading && selectedAction === 'call' ? (
                  <ActivityIndicator color={'#FFFFFF'} size="small" />
                ) : (
                  <>
                    <Ionicons name="call" size={22} color={'#FFFFFF'} />
                    <Text style={styles.actionButtonText}>Call</Text>
                  </>
                )}
              </Pressable>
            )}
            
            {hasPhone && (
              <Pressable
                style={[styles.actionButton, styles.textButton]}
                onPress={() => recordAction('text')}
                disabled={loading}
              >
                {loading && selectedAction === 'text' ? (
                  <ActivityIndicator color={'#FFFFFF'} size="small" />
                ) : (
                  <>
                    <Ionicons name="chatbubble" size={22} color={'#FFFFFF'} />
                    <Text style={styles.actionButtonText}>Text</Text>
                  </>
                )}
              </Pressable>
            )}
            
            {hasEmail && (
              <Pressable
                style={[styles.actionButton, styles.emailButton]}
                onPress={() => recordAction('email')}
                disabled={loading}
              >
                {loading && selectedAction === 'email' ? (
                  <ActivityIndicator color={'#FFFFFF'} size="small" />
                ) : (
                  <>
                    <Ionicons name="mail" size={22} color={'#FFFFFF'} />
                    <Text style={styles.actionButtonText}>Email</Text>
                  </>
                )}
              </Pressable>
            )}
          </View>

          {/* Dismiss Button */}
          <Pressable style={styles.dismissButton} onPress={handleDismiss}>
            <Text style={styles.dismissText}>Dismiss</Text>
          </Pressable>
        </Animated.View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modal: {
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
    width: '100%',
    maxWidth: 400,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconContainerJumpBall: {
    backgroundColor: '#FF9500',
  },
  title: {
    flex: 1,
    fontSize: 18,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  closeButton: {
    padding: 4,
  },
  content: {
    padding: 20,
    alignItems: 'center',
  },
  contactName: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 8,
    textAlign: 'center',
  },
  sourceTag: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#5856D620',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
    marginBottom: 12,
  },
  sourceTagText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#5856D6',
  },
  message: {
    fontSize: 15,
    color: '#8E8E93',
    textAlign: 'center',
    lineHeight: 22,
  },
  jumpBallBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF950020',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    marginTop: 16,
    gap: 6,
  },
  jumpBallText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#FF9500',
  },
  contactInfo: {
    paddingHorizontal: 20,
    paddingBottom: 20,
    gap: 8,
  },
  contactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    gap: 10,
  },
  contactText: {
    fontSize: 14,
    color: '#FFFFFF',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  actions: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    gap: 10,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  callButton: {
    backgroundColor: '#34C759',
  },
  textButton: {
    backgroundColor: '#007AFF',
  },
  emailButton: {
    backgroundColor: '#5856D6',
  },
  actionButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  dismissButton: {
    padding: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  dismissText: {
    fontSize: 15,
    color: '#8E8E93',
    fontWeight: '500',
  },
});

export default LeadNotificationModal;
