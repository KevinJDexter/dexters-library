"""
Tests for GET /api/igdb/search.

The endpoint takes its IGDB client through Depends, so these override that
dependency with a stand-in. No network, and no need for httpx mocking here —
that's already covered where the client itself is tested.
"""

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from main import app
from video_games.igdb import (
    IgdbAuthError,
    IgdbError,
    IgdbGame,
    IgdbUnavailable,
    get_client,
)

FF6 = IgdbGame(
    igdb_id=1234,
    name="Final Fantasy VI",
    release_year=1994,
    cover_url="https://images.igdb.com/igdb/image/upload/t_cover_big/abc.jpg",
)


class FakeIgdbClient:
    """Stands in for IgdbClient. Either returns games or raises whatever the
    test wants, and records the arguments it was called with."""

    def __init__(self, results=None, raises: Optional[Exception] = None):
        self.results = results if results is not None else []
        self.raises = raises
        self.calls: list[tuple] = []

    def search(self, title: str, limit: int = 10):
        self.calls.append((title, limit))
        if self.raises:
            raise self.raises
        return self.results


@pytest.fixture
def fake_igdb():
    """Installs a FakeIgdbClient for the duration of one test.

    The fixture yields a setter rather than a client, because each test wants
    a differently-configured fake. Whatever gets installed is torn down after.
    """
    installed: list[FakeIgdbClient] = []

    def install(**kwargs) -> FakeIgdbClient:
        client = FakeIgdbClient(**kwargs)
        app.dependency_overrides[get_client] = lambda: client
        installed.append(client)
        return client

    yield install
    app.dependency_overrides.pop(get_client, None)


def test_search_returns_candidates(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake = fake_igdb(results=[FF6])

    response = client.get(
        "/api/igdb/search", params={"title": "final fantasy vi"}, headers=write_headers
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "igdb_id": 1234,
            "name": "Final Fantasy VI",
            "release_year": 1994,
            "cover_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/abc.jpg",
        }
    ]
    # The title reached the client unchanged, with the default limit.
    assert fake.calls == [("final fantasy vi", 10)]


def test_search_passes_limit_through(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake = fake_igdb(results=[])

    client.get(
        "/api/igdb/search",
        params={"title": "hades", "limit": 3},
        headers=write_headers,
    )

    assert fake.calls == [("hades", 3)]


def test_search_with_no_matches_returns_empty_list(
    client: TestClient, write_headers: dict, fake_igdb
) -> None:
    fake_igdb(results=[])

    response = client.get(
        "/api/igdb/search", params={"title": "zzzz"}, headers=write_headers
    )

    # Not an error: an obscure title simply has no match.
    assert response.status_code == 200
    assert response.json() == []


def test_search_requires_the_secret(client: TestClient, fake_igdb) -> None:
    fake = fake_igdb(results=[FF6])

    response = client.get("/api/igdb/search", params={"title": "anything"})

    assert response.status_code == 401
    # And IGDB was never called — the guard runs before the route body, so a
    # rejected request can't burn rate limit.
    assert fake.calls == []


def test_missing_title_is_422(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake_igdb(results=[])

    assert client.get("/api/igdb/search", headers=write_headers).status_code == 422


def test_blank_title_is_422(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake = fake_igdb(results=[])

    response = client.get(
        "/api/igdb/search", params={"title": ""}, headers=write_headers
    )

    assert response.status_code == 422
    assert fake.calls == []


def test_limit_above_cap_is_422(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake_igdb(results=[])

    response = client.get(
        "/api/igdb/search",
        params={"title": "hades", "limit": 500},
        headers=write_headers,
    )

    assert response.status_code == 422


# --- upstream failures map to sensible statuses, never a 500 --------------


def test_igdb_down_returns_503(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake_igdb(raises=IgdbUnavailable("connection refused"))

    response = client.get(
        "/api/igdb/search", params={"title": "hades"}, headers=write_headers
    )

    assert response.status_code == 503
    # The message has to be something the UI can show a person.
    assert "manually" in response.json()["detail"]


def test_bad_credentials_return_502(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake_igdb(raises=IgdbAuthError("rejected"))

    response = client.get(
        "/api/igdb/search", params={"title": "hades"}, headers=write_headers
    )

    assert response.status_code == 502


def test_other_igdb_errors_return_502(client: TestClient, write_headers: dict, fake_igdb) -> None:
    fake_igdb(raises=IgdbError("malformed query"))

    response = client.get(
        "/api/igdb/search", params={"title": "hades"}, headers=write_headers
    )

    assert response.status_code == 502
