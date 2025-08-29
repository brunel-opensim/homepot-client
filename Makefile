# HOMEPOT Client Makefile
# Provides convenient commands for development and deployment

.PHONY: help build up down dev prod test clean logs shell

# Default target
help:
	@echo "HOMEPOT Client Development Commands"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make build    Build Docker image"
	@echo "  make up       Start services (development mode)"
	@echo "  make down     Stop services"
	@echo "  make dev      Start in development mode with hot reload"
	@echo "  make prod     Start in production mode"
	@echo "  make logs     Show service logs"
	@echo "  make shell    Open shell in running container"
	@echo ""
	@echo "Development Commands:"
	@echo "  make test     Run tests in container"
	@echo "  make clean    Clean up containers and images"
	@echo ""

# Docker commands
build:
	docker-compose build

up:
	docker-compose up

down:
	docker-compose down

dev:
	HOMEPOT_ENV=development HOMEPOT_SOURCE_MOUNT=./src docker-compose up --build

prod:
	HOMEPOT_ENV=production docker-compose up --build -d

logs:
	docker-compose logs -f

shell:
	docker-compose exec homepot-client /bin/bash

# Development commands
test:
	docker-compose exec homepot-client pytest

clean:
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -f

# Setup commands
setup:
	cp .env.example .env
	@echo "Environment file created. Please edit .env as needed."
	@echo "For development, uncomment HOMEPOT_SOURCE_MOUNT=./src in .env"
