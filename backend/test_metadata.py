"""
Tests for applying IGDB metadata onto a game.

The fill-blanks-never-overwrite rule is the reason this file exists. It's the
one behaviour here that fails *silently* — a re-sync that quietly replaces a
curated value looks exactly like a re-sync that worked.
"""

from datetime import date

from sqlmodel import Session, select

from video_games.igdb import IgdbGameDetail, IgdbTag
from video_games.metadata import apply_igdb_detail, get_or_create_tags
from video_games.models import Tag, VideoGame

DETAIL = IgdbGameDetail(
    igdb_id=119171,
    name="Baldur's Gate III",
    summary="An ancient evil has returned.",
    first_release_date=date(2023, 8, 3),
    cover_image_id="co670h",
    esrb_rating="M",
    max_local_players=2,
    max_online_players=4,
    tags=(
        IgdbTag("genre", "Role-playing (RPG)"),
        IgdbTag("theme", "Fantasy"),
        IgdbTag("collection", "Baldur's Gate"),
    ),
)


def make_game(**overrides) -> VideoGame:
    fields = {"title": "Baldur's Gate 3", "platform": "PC", "status": "playing"}
    fields.update(overrides)
    return VideoGame(**fields)


# --- tag matching and creation --------------------------------------------


def test_get_or_create_tags_creates_new_rows(session: Session) -> None:
    tags = get_or_create_tags(session, [IgdbTag("genre", "Indie")])
    session.commit()

    assert len(tags) == 1
    assert (tags[0].kind, tags[0].name) == ("genre", "Indie")
    assert len(session.exec(select(Tag)).all()) == 1


def test_get_or_create_tags_reuses_an_existing_row(session: Session) -> None:
    """The whole point: IGDB names are inputs to a taxonomy Dexter owns, so a
    second import must attach to the same row rather than duplicating it."""
    existing = Tag(kind="genre", name="Indie")
    session.add(existing)
    session.commit()

    tags = get_or_create_tags(session, [IgdbTag("genre", "Indie")])
    session.commit()

    assert tags[0].id == existing.id
    assert len(session.exec(select(Tag)).all()) == 1


def test_get_or_create_tags_treats_kind_as_part_of_the_identity(session: Session) -> None:
    """'Action' is both a genre and a theme in IGDB. Two rows, not one."""
    tags = get_or_create_tags(
        session, [IgdbTag("genre", "Action"), IgdbTag("theme", "Action")]
    )
    session.commit()

    assert len({t.id for t in tags}) == 2
    assert len(session.exec(select(Tag)).all()) == 2


def test_get_or_create_tags_does_not_duplicate_within_one_call(session: Session) -> None:
    tags = get_or_create_tags(
        session, [IgdbTag("genre", "Indie"), IgdbTag("genre", "Indie")]
    )
    session.commit()

    assert len(session.exec(select(Tag)).all()) == 1
    assert tags[0].id == tags[1].id


# --- applying to a blank game ---------------------------------------------


def test_apply_fills_every_empty_field(session: Session) -> None:
    game = make_game()
    session.add(game)
    session.commit()

    apply_igdb_detail(session, game, DETAIL)
    session.commit()
    session.refresh(game)

    assert game.igdb_id == 119171
    assert game.summary == "An ancient evil has returned."
    assert game.first_release_date == date(2023, 8, 3)
    assert game.cover_image_id == "co670h"
    assert game.esrb_rating == "M"
    assert game.max_local_players == 2
    assert game.max_online_players == 4
    assert {(t.kind, t.name) for t in game.tags} == {
        ("genre", "Role-playing (RPG)"),
        ("theme", "Fantasy"),
        ("collection", "Baldur's Gate"),
    }


def test_apply_leaves_title_platform_and_status_alone(session: Session) -> None:
    """IGDB knows a title, but the one Dexter typed is the one he wants."""
    game = make_game(title="BG3 (my copy)", platform="Steam Deck", status="beaten")
    session.add(game)
    session.commit()

    apply_igdb_detail(session, game, DETAIL)
    session.commit()
    session.refresh(game)

    assert game.title == "BG3 (my copy)"
    assert game.platform == "Steam Deck"
    assert game.status == "beaten"


# --- the rule: never overwrite --------------------------------------------


def test_apply_never_overwrites_a_populated_field(session: Session) -> None:
    """The behaviour that fails silently, so it gets asserted explicitly."""
    game = make_game(
        summary="My own note about this game.",
        esrb_rating="T",
        cover_image_id="my-own-image",
        max_local_players=8,
        first_release_date=date(1999, 1, 1),
    )
    session.add(game)
    session.commit()

    apply_igdb_detail(session, game, DETAIL)
    session.commit()
    session.refresh(game)

    assert game.summary == "My own note about this game."
    assert game.esrb_rating == "T"
    assert game.cover_image_id == "my-own-image"
    assert game.max_local_players == 8
    assert game.first_release_date == date(1999, 1, 1)
    # The one blank field still got filled.
    assert game.max_online_players == 4


def test_apply_treats_zero_as_a_real_value_not_a_blank(session: Session) -> None:
    """0 is falsy in Python but it's a value someone chose — the check has to
    be `is None`, not truthiness."""
    game = make_game(max_local_players=0)
    session.add(game)
    session.commit()

    apply_igdb_detail(session, game, DETAIL)
    session.commit()
    session.refresh(game)

    assert game.max_local_players == 0


def test_apply_does_not_repoint_an_existing_igdb_id(session: Session) -> None:
    game = make_game(igdb_id=999)
    session.add(game)
    session.commit()

    apply_igdb_detail(session, game, DETAIL)
    session.commit()
    session.refresh(game)

    assert game.igdb_id == 999


def test_reapplying_keeps_manual_tags_and_adds_nothing_twice(session: Session) -> None:
    """A re-sync must not undo curation: a hand-added tag survives, and the
    IGDB ones don't pile up duplicates."""
    game = make_game()
    musou = Tag(kind="genre", name="Musou")
    game.tags.append(musou)
    session.add(game)
    session.commit()

    apply_igdb_detail(session, game, DETAIL)
    session.commit()
    apply_igdb_detail(session, game, DETAIL)
    session.commit()
    session.refresh(game)

    names = [(t.kind, t.name) for t in game.tags]
    assert ("genre", "Musou") in names
    # 1 manual + 3 from IGDB, with the second apply adding none.
    assert len(names) == 4
    assert len(names) == len(set(names))


def test_apply_handles_a_detail_with_nothing_in_it(session: Session) -> None:
    """IGDB records are frequently sparse — an obscure import may have only
    a name."""
    game = make_game()
    session.add(game)
    session.commit()

    sparse = IgdbGameDetail(
        igdb_id=42,
        name="Obscure Import",
        summary=None,
        first_release_date=None,
        cover_image_id=None,
        esrb_rating=None,
        max_local_players=None,
        max_online_players=None,
        tags=(),
    )
    apply_igdb_detail(session, game, sparse)
    session.commit()
    session.refresh(game)

    assert game.igdb_id == 42
    assert game.summary is None
    assert game.tags == []
