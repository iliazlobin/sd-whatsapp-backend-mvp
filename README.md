# WhatsApp MVP

[![Lint](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/lint.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/lint.yml)
[![CI](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/ci.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/ci.yml)
[![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml)

A real-time messaging backend implementing the core WhatsApp loop: send text messages, sync inboxes offline with a monotonic global sequence, push live messages over WebSocket, and track three-tier delivery status — sent, delivered, read. This MVP covers 1:1 direct chats and group chats up to 256 members with message deduplication, cursor-based chat history, and a connection manager for real-time push.

Built to the WhatsApp System Design specification as a focused MVP — no end-to-end encryption, media, presence, or multi-server scaling.

## Quickstart

Requires Docker and Docker Compose v2.

```bash
git clone https://github.com/iliazlobin/sd-whatsapp-backend-mvp.git
cd sd-whatsapp-backend-mvp

# Start the stack
docker compose up -d --build

# Run migrations
docker compose run --rm app alembic upgrade head

# Verify
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8010/healthz')"
# → {"status":"ok"}
```

The runtime image is `python:3.12-slim` (no `curl`). Use Python's `urllib` for the health check, or override the host port:

```bash
APP_PORT=8020 docker compose up -d
```

## Architecture

```
Client (HTTP/WebSocket)
       │
       ▼
┌─────────────────────────────┐
│   FastAPI (uvicorn :8000)   │
│  ┌───────────────────────┐  │
│  │ Routers (thin HTTP)   │  │
│  │ /v1/messages, /inbox, │  │
│  │ /chats, /users, /ws   │  │
│  └──────────┬────────────┘  │
│  ┌──────────▼────────────┐  │
│  │ Service Layer         │  │
│  │ MessageService ·      │  │
│  │ InboxService ·        │  │
│  │ ChatService ·         │  │
│  │ UserService ·         │  │
│  │ ConnectionManager     │  │
│  └──────────┬────────────┘  │
└─────────────┼───────────────┘
       ┌──────┴──────┐
       ▼              ▼
┌──────────┐  ┌─────────────┐
│PostgreSQL│  │   Redis 7   │
│   16     │  │ (dedup TTL  │
│messages, │  │  24h cache) │
│chats,    │  └─────────────┘
│inbox,    │
│users     │
└──────────┘
```

- **Routers** parse HTTP, validate with Pydantic, and delegate to services. No business logic.
- **Services** own the business logic: message persistence with deduplication, inbox fan-out per recipient, WebSocket push to online users, global_seq assignment from a Postgres SEQUENCE.
- **Connection Manager** is an in-memory `dict[user_id, set[WebSocket]]` — sufficient for the single-server MVP. Swappable to Redis Pub/Sub for horizontal scaling.

## API

- `GET /healthz` — liveness probe
- `POST /v1/users` — register a user
- `GET /v1/users/{user_id}` — get user profile
- `POST /v1/messages` — send a text message; returns `message_id` + `global_seq` + `status`
- `POST /v1/messages/{message_id}/ack` — acknowledge delivery or read (idempotent)
- `GET /v1/inbox?user_id=<uuid>&since=<seq>&limit=<n>` — sync pending messages since last acknowledged global_seq
- `POST /v1/chats` — create a direct or group chat; direct chat creation is idempotent
- `GET /v1/chats?user_id=<uuid>` — list a user's chats, newest activity first
- `GET /v1/chats/{chat_id}/messages?limit=20&before=<cursor>` — paginated chat history (newest first)
- `WS /v1/ws?user_id=<uuid>` — persistent WebSocket for real-time message push

### Example: send a message

```bash
curl -s -X POST http://localhost:8010/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"<chat-uuid>","sender_id":"<user-uuid>","content":"hello","client_msg_id":"<unique-uuid>"}'
```

```json
{"message_id":"550e8400-e29b-41d4-a716-446655440000","global_seq":42,"status":"sent","duplicate":false}
```

### Example: inbox sync

```bash
curl -s "http://localhost:8010/v1/inbox?user_id=<uuid>&since=0&limit=50"
```

```json
{"messages":[],"next_cursor":null}
```

## Data Model

| Entity | Purpose | Key Columns |
|---|---|---|
| `users` | Registered users | `user_id` (UUID PK), `username` (UNIQUE), `display_name` |
| `messages` | Every sent message | `message_id` (UUID PK), `chat_id` (FK), `sender_id` (FK), `content`, `client_msg_id` (UNIQUE, dedup), `global_seq` (BIGSERIAL, monotonic) |
| `inbox_entries` | One row per recipient per message — the delivery table | `(user_id, message_id)` composite PK, `global_seq` (denormalized for range scan), `status` (pending/delivered/read), `chat_id` (denormalized) |
| `chats` | Direct and group conversations | `chat_id` (UUID PK), `chat_type` (direct/group), `group_name`, `last_msg_at` (denormalized) |
| `chat_members` | Membership + roles | `(chat_id, user_id)` composite PK, `role` (member/admin) |

The inbox sync query is the primary read path: `WHERE user_id = X AND global_seq > Y ORDER BY global_seq ASC` — a single-partition range scan enabled by denormalizing `global_seq` onto `inbox_entries`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://whatsapp:whatsapp@db:5432/whatsapp` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `APP_PORT` | `8010` | Host port for the `app` service |

Copy `.env.example` to `.env` and adjust for local development.

## Development

```bash
# Install dev dependencies
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start the app
uvicorn whatsapp.main:app --host 0.0.0.0 --port 8000
```

```bash
# Unit tests (no external services)
pytest tests/unit/ -v

# Functional tests (requires Postgres)
DATABASE_URL=postgresql+asyncpg://whatsapp:whatsapp@localhost:5432/whatsapp \
  pytest tests/functional/ -v

# Acceptance tests (black-box, against running system)
API_BASE_URL=http://localhost:8000 pytest verify/acceptance/ -v

# Lint
ruff check src/ tests/ && ruff format --check src/ tests/
```

## CI

| Workflow | Trigger | What it runs |
|---|---|---|
| [Lint](.github/workflows/lint.yml) | push, PR, daily | `ruff check` + `ruff format --check` |
| [CI](.github/workflows/ci.yml) | push, PR, daily | unit tests + Docker Compose stack + acceptance suite |
| [Functional](.github/workflows/functional.yml) | push, PR, daily | functional tests against a service-container Postgres |

## Project Layout

```
.
├── src/whatsapp/           # Application package
│   ├── main.py             # App factory + lifespan + healthz
│   ├── config.py           # pydantic-settings
│   ├── database.py         # SQLAlchemy async engine
│   ├── redis.py            # Redis client factory
│   ├── models/             # SQLAlchemy ORM (user, message, chat, inbox_entry, chat_member)
│   ├── schemas/            # Pydantic request/response DTOs
│   ├── routers/            # Thin HTTP handlers (messages, chats, users, inbox, websocket)
│   └── services/           # Business logic (message_service, inbox_service, chat_service, user_service, connection_manager)
├── tests/
│   ├── unit/               # Isolated service/model tests
│   └── functional/         # In-process ASGITransport integration tests
├── verify/
│   ├── acceptance/         # Black-box HTTP tests (one per functional requirement)
│   └── manifest.env        # acceptance test configuration
├── alembic/                # Database migrations
├── docker-compose.yml      # Local stack (app + postgres + redis)
├── Dockerfile              # Multi-stage python:3.12-slim
├── pyproject.toml          # Dependencies and tool config
└── SPEC.md                 # Engineering spec (canonical source of truth)
```
