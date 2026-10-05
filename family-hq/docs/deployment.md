# Deployment and Migration

## First setup on Windows (PowerShell)

Requirements: Python 3.12 or newer, Git.

```powershell
git clone <your repo url>
cd claude-code-workspace\family-hq
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

copy config.example.toml config.toml
copy .env.example .env
notepad config.toml        # set timezone, backup directory, ...
family-hq init --admin "Your Name"
family-hq task add "My first task"
family-hq task list
```

`family-hq init` creates the data directory, applies migrations, seeds categories, and creates the first ADMIN person. It refuses to create a second "first admin".

## Where things live

| Item | Default | Notes |
|------|---------|-------|
| Config | `config.toml` next to the repo root | `--config` or `FAMILY_HQ_CONFIG` overrides |
| Secrets | `.env` next to the config file | never committed |
| Database | `data/family_hq.sqlite3` | relative to the config file |
| Backups | `data/backups/` | change in `[backup]`; see the OneDrive warning below |
| Logs | stderr, optionally a file | |

All relative paths resolve against the **config file's directory**, so it does not matter where the process is launched from.

**Do not put the database in OneDrive, Dropbox or Google Drive Desktop.** Sync clients lock and rewrite files that SQLite expects to control (especially the `-wal` file) and can corrupt the database, and they would upload private tasks. Backups may go to a synced folder only if that destination scrubs private scopes (see Backups).

## Running

```powershell
family-hq run
# or
python -m family_hq run
```

Startup order: validate config, apply migrations, seed categories, run catch-up jobs, start integrations, run the scheduler. Stop with Ctrl+C.

### Keeping it running on Windows

Any of these work; the app does not care which:

* **Task Scheduler**: trigger "At log on" (or "At startup" for a service-like setup), action: `C:\path\to\family-hq\.venv\Scripts\family-hq.exe`, arguments `--config C:\path\to\family-hq\config.toml run`, start in the repo directory, and untick "Stop the task if it runs longer than". Enable "Run whether user is logged on or not" only if the account's files are readable then.
* **A scheduled catch-up is built in**: if the machine slept, jobs that were due are run on wake or on the next start, and are idempotent.
* **NSSM** or a similar service wrapper, same command line.
* **Docker/Linux**: arrives with Phase 2; the same `family-hq run` is the container entrypoint.

A sleeping laptop means an offline bot. Discord will tell anyone using it that the application did not respond. That is expected on the laptop host and is the main reason to move to the always-on PC.

## Backups

```powershell
family-hq backup create                       # all configured destinations
family-hq backup create --to D:\usb\hq.sqlite3
family-hq backup create --scrub PRIVATE_WORK --to D:\for-home-pc\hq.sqlite3
family-hq backup list
family-hq backup prune
family-hq backup verify path\to\file.sqlite3
```

Backups use SQLite's online backup API (safe while the service is running), are verified with `PRAGMA integrity_check`, are timestamped in UTC (`family_hq-20261005T143000Z.sqlite3`), and are pruned with a retention policy: keep the newest N, the newest per day for D days, and the newest per week for W weeks. Pruning only ever deletes files matching the backup naming pattern, never anything else in the folder.

A destination with `scrub_scopes = ["PRIVATE_WORK"]` gets a copy with those rows deleted and the file `VACUUM`ed so the text does not survive in free pages. Use a scrubbed destination for anything cloud-synced.

**Restore** (manual by design): stop `family-hq run`, copy the backup over the database file (keep the old file aside first), start again. Migrations apply automatically on start.

## Migrating from the laptop to the home PC

1. **Decide what moves.** If the database contains PRIVATE_WORK tasks and you have not confirmed that moving them to a personal machine is acceptable, create a scrubbed bundle (step 2b). Otherwise use a full backup (2a).
2. On the old host:
   * 2a. `family-hq backup create --to C:\temp\hq.sqlite3`
   * 2b. `family-hq backup create --scrub PRIVATE_WORK --to C:\temp\hq.sqlite3`
3. **Stop the old bot** (`Ctrl+C` or stop the scheduled task). Two instances with the same token answer every command twice.
4. On the new host: install Python 3.12, `git clone`, create the venv, `pip install -e .`.
5. Copy `config.toml` and `.env` (carry the Discord token over by a secure route; do not email it). Edit machine-specific values: backup directory, Obsidian vault path.
6. Copy the backup to `data\family_hq.sqlite3` on the new host.
7. `family-hq config check`, `family-hq task list`, then `family-hq run`.
8. Set up Task Scheduler on the new host. Keep the old database file for a while as a rollback, but disable the old scheduled task.

If you moved a scrubbed bundle, the private-work tasks stay on the old machine's database. That is a legitimate way to run a split: the home PC serves the family and personal tasks, and your work tasks remain local to the work machine.

## Moving to PostgreSQL later (not needed now)

Install a driver (for example `psycopg`), set `database.url`, run `family-hq db upgrade`, and copy data with a one-off script. `BackupService` is SQLite specific; use `pg_dump` for Postgres. Nothing above the repository layer changes.
