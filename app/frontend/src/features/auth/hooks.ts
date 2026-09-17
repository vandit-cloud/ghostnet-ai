"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuthStore } from "@/state/auth-store";
import type { Role } from "@/types";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  display_name: string;
  role: Role;
}

export interface CurrentUser {
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
}

export function useCurrentUser() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["current-user"],
    queryFn: () => apiFetch<CurrentUser>("/auth/me"),
    enabled: Boolean(token),
  });
}

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession);

  return useMutation({
    mutationFn: (payload: { username: string; password: string }) =>
      apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
        skipAuth: true,
      }),
    onSuccess: (data) => {
      setSession(data.access_token, data.refresh_token, data.display_name, data.role);
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (payload: { current_password: string; new_password: string }) =>
      apiFetch<void>("/auth/change-password", { method: "POST", body: JSON.stringify(payload) }),
  });
}

export function useLogout() {
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const clearSession = useAuthStore((s) => s.clearSession);

  return useMutation({
    mutationFn: async () => {
      try {
        await apiFetch("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } finally {
        // The session is over locally regardless of whether the server call
        // reached it -- an offline logout must not leave the user "logged
        // in" against their own wishes.
        clearSession();
      }
    },
  });
}
