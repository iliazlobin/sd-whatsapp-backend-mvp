# WhatsApp MVP — Engineering Spec

## 1. Goal & scope

Build the WhatsApp MVP — a real-time messaging backend that supports text message sending, offline inbox sync, group chats, delivery status, and WebSocket push. The MVP implements the core messaging experience from the full WhatsApp System Design.

**In scope**
- Send/receive text messages via REST API
- WebSocket real-time message push to online recipients
- Offline message delivery via global_seq-based inbox sync
- 1:1 direct chats and group chats (up to 256 members)
- Three-tier delivery status: sent, delivered, read
- Message deduplication (client_msg_id)
- User registration and contacts
- Paginated chat history

**Out of scope**
- Media/image/video/audio upload/download (S3/CDN)
- End-to-end encryption (Signal Protocol)
- Presence service (online/offline/last seen)
- Push notifications (APNs/FCM)
- Multi-device support
- Scale requirements (2B users, 100B msgs/day)
- Voice/video calling, payments

## 2. Functional requirements

- **FR-1 — Send text message.** `POST /v1/messages {chat_id, sender_id, content, client_msg_id}` → `201 {message_id, global_seq, status: "sent"}`. Missing field → `422`. Non-existent chat → `404`.
- **FR-2 — Inbox sync.** `GET /v1/inbox?user_id=<id>&since=<seq>&limit=<n>` → `200 {messages: [...], next_cursor: ...}`. Empty → `200 {messages: [], next_cursor: null}`. Invalid user → `404`.
- **FR-3 — Create direct chat.** `POST /v1/chats {type: "direct", member_ids: [u1, u2]}` → `201 {chat_id, type, ...}`. Duplicate → `200` existing chat. One member → `422`.
- **FR-4 — Create group chat.** `POST /v1/chats {type: "group", name, member_ids, created_by}` → `201 {chat_id, type, name, member_count, ...}`. Empty name → `422`. Over 256 members → `422`.
- **FR-5 — Delivery ACK.** `POST /v1/messages/{id}/ack {user_id, status: "delivered"|"read"}` → `200 {message_id, status}`. Re-ACK → `200` idempotent. Unknown message → `404`.
- **FR-6 — Message dedup.** Duplicate `client_msg_id` within 24h → `200 {message_id, global_seq, duplicate: true}`. After TTL → `201` new.
- **FR-7 — WebSocket push.** `WS /v1/ws?user_id=<id>` → receive `{"type": "new_message", "message": {...}}` on new messages. No user_id → `403`. Unknown user → `404`.
- **FR-8 — Chat history.** `GET /v1/chats/{id}/messages?limit=20&before=<cursor>` → `200 {messages: [...], next_cursor: ...}`. Non-member → `403`. Unknown chat → `404`.

## 3. Stack & deployment

- **Runtime:** Python 3.12, FastAPI (REST + WebSocket)
- **Datastore:** PostgreSQL (messages, chats, inboxes, users)
- **Cache:** Redis (WebSocket connection map, dedup cache)
- **Tests:** pytest (unit + functional + black-box acceptance)
- **Deploy:** Docker Compose (app + postgres + redis), port `${APP_PORT:-8010}:8000`

**Design →** [System Design: WhatsApp](https://app.notion.com/p/System-Design-WhatsApp-v2026-06-30-1-38ed865005a881289ecffc1afd8c10e2)

## 4. Data model

```sql
User {
  user_id:     uuid PK
  username:    text UNIQUE
  display_name:text
  created_at:  timestamp
}

Message {
  message_id:   uuid PK
  chat_id:      uuid FK → Chat
  sender_id:    uuid FK → User
  content:      text
  client_msg_id:uuid UNIQUE  ← sender-assigned dedup key
  created_at:   timestamp
}

InboxEntry {
  user_id:     uuid PK    ← partition key
  message_id:  uuid PK
  chat_id:     uuid
  global_seq:  bigint     ← global monotonic for reconnect sync
  status:      enum       ← pending | delivered | read
  created_at:  timestamp
}

Chat {
  chat_id:     uuid PK
  chat_type:   enum       ← direct | group
  group_name:  text?
  created_by:  uuid FK → User
  created_at:  timestamp
  last_msg_at: timestamp  ← denormalized for sort
}

ChatMember {
  chat_id:     uuid PK FK → Chat
  user_id:     uuid PK FK → User
  role:        enum       ← member | admin
  joined_at:   timestamp
}
```

## 5. API

- `POST /v1/users` — register a user; returns user_id
- `POST /v1/messages` — send a text message; returns message_id + global_seq
- `GET /v1/inbox?user_id=<uuid>&since=<global_seq>&limit=<n>` — sync pending messages
- `POST /v1/messages/{message_id}/ack` — acknowledge delivery/read
- `POST /v1/chats` — create direct or group chat; returns chat_id
- `GET /v1/chats?user_id=<uuid>` — list user's chats
- `GET /v1/chats/{chat_id}/messages?limit=20&before=<cursor>` — paginated chat history
- `GET /v1/users/{user_id}/contacts` — list user's contacts
- `POST /v1/users/{user_id}/contacts` — add a contact
- `WS /v1/ws?user_id=<uuid>` — persistent WebSocket for real-time message push
- `GET /healthz` — health check

## 6. Test scenarios

- **Idempotency:** Duplicate message send returns original; duplicate ACK is no-op
- **Ordering:** Inbox sync returns messages in global_seq order; chat history in reverse chronological
- **Pagination:** Chat history respects `limit` and `before` cursor; empty page returns `next_cursor: null`
- **Auth/ownership:** Non-member cannot read chat messages (403); unknown user cannot sync inbox (404)
- **Validation:** Missing required fields → 422; invalid chat type → 422; group over 256 members → 422
- **Error paths:** Non-existent chat → 404; non-existent message → 404; ACK for non-existent message → 404
- **Cross-entity:** Sending a message creates both Message row AND InboxEntries for all chat members
- **WebSocket:** Connected client receives push on new message; disconnected client gets messages on inbox sync

## 7. Module layout

```
src/whatsapp/
  __init__.py
  main.py              # FastAPI app factory + lifespan
  config.py            # pydantic-settings
  routers/
    __init__.py
    messages.py        # POST /v1/messages, POST /v1/messages/{id}/ack
    chats.py           # POST /v1/chats, GET /v1/chats, GET /v1/chats/{id}/messages
    users.py           # POST /v1/users, contacts
    inbox.py           # GET /v1/inbox
    websocket.py       # WS /v1/ws
    health.py          # GET /healthz
  services/
    __init__.py
    message_service.py
    chat_service.py
    inbox_service.py
    user_service.py
    dedup_service.py
    websocket_manager.py
  models/
    __init__.py
    user.py
    message.py
    inbox_entry.py
    chat.py
    chat_member.py
  schemas/
    __init__.py
    message.py
    chat.py
    user.py
    inbox.py
tests/
  unit/
  functional/
verify/
  acceptance/
    test_fr1_send_message.py
    test_fr2_inbox_sync.py
    test_fr3_create_direct_chat.py
    test_fr4_create_group_chat.py
    test_fr5_ack_message.py
    test_fr6_dedup_message.py
    test_fr7_websocket_push.py
    test_fr8_chat_history.py
  manifest.env
alembic/
docker-compose.yml
Dockerfile
pyproject.toml
```

## 8. Run

```bash
# Start the stack
docker compose up -d --build

# Verify health
curl -sf http://localhost:8010/healthz

# Run acceptance suite
API_BASE_URL=http://localhost:8010 pytest verify/acceptance/ -v

# Run all tests
pytest tests/ verify/acceptance/ -v

# Stop
docker compose down
```
