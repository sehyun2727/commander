import { useMemo } from "react";
import type { WidgetDefinition, WidgetPreferenceEntry, WorkspaceSnapshot } from "@/lib/types";
import { WidgetErrorBoundary } from "./WidgetErrorBoundary";
import { WORKSPACE_WIDGET_COMPONENTS } from "./widgetComponents";

// Sprint 15 §4.9/DECISIONS.md #228: one canonical order drives both
// desktop and mobile -- desktop packs consecutive `half`-span widgets two
// per row and gives `full`-span widgets their own row; mobile ignores
// packing entirely and just stacks every visible widget in the same
// order, one per row (`lg:grid-cols-2` only applies at the desktop
// breakpoint). No free x/y grid, no per-breakpoint reordering.
function packRows(entries: WidgetPreferenceEntry[]): WidgetPreferenceEntry[][] {
  const rows: WidgetPreferenceEntry[][] = [];
  let pendingHalf: WidgetPreferenceEntry | null = null;
  for (const entry of entries) {
    if (entry.span === "full") {
      if (pendingHalf) {
        rows.push([pendingHalf]);
        pendingHalf = null;
      }
      rows.push([entry]);
    } else if (pendingHalf) {
      rows.push([pendingHalf, entry]);
      pendingHalf = null;
    } else {
      pendingHalf = entry;
    }
  }
  if (pendingHalf) rows.push([pendingHalf]);
  return rows;
}

const warnedUnsupportedKeys = new Set<string>();

export function WorkspaceWidgetGrid({
  entries,
  snapshot,
  companyId,
  onRefresh,
  catalog,
}: {
  entries: WidgetPreferenceEntry[];
  snapshot: WorkspaceSnapshot;
  companyId: string;
  onRefresh: () => void;
  catalog?: WidgetDefinition[];
}) {
  const rows = packRows(entries);
  const catalogByKey = useMemo(() => new Map((catalog ?? []).map((w) => [w.key, w])), [catalog]);

  return (
    <div className="flex flex-col gap-4">
      {rows.map((row) => (
        <div
          key={row.map((w) => w.widget_key).join("+")}
          className={row.length === 2 ? "grid grid-cols-1 gap-4 lg:grid-cols-2" : "grid grid-cols-1 gap-4"}
        >
          {row.map((entry) => {
            const Widget = WORKSPACE_WIDGET_COMPONENTS[entry.widget_key];
            if (!Widget) {
              // §7.1: unknown/unsupported key -- omit safely in normal
              // mode (never crash, never guess a renderer), report once
              // through the only observability channel this frontend has.
              if (!warnedUnsupportedKeys.has(entry.widget_key)) {
                warnedUnsupportedKeys.add(entry.widget_key);
                console.warn(`CEO Workspace: no renderer for widget "${entry.widget_key}" -- omitted.`);
              }
              return null;
            }
            const title = catalogByKey.get(entry.widget_key)?.title ?? entry.widget_key;
            return (
              <div key={entry.widget_key}>
                <WidgetErrorBoundary widgetTitle={title} critical={entry.widget_key === "primary_next_action"}>
                  <Widget snapshot={snapshot} companyId={companyId} onRefresh={onRefresh} />
                </WidgetErrorBoundary>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
