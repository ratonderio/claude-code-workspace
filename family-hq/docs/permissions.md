# Permissions and Visibility

Two independent checks, both centralized, both default-deny.

1. **Authorizer** (`application/authz.py`): may *this person* see or do *this thing*?
2. **SinkPolicy** (`domain/visibility.py`): may content of *this scope* be sent to *this integration*?

Nothing else in the codebase contains permission rules. If you find an `if role == ...` anywhere else, it is a bug.

## Scopes

| Scope | Rank | Meaning |
|-------|------|---------|
| FAMILY | 0 | Shared household information |
| PERSONAL | 1 | Belongs to one person |
| PRIVATE_WORK | 2 | Belongs to one person, never leaves the machine by default |

Rank expresses restrictiveness. Additional scopes can be added later by extending the enum and the rank table.

## Who can see what

`can_view(actor, scope, owner_id)`:

* The actor must be an active person.
* FAMILY: visible to every active person.
* PERSONAL / PRIVATE_WORK: visible only if `owner_id == actor.id`. **Roles do not matter. Admins do not see other people's private tasks.**

An invisible task behaves exactly like a nonexistent one: lookups raise `NotFoundError`, list queries omit it, prefix search ignores it, and error text never contains its content.

The same rule exists in SQL as `visible_clause(scope_col, owner_col, viewer_id)` used by every list query. `tests/test_visibility.py` asserts the two implementations agree for every combination.

### Containment rule

A task's scope rank must be >= its project's rank and >= its parent task's rank. A FAMILY project may contain PERSONAL tasks (your private prep work for the family vacation); a PRIVATE_WORK project may never contain FAMILY tasks. When a private-scope project or parent is involved, the task owner must be the owner of that project or parent (this follows automatically because only the owner can see it).

### Event (history) visibility

An event is visible to a viewer only if the viewer passes the visibility check against:

* the event's recorded `(visibility_scope, scope_owner_id)` snapshot, **and**
* the current `(scope, owner)` of its task or project.

So making a family task private hides its earlier history from the family, and making a private task family-visible does not reveal its private-era history.

## Roles

| Role | Intended for |
|------|--------------|
| ADMIN | The household administrator (you). Operations: people, categories, backups, configuration. |
| ADULT | Other adults. Same task powers as admin, no administration. |
| MEMBER | Kids or occasional users. Simple participation. |

## Permissions

Defaults come from the role; `people.permissions` holds per-person overrides (`{"assign_others": true}` or `false`).

| Permission | ADMIN | ADULT | MEMBER | Controls |
|------------|:-----:|:-----:|:------:|----------|
| `edit_any_family_task` | yes | yes | no | Edit/cancel FAMILY tasks you did not create or own |
| `assign_others` | yes | yes | no | Assign a task to someone other than yourself |
| `manage_projects` | yes | yes | no | Create/edit FAMILY projects |
| `create_recurring` | yes | yes | no | Create recurring chore definitions (Phase 3) |
| `use_personal_scope` | yes | yes | yes | Create PERSONAL tasks/projects |
| `use_private_work_scope` | yes | yes | no | Create PRIVATE_WORK tasks/projects |
| `manage_people` | yes | no | no | Add/edit/deactivate people |
| `manage_categories` | yes | no | no | Add/rename/deactivate categories |
| `manage_backups` | yes | no | no | Create, prune, verify backups |

`manage_people`, `manage_categories` and `manage_backups` are administrative; per-person overrides are honored but you should rarely need them.

Losing `use_private_work_scope` does not hide private tasks you already own. It only stops creating new ones.

## Task action rules (FAMILY scope)

"Involved" = the actor is the task's owner or creator. "Can work" = actor is the owner, the task is unassigned, or the actor has `edit_any_family_task`.

| Action | Rule |
|--------|------|
| View | Any active person |
| Create | Any active person (title only is enough) |
| Edit fields | Involved, or `edit_any_family_task` |
| Claim | Task is unassigned. Always for yourself |
| Assign to someone else | `assign_others` |
| Assign to self / release your own task | Any active person |
| Start, complete, wait, block, unblock, snooze | Can work. Starting or completing an unassigned task claims it for you (D21) |
| Cancel | Involved, or `edit_any_family_task` |
| Reopen | Involved, or `edit_any_family_task` |
| Add note | Any person who can view the task |
| Change scope | See below |

## Task action rules (PERSONAL and PRIVATE_WORK)

Only the owner can do anything, including create. The owner field is the creator, cannot be changed, and cannot be unassigned. Giving a task to someone else means first changing its scope to FAMILY, which the owner may do, after which normal family rules apply.

## Changing scope

* Allowed for the owner of a private task, or (FAMILY to private) for a person who may edit the task and who is, or becomes, its owner (an unassigned task is claimed by the actor; a task owned by someone else cannot be made private by you).
* The target scope must be allowed for the actor (`use_*_scope`).
* The containment rule must still hold with its project and parent. Otherwise the change is refused with an instruction to move the task first.
* A `SCOPE_CHANGED` event is recorded with the stricter of the two scopes as its snapshot.

## Projects

* View: same visibility rule as tasks.
* Create/edit FAMILY project: `manage_projects`.
* PERSONAL / PRIVATE_WORK projects: owner only, requires the matching `use_*_scope`.
* Name uniqueness is checked only among projects the actor can see.

## Sink policy

Sinks: `DISCORD_CHANNEL` (broadcast), `DISCORD_EPHEMERAL` (reply visible only to the invoker), `GOOGLE_FAMILY` (shared sheet/calendar), `GOOGLE_PRIVATE` (your own Google account), `OBSIDIAN`, `AI`.

Defaults (`[visibility.sinks]` in config):

| Scope | DISCORD_CHANNEL | DISCORD_EPHEMERAL | GOOGLE_FAMILY | GOOGLE_PRIVATE | OBSIDIAN | AI |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|
| FAMILY | yes | yes | yes | yes | yes | yes |
| PERSONAL | **no** | yes | **no** | opt-in | yes | no |
| PRIVATE_WORK | **no** | no | **no** | no | yes | no |

Bold cells are hard invariants: `DISCORD_CHANNEL` and `GOOGLE_FAMILY` are family-audience sinks and the configuration loader refuses to enable them for any scope other than FAMILY.

Using the policy: an integration first filters by *viewer* (the Obsidian vault is the admin's, so it receives what the admin may see: FAMILY plus the admin's own private tasks) and then by *sink* (`SinkPolicy.allows(scope, sink)`). Both must pass.

Reports follow the same split: a **family report** is computed from FAMILY scope only and is the same for every viewer; a **private report** is computed from what the owner can see, optionally narrowed by the AI sink when feeding a summarizer.

## Stale actors

An `Actor` (person plus source) is never trusted for role, permissions or active state. Every service call re-reads the person inside its transaction, so deactivating someone or removing a permission applies to their very next action even if their Discord session or a long-running process still holds the old object.

## Errors, logs and notifications

* Authorization failures on invisible objects look like "not found".
* Authorization failures on visible objects say what is not allowed, never quoting content ("You can't assign tasks to other people", not "You can't assign 'Fix sink' to Wyatt").
* Logs and exceptions carry IDs, counts and event types. They never carry titles, descriptions, notes or project names.
* Discord error replies are built from exception messages with the same guarantee, and are ephemeral.

## Trust boundary

These rules protect against family members, Discord channel visibility, and external integrations. They do not protect against someone who can read the SQLite file or run `family-hq --as <person>` on the host. Disk encryption (BitLocker) and normal account hygiene cover that boundary. The CLI `--as` flag exists for support and testing and is considered inside the boundary.
