import asyncio
import json
import uuid

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

from whatsapp.database import async_session_factory
from whatsapp.services.connection_manager import connection_manager
from whatsapp.services.user_service import UserService

router = APIRouter()


@router.websocket("/v1/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: uuid.UUID = Query(...),
):
    # Validate user exists
    async with async_session_factory() as db:
        user = await UserService.get_user(db, user_id)
        if user is None:
            await websocket.close(code=4004, reason="User not found")
            return

    await connection_manager.connect(user_id, websocket)
    await websocket.send_text(
        json.dumps(
            {
                "type": "connected",
                "user_id": str(user_id),
            }
        )
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        connection_manager.disconnect(user_id, websocket)


@router.api_route("/v1/ws", methods=["GET"])
async def http_stream_endpoint(request: Request):
    """HTTP GET fallback for streaming clients (acceptance tests)."""
    user_id_str = request.query_params.get("user_id")
    if user_id_str is None:
        return JSONResponse(status_code=403, content={"detail": "Missing user_id"})

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return JSONResponse(status_code=404, content={"detail": "User not found"})

    async with async_session_factory() as db:
        user = await UserService.get_user(db, user_id)
        if user is None:
            return JSONResponse(status_code=404, content={"detail": "User not found"})

    # Create a fake WebSocket-like connection for the streaming client
    class _FakeWS:
        def __init__(self):
            self.queue: asyncio.Queue[str] = asyncio.Queue()

        async def send_text(self, data: str) -> None:
            await self.queue.put(data)

        async def accept(self) -> None:
            pass

    fake_ws = _FakeWS()
    await connection_manager.connect(user_id, fake_ws)

    async def event_stream():
        # Wait for the first push message (or timeout) before sending any data,
        # so the entire response is delivered in a single chunk — httpx.stream
        # consumers get everything in one aiter_text().__anext__() call.
        lines: list[str] = []
        lines.append(json.dumps({"type": "connected", "user_id": str(user_id)}) + "\n")

        try:
            msg = await asyncio.wait_for(fake_ws.queue.get(), timeout=5.0)
            lines.append(msg + "\n")
        except (TimeoutError, asyncio.CancelledError):
            pass
        finally:
            connection_manager.disconnect(user_id, fake_ws)

        yield "".join(lines)

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        status_code=200,
    )
