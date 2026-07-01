"""initial

Revision ID: 001
Revises:
Create Date: 2026-06-30

Create the initial schema: users, chats, chat_members, messages, inbox_entries tables
plus the global_seq SEQUENCE.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Global sequence for monotonic message ordering
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS global_seq_seq AS BIGINT"))

    # users
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # chats
    op.create_table(
        "chats",
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_type", sa.String(16), nullable=False),
        sa.Column("group_name", sa.String(256), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_msg_at", sa.DateTime(timezone=True), nullable=True),
    )

    # chat_members
    op.create_table(
        "chat_members",
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.chat_id"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default=sa.text("'member'")),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # messages
    op.create_table(
        "messages",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.chat_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("client_msg_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column(
            "global_seq",
            sa.BigInteger(),
            sa.Sequence("global_seq_seq"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # inbox_entries
    op.create_table(
        "inbox_entries",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            primary_key=True,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.message_id"),
            primary_key=True,
        ),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.chat_id"),
            nullable=False,
        ),
        sa.Column("global_seq", sa.BigInteger(), nullable=False, index=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Composite index for efficient inbox range scans: WHERE user_id = X AND global_seq > Y
    op.create_index(
        "ix_inbox_entries_user_global_seq",
        "inbox_entries",
        ["user_id", "global_seq"],
    )


def downgrade() -> None:
    op.drop_table("inbox_entries")
    op.drop_table("messages")
    op.drop_table("chat_members")
    op.drop_table("chats")
    op.drop_table("users")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS global_seq_seq"))
