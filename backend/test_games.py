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


# --- CSV export -----------------------------------------------------------


def test_export_returns_csv(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    session.add(VideoGame(title="Celeste", platform="PC", status="completed"))
    session.commit()

    response = client.get("/api/games/export", headers=write_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    lines = response.text.strip().splitlines()
    assert lines[0] == "title,platform,status"
    assert lines[1] == "Celeste,PC,completed"


def test_export_without_secret_is_401(client: TestClient) -> None:
    assert client.get("/api/games/export").status_code == 401


# --- CSV import -----------------------------------------------------------


def _csv_upload(body: str) -> dict:
    """Build the multipart payload httpx expects: (filename, content, type)."""
    return {"file": ("games.csv", body, "text/csv")}


def test_import_inserts_rows(client: TestClient, write_headers: dict) -> None:
    body = "title,platform,status\nChrono Trigger,SNES,beaten\nOuter Wilds,PC,completed\n"

    response = client.post(
        "/api/games/import", files=_csv_upload(body), headers=write_headers
    )

    assert response.status_code == 200
    assert response.json() == {"imported": 2}

    titles = {g["title"] for g in client.get("/api/games").json()}
    assert titles == {"Chrono Trigger", "Outer Wilds"}


def test_import_reports_every_bad_row_and_inserts_nothing(
    client: TestClient, write_headers: dict
) -> None:
    # Row 2 is fine; row 3 has a blank title, row 4 a blank platform.
    body = (
        "title,platform,status\n"
        "Valid Game,PC,playing\n"
        "   ,PS5,beaten\n"
        "Another,,notPlayed\n"
    )

    response = client.post(
        "/api/games/import", files=_csv_upload(body), headers=write_headers
    )

    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    # Both failures reported, not just the first — and numbered as the user
    # sees them in a spreadsheet.
    assert [(e["row"], e["field"]) for e in errors] == [(3, "title"), (4, "platform")]

    # All-or-nothing: the one valid row must NOT have been inserted.
    assert client.get("/api/games").json() == []


def test_import_rejects_missing_columns(
    client: TestClient, write_headers: dict
) -> None:
    response = client.post(
        "/api/games/import",
        files=_csv_upload("name,console\nWrong,Columns\n"),
        headers=write_headers,
    )

    assert response.status_code == 422
    assert "Missing required column" in response.json()["detail"]


def test_import_rejects_header_only_file(
    client: TestClient, write_headers: dict
) -> None:
    response = client.post(
        "/api/games/import",
        files=_csv_upload("title,platform,status\n"),
        headers=write_headers,
    )

    assert response.status_code == 422


def test_import_without_secret_is_401(client: TestClient) -> None:
    body = "title,platform,status\nChrono Trigger,SNES,beaten\n"

    response = client.post("/api/games/import", files=_csv_upload(body))

    assert response.status_code == 401
    assert client.get("/api/games").json() == []


def test_export_output_can_be_reimported(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    """The round trip is the real contract: what comes out must go back in."""
    session.add(VideoGame(title="Hades", platform="Switch", status="completed"))
    session.commit()

    exported = client.get("/api/games/export", headers=write_headers).text

    response = client.post(
        "/api/games/import", files=_csv_upload(exported), headers=write_headers
    )

    assert response.status_code == 200
    assert response.json() == {"imported": 1}
