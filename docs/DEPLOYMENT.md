# Deployment — Commander

This is the operator's reference for running Commander outside of local
development: first deployment, production run recipe, backup/restore, and
upgrading an existing install. It is the sole operational reference for
Sprint 19 (`v1.1.0`) — see `docs/KNOWN_ISSUES.md` for the operating limits
that apply once it's running.

## 1. Prerequisites

- Linux, macOS, or WSL2 on Windows. (Native Windows works for development
  via PowerShell, as this repo's own dev environment demonstrates, but this
  guide's production recipe assumes a Unix-like shell.)
- Python 3.11+
- Node.js 20+
- pnpm
- Docker Desktop or Docker Engine (for Postgres; see §2)
- git

## 2. First deployment walkthrough

```bash
git clone <repo-url> commander
cd commander
cp .env.example .env        # then edit .env — see §4 for the production variant
make install                # API venv + dashboard deps
make db-up                  # start Postgres, wait for healthy
make db-upgrade             # apply Alembic migrations to head
make seed                   # optional — creates a demo Company "Acme AI"
make dev                    # API :8000 + dashboard :3000, foreground
```

`make dev` is a development convenience (auto-reload, both processes in one
foreground terminal via a trap). For an always-on deployment, use the
production run recipe in §3 instead of `make dev`.

This walkthrough was dry-run against this repo's own Postgres 16 container
during Sprint 19 Phase 3: `make db-upgrade` and a plain `uvicorn
app.main:app` boot both completed cleanly, boot checks passed, and the
server logged `alembic_head=c2a7e1f4b6d3 db_revision=c2a7e1f4b6d3` (schema
in sync) before accepting requests.

## 3. Production run recipe

Commander is a single FastAPI process (`apps/api`) plus a single Next.js
process (`apps/dashboard`). There is no ops stack beyond Postgres — see
`docs/KNOWN_ISSUES.md` §1 for the single-worker/no-broker tradeoffs this
implies.

### Option A — systemd (recommended for a persistent host)

`/etc/systemd/system/commander-api.service`:

```ini
[Unit]
Description=Commander API
After=network.target docker.service

[Service]
Type=simple
User=commander
WorkingDirectory=/opt/commander
EnvironmentFile=/opt/commander/.env
ExecStart=/opt/commander/apps/api/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
WorkingDirectory=/opt/commander/apps/api
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`--workers 1` is deliberate, not a placeholder — see the single-worker
tradeoff in `docs/KNOWN_ISSUES.md` §1. Running more than one worker process
is not currently a supported topology (no cross-process coordination for
background Mission pipelines).

`/etc/systemd/system/commander-dashboard.service` follows the same shape,
running `pnpm --filter @commander/dashboard start` after a production
`pnpm --filter @commander/dashboard build`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now commander-api commander-dashboard
```

### Option B — nohup (simple, single-host, no systemd)

```bash
cd /opt/commander/apps/api
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 \
  > /var/log/commander-api.log 2>&1 &

cd /opt/commander/apps/dashboard
pnpm build
nohup pnpm start > /var/log/commander-dashboard.log 2>&1 &
```

## 4. `.env.production.example`

`.env.production.example` (repo root) is the production-oriented template
— copy it to `.env` and fill in real values. It differs from
`.env.example` in the fields that matter for a real deployment:
`COMMANDER_PROVIDER` defaults to `anthropic` (never `mock`),
`COMMANDER_COOKIE_SECURE=true` (required behind TLS — see the inline
comment for why a browser silently drops the cookie otherwise), a
placeholder strong `POSTGRES_PASSWORD`, and no demo account credentials.

## 5. Optional HTTPS termination (nginx)

Optional, not required for v1.1.0 to function — Commander itself speaks
plain HTTP; TLS termination is an operator concern typical of any
self-hosted app.

```nginx
server {
    listen 443 ssl;
    server_name commander.yourcompany.com;

    ssl_certificate     /etc/letsencrypt/live/commander.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/commander.yourcompany.com/privkey.pem;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # SSE (/api/events/stream) needs buffering off and a long read
        # timeout, or nginx will buffer/cut the stream.
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 6. Backup and restore

Two things need backing up: the Postgres database, and the
`COMMANDER_WORKSPACE_ROOT` directory (every Company's real git history —
not reconstructable from the DB alone).

**Backup:**

```bash
pg_dump -Fc -h localhost -U commander commander > commander-$(date +%F).dump
tar -czf commander-workspaces-$(date +%F).tar.gz -C /var/lib/commander workspaces
```

**Restore:**

```bash
# Database (into a fresh, empty database named `commander`):
pg_restore -h localhost -U commander -d commander --clean --if-exists commander-2026-08-19.dump

# Workspaces:
tar -xzf commander-workspaces-2026-08-19.tar.gz -C /var/lib/commander
```

After restoring the database, run `make db-upgrade` once to confirm the
restored schema matches the running code's Alembic head before starting
the API process.

## 7. Upgrading from v1.0.0 (or any pre-Sprint-19 revision)

```bash
git pull
make install       # picks up any new Python/Node dependencies
make db-upgrade     # applies any migrations added since your last upgrade
# restart the API and dashboard processes (systemctl restart ... or re-run
# the nohup commands in §3)
```

**Special note if upgrading from v1.0.0 specifically:** v1.0.0 predates the
Sprint 9 auth schema. It has no `users` or `sessions` table, and no
Company has an `owner_id`. `make db-upgrade` will run the
`fa793dce62cb_accounts_and_sessions` migration (among others) to add them,
but migrating the schema does not by itself attribute existing pre-auth
Companies to a CEO account — a v1.0.0 database has no account to attribute
them to yet. After upgrading:

1. Register a CEO account through the normal signup flow (or
   `scripts/reset_password.py <email> <new-password>` if you'd rather set
   a password directly against a manually-inserted `users` row).
2. Attribute existing Companies to that account. There is no scripted
   migration for this step because the correct owner is an operator
   decision, not a derivable fact — run one SQL statement per Company (or
   in bulk if a single CEO owns everything):

   ```sql
   UPDATE projects SET owner_id = '<new-user-id>' WHERE owner_id IS NULL;
   ```

Until this step is done, pre-auth Companies are invisible to every CEO
account (Rule #15 — all data access is account-scoped; an unowned Company
matches no account's ownership check).

## 8. Operational limits

See `docs/KNOWN_ISSUES.md` for the full list of accepted tradeoffs and the
verified operating envelope (load smoke results, provider variance notes).
Read it before sizing a deployment or promising an SLA against it.
