#!/bin/bash
# Simple PostgreSQL query helper for HOMEPOT database

export PGPASSWORD='homepot_dev_password'

# If no argument provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/query-db.sh [command]"
    echo ""
    echo "Available commands:"
    echo "  tables          - List all tables"
    echo "  users           - Show all users"
    echo "  sites           - Show all sites"
    echo "  devices         - Show all devices"
    echo "  count           - Count rows in all tables"
    echo "  schema [table]  - Show table structure"
    echo "  where           - Show where PostgreSQL stores data"
    echo "  sql 'query'     - Run custom SQL query"
    echo ""
    echo "Examples:"
    echo "  ./scripts/query-db.sh count"
    echo "  ./scripts/query-db.sh users"
    echo "  ./scripts/query-db.sh schema users"
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
    count)
        psql -h localhost -U homepot_user -d homepot_db <<EOF
SELECT 'sites' as table_name, COUNT(*) as rows FROM sites
UNION ALL SELECT 'devices', COUNT(*) FROM devices
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'jobs', COUNT(*) FROM jobs
UNION ALL SELECT 'health_checks', COUNT(*) FROM health_checks
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
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
