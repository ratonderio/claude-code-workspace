# Family HQ

A household task coordination, workload tracking and reporting system. Discord is (eventually) the family's friendly front door; behind it sits one SQLite database with a service layer, an activity ledger, and privacy rules baked into the data model.

This is a personal project, not a general-purpose task manager. It is meant to stay small enough to debug on a Tuesday night.

**Status:** Phase 1 (local core) is built and tested. Discord, recurrence, reports, Google and Obsidian are designed but not yet implemented. See [docs/roadmap.md](docs/roadmap.md).

## What works today

* People, projects, categories (configurable), tasks, with a full lifecycle: `INBOX, OPEN, PLANNED, IN_PROGRESS, WAITING, BLOCKED, DONE, CANCELLED`
* Assign, claim, release, start, wait, block, unblock, snooze, cancel, reopen, notes
* An append-only activity ledger, kept forever (finished work does not vanish)
* Three visibility scopes (`FAMILY`, `PERSONAL`, `PRIVATE_WORK`) enforced centrally, with leak tests
* Effort buckets (XS to XL) converted to relative workload points
* A CLI for everything above, with `--json` output for automation
* SQLite backups: online snapshot, integrity check, retention, and scrubbed copies that leave private work behind
* `family-hq run`: startup checks, migrations, scheduled backups (Discord plugs in here in Phase 2)

## Quick start

Requires Python 3.12 or newer.

```bash
cd family-hq
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip install -e ".[dev]"

cp config.example.toml config.toml        # then set your time zone
cp .env.example .env                      # secrets (none needed yet)
family-hq init --admin "Your Name"
```

Windows (PowerShell) setup, running as a service, and migrating to another machine are in [docs/deployment.md](docs/deployment.md).

## A tour

```bash
family-hq person add Mysti --role adult
family-hq person add Wyatt --discord-id 123456789012345678

family-hq project add "Fix Van"
family-hq task add "Fix bathroom sink" --owner Wyatt --priority high --effort m --due fri --category Repair
family-hq task add "Call mechanic" --mine --project "Fix Van" --effort xs --due tomorrow
family-hq task add "Clean garage" --effort l                       # unassigned: anyone can claim
family-hq task add "Prep quarterly review" --scope private-work    # only you will ever see this

family-hq task list                       # what is open (active statuses), with a workload summary
family-hq task list --mine --overdue
family-hq task list --all --done-since monday
family-hq --as Wyatt task claim 4bd4      # ids can be shortened to any unique prefix
family-hq task block 4bd4 "waiting on a part"
family-hq task show 4bd4                  # details plus the whole history
family-hq --json task list | jq .         # stable machine-readable output

family-hq backup create
family-hq backup create --scrub PRIVATE_WORK --to D:\for-home-pc\hq.sqlite3
family-hq config check
family-hq run
```

Dates understood by `--due`, `snooze` and filters: `today`, `tomorrow`, `fri`, `friday 5pm`, `2026-10-09`, `2026-10-09 17:30`, `+3d`, `+2w`. A bare weekday means the next one after today. Date-only deadlines are end of that day in your household time zone.

`--as NAME` (or `FAMILY_HQ_ACTOR`, or `[cli] default_actor`) picks who is acting. If you are the only admin it defaults to you.

## How it fits together

```
Discord (Phase 2)   CLI   Obsidian import (Phase 6)   scheduler
         \           |            /                       /
          +----------+-----------+-----------------------+
                              |
                    Application services      <- all mutations, all authorization, all events
                              |
                    Domain (pure Python)
                              |
              Repository protocols -> SQLAlchemy -> SQLite (Postgres later)

   Read-only projections later: reports, Obsidian, Google Sheets/Calendar, AI
```

Read these in order if you want to understand it deeply:

1. [docs/design-review.md](docs/design-review.md): the critique of the original spec, risks, and open questions
2. [docs/architecture.md](docs/architecture.md): layers, import rules, lifecycle, extension points
3. [docs/data-model.md](docs/data-model.md): tables, invariants, lifecycle
4. [docs/permissions.md](docs/permissions.md): who can see and do what, and which integrations may receive which scope
5. [docs/decisions.md](docs/decisions.md): every numbered decision with its reason
6. [docs/roadmap.md](docs/roadmap.md): phases and acceptance checks

## Privacy in one paragraph

Private tasks (`PERSONAL`, `PRIVATE_WORK`) belong to their owner. Not admins, not spouses, not anyone else can see them, find them by search, see their history, or tell they exist (a hidden task behaves exactly like a missing one). Which integrations may receive a scope is a separate, configurable policy; family-audience sinks (shared Discord channel, shared Google Sheet) can only ever carry `FAMILY`. Logs and error messages never include titles, descriptions or notes. Backups can scrub private scopes so a cloud-synced copy contains none of that text. What this does **not** protect against is someone with access to the database file or the operator CLI on the host; use disk encryption for that.

## Development

```bash
pytest                      # ~250 tests, a few seconds
ruff check src tests && ruff format src tests
mypy src                    # strict
```

Layout:

```
src/family_hq/
  domain/        pure rules: enums, Task/Person/Project, transitions, visibility, dates, workload
  application/   services (the only code that mutates), authorizer, backups
  repositories/  protocols (base.py) and the SQLAlchemy implementation
  db/            engine/pragmas, ORM models, Alembic migrations
  cli/           Click commands
  app.py         composition root and the long-running service loop
tests/
docs/
```

Changing the schema: edit `db/models.py`, then
`FAMILY_HQ_CONFIG=config.toml alembic revision --autogenerate -m "what changed"`, review the file (swap any `family_hq.db.types.UTCDateTime` for `sa.DateTime(timezone=True)`), and run the tests. `tests/test_migrations.py` fails if the models and migrations drift.

Rules worth remembering when extending:

* Mutations go through a service method. Never write through a repository from the CLI or Discord layer. `tests/test_architecture.py` enforces the import boundaries.
* Reads that a person can trigger go through viewer-scoped repository methods. There is deliberately no "get any task by id".
* Never put a title, description, note or project name in a log line or exception message.
* New integrations get their own `Sink` and are gated by `SinkPolicy`.
* Time is injected (`Clock`); datetimes are always timezone-aware.

## Security notes

* `.env`, `config.toml`, `data/`, and credential files are git-ignored. The config loader refuses secret-looking keys in `config.toml`.
* Do not keep the database inside OneDrive, Dropbox or Google Drive Desktop. `family-hq config check` warns if you do.
* If you moved from a work laptop: check your employer's policy before copying `PRIVATE_WORK` data anywhere. `backup create --scrub PRIVATE_WORK` exists for exactly that.
