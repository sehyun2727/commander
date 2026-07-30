"use client";

import { useAuth } from "@/lib/auth-context";

/** Minimal top-right account area (Sprint 9 §2.11 -- "이메일 또는 이니셜 +
 * 로그아웃. 드롭다운 메뉴 같은 건 만들지 마라"): a single click signs out, no
 * menu. The seed of the Render-style header this becomes in Sprint 14. */
export function AccountBadge() {
  const { user, logout } = useAuth();
  if (!user) return null;

  const initial = (user.display_name || user.email)[0]?.toUpperCase() ?? "?";

  return (
    <button
      onClick={() => logout()}
      title={`${user.email} — Sign out`}
      className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent transition-colors hover:bg-status-red-soft hover:text-status-red"
    >
      {initial}
    </button>
  );
}
