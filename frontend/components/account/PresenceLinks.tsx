/**
 * PresenceLinks.tsx — All personal presence assets in one component.
 *
 * Renders: Digital Card, Showcase, Review Link, Link Page,
 *          Landing Page, Templates, Card Templates, Email Signature
 *
 * Parent passes user + routing context. This component owns
 * the copied-link state and copy-to-clipboard logic.
 */

import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Platform, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showSimpleAlert } from '../../services/alert';
import { Avatar } from '../Avatar';
import { resolveUserPhotoUrl } from '../../utils/photoUrl';
import { PresenceCard } from './PresenceCard';

const PROD_BASE = 'https://app.imonsocial.com';

// Append self_preview=1 so the backend skips tracking when the user views their own page
function openUrl(url: string) {
  const separator = url.includes('?') ? '&' : '?';
  const previewUrl = `${url}${separator}self_preview=1`;
  if (Platform.OS === 'web') window.open(previewUrl, '_blank');
  else Linking.openURL(previewUrl);
}

function copyToClipboard(url: string, label: string) {
  if (Platform.OS === 'web' && navigator.clipboard) {
    navigator.clipboard.writeText(url);
    showSimpleAlert('Copied!', `${label} copied to clipboard`);
  }
}

interface Props {
  user: any;
  colors: Record<string, string>;
  storeSlug: string | null;
  onOpenShareModal: () => void;
  onPreviewReview: () => void;
}

export function PresenceLinks({ user, colors, storeSlug, onOpenShareModal, onPreviewReview }: Props) {
  const router = useRouter();
  const [copiedLink, setCopiedLink] = useState(false);

  const reviewUrl = storeSlug
    ? `${PROD_BASE}/review/${storeSlug}${user?._id ? `?sp=${user._id}` : ''}`
    : '';

  function handleCopyReview() {
    if (!reviewUrl) return;
    copyToClipboard(reviewUrl, 'Review link');
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  }

  return (
    <View style={{ paddingHorizontal: 16 }}>
      <Text style={{ fontSize: 15, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6, marginTop: 24 }}>
        My Presence
      </Text>
      <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 14 }}>
        Everything that represents you to customers
      </Text>

      {/* ── Digital Card ── */}
      <PresenceCard
        testId="presence-digital-card"
        icon="card" iconColor="#007AFF" iconBg="#007AFF20"
        title="My Digital Card"
        url={user?._id ? `${PROD_BASE}/card/${user._id}` : 'Configure in Account Setup'}
        previewBg="#007AFF08"
        onPreviewPress={() => user?._id && openUrl(`${PROD_BASE}/card/${user._id}`)}
        colors={colors}
        previewContent={
          <View style={{ alignItems: 'center' }}>
            <View style={{ marginBottom: 8 }}>
              <Avatar photo={resolveUserPhotoUrl(user)} name={user?.name || ''} size="lg" />
            </View>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{user?.name || 'Your Name'}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>Sales Professional</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
              {['#34C759', '#007AFF', '#FF9500', '#5856D6'].map((c, i) => (
                <View key={i} style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: `${c}20`, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={(['call', 'mail', 'chatbubble', 'globe'] as any)[i]} size={12} color={c} />
                </View>
              ))}
            </View>
          </View>
        }
        actions={[
          { label: 'Preview', icon: 'eye-outline', color: '#007AFF', testId: 'card-preview-btn',
            onPress: () => user?._id && openUrl(`${PROD_BASE}/card/${user._id}`) },
          { label: 'Edit', icon: 'create-outline', color: '#34C759', testId: 'card-edit-btn',
            onPress: () => router.push('/settings/store-profile' as any) },
          { label: 'Copy Link', icon: 'copy-outline', color: '#FF9500', testId: 'card-copy-btn',
            onPress: () => user?._id && copyToClipboard(`${PROD_BASE}/card/${user._id}`, 'Digital card link') },
        ]}
      />

      {/* ── Showcase ── */}
      <PresenceCard
        testId="presence-showcase"
        icon="images" iconColor="#34C759" iconBg="#34C75920"
        title="My Showcase"
        url={user?._id ? `${PROD_BASE}/showcase/${user._id}` : 'Your happy customers page'}
        previewBg="#34C75908"
        onPreviewPress={() => user?._id && openUrl(`${PROD_BASE}/showcase/${user._id}`)}
        colors={colors}
        previewContent={
          <View style={{ alignItems: 'center' }}>
            <View style={{ flexDirection: 'row', gap: 4, marginBottom: 4 }}>
              {['#007AFF20', '#34C75920', '#FF950020'].map((bg, i) => (
                <View key={i} style={{ width: 44, height: 44, borderRadius: 8, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="camera" size={14} color={(['#007AFF', '#34C759', '#FF9500'] as any)[i]} />
                </View>
              ))}
            </View>
            <View style={{ flexDirection: 'row', gap: 4 }}>
              {['#5856D620', '#FF2D5520', '#FFD60A20'].map((bg, i) => (
                <View key={i} style={{ width: 44, height: 44, borderRadius: 8, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="camera" size={14} color={(['#5856D6', '#FF2D55', '#FFD60A'] as any)[i]} />
                </View>
              ))}
            </View>
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6 }}>Your public portfolio</Text>
          </View>
        }
        actions={[
          { label: 'Preview', icon: 'eye-outline', color: '#34C759', testId: 'showcase-preview-btn',
            onPress: () => user?._id && openUrl(`${PROD_BASE}/showcase/${user._id}`) },
          { label: 'Manage', icon: 'settings-outline', color: '#FF9500', testId: 'showcase-manage-btn',
            onPress: () => router.push('/showroom-manage' as any) },
          { label: 'Approve', icon: 'checkmark-circle-outline', color: '#007AFF', testId: 'showcase-approve-btn',
            onPress: () => router.push('/settings/showcase-approvals' as any) },
          { label: 'Copy Link', icon: 'copy-outline', color: '#C9A962', testId: 'showcase-copy-btn',
            onPress: () => user?._id && copyToClipboard(`${PROD_BASE}/showcase/${user._id}`, 'Showcase link') },
        ]}
      />

      {/* ── Review Link ── */}
      <PresenceCard
        testId="presence-review-link"
        icon="star" iconColor="#FFD60A" iconBg="#FFD60A20"
        title="Review Link"
        url={reviewUrl || 'Configure store slug first'}
        previewBg="#FFD60A08"
        onPreviewPress={onPreviewReview}
        colors={colors}
        previewContent={
          <View style={{ alignItems: 'center' }}>
            <View style={{ flexDirection: 'row', gap: 2, marginBottom: 8 }}>
              {[1,2,3,4,5].map(i => <Ionicons key={i} name="star" size={20} color="#FFD60A" />)}
            </View>
            <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>Rate Your Experience</Text>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 8 }}>
              {[['Google','#4285F4'],['Facebook','#1877F2'],['Yelp','#AF2814']].map(([label, c]) => (
                <View key={label} style={{ paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, backgroundColor: `${c}15` }}>
                  <Text style={{ fontSize: 12, fontWeight: '600', color: c }}>{label}</Text>
                </View>
              ))}
            </View>
          </View>
        }
        actions={[
          { label: 'Preview', icon: 'eye-outline', color: '#5856D6', testId: 'review-preview-btn', onPress: onPreviewReview },
          { label: 'Edit Links', icon: 'create-outline', color: '#34C759', testId: 'review-edit-btn',
            onPress: () => router.push('/settings/review-links' as any) },
          { label: copiedLink ? 'Copied!' : 'Copy Link', icon: copiedLink ? 'checkmark' : 'copy-outline',
            color: copiedLink ? '#34C759' : '#FF9500', testId: 'review-copy-btn', onPress: handleCopyReview },
          { label: 'Share', icon: 'share-outline', color: '#FFD60A', testId: 'review-share-btn', onPress: onOpenShareModal },
        ]}
      />

      {/* ── Link Page ── */}
      <PresenceCard
        testId="presence-link-page"
        icon="link" iconColor="#C9A962" iconBg="#C9A96220"
        title="My Link Page"
        url={user?._id ? `${PROD_BASE}/l/${user._id}` : 'Your public link tree'}
        previewBg="#C9A96208"
        onPreviewPress={() => user?._id && openUrl(`${PROD_BASE}/l/${user._id}`)}
        colors={colors}
        previewContent={
          <View style={{ alignItems: 'center', width: '100%', maxWidth: 180 }}>
            <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: '#C9A96230', alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>
              <Ionicons name="person" size={16} color="#C9A962" />
            </View>
            {['Website', 'Instagram', 'Facebook'].map((label) => (
              <View key={label} style={{ width: '100%', paddingVertical: 6, borderRadius: 20, backgroundColor: colors.bg, marginBottom: 4, alignItems: 'center' }}>
                <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>{label}</Text>
              </View>
            ))}
          </View>
        }
        actions={[
          { label: 'Preview', icon: 'eye-outline', color: '#C9A962', testId: 'linkpage-preview-btn',
            onPress: () => user?._id && openUrl(`${PROD_BASE}/l/${user._id}`) },
          { label: 'Edit', icon: 'create-outline', color: '#34C759', testId: 'linkpage-edit-btn',
            onPress: () => router.push('/settings/link-page' as any) },
          { label: 'Copy Link', icon: 'copy-outline', color: '#FF9500', testId: 'linkpage-copy-btn',
            onPress: () => user?._id && copyToClipboard(`${PROD_BASE}/l/${user._id}`, 'Link page URL') },
        ]}
      />

      {/* ── Landing Page ── */}
      <PresenceCard
        testId="presence-landing-page"
        icon="globe-outline" iconColor="#AF52DE" iconBg="#AF52DE20"
        title="My Landing Page"
        url={user?._id ? `${PROD_BASE}/p/${user._id}` : 'Your personal landing page'}
        previewBg="#AF52DE08"
        onPreviewPress={() => user?._id && openUrl(`${PROD_BASE}/p/${user._id}`)}
        colors={colors}
        previewContent={
          <View style={{ alignItems: 'center' }}>
            <Ionicons name="globe-outline" size={28} color="#AF52DE" style={{ marginBottom: 4 }} />
            <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Welcome</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, marginBottom: 8 }}>{user?.name || 'Your Name'}</Text>
            <View style={{ paddingHorizontal: 16, paddingVertical: 6, borderRadius: 20, backgroundColor: '#AF52DE' }}>
              <Text style={{ fontSize: 12, fontWeight: '600', color: '#fff' }}>Get in Touch</Text>
            </View>
          </View>
        }
        actions={[
          { label: 'Preview', icon: 'eye-outline', color: '#AF52DE', testId: 'landing-preview-btn',
            onPress: () => user?._id && openUrl(`${PROD_BASE}/p/${user._id}`) },
          { label: 'Edit', icon: 'create-outline', color: '#34C759', testId: 'landing-edit-btn',
            onPress: () => router.push('/settings/store-profile' as any) },
          { label: 'Copy Link', icon: 'copy-outline', color: '#FF9500', testId: 'landing-copy-btn',
            onPress: () => user?._id && copyToClipboard(`${PROD_BASE}/p/${user._id}`, 'Landing page link') },
        ]}
      />

      {/* ── Simple link-only cards ── */}
      {[
        { testId: 'presence-templates', icon: 'document-text', iconColor: '#FFD60A', iconBg: '#FFD60A20',
          title: 'My Templates', subtitle: 'Quick-send messages for texts & emails',
          actionLabel: 'Manage', actionColor: '#FFD60A', route: '/settings/templates' },
        { testId: 'presence-card-templates', icon: 'gift', iconColor: '#FF2D55', iconBg: '#FF2D5520',
          title: 'Card Templates', subtitle: 'Congrats & birthday card designs',
          actionLabel: 'Manage', actionColor: '#FF2D55', route: '/settings/card-templates' },
        { testId: 'presence-email-sig', icon: 'at', iconColor: '#5856D6', iconBg: '#5856D620',
          title: 'Email Signature', subtitle: 'Your branded email sign-off',
          actionLabel: 'Edit', actionColor: '#5856D6', route: '/email-signature' },
      ].map((item) => (
        <View key={item.testId} style={{ backgroundColor: colors.card, borderRadius: 14, marginBottom: 14, overflow: 'hidden', padding: 14 }} data-testid={item.testId}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 10 }}>
            <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: item.iconBg, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={item.icon as any} size={20} color={item.iconColor} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{item.title}</Text>
              <Text style={{ fontSize: 12, color: colors.textTertiary }}>{item.subtitle}</Text>
            </View>
          </View>
          <View style={{ flexDirection: 'row' }}>
            <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: `${item.actionColor}15` }]}>
              <TouchableOpacity
                style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
                onPress={() => router.push(item.route as any)}
                data-testid={`${item.testId}-btn`}
              >
                <Ionicons name="create-outline" size={14} color={item.actionColor} />
                <Text style={{ fontSize: 13, fontWeight: '600', color: item.actionColor }}>{item.actionLabel}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      ))}
    </View>
  );
}
