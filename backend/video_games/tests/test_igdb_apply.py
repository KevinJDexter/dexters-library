"""
Tests for applying IGDB metadata through the HTTP layer.

The mapping itself is covered in test_metadata.py; these check the wiring —
that IGDB is contacted only when it should be, and that its failures surface
as sensible statuses rather than 500s.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from video_games.igdb import IgdbAuthError, IgdbGameDetail, IgdbTag, IgdbUnavailable
from video_games.models import VideoGame

DETAIL = IgdbGameDetail(
    igdb_id=119171,
    name="Baldur's Gate III",
    summary="An ancient evil has returned.",
    first_release_date=date(2023, 8, 3),
    cover_image_id="co670h",
    esrb_rating="M",
    max_local_players=2,
    max_online_players=4,
    tags=(IgdbTag("genre", "Role-playing (RPG)"),),
)


# --- create with a match --------------------------------------------------


def test_create_with_igdb_id_applies_metadata(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    fake = fake_igdb(detail=DETAIL)

    response = client.post(
        "/api/games",
        json={
            "title": "Baldur's Gate 3",
            "platform": "PC",
            "status": "playing",
            "igdb_id": 119171,
        },
        headers=write_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["igdb_id"] == 119171
    assert body["cover_image_id"] == "co670h"
    assert body["esrb_rating"] == "M"
    assert body["max_local_players"] == 2
    assert body["max_online_players"] == 4
    assert body["first_release_date"] == "2023-08-03"
    assert fake.detail_calls == [119171]


def test_create_without_igdb_id_never_contacts_igdb(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    """Manual entry must keep working with IGDB entirely out of the picture."""
    fake = fake_igdb(detail=DETAIL)

    response = client.post(
        "/api/games",
        json={"title": "Obscure Import", "platform": "Wii", "status": "notPlayed"},
        headers=write_headers,
    )

    assert response.status_code == 201
    assert response.json()["igdb_id"] is None
    assert fake.detail_calls == []


def test_csv_import_still_works_without_igdb(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    fake = fake_igdb(detail=DETAIL)

    response = client.post(
        "/api/games/import",
        files={"file": ("games.csv", "title,platform,status\nHades,Switch,beaten\n", "text/csv")},
        headers=write_headers,
    )

    assert response.status_code == 200
    assert fake.detail_calls == []


# --- re-applying to an existing game --------------------------------------


def test_apply_to_existing_game_links_and_fills(
    client: TestClient, session: Session, write_headers: dict, fake_igdb
) -> None:
    game = VideoGame(title="Baldur's Gate 3", platform="PC", status="playing")
    session.add(game)
    session.commit()
    session.refresh(game)
    fake = fake_igdb(detail=DETAIL)

    response = client.post(
        f"/api/games/{game.id}/igdb",
        json={"igdb_id": 119171},
        headers=write_headers,
    )

    assert response.status_code == 200
    assert response.json()["esrb_rating"] == "M"
    assert fake.detail_calls == [119171]


def test_resync_uses_the_stored_id_when_body_is_omitted(
    client: TestClient, session: Session, write_headers: dict, fake_igdb
) -> None:
    game = VideoGame(
        title="Baldur's Gate 3", platform="PC", status="playing", igdb_id=119171
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    fake = fake_igdb(detail=DETAIL)

    response = client.post(f"/api/games/{game.id}/igdb", headers=write_headers)

    assert response.status_code == 200
    assert fake.detail_calls == [119171]


def test_resync_never_overwrites_a_curated_value(
    client: TestClient, session: Session, write_headers: dict, fake_igdb
) -> None:
    """The behaviour that fails silently, asserted through the endpoint as
    well as the mapping function."""
    game = VideoGame(
        title="Baldur's Gate 3",
        platform="PC",
        status="playing",
        igdb_id=119171,
        esrb_rating="T",
        summary="My own note.",
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    fake_igdb(detail=DETAIL)

    body = client.post(f"/api/games/{game.id}/igdb", headers=write_headers).json()

    assert body["esrb_rating"] == "T"
    assert body["summary"] == "My own note."
    # The blank field was still filled.
    assert body["cover_image_id"] == "co670h"


def test_apply_without_any_igdb_id_is_400(
    client: TestClient, session: Session, write_headers: dict, fake_igdb
) -> None:
    game = VideoGame(title="Unlinked", platform="PC", status="playing")
    session.add(game)
    session.commit()
    session.refresh(game)
    fake = fake_igdb(detail=DETAIL)

    response = client.post(f"/api/games/{game.id}/igdb", headers=write_headers)

    assert response.status_code == 400
    assert fake.detail_calls == []


def test_apply_to_unknown_game_is_404(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    fake = fake_igdb(detail=DETAIL)

    response = client.post(
        "/api/games/999999/igdb", json={"igdb_id": 1}, headers=write_headers
    )

    assert response.status_code == 404
    # The game lookup happens first, so IGDB is never called.
    assert fake.detail_calls == []


def test_apply_requires_the_secret(client: TestClient, session: Session, fake_igdb) -> None:
    game = VideoGame(title="Unlinked", platform="PC", status="playing")
    session.add(game)
    session.commit()
    session.refresh(game)
    fake = fake_igdb(detail=DETAIL)

    response = client.post(f"/api/games/{game.id}/igdb", json={"igdb_id": 1})

    assert response.status_code == 401
    assert fake.detail_calls == []


# --- upstream failures ----------------------------------------------------


def test_unknown_igdb_id_is_404(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    # get_details returns None when IGDB has no such record.
    fake_igdb(detail=None)

    response = client.post(
        "/api/games",
        json={
            "title": "Ghost",
            "platform": "PC",
            "status": "playing",
            "igdb_id": 999999999,
        },
        headers=write_headers,
    )

    assert response.status_code == 404


def test_igdb_down_during_create_is_503_and_creates_nothing(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    fake_igdb(raises=IgdbUnavailable("connection refused"))

    response = client.post(
        "/api/games",
        json={
            "title": "Baldur's Gate 3",
            "platform": "PC",
            "status": "playing",
            "igdb_id": 119171,
        },
        headers=write_headers,
    )

    assert response.status_code == 503
    # Nothing was written — the caller can retry or save without a match.
    assert client.get("/api/games").json() == []


def test_bad_credentials_during_apply_is_502(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    fake_igdb(raises=IgdbAuthError("rejected"))

    response = client.post(
        "/api/games",
        json={
            "title": "Baldur's Gate 3",
            "platform": "PC",
            "status": "playing",
            "igdb_id": 119171,
        },
        headers=write_headers,
    )

    assert response.status_code == 502
