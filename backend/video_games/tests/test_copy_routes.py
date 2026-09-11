"""
Tests for the copy endpoints.

These cover the wiring; the model-level guarantees (cascade, uniqueness,
multi-platform ownership) live in test_copies.py.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from video_games.models import Copy, Platform, VideoGame


def seed(session: Session) -> tuple[int, int]:
    """One game and one platform. Returns their ids."""
    game = VideoGame(title="Assassin's Creed", platform="PS5", status="beaten")
    platform = Platform(name="PS5")
    session.add(game)
    session.add(platform)
    session.commit()
    session.refresh(game)
    session.refresh(platform)
    return game.id, platform.id


# --- listing --------------------------------------------------------------


def test_a_game_with_no_copies_lists_empty(client: TestClient, session: Session) -> None:
    """Not an error — this is the Watching state, and it's ordinary."""
    game_id, _ = seed(session)

    response = client.get(f"/api/games/{game_id}/copies")

    assert response.status_code == 200
    assert response.json() == []


def test_listing_copies_for_an_unknown_game_is_404(client: TestClient) -> None:
    assert client.get("/api/games/999999/copies").status_code == 404


# --- adding ---------------------------------------------------------------


def test_add_a_copy(client: TestClient, session: Session, write_headers: dict) -> None:
    game_id, platform_id = seed(session)

    response = client.post(
        f"/api/games/{game_id}/copies",
        json={"platform_id": platform_id, "format": "physical"},
        headers=write_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["platform_id"] == platform_id
    # The name travels with it so a card can render a badge without a join.
    assert body["platform_name"] == "PS5"
    assert body["format"] == "physical"
    assert body["access"] == "owned"


def test_add_a_borrowed_copy(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    game_id, platform_id = seed(session)

    response = client.post(
        f"/api/games/{game_id}/copies",
        json={
            "platform_id": platform_id,
            "access": "borrowed",
            "borrowed_from": "Sam",
        },
        headers=write_headers,
    )

    assert response.status_code == 201
    assert response.json()["borrowed_from"] == "Sam"


def test_borrowed_from_without_borrowed_access_is_422(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    """Storing "borrowed from Sam" on a copy marked Owned would be incoherent
    data that reads as authoritative later."""
    game_id, platform_id = seed(session)

    response = client.post(
        f"/api/games/{game_id}/copies",
        json={
            "platform_id": platform_id,
            "access": "owned",
            "borrowed_from": "Sam",
        },
        headers=write_headers,
    )

    assert response.status_code == 422


def test_invalid_format_is_422(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    game_id, platform_id = seed(session)

    response = client.post(
        f"/api/games/{game_id}/copies",
        json={"platform_id": platform_id, "format": "cartridge"},
        headers=write_headers,
    )

    assert response.status_code == 422


def test_unknown_platform_is_404_not_500(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    """Checked before the insert, so this names the problem instead of
    surfacing as a foreign-key violation."""
    game_id, _ = seed(session)

    response = client.post(
        f"/api/games/{game_id}/copies",
        json={"platform_id": 999999},
        headers=write_headers,
    )

    assert response.status_code == 404
    assert "platform" in response.json()["detail"].lower()


def test_the_same_platform_twice_is_allowed(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    """Physical and digital on one platform is two copies, not a conflict."""
    game_id, platform_id = seed(session)

    for fmt in ("physical", "digital"):
        response = client.post(
            f"/api/games/{game_id}/copies",
            json={"platform_id": platform_id, "format": fmt},
            headers=write_headers,
        )
        assert response.status_code == 201

    assert len(client.get(f"/api/games/{game_id}/copies").json()) == 2


def test_adding_a_copy_requires_the_secret(
    client: TestClient, session: Session
) -> None:
    game_id, platform_id = seed(session)

    response = client.post(
        f"/api/games/{game_id}/copies", json={"platform_id": platform_id}
    )

    assert response.status_code == 401
    assert client.get(f"/api/games/{game_id}/copies").json() == []


# --- deleting -------------------------------------------------------------


def test_delete_a_copy(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    game_id, platform_id = seed(session)
    created = client.post(
        f"/api/games/{game_id}/copies",
        json={"platform_id": platform_id},
        headers=write_headers,
    ).json()

    response = client.delete(f"/api/copies/{created['id']}", headers=write_headers)

    assert response.status_code == 204
    assert client.get(f"/api/games/{game_id}/copies").json() == []


def test_deleting_the_last_copy_moves_a_game_to_watching(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    """Nothing is toggled. Ownership is derived, so removing the last copy is
    the entire mechanism — the game itself is untouched."""
    game_id, platform_id = seed(session)
    created = client.post(
        f"/api/games/{game_id}/copies",
        json={"platform_id": platform_id},
        headers=write_headers,
    ).json()

    client.delete(f"/api/copies/{created['id']}", headers=write_headers)

    assert client.get(f"/api/games/{game_id}/copies").json() == []
    # The game still exists, still has its status and metadata.
    game = next(g for g in client.get("/api/games").json() if g["id"] == game_id)
    assert game["status"] == "beaten"


def test_deleting_an_unknown_copy_is_404(
    client: TestClient, write_headers: dict
) -> None:
    assert client.delete("/api/copies/999999", headers=write_headers).status_code == 404


def test_deleting_a_copy_requires_the_secret(
    client: TestClient, session: Session, write_headers: dict
) -> None:
    game_id, platform_id = seed(session)
    created = client.post(
        f"/api/games/{game_id}/copies",
        json={"platform_id": platform_id},
        headers=write_headers,
    ).json()

    response = client.delete(f"/api/copies/{created['id']}")

    assert response.status_code == 401
    assert len(client.get(f"/api/games/{game_id}/copies").json()) == 1

