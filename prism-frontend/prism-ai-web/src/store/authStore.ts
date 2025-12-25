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
    
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch('http://localhost:8001/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const data = await response.json();
      // In a real app, store token in localStorage/cookies
      console.log('Access Token:', data.access_token);

      set({
        isLoading: false,
        isAuthenticated: true,
        user: {
          id: '1',
          name: email.split('@')[0],
          email: email,
          avatarUrl: `https://api.dicebear.com/7.x/avataaars/svg?seed=${email}`
        }
      });
    } catch (error) {
      console.error(error);
      set({ isLoading: false, isAuthenticated: false });
      alert('Login Failed. check console.');
    }
  },

  register: async (email, password, name) => {
    set({ isLoading: true });
    // For now, our backend only has a mock DB, so register just simulates login
    // In future: await fetch('http://localhost:8000/register', ...)
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
