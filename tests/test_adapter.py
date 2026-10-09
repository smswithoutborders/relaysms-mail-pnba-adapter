# SPDX-License-Identifier: GPL-3.0-only

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from relaysms_adapter_sdk import (
    Account,
    Attachment,
    AuthenticationError,
    CodeRequest,
    CodeVerificationRequest,
    InvalidParamsError,
    Message,
    RevokeRequest,
    SendRequest,
    TokenInvalidError,
    UpstreamError,
)
from relaysms_adapter_sdk.paths import CONFIG_DIR_ENV, STATE_DIR_ENV

from relaysms_mail_pnba_adapter import RelaySMSMailAdapter
from relaysms_mail_pnba_adapter.authy import AuthyError
from relaysms_mail_pnba_adapter.simplelogin import SimpleLoginError

PHONE = "+237600000000"
ALIAS = {"id": 7, "email": "237600000000@relaysms.me", "enabled": True}


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    (tmp_path / "credentials.json").write_text(
        json.dumps(
            {
                "SL_PRIMARY_EMAIL": "box@relaysms.me",
                "SL_PRIMARY_DOMAIN": "relaysms.me",
                "SL_API_KEY": "k",
                "SMTP_HOST": "smtp.example",
                "SMTP_PORT": "587",
                "SMTP_USERNAME": "u",
                "SMTP_PASSWORD": "p",
                "SMTP_USE_TLS": "true",
                "RANDOM_ALIAS_POOL_SIZE": 15,
            }
        )
    )
    adapter = RelaySMSMailAdapter()
    adapter.client = MagicMock()
    adapter.authy = MagicMock()
    adapter.client.fetch_aliases.return_value = [ALIAS]
    adapter.client.fetch_mailbox_by_email.return_value = {"id": 1}
    return adapter


def test_send_code(adapter):
    adapter.authy.generate_otp.return_value = {"expires_at": 1767225600}
    sent = adapter.send_code(CodeRequest(PHONE, channel="wa"))
    assert sent.expires_at == datetime(2026, 1, 1, tzinfo=UTC)
    adapter.authy.generate_otp.assert_called_once_with(
        phone_number=PHONE, platform="wa", sender=None
    )


def test_code_needs_channel(adapter):
    with pytest.raises(InvalidParamsError, match="channel"):
        adapter.send_code(CodeRequest(PHONE))


class TestVerifyCode:
    def test_enables_existing_alias(self, adapter):
        adapter.client.fetch_aliases.return_value = [{**ALIAS, "enabled": False}]
        account = adapter.verify_code(CodeVerificationRequest(PHONE, "1", "wa"))
        assert account == Account(PHONE, name=ALIAS["email"])
        adapter.client.toggle_alias.assert_called_once_with(7)

    def test_creates_alias(self, adapter):
        adapter.client.fetch_aliases.return_value = []
        adapter.client.create_alias.return_value = ALIAS
        adapter.verify_code(CodeVerificationRequest(PHONE, "1", "wa"))
        kwargs = adapter.client.create_alias.call_args.kwargs
        assert kwargs["alias_prefix"] == "237600000000"
        assert kwargs["hostname"] == "relaysms.me"

    def test_wrong_code(self, adapter):
        adapter.authy.verify_otp.side_effect = AuthyError("invalid code")
        with pytest.raises(AuthenticationError):
            adapter.verify_code(CodeVerificationRequest(PHONE, "0", "wa"))


class TestSendMessage:
    def send(self, adapter, account):
        message = Message(
            body="b",
            recipient="you@x.com",
            subject="s",
            attachments=(Attachment(b"%PDF", "a.pdf", "application/pdf"),),
        )
        return adapter.send_message(SendRequest(message, account))

    def test_from_linked_alias(self, adapter):
        self.send(adapter, Account(PHONE))
        kwargs = adapter.client.send_email.call_args.kwargs
        assert kwargs["alias_id"] == 7
        assert kwargs["to_email"] == "you@x.com"
        assert kwargs["attachments"][0].mimetype == "application/pdf"

    def test_disabled_alias(self, adapter):
        adapter.client.fetch_aliases.return_value = [{**ALIAS, "enabled": False}]
        with pytest.raises(TokenInvalidError):
            self.send(adapter, Account(PHONE))

    def test_offline_uses_a_new_random_alias(self, adapter, tmp_path):
        adapter.client.create_alias.return_value = {**ALIAS, "id": 9}
        self.send(adapter, None)
        prefix = adapter.client.create_alias.call_args.kwargs["alias_prefix"]
        assert prefix.startswith("relaysms-")
        assert adapter.client.send_email.call_args.kwargs["alias_id"] == 9
        assert (tmp_path / "state" / "random_aliases.sqlite3").exists()

    def test_upstream_failure(self, adapter):
        adapter.client.send_email.side_effect = SimpleLoginError("down")
        with pytest.raises(UpstreamError, match="down"):
            self.send(adapter, Account(PHONE))


def test_revoke_disables_alias(adapter):
    adapter.revoke(RevokeRequest(Account(PHONE)))
    adapter.client.toggle_alias.assert_called_once_with(7)
