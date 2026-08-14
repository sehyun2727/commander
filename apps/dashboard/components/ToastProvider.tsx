"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { ApiError } from "@/lib/api";

type ToastVariant = "error" | "success";

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextToastId = 0;

/** Rule #18 ("CEO actions never fail silently"): every dashboard mutation
 * routes its failure here instead of a swallowed console.error, so a
 * failed Decision/Assign/Cancel/etc. always ends as something visible on
 * screen, not a silent no-op the CEO has to notice on their own. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, variant: ToastVariant = "error") => {
    const id = ++nextToastId;
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 7000);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="alert"
            onClick={() => dismiss(t.id)}
            className={`pointer-events-auto cursor-pointer rounded-lg border px-4 py-3 text-sm shadow-panel ${
              t.variant === "error"
                ? "border-status-red/40 bg-status-red-soft text-status-red"
                : "border-status-green/40 bg-status-green-soft text-status-green"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}

/** Every request() failure in lib/api.ts throws ApiError with a
 * CEO-legible `.message` already (either FastAPI's `detail` string or a
 * generic "<method> <path> failed: <status>"). Anything else (network
 * failure, thrown non-Error) falls back to a generic message rather than
 * leaking a raw error object into the toast. */
export function mutationErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Please try again.";
}
