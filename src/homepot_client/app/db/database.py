"""Databse connection and session management for the HomePot Client application."""

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Build PostgreSQL connection URL
DataBaseUrl = (
    f"postgresql+psycopg2://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}"
    f"@{os.getenv('PGHOST')}/{os.getenv('PGDATABASE')}"
    f"?sslmode={os.getenv('PGSSLMODE', 'require')}"
)

try:
    engine = create_engine(DataBaseUrl, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base = declarative_base()
    logger.info("Database engine created successfully.")
except OperationalError as e:
    logger.error("Failed to connect to the database: %s", e)
    raise


def get_db():
    """Dependency for getting a database session (FastAPI style)."""
    db = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        logger.error("Database session error: %s", e)
        raise
    finally:
        if db is not None:
            db.close()


def create_tables():
    """Create all database tables."""
    try:
        # from db import models  # Ensure models are imported
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created successfully.")
    except Exception as e:
        logger.error("Error creating tables: %s", e)
        raise
