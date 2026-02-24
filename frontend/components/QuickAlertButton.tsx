import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  TextInput,
  ActivityIndicator,
  Animated,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const COLORS = {
  background: '#000',
  card: '#1C1C1E',
  accent: '#007AFF',
  alert: '#FF3B30',
  warning: '#FF9500',
  success: '#34C759',
  textPrimary: '#FFF',
  textSecondary: '#8E8E93',
};

// Preset quick alert messages
const PRESET_ALERTS = [
  { id: '1', icon: 'person', text: 'Customer waiting at front', color: '#FF9500' },
  { id: '2', icon: 'hand-left', text: 'Need backup on sales floor', color: '#FF3B30' },
  { id: '3', icon: 'megaphone', text: 'Manager to register please', color: '#5856D6' },
  { id: '4', icon: 'people', text: 'Team huddle in 5 minutes', color: '#007AFF' },
  { id: '5', icon: 'call', text: 'Phone call holding - who can take?', color: '#34C759' },
  { id: '6', icon: 'car', text: 'Customer arrived for pickup', color: '#FF9500' },
];

interface QuickAlertButtonProps {
  visible?: boolean;
}

export default function QuickAlertButton({ visible = true }: QuickAlertButtonProps) {
  const { user } = useAuthStore();
  const [showModal, setShowModal] = useState(false);
  const [customMessage, setCustomMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sentAlert, setSentAlert] = useState<string | null>(null);
  const [pulseAnim] = useState(new Animated.Value(1));

  // Pulse animation for the button
  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.1,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, []);

  const sendAlert = async (message: string) => {
    if (!user?._id || sending) return;

    setSending(true);
    try {
      // First, get user's channels to find the right one to broadcast to
      const channelsRes = await api.get(`/team-chat/channels?user_id=${user._id}`);
      
      let targetChannel = null;
      if (channelsRes.data.success && channelsRes.data.channels.length > 0) {
        // Prefer store channel, then org channel, then any channel
        targetChannel = channelsRes.data.channels.find((c: any) => c.channel_type === 'store') ||
                       channelsRes.data.channels.find((c: any) => c.channel_type === 'org') ||
                       channelsRes.data.channels[0];
      }

      if (!targetChannel) {
        // Create a quick channel if none exists
        const createRes = await api.post('/team-chat/channels', {
          name: 'Quick Alerts',
          channel_type: user.organization_id ? 'org' : 'custom',
          organization_id: user.organization_id,
          store_id: user.store_id,
          member_ids: user.organization_id ? undefined : [user._id],
          created_by: user._id,
        });
        
        if (createRes.data.success) {
          targetChannel = { id: createRes.data.channel_id };
        }
      }

      if (targetChannel) {
        // Send the alert as a broadcast message
        await api.post('/team-chat/messages', {
          channel_id: targetChannel.id,
          sender_id: user._id,
          content: `🚨 QUICK ALERT: ${message}`,
          mentions: [],
          is_broadcast: true,
        });

        setSentAlert(message);
        setTimeout(() => {
          setSentAlert(null);
          setShowModal(false);
          setCustomMessage('');
        }, 1500);
      }
    } catch (error) {
      console.error('Error sending quick alert:', error);
    } finally {
      setSending(false);
    }
  };

  if (!visible || !user) return null;

  return (
    <>
      {/* Floating Quick Alert Button */}
      <Animated.View 
        style={[
          styles.floatingButton,
          { transform: [{ scale: pulseAnim }] }
        ]}
      >
        <TouchableOpacity
          style={styles.alertButton}
          onPress={() => setShowModal(true)}
          activeOpacity={0.8}
          data-testid="quick-alert-btn"
        >
          <Ionicons name="flash" size={28} color="#FFF" />
        </TouchableOpacity>
      </Animated.View>

      {/* Quick Alert Modal */}
      <Modal
        visible={showModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowModal(false)}
      >
        <TouchableOpacity 
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowModal(false)}
        >
          <View style={styles.modalContent} onStartShouldSetResponder={() => true}>
            {/* Header */}
            <View style={styles.modalHeader}>
              <Ionicons name="flash" size={24} color={COLORS.alert} />
              <Text style={styles.modalTitle}>Quick Alert</Text>
              <TouchableOpacity onPress={() => setShowModal(false)}>
                <Ionicons name="close" size={24} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>

            {/* Success State */}
            {sentAlert ? (
              <View style={styles.successContainer}>
                <View style={styles.successIcon}>
                  <Ionicons name="checkmark-circle" size={64} color={COLORS.success} />
                </View>
                <Text style={styles.successText}>Alert Sent!</Text>
                <Text style={styles.successSubtext}>{sentAlert}</Text>
              </View>
            ) : (
              <>
                {/* Preset Alerts */}
                <View style={styles.presetContainer}>
                  {PRESET_ALERTS.map((alert) => (
                    <TouchableOpacity
                      key={alert.id}
                      style={styles.presetButton}
                      onPress={() => sendAlert(alert.text)}
                      disabled={sending}
                    >
                      <View style={[styles.presetIcon, { backgroundColor: alert.color }]}>
                        <Ionicons name={alert.icon as any} size={20} color="#FFF" />
                      </View>
                      <Text style={styles.presetText} numberOfLines={1}>{alert.text}</Text>
                      <Ionicons name="send" size={16} color={COLORS.textSecondary} />
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Custom Message */}
                <View style={styles.customContainer}>
                  <Text style={styles.customLabel}>Or send custom alert:</Text>
                  <View style={styles.customInputRow}>
                    <TextInput
                      style={styles.customInput}
                      value={customMessage}
                      onChangeText={setCustomMessage}
                      placeholder="Type your alert..."
                      placeholderTextColor={COLORS.textSecondary}
                      maxLength={100}
                    />
                    <TouchableOpacity
                      style={[
                        styles.customSendButton,
                        (!customMessage.trim() || sending) && styles.customSendDisabled
                      ]}
                      onPress={() => sendAlert(customMessage.trim())}
                      disabled={!customMessage.trim() || sending}
                    >
                      {sending ? (
                        <ActivityIndicator size="small" color="#FFF" />
                      ) : (
                        <Ionicons name="send" size={18} color="#FFF" />
                      )}
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Info */}
                <Text style={styles.infoText}>
                  Alerts are sent to your entire team with push notifications
                </Text>
              </>
            )}
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  floatingButton: {
    position: 'absolute',
    bottom: 100,
    right: 20,
    zIndex: 1000,
    ...Platform.select({
      web: {
        position: 'fixed' as any,
      },
    }),
  },
  alertButton: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: COLORS.alert,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: COLORS.alert,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
  
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: COLORS.card,
    borderRadius: 20,
    width: '100%',
    maxWidth: 400,
    maxHeight: '80%',
    overflow: 'hidden',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.textPrimary,
    flex: 1,
    marginLeft: 8,
  },

  // Presets
  presetContainer: {
    padding: 12,
  },
  presetButton: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    marginBottom: 8,
  },
  presetIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  presetText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '500',
    color: COLORS.textPrimary,
  },

  // Custom
  customContainer: {
    padding: 16,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  customLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 8,
  },
  customInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  customInput: {
    flex: 1,
    backgroundColor: '#2C2C2E',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: COLORS.textPrimary,
    fontSize: 14,
  },
  customSendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: COLORS.alert,
    justifyContent: 'center',
    alignItems: 'center',
  },
  customSendDisabled: {
    opacity: 0.5,
  },

  // Info
  infoText: {
    fontSize: 11,
    color: COLORS.textSecondary,
    textAlign: 'center',
    padding: 12,
    paddingTop: 0,
  },

  // Success
  successContainer: {
    padding: 32,
    alignItems: 'center',
  },
  successIcon: {
    marginBottom: 16,
  },
  successText: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.success,
    marginBottom: 8,
  },
  successSubtext: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
  },
});
