"use client";

import { useApiHealth } from "@/lib/hooks";

/** App-wide banner for when the API is unreachable -- polling (not a single
 * failed request) so a transient blip doesn't flash the banner; it only
 * shows once `useApiHealth` has actually failed. */
export function ApiStatusBanner() {
  const { isError } = useApiHealth();
  if (!isError) return null;

  return (
    <div
      role="alert"
      className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-status-red-soft px-4 py-2 text-sm font-medium text-status-red"
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
      Can&apos;t reach the Commander API — retrying…
    </div>
  );
}
