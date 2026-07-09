# SPDX-License-Identifier: GPL-3.0-only

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from logutils import get_logger

logger = get_logger(__name__)


@dataclass
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
    RANDOM_ALIAS_POOL_SIZE: int = 15
    SL_BASE_URL: str = "https://app.simplelogin.io/api"
    AUTHY_BASE_URL: str = "https://authy.shortmesh.com"
    AUTHY_TOKEN: Optional[str] = field(default=None)
    AUTHY_SENDER: Optional[str] = field(default=None)


_REQUIRED_FIELDS = {
    "SL_PRIMARY_EMAIL",
    "SL_PRIMARY_DOMAIN",
    "SL_API_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
}


def _resolve_creds_path(configs: Dict[str, Any]) -> Path:
    creds_config = configs.get("credentials", {})
    raw_path = creds_config.get("path", "")
    if not raw_path:
        raise ValueError("Missing 'credentials.path' in configuration.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).parent / path
    return path


def _validate_and_clean_creds(creds: Dict[str, Any]) -> None:
    missing = _REQUIRED_FIELDS - creds.keys()
    if missing:
        raise ValueError(
            f"Missing required credential fields: {', '.join(sorted(missing))}"
        )

    blank = {
        k
        for k in _REQUIRED_FIELDS
        if isinstance(creds[k], str) and not creds[k].strip()
    }
    if blank:
        raise ValueError(
            f"Blank credential fields not allowed: {', '.join(sorted(blank))}"
        )

    try:
        creds["SMTP_PORT"] = int(creds["SMTP_PORT"])
    except (ValueError, TypeError):
        raise ValueError(
            f"SMTP_PORT must be a valid integer, got: {creds.get('SMTP_PORT')}"
        )

    if "SMTP_USE_TLS" in creds:
        val = creds["SMTP_USE_TLS"]
        if isinstance(val, str):
            if val.lower() == "true":
                creds["SMTP_USE_TLS"] = True
            elif val.lower() == "false":
                creds["SMTP_USE_TLS"] = False
            else:
                raise ValueError(
                    f"SMTP_USE_TLS must be 'true' or 'false', got: {val!r}"
                )
        else:
            creds["SMTP_USE_TLS"] = bool(val)


def load_credentials(configs: Dict[str, Any]) -> Credentials:
    """Load, validate, and return a Credentials instance from the specified path."""
    path = _resolve_creds_path(configs)
    logger.debug("Loading credentials from %s", path)
    try:
        with path.open(encoding="utf-8") as f:
            creds = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Credentials file not found: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Credentials file is not valid JSON: {e}")

    _validate_and_clean_creds(creds)
    return Credentials(**creds)
