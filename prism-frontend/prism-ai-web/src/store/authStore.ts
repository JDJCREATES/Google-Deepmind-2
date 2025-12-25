import { create } from 'zustand';

interface User {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

// Mock delay to simulate network request
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const useAuthStore = create<AuthState>((set) => ({
  user: null, // Start logged out
  isAuthenticated: false,
  isLoading: false,

  login: async (email, password) => {
    set({ isLoading: true });
    await delay(1000); // Simulate API call
    
    // Accept any login for prototype
    set({
      isLoading: false,
      isAuthenticated: true,
      user: {
        id: '1',
        name: email.split('@')[0], // Use part of email as name
        email: email,
        avatarUrl: `https://api.dicebear.com/7.x/avataaars/svg?seed=${email}`
      }
    });
  },

  register: async (email, password, name) => {
    set({ isLoading: true });
    await delay(1000);
    
    set({
      isLoading: false,
      isAuthenticated: true,
      user: {
        id: '2',
        name: name,
        email: email,
        avatarUrl: `https://api.dicebear.com/7.x/avataaars/svg?seed=${name}`
      }
    });
  },

  logout: () => {
    set({ user: null, isAuthenticated: false });
  }
}));
