from __future__ import annotations

from fastapi import APIRouter

from astro_abm_api.models.asset import MarketSeriesProfile
from astro_abm_api.services.asset_registry import list_supported_market_series


router = APIRouter()


@router.get("/assets", response_model=list[MarketSeriesProfile])
def list_assets() -> list[MarketSeriesProfile]:
    return list_supported_market_series()
