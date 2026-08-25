# SPDX-License-Identifier: GPL-3.0-only

import base64
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from authy import AuthyClient
from config import Credentials, load_credentials
from logutils import get_logger
from protocol_interfaces import PNBAProtocolInterface
from simplelogin import AliasResponse, Attachment, SimpleLoginClient, SMTPConfig

logger = get_logger(__name__)


def _require(kwargs: dict, *fields: str) -> tuple:
    missing = [f for f in fields if not kwargs.get(f)]
    if missing:
        raise ValueError(f"Missing required parameter(s): {', '.join(missing)}")
    return tuple(kwargs[f] for f in fields)


class RelaySMSMailPNBAAdapter(PNBAProtocolInterface):
    """Adapter integrating RelaySMS-Mail with the PNBA protocol."""

    def __init__(self):
        self.credentials: Credentials = load_credentials(self.config)
        self.client: SimpleLoginClient = SimpleLoginClient(
            api_key=self.credentials.SL_API_KEY,
            smtp=SMTPConfig(
                host=self.credentials.SMTP_HOST,
                port=self.credentials.SMTP_PORT,
                username=self.credentials.SMTP_USERNAME,
                password=self.credentials.SMTP_PASSWORD,
                use_tls=self.credentials.SMTP_USE_TLS,
            ),
            base_url=self.credentials.SL_BASE_URL,
        )
        self.authy: AuthyClient = AuthyClient(
            base_url=self.credentials.AUTHY_BASE_URL,
            token=self.credentials.AUTHY_TOKEN,
        )

    def _normalize_phone(self, phone_number: str) -> str:
        return re.sub(r"\D", "", phone_number)

    def _build_alias(self, phone_number: str) -> str:
        digits = self._normalize_phone(phone_number)
        return (
            f"{self.credentials.ALIAS_PREFIX}"
            f"{digits}"
            f"{self.credentials.ALIAS_SUFFIX}"
            f"@{self.credentials.SL_PRIMARY_DOMAIN}"
        )

    def _build_alias_prefix(self, phone_number: str) -> str:
        digits = self._normalize_phone(phone_number)
        return f"{self.credentials.ALIAS_PREFIX}{digits}{self.credentials.ALIAS_SUFFIX}"

    def _get_alias(self, phone_number: str) -> Optional[AliasResponse]:
        alias = self._build_alias(phone_number)
        aliases = self.client.fetch_aliases(
            query=alias,
            mailbox_email=self.credentials.SL_PRIMARY_EMAIL,
        )
        if not aliases:
            logger.debug("Alias '%s' not found.", alias)
            return None
        return aliases[0]

    def _get_mailbox_id(self) -> int:
        mailbox = self.client.fetch_mailbox_by_email(self.credentials.SL_PRIMARY_EMAIL)
        if not mailbox:
            raise RuntimeError(
                f"Mailbox for '{self.credentials.SL_PRIMARY_EMAIL}' not found."
            )
        return mailbox["id"]

    def _create_alias(self, phone_number: str) -> AliasResponse:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S (%Z)")
        return self.client.create_alias(
            alias_prefix=self._build_alias_prefix(phone_number),
            mailbox_id=self._get_mailbox_id(),
            hostname=self.credentials.SL_PRIMARY_DOMAIN,
            alias_name=f"{self._normalize_phone(phone_number)} Via RelaySMS-Mail",
            note=f"Created by RelaySMS-Mail at {timestamp}.",
        )

    def _get_or_create_alias(self, phone_number: str) -> AliasResponse:
        """Return existing alias, enabling it if disabled, or create a new one."""
        alias = self._get_alias(phone_number)
        if alias:
            if not alias.get("enabled"):
                self.client.toggle_alias(alias["id"])
                logger.debug("Re-enabled alias %s.", alias["email"])
            return alias
        return self._create_alias(phone_number)

    def _create_random_alias(self) -> AliasResponse:
        random_id = secrets.token_hex(self.credentials.RANDOM_ALIAS_ID_BYTES)
        alias_prefix = f"{self.credentials.RANDOM_ALIAS_PREFIX}{random_id}"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S (%Z)")

        return self.client.create_alias(
            alias_prefix=alias_prefix,
            mailbox_id=self._get_mailbox_id(),
            hostname=self.credentials.SL_PRIMARY_DOMAIN,
            alias_name="RelaySMS-Mail No-Reply",
            note=f"Created by RelaySMS-Mail No-Reply at {timestamp}.",
        )

    def _send_email(
        self,
        alias: AliasResponse,
        to_email: str,
        subject: str,
        message: str,
        attachments: list,
    ) -> None:
        self.client.send_email(
            alias_id=alias["id"],
            from_email=self.credentials.SL_PRIMARY_EMAIL,
            to_email=to_email,
            subject=subject,
            body=message,
            attachments=attachments,
        )

    def send_authorization_code(self, phone_number: str, **kwargs) -> Dict[str, Any]:
        (channel,) = _require(kwargs, "channel")

        otp = self.authy.generate_otp(
            phone_number=phone_number,
            platform=channel,
            sender=self.credentials.AUTHY_SENDER,
        )

        return {
            "success": True,
            "message": "Authorization code sent.",
            "expires_at": otp["expires_at"],
        }

    def validate_code_and_fetch_user_info(
        self, phone_number: str, code: str, **kwargs
    ) -> Dict[str, Any]:
        (channel,) = _require(kwargs, "channel")

        self.authy.verify_otp(phone_number=phone_number, platform=channel, code=code)

        alias = self._get_or_create_alias(phone_number)

        return {
            "userinfo": {"account_identifier": phone_number, "name": alias["email"]},
        }

    def validate_password_and_fetch_user_info(
        self, phone_number: str, password: str, **_
    ) -> Dict[str, Any]:
        return {}

    def invalidate_session(self, phone_number: str, **_) -> bool:
        alias = self._get_alias(phone_number)
        if not alias or not alias.get("enabled"):
            logger.debug("Alias not found or already disabled.")
            return True
        self.client.toggle_alias(alias["id"])
        logger.debug("Alias disabled successfully.")
        return True

    def send_message(self, phone_number: Optional[str] = None, **kwargs) -> bool:
        subject, to_email, message = _require(kwargs, "subject", "to_email", "message")

        processed_attachments = []
        for idx, att_dict in enumerate(kwargs.get("attachments") or []):
            filename = att_dict.get("filename", f"attachment_{idx}")
            try:
                processed_attachments.append(
                    Attachment(
                        data=base64.b64decode(att_dict.get("data", "")),
                        filename=filename,
                        mimetype=att_dict.get("mimetype"),
                    )
                )
            except Exception as exc:
                raise ValueError(f"Invalid attachment data in '{filename}'.") from exc

        if phone_number:
            alias = self._get_alias(phone_number)
            if not alias or not alias.get("enabled"):
                raise RuntimeError(f"Alias for '{phone_number}' not found or disabled.")
        else:
            alias = self._create_random_alias()

        self._send_email(alias, to_email, subject, message, processed_attachments)
        return True
