"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

/** Gates a protected page/layout on the current session (Sprint 9 §2.11
 * "미인증 상태로 보호된 경로 진입 → /login 리다이렉트"). Proactive: acts on the
 * `/api/auth/me` check AuthProvider already ran, so an unauthenticated
 * visitor never sees a flash of protected UI while its queries fail. The
 * reactive counterpart -- a session going stale mid-visit -- is handled
 * globally by AuthProvider's `commander:unauthorized` listener instead. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) return null;
  return <>{children}</>;
}
