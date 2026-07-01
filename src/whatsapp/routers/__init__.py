from whatsapp.routers.chats import router as chats_router
from whatsapp.routers.inbox import router as inbox_router
from whatsapp.routers.messages import router as messages_router
from whatsapp.routers.users import router as users_router
from whatsapp.routers.ws import router as ws_router

routers = [users_router, messages_router, inbox_router, chats_router, ws_router]

__all__ = ["routers"]
