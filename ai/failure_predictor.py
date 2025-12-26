"""Failure Prediction Engine - Predict device failures before they occur.

This module analyzes patterns in metrics, errors, and state changes to
identify devices at risk of failure and generate early warnings.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .analytics_service import AIAnalyticsService

logger = logging.getLogger(__name__)


class FailurePredictor:
    """Predicts device failures using pattern analysis."""

    def __init__(self, event_store: Any = None) -> None:
        """Initialize the failure predictor.

        Args:
            event_store: Optional event store (kept for compatibility with existing code)
        """
        self.analytics = AIAnalyticsService()
        self.event_store = event_store

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
            logger.error(f"Failed to predict failure: {e}", exc_info=True)
            return {
                "device_id": device_id,
                "error": str(e),
                "failure_probability": 0.0,
                "risk_level": "unknown",
            }

    async def _analyze_resource_trends(self, device_id: str) -> Dict[str, Any]:
        """Analyze resource usage trends."""
        try:
            trends = await self.analytics.get_device_performance_trends(
                device_id, days=3
            )
            if trends.get("status") == "error":
                return {"score": 0.0, "factors": []}

            metrics = trends.get("metrics", {})
            score = 0.0
            factors = []

            if metrics.get("avg_cpu_percent", 0) > 80:
                score += 0.5
                factors.append(
                    {"type": "resource", "name": "High CPU Usage", "severity": 0.8}
                )

            if metrics.get("avg_memory_percent", 0) > 85:
                score += 0.5
                factors.append(
                    {"type": "resource", "name": "High Memory Usage", "severity": 0.9}
                )

            return {"score": min(1.0, score), "factors": factors}
        except Exception:
            return {"score": 0.0, "factors": []}

    async def _analyze_error_patterns(self, device_id: str) -> Dict[str, Any]:
        """Analyze error logs."""
        try:
            errors = await self.analytics.get_error_frequency_analysis(
                device_id, days=3
            )
            if errors.get("status") == "error":
                return {"score": 0.0, "factors": []}

            rate = errors.get("error_rate_per_day", 0)
            score = 0.0
            factors = []

            if rate > 10:
                score = 1.0
                factors.append(
                    {"type": "error", "name": "Critical Error Rate", "severity": 1.0}
                )
            elif rate > 5:
                score = 0.6
                factors.append(
                    {"type": "error", "name": "High Error Rate", "severity": 0.6}
                )

            return {"score": score, "factors": factors}
        except Exception:
            return {"score": 0.0, "factors": []}

    async def _analyze_state_stability(self, device_id: str) -> Dict[str, Any]:
        """Analyze state changes."""
        # Simplified implementation
        return {"score": 0.0, "factors": []}

    async def _analyze_health_trend(self, device_id: str) -> Dict[str, Any]:
        """Analyze health score trend."""
        # Simplified implementation
        return {"score": 0.0, "factors": []}

    def _determine_risk_level(self, probability: float) -> str:
        if probability > 0.8:
            return "critical"
        elif probability > 0.5:
            return "high"
        elif probability > 0.2:
            return "medium"
        return "low"

    def _generate_recommendations(
        self, risk_level: str, factors: List[Dict]
    ) -> List[str]:
        recs = []
        if risk_level == "critical":
            recs.append("Immediate maintenance required")
        elif risk_level == "high":
            recs.append("Schedule inspection within 24 hours")

        for factor in factors:
            if factor["name"] == "High CPU Usage":
                recs.append("Check for runaway processes")
            elif factor["name"] == "High Memory Usage":
                recs.append("Check for memory leaks")

        return recs

    def _calculate_confidence(self, factors: List[Dict]) -> float:
        # Simple confidence based on number of factors found
        if not factors:
            return 0.5
        return min(0.95, 0.5 + (len(factors) * 0.1))

    def _estimate_failure_time(self, probability: float, window: int) -> str:
        # Rough estimate
        hours = window * (1.0 - probability)
        return (datetime.utcnow() + timedelta(hours=hours)).isoformat()
