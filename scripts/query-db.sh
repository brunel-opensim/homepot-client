#!/bin/bash
# Simple PostgreSQL query helper for HOMEPOT database

export PGPASSWORD='homepot_dev_password'

# If no argument provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/query-db.sh [command]"
    echo ""
    echo "Available commands:"
    echo "  tables              - List all tables"
    echo "  users               - Show all users"
    echo "  sites               - Show all sites"
    echo "  devices             - Show all devices"
    echo "  jobs                - Show all jobs"
    echo "  health_checks       - Show recent health checks"
    echo "  audit_logs          - Show recent audit logs"
    echo "  api_request_logs    - Show recent API requests"
    echo "  user_activities     - Show recent user activities"
    echo "  device_state_history - Show device state changes"
    echo "  job_outcomes        - Show job execution outcomes"
    echo "  error_logs          - Show recent errors"
    echo "  count               - Count rows in all tables"
    echo "  schema [table]      - Show table structure"
    echo "  where               - Show where PostgreSQL stores data"
    echo "  sql 'query'         - Run custom SQL query"
    echo ""
    echo "Examples:"
    echo "  ./scripts/query-db.sh count"
    echo "  ./scripts/query-db.sh jobs"
    echo "  ./scripts/query-db.sh audit_logs"
    echo "  ./scripts/query-db.sh schema health_checks"
    echo "  ./scripts/query-db.sh sql 'SELECT * FROM sites LIMIT 1;'"
    exit 0
fi

case "$1" in
    tables)
        psql -h localhost -U homepot_user -d homepot_db --no-align --tuples-only -c "SELECT schemaname || '.' || tablename FROM pg_tables WHERE schemaname = 'public';" | column
        echo ""
        psql -h localhost -U homepot_user -d homepot_db -c "SELECT COUNT(*) as total_tables FROM pg_tables WHERE schemaname = 'public';"
        ;;
    users)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, username, email, is_admin, is_active, created_at FROM users;
EOF
        ;;
    sites)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, site_id, name, location, is_active FROM sites;
EOF
        ;;
    devices)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, device_id, name, device_type, site_id, status FROM devices LIMIT 10;
EOF
        ;;
    jobs)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, job_id, action, status, priority, site_id, device_id, created_at, completed_at 
FROM jobs 
ORDER BY created_at DESC 
LIMIT 10;
EOF
        ;;
    health_checks)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, device_id, is_healthy, response_time_ms, status_code, endpoint, timestamp 
FROM health_checks 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    audit_logs)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, event_type, description, user_id, job_id, device_id, created_at 
FROM audit_logs 
ORDER BY created_at DESC 
LIMIT 10;
EOF
        ;;
    api_request_logs)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, endpoint, method, status_code, response_time_ms, user_id, timestamp 
FROM api_request_logs 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    user_activities)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, user_id, activity_type, page_url, duration_ms, timestamp 
FROM user_activities 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    device_state_history)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, device_id, previous_state, new_state, changed_by, reason, timestamp 
FROM device_state_history 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    job_outcomes)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, job_id, job_type, device_id, status, duration_ms, timestamp 
FROM job_outcomes 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    error_logs)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT id, category, severity, error_code, error_message, endpoint, timestamp 
FROM error_logs 
ORDER BY timestamp DESC 
LIMIT 10;
EOF
        ;;
    count)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT 'api_request_logs' as table_name, COUNT(*) as rows FROM api_request_logs
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
UNION ALL SELECT 'device_state_history', COUNT(*) FROM device_state_history
UNION ALL SELECT 'devices', COUNT(*) FROM devices
UNION ALL SELECT 'error_logs', COUNT(*) FROM error_logs
UNION ALL SELECT 'health_checks', COUNT(*) FROM health_checks
UNION ALL SELECT 'job_outcomes', COUNT(*) FROM job_outcomes
UNION ALL SELECT 'jobs', COUNT(*) FROM jobs
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
        psql -h localhost -U homepot_user -d homepot_db <<EOF
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
        echo "  PGPASSWORD='homepot_dev_password' psql -h localhost -U homepot_user -d homepot_db"
        echo ""
        ;;
    sql)
        if [ -z "$2" ]; then
            echo "Please provide a SQL query: ./scripts/query-db.sh sql 'SELECT * FROM sites;'"
            exit 1
        fi
        psql -h localhost -U homepot_user -d homepot_db <<EOF
$2
EOF
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run ./scripts/query-db.sh without arguments to see available commands"
        exit 1
        ;;
esac
