/**
 * Avatar.tsx — The ONE component for displaying any person's photo.
 *
 * Features:
 *  - Uses OptimizedImage (expo-image) for disk caching + progressive loading
 *  - Resolves all photo URL types: relative /api/images/, absolute, base64
 *  - Falls back to colored initials when no photo is available
 *  - Consistent sizing system used everywhere in the app
 *
 * Usage:
 *   <Avatar photo={user.photo_url} name={user.name} size="lg" />
 *   <Avatar photo={contact.photo_thumbnail} name="Sarah Jones" size="md" />
 *   <Avatar photo={null} name="Unknown" size="sm" />   ← shows initials
 */

import React, { useState } from 'react';
import { View, Text, ViewStyle, TextStyle } from 'react-native';
import { OptimizedImage } from './OptimizedImage';
import { resolvePhotoUrl } from '../utils/photoUrl';
import { AvatarSize, UserRole } from '../types/index';

// ─── Size map ────────────────────────────────────────────────────────────────
const SIZE_MAP: Record<AvatarSize, { px: number; text: number; radius: number }> = {
  xs:  { px: 24,  text: 9,  radius: 12 },
  sm:  { px: 32,  text: 12, radius: 16 },
  md:  { px: 44,  text: 16, radius: 22 },
  lg:  { px: 56,  text: 20, radius: 28 },
  xl:  { px: 72,  text: 26, radius: 36 },
  xxl: { px: 96,  text: 34, radius: 48 },
};

// Legacy numeric size support — convert px number to nearest named size
function pxToSize(px: number): AvatarSize {
  if (px <= 26) return 'xs';
  if (px <= 36) return 'sm';
  if (px <= 50) return 'md';
  if (px <= 64) return 'lg';
  if (px <= 80) return 'xl';
  return 'xxl';
}

// ─── Initials helpers ─────────────────────────────────────────────────────────
const PALETTE = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#F39C12',
  '#9B59B6', '#1ABC9C', '#E67E22', '#3498DB', '#E74C3C',
  '#2ECC71', '#F1C40F', '#16A085', '#8E44AD', '#D35400',
];

function colorFromName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function initials(name: string): string {
  if (!name?.trim()) return '?';
  const parts = name.trim().split(/\s+/);
  return parts.length === 1
    ? parts[0].slice(0, 2).toUpperCase()
    : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ─── Role colors for UserAvatar ───────────────────────────────────────────────
const ROLE_COLORS: Record<string, string> = {
  super_admin:   '#FF3B30',
  org_admin:     '#FF9500',
  store_manager: '#5856D6',
  user:          '#34C759',
};

// ─── Props ────────────────────────────────────────────────────────────────────
interface AvatarProps {
  /** Photo URL: relative (/api/images/...), absolute (https://...), base64, or null */
  photo?: string | null;
  /** URI alias — same as photo, for backward compatibility */
  uri?: string | null;
  /** Used for initials fallback and background color generation */
  name?: string;
  /** Named size token */
  size?: AvatarSize;
  /** Numeric pixel size (legacy support) */
  sizePx?: number;
  /** Border radius override (legacy support) */
  borderRadius?: number;
  /** Background color override (overrides generated color) */
  color?: string;
  /** Ring/border around the avatar */
  showRing?: boolean;
  ringColor?: string;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

// ─── Component ────────────────────────────────────────────────────────────────
export const Avatar: React.FC<AvatarProps> = ({
  photo,
  uri,
  name = '',
  size = 'md',
  sizePx,
  borderRadius: borderRadiusOverride,
  color,
  showRing = false,
  ringColor = '#007AFF',
  style,
  textStyle,
}) => {
  const [imgError, setImgError] = useState(false);

  // Resolve size
  const resolvedSize = sizePx ? pxToSize(sizePx) : size;
  const { px, text, radius } = SIZE_MAP[resolvedSize];
  const br = borderRadiusOverride ?? radius;

  // Resolve photo URL — prefer `photo` prop, fall back to `uri` (legacy)
  const rawUrl = photo ?? uri ?? null;
  const resolvedUrl = imgError ? null : resolvePhotoUrl(rawUrl);

  const bgColor = color || colorFromName(name);

  const containerStyle: ViewStyle = {
    width: px,
    height: px,
    borderRadius: br,
    overflow: 'hidden',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: bgColor,
    ...(showRing ? { borderWidth: 2, borderColor: ringColor } : {}),
    ...style,
  };

  if (resolvedUrl) {
    return (
      <View style={containerStyle}>
        <OptimizedImage
          source={{ uri: resolvedUrl }}
          style={{ width: px, height: px }}
          contentFit="cover"
          recyclingKey={resolvedUrl}
          placeholder={null}
          onError={() => setImgError(true)}
        />
      </View>
    );
  }

  return (
    <View style={containerStyle}>
      <Text style={[{ fontSize: text, fontWeight: '600', color: '#FFFFFF' }, textStyle]}>
        {initials(name)}
      </Text>
    </View>
  );
};

// ─── Convenience variants ─────────────────────────────────────────────────────

/** For displaying app users (reps, managers, admins) — shows role-based color */
export const UserAvatar: React.FC<AvatarProps & { role?: UserRole | string }> = ({
  role,
  color,
  ...props
}) => (
  <Avatar
    {...props}
    color={color || (role ? ROLE_COLORS[role] : undefined)}
  />
);

/** For displaying contacts — no role color */
export const ContactAvatar: React.FC<AvatarProps> = (props) => <Avatar {...props} />;

export default Avatar;
