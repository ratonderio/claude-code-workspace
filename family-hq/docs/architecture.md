# Architecture

Family HQ is one long-running Python process around one SQLite file. Everything else is an adapter that either asks the service layer to do something (Discord, CLI, Obsidian import) or reads from it (reports, Sheets, Calendar, Obsidian generation, AI).

```
        Discord          CLI        Obsidian import     Scheduler
           \              |              /                  /
            +-------------+-------------+------------------+
                                |
                     Application services
        TaskService  ProjectService  PeopleService  BackupService
        (authorize -> validate -> mutate -> record event, one transaction)
                                |
                   Domain (pure Python, no I/O)
        enums, Task/Person/Project/ActivityEvent, transitions,
        visibility + sink policy, effort points, due-date helpers
                                |
                       Repository protocols
                                |
              SQLAlchemy repositories + UnitOfWork
                                |
                       SQLite (Postgres later)

   Read-only projections (later phases), fed by visibility- and sink-filtered domain objects:
   Reports -> Markdown / JSON      Obsidian generator      Sheets sync
   Calendar sync                   AI summarizer/parser/planner (null by default)
```

## Layers and import rules

| Layer | Package | May import | Must not import |
|-------|---------|-----------|-----------------|
| Domain | `family_hq.domain` | stdlib | everything else |
| Application | `family_hq.application` | domain, repository protocols | SQLAlchemy, Discord, Google |
| Repositories | `family_hq.repositories` | domain, db | application, interfaces |
| DB | `family_hq.db` | SQLAlchemy, Alembic | domain (except type names via repositories) |
| Interfaces | `family_hq.cli`, later `integrations.*` | application, domain | repositories, db models |
| Composition | `family_hq.app` | everything | n/a (the only place wiring happens) |

This is enforced by convention plus a test (`tests/test_architecture.py`) that scans imports.

## The one rule that matters

**All mutations go through a service method.** A service method does, in this order:

1. Resolve the object **through a viewer-scoped lookup**, so an invisible task is indistinguishable from a missing one.
2. Ask the `Authorizer` whether this actor may perform this action on this object.
3. Validate and apply the change (pure domain functions, producing a new frozen dataclass).
4. Write the row (optimistic concurrency via `version`).
5. Append one or more `ActivityEvent`s.
6. Commit once.

Discord handlers, the CLI and any future importer never touch repositories.

## Package layout

```
family-hq/
  pyproject.toml  README.md  .env.example  config.example.toml  alembic.ini
  src/family_hq/
    __main__.py            python -m family_hq  ->  CLI
    app.py                 composition root: Container, build_container(), startup()
    config.py              pydantic Settings (TOML) + Secrets (.env)
    clock.py               Clock protocol, SystemClock, FixedClock
    errors.py              FamilyHQError hierarchy (messages are privacy-safe)
    logging_setup.py
    domain/
      enums.py             Role, Scope, Sink, TaskStatus, Priority, Effort, EventType, Source...
      visibility.py        scope rank, can_view(), SinkPolicy
      people.py            Person, Permission, ROLE_DEFAULTS
      tasks.py             Task, transitions, TaskQuery
      projects.py          Project
      events.py            ActivityEvent
      dates.py             due-date helpers, parse_when()
      workload.py          effort -> points
    application/
      authz.py             Authorizer (the only place permission rules live)
      actor.py             Actor
      task_service.py  project_service.py  people_service.py  category_service.py
      backup_service.py    sqlite online backup, scrub, retention
      uow.py               UnitOfWork protocol
    repositories/
      base.py              Protocols
      sqlalchemy/          models-to-domain mapping, queries, UnitOfWork
    db/
      engine.py            engine factory, SQLite pragmas
      models.py            SQLAlchemy declarative models
      types.py             UTCDateTime
      migrations/          Alembic env + versions
    cli/
      main.py  render.py   and one module per command group
    integrations/          (later) discord/ google/ obsidian/ ai/
    reports/               (later)
  tests/
  docs/
```

## Process model and lifecycle

`family-hq run` (Phase 1: backups only; Phase 2 adds Discord; Phase 3 adds recurrence):

1. Load and validate configuration; fail with a readable message listing every problem.
2. Create data directories; open the engine; apply Alembic migrations.
3. Seed categories if the table is empty.
4. Run catch-up jobs (idempotent): backup-if-due now, recurrence generation later.
5. Start the integrations that are configured (Discord with automatic reconnect).
6. Run a tiny asyncio scheduler for periodic jobs. Every job is safe to run twice and safe to have missed.

There is no dependency on Windows Task Scheduler, services or Docker. The same command runs under any of them (see deployment.md).

Domain logic is synchronous. The Discord layer calls services with `asyncio.to_thread`, so a slow SQLite write never blocks the gateway heartbeat.

## Extension points

* **SchedulingService** (`application/scheduling_service.py`, Phase 8): pure function from (tasks, effort points, deadlines, calendar free/busy) to *suggested* blocks. It returns suggestions; applying one is an explicit, separate service call.
* **AI** (`integrations/ai/`, Phase 7): `ReportSummarizer`, `TaskParser`, `PlanningAssistant` protocols with null implementations. Inputs are built only from objects that passed `SinkPolicy.allows(scope, Sink.AI)`.
* **Integrations** subscribe to the activity ledger by cursor (`seq`) rather than being called from services. A Sheets sync or Discord digest asks "what changed since seq N", which makes them restartable and keeps services ignorant of integrations.
* **PostgreSQL**: change `database.url`, install the driver, run migrations. Dialect-specific code is limited to `db/engine.py` and `BackupService` (SQLite online backup API).

## Time

* Every datetime in the domain is timezone-aware. Naive datetimes are rejected at the repository boundary (`UTCDateTime` type).
* Storage is UTC. The household zone (`app.timezone`) is applied when parsing user input and rendering output.
* Date-only deadlines are stored as 23:59:59 local time on the due date (D10).
* Services receive a `Clock`; tests use `FixedClock` and DST-transition dates.

## Logging

Standard-library `logging`. Console text by default; JSON lines optional (`logging.json = true`). Log calls pass IDs and counts as `extra` fields. Titles and descriptions are never logged; see D14 and `tests/test_privacy.py`.

## Testing strategy

* Services are tested through their public API on a real temporary SQLite file with migrations applied (no mocks of the database).
* A visibility matrix test runs every service method as an unrelated family member against FAMILY, PERSONAL and PRIVATE_WORK tasks and asserts nothing leaks, including through errors, lists, history and logs.
* A SQL-versus-Python visibility parity test guards the two implementations of the same rule.
* Migrations are applied to an empty database and diffed against the ORM metadata.
* Backups: integrity check, retention selection (pure function), and a byte-level check that scrubbed copies do not contain private text.
