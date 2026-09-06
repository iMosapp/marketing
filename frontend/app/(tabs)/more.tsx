import React, { useState, useCallback, useRef, useEffect } from 'react';
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
  Share,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { copyToClipboard } from '../../utils/clipboard';
import { useRouter, useFocusEffect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { showSimpleAlert, showAlert } from '../../services/alert';
import api from '../../services/api';
import { Image as ExpoImage } from 'expo-image';
import { resolveUserPhotoUrlHiRes } from '../../utils/photoUrl';
import { NotificationBell } from '../../components/notifications/NotificationBell';
import { BRAND } from '../../config/brand';
import { usePushNotifications } from '../../hooks/usePushNotifications';
import { AppHome } from '../../components/hub/AppHome';
import { slug as hubSlug, HubApp, HubFolderDef } from '../../components/hub/layout';

// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

// Module-level constant — must be here so sections building code can reference it
const PROD_BASE = 'https://app.imonsocial.com';

type MenuItem = {
  icon: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  color: string;
  badge?: number;
  statusDot?: 'green' | 'red' | 'grey';
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
  const { status: pushStatus, enable: enablePush, disable: disablePush, subscribing: pushSubscribing, isSupported: pushSupported } = usePushNotifications();
  const [pendingUsersCount, setPendingUsersCount] = useState(0);
  const [exitingImpersonation, setExitingImpersonation] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['leads']));
  const [hubSearch, setHubSearch] = useState('');
  const [hubDragging, setHubDragging] = useState(false);
  const [leadsWaiting, setLeadsWaiting] = useState(0);
  const sectionRefs = useRef<Record<string, View | null>>({});
  const scrollRef = useRef<ScrollView>(null);
  const [storeSlug, setStoreSlug] = useState<string | null>(null);

  // Recently Visited & Pinned Tools tracking
  type HubItem = { title: string; icon: string; color: string; subtitle: string; timestamp: number };
  const uid = user?._id || 'anon';
  const PINNED_KEY = `hub_pinned_${uid}`;
  const MAX_PINNED = 6;
  const [pinnedTools, setPinnedTools] = useState<HubItem[]>([]);

  // Load pinned tools on focus
  useFocusEffect(
    useCallback(() => {
      AsyncStorage.getItem(PINNED_KEY).then(raw => {
        if (raw) { try { setPinnedTools(JSON.parse(raw)); } catch {} }
      });
    }, [PINNED_KEY])
  );

  // trackVisit is kept for compatibility — no longer persists since Recently Visited was removed
  const trackVisit = useCallback((_item: { title: string; icon: string; color: string; subtitle: string }) => {
    // no-op — Recently Visited section removed, use Pin instead
  }, []);

  const togglePin = useCallback(async (item: { title: string; icon: string; color: string; subtitle: string }) => {
    try {
      const raw = await AsyncStorage.getItem(PINNED_KEY);
      let pins: HubItem[] = raw ? JSON.parse(raw) : [];
      const exists = pins.some(p => p.title === item.title);
      if (exists) {
        pins = pins.filter(p => p.title !== item.title);
      } else {
        if (pins.length >= MAX_PINNED) {
          pins.pop(); // remove oldest to make room
        }
        pins.unshift({ ...item, timestamp: Date.now() });
      }
      await AsyncStorage.setItem(PINNED_KEY, JSON.stringify(pins));
      setPinnedTools(pins);
    } catch {}
  }, [PINNED_KEY]);

  const isPinned = useCallback((title: string) => pinnedTools.some(p => p.title === title), [pinnedTools]);
  
  // Load pending count for super admins + leads waiting badge
  useFocusEffect(
    useCallback(() => {
      if (user?._id) {
        api.get(`/leads/queue/${user._id}/summary`).then(r => setLeadsWaiting((r.data?.waiting || 0) + (r.data?.mine_waiting || 0))).catch(() => {});
      }
      if (user?.role === 'super_admin' || originalUser?.role === 'super_admin') {
        fetchPendingCount();
      }
      // Fetch store slug for share review link
      if (user?.store_slug) {
        setStoreSlug(user.store_slug);
      } else if (user?.store_id) {
        fetchStoreSlug();
      }
    }, [user?.role, originalUser?.role, user?.store_slug, user?.store_id, user?._id])
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
    const refParam = user?.ref_code ? `${spParam ? '&' : '?'}ref=${user.ref_code}` : '';
    return `https://app.imonsocial.com/review/${storeSlug}${spParam}${refParam}`;
  };
  const reviewShareUrl = getReviewUrl();

  
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

  const handleDeleteAccount = () => {
    showAlert(
      'Delete Account',
      'This will permanently delete your account, all your contacts, messages, and data. This cannot be undone.\n\nAre you sure you want to continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete My Account', style: 'destructive',
          onPress: () => {
            showAlert(
              'Final Confirmation',
              'Type "DELETE" to confirm permanent account deletion.',
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Permanently Delete', style: 'destructive',
                  onPress: async () => {
                    try {
                      await api.delete(`/admin/users/${user?._id}`, { headers: { 'X-User-ID': user?._id } });
                      await logout();
                      router.replace('/auth/login');
                    } catch (e: any) {
                      showSimpleAlert('Error', 'Account deletion failed. Please contact support@imonsocial.com to delete your account.');
                    }
                  }
                }
              ]
            );
          }
        }
      ]
    );
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
  const reallyAdmin = user?.role === 'super_admin' || user?.role === 'org_admin' || user?.role === 'store_manager';
  const [repPreview, setRepPreview] = useState(false);
  const isAdmin = !repPreview && reallyAdmin;
  const isSuperAdmin = !repPreview && user?.role === 'super_admin';
  const isIndependent = !user?.organization_id;

  // Feature permissions from user object (merged with defaults on login)
  const perms = user?.feature_permissions || {};
  const perm = (section: string, item?: string): boolean => {
    const sec = perms[section];
    if (!sec || !sec._enabled) return false;
    if (!item) return true;
    return !!sec[item];
  };

  // Helper: build section items filtered by permissions
  const filterItems = (sectionKey: string, items: (MenuItem & { permKey?: string })[]) =>
    items.filter(i => !i.permKey || perm(sectionKey, i.permKey));

  // ===== REORGANIZED HUB SECTIONS (Role-Aware) =====

  const sections: Section[] = [];
  const isStoreManager = !repPreview && user?.role === 'store_manager';
  const isPartner = !repPreview && (!!(user?.partner_id) || user?.role === 'partner' || user?.role === 'reseller' || user?.role === 'org_admin');

  // ── PARTNER PORTAL SECTION ──────────────────────────────────────────────────
  if (isPartner) {
    sections.push({
      id: 'partner_portal',
      title: 'Partner Portal',
      icon: 'briefcase',
      color: '#C9A962',
      items: [
        {
          icon: 'business',
          title: 'My Accounts',
          subtitle: 'Active & deactivated clients, W-9 status',
          onPress: () => router.push('/admin/partner-portal' as any),
          color: '#C9A962',
        },
        {
          icon: 'document-text',
          title: 'Create New Quote',
          subtitle: 'Onboard a new client',
          onPress: () => router.push('/admin/create-quote' as any),
          color: '#34C759',
        },
        {
          icon: 'receipt',
          title: 'My Invoices',
          subtitle: 'Commission statements & billing',
          onPress: () => router.push('/admin/my-invoices' as any),
          color: '#007AFF',
        },
      ],
    });
  }

  // ============================================================
  // SECTION 1: MY BRAND (Salesperson's personal command center)
  // ============================================================
  {
    const brandItems = [
      { icon: 'megaphone-outline', title: 'Broadcast', subtitle: 'Mass text from your tracking number', color: '#C9A962', publicUrl: null, editRoute: '/broadcast' },
      { icon: 'gift',             title: 'Create a Card to Share', subtitle: 'Pick a template, get a trackable link — no recipient needed', color: '#FF9500', publicUrl: null, editRoute: '/settings/create-card?generic=true' },
      { icon: 'id-card',        title: 'My Digital Card',  subtitle: 'How customers see you', color: '#C9A962', publicUrl: user?._id ? `${PROD_BASE}/card/${user._id}` : null,         editRoute: '/settings/store-profile' },
      { icon: 'link',           title: 'My Link Page',     subtitle: 'All your links in one spot', color: '#007AFF', publicUrl: user?._id ? `${PROD_BASE}/l/${user._id}` : null,          editRoute: '/settings/link-page' },
      { icon: 'planet-outline', title: 'My Landing Page',  subtitle: 'Your full personal page', color: '#AF52DE', publicUrl: user?._id ? `${PROD_BASE}/p/${user._id}` : null,            editRoute: '/settings/store-profile' },
      { icon: 'images',         title: 'My Showcase',      subtitle: 'Your customer gallery', color: '#34C759', publicUrl: user?._id ? `${PROD_BASE}/showcase/${user._id}` : null,       editRoute: '/showroom-manage' },
      { icon: 'star',           title: 'Review Link',      subtitle: 'Share to get reviews', color: '#FFD60A', publicUrl: reviewShareUrl || null,                                        editRoute: '/settings/review-links' },
    ];
    // Classic menu items (no View/Share needed)
    const menuItems: (MenuItem & { permKey?: string })[] = [
      { permKey: 'sms_templates', icon: 'document-text', title: 'My Templates', subtitle: 'SMS & email templates', onPress: () => router.push('/settings/templates'), color: '#AF52DE' },
      { icon: 'color-palette-outline', title: 'Card Templates', subtitle: 'Thank-you & congrats card designs', onPress: () => router.push('/settings/card-templates'), color: '#FF9500' },
      { icon: 'mail-outline', title: 'Email Signature', subtitle: 'Copy & paste into your email', onPress: () => router.push('/email-signature' as any), color: '#5856D6' },
      { icon: 'phone-portrait-outline', title: 'Share the App', subtitle: 'Your install link + QR, see who installed', onPress: () => router.push('/share-app' as any), color: '#34C759' },
    ];
    const filteredMenu = menuItems.filter(i => !i.permKey || perm('content', i.permKey));
    sections.push({
      id: 'my_brand',
      title: 'My Brand',
      icon: 'sparkles',
      color: '#C9A962',
      defaultExpanded: true,
      items: filteredMenu,
      _brandItems: brandItems, // custom — rendered separately
    } as any);
  }

  // ============================================================
  // ============================================================
  // SECTION LEADS: everything lead related in one spot (reps + managers)
  // ============================================================
  {
    const leadItems: (MenuItem & { permKey?: string; badge?: number })[] = [
      { icon: 'globe', title: 'Internet Leads', subtitle: 'Shared lead queue, speed to lead and call retries report', onPress: () => router.push('/leads' as any), color: '#FF3B30', badge: leadsWaiting || undefined },
      { icon: 'call', title: 'Call Retries', subtitle: 'Voicemail retry timing and the auto "just tried you" text', onPress: () => router.push('/settings/call-retries' as any), color: '#FF9F0A' },
    ];
    if (isAdmin && perm('admin')) {
      if (perm('admin', 'contact_tags')) {
        leadItems.push(
          { icon: 'flash', title: 'Lead Source Queue', subtitle: 'Inbound lead log and queued auto-text status', onPress: () => router.push('/admin/internet-leads'), color: '#C9A962' },
          { icon: 'megaphone', title: 'Lead Source Config', subtitle: 'ADF webhooks, texting windows and call ladder', onPress: () => router.push('/admin/lead-sources'), color: '#5856D6' },
          { icon: 'link', title: 'Connect Zapier / Make', subtitle: 'Send leads from any app to a source', onPress: () => router.push('/admin/lead-connect' as any), color: '#FF4A00' },
        );
      }
      if (perm('admin', 'users')) {
        leadItems.push({ icon: 'radio-button-on', title: 'Team Availability', subtitle: 'Who is on shift, drives lead routing', onPress: () => router.push('/admin/team-availability'), color: '#34C759' });
      }
    }
    sections.push({ id: 'leads', title: 'Leads', icon: 'flame', color: '#FF3B30', items: leadItems, defaultExpanded: true } as any);
  }

  // ============================================================
  // SECTION MANAGE — right under My Brand (most-used daily section)
  // Tags, Campaigns, Reviews, Showcase — role-gated
  // Only org_admin / super_admin can manage/edit campaigns
  // ============================================================
  {
    const canManageCampaigns = !repPreview && (user?.role === 'super_admin' || user?.role === 'org_admin');
    const manageItems: (MenuItem & { permKey?: string })[] = [
      { icon: 'pricetags',  title: 'Tags',       subtitle: 'All tags: personal, account and org', onPress: () => router.push('/settings/tags'),             color: '#FF9500' },
      { icon: 'calendar',   title: 'Calendar', subtitle: 'Appointments, tasks, birthdays and sold dates', onPress: () => router.push('/dates-calendar' as any), color: '#AF52DE' },
      { icon: 'pricetags-outline', title: 'Keyword Auto-Tags', subtitle: 'Auto-tag calls and texts by keywords', onPress: () => router.push('/settings/keyword-rules' as any), color: '#5856D6' },
      { icon: 'search-circle', title: 'Keyword Search', subtitle: 'Find any word in texts and call transcripts', onPress: () => router.push('/keyword-search' as any), color: '#32ADE6' },
      { icon: 'car-sport',  title: 'Inventory',  subtitle: 'Vehicles Jessi can quote and check',   onPress: () => router.push('/inventory' as any),          color: '#32ADE6' },
      ...(canManageCampaigns ? [{ icon: 'megaphone' as any,  title: 'Campaigns',  subtitle: 'Build and manage automated campaigns', onPress: () => router.push('/campaigns' as any), color: '#FF2D55' }] : []),
      { icon: 'star',       title: 'Review Center', subtitle: 'Approve, publish and track reviews', onPress: () => router.push('/settings/review-approvals'), color: '#FFD60A' },
      { icon: 'images',     title: 'Showcase',      subtitle: 'Approve showcase entries',          onPress: () => router.push('/settings/showcase-approvals'), color: '#34C759' },
    ];
    if (isAdmin) {
      manageItems.push(
        { icon: 'cloud-download', title: 'Inventory Feed', subtitle: 'HomeNet, vAuto or catalog link, pulled hourly', onPress: () => router.push('/admin/inventory-feed' as any), color: '#32ADE6' },
        { icon: 'star-outline', title: 'Review Links', subtitle: 'Google, Facebook and Yelp links', onPress: () => router.push('/settings/review-links'), color: '#FFD60A' },
      );
    }
    sections.push({ id: 'manage', title: 'Manage', icon: 'settings-outline', color: '#8E8E93', items: manageItems });
  }



  // ============================================================
  // SECTION 2: MY TOOLS (Daily action items)
  // ============================================================
  if (perm('my_tools')) {
    const items = filterItems('my_tools', [
      { permKey: 'touchpoints', icon: 'checkbox-outline', title: "Today's Touchpoints", subtitle: 'Your daily action queue', onPress: () => router.push('/(tabs)/touchpoints' as any), color: '#C9A962' },
      { permKey: 'ask_jessi', icon: 'sparkles', title: 'Ask Jessi', subtitle: 'Your AI assistant', onPress: () => router.push('/jessie'), color: '#C9A962' },
      { permKey: 'ask_jessi', icon: 'person-circle', title: 'My VA', subtitle: 'Your AI clone — see how it sounds', onPress: () => router.push('/settings/virtual-assistant'), color: '#C9A962' },
      { permKey: 'ask_jessi', icon: 'flash', title: 'AI Follow-ups', subtitle: 'Smart outreach suggestions', onPress: () => router.push('/(tabs)/ai-outreach' as any), color: '#AF52DE' },
      { permKey: 'team_chat', icon: 'chatbox-ellipses', title: 'Team Chat', subtitle: 'Internal team messaging', onPress: () => router.push('/(tabs)/team'), color: '#5856D6' },
    ]);
    if (items.length > 0) sections.push({ id: 'my_tools', title: 'My Tools', icon: 'apps', color: '#007AFF', items });
  }

  // ============================================================
  // SECTION 3: CAMPAIGNS  (now also in Manage — keep for quick access via Campaigns tab)
  // ============================================================
  if (perm('campaigns')) {
    const items = filterItems('campaigns', [
      { permKey: 'campaign_dashboard', icon: 'speedometer', title: 'Campaign Dashboard', subtitle: 'Enrollments & performance', onPress: () => router.push('/campaigns/dashboard'), color: '#5AC8FA' },
      { permKey: 'broadcast', icon: 'megaphone', title: 'Broadcast', subtitle: 'Send to many at once', onPress: () => router.push('/broadcast'), color: '#FF9500' },
      { permKey: 'date_triggers', icon: 'calendar-outline', title: 'Date Triggers', subtitle: 'Birthdays & anniversaries', onPress: () => router.push('/settings/date-triggers'), color: '#FF9500' },
    ]);
    if (items.length > 0) sections.push({ id: 'campaigns', title: 'Campaigns', icon: 'rocket', color: '#FF2D55', items });
  }

  // ============================================================
  // SECTION 4: MY PERFORMANCE (How am I doing?)
  // ============================================================
  if (perm('insights')) {
    const items = filterItems('insights', [
      { permKey: 'my_performance', icon: 'stats-chart', title: 'My Stats', subtitle: 'Day / week / month performance', onPress: () => router.push('/touchpoints/performance' as any), color: '#34C759' },
      { permKey: 'my_performance', icon: 'trophy', title: 'Team Sales', subtitle: 'Monthly sold, referrals & repeats by rep', onPress: () => router.push('/reports/team-performance' as any), color: '#C9A962' },
      ...((!repPreview && ['super_admin', 'admin', 'manager', 'store_manager', 'org_admin'].includes(user?.role || '')) ? [
        { permKey: 'my_performance', icon: 'checkbox', title: 'Team Tasks', subtitle: 'Every open customer task per rep, overdue first', onPress: () => router.push('/team-tasks' as any), color: '#FF453A' },
      ] : []),
      { permKey: 'my_performance', icon: 'people', title: 'Customer Engagement', subtitle: 'Ranked by engagement level', onPress: () => router.push('/touchpoints/customer-performance' as any), color: '#FF9500' },
      { permKey: 'leaderboard', icon: 'podium', title: 'Leaderboard', subtitle: 'Where I stand on the team', onPress: () => router.push('/admin/leaderboard'), color: '#AF52DE' },
      { permKey: 'activity_reports', icon: 'bar-chart', title: 'Activity Reports', subtitle: 'Detailed activity analytics', onPress: () => router.push('/reports/activity'), color: '#007AFF' },
      { permKey: 'email_analytics', icon: 'trending-up', title: 'Email Analytics', subtitle: 'Opens, clicks & engagement', onPress: () => router.push('/settings/email-analytics'), color: '#FF2D55' },
      { permKey: 'system_logs', icon: 'bug-outline', title: 'System Logs', subtitle: 'Errors, warnings and diagnostics', onPress: () => router.push('/admin/system-logs'), color: '#FF3B30' },
      { permKey: 'system_logs', icon: 'alert-circle-outline', title: 'Fix Duplicate Campaigns', subtitle: 'Remove duplicate sends — run if contacts got repeat messages', color: '#FF3B30',
        onPress: async () => {
          const { showAlert } = await import('../../services/alert');
          showAlert('Fix Duplicate Campaigns', 'This will remove duplicate campaign copies and cancel any pending duplicate sends. Cannot be undone. Continue?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Fix Now', style: 'destructive', onPress: async () => {
              try {
                const apiMod = await import('../../services/api');
                const res = await apiMod.default.post('/admin/deduplicate-campaigns');
                const d = res.data;
                const { showSimpleAlert } = await import('../../services/alert');
                showSimpleAlert('Done', `Removed ${d.duplicate_campaigns_deleted} duplicates, cancelled ${d.pending_sends_cancelled} sends.`);
              } catch (e: any) {
                const { showSimpleAlert } = await import('../../services/alert');
                showSimpleAlert('Error', e?.response?.data?.detail || 'Failed');
              }
            }}
          ]);
        }
      },
      { permKey: 'system_logs', icon: 'refresh-circle-outline', title: 'Fix Sold Campaign Sequences', subtitle: 'Set campaigns to day-7+ only and auto-send mode', color: '#FF9500',
        onPress: async () => {
          const { showAlert } = await import('../../services/alert');
          showAlert('Fix Sold Campaign Sequences', 'This updates all Sold campaigns to start at day 7 (no duplicates with SOLD wizard) and enables auto-sending. Run this once on production.', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Fix Now', onPress: async () => {
              try {
                const apiMod = await import('../../services/api');
                const res = await apiMod.default.post('/admin/fix-sold-campaign-sequences');
                const d = res.data;
                const { showSimpleAlert } = await import('../../services/alert');
                showSimpleAlert('Done', `Fixed ${d.sold_campaigns_fixed} Sold campaigns. Auto-send set on ${d.other_campaigns_set_auto} others. ${d.pending_sends_set_auto} pending sends activated.`);
              } catch (e: any) {
                const { showSimpleAlert } = await import('../../services/alert');
                showSimpleAlert('Error', e?.response?.data?.detail || 'Failed');
              }
            }}
          ]);
        }
      },
      { permKey: 'my_performance', icon: 'pulse', title: 'SEO Health', subtitle: 'Your online visibility score', onPress: () => router.push('/seo-health'), color: '#30D158' },
      { permKey: 'geo_health', icon: 'brain', title: 'GEO Health', subtitle: 'Your AI citation score — ChatGPT, Gemini, Perplexity', onPress: () => router.push('/geo-health'), color: '#AF52DE' },
      { permKey: 'va_library', icon: 'person-circle', title: 'VA Library', subtitle: 'Build and manage named Virtual Assistant personas', onPress: () => router.push('/admin/va-library'), color: '#C9A962' },
    ]);
    if (items.length > 0) sections.push({ id: 'performance', title: 'My Performance', icon: 'stats-chart', color: '#34C759', items });
  }

  // ============================================================
  // SECTION 5: SETUP (Admin/Manager tools for their accounts)
  // Only visible to admins, store managers, partners
  // ============================================================
  if (isAdmin && perm('admin')) {
    const items: (MenuItem & { permKey?: string })[] = [
      { permKey: 'store_profile', icon: 'storefront-outline', title: 'Store Profile', subtitle: 'Logo, address & store info', onPress: () => router.push('/settings/store-profile' as any), color: '#34C759' },
      { permKey: 'brand_kit', icon: 'color-palette', title: 'Brand Kit', subtitle: 'Email branding & colors', onPress: () => router.push('/settings/brand-kit'), color: '#AF52DE' },
      { permKey: 'brand_kit', icon: 'chatbubbles', title: 'Messaging Channels', subtitle: 'SMS, WhatsApp, Messenger & more', onPress: () => router.push('/settings/messaging-channels'), color: '#25D366' },
      { permKey: 'notifications', icon: 'notifications', title: 'SMS Notifications', subtitle: 'Active conversations & You\'re Needed alerts', onPress: () => router.push('/settings/notifications'), color: '#FF9500' },
      { permKey: 'admin', icon: 'call', title: 'Phone Numbers', subtitle: 'Twilio inventory & billing', onPress: () => router.push('/admin/twilio-numbers'), color: '#34C759' },
      { permKey: 'users', icon: 'people', title: 'Team Members', subtitle: 'Manage users & permissions', onPress: () => router.push('/admin/users'), color: '#007AFF' },
      { permKey: 'invite_team', icon: 'person-add', title: 'Invite Team', subtitle: 'Send invitations', onPress: () => router.push('/settings/invite-team'), color: '#C9A962' },
      { permKey: 'integrations', icon: 'git-network', title: 'Integrations', subtitle: 'API keys & webhooks', onPress: () => router.push('/settings/integrations'), color: '#5856D6' },
    ];
    const filtered = items.filter(i => !i.permKey || perm('admin', i.permKey));
    if (filtered.length > 0) sections.push({ id: 'setup_manage', title: 'Set Up', icon: 'construct', color: '#FF9500', items: filtered });
  }

  // ============================================================
  // SECTION 6: ACCOUNT MANAGEMENT (Partners/Super Admins — multi-account management)
  // For people managing MULTIPLE organizations/accounts
  // ============================================================
  if (isSuperAdmin || isPartner) {
    const items: MenuItem[] = [
      { icon: 'rocket', title: 'Onboarding Hub', subtitle: 'Create & onboard new accounts', onPress: () => router.push('/admin/onboarding-hub' as any), color: '#C9A962' },
      { icon: 'pulse', title: 'Account Health', subtitle: 'Retention dashboard & reports', onPress: () => router.push('/admin/account-health' as any), color: '#00C7BE' },
      ...(isSuperAdmin ? [
        { icon: 'shield-checkmark', title: 'Admin Dashboard', subtitle: 'System overview & activity', onPress: () => router.push('/admin'), color: '#34C759' },
      ] : []),
      { icon: 'business', title: 'Organizations', subtitle: 'Manage organizations', onPress: () => router.push('/admin/organizations'), color: '#007AFF' },
      { icon: 'storefront', title: 'Accounts', subtitle: 'Store accounts', onPress: () => router.push('/admin/stores'), color: '#34C759' },
      { icon: 'people', title: 'All Users', subtitle: 'Cross-org user management', onPress: () => router.push('/admin/users'), color: '#FF9500' },
      ...(isSuperAdmin ? [
        { icon: 'person', title: 'Individuals', subtitle: 'Independent users', onPress: () => router.push('/admin/individuals'), color: '#AF52DE' },
        { icon: 'person-add', title: 'Pending Users', subtitle: 'Approve new signups', onPress: () => router.push('/admin/pending-users'), color: '#FF3B30' },
      ] : []),
      { icon: 'podium', title: 'Leaderboard', subtitle: 'Performance across all accounts', onPress: () => router.push('/admin/leaderboard'), color: '#AF52DE' },
      { icon: 'pulse', title: 'Activity Feed', subtitle: 'Team activity across accounts', onPress: () => router.push('/(tabs)/activity-feed' as any), color: '#5856D6' },
      ...(isSuperAdmin ? [
        { icon: 'analytics', title: 'iMOS Website Leads', subtitle: 'Demo requests and referrals for iMOS itself, not dealership leads', onPress: () => router.push('/admin/lead-tracking'), color: '#C9A962' },
        { icon: 'flame', title: 'iMOS Hot Leads', subtitle: 'New demo requests from the iMOS website', onPress: () => router.push('/admin/hot-leads'), color: '#FF3B30' },
      ] : []),
    ];
    sections.push({ id: 'account_mgmt', title: 'Account Management', icon: 'briefcase', color: '#007AFF', items });
  }

  // ============================================================
  // SECTION 7: INTERNAL OPERATIONS (Super Admin only — revenue, partners, system)
  // ============================================================
  if (isSuperAdmin) {
    const items: MenuItem[] = [
      // Partners
      { icon: 'people-circle', title: 'Partner Portal', subtitle: 'View as partner/reseller', onPress: () => router.push('/partner/dashboard' as any), color: '#007AFF' },
      { icon: 'document-text', title: 'Partner Agreements', subtitle: 'Contracts & commissions', onPress: () => router.push('/admin/partner-agreements'), color: '#AF52DE' },
      { icon: 'color-palette', title: 'White Label Partners', subtitle: 'Manage branded partners', onPress: () => router.push('/admin/white-label'), color: '#E87722' },
      // Revenue
      { icon: 'card', title: 'Billing & Revenue', subtitle: 'Payments, MRR & commissions', onPress: () => router.push('/admin/billing'), color: '#34C759' },
      { icon: 'trending-up', title: 'Revenue Forecast', subtitle: 'Sales projections', onPress: () => router.push('/admin/forecasting'), color: '#007AFF' },
      { icon: 'documents', title: 'View Quotes', subtitle: 'Subscription quotes', onPress: () => router.push('/admin/quotes'), color: '#30B0C7' },
      { icon: 'receipt', title: 'Create Quote', subtitle: 'Generate new quote', onPress: () => router.push('/admin/create-quote'), color: '#34C759' },
      { icon: 'ticket', title: 'Discount Codes', subtitle: 'Promo codes', onPress: () => router.push('/admin/discount-codes'), color: '#5856D6' },
      // System
      { icon: 'call', title: 'Phone Assignments', subtitle: 'Twilio numbers', onPress: () => router.push('/admin/phone-assignments'), color: '#32ADE6' },
      { icon: 'mail', title: 'Shared Inboxes', subtitle: 'Phone number users', onPress: () => router.push('/admin/shared-inboxes'), color: '#007AFF' },
      { icon: 'swap-horizontal', title: 'Bulk Transfer', subtitle: 'Transfer contacts between users', onPress: () => router.push('/admin/bulk-transfer'), color: '#FF3B30' },
      { icon: 'map-outline', title: 'App Directory', subtitle: 'Browse & share pages', onPress: () => router.push('/admin/app-directory'), color: '#5AC8FA' },
      // Docs & Assets
      { icon: 'library', title: 'Company Docs', subtitle: 'Policies & procedures', onPress: () => router.push('/admin/docs'), color: '#5856D6' },
      { icon: 'color-palette', title: 'Brand Assets', subtitle: 'Logos & downloads', onPress: () => router.push('/admin/brand-assets'), color: '#FF9500' },
      // Diagnostics
      { icon: 'bug', title: 'Error Reports', subtitle: 'App crashes & error logs', onPress: () => router.push('/admin/error-reports' as any), color: '#FF3B30' },
      { icon: 'chatbox-ellipses', title: 'Bug Reports', subtitle: 'User-submitted issues & feedback', onPress: () => router.push('/admin/bug-reports' as any), color: '#FF9500' },
    ];
    sections.push({ id: 'internal_ops', title: 'Internal Operations', icon: 'lock-closed', color: '#8E8E93', items });
  }

  // ============================================================
  // SECTION 8: LEARNING (Training & SOPs — visible to everyone)
  // ============================================================
  if (perm('my_tools', 'training_hub')) {
    const items: MenuItem[] = [
      { icon: 'school', title: 'Training Hub', subtitle: 'Learn the platform', onPress: () => router.push('/training-hub'), color: '#FF9500' },
    ];
    if (isSuperAdmin) {
      items.push({ icon: 'book', title: 'SOPs & Guides', subtitle: 'Step-by-step procedures', onPress: () => router.push('/admin/sops'), color: '#5856D6' });
      items.push({ icon: 'create', title: 'Manage Training', subtitle: 'Edit lessons & tracks', onPress: () => router.push('/admin/manage-training'), color: '#34C759' });
      items.push({ icon: 'analytics', title: 'Training Report', subtitle: 'Video engagement analytics', onPress: () => router.push('/admin/training-reports'), color: '#AF52DE' });
    }
    sections.push({ id: 'learning', title: 'Learning', icon: 'school', color: '#FF9500', items });
  }

  // ============================================================
  // SECTION 9: SETTINGS (Minimal personal settings)
  // ============================================================
  sections.push({
    id: 'settings',
    title: 'Settings',
    icon: 'settings',
    color: colors.textSecondary,
    items: [
      { icon: 'shield-checkmark', title: 'Security', subtitle: 'Passwords & Face ID', onPress: () => router.push('/settings/security'), color: '#FF3B30' },
      // Notification preferences — visible to ALL users so everyone can control SMS vs Push
      { icon: 'chatbubble-ellipses-outline', title: 'Notification Preferences', subtitle: 'SMS alerts, push delivery & quiet times', onPress: () => router.push('/settings/notifications'), color: '#FF9500' },
      { icon: 'time-outline', title: 'My Schedule', subtitle: 'Work hours & notification quiet times', onPress: () => router.push('/settings/schedule'), color: '#34C759' },
      { icon: 'calendar-outline', title: 'Calendar Sync', subtitle: 'Connect Google or Apple calendar', onPress: () => router.push('/settings/calendar'), color: '#007AFF' },
      { icon: 'help-circle-outline', title: 'Help Center', subtitle: 'How-to guides & FAQs', onPress: () => router.push('/help' as any), color: '#007AFF' },
      { icon: 'bug-outline', title: 'Report a Bug', subtitle: 'Flag an issue or share feedback', onPress: () => router.push('/report-bug' as any), color: '#FF3B30' },
      ...(pushSupported ? [{
        icon: 'notifications-outline' as string,
        title: 'Push Notifications',
        subtitle: pushStatus === 'granted' ? 'On — leads, messages & tasks' : pushStatus === 'denied' ? 'Blocked — tap to open Settings' : 'Get alerts for leads & messages',
        color: '#FF9500' as string,
        statusDot: (pushStatus === 'granted' ? 'green' : pushStatus === 'denied' ? 'red' : 'grey') as 'green' | 'red' | 'grey',
        onPress: async () => {
          if (pushStatus === 'granted') {
            if (Platform.OS !== 'web') {
              showSimpleAlert('Notifications On', 'Push notifications are enabled. To disable, go to iOS Settings → Im On Social → Notifications.');
            } else {
              await disablePush();
              showSimpleAlert('Notifications Off', 'Push notifications have been disabled.');
            }
          } else if (pushStatus === 'denied') {
            showSimpleAlert('Notifications Blocked', 'Push notifications were blocked. Go to iOS Settings → Im On Social → Notifications and enable them.');
          } else {
            const ok = await enablePush();
            if (ok) showSimpleAlert('Notifications Enabled!', "You'll now receive alerts for new leads, customer replies, and your daily touchpoints.");
            else if (pushStatus !== 'denied') showSimpleAlert('Not Enabled', 'Could not enable notifications. Check your device settings.');
          }
        },
      }] : []),
    ],
  });

  // allSections is now just 'sections' since admin is inline
  const allSections = sections;

  // ── Hub simplification: split everyday vs admin, brand lives in My Profile ──
  const ADMIN_SECTION_IDS = ['setup_manage', 'account_mgmt', 'internal_ops'];
  const adminSections = allSections.filter(s => ADMIN_SECTION_IDS.includes(s.id));
  const everydaySections = allSections.filter(s => !ADMIN_SECTION_IDS.includes(s.id) && s.id !== 'my_brand');
  const brandSectionRef: any = allSections.find(s => s.id === 'my_brand');

  // Flat search index across EVERYTHING (incl. admin + brand + profile)
  const searchIndex: MenuItem[] = [
    { icon: 'person', title: 'My Profile', subtitle: 'Your info & public pages', color: '#C9A962', onPress: () => router.push('/my-profile' as any) },
    ...((brandSectionRef?._brandItems || []).map((b: any) => ({
      icon: b.icon, title: b.title, subtitle: b.subtitle, color: b.color,
      onPress: () => b.editRoute && router.push(b.editRoute as any),
    }))),
    ...allSections.flatMap(s => s.items),
  ];
  const hubQ = hubSearch.trim().toLowerCase();
  const seenTitles = new Set<string>();
  const searchResults = hubQ
    ? searchIndex.filter(i => {
        if (seenTitles.has(i.title)) return false;
        const hit = i.title.toLowerCase().includes(hubQ) || i.subtitle.toLowerCase().includes(hubQ);
        if (hit) seenTitles.add(i.title);
        return hit;
      })
    : [];

  // Big "What do you want to do?" task tiles
  const taskGrid = [
    { icon: 'flame', label: 'Internet Leads', sub: 'Incoming lead queue', color: '#FF3B30', route: '/leads', badge: leadsWaiting },
    { icon: 'megaphone', label: 'Send a Blast', sub: 'Mass text', color: '#FF9500', route: '/broadcast/new' },
    { icon: 'id-card', label: 'Share My Card', sub: 'Text your card', color: '#C9A962', route: '/quick-send/digitalcard' },
    { icon: 'star', label: 'Get Reviews', sub: 'Send review link', color: '#FFD60A', route: '/quick-send/review' },
    { icon: 'stats-chart', label: 'My Numbers', sub: 'How am I doing?', color: '#34C759', route: '/touchpoints/performance' },
    { icon: 'car-sport', label: 'Inventory', sub: 'What\'s on the lot', color: '#AF52DE', route: '/inventory' },
  ];

  // ── App grid catalog: every section becomes a folder, favourites sit loose on the home grid ──
  const FOLDER_FOR: Record<string, string> = { account_mgmt: 'admin', internal_ops: 'admin', setup_manage: 'setup' };
  const hubFolderDefs: HubFolderDef[] = [];
  const seenFolder = new Set<string>();
  const hubApps: HubApp[] = [];
  const seenApp = new Set<string>();
  const pushApp = (a: HubApp) => { if (!seenApp.has(a.id)) { seenApp.add(a.id); hubApps.push(a); } };
  for (const sec of allSections) {
    const fid = FOLDER_FOR[sec.id] || sec.id;
    if (!seenFolder.has(fid)) {
      seenFolder.add(fid);
      hubFolderDefs.push(fid === 'admin' ? { id: 'admin', title: 'Admin', icon: 'shield-half', color: '#FF3B30' } : fid === 'setup' ? { id: 'setup', title: 'Set Up', icon: 'construct', color: '#FF9500' } : { id: sec.id, title: sec.title, icon: sec.icon, color: sec.color });
    }
    for (const b of ((sec as any)._brandItems || []) as any[]) {
      pushApp({ id: hubSlug(b.title), title: b.title, subtitle: b.subtitle, icon: b.icon, color: b.color, folder: fid, onPress: () => b.editRoute && router.push(b.editRoute as any) });
    }
    for (const it of sec.items as any[]) {
      pushApp({ id: hubSlug(it.title), title: it.title, subtitle: it.subtitle, icon: it.icon, color: it.color, badge: it.badge, statusDot: it.statusDot, folder: fid, onPress: () => { trackVisit({ title: it.title, icon: it.icon, color: it.color, subtitle: it.subtitle }); it.onPress(); } });
    }
  }
  for (const t of taskGrid) {
    pushApp({ id: hubSlug(t.label), title: t.label, subtitle: t.sub, icon: t.icon, color: t.color, badge: (t as any).badge, folder: 'my_tools', onPress: () => router.push(t.route as any) });
  }
  if (!seenFolder.has('my_tools')) hubFolderDefs.push({ id: 'my_tools', title: 'My Tools', icon: 'apps', color: '#007AFF' });
  const hubDefaultLoose = taskGrid.map(t => hubSlug(t.label));

  function openExternal(url: string) {
    // Append self_preview=1 so tracking ignores salesperson viewing their own page
    const sep = url.includes('?') ? '&' : '?';
    const u = `${url}${sep}self_preview=1`;
    if (Platform.OS === 'web') window.open(u, '_blank');
    else Linking.openURL(u);
  }

  function shareLink(url: string, label: string) {
    if (Platform.OS === 'web') {
      copyToClipboard(url);
      showSimpleAlert('Copied!', `${label} link copied to clipboard`);
    } else {
      Share.share(Platform.OS === 'ios' ? { url } : { message: url });
    }
  }

  // ── Brand card render ──
  const renderBrandItem = (item: { icon: string; title: string; subtitle: string; color: string; publicUrl: string | null; editRoute?: string }, index: number) => (
    <TouchableOpacity
      key={`brand-${index}`}
      onPress={() => item.editRoute && router.push(item.editRoute as any)}
      activeOpacity={0.7}
      style={[styles.menuItemCard, { backgroundColor: colors.surface }]}
    >
      <View style={[styles.menuIcon, { backgroundColor: `${item.color}20` }]}>
        <Ionicons name={item.icon as any} size={20} color={item.color} />
      </View>
      <View style={styles.menuContent}>
        <Text style={[styles.menuTitle, { color: colors.text }]} numberOfLines={1}>{item.title}</Text>
        <Text style={[styles.menuSubtitle, { color: colors.textSecondary }]} numberOfLines={1}>{item.subtitle}</Text>
        <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
          {item.publicUrl && (
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: item.color + '20' }}
              onPress={(e: any) => { e?.stopPropagation?.(); openExternal(item.publicUrl!); }}
            >
              <Ionicons name="eye-outline" size={12} color={item.color} />
              <Text style={{ fontSize: 12, fontWeight: '700', color: item.color }}>View</Text>
            </TouchableOpacity>
          )}
          {item.publicUrl && (
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: colors.card }}
              onPress={(e: any) => { e?.stopPropagation?.(); shareLink(item.publicUrl!, item.title); }}
            >
              <Ionicons name="share-outline" size={12} color={colors.textSecondary} />
              <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>Share</Text>
            </TouchableOpacity>
          )}
          {item.publicUrl && (
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: '#FF9500' + '18', borderWidth: 1, borderColor: '#FF9500' + '30' }}
              onPress={(e: any) => {
                e?.stopPropagation?.();
                // Route to the full quick-send flow — has real contact search, tag picker, campaigns
                const route = item.title.toLowerCase().includes('digital card') ? 'digitalcard'
                  : item.title.toLowerCase().includes('link page') ? 'linkpage'
                  : item.title.toLowerCase().includes('landing') ? 'landingpage'
                  : item.title.toLowerCase().includes('showcase') ? 'showcase'
                  : item.title.toLowerCase().includes('review') ? 'review'
                  : 'digitalcard';
                router.push(`/quick-send/${route}` as any);
              }}
            >
              <Ionicons name="pricetag-outline" size={12} color="#FF9500" />
              <Text style={{ fontSize: 12, fontWeight: '600', color: '#FF9500' }}>Send + Tag</Text>
            </TouchableOpacity>
          )}
          {item.editRoute && (
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: colors.card }}
              onPress={(e: any) => { e?.stopPropagation?.(); router.push(item.editRoute as any); }}
            >
              <Ionicons name="create-outline" size={12} color={colors.textSecondary} />
              <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>Edit</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
      <TouchableOpacity
        onPress={(e: any) => { e?.stopPropagation?.(); togglePin({ title: item.title, icon: item.icon, color: item.color, subtitle: item.subtitle }); }}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        style={styles.pinButton}
      >
        <Ionicons name={isPinned(item.title) ? 'bookmark' : 'bookmark-outline'} size={16}
          color={isPinned(item.title) ? item.color : colors.textTertiary} />
      </TouchableOpacity>
    </TouchableOpacity>
  );

  const renderMenuItem = (item: MenuItem, index: number) => (
    <TouchableOpacity
      key={`${item.title}-${index}`}
      style={[styles.menuItemCard, { backgroundColor: colors.surface }]}
      onPress={() => {
        trackVisit({ title: item.title, icon: item.icon, color: item.color, subtitle: item.subtitle });
        item.onPress();
      }}
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
      {item.statusDot && (
        <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: item.statusDot === 'green' ? '#34C759' : item.statusDot === 'red' ? '#FF3B30' : '#8E8E93', marginRight: 8 }} />
      )}
      <TouchableOpacity
        onPress={(e) => {
          e.stopPropagation?.();
          togglePin({ title: item.title, icon: item.icon, color: item.color, subtitle: item.subtitle });
        }}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        style={styles.pinButton}
        data-testid={`pin-${item.title.toLowerCase().replace(/\s+/g, '-')}`}
      >
        <Ionicons
          name={isPinned(item.title) ? 'bookmark' : 'bookmark-outline'}
          size={16}
          color={isPinned(item.title) ? item.color : colors.textTertiary}
        />
      </TouchableOpacity>
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
          {section.id === 'leads' && leadsWaiting > 0 && (
            <View style={[styles.countPill, { backgroundColor: '#FF3B30' }]} data-testid="section-leads-waiting-badge">
              <Text style={[styles.countPillText, { color: '#FFF' }]}>{leadsWaiting > 99 ? '99+' : leadsWaiting} waiting</Text>
            </View>
          )}
          <View style={[styles.countPill, { backgroundColor: colors.surface }]}>
            <Text style={[styles.countPillText, { color: colors.textSecondary }]}>{itemCount + (((section as any)._brandItems || []).length)}</Text>
          </View>
          <Ionicons 
            name={isExpanded ? 'chevron-up' : 'chevron-down'} 
            size={20} 
            color={colors.textSecondary} 
          />
        </TouchableOpacity>
        
        {/* Indented Child Item Cards */}
        {isExpanded && (section as any)._brandItems && (section as any)._brandItems.map((item: any, index: number) =>
          renderBrandItem(item, index)
        )}
        {isExpanded && section.items.map((item, index) => 
          renderMenuItem(item, index)
        )}
      </View>
    );
  };
  
  return (
    <>
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <ScrollView ref={scrollRef} contentContainerStyle={styles.scrollContent} scrollEnabled={!hubDragging}>
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

        {/* ── Profile Setup Banner — shown until photo + bio are complete ── */}
        {(() => {
          // Suppress banner if impersonating (either store flag or user flag after refresh)
          const isImp = isImpersonating || (user as any)?.isImpersonating === true;
          if (isImp) return null;
          const hasPhoto = !!(user?.photo_url || (user as any)?.photo_path);
          const hasBio   = !!((user as any)?.persona?.bio || (user as any)?.bio);
          const complete  = (user as any)?.onboarding_complete === true || (hasPhoto && hasBio);
          if (complete) return null;
          const missing = [!hasPhoto && 'profile photo', !hasBio && 'bio'].filter(Boolean);
          return (
            <TouchableOpacity
              style={styles.onboardingBanner}
              onPress={() => router.push('/profile-setup')}
              activeOpacity={0.92}
              data-testid="profile-setup-banner"
            >
              {/* Gold accent bar */}
              <View style={styles.onboardingAccent} />
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <Ionicons name="sparkles" size={18} color="#C9A962" />
                  <Text style={styles.onboardingTitle}>Set Up Your Profile First</Text>
                </View>
                <Text style={styles.onboardingBody}>
                  Your profile powers your Digital Card, Showcase, Link Page, and Landing Page — everything customers see about you. Take 2 minutes to make it shine.
                </Text>
                {missing.length > 0 && (
                  <View style={styles.onboardingChecklist}>
                    {!hasPhoto && (
                      <View style={styles.onboardingCheckRow}>
                        <Ionicons name="camera-outline" size={15} color="#FF9500" />
                        <Text style={styles.onboardingCheckText}>Add a profile photo</Text>
                      </View>
                    )}
                    {!hasBio && (
                      <View style={styles.onboardingCheckRow}>
                        <Ionicons name="document-text-outline" size={15} color="#FF9500" />
                        <Text style={styles.onboardingCheckText}>Write your bio</Text>
                      </View>
                    )}
                  </View>
                )}
                <View style={styles.onboardingCTA}>
                  <Text style={styles.onboardingCTAText}>Complete My Profile</Text>
                  <Ionicons name="arrow-forward" size={16} color="#000" />
                </View>
              </View>
            </TouchableOpacity>
          );
        })()}

        {/* ── Top: search first, bell beside it ── */}
        <View style={styles.hubTopRow}>
          <View style={[styles.hubSearchBar, { flex: 1, backgroundColor: colors.card, borderColor: hubQ ? '#C9A962' : colors.border }]}>
            <Ionicons name="search" size={17} color={hubQ ? '#C9A962' : colors.textSecondary} />
            <TextInput
              style={[styles.hubSearchInput, { color: colors.text }]}
              placeholder="Search anything… broadcast, reviews, tags"
              placeholderTextColor={colors.textTertiary}
              value={hubSearch}
              onChangeText={setHubSearch}
              autoCapitalize="none"
              data-testid="hub-search-input"
            />
            {hubSearch.length > 0 && (
              <TouchableOpacity onPress={() => setHubSearch('')} data-testid="hub-search-clear">
                <Ionicons name="close-circle" size={17} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
          </View>
          <View style={[styles.hubBell, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <NotificationBell />
          </View>
        </View>

        {/* ── Compact profile strip: who you are + the two things you touch most ── */}
        <View style={[styles.profileStrip, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <TouchableOpacity
            style={styles.profileStripIdentity}
            onPress={() => router.push('/my-profile' as any)}
            activeOpacity={0.8}
            data-testid="profile-card"
          >
            {(user as any)?.photo_url ? (
              <ExpoImage
                source={{ uri: resolveUserPhotoUrlHiRes(user as any) || '' }}
                style={styles.stripAvatar}
                contentFit="cover"
                placeholder={null}
              />
            ) : (
              <View style={[styles.stripAvatar, { backgroundColor: '#C9A96222', alignItems: 'center', justifyContent: 'center' }]}>
                <Text style={{ fontSize: 16, fontWeight: '800', color: '#C9A962' }}>
                  {user?.name?.split(' ').map((n: string) => n[0]).join('').toUpperCase() || '?'}
                </Text>
              </View>
            )}
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={[styles.stripName, { color: colors.text }]} numberOfLines={1}>{user?.name || 'Guest'}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                {(user as any)?.persona?.title || (user as any)?.title ? (
                  <Text style={styles.stripTitle} numberOfLines={1}>
                    {(user as any)?.persona?.title || (user as any)?.title}
                  </Text>
                ) : (
                  <Text style={[styles.stripTitle, { color: colors.textTertiary }]} numberOfLines={1}>{user?.email || ''}</Text>
                )}
              </View>
            </View>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.stripPill}
            onPress={() => router.push('/my-profile' as any)}
            activeOpacity={0.8}
            data-testid="edit-profile-hint-btn"
          >
            <Ionicons name="person" size={14} color="#C9A962" />
            <Text style={styles.stripPillText}>Profile</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.stripPill}
            onPress={() => router.push('/settings/virtual-assistant')}
            activeOpacity={0.8}
            data-testid="virtual-assistant-btn"
          >
            <Ionicons name="person-circle" size={14} color="#C9A962" />
            <Text style={styles.stripPillText}>My VA</Text>
          </TouchableOpacity>
        </View>

        {/* ── Rep Preview banner / toggle ── */}
        {repPreview && (
          <TouchableOpacity
            onPress={() => setRepPreview(false)}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginBottom: 8, backgroundColor: '#C9A96220', borderWidth: 1.5, borderColor: '#C9A962', borderRadius: 12, padding: 12 }}
            data-testid="rep-preview-banner"
          >
            <Ionicons name="eye" size={16} color="#C9A962" />
            <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: '#C9A962' }}>
              Rep Preview — this is what your reps see. Tap to exit.
            </Text>
            <Ionicons name="close" size={16} color="#C9A962" />
          </TouchableOpacity>
        )}
        {reallyAdmin && !repPreview && (
          <TouchableOpacity
            onPress={() => setRepPreview(true)}
            style={{ flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-end', gap: 4, marginRight: 16, marginTop: -2, marginBottom: 2, paddingVertical: 4, paddingHorizontal: 6 }}
            data-testid="rep-preview-toggle"
          >
            <Ionicons name="eye-outline" size={12} color={colors.textTertiary} />
            <Text style={{ fontSize: 11, fontWeight: '600', color: colors.textTertiary }}>View as Rep</Text>
          </TouchableOpacity>
        )}

        {hubQ ? (
          /* ── Search results ── */
          <View style={{ marginTop: 4 }} data-testid="hub-search-results">
            {searchResults.length === 0 ? (
              <Text style={{ fontSize: 13, color: colors.textTertiary, textAlign: 'center', marginTop: 24 }}>
                Nothing found for &quot;{hubSearch.trim()}&quot;
              </Text>
            ) : (
              searchResults.slice(0, 20).map((item, index) => renderMenuItem(item, index))
            )}
          </View>
        ) : (
        <>
        <AppHome
          apps={hubApps}
          folderDefs={hubFolderDefs}
          defaultLoose={hubDefaultLoose}
          userId={String(user?._id || 'anon')}
          remoteLayout={(user as any)?.hub_layout || null}
          colors={colors}
          onDragging={setHubDragging}
        />
        </>
        )}
        
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
                <Text style={[styles.version, { fontSize: 16, fontWeight: '700', color: partnerBranding.primary_color }]}>{partnerBranding.name}</Text>
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

    </SafeAreaView>

    </>
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
    fontSize: 16,
    fontWeight: '800',
  },
  partnerName: {
    fontSize: 16,
    fontWeight: '700',
  },
  partnerPowered: {
    fontSize: 13,
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
    paddingBottom: 0,
    width: '100%',
  },
  header: {
    padding: 16,
  },
  title: {
    fontSize: 28,
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
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  impersonationSubtitle: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  // Onboarding setup banner
  onboardingBanner: {
    marginHorizontal: 16,
    marginBottom: 12,
    marginTop: 4,
    borderRadius: 16,
    backgroundColor: '#1A1400',
    borderWidth: 1,
    borderColor: '#C9A96240',
    overflow: 'hidden',
    flexDirection: 'row',
    padding: 16,
    gap: 0,
  },
  onboardingAccent: {
    width: 4,
    borderRadius: 2,
    backgroundColor: '#C9A962',
    marginRight: 14,
    alignSelf: 'stretch',
  },
  onboardingTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#C9A962',
  },
  onboardingBody: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.75)',
    lineHeight: 20,
    marginBottom: 10,
  },
  onboardingChecklist: {
    gap: 6,
    marginBottom: 12,
  },
  onboardingCheckRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  onboardingCheckText: {
    fontSize: 13,
    color: '#FF9500',
    fontWeight: '600',
  },
  onboardingCTA: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#C9A962',
    alignSelf: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  onboardingCTAText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#000',
  },
  profileCardContainer: {
    marginHorizontal: 16,
    marginBottom: 16,
    zIndex: 10000,
  },
  profileCard: {
    height: 160,
    borderRadius: 18,
    overflow: 'hidden',
    position: 'relative',
    justifyContent: 'flex-end',
  },
  profileCardBell: {
    position: 'absolute',
    top: 12,
    right: 12,
    zIndex: 10,
  },
  profileCardBottom: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 16,
    paddingTop: 0,
  },
  profileActions: {
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    marginLeft: 4,
  },
  profileActionIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileCardHint: {
    marginTop: 8,
  },
  editProfileBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    paddingVertical: 11,
    borderRadius: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: '#C9A96240',
  },
  editProfileBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#C9A962',
  },
  profileCardHintText: {
    fontSize: 13,
  },
  profileAvatarContainer: {
    position: 'relative',
    marginRight: 14,
  },
  profileAvatar: {
    width: 56,
    height: 56,
    borderRadius: 14,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#C9A962',
  },
  profileAvatarImage: {
    width: 56,
    height: 56,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: '#C9A962',
  },
  profileAvatarText: {
    color: colors.text,
    fontSize: 20,
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
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    textAlign: 'center',
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 1,
    letterSpacing: 0.2,
    textShadowColor: 'rgba(0,0,0,0.5)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  profileTitle: {
    fontSize: 12,
    color: '#C9A962',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 2,
  },
  profileEmail: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.7)',
  },
  // Recently Visited
  recentSection: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  recentLabel: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase' as const,
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  recentRow: {
    flexDirection: 'row' as const,
    gap: 8,
    flexWrap: 'wrap' as const,
  },
  recentChip: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 10,
    gap: 8,
    flex: 1,
    minWidth: '45%' as any,
    maxWidth: '48%' as any,
  },
  recentChipIcon: {
    width: 28,
    height: 28,
    borderRadius: 7,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
  },
  recentChipText: {
    fontSize: 15,
    fontWeight: '500' as const,
    flex: 1,
  },
  pinButton: {
    padding: 4,
    marginRight: 4,
  },
  // Section Wrapper
  sectionWrapper: {
    marginHorizontal: 16,
    marginBottom: 8,
    alignItems: 'stretch',
  },
  // ── Hub search + task grid (simplified hub) ──
  hubSearchWrap: { paddingHorizontal: 16, marginTop: 4, marginBottom: 4 },
  hubTopRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, marginTop: 4, marginBottom: 10 },
  hubBell: { width: 46, height: 46, borderRadius: 14, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  profileStrip: { flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginBottom: 6, padding: 10, borderRadius: 16, borderWidth: 1 },
  profileStripIdentity: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10, minWidth: 0 },
  stripAvatar: { width: 44, height: 44, borderRadius: 12, borderWidth: 1.5, borderColor: '#C9A962' },
  stripName: { fontSize: 16, fontWeight: '800' },
  stripTitle: { fontSize: 11, fontWeight: '700', color: '#C9A962', letterSpacing: 0.6, textTransform: 'uppercase', marginTop: 1, flexShrink: 1 },
  stripPill: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, height: 34, borderRadius: 17, backgroundColor: '#C9A96218', borderWidth: 1, borderColor: '#C9A96266' },
  stripPillText: { fontSize: 12, fontWeight: '700', color: '#C9A962' },
  hubSearchBar: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12, borderWidth: 1.5 },
  hubSearchInput: { flex: 1, fontSize: 15, padding: 0 },
  taskGridLabel: { fontSize: 12, fontWeight: '700', color: '#C9A962', letterSpacing: 0.8, textTransform: 'uppercase', marginHorizontal: 16, marginTop: 14, marginBottom: 10 },
  taskGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingHorizontal: 16, marginBottom: 16 },
  taskTile: { width: '48%', flexGrow: 1, borderRadius: 16, borderWidth: 1.5, padding: 14, gap: 8 },
  taskTileIcon: { width: 42, height: 42, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  taskTileLabel: { fontSize: 15, fontWeight: '700' },
  taskTileSub: { fontSize: 12, marginTop: -4 },
  countPill: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2, marginRight: 8 },
  countPillText: { fontSize: 11, fontWeight: '700' },
  adminSubLabel: { fontSize: 12, fontWeight: '700', letterSpacing: 0.8, marginTop: 10, marginBottom: 6, marginLeft: 4 },
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
    fontWeight: '700',
    flex: 1,
  },
  // Indented child item card
  menuItemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-start',
    borderRadius: 10,
    padding: 12,
    paddingLeft: 12,
    marginBottom: 6,
    marginLeft: 16,
    marginRight: 0,
    alignSelf: 'stretch' as any,
    minWidth: 0,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    flexShrink: 0,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 1,
  },
  menuSubtitle: {
    fontSize: 13,
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
    fontSize: 12,
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
    fontSize: 13,
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
    fontSize: 16,
    fontWeight: '600',
  },
  themeToggleSub: {
    fontSize: 13,
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
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
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
    fontSize: 13,
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
    fontSize: 10,
    fontWeight: '800',
    color: colors.text,
  },
  editActionLabel: {
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
    paddingHorizontal: 2,
  },
});

