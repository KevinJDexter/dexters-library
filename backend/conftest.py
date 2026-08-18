"""
Shared pytest setup. pytest auto-discovers this file by its name — every test
in this directory can use the fixtures below without importing them.

Tests run against TEST_DATABASE_URL (never DATABASE_URL) and create/drop all
tables around each test, so the dev database is never touched.
"""

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from database import get_session
from main import app

load_dotenv()

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# --- Safety rail (DL-8) ---------------------------------------------------
# Tests DROP TABLES. This guard makes it impossible to point them at a real
# database by accident: the URL must be set, and the database name must end
# in _test. Runs at import time, so pytest refuses to start if it fails.
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is not set — add it to backend/.env")

_db_name = TEST_DATABASE_URL.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
if not _db_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run: test database is named {_db_name!r}, which doesn't "
        "end in _test. Tests drop tables — point TEST_DATABASE_URL at a "
        "dedicated *_test database."
    )
# ---------------------------------------------------------------------------

test_engine = create_engine(TEST_DATABASE_URL)


# A fixture is a function whose return value pytest injects into any test
# that names it as a parameter — dependency injection again, keyed on the
# parameter name matching the fixture name.
@pytest.fixture
def session():
    # Fresh tables before each test, dropped after — every test starts from
    # a blank, known state and leaves nothing behind.
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session  # the test runs here, receiving this session
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def client(session: Session):
    # dependency_overrides is FastAPI's test hook: any route asking for
    # get_session gets our test session instead. The app code never knows.
    def get_test_session():
        yield session

    app.dependency_overrides[get_session] = get_test_session
    # No `with` block, deliberately: TestClient(app) used as a context
    # manager would run the lifespan (SELECT 1 + create_all) against the
    # real dev engine. Bare, it skips startup and only exercises routes.
    yield TestClient(app)
    app.dependency_overrides.clear()
