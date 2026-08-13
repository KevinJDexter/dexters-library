# Backend Conventions

Loaded automatically when Claude Code reads a file under `backend/`. Root
CLAUDE.md's division of labor and jargon rules still apply here.

## The rule that matters most

I'm a Python beginner. You draft backend code, I review it. That only works
if what you hand me is small enough to actually review.

- Land changes in the smallest independently-reviewable diff — one model
  change, one endpoint, one step. Not a finished feature in one message.
- If a request would naturally produce a big diff, break it into an
  ordered list of small steps and confirm the plan with me before writing
  any code.

## Stack

FastAPI + SQLModel. PostgreSQL on Neon. Deployed on Render.

## Schema

- Schema is created at startup via `SQLModel.metadata.create_all()`. No
  Alembic, no migration files — deliberate, given ~10 rows of seed data.
  Adding a column means dropping and re-seeding.
- Do NOT introduce Alembic or migration scaffolding unless I explicitly
  ask. If a change seems to need a real migration, stop and tell me.

## Connection & config

- `DATABASE_URL` comes from the environment. Never hardcode it, never
  commit it.
- Use Neon's *direct* connection string, not the pooled one — this is a
  single long-running process, not serverless functions. Don't suggest
  the pooled string.

## Testing

- Tests run against a local PostgreSQL database, not SQLite. Don't
  suggest SQLite for backend tests, even for speed — type looseness
  there can hide a red deploy behind green tests.

## Data modeling

- `platform` and `status` on `Game` are plain string columns. No lookup
  tables, enums, or foreign keys for these. Don't introduce that
  structure unasked.

## Workflow

- Vertical slices: DB → API → tests → UI → deployed, one feature at a
  time. Never "all the models, then all the endpoints."
