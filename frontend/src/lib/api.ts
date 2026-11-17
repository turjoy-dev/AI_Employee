import axios from "axios";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export const TOKEN_STORAGE_KEY = "ai_employee_access_token";
export const USER_STORAGE_KEY = "ai_employee_user";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach JWT access_token from localStorage on every outgoing request
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = window.localStorage.getItem(TOKEN_STORAGE_KEY);
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle 401 Unauthorized responses globally: clear auth state and redirect to /login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      typeof window !== "undefined" &&
      error?.response?.status === 401 &&
      !error?.config?.url?.includes("/auth/login")
    ) {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      window.localStorage.removeItem(USER_STORAGE_KEY);
      // Dynamically import store to avoid circular dependency at module init
      import("@/store/useAuthStore").then(({ useAuthStore }) => {
        useAuthStore.getState().clearAuth();
      });
      if (window.location.pathname !== "/login") {
        window.location.replace("/login");
      }
    }
    return Promise.reject(error);
  }
);

export interface Lead {
  id: string;
  customer_id: string;
  conversation_id: string | null;
  source: string;
  status: string;
  priority: string;
  score: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Customer {
  id: string;
  full_name: string;
  phone_number: string | null;
  email: string | null;
  preferred_language: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  customer_id: string;
  channel: string;
  status: string;
  summary: string | null;
  started_at: string;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  metadata_json: Record<string, unknown> | string | null;
  timestamp: string;
  created_at: string;
  updated_at: string;
}
