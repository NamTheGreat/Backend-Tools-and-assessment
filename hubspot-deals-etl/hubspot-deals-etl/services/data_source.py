"""
DLT data source for HubSpot deals.

Handles extraction, transformation, checkpointing, and metadata injection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

import dlt

from services.api_service import HubSpotAPIService

logger = logging.getLogger(__name__)

DEAL_PROPERTIES = [
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


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO8601 datetime string from HubSpot into UTC datetime."""
    if not value:
        return None

    try:
        if isinstance(value, str) and value.isdigit():
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        logger.warning("Could not parse datetime: %s", value)
        return None


def _parse_decimal(value: str | None) -> float | None:
    """Parse a numeric string from HubSpot into float."""
    if value is None:
        return None

    if isinstance(value, str) and not value.strip():
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning("Could not parse decimal: %s", value)
        return None


def _parse_bool(value: Any) -> bool | None:
    """Parse HubSpot boolean values into Python bool."""
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False

    logger.warning("Could not parse boolean: %s", value)
    return None


def _transform_deal(
    raw_deal: dict[str, Any],
    scan_id: str,
    tenant_id: str,
    extracted_at: datetime,
) -> dict[str, Any]:
    """Transform a raw HubSpot deal into the target database schema."""
    props = raw_deal.get("properties", {})
    raw_probability = _parse_decimal(props.get("hs_deal_stage_probability"))
    probability = round(raw_probability / 100, 4) if raw_probability is not None else None

    return {
        "id": raw_deal["id"],
        "deal_name": props.get("dealname") or "",
        "amount": _parse_decimal(props.get("amount")),
        "deal_stage": props.get("dealstage") or None,
        "pipeline": props.get("pipeline") or None,
        "close_date": _parse_datetime(props.get("closedate")),
        "created_date": _parse_datetime(props.get("createdate")),
        "last_modified_date": _parse_datetime(props.get("hs_lastmodifieddate")),
        "hubspot_owner_id": props.get("hubspot_owner_id") or None,
        "description": props.get("description") or None,
        "deal_stage_probability": probability,
        "is_closed": _parse_bool(props.get("hs_is_closed")),
        "is_closed_won": _parse_bool(props.get("hs_is_closed_won")),
        "priority": props.get("hs_priority") or None,
        "_extracted_at": extracted_at.isoformat(),
        "_scan_id": scan_id,
        "_tenant_id": tenant_id,
    }


class HubSpotDealsDataSource:
    """DLT-compatible data source for HubSpot deals extraction."""

    def __init__(
        self,
        access_token: str,
        scan_id: str,
        tenant_id: str,
        checkpoint_every_n_pages: int = 5,
        limit_per_page: int = 100,
    ) -> None:
        self.api = HubSpotAPIService(access_token=access_token)
        self.scan_id = scan_id
        self.tenant_id = tenant_id
        self.checkpoint_every_n_pages = checkpoint_every_n_pages
        self.limit_per_page = limit_per_page
        self._checkpoint_state: dict[str, Any] = {}

        logger.info(
            "HubSpotDealsDataSource init: scan_id=%s tenant=%s checkpoint_every=%d",
            scan_id,
            tenant_id,
            checkpoint_every_n_pages,
        )

    def validate(self) -> bool:
        """Validate HubSpot credentials before extraction."""
        return self.api.validate_credentials()

    def _save_checkpoint(self, page: int, records_processed: int) -> None:
        """Persist lightweight checkpoint state in memory."""
        self._checkpoint_state = {
            "scan_id": self.scan_id,
            "last_page": page,
            "records_processed": records_processed,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Checkpoint saved: page=%d records=%d", page, records_processed)

    def get_checkpoint(self) -> dict[str, Any]:
        """Return the current checkpoint state."""
        return self._checkpoint_state

    def extract(self) -> Iterator[dict[str, Any]]:
        """Extract, transform, and yield deals from HubSpot."""
        extracted_at = datetime.now(timezone.utc)
        page = 0
        records_processed = 0
        page_buffer: list[dict[str, Any]] = []

        logger.info(
            "Starting extraction: scan_id=%s tenant=%s extracted_at=%s",
            self.scan_id,
            self.tenant_id,
            extracted_at.isoformat(),
        )

        for raw_deal in self.api.get_deals(
            properties=DEAL_PROPERTIES,
            limit=self.limit_per_page,
        ):
            try:
                page_buffer.append(
                    _transform_deal(
                        raw_deal=raw_deal,
                        scan_id=self.scan_id,
                        tenant_id=self.tenant_id,
                        extracted_at=extracted_at,
                    )
                )
                records_processed += 1
            except Exception as exc:
                logger.error(
                    "Failed to transform deal id=%s: %s",
                    raw_deal.get("id", "unknown"),
                    exc,
                )
                continue

            if len(page_buffer) >= self.limit_per_page:
                page += 1
                for record in page_buffer:
                    yield record
                page_buffer = []

                if page % self.checkpoint_every_n_pages == 0:
                    self._save_checkpoint(page, records_processed)

        if page_buffer:
            page += 1
            for record in page_buffer:
                yield record
            self._save_checkpoint(page, records_processed)

        logger.info(
            "Extraction complete: scan_id=%s total_records=%d pages=%d",
            self.scan_id,
            records_processed,
            page,
        )

    def get_resource_config(self) -> dict[str, Any]:
        """Return DLT resource configuration."""
        return {
            "name": "deals",
            "primary_key": "id",
            "write_disposition": "merge",
            "schema": "hubspot_deals",
            "columns": {
                "id": {"data_type": "text", "nullable": False},
                "deal_name": {"data_type": "text", "nullable": False},
                "amount": {"data_type": "decimal", "nullable": True},
                "deal_stage": {"data_type": "text", "nullable": True},
                "pipeline": {"data_type": "text", "nullable": True},
                "close_date": {"data_type": "timestamp", "nullable": True},
                "created_date": {"data_type": "timestamp", "nullable": True},
                "last_modified_date": {"data_type": "timestamp", "nullable": True},
                "hubspot_owner_id": {"data_type": "text", "nullable": True},
                "description": {"data_type": "text", "nullable": True},
                "deal_stage_probability": {"data_type": "decimal", "nullable": True},
                "is_closed": {"data_type": "bool", "nullable": True},
                "is_closed_won": {"data_type": "bool", "nullable": True},
                "priority": {"data_type": "text", "nullable": True},
                "_extracted_at": {"data_type": "timestamp", "nullable": False},
                "_scan_id": {"data_type": "text", "nullable": False},
                "_tenant_id": {"data_type": "text", "nullable": False},
            },
        }


def create_data_source(
    job_config: dict[str, Any],
    auth_config: dict[str, Any],
    filters: dict[str, Any],
    checkpoint_callback: Optional[Callable] = None,
    check_cancel_callback: Optional[Callable] = None,
    check_pause_callback: Optional[Callable] = None,
    resume_from: Optional[dict[str, Any]] = None,
):
    """
    Backward-compatible DLT source factory for HubSpot deals extraction.

    The cancellation and pause callbacks are preserved in the signature so the
    current extraction service can keep calling this function unchanged.
    """

    logger = logging.getLogger(__name__)
    access_token = auth_config.get("accessToken") or auth_config.get("hubspot_access_token")
    if not access_token:
        raise ValueError("No access token found in auth configuration")

    scan_id = filters.get("scan_id") or job_config.get("scanId") or "unknown"
    tenant_id = (
        filters.get("tenant_id")
        or filters.get("organization_id")
        or job_config.get("organizationId")
        or "unknown"
    )
    limit_per_page = int(filters.get("limit_per_page") or job_config.get("limit_per_page") or 100)
    checkpoint_every_n_pages = int(
        filters.get("checkpoint_every_n_pages")
        or job_config.get("checkpoint_every_n_pages")
        or 5
    )

    data_source = HubSpotDealsDataSource(
        access_token=access_token,
        scan_id=scan_id,
        tenant_id=tenant_id,
        checkpoint_every_n_pages=checkpoint_every_n_pages,
        limit_per_page=limit_per_page,
    )

    if resume_from:
        data_source._checkpoint_state = {
            "scan_id": scan_id,
            "resume_from": resume_from,
        }
        logger.info("Resuming extraction from checkpoint: %s", resume_from)

    @dlt.resource(**data_source.get_resource_config())
    def get_main_data() -> Iterator[dict[str, Any]]:
        yield from data_source.extract()

    return [get_main_data]
