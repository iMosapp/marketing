// Role-Based Onboarding Slide Libraries
// Focused on QUICK WINS  - the immediate value each role gets

import { OnboardingSlide } from './types';

// ============================================
// SHARED SLIDES (Used by all roles)
// ============================================
export const WELCOME_SLIDES: OnboardingSlide[] = [
  {
    id: 'welcome',
    type: 'welcome',
    title: 'Welcome to Your New Sales Toolkit',
    subtitle: "i'M On Social",
    description: "You're about to unlock a set of powerful tools that make you look great, stay connected, and close more deals  - starting right now.",
    icon: 'rocket',
    iconColor: '#007AFF',
    bgGradient: ['#FFFFFF', '#F8F9FB'],
    benefits: [
      "See what's ready for you in under 3 minutes",
      'Start using your tools immediately',
      'Quick wins you can share today',
    ],
  },
  {
    id: 'verify_profile',
    type: 'interactive',
    title: 'Quick Profile Check',
    subtitle: "Let's Make Sure We Got It Right",
    description: "This info powers your digital business card and AI assistant  - make it shine.",
    icon: 'checkmark-circle',
    iconColor: '#34C759',
    bgGradient: ['#FFFFFF', '#F8F9FB'],
    interactiveType: 'multi_input',
    inputFields: [
      { key: 'name', label: 'Your Name', placeholder: 'Full name as customers will see it' },
      { key: 'title', label: 'Your Title', placeholder: 'e.g. Sales Consultant, Finance Manager' },
      { key: 'bio', label: 'Short Bio', placeholder: 'A brief intro about yourself...', multiline: true },
    ],
  },
];

// ============================================
// QUICK WIN SLIDES  - The core value proposition
// ============================================
const QUICK_WIN_DIGITAL_CARD: OnboardingSlide = {
  id: 'qw_digital_card',
  type: 'quick_win',
  title: 'Your Digital Business Card',
  subtitle: 'Quick Win #1',
  description: "A sleek, shareable card with your photo, contact info, social links, and QR code. Text it, email it, or let customers scan it  - your reputation in one link.",
  icon: 'card',
  iconColor: '#5856D6',
  bgGradient: ['#FFFFFF', '#F5F5FF'],
  demoComponent: 'DigitalCardDemo',
  tryItRoute: '/settings/store-profile',
  tryItLabel: 'Set Up My Card',
  quickWinNumber: 1,
  benefits: [
    'Share via text, email, or QR code',
    'Personal reviews live on your card',
    'Social links all in one place',
    'Customers can call, text, or leave reviews',
  ],
};

const QUICK_WIN_CONGRATS_CARDS: OnboardingSlide = {
  id: 'qw_congrats_cards',
  type: 'quick_win',
  title: 'Congrats Cards',
  subtitle: 'Quick Win #2',
  description: "Just closed a deal? Create a custom congrats card in seconds. Upload their photo, add a message, and share it via text or email. They land on a branded page with your reviews and socials.",
  icon: 'gift',
  iconColor: '#007AFF',
  bgGradient: ['#FFFFFF', '#FFFBF0'],
  demoComponent: 'CongratsCardDemo',
  tryItRoute: '/settings/create-congrats',
  tryItLabel: 'Create a Congrats Card',
  quickWinNumber: 2,
  benefits: [
    'Upload a photo → preview → send in seconds',
    'Branded card with your name & store',
    'Share via SMS, email, Facebook, or Twitter',
    'Drives Google reviews and social engagement',
  ],
};

const QUICK_WIN_BIRTHDAY_CARDS: OnboardingSlide = {
  id: 'qw_birthday_cards',
  type: 'quick_win',
  title: 'Birthday Cards',
  subtitle: 'Quick Win #3',
  description: "Never miss a birthday. Create personalized birthday cards on the fly, or let the system auto-generate them for tagged contacts. A personal touch that keeps you top of mind.",
  icon: 'gift',
  iconColor: '#FF6B8A',
  bgGradient: ['#FFFFFF', '#FFF5F7'],
  demoComponent: 'BirthdayCardDemo',
  tryItRoute: '/settings/create-birthday-card',
  tryItLabel: 'Create a Birthday Card',
  quickWinNumber: 3,
  benefits: [
    'Create custom cards with a photo and message',
    'Auto-generate for contacts tagged "Birthday"',
    'Preview before you send',
    'Share via SMS, email, or social media',
  ],
};

const QUICK_WIN_REVIEW_PAGE: OnboardingSlide = {
  id: 'qw_review_page',
  type: 'quick_win',
  title: 'Your Review & Reputation Page',
  subtitle: 'Quick Win #4',
  description: "From your digital card, customers land on a personal review page. They can leave you a review, see your social links, and connect directly. It's your personal reputation hub.",
  icon: 'star',
  iconColor: '#FFD60A',
  bgGradient: ['#FFFFFF', '#FFFCF0'],
  demoComponent: 'ReviewPageDemo',
  tryItRoute: '/settings/store-profile',
  tryItLabel: 'View My Review Page',
  quickWinNumber: 4,
  benefits: [
    'Personal review landing page for YOUR name',
    'Drives Google reviews from happy customers',
    'Shows your social media links',
    'Easy for customers  - one tap to leave a review',
  ],
};

const QUICK_WIN_SHOWROOM: OnboardingSlide = {
  id: 'qw_showroom',
  type: 'quick_win',
  title: 'Your Showroom Page',
  subtitle: 'Quick Win #5',
  description: "A landing page that showcases your work  - congrats cards, featured vehicles, happy customers. Edit what shows up. Perfect to text or email while a customer is waiting in your office.",
  icon: 'images',
  iconColor: '#007AFF',
  bgGradient: ['#FFFFFF', '#F0F5FF'],
  demoComponent: 'ShowroomDemo',
  tryItRoute: '/showroom-manage',
  tryItLabel: 'Manage My Showroom',
  quickWinNumber: 5,
  benefits: [
    'Showcase your best work to new customers',
    'Editable  - choose what shows up',
    'Quick to share via text or email',
    'Builds trust while they wait',
  ],
};

const QUICK_WIN_QUICK_ACTIONS: OnboardingSlide = {
  id: 'qw_quick_actions',
  type: 'quick_win',
  title: 'Email & Text in Seconds',
  subtitle: 'Quick Win #6',
  description: "Reach anyone instantly from the inbox. Send a text, an email, a congrats card, or a review invite  - all tracked so you never lose a touchpoint.",
  icon: 'flash',
  iconColor: '#FF9500',
  bgGradient: ['#FFFFFF', '#FFF8F0'],
  demoComponent: 'QuickActionsDemo',
  tryItRoute: '/(tabs)/inbox',
  tryItLabel: 'Open My Inbox',
  quickWinNumber: 6,
  benefits: [
    'Text or email from one place',
    'Send congrats cards, review invites, digital card',
    'Every message is tracked and logged',
    'Works from your personal phone too',
  ],
};

const QUICK_WIN_CSV_IMPORT: OnboardingSlide = {
  id: 'qw_csv_import',
  type: 'quick_win',
  title: 'Import Your Contacts',
  subtitle: 'Quick Win #7',
  description: "Got a spreadsheet of customers? Upload a CSV and import them all in seconds. Tags, phone numbers, emails  - everything comes in clean.",
  icon: 'cloud-upload',
  iconColor: '#34C759',
  bgGradient: ['#FFFFFF', '#F0FFF5'],
  tryItRoute: '/settings/import-contacts',
  tryItLabel: 'Import Contacts Now',
  quickWinNumber: 7,
  benefits: [
    'Upload a CSV file with your contacts',
    'Map columns to fields automatically',
    'Tags and custom fields supported',
    'Get your whole database in one click',
  ],
};

const QUICK_WIN_CAMPAIGNS: OnboardingSlide = {
  id: 'qw_campaigns',
  type: 'quick_win',
  title: 'Automated Campaigns',
  subtitle: 'Quick Win #8',
  description: "Set up birthday greetings, anniversary messages, and post-sale follow-ups that run automatically. The system does the work  - you get the credit.",
  icon: 'calendar',
  iconColor: '#AF52DE',
  bgGradient: ['#FFFFFF', '#F5F5FF'],
  demoComponent: 'CampaignsDemo',
  tryItRoute: '/settings/date-triggers',
  tryItLabel: 'Set Up Campaigns',
  quickWinNumber: 8,
  benefits: [
    'Auto-send birthday cards & greetings',
    'Post-sale follow-up sequences',
    'Anniversary & holiday messages',
    'Runs daily  - you just set it and forget it',
  ],
};

// ============================================
// MANAGER-SPECIFIC QUICK WINS
// ============================================
const QUICK_WIN_LEADERBOARD: OnboardingSlide = {
  id: 'qw_leaderboard',
  type: 'quick_win',
  title: 'Team Leaderboards',
  subtitle: 'Manager Quick Win',
  description: "See who's leading in messages, reviews, cards shared, and more. Drive healthy competition and celebrate top performers.",
  icon: 'trophy',
  iconColor: '#FFD60A',
  bgGradient: ['#FFFFFF', '#FFFCF0'],
  tryItRoute: '/admin/leaderboard',
  tryItLabel: 'View Leaderboard',
  benefits: [
    'Real-time rankings by category',
    'Messages, reviews, cards, and more',
    'Weekly and monthly views',
    'Motivate your team with visibility',
  ],
};

const QUICK_WIN_REPORTING: OnboardingSlide = {
  id: 'qw_reporting',
  type: 'quick_win',
  title: 'Activity Reports',
  subtitle: 'Manager Quick Win',
  description: "Track every message, card, and review across your team. Filter by date, export data, and schedule automatic email reports.",
  icon: 'analytics',
  iconColor: '#007AFF',
  bgGradient: ['#FFFFFF', '#F0F5FF'],
  tryItRoute: '/admin/reports/activity',
  tryItLabel: 'View Reports',
  benefits: [
    'Track 14+ activity metrics',
    'Filter by date range',
    'Schedule automatic email delivery',
    'Know exactly who\'s doing what',
  ],
};

// ============================================
// ADMIN-SPECIFIC QUICK WINS
// ============================================
const QUICK_WIN_USER_MANAGEMENT: OnboardingSlide = {
  id: 'qw_user_management',
  type: 'quick_win',
  title: 'User & Store Management',
  subtitle: 'Admin Quick Win',
  description: "Add users, assign roles, manage stores, and send invite links  - all from the Admin dashboard. Your team is up and running in minutes.",
  icon: 'people',
  iconColor: '#AF52DE',
  bgGradient: ['#FFFFFF', '#F5F5FF'],
  tryItRoute: '/admin/users',
  tryItLabel: 'Manage Users',
  benefits: [
    'Create accounts & send invite links',
    'Assign roles: Admin, Manager, Salesperson',
    'Manage multiple store locations',
    'Deactivate users without losing data',
  ],
};

// ============================================
// AI SETUP SLIDE
// ============================================
const AI_STYLE_SLIDE: OnboardingSlide = {
  id: 'ai_style_sales',
  type: 'ai_setup',
  title: 'Meet Jessi  - Your AI Assistant',
  subtitle: 'She Responds When You Can\'t',
  description: "Jessi learns your style and responds to customers 24/7. Pick how she should sound:",
  icon: 'sparkles',
  iconColor: '#007AFF',
  bgGradient: ['#FFFFFF', '#FFFBF0'],
  interactiveType: 'choice',
  choices: [
    { id: 'professional', label: 'Professional', description: 'Formal, polished, business-focused', icon: 'briefcase' },
    { id: 'friendly', label: 'Friendly & Warm', description: 'Casual, personable, approachable', icon: 'heart' },
    { id: 'energetic', label: 'High Energy', description: 'Excited, enthusiastic, upbeat', icon: 'flash' },
    { id: 'laid_back', label: 'Laid Back', description: 'Relaxed, easy-going, chill', icon: 'cafe' },
  ],
};

// ============================================
// CHECKLIST SLIDE (before completion)
// ============================================
const SALESPERSON_CHECKLIST: OnboardingSlide = {
  id: 'checklist',
  type: 'checklist',
  title: 'Your Quick Win Checklist',
  subtitle: 'Get Started in 5 Minutes',
  description: "Here's everything you can do right now. Tap any item to jump straight to it after onboarding.",
  icon: 'checkbox',
  iconColor: '#34C759',
  bgGradient: ['#FFFFFF', '#F0FFF5'],
  checklistItems: [
    { id: 'digital_card', label: 'Set up your Digital Business Card', description: 'Add your photo, bio, and social links', route: '/settings/store-profile', icon: 'card', iconColor: '#5856D6' },
    { id: 'congrats_card', label: 'Create your first Congrats Card', description: 'Celebrate a recent sale', route: '/settings/create-congrats', icon: 'gift', iconColor: '#007AFF' },
    { id: 'birthday_card', label: 'Create a Birthday Card', description: 'Send a personal touch', route: '/settings/create-birthday-card', icon: 'gift', iconColor: '#FF6B8A' },
    { id: 'showroom', label: 'Customize your Showroom', description: 'Choose what customers see', route: '/showroom-manage', icon: 'images', iconColor: '#007AFF' },
    { id: 'import_contacts', label: 'Import your contacts via CSV', description: 'Bring in your customer list', route: '/settings/import-contacts', icon: 'cloud-upload', iconColor: '#34C759' },
    { id: 'send_message', label: 'Send your first message', description: 'Text or email a customer', route: '/(tabs)/inbox', icon: 'chatbubble', iconColor: '#FF9500' },
  ],
};

const MANAGER_CHECKLIST: OnboardingSlide = {
  id: 'checklist',
  type: 'checklist',
  title: 'Your Quick Win Checklist',
  subtitle: 'Get Your Team Started',
  description: "Here's everything you can do right now. Tap any item to jump straight to it.",
  icon: 'checkbox',
  iconColor: '#34C759',
  bgGradient: ['#FFFFFF', '#F0FFF5'],
  checklistItems: [
    ...SALESPERSON_CHECKLIST.checklistItems!,
    { id: 'leaderboard', label: 'Check the Leaderboard', description: 'See your team\'s rankings', route: '/admin/leaderboard', icon: 'trophy', iconColor: '#FFD60A' },
    { id: 'reports', label: 'Review Activity Reports', description: 'Track your team\'s output', route: '/admin/reports/activity', icon: 'analytics', iconColor: '#007AFF' },
    { id: 'campaigns', label: 'Set up automated campaigns', description: 'Birthdays, anniversaries, follow-ups', route: '/settings/date-triggers', icon: 'calendar', iconColor: '#AF52DE' },
  ],
};

const ADMIN_CHECKLIST: OnboardingSlide = {
  id: 'checklist',
  type: 'checklist',
  title: 'Your Quick Win Checklist',
  subtitle: 'Launch Your Organization',
  description: "Everything you need to get your team up and running. Tap any item to jump to it.",
  icon: 'checkbox',
  iconColor: '#34C759',
  bgGradient: ['#FFFFFF', '#F0FFF5'],
  checklistItems: [
    ...MANAGER_CHECKLIST.checklistItems!,
    { id: 'manage_users', label: 'Add & invite team members', description: 'Build your team', route: '/admin/users', icon: 'people', iconColor: '#AF52DE' },
  ],
};

// ============================================
// COMPLETION SLIDES
// ============================================
const SALESPERSON_COMPLETE: OnboardingSlide = {
  id: 'complete',
  type: 'complete',
  title: "You're Ready to Win!",
  subtitle: 'Your Sales Toolkit is Live',
  description: "Everything is set up. Your digital card, review page, showroom, and quick actions are all ready to go. Start building relationships!",
  icon: 'checkmark-done',
  iconColor: '#34C759',
  bgGradient: ['#FFFFFF', '#F0FFF5'],
  benefits: [
    'Digital Business Card  - ready to share',
    'Congrats & Birthday Cards  - create anytime',
    'Review Page & Showroom  - live now',
    'Inbox  - start conversations today',
  ],
};

const MANAGER_COMPLETE: OnboardingSlide = {
  id: 'complete',
  type: 'complete',
  title: 'Ready to Lead!',
  subtitle: 'Your Team Toolkit is Live',
  description: "You've got all the tools your team needs. Invite your salespeople and watch the leaderboard light up!",
  icon: 'checkmark-done',
  iconColor: '#34C759',
  bgGradient: ['#FFFFFF', '#F0FFF5'],
  benefits: [
    'All salesperson tools  - ready for your team',
    'Leaderboards & Reports  - track performance',
    'Automated Campaigns  - set and forget',
    'Team Invites  - onboard your people',
  ],
};

const ADMIN_COMPLETE: OnboardingSlide = {
  id: 'complete',
  type: 'complete',
  title: "You're All Set!",
  subtitle: 'Organization Admin Ready',
  description: "Your organization is live. Add stores, invite managers, and let the toolkit cascade to your entire team.",
  icon: 'checkmark-done',
  iconColor: '#34C759',
  bgGradient: ['#FFFFFF', '#F0FFF5'],
  benefits: [
    'Full admin dashboard  - all tools unlocked',
    'User & store management  - at your fingertips',
    'Leaderboards, reports, campaigns  - all live',
    'Invite your managers to start deployment',
  ],
};

// ============================================
// ASSEMBLED ROLE LIBRARIES
// ============================================

export const SALESPERSON_SLIDES: OnboardingSlide[] = [
  ...WELCOME_SLIDES,
  QUICK_WIN_DIGITAL_CARD,
  QUICK_WIN_CONGRATS_CARDS,
  QUICK_WIN_BIRTHDAY_CARDS,
  QUICK_WIN_REVIEW_PAGE,
  QUICK_WIN_SHOWROOM,
  QUICK_WIN_QUICK_ACTIONS,
  QUICK_WIN_CSV_IMPORT,
  QUICK_WIN_CAMPAIGNS,
  AI_STYLE_SLIDE,
  SALESPERSON_CHECKLIST,
  SALESPERSON_COMPLETE,
];

export const STORE_MANAGER_SLIDES: OnboardingSlide[] = [
  ...WELCOME_SLIDES,
  QUICK_WIN_DIGITAL_CARD,
  QUICK_WIN_CONGRATS_CARDS,
  QUICK_WIN_BIRTHDAY_CARDS,
  QUICK_WIN_REVIEW_PAGE,
  QUICK_WIN_SHOWROOM,
  QUICK_WIN_QUICK_ACTIONS,
  QUICK_WIN_CSV_IMPORT,
  QUICK_WIN_CAMPAIGNS,
  QUICK_WIN_LEADERBOARD,
  QUICK_WIN_REPORTING,
  AI_STYLE_SLIDE,
  {
    id: 'invite_salespeople',
    type: 'team_invite' as const,
    title: 'Invite Your Sales Team',
    subtitle: 'Build Your Team',
    description: "i'M On Social",
    icon: 'people-circle',
    iconColor: '#34C759',
    bgGradient: ['#FFFFFF', '#F0FFF5'],
    interactiveType: 'team_invite' as const,
    inviteRole: 'user' as const,
    inviteTitle: 'Salesperson',
    skipable: true,
    benefits: [
      "They'll get their own quick-wins walkthrough",
      'Digital card, congrats cards, and more  - ready instantly',
      "You'll see their activity on your dashboard",
    ],
  },
  MANAGER_CHECKLIST,
  MANAGER_COMPLETE,
];

export const ORG_ADMIN_SLIDES: OnboardingSlide[] = [
  ...WELCOME_SLIDES,
  QUICK_WIN_DIGITAL_CARD,
  QUICK_WIN_CONGRATS_CARDS,
  QUICK_WIN_BIRTHDAY_CARDS,
  QUICK_WIN_REVIEW_PAGE,
  QUICK_WIN_SHOWROOM,
  QUICK_WIN_QUICK_ACTIONS,
  QUICK_WIN_CSV_IMPORT,
  QUICK_WIN_CAMPAIGNS,
  QUICK_WIN_LEADERBOARD,
  QUICK_WIN_REPORTING,
  QUICK_WIN_USER_MANAGEMENT,
  AI_STYLE_SLIDE,
  {
    id: 'invite_managers',
    type: 'team_invite' as const,
    title: 'Invite Your Store Managers',
    subtitle: 'Start the Deployment',
    description: "Add the managers who will run each store. They'll complete their own onboarding and invite their salespeople.",
    icon: 'people-circle',
    iconColor: '#007AFF',
    bgGradient: ['#FFFFFF', '#F0F5FF'],
    interactiveType: 'team_invite' as const,
    inviteRole: 'store_manager' as const,
    inviteTitle: 'Store Manager',
    skipable: true,
    benefits: [
      "Managers get their own quick-wins walkthrough",
      "They'll invite their salespeople next",
      'Cascading deployment from top-down',
    ],
  },
  ADMIN_CHECKLIST,
  ADMIN_COMPLETE,
];

// ============================================
// SLIDE SELECTOR BY ROLE
// ============================================
export const getOnboardingSlidesForRole = (role: string): OnboardingSlide[] => {
  switch (role) {
    case 'super_admin':
    case 'org_admin':
      return ORG_ADMIN_SLIDES;
    case 'store_manager':
      return STORE_MANAGER_SLIDES;
    case 'user':
    default:
      return SALESPERSON_SLIDES;
  }
};
