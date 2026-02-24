// ============================================
// ONBOARDING TYPES
// ============================================

export type SlideType = 'welcome' | 'feature' | 'ai_setup' | 'interactive' | 'action' | 'complete' | 'team_invite';

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
  inviteRole?: 'store_manager' | 'user'; // For team_invite type slides
  inviteTitle?: string; // Label for who they're inviting
  skipable?: boolean; // Can this step be skipped
}
