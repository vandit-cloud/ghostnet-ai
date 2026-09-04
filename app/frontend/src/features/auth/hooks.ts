"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuthStore } from "@/state/auth-store";

interface LoginResponse {
  access_token: string;
  token_type: string;
  display_name: string;
}

export interface CurrentUser {
  username: string;
  display_name: string;
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
      setSession(data.access_token, data.display_name);
    },
  });
}
