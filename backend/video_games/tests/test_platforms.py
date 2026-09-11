"""
Tests for the platform endpoints.

Platform exists as a table rather than an enum precisely so a console
launching needs a row, not a deploy. These check that path works and that
the unique constraint surfaces as a recoverable error rather than a crash.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from video_games.models import Platform


def test_list_platforms_is_empty_initially(client: TestClient) -> None:
    response = client.get("/api/platforms")

    assert response.status_code == 200
    assert response.json() == []


def test_list_platforms_is_alphabetical(client: TestClient, session: Session) -> None:
    """Sorted server-side so every consumer gets the same order — the add/edit
    dropdown shouldn't have to re-sort it."""
    for name in ("Steam", "Gameboy", "PS5"):
        session.add(Platform(name=name))
    session.commit()

    names = [p["name"] for p in client.get("/api/platforms").json()]

    assert names == ["Gameboy", "PS5", "Steam"]


def test_create_platform(client: TestClient, write_headers: dict) -> None:
    response = client.post(
        "/api/platforms", json={"name": "Wii Virtual Console"}, headers=write_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Wii Virtual Console"
    assert isinstance(body["id"], int)

    assert [p["name"] for p in client.get("/api/platforms").json()] == [
        "Wii Virtual Console"
    ]


def test_create_platform_strips_whitespace(
    client: TestClient, write_headers: dict
) -> None:
    response = client.post(
        "/api/platforms", json={"name": "  PS5  "}, headers=write_headers
    )

    assert response.status_code == 201
    assert response.json()["name"] == "PS5"


def test_create_platform_rejects_a_blank_name(
    client: TestClient, write_headers: dict
) -> None:
    response = client.post(
        "/api/platforms", json={"name": "   "}, headers=write_headers
    )

    assert response.status_code == 422


def test_duplicate_platform_is_409_not_500(
    client: TestClient, write_headers: dict
) -> None:
    """The unique index is what makes "PS5" vs "Playstation 5" typos
    impossible. Hitting it is a client mistake, so it gets a 4xx — and the
    session has to survive it well enough to answer the next request."""
    client.post("/api/platforms", json={"name": "PS5"}, headers=write_headers)

    response = client.post(
        "/api/platforms", json={"name": "PS5"}, headers=write_headers
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    # Still exactly one, and the API is still working after the failed write.
    assert len(client.get("/api/platforms").json()) == 1


def test_create_platform_requires_the_secret(client: TestClient) -> None:
    response = client.post("/api/platforms", json={"name": "PS5"})

    assert response.status_code == 401
    assert client.get("/api/platforms").json() == []
