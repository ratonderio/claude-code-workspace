# Phase 0: Specification Review

This is the critical read of the original specification: what to cut, what contradicts itself, what is risky, and the smallest architecture that still satisfies the goals. Decisions that came out of it are numbered in [decisions.md](decisions.md).

## 1. Verdict in one paragraph

The spec is coherent and unusually well scoped for a personal project. The core idea (SQLite as the truth, everything else a projection of it, one service layer, visibility as a first-class domain concept) is the right shape. The risks are not in the architecture; they are in (a) a handful of places where "private" is under-specified, (b) the host being a work laptop, and (c) the sheer number of integrations that each add an ongoing maintenance cost. The plan below keeps the shape and trims the surface area.

## 2. Contradictions and under-specified points

| # | Issue | Resolution |
|---|-------|------------|
| C1 | "PERSONAL: visible only to me" but other family members also have Discord accounts and may want personal tasks. "Me" cannot be hard-coded. | Private scopes are visible to the **owner** of the task, never to a role. See D3. |
| C2 | ADMIN role vs "PRIVATE_WORK excluded from family Discord views". Does an admin see other people's private tasks? | No. Admin is an operations role (manage people, categories, backups). Role never overrides ownership of private data. D3. |
| C3 | "Family reports must exclude private scopes" and "PERSONAL can optionally sync to private Google surfaces". Both are true, for different sinks. | Visibility is two separate questions: *who may view* (person-based) and *which integrations may receive it* (sink-based). D4. |
| C4 | Tasks have a single `visibility_scope` but also belong to projects and have parents. A FAMILY task inside a PRIVATE_WORK project leaks the project name; a PRIVATE_WORK child under a FAMILY parent leaks structure. | Containment rule: a task's scope must be at least as restrictive as its project's and its parent's. D5. |
| C5 | Append-only activity log vs privacy. A task that later becomes private still has old history rows that contain its title. | Events carry a scope snapshot. An event is visible only if **both** its snapshot and the task's current scope allow the viewer. History never becomes more public than it was. D6. |
| C6 | `blocked_reason` is listed as a field but WAITING is also a status, and the spec wants "waiting on" tracking. | One field, used for both BLOCKED and WAITING. The name is kept as specified; docs call it the "status reason". |
| C7 | The spec lists no field for snooze, but `/task snooze` and "repeatedly postponing" statistics are required. | Added `snoozed_until` and `postpone_count`. D8. |
| C8 | "Calendar event ID", "Discord message/channel references" and "external sync metadata" are all listed as task fields. Three integrations would add three column groups to the hottest table. | One `external_refs` table keyed by (entity, system, key). Tasks stay clean and new integrations need no schema change on `tasks`. D9. |
| C9 | "Due: Tuesday" is a date, but `due_at` is a timestamp. Storing midnight UTC makes a Tuesday deadline overdue on Monday evening in US time zones. | `due_at` is a UTC instant plus `due_all_day`. All-day deadlines are stored as 23:59:59 local on that date, so the local date is always recoverable and DST cannot shift it. D10. |
| C10 | "Repository interfaces so SQLite can be replaced by PostgreSQL", with the suggested folder `repositories/sqlite/`. A SQLAlchemy repository is not SQLite specific. | One SQLAlchemy implementation (`repositories/sqlalchemy/`). Only engine setup (pragmas, WAL) is SQLite specific and lives in `db/engine.py`. D11. |
| C11 | "Avoid gamifying" vs "family workload" reports. Per-person completion leaderboards are the default gamification. | Family reports show household-level totals and category/project breakdowns. Per-person numbers appear only in the owner's own private report. D12. |

## 2a. Things the spec did not say that matter

* **A gap in sequential numbers is a leak.** Friendly `#42` task numbers would let a family member infer "there are two tasks I cannot see". Tasks use UUIDs with short-prefix lookup in the CLI instead. D13.
* **Name uniqueness is a leak.** "A project named X already exists" confirms a private project exists. Uniqueness for projects is checked only among projects the actor can see.
* **Error messages are an exfiltration path.** Not-found and not-allowed are the same error for invisible tasks, and no error or log line contains a task title or description. D14.
* **Backups are an exfiltration path.** A backup copied to a cloud-synced folder carries every PRIVATE_WORK row. Backup destinations can declare scopes to scrub, and scrubbed copies are `VACUUM`ed so deleted rows do not linger in free pages. D15.

## 3. Unnecessary complexity (cut or deferred)

* **Google Drive adapter.** Nothing in the spec needs it except possibly off-site backups. Dropped from the plan; backup destinations are plain folders (which can be a Drive-synced folder, with the scrub option above).
* **Many Discord channels.** One required channel (`#family-hq`) and one optional log/digest channel. `#chores` and `#family-calendar` can be added by config later without code changes.
* **A separate `Obsidian` bidirectional sync.** Already scoped as generate-only plus explicit import. Agreed; do not drift from this.
* **PostgreSQL, Docker, a web UI.** Not introduced. The repository and UnitOfWork seams are the only concessions.
* **Full event sourcing.** Not needed. Rows hold current state; events are an append-only ledger beside them.
* **Auto-created Discord users, child accounts, per-field ACLs.** None. A person must be added by an admin and mapped to a Discord ID.
* **Per-task time estimates in minutes.** Effort buckets stay buckets. Points are configurable and explicitly relative.
* **`PLANNED` status.** It has no behavior until a scheduling engine exists. It stays in the enum (cheap, specified) but nothing in the family UI shows it as distinct from OPEN.

## 4. Security and privacy concerns

Ranked by how likely they are to actually bite.

1. **Hosting PRIVATE_WORK data on, and moving it off, an employer laptop.** The first host is a work laptop. Two sub-risks: your employer may have policy about family data and a Discord bot on their device, and, more importantly, the "migrate to the home PC" step moves work-derived task text onto a personal machine. The system supports excluding PRIVATE_WORK from exports and migration bundles (scrubbed backup), and the migration doc says to use that unless you have confirmed otherwise. **Please confirm your employer's policy; I cannot judge it.** (Open question Q1.)
2. **Centralized authorization has two implementations.** A visibility rule exists once in Python (single-object checks) and once as a SQL filter (list queries). They can drift. Mitigation: both live in one module, and a parametrized test asserts they agree for every (scope, owner, viewer) combination.
3. **Discord is not a private channel.** Slash command replies can be ephemeral (visible only to the invoker), but the content still transits Discord. Defaults: FAMILY tasks may appear anywhere; PERSONAL tasks only in ephemeral replies to their owner; PRIVATE_WORK never appears in Discord at all. All configurable per sink, with an enforced invariant that broadcast sinks (family channel, family Google Sheet) accept FAMILY only.
4. **SQLite is not encrypted.** Anyone with file access reads everything. The app-level privacy protects against family members, Discord, and exports; it does not protect against someone logged into the laptop. Use BitLocker/disk encryption; SQLCipher is a possible later upgrade but is deliberately not introduced.
5. **The CLI is a trusted operator console.** `--as <person>` lets the person at the keyboard act as anyone, including seeing that person's private tasks. This is necessary for testing and support. It is documented as inside the trust boundary.
6. **Do not put the database inside OneDrive/Dropbox/Google Drive Desktop folders.** Sync clients and SQLite WAL files corrupt each other, and it would also upload PRIVATE_WORK data. Backups are the only thing that should go near a synced folder, and only scrubbed.
7. **Secrets.** Discord token and Google credentials only in `.env` / credential files, both ignored by git. The config loader refuses to read secrets from the TOML file.
8. **AI exfiltration.** One eligibility function (`SinkPolicy.allows(scope, Sink.AI)`) is the only gate. PERSONAL and PRIVATE_WORK are off by default. Prompts are built from the same visibility-filtered, sink-filtered objects, never from raw tables.
9. **Logging.** Log lines carry IDs, counts, and event types, never titles or descriptions. A test asserts this by creating a private task and scanning captured logs.
10. **Stale Discord buttons.** A card posted last week is still clickable. Every action re-checks visibility, permission, and state transition rules server side; the card is never trusted. Tasks carry a `version` for optimistic concurrency, so two people tapping Claim at once yields one winner and one polite "already claimed".

## 5. Technical and product risks

* **The family experience depends on uptime.** A laptop that sleeps makes the bot offline, and Discord shows "application did not respond" to the person who tried. This is the biggest product risk for adoption. Mitigations: migrate to the always-on home PC early; make startup catch-up (recurrence, overdue digests) idempotent so downtime heals itself; consider cheap always-on hosting later if privacy allows. The Windows laptop is fine for development and your own use.
* **Windows specifics.** Windows has no system IANA time zone database, so `tzdata` is a hard dependency. asyncio signal handling differs on Windows, so shutdown uses `KeyboardInterrupt` rather than `loop.add_signal_handler`. Paths are always resolved relative to the config file, not the working directory, because Task Scheduler launches processes from `System32`.
* **Two bot instances at once.** During migration, if the old and new machines both run the bot with the same token, every command is answered twice. The migration checklist says to stop the old host first.
* **Time zones and DST.** Everything is stored as UTC, converted at the edges, and tested across both DST transitions. Recurrence (Phase 3) is where this really bites: a 7:00 local chore must stay at 7:00 local across DST, which means expanding RRULEs in local time, not UTC.
* **Schema drift.** Hand-written migrations and ORM models can disagree. A test runs migrations on an empty database and diffs the result against the ORM metadata.
* **Scope creep through "just one more integration".** Every adapter is a maintenance subscription (API changes, token expiry). The roadmap orders integrations by value and keeps each one removable without touching the core.
* **LLM natural language capture** needs Discord's privileged *Message Content* intent. Slash commands do not. This is why capture-by-message is a Phase 7 decision rather than a Phase 2 convenience.
* **Over-abstraction.** Domain dataclasses plus ORM models plus repository protocols is three representations of a task. It is worth it here because the Discord, reporting, Obsidian and Sheets layers must never see ORM objects (lazy loading, detached sessions, accidental writes). It would not be worth it for a one-screen script. The mapping code is kept in one place per entity.

## 6. Smallest architecture that satisfies the goals

```
Interfaces (CLI now; Discord, scheduler, Obsidian import later)
        |
Application services (TaskService, ProjectService, PeopleService, BackupService)
        |  all mutations, all authorization, all events
Domain (pure Python: enums, dataclasses, transitions, visibility policy)
        |
Repository protocols  --->  SQLAlchemy implementation  --->  SQLite (Postgres later)

Projections (read-only, Phase 4+): reports, Obsidian, Sheets, Calendar, AI
```

Rules that keep it small:

1. Interfaces call services. Services own transactions. Nothing else writes.
2. Domain code has no I/O and no SQLAlchemy imports.
3. Projections consume visibility- and sink-filtered domain objects, never the database directly.
4. One Python process, synchronous domain logic, async only at the Discord/network edges.
5. Every integration is optional and can be deleted without a schema change.

## 7. What changed versus the suggested layout

* `repositories/sqlite/` becomes `repositories/sqlalchemy/` (C10).
* Alembic migrations live inside the package (`src/family_hq/db/migrations/`) so `family-hq db upgrade` works from an installed package and from any working directory.
* `integrations/google/drive.py` is dropped (section 3).
* `docker-compose.yml` is deferred to Phase 2, when there is a long-running service worth containerizing and I can test it.
* The generated project lives in `family-hq/` inside this repository because the repository already contains unrelated material at its root.

## 8. Open questions (everything else was decided and documented)

* **Q1. Employer policy** on running this on the work laptop and on moving PRIVATE_WORK data later. Default taken: single database, scrub-on-export, nothing PRIVATE_WORK leaves the machine unless you configure otherwise.
* **Q2. Separate physical database for PRIVATE_WORK?** It would make leaks structurally impossible (a filter bug cannot expose rows that are in another file) and make migration trivial, at the cost of cross-database aggregation in your private reports and no foreign keys across the boundary. I chose a single database with defense in depth (D2) because the reporting you want is mostly cross-scope. The repository seam means this can be revisited without touching Discord or reports. Tell me if you would rather pay that cost now.
* **Q3. Your household time zone.** `config.example.toml` uses `America/New_York`; set yours.
