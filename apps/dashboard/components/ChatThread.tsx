"use client";

import { useState } from "react";
import { useMessages, usePostMessage } from "@/lib/hooks";
import { relativeTime } from "@/lib/utils";

export function ChatThread({ taskId }: { taskId: string }) {
  const { data: messages, isLoading } = useMessages(taskId);
  const post = usePostMessage(taskId);
  const [text, setText] = useState("");

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    setText("");
    await post.mutateAsync(trimmed);
  }

  return (
    <div className="flex flex-col rounded-xl border border-base-border bg-base-card shadow-panel">
      <div className="max-h-[28rem] min-h-[10rem] flex-1 space-y-3 overflow-y-auto p-4">
        {isLoading && <p className="text-sm text-text-muted">Loading meeting…</p>}
        {!isLoading && (messages?.length ?? 0) === 0 && (
          <p className="text-center text-sm text-text-faint">No messages yet. Say hello to the Department.</p>
        )}
        {messages?.map((message) => {
          const isCeo = message.actor.role === "ceo";
          const messageText = (message.payload as { text?: string }).text ?? "";
          return (
            <div key={message.id} className={`flex ${isCeo ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-xl px-3.5 py-2.5 ${isCeo ? "bg-accent text-white" : "bg-base-hover text-text"}`}>
                {!isCeo && <p className="mb-0.5 text-[11px] font-semibold opacity-70">{message.actor.name}</p>}
                <p className="whitespace-pre-wrap text-sm">{messageText}</p>
                <p className={`mt-1 text-[10px] ${isCeo ? "text-white/60" : "text-text-faint"}`}>
                  {relativeTime(message.created_at)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
      <form onSubmit={handleSend} className="flex gap-2 border-t border-base-border p-3">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Message the Department…"
          className="flex-1 rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={post.isPending || !text.trim()}
          className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
