import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/auth";
import AppShell from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "Core Banking — Tableau de bord",
  description: "Système de gestion comptable SYSCOHADA/BCEAO",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
