"use client";

import { useState } from "react";
import { FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import { getToken } from "@/lib/auth";

interface Props {
  pdfUrl?: string;
  excelUrl?: string;
}

async function downloadWithAuth(url: string, filename: string) {
  const token = getToken();
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    const msg = typeof err?.detail === "string" ? err.detail : `Erreur ${res.status}`;
    throw new Error(msg);
  }
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}

function ExportButton({
  url,
  filename,
  icon: Icon,
  label,
}: {
  url: string;
  filename: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handle = async () => {
    setLoading(true);
    setError("");
    try {
      await downloadWithAuth(url, filename);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <button onClick={handle} disabled={loading} className="btn-secondary text-xs disabled:opacity-60">
        {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
        {label}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}

export default function ExportButtons({ pdfUrl, excelUrl }: Props) {
  return (
    <div className="flex items-start gap-2">
      {pdfUrl && (
        <ExportButton url={pdfUrl} filename="rapport.pdf" icon={FileText} label="PDF" />
      )}
      {excelUrl && (
        <ExportButton url={excelUrl} filename="rapport.xlsx" icon={FileSpreadsheet} label="Excel" />
      )}
    </div>
  );
}
