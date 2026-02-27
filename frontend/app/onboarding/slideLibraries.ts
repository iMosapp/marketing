// Role-Based Onboarding Slide Libraries
// Each role has a customized onboarding experience

import { OnboardingSlide } from './types';

// ============================================
// SHARED SLIDES (Used by all roles)
// ============================================
export const SHARED_SLIDES: OnboardingSlide[] = [
  {
    id: 'welcome',
    type: 'welcome',
    title: 'Welcome to iMOs!',
    subtitle: "i'M On Social",
    description: 'The new way to own your digital presence, reviews, and customer connections.',
    icon: 'rocket',
    iconColor: '#C9A962',
    bgGradient: ['#1A1A2E', '#16213E'],
    benefits: [
      'Quick personalized walkthrough',
      'Set up your social presence',
      'Start building your reputation',
    ],
  },
  {
    id: 'verify_profile',
    type: 'interactive',
    title: 'Verify Your Info',
    subtitle: 'Let\'s Make Sure We Got It Right',
    description: 'This info powers your AI assistant and digital business card.',
    icon: 'checkmark-circle',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    interactiveType: 'multi_input',
    inputFields: [
      { key: 'name', label: 'Your Name', placeholder: 'Full name as others will see it' },
      { key: 'title', label: 'Your Title/Role', placeholder: 'e.g. Regional Manager, Sales Consultant' },
      { key: 'bio', label: 'Short Bio', placeholder: 'A brief intro about yourself...', multiline: true },
    ],
  },
];

// ============================================
// ORG ADMIN SLIDES
// ============================================
export const ORG_ADMIN_SLIDES: OnboardingSlide[] = [
  ...SHARED_SLIDES,
  // Organization Overview
  {
    id: 'org_overview',
    type: 'feature',
    title: 'Your Organization Dashboard',
    subtitle: 'Manage Everything From Here',
    description: 'As an Organization Admin, you have oversight of all stores and team members in your organization.',
    icon: 'business',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    benefits: [
      '🏢 View all stores in your organization',
      '👥 Manage users across all locations',
      '📊 See organization-wide analytics',
      '⚙️ Configure organization settings',
    ],
  },
  // Admin Dashboard Access
  {
    id: 'admin_dashboard',
    type: 'feature',
    title: 'Admin Dashboard',
    subtitle: 'Your Control Center',
    description: 'Access the Admin Dashboard from More → Administration to see real-time data and manage your team.',
    icon: 'stats-chart',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    benefits: [
      '📈 View performance metrics',
      '👥 See all active users',
      '🏪 Monitor store activity',
      '📉 Track engagement trends',
    ],
  },
  // Store Management
  {
    id: 'store_management',
    type: 'feature',
    title: 'Managing Your Stores',
    subtitle: 'Multi-Location Overview',
    description: 'Each store (Account) operates independently but you can view and manage them all.',
    icon: 'storefront',
    iconColor: '#FF9500',
    bgGradient: ['#2E1F0F', '#1A1A1A'],
    benefits: [
      '🏪 View all stores under your organization',
      '👤 See store managers and their teams',
      '📊 Compare performance across locations',
      '➕ Add new stores as you expand',
    ],
  },
  // User Management
  {
    id: 'user_management',
    type: 'feature',
    title: 'Managing Your Team',
    subtitle: 'User Administration',
    description: 'Add, edit, and manage all users across your organization from one place.',
    icon: 'people',
    iconColor: '#AF52DE',
    bgGradient: ['#1A0F2E', '#2D1B4E'],
    benefits: [
      '➕ Create new user accounts',
      '🔑 Send invite links to new team members',
      '👤 Assign users to specific stores',
      '🛡️ Manage user roles & permissions',
    ],
  },
  // Team Invites
  {
    id: 'team_invites',
    type: 'feature',
    title: 'Inviting Your Team',
    subtitle: 'Grow Your Organization',
    description: 'Use invite links to quickly onboard new managers and team members.',
    icon: 'person-add',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#16213E'],
    benefits: [
      '🔗 Generate unique invite links',
      '📱 Share via SMS or email',
      '📊 Track who\'s joined via your links',
      '🎯 Set role automatically when they join',
    ],
  },
  // Reports & Analytics
  {
    id: 'org_reports',
    type: 'feature',
    title: 'Organization Reports',
    subtitle: 'Data-Driven Decisions',
    description: 'Access detailed reports across all your stores to identify trends and opportunities.',
    icon: 'analytics',
    iconColor: '#FF2D55',
    bgGradient: ['#2E0F1A', '#1A1A1A'],
    benefits: [
      '📊 Message volume by store',
      '👥 Lead capture rates',
      '🏆 Top performers across locations',
      '📈 Growth trends over time',
    ],
  },
  // TEAM INVITE - Invite Store Managers
  {
    id: 'invite_managers',
    type: 'team_invite',
    title: 'Invite Your Store Managers',
    subtitle: 'Start the Deployment',
    description: 'Add the managers who will run each store. They\'ll receive an invite and go through their own onboarding.',
    icon: 'people-circle',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    interactiveType: 'team_invite',
    inviteRole: 'store_manager',
    inviteTitle: 'Store Manager',
    skipable: true,
    benefits: [
      '📧 They\'ll receive an email/SMS invite',
      '🎓 They\'ll complete their manager training',
      '👥 Then they\'ll invite their salespeople',
      '🔄 Cascading deployment from top-down',
    ],
  },
  // Complete
  {
    id: 'complete',
    type: 'complete',
    title: 'You\'re All Set!',
    subtitle: 'Organization Admin Ready',
    description: 'You have full access to manage your organization. Your managers will receive their invites and start their onboarding!',
    icon: 'checkmark-done',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    benefits: [
      '✅ Organization dashboard ready',
      '✅ Store manager invites queued',
      '✅ Top-down deployment initiated',
    ],
  },
];

// ============================================
// STORE MANAGER SLIDES
// ============================================
export const STORE_MANAGER_SLIDES: OnboardingSlide[] = [
  ...SHARED_SLIDES,
  // Manager Role Overview
  {
    id: 'manager_overview',
    type: 'feature',
    title: 'Your Manager Dashboard',
    subtitle: 'Lead Your Team to Success',
    description: 'As a Store Manager, you\'re responsible for your location and your team\'s performance.',
    icon: 'shield-checkmark',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    benefits: [
      '👥 Manage your team members',
      '📊 Track team performance',
      '🎯 Set and monitor goals',
      '📱 Support your salespeople',
    ],
  },
  // Your Store
  {
    id: 'your_store',
    type: 'feature',
    title: 'Your Store Dashboard',
    subtitle: 'Location Overview',
    description: 'See everything happening at your location from one central dashboard.',
    icon: 'storefront',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    benefits: [
      '🏪 Your store\'s key metrics',
      '👥 Your team members list',
      '📈 Activity and engagement stats',
      '🔔 Important notifications',
    ],
  },
  // Team Management
  {
    id: 'team_management',
    type: 'feature',
    title: 'Managing Your Team',
    subtitle: 'Build a Winning Team',
    description: 'Add team members, track their progress, and help them succeed.',
    icon: 'people',
    iconColor: '#FF9500',
    bgGradient: ['#2E1F0F', '#1A1A1A'],
    benefits: [
      '➕ Invite new team members',
      '📊 View individual performance',
      '🏆 See leaderboard rankings',
      '💬 Support team conversations',
    ],
  },
  // Team Invites for Managers
  {
    id: 'manager_invites',
    type: 'feature',
    title: 'Growing Your Team',
    subtitle: 'Invite Your Salespeople',
    description: 'Got a new hire? Send them an invite link and they\'ll be set up in minutes.',
    icon: 'person-add',
    iconColor: '#AF52DE',
    bgGradient: ['#1A0F2E', '#2D1B4E'],
    benefits: [
      '🔗 Share your unique invite link',
      '📱 Send via text or email',
      '📊 Track who\'s clicked and joined',
      '✅ New hires land in YOUR team',
    ],
  },
  // Leaderboards
  {
    id: 'leaderboards',
    type: 'feature',
    title: 'Team Leaderboards',
    subtitle: 'Drive Healthy Competition',
    description: 'Motivate your team with real-time leaderboards showing top performers.',
    icon: 'trophy',
    iconColor: '#FFD60A',
    bgGradient: ['#2E2A0F', '#1A1A1A'],
    benefits: [
      '🏆 See who\'s leading in messages',
      '📈 Track contacts and leads',
      '🎯 Weekly and monthly rankings',
      '🔥 Celebrate top performers',
    ],
  },
  // Performance Tracking
  {
    id: 'performance_tracking',
    type: 'feature',
    title: 'Performance Insights',
    subtitle: 'Know Your Numbers',
    description: 'Track your team\'s activity and identify coaching opportunities.',
    icon: 'analytics',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#16213E'],
    benefits: [
      '📊 Messages sent per person',
      '👥 Contacts created',
      '🤖 AI usage and effectiveness',
      '📈 Week-over-week trends',
    ],
  },
  // App Navigation for Managers
  {
    id: 'nav_overview_manager',
    type: 'feature',
    title: 'Your Navigation',
    subtitle: 'Find Everything Fast',
    description: 'The bottom navigation gets you everywhere you need to go:',
    icon: 'apps',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    benefits: [
      '📥 Inbox - Customer conversations',
      '👥 Contacts - Customer database',
      '📞 Keypad - Calls',
      '💬 Team - Team chat + leaderboards',
      '⚙️ More - Admin & settings',
    ],
  },
  // TEAM INVITE - Invite Salespeople
  {
    id: 'invite_salespeople',
    type: 'team_invite',
    title: 'Invite Your Sales Team',
    subtitle: 'Build Your Team',
    description: 'Add the salespeople who will use iMOs. They\'ll receive an invite and complete their training.',
    icon: 'people-circle',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    interactiveType: 'team_invite',
    inviteRole: 'user',
    inviteTitle: 'Salesperson',
    skipable: true,
    benefits: [
      '📧 They\'ll receive an email/SMS invite',
      '🎓 They\'ll learn how to use the tools',
      '🚀 They\'ll be ready to start selling',
      '📊 You\'ll see their activity on your dashboard',
    ],
  },
  // Complete
  {
    id: 'complete',
    type: 'complete',
    title: 'Ready to Lead!',
    subtitle: 'Manager Mode: Activated',
    description: 'You\'re set up to lead your team. Your salespeople will receive their invites and complete their training!',
    icon: 'checkmark-done',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    benefits: [
      '✅ Dashboard ready',
      '✅ Team invites queued',
      '✅ Performance tracking active',
    ],
  },
];

// ============================================
// SALESPERSON SLIDES
// ============================================
export const SALESPERSON_SLIDES: OnboardingSlide[] = [
  ...SHARED_SLIDES,
  // Salesperson Welcome
  {
    id: 'sales_overview',
    type: 'feature',
    title: 'Your Social Toolkit',
    subtitle: 'Own Your Reputation',
    description: 'iMOs is your personal Social Relationship OS. Digital card, reviews, social links, customer connections — all under your name.',
    icon: 'briefcase',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    benefits: [
      'Your own digital business card & review profile',
      'AI assistant that responds when you\'re busy',
      'Social links & reputation that move with you',
      'Track every customer touchpoint',
    ],
  },
  // Navigation
  {
    id: 'nav_overview_sales',
    type: 'feature',
    title: 'Your Home Base',
    subtitle: 'The Bottom Navigation Bar',
    description: 'Five tabs at the bottom of your screen to run your business:',
    icon: 'apps',
    iconColor: '#FF9500',
    bgGradient: ['#2E1F0F', '#1A1A1A'],
    benefits: [
      '📥 Inbox - All your customer texts',
      '👥 Contacts - Your customer database',
      '📞 Keypad - Make & receive calls',
      '💬 Team - Chat with coworkers',
      '⚙️ More - Settings & features',
    ],
  },
  // Inbox
  {
    id: 'inbox_tour_sales',
    type: 'feature',
    title: 'Your Inbox',
    subtitle: 'Where Deals Happen',
    description: 'Every customer conversation lives here. This is your command center.',
    icon: 'chatbubbles',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#16213E'],
    benefits: [
      '🔵 Blue = Your messages',
      '⚪ Gray = Customer replies',
      '✨ Tap to continue any conversation',
      '➕ "New Message" to start fresh',
    ],
  },
  // Contacts
  {
    id: 'contacts_tour_sales',
    type: 'feature',
    title: 'Your Contacts',
    subtitle: 'Your Customer Database',
    description: 'Everyone you\'ve ever talked to is here. Search, filter, and reach out in seconds.',
    icon: 'people',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    benefits: [
      '🔍 Search by name or phone',
      '🏷️ Filter by tags (Hot Lead, VIP, etc.)',
      '➕ Add new contacts with + button',
      '📱 Tap any contact to text or call',
    ],
  },
  // New Message Flow
  {
    id: 'new_message_flow_sales',
    type: 'feature',
    title: 'Starting a Conversation',
    subtitle: 'How to Text New People',
    description: 'When you meet someone new, here\'s how to add them and start chatting:',
    icon: 'create',
    iconColor: '#FF9500',
    bgGradient: ['#2E1F0F', '#1A1A1A'],
    benefits: [
      '1️⃣ Tap "New Message" in Inbox',
      '2️⃣ Type their phone number',
      '3️⃣ Add their name, photo & tags',
      '4️⃣ Send message - saves automatically!',
    ],
  },
  // Meet Jessi AI
  {
    id: 'ai_assistant_sales',
    type: 'feature',
    title: 'Meet Jessi',
    subtitle: 'Your AI Assistant',
    description: 'Jessi is your personal AI that responds to customers when you\'re busy. She learns your style!',
    icon: 'sparkles',
    iconColor: '#C9A962',
    bgGradient: ['#2E2A1A', '#1A1A1A'],
    demoComponent: 'AISuggestionsDemo',
    benefits: [
      '🤖 Responds 24/7',
      '🎯 Learns YOUR style',
      '💬 Suggests responses',
      '📍 Find in More → Ask Jessi',
    ],
  },
  // AI Style Setup
  {
    id: 'ai_style_sales',
    type: 'ai_setup',
    title: 'How Do You Talk?',
    subtitle: 'Set Jessi\'s Communication Style',
    description: 'Help Jessi match your vibe. How do you usually talk to customers?',
    icon: 'chatbubble-ellipses',
    iconColor: '#007AFF',
    bgGradient: ['#0F1A2E', '#1A2E4E'],
    interactiveType: 'choice',
    choices: [
      { id: 'professional', label: 'Professional', description: 'Formal, polished, business-focused', icon: 'briefcase' },
      { id: 'friendly', label: 'Friendly & Warm', description: 'Casual, personable, approachable', icon: 'heart' },
      { id: 'energetic', label: 'High Energy', description: 'Excited, enthusiastic, upbeat', icon: 'flash' },
      { id: 'laid_back', label: 'Laid Back', description: 'Relaxed, easy-going, chill', icon: 'cafe' },
    ],
  },
  // Digital Business Card
  {
    id: 'digital_card_sales',
    type: 'feature',
    title: 'Your Digital Business Card',
    subtitle: 'Your Personal Social Hub',
    description: 'A sleek, shareable card with your photo, contact info, social links, personal reviews, and QR code. Your reputation, in one link.',
    icon: 'card',
    iconColor: '#5856D6',
    bgGradient: ['#1A0F2E', '#2D1B4E'],
    demoComponent: 'DigitalCardDemo',
    benefits: [
      'Share via text, email, or QR code',
      'Personal reviews live on your card',
      'Social links all in one place',
      'Your reputation moves with you',
    ],
  },
  // Congrats Cards
  {
    id: 'congrats_cards_sales',
    type: 'feature',
    title: 'Congrats Cards',
    subtitle: 'Celebrate Every Deal',
    description: 'Send beautiful, shareable cards when your customers buy. They\'ll love sharing on social media!',
    icon: 'gift',
    iconColor: '#FF2D55',
    bgGradient: ['#2E0F1A', '#1A1A1A'],
    demoComponent: 'CongratsCardDemo',
    benefits: [
      '🎉 Celebrate customer purchases',
      '📸 Beautiful shareable graphics',
      '📱 Customers share on social media',
      '🔄 Free marketing for you!',
    ],
  },
  // Templates
  {
    id: 'templates_sales',
    type: 'feature',
    title: 'Message Templates',
    subtitle: 'Save Time on Repeat Messages',
    description: 'Create templates for messages you send often. One tap to send!',
    icon: 'document-text',
    iconColor: '#FF9500',
    bgGradient: ['#2E1F0F', '#1A1A1A'],
    benefits: [
      '📝 Save your best messages',
      '⚡ Send with one tap',
      '🎯 Personalize with merge fields',
      '📍 Find in More → Templates',
    ],
  },
  // Performance
  {
    id: 'performance_sales',
    type: 'feature',
    title: 'Your Performance',
    subtitle: 'Know Your Numbers',
    description: 'Track your activity and see how you\'re doing compared to your team.',
    icon: 'trending-up',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    demoComponent: 'AnalyticsDemo',
    benefits: [
      '📊 Messages sent & responses',
      '👥 Leads captured',
      '🏆 Team leaderboard position',
      '📈 Weekly trends',
    ],
  },
  // Training Hub
  {
    id: 'training_hub_sales',
    type: 'feature',
    title: 'Training Hub',
    subtitle: 'Level Up Your Skills',
    description: 'Video tutorials and guides to help you master iMOs and close more deals.',
    icon: 'school',
    iconColor: '#AF52DE',
    bgGradient: ['#1A0F2E', '#2D1B4E'],
    benefits: [
      '🎥 Step-by-step video tutorials',
      '📚 Best practices guides',
      '💡 Tips from top performers',
      '📍 Find in More → Training Hub',
    ],
  },
  // Complete
  {
    id: 'complete',
    type: 'complete',
    title: 'You\'re Ready!',
    subtitle: 'Go Close Some Deals',
    description: 'You\'ve got everything you need. Time to start building relationships!',
    icon: 'checkmark-done',
    iconColor: '#34C759',
    bgGradient: ['#0F2E1A', '#1A2E1A'],
    benefits: [
      '✅ Inbox ready for conversations',
      '✅ AI assistant trained',
      '✅ Digital card ready to share',
    ],
  },
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
