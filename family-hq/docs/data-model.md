# Data Model

Conventions

* Primary keys are UUID4 strings (36 chars with dashes), except `activity_events.seq`, an autoincrement integer used for ordering and cursors (`id` is also a UUID).
* Datetimes are timezone-aware in Python and stored as UTC.
* Enum-like columns are plain strings, validated in the domain layer (D17).
* "Scope" means `visibility_scope`: `FAMILY`, `PERSONAL`, `PRIVATE_WORK`.
* Rows are never physically deleted in normal operation. The only deletion path is the backup scrubber, which operates on a copy.

## Entity relationship overview

```
people 1---* tasks (owner, creator, completed_by)
people 1---* projects (owner)
categories 1---* tasks
projects 1---* tasks
tasks 1---* tasks (parent_task_id)
recurrence_definitions 1---* tasks (occurrences)
tasks / projects 1---* activity_events
(any entity) 1---* external_refs
```

## people

| Column | Type | Notes |
|--------|------|-------|
| id | str PK | |
| display_name | str | unique, case-insensitive (enforced in service) |
| discord_user_id | str, null, unique | Discord snowflakes exceed JavaScript safe integers; stored as text |
| active | bool | inactive people cannot act and cannot be assigned work |
| role | str | ADMIN, ADULT, MEMBER |
| google_email | str, null | reference only, no credentials |
| permissions | JSON | per-person overrides, `{"assign_others": true}`; see permissions.md |
| created_at, updated_at | datetime | |

## categories

| Column | Type | Notes |
|--------|------|-------|
| id | str PK | |
| name | str | unique case-insensitive |
| sort_order | int | |
| active | bool | deactivate instead of delete |
| created_at | datetime | |

## projects

| Column | Type | Notes |
|--------|------|-------|
| id | str PK | |
| name | str | unique only among projects visible to the actor |
| description | str, null | |
| status | str | ACTIVE, ON_HOLD, DONE, ARCHIVED |
| visibility_scope | str | immutable in Phase 1 |
| owner_id | FK people, null | required when scope is not FAMILY |
| created_at, updated_at | datetime | |
| due_at, due_all_day | datetime null, bool | optional deadline |

## tasks

| Column | Type | Notes |
|--------|------|-------|
| id | str PK | stable, immutable |
| title | str (1..200) | |
| description | str, null | |
| status | str | INBOX, OPEN, PLANNED, IN_PROGRESS, WAITING, BLOCKED, DONE, CANCELLED |
| owner_id | FK people, null | null = unassigned (claimable). Required if scope is not FAMILY |
| creator_id | FK people, null | null only for system-generated tasks |
| project_id | FK projects, null | scope containment rule applies |
| category_id | FK categories, null | |
| visibility_scope | str | |
| priority | str | LOW, NORMAL, HIGH, URGENT (default NORMAL) |
| effort | str, null | XS, S, M, L, XL; null = unestimated |
| created_at, updated_at | datetime | |
| due_at | datetime, null | UTC instant |
| due_all_day | bool | true: due_at is 23:59:59 local on the due date |
| completed_at | datetime, null | set on DONE |
| completed_by_id | FK people, null | who finished it |
| cancelled_at | datetime, null | set on CANCELLED |
| snoozed_until | datetime, null | hides from actionable views until then |
| postpone_count | int | snoozes plus later-moved deadlines |
| blocked_reason | str, null | the "status reason" for BLOCKED and WAITING |
| source | str | CLI, DISCORD, OBSIDIAN, RECURRENCE, AI, SYSTEM |
| parent_task_id | FK tasks, null | set at creation only (so cycles are impossible) |
| recurrence_definition_id | FK recurrence_definitions, null | |
| occurrence_key | str, null | e.g. local date of the occurrence |
| version | int | optimistic concurrency |

Constraints and indexes

* `UNIQUE (recurrence_definition_id, occurrence_key)`: the database-level guarantee behind idempotent recurrence generation. SQLite and Postgres both treat NULLs as distinct, so ordinary tasks are unaffected.
* Indexes on `status`, `(owner_id, status)`, `due_at`, `visibility_scope`, `project_id`, `completed_at`.
* Invariants enforced in the service layer (not CHECK constraints, D17): non-FAMILY tasks have an owner; containment rule (D5); BLOCKED has a reason; DONE has `completed_at`; CANCELLED has `cancelled_at`.

Workload points are *not* stored. They are computed from `effort` through the configurable mapping, so changing the mapping retroactively changes reports consistently.

## recurrence_definitions (schema reserved, service arrives in Phase 3)

Core columns: `id, title, description, owner_id, creator_id, project_id, category_id, visibility_scope, priority, effort, rrule, dtstart, timezone, active, generated_through, created_at, updated_at`. Phase 3 may add columns by migration.

Design intent: the definition is a template plus an RFC 5545 RRULE evaluated in the definition's local time zone. Each occurrence is a normal row in `tasks` carrying `recurrence_definition_id` and `occurrence_key`. Statistics such as late, skipped, reassigned come for free from ordinary task fields and events.

## activity_events (append-oriented ledger)

| Column | Type | Notes |
|--------|------|-------|
| seq | int PK autoincrement | ordering and integration cursors |
| id | str unique | UUID |
| occurred_at | datetime | |
| event_type | str | see below |
| actor_id | FK people, null | null for system actions |
| source | str | CLI, DISCORD, ... |
| task_id | FK tasks, null | |
| project_id | FK projects, null | |
| visibility_scope | str | **snapshot** at the time of the event (stricter of old/new for scope changes) |
| scope_owner_id | str, null | snapshot of the task owner for private scopes |
| data | JSON | structured metadata |

Event types: `TASK_CREATED, TASK_UPDATED, TASK_ASSIGNED, TASK_UNASSIGNED, TASK_CLAIMED, TASK_STARTED, TASK_WAITING, TASK_BLOCKED, TASK_UNBLOCKED, TASK_SNOOZED, TASK_COMPLETED, TASK_CANCELLED, TASK_REOPENED, TASK_STATUS_CHANGED, TASK_NOTE_ADDED, DEADLINE_CHANGED, SCOPE_CHANGED, RECURRENCE_GENERATED (reserved), PROJECT_CREATED, PROJECT_UPDATED`.

`data` conventions

* Field changes: `{"changes": {"priority": ["NORMAL", "HIGH"]}}`. Title changes include both values; description changes record `"description_changed": true` only.
* Status moves: `{"from": "OPEN", "to": "BLOCKED", "reason": "..."}`.
* Assignments: `{"from": <person_id|null>, "to": <person_id|null>}`.
* Deadlines: `{"from": <iso|null>, "to": <iso|null>, "all_day": bool}`.
* Notes: `{"text": "..."}`.

Visibility of an event: the viewer must be allowed by the snapshot (`visibility_scope`, `scope_owner_id`) **and** by the subject's current scope and owner. See permissions.md.

Not full event sourcing: current state lives in `tasks`; events are the history. Rebuilding state from events is not a goal; answering "what happened and when" is.

## external_refs

| Column | Type | Notes |
|--------|------|-------|
| id | str PK | |
| entity_type | str | `task`, `project`, `person` |
| entity_id | str | |
| system | str | `discord`, `google_calendar`, `google_sheets`, `obsidian` |
| ref_key | str | distinguishes multiple refs per system, e.g. `card`, `deadline`, `row` |
| external_id | str | message ID, event ID, row key |
| content_hash | str, null | hash of what was last pushed; unchanged hash means skip the API call |
| payload | JSON | channel ID, etag, anything adapter-specific |
| synced_at | datetime | |

`UNIQUE (entity_type, entity_id, system, ref_key)`. This is what makes sync idempotent: look up the ref, update if present, create and record if absent.

## Domain objects

Frozen dataclasses mirror these tables (`Task`, `Person`, `Project`, `ActivityEvent`). Derived properties live on the dataclasses: `Task.is_active`, `Task.is_overdue(now)`, `Task.due_date(tz)`. Workload points come from `domain.workload`.

## Task lifecycle

```
INBOX --+                                   +--> DONE ----(reopen)----+
OPEN  --+--> any other active status  ------+                         |
PLANNED-+     (BLOCKED needs a reason)      +--> CANCELLED --(reopen)-+--> OPEN
IN_PROGRESS                                                           
WAITING
BLOCKED
```

* Active to active: always allowed (except to itself).
* Active to DONE or CANCELLED: allowed.
* DONE/CANCELLED to OPEN: only via `reopen`. Nothing else leaves a terminal state.

## Categories and projects in use

Initial categories (seeded once from config): Chore, Cleaning, Errand, Parenting, School, Appointment, Finance, Administrative, Repair, Vehicle, Shopping, Home, Project, Personal, Work. Add, rename or deactivate through the CLI.
