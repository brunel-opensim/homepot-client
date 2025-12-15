# Deployment Guide

This guide covers production deployment of HOMEPOT using Docker and enterprise configurations.

## Production Deployment Overview

HOMEPOT supports multiple deployment scenarios:

- **Single Server**: All components on one machine
- **Multi-tier**: Database, API, and dashboard on separate servers
- **Container Orchestration**: Kubernetes or Docker Swarm
- **Cloud Deployment**: AWS, Azure, Google Cloud Platform

## Docker Deployment

### Quick Start

```bash
# Production deployment with Docker Compose
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Configure environment
cp .env.example .env
# Edit .env with your production settings

# Deploy
docker-compose up -d --build

# Verify deployment
curl http://localhost:8000/health
```

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  homepot-api:
    build: .
    ports:
      - "${HOMEPOT_PORT:-8000}:8000"
    environment:
      - HOMEPOT_ENV=production
      - HOMEPOT_DEBUG=false
      - DATABASE__URL=postgresql://homepot_user:homepot_dev_password@db:5432/homepot
    depends_on:
      - db

  db:
    image: postgres:16
    environment:
      - POSTGRES_DB=homepot
      - POSTGRES_USER=homepot_user
      - POSTGRES_PASSWORD=homepot_dev_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - homepot-api
    restart: unless-stopped
```

### Environment Configuration

```bash
# .env file for production
HOMEPOT_ENV=production
HOMEPOT_PORT=8000
HOMEPOT_DEBUG=false

# Database
HOMEPOT_DATABASE_URL=postgresql://user:pass@localhost/homepot
HOMEPOT_DATABASE_POOL_SIZE=20

# Security
HOMEPOT_SECRET_KEY=your-secret-key-here
HOMEPOT_JWT_SECRET=your-jwt-secret-here
HOMEPOT_ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com

# Logging
HOMEPOT_LOG_LEVEL=INFO
HOMEPOT_LOG_FILE=/app/logs/homepot.log

# Monitoring
HOMEPOT_METRICS_ENABLED=true
HOMEPOT_HEALTH_CHECK_INTERVAL=30
```

## Database Setup

### PostgreSQL (Recommended for Production)

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE homepot;
CREATE USER homepot_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE homepot TO homepot_user;
\q

# Update environment
echo "HOMEPOT_DATABASE_URL=postgresql://homepot_user:secure_password@localhost/homepot" >> .env
```

### Production Database Setup

**HOMEPOT uses PostgreSQL** for production deployments:

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE homepot;
CREATE USER homepot_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE homepot TO homepot_user;
\q

# Update environment
echo "DATABASE__URL=postgresql://homepot_user:secure_password@localhost:5432/homepot" >> .env
```

### Development/Local Setup

For local development, you can use the initialization script:

```bash
# Initialize PostgreSQL database
./scripts/init-postgresql.sh
```

### Database Migration

```bash
# Run database migrations
docker-compose exec homepot-api python -m homepot.migrate

# Backup database
docker-compose exec homepot-api python -m homepot.backup

# Restore database
docker-compose exec homepot-api python -m homepot.restore backup.sql
```

## Reverse Proxy Setup

### Nginx Configuration

```nginx
# nginx.conf
upstream homepot_api {
    server homepot-api:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # API proxy
    location /api/ {
        proxy_pass http://homepot_api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://homepot_api/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location / {
        proxy_pass http://homepot_api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Apache Configuration

```apache
# /etc/apache2/sites-available/homepot.conf
<VirtualHost *:80>
    ServerName yourdomain.com
    Redirect permanent / https://yourdomain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName yourdomain.com
    
    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/cert.pem
    SSLCertificateKeyFile /etc/ssl/private/key.pem
    
    ProxyPreserveHost On
    ProxyPass /api/ http://localhost:8000/
    ProxyPassReverse /api/ http://localhost:8000/
    
    # WebSocket proxy
    ProxyPass /ws/ ws://localhost:8000/ws/
    ProxyPassReverse /ws/ ws://localhost:8000/ws/
</VirtualHost>
```

## Security Configuration

### SSL/TLS Setup

```bash
# Generate self-signed certificate (development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Use Let's Encrypt (production)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp  # Block direct API access
sudo ufw enable
```

### Authentication Setup

```bash
# Configure API authentication
export HOMEPOT_AUTH_ENABLED=true
export HOMEPOT_JWT_SECRET=$(openssl rand -base64 32)
export HOMEPOT_SESSION_TIMEOUT=3600

# Add to .env file
echo "HOMEPOT_AUTH_ENABLED=true" >> .env
echo "HOMEPOT_JWT_SECRET=$HOMEPOT_JWT_SECRET" >> .env
```

## Monitoring and Logging

### Log Configuration

```bash
# Set up log rotation
sudo tee /etc/logrotate.d/homepot > /dev/null <<EOF
/opt/homepot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 homepot homepot
    postrotate
        docker-compose restart homepot-api
    endscript
}
EOF
```

### Health Monitoring

```bash
# Health check script
#!/bin/bash
# /opt/homepot/scripts/health-check.sh

HEALTH_URL="http://localhost:8000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "OK: HOMEPOT API is healthy"
    exit 0
else
    echo "CRITICAL: HOMEPOT API health check failed (HTTP $RESPONSE)"
    exit 2
fi

# Add to crontab
# */5 * * * * /opt/homepot/scripts/health-check.sh
```

### Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'homepot'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

## Backup and Recovery

### Database Backup

```bash
# Automated backup script
#!/bin/bash
# /opt/homepot/scripts/backup.sh

BACKUP_DIR="/opt/homepot/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
docker-compose exec -T homepot-api python -m homepot.backup > $BACKUP_DIR/homepot_$DATE.sql

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz .env docker-compose.yml nginx.conf

# Remove backups older than 30 days
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/homepot_$DATE.sql"
```

### Disaster Recovery

```bash
# Recovery procedure
# 1. Restore from backup
docker-compose exec -T homepot-api python -m homepot.restore < backup.sql

# 2. Restart services
docker-compose restart

# 3. Verify health
curl http://localhost:8000/health
```

## Scaling and Performance

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  homepot-api:
    build: .
    environment:
      - HOMEPOT_ENV=production
    deploy:
      replicas: 3
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - homepot-api

  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

### Load Balancing

```nginx
# nginx load balancing
upstream homepot_backend {
    least_conn;
    server homepot-api-1:8000 weight=1;
    server homepot-api-2:8000 weight=1;
    server homepot-api-3:8000 weight=1;
}

server {
    location / {
        proxy_pass http://homepot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Performance Tuning

```bash
# Environment variables for performance
export HOMEPOT_WORKERS=4
export HOMEPOT_MAX_CONNECTIONS=1000
export HOMEPOT_KEEPALIVE_TIMEOUT=65
export HOMEPOT_CLIENT_MAX_SIZE=16m

# Database connection pooling
export HOMEPOT_DB_POOL_SIZE=20
export HOMEPOT_DB_MAX_OVERFLOW=0
export HOMEPOT_DB_POOL_TIMEOUT=30
```

## Cloud Deployment

### AWS Deployment

```bash
# Install AWS CLI
pip install awscli

# Deploy to ECS
aws ecs create-cluster --cluster-name homepot-cluster

# Create task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service --cluster homepot-cluster --service-name homepot-service
```

### Kubernetes Deployment

```yaml
# k8s-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: homepot-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: homepot-api
  template:
    metadata:
      labels:
        app: homepot-api
    spec:
      containers:
      - name: homepot-api
        image: homepot-client:latest
        ports:
        - containerPort: 8000
        env:
        - name: HOMEPOT_ENV
          value: "production"
---
apiVersion: v1
kind: Service
metadata:
  name: homepot-service
spec:
  selector:
    app: homepot-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Troubleshooting

### Common Deployment Issues

**Container Won't Start:**
```bash
# Check logs
docker-compose logs homepot-api

# Check container status
docker-compose ps

# Debug container
docker-compose exec homepot-api /bin/bash
```

**Database Connection Issues:**
```bash
# Test database connection
docker-compose exec homepot-api python -c "
from homepot.database import DatabaseService
import asyncio
async def test():
    db = DatabaseService()
    await db.initialize()
    print('Database connection successful')
asyncio.run(test())
"
```

**Performance Issues:**
```bash
# Monitor resource usage
docker stats

# Check application metrics
curl http://localhost:8000/metrics

# Profile application
docker-compose exec homepot-api python -m cProfile -o profile.stats -m homepot.main
```

---

*This completes the HOMEPOT documentation suite. For additional help, refer to the [GitHub repository](https://github.com/brunel-opensim/homepot-client) or contact the development team.*
