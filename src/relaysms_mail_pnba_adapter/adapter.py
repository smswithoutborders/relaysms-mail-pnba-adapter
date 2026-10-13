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
            api_key=self.credentials.sl_api_key,
            smtp=SMTPConfig(
                host=self.credentials.smtp_host,
                port=self.credentials.smtp_port,
                username=self.credentials.smtp_username,
                password=self.credentials.smtp_password,
                use_tls=self.credentials.smtp_use_tls,
            ),
            base_url=self.credentials.sl_base_url,
        )
        self.authy = AuthyClient(
            base_url=self.credentials.authy_base_url,
            token=self.credentials.authy_token,
        )

    @override
    def send_code(self, request: CodeRequest) -> CodeSent:
        if not request.channel:
            raise InvalidParamsError("A channel is required.")
        with _upstream():
            otp = self.authy.generate_otp(
                phone_number=request.phone_number,
                platform=request.channel,
                sender=self.credentials.authy_sender,
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
                from_email=self.credentials.sl_primary_email,
                to_email=message.recipient,
                subject=message.subject or "",
                body=message.body,
                attachments=attachments,
            )
        return SendResult()

    def _alias_prefix(self, phone_number: str) -> str:
        digits = re.sub(r"\D", "", phone_number)
        return f"{self.credentials.alias_prefix}{digits}{self.credentials.alias_suffix}"

    def _get_alias(self, phone_number: str) -> AliasResponse | None:
        alias = (
            f"{self._alias_prefix(phone_number)}@{self.credentials.sl_primary_domain}"
        )
        aliases = self.client.fetch_aliases(
            query=alias, mailbox_email=self.credentials.sl_primary_email
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
        with RandomAliasStore(self.credentials.random_alias_db_filename) as store:
            for _ in range(RANDOM_ALIAS_ATTEMPTS):
                random_id = secrets.token_hex(self.credentials.random_alias_id_bytes)
                prefix = f"{self.credentials.random_alias_prefix}{random_id}"
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
        mailbox = self.client.fetch_mailbox_by_email(self.credentials.sl_primary_email)
        if not mailbox:
            raise UpstreamError(f"No mailbox for {self.credentials.sl_primary_email}.")
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S (%Z)")
        return self.client.create_alias(
            alias_prefix=prefix,
            mailbox_id=mailbox["id"],
            hostname=self.credentials.sl_primary_domain,
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
