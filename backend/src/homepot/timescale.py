"""TimescaleDB integration for time-series optimization.

This module provides TimescaleDB extension setup and hypertable management
for optimizing time-series data storage and queries in the HOMEPOT system.

TimescaleDB is a PostgreSQL extension that provides:
- Automatic time-based partitioning (10-50x query performance)
- Continuous aggregates for pre-computed metrics
- Data retention and compression policies
- Full PostgreSQL compatibility (falls back gracefully if not installed)
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TimescaleDBManager:
    """Manager for TimescaleDB extension and hypertable operations."""

    def __init__(self, session: AsyncSession):
        """Initialize TimescaleDB manager.

        Args:
            session: Async SQLAlchemy database session
        """
        self.session = session
        self._timescaledb_available: Optional[bool] = None

    async def is_timescaledb_available(self) -> bool:
        """Check if TimescaleDB extension is available.

        Returns:
            True if TimescaleDB extension is installed and active
        """
        if self._timescaledb_available is not None:
            return self._timescaledb_available

        try:
            result = await self.session.execute(
                text(
                    "SELECT installed_version FROM pg_available_extensions WHERE name = 'timescaledb'"
                )
            )
            version = result.scalar()
            self._timescaledb_available = version is not None
            if self._timescaledb_available:
                logger.info(f"TimescaleDB extension version {version} is available")
            else:
                logger.info(
                    "TimescaleDB extension not available - using standard PostgreSQL"
                )
            return self._timescaledb_available
        except Exception as e:
            logger.warning(f"Could not check TimescaleDB availability: {e}")
            self._timescaledb_available = False
            return False

    async def enable_extension(self) -> bool:
        """Enable TimescaleDB extension in the database.

        Returns:
            True if extension was enabled successfully

        Note:
            Requires PostgreSQL superuser or database owner privileges
        """
        try:
            await self.session.execute(
                text("CREATE EXTENSION IF NOT EXISTS timescaledb")
            )
            await self.session.commit()
            logger.info("TimescaleDB extension enabled successfully")
            self._timescaledb_available = True
            return True
        except Exception as e:
            logger.error(f"Failed to enable TimescaleDB extension: {e}")
            await self.session.rollback()
            return False

    async def create_hypertable(
        self,
        table_name: str,
        time_column: str = "timestamp",
        if_not_exists: bool = True,
        chunk_time_interval: str = "1 week",
    ) -> bool:
        """Convert a regular table to a TimescaleDB hypertable.

        Args:
            table_name: Name of the table to convert
            time_column: Name of the timestamp column for partitioning
            if_not_exists: Skip if hypertable already exists
            chunk_time_interval: Time range for each partition chunk

        Returns:
            True if hypertable was created successfully
        """
        if not await self.is_timescaledb_available():
            logger.warning(
                f"Cannot create hypertable {table_name}: TimescaleDB not available"
            )
            return False

        try:
            # Check if already a hypertable
            if if_not_exists and await self._is_hypertable(table_name):
                logger.info(f"Table {table_name} is already a hypertable")
                return True

            # Create hypertable
            query = text(
                f"SELECT create_hypertable('{table_name}', '{time_column}', "
                f"chunk_time_interval => INTERVAL '{chunk_time_interval}', "
                f"if_not_exists => {if_not_exists})"
            )
            await self.session.execute(query)
            await self.session.commit()
            logger.info(f"Successfully created hypertable: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create hypertable {table_name}: {e}")
            await self.session.rollback()
            return False

    async def _is_hypertable(self, table_name: str) -> bool:
        """Check if a table is already a hypertable.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table is a hypertable
        """
        try:
            result = await self.session.execute(
                text(
                    "SELECT * FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name = :table_name"
                ),
                {"table_name": table_name},
            )
            return result.first() is not None
        except Exception:
            return False

    async def add_retention_policy(
        self,
        hypertable: str,
        retention_period: str = "90 days",
        if_not_exists: bool = True,
    ) -> bool:
        """Add automatic data retention policy to hypertable.

        Args:
            hypertable: Name of the hypertable
            retention_period: How long to keep data (e.g., "90 days", "1 year")
            if_not_exists: Skip if policy already exists

        Returns:
            True if retention policy was added successfully
        """
        if not await self.is_timescaledb_available():
            logger.warning(f"Cannot add retention policy: TimescaleDB not available")
            return False

        try:
            query = text(
                f"SELECT add_retention_policy('{hypertable}', "
                f"INTERVAL '{retention_period}', "
                f"if_not_exists => {if_not_exists})"
            )
            await self.session.execute(query)
            await self.session.commit()
            logger.info(f"Added retention policy to {hypertable}: {retention_period}")
            return True
        except Exception as e:
            logger.error(f"Failed to add retention policy to {hypertable}: {e}")
            await self.session.rollback()
            return False

    async def add_compression_policy(
        self,
        hypertable: str,
        compress_after: str = "7 days",
        if_not_exists: bool = True,
    ) -> bool:
        """Add automatic compression policy to hypertable.

        Args:
            hypertable: Name of the hypertable
            compress_after: Age of data to compress (e.g., "7 days", "1 month")
            if_not_exists: Skip if policy already exists

        Returns:
            True if compression policy was added successfully
        """
        if not await self.is_timescaledb_available():
            logger.warning(f"Cannot add compression policy: TimescaleDB not available")
            return False

        try:
            # Enable compression on the hypertable first
            await self.session.execute(
                text(f"ALTER TABLE {hypertable} SET (timescaledb.compress)")
            )

            # Add compression policy
            query = text(
                f"SELECT add_compression_policy('{hypertable}', "
                f"INTERVAL '{compress_after}', "
                f"if_not_exists => {if_not_exists})"
            )
            await self.session.execute(query)
            await self.session.commit()
            logger.info(
                f"Added compression policy to {hypertable}: compress after {compress_after}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add compression policy to {hypertable}: {e}")
            await self.session.rollback()
            return False

    async def create_continuous_aggregate(
        self,
        view_name: str,
        hypertable: str,
        query: str,
        refresh_interval: str = "1 hour",
    ) -> bool:
        """Create a continuous aggregate (materialized view) for pre-computed metrics.

        Args:
            view_name: Name for the continuous aggregate view
            hypertable: Source hypertable name
            query: SELECT query defining the aggregate (must include time_bucket)
            refresh_interval: How often to refresh the aggregate

        Returns:
            True if continuous aggregate was created successfully

        Example:
            query = '''
                SELECT time_bucket('1 hour', timestamp) AS bucket,
                       device_id,
                       AVG(cpu_percent) as avg_cpu,
                       MAX(cpu_percent) as max_cpu
                FROM health_checks
                GROUP BY bucket, device_id
            '''
        """
        if not await self.is_timescaledb_available():
            logger.warning(
                f"Cannot create continuous aggregate: TimescaleDB not available"
            )
            return False

        try:
            # Create continuous aggregate
            create_query = text(
                f"CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name} "
                f"WITH (timescaledb.continuous) AS {query}"
            )
            await self.session.execute(create_query)

            # Add refresh policy
            refresh_query = text(
                f"SELECT add_continuous_aggregate_policy('{view_name}', "
                f"start_offset => INTERVAL '2 hours', "
                f"end_offset => INTERVAL '1 hour', "
                f"schedule_interval => INTERVAL '{refresh_interval}')"
            )
            await self.session.execute(refresh_query)
            await self.session.commit()
            logger.info(f"Created continuous aggregate: {view_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create continuous aggregate {view_name}: {e}")
            await self.session.rollback()
            return False

    async def get_hypertable_stats(self, hypertable: str) -> Optional[Dict[str, Any]]:
        """Get statistics about a hypertable.

        Args:
            hypertable: Name of the hypertable

        Returns:
            Dictionary with hypertable statistics or None if not available
        """
        if not await self.is_timescaledb_available():
            return None

        try:
            result = await self.session.execute(
                text(
                    "SELECT * FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name = :table_name"
                ),
                {"table_name": hypertable},
            )
            row = result.first()
            if row:
                return dict(row._mapping)
            return None
        except Exception as e:
            logger.error(f"Failed to get hypertable stats for {hypertable}: {e}")
            return None

    async def get_chunk_stats(self, hypertable: str) -> List[Dict[str, Any]]:
        """Get statistics about chunks in a hypertable.

        Args:
            hypertable: Name of the hypertable

        Returns:
            List of dictionaries with chunk statistics
        """
        if not await self.is_timescaledb_available():
            return []

        try:
            result = await self.session.execute(
                text(
                    "SELECT * FROM timescaledb_information.chunks "
                    "WHERE hypertable_name = :table_name "
                    "ORDER BY range_start DESC"
                ),
                {"table_name": hypertable},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get chunk stats for {hypertable}: {e}")
            return []
