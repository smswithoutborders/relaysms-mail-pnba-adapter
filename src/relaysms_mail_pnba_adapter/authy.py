# SPDX-License-Identifier: GPL-3.0-only
"""
Shortmesh Authy API client.
API docs: https://github.com/shortmesh/Authy-API/blob/main/docs/USAGE.md
"""

import logging
from http import HTTPStatus
from typing import TypedDict

from relaysms_mail_pnba_adapter.httpclient import HTTPClient, HTTPError

logger = logging.getLogger(__name__)


class OTPResponse(TypedDict):
    message: str
    expires_at: str


class VerifyResponse(TypedDict):
    message: str


class PlatformResponse(TypedDict):
    platform: str
    device_id: str


class AuthyError(HTTPError):
    """Raised when the Authy API returns an error or request fails."""


class AuthyClient:
    """Shortmesh Authy API client for OTP generation, delivery, and verification.

    Args:
        base_url: Authy API base URL.
        token: Optional Matrix Bearer token. When provided, authenticates requests
               and enables the ``sender`` field on OTP generation.
    """

    def __init__(self, base_url: str, token: str | None = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = HTTPClient(base_url=base_url, headers=headers)

    def generate_otp(
        self,
        phone_number: str,
        platform: str,
        sender: str | None = None,
    ) -> OTPResponse:
        """Request an OTP be sent to ``phone_number`` on ``platform``.

        Args:
            phone_number: Recipient phone number in E.164 format.
            platform: Platform identifier (e.g. ``"wa"`` for WhatsApp).
            sender: Specific device to send from. Only effective when authenticated.

        Raises:
            AuthyError: If the request fails.
        """
        payload: dict = {"phone_number": phone_number, "platform": platform}
        if sender:
            payload["sender"] = sender

        try:
            data: OTPResponse = self._http.post("/api/v1/otp/generate", payload)
        except HTTPError as e:
            raise _authy_error(e, phone_number) from e

        logger.debug("OTP sent via %s, expires at %s.", platform, data["expires_at"])
        return data

    def verify_otp(
        self,
        phone_number: str,
        platform: str,
        code: str,
    ) -> VerifyResponse:
        """Verify an OTP code for ``phone_number``.

        Raises:
            AuthyError: If the request fails or the code is invalid/expired.
        """
        try:
            data: VerifyResponse = self._http.post(
                "/api/v1/otp/verify",
                {"phone_number": phone_number, "platform": platform, "code": code},
            )
        except HTTPError as e:
            raise _authy_error(e, phone_number) from e

        logger.debug("OTP verified.")
        return data

    def list_platforms(self) -> list[PlatformResponse]:
        """Return available platforms and their associated device IDs."""
        try:
            data = self._http.get("/api/v1/platforms")
        except HTTPError as e:
            raise AuthyError(str(e), status_code=e.status_code) from e

        logger.debug("Fetched %d platforms.", len(data))
        return data


def _authy_error(e: HTTPError, phone_number: str) -> AuthyError:
    """Wrap ``e``, logging ``phone_number`` masked if Authy answered 400."""
    if e.status_code == HTTPStatus.BAD_REQUEST:
        logger.warning("Authy rejected the request for %s: %s", _mask(phone_number), e)
    return AuthyError(str(e), status_code=e.status_code)


def _mask(phone_number: str) -> str:
    """Mask all but a phone number's first four and last two digits.

    Punctuation is kept and the digit count added. A number with fewer than 8
    digits is masked in full.
    """
    digits = sum(c.isdigit() for c in phone_number)
    masked = []
    position = 0
    for c in phone_number:
        if c.isdigit():
            if digits < 8 or 4 <= position < digits - 2:
                c = "x"
            position += 1
        masked.append(c)
    return f"{''.join(masked)} ({digits} digits)"
