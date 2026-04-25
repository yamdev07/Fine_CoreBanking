const BASE = process.env.NEXT_PUBLIC_ACCOUNTING_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(err.message ?? res.statusText);
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

export const getFiscalYears = () => req<FiscalYear[]>("/api/v1/journals/fiscal-years");

export const createFiscalYear = (data: { name: string; start_date: string; end_date: string }) =>
  req<FiscalYear>("/api/v1/journals/fiscal-years", { method: "POST", body: JSON.stringify(data) });

export const closeFiscalYear = (id: string) =>
  req<FiscalYear>(`/api/v1/journals/fiscal-years/${id}/close`, { method: "POST" });

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
  journal_id?: string;
  journal_code?: string;
  entry_date: string;
  value_date?: string;
  description: string;
  reference?: string;
  lines: JournalLine[];
}

export interface JournalEntry {
  id: string;
  entry_number: string;
  journal_code: string;
  entry_date: string;
  description: string;
  reference?: string;
  status: "DRAFT" | "POSTED" | "CANCELLED";
  total_debit: number;
  total_credit: number;
  created_at: string;
}

export const getJournalEntries = (params?: {
  status?: string;
  page?: number;
  size?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  qs.set("page", String(params?.page ?? 1));
  qs.set("size", String(params?.size ?? 50));
  return req<{ items: JournalEntry[]; total: number; pages: number }>(`/api/v1/journals/entries?${qs}`);
};

export const createJournalEntry = (data: JournalEntryCreate) =>
  req<JournalEntry>("/api/v1/journals/entries", { method: "POST", body: JSON.stringify(data) });

export const postJournalEntry = (id: string) =>
  req<JournalEntry>(`/api/v1/journals/entries/${id}/post`, { method: "POST" });

export const cancelJournalEntry = (id: string) =>
  req<JournalEntry>(`/api/v1/journals/entries/${id}/cancel`, { method: "POST" });
