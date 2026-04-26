"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/auth";
import Sidebar from "./Sidebar";
import { PageLoader } from "@/components/ui/Spinner";

const PUBLIC_PATHS = ["/login"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (!loading && !user && !isPublic) {
      router.push("/login");
    }
  }, [loading, user, isPublic, router]);

  if (isPublic) return <>{children}</>;

  if (loading) return <PageLoader fixed />;

  if (!user) return <PageLoader fixed />;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-auto min-w-0">{children}</main>
    </div>
  );
}
