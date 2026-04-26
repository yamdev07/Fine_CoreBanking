export type UserRole = "ADMIN" | "ACCOUNTANT" | "AUDITOR";

export interface AuthUser {
  id: string;
  username: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface AuthState {
  token: string;
  user: AuthUser;
  expires_at: number; // ms timestamp
}

const KEY = "cb_auth";

export function saveAuth(token: string, user: AuthUser, expires_in: number): void {
  const state: AuthState = {
    token,
    user,
    expires_at: Date.now() + expires_in * 1000,
  };
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {}
}

export function loadAuth(): AuthState | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const state: AuthState = JSON.parse(raw);
    if (Date.now() >= state.expires_at) {
      localStorage.removeItem(KEY);
      return null;
    }
    return state;
  } catch {
    return null;
  }
}

export function clearAuth(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {}
}

export function getToken(): string | null {
  return loadAuth()?.token ?? null;
}

export const ROLE_LABELS: Record<UserRole, string> = {
  ADMIN:      "Administrateur",
  ACCOUNTANT: "Comptable",
  AUDITOR:    "Auditeur",
};

export const ROLE_COLOR: Record<UserRole, string> = {
  ADMIN:      "badge-purple",
  ACCOUNTANT: "badge-blue",
  AUDITOR:    "badge-gray",
};

export function can(user: AuthUser | null, action: "write" | "admin"): boolean {
  if (!user) return false;
  if (action === "admin")  return user.role === "ADMIN";
  if (action === "write")  return user.role === "ADMIN" || user.role === "ACCOUNTANT";
  return true;
}
