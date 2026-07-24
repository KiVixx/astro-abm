from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, status

from astro_abm.market_series import (
    MarketSeriesConflictError,
    MarketSeriesNotFoundError,
    MarketSeriesStore,
    MarketSeriesValidationError,
    refresh_market_series,
)
from astro_abm_api.models.asset import (
    CustomMarketSeriesCreateRequest,
    CustomMarketSeriesRecord,
    CustomMarketSeriesUpdateRequest,
    MarketSeriesListResponse,
    MarketSeriesRefreshResponse,
)
from astro_abm_api.services.asset_registry import list_supported_market_series
from astro_abm_api.services.auth_session import (
    current_user,
    require_csrf,
    require_current_user,
)
from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.usage_limits import enforce_market_series_operation


router = APIRouter(prefix="/market-series", tags=["market-series"])


@router.get("", response_model=MarketSeriesListResponse)
def list_market_series(request: Request) -> MarketSeriesListResponse:
    user = current_user(request)
    records = MarketSeriesStore().list_visible(user.user_id if user else None)
    return MarketSeriesListResponse(
        built_in=list_supported_market_series(),
        custom=[_public_record(item) for item in records],
    )


@router.post(
    "",
    response_model=CustomMarketSeriesRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_market_series(
    payload: CustomMarketSeriesCreateRequest,
    request: Request,
) -> CustomMarketSeriesRecord:
    user = require_current_user(request)
    require_csrf(request)
    enforce_market_series_operation(
        request,
        AuthStore(),
        user_id=user.user_id,
        operation="register",
    )
    store = MarketSeriesStore()
    existing_count = sum(item.is_owner for item in store.list_visible(user.user_id))
    quota = _bounded_env("ASTRO_ABM_USER_MARKET_SERIES_QUOTA", 25, 1, 250)
    if existing_count >= quota:
        raise HTTPException(status_code=429, detail="market series quota reached")
    try:
        record = store.register(
            owner_id=user.user_id,
            symbol=payload.symbol,
            label=payload.label,
            asset_type=payload.asset_type,
            provider=payload.provider,
            provider_symbol=payload.provider_symbol,
            currency=payload.currency,
            market_timezone=payload.market_timezone,
            visibility=payload.visibility,
            maintenance_enabled=payload.maintenance_enabled,
        )
    except MarketSeriesConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except MarketSeriesValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _public_record(record)


@router.patch("/{series_id}", response_model=CustomMarketSeriesRecord)
def update_market_series(
    series_id: str,
    payload: CustomMarketSeriesUpdateRequest,
    request: Request,
) -> CustomMarketSeriesRecord:
    user = require_current_user(request)
    require_csrf(request)
    try:
        record = MarketSeriesStore().update_subscription(
            series_id,
            user.user_id,
            enabled=payload.enabled,
            maintenance_enabled=payload.maintenance_enabled,
            visibility=payload.visibility,
        )
    except MarketSeriesNotFoundError as error:
        raise HTTPException(status_code=404, detail="market series not found") from error
    except MarketSeriesValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _public_record(record)


@router.delete("/{series_id}")
def delete_market_series(series_id: str, request: Request) -> dict[str, object]:
    user = require_current_user(request)
    require_csrf(request)
    try:
        MarketSeriesStore().delete_subscription(series_id, user.user_id)
    except MarketSeriesNotFoundError as error:
        raise HTTPException(status_code=404, detail="market series not found") from error
    return {
        "series_id": series_id,
        "deleted": True,
        "price_history_retained": True,
    }


@router.post(
    "/{series_id}/validate",
    response_model=MarketSeriesRefreshResponse,
)
def validate_market_series(
    series_id: str,
    request: Request,
) -> MarketSeriesRefreshResponse:
    return _refresh_owned_series(series_id, request, operation="validate")


@router.post(
    "/{series_id}/refresh",
    response_model=MarketSeriesRefreshResponse,
)
def refresh_owned_market_series(
    series_id: str,
    request: Request,
) -> MarketSeriesRefreshResponse:
    return _refresh_owned_series(series_id, request, operation="refresh")


def _refresh_owned_series(
    series_id: str,
    request: Request,
    *,
    operation: str,
) -> MarketSeriesRefreshResponse:
    user = require_current_user(request)
    require_csrf(request)
    store = MarketSeriesStore()
    try:
        store.get_for_owner(series_id, user.user_id)
    except MarketSeriesNotFoundError as error:
        raise HTTPException(status_code=404, detail="market series not found") from error
    enforce_market_series_operation(
        request,
        AuthStore(),
        user_id=user.user_id,
        operation=operation,
    )
    result = refresh_market_series(store, series_id, attempts=1)
    record = store.get_for_owner(series_id, user.user_id)
    return MarketSeriesRefreshResponse(
        series=_public_record(record),
        status=result.status,
        fetched_rows=result.fetched_rows,
        rows_written=result.rows_written,
        attempts=result.attempts,
        adopted_existing=result.adopted_existing,
        errors=list(result.errors),
    )


def _public_record(record) -> CustomMarketSeriesRecord:  # type: ignore[no-untyped-def]
    values = record.to_dict()
    values.pop("owner_id", None)
    values.pop("data_path", None)
    return CustomMarketSeriesRecord.model_validate(values)


def _bounded_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))
