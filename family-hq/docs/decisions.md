# Decision Log

Short, numbered, each with the reason. When a decision changes, edit the entry and add a dated note rather than deleting history.

## Storage and architecture

**D1. SQLite is canonical.** Sheets, Calendar, Obsidian, Discord feeds and AI inputs are projections that can be rebuilt from the database. Losing any of them loses nothing.

**D2. One database, scope column, defense in depth.** Not one file per scope. Reason: the private reports you want combine scopes. Defense in depth instead: viewer-scoped repository queries, a central authorizer, sink policy, scrub-on-export backups, and leak tests. Revisit if the PRIVATE_WORK volume or sensitivity grows (see design-review Q2).

**D7. Domain dataclasses are separate from ORM models.** Services, reports and Discord only ever see frozen dataclasses. The ORM lives behind `repositories/sqlalchemy/`. Each service call runs in one `UnitOfWork` (one transaction): state change plus event, atomically.

**D11. Repository protocols with one SQLAlchemy implementation.** Postgres should work by changing the URL and running migrations. Only `db/engine.py` knows about SQLite pragmas.

**D16. Optimistic concurrency.** `tasks.version` increments on every update; a stale write raises `ConflictError`. This is what makes Discord buttons safe against double clicks and week-old cards.

**D17. Enums are stored as plain strings with no database CHECK constraints.** Domain code converts to `StrEnum` and rejects unknown values. This keeps adding a status or scope a code change rather than a table-rebuild migration (painful on SQLite).

**D23. Alembic migrations live in the package** (`family_hq/db/migrations`) and are applied programmatically on startup and by `family-hq db upgrade`. Models and migrations are checked for drift by a test.

**D24. Time is injected.** Services take a `Clock`. All datetimes are timezone-aware, stored as UTC, converted to the household zone only at the edges (rendering, parsing).

## Privacy and security

**D3. Private scopes belong to the owner.** A PERSONAL or PRIVATE_WORK task is visible to its owner and nobody else, including admins. Such a task must have an owner, and its owner cannot be changed (to give it away, make it FAMILY first).

**D4. Two separate questions.** `Authorizer` answers "may this person see/do this?". `SinkPolicy` answers "may content of this scope go to this integration?". Both must say yes. Broadcast sinks (family Discord channel, family Google Sheet) are hard-wired to FAMILY and a config that tries otherwise is rejected at load time.

**D5. Containment rule.** Scope rank is FAMILY < PERSONAL < PRIVATE_WORK (more restrictive is higher). A task's rank must be >= its project's and its parent's. Project visibility is immutable in Phase 1.

**D6. Event scope snapshot.** Events record the scope and owner at the time. Viewing an event requires that both the snapshot and the task's current scope allow the viewer, so history can never become more public than it was. Events about a scope change use the stricter of old and new scope.

**D13. UUIDs, no sequence numbers.** Gaps in `#42` style numbers reveal hidden tasks. The CLI resolves unique UUID prefixes among visible tasks only.

**D14. Safe errors and logs.** Exceptions raised by services never contain task titles or descriptions. Invisible tasks produce the same `NotFoundError` as nonexistent ones. Logs carry IDs and counts only.

**D15. Backups can scrub scopes.** A destination may declare `scrub_scopes`; the copy has those rows deleted and is `VACUUM`ed. `backup create --scrub PRIVATE_WORK --to PATH` doubles as the migration bundle that leaves work data behind.

## Domain modeling

**D8. Snooze is a field, not a status.** `snoozed_until` hides a task from "actionable" views until then; `postpone_count` increments on snooze and when a due date moves later.

**D9. External references live in `external_refs`.** Discord message IDs, Calendar event IDs, Sheet row keys and content hashes, keyed by (entity_type, entity_id, system, ref_key).

**D10. Deadlines are UTC instants plus `due_all_day`.** An all-day deadline is stored as 23:59:59 in the household zone on that date. Overdue means `now > due_at`. The "due date" is always `due_at` converted to the household zone.

**D12. No per-person leaderboards in family-facing output.**

**D18. Task lifecycle.** Active statuses: INBOX, OPEN, PLANNED, IN_PROGRESS, WAITING, BLOCKED. Terminal: DONE, CANCELLED. Any active status may move to any other (BLOCKED requires a reason). Terminal statuses only move back via an explicit `reopen` to OPEN. `completed_at` is set on DONE; `cancelled_at` on CANCELLED; both are cleared on reopen (the events keep the history).

**D19. Categories are rows, seeded once.** Initial names come from config and are inserted only when the table is empty, so renaming "Chore" to "Chores" is not undone on the next start.

**D20. Notes are events.** `TASK_NOTE_ADDED` with the text in event data. No separate notes table, so notes inherit the same visibility filtering and scrubbing. History records old and new values for short fields, and only a `description_changed` flag for descriptions.

**D21. Completing or starting an unassigned family task claims it for the actor.** The person who did the garage is the person who owns the garage. `completed_by_id` records who finished a task even if the owner differs (an adult finishing a child's chore).

**D22. Unestimated tasks count as zero workload points** and are reported separately as "unestimated", rather than inventing a default.

## Permissions defaults (see permissions.md)

**D26.** ADMIN and ADULT can edit any FAMILY task, assign to anyone, manage family projects, create recurring chores, and use all three scopes. MEMBER can create tasks, claim, work on tasks they own or that are unassigned, edit tasks they created or own, add notes, and use FAMILY and PERSONAL scopes. Individual overrides live in `people.permissions`.

**D31. Actors are re-read inside every transaction.** An `Actor` may be minutes or days old (a Discord session). Role, permissions and `active` are loaded from the database at the moment of each action, so deactivating or demoting a person takes effect immediately. Found by a test, not by foresight.

**D32. SQLite takes the write lock at transaction start (`BEGIN IMMEDIATE`).** Combined with the `version` check this makes "claim if still unassigned" race-free. Cost: reads also serialize briefly, which is irrelevant at household scale.

**D33. Service listing methods have explicit names** (`list_tasks`, `list_projects`, ...) because a method called `list` shadows the builtin inside its own class and breaks strict typing.

## Tooling

**D25. Every call carries an `Actor` = (person, source).** Source is CLI, DISCORD, OBSIDIAN, RECURRENCE, AI or SYSTEM, and ends up on events and on tasks created through that path.

**D27. Click for the CLI, pydantic for configuration, stdlib logging with an optional JSON formatter.** Fewer dependencies than Typer/Rich/structlog and easy to debug. `--json` on read commands gives automation a stable surface.

**D28. Config paths resolve relative to the config file**, never the working directory (Windows Task Scheduler and services start in odd directories). Secrets come only from environment / `.env`.

**D29. Python 3.12+, `tzdata` required** (Windows has no IANA database).

**D30. Docker deferred until there is a service to run (Phase 2).** Development never requires it.
