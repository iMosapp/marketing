/**
 * ContactContext.tsx — Shared state for the contact detail page.
 *
 * Architecture:
 *  - The main ContactDetailScreen owns all state (useState hooks)
 *  - It wraps its render tree with <ContactContext.Provider value={...}>
 *  - Sub-components call useContact() to get any state/handler they need
 *  - No prop drilling required
 *
 * Adding a new sub-component:
 *  1. Add any new state/handlers to the interface below
 *  2. Include them in the ctxValue object in contact/[id].tsx
 *  3. Call useContact() in the new component
 */

import { createContext, useContext } from 'react';

export interface ContactContextValue {
  // ── Core ────────────────────────────────────────────────────────────────
  contactId: string;
  user: any;
  router: any;
  colors: any;
  s: any; // StyleSheet result from getS(colors)

  // ── Contact data ─────────────────────────────────────────────────────────
  contact: any;
  setContact: (c: any) => void;
  loading: boolean;
  saving: boolean;
  isEditing: boolean;
  setIsEditing: (v: boolean) => void;
  isNewContact: boolean;

  // ── Events & feed ────────────────────────────────────────────────────────
  events: any[];
  filteredEvents: any[];
  stats: any;
  eventsLoading: boolean;
  expandedEvents: Record<number, boolean>;
  setExpandedEvents: (v: Record<number, boolean>) => void;
  showAllEvents: boolean;
  setShowAllEvents: (v: boolean) => void;
  feedSearch: string;
  setFeedSearch: (v: string) => void;
  collapsedDateGroups: Record<string, boolean>;
  setCollapsedDateGroups: (v: Record<string, boolean>) => void;
  contactTab: 'feed' | 'details';
  setContactTab: (v: 'feed' | 'details') => void;

  // ── Suggested actions ─────────────────────────────────────────────────────
  suggestedActions: any[];
  actionProgress: any[];
  progressCompleted: number;
  progressTotal: number;

  // ── AI intel ──────────────────────────────────────────────────────────────
  intelData: any;
  intelLoading: boolean;
  intelGenerating: boolean;
  showIntel: boolean;
  setShowIntel: (v: boolean) => void;
  generateIntel: () => void;

  // ── Voice notes ───────────────────────────────────────────────────────────
  voiceNotes: any[];
  voiceNotesLoading: boolean;
  isRecording: boolean;
  recordingTime: number;
  uploadingVoiceNote: boolean;
  playingNoteId: string | null;
  showAllNotes: boolean;
  setShowAllNotes: (v: boolean) => void;

  // ── Log reply ─────────────────────────────────────────────────────────────
  showLogReply: boolean;
  setShowLogReply: (v: boolean) => void;
  replyText: string;
  setReplyText: (v: string) => void;
  replyPhoto: string | null;
  setReplyPhoto: (v: string | null) => void;
  submittingReply: boolean;

  // ── Composer ──────────────────────────────────────────────────────────────
  composerMessage: string;
  setComposerMessage: (v: string) => void;
  composerMode: 'sms' | 'email';
  setComposerMode: (v: 'sms' | 'email') => void;
  composerSending: boolean;
  composerInputHeight: number;
  setComposerInputHeight: (v: number) => void;
  selectedMedia: any;
  setSelectedMedia: (v: any) => void;
  isVoiceRecording: boolean;
  voiceTranscribing: boolean;
  loadingAI: boolean;
  showAISuggestion: boolean;
  setShowAISuggestion: (v: boolean) => void;
  aiSuggestion: string;
  setAiSuggestion: (v: string) => void;

  // ── Toolbar modals ────────────────────────────────────────────────────────
  showTemplates: boolean;
  setShowTemplates: (v: boolean) => void;
  showReviewLinks: boolean;
  setShowReviewLinks: (v: boolean) => void;
  showBusinessCard: boolean;
  setShowBusinessCard: (v: boolean) => void;
  showLandingPageOptions: boolean;
  setShowLandingPageOptions: (v: boolean) => void;
  showPhotoOptionsModal: boolean;
  setShowPhotoOptionsModal: (v: boolean) => void;
  showSoldModal: boolean;
  setShowSoldModal: (v: boolean) => void;
  soldWorkflowResult: any;

  // ── Toolbar data ──────────────────────────────────────────────────────────
  templates: any[];
  reviewLinks: Record<string, string>;
  storeSlug: string;
  customLinkName: string;
  campaigns: any[];
  selectedCampaign: string | null;
  setSelectedCampaign: (v: string | null) => void;
  loadingCampaigns: boolean;
  contactEnrollments: any[];

  // ── Picker modals ─────────────────────────────────────────────────────────
  showTagPicker: boolean;
  setShowTagPicker: (v: boolean) => void;
  tagSearch: string;
  setTagSearch: (v: string) => void;
  availableTags: any[];
  showReferralPicker: boolean;
  setShowReferralPicker: (v: boolean) => void;
  allContacts: any[];
  contactSearch: string;
  setContactSearch: (v: string) => void;
  referrals: any[];
  showCampaignPicker: boolean;
  setShowCampaignPicker: (v: boolean) => void;

  // ── Date picker ───────────────────────────────────────────────────────────
  showDatePicker: boolean;
  setShowDatePicker: (v: boolean) => void;
  activeDateField: string | null;
  setActiveDateField: (v: string | null) => void;
  activeDateLabel: string;
  setActiveDateLabel: (v: string) => void;
  tempDate: Date;
  setTempDate: (v: Date) => void;
  webMonth: number;
  setWebMonth: (v: number) => void;
  webDay: number;
  setWebDay: (v: number) => void;
  webYear: number;
  setWebYear: (v: number) => void;
  pendingCustomDate: Date | null;
  setPendingCustomDate: (v: Date | null) => void;
  showCustomDateLabel: boolean;
  setShowCustomDateLabel: (v: boolean) => void;
  newCustomDateName: string;
  setNewCustomDateName: (v: string) => void;

  // ── Photo viewer ──────────────────────────────────────────────────────────
  showPhotoViewer: boolean;
  setShowPhotoViewer: (v: boolean) => void;
  allPhotos: any[];
  fullPhoto: string | null;
  selectedPhotoIndex: number;
  setSelectedPhotoIndex: (v: number) => void;
  galleryWidth: number;
  setGalleryWidth: (v: number) => void;

  // ── Action sheet (web) ────────────────────────────────────────────────────
  webActionSheet: { visible: boolean; title: string; options: any[] };
  setWebActionSheet: (v: any) => void;

  // ── Handlers ──────────────────────────────────────────────────────────────
  handleQuickAction: (action: string) => void;
  handleSuggestedAction: (action: any) => void;
  handleComposerSend: (overrideMsg?: string) => void;
  handleAttachPhoto: () => void;
  handleVoiceToText: () => void;
  loadAISuggestionForComposer: () => void;
  openBusinessCardPicker: () => void;
  insertReviewLink: (platformId: string, url: string, platformName: string) => void;
  selectTemplate: (template: any) => void;
  sendVCardLink: () => void;
  sendBusinessCardLink: () => void;
  handleEnrollCampaign: () => void;
  handleAddTag: (tag: string) => void;
  handleRemoveTag: (tag: string) => void;
  handleSelectReferral: (c: any) => void;
  openDatePicker: (field: string, currentDate: Date | null, label?: string) => void;
  handleConfirmDate: () => void;
  handleStartRecording: () => void;
  handleStopRecording: () => void;
  handlePlayVoiceNote: (noteId: string, audioUrl: string) => void;
  handleDeleteVoiceNote: (noteId: string) => void;
  submitReply: () => void;
  loadContact: () => void;
  generateIntel: () => void;
  showToast: (msg: string, type?: string) => void;
  channelPicker: any;
}

const ContactContext = createContext<ContactContextValue | null>(null);

export const useContact = (): ContactContextValue => {
  const ctx = useContext(ContactContext);
  if (!ctx) throw new Error('useContact must be used within ContactDetailScreen');
  return ctx;
};

export default ContactContext;
