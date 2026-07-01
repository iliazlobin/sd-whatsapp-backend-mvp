"""White-box test fixtures and helpers for the WhatsApp MVP.

These tests import the app package and talk to it in-process via
httpx.ASGITransport (functional) or call services directly (unit).

Uses SQLite in-memory for fast, isolated tests.
"""

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from whatsapp.models.base import Base

# Override database URL before any app imports
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = ""

# Monkey-patch the app's database module to use our test engine
import whatsapp.config  # noqa: E402
import whatsapp.database  # noqa: E402

whatsapp.config.settings.database_url = TEST_DATABASE_URL

# Create a shared async engine for all tests
_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
whatsapp.database.engine = _test_engine
whatsapp.database.async_session_factory = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)

# Create tables once
_tables_created = False


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once per test session."""
    global _tables_created
    if not _tables_created:

        async def _create():
            async with _test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(_create())
        _tables_created = True
    yield


@pytest.fixture
async def db_session(_create_tables):
    """Per-test DB session with transaction rollback for isolation."""
    async_session = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
def app():
    """Create a fresh FastAPI app instance for each test."""
    from whatsapp.main import create_app

    return create_app()


@pytest.fixture
async def async_client(app):
    """Async httpx client backed by ASGITransport (no real HTTP server)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
