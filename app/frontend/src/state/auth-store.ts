"use client";

import { create } from "zustand";

import type { Role } from "@/types";

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  displayName: string | null;
  role: Role | null;
  setSession: (token: string, refreshToken: string, displayName: string, role: Role) => void;
  setAccessToken: (token: string, refreshToken: string) => void;
  clearSession: () => void;
  hydrate: () => void;
}

const TOKEN_KEY = "ghostnet_token";
const REFRESH_KEY = "ghostnet_refresh_token";
const NAME_KEY = "ghostnet_display_name";
const ROLE_KEY = "ghostnet_role";

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  refreshToken: null,
  displayName: null,
  role: null,
  setSession: (token, refreshToken, displayName, role) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(REFRESH_KEY, refreshToken);
      window.localStorage.setItem(NAME_KEY, displayName);
      window.localStorage.setItem(ROLE_KEY, role);
    }
    set({ token, refreshToken, displayName, role });
  },
  setAccessToken: (token, refreshToken) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(REFRESH_KEY, refreshToken);
    }
    set({ token, refreshToken });
  },
  clearSession: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(REFRESH_KEY);
      window.localStorage.removeItem(NAME_KEY);
      window.localStorage.removeItem(ROLE_KEY);
    }
    set({ token: null, refreshToken: null, displayName: null, role: null });
  },
  hydrate: () => {
    if (typeof window === "undefined") return;
    const token = window.localStorage.getItem(TOKEN_KEY);
    const refreshToken = window.localStorage.getItem(REFRESH_KEY);
    const displayName = window.localStorage.getItem(NAME_KEY);
    const role = window.localStorage.getItem(ROLE_KEY) as Role | null;
    if (token) {
      set({ token, refreshToken, displayName, role });
    }
  },
}));
