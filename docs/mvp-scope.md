# WhatsApp MVP — Scope & Acceptance Criteria

## Stack
- **Language:** Python 3.12
- **Framework:** FastAPI (REST + WebSocket)
- **Datastore:** PostgreSQL (messages, chats, inbox, users)
- **Cache:** Redis (WebSocket connection map, dedup cache)
- **Test runner:** pytest (unit + functional + black-box acceptance)
- **Infra:** Docker Compose (app + postgres + redis)

## Scope IN
- FR1: Send and receive text messages via REST + WebSocket push
- FR2: Offline message delivery with inbox sync (global_seq-based range scan)
- FR3: Create 1:1 and group chats, list user's chats
- FR4: Delivery status — sent/delivered/read transitions
- FR5: Message deduplication (client_msg_id)
- FR6: User registration and contact list
- FR7: WebSocket real-time message push to online recipients
- FR8: Paginated chat history

## Scope OUT
- Media/image/video/audio upload and download (requires S3/CDN)
- End-to-end encryption (Signal Protocol, X3DH, Double Ratchet)
- Presence service (online/offline/last seen)
- Push notifications (APNs/FCM)
- Multi-device support
- Scale requirements (2B users, 100B msgs/day)
- Voice/video calling, status/stories, payments, business API

## Functional Requirements

### FR-1 — Send a text message
Send a text message to a chat. The server persists the Message and creates one InboxEntry per recipient, assigns a global_seq, and returns the message_id.

**Acceptance:** `POST /v1/messages` with `{chat_id, sender_id, content, client_msg_id}` → `201` with `{message_id, global_seq, status: "sent"}`. Missing field → `422`. Non-existent chat → `404`.

### FR-2 — Inbox sync (offline delivery)
Retrieve all messages since the last acknowledged global_seq. Supports efficient reconnect: a single-partition range scan returns pending messages in order.

**Acceptance:** `GET /v1/inbox?user_id=<uuid>&since=<global_seq>&limit=<n>` → `200` with `{messages: [{message_id, chat_id, sender_id, content, global_seq, status, created_at}], next_cursor: <seq>}`. Empty inbox → `200` with `{messages: [], next_cursor: null}`. Invalid user → `404`.

### FR-3 — Create a direct (1:1) chat
Create a 1:1 chat between two users. If a chat already exists between them, return the existing one (idempotent).

**Acceptance:** `POST /v1/chats` with `{type: "direct", member_ids: [u1, u2]}` → `201` with `{chat_id, type, members, created_at}`. Duplicate → `200` with existing chat. Only one member → `422`.

### FR-4 — Create a group chat
Create a group chat with a name and member list. The creator is auto-added as admin. Supports up to 256 members for MVP.

**Acceptance:** `POST /v1/chats` with `{type: "group", name: "Study Group", member_ids: [u1,u2,u3], created_by: <uuid>}` → `201` with `{chat_id, type, name, member_count, created_at}`. Empty name → `422`. >256 members → `422`.

### FR-5 — Delivery acknowledgement (ACK)
Recipient acknowledges message delivery. Updates the InboxEntry status from `pending` → `delivered` (or `read` for read receipts). Idempotent — re-ACK is a no-op (200, no state change).

**Acceptance:** `POST /v1/messages/{message_id}/ack` with `{user_id, status: "delivered"|"read"}` → `200` with `{message_id, status}`. Already acknowledged → `200` (idempotent). Non-existent message → `404`. Unknown user → `404`.

### FR-6 — Message deduplication
If the sender retries a send with the same `client_msg_id`, the server returns the original message_id and global_seq without creating a duplicate.

**Acceptance:** `POST /v1/messages` with duplicate `client_msg_id` within 24h → `200` with `{message_id, global_seq, status, duplicate: true}`. After 24h TTL → `201` (new message).

### FR-7 — Real-time message push via WebSocket
Connected clients receive new messages pushed over WebSocket in real time. The WebSocket endpoint accepts a user_id query param and pushes message envelopes as JSON frames.

**Acceptance:** Connect `WS /v1/ws?user_id=<uuid>` → receive `{"type": "new_message", "message": {...}}` when another user sends a message to a chat this user is a member of. No auth → `403`. Unknown user → `404`.

### FR-8 — Get chat history
Retrieve paginated message history for a chat, ordered by created_at descending (newest first). Supports cursor-based pagination.

**Acceptance:** `GET /v1/chats/{chat_id}/messages?limit=20` → `200` with `{messages: [...], next_cursor: <id>}`. `GET /v1/chats/{chat_id}/messages?limit=20&before=<message_id>` → `200` with next page. Non-member → `403`. Non-existent chat → `404`.

## Data Model (MVP subset)

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
  client_msg_id:uuid UNIQUE
  created_at:   timestamp
}

InboxEntry {
  user_id:     uuid PK   ← partition key
  message_id:  uuid PK
  chat_id:     uuid
  global_seq:  bigint
  status:      enum      ← pending | delivered | read
  created_at:  timestamp
}

Chat {
  chat_id:     uuid PK
  chat_type:   enum      ← direct | group
  group_name:  text?
  created_by:  uuid FK → User
  created_at:  timestamp
  last_msg_at: timestamp
}

ChatMember {
  chat_id:     uuid PK FK → Chat
  user_id:     uuid PK FK → User
  role:        enum      ← member | admin
  joined_at:   timestamp
}
```

## Build Plan

See KICKOFF.md for the full kanban chain. Summary:

1. **Architect** — design.md + `verify/acceptance/` black-box suite (8 cases, one per FR)
2. **Senior Engineer** — scaffold: repo layout, deps, config, compose, schema, health endpoint
3. **Staff Engineer** — implement FRs until all acceptance cases pass + unit + functional tests + ruff clean
4. **Verifier** — gate: all three test layers green + ruff clean
5. **SRE** — DEPLOY.md, .env.example, `verify/manifest.env`, CI/CD workflows, Docker verification
6. **Writer** — README.md, DESIGN.md, cleanup build harness
