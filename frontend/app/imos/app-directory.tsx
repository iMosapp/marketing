import React, { useState, useMemo } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, TextInput, Platform, LayoutAnimation, UIManager, ActivityIndicator, Alert,
  useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { ImosHeader, ImosFooter, getShareUrl } from './_components';
import api from '../../services/api';
import { WebModal } from '../../components/WebModal';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const PROD_BASE = 'https://app.imosapp.com';

type PageEntry = {
  name: string;
  description: string;
  path: string;
  icon: string;
  color: string;
  audience: string;
};

type Category = {
  id: string;
  title: string;
  icon: string;
  color: string;
  pages: PageEntry[];
};

const PAGE_CATALOG: Category[] = [
  {
    id: 'public_pages',
    title: 'Public Customer Pages',
    icon: 'globe-outline',
    color: '#34C759',
    pages: [
      { name: 'Digital Business Card', description: 'Shareable card with photo, QR, reviews, social links', path: '/imos/digital-card', icon: 'card-outline', color: '#007AFF', audience: 'Customers, prospects' },
      { name: 'Congrats Card', description: 'Branded congratulations card for customers', path: '/imos/congrats-template', icon: 'gift-outline', color: '#007AFF', audience: 'Customers' },
      { name: 'Birthday Card', description: 'Personalized birthday card with photo & message', path: '/imos/birthday-card', icon: 'gift-outline', color: '#FF6B8A', audience: 'Customers' },
      { name: 'Review Page', description: 'Store review landing page with Google, Yelp, Facebook links', path: '/imos/reviews', icon: 'star-outline', color: '#FFD60A', audience: 'Customers' },
      { name: 'Showcase', description: 'User showcase page  - congrats cards, featured work', path: '/imos/showcase', icon: 'images-outline', color: '#007AFF', audience: 'Customers, public' },
      { name: 'Join / Invite Page', description: 'Team invite link landing page', path: '/imos/join', icon: 'person-add-outline', color: '#34C759', audience: 'New team members' },
      { name: 'Partner Agreement', description: 'Public partner agreement signing page', path: '/imos/partner-agreements', icon: 'document-text-outline', color: '#FF9500', audience: 'Partners' },
      { name: 'NDA Signing', description: 'Public NDA signing page', path: '/imos/nda', icon: 'lock-closed-outline', color: '#FF3B30', audience: 'Partners, employees' },
    ],
  },
  {
    id: 'marketing',
    title: 'Marketing & Sales',
    icon: 'diamond-outline',
    color: '#007AFF',
    pages: [
      { name: "i'M On Social Home", description: 'Main marketing page', path: '/imos', icon: 'home-outline', color: '#007AFF', audience: 'Everyone' },
      { name: 'Sales Presentation', description: 'Interactive slide deck for prospects', path: '/imos/salespresentation', icon: 'easel-outline', color: '#007AFF', audience: 'Prospects, investors' },
      { name: 'Features Overview', description: 'Full feature showcase', path: '/imos/features', icon: 'apps-outline', color: '#007AFF', audience: 'Prospects, customers' },
      { name: 'Pricing Plans', description: 'Subscription tiers & pricing', path: '/imos/pricing', icon: 'pricetag-outline', color: '#34C759', audience: 'Prospects, customers' },
      { name: 'Page Hub', description: 'Browse all public pages', path: '/imos/hub', icon: 'grid-outline', color: '#5856D6', audience: 'Everyone' },
      { name: 'App Directory', description: 'Full page catalog with search & share', path: '/imos/app-directory', icon: 'folder-outline', color: '#FF9500', audience: 'Admins, partners' },
      { name: 'Reviews & Reputation', description: 'Marketing page for the reviews feature', path: '/imos/reviews', icon: 'star', color: '#FFD60A', audience: 'Prospects, demos' },
    ],
  },
  {
    id: 'onboarding',
    title: 'Onboarding & Training',
    icon: 'rocket-outline',
    color: '#FF9500',
    pages: [
      { name: 'Onboarding Preview', description: 'Preview all 5 role onboarding flows', path: '/imos/onboarding-preview', icon: 'eye-outline', color: '#007AFF', audience: 'Admins, prospects' },
      { name: 'Training Hub', description: "Learn how to use i'M On Social", path: '/imos/training', icon: 'school-outline', color: '#FF9500', audience: 'All users' },
    ],
  },
  {
    id: 'core',
    title: 'Core App',
    icon: 'apps-outline',
    color: '#007AFF',
    pages: [
      { name: 'Inbox', description: 'Message conversations & threads', path: '/imos/inbox', icon: 'chatbubble-outline', color: '#007AFF', audience: 'All users' },
      { name: 'Contacts', description: 'Contact management & CRM', path: '/imos/contacts', icon: 'people-outline', color: '#5856D6', audience: 'All users' },
      { name: 'Dialer', description: 'Phone dialer & call log', path: '/imos/dialer', icon: 'keypad-outline', color: '#34C759', audience: 'All users' },
      { name: 'Team Chat', description: 'Team collaboration', path: '/imos/team', icon: 'chatbubbles-outline', color: '#FF9500', audience: 'All users' },
      { name: 'More / Settings', description: 'Navigation hub', path: '/imos/more', icon: 'menu-outline', color: '#8E8E93', audience: 'All users' },
    ],
  },
  {
    id: 'communication',
    title: 'Communication Tools',
    icon: 'megaphone-outline',
    color: '#FF2D55',
    pages: [
      { name: 'Broadcast', description: 'Mass messaging to team', path: '/imos/broadcast', icon: 'megaphone-outline', color: '#FF9500', audience: 'All users' },
      { name: 'SMS Campaigns', description: 'Automated SMS follow-ups', path: '/imos/campaigns', icon: 'chatbubbles-outline', color: '#FF2D55', audience: 'All users' },
      { name: 'Email Campaigns', description: 'Automated email follow-ups', path: '/imos/campaigns/email', icon: 'mail-outline', color: '#AF52DE', audience: 'All users' },
      { name: 'Campaign Dashboard', description: 'Campaign analytics & enrollments', path: '/imos/campaigns/dashboard', icon: 'speedometer-outline', color: '#5AC8FA', audience: 'All users' },
      { name: 'Date Triggers', description: 'Birthday, anniversary, holiday campaigns', path: '/imos/date-triggers', icon: 'calendar-outline', color: '#FF9500', audience: 'All users' },
    ],
  },
  {
    id: 'templates',
    title: 'Templates & Branding',
    icon: 'color-palette-outline',
    color: '#AF52DE',
    pages: [
      { name: 'SMS Templates', description: 'Pre-built SMS messages', path: '/imos/templates', icon: 'document-text-outline', color: '#FFD60A', audience: 'All users' },
      { name: 'Email Templates', description: 'Pre-built email designs', path: '/imos/email-templates', icon: 'mail-outline', color: '#34C759', audience: 'All users' },
      { name: 'Brand Kit', description: 'Email branding & colors', path: '/imos/brand-kit', icon: 'color-palette-outline', color: '#AF52DE', audience: 'All users' },
      { name: 'Congrats Cards', description: 'Thank you card templates', path: '/imos/congrats-template', icon: 'gift-outline', color: '#007AFF', audience: 'All users' },
    ],
  },
  {
    id: 'analytics',
    title: 'Performance & Analytics',
    icon: 'stats-chart-outline',
    color: '#34C759',
    pages: [
      { name: 'Analytics', description: 'Performance metrics', path: '/imos/analytics', icon: 'stats-chart-outline', color: '#34C759', audience: 'All users' },
      { name: 'Reports', description: 'Detailed performance reports', path: '/imos/reports', icon: 'bar-chart-outline', color: '#007AFF', audience: 'All users' },
      { name: 'Email Analytics', description: 'Opens, clicks, engagement', path: '/imos/email-analytics', icon: 'trending-up-outline', color: '#FF2D55', audience: 'All users' },
      { name: 'Leaderboard', description: 'Team performance rankings', path: '/imos/leaderboard', icon: 'trophy-outline', color: '#FFD60A', audience: 'Team members' },
    ],
  },
  {
    id: 'contacts_leads',
    title: 'Contacts & Leads',
    icon: 'people-outline',
    color: '#5856D6',
    pages: [
      { name: 'Lead Sources', description: 'Inbound lead routing config', path: '/imos/lead-sources', icon: 'git-branch-outline', color: '#5856D6', audience: 'Admins' },
      { name: 'Contact Tags', description: 'Tag management', path: '/imos/tags', icon: 'pricetags-outline', color: '#FF9500', audience: 'All users' },
      { name: 'Review Links', description: 'Google, Facebook, Yelp links', path: '/imos/review-links', icon: 'star-outline', color: '#FFD60A', audience: 'All users' },
      { name: 'Import Contacts', description: 'Bulk import from CSV', path: '/imos/import', icon: 'cloud-upload-outline', color: '#007AFF', audience: 'All users' },
    ],
  },
  {
    id: 'profile_ai',
    title: 'Profile & AI',
    icon: 'person-outline',
    color: '#FF9500',
    pages: [
      { name: 'Digital Card', description: 'Bio, socials & shareable card', path: '/imos/digital-card', icon: 'card-outline', color: '#007AFF', audience: 'All users' },
      { name: 'AI Persona', description: 'Communication style settings', path: '/imos/persona', icon: 'sparkles-outline', color: '#AF52DE', audience: 'All users' },
      { name: 'Ask Jessi', description: 'AI assistant', path: '/imos/jessi', icon: 'sparkles-outline', color: '#007AFF', audience: 'All users' },
      { name: 'My Account', description: 'Account settings & profile', path: '/imos/account', icon: 'person-circle-outline', color: '#8E8E93', audience: 'All users' },
    ],
  },
  {
    id: 'settings',
    title: 'Settings',
    icon: 'settings-outline',
    color: '#8E8E93',
    pages: [
      { name: 'Security', description: 'Passwords & authentication', path: '/imos/security', icon: 'shield-checkmark-outline', color: '#FF3B30', audience: 'All users' },
      { name: 'Calendar', description: 'Connect external calendars', path: '/imos/calendar', icon: 'calendar-outline', color: '#007AFF', audience: 'All users' },
      { name: 'Integrations', description: 'API keys & webhooks', path: '/imos/integrations', icon: 'git-network-outline', color: '#5856D6', audience: 'All users' },
      { name: 'Invite Team', description: 'Send team invitations', path: '/imos/invite-team', icon: 'person-add-outline', color: '#007AFF', audience: 'Admins' },
    ],
  },
  {
    id: 'admin',
    title: 'Administration',
    icon: 'shield-checkmark-outline',
    color: '#FF3B30',
    pages: [
      { name: 'Admin Dashboard', description: 'Overview & activity feed', path: '/imos/admin', icon: 'shield-checkmark-outline', color: '#34C759', audience: 'Admins' },
      { name: 'Users', description: 'Manage team members', path: '/imos/users', icon: 'people-outline', color: '#FF9500', audience: 'Admins' },
      { name: 'Organizations', description: 'Manage organizations', path: '/imos/organizations', icon: 'business-outline', color: '#007AFF', audience: 'Super Admin' },
      { name: 'Stores', description: 'Manage store accounts', path: '/imos/stores', icon: 'storefront-outline', color: '#34C759', audience: 'Admins' },
      { name: 'Pending Users', description: 'Approve new signups', path: '/imos/pending-users', icon: 'person-add-outline', color: '#FF3B30', audience: 'Super Admin' },
      { name: 'Individuals', description: 'Independent user management', path: '/imos/individuals', icon: 'person-outline', color: '#AF52DE', audience: 'Super Admin' },
      { name: 'Company Directory', description: 'Team roster & leaderboards', path: '/imos/directory', icon: 'people-outline', color: '#AF52DE', audience: 'Admins' },
      { name: 'Shared Inboxes', description: 'Phone number assignments', path: '/imos/shared-inboxes', icon: 'mail-outline', color: '#007AFF', audience: 'Super Admin' },
      { name: 'Bulk Transfer', description: 'Transfer contacts between users', path: '/imos/bulk-transfer', icon: 'swap-horizontal-outline', color: '#FF3B30', audience: 'Super Admin' },
      { name: 'Phone Assignments', description: 'Twilio number management', path: '/imos/phone-assignments', icon: 'call-outline', color: '#32ADE6', audience: 'Super Admin' },
      { name: 'Partner Agreements', description: 'Reseller contracts', path: '/imos/partner-agreements', icon: 'document-text-outline', color: '#FF9500', audience: 'Super Admin' },
      { name: 'Billing', description: 'Subscription & billing info', path: '/imos/billing', icon: 'card-outline', color: '#34C759', audience: 'Admins' },
      { name: 'Activity Feed', description: 'Recent admin activity', path: '/imos/activity-feed', icon: 'pulse-outline', color: '#FF2D55', audience: 'Admins' },
    ],
  },
  {
    id: 'legal',
    title: 'Legal & Compliance',
    icon: 'shield-outline',
    color: '#8E8E93',
    pages: [
      { name: 'Privacy Policy', description: 'How we protect your data', path: '/imos/privacy', icon: 'shield-outline', color: '#5856D6', audience: 'Everyone' },
      { name: 'Terms of Service', description: 'Usage terms and conditions', path: '/imos/terms', icon: 'document-text-outline', color: '#8E8E93', audience: 'Everyone' },
      { name: 'Login', description: "Sign in to i'M On Social", path: '/imos/login', icon: 'log-in-outline', color: '#007AFF', audience: 'All users' },
      { name: 'Sign Up', description: 'Create a new account', path: '/imos/signup', icon: 'person-add-outline', color: '#34C759', audience: 'New users' },
    ],
  },
];

export default function AppDirectoryScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const maxW = isDesktop ? 960 : undefined;
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['public_pages', 'marketing']));
  const [shareModal, setShareModal] = useState<PageEntry | null>(null);
  const [shareChannel, setShareChannel] = useState<'email' | 'sms'>('email');
  const [recipientName, setRecipientName] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  const filteredCatalog = useMemo(() => {
    if (!searchQuery.trim()) return PAGE_CATALOG;
    const q = searchQuery.toLowerCase();
    return PAGE_CATALOG.map(cat => ({
      ...cat,
      pages: cat.pages.filter(p =>
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.path.toLowerCase().includes(q) ||
        p.audience.toLowerCase().includes(q)
      ),
    })).filter(cat => cat.pages.length > 0);
  }, [searchQuery]);

  const totalPages = useMemo(() => PAGE_CATALOG.reduce((sum, c) => sum + c.pages.length, 0), []);

  const toggleCategory = (id: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpandedCategories(prev => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  };

  const getFullUrl = (path: string) => `${PROD_BASE}${path}`;

  const handleCopyLink = async (page: PageEntry) => {
    const url = getFullUrl(page.path);
    if (Platform.OS === 'web' && navigator.clipboard) {
      await navigator.clipboard.writeText(url);
    }
    setCopiedPath(page.path);
    setTimeout(() => setCopiedPath(null), 2000);
    try { await api.post('/admin/app-directory/share/copy-link', { page_name: page.name, page_path: page.path }); } catch {}
  };

  const handlePreview = (page: PageEntry) => {
    router.push(page.path as any);
  };

  const handleShare = async () => {
    if (!shareModal) return;
    if (shareChannel === 'email' && !recipientEmail.trim()) {
      Alert.alert('Required', 'Please enter an email address');
      return;
    }
    if (shareChannel === 'sms' && !recipientPhone.trim()) {
      Alert.alert('Required', 'Please enter a phone number');
      return;
    }
    setSending(true);
    try {
      const res = await api.post('/admin/app-directory/share', {
        page_name: shareModal.name,
        page_path: shareModal.path,
        page_url: getFullUrl(shareModal.path),
        recipient_name: recipientName.trim() || undefined,
        recipient_email: shareChannel === 'email' ? recipientEmail.trim() : undefined,
        recipient_phone: shareChannel === 'sms' ? recipientPhone.trim() : undefined,
        channel: shareChannel,
        custom_message: customMessage.trim() || undefined,
      });
      if (res.data.success) {
        Alert.alert('Sent!', `${shareChannel === 'email' ? 'Email' : 'SMS'} sent successfully`);
        closeShareModal();
      }
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || 'Failed to send');
    } finally {
      setSending(false);
    }
  };

  const closeShareModal = () => {
    setShareModal(null);
    setRecipientName('');
    setRecipientEmail('');
    setRecipientPhone('');
    setCustomMessage('');
    setShareChannel('email');
  };

  return (
    <View style={st.container}>
      <ImosHeader />
      <ScrollView contentContainerStyle={st.scroll} showsVerticalScrollIndicator={false}>
        <View style={maxW ? { maxWidth: maxW, alignSelf: 'center', width: '100%' } : undefined}>

          {/* Title */}
          <View style={st.titleSection}>
            <Text style={st.label}>ALL PAGES</Text>
            <Text style={[st.title, isDesktop && { fontSize: 36 }]}>App Directory</Text>
            <Text style={st.subtitle}>i'M On Social</Text>
          </View>

          {/* Search */}
          <View style={st.searchWrap}>
            <View style={st.searchBar}>
              <Ionicons name="search" size={18} color="#8E8E93" />
              <TextInput
                style={st.searchInput}
                placeholder="Search pages, features, audience..."
                placeholderTextColor="#6E6E73"
                value={searchQuery}
                onChangeText={setSearchQuery}
                data-testid="directory-search"
              />
              {searchQuery.length > 0 && (
                <TouchableOpacity onPress={() => setSearchQuery('')}>
                  <Ionicons name="close-circle" size={18} color="#6E6E73" />
                </TouchableOpacity>
              )}
            </View>
          </View>

          {/* Categories */}
          {filteredCatalog.map(cat => {
            const isExpanded = expandedCategories.has(cat.id);
            return (
              <View key={cat.id} style={st.catWrapper} data-testid={`category-${cat.id}`}>
                <TouchableOpacity style={st.catHeader} onPress={() => toggleCategory(cat.id)} activeOpacity={0.7}>
                  <View style={[st.catIcon, { backgroundColor: `${cat.color}20` }]}>
                    <Ionicons name={cat.icon as any} size={20} color={cat.color} />
                  </View>
                  <Text style={st.catTitle}>{cat.title}</Text>
                  <View style={[st.catBadge, { backgroundColor: `${cat.color}20` }]}>
                    <Text style={[st.catBadgeText, { color: cat.color }]}>{cat.pages.length}</Text>
                  </View>
                  <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={20} color="#8E8E93" />
                </TouchableOpacity>

                {isExpanded && (
                  <View style={isDesktop ? st.pageGridDesktop : undefined}>
                    {cat.pages.map((page) => (
                      <View key={page.path} style={[st.pageCard, isDesktop && st.pageCardDesktop]}>
                        <View style={st.pageTop}>
                          <View style={[st.pageIcon, { backgroundColor: `${page.color}18` }]}>
                            <Ionicons name={page.icon as any} size={18} color={page.color} />
                          </View>
                          <View style={st.pageInfo}>
                            <Text style={st.pageName}>{page.name}</Text>
                            <Text style={st.pageDesc}>{page.description}</Text>
                          </View>
                        </View>
                        <Text style={st.pageUrl} numberOfLines={1}>{getFullUrl(page.path)}</Text>
                        <Text style={st.pageAudience}>{page.audience}</Text>
                        <View style={st.pageActions}>
                          <TouchableOpacity style={st.actionBtn} onPress={() => handlePreview(page)}>
                            <Ionicons name="eye-outline" size={14} color="#007AFF" />
                            <Text style={[st.actionText, { color: '#007AFF' }]}>Preview</Text>
                          </TouchableOpacity>
                          <TouchableOpacity style={st.actionBtn} onPress={() => handleCopyLink(page)}>
                            <Ionicons name={copiedPath === page.path ? 'checkmark' : 'copy-outline'} size={14} color={copiedPath === page.path ? '#34C759' : '#FF9500'} />
                            <Text style={[st.actionText, { color: copiedPath === page.path ? '#34C759' : '#FF9500' }]}>
                              {copiedPath === page.path ? 'Copied!' : 'Copy'}
                            </Text>
                          </TouchableOpacity>
                          <TouchableOpacity style={[st.actionBtn, st.shareBtn]} onPress={() => setShareModal(page)}>
                            <Ionicons name="share-outline" size={14} color="#007AFF" />
                            <Text style={[st.actionText, { color: '#007AFF' }]}>Share</Text>
                          </TouchableOpacity>
                        </View>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            );
          })}

          {filteredCatalog.length === 0 && (
            <View style={st.emptyState}>
              <Ionicons name="search-outline" size={48} color="#3A3A3C" />
              <Text style={st.emptyText}>No pages found</Text>
              <Text style={st.emptySubtext}>Try a different search term</Text>
            </View>
          )}

        </View>
        <ImosFooter />
      </ScrollView>

      {/* Share Modal */}
      <WebModal visible={!!shareModal} animationType="slide" presentationStyle="pageSheet" onRequestClose={closeShareModal}>
        <View style={st.modalContainer}>
          <View style={st.modalHeader}>
            <TouchableOpacity onPress={closeShareModal}><Text style={st.modalCancel}>Cancel</Text></TouchableOpacity>
            <Text style={st.modalTitle}>Share Page</Text>
            <TouchableOpacity onPress={handleShare} disabled={sending}>
              {sending ? <ActivityIndicator size="small" color="#007AFF" /> : <Text style={st.modalSend}>Send</Text>}
            </TouchableOpacity>
          </View>
          <ScrollView style={st.modalBody}>
            {shareModal && (
              <View style={st.sharePageInfo}>
                <View style={[st.sharePageIcon, { backgroundColor: `${shareModal.color}18` }]}>
                  <Ionicons name={shareModal.icon as any} size={22} color={shareModal.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={st.sharePageName}>{shareModal.name}</Text>
                  <Text style={st.sharePagePath}>{getFullUrl(shareModal.path)}</Text>
                </View>
              </View>
            )}

            <Text style={st.inputLabel}>Send via</Text>
            <View style={st.channelToggle}>
              <TouchableOpacity style={[st.channelBtn, shareChannel === 'email' && st.channelBtnActive]} onPress={() => setShareChannel('email')}>
                <Ionicons name="mail-outline" size={18} color={shareChannel === 'email' ? '#007AFF' : '#8E8E93'} />
                <Text style={[st.channelText, shareChannel === 'email' && st.channelTextActive]}>Email</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[st.channelBtn, shareChannel === 'sms' && st.channelBtnActive]} onPress={() => setShareChannel('sms')}>
                <Ionicons name="chatbubble-outline" size={18} color={shareChannel === 'sms' ? '#007AFF' : '#8E8E93'} />
                <Text style={[st.channelText, shareChannel === 'sms' && st.channelTextActive]}>SMS</Text>
              </TouchableOpacity>
            </View>

            <Text style={st.inputLabel}>Recipient Name (optional)</Text>
            <TextInput style={st.modalInput} placeholder="John Smith" placeholderTextColor="#6E6E73" value={recipientName} onChangeText={setRecipientName} />

            {shareChannel === 'email' ? (
              <>
                <Text style={st.inputLabel}>Email Address *</Text>
                <TextInput style={st.modalInput} placeholder="john@example.com" placeholderTextColor="#6E6E73" value={recipientEmail} onChangeText={setRecipientEmail} keyboardType="email-address" autoCapitalize="none" />
              </>
            ) : (
              <>
                <Text style={st.inputLabel}>Phone Number *</Text>
                <TextInput style={st.modalInput} placeholder="+1 555 123 4567" placeholderTextColor="#6E6E73" value={recipientPhone} onChangeText={setRecipientPhone} keyboardType="phone-pad" />
              </>
            )}

            <Text style={st.inputLabel}>Custom Message (optional)</Text>
            <TextInput style={[st.modalInput, { height: 80, textAlignVertical: 'top', paddingTop: 12 }]} placeholder="i'M On Social" placeholderTextColor="#6E6E73" value={customMessage} onChangeText={setCustomMessage} multiline />
          </ScrollView>
        </View>
      </WebModal>
    </View>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingBottom: 0 },
  titleSection: { alignItems: 'center', paddingTop: 40, paddingBottom: 16, paddingHorizontal: 20 },
  label: { fontSize: 11, fontWeight: '700', color: '#007AFF', letterSpacing: 2, marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', marginBottom: 8, textAlign: 'center' },
  subtitle: { fontSize: 15, color: '#8E8E93', textAlign: 'center' },
  searchWrap: { paddingHorizontal: 16, paddingBottom: 16 },
  searchBar: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F7', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, gap: 8 },
  searchInput: { flex: 1, fontSize: 15, color: '#1D1D1F' },
  catWrapper: { marginHorizontal: 16, marginBottom: 8 },
  catHeader: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F7', borderRadius: 12, padding: 14, marginBottom: 8 },
  catIcon: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  catTitle: { fontSize: 16, fontWeight: '600', color: '#1D1D1F', flex: 1 },
  catBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, marginRight: 8 },
  catBadgeText: { fontSize: 14, fontWeight: '600' },
  pageGridDesktop: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pageCard: { backgroundColor: '#F5F5F7', borderRadius: 12, padding: 14, marginLeft: 16, marginBottom: 8, borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)' },
  pageCardDesktop: { width: '47%', marginLeft: 0 },
  pageTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  pageIcon: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 10 },
  pageInfo: { flex: 1 },
  pageName: { fontSize: 15, fontWeight: '600', color: '#1D1D1F' },
  pageDesc: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  pageUrl: { fontSize: 10, color: '#4A4A4C', fontFamily: Platform.OS === 'web' ? 'monospace' : undefined, marginBottom: 2 },
  pageAudience: { fontSize: 11, color: '#5856D6', marginBottom: 8 },
  pageActions: { flexDirection: 'row', gap: 6 },
  actionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, backgroundColor: 'rgba(0,0,0,0.04)', paddingVertical: 8, borderRadius: 8 },
  shareBtn: { backgroundColor: '#007AFF15' },
  actionText: { fontSize: 12, fontWeight: '500', color: '#1D1D1F' },
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { color: '#8E8E93', fontSize: 16, marginTop: 12 },
  emptySubtext: { color: '#6E6E73', fontSize: 13, marginTop: 4 },
  modalContainer: { flex: 1, backgroundColor: '#FFFFFF' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.06)' },
  modalCancel: { fontSize: 16, color: '#007AFF' },
  modalTitle: { fontSize: 17, fontWeight: '600', color: '#1D1D1F' },
  modalSend: { fontSize: 16, fontWeight: '600', color: '#007AFF' },
  modalBody: { padding: 16 },
  sharePageInfo: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F7', borderRadius: 12, padding: 14, marginBottom: 20, gap: 12 },
  sharePageIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  sharePageName: { fontSize: 16, fontWeight: '600', color: '#1D1D1F' },
  sharePagePath: { fontSize: 12, color: '#6E6E73', marginTop: 4 },
  inputLabel: { fontSize: 13, fontWeight: '600', color: '#8E8E93', marginBottom: 8, marginTop: 16, marginLeft: 4 },
  modalInput: { backgroundColor: '#F5F5F7', borderRadius: 10, padding: 14, fontSize: 15, color: '#1D1D1F', borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)' },
  channelToggle: { flexDirection: 'row', gap: 10 },
  channelBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 14, borderRadius: 12, backgroundColor: '#F5F5F7', borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)' },
  channelBtnActive: { backgroundColor: '#007AFF15', borderColor: '#007AFF' },
  channelText: { fontSize: 15, fontWeight: '500', color: '#8E8E93' },
  channelTextActive: { color: '#007AFF' },
});
