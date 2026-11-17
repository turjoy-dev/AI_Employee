"""Idempotent seed script to create the initial admin account inside the database."""

from sqlalchemy import select

from backend.core.security import get_password_hash
from backend.database.connection import SessionLocal
from backend.database.init_db import init_db
from backend.database.models import User

DEFAULT_ADMIN_EMAIL = "admin@aiemployee.com"
DEFAULT_ADMIN_PASSWORD = "AdminPassword!2026"


def seed_admin() -> None:
    """Initialize database schema and insert the default admin user if absent."""
    init_db()
    db = SessionLocal()
    try:
        existing = db.execute(
            select(User).where(User.email == DEFAULT_ADMIN_EMAIL)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Admin user already exists: {existing.email} (active={existing.is_active})")
            return

        admin = User(
            email=DEFAULT_ADMIN_EMAIL,
            hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Created admin user: {DEFAULT_ADMIN_EMAIL}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
