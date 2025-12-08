# Docker Setup for HOMEPOT Backend

This directory contains the Docker configuration for running the HOMEPOT backend service along with PostgreSQL and Redis.

## Prerequisites

- Docker
- Docker Compose

## Services

- **backend**: The FastAPI application (Python 3.11).
- **db**: PostgreSQL 15 database.
- **redis**: Redis for caching and background tasks.

## Getting Started

1.  **Build and Run**:
    Run the following command in this directory to build the images and start the services:

    ```bash
    cd backend
    docker compose up --build (or) docker compose up -d --build
    ```

    The backend will be available at `http://localhost:8000`.
    The API documentation can be accessed at `http://localhost:8000/docs`.

2.  **Database Initialization**:
    The PostgreSQL database is initialized with the credentials defined in `docker-compose.yml`.
    
    If yow have specific initialization scripts (e.g., from `init-prostgress.md`), you can place them in a directory (e.g., `init-scripts`) and uncomment the volume mapping in `docker-compose.yml`:

    ```yaml
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ```

    Supported file extensions for initialization scripts are `.sh`, `.sql`, and `.sql.gz`.

3.  **Environment Variables**:
    The `docker-compose.yml` file sets default environment variables for development. You can override these by creating a `.env` file or modifying the `docker-compose.yml` directly.

    Key variables:
    - `DATABASE__URL`: Connection string for PostgreSQL.
    - `REDIS__URL`: Connection string for Redis.

4.  **Stopping the Services**:
    To stop the services, press `Ctrl+C` or run:

    ```bash
    docker compose down
    ```

    To stop and remove volumes (reset database):

    ```bash
    docker compose down -v
    ```
