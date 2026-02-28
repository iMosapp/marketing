// ============================================
// ONBOARDING TYPES
// ============================================

export type SlideType = 'welcome' | 'feature' | 'quick_win' | 'ai_setup' | 'interactive' | 'action' | 'checklist' | 'complete' | 'team_invite';

export interface OnboardingSlide {
  id: string;
  type: SlideType;
  title: string;
  subtitle?: string;
  description: string;
  icon: string;
  iconColor: string;
  bgGradient: string[];
  benefits?: string[];
  interactiveType?: 'choice' | 'input' | 'multi_input' | 'import' | 'team_invite';
  inputFields?: { key: string; label: string; placeholder: string; multiline?: boolean }[];
  choices?: { id: string; label: string; description: string; icon: string }[];
  actionButton?: { label: string; route: string };
  demoComponent?: string;
  inviteRole?: 'store_manager' | 'user';
  inviteTitle?: string;
  skipable?: boolean;
  // Quick Win specific
  tryItRoute?: string; // "Try it now" navigation route
  tryItLabel?: string; // Custom label for the try it button
  quickWinNumber?: number; // e.g., "Quick Win #1"
  // Checklist specific
  checklistItems?: { id: string; label: string; description: string; route: string; icon: string; iconColor: string }[];
}
