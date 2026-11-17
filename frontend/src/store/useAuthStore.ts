"use client";

import { create } from "zustand";
import { api, TOKEN_STORAGE_KEY, USER_STORAGE_KEY } from "@/lib/api";

export interface AuthUser {
  email: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  hydrate: () => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  hydrate: () => {
    if (typeof window === "undefined") return;
    const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    const storedUserRaw = window.localStorage.getItem(USER_STORAGE_KEY);
    let parsedUser: AuthUser | null = null;
    if (storedUserRaw) {
      try {
        parsedUser = JSON.parse(storedUserRaw) as AuthUser;
      } catch {
        parsedUser = null;
      }
    }
    if (storedToken) {
      set({
        token: storedToken,
        user: parsedUser,
        isAuthenticated: true,
      });
    } else {
      set({
        token: null,
        user: null,
        isAuthenticated: false,
      });
    }
  },

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const formBody = new URLSearchParams();
      formBody.append("username", email.trim());
      formBody.append("password", password);

      const response = await api.post<{
        access_token: string;
        token_type: string;
      }>("/auth/login", formBody.toString(), {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      const accessToken = response.data.access_token;
      const profile: AuthUser = { email: email.trim(), role: "admin" };

      if (typeof window !== "undefined") {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
        window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(profile));
      }

      set({
        token: accessToken,
        user: profile,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: unknown) {
      let message = "Invalid email or password.";
      if (
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof (err as { response?: { data?: { detail?: string } } }).response?.data?.detail === "string"
      ) {
        message = (err as { response: { data: { detail: string } } }).response.data.detail;
      }
      set({
        isLoading: false,
        error: message,
        isAuthenticated: false,
        token: null,
      });
      throw err;
    }
  },

  logout: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      window.localStorage.removeItem(USER_STORAGE_KEY);
    }
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      error: null,
    });
  },

  clearAuth: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      window.localStorage.removeItem(USER_STORAGE_KEY);
    }
    set({
      token: null,
      user: null,
      isAuthenticated: false,
    });
  },
}));
