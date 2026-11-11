from fastapi import APIRouter

from nicto.adapters.api.v1.streams.routes import streams_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(streams_router)
