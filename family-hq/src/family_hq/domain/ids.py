from __future__ import annotations

import re
import uuid

_HEX_PREFIX = re.compile(r"^[0-9a-fA-F-]{1,36}$")


def new_id() -> str:
    """Stable, immutable identifier (UUID4, lowercase, with dashes)."""
    return str(uuid.uuid4())


def looks_like_id_prefix(text: str) -> bool:
    return bool(_HEX_PREFIX.match(text))
