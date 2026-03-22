import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';

import { useThemeStore } from '../../store/themeStore';
export default function InviteTeamScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [sending, setSending] = useState(false);
  const [recentInvites, setRecentInvites] = useState<any[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(true);
  
  // Form state
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState('user');
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [website, setWebsite] = useState('');
  const [socialInstagram, setSocialInstagram] = useState('');
  const [socialFacebook, setSocialFacebook] = useState('');
  const [socialLinkedin, setSocialLinkedin] = useState('');
  const [socialTwitter, setSocialTwitter] = useState('');
  const [sendSms, setSendSms] = useState(true);
  const [showExtras, setShowExtras] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [inviteResult, setInviteResult] = useState<{ name: string; email: string; phone: string; password: string; role: string; sms_sent?: boolean; contact_created?: boolean } | null>(null);
  const [copied, setCopied] = useState(false);

  // Available roles based on current user's role
  const getRoleOptions = () => {
    if (user?.role === 'super_admin') {
      return [
        { value: 'org_admin', label: 'Org Admin', icon: 'shield-checkmark', desc: 'Full org access', color: '#007AFF' },
        { value: 'store_manager', label: 'Store Manager', icon: 'storefront', desc: 'Manages a store', color: '#34C759' },
        { value: 'user', label: 'Team Member', icon: 'person', desc: 'Standard access', color: '#C9A962' },
        { value: 'individual', label: 'Individual', icon: 'person-circle', desc: 'Solo account', color: '#AF52DE' },
      ];
    }
    if (user?.role === 'org_admin') {
      return [
        { value: 'store_manager', label: 'Store Manager', icon: 'storefront', desc: 'Manages a store', color: '#34C759' },
        { value: 'user', label: 'Team Member', icon: 'person', desc: 'Standard access', color: '#C9A962' },
      ];
    }
    return [
      { value: 'user', label: 'Team Member', icon: 'person', desc: 'Standard access', color: '#C9A962' },
    ];
  };

  const roleOptions = getRoleOptions();

  useFocusEffect(
    useCallback(() => {
      loadRecentInvites();
    }, [user?._id])
  );

  const loadRecentInvites = async () => {
    if (!user?._id) return;
    try {
      setLoadingRecent(true);
      const res = await api.get('/admin/users', { headers: { 'X-User-ID': user._id } });
      // Show recently created users as "invites"
      const recent = (res.data || [])
        .filter((u: any) => u._id !== user._id)
        .sort((a: any, b: any) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
        .slice(0, 5);
      setRecentInvites(recent);
    } catch (error) {
      console.error('Failed to load recent invites:', error);
    } finally {
      setLoadingRecent(false);
    }
  };

  const handleSendInvite = async () => {
    if (!firstName.trim()) {
      showSimpleAlert('First Name Required', 'Please enter a first name');
      return;
    }
    if (!lastName.trim()) {
      showSimpleAlert('Last Name Required', 'Please enter a last name');
      return;
    }
    if (!email.trim() || !email.includes('@')) {
      showSimpleAlert('Valid Email Required', 'Please enter a valid email address');
      return;
    }
    if (!phone.trim()) {
      showSimpleAlert('Phone Required', 'Please enter a phone number');
      return;
    }

    setSending(true);
    setSuccessMessage('');
    setInviteResult(null);
    setCopied(false);
    try {
      const fullName = `${firstName.trim()} ${lastName.trim()}`;
      const payload: any = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        name: fullName,
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        role: role === 'individual' ? 'user' : role,
        send_invite: true,
        send_sms: sendSms,
        ...(role !== 'individual' && user?.organization_id ? { organization_id: user.organization_id } : {}),
        ...(role !== 'individual' && role === 'user' && user?.store_id ? { store_id: user.store_id } : {}),
      };
      if (title.trim()) payload.title = title.trim();
      if (company.trim()) payload.company = company.trim();
      if (website.trim()) payload.website = website.trim();
      if (socialInstagram.trim()) payload.social_instagram = socialInstagram.trim();
      if (socialFacebook.trim()) payload.social_facebook = socialFacebook.trim();
      if (socialLinkedin.trim()) payload.social_linkedin = socialLinkedin.trim();
      if (socialTwitter.trim()) payload.social_twitter = socialTwitter.trim();

      const res = await api.post('/admin/users/create', payload, {
        headers: { 'X-User-ID': user?._id }
      });

      const data = res.data;
      if (data.success) {
        const roleName = roleOptions.find(r => r.value === role)?.label || 'Team Member';
        setSuccessMessage(`${fullName} has been created as ${roleName}.`);
        setInviteResult({
          name: fullName,
          email: email.trim().toLowerCase(),
          phone: phone.trim(),
          password: data.temp_password || '',
          role: roleName,
          sms_sent: data.sms_sent,
          contact_created: data.contact_created,
        });
        // Reset form
        setFirstName(''); setLastName(''); setEmail(''); setPhone('');
        setTitle(''); setCompany(''); setWebsite('');
        setSocialInstagram(''); setSocialFacebook(''); setSocialLinkedin(''); setSocialTwitter('');
        setRole('user'); setShowExtras(false);
        loadRecentInvites();
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to send invitation';
      showSimpleAlert('Error', detail);
    } finally {
      setSending(false);
    }
  };

  const getInviteText = () => {
    if (!inviteResult) return '';
    return (
      `Welcome to i'M On Social, ${inviteResult.name}!\n\n` +
      `Your login: ${inviteResult.email}\n` +
      `Temp password: ${inviteResult.password}\n\n` +
      `Download the app:\n` +
      `Apple: https://apps.apple.com/app/im-on-social/id6743597907\n` +
      `Android: https://play.google.com/store/apps/details?id=com.imonsocial.app\n\n` +
      `Or log in at: https://app.imonsocial.com`
    );
  };

  const handleCopyInvite = async () => {
    const text = getInviteText();
    try {
      if (Platform.OS === 'web') {
        await navigator.clipboard.writeText(text);
      } else {
        await Clipboard.setStringAsync(text);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch (e) {
      showSimpleAlert('Copy Failed', 'Could not copy to clipboard');
    }
  };

  const handleNewInvite = () => {
    setInviteResult(null);
    setSuccessMessage('');
    setCopied(false);
  };

  const handleDeleteMember = async (memberId: string, memberName: string) => {
    showConfirm(
      'Remove Team Member',
      `Are you sure you want to remove ${memberName}? This action cannot be undone.`,
      async () => {
        try {
          await api.delete(`/admin/users/${memberId}`, {
            headers: { 'X-User-ID': user?._id },
          });
          loadRecentInvites();
        } catch (error: any) {
          const detail = error?.response?.data?.detail || 'Failed to delete user';
          showSimpleAlert('Error', detail);
        }
      },
      undefined,
      'Remove',
      'Cancel'
    );
  };

  const getRoleBadgeColor = (r: string) => {
    switch (r) {
      case 'super_admin': return '#FF3B30';
      case 'org_admin': return '#007AFF';
      case 'store_manager': return '#34C759';
      case 'individual': return '#AF52DE';
      default: return colors.textSecondary;
    }
  };

  const getRoleLabel = (r: string) => {
    switch (r) {
      case 'super_admin': return 'Super Admin';
      case 'org_admin': return 'Org Admin';
      case 'store_manager': return 'Manager';
      case 'individual': return 'Individual';
      default: return 'Team Member';
    }
  };

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
        {/* Invite Form */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="person-add" size={22} color="#C9A962" />
            <Text style={styles.sectionTitle}>Send Invitation</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Create a new team member and send them login credentials
          </Text>

          {/* Show invite result card OR the form */}
          {inviteResult ? (
            <View style={styles.inviteResultCard}>
              <View style={styles.inviteResultHeader}>
                <Ionicons name="checkmark-circle" size={24} color="#34C759" />
                <Text style={styles.inviteResultTitle}>{successMessage}</Text>
              </View>

              {inviteResult.sms_sent && (
                <View style={[styles.successBanner, { marginBottom: 0 }]}>
                  <Ionicons name="chatbubble" size={16} color="#34C759" />
                  <Text style={styles.successText}>SMS sent with login info &amp; app links</Text>
                </View>
              )}
              {inviteResult.contact_created && (
                <View style={[styles.successBanner, { marginBottom: 0, backgroundColor: 'rgba(0,122,255,0.1)' }]}>
                  <Ionicons name="person-add" size={16} color="#007AFF" />
                  <Text style={[styles.successText, { color: '#007AFF' }]}>Added to your contacts with "new-user" tag</Text>
                </View>
              )}
              
              <View style={styles.inviteCredentials}>
                <View style={styles.credRow}>
                  <Text style={styles.credLabel}>Email</Text>
                  <Text style={styles.credValue} selectable>{inviteResult.email}</Text>
                </View>
                <View style={styles.credDivider} />
                <View style={styles.credRow}>
                  <Text style={styles.credLabel}>Phone</Text>
                  <Text style={styles.credValue} selectable>{inviteResult.phone}</Text>
                </View>
                <View style={styles.credDivider} />
                <TouchableOpacity style={styles.credRow} onPress={async () => {
                  try {
                    if (Platform.OS === 'web') { await navigator.clipboard.writeText(inviteResult.password); }
                    else { await Clipboard.setStringAsync(inviteResult.password); }
                    showSimpleAlert('Copied', 'Password copied to clipboard');
                  } catch {}
                }}>
                  <Text style={styles.credLabel}>Password</Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Text style={[styles.credValue, { color: '#007AFF' }]} selectable>{inviteResult.password}</Text>
                    <Ionicons name="copy-outline" size={14} color="#007AFF" />
                  </View>
                </TouchableOpacity>
                <View style={styles.credDivider} />
                <View style={styles.credRow}>
                  <Text style={styles.credLabel}>Role</Text>
                  <Text style={styles.credValue}>{inviteResult.role}</Text>
                </View>
              </View>

              <TouchableOpacity
                style={[styles.copyButton, copied && styles.copyButtonCopied]}
                onPress={handleCopyInvite}
                data-testid="copy-invite-btn"
              >
                <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={20} color={copied ? '#34C759' : '#FFF'} />
                <Text style={[styles.copyButtonText, copied && { color: '#34C759' }]}>
                  {copied ? 'Copied! Paste in your text app' : 'Copy Invite Message'}
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.newInviteButton}
                onPress={handleNewInvite}
                data-testid="new-invite-btn"
              >
                <Ionicons name="add-circle-outline" size={18} color="#007AFF" />
                <Text style={styles.newInviteButtonText}>Send Another Invite</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <>

          {successMessage && !inviteResult ? (
            <View style={styles.successBanner}>
              <Ionicons name="checkmark-circle" size={22} color="#34C759" />
              <Text style={styles.successText}>{successMessage}</Text>
            </View>
          ) : null}

          {/* First + Last Name — side by side */}
          <View style={{ flexDirection: 'row', gap: 10, marginBottom: 16 }}>
            <View style={{ flex: 1 }}>
              <Text style={styles.inputLabel}>First Name *</Text>
              <View style={styles.inputRow}>
                <Ionicons name="person-outline" size={18} color={colors.textSecondary} />
                <TextInput
                  style={styles.textInput}
                  value={firstName}
                  onChangeText={setFirstName}
                  placeholder="John"
                  placeholderTextColor="#6E6E73"
                  autoCapitalize="words"
                  data-testid="invite-first-name"
                />
              </View>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.inputLabel}>Last Name *</Text>
              <View style={styles.inputRow}>
                <TextInput
                  style={styles.textInput}
                  value={lastName}
                  onChangeText={setLastName}
                  placeholder="Smith"
                  placeholderTextColor="#6E6E73"
                  autoCapitalize="words"
                  data-testid="invite-last-name"
                />
              </View>
            </View>
          </View>

          <View style={styles.formGroup}>
            <Text style={styles.inputLabel}>Email Address *</Text>
            <View style={styles.inputRow}>
              <Ionicons name="mail-outline" size={18} color={colors.textSecondary} />
              <TextInput
                style={styles.textInput}
                value={email}
                onChangeText={setEmail}
                placeholder="john@company.com"
                placeholderTextColor="#6E6E73"
                keyboardType="email-address"
                autoCapitalize="none"
                data-testid="invite-email"
              />
            </View>
          </View>

          <View style={styles.formGroup}>
            <Text style={styles.inputLabel}>Phone Number *</Text>
            <View style={styles.inputRow}>
              <Ionicons name="call-outline" size={18} color={colors.textSecondary} />
              <TextInput
                style={styles.textInput}
                value={phone}
                onChangeText={setPhone}
                placeholder="(555) 123-4567"
                placeholderTextColor="#6E6E73"
                keyboardType="phone-pad"
                data-testid="invite-phone"
              />
            </View>
          </View>

          {/* Optional enrichment — collapsible */}
          <TouchableOpacity
            style={styles.extrasToggle}
            onPress={() => setShowExtras(!showExtras)}
            data-testid="invite-show-extras"
          >
            <Ionicons name={showExtras ? 'chevron-up' : 'chevron-down'} size={18} color="#007AFF" />
            <Text style={styles.extrasToggleText}>
              {showExtras ? 'Hide' : 'Add'} title, company & social links
            </Text>
          </TouchableOpacity>

          {showExtras && (
            <View style={styles.extrasSection}>
              <View style={{ flexDirection: 'row', gap: 10, marginBottom: 16 }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.inputLabel}>Title</Text>
                  <View style={styles.inputRow}>
                    <Ionicons name="briefcase-outline" size={16} color={colors.textSecondary} />
                    <TextInput style={styles.textInput} value={title} onChangeText={setTitle} placeholder="Sales Manager" placeholderTextColor="#6E6E73" autoCapitalize="words" data-testid="invite-title" />
                  </View>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.inputLabel}>Company</Text>
                  <View style={styles.inputRow}>
                    <Ionicons name="business-outline" size={16} color={colors.textSecondary} />
                    <TextInput style={styles.textInput} value={company} onChangeText={setCompany} placeholder="ABC Motors" placeholderTextColor="#6E6E73" autoCapitalize="words" data-testid="invite-company" />
                  </View>
                </View>
              </View>
              <View style={styles.formGroup}>
                <Text style={styles.inputLabel}>Website</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="globe-outline" size={16} color={colors.textSecondary} />
                  <TextInput style={styles.textInput} value={website} onChangeText={setWebsite} placeholder="www.company.com" placeholderTextColor="#6E6E73" autoCapitalize="none" keyboardType="url" data-testid="invite-website" />
                </View>
              </View>
              <View style={styles.formGroup}>
                <Text style={styles.inputLabel}>Social Links</Text>
                <View style={{ gap: 8 }}>
                  <View style={styles.inputRow}>
                    <Ionicons name="logo-instagram" size={16} color="#E4405F" />
                    <TextInput style={styles.textInput} value={socialInstagram} onChangeText={setSocialInstagram} placeholder="Instagram URL" placeholderTextColor="#6E6E73" autoCapitalize="none" />
                  </View>
                  <View style={styles.inputRow}>
                    <Ionicons name="logo-facebook" size={16} color="#1877F2" />
                    <TextInput style={styles.textInput} value={socialFacebook} onChangeText={setSocialFacebook} placeholder="Facebook URL" placeholderTextColor="#6E6E73" autoCapitalize="none" />
                  </View>
                  <View style={styles.inputRow}>
                    <Ionicons name="logo-linkedin" size={16} color="#0A66C2" />
                    <TextInput style={styles.textInput} value={socialLinkedin} onChangeText={setSocialLinkedin} placeholder="LinkedIn URL" placeholderTextColor="#6E6E73" autoCapitalize="none" />
                  </View>
                  <View style={styles.inputRow}>
                    <Ionicons name="logo-twitter" size={16} color="#1DA1F2" />
                    <TextInput style={styles.textInput} value={socialTwitter} onChangeText={setSocialTwitter} placeholder="Twitter/X URL" placeholderTextColor="#6E6E73" autoCapitalize="none" />
                  </View>
                </View>
              </View>
            </View>
          )}

          <View style={styles.formGroup}>
            <Text style={styles.inputLabel}>Role</Text>
            <View style={styles.roleSelector}>
              {roleOptions.map((opt) => {
                const isActive = role === opt.value;
                return (
                  <TouchableOpacity
                    key={opt.value}
                    style={[
                      styles.roleOption,
                      isActive && styles.roleOptionActive,
                      isActive && { borderColor: opt.color },
                    ]}
                    onPress={() => setRole(opt.value)}
                  >
                    <View style={[styles.roleIconWrap, { backgroundColor: (isActive ? opt.color : colors.borderLight) + '25' }]}>
                      <Ionicons name={opt.icon as any} size={18} color={isActive ? opt.color : colors.textSecondary} />
                    </View>
                    <View style={styles.roleTextWrap}>
                      <Text style={[styles.roleOptionText, isActive && styles.roleOptionTextActive]}>{opt.label}</Text>
                      <Text style={styles.roleDesc}>{opt.desc}</Text>
                    </View>
                    <View style={[styles.roleRadio, isActive && styles.roleRadioActive, isActive && { borderColor: opt.color }]}>
                      {isActive ? <View style={[styles.roleRadioDot, { backgroundColor: opt.color }]} /> : null}
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* SMS Toggle */}
          <TouchableOpacity
            style={styles.smsToggle}
            onPress={() => setSendSms(!sendSms)}
            data-testid="invite-sms-toggle"
          >
            <View style={styles.smsToggleLeft}>
              <Ionicons name="chatbubble-outline" size={18} color={sendSms ? '#34C759' : colors.textSecondary} />
              <View>
                <Text style={[styles.inputLabel, { marginBottom: 0 }]}>Send SMS with login info</Text>
                <Text style={{ fontSize: 14, color: colors.textSecondary }}>App links + temp password via text</Text>
              </View>
            </View>
            <View style={[styles.toggle, sendSms && styles.toggleActive]}>
              <View style={[styles.toggleDot, sendSms && styles.toggleDotActive]} />
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.sendButton, sending && { opacity: 0.6 }]}
            onPress={handleSendInvite}
            disabled={sending}
            data-testid="invite-send-btn"
          >
            {sending ? (
              <ActivityIndicator size="small" color={colors.text} />
            ) : (
              <>
                <Ionicons name="person-add" size={18} color={colors.text} />
                <Text style={styles.sendButtonText}>Create User</Text>
              </>
            )}
          </TouchableOpacity>
            </>
          )}
        </View>

        {/* Recent Team Members */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="people" size={22} color="#007AFF" />
            <Text style={styles.sectionTitle}>Recent Team Members</Text>
          </View>

          {loadingRecent ? (
            <ActivityIndicator size="small" color="#C9A962" style={{ marginVertical: 20 }} />
          ) : recentInvites.length === 0 ? (
            <Text style={styles.emptyText}>No team members yet. Send your first invite above!</Text>
          ) : (
            recentInvites.map((member: any) => (
              <View key={member._id} style={styles.memberRow}>
                <View style={styles.memberAvatar}>
                  <Text style={styles.memberAvatarText}>
                    {(member.name || '?').split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)}
                  </Text>
                </View>
                <View style={styles.memberInfo}>
                  <Text style={styles.memberName}>{member.name}</Text>
                  <Text style={styles.memberEmail}>{member.email}</Text>
                </View>
                <View style={[styles.roleBadge, { backgroundColor: getRoleBadgeColor(member.role) + '20' }]}>
                  <Text style={[styles.roleBadgeText, { color: getRoleBadgeColor(member.role) }]}>
                    {getRoleLabel(member.role)}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.deleteButton}
                  onPress={() => handleDeleteMember(member._id, member.name)}
                  data-testid={`delete-member-${member._id}`}
                >
                  <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            ))
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    padding: 16,
  },
  section: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  sectionDescription: {
    fontSize: 16,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: 'rgba(52, 199, 89, 0.15)',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
  },
  successText: {
    flex: 1,
    color: '#34C759',
    fontSize: 16,
    lineHeight: 20,
  },
  formGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.text,
    marginBottom: 8,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: 14,
    gap: 10,
  },
  textInput: {
    flex: 1,
    fontSize: 18,
    color: colors.text,
    paddingVertical: 14,
  },
  roleSelector: {
    flexDirection: 'column',
    gap: 8,
  },
  roleOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: 'transparent',
    gap: 12,
  },
  roleOptionActive: {
    backgroundColor: '#1A1A1A',
  },
  roleIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  roleTextWrap: {
    flex: 1,
  },
  roleOptionText: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  roleOptionTextActive: {
    color: colors.text,
  },
  roleDesc: {
    fontSize: 14,
    color: '#6E6E73',
    marginTop: 1,
  },
  roleRadio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  roleRadioActive: {
    borderWidth: 2,
  },
  roleRadioDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  sendButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 16,
    borderRadius: 25,
    gap: 8,
    marginTop: 4,
  },
  sendButtonText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
  },
  emptyText: {
    color: '#6E6E73',
    fontSize: 16,
    textAlign: 'center',
    paddingVertical: 20,
  },
  memberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
    gap: 12,
  },
  memberAvatar: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  memberAvatarText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '500',
  },
  memberEmail: {
    color: colors.textSecondary,
    fontSize: 15,
    marginTop: 2,
  },
  roleBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  roleBadgeText: {
    fontSize: 14,
    fontWeight: '600',
  },
  deleteButton: {
    padding: 8,
    marginLeft: 8,
  },
  // Invite result card
  inviteResultCard: {
    gap: 16,
  },
  inviteResultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  inviteResultTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
    color: '#34C759',
  },
  inviteCredentials: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    overflow: 'hidden',
  },
  credRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  credLabel: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  credValue: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  credDivider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginHorizontal: 16,
  },
  copyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    paddingVertical: 16,
    borderRadius: 25,
    gap: 8,
  },
  copyButtonCopied: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: '#34C759',
  },
  copyButtonText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
  },
  newInviteButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
  },
  newInviteButtonText: {
    color: '#007AFF',
    fontSize: 16,
    fontWeight: '500',
  },
  extrasToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 10,
    marginBottom: 8,
  },
  extrasToggleText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
  extrasSection: {
    marginBottom: 8,
  },
  smsToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    padding: 14,
    borderRadius: 12,
    marginBottom: 16,
  },
  smsToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  toggle: {
    width: 44,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.borderLight,
    padding: 2,
    justifyContent: 'center',
  },
  toggleActive: {
    backgroundColor: '#34C759',
  },
  toggleDot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#fff',
  },
  toggleDotActive: {
    alignSelf: 'flex-end' as const,
  },
});
