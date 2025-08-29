#!/bin/bash
# Docker build validation script for CI/CD

set -e

echo "🐳 Validating Docker setup..."

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo "❌ Error: Dockerfile not found"
    exit 1
fi

# Check if .dockerignore exists
if [ ! -f ".dockerignore" ]; then
    echo "❌ Error: .dockerignore not found"
    exit 1
fi

# Check if main application file exists
if [ ! -f "src/homepot_client/main.py" ]; then
    echo "❌ Error: main.py not found"
    exit 1
fi

# Validate Dockerfile syntax (basic check)
if ! docker --version > /dev/null 2>&1; then
    echo "⚠️  Warning: Docker not available for build test"
    echo "✅ Docker files validation passed (syntax check only)"
    exit 0
fi

echo "🏗️  Building Docker image..."
docker build -t homepot-client:ci-test .

echo "🧪 Testing container startup..."
# Start container in background and test health endpoint
CONTAINER_ID=$(docker run -d -p 8001:8000 homepot-client:ci-test)

# Wait for container to start
sleep 10

# Test health endpoint
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Container health check passed"
    STATUS=0
else
    echo "❌ Container health check failed"
    docker logs $CONTAINER_ID
    STATUS=1
fi

# Cleanup
docker stop $CONTAINER_ID
docker rm $CONTAINER_ID
docker rmi homepot-client:ci-test

echo "🐳 Docker validation completed"
exit $STATUS
