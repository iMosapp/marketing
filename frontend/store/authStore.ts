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

// Singleton promise to prevent concurrent loadAuth calls
let _loadAuthPromise: Promise<void> | null = null;

// Normalize legacy role names to canonical ones
// DB may have 'admin' or 'manager' but frontend expects 'org_admin' or 'store_manager'
function normalizeUser(user: User | null): User | null {
  if (!user) return null;
  const ROLE_MAP: Record<string, string> = {
    admin: 'org_admin',
    manager: 'store_manager',
  };
  if (user.role && ROLE_MAP[user.role]) {
    return { ...user, role: ROLE_MAP[user.role] as any };
  }
  return user;
}

// Read the JS-readable cookie synchronously (instant, no network)
function _getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? match[2] : null;
}

// Centralized cookie-based session restore
async function _restoreFromCookie(set: any) {
  try {
    const { default: api } = await import('../services/api');
    const res = await api.get('/auth/me');
    if (res.data?.user && res.data?.token) {
      await AsyncStorage.setItem('auth_token', res.data.token).catch(() => {});
      await AsyncStorage.setItem('user', JSON.stringify(res.data.user)).catch(() => {});
      _idbSet('imonsocial_user', JSON.stringify(res.data.user)).catch(() => {});
      _idbSet('imonsocial_token', res.data.token).catch(() => {});
      set({ user: normalizeUser(res.data.user), token: res.data.token, isAuthenticated: true, isLoading: false });
      return;
    }
  } catch (e) {
    // Network error or 401 — cookie may be expired or invalid
  }
  set({ isLoading: false });
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
  
  setUser: (user) => set({ user: normalizeUser(user), isAuthenticated: !!user }),
  
  setToken: (token) => set({ token }),
  
  updateUser: (updates) => set((state) => ({
    user: state.user ? { ...state.user, ...updates } : null
  })),
  
  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const response = await authAPI.login(email, password);
      const { user, token, partner_branding } = response;
      
      // === WRITE STRATEGY: IDB first (reliable on all iOS), AsyncStorage second (fast cache) ===
      // IndexedDB is the primary store — it survives iOS localStorage purges and privacy restrictions.
      try {
        await _idbSet('imonsocial_token', token);
        await _idbSet('imonsocial_user', JSON.stringify(user));
        if (partner_branding) {
          await _idbSet('imonsocial_branding', JSON.stringify(partner_branding));
        }
      } catch (idbErr) {
        console.warn('[Auth] IDB write failed:', idbErr);
      }
      // AsyncStorage (localStorage) as a fast-read cache — non-fatal if blocked on iOS
      try {
        await AsyncStorage.setItem('auth_token', token);
        await AsyncStorage.setItem('user', JSON.stringify(user));
        if (partner_branding) {
          await AsyncStorage.setItem('partner_branding', JSON.stringify(partner_branding));
        } else {
          await AsyncStorage.removeItem('partner_branding');
        }
      } catch (storageErr: any) {
        // iOS WebKit throws SecurityError when localStorage is blocked — this is expected
        console.warn('[Auth] localStorage blocked, IDB-only session:', storageErr?.message);
      }
      
      set({ user: normalizeUser(user), token, partnerBranding: partner_branding || null, isAuthenticated: true, isLoading: false });
      
      // Register service worker AFTER successful login (never on login page)
      if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
        try {
          navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => {});
        } catch {}
      }
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
      
      try { await _idbSet('imonsocial_token', token); } catch {}
      try { await _idbSet('imonsocial_user', JSON.stringify(user)); } catch {}
      try { await AsyncStorage.setItem('auth_token', token); } catch {}
      try { await AsyncStorage.setItem('user', JSON.stringify(user)); } catch {}
      
      set({ user: normalizeUser(user), token, isAuthenticated: true, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },
  
  logout: async () => {
    try { await AsyncStorage.removeItem('auth_token'); } catch {}
    try { await AsyncStorage.removeItem('user'); } catch {}
    try { await AsyncStorage.removeItem('original_auth'); } catch {}
    try { await AsyncStorage.removeItem('partner_branding'); } catch {}
    _idbClear().catch(() => {});
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
    if (_loadAuthPromise) return _loadAuthPromise;
    
    _loadAuthPromise = (async () => {
      const safeParse = (str: string | null): any => {
        if (!str) return null;
        try { return JSON.parse(str); } catch { return null; }
      };

      // Safe wrappers — never throw even if storage is blocked on iOS
      const safeAsyncGet = async (key: string): Promise<string | null> => {
        try { return await AsyncStorage.getItem(key); } catch { return null; }
      };
      const safeIdbGet = async (key: string): Promise<string | null> => {
        try { return await _idbGet(key); } catch { return null; }
      };

      try {
        // === LAYER 1: AsyncStorage — fast on devices where localStorage works ===
        let token = await safeAsyncGet('auth_token');
        let userStr = await safeAsyncGet('user');

        // === LAYER 2: IndexedDB — primary fallback, survives iOS privacy restrictions ===
        // Always check IDB if AsyncStorage came up empty (covers iOS localStorage-blocked case)
        if (!token || !userStr) {
          const idbToken = await safeIdbGet('imonsocial_token');
          const idbUser = await safeIdbGet('imonsocial_user');
          if (idbToken && idbUser) {
            token = idbToken;
            userStr = idbUser;
            // Back-fill AsyncStorage for faster future reads (non-fatal)
            try { await AsyncStorage.setItem('auth_token', idbToken); } catch {}
            try { await AsyncStorage.setItem('user', idbUser); } catch {}
          }
        }

        if (token && userStr) {
          const user = safeParse(userStr);
          if (!user || !user._id) {
            await _restoreFromCookie(set);
            return;
          }

          // Restore impersonation state
          const originalAuthStr = await safeAsyncGet('original_auth');
          const brandingStr = await safeAsyncGet('partner_branding') || await safeIdbGet('imonsocial_branding');
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

          set({ user: normalizeUser(user), token, partnerBranding, isAuthenticated: true, isLoading: false, isImpersonating, originalUser, originalToken });
          return;
        }

        // === LAYER 3: HTTP-only session cookie → /auth/me ===
        // Server set imonsocial_uid as a JS-readable cookie — if present, session is live
        const uidCookie = _getCookie('imonsocial_uid');
        if (uidCookie) {
          for (let attempt = 0; attempt < 2; attempt++) {
            try {
              const { default: api } = await import('../services/api');
              const res = await api.get('/auth/me');
              if (res.data?.user && res.data?.token) {
                // Restore into both storage layers
                try { await _idbSet('imonsocial_token', res.data.token); } catch {}
                try { await _idbSet('imonsocial_user', JSON.stringify(res.data.user)); } catch {}
                try { await AsyncStorage.setItem('auth_token', res.data.token); } catch {}
                try { await AsyncStorage.setItem('user', JSON.stringify(res.data.user)); } catch {}
                set({ user: normalizeUser(res.data.user), token: res.data.token, isAuthenticated: true, isLoading: false });
                return;
              }
            } catch {
              if (attempt === 0) await new Promise(r => setTimeout(r, 1000));
            }
          }
        }

        // Nothing found — genuinely not logged in
        set({ isLoading: false });
      } catch {
        // Last resort: cookie restore
        await _restoreFromCookie(set);
      }
    })();

    try { await _loadAuthPromise; } finally { _loadAuthPromise = null; }
  },
  
  startImpersonation: async (impersonatedUser, impersonationToken) => {
    const { user, token } = get();
    const originalPayload = JSON.stringify({ user, token });

    // Persist original auth to both stores (non-fatal)
    try { await _idbSet('imonsocial_original_auth', originalPayload); } catch {}
    try { await AsyncStorage.setItem('original_auth', originalPayload); } catch {}

    // Persist impersonated session
    const impersonatedPayload = JSON.stringify({ ...impersonatedUser, isImpersonating: true });
    try { await _idbSet('imonsocial_token', impersonationToken); } catch {}
    try { await _idbSet('imonsocial_user', impersonatedPayload); } catch {}
    try { await AsyncStorage.setItem('auth_token', impersonationToken); } catch {}
    try { await AsyncStorage.setItem('user', impersonatedPayload); } catch {}

    set({
      user: normalizeUser({ ...impersonatedUser, isImpersonating: true }),
      token: impersonationToken,
      isImpersonating: true,
      originalUser: user,
      originalToken: token
    });
  },

  stopImpersonation: async () => {
    const { originalUser, originalToken } = get();

    if (originalUser && originalToken) {
      const userPayload = JSON.stringify(originalUser);
      try { await _idbSet('imonsocial_token', originalToken); } catch {}
      try { await _idbSet('imonsocial_user', userPayload); } catch {}
      try { await AsyncStorage.setItem('auth_token', originalToken); } catch {}
      try { await AsyncStorage.setItem('user', userPayload); } catch {}
      try { await AsyncStorage.removeItem('original_auth'); } catch {}
      try { await _idbSet('imonsocial_original_auth', ''); } catch {}

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