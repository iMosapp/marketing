import React, { useRef } from 'react';
import { View, Text, TouchableOpacity, Animated, Platform } from 'react-native';
import { Swipeable, RectButton } from 'react-native-gesture-handler';
import { Ionicons } from '@expo/vector-icons';
import { Avatar } from '../Avatar';
import { WebSwipeableItem, wasRecentSwipe } from '../WebSwipeableItem';

const GOLD = '#C9A962';

const STATUS_STYLES: Record<string, { bg: string; fg: string }> = {
  VIP: { bg: '#C9A96222', fg: '#C9A962' },
  Sold: { bg: '#34C75922', fg: '#34C759' },
  Hot: { bg: '#FF453A22', fg: '#FF453A' },
  Referral: { bg: '#007AFF22', fg: '#007AFF' },
  Prospect: { bg: '#8E8E9322', fg: '#8E8E93' },
};

function getStatus(tags: string[]): string | null {
  if (tags.includes('VIP')) return 'VIP';
  if (tags.includes('sold')) return 'Sold';
  if (tags.includes('hot')) return 'Hot';
  if (tags.includes('referral')) return 'Referral';
  if (tags.includes('prospect')) return 'Prospect';
  return null;
}

export function daysUntilBirthday(birthday?: string | null): number | null {
  if (!birthday) return null;
  const b = new Date(birthday);
  if (isNaN(b.getTime())) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const next = new Date(now.getFullYear(), b.getUTCMonth(), b.getUTCDate());
  if (next < today) next.setFullYear(next.getFullYear() + 1);
  return Math.round((next.getTime() - today.getTime()) / 86400000);
}

function timeAgoLabel(daysAgo: number | null): string | null {
  if (daysAgo === null) return null;
  if (daysAgo === 0) return 'Today';
  if (daysAgo === 1) return 'Yesterday';
  if (daysAgo < 30) return `${daysAgo}d ago`;
  if (daysAgo < 365) return `${Math.floor(daysAgo / 30)}mo ago`;
  return `${Math.floor(daysAgo / 365)}yr ago`;
}

function recencyColor(daysAgo: number | null): string {
  if (daysAgo === null) return 'transparent';
  if (daysAgo <= 7) return '#34C759';
  if (daysAgo <= 21) return '#FF9500';
  return '#FF453A';
}

interface Props {
  item: any;
  colors: any;
  selectMode: boolean;
  isSelected: boolean;
  isTeamView: boolean;
  isOwnContact: boolean;
  onPress: () => void;
  onLongPress: () => void;
  onCall: () => void;
  onText: () => void;
  onEmail: () => void;
  onDraft: () => void;
}

function ContactRowInner({
  item, colors, selectMode, isSelected, isTeamView, isOwnContact,
  onPress, onLongPress, onCall, onText, onEmail, onDraft,
}: Props) {
  const swipeRef = useRef<Swipeable>(null);
  const tags: string[] = item.tags || [];
  const status = getStatus(tags);

  const lastTouch = item.last_activity_at || item.updated_at;
  const daysAgo = lastTouch ? Math.floor((Date.now() - new Date(lastTouch).getTime()) / 86400000) : null;
  const touchLabel = timeAgoLabel(daysAgo);
  const vehicle = (item.vehicle || '').trim();
  const subParts = [touchLabel, vehicle].filter(Boolean);
  const subtitle = subParts.length > 0 ? subParts.join('  ·  ') : (item.phone || '');
  const dotColor = recencyColor(daysAgo);
  const canAct = !isTeamView || isOwnContact;

  const closeThen = (fn: () => void) => () => { swipeRef.current?.close(); fn(); };

  const renderRightActions = (
    _progress: Animated.AnimatedInterpolation<number>,
    dragX: Animated.AnimatedInterpolation<number>
  ) => {
    const scale = dragX.interpolate({ inputRange: [-180, 0], outputRange: [1, 0.4], extrapolate: 'clamp' });
    const actions = [
      { icon: 'chatbubble', label: 'Text', bg: '#34C759', fn: onText, tid: `swipe-text-${item._id}` },
      { icon: 'call', label: 'Call', bg: '#007AFF', fn: onCall, tid: `swipe-call-${item._id}` },
      { icon: 'mail', label: 'Email', bg: '#5E5CE6', fn: onEmail, tid: `swipe-email-${item._id}` },
    ];
    return (
      <View style={{ flexDirection: 'row' }}>
        {actions.map((a) => (
          <RectButton
            key={a.label}
            style={{ width: 64, justifyContent: 'center', alignItems: 'center', backgroundColor: a.bg }}
            onPress={closeThen(a.fn)}
            testID={a.tid}
          >
            <Animated.View style={{ alignItems: 'center', gap: 3, transform: [{ scale }] }}>
              <Ionicons name={a.icon as any} size={20} color="#fff" />
              <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 11, fontWeight: '600', color: '#fff' }}>{a.label}</Text>
            </Animated.View>
          </RectButton>
        ))}
      </View>
    );
  };

  const row = (
    <TouchableOpacity
      style={{
        flexDirection: 'row', alignItems: 'center',
        paddingHorizontal: 16, paddingVertical: 12,
        backgroundColor: colors.bg,
      }}
      onPress={() => {
        if (Platform.OS === 'web' && wasRecentSwipe()) return;
        onPress();
      }}
      onLongPress={onLongPress}
      activeOpacity={0.7}
      testID={`contact-row-${item._id}`} dataSet={{ testid: `contact-row-${item._id}` } as any}
    >
      {selectMode && !isTeamView && (
        <View style={{
          width: 24, height: 24, borderRadius: 12, borderWidth: 2, marginRight: 10,
          borderColor: isSelected ? GOLD : colors.textSecondary,
          backgroundColor: isSelected ? GOLD : 'transparent',
          justifyContent: 'center', alignItems: 'center',
        }}>
          {isSelected && <Ionicons name="checkmark" size={15} color="#000" />}
        </View>
      )}

      {/* Avatar + recency dot */}
      <View style={{ marginRight: 12 }}>
        <Avatar
          photo={item.photo_thumbnail || item.photo_url}
          name={`${item.first_name || ''} ${item.last_name || ''}`.trim()}
          size="md"
          style={{ width: 46, height: 46, borderRadius: 14 } as any}
        />
        {dotColor !== 'transparent' && (
          <View style={{
            position: 'absolute', bottom: -2, right: -2,
            width: 13, height: 13, borderRadius: 7,
            backgroundColor: dotColor, borderWidth: 2.5, borderColor: colors.bg,
          }} testID={`recency-dot-${item._id}`} dataSet={{ testid: `recency-dot-${item._id}` } as any} />
        )}
      </View>

      {/* Name + relationship line */}
      <View style={{ flex: 1, marginRight: 8 }}>
        <Text maxFontSizeMultiplier={1.0} numberOfLines={1} style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>
          {item.first_name} {item.last_name || ''}
        </Text>
        {isTeamView && item.salesperson_name && !isOwnContact ? (
          <Text maxFontSizeMultiplier={1.0} numberOfLines={1} style={{ fontSize: 13, color: GOLD, fontWeight: '500', marginTop: 1 }} testID="team-contact-salesperson" dataSet={{ testid: "team-contact-salesperson" } as any}>
            {item.salesperson_name}
          </Text>
        ) : null}
        {subtitle ? (
          <Text maxFontSizeMultiplier={1.0} numberOfLines={1} style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
            {subtitle}
          </Text>
        ) : null}
      </View>

      {/* Birthday chip (within 30 days) */}
      {(() => {
        const bd = daysUntilBirthday(item.birthday);
        if (bd === null || bd > 30) return null;
        return (
          <View
            style={{
              flexDirection: 'row', alignItems: 'center', gap: 3,
              backgroundColor: '#AF52DE22', borderRadius: 8,
              paddingHorizontal: 7, paddingVertical: 3, marginRight: 6,
            }}
            testID={`bday-chip-${item._id}`}
            dataSet={{ testid: `bday-chip-${item._id}` }}
          >
            <Ionicons name="gift" size={10} color="#AF52DE" />
            <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 10.5, fontWeight: '800', color: '#AF52DE' }}>
              {bd === 0 ? 'Today!' : `${bd}d`}
            </Text>
          </View>
        );
      })()}

      {/* Status pill */}
      {status && (
        <View style={{
          backgroundColor: STATUS_STYLES[status].bg, borderRadius: 8,
          paddingHorizontal: 8, paddingVertical: 3, marginRight: 8,
        }}>
          <Text maxFontSizeMultiplier={1.0} style={{ fontSize: 11, fontWeight: '800', color: STATUS_STYLES[status].fg }}>
            {status}
          </Text>
        </View>
      )}

      {/* AI draft sparkle OR view-only eye */}
      {canAct ? (
        !selectMode && (
          <TouchableOpacity
            style={{
              width: 38, height: 38, borderRadius: 19,
              backgroundColor: GOLD + '1E',
              alignItems: 'center', justifyContent: 'center',
            }}
            onPress={(e: any) => { e.stopPropagation?.(); onDraft(); }}
            testID={`draft-btn-${item._id}`} dataSet={{ testid: `draft-btn-${item._id}` } as any}
          >
            <Ionicons name="sparkles" size={17} color={GOLD} />
          </TouchableOpacity>
        )
      ) : (
        <Ionicons name="eye-outline" size={18} color={colors.textSecondary} />
      )}
    </TouchableOpacity>
  );

  if (selectMode || !canAct) return row;

  if (Platform.OS === 'web') {
    return (
      <WebSwipeableItem
        rightActions={[
          { key: `text-${item._id}`, icon: 'chatbubble', label: 'Text', color: '#fff', bgColor: '#34C759', onPress: onText },
          { key: `call-${item._id}`, icon: 'call', label: 'Call', color: '#fff', bgColor: '#007AFF', onPress: onCall },
          { key: `email-${item._id}`, icon: 'mail', label: 'Email', color: '#fff', bgColor: '#5E5CE6', onPress: onEmail },
        ]}
      >
        {row}
      </WebSwipeableItem>
    );
  }

  return (
    <Swipeable
      ref={swipeRef}
      friction={2}
      rightThreshold={40}
      renderRightActions={renderRightActions}
      overshootRight={false}
    >
      {row}
    </Swipeable>
  );
}

export const ContactRow = React.memo(ContactRowInner);
