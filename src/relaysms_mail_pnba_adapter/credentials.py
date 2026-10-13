# SPDX-License-Identifier: GPL-3.0-only
"""SimpleLogin, SMTP and Authy settings from credentials.json."""

import dataclasses
from dataclasses import dataclass

from relaysms_adapter_sdk import read_config

REQUIRED = (
    "sl_primary_email",
    "sl_primary_domain",
    "sl_api_key",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_password",
)


@dataclass(frozen=True)
class Credentials:
    sl_primary_email: str
    sl_primary_domain: str
    sl_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_tls: bool = True
    alias_prefix: str = ""
    alias_suffix: str = ""
    random_alias_prefix: str = "relaysms-"
    random_alias_id_bytes: int = 4
    random_alias_db_filename: str = "random_aliases.sqlite3"
    sl_base_url: str = "https://app.simplelogin.io/api"
    authy_base_url: str = "https://authy.shortmesh.com"
    authy_token: str | None = None
    authy_sender: str | None = None


def load() -> Credentials:
    """Read credentials.json from the adapter's config directory.

    Raises:
        ValueError: The file is invalid.
    """
    raw = read_config()
    blank = [key for key in REQUIRED if not str(raw.get(key, "")).strip()]
    if blank:
        raise ValueError(f"credentials.json needs {', '.join(blank)}.")
    try:
        raw["smtp_port"] = int(raw["smtp_port"])
    except ValueError as e:
        raise ValueError("smtp_port in credentials.json must be a number.") from e
    if isinstance(raw.get("smtp_use_tls"), str):
        raw["smtp_use_tls"] = raw["smtp_use_tls"].lower() == "true"

    fields = {field.name for field in dataclasses.fields(Credentials)}
    return Credentials(**{key: value for key, value in raw.items() if key in fields})
