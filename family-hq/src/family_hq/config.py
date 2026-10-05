"""Configuration: application settings from TOML, secrets from the environment / .env.

* Unknown keys are errors (typos should not silently do nothing).
* Secrets are refused in the TOML file; they belong in .env (never committed).
* Relative paths resolve against the config file's directory, not the working directory.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from family_hq.db.engine import sqlite_url
from family_hq.domain.enums import Effort, Scope
from family_hq.domain.visibility import SinkPolicy
from family_hq.domain.workload import DEFAULT_POINTS
from family_hq.errors import ConfigError, FamilyHQError

DEFAULT_CATEGORIES = [
    "Chore", "Cleaning", "Errand", "Parenting", "School", "Appointment", "Finance",
    "Administrative", "Repair", "Vehicle", "Shopping", "Home", "Project", "Personal", "Work",
]  # fmt: skip

ENV_CONFIG_PATH = "FAMILY_HQ_CONFIG"
_SECRET_KEY_HINTS = ("token", "secret", "password", "api_key", "apikey", "webhook")


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AppSection(_Section):
    timezone: str
    data_dir: Path = Path("data")

    @field_validator("timezone")
    @classmethod
    def _valid_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown time zone '{value}' (example: America/New_York)") from None
        return value


class DatabaseSection(_Section):
    url: str | None = None  # default: sqlite file in data_dir


class CliSection(_Section):
    default_actor: str | None = None  # person display name used when --as is not given


class CategoriesSection(_Section):
    initial: list[str] = Field(default_factory=lambda: list(DEFAULT_CATEGORIES))


class WorkloadSection(_Section):
    points: dict[str, int] = Field(
        default_factory=lambda: {e.value: p for e, p in DEFAULT_POINTS.items()}
    )

    @field_validator("points")
    @classmethod
    def _complete(cls, value: dict[str, int]) -> dict[str, int]:
        try:
            parsed = {Effort.parse(k).value: v for k, v in value.items()}
        except FamilyHQError as exc:
            raise ValueError(str(exc)) from None
        missing = [e.value for e in Effort if e.value not in parsed]
        if missing:
            raise ValueError(f"missing efforts: {', '.join(missing)}")
        if any(v < 0 for v in parsed.values()):
            raise ValueError("points must be >= 0")
        return parsed


class VisibilitySection(_Section):
    # {"FAMILY": ["OBSIDIAN", ...]}; scopes left out use the safe defaults.
    sinks: dict[str, list[str]] = Field(default_factory=dict)


class RetentionSection(_Section):
    keep_last: int = Field(14, ge=1)
    keep_daily_days: int = Field(30, ge=0)
    keep_weekly_weeks: int = Field(12, ge=0)


class BackupDestinationSection(_Section):
    name: str
    path: Path
    scrub_scopes: list[str] = Field(default_factory=list)

    @field_validator("scrub_scopes")
    @classmethod
    def _valid_scopes(cls, value: list[str]) -> list[str]:
        try:
            return [Scope.parse(v).value for v in value]
        except FamilyHQError as exc:
            raise ValueError(str(exc)) from None


class BackupSection(_Section):
    enabled: bool = True
    interval_hours: float = Field(24, gt=0)
    retention: RetentionSection = Field(default_factory=lambda: RetentionSection())
    destinations: list[BackupDestinationSection] = Field(default_factory=list)


class LoggingSection(_Section):
    level: str = "INFO"
    json_format: bool = Field(False, alias="json")
    file: Path | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Settings(_Section):
    app: AppSection
    database: DatabaseSection = Field(default_factory=DatabaseSection)
    cli: CliSection = Field(default_factory=CliSection)
    categories: CategoriesSection = Field(default_factory=CategoriesSection)
    workload: WorkloadSection = Field(default_factory=WorkloadSection)
    visibility: VisibilitySection = Field(default_factory=VisibilitySection)
    backup: BackupSection = Field(default_factory=lambda: BackupSection())
    logging: LoggingSection = Field(default_factory=lambda: LoggingSection())

    # Not part of the file: where the config lives; every relative path hangs off this.
    base_dir: Path = Field(default=Path("."), exclude=True)

    @model_validator(mode="after")
    def _check_sink_policy(self) -> Settings:
        self.sink_policy  # noqa: B018  (raises ConfigError on an invalid policy)
        return self

    # ---- derived values -------------------------------------------------------------------

    def resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else (self.base_dir / path)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app.timezone)

    @property
    def data_dir(self) -> Path:
        return self.resolve(self.app.data_dir)

    @property
    def database_url(self) -> str:
        return self.database.url or sqlite_url(self.data_dir / "family_hq.sqlite3")

    @property
    def sink_policy(self) -> SinkPolicy:
        return SinkPolicy.from_lists(self.visibility.sinks)

    @property
    def effort_points(self) -> dict[Effort, int]:
        return {Effort.parse(k): v for k, v in self.workload.points.items()}

    @property
    def backup_destinations(self) -> list[BackupDestinationSection]:
        """Configured destinations with absolute paths; a default local one if none given."""
        configured = self.backup.destinations or [
            BackupDestinationSection(name="local", path=Path("backups"), scrub_scopes=[])
        ]
        base = self.data_dir if not self.backup.destinations else self.base_dir
        return [d.model_copy(update={"path": d.path if d.path.is_absolute() else base / d.path})
                for d in configured]  # fmt: skip


class Secrets(BaseSettings):
    """Values that must never live in the TOML file or in git. Read from env / .env."""

    model_config = SettingsConfigDict(env_prefix="FAMILY_HQ_", extra="ignore")

    discord_token: SecretStr | None = None
    ai_api_key: SecretStr | None = None


def find_config_path(explicit: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    elif os.environ.get(ENV_CONFIG_PATH):
        candidates.append(Path(os.environ[ENV_CONFIG_PATH]))
    else:
        candidates.append(Path.cwd() / "config.toml")
    path = candidates[0]
    if not path.is_file():
        raise ConfigError(
            f"Config file not found: {path}. Copy config.example.toml to config.toml and edit it, "
            f"or pass --config / set {ENV_CONFIG_PATH}."
        )
    return path


def _reject_secrets(data: Any, prefix: str = "") -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            full = f"{prefix}{key}"
            if any(hint in str(key).lower() for hint in _SECRET_KEY_HINTS):
                raise ConfigError(
                    f"'{full}' looks like a secret. Secrets belong in .env, not in config.toml."
                )
            _reject_secrets(value, f"{full}.")
    elif isinstance(data, list):
        for item in data:
            _reject_secrets(item, prefix)


def load_settings(path: Path | None = None) -> Settings:
    config_path = find_config_path(path).resolve()
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{config_path}: invalid TOML: {exc}") from exc
    _reject_secrets(raw)
    try:
        settings = Settings.model_validate(raw)
    except PydanticValidationError as exc:
        problems = "\n".join(
            f"  - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigError(f"{config_path} is not valid:\n{problems}") from exc
    except FamilyHQError:
        raise
    settings.base_dir = config_path.parent
    return settings


def load_secrets(settings: Settings) -> Secrets:
    return Secrets(_env_file=settings.base_dir / ".env")
