from __future__ import annotations

from fastapi import APIRouter, Request

from astro_abm_api.models.asset import MarketSeriesProfile
from astro_abm_api.services.asset_registry import list_available_market_series
from astro_abm_api.services.auth_session import current_user


router = APIRouter()


@router.get("/assets", response_model=list[MarketSeriesProfile])
def list_assets(request: Request) -> list[MarketSeriesProfile]:
    user = current_user(request)
    return list_available_market_series(user.user_id if user else None)
