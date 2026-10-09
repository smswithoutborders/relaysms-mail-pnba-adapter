# SPDX-License-Identifier: GPL-3.0-only

import logging
import re
import secrets
import smtplib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import override

from relaysms_adapter_sdk import (
    Account,
    AdapterError,
    AuthenticationError,
    CodeRequest,
    CodeSent,
    CodeVerificationRequest,
    InvalidParamsError,
    PNBAAdapter,
    RevokeRequest,
    SendRequest,
    SendResult,
    TokenInvalidError,
    UpstreamError,
)

from relaysms_mail_pnba_adapter import credentials
from relaysms_mail_pnba_adapter.authy import AuthyClient, AuthyError
from relaysms_mail_pnba_adapter.random_alias_store import RandomAliasStore
from relaysms_mail_pnba_adapter.simplelogin import (
    AliasResponse,
    Attachment,
    SimpleLoginClient,
    SimpleLoginError,
    SMTPConfig,
)

logger = logging.getLogger(__name__)

RANDOM_ALIAS_ATTEMPTS = 10


class RelaySMSMailAdapter(PNBAAdapter):
    def __init__(self) -> None:
        self.credentials = credentials.load()
        self.client = SimpleLoginClient(
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
        self.authy = AuthyClient(
            base_url=self.credentials.AUTHY_BASE_URL,
            token=self.credentials.AUTHY_TOKEN,
        )

    @override
    def send_code(self, request: CodeRequest) -> CodeSent:
        if not request.channel:
            raise InvalidParamsError("A channel is required.")
        with _upstream():
            otp = self.authy.generate_otp(
                phone_number=request.phone_number,
                platform=request.channel,
                sender=self.credentials.AUTHY_SENDER,
            )
        return CodeSent(
            expires_at=_expiry(otp.get("expires_at")),
            message="Authorization code sent.",
        )

    @override
    def verify_code(self, request: CodeVerificationRequest) -> Account:
        if not request.channel:
            raise InvalidParamsError("A channel is required.")
        try:
            self.authy.verify_otp(
                phone_number=request.phone_number,
                platform=request.channel,
                code=request.code,
            )
        except AuthyError as e:
            raise AuthenticationError(str(e)) from e
        with _upstream():
            alias = self._get_or_create_alias(request.phone_number)
        return Account(identifier=request.phone_number, name=alias["email"])

    @override
    def revoke(self, request: RevokeRequest) -> None:
        with _upstream():
            alias = self._get_alias(request.account.identifier)
            if alias and alias.get("enabled"):
                self.client.toggle_alias(alias["id"])
                logger.info("Alias disabled.")

    @override
    def send_message(self, request: SendRequest) -> SendResult:
        message = request.message
        if not message.recipient:
            raise InvalidParamsError("A recipient is required.")
        attachments = [
            Attachment(data=a.data, filename=a.filename, mimetype=a.mimetype)
            for a in message.attachments
        ]
        with _upstream():
            if request.account is None:
                alias = self._create_random_alias()
            else:
                alias = self._get_alias(request.account.identifier)
                if not alias or not alias.get("enabled"):
                    raise TokenInvalidError("The alias is gone or disabled.")
            self.client.send_email(
                alias_id=alias["id"],
                from_email=self.credentials.SL_PRIMARY_EMAIL,
                to_email=message.recipient,
                subject=message.subject or "",
                body=message.body,
                attachments=attachments,
            )
        return SendResult()

    def _alias_prefix(self, phone_number: str) -> str:
        digits = re.sub(r"\D", "", phone_number)
        return f"{self.credentials.ALIAS_PREFIX}{digits}{self.credentials.ALIAS_SUFFIX}"

    def _get_alias(self, phone_number: str) -> AliasResponse | None:
        alias = (
            f"{self._alias_prefix(phone_number)}@{self.credentials.SL_PRIMARY_DOMAIN}"
        )
        aliases = self.client.fetch_aliases(
            query=alias, mailbox_email=self.credentials.SL_PRIMARY_EMAIL
        )
        return aliases[0] if aliases else None

    def _get_or_create_alias(self, phone_number: str) -> AliasResponse:
        """Return the number's alias, enabling it if disabled, or create one."""
        alias = self._get_alias(phone_number)
        if alias:
            if not alias.get("enabled"):
                self.client.toggle_alias(alias["id"])
            return alias
        digits = re.sub(r"\D", "", phone_number)
        return self._create_alias(
            self._alias_prefix(phone_number),
            name=f"{digits} Via RelaySMS-Mail",
            note="Created by RelaySMS-Mail",
        )

    def _create_random_alias(self) -> AliasResponse:
        with RandomAliasStore(self.credentials.RANDOM_ALIAS_DB_FILENAME) as store:
            for _ in range(RANDOM_ALIAS_ATTEMPTS):
                random_id = secrets.token_hex(self.credentials.RANDOM_ALIAS_ID_BYTES)
                prefix = f"{self.credentials.RANDOM_ALIAS_PREFIX}{random_id}"
                if store.register(prefix):
                    break
            else:
                raise UpstreamError("No unused random alias was found.")
            try:
                return self._create_alias(
                    prefix,
                    name="RelaySMS-Mail No-Reply",
                    note="Created by RelaySMS-Mail No-Reply",
                )
            except Exception:
                store.remove(prefix)
                raise

    def _create_alias(self, prefix: str, *, name: str, note: str) -> AliasResponse:
        mailbox = self.client.fetch_mailbox_by_email(self.credentials.SL_PRIMARY_EMAIL)
        if not mailbox:
            raise UpstreamError(f"No mailbox for {self.credentials.SL_PRIMARY_EMAIL}.")
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S (%Z)")
        return self.client.create_alias(
            alias_prefix=prefix,
            mailbox_id=mailbox["id"],
            hostname=self.credentials.SL_PRIMARY_DOMAIN,
            alias_name=name,
            note=f"{note} at {timestamp}.",
        )


def _expiry(value: object) -> datetime | None:
    """Read Authy's expiry, which is epoch seconds or ISO 8601."""
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, UTC)
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


@contextmanager
def _upstream() -> Iterator[None]:
    """Map SimpleLogin, Authy and SMTP failures to UpstreamError."""
    try:
        yield
    except AdapterError:
        raise
    except (SimpleLoginError, AuthyError, smtplib.SMTPException, OSError) as e:
        raise UpstreamError(str(e)) from e
