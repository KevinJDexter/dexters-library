# Dexter's Library

A tracker for my own game collection and achievements.

A learning project: Angular frontend, Python (FastAPI) backend, PostgreSQL, deployed so
it works on desktop and phone.

## Layout

```
dexters-library/
├── frontend/     Angular 22 app (standalone components, signals)
├── backend/      Python FastAPI API
│   ├── alembic/      Database migrations
│   └── video_games/  Feature package: models, routes, IGDB client
└── CLAUDE.md     Project instructions for AI tooling
```

One repository, two folders. Everything versions together, one deploy story to learn.

## Prerequisites

- **Python 3.9+** (the venv currently runs 3.9)
- **Node 20+** for the Angular CLI
- **PostgreSQL** running locally — [Postgres.app](https://postgresapp.com) on macOS.
  Its command-line tools aren't on `PATH` by default; add them if you want `psql`:
  ```bash
  export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"
  ```

Create two local databases — one for development, one for tests:

```bash
createdb dexters_library_dev
createdb dexters_library_test
```

The test database name **must** end in `_test`. The test suite drops and recreates
tables, and refuses to run against anything not named that way.

## Configuration

The backend reads everything from `backend/.env`, which is gitignored and never
committed. Create it with:

```
DATABASE_URL=postgresql+psycopg://localhost/dexters_library_dev
TEST_DATABASE_URL=postgresql+psycopg://localhost/dexters_library_test
WRITE_SECRET=any-long-random-string
IGDB_CLIENT_ID=...
IGDB_CLIENT_SECRET=...
```

Notes:

- The `postgresql+psycopg://` prefix is SQLAlchemy's driver syntax. `pg_dump` and
  `psql` want a plain `postgresql://` URL instead — a real trip hazard.
- `WRITE_SECRET` guards every write endpoint plus the IGDB search. Generate one with
  `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`.
- IGDB credentials come from a [Twitch developer application](https://dev.twitch.tv/console/apps)
  (a Twitch account with phone-verified 2FA is required). **The API refuses to start
  without them.**

Every one of these fails loudly at startup if missing, rather than breaking later in
some confusing way.

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv          # create an isolated Python environment
source .venv/bin/activate      # switch into it (do this every new terminal)
pip install -r requirements.txt
alembic upgrade head           # build the schema
python seed.py                 # optional: ten starter games
uvicorn main:app --reload      # runs on http://127.0.0.1:8000
```

Check it: open <http://127.0.0.1:8000/api/health> — you should see
`{"status":"ok","message":"Hello from Python and Postgres","database":"ok"}`.

If `database` says `unreachable`, Postgres isn't running or `DATABASE_URL` is wrong.

Bonus: <http://127.0.0.1:8000/docs> gives you interactive API documentation that
FastAPI generates for free from the code.

### Frontend

```bash
cd frontend
npm install
npm start                      # runs on http://localhost:4200
```

`ng serve` swaps `environments/environment.ts` for `environment.development.ts`, which
points the app at `http://127.0.0.1:8000`. Nothing to configure locally.

## Running both

Two terminals. Backend on `:8000`, frontend on `:4200`. The frontend calls the backend;
CORS is already configured in `backend/main.py` to allow it.

**The backend must be running**, or the game list shows its error state — the frontend
has no mock data any more.

## Tests

```bash
cd backend
.venv/bin/python -m pytest        # runs against TEST_DATABASE_URL
```

No network is required: the IGDB client's HTTP calls are faked in tests.

## Database changes

Alembic owns the schema. `create_all` is gone — starting the app never alters the
database.

```bash
alembic revision --autogenerate -m "what changed"   # generate
alembic upgrade head                                 # apply
alembic current                                      # where am I?
```

**Read every generated migration before running it.** Autogenerate is reliable for
added columns and tables, and unreliable for renames — it will happily emit
drop-then-create and lose the data.

To target a database other than the one in `.env` (production, say), override the
variable for that one command rather than editing the file:

```bash
DATABASE_URL="postgresql+psycopg://..." alembic upgrade head
```

Back up first: `pg_dump "postgresql://..." --no-owner --no-privileges -f backup.sql`

## Deployment

Render, free tier, two services:

- **API** — start command runs `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`.
  All five environment variables above must be set there too, with `DATABASE_URL`
  pointing at Neon.
- **Static site** — build command is `npm run build`, which injects `WRITE_SECRET`
  at build time via esbuild's `--define`. That variable must be set on the static
  site as well, or writes will 401 in production.

Deployed API: <https://dexters-library-api.onrender.com>

The free tier sleeps when idle, so the first request after a while takes 30-60 seconds.
The UI treats that as a loading state, not an error.
