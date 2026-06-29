# SPDX-License-Identifier: GPL-3.0-only

from typing import Any, Optional, Union

import requests

from logutils import get_logger

logger = get_logger(__name__)


class HTTPError(Exception):
    """Raised when an HTTP request fails."""


class HTTPClient:
    """Generic HTTP client wrapping a requests.Session.

    Args:
        base_url: Base URL prepended to all request paths.
        headers: Default headers applied to every request.
        timeout: Request timeout in seconds.
    """

    _TIMEOUT: int = 30

    def __init__(
        self,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        timeout: int = _TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        if headers:
            self._session.headers.update(headers)

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def get(self, path: str, **kwargs: Any) -> Any:
        response = self._session.get(self._url(path), timeout=self._timeout, **kwargs)
        return _handle(response)

    def post(self, path: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        response = self._session.post(
            self._url(path), json=payload, timeout=self._timeout, **kwargs
        )
        return _handle(response)

    def delete(self, path: str, **kwargs: Any) -> Any:
        response = self._session.delete(
            self._url(path), timeout=self._timeout, **kwargs
        )
        return _handle(response)


def _handle(response: requests.Response) -> Union[dict[str, Any], list]:
    try:
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, (dict, list)):
            raise HTTPError(f"Unexpected response type: {type(data).__name__}")
        return data
    except requests.exceptions.HTTPError:
        raise HTTPError(_extract_error(response)) from None
    except requests.exceptions.RequestException as e:
        raise HTTPError(str(e)) from e


def _extract_error(response: requests.Response) -> str:
    try:
        return response.json().get("error") or response.text
    except Exception:
        return response.text or f"HTTP {response.status_code}"
