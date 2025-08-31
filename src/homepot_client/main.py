"""
HOMEPOT Client FastAPI Application.

This module provides the main FastAPI application for the HOMEPOT client,
exposing REST API endpoints for device management and monitoring.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from homepot_client.client import HomepotClient
from homepot_client.database import get_database_service, close_database_service
from homepot_client.orchestrator import get_job_orchestrator, stop_job_orchestrator
from homepot_client.agents import get_agent_manager, stop_agent_manager
from homepot_client.models import DeviceType, JobPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global client instance
client_instance: Optional[HomepotClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events."""
    global client_instance

    # Startup
    logger.info("Starting HOMEPOT Client application...")
    
    # Initialize database
    try:
        db_service = await get_database_service()
        logger.info("Database service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Initialize job orchestrator
    try:
        orchestrator = await get_job_orchestrator()
        logger.info("Job orchestrator initialized")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        raise
    
    # Initialize agent manager (Phase 3)
    try:
        agent_manager = await get_agent_manager()
        logger.info("Agent manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize agent manager: {e}")
        raise
    
    # Initialize client
    client_instance = HomepotClient()
    try:
        await client_instance.connect()
        logger.info("HOMEPOT Client connected successfully")
    except Exception as e:
        logger.warning(f"Failed to connect client on startup: {e}")

    yield

    # Shutdown
    logger.info("Shutting down HOMEPOT Client application...")
    
    # Shutdown agent manager
    try:
        await stop_agent_manager()
        logger.info("Agent manager stopped")
    except Exception as e:
        logger.error(f"Error stopping agent manager: {e}")
    
    # Shutdown orchestrator
    try:
        await stop_job_orchestrator()
        logger.info("Job orchestrator stopped")
    except Exception as e:
        logger.error(f"Error stopping orchestrator: {e}")
    
    # Shutdown database
    try:
        await close_database_service()
        logger.info("Database service closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")
    
    # Disconnect client
    if client_instance and client_instance.is_connected():
        await client_instance.disconnect()
        logger.info("HOMEPOT Client disconnected")


# Pydantic models for API requests/responses
class CreateJobRequest(BaseModel):
    """Request model for creating a new job."""
    action: str = "Update POS payment config"
    description: Optional[str] = None
    config_url: Optional[str] = None
    config_version: Optional[str] = None
    priority: str = JobPriority.HIGH
    
    class Config:
        schema_extra = {
            "example": {
                "action": "Update POS payment config",
                "description": "Fix payment gateway configuration for site-123",
                "priority": "high"
            }
        }


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    action: str
    status: str
    priority: str
    site_id: Optional[str] = None
    segment: Optional[str] = None
    config_url: Optional[str] = None
    config_version: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error_message: Optional[str] = None


class SiteHealthResponse(BaseModel):
    """Response model for site health status."""
    site_id: str
    total_devices: int
    healthy_devices: int
    offline_devices: int
    error_devices: int
    health_percentage: float
    status_summary: str
    devices: List[Dict]
    last_updated: str


class CreateSiteRequest(BaseModel):
    """Request model for creating a new site."""
    site_id: str
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "site_id": "site-123",
                "name": "Main Retail Store",
                "description": "Primary retail location with 5 POS terminals",
                "location": "London, UK"
            }
        }


class CreateDeviceRequest(BaseModel):
    """Request model for creating a new device."""
    device_id: str
    name: str
    device_type: str = DeviceType.POS_TERMINAL
    ip_address: Optional[str] = None
    config: Optional[Dict] = None
    
    class Config:
        schema_extra = {
            "example": {
                "device_id": "pos-terminal-001",
                "name": "POS Terminal 1",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.10",
                "config": {"gateway_url": "https://payments.example.com"}
            }
        }


# Create FastAPI application
app = FastAPI(
    title="HOMEPOT Client API",
    description="REST API for HOMEPOT device management and monitoring",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance


@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """Root endpoint providing basic information."""
    return {
        "message": "HOMEPOT Client API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "operational",
    }


@app.get("/health", tags=["Health"])
async def health_check(client: HomepotClient = Depends(get_client)) -> Dict[str, Any]:
    """Health check endpoint for monitoring and load balancers."""
    try:
        is_connected = client.is_connected()
        version = client.get_version()

        return {
            "status": "healthy" if is_connected else "degraded",
            "client_connected": is_connected,
            "version": version,
            "timestamp": asyncio.get_event_loop().time(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time(),
        }


@app.get("/status", tags=["Client"])
async def get_status(client: HomepotClient = Depends(get_client)) -> Dict[str, Any]:
    """Get detailed client status information."""
    try:
        is_connected = client.is_connected()
        version = client.get_version()

        return {
            "connected": is_connected,
            "version": version,
            "uptime": asyncio.get_event_loop().time(),
            "client_type": "HOMEPOT Client",
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


@app.post("/connect", tags=["Client"])
async def connect_client(client: HomepotClient = Depends(get_client)) -> Dict[str, str]:
    """Connect the HOMEPOT client."""
    try:
        if client.is_connected():
            return {"message": "Client already connected", "status": "connected"}

        await client.connect()
        return {"message": "Client connected successfully", "status": "connected"}
    except Exception as e:
        logger.error(f"Connect failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect: {e}")


@app.post("/disconnect", tags=["Client"])
async def disconnect_client(
    client: HomepotClient = Depends(get_client),
) -> Dict[str, str]:
    """Disconnect the HOMEPOT client."""
    try:
        if not client.is_connected():
            return {"message": "Client already disconnected", "status": "disconnected"}

        await client.disconnect()
        return {"message": "Client disconnected successfully", "status": "disconnected"}
    except Exception as e:
        logger.error(f"Disconnect failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect: {e}")


@app.get("/version", tags=["Client"])
async def get_version(client: HomepotClient = Depends(get_client)) -> Dict[str, str]:
    """Get the client version information."""
    try:
        version = client.get_version()
        return {"version": version}
    except Exception as e:
        logger.error(f"Version check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get version: {e}")


# POS Scenario API Endpoints

@app.post("/sites", tags=["Sites"], response_model=Dict[str, str])
async def create_site(site_request: CreateSiteRequest) -> Dict[str, str]:
    """Create a new site for device management."""
    try:
        db_service = await get_database_service()
        
        # Check if site already exists
        existing_site = await db_service.get_site_by_site_id(site_request.site_id)
        if existing_site:
            raise HTTPException(status_code=409, detail=f"Site {site_request.site_id} already exists")
        
        # Create new site
        site = await db_service.create_site(
            site_id=site_request.site_id,
            name=site_request.name,
            description=site_request.description,
            location=site_request.location,
        )
        
        logger.info(f"Created site {site.site_id}")
        return {
            "message": f"Site {site.site_id} created successfully",
            "site_id": site.site_id,
            "name": site.name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create site: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create site: {e}")


@app.post("/sites/{site_id}/devices", tags=["Devices"], response_model=Dict[str, str])
async def create_device(site_id: str, device_request: CreateDeviceRequest) -> Dict[str, str]:
    """Create a new device for a site."""
    try:
        db_service = await get_database_service()
        
        # Get site
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
        
        # Create device
        device = await db_service.create_device(
            device_id=device_request.device_id,
            name=device_request.name,
            device_type=device_request.device_type,
            site_id=site.id,
            ip_address=device_request.ip_address,
            config=device_request.config,
        )
        
        logger.info(f"Created device {device.device_id} for site {site_id}")
        return {
            "message": f"Device {device.device_id} created successfully",
            "device_id": device.device_id,
            "site_id": site_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create device: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create device: {e}")


@app.post("/sites/{site_id}/jobs", tags=["Jobs"], response_model=Dict[str, str])
async def create_pos_config_job(
    site_id: str, 
    job_request: CreateJobRequest
) -> Dict[str, str]:
    """Create a POS configuration update job (Step 1-2 from scenario).
    
    This endpoint implements:
    1. Tech logs in and selects site → Action: "Update POS payment config"
    2. Core API enqueues a job to segment: site-123/pos-terminals
    """
    try:
        orchestrator = await get_job_orchestrator()
        
        # Create the job using orchestrator
        job_id = await orchestrator.create_pos_config_update_job(
            site_id=site_id,
            action=job_request.action,
            description=job_request.description,
            config_url=job_request.config_url,
            config_version=job_request.config_version,
            priority=job_request.priority,
        )
        
        logger.info(f"Created job {job_id} for site {site_id}")
        return {
            "message": f"Job created successfully for site {site_id}",
            "job_id": job_id,
            "site_id": site_id,
            "action": job_request.action,
            "status": "queued",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")


@app.get("/jobs/{job_id}", tags=["Jobs"], response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get job status and details (real-time tracking)."""
    try:
        orchestrator = await get_job_orchestrator()
        
        job_status = await orchestrator.get_job_status(job_id)
        if not job_status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return JobStatusResponse(**job_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {e}")


@app.get("/sites/{site_id}/health", tags=["Health"], response_model=SiteHealthResponse)
async def get_site_health(site_id: str) -> SiteHealthResponse:
    """Get site health status (Step 5: '5/5 terminals healthy')."""
    try:
        db_service = await get_database_service()
        
        # Get site
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
        
        # Get all devices for the site
        devices = await db_service.get_devices_by_site_and_segment(site.id)
        
        if not devices:
            return SiteHealthResponse(
                site_id=site_id,
                total_devices=0,
                healthy_devices=0,
                offline_devices=0,
                error_devices=0,
                health_percentage=0.0,
                status_summary="No devices found",
                devices=[],
                last_updated=datetime.utcnow().isoformat(),
            )
        
        # Count device statuses
        from homepot_client.models import DeviceStatus
        healthy_count = sum(1 for d in devices if d.status == DeviceStatus.ONLINE)
        offline_count = sum(1 for d in devices if d.status == DeviceStatus.OFFLINE)
        error_count = sum(1 for d in devices if d.status == DeviceStatus.ERROR)
        
        total_count = len(devices)
        health_percentage = (healthy_count / total_count * 100) if total_count > 0 else 0
        
        # Create status summary
        if healthy_count == total_count:
            status_summary = f"{healthy_count}/{total_count} terminals healthy"
        elif healthy_count == 0:
            status_summary = f"All {total_count} terminals offline/error"
        else:
            status_summary = f"{healthy_count}/{total_count} terminals healthy"
        
        # Device details
        device_list = []
        for device in devices:
            device_list.append({
                "device_id": device.device_id,
                "name": device.name,
                "type": device.device_type,
                "status": device.status,
                "ip_address": device.ip_address,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            })
        
        return SiteHealthResponse(
            site_id=site_id,
            total_devices=total_count,
            healthy_devices=healthy_count,
            offline_devices=offline_count,
            error_devices=error_count,
            health_percentage=health_percentage,
            status_summary=status_summary,
            devices=device_list,
            last_updated=datetime.utcnow().isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get site health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get site health: {e}")


@app.get("/sites", tags=["Sites"])
async def list_sites() -> Dict[str, List[Dict]]:
    """List all sites."""
    try:
        db_service = await get_database_service()
        
        # For demo, we'll create a simple query (in real app, add pagination)
        from sqlalchemy import select
        from homepot_client.models import Site
        
        async with db_service.get_session() as session:
            result = await session.execute(
                select(Site).where(Site.is_active == True).order_by(Site.created_at.desc())
            )
            sites = result.scalars().all()
            
            site_list = []
            for site in sites:
                site_list.append({
                    "site_id": site.site_id,
                    "name": site.name,
                    "description": site.description,
                    "location": site.location,
                    "created_at": site.created_at.isoformat() if site.created_at else None,
                })
            
            return {"sites": site_list}
        
    except Exception as e:
        logger.error(f"Failed to list sites: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sites: {e}")


# Phase 3: Agent Management API Endpoints

@app.get("/agents", tags=["Agents"])
async def list_agents() -> Dict[str, List[Dict]]:
    """List all active POS agents and their status."""
    try:
        from homepot_client.agents import get_agent_manager
        
        agent_manager = await get_agent_manager()
        agents_status = await agent_manager.get_all_agents_status()
        
        return {"agents": agents_status}
        
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {e}")


@app.get("/agents/{device_id}", tags=["Agents"])
async def get_agent_status(device_id: str) -> Dict[str, Any]:
    """Get detailed status of a specific POS agent."""
    try:
        from homepot_client.agents import get_agent_manager
        
        agent_manager = await get_agent_manager()
        agent_status = await agent_manager.get_agent_status(device_id)
        
        if not agent_status:
            raise HTTPException(status_code=404, detail=f"Agent for device {device_id} not found")
        
        return agent_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {e}")


@app.post("/agents/{device_id}/push", tags=["Agents"])
async def send_push_notification(device_id: str, notification_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send a direct push notification to a POS agent for testing."""
    try:
        from homepot_client.agents import get_agent_manager
        
        agent_manager = await get_agent_manager()
        response = await agent_manager.send_push_notification(device_id, notification_data)
        
        if not response:
            raise HTTPException(status_code=404, detail=f"Agent for device {device_id} not found")
        
        return {
            "message": f"Push notification sent to {device_id}",
            "device_id": device_id,
            "response": response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send push notification: {e}")


# Phase 3: Device Health Check Endpoints

@app.get("/devices/{device_id}/health", tags=["Health"])
async def get_device_health(device_id: str) -> Dict[str, Any]:
    """Get detailed health status of a specific device."""
    try:
        from homepot_client.agents import get_agent_manager
        
        agent_manager = await get_agent_manager()
        agent_status = await agent_manager.get_agent_status(device_id)
        
        if not agent_status:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
        # Get the last health check data
        health_data = agent_status.get("last_health_check")
        if not health_data:
            # Trigger a health check
            response = await agent_manager.send_push_notification(device_id, {
                "action": "health_check",
                "data": {}
            })
            
            if response and response.get("health_check"):
                health_data = response["health_check"]
            else:
                raise HTTPException(status_code=503, detail="Health check failed")
        
        return {
            "device_id": device_id,
            "health": health_data,
            "agent_state": agent_status.get("state"),
            "last_updated": datetime.utcnow().isoformat(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get device health: {e}")


@app.post("/devices/{device_id}/health", tags=["Health"])
async def trigger_health_check(device_id: str) -> Dict[str, Any]:
    """Trigger an immediate health check for a device."""
    try:
        from homepot_client.agents import get_agent_manager
        
        agent_manager = await get_agent_manager()
        
        # Send health check request to agent
        response = await agent_manager.send_push_notification(device_id, {
            "action": "health_check",
            "data": {}
        })
        
        if not response:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
        if response.get("status") != "success":
            raise HTTPException(status_code=503, detail=f"Health check failed: {response.get('message', 'Unknown error')}")
        
        return {
            "message": f"Health check completed for {device_id}",
            "device_id": device_id,
            "health": response.get("health_check"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger health check: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger health check: {e}")


@app.post("/devices/{device_id}/restart", tags=["Actions"])
async def restart_device(device_id: str) -> Dict[str, Any]:
    """Restart the POS application on a device."""
    try:
        from homepot_client.agents import get_agent_manager
        
        agent_manager = await get_agent_manager()
        
        # Send restart request to agent
        response = await agent_manager.send_push_notification(device_id, {
            "action": "restart_pos_app",
            "data": {}
        })
        
        if not response:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
        return {
            "message": f"Restart request sent to {device_id}",
            "device_id": device_id,
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart device: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart device: {e}")


@app.get("/version", tags=["Client"])


# WebSocket endpoint for real-time status updates
@app.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time status updates.
    
    Provides live updates of job status and site health for dashboard UI.
    """
    await websocket.accept()
    logger.info("WebSocket client connected")
    
    try:
        while True:
            # Get orchestrator and database services
            orchestrator = await get_job_orchestrator()
            db_service = await get_database_service()
            
            # Get recent jobs status
            recent_jobs = await orchestrator.get_recent_jobs_status()
            
            # Get all sites health summary
            from sqlalchemy import select
            from homepot_client.models import Site, Device, DeviceStatus
            
            sites_health = []
            async with db_service.get_session() as session:
                result = await session.execute(
                    select(Site).where(Site.is_active == True).order_by(Site.created_at.desc())
                )
                sites = result.scalars().all()
                
                for site in sites:
                    # Get devices for this site
                    device_result = await session.execute(
                        select(Device).where(Device.site_id == site.id)
                    )
                    devices = device_result.scalars().all()
                    
                    if devices:
                        healthy_count = sum(1 for d in devices if d.status == DeviceStatus.ONLINE)
                        total_count = len(devices)
                        sites_health.append({
                            "site_id": site.site_id,
                            "name": site.name,
                            "health_status": f"{healthy_count}/{total_count} terminals healthy",
                            "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0,
                            "total_devices": total_count,
                            "healthy_devices": healthy_count,
                        })
            
            # Send status update
            status_update = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "status_update",
                "data": {
                    "recent_jobs": recent_jobs,
                    "sites_health": sites_health,
                }
            }
            
            await websocket.send_json(status_update)
            
            # Wait before next update (configurable in real app)
            await asyncio.sleep(5)  # Update every 5 seconds
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass


@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def get_dashboard():
    """Simple dashboard HTML for testing WebSocket and API endpoints."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>HOMEPOT Client Dashboard - Phase 3</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .dashboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
            .panel { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .status-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .healthy { background-color: #d4edda; border-color: #c3e6cb; }
            .warning { background-color: #fff3cd; border-color: #ffeaa7; }
            .error { background-color: #f8d7da; border-color: #f5c6cb; }
            .job-status { padding: 5px 10px; border-radius: 3px; color: white; margin-left: 10px; }
            .status-queued { background-color: #6c757d; }
            .status-running { background-color: #007bff; }
            .status-sent { background-color: #17a2b8; }
            .status-acknowledged { background-color: #28a745; }
            .status-completed { background-color: #28a745; }
            .status-failed { background-color: #dc3545; }
            .agent-state { padding: 3px 8px; border-radius: 3px; font-size: 0.8em; color: white; }
            .state-idle { background-color: #28a745; }
            .state-downloading { background-color: #17a2b8; }
            .state-updating { background-color: #ffc107; color: black; }
            .state-restarting { background-color: #fd7e14; }
            .state-health_check { background-color: #6f42c1; }
            .state-error { background-color: #dc3545; }
            .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 15px; }
            .metric { background: #f8f9fa; padding: 10px; border-radius: 5px; text-align: center; }
            .metric-value { font-size: 1.5em; font-weight: bold; color: #007bff; }
            .api-section { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .endpoint { background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px; font-family: monospace; }
            .badge { background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }
            .phase-badge { background: #28a745; color: white; padding: 4px 8px; border-radius: 5px; font-size: 0.9em; margin-left: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏠 HOMEPOT Client Dashboard <span class="phase-badge">Phase 3: Agent Simulation</span></h1>
                <p><strong>Consortium Project:</strong> Homogenous Cyber Management of End-Points and OT</p>
                <p><strong>Real POS Agent Simulation:</strong> Interactive device health checks & configuration management</p>
            </div>
            
            <div class="dashboard-grid">
                <div class="panel">
                    <h2>📊 Real-time Status</h2>
                    <div id="sites-health"></div>
                    <div id="recent-jobs"></div>
                </div>
                
                <div class="panel">
                    <h2>🤖 Agent Simulation</h2>
                    <div id="agents-status"></div>
                    <div class="metrics" id="simulation-metrics">
                        <div class="metric">
                            <div class="metric-value" id="total-agents">0</div>
                            <div>Active Agents</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="health-checks">0</div>
                            <div>Health Checks/min</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="api-section">
                <h2>🔗 Phase 3 API Endpoints</h2>
                <p>Test the enhanced POS scenario with realistic agent simulation:</p>
                
                <h3>Core Workflow (Phases 1-2)</h3>
                <div class="endpoint"><span class="badge">POST</span> /sites - Create restaurant site</div>
                <div class="endpoint"><span class="badge">POST</span> /sites/{site_id}/devices - Add POS terminals</div>
                <div class="endpoint"><span class="badge">POST</span> /sites/{site_id}/jobs - Trigger payment config update</div>
                <div class="endpoint"><span class="badge">GET</span> /jobs/{job_id} - Monitor job progress</div>
                <div class="endpoint"><span class="badge">GET</span> /sites/{site_id}/health - Check site health status</div>
                
                <h3>Agent Management (Phase 3)</h3>
                <div class="endpoint"><span class="badge">GET</span> /agents - List all POS agents</div>
                <div class="endpoint"><span class="badge">GET</span> /agents/{device_id} - Get agent status</div>
                <div class="endpoint"><span class="badge">POST</span> /agents/{device_id}/push - Send test notification</div>
                
                <h3>Device Health & Actions (Phase 3)</h3>
                <div class="endpoint"><span class="badge">GET</span> /devices/{device_id}/health - Device health details</div>
                <div class="endpoint"><span class="badge">POST</span> /devices/{device_id}/health - Trigger health check</div>
                <div class="endpoint"><span class="badge">POST</span> /devices/{device_id}/restart - Restart POS app</div>
            </div>
        </div>
        
        <script>
            const ws = new WebSocket("ws://localhost:8000/ws/status");
            let healthCheckCount = 0;
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === "status_update") {
                    updateSitesHealth(data.data.sites_health);
                    updateRecentJobs(data.data.recent_jobs);
                    updateAgentsStatus(data.data.agents_status || []);
                }
            };
            
            function updateSitesHealth(sites) {
                const container = document.getElementById('sites-health');
                if (!sites || sites.length === 0) {
                    container.innerHTML = '<h3>Sites Health Status</h3><p>No sites configured</p>';
                    return;
                }
                
                let html = '<h3>Sites Health Status</h3>';
                sites.forEach(site => {
                    const cssClass = site.health_percentage === 100 ? 'healthy' : 
                                   site.health_percentage > 50 ? 'warning' : 'error';
                    html += `
                        <div class="status-card ${cssClass}">
                            <strong>${site.name}</strong> (${site.site_id})<br>
                            ${site.health_status}<br>
                            <small>Health: ${site.health_percentage.toFixed(1)}%</small>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
            
            function updateRecentJobs(jobs) {
                const container = document.getElementById('recent-jobs');
                if (!jobs || jobs.length === 0) {
                    container.innerHTML = '<h3>Recent Jobs</h3><p>No recent jobs</p>';
                    return;
                }
                
                let html = '<h3>Recent Jobs</h3>';
                jobs.forEach(job => {
                    html += `
                        <div class="status-card">
                            <strong>Job ${job.job_id}</strong>
                            <span class="job-status status-${job.status}">${job.status}</span><br>
                            <small>${job.description || job.action}</small><br>
                            <small>Site: ${job.site_id} | Created: ${new Date(job.created_at).toLocaleString()}</small>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
            
            function updateAgentsStatus(agents) {
                const container = document.getElementById('agents-status');
                const totalAgentsEl = document.getElementById('total-agents');
                
                if (!agents || agents.length === 0) {
                    container.innerHTML = '<h3>POS Agents</h3><p>No agents active</p>';
                    totalAgentsEl.textContent = '0';
                    return;
                }
                
                totalAgentsEl.textContent = agents.length;
                
                let html = '<h3>POS Agents</h3>';
                agents.forEach(agent => {
                    const stateClass = `state-${agent.state || 'idle'}`;
                    const healthStatus = agent.last_health_check ? 
                        (agent.last_health_check.status === 'healthy' ? '✅' : '❌') : '⏳';
                    
                    html += `
                        <div class="status-card">
                            <strong>${agent.device_id}</strong>
                            <span class="agent-state ${stateClass}">${agent.state || 'idle'}</span><br>
                            <small>Config: v${agent.config_version} | Health: ${healthStatus}</small>
                        </div>
                    `;
                });
                container.innerHTML = html;
                
                // Update health check counter (simplified)
                healthCheckCount += Math.floor(Math.random() * 3);
                document.getElementById('health-checks').textContent = Math.floor(healthCheckCount / 60);
            }
            
            // Fetch agent status periodically
            setInterval(async () => {
                try {
                    const response = await fetch('/agents');
                    const data = await response.json();
                    updateAgentsStatus(data.agents || []);
                } catch (error) {
                    console.error('Failed to fetch agents:', error);
                }
            }, 10000); // Every 10 seconds
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
            
            ws.onclose = function() {
                console.log('WebSocket connection closed');
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/version", tags=["Client"])
async def get_version(client: HomepotClient = Depends(get_client)) -> Dict[str, str]:
    """Get the client version information."""
    try:
        version = client.get_version()
        return {"version": version}
    except Exception as e:
        logger.error(f"Version check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get version: {e}")


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "status_code": 500}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
