# WhatsApp MVP — Deploy Guide

## Prerequisites

- Docker Engine 24+ with Compose v2
- Python 3.12 (for local development)
- Git

## Quick Start

```bash
# Clone
git clone https://github.com/iliazlobin/sd-whatsapp-backend-mvp.git
cd sd-whatsapp-backend-mvp

# Start the stack
docker compose up -d --build

# Run migrations
docker compose run --rm -T app alembic upgrade head

# Verify
curl -sf http://localhost:8010/healthz
# → {"status":"ok"}
```

The slim runtime image has no `curl` — the compose healthcheck uses Python's `urllib` inside the container. On the host, `curl` works fine.

## Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://whatsapp:whatsapp@db:5432/whatsapp` | PostgreSQL async connection string (compose) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string (compose) |
| `APP_PORT` | `8010` | Host port for Docker Compose (container always listens on 8000) |

Override the host port:

```bash
APP_PORT=8020 docker compose up -d
```

## Stack

```
app (FastAPI + uvicorn) ── port 8000:${APP_PORT:-8010}
  │
  ├── db (PostgreSQL 16)
  └── redis (Redis 7)
```

Only `app` publishes a host port. `db` and `redis` communicate over the compose network.

## Healthcheck

The compose healthcheck (inside the container) uses Python's stdlib because the slim runtime has no `curl`:

```bash
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
```

On the host, check against the published port (default 8010):

```bash
curl -sf http://localhost:8010/healthz
# or
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8010/healthz')"
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness probe |
| `POST` | `/v1/users` | Register a user |
| `GET` | `/v1/users/{user_id}` | Get user info |
| `POST` | `/v1/messages` | Send a message |
| `POST` | `/v1/messages/{message_id}/ack` | Acknowledge delivery/read |
| `GET` | `/v1/inbox` | Sync inbox (cursor-based) |
| `POST` | `/v1/chats` | Create direct or group chat |
| `GET` | `/v1/chats` | List user's chats |
| `GET` | `/v1/chats/{chat_id}/messages` | Chat message history |
| `WS` | `/v1/ws` | WebSocket for real-time push |

## Run Tests

```bash
# Unit tests (no DB needed)
docker compose run --rm -T app pytest tests/unit/ -v

# Functional tests (needs DB + migrations)
docker compose up -d
docker compose run --rm -T app alembic upgrade head
docker compose run --rm -T app pytest tests/functional/ -v

# Acceptance tests (black-box, against live system)
docker compose up -d --build
docker compose run --rm -T app alembic upgrade head
API_BASE_URL=http://localhost:8000 python -m pytest verify/acceptance/ -v
```

## Teardown

```bash
docker compose down --volumes --remove-orphans
```

## CI/CD

GitHub Actions runs three workflows on every push and daily on schedule:

| Workflow | What | Gate |
|---|---|---|
| `lint.yml` | ruff check + format (v0.8.0) | hard |
| `ci.yml` | unit tests + e2e acceptance | hard |
| `functional.yml` | functional tests (own Postgres) | hard |
| Copilot Code Review | automated PR review | advisory |

Copilot Code Review is an advisory check — it comments on PRs but does not block merges.

## Local Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn whatsapp.main:app --host 0.0.0.0 --port 8000
```
