"""Tests for the /healthz endpoint."""

import pytest


@pytest.mark.asyncio
async def test_healthz(async_client):
    """GET /healthz returns 200 with {"status": "ok"}."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok"}
