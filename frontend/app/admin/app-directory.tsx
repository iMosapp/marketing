import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  TextInput,
  Platform,
  Linking,
  LayoutAnimation,
  UIManager,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { WebModal } from '../../components/WebModal';

import { useThemeStore } from '../../store/themeStore';
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const APP_URL = 'https://app.imonsocial.com';

type PageEntry = {
  name: string;
  description: string;
  path: string;
  icon: string;
  color: string;
  requiresAuth: boolean;
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
    color: '#FF6B8A',
    pages: [
      { name: 'Digital Business Card', description: 'Shareable card with photo, QR, reviews, social links', path: '/imos/digital-card', icon: 'card-outline', color: '#5856D6', requiresAuth: false, audience: 'Customers, public' },
      { name: 'Congrats Card', description: 'Branded congratulations card for customers', path: '/imos/congrats-template', icon: 'gift-outline', color: '#C9A962', requiresAuth: false, audience: 'Customers, public' },
      { name: 'Birthday Card', description: 'Personalized birthday card with photo & message', path: '/imos/birthday-card', icon: 'gift-outline', color: '#FF6B8A', requiresAuth: false, audience: 'Customers, public' },
      { name: 'Review Page', description: 'Store review landing page with Google, Yelp, Facebook links', path: '/imos/reviews', icon: 'star-outline', color: '#FFD60A', requiresAuth: false, audience: 'Customers, public' },
      { name: 'Showcase', description: 'User showcase page  - congrats cards, featured work', path: '/imos/showcase', icon: 'images-outline', color: '#007AFF', requiresAuth: false, audience: 'Customers, public' },
      { name: 'Join / Invite Page', description: 'Team invite link landing page', path: '/imos/join', icon: 'person-add-outline', color: '#34C759', requiresAuth: false, audience: 'New team members' },
      { name: 'Partner Agreement', description: 'Public partner agreement signing page', path: '/imos/partner-agreements', icon: 'document-text-outline', color: '#FF9500', requiresAuth: false, audience: 'Partners' },
      { name: 'NDA Signing', description: 'Public NDA signing page', path: '/imos/nda', icon: 'lock-closed-outline', color: '#FF3B30', requiresAuth: false, audience: 'Partners, employees' },
    ],
  },
  {
    id: 'quick_wins',
    title: 'Quick Win Tools',
    icon: 'flash-outline',
    color: '#34C759',
    pages: [
      { name: 'Create Congrats Card', description: 'Upload photo, preview, and share a congrats card', path: '/imos/congrats-template', icon: 'gift-outline', color: '#C9A962', requiresAuth: false, audience: 'All users' },
      { name: 'Create Birthday Card', description: 'Upload photo, preview, and share a birthday card', path: '/imos/birthday-card', icon: 'gift-outline', color: '#FF6B8A', requiresAuth: false, audience: 'All users' },
      { name: 'Manage Showcase', description: 'Edit what shows on your showcase page', path: '/imos/showcase-manage', icon: 'images-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
      { name: 'Import Contacts (CSV)', description: 'Bulk import contacts from spreadsheet', path: '/imos/import', icon: 'cloud-upload-outline', color: '#34C759', requiresAuth: false, audience: 'All users' },
      { name: 'Store Profile / Digital Card Setup', description: 'Set up your digital business card & store branding', path: '/imos/store-profile', icon: 'card-outline', color: '#5856D6', requiresAuth: false, audience: 'All users' },
      { name: 'Review Links Setup', description: 'Configure Google, Yelp, Facebook review URLs', path: '/imos/review-links', icon: 'star-outline', color: '#FFD60A', requiresAuth: false, audience: 'All users' },
      { name: 'Date Trigger Campaigns', description: 'Auto birthday, anniversary, holiday messages', path: '/imos/date-triggers', icon: 'calendar-outline', color: '#AF52DE', requiresAuth: false, audience: 'All users' },
      { name: 'Help Center', description: 'How-to articles for key features', path: '/imos/help', icon: 'help-circle-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
    ],
  },
  {
    id: 'analytics_reports',
    title: 'Analytics & Reporting',
    icon: 'stats-chart-outline',
    color: '#007AFF',
    pages: [
      { name: 'Leaderboard', description: 'Real-time team rankings by category', path: '/imos/leaderboard', icon: 'trophy-outline', color: '#FFD60A', requiresAuth: false, audience: 'All users' },
      { name: 'Activity Reports', description: '14+ metrics with date filters & email delivery', path: '/imos/reports', icon: 'bar-chart-outline', color: '#007AFF', requiresAuth: false, audience: 'Managers, Admins' },
      { name: 'Personal Reports', description: 'Your individual performance stats', path: '/imos/reports-personal', icon: 'person-outline', color: '#34C759', requiresAuth: false, audience: 'All users' },
      { name: 'Team Reports', description: 'Team-wide performance breakdown', path: '/imos/reports-team', icon: 'people-outline', color: '#FF9500', requiresAuth: false, audience: 'Managers, Admins' },
      { name: 'Campaign Reports', description: 'Campaign enrollment & delivery stats', path: '/imos/reports-campaigns', icon: 'megaphone-outline', color: '#AF52DE', requiresAuth: false, audience: 'All users' },
      { name: 'Messaging Reports', description: 'SMS & email analytics', path: '/imos/reports-messaging', icon: 'chatbubble-outline', color: '#5856D6', requiresAuth: false, audience: 'All users' },
      { name: 'My Rankings', description: 'Your personal leaderboard position & stats', path: '/imos/my-rankings', icon: 'ribbon-outline', color: '#C9A962', requiresAuth: false, audience: 'All users' },
      { name: 'Lead Attribution', description: 'Track demo requests, sources, UTM campaigns & referrals', path: '/admin/lead-tracking', icon: 'analytics-outline', color: '#C9A962', requiresAuth: true, audience: 'Admins' },
    ],
  },
  {
    id: 'marketing',
    title: 'Marketing & Sales',
    icon: 'diamond-outline',
    color: '#C9A962',
    pages: [
      { name: 'Marketing Landing Page', description: 'Full landing page with voiceover & demo slideshow', path: '/landing.html', icon: 'videocam-outline', color: '#FF2D55', requiresAuth: false, audience: 'Prospects, customers' },
      { name: 'Ad: Digital Business Card', description: 'Sponsored ad  - share trackable digital cards', path: '/ad-digital-card.html', icon: 'card-outline', color: '#007AFF', requiresAuth: false, audience: 'FB/IG Ad' },
      { name: 'Ad: Customer Showcase', description: 'Sponsored ad  - showcase happy customers & reviews', path: '/ad-showcase.html', icon: 'images-outline', color: '#34C759', requiresAuth: false, audience: 'FB/IG Ad' },
      { name: 'Ad: Review Link Machine', description: 'Sponsored ad  - one-tap Google & Facebook review requests', path: '/ad-reviews.html', icon: 'star-outline', color: '#FFD60A', requiresAuth: false, audience: 'FB/IG Ad' },
      { name: 'Ad: Stay Connected', description: 'Sponsored ad  - automated follow-ups & AI messaging', path: '/ad-autopilot.html', icon: 'rocket-outline', color: '#AF52DE', requiresAuth: false, audience: 'FB/IG Ad' },
      { name: "i'M On Social Home", description: 'Main marketing page', path: '/imos', icon: 'home-outline', color: '#C9A962', requiresAuth: false, audience: 'Everyone' },
      { name: 'Schedule a Demo', description: 'Lead capture form', path: '/imos/demo', icon: 'calendar-outline', color: '#34C759', requiresAuth: false, audience: 'Prospects' },
      { name: "Why Use i'M On Social", description: 'Interactive slide deck', path: '/imos/salespresentation', icon: 'easel-outline', color: '#C9A962', requiresAuth: false, audience: 'Prospects, investors' },
      { name: 'Features Overview', description: 'Full feature showcase', path: '/imos/features', icon: 'apps-outline', color: '#007AFF', requiresAuth: false, audience: 'Prospects, customers' },
      { name: 'Pricing Plans', description: 'Subscription tiers', path: '/imos/pricing', icon: 'pricetag-outline', color: '#34C759', requiresAuth: false, audience: 'Prospects, customers' },
      { name: 'Solutions Hub', description: 'Browse solutions', path: '/imos/hub', icon: 'grid-outline', color: '#5856D6', requiresAuth: false, audience: 'Everyone' },
    ],
  },
  {
    id: 'onboarding',
    title: 'Onboarding & Training',
    icon: 'rocket-outline',
    color: '#FF9500',
    pages: [
      { name: 'Onboarding Preview', description: 'Preview all role onboarding flows', path: '/imos/onboarding-preview', icon: 'eye-outline', color: '#C9A962', requiresAuth: false, audience: 'Admins, prospects' },
      { name: 'Training Hub', description: "Learn how to use i'M On Social", path: '/imos/training', icon: 'school-outline', color: '#FF9500', requiresAuth: false, audience: 'All users' },
    ],
  },
  {
    id: 'core',
    title: 'Core App',
    icon: 'apps-outline',
    color: '#007AFF',
    pages: [
      { name: 'Inbox', description: 'Message conversations & threads', path: '/imos/inbox', icon: 'chatbubble-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
      { name: 'Contacts', description: 'Contact management & CRM', path: '/imos/contacts', icon: 'people-outline', color: '#5856D6', requiresAuth: false, audience: 'All users' },
      { name: 'Contact Detail', description: 'Full contact view with photo gallery, relationship intel, events', path: '/imos/contact-detail', icon: 'person-outline', color: '#FF9500', requiresAuth: false, audience: 'All users' },
      { name: 'Dialer', description: 'Phone dialer & call log', path: '/imos/dialer', icon: 'keypad-outline', color: '#34C759', requiresAuth: false, audience: 'All users' },
      { name: 'Team Chat', description: 'Team collaboration', path: '/imos/team', icon: 'chatbubbles-outline', color: '#FF9500', requiresAuth: false, audience: 'All users' },
      { name: 'More / Settings', description: 'Navigation hub with quick actions', path: '/imos/more', icon: 'menu-outline', color: '#8E8E93', requiresAuth: false, audience: 'All users' },
      { name: 'Ask Jessi AI', description: 'AI assistant  - voice & text', path: '/imos/jessi', icon: 'sparkles-outline', color: '#C9A962', requiresAuth: false, audience: 'All users' },
      { name: 'Notifications', description: 'Lead alerts, system notifications', path: '/imos/notifications', icon: 'notifications-outline', color: '#FF3B30', requiresAuth: false, audience: 'All users' },
      { name: 'Search', description: 'Global search across contacts & messages', path: '/imos/search', icon: 'search-outline', color: '#8E8E93', requiresAuth: false, audience: 'All users' },
      { name: 'Tasks', description: 'To-do list and task management', path: '/imos/tasks', icon: 'checkbox-outline', color: '#34C759', requiresAuth: false, audience: 'All users' },
      { name: 'Training Hub', description: 'Video tutorials & guides', path: '/imos/training', icon: 'school-outline', color: '#AF52DE', requiresAuth: false, audience: 'All users' },
      { name: 'Voice Training', description: 'Train your AI voice persona', path: '/imos/voice-training', icon: 'mic-outline', color: '#FF2D55', requiresAuth: false, audience: 'All users' },
    ],
  },
  {
    id: 'communication',
    title: 'Communication Tools',
    icon: 'megaphone-outline',
    color: '#FF2D55',
    pages: [
      { name: 'Broadcast', description: 'Mass messaging to team', path: '/imos/broadcast', icon: 'megaphone-outline', color: '#FF9500', requiresAuth: false, audience: 'All users' },
      { name: 'SMS Campaigns', description: 'Automated SMS follow-ups', path: '/imos/campaigns', icon: 'chatbubbles-outline', color: '#FF2D55', requiresAuth: false, audience: 'All users' },
      { name: 'Email Campaigns', description: 'Automated email follow-ups', path: '/imos/campaigns/email', icon: 'mail-outline', color: '#AF52DE', requiresAuth: false, audience: 'All users' },
      { name: 'Campaign Dashboard', description: 'Campaign analytics & enrollments', path: '/imos/campaigns/dashboard', icon: 'speedometer-outline', color: '#5AC8FA', requiresAuth: false, audience: 'All users' },
      { name: 'Date Triggers', description: 'Birthday, anniversary, holiday campaigns', path: '/imos/date-triggers', icon: 'calendar-outline', color: '#FF9500', requiresAuth: false, audience: 'All users' },
    ],
  },
  {
    id: 'templates',
    title: 'Templates & Branding',
    icon: 'color-palette-outline',
    color: '#AF52DE',
    pages: [
      { name: 'SMS Templates', description: 'Pre-built SMS messages', path: '/imos/templates', icon: 'document-text-outline', color: '#FFD60A', requiresAuth: false, audience: 'All users' },
      { name: 'Email Templates', description: 'Pre-built email designs', path: '/imos/email-templates', icon: 'mail-outline', color: '#34C759', requiresAuth: false, audience: 'All users' },
      { name: 'Brand Kit', description: 'Email branding & colors', path: '/imos/brand-kit', icon: 'color-palette-outline', color: '#AF52DE', requiresAuth: false, audience: 'All users' },
      { name: 'Congrats Card Templates', description: 'Thank you card templates', path: '/imos/congrats-template', icon: 'gift-outline', color: '#C9A962', requiresAuth: false, audience: 'All users' },
      { name: 'Birthday Card Templates', description: 'Birthday card design & defaults', path: '/imos/birthday-card', icon: 'gift-outline', color: '#FF6B8A', requiresAuth: false, audience: 'All users' },
    ],
  },
  {
    id: 'analytics',
    title: 'Performance & Analytics',
    icon: 'stats-chart-outline',
    color: '#34C759',
    pages: [
      { name: 'Analytics Overview', description: 'Performance metrics dashboard', path: '/imos/analytics', icon: 'stats-chart-outline', color: '#34C759', requiresAuth: false, audience: 'All users' },
      { name: 'Reports Hub', description: 'Detailed performance reports', path: '/imos/reports', icon: 'bar-chart-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
      { name: 'Email Analytics', description: 'Opens, clicks, engagement', path: '/imos/email-analytics', icon: 'trending-up-outline', color: '#FF2D55', requiresAuth: false, audience: 'All users' },
      { name: 'Leaderboard', description: 'Team performance rankings', path: '/imos/leaderboard', icon: 'trophy-outline', color: '#FFD60A', requiresAuth: false, audience: 'Team members' },
    ],
  },
  {
    id: 'contacts_leads',
    title: 'Contacts & Leads',
    icon: 'people-outline',
    color: '#5856D6',
    pages: [
      { name: 'Lead Sources', description: 'Inbound lead routing config', path: '/imos/lead-sources', icon: 'git-branch-outline', color: '#5856D6', requiresAuth: false, audience: 'Admins' },
      { name: 'Contact Tags', description: 'Tag management', path: '/imos/tags', icon: 'pricetags-outline', color: '#FF9500', requiresAuth: false, audience: 'All users' },
      { name: 'Review Links', description: 'Google, Facebook, Yelp links', path: '/imos/review-links', icon: 'star-outline', color: '#FFD60A', requiresAuth: false, audience: 'All users' },
      { name: 'Import Contacts', description: 'Bulk import from CSV', path: '/imos/import', icon: 'cloud-upload-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
      { name: 'Lead Attribution', description: 'Demo requests, sources, UTM campaigns & referral tracking', path: '/admin/lead-tracking', icon: 'analytics-outline', color: '#C9A962', requiresAuth: true, audience: 'Admins' },
    ],
  },
  {
    id: 'profile_ai',
    title: 'Profile & AI',
    icon: 'person-outline',
    color: '#FF9500',
    pages: [
      { name: 'Digital Card', description: 'Bio, socials & shareable card', path: '/imos/digital-card', icon: 'card-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
      { name: 'AI Persona', description: 'Communication style settings', path: '/imos/persona', icon: 'sparkles-outline', color: '#AF52DE', requiresAuth: false, audience: 'All users' },
      { name: 'Ask Jessi', description: 'AI assistant', path: '/imos/jessi', icon: 'sparkles-outline', color: '#C9A962', requiresAuth: false, audience: 'All users' },
      { name: 'My Account', description: 'Account settings & profile', path: '/imos/account', icon: 'person-circle-outline', color: '#8E8E93', requiresAuth: false, audience: 'All users' },
    ],
  },
  {
    id: 'settings',
    title: 'Settings',
    icon: 'settings-outline',
    color: '#8E8E93',
    pages: [
      { name: 'Security', description: 'Passwords & authentication', path: '/imos/security', icon: 'shield-checkmark-outline', color: '#FF3B30', requiresAuth: false, audience: 'All users' },
      { name: 'Calendar', description: 'Connect external calendars', path: '/imos/calendar', icon: 'calendar-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
      { name: 'Integrations', description: 'API keys & webhooks', path: '/imos/integrations', icon: 'git-network-outline', color: '#5856D6', requiresAuth: false, audience: 'All users' },
      { name: 'Invite Team', description: 'Send team invitations', path: '/imos/invite-team', icon: 'person-add-outline', color: '#C9A962', requiresAuth: false, audience: 'Admins' },
    ],
  },
  {
    id: 'admin',
    title: 'Administration',
    icon: 'shield-checkmark-outline',
    color: '#FF3B30',
    pages: [
      { name: 'Admin Dashboard', description: 'Overview & activity feed', path: '/imos/admin', icon: 'shield-checkmark-outline', color: '#34C759', requiresAuth: false, audience: 'Admins' },
      { name: 'Users', description: 'Manage team members', path: '/imos/users', icon: 'people-outline', color: '#FF9500', requiresAuth: false, audience: 'Admins' },
      { name: 'Organizations', description: 'Manage organizations', path: '/imos/organizations', icon: 'business-outline', color: '#007AFF', requiresAuth: false, audience: 'Super Admin' },
      { name: 'Stores', description: 'Manage store accounts', path: '/imos/stores', icon: 'storefront-outline', color: '#34C759', requiresAuth: false, audience: 'Admins' },
      { name: 'Pending Users', description: 'Approve new signups', path: '/imos/pending-users', icon: 'person-add-outline', color: '#FF3B30', requiresAuth: false, audience: 'Super Admin' },
      { name: 'Individuals', description: 'Independent users', path: '/imos/individuals', icon: 'person-outline', color: '#AF52DE', requiresAuth: false, audience: 'Super Admin' },
      { name: 'Company Directory', description: 'Team roster & leaderboards', path: '/imos/directory', icon: 'people-outline', color: '#AF52DE', requiresAuth: false, audience: 'Admins' },
      { name: 'Shared Inboxes', description: 'Phone number assignments', path: '/imos/shared-inboxes', icon: 'mail-outline', color: '#007AFF', requiresAuth: false, audience: 'Super Admin' },
      { name: 'Bulk Transfer', description: 'Transfer contacts between users', path: '/imos/bulk-transfer', icon: 'swap-horizontal-outline', color: '#FF3B30', requiresAuth: false, audience: 'Super Admin' },
      { name: 'Phone Assignments', description: 'Twilio number management', path: '/imos/phone-assignments', icon: 'call-outline', color: '#32ADE6', requiresAuth: false, audience: 'Super Admin' },
      { name: 'Partner Agreements', description: 'Reseller contracts', path: '/imos/partner-agreements', icon: 'document-text-outline', color: '#FF9500', requiresAuth: false, audience: 'Super Admin' },
      { name: 'Billing', description: 'Subscription & billing info', path: '/imos/billing', icon: 'card-outline', color: '#34C759', requiresAuth: false, audience: 'Admins' },
      { name: 'Activity Feed', description: 'Recent admin activity', path: '/imos/activity-feed', icon: 'pulse-outline', color: '#FF2D55', requiresAuth: false, audience: 'Admins' },
      { name: 'App Directory', description: 'Complete page index', path: '/imos/app-directory', icon: 'albums-outline', color: '#8E8E93', requiresAuth: false, audience: 'Internal / Unlisted' },
    ],
  },
  {
    id: 'legal',
    title: 'Legal & Auth',
    icon: 'shield-outline',
    color: '#8E8E93',
    pages: [
      { name: 'Privacy Policy', description: 'How we protect your data', path: '/imos/privacy', icon: 'shield-outline', color: '#5856D6', requiresAuth: false, audience: 'Everyone' },
      { name: 'Terms of Service', description: 'Usage terms and conditions', path: '/imos/terms', icon: 'document-text-outline', color: '#8E8E93', requiresAuth: false, audience: 'Everyone' },
      { name: 'Login', description: "Sign in to i'M On Social", path: '/imos/login', icon: 'log-in-outline', color: '#007AFF', requiresAuth: false, audience: 'All users' },
      { name: 'Sign Up', description: 'Create a new account', path: '/imos/signup', icon: 'person-add-outline', color: '#34C759', requiresAuth: false, audience: 'New users' },
    ],
  },
];

export default function AppDirectoryScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
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
      pages: cat.pages.filter(
        p =>
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

  const handleCopyLink = async (page: PageEntry) => {
    const url = `${APP_URL}${page.path}`;
    await Clipboard.setStringAsync(url);
    setCopiedPath(page.path);
    setTimeout(() => setCopiedPath(null), 2000);
    try { await api.post('/admin/app-directory/share/copy-link', { page_name: page.name, page_path: page.path }); } catch {}
  };

  const handlePreview = (page: PageEntry) => {
    // Static files (like .html) need to open via browser, not the React router
    if (page.path.endsWith('.html')) {
      const origin = process.env.EXPO_PUBLIC_APP_URL || APP_URL;
      const url = `${origin}${page.path}`;
      if (Platform.OS === 'web') {
        window.open(url, '_blank');
      } else {
        Linking.openURL(url);
      }
      return;
    }
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
        recipient_name: recipientName.trim() || undefined,
        recipient_email: shareChannel === 'email' ? recipientEmail.trim() : undefined,
        recipient_phone: shareChannel === 'sms' ? recipientPhone.trim() : undefined,
        channel: shareChannel,
        custom_message: customMessage.trim() || undefined,
      });
      if (res.data.success) {
        const mockNote = res.data.mock ? ' (mock mode)' : '';
        Alert.alert('Sent!', `${shareChannel === 'email' ? 'Email' : 'SMS'} sent successfully${mockNote}`);
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
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="back-button">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.title}>App Directory</Text>
          <Text style={styles.subtitle}>{totalPages} pages</Text>
        </View>
        <View style={{ width: 36 }} />
      </View>

      {/* Search */}
      <View style={styles.searchWrap}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={18} color={colors.textSecondary} />
          <TextInput
            style={styles.searchInput}
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

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {filteredCatalog.map(cat => {
          const isExpanded = expandedCategories.has(cat.id);
          return (
            <View key={cat.id} style={styles.catWrapper} data-testid={`category-${cat.id}`}>
              {/* Category Header */}
              <TouchableOpacity
                style={styles.catHeader}
                onPress={() => toggleCategory(cat.id)}
                activeOpacity={0.7}
                data-testid={`category-header-${cat.id}`}
              >
                <View style={[styles.catIcon, { backgroundColor: `${cat.color}20` }]}>
                  <Ionicons name={cat.icon as any} size={20} color={cat.color} />
                </View>
                <Text style={styles.catTitle}>{cat.title}</Text>
                <View style={[styles.catBadge, { backgroundColor: `${cat.color}20` }]}>
                  <Text style={[styles.catBadgeText, { color: cat.color }]}>{cat.pages.length}</Text>
                </View>
                <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={20} color={colors.textSecondary} />
              </TouchableOpacity>

              {/* Page Cards */}
              {isExpanded && cat.pages.map((page, idx) => (
                <View key={page.path} style={styles.pageCard} data-testid={`page-${page.name.toLowerCase().replace(/\s+/g, '-')}`}>
                  <View style={styles.pageTop}>
                    <View style={[styles.pageIcon, { backgroundColor: `${page.color}18` }]}>
                      <Ionicons name={page.icon as any} size={18} color={page.color} />
                    </View>
                    <View style={styles.pageInfo}>
                      <Text style={styles.pageName}>{page.name}</Text>
                      <Text style={styles.pageDesc}>{page.description}</Text>
                    </View>
                    {!page.requiresAuth && (
                      <View style={styles.publicBadge}>
                        <Text style={styles.publicBadgeText}>Public</Text>
                      </View>
                    )}
                  </View>
                  <View style={styles.pageMeta}>
                    <Text style={styles.pagePath} numberOfLines={1}>{page.path}</Text>
                    <Text style={styles.pageAudience}>{page.audience}</Text>
                  </View>
                  {/* Action Buttons */}
                  <View style={styles.pageActions}>
                    <TouchableOpacity
                      style={styles.actionBtn}
                      onPress={() => handlePreview(page)}
                      data-testid={`preview-${page.name.toLowerCase().replace(/\s+/g, '-')}`}
                    >
                      <Ionicons name="eye-outline" size={16} color="#007AFF" />
                      <Text style={styles.actionText}>Preview</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.actionBtn}
                      onPress={() => handleCopyLink(page)}
                      data-testid={`copy-${page.name.toLowerCase().replace(/\s+/g, '-')}`}
                    >
                      <Ionicons
                        name={copiedPath === page.path ? 'checkmark-outline' : 'copy-outline'}
                        size={16}
                        color={copiedPath === page.path ? '#34C759' : '#FF9500'}
                      />
                      <Text style={[styles.actionText, copiedPath === page.path && { color: '#34C759' }]}>
                        {copiedPath === page.path ? 'Copied' : 'Copy Link'}
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.actionBtn, styles.shareBtn]}
                      onPress={() => setShareModal(page)}
                      data-testid={`share-${page.name.toLowerCase().replace(/\s+/g, '-')}`}
                    >
                      <Ionicons name="share-outline" size={16} color="#C9A962" />
                      <Text style={[styles.actionText, { color: '#C9A962' }]}>Share</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </View>
          );
        })}

        {filteredCatalog.length === 0 && (
          <View style={styles.emptyState}>
            <Ionicons name="search-outline" size={48} color={colors.borderLight} />
            <Text style={styles.emptyText}>No pages found</Text>
            <Text style={styles.emptySubtext}>Try a different search term</Text>
          </View>
        )}
      </ScrollView>

      {/* Share Modal */}
      <WebModal visible={!!shareModal} animationType="slide" presentationStyle="pageSheet" onRequestClose={closeShareModal}>
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={closeShareModal}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Share Page</Text>
            <TouchableOpacity onPress={handleShare} disabled={sending}>
              {sending ? (
                <ActivityIndicator size="small" color="#C9A962" />
              ) : (
                <Text style={styles.modalSend}>Send</Text>
              )}
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalBody}>
            {/* Page Info */}
            {shareModal && (
              <View style={styles.sharePageInfo}>
                <View style={[styles.sharePageIcon, { backgroundColor: `${shareModal.color}18` }]}>
                  <Ionicons name={shareModal.icon as any} size={22} color={shareModal.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.sharePageName}>{shareModal.name}</Text>
                  <Text style={styles.sharePagePath}>{APP_URL}{shareModal.path}</Text>
                </View>
              </View>
            )}

            {/* Channel Toggle */}
            <Text style={styles.inputLabel}>Send via</Text>
            <View style={styles.channelToggle}>
              <TouchableOpacity
                style={[styles.channelBtn, shareChannel === 'email' && styles.channelBtnActive]}
                onPress={() => setShareChannel('email')}
                data-testid="channel-email"
              >
                <Ionicons name="mail-outline" size={18} color={shareChannel === 'email' ? '#C9A962' : colors.textSecondary} />
                <Text style={[styles.channelText, shareChannel === 'email' && styles.channelTextActive]}>Email</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.channelBtn, shareChannel === 'sms' && styles.channelBtnActive]}
                onPress={() => setShareChannel('sms')}
                data-testid="channel-sms"
              >
                <Ionicons name="chatbubble-outline" size={18} color={shareChannel === 'sms' ? '#C9A962' : colors.textSecondary} />
                <Text style={[styles.channelText, shareChannel === 'sms' && styles.channelTextActive]}>SMS</Text>
              </TouchableOpacity>
            </View>

            {/* Recipient Fields */}
            <Text style={styles.inputLabel}>Recipient Name (optional)</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="John Smith"
              placeholderTextColor="#6E6E73"
              value={recipientName}
              onChangeText={setRecipientName}
              autoCapitalize="words"
              data-testid="recipient-name-input"
            />

            {shareChannel === 'email' ? (
              <>
                <Text style={styles.inputLabel}>Email Address *</Text>
                <TextInput
                  style={styles.modalInput}
                  placeholder="john@example.com"
                  placeholderTextColor="#6E6E73"
                  value={recipientEmail}
                  onChangeText={setRecipientEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  data-testid="recipient-email-input"
                />
              </>
            ) : (
              <>
                <Text style={styles.inputLabel}>Phone Number *</Text>
                <TextInput
                  style={styles.modalInput}
                  placeholder="+1 555 123 4567"
                  placeholderTextColor="#6E6E73"
                  value={recipientPhone}
                  onChangeText={setRecipientPhone}
                  keyboardType="phone-pad"
                  data-testid="recipient-phone-input"
                />
              </>
            )}

            <Text style={styles.inputLabel}>Custom Message (optional)</Text>
            <TextInput
              style={[styles.modalInput, { height: 80, textAlignVertical: 'top', paddingTop: 12 }]}
              placeholder="i'M On Social"
              placeholderTextColor="#6E6E73"
              value={customMessage}
              onChangeText={setCustomMessage}
              multiline
              data-testid="custom-message-input"
            />

            {shareModal && !shareModal.requiresAuth && (
              <View style={styles.publicNote}>
                <Ionicons name="globe-outline" size={16} color="#34C759" />
                <Text style={styles.publicNoteText}>This is a public page - no login required to view</Text>
              </View>
            )}
            {shareModal && shareModal.requiresAuth && (
              <View style={styles.authNote}>
                <Ionicons name="lock-closed-outline" size={16} color="#FF9500" />
                <Text style={styles.authNoteText}>Recipient will need to log in to view this page</Text>
              </View>
            )}
          </ScrollView>
        </SafeAreaView>
      </WebModal>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backBtn: { padding: 4 },
  headerCenter: { flex: 1, alignItems: 'center' },
  title: { fontSize: 18, fontWeight: '600', color: colors.text },
  subtitle: { fontSize: 14, color: '#6E6E73', marginTop: 2 },
  searchWrap: { paddingHorizontal: 16, paddingVertical: 10 },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  searchInput: { flex: 1, fontSize: 17, color: colors.text },
  scrollContent: { paddingBottom: 32 },
  // Category
  catWrapper: { marginHorizontal: 16, marginBottom: 8 },
  catHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  catIcon: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  catTitle: { fontSize: 18, fontWeight: '600', color: colors.text, flex: 1 },
  catBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, marginRight: 8 },
  catBadgeText: { fontSize: 16, fontWeight: '600' },
  // Page card
  pageCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    marginLeft: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  pageTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  pageIcon: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 10 },
  pageInfo: { flex: 1 },
  pageName: { fontSize: 17, fontWeight: '600', color: colors.text },
  pageDesc: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  publicBadge: {
    backgroundColor: '#34C75920',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  publicBadgeText: { fontSize: 12, fontWeight: '600', color: '#34C759' },
  pageMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
    paddingHorizontal: 2,
  },
  pagePath: { fontSize: 13, color: '#6E6E73', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', flex: 1 },
  pageAudience: { fontSize: 13, color: '#5856D6', marginLeft: 8 },
  // Actions
  pageActions: { flexDirection: 'row', gap: 8 },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    backgroundColor: colors.surface,
    paddingVertical: 8,
    borderRadius: 8,
  },
  shareBtn: { backgroundColor: '#C9A96215' },
  actionText: { fontSize: 14, fontWeight: '500', color: colors.text },
  // Empty state
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { color: colors.textSecondary, fontSize: 18, marginTop: 12 },
  emptySubtext: { color: '#6E6E73', fontSize: 15, marginTop: 4 },
  // Modal
  modalContainer: { flex: 1, backgroundColor: colors.bg },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  modalCancel: { fontSize: 18, color: '#007AFF' },
  modalTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  modalSend: { fontSize: 18, fontWeight: '600', color: '#C9A962' },
  modalBody: { padding: 16 },
  sharePageInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    gap: 12,
  },
  sharePageIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  sharePageName: { fontSize: 18, fontWeight: '600', color: colors.text },
  sharePagePath: { fontSize: 14, color: '#6E6E73', marginTop: 4 },
  inputLabel: { fontSize: 15, fontWeight: '600', color: colors.textSecondary, marginBottom: 8, marginTop: 16, marginLeft: 4 },
  modalInput: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    fontSize: 17,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  channelToggle: { flexDirection: 'row', gap: 10 },
  channelBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.surface,
  },
  channelBtnActive: { backgroundColor: '#C9A96215', borderColor: '#C9A962' },
  channelText: { fontSize: 17, fontWeight: '500', color: colors.textSecondary },
  channelTextActive: { color: '#C9A962' },
  publicNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 20,
    padding: 12,
    backgroundColor: '#34C75910',
    borderRadius: 10,
  },
  publicNoteText: { fontSize: 15, color: '#34C759', flex: 1 },
  authNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 20,
    padding: 12,
    backgroundColor: '#FF950010',
    borderRadius: 10,
  },
  authNoteText: { fontSize: 15, color: '#FF9500', flex: 1 },
});
