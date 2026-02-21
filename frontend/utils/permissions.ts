/**
 * Role-Based Access Control (RBAC) Permissions System
 * 
 * Roles hierarchy (highest to lowest):
 * 1. super_admin - Platform owner, sees everything globally
 * 2. org_admin - Organization admin, sees all stores/users within their org
 * 3. store_manager - Store manager, sees users/data within their store(s)
 * 4. user - Regular sales rep, sees only their own data
 */

export type UserRole = 'super_admin' | 'org_admin' | 'store_manager' | 'user';

export interface User {
  _id: string;
  role: UserRole;
  organization_id?: string;
  store_id?: string;
  store_ids?: string[];
}

// Permission categories
export type Permission = 
  // Customer management
  | 'view_organizations'
  | 'manage_organizations'
  | 'view_all_stores'
  | 'view_org_stores'
  | 'view_store_stores'
  | 'manage_stores'
  | 'view_all_users'
  | 'view_org_users'
  | 'view_store_users'
  | 'manage_users'
  | 'view_individuals'
  // Data access
  | 'view_global_data'
  | 'view_org_data'
  | 'view_store_data'
  | 'view_own_data'
  // Tools
  | 'view_billing'
  | 'view_invoices'
  | 'view_revenue_forecast'
  | 'approve_users'
  | 'view_leaderboards'
  | 'view_activity_feed'
  | 'view_training_preview'
  | 'manage_onboarding_settings'
  | 'impersonate_users'
  // Admin sections
  | 'view_admin_customers_section'
  | 'view_admin_data_section'
  | 'view_admin_tools_section'
  | 'view_admin_internal_section'
  // Store/Org settings
  | 'manage_campaign_permissions'
  | 'manage_store_settings'
  | 'manage_org_settings';

// Role to permissions mapping
const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  super_admin: [
    // All permissions
    'view_organizations',
    'manage_organizations',
    'view_all_stores',
    'view_org_stores',
    'view_store_stores',
    'manage_stores',
    'view_all_users',
    'view_org_users',
    'view_store_users',
    'manage_users',
    'view_individuals',
    'view_global_data',
    'view_org_data',
    'view_store_data',
    'view_own_data',
    'view_billing',
    'view_invoices',
    'view_revenue_forecast',
    'approve_users',
    'view_leaderboards',
    'view_activity_feed',
    'view_training_preview',
    'manage_onboarding_settings',
    'impersonate_users',
    'view_admin_customers_section',
    'view_admin_data_section',
    'view_admin_tools_section',
    'view_admin_internal_section',
    'manage_campaign_permissions',
    'manage_store_settings',
    'manage_org_settings',
  ],
  
  org_admin: [
    // Can see and manage within their organization
    'view_org_stores',
    'manage_stores',
    'view_org_users',
    'manage_users',
    'view_org_data',
    'view_store_data',
    'view_own_data',
    'approve_users',
    'view_leaderboards',
    'view_activity_feed',
    'view_training_preview',
    'view_admin_customers_section',
    'view_admin_data_section',
    'view_admin_tools_section',
    'manage_campaign_permissions',
    'manage_store_settings',
    'manage_org_settings',
  ],
  
  store_manager: [
    // Can see and manage within their store(s)
    'view_store_stores',
    'view_store_users',
    'view_store_data',
    'view_own_data',
    'view_leaderboards',
    'view_activity_feed',
    'view_training_preview',
    'view_invoices',
    'view_admin_data_section',
    'view_admin_tools_section',
    'manage_store_settings',
  ],
  
  user: [
    // Can only see their own data
    'view_own_data',
    'view_leaderboards',
  ],
};

/**
 * Check if a user has a specific permission
 */
export function hasPermission(user: User | null | undefined, permission: Permission): boolean {
  if (!user || !user.role) return false;
  
  const permissions = ROLE_PERMISSIONS[user.role];
  return permissions?.includes(permission) || false;
}

/**
 * Check if user has any of the given permissions
 */
export function hasAnyPermission(user: User | null | undefined, permissions: Permission[]): boolean {
  return permissions.some(p => hasPermission(user, p));
}

/**
 * Check if user has all of the given permissions
 */
export function hasAllPermissions(user: User | null | undefined, permissions: Permission[]): boolean {
  return permissions.every(p => hasPermission(user, p));
}

/**
 * Get the data scope for a user (what data they can access)
 */
export function getDataScope(user: User | null | undefined): 'global' | 'organization' | 'store' | 'self' {
  if (!user || !user.role) return 'self';
  
  switch (user.role) {
    case 'super_admin':
      return 'global';
    case 'org_admin':
      return 'organization';
    case 'store_manager':
      return 'store';
    default:
      return 'self';
  }
}

/**
 * Check if user can view a specific admin section
 */
export function canViewAdminSection(user: User | null | undefined, section: 'customers' | 'data' | 'tools' | 'internal'): boolean {
  const permissionMap: Record<string, Permission> = {
    customers: 'view_admin_customers_section',
    data: 'view_admin_data_section',
    tools: 'view_admin_tools_section',
    internal: 'view_admin_internal_section',
  };
  
  return hasPermission(user, permissionMap[section]);
}

/**
 * Check if user can access the admin panel at all
 */
export function canAccessAdmin(user: User | null | undefined): boolean {
  if (!user || !user.role) return false;
  return ['super_admin', 'org_admin', 'store_manager'].includes(user.role);
}

/**
 * Get role display name
 */
export function getRoleDisplayName(role: UserRole): string {
  const names: Record<UserRole, string> = {
    super_admin: 'Super Admin',
    org_admin: 'Organization Admin',
    store_manager: 'Store Manager',
    user: 'Sales Rep',
  };
  return names[role] || role;
}

/**
 * Check if a user can manage another user
 */
export function canManageUser(manager: User | null | undefined, targetUser: User): boolean {
  if (!manager || !manager.role) return false;
  
  // Super admin can manage everyone
  if (manager.role === 'super_admin') return true;
  
  // Org admin can manage users in their org (except other org admins)
  if (manager.role === 'org_admin') {
    if (!manager.organization_id) return false;
    if (manager.organization_id !== targetUser.organization_id) return false;
    if (targetUser.role === 'org_admin' || targetUser.role === 'super_admin') return false;
    return true;
  }
  
  // Store manager can manage users in their store(s) (except managers and above)
  if (manager.role === 'store_manager') {
    if (!manager.store_ids || manager.store_ids.length === 0) return false;
    if (!targetUser.store_id && !targetUser.store_ids?.length) return false;
    
    const targetStores = targetUser.store_ids || (targetUser.store_id ? [targetUser.store_id] : []);
    const hasOverlap = targetStores.some(s => manager.store_ids?.includes(s));
    
    if (!hasOverlap) return false;
    if (['super_admin', 'org_admin', 'store_manager'].includes(targetUser.role)) return false;
    return true;
  }
  
  return false;
}

/**
 * Filter admin menu items based on user permissions
 */
export interface AdminMenuItem {
  id: string;
  label: string;
  icon: string;
  route: string;
  requiredPermission?: Permission;
  requiredRole?: UserRole[];
  section: 'customers' | 'data' | 'tools' | 'internal';
}

export function filterMenuItems(user: User | null | undefined, items: AdminMenuItem[]): AdminMenuItem[] {
  if (!user) return [];
  
  return items.filter(item => {
    // Check section permission first
    if (!canViewAdminSection(user, item.section)) return false;
    
    // Check specific permission if required
    if (item.requiredPermission && !hasPermission(user, item.requiredPermission)) return false;
    
    // Check role requirement if specified
    if (item.requiredRole && !item.requiredRole.includes(user.role)) return false;
    
    return true;
  });
}

/**
 * Admin menu items with their permissions
 */
export const ADMIN_MENU_ITEMS: AdminMenuItem[] = [
  // Customers section
  { id: 'organizations', label: 'Organizations', icon: 'business', route: '/admin/organizations', requiredPermission: 'view_organizations', section: 'customers' },
  { id: 'stores', label: 'Stores', icon: 'storefront', route: '/admin/stores', section: 'customers' },
  { id: 'users', label: 'Users', icon: 'people', route: '/admin/users', section: 'customers' },
  { id: 'individuals', label: 'Individuals', icon: 'person', route: '/admin/individuals', requiredPermission: 'view_individuals', section: 'customers' },
  
  // Data section
  { id: 'messages', label: 'Messages', icon: 'chatbubbles', route: '/admin/data/messages', section: 'data' },
  { id: 'calls', label: 'Calls', icon: 'call', route: '/admin/data/calls', section: 'data' },
  { id: 'mvp', label: 'MVP', icon: 'sparkles', route: '/admin/data/ai-messages', section: 'data' },
  { id: 'contacts', label: 'Contacts', icon: 'person', route: '/admin/contacts', section: 'data' },
  { id: 'card-shares', label: 'Card Shares', icon: 'card', route: '/admin/data/card-shares', section: 'data' },
  { id: 'congrats-cards', label: 'Congrats Cards', icon: 'gift', route: '/admin/data/congrats-cards', section: 'data' },
  { id: 'referrals', label: 'Referrals', icon: 'git-network', route: '/admin/data/referrals', section: 'data' },
  { id: 'campaigns', label: 'Campaigns', icon: 'rocket', route: '/admin/data/campaigns', section: 'data' },
  
  // Tools section
  { id: 'billing', label: 'Billing & Revenue', icon: 'card', route: '/admin/billing', requiredPermission: 'view_billing', section: 'tools' },
  { id: 'forecast', label: 'Revenue Forecast', icon: 'trending-up', route: '/admin/forecasting', requiredPermission: 'view_revenue_forecast', section: 'tools' },
  { id: 'pending-users', label: 'Pending Users', icon: 'person-add', route: '/admin/pending-users', requiredPermission: 'approve_users', section: 'tools' },
  { id: 'leaderboards', label: 'Leaderboards', icon: 'trophy', route: '/admin/leaderboards', section: 'tools' },
  { id: 'activity', label: 'Activity', icon: 'pulse', route: '/admin/activity-feed', section: 'tools' },
  { id: 'training-preview', label: 'Training Preview', icon: 'school', route: '/admin/training-preview', section: 'tools' },
  
  // Internal section (super_admin only)
  { id: 'onboarding-settings', label: 'Onboarding Settings', icon: 'settings', route: '/admin/onboarding-settings', requiredPermission: 'manage_onboarding_settings', section: 'internal' },
  { id: 'phone-assignments', label: 'Phone Assignments', icon: 'call', route: '/admin/phone-assignments', section: 'internal' },
  { id: 'partner-agreements', label: 'Partner Agreements', icon: 'document-text', route: '/admin/partner-agreements', section: 'internal' },
  { id: 'discount-codes', label: 'Discount Codes', icon: 'pricetag', route: '/admin/discount-codes', section: 'internal' },
  { id: 'quotes', label: 'Quotes', icon: 'document', route: '/admin/quotes', section: 'internal' },
];

export default {
  hasPermission,
  hasAnyPermission,
  hasAllPermissions,
  getDataScope,
  canViewAdminSection,
  canAccessAdmin,
  getRoleDisplayName,
  canManageUser,
  filterMenuItems,
  ADMIN_MENU_ITEMS,
};
