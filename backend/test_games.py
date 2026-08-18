"""
Tests for /api/games. pytest collects any file named test_*.py and runs
every function in it named test_* — no registration, just naming.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from models import VideoGame


def test_list_games_returns_seeded_rows(client: TestClient, session: Session) -> None:
    # Asking for both fixtures wires everything: session gives us fresh
    # tables on the test DB, client routes the app's queries to that session.
    session.add(VideoGame(title="Outer Wilds", platform="PC", status="beaten"))
    session.add(VideoGame(title="Chrono Trigger", platform="SNES", status="notPlayed"))
    session.commit()

    response = client.get("/api/games")

    assert response.status_code == 200

    games = response.json()
    assert len(games) == 2

    # Shape check on one row: the exact keys the frontend will rely on,
    # and the values we just inserted coming back out.
    first = games[0]
    assert set(first.keys()) == {"id", "title", "platform", "status", "created_at"}
    assert first["title"] == "Outer Wilds"
    assert first["platform"] == "PC"
    assert first["status"] == "beaten"
    assert isinstance(first["id"], int)
