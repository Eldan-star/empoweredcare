import axios, { AxiosError } from "axios";
import { useAppStore } from "@/store/appStore";
import { useAuthStore, type AuthUser } from "@/store/authStore";
import type {
  ChatResponse,
  HealthStatus,
  OutbreakProcessResponse,
  OutbreakReport,
  QueryResponse,
  SummaryData,
} from "@/types";

/**
 * HTTP client for the FastAPI backend (main.py).
 *
 * The base URL is read from the app store on every request so that a change in
 * Settings takes effect immediately. The bearer token comes from the auth store.
 */
const http = axios.create({ timeout: 180_000 });

http.interceptors.request.use((config) => {
  config.baseURL = useAppStore.getState().apiBaseUrl.replace(/\/$/, "");
  const token = useAuthStore.getState().token;
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

http.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    const isLoginCall = error.config?.url?.includes("/auth/login");
    if (error.response?.status === 401 && !isLoginCall) {
      useAuthStore.getState().logout();
      if (window.location.pathname !== "/login") window.location.assign("/login");
    }
    return Promise.reject(error);
  },
);

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: AuthUser["role"];
  full_name: string | null;
}

export interface TeamMember {
  id: string;
  email: string;
  full_name: string | null;
  role: AuthUser["role"];
  is_active: boolean;
  created_at: string | null;
}

export interface AnalysisStatus {
  status: {
    last_run: string | null;
    last_result: Record<string, unknown> | null;
    next_run: string | null;
    schedule: string | null;
    is_running: boolean;
  };
  is_scheduler_running: boolean;
}

export interface PatientRecordInput {
  patient_name: string;
  sex?: string;
  age?: string;
  city?: string;
  subcity?: string;
  woreda?: string;
  mrn?: string;
  occupation?: string;
  date?: string;
  chief_complaint?: string;
  history?: string;
  physical_exam?: string;
  vital_signs?: Record<string, unknown> | null;
  assessment?: string | null;
  past_medical_history?: string | null;
  plan?: string | null;
}

export interface PatientRecordSaved {
  id: string;
  message: string;
  patient_name: string;
  mrn?: string | null;
  saved_at: string;
}

export interface PatientRecordRow extends PatientRecordInput {
  id: string;
  saved_at: string;
  saved_by: string;
}

const data = <T,>(p: Promise<{ data: T }>) => p.then((r) => r.data);

export const api = {
  // --- Auth ---------------------------------------------------------------
  login(email: string, password: string) {
    const form = new URLSearchParams({ username: email, password });
    return data<TokenResponse>(
      http.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      }),
    );
  },
  register(body: { token: string; password: string; full_name: string }) {
    return data<Record<string, unknown>>(http.post("/auth/register", body));
  },
  forgotPassword(email: string) {
    return data<Record<string, unknown>>(
      http.post("/auth/forgot-password", { email, frontend_url: window.location.origin }),
    );
  },
  resetPassword(token: string, new_password: string) {
    return data<Record<string, unknown>>(http.post("/auth/reset-password", { token, new_password }));
  },
  getMe() {
    return data<AuthUser>(http.get("/auth/me"));
  },
  changePassword(old_password: string, new_password: string) {
    return data<Record<string, unknown>>(http.post("/auth/change-password", { old_password, new_password }));
  },

  // --- Admin --------------------------------------------------------------
  getUsers() {
    return data<TeamMember[]>(http.get("/admin/users"));
  },
  inviteUser(email: string, role: AuthUser["role"], frontend_url: string) {
    return data<Record<string, unknown>>(http.post("/admin/invite", { email, role, frontend_url }));
  },
  deleteUser(userId: string) {
    return data<Record<string, unknown>>(http.delete(`/admin/users/${encodeURIComponent(userId)}`));
  },
  getAnalysisStatus() {
    return data<AnalysisStatus>(http.get("/admin/analyze/status"));
  },
  triggerAnalysis() {
    return data<{ message: string; timestamp: string; result: Record<string, unknown> }>(
      http.post("/admin/analyze/manual"),
    );
  },
  updateCronSchedule(cron: string) {
    return data<{ message: string; next_run: string }>(http.post("/admin/analyze/schedule", { cron }));
  },

  // --- System -------------------------------------------------------------
  getHealth() {
    return data<HealthStatus>(http.get("/health"));
  },

  // --- Outbreak reports ---------------------------------------------------
  getReports() {
    // Older stored records only carry `timestamp`; normalise so every record has a received time.
    return data<OutbreakReport[]>(http.get("/outbreak/reports")).then((rs) =>
      rs.map((r) => ({ ...r, created_at: r.created_at || r.timestamp || "" })),
    );
  },
  getSummary() {
    return data<SummaryData>(http.get("/outbreak/summary"));
  },
  processReport(text: string) {
    return data<OutbreakProcessResponse[]>(http.post("/outbreak/process", { text })) as Promise<
      OutbreakReport[]
    >;
  },
  uploadFile(file: File) {
    const form = new FormData();
    form.append("file", file);
    return data<OutbreakProcessResponse[]>(http.post("/outbreak/upload", form)) as Promise<
      OutbreakReport[]
    >;
  },
  approveReport(sessionId: string, approved: boolean) {
    return data<{ session_id: string; approved: boolean; message: string; timestamp: string }>(
      http.post(`/outbreak/approve/${encodeURIComponent(sessionId)}`, { approved }),
    );
  },
  query(query: string) {
    return data<QueryResponse>(http.post("/outbreak/query", { query }));
  },

  // --- Assistant ----------------------------------------------------------
  chat(message: string, session_id?: string) {
    return data<ChatResponse>(http.post("/outbreak/chat", { message, session_id }));
  },
  clearChat(sessionId: string) {
    return data<{ message: string }>(http.delete(`/outbreak/chat/${encodeURIComponent(sessionId)}`));
  },

  // --- Patient records ----------------------------------------------------
  savePatientRecord(record: PatientRecordInput) {
    return data<PatientRecordSaved>(http.post("/patient/record", record));
  },
  getPatientRecords() {
    return data<{ total: number; records: PatientRecordRow[] }>(http.get("/patient/records"));
  },
};

/** Human-readable message from an API error. */
export function apiErrorMessage(err: unknown, fallback = "Request failed"): string {
  const e = err as AxiosError<{ detail?: string }>;
  return e?.response?.data?.detail || e?.message || fallback;
}
