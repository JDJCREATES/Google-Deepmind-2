import { create } from 'zustand';

interface User {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
  authMethod?: 'google' | 'password';
  tier?: 'free' | 'starter' | 'pro' | 'enterprise';
  subscription_status?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: () => void;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
  clearError: () => void;
  isAuthModalOpen: boolean;
  openAuthModal: () => void;
  closeAuthModal: () => void;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// Mock delay to simulate network request
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  isAuthModalOpen: false,

  openAuthModal: () => set({ isAuthModalOpen: true }),
  closeAuthModal: () => set({ isAuthModalOpen: false, error: null }),
  clearError: () => set({ error: null }),

  /**
   * Check current session status
   */
  checkSession: async () => {
    try {
      const response = await fetch(`${API_URL}/auth/user`, {
        credentials: 'include', // Include cookies
      });

      if (response.ok) {
        const data = await response.json();
        if (data.authenticated && data.user) {
          set({
            user: {
              id: data.user.id,
              name: data.user.name,
              email: data.user.email,
              avatarUrl: data.user.picture,
              authMethod: data.user.auth_method,
            },
            isAuthenticated: true,
          });
        } else {
          set({ user: null, isAuthenticated: false });
        }
      }
    } catch (error) {
      console.error('[Auth] Session check failed:', error);
      set({ user: null, isAuthenticated: false });
    }
  },

  /**
   * Login with Google OAuth
   * Redirects to Google consent screen
   */
  loginWithGoogle: () => {
    if (import.meta.env.DEV) {
      console.log('[Auth] Initiating Google login...');
      console.log(`[Auth] Redirecting to: ${API_URL}/auth/google`);
    }
    // Don't set loading - we're redirecting immediately
    window.location.href = `${API_URL}/auth/google`;
  },

  /**
   * Login with email/password (existing mock implementation)
   */
  login: async (email, password) => {
    set({ isLoading: true, error: null });
    
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch(`${API_URL}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const data = await response.json();
      console.log('[Auth] Access Token:', data.access_token);

      set({
        isLoading: false,
        isAuthenticated: true,
        user: {
          id: '1',
          name: email.split('@')[0],
          email: email,
          avatarUrl: `https://api.dicebear.com/7.x/avataaars/svg?seed=${email}`,
          authMethod: 'password',
        }
      });
    } catch (error) {
      console.error('[Auth] Login error:', error);
      set({ 
        isLoading: false, 
        isAuthenticated: false,
        error: 'Login failed. Please check your credentials.',
      });
    }
  },

  /**
   * Register new user (mock - not implemented on backend yet)
   */
  register: async (email, password, name) => {
    set({ isLoading: true, error: null });
    await delay(1000);
    
    set({
      isLoading: false,
      isAuthenticated: true,
      user: {
        id: '2',
        name: name,
        email: email,
        avatarUrl: `https://api.dicebear.com/7.x/avataaars/svg?seed=${name}`,
        authMethod: 'password',
      }
    });
  },

  /**
   * Logout and clear session
   */
  logout: async () => {
    try {
      await fetch(`${API_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch (error) {
      console.error('[Auth] Logout error:', error);
    }
    
    set({ user: null, isAuthenticated: false, error: null });
  }
}));
