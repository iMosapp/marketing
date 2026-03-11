/**
 * Universal customer interaction tracker.
 * Fire-and-forget — never blocks the user action.
 *
 * ARCHITECTURE:
 * - Every customer-facing page reads `cid` (contact_id) from URL params
 * - `cid` is appended by the short URL redirect handler for accurate attribution
 * - Tracking calls POST /api/tracking/event which logs a contact_event
 * - contact_events feed into: daily touchpoints, leaderboard, performance dashboard, activity feed
 *
 * Usage:
 *   trackCustomerAction('card', 'call_clicked', { salesperson_id: '...', contact_id: '...', url: 'tel:...' })
 */
import api from './api';

interface TrackingContext {
  salesperson_id: string;
  contact_id?: string;        // Preferred — from `cid` URL param (most reliable)
  customer_phone?: string;    // Fallback — for legacy links without cid
  customer_name?: string;     // Fallback
  card_id?: string;
  url?: string;
  platform?: string;
  description?: string;
  metadata?: Record<string, any>;
}

export function trackCustomerAction(
  page: string,
  action: string,
  context: TrackingContext
) {
  // Fire and forget — never await, never throw
  api.post('/tracking/event', {
    page,
    action,
    ...context,
  }).catch(() => {
    // Silently fail — tracking should never block the user
  });
}
