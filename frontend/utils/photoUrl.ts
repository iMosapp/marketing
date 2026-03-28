/**
 * photoUrl.ts — Single source of truth for resolving user/contact photo URLs.
 *
 * Rules (priority order):
 *  1. Null/empty       → return null (caller shows initials fallback)
 *  2. data:image/...   → raw base64 (legacy, still display it)
 *  3. /api/images/...  → relative path, prepend BACKEND_URL on native
 *  4. http(s)://...    → external URL, return as-is
 *  5. anything else    → treat as relative, prepend BACKEND_URL
 */

import { Platform } from 'react-native';

const BACKEND_URL =
  Platform.OS === 'web'
    ? ''
    : process.env.EXPO_PUBLIC_BACKEND_URL || '';

/**
 * Resolves any photo value (relative path, absolute URL, base64, null)
 * into a fully-qualified URL the Image component can load.
 */
export function resolvePhotoUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith('data:')) return url;           // base64 — pass through
  if (url.startsWith('http://') || url.startsWith('https://')) return url; // absolute
  if (url.startsWith('/')) return `${BACKEND_URL}${url}`; // relative path
  return `${BACKEND_URL}/${url}`;                    // bare path — prepend base
}

/**
 * Picks the best available photo URL from a user object.
 * Checks avatar → thumbnail → full in order of smallest file size.
 */
export function resolveUserPhotoUrl(user: {
  photo_avatar_path?: string | null;
  photo_thumb_path?: string | null;
  photo_path?: string | null;
  photo_url?: string | null;
  _id?: string;
} | null | undefined): string | null {
  if (!user) return null;

  if (user.photo_avatar_path) return resolvePhotoUrl(`/api/images/${user.photo_avatar_path}`);
  if (user.photo_thumb_path)  return resolvePhotoUrl(`/api/images/${user.photo_thumb_path}`);
  if (user.photo_path)        return resolvePhotoUrl(`/api/images/${user.photo_path}`);
  if (user.photo_url)         return resolvePhotoUrl(user.photo_url);
  return null;
}

/**
 * Picks the best available photo URL from a contact object.
 */
export function resolveContactPhotoUrl(contact: {
  photo_thumbnail?: string | null;
  photo_url?: string | null;
  photo?: string | null;
} | null | undefined): string | null {
  if (!contact) return null;
  return resolvePhotoUrl(contact.photo_thumbnail || contact.photo_url || contact.photo || null);
}
