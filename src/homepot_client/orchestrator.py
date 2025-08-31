"""Job queue and orchestrator for HOMEPOT Client.

This module implements the job queue system and orchestrator that handles
device management tasks as shown in the POS payment gateway scenario.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homepot_client.config import get_settings
from homepot_client.database import get_database_service
from homepot_client.models import Job, JobPriority, JobStatus

logger = logging.getLogger(__name__)


class PushNotification:
    """Push notification payload for device communication."""
    
    def __init__(
        self,
        config_url: str,
        version: str,
        ttl_sec: int = 300,
        collapse_key: Optional[str] = None,
        priority: str = "high",
    ):
        """Initialize push notification.
        
        Args:
            config_url: URL to download new configuration
            version: Configuration version
            ttl_sec: Time to live in seconds
            collapse_key: Key for grouping notifications
            priority: Notification priority (low, normal, high, critical)
        """
        self.config_url = config_url
        self.version = version
        self.ttl_sec = ttl_sec
        self.collapse_key = collapse_key or f"homepot-config-{version}"
        self.priority = priority
        self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "config_url": self.config_url,
            "version": self.version,
            "ttl_sec": self.ttl_sec,
            "collapse_key": self.collapse_key,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }
    
    def is_expired(self) -> bool:
        """Check if notification has expired."""
        return datetime.utcnow() > self.created_at + timedelta(seconds=self.ttl_sec)


class JobOrchestrator:
    """Orchestrator for managing and executing device jobs."""
    
    def __init__(self):
        """Initialize job orchestrator."""
        self.settings = get_settings()
        self._running = False
        self._job_queue = asyncio.Queue()
        self._active_jobs: Dict[str, Job] = {}
        self._worker_tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start the job orchestrator."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker tasks
        num_workers = self.settings.devices.max_concurrent_jobs
        for i in range(num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(task)
        
        logger.info(f"Job orchestrator started with {num_workers} workers")
    
    async def stop(self):
        """Stop the job orchestrator."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for tasks to finish
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        
        logger.info("Job orchestrator stopped")
    
    async def create_pos_config_update_job(
        self,
        site_id: str,
        action: str = "Update POS payment config",
        description: Optional[str] = None,
        config_url: Optional[str] = None,
        config_version: Optional[str] = None,
        user_id: int = 1,  # Default user for demo
        priority: str = JobPriority.HIGH,
    ) -> str:
        """Create a POS configuration update job (the main scenario).
        
        This implements the workflow from your scenario:
        1. Tech logs in and selects site → Action: "Update POS payment config"
        2. Core API enqueues a job to segment: site-123/pos-terminals
        
        Args:
            site_id: Site identifier (e.g., "site-123")
            action: Job action description
            description: Detailed job description
            config_url: URL to new configuration
            config_version: Configuration version
            user_id: User who created the job
            priority: Job priority
            
        Returns:
            job_id: Unique job identifier
        """
        db_service = await get_database_service()
        
        # Get site from database
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise ValueError(f"Site {site_id} not found")
        
        # Generate job ID and configuration details
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        config_version = config_version or f"v{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        config_url = config_url or f"https://config.homepot.local/{site_id}/pos/{config_version}.json"
        
        # Create job in database
        job = await db_service.create_job(
            job_id=job_id,
            action=action,
            description=description or f"Update POS payment configuration for {site_id}",
            site_id=site.id,
            segment="pos-terminals",  # Target POS terminals segment
            config_url=config_url,
            config_version=config_version,
            ttl_seconds=self.settings.push.default_ttl,
            collapse_key=f"pos-gateway-{site_id}",
            priority=priority,
            created_by=user_id,
            payload={
                "action": action,
                "site_id": site_id,
                "segment": "pos-terminals",
                "config_type": "payment_gateway",
                "restart_required": True,
            },
        )
        
        # Add job to queue for processing
        await self._job_queue.put(job)
        
        # Create audit log
        await db_service.create_audit_log(
            event_type="job_created",
            description=f"Created job {job_id} for {action} at {site_id}",
            user_id=user_id,
            job_id=job.id,
            site_id=site.id,
            metadata={
                "job_id": job_id,
                "action": action,
                "site_id": site_id,
                "segment": "pos-terminals",
                "priority": priority,
            },
        )
        
        logger.info(f"Created POS config update job {job_id} for site {site_id}")
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get current job status and details."""
        db_service = await get_database_service()
        job = await db_service.get_job_by_id(job_id)
        
        if not job:
            return None
        
        return {
            "job_id": job.job_id,
            "action": job.action,
            "description": job.description,
            "status": job.status,
            "priority": job.priority,
            "site_id": job.site.site_id if job.site else None,
            "segment": job.segment,
            "config_url": job.config_url,
            "config_version": job.config_version,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error_message": job.error_message,
        }
    
    async def _worker(self, worker_name: str):
        """Worker task for processing jobs from the queue."""
        logger.info(f"Job worker {worker_name} started")
        
        while self._running:
            try:
                # Get job from queue with timeout
                job = await asyncio.wait_for(self._job_queue.get(), timeout=1.0)
                
                # Process the job
                await self._process_job(job, worker_name)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Job worker {worker_name} stopped")
    
    async def _process_job(self, job: Job, worker_name: str):
        """Process a single job (Step 3 from scenario: Orchestrator sends push)."""
        logger.info(f"Worker {worker_name} processing job {job.job_id}")
        
        try:
            # Mark job as started
            db_service = await get_database_service()
            await db_service.update_job_status(job.job_id, JobStatus.SENT)
            
            # Step 3: Orchestrator sends a high-priority push with tiny payload
            push_notification = PushNotification(
                config_url=job.config_url,
                version=job.config_version,
                ttl_sec=job.ttl_seconds,
                collapse_key=job.collapse_key,
                priority="high",
            )
            
            # Get target devices for this job
            devices = await db_service.get_devices_by_site_and_segment(
                site_id=job.site_id,
                segment=job.segment,
            )
            
            if not devices:
                # No devices found - mark as completed with warning
                await db_service.update_job_status(
                    job.job_id,
                    JobStatus.COMPLETED,
                    result={"status": "no_devices", "message": f"No {job.segment} devices found"},
                )
                logger.warning(f"Job {job.job_id}: No devices found for segment {job.segment}")
                return
            
            # Send push notifications to all devices
            successful_pushes = 0
            failed_pushes = 0
            device_results = []
            
            for device in devices:
                try:
                    # Simulate sending push notification
                    success = await self._send_push_notification(device, push_notification)
                    
                    if success:
                        successful_pushes += 1
                        device_results.append({
                            "device_id": device.device_id,
                            "status": "push_sent",
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                    else:
                        failed_pushes += 1
                        device_results.append({
                            "device_id": device.device_id,
                            "status": "push_failed",
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                        
                except Exception as e:
                    failed_pushes += 1
                    device_results.append({
                        "device_id": device.device_id,
                        "status": "push_error",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    logger.error(f"Failed to send push to device {device.device_id}: {e}")
            
            # Update job with results
            result = {
                "total_devices": len(devices),
                "successful_pushes": successful_pushes,
                "failed_pushes": failed_pushes,
                "devices": device_results,
                "push_payload": push_notification.to_dict(),
            }
            
            if failed_pushes == 0:
                await db_service.update_job_status(job.job_id, JobStatus.ACKNOWLEDGED, result=result)
                logger.info(f"Job {job.job_id} completed successfully: {successful_pushes}/{len(devices)} devices")
            else:
                await db_service.update_job_status(
                    job.job_id,
                    JobStatus.FAILED,
                    result=result,
                    error_message=f"Failed to send push to {failed_pushes}/{len(devices)} devices",
                )
                logger.warning(f"Job {job.job_id} completed with errors: {successful_pushes}/{len(devices)} devices successful")
            
        except Exception as e:
            logger.error(f"Job {job.job_id} processing failed: {e}")
            
            # Mark job as failed
            db_service = await get_database_service()
            await db_service.update_job_status(
                job.job_id,
                JobStatus.FAILED,
                error_message=str(e),
            )
    
    async def _send_push_notification(self, device, push_notification: PushNotification) -> bool:
        """Send push notification to a device using the agent manager.
        
        This now uses the realistic agent simulation instead of basic simulation.
        """
        try:
            # Import here to avoid circular imports
            from homepot_client.agents import get_agent_manager
            
            agent_manager = await get_agent_manager()
            
            # Prepare notification data for the agent
            notification_data = {
                "action": push_notification.action,
                "data": {
                    "config_url": push_notification.config_url,
                    "config_version": push_notification.version,
                    "priority": push_notification.priority,
                },
                "collapse_key": push_notification.collapse_key,
                "time_to_live": push_notification.time_to_live,
            }
            
            # Send to agent and get response
            response = await agent_manager.send_push_notification(device.device_id, notification_data)
            
            if response and response.get("status") == "success":
                logger.debug(f"Push notification successful to {device.device_id}: {response.get('message', 'OK')}")
                return True
            else:
                error_msg = response.get("message", "Unknown error") if response else "No response from agent"
                logger.warning(f"Push notification failed to {device.device_id}: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send push to {device.device_id}: {e}")
            return False

    async def get_recent_jobs_status(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent jobs status for WebSocket updates."""
        try:
            from sqlalchemy import select, desc
            
            async with self.db_service.get_session() as session:
                result = await session.execute(
                    select(Job)
                    .order_by(desc(Job.created_at))
                    .limit(limit)
                )
                jobs = result.scalars().all()
                
                recent_jobs = []
                for job in jobs:
                    recent_jobs.append({
                        "job_id": job.job_id,
                        "site_id": job.site_id,
                        "status": job.status.value,
                        "action": job.action,
                        "description": job.description,
                        "created_at": job.created_at.isoformat() if job.created_at else None,
                        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    })
                
                return recent_jobs
                
        except Exception as e:
            logger.error(f"Failed to get recent jobs: {e}")
            return []


# Global orchestrator instance
_orchestrator: Optional[JobOrchestrator] = None


async def get_job_orchestrator() -> JobOrchestrator:
    """Get job orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = JobOrchestrator()
        await _orchestrator.start()
    return _orchestrator


async def stop_job_orchestrator():
    """Stop job orchestrator."""
    global _orchestrator
    if _orchestrator is not None:
        await _orchestrator.stop()
        _orchestrator = None
