"""
The /api/health endpoint. Moved verbatim from main.py (DL-22).

Not a feature package: health is app-level infrastructure, so it sits at the
top level next to database.py and security.py rather than under a domain.
"""

from fastapi import APIRouter
from sqlmodel import Session, text

from database import engine

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    """Confirms the API is alive and can reach the database."""
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        database_status = "ok"
        message = "Hello from Python and Postgres"
    except Exception:
        database_status = "unreachable"
        message = "Hello from Python"

    return {
        "status": "ok",
        "message": message,
        "database": database_status,
    }
