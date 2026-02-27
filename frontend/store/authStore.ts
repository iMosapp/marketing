import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authAPI } from '../services/api';

interface User {
  _id: string;
  email: string;
  name: string;
  phone: string;
  mvpline_number?: string;
  onboarding_complete: boolean;
  persona?: any;
  store_id?: string;
  organization_id?: string;
  role?: string;
  status?: string;  // pending, active, inactive
  account_type?: string;  // independent, organization
  needs_onboarding?: boolean;
  needs_password_change?: boolean;  // Flag for first-time password change
  isImpersonating?: boolean;  // Flag for impersonation mode
}

interface PartnerBranding {
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

interface AuthState {
  user: User | null;
  token: string | null;
  partnerBranding: PartnerBranding | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isImpersonating: boolean;
  originalUser: User | null;
  originalToken: string | null;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  updateUser: (updates: Partial<User>) => void;
  login: (email: string, password: string) => Promise<void>;
  signup: (data: any) => Promise<void>;
  logout: () => Promise<void>;
  loadAuth: () => Promise<void>;
  startImpersonation: (user: User, token: string) => Promise<void>;
  stopImpersonation: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  isImpersonating: false,
  originalUser: null,
  originalToken: null,
  
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  
  setToken: (token) => set({ token }),
  
  updateUser: (updates) => set((state) => ({
    user: state.user ? { ...state.user, ...updates } : null
  })),
  
  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const response = await authAPI.login(email, password);
      const { user, token } = response;
      
      await AsyncStorage.setItem('auth_token', token);
      await AsyncStorage.setItem('user', JSON.stringify(user));
      
      set({ user, token, isAuthenticated: true, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },
  
  signup: async (data) => {
    set({ isLoading: true });
    try {
      const user = await authAPI.signup(data);
      const token = `token_${user._id}`;
      
      await AsyncStorage.setItem('auth_token', token);
      await AsyncStorage.setItem('user', JSON.stringify(user));
      
      set({ user, token, isAuthenticated: true, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },
  
  logout: async () => {
    await AsyncStorage.removeItem('auth_token');
    await AsyncStorage.removeItem('user');
    await AsyncStorage.removeItem('original_auth');
    set({ 
      user: null, 
      token: null, 
      isAuthenticated: false,
      isImpersonating: false,
      originalUser: null,
      originalToken: null 
    });
  },
  
  loadAuth: async () => {
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const userStr = await AsyncStorage.getItem('user');
      const originalAuthStr = await AsyncStorage.getItem('original_auth');
      
      if (token && userStr) {
        const user = JSON.parse(userStr);
        let isImpersonating = false;
        let originalUser = null;
        let originalToken = null;
        
        if (originalAuthStr) {
          const originalAuth = JSON.parse(originalAuthStr);
          isImpersonating = true;
          originalUser = originalAuth.user;
          originalToken = originalAuth.token;
        }
        
        set({ 
          user, 
          token, 
          isAuthenticated: true, 
          isLoading: false,
          isImpersonating,
          originalUser,
          originalToken
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      set({ isLoading: false });
    }
  },
  
  startImpersonation: async (impersonatedUser, impersonationToken) => {
    const { user, token } = get();
    
    // Store original auth
    await AsyncStorage.setItem('original_auth', JSON.stringify({ user, token }));
    
    // Set impersonated user
    await AsyncStorage.setItem('auth_token', impersonationToken);
    await AsyncStorage.setItem('user', JSON.stringify({ ...impersonatedUser, isImpersonating: true }));
    
    set({
      user: { ...impersonatedUser, isImpersonating: true },
      token: impersonationToken,
      isImpersonating: true,
      originalUser: user,
      originalToken: token
    });
  },
  
  stopImpersonation: async () => {
    const { originalUser, originalToken } = get();
    
    if (originalUser && originalToken) {
      // Restore original auth
      await AsyncStorage.setItem('auth_token', originalToken);
      await AsyncStorage.setItem('user', JSON.stringify(originalUser));
      await AsyncStorage.removeItem('original_auth');
      
      set({
        user: originalUser,
        token: originalToken,
        isImpersonating: false,
        originalUser: null,
        originalToken: null
      });
    }
  },
}));