"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { useRequireAuth } from "@/context/auth";
import {
  getUsers, createUser, updateUser,
  type UserRecord,
} from "@/lib/api/accounting";
import { ROLE_LABELS, ROLE_COLOR, type UserRole } from "@/lib/auth";
import { ErrorBox, Spinner } from "@/components/ui/Spinner";
import { formatDate } from "@/lib/utils";
import {
  Plus, Pencil, UserX, Check, X, Shield, Eye, EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";

type FormMode = "create" | "edit";

interface UserForm {
  username: string;
  full_name: string;
  email: string;
  password: string;
  role: UserRole;
}

const EMPTY_FORM: UserForm = {
  username: "", full_name: "", email: "", password: "", role: "AUDITOR",
};

export default function UsersPage() {
  const { user: me } = useRequireAuth();
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formMode, setFormMode] = useState<FormMode | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<UserForm>(EMPTY_FORM);
  const [showPw, setShowPw] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  async function load() {
    try {
      setLoading(true);
      setError("");
      setUsers(await getUsers());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (me && me.role !== "ADMIN") {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <Shield className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">Accès réservé aux administrateurs.</p>
        </div>
      </div>
    );
  }

  function openCreate() {
    setForm(EMPTY_FORM);
    setEditId(null);
    setFormMode("create");
    setFormError("");
  }

  function openEdit(u: UserRecord) {
    setForm({ username: u.username, full_name: u.full_name, email: u.email, password: "", role: u.role });
    setEditId(u.id);
    setFormMode("edit");
    setFormError("");
  }

  function closeForm() {
    setFormMode(null);
    setEditId(null);
    setFormError("");
  }

  async function handleSave() {
    setSaving(true);
    setFormError("");
    try {
      if (formMode === "create") {
        await createUser(form);
      } else if (editId) {
        const payload: Record<string, unknown> = {
          full_name: form.full_name, email: form.email, role: form.role,
        };
        if (form.password) payload.password = form.password;
        await updateUser(editId, payload);
      }
      await load();
      closeForm();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(u: UserRecord) {
    await updateUser(u.id, { is_active: !u.is_active });
    await load();
  }

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Gestion des utilisateurs"
        subtitle="Créez et gérez les accès au système"
        actions={
          <button onClick={openCreate} className="btn-primary">
            <Plus className="w-4 h-4" /> Nouvel utilisateur
          </button>
        }
      />

      <div className="flex-1 p-6 space-y-5">
        {error && <ErrorBox message={error} />}

        {/* Form panel */}
        {formMode && (
          <div className="card p-6 border-brand-100 ring-1 ring-brand-200">
            <div className="flex items-center justify-between mb-5">
              <h2 className="section-title">
                {formMode === "create" ? "Nouvel utilisateur" : "Modifier l'utilisateur"}
              </h2>
              <button onClick={closeForm} className="btn-icon"><X className="w-4 h-4" /></button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className={cn("form-group", formMode === "edit" && "opacity-50 pointer-events-none")}>
                <label className="label">Nom d&apos;utilisateur</label>
                <input className="input" value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  disabled={formMode === "edit"} placeholder="jean.dupont" />
              </div>
              <div className="form-group">
                <label className="label">Nom complet</label>
                <input className="input" value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  placeholder="Jean Dupont" />
              </div>
              <div className="form-group">
                <label className="label">Email</label>
                <input className="input" type="email" value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="jean@banque.com" />
              </div>
              <div className="form-group">
                <label className="label">Rôle</label>
                <select className="input" value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
                  <option value="ADMIN">Administrateur</option>
                  <option value="ACCOUNTANT">Comptable</option>
                  <option value="AUDITOR">Auditeur</option>
                </select>
              </div>
              <div className="form-group col-span-2">
                <label className="label">
                  {formMode === "create" ? "Mot de passe" : "Nouveau mot de passe (optionnel)"}
                </label>
                <div className="relative">
                  <input className="input pr-10" type={showPw ? "text" : "password"}
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    placeholder={formMode === "edit" ? "Laisser vide pour ne pas changer" : "Min. 8 caractères"} />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>

            {formError && <ErrorBox message={formError} className="mt-3" />}

            <div className="flex items-center justify-end gap-3 mt-5 pt-4 border-t border-slate-100">
              <button onClick={closeForm} className="btn-secondary">Annuler</button>
              <button onClick={handleSave} disabled={saving} className="btn-primary">
                {saving ? <><span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Enregistrement...</> : <><Check className="w-4 h-4" /> Enregistrer</>}
              </button>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="card overflow-hidden">
          {loading ? (
            <div className="flex justify-center py-16"><Spinner /></div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="th">Utilisateur</th>
                  <th className="th">Email</th>
                  <th className="th">Rôle</th>
                  <th className="th">Statut</th>
                  <th className="th">Dernière connexion</th>
                  <th className="th">Créé le</th>
                  <th className="th text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="tr-hover border-b border-slate-50 last:border-0">
                    <td className="td">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center shrink-0">
                          <span className="text-brand-600 font-bold text-xs">{u.full_name.charAt(0)}</span>
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900 text-sm">{u.full_name}</p>
                          <p className="text-slate-400 text-xs font-mono">@{u.username}</p>
                        </div>
                      </div>
                    </td>
                    <td className="td text-slate-500">{u.email}</td>
                    <td className="td">
                      <span className={ROLE_COLOR[u.role]}>
                        {ROLE_LABELS[u.role]}
                      </span>
                    </td>
                    <td className="td">
                      {u.is_active
                        ? <span className="badge-green">Actif</span>
                        : <span className="badge-red">Inactif</span>}
                    </td>
                    <td className="td text-slate-400 text-xs">
                      {u.last_login_at ? formatDate(u.last_login_at.slice(0, 10)) : "—"}
                    </td>
                    <td className="td text-slate-400 text-xs">
                      {formatDate(u.created_at.slice(0, 10))}
                    </td>
                    <td className="td">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => openEdit(u)} className="btn-icon" title="Modifier">
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        {u.id !== me?.id && (
                          <button
                            onClick={() => handleToggleActive(u)}
                            className={cn("btn-icon", u.is_active ? "hover:text-amber-500" : "hover:text-emerald-500")}
                            title={u.is_active ? "Désactiver" : "Réactiver"}
                          >
                            {u.is_active ? <UserX className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={7} className="empty">Aucun utilisateur</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
