from fastapi import APIRouter

from app.routers import account, admin, auth, avatars, chat, health, schedule

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(avatars.router, tags=["avatars"])
api_router.include_router(schedule.router, prefix="/schedule", tags=["schedule"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
