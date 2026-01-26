"""pytest 설정 및 fixtures."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from main import app


# 테스트용 인메모리 SQLite DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """테스트용 DB 세션."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    """각 테스트마다 새로운 DB 생성."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """테스트 클라이언트."""
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()
