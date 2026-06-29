# SPDX-License-Identifier: GPL-3.0-only
"""
Shortmesh Authy API client.
API docs: https://github.com/shortmesh/Authy-API/blob/main/docs/USAGE.md
"""

from typing import Optional, TypedDict

from httpclient import HTTPClient, HTTPError
from logutils import get_logger

logger = get_logger(__name__)


class OTPResponse(TypedDict):
    message: str
    expires_at: str


class VerifyResponse(TypedDict):
    message: str


class PlatformResponse(TypedDict):
    platform: str
    device_id: str


class AuthyError(Exception):
    """Raised when the Authy API returns an error or request fails."""


class AuthyClient:
    """Shortmesh Authy API client for OTP generation, delivery, and verification.

    Args:
        base_url: Authy API base URL.
        token: Optional Matrix Bearer token. When provided, authenticates requests
               and enables the ``sender`` field on OTP generation.
    """

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = HTTPClient(base_url=base_url, headers=headers)

    def generate_otp(
        self,
        phone_number: str,
        platform: str,
        sender: Optional[str] = None,
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
            raise AuthyError(str(e)) from e

        logger.debug(
            "OTP sent to %s, via %s, expires_at %s.",
            phone_number,
            platform,
            data["expires_at"],
        )
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
            raise AuthyError(str(e)) from e

        logger.debug("OTP verified for %s.", phone_number)
        return data

    def list_platforms(self) -> list[PlatformResponse]:
        """Return available platforms and their associated device IDs."""
        try:
            data = self._http.get("/api/v1/platforms")
        except HTTPError as e:
            raise AuthyError(str(e)) from e

        logger.debug("Fetched %d platforms.", len(data))
        return data
