from collections.abc import AsyncGenerator
import socket

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.base import Base
from app.api.deps import get_db
from app.main import app


def _check_pg():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", 5432)) == 0
        s.close()
        return result
    except Exception:
        return False


PG_AVAILABLE = _check_pg()
requires_pg = pytest.mark.skipif(not PG_AVAILABLE, reason="PostgreSQL not available")

# Use a separate test database
_base = settings.database_url.rsplit("/", 1)[0]
TEST_DATABASE_URL = f"{_base}/aiwriter_test"

_engine_created = False
test_engine = None
test_session_factory = None


def _ensure_engine():
    global _engine_created, test_engine, test_session_factory
    if not _engine_created:
        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
        test_session_factory = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        _engine_created = True


@pytest.fixture
async def setup_db():
    _ensure_engine()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(setup_db) -> AsyncGenerator[AsyncSession, None]:
    _ensure_engine()
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    _ensure_engine()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {settings.auth_token}"}
