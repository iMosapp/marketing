/**
 * types/index.ts — Single source of truth for all TypeScript interfaces.
 * Import from here instead of redefining types in each file.
 */

// ─────────────────────────────────────────
// USER
// ─────────────────────────────────────────
export interface User {
  _id: string;
  email: string;
  name: string;
  phone?: string | null;
  title?: string | null;
  bio?: string | null;
  mvpline_number?: string | null;
  onboarding_complete?: boolean | null;
  persona?: Record<string, any>;
  store_id?: string | null;
  store_name?: string | null;
  store_slug?: string | null;
  organization_id?: string | null;
  org_id?: string | null;
  organization_name?: string | null;
  org_slug?: string | null;
  role?: UserRole;
  status?: 'active' | 'pending' | 'inactive';
  account_type?: 'independent' | 'organization';
  photo_url?: string | null;
  photo_path?: string | null;
  photo_thumb_path?: string | null;
  photo_avatar_path?: string | null;
  social_links?: Record<string, string>;
  feature_permissions?: Record<string, any>;
  needs_password_change?: boolean;
  isImpersonating?: boolean;
  timezone?: string;
}

export type UserRole =
  | 'super_admin'
  | 'org_admin'
  | 'store_manager'
  | 'user'
  | 'admin'      // legacy — maps to org_admin
  | 'manager';   // legacy — maps to store_manager

export const ROLE_LABELS: Record<string, string> = {
  super_admin:   'Super Admin',
  org_admin:     'Org Admin',
  store_manager: 'Account Manager',
  user:          'Sales Rep',
};

export const ROLE_COLORS: Record<string, string> = {
  super_admin:   '#FF3B30',
  org_admin:     '#FF9500',
  store_manager: '#34C759',
  user:          '#007AFF',
};

// ─────────────────────────────────────────
// CONTACT
// ─────────────────────────────────────────
export interface Contact {
  _id: string;
  user_id: string;
  first_name: string;
  last_name?: string;
  phone?: string | null;
  email?: string | null;
  photo_url?: string | null;
  photo_thumbnail?: string | null;
  photo?: string | null;
  tags?: string[];
  vehicle?: string | null;
  notes?: string | null;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export type ContactTag =
  | 'hot_lead' | 'prospect' | 'sold' | 'at_risk'
  | 'dormant' | 'referral' | 'vip' | string;

// ─────────────────────────────────────────
// MESSAGE / CONVERSATION
// ─────────────────────────────────────────
export interface Message {
  _id: string;
  conversation_id: string;
  user_id: string;
  contact_id: string;
  body: string;
  direction: 'inbound' | 'outbound';
  channel: 'sms' | 'email' | 'internal';
  status?: 'sent' | 'delivered' | 'read' | 'failed';
  created_at: string;
  read_at?: string | null;
}

export interface Conversation {
  _id: string;
  user_id: string;
  contact_id: string;
  contact_name: string;
  contact_photo?: string | null;
  last_message?: string;
  last_message_at?: string;
  unread_count: number;
  channel: 'sms' | 'email';
}

// ─────────────────────────────────────────
// PARTNER BRANDING
// ─────────────────────────────────────────
export interface PartnerBranding {
  name: string;
  slug: string;
  logo?: string | null;
  logo_icon?: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  text_color: string;
  powered_by_text: string;
  company_name: string;
  company_address?: string;
  company_phone?: string;
  company_email?: string;
  company_website?: string;
}

// ─────────────────────────────────────────
// COMMON UI
// ─────────────────────────────────────────
export type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'xxl';
