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
        <title>HOMEPOT Client Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .status-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .healthy { background-color: #d4edda; }
            .warning { background-color: #fff3cd; }
            .error { background-color: #f8d7da; }
            .job-status { padding: 5px 10px; border-radius: 3px; color: white; }
            .status-queued { background-color: #6c757d; }
            .status-running { background-color: #007bff; }
            .status-completed { background-color: #28a745; }
            .status-failed { background-color: #dc3545; }
        </style>
    </head>
    <body>
        <h1>🏠 HOMEPOT Client Dashboard</h1>
        <p><strong>Consortium Project:</strong> Homogenous Cyber Management of End-Points and OT</p>
        
        <div id="status">
            <h2>📊 Real-time Status</h2>
            <div id="sites-health"></div>
            <div id="recent-jobs"></div>
        </div>
        
        <div>
            <h2>🔗 API Examples</h2>
            <p>Test the POS scenario workflow:</p>
            <ul>
                <li><strong>Create Site:</strong> POST /sites</li>
                <li><strong>Create Device:</strong> POST /sites/{site_id}/devices</li>
                <li><strong>Update POS Config:</strong> POST /sites/{site_id}/jobs</li>
                <li><strong>Check Job Status:</strong> GET /jobs/{job_id}</li>
                <li><strong>Site Health:</strong> GET /sites/{site_id}/health</li>
            </ul>
        </div>
        
        <script>
            const ws = new WebSocket("ws://localhost:8000/ws/status");
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === "status_update") {
                    updateSitesHealth(data.data.sites_health);
                    updateRecentJobs(data.data.recent_jobs);
                }
            };
            
            function updateSitesHealth(sites) {
                const container = document.getElementById('sites-health');
                if (!sites || sites.length === 0) {
                    container.innerHTML = '<p>No sites configured</p>';
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
                            <small>${job.description}</small><br>
                            <small>Site: ${job.site_id} | Created: ${new Date(job.created_at).toLocaleString()}</small>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
            
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
