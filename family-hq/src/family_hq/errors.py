"""Exception hierarchy.

Contract: messages on these exceptions may be shown to end users (CLI output, Discord
replies) and written to logs. They must therefore NEVER contain task titles, descriptions,
notes or project names. Refer to objects by id or by generic wording.
"""


class FamilyHQError(Exception):
    """Base class for every expected, user-presentable error."""


class ConfigError(FamilyHQError):
    """Configuration is missing or invalid."""


class ValidationError(FamilyHQError):
    """Input is malformed or violates a domain rule."""


class NotFoundError(FamilyHQError):
    """Object does not exist OR the actor may not see it (deliberately indistinguishable)."""


class PermissionDeniedError(FamilyHQError):
    """The actor can see the object but may not perform the action."""


class ConflictError(FamilyHQError):
    """State conflict: invalid transition, already claimed, stale write, duplicate name."""
