/**
 * Universal customer interaction tracker.
 * Fire-and-forget — never blocks the user action.
 * Usage: trackCustomerAction('card', 'website_clicked', { salesperson_id, customer_phone, url })
 */
import api from './api';

interface TrackingContext {
  salesperson_id: string;
  customer_phone?: string;
  customer_name?: string;
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
