import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useThemeStore } from '../store/themeStore';
type MatchData = {
  contact_id: string;
  existing_name: string;
  provided_name: string;
  phone?: string;
  email?: string;
};

type Props = {
  visible: boolean;
  matchData: MatchData | null;
  onUseExisting: () => void;
  onUpdateName: () => void;
  onCreateNew: () => void;
  onCancel: () => void;
};

export const ContactMatchModal: React.FC<Props> = ({
  visible,
  matchData,
  onUseExisting,
  onUpdateName,
  onCreateNew,
  onCancel,
}) => {
  const { colors } = useThemeStore();
  if (!visible || !matchData) return null;

  const WebModal = Platform.OS === 'web'
    ? ({ children, ...props }: any) => props.visible ? <View style={styles.overlay}>{children}</View> : null
    : require('react-native').Modal;

  return (
    <WebModal visible={visible} transparent animationType="fade">
      <View style={styles.overlay}>
        <View style={[styles.modal, { backgroundColor: '#1C1C1E' }]} data-testid="contact-match-modal">
          <View style={styles.iconRow}>
            <View style={styles.iconCircle}>
              <Ionicons name="person-circle" size={44} color="#FF9500" />
            </View>
          </View>

          <Text style={[styles.title, { color: '#FFFFFF' }]}>Contact Already Exists</Text>
          <Text style={[styles.subtitle, { color: '#8E8E93' }]}>
            A contact with this {matchData.phone ? 'phone number' : 'email'} already exists:
          </Text>

          <View style={[styles.matchCard, { backgroundColor: '#2C2C2E' }]}>
            <Text style={styles.matchLabel}>EXISTING CONTACT</Text>
            <Text style={[styles.matchName, { color: '#FFFFFF' }]}>{matchData.existing_name}</Text>
            {matchData.phone ? (
              <Text style={[styles.matchDetail, { color: '#8E8E93' }]}>{matchData.phone}</Text>
            ) : null}
            {matchData.email ? (
              <Text style={[styles.matchDetail, { color: '#8E8E93' }]}>{matchData.email}</Text>
            ) : null}
          </View>

          <View style={styles.vsRow}>
            <View style={[styles.vsDivider, { backgroundColor: '#2C2C2E' }]} />
            <Text style={styles.vsText}>You entered</Text>
            <View style={[styles.vsDivider, { backgroundColor: '#2C2C2E' }]} />
          </View>

          <View style={[styles.providedCard, { backgroundColor: '#2C2C2E' }]}>
            <Text style={styles.providedName}>{matchData.provided_name}</Text>
          </View>

          <View style={styles.actions}>
            <TouchableOpacity
              style={[styles.actionBtn, { backgroundColor: '#2C2C2E' }]}
              onPress={onUseExisting}
              data-testid="match-use-existing"
            >
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
              <Text style={[styles.actionText, { color: '#FFFFFF' }]}>Use Existing Contact</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionBtn, { backgroundColor: '#2C2C2E' }]}
              onPress={onUpdateName}
              data-testid="match-update-name"
            >
              <Ionicons name="create" size={20} color="#007AFF" />
              <Text style={[styles.actionText, { color: '#FFFFFF' }]}>
                Update to "{matchData.provided_name}"
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionBtn, styles.actionBtnLast, { backgroundColor: '#2C2C2E' }]}
              onPress={onCreateNew}
              data-testid="match-create-new"
            >
              <Ionicons name="person-add" size={20} color="#FF9500" />
              <Text style={[styles.actionText, { color: '#FFFFFF' }]}>Create New Contact</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity onPress={onCancel} style={styles.cancelBtn} data-testid="match-cancel">
            <Text style={[styles.cancelText, { color: '#8E8E93' }]}>Cancel</Text>
          </TouchableOpacity>
        </View>
      </View>
    </WebModal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute' as any,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 9999,
  },
  modal: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 24,
    width: '90%',
    maxWidth: 380,
  },
  iconRow: { alignItems: 'center', marginBottom: 16 },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FF950015',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFFFFF',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#8E8E93',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 20,
  },
  matchCard: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  matchLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#6E6E73',
    letterSpacing: 1,
    marginBottom: 6,
  },
  matchName: { fontSize: 17, fontWeight: '600', color: '#FFFFFF' },
  matchDetail: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  vsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 12,
  },
  vsDivider: { flex: 1, height: 1, backgroundColor: '#2C2C2E' },
  vsText: { fontSize: 12, color: '#6E6E73', marginHorizontal: 12 },
  providedCard: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
    marginBottom: 20,
  },
  providedName: { fontSize: 17, fontWeight: '600', color: '#FF9500' },
  actions: { gap: 8 },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    padding: 14,
    borderRadius: 10,
    gap: 10,
  },
  actionBtnLast: {},
  actionText: { fontSize: 15, color: '#FFFFFF', fontWeight: '500', flex: 1 },
  cancelBtn: {
    marginTop: 12,
    padding: 12,
    alignItems: 'center',
  },
  cancelText: { fontSize: 15, color: '#8E8E93', fontWeight: '500' },
});
