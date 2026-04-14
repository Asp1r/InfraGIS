import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest"
os.environ["TESTING"] = "1"
os.environ["UPLOAD_DIR"] = "uploads_test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.main import app
from app.models import User, UserRole
from app.security import hash_password


@pytest.fixture
def db() -> Session:
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db: Session):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    admin = User(
        login="admin",
        password_hash=hash_password("adminpass"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def viewer_client(db: Session):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    admin = User(
        login="admin",
        password_hash=hash_password("adminpass"),
        role=UserRole.admin,
        is_active=True,
    )
    viewer = User(
        login="viewer1",
        password_hash=hash_password("viewerpass"),
        role=UserRole.viewer,
        is_active=True,
    )
    db.add_all([admin, viewer])
    db.commit()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
