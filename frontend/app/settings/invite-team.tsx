import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
  Share,
  Platform,
  Clipboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

export default function InviteTeamScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [inviteLink, setInviteLink] = useState<any>(null);
  const [shares, setShares] = useState<any>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  
  // Form state
  const [recipientPhone, setRecipientPhone] = useState('');
  const [recipientName, setRecipientName] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [showShareForm, setShowShareForm] = useState(false);
  const [showEmailForm, setShowEmailForm] = useState(false);
  
  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [user?._id])
  );
  
  const loadData = async () => {
    if (!user?._id) return;
    
    try {
      setLoading(true);
      setLoadError(null);
      const [linkRes, sharesRes] = await Promise.all([
        api.get(`/team-invite/user/${user._id}/invite-link`).catch(() => null),
        api.get(`/team-invite/shares/${user._id}`).catch(() => null),
      ]);
      if (linkRes?.data) setInviteLink(linkRes.data);
      if (sharesRes?.data) setShares(sharesRes.data);
    } catch (error: any) {
      console.error('Failed to load invite data:', error);
      setLoadError(error?.response?.data?.detail || 'Failed to load invite data');
    } finally {
      setLoading(false);
    }
  };
  
  const copyToClipboard = async () => {
    if (!inviteLink?.invite_url) return;
    
    try {
      if (Platform.OS === 'web') {
        await navigator.clipboard.writeText(inviteLink.invite_url);
      } else {
        Clipboard.setString(inviteLink.invite_url);
      }
      Alert.alert('Copied!', 'Invite link copied to clipboard');
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };
  
  const shareNative = async () => {
    if (!inviteLink?.invite_url) return;
    
    try {
      await Share.share({
        message: `Join our team! ${inviteLink.invite_url}`,
        url: inviteLink.invite_url,
      });
    } catch (error) {
      console.error('Share failed:', error);
    }
  };
  
  const sendViaSMS = async () => {
    if (!recipientPhone.trim()) {
      Alert.alert('Error', 'Please enter a phone number');
      return;
    }
    
    try {
      setSending(true);
      const res = await api.post('/team-invite/share-via-sms', {
        user_id: user?._id,
        recipient_phone: recipientPhone.trim(),
        recipient_name: recipientName.trim() || undefined,
      });
      
      if (res.data.success) {
        Alert.alert(
          'Invite Sent!',
          res.data.message_sent 
            ? `SMS sent to ${recipientPhone}`
            : 'Invite queued for delivery'
        );
        setRecipientPhone('');
        setRecipientName('');
        setShowShareForm(false);
        // Refresh shares
        loadData();
      }
    } catch (error: any) {
      console.error('Failed to send invite:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to send invite');
    } finally {
      setSending(false);
    }
  };
  
  const sendViaEmail = async () => {
    if (!recipientEmail.trim()) {
      Alert.alert('Error', 'Please enter an email address');
      return;
    }
    
    if (!recipientEmail.includes('@')) {
      Alert.alert('Error', 'Please enter a valid email address');
      return;
    }
    
    try {
      setSending(true);
      const res = await api.post('/team-invite/send-email-invite', {
        store_id: user?.store_id,
        created_by: user?._id,
        recipient_email: recipientEmail.trim().toLowerCase(),
        recipient_name: recipientName.trim() || undefined,
        custom_message: customMessage.trim() || undefined,
      });
      
      if (res.data.success) {
        Alert.alert(
          'Invite Sent!',
          res.data.email_sent 
            ? `Email invitation sent to ${recipientEmail}`
            : res.data.message
        );
        setRecipientEmail('');
        setRecipientName('');
        setCustomMessage('');
        setShowEmailForm(false);
        loadData();
      }
    } catch (error: any) {
      console.error('Failed to send email invite:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to send invite');
    } finally {
      setSending(false);
    }
  };
  
  const formatPhone = (phone: string) => {
    // Simple phone formatting
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.length === 10) {
      return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
    }
    return phone;
  };
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      </SafeAreaView>
    );
  }
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Invite Team</Text>
        <View style={{ width: 40 }} />
      </View>
      
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Your Invite Link */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="link" size={22} color="#C9A962" />
            <Text style={styles.sectionTitle}>Your Invite Link</Text>
          </View>
          
          <View style={styles.linkBox}>
            <Text style={styles.linkText} numberOfLines={1}>
              {inviteLink?.invite_url || 'Loading...'}
            </Text>
          </View>
          
          <View style={styles.linkActions}>
            <TouchableOpacity style={styles.linkActionButton} onPress={copyToClipboard}>
              <Ionicons name="copy-outline" size={20} color="#FFF" />
              <Text style={styles.linkActionText}>Copy</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.linkActionButton} onPress={shareNative}>
              <Ionicons name="share-outline" size={20} color="#FFF" />
              <Text style={styles.linkActionText}>Share</Text>
            </TouchableOpacity>
          </View>
          
          <View style={styles.usageStats}>
            <Text style={styles.usageText}>
              <Text style={styles.usageNumber}>{inviteLink?.uses_count || 0}</Text> people joined via this link
            </Text>
          </View>
        </View>
        
        {/* Send via SMS */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="chatbubble-ellipses" size={22} color="#007AFF" />
            <Text style={styles.sectionTitle}>Send via SMS</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Share your invite link via SMS to track who clicks and joins
          </Text>
          
          {!showShareForm ? (
            <TouchableOpacity
              style={styles.sendSMSButton}
              onPress={() => setShowShareForm(true)}
            >
              <Ionicons name="paper-plane" size={20} color="#000" />
              <Text style={styles.sendSMSButtonText}>Send Invite via SMS</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.shareForm}>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Phone Number *</Text>
                <TextInput
                  style={styles.textInput}
                  value={recipientPhone}
                  onChangeText={setRecipientPhone}
                  placeholder="(555) 123-4567"
                  placeholderTextColor="#6E6E73"
                  keyboardType="phone-pad"
                  autoFocus
                />
              </View>
              
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Name (optional)</Text>
                <TextInput
                  style={styles.textInput}
                  value={recipientName}
                  onChangeText={setRecipientName}
                  placeholder="John Smith"
                  placeholderTextColor="#6E6E73"
                  autoCapitalize="words"
                />
              </View>
              
              <View style={styles.formActions}>
                <TouchableOpacity
                  style={styles.cancelButton}
                  onPress={() => setShowShareForm(false)}
                >
                  <Text style={styles.cancelButtonText}>Cancel</Text>
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.sendButton}
                  onPress={sendViaSMS}
                  disabled={sending}
                >
                  {sending ? (
                    <ActivityIndicator size="small" color="#000" />
                  ) : (
                    <>
                      <Ionicons name="send" size={18} color="#000" />
                      <Text style={styles.sendButtonText}>Send</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>
        
        {/* Send via Email */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="mail" size={22} color="#34C759" />
            <Text style={styles.sectionTitle}>Send via Email</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Send a professional email invitation with a direct signup link
          </Text>
          
          {!showEmailForm ? (
            <TouchableOpacity
              style={[styles.sendSMSButton, { backgroundColor: '#34C759' }]}
              onPress={() => setShowEmailForm(true)}
              data-testid="send-email-invite-btn"
            >
              <Ionicons name="mail" size={20} color="#FFF" />
              <Text style={[styles.sendSMSButtonText, { color: '#FFF' }]}>Send Email Invite</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.shareForm}>
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email Address *</Text>
                <TextInput
                  style={styles.textInput}
                  value={recipientEmail}
                  onChangeText={setRecipientEmail}
                  placeholder="colleague@company.com"
                  placeholderTextColor="#6E6E73"
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoFocus
                  data-testid="email-invite-email-input"
                />
              </View>
              
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Name (optional)</Text>
                <TextInput
                  style={styles.textInput}
                  value={recipientName}
                  onChangeText={setRecipientName}
                  placeholder="John Smith"
                  placeholderTextColor="#6E6E73"
                  autoCapitalize="words"
                  data-testid="email-invite-name-input"
                />
              </View>
              
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Personal Message (optional)</Text>
                <TextInput
                  style={[styles.textInput, { height: 80, textAlignVertical: 'top' }]}
                  value={customMessage}
                  onChangeText={setCustomMessage}
                  placeholder="Looking forward to working with you!"
                  placeholderTextColor="#6E6E73"
                  multiline
                  data-testid="email-invite-message-input"
                />
              </View>
              
              <View style={styles.formActions}>
                <TouchableOpacity
                  style={styles.cancelButton}
                  onPress={() => {
                    setShowEmailForm(false);
                    setRecipientEmail('');
                    setRecipientName('');
                    setCustomMessage('');
                  }}
                >
                  <Text style={styles.cancelButtonText}>Cancel</Text>
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={[styles.sendButton, { backgroundColor: '#34C759' }]}
                  onPress={sendViaEmail}
                  disabled={sending}
                  data-testid="email-invite-send-btn"
                >
                  {sending ? (
                    <ActivityIndicator size="small" color="#FFF" />
                  ) : (
                    <>
                      <Ionicons name="send" size={18} color="#FFF" />
                      <Text style={[styles.sendButtonText, { color: '#FFF' }]}>Send</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>
        
        {/* Your Analytics */}
        {shares && shares.stats && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="analytics" size={22} color="#34C759" />
              <Text style={styles.sectionTitle}>Your Analytics</Text>
            </View>
            
            <View style={styles.statsGrid}>
              <View style={styles.statCard}>
                <Text style={styles.statNumber}>{shares.stats.total_shares}</Text>
                <Text style={styles.statLabel}>Invites Sent</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statNumber}>{shares.stats.total_clicked}</Text>
                <Text style={styles.statLabel}>Clicked</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statNumber}>{shares.stats.total_joined}</Text>
                <Text style={styles.statLabel}>Joined</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statNumber, { color: '#34C759' }]}>
                  {shares.stats.conversion_rate}%
                </Text>
                <Text style={styles.statLabel}>Conversion</Text>
              </View>
            </View>
          </View>
        )}
        
        {/* Recent Shares */}
        {shares?.shares && shares.shares.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="time" size={22} color="#8E8E93" />
              <Text style={styles.sectionTitle}>Recent Shares</Text>
            </View>
            
            {shares.shares.slice(0, 5).map((share: any, index: number) => (
              <View key={share._id} style={styles.shareRow}>
                <View style={styles.shareInfo}>
                  <Text style={styles.shareName}>
                    {share.recipient_name || 'Unknown'}
                  </Text>
                  <Text style={styles.sharePhone}>{share.recipient_phone}</Text>
                </View>
                <View style={styles.shareStatus}>
                  {share.joined ? (
                    <View style={[styles.statusBadge, { backgroundColor: '#34C759' }]}>
                      <Ionicons name="checkmark-circle" size={14} color="#FFF" />
                      <Text style={styles.statusText}>Joined</Text>
                    </View>
                  ) : share.clicked ? (
                    <View style={[styles.statusBadge, { backgroundColor: '#007AFF' }]}>
                      <Ionicons name="eye" size={14} color="#FFF" />
                      <Text style={styles.statusText}>Clicked</Text>
                    </View>
                  ) : (
                    <View style={[styles.statusBadge, { backgroundColor: '#8E8E93' }]}>
                      <Ionicons name="hourglass" size={14} color="#FFF" />
                      <Text style={styles.statusText}>Pending</Text>
                    </View>
                  )}
                </View>
              </View>
            ))}
          </View>
        )}
        
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  content: {
    padding: 16,
  },
  section: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  sectionDescription: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 16,
  },
  linkBox: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    marginBottom: 12,
  },
  linkText: {
    color: '#007AFF',
    fontSize: 14,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  linkActions: {
    flexDirection: 'row',
    gap: 10,
  },
  linkActionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#3C3C3E',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 8,
  },
  linkActionText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '500',
  },
  usageStats: {
    marginTop: 12,
    alignItems: 'center',
  },
  usageText: {
    color: '#8E8E93',
    fontSize: 14,
  },
  usageNumber: {
    color: '#C9A962',
    fontWeight: '600',
  },
  sendSMSButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 14,
    borderRadius: 25,
    gap: 8,
  },
  sendSMSButtonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },
  shareForm: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 16,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#FFF',
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: '#3C3C3E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  formActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  cancelButton: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#3C3C3E',
  },
  cancelButtonText: {
    color: '#8E8E93',
    fontSize: 15,
    fontWeight: '500',
  },
  sendButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 8,
  },
  sendButtonText: {
    color: '#000',
    fontSize: 15,
    fontWeight: '600',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  statNumber: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFF',
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
  shareRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  shareInfo: {
    flex: 1,
  },
  shareName: {
    fontSize: 15,
    fontWeight: '500',
    color: '#FFF',
  },
  sharePhone: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  shareStatus: {
    marginLeft: 12,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    gap: 4,
  },
  statusText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '500',
  },
});
