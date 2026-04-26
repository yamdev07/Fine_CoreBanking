"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth";
import { Landmark, Eye, EyeOff, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur de connexion.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-brand-950 to-slate-900 flex items-center justify-center p-4">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-brand-600/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-brand-800/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand-600 rounded-2xl shadow-lg mb-4">
            <Landmark className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Core Banking</h1>
          <p className="text-slate-400 text-sm mt-1">Système de gestion comptable</p>
        </div>

        {/* Card */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-7 shadow-2xl">
          <h2 className="text-lg font-semibold text-white mb-1">Connexion</h2>
          <p className="text-slate-400 text-sm mb-6">Entrez vos identifiants pour continuer</p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="form-group">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider">
                Nom d&apos;utilisateur
              </label>
              <input
                type="text"
                className="w-full px-3.5 py-2.5 text-sm bg-white/10 border border-white/15 text-white rounded-xl
                           placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50
                           focus:border-brand-500 transition-all"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            <div className="form-group">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider">
                Mot de passe
              </label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  className="w-full px-3.5 py-2.5 pr-10 text-sm bg-white/10 border border-white/15 text-white rounded-xl
                             placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50
                             focus:border-brand-500 transition-all"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3.5 py-2.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy || !username || !password}
              className="w-full py-2.5 bg-brand-600 hover:bg-brand-500 active:bg-brand-700 text-white font-semibold
                         text-sm rounded-xl transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed
                         shadow-lg shadow-brand-900/30 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2
                         focus:ring-offset-transparent flex items-center justify-center gap-2"
            >
              {busy ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Connexion...
                </>
              ) : "Se connecter"}
            </button>
          </form>

          <p className="mt-6 text-center text-xs text-slate-500">
            Compte par défaut : <span className="text-slate-400 font-mono">admin / Admin1234!</span>
          </p>
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          SYSCOHADA · BCEAO/UEMOA · {new Date().getFullYear()}
        </p>
      </div>
    </div>
  );
}
