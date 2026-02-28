import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Platform,
  Image,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

const IS_WEB = Platform.OS === 'web';

export default function PendingSendPage() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { user } = useAuthStore();
  const [pendingSend, setPendingSend] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [allPending, setAllPending] = useState<any[]>([]);

  useEffect(() => {
    if (!user?._id) return;
    fetchPendingSends();
  }, [user?._id, id]);

  const fetchPendingSends = async () => {
    try {
      const res = await api.get(`/campaigns/${user._id}/pending-sends`);
      const items = res.data || [];
      setAllPending(items);

      if (id && id !== 'index') {
        const found = items.find((p: any) => p._id === id);
        if (found) {
          setPendingSend(found);
          setMessage(found.message || '');
        }
      } else if (items.length > 0) {
        setPendingSend(items[0]);
        setMessage(items[0].message || '');
      }
    } catch (e) {
      console.error('Failed to fetch pending sends:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSendViaNative = () => {
    if (!pendingSend) return;
    const phone = pendingSend.contact_phone;
    const channel = pendingSend.channel || 'sms';

    if (channel === 'email') {
      const email = pendingSend.contact_email || '';
      const subject = encodeURIComponent(`From ${user?.name || 'Your Rep'}`);
      const body = encodeURIComponent(message);
      if (IS_WEB) {
        window.open(`mailto:${email}?subject=${subject}&body=${body}`, '_blank');
      }
    } else {
      const encoded = encodeURIComponent(message);
      const ua = (typeof navigator !== 'undefined' && navigator.userAgent) || '';
      const isIOS = /iPhone|iPad|iPod/i.test(ua);
      const smsLink = isIOS ? `sms:${phone}&body=${encoded}` : `sms:${phone}?body=${encoded}`;
      if (IS_WEB) {
        window.location.href = smsLink;
      }
    }

    // Mark as sent
    markAsSent();
  };

  const markAsSent = async () => {
    if (!pendingSend || !user?._id) return;
    setSending(true);
    try {
      await api.post(`/campaigns/${user._id}/pending-sends/${pendingSend._id}/complete`);
      Alert.alert('Sent!', 'Message marked as sent and logged to activity.', [
        {
          text: 'OK',
          onPress: () => {
            const remaining = allPending.filter(p => p._id !== pendingSend._id);
            if (remaining.length > 0) {
              setPendingSend(remaining[0]);
              setMessage(remaining[0].message || '');
              setAllPending(remaining);
            } else {
              router.back();
            }
          },
        },
      ]);
    } catch (e) {
      Alert.alert('Error', 'Failed to mark as sent');
    } finally {
      setSending(false);
    }
  };

  const handleSkip = async () => {
    if (!pendingSend || !user?._id) return;
    try {
      await api.post(`/campaigns/${user._id}/pending-sends/${pendingSend._id}/skip`);
      const remaining = allPending.filter(p => p._id !== pendingSend._id);
      if (remaining.length > 0) {
        setPendingSend(remaining[0]);
        setMessage(remaining[0].message || '');
        setAllPending(remaining);
      } else {
        router.back();
      }
    } catch (e) {
      Alert.alert('Error', 'Failed to skip');
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  if (!pendingSend) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Campaign Messages</Text>
          <View style={{ width: 36 }} />
        </View>
        <View style={styles.emptyWrap}>
          <Ionicons name="checkmark-circle" size={48} color="#34C759" />
          <Text style={styles.emptyTitle}>All caught up!</Text>
          <Text style={styles.emptySubtitle}>No pending campaign messages to send.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const channel = pendingSend.channel || 'sms';

  return (
    <SafeAreaView style={styles.container} data-testid="pending-send-page">
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="pending-send-back">
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={styles.headerTitle}>Campaign Message</Text>
          <Text style={styles.headerSub}>{allPending.length} pending</Text>
        </View>
        <TouchableOpacity onPress={handleSkip} data-testid="pending-send-skip">
          <Text style={{ color: '#FF9500', fontSize: 14, fontWeight: '600' }}>Skip</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content}>
        {/* Campaign Info */}
        <View style={styles.infoCard}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <View style={[styles.channelBadge, { backgroundColor: channel === 'email' ? '#AF52DE20' : '#007AFF20' }]}>
              <Ionicons name={channel === 'email' ? 'mail' : 'chatbubble'} size={16} color={channel === 'email' ? '#AF52DE' : '#007AFF'} />
            </View>
            <View>
              <Text style={styles.campaignName}>{pendingSend.campaign_name}</Text>
              <Text style={styles.stepInfo}>Step {pendingSend.step} - {channel.toUpperCase()}</Text>
            </View>
          </View>
        </View>

        {/* Recipient */}
        <View style={styles.recipientCard}>
          <Text style={styles.recipientLabel}>To:</Text>
          <Text style={styles.recipientName}>{pendingSend.contact_name || 'Unknown'}</Text>
          <Text style={styles.recipientDetail}>
            {channel === 'email' ? pendingSend.contact_email : pendingSend.contact_phone}
          </Text>
        </View>

        {/* Editable Message */}
        <View style={styles.messageSection}>
          <Text style={styles.messageLabel}>Message</Text>
          <TextInput
            style={styles.messageInput}
            value={message}
            onChangeText={setMessage}
            multiline
            numberOfLines={8}
            textAlignVertical="top"
            placeholderTextColor="#6E6E73"
            data-testid="pending-send-message"
          />
          <Text style={styles.charCount}>{message.length} chars</Text>
        </View>

        {/* Media Attachments */}
        {(pendingSend.media_urls || []).length > 0 && (
          <View style={styles.mediaSection}>
            <Text style={styles.messageLabel}>Attachments</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {pendingSend.media_urls.map((url: string, i: number) => (
                <Image key={i} source={{ uri: url }} style={styles.mediaThumb} />
              ))}
            </ScrollView>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actions}>
          <TouchableOpacity
            style={styles.sendButton}
            onPress={handleSendViaNative}
            disabled={sending}
            data-testid="pending-send-button"
          >
            {sending ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name={channel === 'email' ? 'mail' : 'chatbubble'} size={18} color="#FFF" />
                <Text style={styles.sendButtonText}>
                  {channel === 'email' ? 'Open Email App & Send' : 'Open SMS App & Send'}
                </Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity style={styles.markSentButton} onPress={markAsSent} data-testid="mark-sent-only">
            <Ionicons name="checkmark-circle" size={18} color="#34C759" />
            <Text style={styles.markSentText}>Already Sent (Mark Complete)</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16,
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1C1C1E',
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 10, backgroundColor: '#1C1C1E',
    alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: '#8E8E93' },
  content: { flex: 1, padding: 16 },
  emptyWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  emptySubtitle: { fontSize: 14, color: '#8E8E93' },
  infoCard: {
    backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: '#2C2C2E', marginBottom: 12,
  },
  channelBadge: {
    width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
  },
  campaignName: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  stepInfo: { fontSize: 12, color: '#8E8E93', marginTop: 1 },
  recipientCard: {
    backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: '#2C2C2E', marginBottom: 12,
  },
  recipientLabel: { fontSize: 11, color: '#8E8E93', fontWeight: '600' },
  recipientName: { fontSize: 16, fontWeight: '700', color: '#FFF', marginTop: 2 },
  recipientDetail: { fontSize: 13, color: '#007AFF', marginTop: 1 },
  messageSection: { marginBottom: 12 },
  messageLabel: { fontSize: 13, fontWeight: '600', color: '#8E8E93', marginBottom: 6 },
  messageInput: {
    backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14,
    color: '#FFF', fontSize: 15, lineHeight: 22, minHeight: 120,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  charCount: { fontSize: 11, color: '#6E6E73', marginTop: 4, textAlign: 'right' },
  mediaSection: { marginBottom: 12 },
  mediaThumb: { width: 80, height: 80, borderRadius: 10, marginRight: 8 },
  actions: { gap: 10, marginTop: 8 },
  sendButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#007AFF', borderRadius: 14, paddingVertical: 16,
  },
  sendButtonText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  markSentButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: '#1C1C1E', borderRadius: 14, paddingVertical: 14,
    borderWidth: 1, borderColor: '#34C75940',
  },
  markSentText: { fontSize: 14, fontWeight: '600', color: '#34C759' },
});
