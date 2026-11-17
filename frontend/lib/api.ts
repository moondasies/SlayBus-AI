"use client";

import type { Paper, PaperSummary, Profile, Question, SourceChunk, Textbook } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type TokenGetter = () => Promise<string | null>;
let getToken: TokenGetter = async () => null;
let onUnauthorized: () => void = () => {};

/** Called once by the AuthProvider so every request carries the user's token. */
export function configureApi(tokenGetter: TokenGetter, unauthorized: () => void) {
  getToken = tokenGetter;
  onUnauthorized = unauthorized;
}

function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      // FastAPI validation errors: [{loc, msg}]
      return detail
        .map((d: { msg?: string; loc?: unknown[] }) => (d.msg || "Invalid value").replace(/^Value error, /, ""))
        .join("; ");
    }
  }
  return status >= 500 ? "Something went wrong on the server. Please try again." : `Request failed (${status})`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the SLAYBUS agent. Is it running?");
  }
  if (res.status === 401) onUnauthorized();
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {}
    throw new ApiError(res.status, messageFrom(body, res.status));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  devToken: (email: string) =>
    request<{ access_token: string; user_id: string; email: string }>("/dev/token", { method: "POST", body: json({ email }) }),

  me: () => request<Profile>("/me"),
  updateMe: (body: Partial<Pick<Profile, "name" | "school" | "board" | "subjects" | "classes">>) =>
    request<Profile>("/me", { method: "PUT", body: json(body) }),

  textbooks: () => request<Textbook[]>("/textbooks"),
  textbook: (id: string) => request<Textbook>(`/textbooks/${id}`),
  uploadTextbook: (form: FormData) => request<Textbook>("/textbooks", { method: "POST", body: form }),
  reprocessTextbook: (id: string) => request(`/textbooks/${id}/reprocess`, { method: "POST" }),
  deleteTextbook: (id: string) => request<void>(`/textbooks/${id}`, { method: "DELETE" }),

  papers: () => request<PaperSummary[]>("/papers"),
  paper: (id: string) => request<Paper>(`/papers/${id}`),
  generatePaper: (blueprint: unknown) => request<Paper>("/papers/generate", { method: "POST", body: json(blueprint) }),
  updatePaper: (id: string, body: { title?: string; duration_min?: number | null; instructions?: string | null }) =>
    request<Paper>(`/papers/${id}`, { method: "PATCH", body: json(body) }),
  deletePaper: (id: string) => request<void>(`/papers/${id}`, { method: "DELETE" }),
  reorder: (id: string, question_ids: string[]) =>
    request<Paper>(`/papers/${id}/reorder`, { method: "POST", body: json({ question_ids }) }),
  addFromBank: (paperId: string, question_id: string, section: string) =>
    request<Question>(`/papers/${paperId}/questions`, { method: "POST", body: json({ question_id, section }) }),

  bank: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && qs.set(k, String(v)));
    return request<{ total: number; items: Question[] }>(`/questions?${qs}`);
  },
  editQuestion: (id: string, body: Partial<Question>) =>
    request<Question>(`/questions/${id}`, { method: "PATCH", body: json(body) }),
  regenerate: (id: string, body: { difficulty?: string; instructions?: string }) =>
    request<Question>(`/questions/${id}/regenerate`, { method: "POST", body: json(body) }),
  deleteQuestion: (id: string, keepInBank = true) =>
    request<void>(`/questions/${id}?keep_in_bank=${keepInBank}`, { method: "DELETE" }),
  sources: (id: string) => request<SourceChunk[]>(`/questions/${id}/sources`),

  /** Downloads the export as a file in the browser. */
  async download(paperId: string, format: "pdf" | "docx", answers: boolean) {
    const token = await getToken();
    const res = await fetch(`${API_URL}/papers/${paperId}/export?format=${format}&answers=${answers}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      let body: unknown = null;
      try {
        body = await res.json();
      } catch {}
      throw new ApiError(res.status, messageFrom(body, res.status));
    }
    const blob = await res.blob();
    const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || `paper.${format}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return name;
  },
};
