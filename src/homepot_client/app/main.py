"""
Imports for the app
"""

from typing import List
from typing import Optional
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from jose.exceptions import ExpiredSignatureError
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
app.add_middleware(
    CORSMiddleware,
    # allow_origins=config.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add to openAPI documentation
# config.idp.add_swagger_config(app)


# TEST BASE URL API (insecure/test)
@app.get("/")
def root():
    return {"message": "I Am Alive"}


# Incluse all routes from API v1
app.include_router(api_v1_router, prefix="/api/v1")
