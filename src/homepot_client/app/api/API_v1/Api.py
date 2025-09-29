from fastapi import APIRouter
from .Endpoints import HealthEndpoint

api_v1_router = APIRouter()

api_v1_router.include_router(HealthEndpoint.router, prefix="/health", tags=["Health"])