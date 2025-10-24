"""API router managing for all Endpoints in the HomePot system."""

from fastapi import APIRouter

from .Endpoints import (
    AgentsEndpoints,
    ClientEndpoint,
    DevicesEndpoints,
    HealthEndpoint,
    JobsEndpoints,
    PushNotificationEndpoint,
    SitesEndpoint,
    UIEndpoint,
    UserRegisterEndpoint,
)

api_v1_router = APIRouter()

api_v1_router.include_router(HealthEndpoint.router, prefix="/health", tags=["Health"])
api_v1_router.include_router(UIEndpoint.router, prefix="/ui", tags=["UI"])
api_v1_router.include_router(ClientEndpoint.router, prefix="/client", tags=["Client"])
api_v1_router.include_router(SitesEndpoint.router, prefix="/sites", tags=["Sites"])
api_v1_router.include_router(
    DevicesEndpoints.router, prefix="/devices", tags=["Devices"]
)
api_v1_router.include_router(JobsEndpoints.router, prefix="/jobs", tags=["Jobs"])
api_v1_router.include_router(AgentsEndpoints.router, prefix="/agents", tags=["Agents"])
api_v1_router.include_router(
    UserRegisterEndpoint.router, prefix="/auth", tags=["Authentication"]
)
api_v1_router.include_router(
    PushNotificationEndpoint.router, prefix="/push", tags=["Push Notifications"]
)
