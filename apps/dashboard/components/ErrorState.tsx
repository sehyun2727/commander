/** Commander-voiced fallback for a failed TanStack Query fetch. Every
 * route using useQuery/useInfiniteQuery must render this on `isError`
 * instead of leaking `undefined` data or a raw error object. */
export function ErrorState({ description }: { description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-status-red/40 bg-status-red-soft px-6 py-16 text-center">
      <p className="text-sm font-medium text-status-red">Couldn&apos;t load this.</p>
      <p className="mt-1 max-w-sm text-sm text-text-muted">
        {description ?? "Something went wrong reaching your company. Try refreshing in a moment."}
      </p>
    </div>
  );
}
