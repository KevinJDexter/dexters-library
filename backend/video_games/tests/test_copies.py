"""
Tests for the ownership model: platforms and copies.

The rule these exist to protect: ownership is *derived* from copy rows, never
stored as a flag. A game is in the library if it has at least one copy and in
Watching if it has none, so a row count is the only thing that can answer
"do I have this" — and a row count can't disagree with itself.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from video_games.models import Copy, CopyAccess, CopyFormat, Platform, VideoGame


def make_game(session: Session, **overrides) -> VideoGame:
    fields = {"title": "Assassin's Creed", "platform": "PS5", "status": "beaten"}
    fields.update(overrides)
    game = VideoGame(**fields)
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def make_platform(session: Session, name: str) -> Platform:
    platform = Platform(name=name)
    session.add(platform)
    session.commit()
    session.refresh(platform)
    return platform


# --- platform -------------------------------------------------------------


def test_platform_names_are_unique(session: Session) -> None:
    """A foreign key to this table is what makes "PS5" vs "Playstation 5"
    typos impossible — which only holds if the name itself can't duplicate."""
    make_platform(session, "PS5")

    session.add(Platform(name="PS5"))
    with pytest.raises(IntegrityError):
        session.commit()


# --- ownership is derived -------------------------------------------------


def test_a_game_with_no_copies_is_valid(session: Session) -> None:
    """The Watching case: tracked, fully described, not owned. This must be a
    perfectly ordinary row, not a special state."""
    game = make_game(session)

    assert game.copies == []


def test_a_game_can_be_owned_on_several_platforms(session: Session) -> None:
    """The problem the whole ticket exists to solve: one game, three copies,
    and status stays a property of the game rather than of each copy."""
    game = make_game(session)
    for name in ("PS5", "Steam", "Xbox Series X"):
        platform = make_platform(session, name)
        session.add(Copy(video_game_id=game.id, platform_id=platform.id))
    session.commit()
    session.refresh(game)

    assert {c.platform.name for c in game.copies} == {"PS5", "Steam", "Xbox Series X"}
    # One game, one status — not three records to keep in step.
    assert game.status == "beaten"


def test_the_same_platform_can_be_held_twice_in_different_formats(
    session: Session,
) -> None:
    """"Some games I own both physically and digitally" falls out for free:
    two copy rows, one game, same platform."""
    game = make_game(session)
    ps5 = make_platform(session, "PS5")
    session.add(
        Copy(
            video_game_id=game.id,
            platform_id=ps5.id,
            format=CopyFormat.PHYSICAL.value,
        )
    )
    session.add(
        Copy(
            video_game_id=game.id,
            platform_id=ps5.id,
            format=CopyFormat.DIGITAL.value,
        )
    )
    session.commit()
    session.refresh(game)

    assert {c.format for c in game.copies} == {"physical", "digital"}


def test_access_defaults_to_owned(session: Session) -> None:
    game = make_game(session)
    platform = make_platform(session, "PS5")
    copy = Copy(video_game_id=game.id, platform_id=platform.id)
    session.add(copy)
    session.commit()
    session.refresh(copy)

    assert copy.access == CopyAccess.OWNED.value
    # Unknown rather than guessed — migrated rows never recorded the medium.
    assert copy.format is None


def test_a_borrowed_copy_records_who_it_came_from(session: Session) -> None:
    """A borrowed game is playable right now, so it's a copy — and "what do I
    still need to give back" needs a real column to be answerable."""
    game = make_game(session)
    platform = make_platform(session, "Switch")
    session.add(
        Copy(
            video_game_id=game.id,
            platform_id=platform.id,
            access=CopyAccess.BORROWED.value,
            borrowed_from="Sam",
        )
    )
    session.commit()
    session.refresh(game)

    borrowed = game.copies[0]
    assert borrowed.access == "borrowed"
    assert borrowed.borrowed_from == "Sam"


def test_zero_copies_with_a_played_status_is_a_real_state(session: Session) -> None:
    """"Played it, don't own it any more" — sold the disc, let the sub lapse.
    Status and ownership stay independent so this combination survives."""
    game = make_game(session, status="beaten")

    assert game.copies == []
    assert game.status == "beaten"


# --- referential integrity ------------------------------------------------


def test_deleting_a_game_deletes_its_copies(session: Session) -> None:
    """ondelete=CASCADE on the foreign key. Without it, deleting any owned
    game would fail on a foreign-key violation."""
    game = make_game(session)
    platform = make_platform(session, "PS5")
    session.add(Copy(video_game_id=game.id, platform_id=platform.id))
    session.commit()

    session.delete(game)
    session.commit()

    assert session.exec(select(Copy)).all() == []
    # The platform itself survives — it's reference data, not owned by the game.
    assert len(session.exec(select(Platform)).all()) == 1


def test_deleting_a_platform_still_in_use_fails(session: Session) -> None:
    """Deliberately NOT cascading: losing every PS5 copy because a platform row
    was deleted would be silent data loss. Fail loudly instead."""
    game = make_game(session)
    platform = make_platform(session, "PS5")
    session.add(Copy(video_game_id=game.id, platform_id=platform.id))
    session.commit()

    session.delete(platform)
    with pytest.raises(IntegrityError):
        session.commit()
