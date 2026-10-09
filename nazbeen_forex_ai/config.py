"""Environment-based configuration helpers.

Every runtime setting is read from environment variables (see ``.env.example``).
These helpers keep parsing rules explicit and unit-testable instead of scattering
``os.environ.get`` calls through the settings modules.

A local ``.env`` file (git-ignored) is loaded if present; real environment
variables always take precedence over values from the file.
"""

from __future__ import annotations

import os
from pathlib import Path

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def load_dotenv(path: Path | str | None = None) -> None:
    """Load a simple KEY=VALUE .env file into ``os.environ`` without overriding
    variables that are already set.

    Deliberately minimal: comments, blank lines, optional ``export `` prefix and
    optional surrounding quotes are supported. No external dependency.
    """
    env_path = Path(path) if path is not None else Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def env_str(key: str, default: str | None = None) -> str | None:
    """Return the string value of ``key`` or ``default``."""
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def env_bool(key: str, default: bool = False) -> bool:
    """Parse a boolean environment variable.

    Raises ``ValueError`` for values that are not recognized, so typos in
    configuration fail fast instead of silently flipping behaviour.
    """
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(
        f"Invalid boolean for {key}={value!r}; expected one of "
        f"{sorted(_TRUE_VALUES | _FALSE_VALUES)}"
    )


def env_int(key: str, default: int) -> int:
    """Parse an integer environment variable, failing fast on bad input."""
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {key}={value!r}") from exc


def env_list(key: str, default: str = "") -> list[str]:
    """Parse a comma-separated environment variable into a trimmed list."""
    value = os.environ.get(key)
    if value is None or value == "":
        value = default
    return [item.strip() for item in value.split(",") if item.strip()]
