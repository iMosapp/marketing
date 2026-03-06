/**
 * Centralized Event Type Labels — SINGLE SOURCE OF TRUTH for frontend.
 * 
 * Every file that needs to display event type labels MUST import from here.
 * DO NOT create inline event type label maps anywhere else.
 */

export const EVENT_TYPE_LABELS: Record<string, string> = {
  // Card sends
  digital_card_sent: 'Digital Card Shared',
  digital_card_shared: 'Digital Card Shared',
  congrats_card_sent: 'Congrats Card Sent',
  birthday_card_sent: 'Birthday Card Sent',
  thank_you_card_sent: 'Thank You Card Sent',
  thankyou_card_sent: 'Thank You Card Sent',
  holiday_card_sent: 'Holiday Card Sent',
  welcome_card_sent: 'Welcome Card Sent',
  anniversary_card_sent: 'Anniversary Card Sent',
  vcard_sent: 'vCard Shared',
  showcase_shared: 'Showcase Shared',
  link_page_shared: 'Link Page Shared',
  review_request_sent: 'Review Invite Sent',
  
  // Card views (customer actions)
  digital_card_viewed: 'Viewed Digital Card',
  congrats_card_viewed: 'Viewed Congrats Card',
  birthday_card_viewed: 'Viewed Birthday Card',
  thankyou_card_viewed: 'Viewed Thank You Card',
  thank_you_card_viewed: 'Viewed Thank You Card',
  holiday_card_viewed: 'Viewed Holiday Card',
  welcome_card_viewed: 'Viewed Welcome Card',
  anniversary_card_viewed: 'Viewed Anniversary Card',
  
  // Link/review clicks
  review_link_clicked: 'Clicked Review Link',
  review_page_viewed: 'Viewed Review Page',
  review_submitted: 'Left a Review',
  showcase_viewed: 'Viewed Showcase',
  link_page_viewed: 'Viewed Link Page',
  link_clicked: 'Clicked Link',
  link_click: 'Clicked Link',
  
  // Messages
  email_sent: 'Email Sent',
  email_failed: 'Email Failed',
  sms_sent: 'SMS Sent',
  personal_sms: 'Text Sent',
  
  // Other
  call_placed: 'Call Placed',
  new_contact: 'Contact Created',
  new_contact_added: 'New Contact Added',
  voice_note: 'Voice Note',
  note_updated: 'Note Updated',
  customer_reply: 'Customer Reply',
};

/** Notification icon/color mapping for event types */
export const EVENT_TYPE_ICONS: Record<string, { icon: string; color: string }> = {
  digital_card_sent: { icon: 'card', color: '#007AFF' },
  digital_card_shared: { icon: 'card', color: '#007AFF' },
  congrats_card_sent: { icon: 'gift', color: '#C9A962' },
  birthday_card_sent: { icon: 'gift', color: '#FF9500' },
  thank_you_card_sent: { icon: 'thumbs-up', color: '#34C759' },
  thankyou_card_sent: { icon: 'thumbs-up', color: '#34C759' },
  holiday_card_sent: { icon: 'snow', color: '#5AC8FA' },
  welcome_card_sent: { icon: 'hand-left', color: '#007AFF' },
  anniversary_card_sent: { icon: 'heart', color: '#FF2D55' },
  review_request_sent: { icon: 'star', color: '#FFD60A' },
  email_sent: { icon: 'mail', color: '#AF52DE' },
  personal_sms: { icon: 'chatbubble', color: '#30D158' },
  sms_sent: { icon: 'chatbubble', color: '#30D158' },
  customer_reply: { icon: 'arrow-down', color: '#30D158' },
};

/** Get a human-readable label for any event type */
export function getEventLabel(eventType: string): string {
  if (!eventType) return 'Activity';
  return EVENT_TYPE_LABELS[eventType] || eventType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** All card send event types — for filtering/aggregation */
export const ALL_CARD_SENT_TYPES = [
  'congrats_card_sent', 'birthday_card_sent', 'thank_you_card_sent',
  'thankyou_card_sent', 'holiday_card_sent', 'welcome_card_sent',
  'anniversary_card_sent', 'digital_card_sent', 'digital_card_shared',
];

/** All card viewed event types */
export const ALL_CARD_VIEWED_TYPES = [
  'congrats_card_viewed', 'birthday_card_viewed', 'thankyou_card_viewed',
  'thank_you_card_viewed', 'holiday_card_viewed', 'welcome_card_viewed',
  'anniversary_card_viewed', 'digital_card_viewed',
];
