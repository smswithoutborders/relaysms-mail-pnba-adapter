# SPDX-License-Identifier: GPL-3.0-only
"""SimpleLogin, SMTP and Authy settings from credentials.json."""

import dataclasses
import json
from dataclasses import dataclass

from relaysms_adapter_sdk import config_dir

FILENAME = "credentials.json"
REQUIRED = (
    "SL_PRIMARY_EMAIL",
    "SL_PRIMARY_DOMAIN",
    "SL_API_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
)


@dataclass(frozen=True)
class Credentials:
    SL_PRIMARY_EMAIL: str
    SL_PRIMARY_DOMAIN: str
    SL_API_KEY: str
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_USE_TLS: bool = True
    ALIAS_PREFIX: str = ""
    ALIAS_SUFFIX: str = ""
    RANDOM_ALIAS_PREFIX: str = "relaysms-"
    RANDOM_ALIAS_ID_BYTES: int = 4
    RANDOM_ALIAS_DB_FILENAME: str = "random_aliases.sqlite3"
    SL_BASE_URL: str = "https://app.simplelogin.io/api"
    AUTHY_BASE_URL: str = "https://authy.shortmesh.com"
    AUTHY_TOKEN: str | None = None
    AUTHY_SENDER: str | None = None


def load() -> Credentials:
    """Read credentials.json from the adapter's config directory.

    Raises:
        ValueError: The file is invalid.
    """
    path = config_dir() / FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path} is not valid JSON: {e}") from e

    blank = [key for key in REQUIRED if not str(raw.get(key, "")).strip()]
    if blank:
        raise ValueError(f"{path} needs {', '.join(blank)}.")
    try:
        raw["SMTP_PORT"] = int(raw["SMTP_PORT"])
    except ValueError as e:
        raise ValueError(f"SMTP_PORT in {path} must be a number.") from e
    if isinstance(raw.get("SMTP_USE_TLS"), str):
        raw["SMTP_USE_TLS"] = raw["SMTP_USE_TLS"].lower() == "true"

    fields = {field.name for field in dataclasses.fields(Credentials)}
    return Credentials(**{key: value for key, value in raw.items() if key in fields})
