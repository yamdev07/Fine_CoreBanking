import { getToken } from "@/lib/auth";

const BASE = process.env.NEXT_PUBLIC_ACCOUNTING_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init?.headers ?? {}) as Record<string, string>),
  };
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    const msg = err?.detail?.message ?? err?.message ?? res.statusText;
    throw new Error(msg);
  }
  return res.json();
}

// ── Exercices fiscaux ─────────────────────────────────────────────────────────

export interface FiscalYear {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: "OPEN" | "CLOSED";
  created_at: string;
}

export const getFiscalYears = () => req<FiscalYear[]>("/api/v1/fiscal-years/");

export const createFiscalYear = (data: { name: string; start_date: string; end_date: string }) =>
  req<FiscalYear>("/api/v1/fiscal-years/", { method: "POST", body: JSON.stringify(data) });

export const closeFiscalYear = (id: string) =>
  req<FiscalYear>(`/api/v1/fiscal-years/${id}/close`, { method: "POST" });

// ── Plan de comptes ───────────────────────────────────────────────────────────

export interface Account {
  id: string;
  code: string;
  name: string;
  account_class: string;
  account_type: "ACTIF" | "PASSIF" | "CHARGE" | "PRODUIT";
  account_nature: "DEBITEUR" | "CREDITEUR";
  is_leaf: boolean;
  is_active: boolean;
  balance: number;
  currency: string;
}

export const getAccounts = (params?: { class?: string; is_leaf?: boolean }) => {
  const qs = new URLSearchParams();
  if (params?.class) qs.set("account_class", params.class);
  if (params?.is_leaf !== undefined) qs.set("is_leaf", String(params.is_leaf));
  return req<{ items: Account[]; total: number }>(`/api/v1/accounts/?${qs}`);
};

// ── Journaux ──────────────────────────────────────────────────────────────────

export interface Journal {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export const getJournals = () => req<Journal[]>("/api/v1/journals/");

export const getJournalById = (id: string) => req<Journal>(`/api/v1/journals/${id}`);

// ── Écritures comptables ──────────────────────────────────────────────────────

export interface JournalLine {
  account_id?: string;
  account_code?: string;
  debit_amount: number;
  credit_amount: number;
  description?: string;
  third_party_id?: string;
}

export interface JournalEntryCreate {
  journal_id: string;
  entry_date: string;
  value_date?: string;
  description: string;
  reference?: string;
  lines: JournalLine[];
}

export interface JournalEntry {
  id: string;
  entry_number: string;
  journal_id: string;
  journal_code: string | null;
  entry_date: string;
  description: string;
  reference?: string;
  status: "DRAFT" | "POSTED" | "REVERSED";
  total_debit: string;
  total_credit: string;
  created_at: string;
  lines: JournalLine[];
}

export const getJournalEntries = (params?: {
  period_id?: string;
  status?: string;
  page?: number;
  size?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.period_id) qs.set("period_id", params.period_id);
  if (params?.status) qs.set("status", params.status);
  qs.set("page", String(params?.page ?? 1));
  qs.set("size", String(params?.size ?? 50));
  return req<{ items: JournalEntry[]; total: number; pages: number }>(`/api/v1/journal-entries/?${qs}`);
};

export const createJournalEntry = (data: JournalEntryCreate) =>
  req<JournalEntry>("/api/v1/journal-entries/", { method: "POST", body: JSON.stringify(data) });

export const postJournalEntry = (id: string) =>
  req<JournalEntry>(`/api/v1/journal-entries/${id}/post`, { method: "POST" });

export const reverseJournalEntry = (id: string, reversal_date: string) =>
  req<JournalEntry>(`/api/v1/journal-entries/${id}/reverse?reversal_date=${reversal_date}`, { method: "POST" });

// ── Utilisateurs (Admin) ──────────────────────────────────────────────────────

export interface UserRecord {
  id: string;
  username: string;
  full_name: string;
  email: string;
  role: "ADMIN" | "ACCOUNTANT" | "AUDITOR";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export const getUsers = () => req<UserRecord[]>("/api/v1/users");

export const createUser = (data: {
  username: string; full_name: string; email: string;
  password: string; role: string;
}) => req<UserRecord>("/api/v1/users", { method: "POST", body: JSON.stringify(data) });

export const updateUser = (id: string, data: Partial<{
  full_name: string; email: string; role: string;
  is_active: boolean; password: string;
}>) => req<UserRecord>(`/api/v1/users/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deactivateUser = (id: string) => {
  const token = getToken();
  return fetch(`${BASE}/api/v1/users/${id}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
};
