import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User } from '@/api/types';

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  
  setToken: (token: string) => void;
  setAuth: (token: string, refreshToken: string, user: User) => void;
  logout: () => void;
}

/**
 * Zustand store for authentication state with localStorage persistence
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      setToken: (token: string) =>
        set({ token, isAuthenticated: true }),

      setAuth: (token: string, refreshToken: string, user: User) =>
        set({
          token,
          refreshToken,
          user,
          isAuthenticated: true,
        }),

      logout: () =>
        set({
          token: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        }),
    }),
    {
      name: 'abos-auth-storage',
    }
  )
);
