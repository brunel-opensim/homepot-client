"""Imports for the app."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from homepot_client.app.api.API_v1.Api import api_v1_router

# App declaration
app = FastAPI(
    ttitle="HOMEPOT Client API",
    description="REST API for HOMEPOT device management and monitoring",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    # lifespan=lifespan,
)


# Create tables
# database.CreateTables()

# CORS settings
origins = [ 
    "http://localhost:8080",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3000",
    "http://192.168.0.112:3000",
    "http://192.168.0.112:3001",
    "http://192.168.0.112:8080"
]

# CORS settings
app.add_middleware(
    CORSMiddleware,
    # allow_origins=config.origins,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add to openAPI documentation
# config.idp.add_swagger_config(app)


# TEST BASE URL API (insecure/test)
@app.get("/")
def root() -> dict:
    """Root endpoint to test if the API is alive."""
    return {"message": "I Am Alive"}


# Incluse all routes from API v1
app.include_router(api_v1_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")  # nosec B104
