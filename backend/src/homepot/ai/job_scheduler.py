"""Predictive Job Scheduler - AI-powered job timing optimization.

This module uses machine learning insights from analytics data to recommend
optimal times for job execution, maximizing success probability and
minimizing business disruption.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homepot.ai.analytics_service import AIAnalyticsService

logger = logging.getLogger(__name__)


class PredictiveJobScheduler:
    """AI-powered job scheduler that optimizes execution timing."""

    def __init__(self) -> None:
        """Initialize the predictive scheduler."""
        self.analytics = AIAnalyticsService()

    async def recommend_execution_time(
        self,
        site_id: str,
        job_priority: str = "medium",
        earliest_start: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Recommend optimal execution time for a job.

        Args:
            site_id: Target site identifier
            job_priority: Job priority (low, medium, high, critical)
            earliest_start: Earliest acceptable start time (default: now)

        Returns:
            Dict with recommended time, success probability, and reasoning
        """
        if earliest_start is None:
            earliest_start = datetime.utcnow()

        try:
            # Get site operating schedule
            scheduling_windows = await self.analytics.get_optimal_scheduling_windows(
                site_id
            )

            if scheduling_windows.get("status") == "no_schedule":
                # No schedule data - recommend immediate execution for critical jobs
                if job_priority == "critical":
                    return {
                        "recommended_time": earliest_start.isoformat(),
                        "confidence": 0.5,
                        "reasoning": "No schedule data - executing immediately due to critical priority",
                        "alternative_times": [],
                    }
                else:
                    # Default to early morning
                    tomorrow_morning = (earliest_start + timedelta(days=1)).replace(
                        hour=8, minute=0, second=0
                    )
                    return {
                        "recommended_time": tomorrow_morning.isoformat(),
                        "confidence": 0.6,
                        "reasoning": "No schedule data - defaulting to early morning execution",
                        "alternative_times": [],
                    }

            # Get historical job patterns
            job_patterns = await self.analytics.get_job_outcome_patterns(
                site_id, days=30
            )

            # Find optimal windows
            recommendations = scheduling_windows.get("recommendations", [])
            current_day = earliest_start.weekday()  # 0=Monday

            # Priority-based scheduling strategy
            if job_priority == "critical":
                # Critical jobs: Execute ASAP, avoid only closed hours
                for rec in recommendations:
                    if rec["day_of_week"] == current_day and rec["status"] == "open":
                        return {
                            "recommended_time": earliest_start.isoformat(),
                            "confidence": 0.9,
                            "reasoning": "Critical priority - executing immediately during open hours",
                            "site_status": rec,
                            "alternative_times": [],
                        }
                # If today is closed, find next open day
                return await self._find_next_open_slot(
                    recommendations, earliest_start, "Critical priority"
                )

            elif job_priority == "high":
                # High priority: Execute within 4 hours, prefer off-peak
                target_day_rec = next(
                    (r for r in recommendations if r["day_of_week"] == current_day),
                    None,
                )

                if target_day_rec and target_day_rec.get("optimal_windows"):
                    # Try to fit in optimal window today
                    optimal = target_day_rec["optimal_windows"][0]
                    recommended_time = self._parse_optimal_window_time(
                        earliest_start, optimal["start"]
                    )

                    # If window is within 4 hours, use it
                    if recommended_time < earliest_start + timedelta(hours=4):
                        return {
                            "recommended_time": recommended_time.isoformat(),
                            "confidence": 0.85,
                            "reasoning": f"High priority - optimal window: {optimal['reason']}",
                            "site_status": target_day_rec,
                            "alternative_times": self._get_alternative_times(
                                target_day_rec, earliest_start
                            ),
                        }

                # No optimal window soon - execute in 2 hours
                return {
                    "recommended_time": (
                        earliest_start + timedelta(hours=2)
                    ).isoformat(),
                    "confidence": 0.7,
                    "reasoning": "High priority - executing within 2 hours",
                    "alternative_times": [],
                }

            else:  # medium or low priority
                # Find best optimal window in next 7 days
                best_recommendation = await self._find_best_window_in_week(
                    recommendations,
                    earliest_start,
                    job_patterns,
                )

                return best_recommendation

        except Exception as e:
            logger.error(f"Failed to recommend execution time: {e}", exc_info=True)
            # Fallback recommendation
            return {
                "recommended_time": (earliest_start + timedelta(hours=2)).isoformat(),
                "confidence": 0.5,
                "reasoning": f"Error in analysis - using fallback (2 hours delay): {str(e)}",
                "alternative_times": [],
            }

    async def calculate_success_probability(
        self,
        site_id: str,
        device_id: str,
        scheduled_time: datetime,
    ) -> Dict[str, Any]:
        """Calculate probability of job success at given time.

        Args:
            site_id: Target site
            device_id: Target device
            scheduled_time: Proposed execution time

        Returns:
            Dict with probability score (0-1) and factors analysis
        """
        try:
            probability = 1.0
            factors = []

            # Factor 1: Device health (40% weight)
            device_perf = await self.analytics.get_device_performance_trends(
                device_id, days=7
            )

            if device_perf.get("status") != "error":
                health_score = device_perf.get("health_score", 70) / 100
                probability *= 0.6 + 0.4 * health_score  # Scale 0.6-1.0
                factors.append(
                    {
                        "factor": "device_health",
                        "weight": 0.4,
                        "score": health_score,
                        "impact": (
                            "positive"
                            if health_score > 0.8
                            else "neutral" if health_score > 0.6 else "negative"
                        ),
                    }
                )

            # Factor 2: Historical success rate at this hour (30% weight)
            job_patterns = await self.analytics.get_job_outcome_patterns(
                site_id, days=30
            )

            if job_patterns.get("status") != "error":
                hour = scheduled_time.hour
                optimal_hours = job_patterns.get("optimal_hours", [])
                hour_data = next((h for h in optimal_hours if h["hour"] == hour), None)

                if hour_data:
                    hour_success = hour_data["success_rate"] / 100
                    probability *= 0.7 + 0.3 * hour_success
                    factors.append(
                        {
                            "factor": "historical_success_rate",
                            "weight": 0.3,
                            "score": hour_success,
                            "impact": "positive" if hour_success > 0.9 else "neutral",
                        }
                    )
                else:
                    # Unknown hour - neutral
                    probability *= 0.85
                    factors.append(
                        {
                            "factor": "historical_success_rate",
                            "weight": 0.3,
                            "score": 0.85,
                            "impact": "neutral",
                            "note": "Limited historical data for this hour",
                        }
                    )

            # Factor 3: Site operating schedule (20% weight)
            day_of_week = scheduled_time.weekday()
            scheduling = await self.analytics.get_optimal_scheduling_windows(
                site_id, day_of_week
            )

            if scheduling.get("status") != "error":
                recs = scheduling.get("recommendations", [])
                day_rec = next(
                    (r for r in recs if r["day_of_week"] == day_of_week), None
                )

                if day_rec:
                    if day_rec["status"] == "closed":
                        probability *= 0.3  # Major penalty for closed days
                        factors.append(
                            {
                                "factor": "site_schedule",
                                "weight": 0.2,
                                "score": 0.3,
                                "impact": "negative",
                                "note": "Site is closed",
                            }
                        )
                    elif day_rec.get("is_maintenance_window"):
                        probability *= 0.5  # Penalty for maintenance
                        factors.append(
                            {
                                "factor": "site_schedule",
                                "weight": 0.2,
                                "score": 0.5,
                                "impact": "negative",
                                "note": "Maintenance window",
                            }
                        )
                    elif day_rec.get("optimal_windows"):
                        probability *= 1.0  # Neutral/positive for open days
                        factors.append(
                            {
                                "factor": "site_schedule",
                                "weight": 0.2,
                                "score": 1.0,
                                "impact": "positive",
                                "note": "Within operating hours",
                            }
                        )

            # Factor 4: Recent error rate (10% weight)
            errors = await self.analytics.get_error_frequency_analysis(
                device_id, days=7
            )

            if errors.get("status") != "error":
                error_rate = errors.get("error_rate_per_day", 0)
                if error_rate > 10:
                    probability *= 0.6
                    factors.append(
                        {
                            "factor": "error_rate",
                            "weight": 0.1,
                            "score": 0.6,
                            "impact": "negative",
                            "note": f"High error rate: {error_rate}/day",
                        }
                    )
                elif error_rate > 5:
                    probability *= 0.8
                    factors.append(
                        {
                            "factor": "error_rate",
                            "weight": 0.1,
                            "score": 0.8,
                            "impact": "neutral",
                            "note": f"Moderate error rate: {error_rate}/day",
                        }
                    )
                else:
                    factors.append(
                        {
                            "factor": "error_rate",
                            "weight": 0.1,
                            "score": 1.0,
                            "impact": "positive",
                            "note": "Low error rate",
                        }
                    )

            # Ensure probability stays in valid range
            probability = max(0.1, min(1.0, probability))

            return {
                "site_id": site_id,
                "device_id": device_id,
                "scheduled_time": scheduled_time.isoformat(),
                "success_probability": round(probability, 3),
                "confidence_level": (
                    "high"
                    if probability > 0.8
                    else "medium" if probability > 0.6 else "low"
                ),
                "factors": factors,
                "recommendation": self._get_probability_recommendation(probability),
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to calculate success probability: {e}", exc_info=True)
            return {
                "site_id": site_id,
                "device_id": device_id,
                "scheduled_time": scheduled_time.isoformat(),
                "success_probability": 0.7,
                "confidence_level": "low",
                "recommendation": "Proceed with caution - analysis incomplete",
                "error": str(e),
            }

    def _parse_optimal_window_time(
        self, base_date: datetime, time_str: str
    ) -> datetime:
        """Parse optimal window time string and combine with base date."""
        try:
            hour, minute = map(int, time_str.split(":"))
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except Exception:
            return base_date

    def _get_alternative_times(
        self, day_recommendation: Dict[str, Any], earliest_start: datetime
    ) -> List[Dict[str, Any]]:
        """Get list of alternative execution times."""
        alternatives = []

        optimal_windows = day_recommendation.get("optimal_windows", [])
        for window in optimal_windows[:3]:  # Top 3 windows
            time = self._parse_optimal_window_time(earliest_start, window["start"])
            alternatives.append({"time": time.isoformat(), "reason": window["reason"]})

        return alternatives

    async def _find_next_open_slot(
        self,
        recommendations: List[Dict[str, Any]],
        earliest_start: datetime,
        reason: str,
    ) -> Dict[str, Any]:
        """Find next available open slot."""
        current_day = earliest_start.weekday()

        # Check next 7 days
        for offset in range(7):
            check_day = (current_day + offset) % 7
            day_rec = next(
                (r for r in recommendations if r["day_of_week"] == check_day), None
            )

            if (
                day_rec
                and day_rec["status"] == "open"
                and not day_rec.get("is_maintenance_window")
            ):
                target_date = earliest_start + timedelta(days=offset)

                # Use first optimal window if available
                if day_rec.get("optimal_windows"):
                    optimal = day_rec["optimal_windows"][0]
                    recommended_time = self._parse_optimal_window_time(
                        target_date, optimal["start"]
                    )
                else:
                    # Default to 9 AM
                    recommended_time = target_date.replace(hour=9, minute=0, second=0)

                return {
                    "recommended_time": recommended_time.isoformat(),
                    "confidence": 0.75,
                    "reasoning": f"{reason} - next available open slot",
                    "site_status": day_rec,
                    "alternative_times": self._get_alternative_times(
                        day_rec, target_date
                    ),
                }

        # Fallback if no open day found (shouldn't happen)
        return {
            "recommended_time": (earliest_start + timedelta(days=1)).isoformat(),
            "confidence": 0.4,
            "reasoning": "No optimal window found - using fallback",
            "alternative_times": [],
        }

    async def _find_best_window_in_week(
        self,
        recommendations: List[Dict[str, Any]],
        earliest_start: datetime,
        job_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Find best execution window in the next 7 days."""
        current_day = earliest_start.weekday()
        best_score = 0.0
        best_recommendation = None

        for offset in range(7):
            check_day = (current_day + offset) % 7
            day_rec = next(
                (r for r in recommendations if r["day_of_week"] == check_day), None
            )

            if not day_rec or day_rec["status"] != "open":
                continue

            # Score this day
            score = 1.0

            # Penalty for maintenance
            if day_rec.get("is_maintenance_window"):
                score *= 0.3

            # Bonus for optimal windows
            if day_rec.get("optimal_windows"):
                score *= 1.5

            # Penalty for high volume
            expected_vol = day_rec.get("expected_transaction_volume", 0)
            if expected_vol > 600:
                score *= 0.7
            elif expected_vol > 400:
                score *= 0.85

            # Bonus for sooner dates (but not too much)
            if offset == 0:
                score *= 1.2
            elif offset <= 2:
                score *= 1.1

            if score > best_score:
                best_score = score
                target_date = earliest_start + timedelta(days=offset)

                # Use first optimal window
                if day_rec.get("optimal_windows"):
                    optimal = day_rec["optimal_windows"][0]
                    recommended_time = self._parse_optimal_window_time(
                        target_date, optimal["start"]
                    )
                    reasoning = f"Optimal window: {optimal['reason']}"
                else:
                    recommended_time = target_date.replace(hour=9, minute=0, second=0)
                    reasoning = "Earliest available time"

                best_recommendation = {
                    "recommended_time": recommended_time.isoformat(),
                    "confidence": round(min(0.95, best_score * 0.8), 2),
                    "reasoning": reasoning,
                    "site_status": day_rec,
                    "alternative_times": self._get_alternative_times(
                        day_rec, target_date
                    ),
                }

        if best_recommendation:
            return best_recommendation

        # Fallback
        return {
            "recommended_time": (earliest_start + timedelta(hours=2)).isoformat(),
            "confidence": 0.5,
            "reasoning": "No optimal window identified - using default delay",
            "alternative_times": [],
        }

    def _get_probability_recommendation(self, probability: float) -> str:
        """Get recommendation text based on probability."""
        if probability >= 0.9:
            return "Excellent conditions - proceed confidently"
        elif probability >= 0.8:
            return "Good conditions - recommended to proceed"
        elif probability >= 0.7:
            return "Acceptable conditions - proceed with standard monitoring"
        elif probability >= 0.6:
            return "Fair conditions - consider rescheduling if possible"
        elif probability >= 0.5:
            return "Marginal conditions - recommended to reschedule"
        else:
            return "Poor conditions - strongly recommend rescheduling"
