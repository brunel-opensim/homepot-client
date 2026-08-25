#!/bin/bash
# Simple PostgreSQL query helper for HOMEPOT database
#
# Connection is configurable via env vars (defaults target a local dev
# PostgreSQL, e.g. the one running inside WSL next to the backend):
#   HOMEPOT_DB_HOST / _PORT / _USER / _NAME / _PASSWORD
# Example (from macOS, pointing at the WSL/Windows host):
#   HOMEPOT_DB_HOST=192.168.x.x ./scripts/query-db.sh devices

DB_HOST="${HOMEPOT_DB_HOST:-localhost}"
DB_PORT="${HOMEPOT_DB_PORT:-5432}"
DB_USER="${HOMEPOT_DB_USER:-homepot_user}"
DB_NAME="${HOMEPOT_DB_NAME:-homepot_db}"
DB_PASSWORD="${HOMEPOT_DB_PASSWORD:-homepot_dev_password}"
export PGPASSWORD="$DB_PASSWORD"

# Run a psql query against the configured database.
psqlq() {
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" "$@"
}

# If no argument provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/query-db.sh [command] [argument]"
    echo ""
    echo "Available commands:"
    echo "  tables                     - List all tables with row counts"
    echo "  show [table]               - Show all rows from any table (e.g. show enrolment_intents)"
    echo "  users                      - Show all users"
    echo "  sites                      - Show all sites"
    echo "  devices                    - Show all devices"
    echo "  devices_by_name [name]     - Find a device by name (e.g. demo-mac-1)"
    echo "  jobs                       - Show all jobs"
    echo "  health_checks              - Show recent health checks"
    echo "  audit_logs                 - Show recent audit logs"
    echo "  api_request_logs           - Show recent API requests"
    echo "  user_activities            - Show recent user activities"
    echo "  device_state_history       - Show device state changes"
    echo "  device_metrics             - Show device performance metrics"
    echo "  configuration_history      - Show configuration changes"
    echo "  site_operating_schedules   - Show site schedules"
    echo "  job_outcomes               - Show job execution outcomes"
    echo "  push_logs [device]         - Show push notification logs (alias: push_notification_logs)"
    echo "  push_notification_logs [device] - Show push logs; filter by device name (e.g. demo-mac-1)"
    echo "  device_commands [device]   - Show the command queue/outcomes (e.g. health_check); filter by device name"
    echo "  error_logs                 - Show recent errors"
    echo "  alerts                     - Show active alerts"
    echo "  count                      - Count rows in all tables"
    echo "  schema [table]             - Show table structure"
    echo "  where                      - Show where PostgreSQL stores data"
    echo "  site_devices [site_id]     - Show all devices for a specific site"
    echo "  device_details [device_id] - Show full details and recent metrics for a device"
    echo "  archived_purged            - Show archived (data retained) and purged (tombstone) sites/devices"
    echo "  sql 'query'                - Run custom SQL query"
    echo ""
    echo "Examples:"
    echo "  ./scripts/query-db.sh count"
    echo "  ./scripts/query-db.sh show enrolment_intents"
    echo "  ./scripts/query-db.sh show tenants"
    echo "  ./scripts/query-db.sh site_devices site-001"
    echo "  ./scripts/query-db.sh device_details DEVICE-XXXX-XXXX-XXXX"
    echo "  ./scripts/query-db.sh devices_by_name demo-mac-1"
    echo "  ./scripts/query-db.sh push_notification_logs demo-mac-1"
    echo "  ./scripts/query-db.sh device_commands demo-mac-1"
    echo "  ./scripts/query-db.sh jobs"
    exit 0
fi

case "$1" in
    tables)
        echo "All public tables (with size info):"
        echo "-----------------------------------"
        echo "\dt+" | psqlq 2>/dev/null
        echo ""
        echo "Row counts:"
        echo "-----------"
        TABLES=$(psqlq -t -A -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")
        for t in $TABLES; do
          COUNT=$(psqlq -t -A -c "SELECT COUNT(*) FROM public.$t;" 2>/dev/null)
          printf "  %-35s %s rows\n" "$t" "$COUNT"
        done
        echo ""
        psqlq -c "SELECT COUNT(*) as total_tables FROM pg_tables WHERE schemaname = 'public';"
        ;;
    users)
        psqlq <<EOF
SELECT id, username, full_name, email, is_admin, is_active, created_at FROM users;
EOF
        ;;
    sites)
        psqlq <<EOF
SELECT id, site_id, name, location, lifecycle_state, is_active FROM sites;
EOF
        ;;
    devices)
        psqlq <<EOF
SELECT d.id, d.device_id, d.name, d.device_type, s.site_id, d.lifecycle_state, d.is_active, d.status
FROM devices d
JOIN sites s ON d.site_id = s.id
ORDER BY d.id
LIMIT 10;
EOF
        ;;
    archived_purged)
        echo "=== Archived / Purged Entities ==="
        echo ""
        echo "--- Archived sites (data retained, hidden) ---"
        psqlq <<EOF
SELECT site_id, name, lifecycle_state
FROM sites
WHERE is_active = false OR lifecycle_state = 'archived'
ORDER BY id;
EOF
        echo ""
        echo "--- Archived devices (unpaired/retired, data retained) ---"
        psqlq <<EOF
SELECT d.device_id, d.name, d.lifecycle_state, s.site_id
FROM devices d
JOIN sites s ON d.site_id = s.id
WHERE d.is_active = false OR d.lifecycle_state IN ('unpaired','retired')
ORDER BY d.id;
EOF
        echo ""
        echo "--- Purged sites (data deleted; tombstone from audit_logs) ---"
        psqlq <<EOF
SELECT al.created_at AS purged_at,
       (al.old_values->>'site_id') AS site_id,
       (al.old_values->>'name') AS name
FROM audit_logs al
WHERE al.event_type = 'site_deleted'
  AND al.old_values->>'cleanup_policy' = 'purge'
ORDER BY al.created_at DESC;
EOF
        echo ""
        echo "--- Purged devices (data deleted; tombstone from audit_logs) ---"
        psqlq <<EOF
SELECT al.created_at AS purged_at,
       (al.old_values->>'device_id') AS device_id,
       (al.old_values->>'name') AS name
FROM audit_logs al
WHERE al.event_type = 'device_deleted'
ORDER BY al.created_at DESC;
EOF
        ;;
    jobs)
        psqlq <<EOF
SELECT j.id, j.job_id, j.action, j.status, s.site_id, d.device_id, j.created_at 
FROM jobs j
JOIN sites s ON j.site_id = s.id
LEFT JOIN devices d ON j.device_id = d.id
ORDER BY j.created_at DESC 
LIMIT 10;
EOF
        ;;
    health_checks)
        psqlq <<EOF
SELECT h.id, d.device_id, h.is_healthy, h.response_time_ms, h.status_code, h.timestamp 
FROM health_checks h
JOIN devices d ON h.device_id = d.id
ORDER BY h.timestamp DESC 
LIMIT 10;
EOF
        ;;
    audit_logs)
        psqlq <<EOF
SELECT id, event_type, description, user_id, job_id, device_id, created_at 
FROM audit_logs 
ORDER BY created_at DESC 
LIMIT 10;
EOF
        ;;
    api_request_logs)
        psqlq <<EOF
SELECT id, endpoint, method, status_code, response_time_ms, user_id, timestamp 
FROM api_request_logs 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    user_activities)
        psqlq <<EOF
SELECT id, user_id, activity_type, page_url, duration_ms, timestamp 
FROM user_activities 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    device_state_history)
        psqlq <<EOF
SELECT id, device_id, previous_state, new_state, changed_by, reason, timestamp 
FROM device_state_history 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    job_outcomes)
        psqlq <<EOF
SELECT id, job_id, job_type, device_id, status, duration_ms, timestamp 
FROM job_outcomes 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    push_logs|push_notification_logs)
        # Optional filter by device name (or device_id) as $2.
        FILTER=""
        if [ -n "$2" ]; then
            FILTER="WHERE d.name = '$2' OR d.device_id = '$2'"
        fi
        psqlq <<EOF
SELECT p.id, d.name AS device, p.message_id, p.provider, p.status,
       p.payload, p.sent_at, p.received_at
FROM push_notification_logs p
LEFT JOIN devices d ON p.device_id = d.device_id
${FILTER}
ORDER BY p.sent_at DESC
LIMIT 20;
EOF
        ;;
    device_commands)
        # Command queue/outcomes; optional filter by device name (or device_id).
        FILTER=""
        if [ -n "$2" ]; then
            FILTER="WHERE d.name = '$2' OR d.device_id = '$2'"
        fi
        psqlq <<EOF
SELECT c.command_id, d.name AS device, c.command_type, c.status,
       c.created_at, c.sent_at, c.executed_at, c.result
FROM device_commands c
LEFT JOIN devices d ON c.device_id = d.id
${FILTER}
ORDER BY c.created_at DESC
LIMIT 20;
EOF
        ;;
    devices_by_name)
        if [ -z "$2" ]; then
            echo "Please provide a device name: ./scripts/query-db.sh devices_by_name demo-mac-1"
            exit 1
        fi
        psqlq <<EOF
SELECT d.id, d.device_id, d.name, d.device_type, s.site_id, d.lifecycle_state,
       d.is_active, d.status, d.last_heartbeat_at
FROM devices d
JOIN sites s ON d.site_id = s.id
WHERE d.name = '$2' OR d.device_id = '$2'
ORDER BY d.id;
EOF
        ;;
    error_logs)
        psqlq <<EOF
SELECT id, category, severity, error_code, error_message, endpoint, timestamp 
FROM error_logs 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    alerts)
        psqlq <<EOF
SELECT id, device_id, category as type, severity, status, title, timestamp
FROM alerts 
ORDER BY timestamp DESC;
EOF
        ;;
    device_metrics)
        psqlq <<EOF
SELECT m.id, d.device_id, m.cpu_percent, m.memory_percent, m.transaction_count, m.timestamp 
FROM device_metrics m
JOIN devices d ON m.device_id = d.id
ORDER BY m.timestamp DESC 
LIMIT 10;
EOF
        ;;
    configuration_history)
        psqlq <<EOF
SELECT id, change_type, entity_id, parameter_name, 
       was_successful, timestamp, changed_by
FROM configuration_history 
ORDER BY timestamp DESC 
LIMIT 20;
EOF
        ;;
    site_operating_schedules)
        psqlq <<EOF
SELECT id, site_id, day_of_week, open_time, close_time, 
       is_maintenance_window, expected_transaction_volume 
FROM site_operating_schedules 
ORDER BY site_id, day_of_week;
EOF
        ;;
    count)
        psqlq <<EOF
SELECT 'alerts' as table_name, COUNT(*) as rows FROM alerts
UNION ALL SELECT 'api_request_logs', COUNT(*) FROM api_request_logs
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
UNION ALL SELECT 'configuration_history', COUNT(*) FROM configuration_history
UNION ALL SELECT 'device_metrics', COUNT(*) FROM device_metrics
UNION ALL SELECT 'device_state_history', COUNT(*) FROM device_state_history
UNION ALL SELECT 'devices', COUNT(*) FROM devices
UNION ALL SELECT 'error_logs', COUNT(*) FROM error_logs
UNION ALL SELECT 'health_checks', COUNT(*) FROM health_checks
UNION ALL SELECT 'job_outcomes', COUNT(*) FROM job_outcomes
UNION ALL SELECT 'jobs', COUNT(*) FROM jobs
UNION ALL SELECT 'push_notification_logs', COUNT(*) FROM push_notification_logs
UNION ALL SELECT 'site_operating_schedules', COUNT(*) FROM site_operating_schedules
UNION ALL SELECT 'sites', COUNT(*) FROM sites
UNION ALL SELECT 'user_activities', COUNT(*) FROM user_activities
UNION ALL SELECT 'users', COUNT(*) FROM users
ORDER BY table_name;
EOF
        ;;
    schema)
        if [ -z "$2" ]; then
            echo "Please specify a table name: ./scripts/query-db.sh schema users"
            exit 1
        fi
        psqlq <<EOF
SELECT 
    column_name, 
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = '$2' 
ORDER BY ordinal_position;
EOF
        ;;
    where)
        echo ""
        echo "PostgreSQL Data Location:"
        echo "========================="
        echo ""
        echo "Unlike SQLite (single file), PostgreSQL stores data in a system directory:"
        echo ""
        sudo -u postgres psql -c "SHOW data_directory;" 2>/dev/null || echo "  Default: /var/lib/postgresql/16/main/"
        echo ""
        echo "Your database 'homepot_db' is stored there as binary files."
        echo "You cannot directly open these files - you MUST use psql to access data."
        echo ""
        echo "To explore interactively, run:"
        echo "  PGPASSWORD='homepot_dev_password' psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
        echo ""
        ;;
    sql)
        if [ -z "$2" ]; then
            echo "Please provide a SQL query: ./scripts/query-db.sh sql 'SELECT * FROM sites;'"
            exit 1
        fi
        psqlq <<EOF
$2
EOF
        ;;
    site_devices)
        if [ -z "$2" ]; then
            echo "Please provide a site_id: ./scripts/query-db.sh site_devices site-001"
            exit 1
        fi
        echo "Devices for Site: $2"
        echo "------------------------------------------------"
        psqlq <<EOF
SELECT d.device_id, d.name, d.device_type, d.status, d.ip_address 
FROM devices d
JOIN sites s ON d.site_id = s.id
WHERE s.site_id = '$2'
ORDER BY d.device_id;
EOF
        ;;
    device_details)
        if [ -z "$2" ]; then
            echo "Please provide a device_id: ./scripts/query-db.sh device_details DEVICE-XXXX-XXXX-XXXX"
            exit 1
        fi
        echo "=== Device Information: $2 ==="
        psqlq -x <<EOF
SELECT * FROM devices WHERE device_id = '$2';
EOF
        echo ""
        echo "=== Recent Metrics (Last 5) ==="
        psqlq <<EOF
SELECT timestamp, cpu_percent, memory_percent, transaction_count, error_rate 
FROM device_metrics 
WHERE device_id = (SELECT id FROM devices WHERE device_id = '$2') 
ORDER BY timestamp DESC 
LIMIT 5;
EOF
        ;;
    history_details)
        if [ -z "$2" ]; then
            echo "Please provide a history id: ./scripts/query-db.sh history_details 123"
            exit 1
        fi
        echo "=== Configuration History Details: $2 ==="
        psqlq -x <<EOF
SELECT * FROM configuration_history WHERE id = $2;
EOF
        ;;
    site_hierarchy)
        if [ -z "$2" ]; then
            echo "Please provide a site_id: ./scripts/query-db.sh site_hierarchy site-001"
            exit 1
        fi
        SITE_ID="$2"
        echo "=== Hierarchy Report for Site: $SITE_ID ==="
        
        # Get Site PK
        SITE_PK=$(psqlq -t -c "SELECT id FROM sites WHERE site_id = '$SITE_ID';" | tr -d ' ')
        
        if [ -z "$SITE_PK" ]; then
            echo "Site not found!"
            exit 1
        fi
        
        echo "Site Internal ID: $SITE_PK"
        
        echo ""
        echo "--- Devices & Associated Records ---"
        echo "This report confirms that records are correctly linked to devices under this site."
        echo ""
        psqlq <<EOF
        SELECT 
            d.device_id,
            d.name,
            (SELECT COUNT(*) FROM device_metrics m WHERE m.device_id = d.id) as metrics,
            (SELECT COUNT(*) FROM device_state_history h WHERE h.device_id = d.id) as state_changes,
            (SELECT COUNT(*) FROM configuration_history c WHERE c.entity_id = d.device_id AND c.entity_type = 'device') as config_changes,
            (SELECT COUNT(*) FROM push_notification_logs p WHERE p.device_id = d.device_id) as push_logs,
            (SELECT COUNT(*) FROM job_outcomes j WHERE j.device_id = d.device_id) as jobs
        FROM devices d
        WHERE d.site_id = $SITE_PK
        ORDER BY d.device_id;
EOF
        ;;
    show)
        if [ -z "$2" ]; then
            echo "Usage: ./scripts/query-db.sh show <table_name>"
            echo ""
            echo "Available tables:"
            psqlq -t -A -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
            exit 1
        fi
        psqlq <<EOF
SELECT * FROM public.$2 ORDER BY id DESC NULLS LAST LIMIT 50;
EOF
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run ./scripts/query-db.sh without arguments to see available commands"
        exit 1
        ;;
esac
