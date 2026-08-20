"""
Tests for /api/games. pytest collects any file named test_*.py and runs
every function in it named test_* — no registration, just naming.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from video_games.models import VideoGame


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


def test_update_game_changes_only_sent_fields(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    game = VideoGame(title="Hollow Knight", platform="PC", status="notPlayed")
    session.add(game)
    session.commit()
    session.refresh(game)

    response = client.patch(
        f"/api/games/{game.id}",
        json={"status": "beaten"},
        headers=write_headers,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "beaten"
    # The whole point of PATCH: unsent fields survive untouched.
    assert updated["title"] == "Hollow Knight"
    assert updated["platform"] == "PC"


def test_update_missing_game_is_404(client: TestClient, write_headers: dict) -> None:
    response = client.patch(
        "/api/games/999999", json={"status": "beaten"}, headers=write_headers
    )

    assert response.status_code == 404


def test_update_without_secret_is_401(client: TestClient, session: Session) -> None:
    game = VideoGame(title="Hollow Knight", platform="PC", status="notPlayed")
    session.add(game)
    session.commit()
    session.refresh(game)

    response = client.patch(f"/api/games/{game.id}", json={"status": "beaten"})

    assert response.status_code == 401
    # The row must be untouched, not just the response rejected.
    session.refresh(game)
    assert game.status == "notPlayed"


def test_delete_game_removes_it(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    game = VideoGame(title="Hollow Knight", platform="PC", status="notPlayed")
    session.add(game)
    session.commit()
    session.refresh(game)

    response = client.delete(f"/api/games/{game.id}", headers=write_headers)

    assert response.status_code == 204
    assert client.get("/api/games").json() == []


def test_delete_missing_game_is_404(client: TestClient, write_headers: dict) -> None:
    response = client.delete("/api/games/999999", headers=write_headers)

    assert response.status_code == 404


def test_delete_without_secret_is_401(client: TestClient, session: Session) -> None:
    game = VideoGame(title="Hollow Knight", platform="PC", status="notPlayed")
    session.add(game)
    session.commit()
    session.refresh(game)

    response = client.delete(f"/api/games/{game.id}")

    assert response.status_code == 401
    # Still there.
    assert len(client.get("/api/games").json()) == 1
