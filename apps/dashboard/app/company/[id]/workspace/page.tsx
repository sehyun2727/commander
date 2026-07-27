"use client";

import { useState } from "react";
import { useWorkspaceFile, useWorkspaceMerges, useWorkspaceTree } from "@/lib/hooks";

export default function WorkspacePage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: tree, isLoading: treeLoading, isError: treeError } = useWorkspaceTree(companyId);
  const { data: merges, isError: mergesError } = useWorkspaceMerges(companyId);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const { data: file, isLoading: fileLoading, isError: fileError } = useWorkspaceFile(companyId, selectedPath);

  return (
    <main className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-text">Workspace</h1>
        <p className="mt-1 text-sm text-text-muted">
          The company&apos;s real, git-backed codebase — browse files and merge history.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
        <div className="rounded-xl border border-base-border bg-base-card p-3 shadow-panel">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-faint">Files</h2>
          {treeLoading ? (
            <p className="text-xs text-text-faint">Loading…</p>
          ) : treeError ? (
            <p className="text-xs text-status-red">Couldn&apos;t load files.</p>
          ) : !tree?.length ? (
            <p className="text-xs text-text-faint">No committed code yet.</p>
          ) : (
            <ul className="space-y-0.5">
              {tree.map((entry) => (
                <li key={entry.path}>
                  <button
                    onClick={() => setSelectedPath(entry.path)}
                    className={`block w-full truncate rounded-md px-2 py-1 text-left font-mono text-xs ${
                      selectedPath === entry.path
                        ? "bg-accent-soft text-accent"
                        : "text-text-muted hover:bg-base-hover hover:text-text"
                    }`}
                  >
                    {entry.path}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-faint">File Viewer</h2>
            {!selectedPath ? (
              <p className="text-sm text-text-faint">Select a file from the tree to view its contents.</p>
            ) : fileLoading ? (
              <p className="text-sm text-text-faint">Loading {selectedPath}…</p>
            ) : fileError ? (
              <p className="text-sm text-status-red">Couldn&apos;t load {selectedPath}. Try refreshing in a moment.</p>
            ) : (
              <pre className="max-h-[32rem] overflow-auto rounded-lg bg-base-raised p-3 text-xs text-text-muted">
                {file?.content}
              </pre>
            )}
          </div>

          <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-faint">Recent Merges</h2>
            {mergesError ? (
              <p className="text-sm text-status-red">Couldn&apos;t load merge history.</p>
            ) : !merges?.length ? (
              <p className="text-sm text-text-faint">No merges yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {merges.map((merge) => (
                  <li key={merge.commit_sha} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-text-muted">{merge.subject}</span>
                    <span className="shrink-0 text-xs text-text-faint">
                      {new Date(merge.merged_at).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
