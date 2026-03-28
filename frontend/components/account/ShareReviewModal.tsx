/**
 * ShareReviewModal.tsx — Modal for sharing the review link via SMS, email, or copy.
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { WebModal } from '../WebModal';

interface Props {
  visible: boolean;
  onClose: () => void;
  colors: Record<string, string>;
  reviewUrl: string;
  copiedLink: boolean;
  onCopyLink: () => void;
  onShareSMS: () => void;
  onShareEmail: () => void;
  onPreview: () => void;
}

export function ShareReviewModal({
  visible, onClose, colors, reviewUrl,
  copiedLink, onCopyLink, onShareSMS, onShareEmail, onPreview,
}: Props) {
  return (
    <WebModal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={s.modal}>
        <View style={s.header}>
          <TouchableOpacity onPress={onClose}>
            <Ionicons name="close" size={24} color={colors.textSecondary} />
          </TouchableOpacity>
          <Text style={[s.headerTitle, { color: colors.text }]}>Share Review Link</Text>
          <View style={{ width: 24 }} />
        </View>

        <View style={[s.linkBox, { backgroundColor: colors.card }]}>
          <Ionicons name="link" size={18} color="#FFD60A" />
          <Text style={[s.linkText, { color: colors.text }]} numberOfLines={2}>
            {reviewUrl || 'Loading store link...'}
          </Text>
        </View>

        <View style={s.actions}>
          <TouchableOpacity style={s.actionBtn} onPress={onCopyLink} data-testid="share-copy-btn">
            <View style={[s.actionIcon, { backgroundColor: '#FF950020' }]}>
              <Ionicons name={copiedLink ? 'checkmark' : 'copy-outline'} size={24} color={copiedLink ? '#34C759' : '#FF9500'} />
            </View>
            <Text style={[s.actionLabel, { color: colors.textSecondary }]}>{copiedLink ? 'Copied!' : 'Copy Link'}</Text>
          </TouchableOpacity>

          <TouchableOpacity style={s.actionBtn} onPress={onShareSMS} data-testid="share-sms-btn">
            <View style={[s.actionIcon, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
            </View>
            <Text style={[s.actionLabel, { color: colors.textSecondary }]}>Text</Text>
          </TouchableOpacity>

          <TouchableOpacity style={s.actionBtn} onPress={onShareEmail} data-testid="share-email-btn">
            <View style={[s.actionIcon, { backgroundColor: '#007AFF20' }]}>
              <Ionicons name="mail-outline" size={24} color="#007AFF" />
            </View>
            <Text style={[s.actionLabel, { color: colors.textSecondary }]}>Email</Text>
          </TouchableOpacity>

          <TouchableOpacity style={s.actionBtn} onPress={onPreview} data-testid="share-preview-btn">
            <View style={[s.actionIcon, { backgroundColor: '#5856D620' }]}>
              <Ionicons name="eye-outline" size={24} color="#5856D6" />
            </View>
            <Text style={[s.actionLabel, { color: colors.textSecondary }]}>Preview</Text>
          </TouchableOpacity>
        </View>

        <Text style={[s.hint, { color: colors.textTertiary }]}>
          Tap Text or Email to send with a pre-written message asking for a review.
        </Text>
      </View>
    </WebModal>
  );
}

const s = StyleSheet.create({
  modal: { flex: 1, padding: 20 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  linkBox: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 12, marginBottom: 24 },
  linkText: { flex: 1, fontSize: 14 },
  actions: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 24 },
  actionBtn: { alignItems: 'center', gap: 8 },
  actionIcon: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  actionLabel: { fontSize: 13, fontWeight: '500' },
  hint: { fontSize: 13, textAlign: 'center', lineHeight: 18 },
});
