from __future__ import annotations

from pathlib import Path

import pytest

from family_hq.app import startup
from family_hq.application.actor import Actor
from family_hq.config import load_secrets, load_settings
from family_hq.domain.enums import Effort, Scope, Sink, Source
from family_hq.errors import ConfigError

EXAMPLE = Path(__file__).parent.parent / "config.example.toml"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_config_loads_and_matches_documented_defaults(tmp_path):
    settings = load_settings(write(tmp_path, EXAMPLE.read_text(encoding="utf-8")))
    assert settings.app.timezone == "America/New_York"
    assert settings.effort_points[Effort.XL] == 16
    policy = settings.sink_policy
    assert policy.allows(Scope.FAMILY, Sink.DISCORD_CHANNEL)
    assert not policy.allows(Scope.PRIVATE_WORK, Sink.AI)
    assert settings.backup.retention.keep_last == 14


def test_relative_paths_resolve_against_the_config_file_not_the_cwd(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    cfg_dir = tmp_path / "install"
    cfg_dir.mkdir()
    settings = load_settings(write(cfg_dir, '[app]\ntimezone = "UTC"\ndata_dir = "mydata"\n'))
    assert settings.data_dir == cfg_dir.resolve() / "mydata"
    assert settings.database_url.endswith("/mydata/family_hq.sqlite3")
    [dest] = settings.backup_destinations
    assert dest.path == cfg_dir.resolve() / "mydata" / "backups"


def test_config_path_from_environment(tmp_path, monkeypatch):
    path = write(tmp_path, '[app]\ntimezone = "UTC"\n')
    monkeypatch.setenv("FAMILY_HQ_CONFIG", str(path))
    assert load_settings().app.timezone == "UTC"


def test_missing_config_gives_actionable_error(tmp_path, monkeypatch):
    monkeypatch.delenv("FAMILY_HQ_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match=r"config\.example\.toml"):
        load_settings()


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ('[app]\ntimezone = "Mars/Olympus"\n', "unknown time zone"),
        ('[app]\ntimezone = "UTC"\ntypo = 1\n', "typo"),
        ('[app]\ntimezone = "UTC"\n[discord]\ntoken = "abc"\n', "looks like a secret"),
        ('[app]\ntimezone = "UTC"\n[logging]\napi_key = "abc"\n', "looks like a secret"),
        (
            '[app]\ntimezone = "UTC"\n[visibility.sinks]\nPERSONAL = ["DISCORD_CHANNEL"]\n',
            "family-audience",
        ),
        ('[app]\ntimezone = "UTC"\n[workload.points]\nXS = 1\n', "missing efforts"),
        ('[app]\ntimezone = "UTC"\n[backup.retention]\nkeep_last = 0\n', "keep_last"),
        (
            '[app]\ntimezone = "UTC"\n[[backup.destinations]]\nname="x"\npath="y"\nscrub_scopes=["NOPE"]\n',
            "scope",
        ),
        ("[app\n", "invalid TOML"),
        ("", "app"),
    ],
)
def test_bad_config_is_rejected_with_a_readable_message(tmp_path, body, fragment):
    with pytest.raises(ConfigError) as exc:
        load_settings(write(tmp_path, body))
    assert fragment in str(exc.value)


def test_secrets_come_from_dotenv_next_to_the_config(tmp_path, monkeypatch):
    monkeypatch.delenv("FAMILY_HQ_DISCORD_TOKEN", raising=False)
    settings = load_settings(write(tmp_path, '[app]\ntimezone = "UTC"\n'))
    assert load_secrets(settings).discord_token is None
    (tmp_path / ".env").write_text("FAMILY_HQ_DISCORD_TOKEN=abc123\n", encoding="utf-8")
    secrets = load_secrets(settings)
    assert secrets.discord_token is not None
    assert secrets.discord_token.get_secret_value() == "abc123"
    assert "abc123" not in repr(secrets)  # never printed by accident


def test_categories_are_seeded_once_and_renames_survive_restart(tmp_path):
    settings = load_settings(
        write(tmp_path, '[app]\ntimezone = "UTC"\n[categories]\ninitial = ["Chore", "Errand"]\n')
    )
    c = startup(settings)
    admin = Actor(c.people.bootstrap_admin("Joey"), Source.CLI)
    assert [x.name for x in c.categories.list_categories()] == ["Chore", "Errand"]
    c.categories.rename(admin, "Chore", "Chores")
    c.close()
    again = startup(settings)  # restart: must not re-add "Chore"
    assert [x.name for x in again.categories.list_categories()] == ["Chores", "Errand"]
    again.close()
