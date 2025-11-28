"""Tests for user authentication logic."""

from datetime import datetime, timezone

from homepot.app.auth_utils import hash_password, verify_password
from homepot.models import User


def test_user_signup(temp_db):
    """Test user signup logic."""
    db = temp_db()

    # Create new user
    user = User(
        email="newuser@example.com",
        username="newuser",
        hashed_password=hash_password("password123"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Assertions
    assert user.id is not None
    assert user.email == "newuser@example.com"
    assert user.username == "newuser"
    assert verify_password("password123", user.hashed_password)

    db.close()


def test_user_login_success(temp_db):
    """Test successful login with correct credentials."""
    db = temp_db()

    # Setup test user
    user = User(
        email="loginuser@example.com",
        username="loginuser",
        hashed_password=hash_password("correctpass"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()

    # Verify login checks
    stored_user = db.query(User).filter(User.email == "loginuser@example.com").first()
    assert stored_user is not None
    assert verify_password("correctpass", stored_user.hashed_password)

    db.close()


def test_user_login_wrong_password(temp_db):
    """Test login fails when password is incorrect."""
    db = temp_db()

    # Setup test user
    user = User(
        email="wrongpass@example.com",
        username="wrongpass",
        hashed_password=hash_password("correctpass"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()

    stored_user = db.query(User).filter(User.email == "wrongpass@example.com").first()

    # Wrong password
    assert not verify_password("incorrectpass", stored_user.hashed_password)

    db.close()


def test_user_login_invalid_email(temp_db):
    """Test login fails when email does not exist."""
    db = temp_db()

    stored_user = db.query(User).filter(User.email == "noemail@example.com").first()

    # Should not exist
    assert stored_user is None

    db.close()


def test_user_delete_success(temp_db):
    """Test deleting an existing user."""
    db = temp_db()

    # Create user
    user = User(
        email="deleteuser@example.com",
        username="deleteuser",
        hashed_password=hash_password("pass123"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()

    # Ensure user exists before delete
    stored_user = db.query(User).filter(User.email == "deleteuser@example.com").first()
    assert stored_user is not None

    # Delete the user
    db.delete(stored_user)
    db.commit()

    # Verify deletion
    deleted_user = db.query(User).filter(User.email == "deleteuser@example.com").first()
    assert deleted_user is None

    db.close()


def test_user_delete_invalid_email(temp_db):
    """Test deleting a non-existing user."""
    db = temp_db()

    # Query user that does not exist
    user = db.query(User).filter(User.email == "notfound@example.com").first()

    # Should not exist
    assert user is None

    db.close()
