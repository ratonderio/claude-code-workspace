# Implementation Roadmap

Each phase ends with a demonstrable acceptance check and leaves the system usable. Later phases never require rewrites of earlier ones; they add adapters and read-side code.

| Phase | Theme | Status |
|-------|-------|--------|
| 0 | Design review, architecture, data model, permissions | done |
| 1 | Local core: DB, services, events, CLI, backups, tests | **built** |
| 2 | Discord family MVP | next |
| 3 | Recurrence | |
| 4 | Reports | |
| 5 | Google Sheets and Calendar | |
| 6 | Obsidian | |
| 7 | AI interfaces | |
| 8 | Scheduling suggestions | |

## Phase 1: local core (built)

Delivered: project skeleton, config (TOML plus `.env`), SQLite with Alembic migrations, People/Projects/Categories/Tasks, repository protocols with a SQLAlchemy implementation, UnitOfWork, `TaskService` with the full lifecycle, activity ledger, central `Authorizer` and `SinkPolicy`, due-date parsing, CLI, backups with retention and scrubbing, `family-hq run` lifecycle skeleton, tests.

Acceptance: using only the CLI, create, assign, modify, complete, block, list, filter and inspect tasks, with history retained. The test `tests/test_cli_acceptance.py` runs exactly that story.

Known limits to keep in mind: project visibility is immutable; subtask parent is set only at creation; no restore command (restore is "stop the service and copy the file back", documented).

## Phase 2: Discord family MVP

* `integrations/discord/` using discord.py 2.x; slash command group `/task`, buttons, modals, select menus, embeds, ephemeral replies for anything non-FAMILY.
* Person mapping by `discord_user_id`; unknown users get a polite refusal.
* Commands: add (modal), mine, today, week, list, claim, assign, start, done, blocked, details, snooze, cancel, inbox, edit.
* Task card view with buttons; every button re-validates through the services.
* Family feed: a cursor over `activity_events` (`seq`), grouped into a digest on a timer rather than one message per event; FAMILY scope only; one required channel plus an optional log channel.
* Dockerfile and `docker-compose.yml`.
* Stretch: message context menu "Create task from message".

Acceptance: the family can run their week from Discord without CLI or database access.

## Phase 3: recurrence

* `domain/recurrence.py`, `RecurrenceService`, definitions table service.
* RFC 5545 RRULE via `python-dateutil`, expanded in the definition's local zone so a 7:00 chore stays 7:00 across DST.
* Planning horizon (default 30 days). Generation inserts occurrences guarded by `UNIQUE(recurrence_definition_id, occurrence_key)`; running it twice creates nothing new.
* Catch-up on startup plus a daily scheduler job.
* Occurrence statistics: completed, late, skipped, reassigned (derived from fields and events).
* Tests: date boundaries, month ends, DST in both directions, duplicate prevention, horizon changes.

Acceptance: a weekly chore creates individually trackable weekly occurrences with no duplicates.

## Phase 4: reports

* Pure functions: tasks and events in, report objects out; renderers to JSON and Markdown.
* Daily and weekly reports, workload points, backlog growth, age of oldest tasks, repeated postponement, category/project breakdowns.
* Family report from FAMILY scope only; private report from owner-visible scope.
* `family-hq report daily|weekly [--family|--private] [--json|--markdown]`.

Acceptance: a weekly report shows accomplishments and remaining workload, and the family variant provably contains no private data.

## Phase 5: Google

* OAuth installed-app flow for your own account; service account optional for a family-shared sheet.
* Sheets: sync keyed by UUID using `external_refs`, rebuild-from-scratch command, generated-data banner, sink-filtered rows.
* Calendar: only appointments, explicit-time tasks, configured categories, and tasks you flag; all-day deadline markers optional; event IDs stored; updates modify in place.
* Docs: `docs/google-setup.md`.

Acceptance: a readable Sheet and Calendar deadlines, re-sync creates no duplicates, deleting the Sheet loses nothing.

## Phase 6: Obsidian

* `family-hq obsidian generate`: Dashboard, Inbox, My Tasks, Waiting and Blocked, Projects/, Daily/, Weekly Reviews/, each stamped as generated.
* `family-hq obsidian import`: only explicitly marked lines (`FAMILYHQ:` prefix, with `@person #category !priority` tokens) or YAML task blocks; imports are idempotent via a marker written back or a hash.
* Private scopes included, since the vault is yours.

Acceptance: one command refreshes the vault without manual edits.

## Phase 7: AI

* `ReportSummarizer`, `TaskParser`, `PlanningAssistant` protocols with null implementations; one provider implementation.
* Every AI input passes through `SinkPolicy.allows(scope, Sink.AI)`; PRIVATE_WORK excluded unless configured.
* Natural-language capture (needs Discord Message Content intent); deterministic `/task add` remains primary.

## Phase 8: scheduling

* `SchedulingService` returning suggested blocks from effort points, deadlines, working hours and Calendar free/busy.
* Suggestions only; applying them is an explicit approval step.

## Cross-cutting backlog (do when it hurts)

* Restore command with pre-restore safety copy.
* Project visibility change with containment re-check.
* Optional SQLCipher.
* Postgres migration rehearsal (CI job running the same tests against Postgres).
* A tiny read-only status page (health, last backup, last sync).
