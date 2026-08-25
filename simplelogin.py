# SPDX-License-Identifier: GPL-3.0-only
"""
SimpleLogin API client with SMTP delivery support.
API docs: https://github.com/simple-login/app/blob/master/docs/api.md
"""

import mimetypes
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any, Optional, TypedDict

from httpclient import HTTPClient, HTTPError
from logutils import get_logger

logger = get_logger(__name__)


class SuffixOption(TypedDict):
    suffix: str
    signed_suffix: str


class SuffixListResponse(TypedDict):
    suffixes: list[SuffixOption]


class MailboxResponse(TypedDict):
    id: int
    email: str


class AliasResponse(TypedDict):
    id: int
    email: str
    enabled: bool
    mailboxes: list[MailboxResponse]


class AliasListResponse(TypedDict):
    aliases: list[AliasResponse]


class MailboxListResponse(TypedDict):
    mailboxes: list[MailboxResponse]


class ContactResponse(TypedDict):
    id: int
    contact: str
    reverse_alias: str
    existed: bool


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True


@dataclass
class Attachment:
    data: bytes
    filename: str
    mimetype: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError(f"Attachment '{self.filename}' has no data.")
        if self.mimetype is None:
            self.mimetype = _detect_mimetype(self.data[:32], self.filename)

    @property
    def maintype(self) -> str:
        return self.mimetype.split("/")[0]

    @property
    def subtype(self) -> str:
        return self.mimetype.split("/")[1]


class SimpleLoginError(Exception):
    """Raised when the SimpleLogin API returns an error or delivery fails."""


class SimpleLoginClient:
    """SimpleLogin API client with integrated SMTP delivery.

    Args:
        api_key: SimpleLogin API key.
        smtp: SMTP configuration for email delivery.
        base_url: API base URL. Defaults to the hosted SimpleLogin instance.
    """

    DEFAULT_BASE_URL: str = "https://app.simplelogin.io/api"

    def __init__(
        self, api_key: str, smtp: SMTPConfig, base_url: str = DEFAULT_BASE_URL
    ) -> None:
        self._smtp = smtp
        self._http = HTTPClient(
            base_url=base_url,
            headers={"Authentication": api_key},
        )

    def fetch_suffix(self, hostname: str) -> Optional[SuffixOption]:
        """Return the signed suffix for ``hostname``, or ``None``."""
        try:
            data: SuffixListResponse = self._http.get(
                f"/v5/alias/options?hostname={hostname}"
            )
        except HTTPError as e:
            raise SimpleLoginError(str(e)) from e

        suffix = next(
            (
                sx
                for sx in data["suffixes"]
                if sx["suffix"].lstrip("@.").endswith(hostname)
            ),
            None,
        )
        logger.debug(
            "Suffix %s for hostname %s.", "found" if suffix else "not found", hostname
        )
        return suffix

    def fetch_aliases(
        self, query: Optional[str] = None, mailbox_email: Optional[str] = None
    ) -> list[AliasResponse]:
        payload: dict[str, Any] = {"query": query} if query else {}
        try:
            data: AliasListResponse = self._http.post("/v2/aliases?page_id=0", payload)
        except HTTPError as e:
            raise SimpleLoginError(str(e)) from e

        logger.debug("Fetched aliases (query=%r).", query)
        aliases: list[AliasResponse] = data.get("aliases", [])

        if not mailbox_email:
            return aliases

        return [
            alias
            for alias in aliases
            if any(
                mb.get("email") == mailbox_email for mb in alias.get("mailboxes", [])
            )
        ]

    def toggle_alias(self, alias_id: int) -> bool:
        """Toggle an alias on/off. Returns the new enabled state."""
        try:
            data = self._http.post(f"/aliases/{alias_id}/toggle", {})
        except HTTPError as e:
            raise SimpleLoginError(str(e)) from e
        logger.debug("Alias ID %s toggled, enabled=%s.", alias_id, data["enabled"])
        return data["enabled"]

    def create_alias(
        self,
        alias_prefix: str,
        mailbox_id: int,
        hostname: str,
        note: Optional[str] = None,
        alias_name: Optional[str] = None,
    ) -> AliasResponse:
        """Create a new alias. Raises ``SimpleLoginError`` if no suffix exists for ``hostname``."""
        suffix = self.fetch_suffix(hostname)
        if suffix is None:
            raise SimpleLoginError(f"No suffix available for hostname '{hostname}'.")

        payload: dict[str, Any] = {
            "alias_prefix": alias_prefix,
            "signed_suffix": suffix["signed_suffix"],
            "mailbox_ids": [mailbox_id],
            "note": note,
            "name": alias_name,
        }
        try:
            alias: AliasResponse = self._http.post("/v3/alias/custom/new", payload)
        except HTTPError as e:
            raise SimpleLoginError(str(e)) from e

        logger.debug("Created alias %s.", alias["email"])
        return alias

    def delete_alias(self, alias_id: int) -> None:
        try:
            self._http.delete(f"/aliases/{alias_id}")
        except HTTPError as e:
            raise SimpleLoginError(str(e)) from e
        logger.debug("Deleted alias ID %s.", alias_id)

    def fetch_mailboxes(self) -> list[MailboxResponse]:
        try:
            data: MailboxListResponse = self._http.get("/mailboxes")
        except HTTPError as e:
            raise SimpleLoginError(str(e)) from e
        logger.debug("Fetched %d mailboxes.", len(data["mailboxes"]))
        return data["mailboxes"]

    def fetch_mailbox_by_email(self, email: str) -> Optional[MailboxResponse]:
        mailbox = next(
            (mb for mb in self.fetch_mailboxes() if mb.get("email") == email),
            None,
        )
        logger.debug("Mailbox %s for %s.", "found" if mailbox else "not found", email)
        return mailbox

    def get_or_create_contact(
        self, alias_id: int, email_address: str
    ) -> ContactResponse:
        try:
            data: ContactResponse = self._http.post(
                f"/aliases/{alias_id}/contacts", {"contact": f"<{email_address}>"}
            )
        except HTTPError as e:
            raise SimpleLoginError(str(e)) from e

        logger.debug(
            "Contact '%s' %s.",
            data["contact"],
            "retrieved" if data["existed"] else "created",
        )
        return data

    def send_email(
        self,
        alias_id: int,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        attachments: Optional[list[Attachment]] = None,
    ) -> None:
        """Send an email via a SimpleLogin alias over SMTP.

        Raises:
            SimpleLoginError: If the reverse-alias cannot be resolved.
            smtplib.SMTPException: If SMTP delivery fails.
        """
        reverse_alias = self.get_or_create_contact(alias_id, to_email)["reverse_alias"]
        logger.debug("Resolved reverse-alias '%s' for %s.", reverse_alias, to_email)

        msg = _build_message(
            from_email=from_email,
            to_email=reverse_alias,
            subject=subject,
            body=body,
            body_html=body_html,
            attachments=attachments or [],
        )
        _deliver(msg, self._smtp)
        logger.debug("Email delivered to %s via %s.", to_email, reverse_alias)


def _detect_mimetype(data: bytes, filename: str) -> str:
    try:
        import magic

        return magic.from_buffer(data, mime=True)
    except ImportError:
        logger.warning(
            "python-magic not installed; falling back to filename extension."
        )
    except Exception:
        pass
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _build_message(
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    body_html: Optional[str],
    attachments: list[Attachment],
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    if body_html:
        msg.set_content(body)
        msg.add_alternative(body_html, subtype="html")
    else:
        msg.set_content(body)

    for att in attachments:
        msg.add_attachment(
            att.data, maintype=att.maintype, subtype=att.subtype, filename=att.filename
        )
        logger.debug("Attached %s (%s).", att.filename, att.mimetype)

    return msg


def _deliver(msg: EmailMessage, smtp: SMTPConfig) -> None:
    context = ssl.create_default_context()
    if smtp.port == 465:
        with smtplib.SMTP_SSL(smtp.host, smtp.port, context=context) as conn:
            conn.login(smtp.username, smtp.password)
            conn.send_message(msg)
    else:
        with smtplib.SMTP(smtp.host, smtp.port) as conn:
            conn.ehlo()
            if conn.has_extn("STARTTLS") or smtp.use_tls:
                conn.starttls(context=context)
                conn.ehlo()
            conn.login(smtp.username, smtp.password)
            conn.send_message(msg)
