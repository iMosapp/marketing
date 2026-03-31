import axios from 'axios';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Get backend URL - use relative path for web, env var for native
const getBackendUrl = () => {
  // On web (browser), always use relative path so it works on any domain
  if (Platform.OS === 'web') {
    return '/api';
  }
  // On native (iOS/Android), use the configured backend URL
  const backendUrl = process.env.EXPO_PUBLIC_BACKEND_URL || Constants.expoConfig?.extra?.backendUrl;
  if (backendUrl) {
    return `${backendUrl}/api`;
  }
  return '/api';
};

const BACKEND_URL = getBackendUrl();

const api = axios.create({
  baseURL: BACKEND_URL,
  timeout: 60000, // 60 seconds for AI/voice processing
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token and user ID
// Uses in-memory Zustand state first (instant), falls back to AsyncStorage only if needed
api.interceptors.request.use(
  async (config) => {
    try {
      // Try in-memory state first — avoids AsyncStorage read on every request
      const { useAuthStore } = await import('../store/authStore');
      const { user } = useAuthStore.getState();
      if (user?._id) {
        config.headers['X-User-ID'] = user._id;
        return config;
      }
      // Fallback: read from AsyncStorage (cold boot, before loadAuth completes)
      const userStr = await AsyncStorage.getItem('user');
      if (userStr) {
        try {
          const parsed = JSON.parse(userStr);
          if (parsed?._id) {
            config.headers['X-User-ID'] = parsed._id;
          }
        } catch {}
      }
    } catch (e) {
      console.log('Error getting user for header:', e);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: auto-restore session from cookie on 401
let isRestoringSession = false;
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    // If we get a 401 and haven't already tried to restore, try cookie-based restore
    if (error.response?.status === 401 && !originalRequest._retried && !isRestoringSession 
        && !originalRequest.url?.includes('/auth/me') && !originalRequest.url?.includes('/auth/login')) {
      originalRequest._retried = true;
      isRestoringSession = true;
      try {
        const res = await api.get('/auth/me');
        if (res.data?.user && res.data?.token) {
          await AsyncStorage.setItem('auth_token', res.data.token);
          await AsyncStorage.setItem('user', JSON.stringify(res.data.user));
          // Update auth store
          const { useAuthStore } = await import('../store/authStore');
          useAuthStore.getState().setUser(res.data.user);
          useAuthStore.getState().setToken(res.data.token);
          isRestoringSession = false;
          // Retry the original request
          return api(originalRequest);
        }
      } catch {
        // Cookie restore failed — user truly needs to log in
      }
      isRestoringSession = false;
    }
    if (error.response) {
      console.error('API Error:', error.response.data);
      // Report server errors (5xx) and unexpected client errors to error tracking
      if (error.response.status >= 500) {
        import('../services/errorReporter').then(({ reportError }) => {
          reportError({
            error_message: `API ${error.response.status}: ${error.config?.method?.toUpperCase()} ${error.config?.url} — ${JSON.stringify(error.response.data)?.slice(0, 300)}`,
            error_type: 'api_error',
            extra: { status: error.response.status, url: error.config?.url, method: error.config?.method },
          });
        }).catch(() => {});
      }
    } else if (error.request) {
      console.error('Network Error:', error.message);
      // Report network failures (server unreachable)
      import('../services/errorReporter').then(({ reportError }) => {
        reportError({
          error_message: `Network Error: ${error.message} — ${error.config?.method?.toUpperCase()} ${error.config?.url}`,
          error_type: 'api_error',
          extra: { url: error.config?.url, method: error.config?.method },
        });
      }).catch(() => {});
    } else {
      console.error('Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// ============= AUTH API =============
export const authAPI = {
  signup: async (data: {
    email: string;
    password: string;
    name: string;
    phone: string;
    mode?: string;
  }) => {
    const response = await api.post('/auth/signup', data);
    return response.data;
  },

  login: async (email: string, password: string) => {
    // Auto-detect user timezone for scheduling features
    let timezone: string | undefined;
    try {
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {}
    const response = await api.post('/auth/login', { email, password, timezone });
    return response.data;
  },

  getUser: async (userId: string) => {
    const response = await api.get(`/user/${userId}`);
    return response.data;
  },

  forgotPassword: async (email: string) => {
    const response = await api.post('/auth/forgot-password/request', { email });
    return response.data;
  },

  verifyResetCode: async (email: string, code: string) => {
    const response = await api.post('/auth/forgot-password/verify', { email, code });
    return response.data;
  },

  resetPassword: async (email: string, code: string, newPassword: string) => {
    const response = await api.post('/auth/forgot-password/reset', { 
      email, 
      code, 
      new_password: newPassword 
    });
    return response.data;
  },

  changePassword: async (userId: string, currentPassword: string, newPassword: string) => {
    const response = await api.post('/auth/change-password', { 
      user_id: userId,
      current_password: currentPassword, 
      new_password: newPassword 
    });
    return response.data;
  },
};

// ============= ONBOARDING API =============
export const onboardingAPI = {
  savePersona: async (userId: string, persona: any) => {
    const response = await api.post(`/onboarding/profile/${userId}`, persona);
    return response.data;
  },

  getPersona: async (userId: string) => {
    const response = await api.get(`/onboarding/profile/${userId}`);
    return response.data;
  },
};

// ============= CONTACTS API =============
export const contactsAPI = {
  getAll: async (userId: string, search?: string, viewMode?: string, sortBy?: string, skip = 0, limit = 50) => {
    const params: any = { skip, limit, paginated: true };
    if (search) params.search = search;
    if (viewMode) params.view_mode = viewMode;
    if (sortBy) params.sort_by = sortBy;
    const response = await api.get(`/contacts/${userId}`, { params });
    // Support both paginated {contacts, total, has_more} and legacy array response
    if (Array.isArray(response.data)) return { contacts: response.data, total: response.data.length, has_more: false };
    return response.data;
  },

  getById: async (userId: string, contactId: string) => {
    const response = await api.get(`/contacts/${userId}/${contactId}`);
    return response.data;
  },

  getFullPhoto: async (userId: string, contactId: string) => {
    const response = await api.get(`/contacts/${userId}/${contactId}/photo/full`);
    return response.data;
  },

  // Voice notes
  getVoiceNotes: async (userId: string, contactId: string) => {
    const response = await api.get(`/voice-notes/${userId}/${contactId}`);
    return response.data;
  },

  uploadVoiceNote: async (userId: string, contactId: string, audioBlob: Blob, duration: number) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice_note.webm');
    formData.append('duration', String(Math.round(duration)));
    const response = await api.post(`/voice-notes/${userId}/${contactId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    });
    return response.data;
  },

  deleteVoiceNote: async (userId: string, contactId: string, noteId: string) => {
    const response = await api.delete(`/voice-notes/${userId}/${contactId}/${noteId}`);
    return response.data;
  },

  // Contact Intel (AI Summary)
  getContactIntel: async (userId: string, contactId: string) => {
    const response = await api.get(`/contact-intel/${userId}/${contactId}`);
    return response.data;
  },

  generateContactIntel: async (userId: string, contactId: string) => {
    const response = await api.post(`/contact-intel/${userId}/${contactId}`, {}, { timeout: 30000 });
    return response.data;
  },

  suggestMessage: async (userId: string, contactId: string) => {
    const response = await api.post(`/contact-intel/${userId}/${contactId}/suggest-message`, {}, { timeout: 20000 });
    return response.data;
  },

  create: async (userId: string, data: any) => {
    const response = await api.post(`/contacts/${userId}`, data);
    return response.data;
  },

  update: async (userId: string, contactId: string, data: any) => {
    const response = await api.put(`/contacts/${userId}/${contactId}`, data);
    return response.data;
  },

  importContacts: async (userId: string, contacts: any[]) => {
    const response = await api.post(`/contacts/${userId}/import`, contacts);
    return response.data;
  },

  getReferrals: async (userId: string, contactId: string) => {
    const response = await api.get(`/contacts/${userId}/${contactId}/referrals`);
    return response.data;
  },

  delete: async (userId: string, contactId: string) => {
    const response = await api.delete(`/contacts/${userId}/${contactId}`);
    return response.data;
  },

  bulkDelete: async (userId: string, contactIds: string[]) => {
    const response = await api.post(`/contacts/${userId}/bulk-delete`, { contact_ids: contactIds });
    return response.data;
  },

  getEvents: async (userId: string, contactId: string, limit: number = 50) => {
    const response = await api.get(`/contacts/${userId}/${contactId}/events`, { params: { limit } });
    return response.data;
  },

  getStats: async (userId: string, contactId: string) => {
    const response = await api.get(`/contacts/${userId}/${contactId}/stats`);
    return response.data;
  },

  logEvent: async (userId: string, contactId: string, eventData: any) => {
    const response = await api.post(`/contacts/${userId}/${contactId}/events`, eventData);
    return response.data;
  },
};

// ============= MESSAGES API =============
export const messagesAPI = {
  getConversations: async (userId: string) => {
    const response = await api.get(`/messages/conversations/${userId}`);
    return response.data;
  },

  getThread: async (conversationId: string) => {
    const response = await api.get(`/messages/thread/${conversationId}`);
    return response.data;
  },

  send: async (userId: string, data: { conversation_id: string; content: string; media_url?: string; channel?: string; event_type?: string }) => {
    const response = await api.post(`/messages/send/${userId}/${data.conversation_id}`, data);
    return response.data;
  },

  createConversation: async (userId: string, data: { contact_id: string; contact_phone?: string }) => {
    const response = await api.post(`/messages/conversations/${userId}`, data);
    return response.data;
  },

  getAISuggestion: async (conversationId: string) => {
    const response = await api.post(`/messages/ai-suggest/${conversationId}`);
    return response.data;
  },

  getReviewLinks: async (userId: string) => {
    const response = await api.get(`/users/${userId}/review-links`);
    return response.data;
  },

  // Quick actions for conversations (use singular 'conversation' to avoid route conflicts)
  archiveConversation: async (conversationId: string) => {
    const response = await api.put(`/messages/conversation/${conversationId}/archive`);
    return response.data;
  },

  restoreConversation: async (conversationId: string) => {
    const response = await api.put(`/messages/conversation/${conversationId}/restore`);
    return response.data;
  },

  markAsRead: async (conversationId: string) => {
    const response = await api.put(`/messages/conversation/${conversationId}/read`);
    return response.data;
  },

  markAsUnread: async (conversationId: string) => {
    const response = await api.put(`/messages/conversation/${conversationId}/unread`);
    return response.data;
  },

  deleteConversation: async (conversationId: string) => {
    const response = await api.delete(`/messages/conversation/${conversationId}`);
    return response.data;
  },

  flagConversation: async (userId: string, conversationId: string, flagged: boolean) => {
    const response = await api.put(`/messages/conversations/${userId}/${conversationId}`, { flagged });
    return response.data;
  },

  updateConversation: async (userId: string, conversationId: string, data: any) => {
    const response = await api.put(`/messages/conversations/${userId}/${conversationId}`, data);
    return response.data;
  },

  // Bulk actions
  bulkArchive: async (conversationIds: string[]) => {
    const response = await api.post('/messages/bulk/archive', { conversation_ids: conversationIds });
    return response.data;
  },

  bulkRestore: async (conversationIds: string[]) => {
    const response = await api.post('/messages/bulk/restore', { conversation_ids: conversationIds });
    return response.data;
  },

  bulkMarkRead: async (conversationIds: string[]) => {
    const response = await api.post('/messages/bulk/read', { conversation_ids: conversationIds });
    return response.data;
  },

  bulkMarkUnread: async (conversationIds: string[]) => {
    const response = await api.post('/messages/bulk/unread', { conversation_ids: conversationIds });
    return response.data;
  },

  bulkDelete: async (conversationIds: string[]) => {
    const response = await api.post('/messages/bulk/delete', { conversation_ids: conversationIds });
    return response.data;
  },
};

// ============= CALLS API =============
export const callsAPI = {
  create: async (userId: string, data: {
    contact_id: string;
    type: string;
    duration?: number;
  }) => {
    const response = await api.post(`/calls/${userId}`, data);
    return response.data;
  },

  getAll: async (userId: string, callType?: string) => {
    const params = callType ? { call_type: callType } : {};
    const response = await api.get(`/calls/${userId}`, { params });
    return response.data;
  },
};

// ============= CAMPAIGNS API =============
export const campaignsAPI = {
  getAll: async (userId: string) => {
    const response = await api.get(`/campaigns/${userId}`);
    return response.data;
  },

  get: async (userId: string, campaignId: string) => {
    const response = await api.get(`/campaigns/${userId}/${campaignId}`);
    return response.data;
  },

  create: async (userId: string, data: any) => {
    const response = await api.post(`/campaigns/${userId}`, data);
    return response.data;
  },

  update: async (userId: string, campaignId: string, data: any) => {
    const response = await api.put(`/campaigns/${userId}/${campaignId}`, data);
    return response.data;
  },

  delete: async (userId: string, campaignId: string) => {
    const response = await api.delete(`/campaigns/${userId}/${campaignId}`);
    return response.data;
  },

  duplicate: async (userId: string, campaignId: string) => {
    const response = await api.post(`/campaigns/${userId}/${campaignId}/duplicate`);
    return response.data;
  },

  // Enrollment methods
  enrollContact: async (userId: string, campaignId: string, contactId: string) => {
    const response = await api.post(`/campaigns/${userId}/${campaignId}/enroll/${contactId}`);
    return response.data;
  },

  getEnrollments: async (userId: string, campaignId: string, status?: string) => {
    const params = status ? { status } : {};
    const response = await api.get(`/campaigns/${userId}/${campaignId}/enrollments`, { params });
    return response.data;
  },

  cancelEnrollment: async (userId: string, campaignId: string, enrollmentId: string) => {
    const response = await api.delete(`/campaigns/${userId}/${campaignId}/enrollments/${enrollmentId}`);
    return response.data;
  },

  // Scheduler methods
  getPendingCount: async () => {
    const response = await api.get('/campaigns/scheduler/pending');
    return response.data;
  },

  processScheduler: async () => {
    const response = await api.post('/campaigns/scheduler/process');
    return response.data;
  },
};

// ============= TASKS API =============
export const tasksAPI = {
  getAll: async (userId: string, completed?: boolean) => {
    const params = completed !== undefined ? { completed } : {};
    const response = await api.get(`/tasks/${userId}`, { params });
    return response.data;
  },

  getFiltered: async (userId: string, filter: string = 'today', limit: number = 50) => {
    const response = await api.get(`/tasks/${userId}`, { params: { filter, limit } });
    return response.data;
  },

  getSummary: async (userId: string) => {
    const response = await api.get(`/tasks/${userId}/summary`);
    return response.data;
  },

  getPerformance: async (userId: string, period: string = 'week') => {
    const response = await api.get(`/tasks/${userId}/performance`, { params: { period } });
    return response.data;
  },

  create: async (userId: string, data: any) => {
    const response = await api.post(`/tasks/${userId}`, data);
    return response.data;
  },

  update: async (userId: string, taskId: string, data: any) => {
    const response = await api.put(`/tasks/${userId}/${taskId}`, data);
    return response.data;
  },

  patchTask: async (userId: string, taskId: string, data: any) => {
    const response = await api.patch(`/tasks/${userId}/${taskId}`, data);
    return response.data;
  },

  delete: async (userId: string, taskId: string) => {
    const response = await api.delete(`/tasks/${userId}/${taskId}`);
    return response.data;
  },
};

// ============= AI API =============
export const aiAPI = {
  generateMessage: async (userId: string, context: string, intent: string) => {
    const response = await api.post(
      `/ai/generate-message?user_id=${userId}&context=${encodeURIComponent(context)}&intent=${intent}`
    );
    return response.data;
  },

  detectIntent: async (message: string) => {
    const response = await api.post('/ai/detect-intent', { message });
    return response.data;
  },
};

// ============= ADMIN API =============
export const adminAPI = {
  // Organizations
  createOrganization: async (data: any) => {
    const response = await api.post('/admin/organizations', data);
    return response.data;
  },

  listOrganizations: async () => {
    const response = await api.get('/admin/organizations');
    return response.data;
  },

  getOrganization: async (orgId: string) => {
    const response = await api.get(`/admin/organizations/${orgId}`);
    return response.data;
  },

  updateOrganization: async (orgId: string, data: any) => {
    const response = await api.put(`/admin/organizations/${orgId}`, data);
    return response.data;
  },

  deleteOrganization: async (orgId: string) => {
    const response = await api.delete(`/admin/organizations/${orgId}`);
    return response.data;
  },

  // Stores
  createStore: async (data: any) => {
    const response = await api.post('/admin/stores', data);
    return response.data;
  },

  listStores: async (orgId: string) => {
    const response = await api.get(`/admin/stores?organization_id=${orgId}`);
    return response.data;
  },

  getStore: async (storeId: string) => {
    const response = await api.get(`/admin/stores/${storeId}`);
    return response.data;
  },

  updateStore: async (storeId: string, data: any) => {
    const response = await api.put(`/admin/stores/${storeId}`, data);
    return response.data;
  },

  deleteStore: async (storeId: string) => {
    const response = await api.delete(`/admin/stores/${storeId}`);
    return response.data;
  },

  // Users (Admin)
  createUser: async (data: any) => {
    const response = await api.post('/admin/users', data);
    return response.data;
  },

  listOrgUsers: async (orgId: string, storeId?: string, role?: string) => {
    const params: any = {};
    if (storeId) params.store_id = storeId;
    if (role) params.role = role;
    const response = await api.get(`/admin/organizations/${orgId}/users`, { params });
    return response.data;
  },

  updateUser: async (userId: string, data: any) => {
    const response = await api.put(`/admin/users/${userId}`, data);
    return response.data;
  },

  deleteUser: async (userId: string) => {
    const response = await api.delete(`/admin/users/${userId}`);
    return response.data;
  },

  // Stats
  getStats: async (orgId?: string) => {
    const params = orgId ? { org_id: orgId } : {};
    const response = await api.get('/admin/stats', { params });
    return response.data;
  },

  // Leaderboard
  getLeaderboard: async (orgId: string, storeId?: string, metric?: string) => {
    const params: any = {};
    if (storeId) params.store_id = storeId;
    if (metric) params.metric = metric;
    const response = await api.get(`/admin/organizations/${orgId}/leaderboard`, { params });
    return response.data;
  },

  // Regional Leaderboard (Independents)
  getRegionalLeaderboard: async (userId: string, scope?: string, metric?: string) => {
    const params: any = { user_id: userId };
    if (scope) params.scope = scope;
    if (metric) params.metric = metric;
    const response = await api.get('/leaderboard/regional', { params });
    return response.data;
  },

  getLeaderboardSettings: async (userId: string) => {
    const response = await api.get(`/users/${userId}/leaderboard-settings`);
    return response.data;
  },

  updateLeaderboardSettings: async (userId: string, settings: { leaderboard_visible?: boolean; compare_scope?: string }) => {
    const response = await api.put(`/users/${userId}/leaderboard-settings`, settings);
    return response.data;
  },

  // Activity Feed
  getActivityFeed: async (userId: string, limit: number = 20) => {
    const response = await api.get(`/activity/${userId}`, { params: { limit } });
    return response.data;
  },
};

// ============= TEMPLATES API =============
export const templatesAPI = {
  getAll: async (userId: string) => {
    const response = await api.get(`/templates/${userId}`);
    return response.data;
  },

  get: async (userId: string, templateId: string) => {
    const response = await api.get(`/templates/${userId}/${templateId}`);
    return response.data;
  },

  create: async (userId: string, template: { name: string; content: string; category?: string }) => {
    const response = await api.post(`/templates/${userId}`, template);
    return response.data;
  },

  update: async (userId: string, templateId: string, template: { name?: string; content?: string; category?: string }) => {
    const response = await api.put(`/templates/${userId}/${templateId}`, template);
    return response.data;
  },

  delete: async (userId: string, templateId: string) => {
    const response = await api.delete(`/templates/${userId}/${templateId}`);
    return response.data;
  },

  trackUsage: async (userId: string, templateId: string) => {
    const response = await api.post(`/templates/${userId}/${templateId}/use`);
    return response.data;
  },

  getCategories: async (userId: string) => {
    const response = await api.get(`/templates/${userId}/categories/list`);
    return response.data;
  },
};

// ============= TAGS API =============
export const tagsAPI = {
  getAll: async (userId: string) => {
    const response = await api.get(`/tags/${userId}`);
    return response.data;
  },

  getPending: async (userId: string) => {
    const response = await api.get(`/tags/${userId}/pending`);
    return response.data;
  },

  create: async (userId: string, tag: { name: string; color: string; icon?: string }) => {
    const response = await api.post(`/tags/${userId}`, tag);
    return response.data;
  },

  approve: async (userId: string, tagId: string) => {
    const response = await api.post(`/tags/${userId}/approve/${tagId}`);
    return response.data;
  },

  reject: async (userId: string, tagId: string) => {
    const response = await api.post(`/tags/${userId}/reject/${tagId}`);
    return response.data;
  },

  update: async (userId: string, tagId: string, tag: { name?: string; color?: string; icon?: string }) => {
    const response = await api.put(`/tags/${userId}/${tagId}`, tag);
    return response.data;
  },

  delete: async (userId: string, tagId: string) => {
    const response = await api.delete(`/tags/${userId}/${tagId}`);
    return response.data;
  },

  getColors: async (userId: string) => {
    const response = await api.get(`/tags/${userId}/colors`);
    return response.data;
  },

  assignToContacts: async (userId: string, tagName: string, contactIds: string[]) => {
    const response = await api.post(`/tags/${userId}/assign`, { tag_name: tagName, contact_ids: contactIds });
    return response.data;
  },

  removeFromContacts: async (userId: string, tagName: string, contactIds: string[]) => {
    const response = await api.post(`/tags/${userId}/remove`, { tag_name: tagName, contact_ids: contactIds });
    return response.data;
  },

  getContactsByTag: async (userId: string, tagName: string) => {
    const response = await api.get(`/tags/${userId}/contacts/${encodeURIComponent(tagName)}`);
    return response.data;
  },
};

// ============= SEARCH API =============
export const searchAPI = {
  globalSearch: async (userId: string, query: string, types?: string[], limit?: number) => {
    const params: any = { q: query };
    if (types && types.length > 0) params.types = types.join(',');
    if (limit) params.limit = limit;
    const response = await api.get(`/search/${userId}`, { params });
    return response.data;
  },

  getSuggestions: async (userId: string, query: string, limit?: number) => {
    const params: any = { q: query };
    if (limit) params.limit = limit;
    const response = await api.get(`/search/${userId}/suggestions`, { params });
    return response.data;
  },
};

// ============= EMAIL API =============
export const emailAPI = {
  // Send email
  send: async (userId: string, data: {
    recipient_email: string;
    recipient_name?: string;
    subject: string;
    html_content: string;
    contact_id?: string;
  }) => {
    const response = await api.post(`/email/send?user_id=${userId}`, data);
    return response.data;
  },

  // Email Templates
  getTemplates: async (userId: string) => {
    const response = await api.get(`/email/templates/${userId}`);
    return response.data;
  },

  createTemplate: async (userId: string, template: {
    name: string;
    subject: string;
    html_content: string;
    category?: string;
    description?: string;
  }) => {
    const response = await api.post(`/email/templates/${userId}`, template);
    return response.data;
  },

  updateTemplate: async (userId: string, templateId: string, template: any) => {
    const response = await api.put(`/email/templates/${userId}/${templateId}`, template);
    return response.data;
  },

  deleteTemplate: async (userId: string, templateId: string) => {
    const response = await api.delete(`/email/templates/${userId}/${templateId}`);
    return response.data;
  },

  // Email Campaigns
  getCampaigns: async (userId: string) => {
    const response = await api.get(`/email/campaigns/${userId}`);
    return response.data;
  },

  createCampaign: async (userId: string, campaign: {
    name: string;
    description?: string;
    subject: string;
    html_content: string;
    trigger_type?: string;
  }) => {
    const response = await api.post(`/email/campaigns/${userId}`, campaign);
    return response.data;
  },

  updateCampaign: async (userId: string, campaignId: string, updates: any) => {
    const response = await api.put(`/email/campaigns/${userId}/${campaignId}`, updates);
    return response.data;
  },

  deleteCampaign: async (userId: string, campaignId: string) => {
    const response = await api.delete(`/email/campaigns/${userId}/${campaignId}`);
    return response.data;
  },

  // Brand Kit
  getBrandKit: async (entityType: 'user' | 'store' | 'organization', entityId: string) => {
    const response = await api.get(`/email/brand-kit/${entityType}/${entityId}`);
    return response.data;
  },

  updateBrandKit: async (entityType: 'user' | 'store' | 'organization', entityId: string, brandKit: any) => {
    const response = await api.put(`/email/brand-kit/${entityType}/${entityId}`, brandKit);
    return response.data;
  },

  // User Preferences (toggle style, default mode)
  getPreferences: async (userId: string) => {
    const response = await api.get(`/email/preferences/${userId}`);
    return response.data;
  },

  updatePreferences: async (userId: string, preferences: {
    default_mode?: 'sms' | 'email';
    toggle_style?: 'pill' | 'fab' | 'tabs' | 'segmented';
  }) => {
    const response = await api.put(`/email/preferences/${userId}`, preferences);
    return response.data;
  },

  // Email Logs
  getLogs: async (userId: string, limit?: number) => {
    const params = limit ? { limit } : {};
    const response = await api.get(`/email/logs/${userId}`, { params });
    return response.data;
  },

  // Email Analytics
  getAnalytics: async (userId: string, days?: number) => {
    const params = days ? { days } : {};
    const response = await api.get(`/email/analytics/${userId}`, { params });
    return response.data;
  },
};

export default api;

// Leaderboard API
export const leaderboardAPI = {
  getStore: async (userId: string, month?: number, year?: number, category?: string, period?: string) => {
    const params = new URLSearchParams();
    if (month) params.append('month', String(month));
    if (year) params.append('year', String(year));
    if (category) params.append('category', category);
    if (period) params.append('period', period);
    const response = await api.get(`/leaderboard/v2/store/${userId}?${params}`);
    return response.data;
  },
  getOrg: async (userId: string, month?: number, year?: number, category?: string, period?: string) => {
    const params = new URLSearchParams();
    if (month) params.append('month', String(month));
    if (year) params.append('year', String(year));
    if (category) params.append('category', category);
    if (period) params.append('period', period);
    const response = await api.get(`/leaderboard/v2/org/${userId}?${params}`);
    return response.data;
  },
  getGlobal: async (userId: string, month?: number, year?: number, category?: string, period?: string) => {
    const params = new URLSearchParams();
    if (month) params.append('month', String(month));
    if (year) params.append('year', String(year));
    if (category) params.append('category', category);
    if (period) params.append('period', period);
    const response = await api.get(`/leaderboard/v2/global/${userId}?${params}`);
    return response.data;
  },
};

// ============= PERMISSION TEMPLATES API =============
export const permissionTemplatesAPI = {
  list: async (storeId?: string, orgId?: string) => {
    const params = new URLSearchParams();
    if (storeId) params.append('store_id', storeId);
    if (orgId) params.append('org_id', orgId);
    const response = await api.get(`/permission-templates/?${params}`);
    return response.data;
  },

  get: async (templateId: string) => {
    const response = await api.get(`/permission-templates/${templateId}`);
    return response.data;
  },

  create: async (data: any, userId: string) => {
    const response = await api.post('/permission-templates/', data, {
      headers: { 'X-User-ID': userId },
    });
    return response.data;
  },

  update: async (templateId: string, data: any, userId: string) => {
    const response = await api.put(`/permission-templates/${templateId}`, data, {
      headers: { 'X-User-ID': userId },
    });
    return response.data;
  },

  delete: async (templateId: string, userId: string) => {
    const response = await api.delete(`/permission-templates/${templateId}`, {
      headers: { 'X-User-ID': userId },
    });
    return response.data;
  },

  apply: async (templateId: string, targetUserId: string, requestingUserId: string) => {
    const response = await api.post(`/permission-templates/${templateId}/apply/${targetUserId}`, {}, {
      headers: { 'X-User-ID': requestingUserId },
    });
    return response.data;
  },

  getAuditLog: async (limit: number = 50) => {
    const response = await api.get(`/permission-templates/audit-log?limit=${limit}`);
    return response.data;
  },
};

