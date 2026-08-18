"use client";

import { useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { mutationErrorMessage } from "@/components/ToastProvider";
import {
  isStaleRevisionConflict,
  useResetWorkspacePreferences,
  useUpdateWorkspacePreferences,
  useWorkspacePreferences,
} from "@/lib/hooks";
import type { WidgetDefinition, WidgetPreferenceEntry, WorkspacePreferences } from "@/lib/types";
import { WORKSPACE_WIDGET_COMPONENTS } from "./widgetComponents";

function sameEntries(a: WidgetPreferenceEntry[], b: WidgetPreferenceEntry[]): boolean {
  if (a.length !== b.length) return false;
  const byKey = new Map(b.map((e) => [e.widget_key, e]));
  return a.every((e) => {
    const other = byKey.get(e.widget_key);
    return !!other && other.visible === e.visible && other.order === e.order && other.span === e.span;
  });
}

function EditModeShell({
  onClose,
  saveControls,
  children,
}: {
  onClose: () => void;
  saveControls?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-text">Customize Workspace</h1>
          <p className="mt-1 text-sm text-text-muted">
            Reorder, hide, and restore widgets. Changes apply only after you save.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {saveControls}
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-base-border px-4 py-2 text-sm font-medium text-text hover:bg-base-hover"
          >
            Close
          </button>
        </div>
      </header>
      {children}
    </main>
  );
}

export function WorkspaceEditMode({
  companyId,
  catalog,
  onClose,
}: {
  companyId: string;
  catalog: WidgetDefinition[];
  onClose: () => void;
}) {
  const { data: preferences, isLoading, isError, refetch } = useWorkspacePreferences(companyId);

  if (isLoading) {
    return (
      <EditModeShell onClose={onClose}>
        <div className="h-64 animate-pulse rounded-xl bg-base-hover" />
      </EditModeShell>
    );
  }

  if (isError || !preferences) {
    return (
      <EditModeShell onClose={onClose}>
        <ErrorState description="Couldn't load your Workspace layout. Try again in a moment." />
      </EditModeShell>
    );
  }

  return (
    <WorkspaceEditModeReady
      companyId={companyId}
      catalog={catalog}
      preferences={preferences}
      onClose={onClose}
      onReload={refetch}
    />
  );
}

function WorkspaceEditModeReady({
  companyId,
  catalog,
  preferences,
  onClose,
  onReload,
}: {
  companyId: string;
  catalog: WidgetDefinition[];
  preferences: WorkspacePreferences;
  onClose: () => void;
  onReload: () => Promise<{ data?: WorkspacePreferences }>;
}) {
  const [savedEntries, setSavedEntries] = useState<WidgetPreferenceEntry[]>(preferences.widgets);
  const [entries, setEntries] = useState<WidgetPreferenceEntry[]>(preferences.widgets);
  const [revision, setRevision] = useState(preferences.revision);
  const [conflict, setConflict] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const update = useUpdateWorkspacePreferences(companyId);
  const reset = useResetWorkspacePreferences(companyId);

  const catalogByKey = useMemo(() => new Map(catalog.map((w) => [w.key, w])), [catalog]);
  const dirty = !sameEntries(entries, savedEntries);

  // Browser-level guard against losing edits to a tab close/reload -- this
  // codebase has no existing pattern for blocking in-app client-side route
  // navigation (no other page attempts it), so that stays out of scope here
  // (recorded in docs/DECISIONS.md); Cancel below covers in-page discard.
  useEffect(() => {
    if (!dirty) return;
    function handler(e: BeforeUnloadEvent) {
      e.preventDefault();
      e.returnValue = "";
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const visible = [...entries].filter((e) => e.visible).sort((a, b) => a.order - b.order);
  const hidden = [...entries].filter((e) => !e.visible).sort((a, b) => a.order - b.order);

  function titleFor(widgetKey: string): string {
    return catalogByKey.get(widgetKey)?.title ?? widgetKey;
  }

  function isSupported(widgetKey: string): boolean {
    return widgetKey in WORKSPACE_WIDGET_COMPONENTS;
  }

  function moveVisible(widgetKey: string, direction: -1 | 1) {
    const idx = visible.findIndex((e) => e.widget_key === widgetKey);
    const swapIdx = idx + direction;
    if (idx < 0 || swapIdx < 0 || swapIdx >= visible.length) return;
    const a = visible[idx];
    const b = visible[swapIdx];
    setEntries((prev) =>
      prev.map((e) => {
        if (e.widget_key === a.widget_key) return { ...e, order: b.order };
        if (e.widget_key === b.widget_key) return { ...e, order: a.order };
        return e;
      })
    );
    setAnnouncement(
      `${titleFor(a.widget_key)} moved to position ${swapIdx + 1} of ${visible.length}.`
    );
  }

  function hideWidget(widgetKey: string) {
    setEntries((prev) => prev.map((e) => (e.widget_key === widgetKey ? { ...e, visible: false } : e)));
    setAnnouncement(`${titleFor(widgetKey)} hidden.`);
  }

  function restoreWidget(widgetKey: string) {
    const maxOrder = entries.reduce((max, e) => Math.max(max, e.order), 0);
    setEntries((prev) =>
      prev.map((e) => (e.widget_key === widgetKey ? { ...e, visible: true, order: maxOrder + 1 } : e))
    );
    setAnnouncement(`${titleFor(widgetKey)} restored.`);
  }

  async function handleSave() {
    setErrorMessage(null);
    setConflict(false);
    try {
      const result = await update.mutateAsync({ expected_revision: revision, widgets: entries });
      setSavedEntries(result.widgets);
      setEntries(result.widgets);
      setRevision(result.revision);
      setAnnouncement("Workspace layout saved.");
    } catch (error) {
      if (isStaleRevisionConflict(error)) {
        setConflict(true);
      } else {
        setErrorMessage(mutationErrorMessage(error));
      }
    }
  }

  function handleCancel() {
    if (dirty && !window.confirm("Discard unsaved changes to your Workspace layout?")) return;
    setEntries(savedEntries);
    setErrorMessage(null);
    setConflict(false);
    onClose();
  }

  async function handleReset() {
    if (!window.confirm("Reset the Workspace layout to its default order and visibility? This applies immediately.")) {
      return;
    }
    setErrorMessage(null);
    setConflict(false);
    try {
      const result = await reset.mutateAsync();
      setSavedEntries(result.widgets);
      setEntries(result.widgets);
      setRevision(result.revision);
      setAnnouncement("Workspace layout reset to default.");
    } catch {
      // useResetWorkspacePreferences already surfaces a toast (Rule #18).
    }
  }

  async function handleReloadLatest() {
    if (dirty && !window.confirm("Reload the latest layout from the server? Your unsaved changes will be lost.")) {
      return;
    }
    const fresh = await onReload();
    if (fresh.data) {
      setSavedEntries(fresh.data.widgets);
      setEntries(fresh.data.widgets);
      setRevision(fresh.data.revision);
      setConflict(false);
      setAnnouncement("Loaded the latest Workspace layout.");
    }
  }

  return (
    <EditModeShell
      onClose={handleCancel}
      saveControls={
        <>
          {dirty && (
            <button
              type="button"
              onClick={handleCancel}
              className="rounded-lg border border-base-border px-4 py-2 text-sm font-medium text-text hover:bg-base-hover"
            >
              Cancel
            </button>
          )}
          <button
            type="button"
            onClick={handleSave}
            disabled={!dirty || update.isPending}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {update.isPending ? "Saving…" : "Save Layout"}
          </button>
        </>
      }
    >
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>

      {conflict && (
        <div className="mb-4 rounded-lg border border-status-amber/40 bg-status-amber-soft px-4 py-3 text-sm text-status-amber">
          <p className="font-medium">Someone changed this layout since you loaded it.</p>
          <p className="mt-1 text-text-muted">
            Your unsaved changes are still here. Reload the latest layout to see what changed, or keep editing and
            save again to overwrite it.
          </p>
          <button
            type="button"
            onClick={handleReloadLatest}
            className="mt-2 rounded-lg border border-status-amber/50 px-3 py-1.5 text-xs font-medium text-status-amber hover:bg-status-amber-soft"
          >
            Reload Latest Layout
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="mb-4 rounded-lg border border-status-red/40 bg-status-red-soft px-4 py-3 text-sm text-status-red">
          {errorMessage}
        </div>
      )}

      <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-faint">
          Visible Widgets ({visible.length})
        </h2>
        <ul className="space-y-2">
          {visible.map((entry, index) => {
            const definition = catalogByKey.get(entry.widget_key);
            const supported = isSupported(entry.widget_key);
            return (
              <li
                key={entry.widget_key}
                className="flex flex-col gap-2 rounded-lg border border-base-border bg-base-raised p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-text">
                    {definition?.title ?? entry.widget_key}
                    {definition?.required && (
                      <span className="ml-2 rounded bg-base-hover px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-faint">
                        Required
                      </span>
                    )}
                    {!supported && (
                      <span className="ml-2 rounded bg-status-red-soft px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-status-red">
                        Unsupported — will not display
                      </span>
                    )}
                  </p>
                  {definition?.description && <p className="mt-0.5 text-xs text-text-muted">{definition.description}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    type="button"
                    aria-label={`Move ${titleFor(entry.widget_key)} up`}
                    onClick={() => moveVisible(entry.widget_key, -1)}
                    disabled={index === 0}
                    className="rounded-lg border border-base-border px-2.5 py-1.5 text-xs font-medium text-text hover:bg-base-hover disabled:opacity-30"
                  >
                    Move up
                  </button>
                  <button
                    type="button"
                    aria-label={`Move ${titleFor(entry.widget_key)} down`}
                    onClick={() => moveVisible(entry.widget_key, 1)}
                    disabled={index === visible.length - 1}
                    className="rounded-lg border border-base-border px-2.5 py-1.5 text-xs font-medium text-text hover:bg-base-hover disabled:opacity-30"
                  >
                    Move down
                  </button>
                  {!definition?.required && (
                    <button
                      type="button"
                      aria-label={`Hide ${titleFor(entry.widget_key)}`}
                      onClick={() => hideWidget(entry.widget_key)}
                      className="rounded-lg border border-base-border px-2.5 py-1.5 text-xs font-medium text-text hover:bg-base-hover"
                    >
                      Hide
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="mt-4 rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-faint">
          Hidden Widgets ({hidden.length})
        </h2>
        {hidden.length === 0 ? (
          <p className="text-xs text-text-faint">Every optional widget is currently visible.</p>
        ) : (
          <ul className="space-y-2">
            {hidden.map((entry) => {
              const definition = catalogByKey.get(entry.widget_key);
              return (
                <li
                  key={entry.widget_key}
                  className="flex flex-col gap-2 rounded-lg border border-base-border bg-base-raised p-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="text-sm font-medium text-text">{definition?.title ?? entry.widget_key}</p>
                    {definition?.description && (
                      <p className="mt-0.5 text-xs text-text-muted">{definition.description}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    aria-label={`Restore ${titleFor(entry.widget_key)}`}
                    onClick={() => restoreWidget(entry.widget_key)}
                    className="shrink-0 rounded-lg border border-base-border px-2.5 py-1.5 text-xs font-medium text-text hover:bg-base-hover"
                  >
                    Restore
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={handleReset}
          disabled={reset.isPending}
          className="rounded-lg border border-status-red/40 px-4 py-2 text-sm font-medium text-status-red hover:bg-status-red-soft disabled:opacity-50"
        >
          {reset.isPending ? "Resetting…" : "Reset to Default"}
        </button>
      </div>
    </EditModeShell>
  );
}
