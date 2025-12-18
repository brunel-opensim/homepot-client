"""Failure Prediction Engine - Predict device failures before they occur.

This module analyzes patterns in metrics, errors, and state changes to
identify devices at risk of failure and generate early warnings.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select

from homepot.ai.analytics_service import AIAnalyticsService
from homepot.app.models.AnalyticsModel import (
    DeviceMetrics,
    DeviceStateHistory,
    ErrorLog,
)
from homepot.database import get_database_service

logger = logging.getLogger(__name__)


class FailurePredictor:
    """Predicts device failures using pattern analysis."""

    def __init__(self):
        """Initialize the failure predictor."""
        self.analytics = AIAnalyticsService()

    async def predict_device_failure(
        self,
        device_id: str,
        prediction_window_hours: int = 24,
    ) -> Dict[str, Any]:
        """Predict likelihood of device failure in the next N hours.

        Args:
            device_id: Device to analyze
            prediction_window_hours: Prediction time window (default: 24h)

        Returns:
            Dict with failure probability, risk level, and contributing factors
        """
        try:
            risk_score = 0.0
            risk_factors = []

            # Factor 1: Resource trends (CPU/Memory/Disk)
            resource_risk = await self._analyze_resource_trends(device_id)
            risk_score += resource_risk["score"] * 0.35  # 35% weight
            if resource_risk["score"] > 0:
                risk_factors.extend(resource_risk["factors"])

            # Factor 2: Error frequency and severity
            error_risk = await self._analyze_error_patterns(device_id)
            risk_score += error_risk["score"] * 0.30  # 30% weight
            if error_risk["score"] > 0:
                risk_factors.extend(error_risk["factors"])

            # Factor 3: State transition instability
            state_risk = await self._analyze_state_stability(device_id)
            risk_score += state_risk["score"] * 0.20  # 20% weight
            if state_risk["score"] > 0:
                risk_factors.extend(state_risk["factors"])

            # Factor 4: Historical health score
            health_risk = await self._analyze_health_trend(device_id)
            risk_score += health_risk["score"] * 0.15  # 15% weight
            if health_risk["score"] > 0:
                risk_factors.extend(health_risk["factors"])

            # Normalize to 0-1 range
            failure_probability = min(1.0, max(0.0, risk_score))

            # Determine risk level
            risk_level = self._determine_risk_level(failure_probability)

            # Generate recommendations
            recommendations = self._generate_recommendations(risk_level, risk_factors)

            return {
                "device_id": device_id,
                "failure_probability": round(failure_probability, 3),
                "risk_level": risk_level,
                "prediction_window_hours": prediction_window_hours,
                "confidence": self._calculate_confidence(risk_factors),
                "risk_factors": sorted(
                    risk_factors, key=lambda x: x.get("severity", 0), reverse=True
                ),
                "recommendations": recommendations,
                "prediction_timestamp": datetime.utcnow().isoformat(),
                "predicted_failure_time": (
                    self._estimate_failure_time(
                        failure_probability, prediction_window_hours
                    )
                    if failure_probability > 0.5
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Failed to predict device failure: {e}", exc_info=True)
            return {
                "device_id": device_id,
                "status": "error",
                "message": str(e),
                "failure_probability": 0.0,
                "risk_level": "unknown",
            }

    async def identify_at_risk_devices(
        self,
        site_id: Optional[str] = None,
        min_risk_level: str = "medium",
    ) -> Dict[str, Any]:
        """Identify all devices currently at risk of failure.

        Args:
            site_id: Optional site filter
            min_risk_level: Minimum risk level to include (low, medium, high, critical)

        Returns:
            Dict with list of at-risk devices and summary statistics
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Get all active devices
                from homepot.models import Device

                query = select(Device).where(Device.is_active == True)  # noqa: E712
                if site_id:
                    query = query.where(Device.site_id == site_id)

                result = await session.execute(query)
                devices = result.scalars().all()

                # Analyze each device
                at_risk_devices = []
                risk_threshold = {
                    "low": 0.3,
                    "medium": 0.5,
                    "high": 0.7,
                    "critical": 0.85,
                }.get(min_risk_level, 0.5)

                for device in devices:
                    prediction = await self.predict_device_failure(device.device_id)

                    if prediction.get("failure_probability", 0) >= risk_threshold:
                        at_risk_devices.append(
                            {
                                "device_id": device.device_id,
                                "device_name": device.name,
                                "site_id": device.site_id,
                                "failure_probability": prediction[
                                    "failure_probability"
                                ],
                                "risk_level": prediction["risk_level"],
                                "top_risk_factors": prediction.get("risk_factors", [])[
                                    :3
                                ],
                                "recommendations": prediction.get(
                                    "recommendations", []
                                )[:2],
                            }
                        )

                # Sort by risk
                at_risk_devices.sort(
                    key=lambda x: x["failure_probability"], reverse=True
                )

                # Summary statistics
                risk_distribution = {
                    "critical": sum(
                        1 for d in at_risk_devices if d["risk_level"] == "critical"
                    ),
                    "high": sum(
                        1 for d in at_risk_devices if d["risk_level"] == "high"
                    ),
                    "medium": sum(
                        1 for d in at_risk_devices if d["risk_level"] == "medium"
                    ),
                    "low": sum(1 for d in at_risk_devices if d["risk_level"] == "low"),
                }

                return {
                    "site_id": site_id,
                    "total_devices_analyzed": len(devices),
                    "at_risk_count": len(at_risk_devices),
                    "risk_distribution": risk_distribution,
                    "at_risk_devices": at_risk_devices,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to identify at-risk devices: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "at_risk_devices": []}

    async def _analyze_resource_trends(self, device_id: str) -> Dict[str, Any]:
        """Analyze resource usage trends."""
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Get last hour of metrics
                cutoff = datetime.utcnow() - timedelta(hours=1)

                result = await session.execute(
                    select(DeviceMetrics)
                    .where(
                        and_(
                            DeviceMetrics.device_id == device_id,
                            DeviceMetrics.timestamp >= cutoff,
                        )
                    )
                    .order_by(DeviceMetrics.timestamp.asc())
                )
                metrics = result.scalars().all()

                if len(metrics) < 10:
                    return {"score": 0.0, "factors": []}

                score = 0.0
                factors = []

                # Check CPU trend
                recent_cpu = [m.cpu_percent or 0 for m in metrics[-10:]]
                avg_cpu = sum(recent_cpu) / len(recent_cpu)

                if avg_cpu > 90:
                    score += 0.4
                    factors.append(
                        {
                            "category": "resource",
                            "issue": "critical_cpu_usage",
                            "severity": 3,
                            "description": f"CPU usage critically high: {avg_cpu:.1f}%",
                            "metric_value": avg_cpu,
                        }
                    )
                elif avg_cpu > 80:
                    score += 0.2
                    factors.append(
                        {
                            "category": "resource",
                            "issue": "high_cpu_usage",
                            "severity": 2,
                            "description": f"CPU usage elevated: {avg_cpu:.1f}%",
                            "metric_value": avg_cpu,
                        }
                    )

                # Check memory trend
                recent_memory = [m.memory_percent or 0 for m in metrics[-10:]]
                avg_memory = sum(recent_memory) / len(recent_memory)

                if avg_memory > 95:
                    score += 0.4
                    factors.append(
                        {
                            "category": "resource",
                            "issue": "critical_memory_usage",
                            "severity": 3,
                            "description": f"Memory usage critically high: {avg_memory:.1f}%",
                            "metric_value": avg_memory,
                        }
                    )
                elif avg_memory > 85:
                    score += 0.2
                    factors.append(
                        {
                            "category": "resource",
                            "issue": "high_memory_usage",
                            "severity": 2,
                            "description": f"Memory usage elevated: {avg_memory:.1f}%",
                            "metric_value": avg_memory,
                        }
                    )

                # Check disk trend
                recent_disk = [m.disk_percent or 0 for m in metrics[-10:]]
                avg_disk = sum(recent_disk) / len(recent_disk)

                if avg_disk > 95:
                    score += 0.3
                    factors.append(
                        {
                            "category": "resource",
                            "issue": "critical_disk_usage",
                            "severity": 3,
                            "description": f"Disk usage critically high: {avg_disk:.1f}%",
                            "metric_value": avg_disk,
                        }
                    )
                elif avg_disk > 90:
                    score += 0.15
                    factors.append(
                        {
                            "category": "resource",
                            "issue": "high_disk_usage",
                            "severity": 2,
                            "description": f"Disk usage elevated: {avg_disk:.1f}%",
                            "metric_value": avg_disk,
                        }
                    )

                return {"score": min(1.0, score), "factors": factors}

        except Exception as e:
            logger.error(f"Resource trend analysis failed: {e}")
            return {"score": 0.0, "factors": []}

    async def _analyze_error_patterns(self, device_id: str) -> Dict[str, Any]:
        """Analyze error frequency and severity."""
        try:
            errors = await self.analytics.get_error_frequency_analysis(
                device_id, days=1
            )

            if errors.get("status") == "no_errors":
                return {"score": 0.0, "factors": []}

            score = 0.0
            factors = []

            error_rate = errors.get("error_rate_per_day", 0)
            by_severity = errors.get("by_severity", {})

            # Critical errors are highest priority
            critical_count = by_severity.get("critical", 0)
            if critical_count > 0:
                score += 0.5
                factors.append(
                    {
                        "category": "errors",
                        "issue": "critical_errors_present",
                        "severity": 3,
                        "description": f"{critical_count} critical errors in last 24h",
                        "metric_value": critical_count,
                    }
                )

            # High error rate
            if error_rate > 20:
                score += 0.4
                factors.append(
                    {
                        "category": "errors",
                        "issue": "very_high_error_rate",
                        "severity": 3,
                        "description": f"Extremely high error rate: {error_rate:.1f}/day",
                        "metric_value": error_rate,
                    }
                )
            elif error_rate > 10:
                score += 0.2
                factors.append(
                    {
                        "category": "errors",
                        "issue": "high_error_rate",
                        "severity": 2,
                        "description": f"High error rate: {error_rate:.1f}/day",
                        "metric_value": error_rate,
                    }
                )

            return {"score": min(1.0, score), "factors": factors}

        except Exception as e:
            logger.error(f"Error pattern analysis failed: {e}")
            return {"score": 0.0, "factors": []}

    async def _analyze_state_stability(self, device_id: str) -> Dict[str, Any]:
        """Analyze device state transition patterns."""
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Get last 6 hours of state history
                cutoff = datetime.utcnow() - timedelta(hours=6)

                result = await session.execute(
                    select(DeviceStateHistory)
                    .where(
                        and_(
                            DeviceStateHistory.device_id == device_id,
                            DeviceStateHistory.changed_at >= cutoff,
                        )
                    )
                    .order_by(DeviceStateHistory.changed_at.asc())
                )
                transitions = result.scalars().all()

                if len(transitions) < 2:
                    return {"score": 0.0, "factors": []}

                score = 0.0
                factors = []

                # Count transitions
                transition_count = len(transitions)

                # Frequent transitions indicate instability
                if transition_count > 20:
                    score += 0.5
                    factors.append(
                        {
                            "category": "stability",
                            "issue": "frequent_state_changes",
                            "severity": 3,
                            "description": f"Excessive state transitions: {transition_count} in 6h",
                            "metric_value": transition_count,
                        }
                    )
                elif transition_count > 10:
                    score += 0.25
                    factors.append(
                        {
                            "category": "stability",
                            "issue": "unstable_state",
                            "severity": 2,
                            "description": f"Frequent state transitions: {transition_count} in 6h",
                            "metric_value": transition_count,
                        }
                    )

                # Check for error states
                error_states = [
                    t for t in transitions if "error" in t.new_state.lower()
                ]
                if error_states:
                    score += 0.3
                    factors.append(
                        {
                            "category": "stability",
                            "issue": "error_state_detected",
                            "severity": 3,
                            "description": f"Device entered error state {len(error_states)} times",
                            "metric_value": len(error_states),
                        }
                    )

                return {"score": min(1.0, score), "factors": factors}

        except Exception as e:
            logger.error(f"State stability analysis failed: {e}")
            return {"score": 0.0, "factors": []}

    async def _analyze_health_trend(self, device_id: str) -> Dict[str, Any]:
        """Analyze overall health score trend."""
        try:
            perf = await self.analytics.get_device_performance_trends(device_id, days=7)

            if perf.get("status") == "no_data":
                return {"score": 0.0, "factors": []}

            health_score = perf.get("health_score", 70)
            score = 0.0
            factors = []

            if health_score < 30:
                score += 0.4
                factors.append(
                    {
                        "category": "health",
                        "issue": "poor_health_score",
                        "severity": 3,
                        "description": f"Health score critically low: {health_score:.1f}/100",
                        "metric_value": health_score,
                    }
                )
            elif health_score < 50:
                score += 0.2
                factors.append(
                    {
                        "category": "health",
                        "issue": "low_health_score",
                        "severity": 2,
                        "description": f"Health score below normal: {health_score:.1f}/100",
                        "metric_value": health_score,
                    }
                )

            return {"score": score, "factors": factors}

        except Exception as e:
            logger.error(f"Health trend analysis failed: {e}")
            return {"score": 0.0, "factors": []}

    def _determine_risk_level(self, probability: float) -> str:
        """Determine risk level from probability."""
        if probability >= 0.85:
            return "critical"
        elif probability >= 0.7:
            return "high"
        elif probability >= 0.5:
            return "medium"
        elif probability >= 0.3:
            return "low"
        else:
            return "minimal"

    def _calculate_confidence(self, risk_factors: List[Dict]) -> float:
        """Calculate confidence in prediction based on available data."""
        if not risk_factors:
            return 0.3  # Low confidence with no data

        # More factors = higher confidence
        factor_count = len(risk_factors)

        if factor_count >= 5:
            return 0.95
        elif factor_count >= 3:
            return 0.85
        elif factor_count >= 2:
            return 0.75
        else:
            return 0.6

    def _generate_recommendations(
        self, risk_level: str, risk_factors: List[Dict]
    ) -> List[str]:
        """Generate actionable recommendations based on risk assessment."""
        recommendations = []

        if risk_level == "critical":
            recommendations.append("URGENT: Immediate intervention required")
            recommendations.append("Consider taking device offline for maintenance")
            recommendations.append("Schedule replacement or repair ASAP")
        elif risk_level == "high":
            recommendations.append("Schedule maintenance within 24 hours")
            recommendations.append("Avoid scheduling critical jobs to this device")
            recommendations.append("Monitor device closely")
        elif risk_level == "medium":
            recommendations.append("Schedule preventive maintenance within 3 days")
            recommendations.append("Reduce workload if possible")
        elif risk_level == "low":
            recommendations.append("Continue normal monitoring")
            recommendations.append("Consider preventive maintenance during next window")

        # Add specific recommendations based on factors
        for factor in risk_factors[:3]:  # Top 3 factors
            issue = factor.get("issue", "")

            if "cpu" in issue:
                recommendations.append("Investigate CPU-intensive processes")
            elif "memory" in issue:
                recommendations.append("Check for memory leaks or restart services")
            elif "disk" in issue:
                recommendations.append("Clean up disk space or expand storage")
            elif "error" in issue:
                recommendations.append("Review error logs and address root causes")
            elif "state" in issue:
                recommendations.append("Investigate network or connectivity issues")

        return list(set(recommendations))  # Remove duplicates

    def _estimate_failure_time(self, probability: float, window_hours: int) -> str:
        """Estimate when failure might occur based on probability."""
        if probability >= 0.9:
            estimated_hours = window_hours * 0.2  # 20% into window
        elif probability >= 0.7:
            estimated_hours = window_hours * 0.5  # 50% into window
        else:
            estimated_hours = window_hours * 0.8  # 80% into window

        estimated_time = datetime.utcnow() + timedelta(hours=estimated_hours)
        return estimated_time.isoformat()
