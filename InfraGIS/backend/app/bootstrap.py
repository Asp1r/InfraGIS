from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRole
from app.security import hash_password


def ensure_bootstrap_admin(db: Session) -> None:
    if not settings.admin_login or not settings.admin_password:
        return
    has_admin = db.scalar(select(User.id).where(User.role == UserRole.admin).limit(1))
    if has_admin:
        return
    existing = db.scalar(select(User).where(User.login == settings.admin_login))
    if existing:
        return
    user = User(
        login=settings.admin_login,
        password_hash=hash_password(settings.admin_password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
