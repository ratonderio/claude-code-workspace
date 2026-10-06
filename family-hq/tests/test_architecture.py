"""Import rules from docs/architecture.md, enforced by scanning the source tree."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "family_hq"


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def files(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


THIRD_PARTY_FORBIDDEN_IN_DOMAIN_AND_APP = (
    "sqlalchemy",
    "alembic",
    "discord",
    "googleapiclient",
    "click",
)


@pytest.mark.parametrize("path", files("domain"), ids=lambda p: p.name)
def test_domain_depends_on_nothing_but_the_standard_library(path):
    for module in imports_of(path):
        if module.startswith("family_hq"):
            assert module.startswith(("family_hq.domain", "family_hq.errors")), (path.name, module)
        else:
            top = module.split(".")[0]
            assert top not in THIRD_PARTY_FORBIDDEN_IN_DOMAIN_AND_APP, (path.name, module)


@pytest.mark.parametrize("path", files("application"), ids=lambda p: p.name)
def test_application_layer_knows_no_infrastructure(path):
    for module in imports_of(path):
        assert module.split(".")[0] not in THIRD_PARTY_FORBIDDEN_IN_DOMAIN_AND_APP, (
            path.name,
            module,
        )
        assert not module.startswith(
            (
                "family_hq.db",
                "family_hq.repositories.sqlalchemy",
                "family_hq.cli",
                "family_hq.config",
            )
        ), (path.name, module)


@pytest.mark.parametrize("path", files("cli"), ids=lambda p: p.name)
def test_cli_goes_through_services_not_repositories(path):
    allowed_db = {"family_hq.db.migrate"}
    for module in imports_of(path):
        assert not module.startswith("family_hq.repositories"), (path.name, module)
        if module.startswith("family_hq.db"):
            assert module in allowed_db, (path.name, module)


@pytest.mark.parametrize("path", files("repositories"), ids=lambda p: p.name)
def test_repositories_do_not_import_services(path):
    for module in imports_of(path):
        assert not module.startswith(("family_hq.application", "family_hq.cli", "family_hq.app")), (
            path.name,
            module,
        )
