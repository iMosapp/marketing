import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
  Image,
  Animated,
  LayoutAnimation,
  UIManager,
  Linking,
  TextInput,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { showSimpleAlert } from '../../services/alert';
import api from '../../services/api';
import { NotificationBell } from '../../components/notifications/NotificationBell';
import { WebModal } from '../../components/WebModal';
import { BRAND } from '../../config/brand';

// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

type MenuItem = {
  icon: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  color: string;
  badge?: number;
};

type Section = {
  id: string;
  title: string;
  icon: string;
  color: string;
  items: MenuItem[];
  defaultExpanded?: boolean;
};

export default function MoreScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user, logout, isImpersonating, stopImpersonation, originalUser, partnerBranding } = useAuthStore();
  const themeMode = useThemeStore((s) => s.mode);
  const toggleTheme = useThemeStore((s) => s.toggle);
  const [pendingUsersCount, setPendingUsersCount] = useState(0);
  const [exitingImpersonation, setExitingImpersonation] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const sectionRefs = useRef<Record<string, View | null>>({});
  const scrollRef = useRef<ScrollView>(null);
  const [showShareModal, setShowShareModal] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);
  const [shareRecipientName, setShareRecipientName] = useState('');
  const [shareRecipientPhone, setShareRecipientPhone] = useState('');
  const [shareRecipientEmail, setShareRecipientEmail] = useState('');
  const [matchModalVisible, setMatchModalVisible] = useState(false);
  const [matchInfo, setMatchInfo] = useState<any>(null);
  const [pendingSharePayload, setPendingSharePayload] = useState<any>(null);
  const [showShowroomShare, setShowShowroomShare] = useState(false);
  const [showBirthdayShare, setShowBirthdayShare] = useState(false);
  const [shareMode, setShareMode] = useState<'review' | 'showroom' | 'birthday'>('review');
  
  // Load pending count for super admins
  useFocusEffect(
    useCallback(() => {
      if (user?.role === 'super_admin' || originalUser?.role === 'super_admin') {
        fetchPendingCount();
      }
      // Fetch store slug for share review link
      if (user?.store_slug) {
        setStoreSlug(user.store_slug);
      } else if (user?.store_id) {
        fetchStoreSlug();
      }
    }, [user?.role, originalUser?.role, user?.store_slug, user?.store_id])
  );
  
  const fetchPendingCount = async () => {
    try {
      const res = await api.get('/admin/pending-users/count');
      setPendingUsersCount(res.data.count);
    } catch (error) {
      console.error('Failed to fetch pending users count:', error);
    }
  };

  const fetchStoreSlug = async () => {
    try {
      const res = await api.get(`/admin/stores/${user?.store_id}`, {
        headers: { 'X-User-ID': user?._id }
      });
      const slug = res.data?.slug;
      if (slug) {
        setStoreSlug(slug);
      } else if (res.data?.name) {
        setStoreSlug(res.data.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
      }
    } catch (e) {}
  };

  const getReviewUrl = () => {
    if (!storeSlug) return '';
    const spParam = user?._id ? `?sp=${user._id}` : '';
    return `https://app.imonsocial.com/review/${storeSlug}${spParam}`;
  };

  const handleCopyReviewLink = async () => {
    const url = getReviewUrl();
    try {
      if (Platform.OS === 'web' && navigator.clipboard) {
        await navigator.clipboard.writeText(url);
      } else if (Platform.OS === 'web') {
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
    } catch {
      try {
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      } catch {}
    }
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const logReviewShareEvent = async (platform: string, forceAction?: string) => {
    const phone = shareRecipientPhone.trim();
    const email = shareRecipientEmail.trim();
    const name = shareRecipientName.trim();
    if (!phone && !email) return;
    if (!user?._id) return;

    const payload: any = {
      phone, email, name,
      event_type: 'review_shared',
      event_title: 'Review Link Shared',
      event_description: `Shared review link via ${platform}`,
      event_icon: 'star',
      event_color: '#FFD60A',
    };
    if (forceAction) payload.force_action = forceAction;

    try {
      const res = await api.post(`/contacts/${user._id}/find-or-create-and-log`, payload);
      if (res.data.needs_confirmation) {
        setMatchInfo(res.data);
        setPendingSharePayload({ platform, payload });
        setMatchModalVisible(true);
      }
    } catch (err) {
      console.error('Failed to log review share event:', err);
    }
  };

  const resolveReviewMatch = async (action: string) => {
    setMatchModalVisible(false);
    if (!pendingSharePayload || !user?._id) return;
    try {
      await api.post(`/contacts/${user._id}/find-or-create-and-log`, {
        ...pendingSharePayload.payload,
        force_action: action,
      });
    } catch {}
    setMatchInfo(null);
    setPendingSharePayload(null);
  };

  const handleShareViaSMS = async () => {
    const url = getReviewUrl();
    const msg = `Hey! We'd love your feedback. Leave us a review here: ${url}`;
    const phone = shareRecipientPhone.trim();
    const isApple = /iPad|iPhone|iPod|Macintosh/.test(navigator.userAgent);
    const sep = isApple ? '&' : '?';
    const smsUrl = phone
      ? `sms:${phone}${sep}body=${encodeURIComponent(msg)}`
      : `sms:${sep === '&' ? '&' : '?'}body=${encodeURIComponent(msg)}`;
    
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = smsUrl;
      a.target = '_self';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      Linking.openURL(smsUrl);
    }

    await logReviewShareEvent('sms');
    setShowShareModal(false);
    setShareRecipientName('');
    setShareRecipientPhone('');
    setShareRecipientEmail('');
  };

  const handleShareViaEmail = async () => {
    const url = getReviewUrl();
    const subject = "We'd love your feedback!";
    const body = `Hi!\n\nThank you for your business. We'd really appreciate it if you could take a moment to leave us a review:\n\n${url}\n\nThank you!`;
    const email = shareRecipientEmail.trim();
    const mailto = email
      ? `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
      : `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a');
      a.href = mailto;
      a.target = '_self';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      Linking.openURL(mailto);
    }

    await logReviewShareEvent('email');
    setShowShareModal(false);
    setShareRecipientName('');
    setShareRecipientPhone('');
    setShareRecipientEmail('');
  };

  const handlePreviewReviewPage = () => {
    const slug = storeSlug || 'my-store';
    router.push(`/review/${slug}` as any);
    setShowShareModal(false);
  };

  // ===== Showroom Share Helpers =====
  const getShowroomUrl = () => {
    const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
    return `${baseUrl}/showcase/${user?._id}`;
  };

  const handleCopyShowroomLink = async () => {
    const url = getShowroomUrl();
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(url);
      }
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {}
  };

  const handleShowroomViaSMS = () => {
    const url = getShowroomUrl();
    const name = shareRecipientName.trim();
    const phone = shareRecipientPhone.trim();
    const greeting = name ? `Hi ${name}, ` : '';
    const body = `${greeting}Check out our happy customers and reviews: ${url}`;
    const smsUrl = Platform.OS === 'ios' ? `sms:${phone}&body=${encodeURIComponent(body)}` : `sms:${phone}?body=${encodeURIComponent(body)}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a'); a.href = smsUrl; a.target = '_self'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } else { Linking.openURL(smsUrl); }
    setShowShowroomShare(false);
    setShareRecipientName(''); setShareRecipientPhone(''); setShareRecipientEmail('');
  };

  const handleShowroomViaEmail = () => {
    const url = getShowroomUrl();
    const subject = 'Check Out Our Happy Customers!';
    const body = `Hi!\n\nTake a look at what our customers are saying:\n\n${url}\n\nThank you!`;
    const email = shareRecipientEmail.trim();
    const mailto = email ? `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}` : `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a'); a.href = mailto; a.target = '_self'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } else { Linking.openURL(mailto); }
    setShowShowroomShare(false);
    setShareRecipientName(''); setShareRecipientPhone(''); setShareRecipientEmail('');
  };

  // ===== Birthday Card Share Helpers =====
  const handleBirthdayViaSMS = () => {
    const phone = shareRecipientPhone.trim();
    const name = shareRecipientName.trim();
    const greeting = name ? `Happy Birthday ${name}! ` : 'Happy Birthday! ';
    const body = `${greeting}We hope your day is amazing. Thank you for being a valued customer!`;
    const smsUrl = Platform.OS === 'ios' ? `sms:${phone}&body=${encodeURIComponent(body)}` : `sms:${phone}?body=${encodeURIComponent(body)}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a'); a.href = smsUrl; a.target = '_self'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } else { Linking.openURL(smsUrl); }
    setShowBirthdayShare(false);
    setShareRecipientName(''); setShareRecipientPhone(''); setShareRecipientEmail('');
  };

  const handleBirthdayViaEmail = () => {
    const subject = 'Happy Birthday from Us!';
    const name = shareRecipientName.trim();
    const body = name
      ? `Happy Birthday, ${name}!\n\nWe hope you have an amazing day! Thank you for being such a wonderful customer.\n\nWarm wishes!`
      : `Happy Birthday!\n\nWe hope you have an amazing day! Thank you for being such a wonderful customer.\n\nWarm wishes!`;
    const email = shareRecipientEmail.trim();
    const mailto = email ? `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}` : `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    if (Platform.OS === 'web') {
      const a = document.createElement('a'); a.href = mailto; a.target = '_self'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } else { Linking.openURL(mailto); }
    setShowBirthdayShare(false);
    setShareRecipientName(''); setShareRecipientPhone(''); setShareRecipientEmail('');
  };
  
  const handleExitImpersonation = async () => {
    setExitingImpersonation(true);
    try {
      await stopImpersonation();
      showSimpleAlert('Success', `You are now logged back in as ${originalUser?.name}`);
      router.replace('/(tabs)/inbox');
    } catch (error) {
      showSimpleAlert('Error', 'Failed to exit impersonation');
    } finally {
      setExitingImpersonation(false);
    }
  };
  
  const handleLogout = async () => {
    try {
      await logout();
      router.replace('/auth/login');
    } catch (e) {
      console.error('Logout error:', e);
      router.replace('/auth/login');
    }
  };
  
  const toggleSection = (sectionId: string) => {
    const ref = sectionRefs.current[sectionId];
    let beforeY = 0;
    
    // Capture where this section is on screen right now
    if (Platform.OS === 'web' && ref) {
      const rect = (ref as any).getBoundingClientRect?.();
      if (rect) beforeY = rect.top;
    }
    
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpandedSections(prev => {
      const newSet = new Set<string>();
      if (!prev.has(sectionId)) {
        newSet.add(sectionId);
      }
      return newSet;
    });
    
    // After layout updates, adjust scroll so section stays at the same spot on screen
    if (Platform.OS === 'web' && ref) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const rect = (ref as any).getBoundingClientRect?.();
          if (rect && scrollRef.current) {
            const diff = rect.top - beforeY;
            if (Math.abs(diff) > 2) {
              const scrollNode = (scrollRef.current as any).getScrollableNode?.();
              if (scrollNode) {
                scrollNode.scrollTop += diff;
              }
            }
          }
        });
      });
    }
  };
  
  // Check user roles
  const isAdmin = user?.role === 'super_admin' || user?.role === 'org_admin' || user?.role === 'store_manager';
  const isSuperAdmin = user?.role === 'super_admin';
  const isIndependent = !user?.organization_id;

  // Define all sections with their items
  const sections: Section[] = [
    // Tools - Daily use items not on the Home tab
    {
      id: 'tools',
      title: 'Tools',
      icon: 'apps',
      color: '#007AFF',
      defaultExpanded: true,
      items: [
        {
          icon: 'chatbox-ellipses',
          title: 'Team Chat',
          subtitle: 'Internal team messaging',
          onPress: () => router.push('/(tabs)/team'),
          color: '#5856D6',
        },
        {
          icon: 'checkmark-done',
          title: 'Tasks & Reminders',
          subtitle: 'Manage follow-ups',
          onPress: () => router.push('/tasks'),
          color: '#34C759',
        },
        {
          icon: 'sparkles',
          title: 'Ask Jessi',
          subtitle: 'Your AI assistant',
          onPress: () => router.push('/jessie'),
          color: '#C9A962',
        },
        {
          icon: 'school',
          title: 'Training Hub',
          subtitle: "Learn how to use i'M On Social",
          onPress: () => router.push('/training-hub'),
          color: '#FF9500',
        },
      ],
    },
    // Campaigns & Outreach
    {
      id: 'campaigns',
      title: 'Campaigns',
      icon: 'rocket',
      color: '#FF2D55',
      items: [
        {
          icon: 'chatbubbles',
          title: 'SMS Campaigns',
          subtitle: 'Automated SMS follow-ups',
          onPress: () => router.push('/campaigns'),
          color: '#FF2D55',
        },
        {
          icon: 'mail',
          title: 'Email Campaigns',
          subtitle: 'Automated email follow-ups',
          onPress: () => router.push('/campaigns/email'),
          color: '#AF52DE',
        },
        {
          icon: 'speedometer',
          title: 'Campaign Dashboard',
          subtitle: 'View enrollments',
          onPress: () => router.push('/campaigns/dashboard'),
          color: '#5AC8FA',
        },
        {
          icon: 'megaphone',
          title: 'Broadcast',
          subtitle: 'Mass messaging',
          onPress: () => router.push('/broadcast'),
          color: '#FF9500',
        },
        {
          icon: 'calendar-outline',
          title: 'Date Triggers',
          subtitle: 'Birthdays, anniversaries, holidays',
          onPress: () => router.push('/settings/date-triggers'),
          color: '#FF9500',
        },
      ],
    },
    // Reports & Performance
    {
      id: 'performance',
      title: 'Reports',
      icon: 'stats-chart',
      color: '#34C759',
      items: [
        {
          icon: 'bar-chart',
          title: 'Activity Reports',
          subtitle: 'Activity reports & analytics',
          onPress: () => router.push('/reports/activity'),
          color: '#007AFF',
        },
        {
          icon: 'stats-chart',
          title: 'Analytics',
          subtitle: 'Performance metrics',
          onPress: () => router.push('/analytics'),
          color: '#34C759',
        },
        {
          icon: 'bar-chart',
          title: 'Email Analytics',
          subtitle: 'Opens, clicks, engagement',
          onPress: () => router.push('/settings/email-analytics'),
          color: '#FF2D55',
        },
        {
          icon: 'trophy',
          title: 'My Rankings',
          subtitle: 'Your personal performance',
          onPress: () => router.push('/admin/my-rankings'),
          color: '#FFD60A',
        },
        {
          icon: 'podium',
          title: 'Leaderboard',
          subtitle: 'Team rankings & performance',
          onPress: () => router.push('/admin/leaderboard'),
          color: '#AF52DE',
        },
      ],
    },
    // Templates & Branding
    {
      id: 'templates',
      title: 'Templates & Branding',
      icon: 'color-palette',
      color: '#AF52DE',
      items: [
        {
          icon: 'document-text',
          title: 'SMS Templates',
          subtitle: 'Create SMS templates',
          onPress: () => router.push('/settings/templates'),
          color: '#FFD60A',
        },
        {
          icon: 'mail-outline',
          title: 'Email Templates',
          subtitle: 'Create email templates',
          onPress: () => router.push('/settings/email-templates'),
          color: '#34C759',
        },
        {
          icon: 'color-palette-outline',
          title: 'Card Templates',
          subtitle: 'Customize card designs & messages',
          onPress: () => router.push('/settings/card-templates'),
          color: '#FF9500',
        },
        {
          icon: 'color-palette',
          title: 'Brand Kit',
          subtitle: 'Email branding & colors',
          onPress: () => router.push('/settings/brand-kit'),
          color: '#AF52DE',
        },
        {
          icon: 'images',
          title: 'Manage Showcase',
          subtitle: 'Edit your happy customers page',
          onPress: () => router.push(`/showroom-manage` as any),
          color: '#34C759',
        },
      ],
    },
    // Contacts & Leads
    {
      id: 'contacts',
      title: 'Contacts & Leads',
      icon: 'people',
      color: '#5856D6',
      items: [
        {
          icon: 'git-branch',
          title: 'Lead Sources',
          subtitle: 'Inbound leads & routing',
          onPress: () => router.push('/admin/lead-sources'),
          color: '#5856D6',
        },
        {
          icon: 'pricetags',
          title: 'Contact Tags',
          subtitle: 'Organize with tags',
          onPress: () => router.push('/settings/tags'),
          color: '#FF9500',
        },
        {
          icon: 'star-outline',
          title: 'Review Links',
          subtitle: 'Google, Facebook, Yelp',
          onPress: () => router.push('/settings/review-links'),
          color: '#FFD60A',
        },
        {
          icon: 'chatbubbles-outline',
          title: 'Review Approvals',
          subtitle: 'Approve customer reviews',
          onPress: () => router.push('/settings/review-approvals'),
          color: '#AF52DE',
        },
        {
          icon: 'shield-checkmark-outline',
          title: 'Showcase Approvals',
          subtitle: 'Approve showcase posts',
          onPress: () => router.push('/settings/showcase-approvals'),
          color: '#34C759',
        },
      ],
    },
    // Settings & Security
    {
      id: 'settings',
      title: 'Settings',
      icon: 'settings',
      color: colors.textSecondary,
      items: [
        {
          icon: 'storefront-outline',
          title: 'Store Profile',
          subtitle: 'Logo, address, store info',
          onPress: () => router.push('/settings/store-profile' as any),
          color: '#34C759',
        },
        {
          icon: 'shield-checkmark',
          title: 'Security',
          subtitle: 'Face ID, passwords',
          onPress: () => router.push('/settings/security'),
          color: '#FF3B30',
        },
        {
          icon: 'calendar-outline',
          title: 'Calendar',
          subtitle: 'Connect calendars',
          onPress: () => router.push('/settings/calendar'),
          color: '#007AFF',
        },
        {
          icon: 'git-network',
          title: 'Integrations',
          subtitle: 'API keys & webhooks',
          onPress: () => router.push('/settings/integrations'),
          color: '#5856D6',
        },
        {
          icon: 'help-circle-outline',
          title: 'Help Center',
          subtitle: 'How-to guides & FAQs',
          onPress: () => router.push('/help' as any),
          color: '#007AFF',
        },
      ],
    },
  ];

  // Admin section - only for admins
  const adminSection: Section | null = isAdmin ? {
    id: 'admin',
    title: 'Administration',
    icon: 'shield-checkmark',
    color: '#FF3B30',
    items: [
      {
        icon: 'rocket-outline',
        title: 'Client Onboarding',
        subtitle: 'Step-by-step setup checklist',
        onPress: () => router.push('/admin/client-onboarding'),
        color: '#C9A962',
      },
      {
        icon: 'shield-checkmark',
        title: 'Admin Dashboard',
        subtitle: 'Overview & activity',
        onPress: () => router.push('/admin'),
        color: '#34C759',
      },
      {
        icon: 'map-outline',
        title: 'App Directory',
        subtitle: 'Browse & share pages',
        onPress: () => router.push('/admin/app-directory'),
        color: '#5AC8FA',
      },
      {
        icon: 'library',
        title: 'Company Docs',
        subtitle: 'Policies, security & training',
        onPress: () => router.push('/admin/docs'),
        color: '#5856D6',
      },
      {
        icon: 'person-add',
        title: 'Invite Team',
        subtitle: 'Send invitations',
        onPress: () => router.push('/settings/invite-team'),
        color: '#C9A962',
      },
      // Organizations - super_admin only
      ...(isSuperAdmin ? [{
        icon: 'business',
        title: 'Organizations',
        subtitle: 'Manage organizations',
        onPress: () => router.push('/admin/organizations'),
        color: '#007AFF',
      }] : []),
      // Accounts (Stores) - org_admin and above
      ...(isSuperAdmin || user?.role === 'org_admin' ? [{
        icon: 'storefront',
        title: 'Accounts',
        subtitle: 'Manage store accounts',
        onPress: () => router.push('/admin/stores'),
        color: '#34C759',
      }] : []),
      // Users - org_admin and above
      ...(isSuperAdmin || user?.role === 'org_admin' || user?.role === 'store_manager' ? [{
        icon: 'people',
        title: 'Users',
        subtitle: 'Manage team members',
        onPress: () => router.push('/admin/users'),
        color: '#FF9500',
      }] : []),
      ...(isSuperAdmin ? [
        {
          icon: 'person',
          title: 'Individuals',
          subtitle: 'Independent users',
          onPress: () => router.push('/admin/individuals'),
          color: '#AF52DE',
        },
        {
          icon: 'person-add',
          title: 'Pending Users',
          subtitle: 'Approve new signups',
          onPress: () => router.push('/admin/pending-users'),
          color: '#FF3B30',
          badge: pendingUsersCount,
        },
        {
          icon: 'document-text',
          title: 'Partner Agreements',
          subtitle: 'Reseller contracts',
          onPress: () => router.push('/admin/partner-agreements'),
          color: '#FF9500',
        },
        {
          icon: 'color-palette',
          title: 'White Label Partners',
          subtitle: 'Manage branded partners',
          onPress: () => router.push('/admin/white-label'),
          color: '#E87722',
        },
        {
          icon: 'people',
          title: 'Company Directory',
          subtitle: 'Team & leaderboards',
          onPress: () => router.push('/admin/directory'),
          color: '#AF52DE',
        },
        {
          icon: 'mail',
          title: 'Shared Inboxes',
          subtitle: 'Phone number users',
          onPress: () => router.push('/admin/shared-inboxes'),
          color: '#007AFF',
        },
        {
          icon: 'swap-horizontal',
          title: 'Bulk Transfer',
          subtitle: 'Transfer contacts',
          onPress: () => router.push('/admin/bulk-transfer'),
          color: '#FF3B30',
        },
        {
          icon: 'call',
          title: 'Phone Assignments',
          subtitle: 'Twilio numbers',
          onPress: () => router.push('/admin/phone-assignments'),
          color: '#32ADE6',
        },
        {
          icon: 'documents',
          title: 'View Quotes',
          subtitle: 'Subscription quotes',
          onPress: () => router.push('/admin/quotes'),
          color: '#30B0C7',
        },
        {
          icon: 'receipt',
          title: 'Create Quote',
          subtitle: 'Generate quotes',
          onPress: () => router.push('/admin/create-quote'),
          color: '#34C759',
        },
        {
          icon: 'ticket',
          title: 'Discount Codes',
          subtitle: 'Manage discounts',
          onPress: () => router.push('/admin/discount-codes'),
          color: '#5856D6',
        },
      ] : []),
    ],
  } : null;

  // Combine all sections
  const allSections = adminSection ? [adminSection, ...sections] : sections;

  const renderMenuItem = (item: MenuItem, index: number) => (
    <TouchableOpacity
      key={`${item.title}-${index}`}
      style={[styles.menuItemCard, { backgroundColor: colors.surface }]}
      onPress={item.onPress}
      activeOpacity={0.7}
      data-testid={`menu-item-${item.title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
        <Ionicons name={item.icon as any} size={20} color={item.color} />
      </View>
      <View style={styles.menuContent}>
        <Text style={[styles.menuTitle, { color: colors.text }]}>{item.title}</Text>
        <Text style={[styles.menuSubtitle, { color: colors.textSecondary }]}>{item.subtitle}</Text>
      </View>
      {item.badge && item.badge > 0 && (
        <View style={styles.notificationBadge}>
          <Text style={styles.notificationBadgeText}>{item.badge}</Text>
        </View>
      )}
      <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
    </TouchableOpacity>
  );

  const renderSection = (section: Section) => {
    const isExpanded = expandedSections.has(section.id);
    const itemCount = section.items.length;

    return (
      <View key={section.id} style={styles.sectionWrapper} data-testid={`section-${section.id}`}>
        {/* Section Header Card */}
        <TouchableOpacity
          ref={(el: any) => { sectionRefs.current[section.id] = el; }}
          style={[styles.sectionHeaderCard, { backgroundColor: colors.card }]}
          onPress={() => toggleSection(section.id)}
          activeOpacity={0.7}
          data-testid={`section-header-${section.id}`}
        >
          <View style={[styles.sectionIcon, { backgroundColor: `${section.color}20` }]}>
            <Ionicons name={section.icon as any} size={20} color={section.color} />
          </View>
          <Text style={[styles.sectionTitleText, { color: colors.text }]}>{section.title}</Text>
          <Ionicons 
            name={isExpanded ? 'chevron-up' : 'chevron-down'} 
            size={20} 
            color={colors.textSecondary} 
          />
        </TouchableOpacity>
        
        {/* Indented Child Item Cards */}
        {isExpanded && section.items.map((item, index) => 
          renderMenuItem(item, index)
        )}
      </View>
    );
  };
  
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <ScrollView ref={scrollRef} contentContainerStyle={styles.scrollContent}>
        {/* Impersonation Banner */}
        {isImpersonating && (
          <TouchableOpacity 
            style={styles.impersonationBanner}
            onPress={handleExitImpersonation}
            disabled={exitingImpersonation}
            data-testid="impersonation-banner"
          >
            <View style={styles.impersonationContent}>
              <Ionicons name="person-circle" size={24} color={colors.text} />
              <View style={styles.impersonationTextContainer}>
                <Text style={styles.impersonationTitle}>Impersonating {user?.name}</Text>
                <Text style={styles.impersonationSubtitle}>Tap to return to {originalUser?.name}</Text>
              </View>
            </View>
            <Ionicons name="close-circle" size={28} color={colors.text} />
          </TouchableOpacity>
        )}
        
        {/* Partner Branding Banner */}
        {partnerBranding && (
          <View style={[styles.partnerBanner, { borderBottomColor: partnerBranding.primary_color + '30', backgroundColor: colors.cardAlt }]} data-testid="partner-branding-banner">
            <View style={styles.partnerBannerInner}>
              {partnerBranding.logo ? (
                <Image source={{ uri: partnerBranding.logo }} style={styles.partnerLogo} resizeMode="contain" />
              ) : (
                <View style={[styles.partnerLogoPlaceholder, { backgroundColor: partnerBranding.primary_color + '20' }]}>
                  <Text style={[styles.partnerLogoText, { color: partnerBranding.primary_color }]}>
                    {partnerBranding.name?.split(' ').map((w: string) => w[0]).join('').slice(0, 2)}
                  </Text>
                </View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={[styles.partnerName, { color: partnerBranding.primary_color }]}>{partnerBranding.name}</Text>
                <Text style={styles.partnerPowered}>{partnerBranding.powered_by_text}</Text>
              </View>
            </View>
          </View>
        )}

        {/* Profile Card - Digital Card Style */}
        <View style={styles.profileCardContainer}>
          <TouchableOpacity 
            style={[styles.profileCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            onPress={() => router.push('/my-account')}
            activeOpacity={0.7}
            data-testid="profile-card"
          >
            <View style={styles.profileAvatarContainer}>
              {user?.photo_url ? (
                <Image source={{ uri: user.photo_url }} style={styles.profileAvatarImage} />
              ) : (
                <View style={styles.profileAvatar}>
                  <Text style={styles.profileAvatarText}>
                    {user?.name
                      ?.split(' ')
                      .map((n) => n[0])
                      .join('')
                      .toUpperCase() || '?'}
                  </Text>
                </View>
              )}
            </View>
            <View style={styles.profileInfo}>
              <Text style={[styles.profileName, { color: colors.text }]}>{user?.name || 'Guest'}</Text>
              {user?.title ? (
                <Text style={styles.profileTitle}>{user.title}</Text>
              ) : null}
              <Text style={[styles.profileEmail, { color: colors.textSecondary }]}>{user?.email || ''}</Text>
              {user?.phone && (
                <Text style={[styles.profilePhone, { color: colors.textSecondary }]}>{user.phone}</Text>
              )}
            </View>
            <Ionicons name="chevron-forward" size={18} color="#555" />
          </TouchableOpacity>
          
          {/* Stacked Bell + Theme + Logout */}
          <View style={styles.profileActions}>
            <NotificationBell />
            <TouchableOpacity
              style={[styles.profileSignOutBtn, { backgroundColor: colors.card }]}
              onPress={toggleTheme}
              data-testid="theme-toggle-btn"
            >
              <Ionicons name={themeMode === 'dark' ? 'moon' : 'sunny'} size={18} color={themeMode === 'dark' ? '#5856D6' : '#FF9500'} />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.profileSignOutBtn, { backgroundColor: colors.card }]}
              onPress={handleLogout}
              data-testid="logout-button"
            >
              <Ionicons name="log-out-outline" size={18} color="#FF3B30" />
            </TouchableOpacity>
          </View>
        </View>
        
        {/* All Collapsible Sections */}
        {allSections.map(section => renderSection(section))}
        
        {/* Legal Section - Always visible, not collapsible */}
        <View style={styles.legalSection}>
          <TouchableOpacity
            style={styles.legalItem}
            onPress={() => router.push('/terms')}
            data-testid="terms-of-service-link"
          >
            <Ionicons name="document-text" size={18} color="#6E6E73" />
            <Text style={styles.legalText}>Terms of Service</Text>
          </TouchableOpacity>
          <Text style={styles.legalDivider}>•</Text>
          <TouchableOpacity
            style={styles.legalItem}
            onPress={() => router.push('/privacy')}
            data-testid="privacy-policy-link"
          >
            <Ionicons name="shield-checkmark" size={18} color="#6E6E73" />
            <Text style={styles.legalText}>Privacy Policy</Text>
          </TouchableOpacity>
        </View>
        
        <View style={styles.versionContainer}>
          {partnerBranding ? (
            <>
              {partnerBranding.logo ? (
                <Image source={{ uri: partnerBranding.logo }} style={styles.versionLogo} resizeMode="contain" />
              ) : (
                <Text style={[styles.version, { fontSize: 14, fontWeight: '700', color: partnerBranding.primary_color }]}>{partnerBranding.name}</Text>
              )}
              <Text style={[styles.version, { marginTop: 4 }]}>{partnerBranding.powered_by_text}</Text>
            </>
          ) : (
            <>
              <Text style={styles.version}>{BRAND.poweredByText}</Text>
              <Text style={[styles.version, { marginTop: 4 }]}>v1.0.0</Text>
            </>
          )}
        </View>
      </ScrollView>

      {/* Share Review Link Modal */}
      <WebModal visible={showShareModal} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowShareModal(false)}>
        <View style={shareStyles.modal}>
          <View style={shareStyles.header}>
            <TouchableOpacity onPress={() => setShowShareModal(false)} data-testid="share-modal-close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
            <Text style={shareStyles.headerTitle}>Share Review Link</Text>
            <View style={{ width: 24 }} />
          </View>

          {!storeSlug && (
            <TouchableOpacity onPress={() => { setShowShareModal(false); router.push('/settings/store-profile' as any); }}>
              <Text style={{ color: '#FF9500', fontSize: 13, textAlign: 'center', marginTop: 12, paddingHorizontal: 16, textDecorationLine: 'underline' }}>
                Store slug not set. Tap here to configure in Store Profile.
              </Text>
            </TouchableOpacity>
          )}

          {/* Recipient Info */}
          <View style={shareStyles.recipientSection}>
            <Text style={shareStyles.recipientLabel}>SEND TO (OPTIONAL)</Text>
            <TextInput
              style={shareStyles.recipientInput}
              placeholder="Recipient Name"
              placeholderTextColor="#6E6E73"
              value={shareRecipientName}
              onChangeText={setShareRecipientName}
              data-testid="share-recipient-name"
            />
            <TextInput
              style={shareStyles.recipientInput}
              placeholder="Phone"
              placeholderTextColor="#6E6E73"
              value={shareRecipientPhone}
              onChangeText={setShareRecipientPhone}
              keyboardType="phone-pad"
              data-testid="share-recipient-phone"
            />
            <TextInput
              style={shareStyles.recipientInput}
              placeholder="Email"
              placeholderTextColor="#6E6E73"
              value={shareRecipientEmail}
              onChangeText={setShareRecipientEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              data-testid="share-recipient-email"
            />
          </View>

          {/* Action Buttons */}
          <View style={shareStyles.actions}>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleCopyReviewLink} data-testid="share-copy-link-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#FF950020' }]}>
                <Ionicons name={copiedLink ? 'checkmark' : 'copy-outline'} size={24} color={copiedLink ? '#34C759' : '#FF9500'} />
              </View>
              <Text style={shareStyles.actionLabel}>{copiedLink ? 'Copied!' : 'Copy Link'}</Text>
            </TouchableOpacity>

            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleShareViaSMS} data-testid="share-sms-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
              </View>
              <Text style={shareStyles.actionLabel}>Text</Text>
            </TouchableOpacity>

            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleShareViaEmail} data-testid="share-email-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="mail-outline" size={24} color="#007AFF" />
              </View>
              <Text style={shareStyles.actionLabel}>Email</Text>
            </TouchableOpacity>

            <TouchableOpacity style={shareStyles.actionBtn} onPress={handlePreviewReviewPage} data-testid="share-preview-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#5856D620' }]}>
                <Ionicons name="eye-outline" size={24} color="#5856D6" />
              </View>
              <Text style={shareStyles.actionLabel}>Preview</Text>
            </TouchableOpacity>
          </View>

          {/* Manage Links Shortcut */}
          <TouchableOpacity 
            style={shareStyles.manageLink}
            onPress={() => { setShowShareModal(false); router.push('/settings/review-links' as any); }}
            data-testid="share-manage-links-btn"
          >
            <Ionicons name="settings-outline" size={16} color={colors.textSecondary} />
            <Text style={shareStyles.manageLinkText}>Manage Review Platform Links</Text>
            <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
          </TouchableOpacity>

          <Text style={shareStyles.hint}>
            Tap Text or Email to send a pre-written review request to your customer.
          </Text>
        </View>
      </WebModal>

      {/* Showroom Share Modal */}
      <WebModal visible={showShowroomShare} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowShowroomShare(false)}>
        <View style={shareStyles.modal}>
          <View style={shareStyles.header}>
            <TouchableOpacity onPress={() => setShowShowroomShare(false)} data-testid="showroom-share-close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
            <Text style={shareStyles.headerTitle}>Share My Showcase</Text>
            <View style={{ width: 24 }} />
          </View>

          <View style={shareStyles.recipientSection}>
            <Text style={shareStyles.recipientLabel}>SEND TO (OPTIONAL)</Text>
            <TextInput style={shareStyles.recipientInput} placeholder="Recipient Name" placeholderTextColor="#6E6E73"
              value={shareRecipientName} onChangeText={setShareRecipientName} data-testid="showroom-recipient-name" />
            <TextInput style={shareStyles.recipientInput} placeholder="Phone" placeholderTextColor="#6E6E73"
              value={shareRecipientPhone} onChangeText={setShareRecipientPhone} keyboardType="phone-pad" data-testid="showroom-recipient-phone" />
            <TextInput style={shareStyles.recipientInput} placeholder="Email" placeholderTextColor="#6E6E73"
              value={shareRecipientEmail} onChangeText={setShareRecipientEmail} keyboardType="email-address" autoCapitalize="none" data-testid="showroom-recipient-email" />
          </View>

          <View style={shareStyles.actions}>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleCopyShowroomLink} data-testid="showroom-copy-link">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#FF950020' }]}>
                <Ionicons name={copiedLink ? 'checkmark' : 'copy-outline'} size={24} color={copiedLink ? '#34C759' : '#FF9500'} />
              </View>
              <Text style={shareStyles.actionLabel}>{copiedLink ? 'Copied!' : 'Copy Link'}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleShowroomViaSMS} data-testid="showroom-sms-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
              </View>
              <Text style={shareStyles.actionLabel}>Text</Text>
            </TouchableOpacity>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleShowroomViaEmail} data-testid="showroom-email-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="mail-outline" size={24} color="#007AFF" />
              </View>
              <Text style={shareStyles.actionLabel}>Email</Text>
            </TouchableOpacity>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={() => { setShowShowroomShare(false); router.push(`/showcase/${user?._id}` as any); }} data-testid="showroom-preview-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#5856D620' }]}>
                <Ionicons name="eye-outline" size={24} color="#5856D6" />
              </View>
              <Text style={shareStyles.actionLabel}>Preview</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={shareStyles.manageLink} onPress={() => { setShowShowroomShare(false); router.push('/showroom-manage' as any); }} data-testid="showroom-manage-btn">
            <Ionicons name="settings-outline" size={16} color={colors.textSecondary} />
            <Text style={shareStyles.manageLinkText}>Manage Showcase Entries</Text>
            <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
          </TouchableOpacity>

          <Text style={shareStyles.hint}>Share your Showcase link to showcase your happy customers and reviews.</Text>
        </View>
      </WebModal>

      {/* Birthday Card Share Modal */}
      <WebModal visible={showBirthdayShare} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowBirthdayShare(false)}>
        <View style={shareStyles.modal}>
          <View style={shareStyles.header}>
            <TouchableOpacity onPress={() => setShowBirthdayShare(false)} data-testid="birthday-share-close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
            <Text style={shareStyles.headerTitle}>Send Birthday Wishes</Text>
            <View style={{ width: 24 }} />
          </View>

          <View style={shareStyles.recipientSection}>
            <Text style={shareStyles.recipientLabel}>BIRTHDAY CUSTOMER</Text>
            <TextInput style={shareStyles.recipientInput} placeholder="Customer Name" placeholderTextColor="#6E6E73"
              value={shareRecipientName} onChangeText={setShareRecipientName} data-testid="birthday-recipient-name" />
            <TextInput style={shareStyles.recipientInput} placeholder="Phone" placeholderTextColor="#6E6E73"
              value={shareRecipientPhone} onChangeText={setShareRecipientPhone} keyboardType="phone-pad" data-testid="birthday-recipient-phone" />
            <TextInput style={shareStyles.recipientInput} placeholder="Email" placeholderTextColor="#6E6E73"
              value={shareRecipientEmail} onChangeText={setShareRecipientEmail} keyboardType="email-address" autoCapitalize="none" data-testid="birthday-recipient-email" />
          </View>

          <View style={shareStyles.actions}>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleBirthdayViaSMS} data-testid="birthday-sms-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="chatbubble-outline" size={24} color="#34C759" />
              </View>
              <Text style={shareStyles.actionLabel}>Text</Text>
            </TouchableOpacity>
            <TouchableOpacity style={shareStyles.actionBtn} onPress={handleBirthdayViaEmail} data-testid="birthday-email-btn">
              <View style={[shareStyles.actionIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="mail-outline" size={24} color="#007AFF" />
              </View>
              <Text style={shareStyles.actionLabel}>Email</Text>
            </TouchableOpacity>
          </View>

          <Text style={shareStyles.hint}>Send a personalized birthday greeting to your customer via text or email.</Text>
        </View>
      </WebModal>

      {/* Contact Match Modal */}
      {matchModalVisible && matchInfo && (
        <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
          <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 24, width: '90%', maxWidth: 380 }} data-testid="review-match-modal">
            <View style={{ alignItems: 'center', marginBottom: 16 }}>
              <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: '#FF950015', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="person-circle" size={44} color="#FF9500" />
              </View>
            </View>
            <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, textAlign: 'center', marginBottom: 8 }}>Contact Already Exists</Text>
            <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginBottom: 16 }}>A contact with this info already exists:</Text>
            <View style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 14, alignItems: 'center' }}>
              <Text style={{ fontSize: 10, fontWeight: '700', color: '#6E6E73', letterSpacing: 1, marginBottom: 6 }}>EXISTING CONTACT</Text>
              <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>{matchInfo.existing_name}</Text>
              {matchInfo.phone ? <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>{matchInfo.phone}</Text> : null}
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginVertical: 12 }}>
              <View style={{ flex: 1, height: 1, backgroundColor: colors.surface }} />
              <Text style={{ fontSize: 12, color: '#6E6E73', marginHorizontal: 12 }}>You entered</Text>
              <View style={{ flex: 1, height: 1, backgroundColor: colors.surface }} />
            </View>
            <View style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 14, alignItems: 'center', marginBottom: 20 }}>
              <Text style={{ fontSize: 17, fontWeight: '600', color: '#FF9500' }}>{matchInfo.provided_name}</Text>
            </View>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveReviewMatch('use_existing')}>
              <Ionicons name="checkmark-circle" size={20} color="#34C759" />
              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '500', flex: 1 }}>Use Existing Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveReviewMatch('update_name')}>
              <Ionicons name="create" size={20} color="#007AFF" />
              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '500', flex: 1 }}>Update to "{matchInfo.provided_name}"</Text>
            </TouchableOpacity>
            <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, padding: 14, borderRadius: 10, gap: 10, marginBottom: 8 }} onPress={() => resolveReviewMatch('create_new')}>
              <Ionicons name="person-add" size={20} color="#FF9500" />
              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '500', flex: 1 }}>Create New Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setMatchModalVisible(false); setMatchInfo(null); }} style={{ marginTop: 4, padding: 12, alignItems: 'center' }}>
              <Text style={{ fontSize: 15, color: colors.textSecondary }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  partnerBanner: {
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 4,
    paddingVertical: 12,
    paddingHorizontal: 14,
    backgroundColor: colors.bg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.card,
    borderBottomWidth: 2,
  },
  partnerBannerInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  partnerLogo: {
    width: 36,
    height: 36,
    borderRadius: 8,
  },
  partnerLogoPlaceholder: {
    width: 36,
    height: 36,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  partnerLogoText: {
    fontSize: 14,
    fontWeight: '800',
  },
  partnerName: {
    fontSize: 15,
    fontWeight: '700',
  },
  partnerPowered: {
    fontSize: 11,
    color: colors.textTertiary,
    marginTop: 1,
  },
  bellContainer: {
    position: 'absolute',
    top: Platform.OS === 'web' ? 12 : 8,
    right: 16,
    zIndex: 9999,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  header: {
    padding: 16,
  },
  title: {
    fontSize: 34,
    fontWeight: 'bold',
    color: colors.text,
  },
  impersonationBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#5856D6',
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 14,
    borderRadius: 12,
  },
  impersonationContent: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  impersonationTextContainer: {
    marginLeft: 12,
    flex: 1,
  },
  impersonationTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  impersonationSubtitle: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  profileCardContainer: {
    flexDirection: 'row',
    alignItems: 'stretch',
    marginHorizontal: 16,
    marginBottom: 16,
    gap: 8,
    zIndex: 10000,
  },
  profileCard: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: '#1A1A1A',
    padding: 20,
    borderRadius: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  profileActions: {
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    zIndex: 10000,
  },
  profileSignOutBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileAvatarContainer: {
    position: 'relative',
    marginRight: 14,
  },
  profileAvatar: {
    width: 60,
    height: 60,
    borderRadius: 16,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileAvatarImage: {
    width: 60,
    height: 60,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#C9A962',
  },
  profileAvatarText: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '600',
  },
  // Profile Info
  quickSettingsRow: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginBottom: 16,
    gap: 8,
  },
  quickSettingsBtn: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    gap: 6,
  },
  quickSettingsIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickSettingsLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    textAlign: 'center',
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: 19,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 2,
    letterSpacing: 0.2,
  },
  profileTitle: {
    fontSize: 11,
    color: '#C9A962',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  profileEmail: {
    fontSize: 12,
    marginBottom: 1,
  },
  profilePhone: {
    fontSize: 12,
  },
  // Section Wrapper
  sectionWrapper: {
    marginHorizontal: 16,
    marginBottom: 8,
  },
  // Section Header Card (standalone card)
  sectionHeaderCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  sectionIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  sectionTitleText: {
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
  },
  // Indented child item card
  menuItemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 10,
    padding: 12,
    marginBottom: 6,
    marginLeft: 16,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 15,
    fontWeight: '500',
    marginBottom: 1,
  },
  menuSubtitle: {
    fontSize: 12,
  },
  notificationBadge: {
    backgroundColor: '#FF3B30',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginRight: 8,
    minWidth: 22,
    alignItems: 'center',
  },
  notificationBadgeText: {
    color: colors.text,
    fontSize: 11,
    fontWeight: '700',
  },
  // Legal Section
  legalSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 8,
    gap: 12,
  },
  legalItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legalText: {
    fontSize: 13,
    color: '#6E6E73',
  },
  legalDivider: {
    fontSize: 13,
    color: colors.borderLight,
  },
  versionContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    marginBottom: 8,
    gap: 6,
  },
  versionLogo: {
    width: 36,
    height: 14,
  },
  version: {
    fontSize: 12,
    color: '#6E6E73',
  },
  themeToggleCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 14,
    borderRadius: 12,
  },
  themeToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  themeToggleTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  themeToggleSub: {
    fontSize: 12,
    marginTop: 1,
  },
  // Quick Actions
  quickActionsSection: {
    marginHorizontal: 16,
    marginBottom: 16,
  },
  quickActionsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  quickActionsTitle: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
  },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  quickActionTile: {
    width: '31%',
    flexGrow: 1,
    flexBasis: '30%',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    gap: 6,
  },
  quickActionIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickActionLabel: {
    fontSize: 11,
    fontWeight: '600',
    textAlign: 'center',
    paddingHorizontal: 4,
  },
  // Edit panel
  editActionsPanel: {
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  editActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  editActionItem: {
    width: '23%',
    flexGrow: 1,
    flexBasis: '22%',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  editActionIconBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  editActionBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    width: 16,
    height: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  editActionBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: colors.text,
  },
  editActionLabel: {
    fontSize: 10,
    fontWeight: '600',
    textAlign: 'center',
    paddingHorizontal: 2,
  },
});

const shareStyles = StyleSheet.create({
  modal: {
    flex: 1,
    backgroundColor: '#000000',
    paddingTop: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  linkBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  linkText: {
    flex: 1,
    fontSize: 14,
    fontFamily: Platform.OS === 'web' ? 'monospace' : undefined,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 32,
    paddingHorizontal: 16,
  },
  actionBtn: {
    alignItems: 'center',
    gap: 8,
  },
  actionIcon: {
    width: 56,
    height: 56,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
  },
  manageLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 32,
    paddingVertical: 12,
    marginHorizontal: 16,
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
  },
  manageLinkText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#8E8E93',
  },
  hint: {
    fontSize: 13,
    color: '#6E6E73',
    textAlign: 'center',
    marginTop: 20,
    paddingHorizontal: 32,
    lineHeight: 18,
  },
  recipientSection: {
    marginHorizontal: 16,
    marginTop: 16,
    gap: 8,
  },
  recipientLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#6E6E73',
    letterSpacing: 1,
    marginBottom: 0,
    textTransform: 'uppercase',
  },
  recipientRow: {
    flexDirection: 'row',
    gap: 8,
    width: '100%',
  },
  recipientInput: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
    color: '#FFFFFF',
    borderWidth: 1.5,
    borderColor: '#3A3A3C',
    minWidth: 0,
  },
});