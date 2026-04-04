/**
 * ContactContext.tsx
 * 
 * React Context for the Contact Detail screen.
 * This is the extraction foundation — state lives here, 
 * components consume it via useContactContext().
 * 
 * Extraction progress:
 *   ✅ Phase 3a — contactStyles.ts (245 styles)
 *   ✅ Phase 3b — contactHelpers.tsx (utils + IntelRenderer)
 *   ✅ Phase 3c — contact/new.tsx (new contact form)
 *   🔄 Phase 3d — ContactContext (this file) + ActivityFeed
 *   ⏳ Phase 3e — PhotoGallery, VoiceNotes, CampaignSection, TagSection
 */

import React, { createContext, useContext } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ContactEvent {
  event_type: string;
  icon: string;
  color: string;
  title: string;
  description: string;
  timestamp: string;
  category: string;
  direction?: string;
  has_photo?: boolean;
  full_content?: string;
  link?: string;
  channel?: string;
  subject?: string;
}

export interface ContactStats {
  total_touchpoints: number;
  messages_sent: number;
  campaigns: number;
  cards_sent: number;
  broadcasts: number;
  custom_events: number;
  link_clicks: number;
  referral_count: number;
  created_at: string | null;
}

export interface CustomDateField {
  name: string;
  date: Date | null;
}

// ── Context shape ─────────────────────────────────────────────────────────────

export interface ContactContextValue {
  // Core
  contact: any;
  setContact: (c: any) => void;
  contactId: string;
  userId: string;
  isEditing: boolean;
  setIsEditing: (v: boolean) => void;
  loading: boolean;
  saving: boolean;
  colors: any;

  // Activity Feed
  events: ContactEvent[];
  setEvents: (e: ContactEvent[]) => void;
  stats: ContactStats;
  eventsLoading: boolean;
  expandedEvents: Record<number, boolean>;
  setExpandedEvents: (v: Record<number, boolean>) => void;
  showAllEvents: boolean;
  setShowAllEvents: (v: boolean) => void;
  feedSearch: string;
  setFeedSearch: (v: string) => void;
  collapsedDateGroups: Record<string, boolean>;
  setCollapsedDateGroups: (v: Record<string, boolean>) => void;

  // Photo/Gallery
  allPhotos: any[];
  setAllPhotos: (p: any[]) => void;
  showPhotoViewer: boolean;
  setShowPhotoViewer: (v: boolean) => void;
  selectedPhotoIndex: number;
  setSelectedPhotoIndex: (v: number) => void;

  // Tags
  addTagFromHero: (tag: string) => void;
  removeTag: (tag: string) => void;

  // Campaigns
  loadingCampaigns: boolean;
  selectedCampaign: string | null;
  setSelectedCampaign: (v: string | null) => void;

  // Composer
  composerMessage: string;
  setComposerMessage: (v: string) => void;
  composerMode: 'sms' | 'email';
  setComposerMode: (v: 'sms' | 'email') => void;

  // Reload helper
  reloadEvents: () => Promise<void>;
}

// ── Context + Hook ─────────────────────────────────────────────────────────────

const ContactContext = createContext<ContactContextValue | null>(null);

export function useContactContext(): ContactContextValue {
  const ctx = useContext(ContactContext);
  if (!ctx) {
    throw new Error('useContactContext must be used inside ContactProvider');
  }
  return ctx;
}

export const ContactProvider = ContactContext.Provider;
export default ContactContext;
