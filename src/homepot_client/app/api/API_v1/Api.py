from fastapi import APIRouter
from .Endpoints import HealthEndpoint, UIEndpoint, ClientEndpoint, SitesEndpoint, DevicesEndpoints, JobsEndpoints

api_v1_router = APIRouter()

api_v1_router.include_router(HealthEndpoint.router, prefix="/health", tags=["Health"])
api_v1_router.include_router(UIEndpoint.router, prefix="/ui", tags=["UI"])
api_v1_router.include_router(ClientEndpoint.router, prefix="/client", tags=["Client"])
api_v1_router.include_router(SitesEndpoint.router, prefix="/sites", tags=["Sites"])
api_v1_router.include_router(DevicesEndpoints.router, prefix="/devices", tags=["Devices"])
api_v1_router.include_router(JobsEndpoints.router, prefix="/jobs", tags=["Jobs"])