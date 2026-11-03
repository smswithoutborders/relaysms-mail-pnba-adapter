# SPDX-License-Identifier: GPL-3.0-only

import dataclasses
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
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
    manifest,
)
from relaysms_adapter_sdk.paths import CONFIG_DIR_ENV, STATE_DIR_ENV

from relaysms_mail_pnba_adapter import RelaySMSMailAdapter
from relaysms_mail_pnba_adapter.authy import AuthyClient, AuthyError
from relaysms_mail_pnba_adapter.credentials import Credentials
from relaysms_mail_pnba_adapter.httpclient import HTTPError, _handle
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


def test_authy_logs_leave_out_the_phone_number(caplog):
    caplog.set_level(logging.DEBUG)
    authy = AuthyClient("https://authy.example")
    authy._http = MagicMock()
    authy._http.post.return_value = {"expires_at": 1767225600}

    authy.generate_otp(PHONE, "wa")
    authy.verify_otp(PHONE, "wa", "123456")

    assert caplog.records
    assert PHONE not in caplog.text


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, InvalidParamsError),
        (401, UpstreamError),
        (500, UpstreamError),
        (None, UpstreamError),
    ],
)
def test_send_code_maps_authy_status(adapter, status, error):
    adapter.authy.generate_otp.side_effect = AuthyError("rejected", status_code=status)
    with pytest.raises(error, match="rejected"):
        adapter.send_code(CodeRequest(PHONE, channel="wa"))


@pytest.mark.parametrize(
    "call",
    [
        lambda authy: authy.generate_otp(PHONE, "wa"),
        lambda authy: authy.verify_otp(PHONE, "wa", "0"),
        lambda authy: authy.list_platforms(),
    ],
    ids=["generate_otp", "verify_otp", "list_platforms"],
)
def test_authy_keeps_the_status_code(call):
    authy = AuthyClient("https://authy.example")
    authy._http = MagicMock()
    authy._http.post.side_effect = HTTPError("bad number", status_code=400)
    authy._http.get.side_effect = authy._http.post.side_effect
    with pytest.raises(AuthyError, match="bad number") as excinfo:
        call(authy)
    assert excinfo.value.status_code == 400


def test_http_error_keeps_the_status_code():
    response = requests.Response()
    response.status_code = 400
    response._content = b'{"error": "bad number"}'
    with pytest.raises(HTTPError, match="bad number") as excinfo:
        _handle(response)
    assert excinfo.value.status_code == 400


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

    @pytest.mark.parametrize(
        ("status", "error"),
        [
            (400, InvalidParamsError),
            (401, AuthenticationError),
            (429, AuthenticationError),
            (500, UpstreamError),
            (None, UpstreamError),
        ],
    )
    def test_maps_authy_status(self, adapter, status, error):
        adapter.authy.verify_otp.side_effect = AuthyError(
            "rejected", status_code=status
        )
        with pytest.raises(error, match="rejected"):
            adapter.verify_code(CodeVerificationRequest(PHONE, "0", "wa"))

    def test_authy_unreachable(self, adapter):
        adapter.authy.verify_otp.side_effect = requests.ConnectionError("unreachable")
        with pytest.raises(UpstreamError, match="unreachable"):
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


def test_adapter_toml_declares_every_setting():
    declared = manifest.load(Path(__file__).parents[1]).config
    expected = {field.name for field in dataclasses.fields(Credentials)}
    assert {field.name for field in declared} == expected
