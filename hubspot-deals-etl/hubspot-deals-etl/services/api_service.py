"""
HubSpot CRM API v3 service.

Handles authentication, pagination, rate limiting, and error handling for the
HubSpot deals endpoint.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Generator

import requests

logger = logging.getLogger(__name__)


class HubSpotAuthenticationError(Exception):
    """Raised when the HubSpot token is invalid or missing required scopes."""


class HubSpotRateLimitError(Exception):
    """Raised when rate limit is hit and retries are exhausted."""


class HubSpotAPIError(Exception):
    """Generic HubSpot API error."""


class HubSpotAPIService:
    """
    Service class for interacting with HubSpot CRM API v3.

    Provides bearer token authentication, cursor-based pagination, rate limit
    handling, token validation, and structured logging.
    """

    BASE_URL = "https://api.hubapi.com"
    DEALS_ENDPOINT = "/crm/v3/objects/deals"
    MAX_RETRIES = 3
    RATE_LIMIT_REQUESTS = 150
    RATE_LIMIT_WINDOW = 10
    DEFAULT_PROPERTIES = [
        "dealname",
        "amount",
        "dealstage",
        "pipeline",
        "closedate",
        "createdate",
        "hs_lastmodifieddate",
        "hubspot_owner_id",
        "description",
        "hs_deal_stage_probability",
        "hs_is_closed",
        "hs_is_closed_won",
        "hs_priority",
    ]

    def __init__(self, access_token: str, timeout: int = 30):
        if not access_token or not access_token.strip():
            raise HubSpotAuthenticationError("HubSpot access token cannot be empty.")

        self.access_token = access_token.strip()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        )
        self._request_count = 0
        self._window_start = time.time()

        logger.info("HubSpotAPIService initialised (timeout=%ds)", timeout)

    def _throttle(self) -> None:
        """Apply a simple client-side rate limit guard."""
        now = time.time()
        elapsed = now - self._window_start
        if elapsed >= self.RATE_LIMIT_WINDOW:
            self._window_start = now
            self._request_count = 0
            return

        if self._request_count >= self.RATE_LIMIT_REQUESTS:
            sleep_for = self.RATE_LIMIT_WINDOW - elapsed
            logger.warning(
                "Client-side HubSpot throttle activated; sleeping for %.2fs",
                sleep_for,
            )
            time.sleep(max(sleep_for, 0))
            self._window_start = time.time()
            self._request_count = 0

    def _request_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Perform a GET request with retries and backoff."""
        backoff = 1
        for attempt in range(1, self.MAX_RETRIES + 1):
            self._throttle()
            self._request_count += 1

            try:
                logger.debug("GET %s params=%s attempt=%d", url, params, attempt)
                response = self.session.get(url, params=params, timeout=self.timeout)

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_for = int(retry_after) if retry_after and retry_after.isdigit() else backoff
                    logger.warning(
                        "Rate limit hit on attempt %d/%d; sleeping %ds",
                        attempt,
                        self.MAX_RETRIES,
                        sleep_for,
                    )
                    if attempt >= self.MAX_RETRIES:
                        raise HubSpotRateLimitError(
                            "Rate limit hit and retries exhausted."
                        )
                    time.sleep(sleep_for)
                    backoff = min(backoff * 2, 60)
                    continue

                if response.status_code in {500, 503, 502, 504}:
                    logger.warning(
                        "HubSpot server error %s on attempt %d/%d; retrying in %ds",
                        response.status_code,
                        attempt,
                        self.MAX_RETRIES,
                        backoff,
                    )
                    if attempt >= self.MAX_RETRIES:
                        raise HubSpotAPIError(
                            f"HubSpot server error {response.status_code} after retries."
                        )
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue

                if response.status_code == 401:
                    raise HubSpotAuthenticationError(
                        "HubSpot token is invalid or expired."
                    )

                if response.status_code == 403:
                    raise HubSpotAuthenticationError(
                        "HubSpot token missing required scope: crm.objects.deals.read"
                    )

                if response.status_code == 400:
                    raise HubSpotAPIError(
                        f"Bad request sent to HubSpot: {response.text[:500]}"
                    )

                raise HubSpotAPIError(
                    f"Unexpected HubSpot response: {response.status_code} - {response.text[:200]}"
                )

            except requests.exceptions.Timeout as exc:
                logger.warning(
                    "HubSpot request timed out on attempt %d/%d",
                    attempt,
                    self.MAX_RETRIES,
                )
                if attempt >= self.MAX_RETRIES:
                    raise HubSpotAPIError(
                        "HubSpot API request timed out after all retries."
                    ) from exc
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

            except requests.exceptions.ConnectionError as exc:
                logger.warning(
                    "HubSpot connection error on attempt %d/%d: %s",
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                )
                if attempt >= self.MAX_RETRIES:
                    raise HubSpotAPIError(f"Cannot connect to HubSpot API: {exc}") from exc
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

        raise HubSpotAPIError("Unexpected retry loop exit.")

    def validate_credentials(self) -> bool:
        """Validate the access token by making a lightweight API call."""
        logger.info("Validating HubSpot credentials")
        url = f"{self.BASE_URL}{self.DEALS_ENDPOINT}"
        data = self._request_json(url, {"limit": 1, "archived": "false"})
        return bool(data)

    def validate_token(self, access_token: str | None = None) -> bool:
        """Backward-compatible wrapper around validate_credentials."""
        if access_token and access_token.strip() and access_token.strip() != self.access_token:
            temp_service = HubSpotAPIService(access_token=access_token.strip(), timeout=self.timeout)
            return temp_service.validate_credentials()
        return self.validate_credentials()

    def get_deals(
        self,
        properties: list[str] | None = None,
        limit: int = 100,
        archived: bool = False,
    ) -> Generator[dict[str, Any], None, None]:
        """Yield all deals from HubSpot using cursor-based pagination."""
        property_list = properties or self.DEFAULT_PROPERTIES
        url = f"{self.BASE_URL}{self.DEALS_ENDPOINT}"
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "properties": ",".join(property_list),
            "archived": str(archived).lower(),
        }

        total_fetched = 0
        page = 0
        logger.info(
            "Starting HubSpot deal extraction (properties=%d, limit=%d)",
            len(property_list),
            limit,
        )

        while True:
            page += 1
            data = self._request_json(url, params)
            results = data.get("results", [])

            if not results:
                logger.info("No more results on page %d; extraction complete", page)
                break

            logger.info(
                "Page %d fetched %d deals (total=%d)",
                page,
                len(results),
                total_fetched + len(results),
            )

            for deal in results:
                total_fetched += 1
                yield deal

            next_cursor = data.get("paging", {}).get("next", {}).get("after")
            if not next_cursor:
                logger.info("Pagination complete. Total deals extracted: %d", total_fetched)
                break

            params["after"] = next_cursor

        logger.info("HubSpot extraction finished. Total records: %d", total_fetched)


# Backward-compatible alias for older imports.
APIService = HubSpotAPIService
