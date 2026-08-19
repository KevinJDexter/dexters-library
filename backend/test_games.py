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


def test_create_game_persists(client: TestClient, write_headers: dict) -> None:
    response = client.post(
        "/api/games",
        json={"title": "Final Fantasy VI", "platform": "SNES", "status": "beaten"},
        headers=write_headers,
    )

    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Final Fantasy VI"
    assert isinstance(created["id"], int)

    # Persistence check: a fresh GET must include the new row — proving it
    # reached the database, not just the response.
    games = client.get("/api/games").json()
    assert any(g["id"] == created["id"] for g in games)


def test_create_game_rejects_blank_title(client: TestClient, write_headers: dict) -> None:
    response = client.post(
        "/api/games",
        # Whitespace-only: the strip-then-validate order in VideoGameCreate
        # is exactly what this exercises.
        json={"title": "   ", "platform": "SNES", "status": "beaten"},
        headers=write_headers,
    )

    assert response.status_code == 422


def test_create_game_without_secret_is_401(client: TestClient) -> None:
    # A perfectly valid body — the ONLY thing wrong is the missing header,
    # so a 401 here can't be blamed on validation.
    response = client.post(
        "/api/games",
        json={"title": "Final Fantasy VI", "platform": "SNES", "status": "beaten"},
    )

    assert response.status_code == 401
    # And nothing must have been written.
    assert client.get("/api/games").json() == []
