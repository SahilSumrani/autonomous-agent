import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.config.settings import settings
from services.api.app.core.database import Base, get_db
from services.api.app.main import app
from services.api.app.models.crm import Organization

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def test_db_session():
    """Create in-memory SQLite tables, yield test session, and tear down cleanly."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        # Create default test organizations
        org1 = Organization(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="TechVerse Dev Workspace",
            slug="techverse-dev",
        )
        org2 = Organization(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            name="Competitor Workspace",
            slug="competitor-org",
        )
        session.add(org1)
        session.add(org2)
        await session.commit()

        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(test_db_session: AsyncSession):
    """FastAPI test client with database dependency overridden to test DB session."""
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
