import asyncio
import re
import time
from collections import deque
from typing import Awaitable, Callable

import httpx
from app.core.config import settings


class RailKitError(Exception):
    """Provider failure with a safe, user-facing message and the HTTP status to return."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _provider_message(response: httpx.Response) -> str | None:
    """RailKit puts its explanation in `error` (or sometimes `message`)."""
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        text = body.get("error") or body.get("message")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


class _WindowLimiter:
    """Process-wide sliding-window limiter shared by every RailKit call."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self._sent: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._sent and now - self._sent[0] >= self.window:
                    self._sent.popleft()
                if len(self._sent) < self.max_requests:
                    self._sent.append(now)
                    return
                await asyncio.sleep(self.window - (now - self._sent[0]) + 0.05)


_limiter = _WindowLimiter(settings.railkit_window_requests, settings.railkit_window_seconds)

# Called after every RailKit request with (endpoint template, HTTP status or None, latency ms).
# Never receives the API key or query values.
RequestHook = Callable[[str, int | None, int], Awaitable[None] | None]

_TEMPLATE_RULES = [
    (re.compile(r"^/api/v1/trains/between/[^/]+/[^/]+$"), "/api/v1/trains/between/{from}/{to}"),
    (re.compile(r"^/api/v1/seats/.+$"), "/api/v1/seats/{train}/{from}/{to}/{date}/{class}/{quota}"),
    (re.compile(r"^/api/v1/trains/[^/]+/info$"), "/api/v1/trains/{train}/info"),
]


def _template(path: str) -> str:
    for pattern, template in _TEMPLATE_RULES:
        if pattern.match(path):
            return template
    return path


class RailKitProvider:
    """RailKit REST adapter. API key stays on the server."""

    MAX_RATE_LIMIT_RETRIES = 3

    def __init__(self, on_request: RequestHook | None = None):
        self.base_url = settings.railkit_base_url.rstrip("/")
        self.api_key = settings.railkit_api_key
        self.on_request = on_request

    async def _notify(self, path: str, status: int | None, started: float) -> None:
        if self.on_request is None:
            return
        result = self.on_request(_template(path), status, int((time.monotonic() - started) * 1000))
        if asyncio.iscoroutine(result):
            await result

    async def _get(self, path: str, params: dict | None = None):
        if not self.api_key:
            raise RailKitError("RailKit API key is not configured. Add RAILKIT_API_KEY to backend .env.", status_code=503)
        headers = {"x-api-key": self.api_key, "accept": "application/json"}
        for attempt in range(self.MAX_RATE_LIMIT_RETRIES + 1):
            await _limiter.acquire()
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=settings.railway_api_timeout_seconds) as client:
                    response = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
            except httpx.RequestError as exc:
                await self._notify(path, None, started)
                raise RailKitError("Could not connect to RailKit. Try again later.", status_code=504) from exc
            await self._notify(path, response.status_code, started)

            if response.status_code == 429 and attempt < self.MAX_RATE_LIMIT_RETRIES:
                try:
                    wait = float(response.headers.get("retry-after") or response.headers.get("ratelimit-reset") or 2)
                except ValueError:
                    wait = 2.0
                await asyncio.sleep(min(max(wait, 1.0), 60.0) * (attempt + 1))
                continue
            break

        try:
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = _provider_message(exc.response)
            if status in (401, 403):
                raise RailKitError(
                    "RailKit refused the request (HTTP %d): %s"
                    % (status, detail or "the API key is invalid or this plan does not allow this endpoint."),
                    status_code=503,
                ) from exc
            if status == 400:
                # RailKit gives no detail here; the usual causes are below.
                raise RailKitError(
                    f"RailKit could not process this request ({detail or 'HTTP 400'}). "
                    "Check that the train runs on this date, stops at both stations, and offers this class.",
                    status_code=400,
                ) from exc
            if status == 429:
                raise RailKitError("RailKit rate limit reached. Wait before retrying.", status_code=429) from exc
            raise RailKitError(
                f"RailKit returned HTTP {status}" + (f": {detail}" if detail else "."),
            ) from exc
        except ValueError as exc:
            raise RailKitError("RailKit returned a response that is not valid JSON.") from exc

        if isinstance(data, dict) and data.get("success") is False:
            raise RailKitError(
                data.get("error") or data.get("message") or "RailKit could not complete the request."
            )
        return data

    async def search_trains(self, from_code: str, to_code: str, date: str | None):
        path = f"/api/v1/trains/between/{from_code}/{to_code}"
        params = {"date": date} if date else None
        return await self._get(path, params)

    async def availability(
        self, train_no: str, from_code: str, to_code: str,
        date: str, travel_class: str, quota: str
    ):
        path = (
            f"/api/v1/seats/{train_no}/{from_code}/{to_code}/"
            f"{date}/{travel_class}/{quota}"
        )
        return await self._get(path)

    async def train_info(self, train_no: str):
        """Train details and full stop list (`data.trainInfo`, `data.route`)."""
        return await self._get(f"/api/v1/trains/{train_no}/info")
