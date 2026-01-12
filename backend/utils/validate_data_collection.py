#!/usr/bin/env python3
"""
HOMEPOT Data Collection Validation Script

Purpose: Automated validation of analytics data collection for 3-5 day runs.
         Developers can run this script to verify all 8 analytics tables are
         collecting data properly before AI training.

Usage:
    python scripts/validate_data_collection.py

    # Or with custom parameters:
    python scripts/validate_data_collection.py --min-days 3 --report report.json

What it checks:
    1. Backend service is running
    2. All 8 analytics tables have data
    3. Data freshness (recent entries)
    4. Data quality (reasonable values)
    5. Collection rates (per hour/day)
    6. Agent activity
    7. Gaps in data collection

Output:
    - Console report with color coding
    - Optional JSON report for CI/CD
    - Exit code 0 = all good, 1 = issues found
"""

import argparse
import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import func, select

from homepot.app.models.AnalyticsModel import (
    APIRequestLog,
    ConfigurationHistory,
    DeviceMetrics,
    DeviceStateHistory,
    ErrorLog,
    JobOutcome,
    SiteOperatingSchedule,
    UserActivity,
)
from homepot.database import get_database_service


def utc_now():
    """Get current UTC time (timezone-naive for database compatibility)."""
    return datetime.utcnow()


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class DataCollectionValidator:
    """Validates analytics data collection for AI training."""

    def __init__(self, min_days: int = 3):
        """Initialize validator.

        Args:
            min_days: Minimum days of data required
        """
        self.min_days = min_days
        self.results = {
            "timestamp": utc_now().isoformat(),
            "min_days_required": min_days,
            "checks": [],
            "overall_status": "unknown",
            "issues": [],
            "recommendations": [],
        }

    async def run_validation(self) -> Dict[str, Any]:
        """Run complete validation suite."""
        print(f"\n{Colors.BOLD}{'='*70}")
        print(f"HOMEPOT Data Collection Validation")
        print(f"{'='*70}{Colors.END}\n")
        print(f"Minimum data requirement: {self.min_days} days\n")

        # Check 1: Database connectivity
        await self._check_database_connectivity()

        # Check 2: Agent activity
        await self._check_agent_activity()

        # Check 3: All 8 analytics tables
        await self._check_device_metrics()
        await self._check_job_outcomes()
        await self._check_device_state_history()
        await self._check_error_logs()
        await self._check_configuration_history()
        await self._check_site_schedules()
        await self._check_api_request_logs()
        await self._check_user_activities()

        # Check 4: Data quality
        await self._check_data_quality()

        # Check 5: Collection gaps
        await self._check_collection_gaps()

        # Determine overall status
        self._determine_overall_status()

        # Print summary
        self._print_summary()

        return self.results

    async def _check_database_connectivity(self):
        """Check if database is accessible."""
        check_name = "Database Connectivity"
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Simple query to test connection
                await session.execute(select(1))

            self._add_check_result(
                check_name, "passed", "Database connection successful"
            )
            print(f"{Colors.GREEN}✓{Colors.END} {check_name}: Connected")
        except Exception as e:
            self._add_check_result(check_name, "failed", f"Cannot connect: {str(e)}")
            self.results["issues"].append(
                "Database not accessible. Ensure PostgreSQL is running and credentials are correct."
            )
            print(f"{Colors.RED}✗{Colors.END} {check_name}: {str(e)}")

    async def _check_agent_activity(self):
        """Check if agents are running and active."""
        check_name = "Agent Activity"
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Check device count
                from homepot.models import Device

                result = await session.execute(
                    select(func.count(Device.device_id)).where(Device.is_active == True)
                )
                active_devices = result.scalar()

                if active_devices == 0:
                    self._add_check_result(
                        check_name, "warning", "No active devices found"
                    )
                    self.results["issues"].append(
                        "No active devices. Start agents with: uvicorn homepot.main:app"
                    )
                    print(
                        f"{Colors.YELLOW}⚠{Colors.END} {check_name}: No active devices"
                    )
                else:
                    self._add_check_result(
                        check_name, "passed", f"{active_devices} active devices found"
                    )
                    print(
                        f"{Colors.GREEN}✓{Colors.END} {check_name}: {active_devices} devices active"
                    )
        except Exception as e:
            self._add_check_result(check_name, "failed", str(e))
            print(f"{Colors.RED}✗{Colors.END} {check_name}: {str(e)}")

    async def _check_device_metrics(self):
        """Validate device_metrics table."""
        await self._check_table(
            "Device Metrics",
            DeviceMetrics,
            DeviceMetrics.timestamp,
            # Smart Filtering enabled:
            # - Snapshot every 5 min = 12/hr = 288/day
            # - Plus significant changes
            # We set expectation to the snapshot baseline to avoid false warnings.
            expected_per_day=288,
            critical=True,
        )

    async def _check_job_outcomes(self):
        """Validate job_outcomes table."""
        await self._check_table(
            "Job Outcomes",
            JobOutcome,
            JobOutcome.timestamp,
            expected_per_day=5,  # At least a few jobs per day
            critical=True,
        )

    async def _check_device_state_history(self):
        """Validate device_state_history table."""
        await self._check_table(
            "Device State History",
            DeviceStateHistory,
            DeviceStateHistory.timestamp,
            expected_per_day=2,  # At least some state changes
            critical=True,
        )

    async def _check_error_logs(self):
        """Validate error_logs table."""
        await self._check_table(
            "Error Logs",
            ErrorLog,
            ErrorLog.timestamp,
            expected_per_day=1,  # May have errors
            critical=False,  # Not critical if no errors
        )

    async def _check_configuration_history(self):
        """Validate configuration_history table."""
        await self._check_table(
            "Configuration History",
            ConfigurationHistory,
            ConfigurationHistory.timestamp,
            expected_per_day=1,  # Config changes
            critical=False,
        )

    async def _check_site_schedules(self):
        """Validate site_operating_schedules table."""
        check_name = "Site Operating Schedules"
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                result = await session.execute(
                    select(func.count(SiteOperatingSchedule.id))
                )
                count = result.scalar()

                if count == 0:
                    self._add_check_result(
                        check_name, "warning", "No schedules configured"
                    )
                    self.results["recommendations"].append(
                        "Configure site schedules using: python utils/populate_schedules.py"
                    )
                    print(
                        f"{Colors.YELLOW}⚠{Colors.END} {check_name}: No schedules (run populate_schedules.py)"
                    )
                elif count < 7:
                    self._add_check_result(
                        check_name, "warning", f"Only {count}/7 days configured"
                    )
                    print(
                        f"{Colors.YELLOW}⚠{Colors.END} {check_name}: {count}/7 days configured"
                    )
                else:
                    self._add_check_result(
                        check_name, "passed", f"{count} schedules configured"
                    )
                    print(
                        f"{Colors.GREEN}✓{Colors.END} {check_name}: {count} schedules configured"
                    )
        except Exception as e:
            self._add_check_result(check_name, "failed", str(e))
            print(f"{Colors.RED}✗{Colors.END} {check_name}: {str(e)}")

    async def _check_api_request_logs(self):
        """Validate api_request_logs table."""
        await self._check_table(
            "API Request Logs",
            APIRequestLog,
            APIRequestLog.timestamp,
            expected_per_day=100,  # At least some API activity
            critical=False,  # Not critical for AI, but useful for monitoring
        )

    async def _check_user_activities(self):
        """Validate user_activities table."""
        await self._check_table(
            "User Activities",
            UserActivity,
            UserActivity.timestamp,
            expected_per_day=50,  # Some user interactions
            critical=False,  # Not critical for device AI, useful for UX analytics
        )

    async def _check_table(
        self,
        name: str,
        model,
        timestamp_field,
        expected_per_day: int,
        critical: bool = True,
    ):
        """Generic table validation."""
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Total count
                result = await session.execute(select(func.count()).select_from(model))
                total_count = result.scalar()

                # Recent count (last 24h)
                cutoff = utc_now() - timedelta(hours=24)
                result = await session.execute(
                    select(func.count())
                    .select_from(model)
                    .where(timestamp_field >= cutoff)
                )
                recent_count = result.scalar()

                # Oldest and newest entries
                result = await session.execute(
                    select(
                        func.min(timestamp_field), func.max(timestamp_field)
                    ).select_from(model)
                )
                oldest, newest = result.one()

                # Calculate collection period
                if oldest and newest:
                    collection_days = (newest - oldest).total_seconds() / 86400
                else:
                    collection_days = 0

                # Evaluate status
                if total_count == 0:
                    status = "failed" if critical else "warning"
                    message = "No data collected"
                    self._add_check_result(name, status, message)
                    self.results["issues"].append(
                        f"{name}: No data found. Ensure backend is running and agents are active."
                    )
                    print(
                        f"{Colors.RED if critical else Colors.YELLOW}{'✗' if critical else '⚠'}{Colors.END} {name}: No data"
                    )
                elif collection_days < self.min_days:
                    status = "warning"
                    message = f"Only {collection_days:.1f} days of data (need {self.min_days})"
                    self._add_check_result(
                        name,
                        status,
                        message,
                        {
                            "total_records": total_count,
                            "recent_24h": recent_count,
                            "collection_days": round(collection_days, 1),
                        },
                    )
                    print(
                        f"{Colors.YELLOW}⚠{Colors.END} {name}: {collection_days:.1f}/{self.min_days} days"
                    )
                else:
                    # Check collection rate
                    actual_per_day = total_count / max(collection_days, 1)
                    rate_percentage = (
                        (actual_per_day / expected_per_day) * 100
                        if expected_per_day > 0
                        else 100
                    )

                    status = "passed"
                    message = f"{total_count} records over {collection_days:.1f} days"
                    self._add_check_result(
                        name,
                        status,
                        message,
                        {
                            "total_records": total_count,
                            "recent_24h": recent_count,
                            "collection_days": round(collection_days, 1),
                            "records_per_day": round(actual_per_day, 1),
                            "expected_per_day": expected_per_day,
                            "rate_percentage": round(rate_percentage, 1),
                        },
                    )
                    print(
                        f"{Colors.GREEN}✓{Colors.END} {name}: {total_count} records ({collection_days:.1f} days)"
                    )

        except Exception as e:
            self._add_check_result(name, "failed", str(e))
            print(f"{Colors.RED}✗{Colors.END} {name}: {str(e)}")

    async def _check_data_quality(self):
        """Check data quality metrics."""
        check_name = "Data Quality"
        print(f"\n{Colors.BOLD}Data Quality Checks:{Colors.END}")

        quality_issues = []

        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Define metrics to check
                metrics_checks = [
                    ("cpu_percent", DeviceMetrics.cpu_percent, 100),
                    ("memory_percent", DeviceMetrics.memory_percent, 100),
                    ("disk_percent", DeviceMetrics.disk_percent, 100),
                    ("network_latency_ms", DeviceMetrics.network_latency_ms, None),
                    ("transaction_count", DeviceMetrics.transaction_count, None),
                    ("transaction_volume", DeviceMetrics.transaction_volume, None),
                    ("error_rate", DeviceMetrics.error_rate, None),
                    ("active_connections", DeviceMetrics.active_connections, None),
                    ("queue_depth", DeviceMetrics.queue_depth, None),
                ]

                for name, column, max_val in metrics_checks:
                    # Check for nulls
                    result = await session.execute(
                        select(func.count(DeviceMetrics.id)).where(column.is_(None))
                    )
                    null_count = result.scalar()

                    if null_count > 0:
                        quality_issues.append(f"{null_count} metrics with null {name}")
                        print(
                            f"  {Colors.YELLOW}⚠{Colors.END} {null_count} records with null {name}"
                        )

                    # Check for max value if applicable
                    if max_val is not None:
                        result = await session.execute(
                            select(func.count(DeviceMetrics.id)).where(column > max_val)
                        )
                        invalid_count = result.scalar()

                        if invalid_count > 0:
                            quality_issues.append(
                                f"{invalid_count} metrics with invalid {name} (>{max_val})"
                            )
                            print(
                                f"  {Colors.RED}✗{Colors.END} {invalid_count} records with {name} > {max_val}"
                            )

            if quality_issues:
                self._add_check_result(check_name, "warning", "; ".join(quality_issues))
            else:
                self._add_check_result(
                    check_name, "passed", "No quality issues detected"
                )
                print(f"  {Colors.GREEN}✓{Colors.END} All data within expected ranges")

        except Exception as e:
            self._add_check_result(check_name, "failed", str(e))
            print(f"  {Colors.RED}✗{Colors.END} {str(e)}")

    async def _check_collection_gaps(self):
        """Check for gaps in data collection."""
        check_name = "Collection Continuity"
        print(f"\n{Colors.BOLD}Collection Continuity:{Colors.END}")

        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Check for gaps longer than 1 hour in device metrics
                cutoff = utc_now() - timedelta(days=self.min_days)
                result = await session.execute(
                    select(DeviceMetrics.timestamp)
                    .where(DeviceMetrics.timestamp >= cutoff)
                    .order_by(DeviceMetrics.timestamp)
                    .limit(1000)
                )
                timestamps = [row[0] for row in result.fetchall()]

                if len(timestamps) < 2:
                    print(
                        f"  {Colors.YELLOW}⚠{Colors.END} Insufficient data for gap analysis"
                    )
                    return

                # Find gaps
                gaps = []
                for i in range(1, len(timestamps)):
                    gap = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
                    if gap > 60:  # Gap > 1 hour
                        gaps.append(
                            {
                                "start": timestamps[i - 1].isoformat(),
                                "end": timestamps[i].isoformat(),
                                "duration_minutes": gap,
                            }
                        )

                if gaps:
                    self._add_check_result(
                        check_name,
                        "warning",
                        f"{len(gaps)} collection gap(s) detected",
                        {"gaps": gaps[:5]},  # First 5 gaps
                    )
                    print(
                        f"  {Colors.YELLOW}⚠{Colors.END} {len(gaps)} gap(s) > 1 hour detected"
                    )
                    self.results["recommendations"].append(
                        "Collection gaps detected. Ensure backend stays running "
                        "continuously."
                    )
                else:
                    self._add_check_result(
                        check_name, "passed", "No significant gaps detected"
                    )
                    print(
                        f"  {Colors.GREEN}✓{Colors.END} "
                        "Continuous data collection confirmed"
                    )

        except Exception as e:
            self._add_check_result(check_name, "failed", str(e))
            print(f"  {Colors.RED}✗{Colors.END} {str(e)}")

    def _add_check_result(
        self, name: str, status: str, message: str, details: Optional[Dict] = None
    ):
        """Add a check result."""
        self.results["checks"].append(
            {
                "name": name,
                "status": status,
                "message": message,
                "details": details or {},
            }
        )

    def _determine_overall_status(self):
        """Determine overall validation status."""
        failed = sum(1 for c in self.results["checks"] if c["status"] == "failed")
        warnings = sum(1 for c in self.results["checks"] if c["status"] == "warning")
        passed = sum(1 for c in self.results["checks"] if c["status"] == "passed")

        if failed > 0:
            self.results["overall_status"] = "failed"
        elif warnings > 0:
            self.results["overall_status"] = "warning"
        else:
            self.results["overall_status"] = "passed"

        self.results["summary"] = {
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "total": passed + warnings + failed,
        }

    def _print_summary(self):
        """Print validation summary."""
        print(f"\n{Colors.BOLD}{'='*70}")
        print(f"Validation Summary")
        print(f"{'='*70}{Colors.END}\n")

        summary = self.results["summary"]
        print(f"Total Checks: {summary['total']}")
        print(f"  {Colors.GREEN}✓{Colors.END} Passed: {summary['passed']}")
        print(f"  {Colors.YELLOW}⚠{Colors.END} Warnings: {summary['warnings']}")
        print(f"  {Colors.RED}✗{Colors.END} Failed: {summary['failed']}")

        # Overall status
        status = self.results["overall_status"]
        if status == "passed":
            color = Colors.GREEN
            symbol = "✓"
            message = "All checks passed! Data collection is healthy."
        elif status == "warning":
            color = Colors.YELLOW
            symbol = "⚠"
            message = "Some warnings detected. Review recommendations below."
        else:
            color = Colors.RED
            symbol = "✗"
            message = "Critical issues found. Fix issues before AI training."

        print(
            f"\n{color}{Colors.BOLD}{symbol} "
            f"Overall Status: {status.upper()}{Colors.END}"
        )
        print(f"{message}")

        # Issues
        if self.results["issues"]:
            print(f"\n{Colors.RED}{Colors.BOLD}Issues Found:{Colors.END}")
            for i, issue in enumerate(self.results["issues"], 1):
                print(f"  {i}. {issue}")

        # Recommendations
        if self.results["recommendations"]:
            print(f"\n{Colors.BLUE}{Colors.BOLD}Recommendations:{Colors.END}")
            for i, rec in enumerate(self.results["recommendations"], 1):
                print(f"  {i}. {rec}")

        print(f"\n{Colors.BOLD}{'='*70}{Colors.END}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate HOMEPOT data collection for AI training"
    )
    parser.add_argument(
        "--min-days",
        type=int,
        default=3,
        help="Minimum days of data required (default: 3)",
    )
    parser.add_argument("--report", type=str, help="Output JSON report to file")

    args = parser.parse_args()

    # Run validation
    validator = DataCollectionValidator(min_days=args.min_days)
    results = await validator.run_validation()

    # Save report if requested
    if args.report:
        with open(args.report, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Report saved to: {args.report}")

    # Exit with appropriate code
    if results["overall_status"] == "failed":
        sys.exit(1)
    elif results["overall_status"] == "warning":
        sys.exit(0)  # Warnings are acceptable
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
