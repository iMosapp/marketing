/**
 * Referral Link Utility
 * Appends the current user's ref code to any shareable URL.
 * 
 * Usage:
 *   import { appendRef } from '../utils/refLink';
 *   const shareUrl = appendRef('https://app.imonsocial.com/imos/digital-card/abc', user.ref_code);
 *   // => 'https://app.imonsocial.com/imos/digital-card/abc?ref=A1B2C3D4'
 */

export function appendRef(url: string, refCode?: string): string {
  if (!refCode) return url;
  try {
    const u = new URL(url);
    u.searchParams.set('ref', refCode);
    return u.toString();
  } catch {
    // Fallback for relative URLs or malformed
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}ref=${refCode}`;
  }
}
