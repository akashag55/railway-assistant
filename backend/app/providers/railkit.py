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


class RailKitProvider:
    """RailKit REST adapter. API key stays on the server."""

    def __init__(self):
        self.base_url = settings.railkit_base_url.rstrip("/")
        self.api_key = settings.railkit_api_key

    async def _get(self, path: str, params: dict | None = None):
        if not self.api_key:
            raise RailKitError("RailKit API key is not configured. Add RAILKIT_API_KEY to backend .env.")
        headers = {"x-api-key": self.api_key, "accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=settings.railway_api_timeout_seconds) as client:
                response = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
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
        except httpx.RequestError as exc:
            raise RailKitError("Could not connect to RailKit. Try again later.", status_code=504) from exc
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
