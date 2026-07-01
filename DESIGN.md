# WhatsApp MVP — Design & Implementation

An MVP messaging backend that implements the core WhatsApp messaging loop. One FastAPI process serves REST endpoints and WebSocket connections backed by PostgreSQL for durable message storage and Redis for deduplication caching. The MVP covers 1:1 direct chats, group chats up to 256 members, and the full send→persist→inbox→sync→ack lifecycle, minus end-to-end encryption, media, presence, and multi-server scaling.

The broader target — the full WhatsApp System Design — scales this to 2 billion users exchanging 100 billion messages daily with end-to-end Signal Protocol encryption, Cassandra-backed inboxes, Redis Pub/Sub cross-server routing, CDN-backed media delivery, and a presence service. This MVP implements the messaging spine that everything else attaches to.

## Architecture

```mermaid
graph TB
    subgraph api["FastAPI App — port 8000"]
        R_MSGS[Messages Router<br/>POST /v1/messages<br/>POST /v1/messages/{id}/ack]
        R_INBOX[Inbox Router<br/>GET /v1/inbox]
        R_CHATS[Chats Router<br/>POST /v1/chats<br/>GET /v1/chats<br/>GET /v1/chats/{id}/messages]
        R_USERS[Users Router<br/>POST /v1/users<br/>GET /v1/users/{id}]
        WS[WebSocket<br/>WS /v1/ws]
    end

    subgraph services["Service Layer"]
        MS[MessageService<br/>send, dedup, fan-out]
        IS[InboxService<br/>sync, ack]
        CS[ChatService<br/>create, list, history]
        US[UserService<br/>create, get]
        CM[ConnectionManager<br/>in-memory dict]
    end

    subgraph data["Data Layer"]
        PG[(PostgreSQL 16<br/>messages, chats,<br/>inbox_entries, users)]
        RD[(Redis 7<br/>dedup cache<br/>TTL 24h)]
    end

    R_MSGS --> MS
    R_INBOX --> IS
    R_CHATS --> CS
    R_USERS --> US
    WS --> CM
    MS --> CM
    MS --> PG
    MS --> RD
    IS --> PG
    CS --> PG
    US --> PG

    classDef edge fill:#fff3bf,stroke:#f08c00,color:#1a1a1a
    classDef svc fill:#d0ebff,stroke:#1c7ed6,color:#1a1a1a
    classDef store fill:#d3f9d8,stroke:#2f9e44,color:#1a1a1a
    classDef rt fill:#ffe8cc,stroke:#e8590c,color:#1a1a1a

    class R_MSGS,R_INBOX,R_CHATS,R_USERS svc
    class MS,IS,CS,US svc
    class WS,CM rt
    class PG,RD store
```

Routers parse HTTP, validate with Pydantic, and delegate to services — no business logic. Services own the domain logic and data access. The Connection Manager is an in-memory `dict[user_id, set[WebSocket]]` for the single-server MVP. Redis is used only for the dedup cache (`client_msg_id` → `message_id`, TTL 24h).

## Scope

### In scope

- Send and receive text messages via REST
- WebSocket real-time push to online recipients
- Offline message delivery via `global_seq`-based inbox sync
- 1:1 direct chats and group chats (up to 256 members)
- Three-tier delivery status: sent, delivered, read
- Message deduplication by `client_msg_id`
- User registration and contacts
- Paginated chat history (cursor-based, newest first)

### Out of scope

- Media upload/download (requires S3/CDN)
- End-to-end encryption (Signal Protocol)
- Presence service (online/offline/last seen)
- Push notifications (APNs/FCM)
- Multi-device support
- Scale requirements (2B users, 100B msgs/day)
- Voice/video calling, payments, business API

## Functional Requirements

- **FR-1 — Send text message.** `POST /v1/messages {chat_id, sender_id, content, client_msg_id}` → `201 {message_id, global_seq, status: "sent"}`. Missing field → `422`. Non-existent chat → `404`.
- **FR-2 — Inbox sync.** `GET /v1/inbox?user_id=<id>&since=<seq>&limit=<n>` → `200 {messages: [...], next_cursor: ...}`. Empty → `200 {messages: [], next_cursor: null}`. Invalid user → `404`.
- **FR-3 — Create direct chat.** `POST /v1/chats {type: "direct", member_ids: [u1, u2]}` → `201 {chat_id, type, ...}`. Duplicate → `200` existing chat. One member → `422`.
- **FR-4 — Create group chat.** `POST /v1/chats {type: "group", name, member_ids, created_by}` → `201 {chat_id, type, name, member_count, ...}`. Empty name → `422`. Over 256 members → `422`.
- **FR-5 — Delivery ACK.** `POST /v1/messages/{id}/ack {user_id, status: "delivered"|"read"}` → `200 {message_id, status}`. Re-ACK → `200` idempotent. Status transitions are monotonic: `pending → delivered → read`. Unknown message → `404`.
- **FR-6 — Message dedup.** Duplicate `client_msg_id` within 24h → `200 {message_id, global_seq, duplicate: true}`. After TTL → `201` new.
- **FR-7 — WebSocket push.** `WS /v1/ws?user_id=<id>` → receive `{"type": "new_message", "message": {...}}` on new messages. No user_id → `403`. Unknown user → `404`.
- **FR-8 — Chat history.** `GET /v1/chats/{id}/messages?limit=20&before=<cursor>` → `200 {messages: [...], next_cursor: ...}`. Non-member → `403`. Unknown chat → `404`.

### Supporting endpoints (not FR-gated, exercised by acceptance test setup)

- `POST /v1/users` — register a user → `201`. Username conflict → `409`.
- `GET /v1/users/{user_id}` — get user profile → `200`. Not found → `404`.
- `POST /v1/users/{user_id}/contacts` — add a contact.
- `GET /v1/users/{user_id}/contacts` — list contacts.

## Data Model

```sql
User {
  user_id:      uuid PK
  username:     text UNIQUE
  display_name: text
  created_at:   timestamp
}

Message {
  message_id:    uuid PK
  chat_id:       uuid FK → Chat       ← partition key for chat history
  sender_id:     uuid FK → User
  content:       text
  client_msg_id: uuid UNIQUE          ← sender-assigned dedup key
  global_seq:    bigint UNIQUE        ← server-assigned monotonic (Postgres SEQUENCE)
  created_at:    timestamp
}

InboxEntry {
  user_id:     uuid PK                ← partition key for inbox sync
  message_id:  uuid PK FK → Message
  chat_id:     uuid FK → Chat         ← denormalized for efficient range scan
  global_seq:  bigint                 ← denormalized for WHERE global_seq > X ORDER BY
  status:      enum                   ← pending | delivered | read
  created_at:  timestamp
}

Chat {
  chat_id:     uuid PK
  chat_type:   enum                   ← direct | group
  group_name:  text?                  ← null for direct chats
  created_by:  uuid FK → User
  created_at:  timestamp
  last_msg_at: timestamp              ← denormalized for chat list sort
}

ChatMember {
  chat_id:     uuid PK FK → Chat
  user_id:     uuid PK FK → User
  role:        enum                   ← member | admin
  joined_at:   timestamp
}
```

### Key schema decisions

- `global_seq` is a Postgres `BIGSERIAL` — a single-sequence monotonic counter. The full design uses Snowflake-style distributed IDs; MVP collapses to a database sequence. Numeric range scans (`WHERE global_seq > X`) are optimal for inbox sync.
- `InboxEntry` duplicates `chat_id` and `global_seq` — denormalized so inbox sync is a single-table range scan without a JOIN to Message. Matches the full design's Cassandra data model approach.
- `client_msg_id UNIQUE` on Message — database-level dedup guarantee. Redis provides a faster check before hitting the DB.
- Direct chat canonical ordering — for 1:1 chats, the server sorts `member_ids` to derive a canonical pair. Two users always get the same `chat_id`.
- No `ChatMember` rows for direct chats — membership is implicit from the two user IDs passed at creation. Only group chats populate `chat_members`.

## Key Design Decisions

### D1: In-memory WebSocket map vs. Redis Pub/Sub

**Decision:** In-memory `dict[user_id, set[WebSocket]]`.

A single FastAPI process can handle thousands of concurrent WebSocket connections via `asyncio`. The full design introduces Redis Pub/Sub to route messages across Chat Server instances — unnecessary at MVP scale with one instance. The Connection Manager interface (`connect`/`disconnect`/`send_to_user`) is the same regardless of backend, so swapping to Redis Pub/Sub later changes only one module.

### D2: Dedup via Redis cache + DB UNIQUE vs. DB-only

**Decision:** Redis cache (24h TTL, `dedup:{client_msg_id}` → `message_id`) as fast path + Postgres UNIQUE on `client_msg_id` as safety net.

WhatsApp production uses a short-lived dedup cache in front of the durable store. The Redis path avoids a DB round-trip on retries; the UNIQUE constraint catches any cache miss. The 24h TTL implements FR-6's dedup window.

### D3: `global_seq` as Postgres SEQUENCE vs. UUID ordering

**Decision:** `BIGSERIAL` — numeric monotonic counter.

Numeric sequences are compact (8 bytes), naturally sortable, and make range scans trivial for the query planner. A Postgres SEQUENCE handles ~50K-100K increments/sec — orders of magnitude above MVP needs. The full design's distributed Snowflake IDs solve a cluster-wide ordering problem the MVP doesn't have.

### D4: Direct chat canonical ordering vs. symmetric double-lookup

**Decision:** Server normalizes member pair by sorting user IDs.

One canonical chat per pair. WhatsApp's production model derives `chat_id` from sorted participant IDs. Prevents "two chats with the same two people" at the data model level. The `chat_members` table has exactly 2 rows, not 4.

### D5: Denormalized `global_seq` and `chat_id` on InboxEntry vs. JOIN-only

**Decision:** `InboxEntry` carries `chat_id` and `global_seq` directly.

The inbox sync query (`WHERE user_id = X AND global_seq > Y ORDER BY global_seq`) is the most performance-sensitive query — it runs on every reconnect. Denormalization makes it a single-partition range scan. Matches the full design's Cassandra data model.

### D6: User registration as supporting endpoint, not a gated FR

**Decision:** `POST /v1/users` has a documented API contract but no dedicated acceptance test file.

The eight gated functional requirements (FR-1 through FR-8) are the acceptance contract. User creation is exercised by every test's setup — if it's broken, every test fails, which is the correct signal.

## Service Layer Design

### MessageService — send message

1. Check Redis `dedup:{client_msg_id}` — if found, return cached result (200 duplicate).
2. Validate chat exists and sender is a member (403 if not).
3. Acquire `nextval('global_seq')` from Postgres SEQUENCE.
4. INSERT Message row. On UNIQUE violation on `client_msg_id`, query the existing message and return 200 duplicate.
5. Fan-out: for each recipient (all chat members except sender), INSERT one `InboxEntry` with `status = "pending"`.
6. Cache `dedup:{client_msg_id}` → `message_id` in Redis with 24h TTL.
7. Push to online recipients via Connection Manager.
8. Update `chats.last_msg_at`. Commit. Return 201.

### InboxService — sync + ack

**Sync:** `SELECT ie.*, m.content, m.sender_id FROM inbox_entries ie JOIN messages m ON ie.message_id = m.message_id WHERE ie.user_id = ? AND ie.global_seq > ? ORDER BY ie.global_seq ASC LIMIT ? + 1`. If results exceed limit, set `next_cursor` to the last `global_seq`; otherwise `null`.

**ACK:** Validate message and InboxEntry exist (404 if not). Status is monotonic: `pending → delivered → read`. Re-ACK with same or lower status returns the current (higher) status. Once `read`, never regresses.

### ChatService — create, list, history

**Direct chat:** Sort member pair → canonical. Query existing chat with both members. If found → 200 idempotent. Else → INSERT Chat + 2 ChatMember rows → 201.

**Group chat:** Validate 2-256 members, name non-empty, `created_by` in member list. INSERT Chat + ChatMember rows (`created_by` as admin) → 201.

**History:** `SELECT * FROM messages WHERE chat_id = ? [AND message_id < ?] ORDER BY created_at DESC LIMIT ? + 1`. Cursor-based pagination; `next_cursor` is the oldest `message_id` in the batch.

### Connection Manager

In-memory `dict[UUID, set[WebSocket]]`. On connect, register the WebSocket. On disconnect, remove it. `send_to_user` iterates the set and pushes JSON. Dead connections are caught by `WebSocketDisconnect` and auto-removed.

## Test Results

The functional test suite (`tests/functional/`) validates behavior scenarios from the spec (§6) against a live database. The CI pipeline runs these with service-container Postgres on every push and PR.

| Spec §6 Scenario | What It Validates | Functional Test | CI Workflow |
|---|---|---|---|
| Idempotency | Duplicate message send returns original; duplicate ACK is no-op | `tests/functional/test_messages.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |
| Ordering | Inbox sync returns messages in `global_seq` order; chat history in reverse chronological | `tests/functional/test_inbox.py`, `tests/functional/test_chats.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |
| Pagination | Chat history respects `limit` and `before` cursor; empty page returns `next_cursor: null` | `tests/functional/test_chats.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |
| Auth/ownership | Non-member cannot read chat messages (403); unknown user cannot sync inbox (404) | `tests/functional/test_chats.py`, `tests/functional/test_inbox.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |
| Validation | Missing fields → 422; invalid chat type → 422; group over 256 members → 422 | `tests/functional/test_chats.py`, `tests/functional/test_messages.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |
| Error paths | Non-existent chat → 404; non-existent message → 404; ACK for unknown message → 404 | `tests/functional/test_messages.py`, `tests/functional/test_chats.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |
| Cross-entity | Sending a message creates both a Message row AND InboxEntries for all chat members | `tests/functional/test_messages.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |
| WebSocket | Connected client receives push on new message; disconnected client gets messages on inbox sync | `tests/functional/test_websocket.py` | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |

### CI Pipeline

| Workflow | Trigger | What It Runs | Status |
|---|---|---|---|
| [Lint](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/lint.yml) | push, PR, daily | `ruff check` + `ruff format --check` | [![Lint](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/lint.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/lint.yml) |
| [CI](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/ci.yml) | push, PR, daily | unit tests + Docker Compose stack + acceptance suite | [![CI](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/ci.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/ci.yml) |
| [Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) | push, PR, daily | functional tests (own Postgres service container) | [![Functional](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-whatsapp-backend-mvp/actions/workflows/functional.yml) |

The acceptance suite (`verify/acceptance/`) runs as a black-box e2e check against a Docker Compose stack in CI.
