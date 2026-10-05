from __future__ import annotations

import asyncio
import json
import logging

from family_hq.app import build_jobs, run_forever, warn_if_synced_folder
from family_hq.config import LoggingSection
from family_hq.logging_setup import JsonFormatter, KeyValueFormatter, configure_logging


def test_jobs_include_backup_when_enabled(world):
    assert [j.name for j in build_jobs(world.container)] == ["backup"]


def test_run_forever_catches_up_runs_jobs_and_stops_cleanly(world):
    async def scenario() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(run_forever(world.container, stop))
        for _ in range(100):  # wait for the catch-up backup to appear
            await asyncio.sleep(0.05)
            if list((world.settings.data_dir / "backups").glob("family_hq-*.sqlite3")):
                break
        stop.set()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(scenario())
    assert list((world.settings.data_dir / "backups").glob("family_hq-*.sqlite3"))


def test_a_failing_job_does_not_stop_the_service(world, caplog):
    from family_hq.app import Job, _run_job

    calls: list[int] = []

    def flaky() -> None:
        calls.append(1)
        raise RuntimeError("boom")

    async def scenario() -> None:
        stop = asyncio.Event()
        runner = asyncio.create_task(_run_job(Job("flaky", 0.01, flaky), stop))
        await asyncio.sleep(0.2)
        stop.set()
        await asyncio.wait_for(runner, timeout=2)

    caplog.set_level(logging.ERROR)
    asyncio.run(scenario())
    assert len(calls) >= 2
    assert any(r.getMessage() == "job_failed" for r in caplog.records)


def test_synced_folder_warning(tmp_path):
    bad = tmp_path / "OneDrive - Contoso" / "hq.sqlite3"
    assert warn_if_synced_folder(f"sqlite:///{bad.as_posix()}") is not None
    assert warn_if_synced_folder(f"sqlite:///{(tmp_path / 'ok' / 'hq.sqlite3').as_posix()}") is None
    assert warn_if_synced_folder("postgresql+psycopg://u:p@host/db") is None


def test_formatters_include_extra_fields_and_valid_json():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "task_created", None, None)
    record.task_id = "abc"
    payload = json.loads(JsonFormatter().format(record))
    assert (
        payload["event"] == "task_created"
        and payload["task_id"] == "abc"
        and payload["level"] == "INFO"
    )
    assert "task_id=abc" in KeyValueFormatter().format(record)


def test_configure_logging_writes_to_a_file(tmp_path):
    section = LoggingSection(level="INFO", json=True, file=tmp_path / "logs" / "hq.log")
    configure_logging(section)
    logging.getLogger("family_hq.test").info("hello", extra={"n": 1})
    for handler in logging.getLogger().handlers:
        handler.flush()
    line = (tmp_path / "logs" / "hq.log").read_text().strip().splitlines()[-1]
    assert json.loads(line)["event"] == "hello"
    logging.getLogger().handlers.clear()
