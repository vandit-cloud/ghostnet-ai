"use client";

import { create } from "zustand";

interface AuthState {
  token: string | null;
  displayName: string | null;
  setSession: (token: string, displayName: string) => void;
  clearSession: () => void;
  hydrate: () => void;
}

const TOKEN_KEY = "ghostnet_token";
const NAME_KEY = "ghostnet_display_name";

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  displayName: null,
  setSession: (token, displayName) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(NAME_KEY, displayName);
    }
    set({ token, displayName });
  },
  clearSession: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(NAME_KEY);
    }
    set({ token: null, displayName: null });
  },
  hydrate: () => {
    if (typeof window === "undefined") return;
    const token = window.localStorage.getItem(TOKEN_KEY);
    const displayName = window.localStorage.getItem(NAME_KEY);
    if (token) {
      set({ token, displayName });
    }
  },
}));
