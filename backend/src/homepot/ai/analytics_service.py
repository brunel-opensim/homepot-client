"""AI Analytics Service - Data aggregation and pattern analysis.

This service queries the analytics tables and provides aggregated insights
for ML models and predictive features.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import and_, select

from homepot.app.models.AnalyticsModel import (
    ConfigurationHistory,
    DeviceMetrics,
    ErrorLog,
    JobOutcome,
    SiteOperatingSchedule,
)
from homepot.database import get_database_service
from homepot.models import Device

logger = logging.getLogger(__name__)


class AIAnalyticsService:
    """Service for aggregating analytics data for AI/ML features."""

    @staticmethod
    async def get_device_performance_trends(
        device_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Analyze device performance trends over time.

        Args:
            device_id: Device identifier
            days: Number of days to analyze (default: 30)

        Returns:
            Dict containing performance metrics, trends, and health score
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)

                # Get recent metrics
                result = await session.execute(
                    select(DeviceMetrics)
                    .where(
                        and_(
                            DeviceMetrics.device_id == device_id,
                            DeviceMetrics.timestamp >= cutoff_date,
                        )
                    )
                    .order_by(DeviceMetrics.timestamp.desc())
                    .limit(1000)
                )
                metrics = result.scalars().all()

                if not metrics:
                    return {
                        "device_id": device_id,
                        "status": "no_data",
                        "message": "No metrics available for analysis",
                    }

                # Calculate aggregates
                avg_cpu = sum(m.cpu_percent or 0 for m in metrics) / len(metrics)
                avg_memory = sum(m.memory_percent or 0 for m in metrics) / len(metrics)
                avg_disk = sum(m.disk_percent or 0 for m in metrics) / len(metrics)

                # Detect trends (simple linear regression on recent data)
                recent_cpu = [m.cpu_percent or 0 for m in metrics[:100]]
                cpu_trend = "increasing" if recent_cpu[0] > recent_cpu[-1] else "stable"

                # Calculate health score (0-100)
                health_score = 100.0
                health_score -= min(avg_cpu, 30)  # Penalize high CPU
                health_score -= min(avg_memory, 30)  # Penalize high memory
                health_score -= min(avg_disk / 2, 20)  # Penalize high disk

                return {
                    "device_id": device_id,
                    "period_days": days,
                    "metrics": {
                        "avg_cpu_percent": round(avg_cpu, 2),
                        "avg_memory_percent": round(avg_memory, 2),
                        "avg_disk_percent": round(avg_disk, 2),
                        "sample_count": len(metrics),
                    },
                    "trends": {
                        "cpu": cpu_trend,
                    },
                    "health_score": round(max(0, health_score), 2),
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to analyze device performance: {e}", exc_info=True)
            return {"device_id": device_id, "status": "error", "message": str(e)}

    @staticmethod
    async def get_job_outcome_patterns(
        site_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Analyze job outcome patterns to identify success factors.

        Args:
            site_id: Optional site filter
            days: Number of days to analyze

        Returns:
            Dict with success rates, failure patterns, optimal timing
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)

                # Build query
                query = select(JobOutcome).where(JobOutcome.completed_at >= cutoff_date)
                if site_id:
                    query = query.where(JobOutcome.site_id == site_id)

                result = await session.execute(query)
                outcomes = result.scalars().all()

                if not outcomes:
                    return {"status": "no_data", "message": "No job outcomes available"}

                # Calculate success rate
                total_jobs = len(outcomes)
                successful_jobs = sum(1 for o in outcomes if o.status == "completed")
                success_rate = (successful_jobs / total_jobs) * 100

                # Analyze by hour of day
                hourly_success = {}
                for outcome in outcomes:
                    hour = outcome.started_at.hour
                    if hour not in hourly_success:
                        hourly_success[hour] = {"total": 0, "success": 0}
                    hourly_success[hour]["total"] += 1
                    if outcome.status == "completed":
                        hourly_success[hour]["success"] += 1

                # Find optimal hours (>90% success rate, minimum 5 jobs)
                optimal_hours = []
                for hour, stats in hourly_success.items():
                    if stats["total"] >= 5:
                        rate = (stats["success"] / stats["total"]) * 100
                        if rate >= 90:
                            optimal_hours.append(
                                {
                                    "hour": hour,
                                    "success_rate": round(rate, 2),
                                    "sample_size": stats["total"],
                                }
                            )

                optimal_hours.sort(key=lambda x: x["success_rate"], reverse=True)

                # Analyze failure reasons
                failed_jobs = [o for o in outcomes if o.status == "failed"]
                failure_patterns = {}
                for job in failed_jobs:
                    reason = job.failure_reason or "unknown"
                    failure_patterns[reason] = failure_patterns.get(reason, 0) + 1

                return {
                    "site_id": site_id,
                    "period_days": days,
                    "summary": {
                        "total_jobs": total_jobs,
                        "successful": successful_jobs,
                        "failed": total_jobs - successful_jobs,
                        "success_rate": round(success_rate, 2),
                    },
                    "optimal_hours": optimal_hours[:5],  # Top 5
                    "failure_patterns": failure_patterns,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to analyze job patterns: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def get_optimal_scheduling_windows(
        site_id: str,
        day_of_week: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get optimal time windows for job scheduling based on site schedule.

        Args:
            site_id: Site identifier
            day_of_week: Optional day filter (0=Monday, 6=Sunday)

        Returns:
            Dict with recommended scheduling windows, avoiding peak/maintenance
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Get site schedules
                query = select(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == site_id
                )
                if day_of_week is not None:
                    query = query.where(
                        SiteOperatingSchedule.day_of_week == day_of_week
                    )

                result = await session.execute(
                    query.order_by(SiteOperatingSchedule.day_of_week)
                )
                schedules = result.scalars().all()

                if not schedules:
                    return {
                        "site_id": site_id,
                        "status": "no_schedule",
                        "message": "No operating schedule configured for site",
                    }

                recommendations = []
                day_names = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]

                for schedule in schedules:
                    if schedule.is_closed:
                        recommendations.append(
                            {
                                "day": day_names[schedule.day_of_week],
                                "day_of_week": schedule.day_of_week,
                                "status": "closed",
                                "recommendation": "Avoid - site closed",
                            }
                        )
                        continue

                    # Calculate optimal windows
                    open_hour = schedule.open_time.hour if schedule.open_time else 8
                    close_hour = schedule.close_time.hour if schedule.close_time else 22
                    peak_start = (
                        schedule.peak_hours_start.hour
                        if schedule.peak_hours_start
                        else 12
                    )
                    peak_end = (
                        schedule.peak_hours_end.hour if schedule.peak_hours_end else 14
                    )

                    # Recommend: 1 hour after open, or 1 hour after peak ends
                    optimal_windows = []

                    # Early morning window (after opening, before peak)
                    if open_hour + 1 < peak_start:
                        optimal_windows.append(
                            {
                                "start": f"{open_hour + 1:02d}:00",
                                "end": f"{peak_start:02d}:00",
                                "reason": "Low traffic - after opening",
                            }
                        )

                    # Evening window (after peak, before closing)
                    if peak_end + 1 < close_hour - 1:
                        optimal_windows.append(
                            {
                                "start": f"{peak_end + 1:02d}:00",
                                "end": f"{close_hour - 1:02d}:00",
                                "reason": "Low traffic - after peak hours",
                            }
                        )

                    # Late night (if open late)
                    if close_hour >= 22:
                        optimal_windows.append(
                            {
                                "start": f"{close_hour - 2:02d}:00",
                                "end": f"{close_hour:02d}:00",
                                "reason": "Minimal traffic - near closing",
                            }
                        )

                    recommendations.append(
                        {
                            "day": day_names[schedule.day_of_week],
                            "day_of_week": schedule.day_of_week,
                            "status": "open",
                            "operating_hours": f"{schedule.open_time} - {schedule.close_time}",
                            "peak_hours": f"{schedule.peak_hours_start} - {schedule.peak_hours_end}",
                            "expected_volume": schedule.expected_transaction_volume,
                            "is_maintenance_window": schedule.is_maintenance_window,
                            "optimal_windows": optimal_windows,
                            "recommendation": (
                                "Ideal for deployment"
                                if optimal_windows
                                and not schedule.is_maintenance_window
                                else "Avoid - maintenance or limited windows"
                            ),
                        }
                    )

                return {
                    "site_id": site_id,
                    "recommendations": recommendations,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to get scheduling windows: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def get_error_frequency_analysis(
        device_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Analyze error frequency and categorization.

        Args:
            device_id: Optional device filter
            days: Number of days to analyze

        Returns:
            Dict with error trends, categories, and severity distribution
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)

                query = select(ErrorLog).where(ErrorLog.timestamp >= cutoff_date)
                if device_id:
                    query = query.where(ErrorLog.device_id == device_id)

                result = await session.execute(
                    query.order_by(ErrorLog.timestamp.desc())
                )
                errors = result.scalars().all()

                if not errors:
                    return {
                        "status": "no_errors",
                        "message": "No errors recorded in the specified period",
                    }

                # Categorize by type
                by_category = {}
                by_severity = {}

                for error in errors:
                    # By category
                    category = error.category or "unknown"
                    by_category[category] = by_category.get(category, 0) + 1

                    # By severity
                    severity = error.severity or "error"
                    by_severity[severity] = by_severity.get(severity, 0) + 1

                # Calculate error rate per day
                error_rate = len(errors) / days

                return {
                    "device_id": device_id,
                    "period_days": days,
                    "total_errors": len(errors),
                    "error_rate_per_day": round(error_rate, 2),
                    "by_category": by_category,
                    "by_severity": by_severity,
                    "health_status": (
                        "critical"
                        if error_rate > 10
                        else "warning" if error_rate > 5 else "healthy"
                    ),
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to analyze errors: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def get_configuration_impact_analysis(
        site_id: Optional[str] = None,
        days: int = 14,
    ) -> Dict[str, Any]:
        """Analyze the impact of configuration changes on system behavior.

        Args:
            site_id: Optional site filter
            days: Number of days to analyze

        Returns:
            Dict with configuration change frequency and correlation with issues
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)

                # Get configuration changes
                query = select(ConfigurationHistory).where(
                    ConfigurationHistory.changed_at >= cutoff_date
                )
                if site_id:
                    query = query.join(Device).where(Device.site_id == site_id)

                result = await session.execute(
                    query.order_by(ConfigurationHistory.changed_at.desc())
                )
                changes = result.scalars().all()

                if not changes:
                    return {
                        "status": "no_changes",
                        "message": "No configuration changes in the specified period",
                    }

                # Analyze change frequency
                change_count = len(changes)
                change_rate = change_count / days

                # Group by change type
                by_field = {}
                for change in changes:
                    field = change.field_changed or "unknown"
                    by_field[field] = by_field.get(field, 0) + 1

                return {
                    "site_id": site_id,
                    "period_days": days,
                    "total_changes": change_count,
                    "change_rate_per_day": round(change_rate, 2),
                    "changes_by_field": by_field,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to analyze config impact: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
