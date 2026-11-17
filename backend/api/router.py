"""Root API router combining all sub-routers for API version 1."""

from fastapi import APIRouter
from backend.api.routes import (
    appointments,
    auth,
    chat,
    conversations,
    customers,
    health,
    knowledge,
    leads,
    messages,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(leads.router)
api_router.include_router(appointments.router)
api_router.include_router(knowledge.router)
api_router.include_router(chat.router)
