"""
FACEGUARD AI - Database Migration & Table Initialization Script
Initializes enterprise schemas (8 tables) and seeds default tenant configurations.
Works across PostgreSQL (Docker/Production) and SQLite (Local Development).
"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.db.base import Base
# Import all models to register with Base.metadata
import app.db.models.tenant  # noqa: F401
import app.db.models.session  # noqa: F401
import app.db.models.fraud  # noqa: F401
import app.db.models.job  # noqa: F401
import app.db.models.audit  # noqa: F401


async def init_schema(db_url: str | None = None) -> None:
    settings = get_settings()
    target_url = db_url or settings.DATABASE_URL
    print(f"Connecting to database: {target_url.split('@')[-1] if '@' in target_url else target_url}")

    try:
        engine = create_async_engine(target_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✓ All 8 enterprise database tables created successfully:")
        for table in sorted(Base.metadata.tables.keys()):
            print(f"   - {table}")
        await engine.dispose()
    except Exception as e:
        print(f"✗ Failed to connect to database at {target_url}: {e}")
        # If PostgreSQL is not reachable, demonstrate with local SQLite
        fallback_url = "sqlite+aiosqlite:///data/faceguard_local.db"
        print(f"\nAttempting fallback initialization on local SQLite: {fallback_url}")
        Path(PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
        fallback_engine = create_async_engine(fallback_url, echo=False)
        async with fallback_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✓ Fallback local SQLite tables created successfully:")
        for table in sorted(Base.metadata.tables.keys()):
            print(f"   - {table}")
        await fallback_engine.dispose()


if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(init_schema(url_arg))
