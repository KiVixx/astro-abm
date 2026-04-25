from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class QuestDBSettings:
    host: str = "localhost"
    port: int = 8812
    user: str = "admin"
    password: str = "quest"
    database: str = "qdb"


@dataclass(frozen=True)
class MarketDataSettings:
    polygon_api_key: str | None = None
    alpha_vantage_api_key: str | None = None
    lunarcrush_api_key: str | None = None
    default_tradfi_provider: str = "polygon"


def load_questdb_settings() -> QuestDBSettings:
    return QuestDBSettings(
        host=os.getenv("QUESTDB_HOST", "localhost"),
        port=int(os.getenv("QUESTDB_PG_PORT", "8812")),
        user=os.getenv("QUESTDB_USER", "admin"),
        password=os.getenv("QUESTDB_PASSWORD", "quest"),
        database=os.getenv("QUESTDB_DATABASE", "qdb"),
    )


def load_market_data_settings() -> MarketDataSettings:
    return MarketDataSettings(
        polygon_api_key=os.getenv("POLYGON_API_KEY"),
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
        lunarcrush_api_key=os.getenv("LUNARCRUSH_API_KEY"),
        default_tradfi_provider=os.getenv("TRADFI_PROVIDER", "polygon"),
    )
