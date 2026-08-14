# Dashboard

Commander Headquarters — the CEO-facing web app (Next.js App Router, TypeScript, Tailwind). Talks to the API Server over REST and SSE. No AI logic lives here.

## Pages

- `/` — company list / found a new company
- `/company/[id]` — Headquarters (stats, CEO Decisions, live Timeline)
- `/company/[id]/missions` — Missions kanban
- `/company/[id]/missions/[taskId]` — mission detail + Meeting chat
- `/company/[id]/meetings/[taskId]` — Meeting chat (same detail view)
- `/company/[id]/employees` — Employees grid
- `/company/[id]/settings` — Company Settings

## Dev

```bash
pnpm install
cp .env.local.example .env.local
pnpm dev
```

Requires the API server running at the URL in `.env.local` (`NEXT_PUBLIC_API_URL`, default `http://localhost:8000`).
