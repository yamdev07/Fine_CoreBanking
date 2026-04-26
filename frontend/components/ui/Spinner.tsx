import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export function Spinner({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={cn("animate-spin text-brand-500", className)} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-80" fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}

export function PageLoader({ fixed = false }: { fixed?: boolean }) {
  return (
    <div className={fixed
      ? "fixed inset-0 flex items-center justify-center bg-slate-50/90 backdrop-blur-sm z-50"
      : "flex flex-col items-center justify-center gap-4 py-24"
    }>
      <Spinner className="w-10 h-10" />
      <p className="text-sm text-slate-400 font-medium">Chargement...</p>
    </div>
  );
}

export function ErrorBox({
  message,
  className,
}: {
  message: string;
  className?: string;
}) {
  return (
    <div className={cn(
      "flex items-center gap-3 rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700",
      className
    )}>
      <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
      {message}
    </div>
  );
}
