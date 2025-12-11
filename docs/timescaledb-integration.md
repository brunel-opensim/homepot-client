# TimescaleDB Integration

## Quick Start

**For Ubuntu 24.04 with PostgreSQL 16:**
```bash
# 1. Add repository and install
sudo sh -c "echo 'deb [signed-by=/usr/share/keyrings/timescaledb.keyring] https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | gpg --dearmor | sudo tee /usr/share/keyrings/timescaledb.keyring > /dev/null
sudo apt update
sudo apt install timescaledb-2-postgresql-16

# 2. Configure and restart
sudo timescaledb-tune --quiet --yes
sudo systemctl restart postgresql

# 3. Enable in database (or use init-postgresql.sh)
sudo -u postgres psql -d homepot_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
```

**Then run the database initialization script - it will automatically use TimescaleDB:**
```bash
bash scripts/init-postgresql.sh
```

## Overview

TimescaleDB is a powerful PostgreSQL extension that transforms PostgreSQL into a high-performance time-series database. HOMEPOT Client uses TimescaleDB to optimize storage and querying of device health metrics, providing **10-50x faster query performance** for time-series data analysis.

## What is TimescaleDB?

TimescaleDB extends PostgreSQL with specialized features for time-series data:

- **Automatic Partitioning**: Data is automatically split into time-based chunks (hypertables)
- **Continuous Aggregates**: Pre-computed materialized views that refresh automatically
- **Data Retention Policies**: Automatic deletion of old data
- **Compression**: Automatic compression of older data to save storage
- **Full SQL Support**: 100% PostgreSQL-compatible - all existing queries work unchanged

### Key Benefits

| Feature | Benefit | Performance Gain |
|---------|---------|------------------|
| Hypertables | Automatic time-based partitioning | 10-20x faster queries |
| Continuous Aggregates | Pre-computed hourly/daily metrics | 50-100x faster dashboards |
| Compression | Reduced storage for historical data | 90%+ storage savings |
| Retention Policies | Automatic data cleanup | Zero maintenance |
| Native SQL | No query rewrites needed | Zero migration effort |

## How It Works in HOMEPOT

### 1. Health Checks Hypertable

The `health_checks` table is converted to a TimescaleDB hypertable, automatically partitioning data into 1-week chunks:

```sql
-- Standard PostgreSQL table
health_checks
  ├── All data in one table
  └── Slow queries on large datasets

-- TimescaleDB hypertable
health_checks
  ├── Chunk 1: Nov 1-7, 2025 (compressed)
  ├── Chunk 2: Nov 8-14, 2025 (compressed)
  ├── Chunk 3: Nov 15-21, 2025 (active)
  └── Chunk 4: Nov 22-28, 2025 (active)
```

### 2. Continuous Aggregates

Pre-computed views for common queries:

#### Hourly Device Metrics (`device_metrics_hourly`)

Refreshes every hour with:
- Average/max CPU, memory, disk usage
- Transaction and error counts
- Network latency
- Unhealthy device counts

**Use case**: Real-time monitoring dashboards

```python
# Fast query using continuous aggregate (10-50x faster)
SELECT * FROM device_metrics_hourly 
WHERE device_id = 123 
AND hour >= NOW() - INTERVAL '24 hours'
```

#### Daily Device Metrics (`device_metrics_daily`)

Refreshes every 6 hours with:
- Daily summary statistics
- Long-term trends
- Uptime tracking

**Use case**: Weekly/monthly reports and trend analysis

#### Site Metrics (`site_metrics_hourly`)

Aggregates metrics across all devices per site:
- Site-wide CPU/memory averages
- Total transactions across site
- Device health status per site

**Use case**: Site-level monitoring and alerts

### 3. Automatic Data Management

#### Compression (after 7 days)
- Older data is automatically compressed using columnar storage
- Saves 90%+ storage space
- Queries remain fast (decompressed on-the-fly)

#### Retention (90 days)
- Data older than 90 days is automatically deleted
- Configurable retention period
- Reduces database size and improves performance

## Installation

### Prerequisites

- PostgreSQL 16 (as used in HOMEPOT Client)
- HOMEPOT Client configured for PostgreSQL (not SQLite)

### Option 1: Package Manager (Recommended)

#### Ubuntu/Debian (Ubuntu 24.04 / PostgreSQL 16)

```bash
# Add TimescaleDB repository
sudo sh -c "echo 'deb [signed-by=/usr/share/keyrings/timescaledb.keyring] https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"

# Add GPG key
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | \
  gpg --dearmor | \
  sudo tee /usr/share/keyrings/timescaledb.keyring > /dev/null

# Update and install TimescaleDB for PostgreSQL 16
sudo apt update
sudo apt install timescaledb-2-postgresql-16

# Configure PostgreSQL
sudo timescaledb-tune --quiet --yes

# Restart PostgreSQL
sudo systemctl restart postgresql

# Verify installation
psql --version
dpkg -l | grep timescale
```

**For PostgreSQL 14 (older systems):**
```bash
sudo apt install timescaledb-2-postgresql-14
```

#### macOS (Homebrew)

```bash
# Install TimescaleDB
brew install timescaledb

# Configure PostgreSQL
timescaledb-tune --quiet --yes

# Restart PostgreSQL
brew services restart postgresql
```

#### RHEL/CentOS/Fedora

```bash
# Add repository
sudo tee /etc/yum.repos.d/timescale_timescaledb.repo <<EOL
[timescale_timescaledb]
name=timescale_timescaledb
baseurl=https://packagecloud.io/timescale/timescaledb/el/\$(rpm -E %{rhel})/\$basearch
repo_gpgcheck=1
gpgcheck=0
enabled=1
gpgkey=https://packagecloud.io/timescale/timescaledb/gpgkey
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOL

# Install
sudo yum install timescaledb-2-postgresql-14

# Configure
sudo timescaledb-tune --quiet --yes

# Restart
sudo systemctl restart postgresql
```

### Option 2: Docker

```bash
# Use TimescaleDB Docker image instead of standard PostgreSQL
docker run -d \
  --name homepot-postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=homepot \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg14
```

### Verify Installation

```bash
# Check if TimescaleDB package is installed
dpkg -l | grep timescale

# Connect to PostgreSQL
psql -U homepot_user -d homepot_db

# Check if extension is available
SELECT * FROM pg_available_extensions WHERE name = 'timescaledb';

# Check if extension is enabled in your database
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';
```

### Enable TimescaleDB Extension

After installing the TimescaleDB package, you need to enable it in your database:

```bash
# Connect to your database
sudo -u postgres psql -d homepot_db

# Enable the extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

# Verify it's enabled
\dx timescaledb

# Exit
\q
```

**Note:** The `init-postgresql.sh` script automatically enables TimescaleDB if the package is installed, so you typically don't need to do this manually when using the initialization script.

## Setup in HOMEPOT

### Automatic Setup (Recommended)

TimescaleDB is automatically initialized when HOMEPOT starts with a PostgreSQL database:

```python
# In your .env or config
DATABASE_URL=postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db

# Start HOMEPOT - TimescaleDB is configured automatically
python -m homepot.main
```

The system will:
1. Detect TimescaleDB extension
2. Enable the extension
3. Convert `health_checks` to hypertable
4. Add compression and retention policies
5. Fall back to standard PostgreSQL if unavailable

### Manual Setup

Use the CLI tool for manual control:

```bash
# Check TimescaleDB status
python -m homepot.cli_timescaledb status

# Set up TimescaleDB (extension + hypertables + policies)
python -m homepot.cli_timescaledb setup

# Create continuous aggregates
python -m homepot.cli_timescaledb create-aggregates

# List chunks
python -m homepot.cli_timescaledb chunks health_checks
```

## Usage

### Querying Device Metrics

#### Raw Data (Standard Query)

```python
# Works with or without TimescaleDB
async def get_recent_metrics(device_id: int):
    result = await session.execute(
        select(HealthCheck)
        .where(HealthCheck.device_id == device_id)
        .where(HealthCheck.timestamp >= datetime.now() - timedelta(hours=24))
        .order_by(HealthCheck.timestamp.desc())
    )
    return result.scalars().all()
```

#### Aggregated Data (Continuous Aggregates)

```python
# Fast pre-computed hourly metrics (10-50x faster)
async def get_hourly_metrics(device_id: int, hours: int = 24):
    result = await session.execute(
        text("""
            SELECT hour, avg_cpu, avg_memory, total_transactions
            FROM device_metrics_hourly
            WHERE device_id = :device_id
            AND hour >= NOW() - INTERVAL ':hours hours'
            ORDER BY hour DESC
        """),
        {"device_id": device_id, "hours": hours}
    )
    return result.fetchall()
```

#### Site-Wide Metrics

```python
# Site-level aggregated metrics
async def get_site_metrics(site_id: int):
    result = await session.execute(
        text("""
            SELECT hour, device_count, avg_cpu, total_transactions
            FROM site_metrics_hourly
            WHERE site_id = :site_id
            AND hour >= NOW() - INTERVAL '7 days'
        """),
        {"site_id": site_id}
    )
    return result.fetchall()
```

### Time-Series Functions

TimescaleDB provides specialized functions for time-series analysis:

```sql
-- Time bucketing (group by hour/day/week)
SELECT time_bucket('1 hour', timestamp) AS hour,
       AVG(cpu_percent) as avg_cpu
FROM health_checks
GROUP BY hour;

-- First/last values in time range
SELECT FIRST(cpu_percent, timestamp) as first_cpu,
       LAST(cpu_percent, timestamp) as last_cpu
FROM health_checks
WHERE device_id = 123;

-- Time-weighted averages
SELECT time_bucket('1 day', timestamp) AS day,
       time_weight('average', timestamp, cpu_percent) as weighted_avg_cpu
FROM health_checks
GROUP BY day;
```

## Configuration

### Retention Policy

Change how long data is kept:

```python
# Default: 90 days
await ts_manager.add_retention_policy(
    hypertable="health_checks",
    retention_period="180 days",  # Keep for 6 months
    if_not_exists=True
)
```

### Compression Policy

Configure when data is compressed:

```python
# Default: 7 days
await ts_manager.add_compression_policy(
    hypertable="health_checks",
    compress_after="30 days",  # Compress after 30 days
    if_not_exists=True
)
```

### Chunk Interval

Adjust partition size:

```python
# Default: 1 week chunks
await ts_manager.create_hypertable(
    table_name="health_checks",
    time_column="timestamp",
    chunk_time_interval="1 day",  # Smaller chunks for high-volume data
)
```

## Performance Tuning

### Continuous Aggregate Refresh

Adjust how often aggregates refresh:

```sql
-- More frequent updates for real-time dashboards
SELECT add_continuous_aggregate_policy('device_metrics_hourly',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes'  -- Refresh every 5 minutes
);
```

### Indexing

Add indexes for commonly queried columns:

```sql
-- Index on device_id for fast device-specific queries
CREATE INDEX idx_health_checks_device_time 
ON health_checks (device_id, timestamp DESC);

-- Index for site-level queries
CREATE INDEX idx_devices_site 
ON devices (site_id);
```

### PostgreSQL Configuration

Optimize PostgreSQL for time-series workloads:

```bash
# Run TimescaleDB tuner
sudo timescaledb-tune

# Or manually adjust postgresql.conf
shared_preload_libraries = 'timescaledb'
shared_buffers = 2GB              # 25% of RAM
effective_cache_size = 6GB        # 75% of RAM
work_mem = 64MB                   # For sorting/aggregation
max_parallel_workers_per_gather = 4  # Parallel query execution
```

## Monitoring

### Check TimescaleDB Status

```bash
# CLI tool
python -m homepot.cli_timescaledb status

# PostgreSQL query
SELECT * FROM timescaledb_information.hypertables;
```

### View Chunk Statistics

```bash
# List all chunks
python -m homepot.cli_timescaledb chunks health_checks

# Check compression status
SELECT * FROM timescaledb_information.chunks 
WHERE hypertable_name = 'health_checks';
```

### Monitor Background Jobs

```sql
-- View all background jobs (compression, retention, aggregates)
SELECT * FROM timescaledb_information.jobs;

-- Check job statistics
SELECT * FROM timescaledb_information.job_stats;
```

## Troubleshooting

### TimescaleDB Not Detected

```bash
# 1. Verify extension is installed
psql -U postgres -c "SELECT * FROM pg_available_extensions WHERE name = 'timescaledb';"

# 2. Enable extension manually
psql -U homepot_user -d homepot_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 3. Check HOMEPOT logs
tail -f logs/homepot.log | grep -i timescale
```

### Hypertable Conversion Failed

```sql
-- Check if table is already a hypertable
SELECT * FROM timescaledb_information.hypertables 
WHERE hypertable_name = 'health_checks';

-- If conversion failed, check for constraints
SELECT conname, contype FROM pg_constraint 
WHERE conrelid = 'health_checks'::regclass;

-- Drop problematic constraints if needed
ALTER TABLE health_checks DROP CONSTRAINT constraint_name;
```

### Poor Query Performance

```sql
-- Analyze query plan
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM health_checks 
WHERE device_id = 123 
AND timestamp >= NOW() - INTERVAL '7 days';

-- Check if continuous aggregate is being used
EXPLAIN SELECT * FROM device_metrics_hourly WHERE device_id = 123;

-- Refresh aggregates manually if needed
CALL refresh_continuous_aggregate('device_metrics_hourly', NULL, NULL);
```

## Migration from Standard PostgreSQL

If you're already running HOMEPOT with standard PostgreSQL:

### 1. Backup Database

```bash
pg_dump -U postgres homepot > homepot_backup.sql
```

### 2. Install TimescaleDB

Follow installation instructions above.

### 3. Convert to Hypertable

```bash
# HOMEPOT will automatically convert on next startup
python -m homepot.main

# Or use manual setup
python -m homepot.cli_timescaledb setup
```

### 4. Create Aggregates

```bash
python -m homepot.cli_timescaledb create-aggregates
```

### 5. Verify

```bash
python -m homepot.cli_timescaledb status
```

**Note**: Converting to a hypertable is non-destructive - all existing data is preserved.

## Fallback Behavior

HOMEPOT gracefully handles missing TimescaleDB:

1. **Detection**: Checks for TimescaleDB extension at startup
2. **Fallback**: If unavailable, uses standard PostgreSQL
3. **Logging**: Warns in logs but continues normally
4. **Compatibility**: All queries work with or without TimescaleDB

```python
# This code works with or without TimescaleDB
await db_service.create_health_check(
    device_id=123,
    is_healthy=True,
    response_data=metrics
)
```

## Best Practices

1. **Use Continuous Aggregates**: Query pre-computed views instead of raw data
2. **Monitor Chunk Sizes**: Keep chunks at optimal size (1-2GB per chunk)
3. **Regular Maintenance**: Let automatic policies handle compression/retention
4. **Index Strategically**: Add indexes for non-time columns you query frequently
5. **Test Queries**: Use `EXPLAIN` to verify queries use indexes and aggregates

## Resources

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [Best Practices Guide](https://docs.timescale.com/timescaledb/latest/how-to-guides/hypertables/best-practices/)
- [Performance Tuning](https://docs.timescale.com/timescaledb/latest/how-to-guides/configuration/about-configuration/)
- [Continuous Aggregates](https://docs.timescale.com/timescaledb/latest/how-to-guides/continuous-aggregates/)

## Support

For HOMEPOT-specific TimescaleDB questions:
- Check logs: `logs/homepot.log`
- Run diagnostics: `python -m homepot.cli_timescaledb status`
- Open issue: [GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)

