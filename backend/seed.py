"""
Seed script: fills an empty video_game table with ten starter games.

Run it from the backend/ directory:
    python seed.py

Re-runnable: if the table already has any rows, it does nothing. To re-seed
from scratch (e.g. after a model change), drop the table first:
    psql: DROP TABLE video_game;
then run the app or this script again.
"""

from sqlmodel import Session, SQLModel, select

from database import engine
from video_games.models import VideoGame

# Just data — a list of unsaved model instances. Nothing touches the
# database until seed() adds them to a session and commits.
SEED_GAMES = [
    # status holds a machine key (camelCase), not display text. The frontend
    # maps keys to labels it shows the user: notPlayed -> "Not Played", etc.
    # Full vocabulary: notPlayed, playing, beaten, onHold, completed, dropped.
    VideoGame(title="The Legend of Zelda: Tears of the Kingdom", platform="Switch", status="beaten"),
    VideoGame(title="Baldur's Gate 3", platform="PC", status="playing"),
    VideoGame(title="Elden Ring", platform="PS5", status="playing"),
    VideoGame(title="Hades", platform="Switch", status="completed"),
    VideoGame(title="Hollow Knight", platform="PC", status="notPlayed"),
    VideoGame(title="Halo Infinite", platform="Xbox", status="dropped"),
    VideoGame(title="Stardew Valley", platform="Switch", status="onHold"),
    VideoGame(title="God of War Ragnarök", platform="PS5", status="beaten"),
    VideoGame(title="Celeste", platform="PC", status="onHold"),
    VideoGame(title="Metroid Prime Remastered", platform="Switch", status="notPlayed"),
]


def seed() -> None:
    # Make sure the table exists so this script works on a fresh database
    # without needing the app to have started first. No-op if it's there.
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # select(VideoGame) is a query object; .first() runs it and returns
        # one row or None. Any row at all means we've already seeded — bail
        # out rather than double up (the ticket's re-runnable requirement).
        if session.exec(select(VideoGame)).first() is not None:
            print("video_game already has rows — nothing to do.")
            return

        # add_all just stages the objects in the session; nothing is sent to
        # Postgres until commit() writes them all in one transaction.
        session.add_all(SEED_GAMES)
        session.commit()
        print(f"Seeded {len(SEED_GAMES)} games.")


# Standard Python entry-point guard: this block runs only when the file is
# executed directly (`python seed.py`), NOT when something imports it. It's
# what keeps `import seed` from silently writing to the database.
if __name__ == "__main__":
    seed()
