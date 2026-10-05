"""Phase 1 acceptance: using only the CLI, create, assign, modify, complete, block, list,
filter and inspect tasks, with historical activity retained."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from family_hq.cli.main import cli

EXAMPLE = Path(__file__).parent.parent / "config.example.toml"


class Hq:
    def __init__(self, tmp_path: Path) -> None:
        self.runner = CliRunner()
        self.config = tmp_path / "config.toml"
        self.config.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")

    def run(self, *args: str, as_: str | None = None, ok: bool = True):
        prefix = ["--config", str(self.config)]
        if as_:
            prefix += ["--as", as_]
        result = self.runner.invoke(cli, [*prefix, *args], catch_exceptions=False)
        if ok:
            assert result.exit_code == 0, f"{args} failed: {result.output}"
        else:
            assert result.exit_code != 0, f"{args} unexpectedly succeeded: {result.output}"
        return result

    def json(self, *args: str, as_: str | None = None):
        prefix = ["--json"]
        result = self.run(*prefix, *args, as_=as_)
        return json.loads(result.stdout)

    def first_id(self, *list_args: str, as_: str | None = None) -> str:
        return self.json("task", "list", *list_args, as_=as_)[0]["id"][:8]


@pytest.fixture
def hq(tmp_path):
    h = Hq(tmp_path)
    h.run("init", "--admin", "Joey")
    h.run("person", "add", "Mysti", "--role", "adult")
    h.run("person", "add", "Wyatt")
    return h


def test_the_whole_story_through_the_cli(hq):
    # create, with a spread of fields
    hq.run("project", "add", "Fix Van", "--desc", "brakes and door")
    hq.run("task", "add", "Fix bathroom sink", "--owner", "Wyatt", "--priority", "high",
           "--effort", "m", "--due", "fri", "--category", "Repair")  # fmt: skip
    hq.run("task", "add", "Clean garage", "--effort", "l")
    hq.run(
        "task",
        "add",
        "Call mechanic",
        "--mine",
        "--project",
        "Fix Van",
        "--effort",
        "xs",
        "--due",
        "+2d",
    )
    sink = hq.first_id("--search", "sink")
    garage = hq.first_id("--search", "garage")
    mechanic = hq.first_id("--search", "mechanic")

    # list and filter
    assert len(hq.json("task", "list")) == 3
    assert [t["title"] for t in hq.json("task", "list", "--owner", "Wyatt")] == [
        "Fix bathroom sink"
    ]
    assert [t["title"] for t in hq.json("task", "list", "--unassigned")] == ["Clean garage"]
    assert [t["title"] for t in hq.json("task", "list", "--mine")] == ["Call mechanic"]
    assert [t["title"] for t in hq.json("task", "list", "--project", "Fix Van")] == [
        "Call mechanic"
    ]
    assert [t["title"] for t in hq.json("task", "list", "--category", "repair")] == [
        "Fix bathroom sink"
    ]
    assert [t["title"] for t in hq.json("task", "list", "--priority", "high")] == [
        "Fix bathroom sink"
    ]
    assert len(hq.json("task", "list", "--due-by", "+30d")) == 2  # sink (fri) and mechanic (+2d)
    assert hq.json("task", "list", "--due-by", "today") == []
    table = hq.run("task", "list").stdout
    assert "about 13 workload points" in table and "(unassigned)" in table

    # assign, modify
    hq.run("task", "assign", garage, "Mysti")
    hq.run(
        "task",
        "edit",
        garage,
        "--priority",
        "urgent",
        "--due",
        "today",
        "--desc",
        "Rent the dumpster first",
    )
    shown = hq.json("task", "show", garage)
    assert shown["owner"] == "Mysti" and shown["priority"] == "URGENT" and shown["description"]

    # work it: start, block, unblock, complete
    hq.run("task", "start", sink, as_="Wyatt")
    hq.run("task", "block", sink, "need a new washer", as_="Wyatt")
    assert (
        hq.json("task", "list", "--status", "blocked")[0]["blocked_reason"] == "need a new washer"
    )
    hq.run("task", "unblock", sink, as_="Wyatt")
    hq.run("task", "note", sink, "bought the washer", as_="Wyatt")
    hq.run("task", "done", sink, as_="Wyatt")
    hq.run("task", "wait", mechanic, "shop to call back")
    assert hq.json("task", "show", mechanic)["status"] == "WAITING"
    hq.run("task", "snooze", mechanic, "+2d")
    assert hq.json("task", "list", "--hide-snoozed", "--mine") == []
    hq.run("task", "cancel", garage, "--reason", "hired a service")

    # completed and cancelled work does not vanish
    assert [t["title"] for t in hq.json("task", "list")] == ["Call mechanic"]
    closed = {t["title"]: t["status"] for t in hq.json("task", "list", "--all")}
    assert closed["Fix bathroom sink"] == "DONE" and closed["Clean garage"] == "CANCELLED"
    done = hq.json("task", "list", "--done-since", "today")
    assert [t["title"] for t in done] == ["Fix bathroom sink"]

    # inspect: history retained in order, human readable
    text = hq.run("task", "show", sink).stdout
    for needle in ("History", "created it", "started it", "marked it blocked: need a new washer",
                   "unblocked it", 'noted: "bought the washer"', "completed it", "Repair"):  # fmt: skip
        assert needle in text, needle
    history = hq.json("task", "history", sink)
    assert [e["type"] for e in history] == [
        "TASK_CREATED", "TASK_STARTED", "TASK_BLOCKED", "TASK_UNBLOCKED", "TASK_NOTE_ADDED", "TASK_COMPLETED",
    ]  # fmt: skip
    assert [e["seq"] for e in history] == sorted(e["seq"] for e in history)

    # reopen
    hq.run("task", "reopen", sink)
    assert hq.json("task", "show", sink)["status"] == "OPEN"


def test_inbox_capture_and_triage(hq):
    hq.run("task", "add", "Maybe look at gutters", "--inbox")
    assert [t["title"] for t in hq.json("task", "list", "--status", "inbox")] == [
        "Maybe look at gutters"
    ]
    ref = hq.first_id("--status", "inbox")
    hq.run("task", "triage", ref, "open")
    assert hq.json("task", "show", ref)["status"] == "OPEN"
    assert "No matching tasks." in hq.run("task", "inbox").stdout


def test_private_work_stays_out_of_other_peoples_cli_views(hq):
    hq.run("task", "add", "Quarterly review prep", "--scope", "private-work")
    hq.run("task", "add", "Water plants", "--owner", "Wyatt")
    assert len(hq.json("task", "list")) == 2
    wyatt_view = hq.json("task", "list", as_="Wyatt")
    assert [t["title"] for t in wyatt_view] == ["Water plants"]
    mysti_view = hq.run("task", "list", "--search", "review", as_="Mysti")
    assert "Quarterly" not in mysti_view.output
    secret_id = hq.first_id("--search", "quarterly")
    result = hq.run("task", "show", secret_id, as_="Mysti", ok=False)
    assert "No such task" in result.output and "Quarterly" not in result.output


def test_errors_are_clean_messages_with_nonzero_exit(hq):
    r = hq.run("task", "show", "deadbeef", ok=False)
    assert r.output.strip() == "Error: No such task"
    r = hq.run("task", "add", "x", "--due", "someday", ok=False)
    assert "Could not understand date" in r.output
    r = hq.run("task", "add", "x", "--effort", "huge", ok=False)
    assert "Unknown effort" in r.output
    r = hq.run("person", "add", "Eve", as_="Wyatt", ok=False)
    assert "permission" in r.output
    r = hq.run("--as", "Nobody", "task", "list", ok=False)
    assert "No such person" in r.output


def test_init_is_repeatable_and_does_not_create_a_second_admin(hq):
    out = hq.run("init", "--admin", "Intruder").stdout
    assert "nothing to bootstrap" in out
    assert [p["name"] for p in hq.json("person", "list")] == ["Joey", "Mysti", "Wyatt"]


def test_categories_are_configurable_from_the_cli(hq):
    hq.run("category", "add", "Pets")
    hq.run("category", "rename", "Pets", "Animals")
    hq.run("task", "add", "Feed the cat", "--category", "animals")
    hq.run("category", "deactivate", "Animals")
    assert "Animals" not in hq.run("category", "list").stdout
    hq.run("task", "add", "Another", "--category", "animals", ok=False)
    hq.run("task", "add", "Not allowed", "--category", "Repair", as_="Wyatt")
    hq.run("category", "add", "Mine", as_="Wyatt", ok=False)


def test_backup_commands(hq, tmp_path):
    hq.run("task", "add", "Backup me")
    out = hq.run("backup", "create").stdout
    assert "[local]" in out
    listing = hq.run("backup", "list").stdout
    assert "family_hq-" in listing
    bundle = tmp_path / "bundle" / "hq.sqlite3"
    hq.run("task", "add", "Work secret ZZQQ", "--scope", "private-work")
    hq.run("backup", "create", "--scrub", "PRIVATE_WORK", "--to", str(bundle))
    assert b"ZZQQ" not in bundle.read_bytes()
    verify = hq.run("backup", "verify", str(bundle)).stdout
    assert "integrity: OK" in verify and "tasks=1" in verify
    hq.run("backup", "create", as_="Wyatt", ok=False)


def test_config_check_and_db_commands(hq):
    out = hq.run("config", "check").stdout
    assert "America/New_York" in out and "PRIVATE_WORK" in out and "OBSIDIAN" in out
    assert "discord token not set" in out
    assert "up to date" in hq.run("db", "upgrade").stdout
    current = hq.run("db", "current").stdout
    assert current.split()[1] == current.split()[3]


def test_project_commands(hq):
    hq.run("project", "add", "Vacation", "--due", "+30d")
    hq.run("task", "add", "Book hotel", "--project", "Vacation", "--effort", "m")
    shown = hq.run("project", "show", "vacation").stdout
    assert "Vacation" in shown and "Book hotel" in shown and "4 workload points" in shown
    hq.run("project", "status", "Vacation", "on-hold")
    assert "ON_HOLD" in hq.run("project", "list").stdout
    hq.run("project", "status", "Vacation", "done")
    assert "No projects." in hq.run("project", "list").stdout
    hq.run("task", "add", "Late idea", "--project", "Vacation", ok=False)
