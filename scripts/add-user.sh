#!/bin/bash
# Script to manually add a user to the HOMEPOT database
# Usage: ./scripts/add-user.sh <username> <email> <password> [is_admin]

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <username> <email> <password> [is_admin]"
    echo "Example: $0 john_doe john@example.com secret123 true"
    exit 1
fi

USERNAME="$1"
EMAIL="$2"
PASSWORD="$3"
IS_ADMIN="${4:-false}"

# Database connection details (should match init-postgresql.sh)
DB_NAME="homepot_db"
DB_USER="homepot_user"
DB_PASSWORD="homepot_dev_password"
DB_HOST="localhost"
DB_PORT="5432"

# Export password for psql
export PGPASSWORD="$DB_PASSWORD"

# Python script to hash password and insert user
# We use a temporary python script to handle password hashing correctly using the backend's logic
cat << EOF > temp_add_user.py
import sys
import os
import bcrypt

# Workaround for passlib/bcrypt 4.0+ incompatibility
if not hasattr(bcrypt, '__about__'):
    class About:
        __version__ = bcrypt.__version__
    bcrypt.__about__ = About()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Add backend src to path to import models
sys.path.append(os.path.abspath("backend/src"))

from homepot.models import User, Base

# Database URL
DATABASE_URL = "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_user(username, email, password, is_admin):
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Check if user exists
        existing_user = db.query(User).filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            print(f"Error: User with email {email} or username {username} already exists.")
            sys.exit(1)

        hashed_password = pwd_context.hash(password)
        
        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_admin=is_admin.lower() == 'true',
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        print(f"Successfully created user: {username} ({email})")
        
    except Exception as e:
        print(f"Error creating user: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    create_user(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
EOF

# Run the python script
# We need to activate the virtual environment if it exists, or assume python is available
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate
fi

# Install passlib if needed (it should be in requirements, but just in case)
pip install passlib bcrypt sqlalchemy psycopg2-binary > /dev/null 2>&1 || true

python3 temp_add_user.py "$USERNAME" "$EMAIL" "$PASSWORD" "$IS_ADMIN"
RESULT=$?

# Cleanup
rm temp_add_user.py

if [ $RESULT -eq 0 ]; then
    echo -e "${GREEN}User added successfully!${NC}"
    echo ""
    echo "To delete this user later, run:"
    echo "export PGPASSWORD='$DB_PASSWORD' && psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c \"DELETE FROM users WHERE username = '$USERNAME';\""
else
    echo -e "${RED}Failed to add user.${NC}"
    exit 1
fi
