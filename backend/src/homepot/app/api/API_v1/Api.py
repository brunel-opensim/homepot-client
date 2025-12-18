"""API router managing for all Endpoints in the HomePot system."""

from fastapi import APIRouter

from .Endpoints import (
    AgentsEndpoints,
    AIEndpoint,
    AnalyticsEndpoint,
    ClientEndpoint,
    DevicesEndpoints,
    DeviceSimulatorEndpoint,
    HealthEndpoint,
    JobsEndpoints,
    PushNotificationEndpoint,
    SiteSchedulesEndpoint,
    SitesEndpoint,
    UIEndpoint,
    UserRegisterEndpoint,
)
from .Endpoints.Mobivisor import MobivisorDeviceEndpoints as MobivisorDevice
from .Endpoints.Mobivisor import MobivisorGroupsEndpoints as MobivisorGroupsEndpoints
from .Endpoints.Mobivisor import MobivisorUserEndpoints as MobivisorUserEndpoints

api_v1_router = APIRouter()

api_v1_router.include_router(HealthEndpoint.router, prefix="/health", tags=["Health"])
api_v1_router.include_router(
    HealthEndpoint.device_metrics_router, tags=["Health", "Device Metrics"]
)
api_v1_router.include_router(UIEndpoint.router, prefix="/ui", tags=["UI"])
api_v1_router.include_router(ClientEndpoint.router, prefix="/client", tags=["Client"])
api_v1_router.include_router(SitesEndpoint.router, prefix="/sites", tags=["Sites"])
api_v1_router.include_router(
    SiteSchedulesEndpoint.router, prefix="/sites", tags=["Site Schedules"]
)
api_v1_router.include_router(
    DevicesEndpoints.router, prefix="/devices", tags=["Devices"]
)
api_v1_router.include_router(JobsEndpoints.router, prefix="/jobs", tags=["Jobs"])
api_v1_router.include_router(AgentsEndpoints.router, prefix="/agents", tags=["Agents"])
api_v1_router.include_router(
    UserRegisterEndpoint.router, prefix="/auth", tags=["Authentication"]
)
api_v1_router.include_router(
    MobivisorDevice.router,
    prefix="/mobivisor",
    tags=["Mobivisor Devices"],
)
api_v1_router.include_router(
    MobivisorUserEndpoints.router,
    prefix="/mobivisor",
    tags=["Mobivisor Users"],
)
api_v1_router.include_router(
    MobivisorGroupsEndpoints.router,
    prefix="/mobivisor",
    tags=["Mobivisor Groups"],
)
api_v1_router.include_router(
    PushNotificationEndpoint.router, prefix="/push", tags=["Push Notifications"]
)
api_v1_router.include_router(
    DeviceSimulatorEndpoint.router, prefix="/testing", tags=["Testing"]
)
api_v1_router.include_router(AnalyticsEndpoint.router, tags=["Analytics"])
api_v1_router.include_router(
    AIEndpoint.router, prefix="/ai", tags=["AI & Machine Learning"]
)
