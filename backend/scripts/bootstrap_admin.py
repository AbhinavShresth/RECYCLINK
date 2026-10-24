import argparse
import getpass
import re

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.identity import Role, User, UserProfile, UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a single explicitly requested administrator account")
    parser.add_argument("email")
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise SystemExit("A valid email address is required")
    password = getpass.getpass("Set administrator password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("An account with that email already exists")
        if db.get(Role, "ADMIN") is None:
            raise SystemExit("Run Alembic migrations before bootstrapping an administrator")
        user = User(email=email, password_hash=hash_password(password))
        user.profile = UserProfile(full_name=args.name.strip(), preferred_language="en")
        user.roles = [UserRole(role_code="USER"), UserRole(role_code="ADMIN")]
        db.add(user)
    print(f"Administrator account created: {email}")


if __name__ == "__main__":
    main()
