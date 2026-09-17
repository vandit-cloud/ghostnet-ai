import { useAuthStore } from "@/state/auth-store";
import type { ApiErrorBody } from "@/types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  code: string;
  requestId: string;
  status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.code = body.error.code;
    this.requestId = body.error.request_id;
    this.status = status;
  }
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

// Dedupes concurrent 401s into a single refresh call rather than each firing
// its own -- several queries can 401 in the same tick after an access token
// expires.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const { refreshToken, setAccessToken, clearSession } = useAuthStore.getState();
      if (!refreshToken) return null;
      try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
          clearSession();
          return null;
        }
        const data = (await response.json()) as { access_token: string; refresh_token: string };
        setAccessToken(data.access_token, data.refresh_token);
        return data.access_token;
      } catch {
        return null;
      }
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}, _retried = false): Promise<T> {
  const token = useAuthStore.getState().token;
  const headers = new Headers(options.headers);

  if (!options.skipAuth && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(options.body instanceof FormData) && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401 && !options.skipAuth) {
    if (!_retried) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return apiFetch<T>(path, options, true);
      }
    }
    useAuthStore.getState().clearSession();
  }

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      body = await response.json();
    } catch {
      body = { error: { code: "UNKNOWN_ERROR", message: response.statusText, request_id: "" } };
    }
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function apiFetchBlob(path: string): Promise<Blob> {
  const token = useAuthStore.getState().token;
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    throw new Error(`Failed to download: ${response.statusText}`);
  }
  return response.blob();
}
