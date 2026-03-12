import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authAPI } from '../services/api';

// IndexedDB helpers — iOS PWA preserves IndexedDB better than localStorage
const IDB_NAME = 'imos_auth';
const IDB_STORE = 'session';

function _idbOpen(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) return reject('no idb');
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(IDB_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function _idbSet(key: string, value: string): Promise<void> {
  return _idbOpen().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, 'readwrite');
    tx.objectStore(IDB_STORE).put(value, key);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  }));
}

function _idbGet(key: string): Promise<string | null> {
  return _idbOpen().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, 'readonly');
    const req = tx.objectStore(IDB_STORE).get(key);
    req.onsuccess = () => { db.close(); resolve(req.result ?? null); };
    req.onerror = () => { db.close(); reject(req.error); };
  }));
}

function _idbClear(): Promise<void> {
  return _idbOpen().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, 'readwrite');
    tx.objectStore(IDB_STORE).clear();
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  })).catch(() => {});
}

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
  partnerBranding: null,
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
      const { user, token, partner_branding } = response;
      
      await AsyncStorage.setItem('auth_token', token);
      await AsyncStorage.setItem('user', JSON.stringify(user));
      // Backup to IndexedDB (survives iOS PWA localStorage purges)
      _idbSet('imos_token', token).catch(() => {});
      _idbSet('imos_user', JSON.stringify(user)).catch(() => {});
      if (partner_branding) {
        await AsyncStorage.setItem('partner_branding', JSON.stringify(partner_branding));
      } else {
        await AsyncStorage.removeItem('partner_branding');
      }
      
      set({ user, token, partnerBranding: partner_branding || null, isAuthenticated: true, isLoading: false });
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
    await AsyncStorage.removeItem('partner_branding');
    // Clear IndexedDB backup
    _idbClear().catch(() => {});
    // Clear server-side session cookie
    try {
      const { default: api } = await import('../services/api');
      await api.post('/auth/logout');
    } catch {}
    set({ 
      user: null, 
      token: null, 
      partnerBranding: null,
      isAuthenticated: false,
      isImpersonating: false,
      originalUser: null,
      originalToken: null 
    });
  },
  
  loadAuth: async () => {
    // Helper: attempt cookie-based session restore from the server (with retry)
    const tryRestoreFromCookie = async (): Promise<boolean> => {
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const { default: api } = await import('../services/api');
          const res = await api.get('/auth/me');
          if (res.data?.user && res.data?.token) {
            const user = res.data.user;
            const restoredToken = res.data.token;
            // Re-persist to AsyncStorage so future cold boots are instant
            await AsyncStorage.setItem('auth_token', restoredToken).catch(() => {});
            await AsyncStorage.setItem('user', JSON.stringify(user)).catch(() => {});
            // Also persist to IndexedDB as backup (iOS PWA preserves it better)
            _idbSet('imos_user', JSON.stringify(user)).catch(() => {});
            _idbSet('imos_token', restoredToken).catch(() => {});
            set({ user, token: restoredToken, isAuthenticated: true, isLoading: false });
            return true;
          }
        } catch (e: any) {
          // Only retry on network errors, not on 401s (which mean no valid session)
          if (e?.response?.status === 401) break;
          if (attempt < 2) {
            await new Promise(r => setTimeout(r, 1500 * (attempt + 1)));
            continue;
          }
        }
        break;
      }
      return false;
    };

    // Helper: safely parse JSON without throwing
    const safeParse = (str: string | null): any => {
      if (!str) return null;
      try { return JSON.parse(str); } catch { return null; }
    };

    // Helper: read from AsyncStorage with retry (iOS cold-boot can return null on first read)
    const readWithRetry = async (key: string, retries = 2): Promise<string | null> => {
      for (let i = 0; i <= retries; i++) {
        const val = await AsyncStorage.getItem(key);
        if (val) return val;
        if (i < retries) await new Promise(r => setTimeout(r, 300 * (i + 1)));
      }
      return null;
    };

    try {
      let token = await readWithRetry('auth_token');
      let userStr = await readWithRetry('user');
      
      // Fallback: try IndexedDB if AsyncStorage is empty (iOS PWA can clear localStorage)
      if ((!token || !userStr) && typeof window !== 'undefined' && window.indexedDB) {
        try {
          const idbToken = await _idbGet('imos_token');
          const idbUser = await _idbGet('imos_user');
          if (idbToken && idbUser) {
            token = idbToken;
            userStr = idbUser;
            // Re-sync to AsyncStorage
            await AsyncStorage.setItem('auth_token', idbToken).catch(() => {});
            await AsyncStorage.setItem('user', idbUser).catch(() => {});
          }
        } catch {}
      }
      
      if (token && userStr) {
        const user = safeParse(userStr);
        
        // If parse failed (corrupted data), try cookie restore instead of giving up
        if (!user || !user._id) {
          console.warn('[Auth] localStorage user data corrupted, attempting cookie restore');
          if (await tryRestoreFromCookie()) return;
          set({ isLoading: false });
          return;
        }
        
        const originalAuthStr = await AsyncStorage.getItem('original_auth');
        const brandingStr = await AsyncStorage.getItem('partner_branding');
        const partnerBranding = safeParse(brandingStr);
        let isImpersonating = false;
        let originalUser = null;
        let originalToken = null;
        
        if (originalAuthStr) {
          const originalAuth = safeParse(originalAuthStr);
          if (originalAuth?.user) {
            isImpersonating = true;
            originalUser = originalAuth.user;
            originalToken = originalAuth.token;
          }
        }
        
        set({ 
          user, 
          token, 
          partnerBranding,
          isAuthenticated: true, 
          isLoading: false,
          isImpersonating,
          originalUser,
          originalToken
        });
      } else {
        // All local storage empty — try restoring from persistent cookie
        console.log('[Auth] No local session found, attempting cookie restore');
        if (await tryRestoreFromCookie()) return;
        set({ isLoading: false });
      }
    } catch (error) {
      // AsyncStorage itself threw (iOS memory pressure, storage full, etc.)
      // CRITICAL: Don't give up — try the cookie as a last resort
      console.warn('[Auth] AsyncStorage read failed, attempting cookie restore:', error);
      try {
        if (await tryRestoreFromCookie()) return;
      } catch {}
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